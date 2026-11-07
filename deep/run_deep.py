#!/usr/bin/env python3
"""
deep/run_deep.py — Phase 1c of /jobhunter scan: the "deep layer".

Harvests sources the script layer misses — LinkedIn guest search API,
jobs.ch public search API, company ATS boards (Workday CXS, SmartRecruiters,
Greenhouse, Lever, Ashby) — then funnels them through
`scan_aggregate.py --inject` (same recency/title/location/blacklist/dedup
funnel, same pipeline.md + scan-history.tsv writer).

WHY IT EXISTS: on 2026-11-06 the scan agent rebuilt these harvesters in
/private/tmp from old transcripts, launched them in the background, ended its
turn waiting on a Monitor, and never woke up. This is the in-repo,
foreground, deadline-bounded version. It is ONE blocking command:

    {PYTHON} deep/run_deep.py [--deadline-seconds 300] [--days 7] [--dry-run]

Every step checks the overall deadline between requests, and every request
has its own timeout <= the time left, so the wall time is bounded by
deadline + one request timeout (<= 15 s). Never run it in the background.

Config: deep/boards.yml. Selftest (fixtures only, no network): --selftest.
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_ROOT = _os.path.dirname(_HERE)
for _v in (_os.path.join(_os.path.dirname(_ROOT), ".venv", "bin", "python3"),
           _os.path.join(_ROOT, ".venv", "bin", "python3")):
    if _os.path.exists(_v) and _os.path.realpath(_sys.executable) != _os.path.realpath(_v):
        _os.execv(_v, [_v] + _sys.argv)
        break

import argparse
import concurrent.futures as cf
import datetime
import html
import json
import re
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

import yaml

HERE = Path(_HERE)
ROOT = Path(_ROOT)
sys.path.insert(0, str(ROOT))

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/130.0 Safari/537.36")
REQ_TIMEOUT = 15
DEFAULT_DEADLINE = 300
# per-step caps (seconds); each is further cut to what the overall deadline leaves
STEP_CAPS = {"linkedin": 110, "linkedin-detail": 45, "jobsch": 60, "ats": 70}
INJECT_RESERVE = 20  # seconds kept back for the scan_aggregate --inject funnel

CH = re.compile(
    r"switzerland|schweiz|suisse|z[uü]rich|zug|baar|basel|bern|winterthur|luzern|lucerne|"
    r"aarau|baden|st\.? ?gallen|schaffhausen|rotkreuz|cham|dietikon|kloten|opfikon|"
    r"wallisellen|dübendorf|reinach|allschwil|uster|schlieren|pfäffikon|steinhausen|"
    r"thalwil|horgen|risch|olten|solothurn|zofingen|kaiseraugst|muttenz|pratteln|"
    r"wetzikon|frauenfeld|rapperswil|sursee|\bCH\b", re.I)


# ── budget ────────────────────────────────────────────────────────────────
class Budget:
    """Overall deadline + per-step caps. `left(step)` is what a step may still use."""

    def __init__(self, deadline, clock=time.monotonic):
        self.clock, self.t0, self.deadline = clock, clock(), float(deadline)
        self.step_end = float("inf")
        self.hit = False

    def total_left(self):
        return max(0.0, self.deadline - (self.clock() - self.t0))

    def start(self, step):
        cap = STEP_CAPS.get(step, 60)
        self.step_end = self.clock() + min(cap, max(0.0, self.total_left() - INJECT_RESERVE))

    def left(self):
        return max(0.0, min(self.step_end - self.clock(), self.total_left() - INJECT_RESERVE))

    def ok(self, need=2.0):
        if self.left() > need:
            return True
        self.hit = True
        return False

    def timeout(self):
        return max(1.0, min(REQ_TIMEOUT, self.left()))


def _get(url, budget, data=None, accept="text/html"):
    hdr = {"User-Agent": UA, "Accept": accept, "Accept-Language": "en-US,en;q=0.9"}
    if data is not None:
        hdr["Content-Type"] = "application/json"
        data = json.dumps(data).encode()
    req = urllib.request.Request(url, data=data, headers=hdr)
    with urllib.request.urlopen(req, timeout=budget.timeout()) as r:
        return r.read().decode("utf-8", "replace")


def _text(fragment):
    return html.unescape(re.sub(r"<[^>]+>", "", fragment or "")).strip()


# ── parsers (pure; covered by --selftest) ─────────────────────────────────
def parse_li_cards(page):
    """LinkedIn guest seeMoreJobPostings HTML -> rows."""
    out = []
    for c in page.split("<li"):
        m = re.search(r'href="(https://[a-z]+\.linkedin\.com/jobs/view/[^"?]+)', c)
        if not m:
            continue
        jid = re.search(r"(\d{8,})/?$", m.group(1)) or re.search(r"(\d{8,})", m.group(1))
        if not jid:
            continue
        g = lambda p: _text((re.search(p, c, re.S) or [None, ""])[1])  # noqa: E731
        out.append({
            "title": g(r'base-search-card__title">(.*?)</h3>'),
            "company": g(r'base-search-card__subtitle">(.*?)</h4>'),
            "location": g(r'job-search-card__location">(.*?)</span>'),
            "date_posted": (re.search(r'datetime="([\d-]+)"', c) or [None, ""])[1],
            "url": f"https://www.linkedin.com/jobs/view/{jid.group(1)}",
            "source": "linkedin-guest"})
    return out


def parse_li_detail(page):
    """LinkedIn guest jobPosting HTML -> {'closed': bool, 'applicants': '37'|'200+'|''}.

    Only what the page states: "37 applicants" -> '37', "Over 200 applicants"
    -> '200+'. "Be among the first 25 applicants" -> '<25'. Nothing -> ''.
    """
    closed = "No longer accepting applications" in page
    m = re.search(r'num-applicants__caption[^>]*>(.*?)</', page, re.S)
    cap = _text(m.group(1)) if m else ""
    applicants = ""
    n = re.search(r"(\d[\d,']*)\s+applicants?", cap, re.I)
    if n:
        num = re.sub(r"\D", "", n.group(1))
        if re.search(r"\bover\b|\bmore than\b", cap, re.I):
            applicants = f"{num}+"
        elif re.search(r"\bfirst\b", cap, re.I):
            applicants = f"<{num}"
        else:
            applicants = num
    return {"closed": closed, "applicants": applicants}


def jobsch_rows(doc, cutoff):
    """jobs.ch /api/v1/public/search JSON -> (rows newer than cutoff and active, n_old)."""
    rows, old = [], 0
    for x in doc.get("documents", []):
        ini = (x.get("initial_publication_date") or x.get("publication_date") or "")[:10]
        if ini and ini < cutoff:
            old += 1
            continue
        if x.get("is_active") is False:
            continue
        rows.append({"title": x.get("title") or "", "company": x.get("company_name") or "",
                     "location": x.get("place") or "", "date_posted": ini,
                     "url": f"https://www.jobs.ch/en/vacancies/detail/{x.get('job_id')}/",
                     "source": "jobsch-api"})
    return rows, old


def wd_posted(text, today):
    """Workday 'Posted Today' / 'Posted Yesterday' / 'Posted 3 Days Ago' /
    'Posted 30+ Days Ago' -> ISO date ('' if unparseable)."""
    t = (text or "").lower()
    if "today" in t:
        d = 0
    elif "yesterday" in t:
        d = 1
    else:
        m = re.search(r"(\d+)\+?\s*days?", t)
        if not m:
            return ""
        d = int(m.group(1))
    return (today - datetime.timedelta(days=d)).isoformat()


def wd_ch_facets(facets):
    """Workday facets tree -> {facetParameter: [ids]} for Switzerland values."""
    fac = {}
    def walk(fs):
        for f in fs:
            for v in f.get("values", []):
                if "values" in v:
                    walk([v])
                elif re.search(r"switzerland|schweiz", v.get("descriptor", ""), re.I):
                    fac.setdefault(f.get("facetParameter", ""), []).append(v["id"])
    walk(facets or [])
    return fac


def sr_rows(c, d):
    out = []
    for p in d.get("content", []):
        loc = p.get("location", {}) or {}
        out.append({"title": p.get("name") or "", "company": (p.get("company") or {}).get("name", c),
                    "location": f"{loc.get('city', '')}, {loc.get('country', '')}".strip(", "),
                    "date_posted": (p.get("releasedDate") or "")[:10],
                    "url": f"https://jobs.smartrecruiters.com/{c}/{p['id']}", "source": "smartrecruiters"})
    return out


def gh_rows(b, d):
    return [{"title": j.get("title") or "", "company": b,
             "location": (j.get("location") or {}).get("name", ""),
             "date_posted": (j.get("first_published") or j.get("updated_at") or "")[:10],
             "url": j["absolute_url"], "source": "greenhouse"}
            for j in d.get("jobs", []) if CH.search((j.get("location") or {}).get("name", ""))]


def lv_rows(b, d):
    return [{"title": j.get("text") or "", "company": b,
             "location": (j.get("categories") or {}).get("location", ""),
             "date_posted": time.strftime("%Y-%m-%d", time.gmtime((j.get("createdAt") or 0) / 1000)),
             "url": j["hostedUrl"], "source": "lever"}
            for j in d if CH.search((j.get("categories") or {}).get("location", "") or "")]


def ab_rows(b, d):
    def ch(j):
        return CH.search(j.get("location") or "") or any(
            CH.search(x.get("location") or "") for x in (j.get("secondaryLocations") or []))
    return [{"title": j.get("title") or "", "company": b, "location": j.get("location") or "",
             "date_posted": (j.get("publishedAt") or "")[:10], "url": j["jobUrl"], "source": "ashby"}
            for j in d.get("jobs", []) if ch(j)]


# ── harvesters (network) ──────────────────────────────────────────────────
def harvest_linkedin(cfg, queries, days, budget, log):
    li = cfg.get("linkedin") or {}
    out = []
    for q in queries:
        if not budget.ok(4):
            log(f"deadline: linkedin stopped before '{q}'")
            break
        u = ("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?"
             + urllib.parse.urlencode({"keywords": q, "location": li.get("location", "Switzerland"),
                                       "distance": li.get("distance_km", 50),
                                       "f_TPR": f"r{int(days) * 86400}", "start": 0}))
        try:
            out += parse_li_cards(_get(u, budget))
        except urllib.error.HTTPError as e:
            log(f"linkedin {q}: HTTP {e.code}")
            if e.code == 429:  # rate-limited: the rest would fail too
                log("linkedin: 429, stopping LinkedIn search (best-effort source)")
                break
        except Exception as e:  # noqa: BLE001
            log(f"linkedin {q}: {e}")
        time.sleep(1.5)
    return out


def enrich_linkedin(rows, cfg, budget, log, keep):
    """Fetch detail pages for up to linkedin.detail_max rows that `keep` accepts:
    drop closed postings, attach `applicants` when LinkedIn states it."""
    maxn = int((cfg.get("linkedin") or {}).get("detail_max", 30))
    done = closed = 0
    for j in rows:
        if done >= maxn or not keep(j):
            continue
        if not budget.ok(4):
            log("deadline: linkedin detail fetch stopped")
            break
        jid = j["url"].rstrip("/").rsplit("/", 1)[1]
        try:
            d = parse_li_detail(_get(
                f"https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/{jid}", budget))
        except urllib.error.HTTPError as e:
            log(f"linkedin detail {jid}: HTTP {e.code}")
            if e.code == 429:
                break
            continue
        except Exception as e:  # noqa: BLE001
            log(f"linkedin detail {jid}: {e}")
            continue
        done += 1
        if d["closed"]:
            j["_closed"] = True
            closed += 1
        if d["applicants"]:
            j["applicants"] = d["applicants"]
        time.sleep(1.5)
    log(f"linkedin detail: fetched={done} closed={closed} "
        f"with_applicants={sum(1 for j in rows if j.get('applicants'))}")
    return [j for j in rows if not j.get("_closed")]


def harvest_jobsch(cfg, queries, cutoff, budget, log):
    js = cfg.get("jobsch") or {}
    out = []
    for q in queries:
        for page in range(1, int(js.get("max_pages", 2)) + 1):
            if not budget.ok(2):
                log(f"deadline: jobs.ch stopped at '{q}'")
                return out
            u = "https://www.jobs.ch/api/v1/public/search?" + urllib.parse.urlencode(
                {"query": q, "location": js.get("location", "Zürich"), "rows": 20,
                 "page": page, "sort": "date"})
            try:
                doc = json.loads(_get(u, budget, accept="application/json"))
            except Exception as e:  # noqa: BLE001
                log(f"jobs.ch {q}: {e}")
                break
            rows, old = jobsch_rows(doc, cutoff)
            out += rows
            n = len(doc.get("documents", []))
            if not n or old == n or page >= doc.get("num_pages", 1):
                break
            time.sleep(0.5)
    return out


def harvest_ats(cfg, cutoff, today, budget, log):
    fails = []

    def wd(spec):
        t, inst, site = spec.split("|")
        base = f"https://{t}.{inst}.myworkdayjobs.com"
        api = f"{base}/wday/cxs/{t}/{site}/jobs"
        got = {}
        try:
            fac = wd_ch_facets(json.loads(_get(api, budget, {"appliedFacets": {}, "limit": 1,
                                                             "offset": 0, "searchText": ""},
                                               "application/json")).get("facets"))
        except Exception as e:  # noqa: BLE001
            fails.append(f"{t}: {str(e)[:60]}")
            return []
        for kw in cfg.get("workday_keywords") or []:
            if not budget.ok(2):
                break
            try:
                r = json.loads(_get(api, budget, {"appliedFacets": fac, "limit": 20, "offset": 0,
                                                  "searchText": kw}, "application/json"))
            except Exception as e:  # noqa: BLE001
                fails.append(f"{t}/{kw}: {str(e)[:60]}")
                break
            for p in r.get("jobPostings", []):
                loc = p.get("locationsText", "")
                if not fac and not CH.search(loc) and not CH.search(p.get("externalPath", "")):
                    continue
                got[p["externalPath"]] = {
                    "title": p.get("title") or "", "company": t, "location": loc,
                    "date_posted": wd_posted(p.get("postedOn"), today),
                    "url": f"{base}/en-US/{site}{p['externalPath']}", "source": "workday-cxs"}
        return list(got.values())

    def fetch(fn, url, b):
        if not budget.ok(2):
            return []
        try:
            return fn(b, json.loads(_get(url, budget, accept="application/json")))
        except Exception as e:  # noqa: BLE001
            if "404" not in str(e):
                fails.append(f"{b}: {str(e)[:60]}")
            return []

    jobs = [(wd, (s,)) for s in cfg.get("workday") or []]
    jobs += [(fetch, (sr_rows, "https://api.smartrecruiters.com/v1/companies/"
                      f"{urllib.parse.quote(c)}/postings?country=ch&limit=100", c))
             for c in cfg.get("smartrecruiters") or []]
    jobs += [(fetch, (gh_rows, f"https://boards-api.greenhouse.io/v1/boards/{b}/jobs", b))
             for b in cfg.get("greenhouse") or []]
    jobs += [(fetch, (lv_rows, f"https://api.lever.co/v0/postings/{b}?mode=json", b))
             for b in cfg.get("lever") or []]
    jobs += [(fetch, (ab_rows, f"https://api.ashbyhq.com/posting-api/job-board/{b}", b))
             for b in cfg.get("ashby") or []]
    out = []
    ex = cf.ThreadPoolExecutor(12)
    futs = [ex.submit(fn, *a) for fn, a in jobs]
    try:
        for f in cf.as_completed(futs, timeout=budget.left() + REQ_TIMEOUT):
            out += f.result()
    except cf.TimeoutError:
        budget.hit = True
        log("deadline: ats harvest cut off, keeping what finished")
    ex.shutdown(wait=False, cancel_futures=True)
    if fails:
        log(f"ats failures ({len(fails)}): {'; '.join(fails[:8])}")
    aliases = cfg.get("aliases") or {}
    for j in out:
        j["company"] = aliases.get(j["company"], j["company"])
    return [j for j in out if not j["date_posted"] or j["date_posted"] >= cutoff]


# ── orchestration ─────────────────────────────────────────────────────────
def default_queries(profile):
    terms = ((profile.get("jobspy") or {}).get("search_terms") or [])
    return [re.sub(r"\s+(switzerland|schweiz|suisse)$", "", t, flags=re.I) for t in terms]


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--deadline-seconds", type=float, default=None,
                    help=f"overall budget (default: profile.yml scan.deep_deadline_seconds, else {DEFAULT_DEADLINE})")
    ap.add_argument("--days", type=int, default=7, help="posting age window (default 7)")
    ap.add_argument("--only", help="comma list of steps: linkedin,jobsch,ats")
    ap.add_argument("--dry-run", action="store_true", help="harvest + funnel report, write nothing")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--selftest", action="store_true", help="parser fixtures only, no network")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    def log(msg):
        print(f"  [deep] {msg}", file=sys.stderr, flush=True)

    cfg = yaml.safe_load((HERE / "boards.yml").read_text()) or {}
    import scan_aggregate as sa
    portals, profile, pos, neg, allow, block = sa.load_cfgs()
    deadline = args.deadline_seconds if args.deadline_seconds is not None else \
        (profile.get("scan") or {}).get("deep_deadline_seconds", DEFAULT_DEADLINE)
    budget = Budget(deadline)
    today = datetime.date.fromisoformat(args.date)
    cutoff = (today - datetime.timedelta(days=args.days)).isoformat()
    queries = cfg.get("queries") or default_queries(profile)
    steps = set((args.only or "linkedin,jobsch,ats").split(","))
    seen, _ = sa.load_history()

    def worth_detail(j):  # same first gates as the funnel, so detail calls go to survivors
        return (j["url"] not in seen and sa.title_bucket(j["title"], pos, neg) != "drop"
                and sa.location_ok(j["location"], allow, block))

    rows, counts = [], {}
    if "linkedin" in steps:
        budget.start("linkedin")
        li = harvest_linkedin(cfg, queries, args.days, budget, log)
        uniq = list({j["url"]: j for j in li}.values())
        budget.start("linkedin-detail")
        rows += enrich_linkedin(uniq, cfg, budget, log, worth_detail)
        counts["linkedin"] = len(uniq)
    if "jobsch" in steps:
        budget.start("jobsch")
        got = harvest_jobsch(cfg, queries, cutoff, budget, log)
        rows += got
        counts["jobsch"] = len(got)
    if "ats" in steps:
        budget.start("ats")
        got = harvest_ats(cfg, cutoff, today, budget, log)
        rows += got
        counts["ats"] = len(got)
    rows = list({j["url"]: j for j in rows if j.get("url")}.values())
    log(f"harvest: {counts} unique={len(rows)} elapsed={int(budget.clock() - budget.t0)}s")

    if not rows:
        print(f"deep: raw=0 elapsed={int(budget.clock() - budget.t0)}s "
              f"deadline_hit={'yes' if budget.hit else 'no'} (nothing to inject)")
        sys.exit(1)
    out = ROOT / "data" / "cache" / f"deep-{args.date}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(rows, ensure_ascii=False, indent=0))
    cmd = [sys.executable, str(ROOT / "scan_aggregate.py"), "--inject", str(out),
           "--date", args.date] + (["--dry-run"] if args.dry_run else [])
    try:
        rc = subprocess.run(cmd, cwd=str(ROOT), timeout=max(60, budget.total_left() + 60)).returncode
    except subprocess.TimeoutExpired:
        log("inject funnel timed out")
        rc = 1
    print(f"deep: raw={len(rows)} elapsed={int(budget.clock() - budget.t0)}s "
          f"deadline_hit={'yes' if budget.hit else 'no'} inject_rc={rc}")
    sys.exit(0 if rc == 0 else 1)


# ── selftest ──────────────────────────────────────────────────────────────
def selftest():
    li_html = (
        '<li><div class="base-card"><a class="base-card__full-link" '
        'href="https://ch.linkedin.com/jobs/view/head-of-strategy-at-acme-4479557664?refId=x">'
        '<h3 class="base-search-card__title">Head of Strategy &amp; M&amp;A</h3>'
        '<h4 class="base-search-card__subtitle"><a>Acme AG</a></h4>'
        '<span class="job-search-card__location">Zurich, Zurich, Switzerland</span>'
        '<time class="job-search-card__listdate" datetime="2026-11-05">2 days ago</time></div></li>'
        '<li><div>no job link here</div></li>')
    r = parse_li_cards(li_html)
    assert r == [{"title": "Head of Strategy & M&A", "company": "Acme AG",
                  "location": "Zurich, Zurich, Switzerland", "date_posted": "2026-11-05",
                  "url": "https://www.linkedin.com/jobs/view/4479557664",
                  "source": "linkedin-guest"}], r

    assert parse_li_detail('<span class="num-applicants__caption topcard__flavor--metadata">'
                           '\n  37 applicants\n</span>') == {"closed": False, "applicants": "37"}
    assert parse_li_detail('<figcaption class="num-applicants__caption">Over 200 applicants'
                           '</figcaption>')["applicants"] == "200+"
    assert parse_li_detail('<figcaption class="num-applicants__caption">Be among the first 25 '
                           'applicants</figcaption>')["applicants"] == "<25"
    d = parse_li_detail('<div>No longer accepting applications</div>')
    assert d == {"closed": True, "applicants": ""}, d  # no count shown -> none invented

    doc = {"documents": [
        {"title": "KAM", "company_name": "Beta", "place": "Zürich", "job_id": "abc",
         "initial_publication_date": "2026-11-05T08:00:00", "is_active": True},
        {"title": "Old", "company_name": "Old", "place": "Bern", "job_id": "old",
         "initial_publication_date": "2026-10-01"},
        {"title": "Gone", "company_name": "G", "place": "Zug", "job_id": "g",
         "initial_publication_date": "2026-11-06", "is_active": False}], "num_pages": 3}
    rows, old = jobsch_rows(doc, "2026-10-31")
    assert old == 1 and [x["title"] for x in rows] == ["KAM"], (rows, old)
    assert rows[0]["url"] == "https://www.jobs.ch/en/vacancies/detail/abc/"

    t = datetime.date(2026, 11, 7)
    assert wd_posted("Posted Today", t) == "2026-11-07"
    assert wd_posted("Posted Yesterday", t) == "2026-11-06"
    assert wd_posted("Posted 18 Days Ago", t) == "2026-10-20"
    assert wd_posted("Posted 30+ Days Ago", t) == "2026-10-08"
    assert wd_posted("", t) == ""
    fac = wd_ch_facets([{"facetParameter": "locationCountry", "values": [
        {"descriptor": "Switzerland", "id": "ch1"}, {"descriptor": "Germany", "id": "de1"}]},
        {"facetParameter": "locations", "values": [{"facetParameter": "x", "values": [
            {"descriptor": "Schweiz - Basel", "id": "b1"}]}]}])
    assert fac == {"locationCountry": ["ch1"], "x": ["b1"]}, fac

    assert gh_rows("acme", {"jobs": [
        {"title": "BD", "location": {"name": "Zürich"}, "absolute_url": "https://g/1",
         "updated_at": "2026-11-01T00:00:00"},
        {"title": "US", "location": {"name": "New York"}, "absolute_url": "https://g/2"}]}) == \
        [{"title": "BD", "company": "acme", "location": "Zürich", "date_posted": "2026-11-01",
          "url": "https://g/1", "source": "greenhouse"}]
    assert [x["url"] for x in lv_rows("b", [
        {"text": "KAM", "categories": {"location": "Basel"}, "hostedUrl": "https://l/1",
         "createdAt": 1762300800000},
        {"text": "X", "categories": {"location": "Paris"}, "hostedUrl": "https://l/2"}])] == ["https://l/1"]
    assert [x["url"] for x in ab_rows("c", {"jobs": [
        {"title": "S", "location": "Remote", "secondaryLocations": [{"location": "Zug"}],
         "jobUrl": "https://a/1"}, {"title": "T", "location": "Berlin", "jobUrl": "https://a/2"}]})] == ["https://a/1"]
    assert sr_rows("SikaAG", {"content": [{"id": "9", "name": "PM", "releasedDate": "2026-11-02T1",
                                           "location": {"city": "Baar", "country": "ch"},
                                           "company": {"name": "Sika"}}]})[0]["url"] == \
        "https://jobs.smartrecruiters.com/SikaAG/9"

    # budget: per-step cap and overall deadline (inject reserve kept back)
    now = [0.0]
    b = Budget(300, clock=lambda: now[0])
    b.start("linkedin")
    assert b.left() == 110
    now[0] = 200
    assert b.left() == 0 and not b.ok() and b.hit   # linkedin step over its cap
    b.start("ats")
    assert b.left() == 70                            # 300-200-20 = 80, cap 70
    now[0] = 260
    assert b.left() == 10 and b.timeout() == 10
    now[0] = 290
    assert b.left() == 0                             # only the inject reserve left
    assert default_queries({"jobspy": {"search_terms": ["Head of Strategy Switzerland",
                                                         "Leiter Strategie Schweiz"]}}) == \
        ["Head of Strategy", "Leiter Strategie"]
    print("run_deep selftest: OK")


if __name__ == "__main__":
    main()
