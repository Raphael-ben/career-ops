#!/usr/bin/env python3
"""
scan_aggregate.py — aggregator for /jobhunter scan (rb).

WHY THIS EXISTS (read before deleting):
  scan.mjs is system-layer and `update-system.mjs` overwrites it on every
  career-ops update — it has TWICE wiped the JobSpy/jobs.ch wiring (v1.8.1,
  v1.10.0). This script lives in the user's fork so updates can never take
  the logic away. It is the durable home for the broad-net
  scrape→filter→dedup→append pipeline.

WHAT IT DOES:
  1. Runs the scrapers: jobspy_scan.py (LinkedIn+Indeed+Google),
     jobs_ch.py (jobs.ch + jobup.ch), stepstone_scan.py.
  2. With --tavily: also runs portals.yml search_queries through the Tavily
     REST API (key: profile.yml tavily.api_key) — replaces the old agent-side
     MCP loop, so Phase 2 costs zero agent tokens.
  3. THREE-WAY title filter (fixes silent false negatives like
     "Business Manager"/"Founder's Office Lead"):
       negative hit -> drop
       positive hit -> PASS -> pipeline.md main list
       neither      -> BORDERLINE -> pipeline.md borderline section,
                       culled later by the LLM triage step
  4. Recency gate: when date_posted is known and older than
     profile.yml scan.max_age_days (default 45) -> drop. Unknown date -> keep.
  5. Dedup by URL against data/scan-history.tsv, then append survivors to
     scan-history.tsv and pipeline.md.

USAGE:
  python3 scan_aggregate.py                    # scrapers only (Phase 1b)
  python3 scan_aggregate.py --tavily           # scrapers + Tavily (Phase 1b+2)
  python3 scan_aggregate.py --dry-run          # report only, writes nothing
  python3 scan_aggregate.py --date 2026-07-09  # override header date
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
for _v in (_os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3"),
           _os.path.join(_HERE, ".venv", "bin", "python3")):
    if _os.path.exists(_v) and _os.path.realpath(_sys.executable) != _os.path.realpath(_v):
        _os.execv(_v, [_v] + _sys.argv)
        break

import argparse
import datetime
import json
import re
import subprocess
import sys
import urllib.request
from urllib.parse import urlparse
from pathlib import Path

import yaml
from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
PORTALS = HERE / "portals.yml"
PROFILE = HERE / "config" / "profile.yml"
HISTORY = HERE / "data" / "scan-history.tsv"
PIPELINE = HERE / "data" / "pipeline.md"
APPLICATIONS = HERE / "data" / "applications.md"
SCRAPERS = ["jobspy_scan.py", "jobs_ch.py", "stepstone_scan.py",
            "efinancialcareers_scan.py", "jobscout24_scan.py", "zuerijobs_scan.py"]

# Statuses in applications.md that mean "don't resurface this role" for fuzzy dedup.
APPLIED_STATUSES = {"applied", "interview", "offer", "responded"}

# Tavily results that are search/directory pages, not individual postings.
# URL-path fragments (high-confidence NOT an individual posting).
DIRECTORY_HINTS = ("/vacancies?", "/vacancies/?", "/occupations/", "/jobs?",
                   "/search?", "/en/jobs/", "/jobs/in-",
                   # person profiles / social, not jobs
                   "/profile/", "xing.com/profile", "linkedin.com/in/",
                   "linkedin.com/posts/", "/consultant/", "/our-consultants",
                   "/our-team", "/team/", "/people/", "/member/",
                   # search / listing roll-ups
                   "-stellen", "-jobs-in-", "/q-", "/skill/", "/companies/cities",
                   # editorial / corporate marketing pages
                   "/insights/", "/news/", "/blog/", "/media/", "/publications",
                   "/publikationen", "/press", "/leadership", "/executive-board",
                   "/management-team", "/our-leadership")

# Whole domains that never yield an individual, applicable posting
# (executive-search firms, job-board aggregators, social, strategy consultancies).
DIRECTORY_DOMAINS = (
    "egonzehnder.com", "kornferry.com", "spencerstuart.com", "heidrick.com",
    "boyden.com", "russellreynolds.com", "amrop.com", "pedersenandpartners.com",
    "stantonchase.com", "kellerexecutivesearch.com", "viavanta.ch",
    "swisslinx.com", "morganphilips.com", "stellar-executive.ch", "hays.ch",
    "roberthalf.com", "robertwalters.com", "pageexecutive.com", "michaelpage.ch",
    "experteer.com", "experteer.ch", "randstad.ch", "careerplus.ch",
    "approachpeople.com", "antal.com", "fintalent.com", "kienbaum.com",
    "odgersberndtson.com", "accurservices.com", "youtube.com", "instagram.com",
    "facebook.com", "hbr.org", "bcg.com", "bain.com", "mckinsey.com",
    "deloitte.com", "accenture.com", "mergersandinquisitions.com",
)


def is_directory(url):
    """True if the URL is a listing/profile/marketing page, not one posting."""
    u = (url or "").lower()
    if not u:
        return True
    if u.endswith(".pdf"):
        return True
    # LinkedIn: only /jobs/view/<id> is an individual posting; the rest are listings
    if "linkedin.com/jobs/" in u and "/jobs/view/" not in u:
        return True
    if any(h in u for h in DIRECTORY_HINTS):
        return True
    host = urlparse(u).netloc
    return any(host == d or host.endswith("." + d) for d in DIRECTORY_DOMAINS)


# Positive posting-signal gate — Tavily only (#tavily-junk). Tavily is a web
# search, not a job feed: it ranks whatever page matches the query text, which
# regularly includes corporate homepages, conference/exec-ed pages, and
# consulting "industries" pages that happen to share vocabulary with a search
# query like "Private Equity Value Creation Manager". DIRECTORY_HINTS/DOMAINS
# above is a blocklist grown one offender at a time and always trails the next
# junk shape; this is the opposite structure — default-deny, so a URL must
# show an actual job-posting signal to survive. The scraper feeds (jobspy,
# jobs.ch, stepstone, ...) never need this: every URL they emit already came
# from a job-detail endpoint by construction.
POSTING_PATH_HINTS = (
    "/job/", "/jobs/", "/career/", "/careers/", "/vacanc", "/stelle",
    "/position", "/offre", "/jobid", "jobid=", "/viewjob", "/postings/",
)

# Host suffixes that are themselves a job board/ATS — any path beyond root
# counts as a posting signal there even without a path token above. NOT
# linkedin.com/indeed.com: both host huge non-posting surfaces (company
# pages, profiles, articles) under paths that carry no job token, so those
# two stay gated by POSTING_PATH_HINTS only ("/jobs/view/", "/viewjob").
POSTING_HOST_SUFFIXES = (
    "jobs.ch", "jobup.ch", "stepstone.de",
    "stepstone.ch", "efinancialcareers.com", "efinancialcareers.ch",
    "jobscout24.ch", "zueri.jobs", "myworkdayjobs.com",
    "greenhouse.io", "job-boards.greenhouse.io", "lever.co",
    "ashbyhq.com", "smartrecruiters.com",
)


def is_tavily_posting(url):
    """Positive gate: keep a Tavily URL only if it looks like an individual
    job posting. Everything else (homepage, agenda/event/program/course/
    exec-ed page, a company's generic /industries//services/ marketing page,
    a bare LinkedIn company page) is dropped, even if it already passed
    is_directory() — this is a stricter, Tavily-only second gate, not a
    replacement for it.
    """
    u = (url or "").lower()
    if not u:
        return False
    if any(h in u for h in POSTING_PATH_HINTS):
        return True
    parsed = urlparse(u)
    host = parsed.netloc
    path = parsed.path.strip("/")
    if not path:
        return False  # homepage / bare root — never a posting
    if any(host == d or host.endswith("." + d) for d in POSTING_HOST_SUFFIXES):
        return True
    # jobs.<company> / careers.<company> subdomains, any path beyond root
    if host.startswith("jobs.") or host.startswith("careers."):
        return True
    return False


def run_scraper(name):
    """Run a scraper, return its JSON list. Never raises — [] on failure."""
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / name)],
            capture_output=True, text=True, timeout=420,
            cwd=str(HERE),  # scrapers read cwd-relative config/profile.yml
        )
        if not proc.stdout.strip():
            print(f"  [{name}] no output ({proc.stderr.strip()[-160:]})", file=sys.stderr)
            return []
        return json.loads(proc.stdout)
    except Exception as e:  # noqa: BLE001 — best-effort, partial results are fine
        print(f"  [{name}] failed: {e}", file=sys.stderr)
        return []


ATS_FULL_CHECKPOINT = HERE / "data" / "cache" / "ats-full-checkpoint.json"


def run_ats_full(profile_cfg, dry_run=False):
    """Optional stage: `node scan-ats-full.mjs` — a reverse-ATS keyword sweep of
    the full public Greenhouse/Lever/Ashby/Workday/iCIMS datasets, filtered by
    portals.yml's own title_filter/location_filter (no company list needed, so
    it finds postings at companies not in portals.yml at all).

    Gated by profile.yml scan.ats_full (default true). Unlike run_scraper(),
    this writes data/pipeline.md and data/scan-history.tsv ITSELF — same
    contract, same functions the other scrapers feed through set-status
    upstream of — so there's no offers list to merge back into main()'s
    funnel; we just diff scan-history.tsv's line count to report a matches
    count. subprocess.run's own `timeout` is the hard cap (no `timeout(1)`
    binary needed); a cap hit or non-zero exit is tolerated — scan-ats-full.mjs
    checkpoints its own progress and `--resume` (used automatically once a
    checkpoint exists) continues the interrupted sweep next run.
    """
    cfg = (profile_cfg.get("scan") or {})
    if not cfg.get("ats_full", True):
        return 0
    cap = int(cfg.get("ats_full_cap_seconds", 900))
    before = len(HISTORY.read_text(errors="replace").splitlines()) if HISTORY.exists() else 0
    args = ["node", str(HERE / "scan-ats-full.mjs")]
    if ATS_FULL_CHECKPOINT.exists():
        args.append("--resume")
    if dry_run:
        args.append("--dry-run")
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                               timeout=cap, cwd=str(HERE))
        if proc.returncode != 0:
            print(f"  [ats-full] exited {proc.returncode}: "
                  f"{proc.stderr.strip()[-300:]}", file=sys.stderr)
    except subprocess.TimeoutExpired:
        print(f"  [ats-full] hit the {cap}s cap — checkpoint saved, "
              f"--resume picks it up next run", file=sys.stderr)
    except Exception as e:  # noqa: BLE001 — best-effort, never blocks the rest of the scan
        print(f"  [ats-full] failed: {e}", file=sys.stderr)
        return 0
    after = len(HISTORY.read_text(errors="replace").splitlines()) if HISTORY.exists() else 0
    return max(0, after - before)


def run_tavily(profile_cfg, portals_cfg):
    """Run portals.yml search_queries via Tavily REST. Zero agent tokens."""
    key = ((profile_cfg.get("tavily") or {}).get("api_key") or "").strip()
    if not key:
        print("  [tavily] no api_key in profile.yml → skipped "
              "(agent MCP fallback per rb/scan.md)", file=sys.stderr)
        return []
    jobs = []
    tavily_kept = 0
    tavily_dropped_nonposting = 0
    queries = [q for q in (portals_cfg.get("search_queries") or [])
               if q.get("enabled", True)]
    print(f"  [tavily] {len(queries)} queries", file=sys.stderr)
    for q in queries:
        query = q.get("query", "")
        include = []
        # map leading `site:host` operator → include_domains
        if query.startswith("site:"):
            host, _, rest = query.partition(" ")
            include = [host[5:].split("/")[0]]
            query = rest
        # "basic" = 1 credit/query (advanced = 2). We only harvest title+URL,
        # so basic is equivalent — halves Tavily spend.
        payload = {"api_key": key, "query": query, "search_depth": "basic",
                   "max_results": 8, "country": "switzerland"}
        if include:
            payload["include_domains"] = include
        try:
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=30) as r:
                results = json.loads(r.read()).get("results", [])
        except Exception as e:  # noqa: BLE001
            print(f"  [tavily] query failed ({q.get('name','?')}): {e}", file=sys.stderr)
            continue
        for res in results:
            url = res.get("url", "")
            if is_directory(url):
                continue  # directory/profile/marketing page, not an individual posting
            if not is_tavily_posting(url):
                tavily_dropped_nonposting += 1
                continue
            tavily_kept += 1
            jobs.append({"title": res.get("title", ""), "company": "",
                         "url": url, "source": "tavily",
                         "location": "", "date_posted": ""})
    print(f"  [tavily] tavily_kept={tavily_kept} "
          f"tavily_dropped_nonposting={tavily_dropped_nonposting}", file=sys.stderr)
    return jobs


def local_llm_verdict(row, cfg):
    """Ask a local LLM (e.g. Ollama) whether a borderline row is worth keeping.

    POSTs {model, prompt, stream:false} to cfg['endpoint'], 10s timeout.
    "no" -> drop. "yes", a parse failure, or any exception -> keep (borderline
    stays borderline either way — this can only shrink the bucket, never grow it).
    # ponytail: interface only — prompt tuning when a model is actually pointed at it.
    """
    endpoint = cfg.get("endpoint", "")
    model = cfg.get("model", "")
    prompt = (
        f"Job title: \"{row.get('title', '')}\" at company \"{row.get('company', '')}\". "
        "Is this plausibly relevant to a Senior Manager/Lead-level strategy, M&A, "
        "business development, applied AI, operations, or transformation role? "
        "Answer with exactly one word: yes or no."
    )
    try:
        req = urllib.request.Request(
            endpoint,
            data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode(),
            headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as r:
            answer = json.loads(r.read()).get("response", "").strip().lower()
        return not answer.startswith("no")
    except Exception:  # noqa: BLE001 — unreachable/misconfigured model -> keep, never gate on it
        return True


def load_cfgs():
    portals = yaml.safe_load(PORTALS.read_text()) or {}
    profile = yaml.safe_load(PROFILE.read_text()) if PROFILE.exists() else {}
    tf = portals.get("title_filter", {}) or {}
    lf = portals.get("location_filter", {}) or {}
    return (portals, profile or {},
            [p.lower() for p in (tf.get("positive") or [])],
            [n.lower() for n in (tf.get("negative") or [])],
            [a.lower() for a in (lf.get("allow") or [])],
            [b.lower() for b in (lf.get("block") or [])])


def load_history():
    """Return (seen_urls, (title, company) pairs) from scan-history.tsv.

    History rows are url\ttitle\tcompany\tsource\tdate\tstatus (see main()'s
    writer below) — title/company feed the fuzzy-dedup corpus.
    """
    seen = set()
    pairs = []
    if HISTORY.exists():
        for line in HISTORY.read_text(errors="replace").splitlines():
            if not line.strip():
                continue
            parts = line.split("\t")
            seen.add(parts[0].strip())
            if len(parts) >= 3:
                pairs.append((parts[1].strip(), parts[2].strip()))
    return seen, pairs


def load_applications(path=None):
    """Parse data/applications.md's tracker table → (role, company) pairs for
    rows whose Status is Applied/Interview/Offer/Responded (see APPLIED_STATUSES).

    Table columns: | # | Date | Company | Role | Score | Status | PDF | Report | Notes |
    """
    path = path or APPLICATIONS
    pairs = []
    if not path.exists():
        return pairs
    for line in path.read_text(errors="replace").splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cols = [c.strip() for c in line.strip("|").split("|")]
        if len(cols) < 6:
            continue
        if cols[0] == "#" or re.fullmatch(r"-+", cols[0]):
            continue  # header / separator row
        company, role, status = cols[2], cols[3], cols[5]
        if status.lower() in APPLIED_STATUSES:
            pairs.append((role, company))
    return pairs


def load_blacklist(path=None):
    """Parse data/blacklist.md -> set of normalized company names to skip.

    Same file scan.mjs reads (its BLACKLIST_PATH), so both scan layers share one
    do-not-apply list instead of drifting apart. Absent file = empty set = no
    filtering, byte-identical to a pre-blacklist run.

    Table shape: | Company | Since | Scope | Reason |
    """
    p = Path(path) if path else HERE / "data" / "blacklist.md"
    if not p.exists():
        return set()
    out = set()
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip().startswith("|"):
            continue
        cells = [c.strip() for c in line.split("|")]
        if len(cells) < 3:
            continue
        company = cells[1]
        if not company or company.lower() == "company":
            continue
        if set(company) <= set("-: "):      # separator row
            continue
        out.add(normalize(company))
    return out


def blacklisted(company, blacklist):
    """True if this posting's company is on the do-not-apply list.

    Substring both ways so "Michael Page" catches "Michael Page International AG"
    and a feed's short "Hays" catches a blacklist row "Hays Recruitment".
    """
    c = normalize(company)
    if not c:
        return False
    return any(b and (b in c or c in b) for b in blacklist)


def normalize(s):
    """Lowercase + strip cosmetic noise so near-identical postings compare equal:
    gender tags (m/w/d), percent ranges (80-100%), punctuation, abbreviations.
    """
    s = (s or "").lower()
    s = re.sub(r"\(\s*[mwfdx/]+\s*\)", " ", s)          # (m/w/d), (f/m/x), ...
    s = re.sub(r"\d{1,3}\s*-\s*\d{1,3}\s*%", " ", s)     # 80-100%
    s = re.sub(r"\d{1,3}\s*%", " ", s)                   # 100%
    s = re.sub(r"\bsr\.?\b", "senior", s)
    s = re.sub(r"\bjr\.?\b", "junior", s)
    s = re.sub(r"\bmgr\.?\b", "manager", s)
    s = re.sub(r"[^\w\s]", " ", s)                       # punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


def is_dupe(row, static_corpus, accepted_this_run, threshold):
    """Fuzzy near-duplicate check against prior history + this run's accepted rows.

    Exact-URL dedup is a separate short-circuit upstream (run_seen/seen) — this
    only fires on rows that already cleared that check and title_bucket.

    Title and company are scored separately (both via token_set_ratio) and the
    minimum of the two must clear the threshold — token_set_ratio on the plain
    concatenation "{title} {company}" lets a long shared title (e.g. "Senior
    Business Development Manager") swamp a short, completely different company
    name, scoring >90 for postings at two unrelated companies. Requiring both
    fields to independently match avoids that false-positive class.
    """
    title = normalize(row.get("title", ""))
    company = normalize(row.get("company", ""))
    if not title:
        return False
    for ot, oc in static_corpus + accepted_this_run:
        if not ot:
            continue
        t_score = fuzz.token_set_ratio(title, ot)
        # Missing company data on either side (e.g. Tavily rows) → don't gate
        # on company, same "sparse data → keep permissive" stance as location_ok.
        c_score = fuzz.token_set_ratio(company, oc) if (company and oc) else 100
        if min(t_score, c_score) >= threshold:
            return True
    return False


def title_bucket(title, pos, neg):
    """'drop' | 'pass' | 'borderline' — borderline goes to LLM triage."""
    t = (title or "").lower()
    if neg and any(n in t for n in neg):
        return "drop"
    if pos and any(p in t for p in pos):
        return "pass"
    return "borderline"


def location_ok(loc, allow, block):
    l = (loc or "").strip().lower()
    if not l:
        return True  # sparse data → keep
    if block and any(b in l for b in block):
        return False
    if allow and not any(a in l for a in allow):
        return False
    return True


def fresh_enough(date_posted, max_age_days, today):
    """Unknown date → keep. Known date older than max_age_days → drop."""
    d = (date_posted or "").strip()[:10]
    if not d:
        return True
    try:
        posted = datetime.date.fromisoformat(d)
    except ValueError:
        return True
    return (today - posted).days <= max_age_days


def pipeline_row(j):
    company = (j.get("company") or "?").strip() or "?"
    title = (j.get("title") or "").strip()
    loc = (j.get("location") or "").strip()
    suffix = f" ({loc})" if loc else ""
    return (f"- [ ] {j.get('url','').strip()} | {company} | "
            f"{title}{suffix} — via {j.get('source','')}, triage\n")


# ── REAPER — closes stale pipeline.md entries so it stops growing forever ──
# data/pipeline.md is append-only (main()'s writer below never removes a
# line) and nothing else ever closed a `- [ ]` for age, so it silently rotted
# to 1000+ open entries. This bounds it: unchecked entries past
# scan.pipeline_max_age_days (default 45) get flipped to `- [x] ... EXPIRED`.

RESCUED_MARK = "⚑ RESCUED"
_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_SECTION_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_ROW_URL = re.compile(r"(https?://\S+)")


def _row_date(parts):
    """First ISO-date-looking token in a scan-history.tsv row's columns 1-5.

    Two row layouts coexist in the real file (append-only history, multiple
    writers over time): ATS/smartrecruiters rows put first_seen at column 1
    (`url  date  portal  title  company  status`); linkedin/tavily rows put
    it at column 4 (`url  title  company  portal  date  status`). Scanning
    the range instead of trusting one fixed index handles both, plus the
    assorted 3/7/11/12-column variants that show up in practice.
    """
    for tok in parts[1:6]:
        tok = tok.strip()
        if _ISO_DATE.match(tok):
            return tok
    return None


def load_first_seen(history_path=None):
    """url -> earliest known first_seen date from scan-history.tsv."""
    path = Path(history_path) if history_path else HISTORY
    out = {}
    if not path.exists():
        return out
    for line in path.read_text(errors="replace").splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        url = parts[0].strip()
        if not url:
            continue
        date = _row_date(parts)
        if not date:
            continue
        if url not in out or date < out[url]:
            out[url] = date
    return out


def reap_pipeline(max_age_days, today=None, pipeline_path=None, history_path=None,
                   dry_run=False):
    """Close unchecked pipeline.md entries older than max_age_days.

    Age resolution per entry (first hit wins, in order):
      1. first_seen for its URL in scan-history.tsv (both layouts, see _row_date)
      2. the date in its enclosing `## Scan YYYY-MM-DD` (or any header
         carrying a YYYY-MM-DD) section, if one exists
      3. undatable -> NEVER reaped, counted separately

    A line containing RESCUED_MARK is always immune, regardless of age.
    Reaped lines flip `- [ ]` -> `- [x]` and get ` — EXPIRED (aged out
    {today})` appended; the rest of the line is untouched byte-for-byte.

    Returns a stats dict: reaped / undatable / open_remaining (entries still
    `- [ ]` after this pass, expired ones included). Writes nothing when
    dry_run or when nothing changed.
    """
    path = Path(pipeline_path) if pipeline_path else PIPELINE
    today = today or datetime.date.today()
    first_seen = load_first_seen(history_path)

    text = path.read_text() if path.exists() else ""
    lines = text.splitlines(keepends=True)

    section_date = None
    reaped = undatable = open_remaining = 0
    out_lines = []
    for line in lines:
        stripped = line.rstrip("\n")
        if stripped.startswith("## "):
            m = _SECTION_DATE.search(stripped)
            section_date = m.group(0) if m else None
            out_lines.append(line)
            continue
        if not stripped.startswith("- [ ]"):
            out_lines.append(line)
            continue
        if RESCUED_MARK in stripped:
            open_remaining += 1
            out_lines.append(line)
            continue
        m = _ROW_URL.search(stripped)
        url = m.group(1) if m else ""
        date_str = first_seen.get(url) or section_date
        age = None
        if date_str:
            try:
                age = (today - datetime.date.fromisoformat(date_str)).days
            except ValueError:
                age = None
        if age is None:
            undatable += 1
            open_remaining += 1
            out_lines.append(line)
        elif age > max_age_days:
            reaped += 1
            out_lines.append(f"- [x]{stripped[5:]} — EXPIRED (aged out "
                              f"{today.isoformat()})\n")
        else:
            open_remaining += 1
            out_lines.append(line)

    if reaped and not dry_run:
        path.write_text("".join(out_lines))

    return {"reaped": reaped, "undatable": undatable, "open_remaining": open_remaining}


def selftest():
    """In-memory fuzzy-dedup assertions — no network, no real files touched."""
    import tempfile

    # exact URL dup dropped (upstream short-circuit — simulated here)
    seen = {"https://example.com/job/1"}
    assert "https://example.com/job/1" in seen

    # fuzzy dup: same role/company, noisy formatting → dropped
    base_title = normalize("Senior Business Development Manager")
    base_company = normalize("Acme")
    corpus = [(base_title, base_company)]
    row_noisy = {"title": "Sr. Business Development Manager (m/w/d) 80-100%",
                 "company": "Acme", "url": "https://example.com/job/2"}
    assert is_dupe(row_noisy, corpus, [], 90), "fuzzy dup not detected"

    # same title, different company → kept (title-only concatenation would
    # false-positive here since the long shared title swamps a short company)
    row_diff_co = {"title": "Senior Business Development Manager",
                    "company": "Other Co", "url": "https://example.com/job/3"}
    assert not is_dupe(row_diff_co, corpus, [], 90), "different company wrongly flagged"

    # applications.md fixture: an Applied row's (role, company) dedupes a fuzzy match
    fixture = (
        "# Applications Tracker\n\n"
        "| # | Date | Company | Role | Score | Status | PDF | Report | Notes |\n"
        "|---|------|---------|------|-------|--------|-----|--------|-------|\n"
        "| 1 | 2026-01-01 | Acme | Senior Business Development Manager | A/5 | Applied | ✅ | - | note |\n"
        "| 2 | 2026-01-02 | Beta | Some Skipped Role | B/5 | SKIP | ✅ | - | note |\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(fixture)
        fixture_path = Path(fh.name)
    try:
        pairs = load_applications(fixture_path)
        assert pairs == [("Senior Business Development Manager", "Acme")], pairs
        app_corpus = [(normalize(r), normalize(c)) for r, c in pairs]
        row_applied = {"title": "Sr. Business Development Manager (m/w/d)",
                       "company": "Acme", "url": "https://example.com/job/4"}
        assert is_dupe(row_applied, app_corpus, [], 90), "applied role not dropped"
    finally:
        fixture_path.unlink()

    # ── reaper fixtures — tmp files only, never touches real data/* ──
    today = datetime.date(2026, 1, 1)
    old_date = (today - datetime.timedelta(days=50)).isoformat()      # >45d
    very_old_date = (today - datetime.timedelta(days=60)).isoformat()  # >45d
    recent_date = (today - datetime.timedelta(days=10)).isoformat()    # <=45d

    url_ats = "https://example.com/job/ats-old"       # TSV layout A, date col1
    url_tavily = "https://example.com/job/tavily-new"  # TSV layout B, date col4
    url_rescued = "https://example.com/job/rescued-old"  # TSV layout A, old, immune
    url_hdr = "https://example.com/job/header-fallback"  # no TSV row, old header
    url_undatable = "https://example.com/job/nowhere"    # no TSV row, no header date

    tsv_fixture = (
        "url\tfirst_seen\tportal\ttitle\tcompany\tstatus\n"
        f"{url_ats}\t{old_date}\tsmartrecruiters\tTitle A\tCompany A\tadded\n"
        f"{url_tavily}\tTitle B\tCompany B\ttavily\t{recent_date}\tborderline\n"
        f"{url_rescued}\t{very_old_date}\tsmartrecruiters\tTitle E\tCompany E\tadded\n"
    )
    pipe_fixture = (
        "# Pipeline\n\n"
        f"## Scan {old_date}\n\n"
        f"- [ ] {url_hdr} | Co F | Title F — via tavily, triage\n\n"
        "## Pendientes\n\n"
        f"- [ ] {url_undatable} | Co G | Title G\n\n"
        f"## Scan {recent_date}\n\n"
        f"- [ ] {url_ats} | Co A | Title A — via smartrecruiters, triage\n"
        f"- [ ] {url_tavily} | Co B | Title B — via tavily, triage\n"
        f"- [ ] {url_rescued} | Co E | {RESCUED_MARK} Title E — via smartrecruiters, triage\n"
    )
    with tempfile.NamedTemporaryFile("w", suffix=".tsv", delete=False) as fh:
        fh.write(tsv_fixture)
        tsv_path = Path(fh.name)
    with tempfile.NamedTemporaryFile("w", suffix=".md", delete=False) as fh:
        fh.write(pipe_fixture)
        pipe_path = Path(fh.name)
    try:
        # both TSV layouts resolve correctly
        fs = load_first_seen(tsv_path)
        assert fs[url_ats] == old_date, fs
        assert fs[url_tavily] == recent_date, fs
        assert url_hdr not in fs and url_undatable not in fs

        stats = reap_pipeline(45, today=today, pipeline_path=pipe_path,
                               history_path=tsv_path)
        out = pipe_path.read_text()
        assert f"- [x] {url_ats}" in out and "EXPIRED (aged out 2026-01-01)" in out, out
        assert f"- [ ] {url_tavily}" in out, "10d-old TSV entry must survive"
        assert f"- [x] {url_hdr}" in out, "section-header fallback must close the old entry"
        assert f"- [ ] {url_undatable}" in out, "undatable entry must never be reaped"
        assert f"- [ ] {url_rescued}" in out and RESCUED_MARK in out, \
            "⚑ RESCUED entry must be immune even though it's 60d old"
        assert stats == {"reaped": 2, "undatable": 1, "open_remaining": 3}, stats

        # dry-run: identical stats, but the file must be untouched
        pipe_path.write_text(pipe_fixture)  # reset (previous run already reaped it)
        dry_stats = reap_pipeline(45, today=today, pipeline_path=pipe_path,
                                   history_path=tsv_path, dry_run=True)
        assert dry_stats == {"reaped": 2, "undatable": 1, "open_remaining": 3}, dry_stats
        assert pipe_path.read_text() == pipe_fixture, "dry-run must not write"
    finally:
        tsv_path.unlink()
        pipe_path.unlink()

    # ── Tavily positive posting-gate fixtures ──
    # Real junk offenders pulled from data/scan-history.tsv's 2026-09-15/16
    # tavily rows (#tavily-junk) — homepages, conference/exec-ed/course pages,
    # consulting "industries" pages, a bare LinkedIn company page.
    tavily_junk = [
        "https://www.imiplc.com",
        "https://www.aptiv.com",
        "https://www.givaudan.com",
        "https://china.ahk.de",
        "https://alterdomus.com/services/private-equity-solutions",
        "https://www.grantthornton.com/services/advisory-services/business-consulting",
        "https://www.ashrae.org/technical-resources/supplier-provided-learning/supplier-webinars",
        "https://www.ey.com/en_ch/industries/private-equity/value-creation",
        "https://www.alexandergroup.com/industries/manufacturing/packaging",
        "https://www.legic.com/connectconference",
        "https://www.terrapinn.com/exhibition/solar-storage-live-zurich/Agenda.stm",
        "https://www.linkedin.com/company/dwyeromega",
        "https://www.privateequitymarketeer.com/private-equity-events",
        "https://www.aaltoee.fi/en/themes/marketing-and-sales",
        "https://www.bbs.unibo.it/en/master-fulltime/analytics-and-ai-for-marketing",
        "https://www.3plogistics.com/events-2026",
        "https://www.sid.org.sg/Web/Web/Events/Event_Display.aspx?EventKey=SC8160926",
    ]
    for u in tavily_junk:
        assert not is_tavily_posting(u), f"tavily positive gate should drop: {u}"

    tavily_real = [
        "https://acme.wd1.myworkdayjobs.com/en-US/External/job/Zurich/Senior-Manager_R12345",
        "https://www.jobs.ch/en/vacancies/detail/00001a2b-3c4d-5e6f-0001-a2b3c4d5e6f7/",
        "https://www.linkedin.com/jobs/view/4012345678",
    ]
    for u in tavily_real:
        assert is_tavily_posting(u), f"tavily positive gate should keep: {u}"

    print("selftest: OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tavily", action="store_true",
                    help="also run portals.yml search_queries via Tavily REST")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    ap.add_argument("--selftest", action="store_true",
                    help="run in-memory fuzzy-dedup assertions, no network/files, then exit")
    ap.add_argument("--reap", action="store_true",
                    help="reap aged-out pipeline.md entries only (no scan), then exit")
    ap.add_argument("--reap-dry-run", action="store_true",
                    help="print what --reap would close, change nothing, then exit")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    today = datetime.date.fromisoformat(args.date)

    portals, profile, pos, neg, allow, block = load_cfgs()
    max_age = int((profile.get("scan") or {}).get("max_age_days", 45))
    fuzzy_threshold = float((profile.get("scan") or {}).get("fuzzy_dedup_threshold", 90))
    pipeline_max_age = int((profile.get("scan") or {}).get("pipeline_max_age_days", 45))

    if args.reap or args.reap_dry_run:
        stats = reap_pipeline(pipeline_max_age, today=today, dry_run=args.reap_dry_run)
        print(f"reap: reaped={stats['reaped']} undatable={stats['undatable']} "
              f"open_remaining={stats['open_remaining']}" +
              ("  (dry-run: nothing written)" if args.reap_dry_run else ""))
        return

    # REAPER — runs at the start of every scan too, so pipeline.md stays
    # bounded without a separate step anyone has to remember to run.
    reap_stats = reap_pipeline(pipeline_max_age, today=today, dry_run=args.dry_run)

    # Runs (and writes pipeline.md/scan-history.tsv) FIRST, before load_history()
    # reads them — so its own rows are in `seen`/static_corpus and the scraper
    # loop below can't re-add the same URL a second time this run.
    ats_full_new = run_ats_full(profile, dry_run=args.dry_run)
    print(f"  ats-full: {ats_full_new} new rows", file=sys.stderr)

    seen, history_pairs = load_history()
    applied_pairs = load_applications()
    static_corpus = [(normalize(t), normalize(c)) for t, c in history_pairs + applied_pairs]

    jobs = []
    for s in SCRAPERS:
        got = run_scraper(s)
        print(f"  {s}: {len(got)} jobs", file=sys.stderr)
        jobs.extend(got)
    if args.tavily:
        got = run_tavily(profile, portals)
        print(f"  tavily: {len(got)} results", file=sys.stderr)
        jobs.extend(got)

    raw = len(jobs)
    fresh = [j for j in jobs if fresh_enough(j.get("date_posted"), max_age, today)]
    lpass = [j for j in fresh if location_ok(j.get("location"), allow, block)]

    blacklist = load_blacklist()

    passed, borderline, run_seen = [], [], set()
    dropped_neg = 0
    dropped_blacklist = 0
    for j in lpass:
        url = (j.get("url") or "").strip()
        if not url or url in seen or url in run_seen:
            continue
        if blacklisted(j.get("company"), blacklist):
            dropped_blacklist += 1
            continue
        bucket = title_bucket(j.get("title"), pos, neg)
        if bucket == "drop":
            dropped_neg += 1
            continue
        run_seen.add(url)
        (passed if bucket == "pass" else borderline).append(j)

    # Fuzzy dedup — after title_bucket so dropped rows never pay the fuzzy-match
    # cost. Checks against scan-history.tsv + applications.md (static_corpus)
    # plus rows already accepted earlier in this same run (accepted_norms).
    fuzzy_dropped = 0
    accepted_norms = []

    def _fuzzy_keep(j):
        nonlocal fuzzy_dropped
        if is_dupe(j, static_corpus, accepted_norms, fuzzy_threshold):
            fuzzy_dropped += 1
            return False
        accepted_norms.append((normalize(j.get("title", "")), normalize(j.get("company", ""))))
        return True

    passed = [j for j in passed if _fuzzy_keep(j)]
    borderline = [j for j in borderline if _fuzzy_keep(j)]

    # Local-LLM triage hook (interface only — see local_llm_verdict docstring).
    # Disabled (default/absent) leaves this whole block a no-op, so the
    # disabled path is byte-identical to pre-1.5 behavior, funnel line included.
    llm_dropped = 0
    local_llm_cfg = ((profile.get("triage") or {}).get("local_llm") or {})
    llm_enabled = bool(local_llm_cfg.get("enabled"))
    if llm_enabled:
        kept = []
        for j in borderline:
            if local_llm_verdict(j, local_llm_cfg):
                kept.append(j)
            else:
                llm_dropped += 1
        borderline = kept

    funnel = (f"\nats-full: {ats_full_new} new rows (writes pipeline.md/scan-history.tsv directly)\n"
              f"Funnel: raw={raw}  fresh(<={max_age}d)={len(fresh)}  "
              f"location_ok={len(lpass)}  neg_dropped={dropped_neg}  "
              f"blacklist_dropped={dropped_blacklist}  "
              f"fuzzy_dropped={fuzzy_dropped}  ")
    if llm_enabled:
        funnel += f"llm_dropped={llm_dropped}  "
    funnel += f"NEW pass={len(passed)}  NEW borderline={len(borderline)}\n"
    funnel += (f"Pipeline reaper: reaped={reap_stats['reaped']}  "
               f"undatable={reap_stats['undatable']}  "
               f"open_remaining={reap_stats['open_remaining']}")
    print(funnel)

    if (passed or borderline) and not args.dry_run:
        with HISTORY.open("a") as fh:
            for j, status in ([(x, "added") for x in passed] +
                              [(x, "borderline") for x in borderline]):
                fh.write("\t".join([
                    j.get("url", "").strip(),
                    (j.get("title") or "").replace("\t", " ").strip(),
                    (j.get("company") or "").replace("\t", " ").strip(),
                    j.get("source", "").strip(),
                    args.date, status]) + "\n")
        with PIPELINE.open("a") as fh:
            fh.write(f"\n## Scan {args.date} (script layer"
                     f"{' + tavily' if args.tavily else ''})\n\n")
            for j in passed:
                fh.write(pipeline_row(j))
            if borderline:
                fh.write(f"\n### Borderline {args.date} — no positive-keyword "
                         f"match, LLM triage decides (do NOT skip silently)\n\n")
                for j in borderline:
                    fh.write(pipeline_row(j))
        print(f"Wrote {len(passed)} pass + {len(borderline)} borderline → "
              f"scan-history.tsv + pipeline.md")
    elif args.dry_run:
        print("(dry-run: nothing written)")

    for label, lst in (("PASS", passed), ("BORDERLINE", borderline)):
        for j in lst[:25]:
            print(f"  {label[:4]:4} • {(j.get('title') or '')[:64]:64} | {j.get('source')}")
        if len(lst) > 25:
            print(f"       … and {len(lst) - 25} more {label.lower()}")


if __name__ == "__main__":
    main()
