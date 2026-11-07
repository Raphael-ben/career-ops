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
# Scraper registry. Order matters: results are merged in THIS order (not
# completion order) so dedup is reproducible with parallel runs.
# Selection: profile.yml `scan.scrapers:` — short names or these script names.
#   absent      -> every scraper below (default)
#   []          -> none (only ats-full / Tavily / --inject feed the funnel)
#   [jobspy, jobs_ch] (or script filenames) -> only those; unknown name -> ValueError.
# Non-Swiss users should drop the Swiss-only boards (jobs_ch.py, jobscout24_scan.py,
# zuerijobs_scan.py). `scan.parallel_scrapers: false` runs them one by one.
SCRAPERS = ["jobspy_scan.py", "jobs_ch.py", "stepstone_scan.py",
            "efinancialcareers_scan.py", "jobscout24_scan.py", "zuerijobs_scan.py",
            "jobfishing_scan.py"]  # no-op ([]) until `jobfishing_scan.py --login` is run

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


SCRAPER_CAP = 420       # per-scraper ceiling (seconds)
SCRAPER_FLOOR = 30      # never start a scraper with less than this left
DEFAULT_DEADLINE = 600  # owner's rule: a scan finishes in <=10 min


def remaining_budget(start, deadline, cap, now=None):
    """Seconds a step may use: min(cap, time left before start+deadline), >= 0.

    Pure (pass `now` to test). start/now are time.monotonic() values.
    """
    import time
    now = time.monotonic() if now is None else now
    return max(0.0, min(float(cap), deadline - (now - start)))


def scraper_timeout(start, deadline, now=None):
    """Timeout for the next scraper, or None when the budget is spent
    (<= SCRAPER_FLOOR left) and the rest must be skipped."""
    left = remaining_budget(start, deadline, SCRAPER_CAP, now)
    if left <= SCRAPER_FLOOR:
        return None
    return max(SCRAPER_FLOOR, int(left))


def run_scraper(name, timeout=SCRAPER_CAP):
    """Run a scraper. Never raises. Returns (jobs, log_lines, cut): log lines
    are collected instead of printed so parallel runs never interleave;
    cut=True when the subprocess timeout killed it."""
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / name)],
            capture_output=True, text=True, timeout=timeout,
            cwd=str(HERE),  # scrapers read cwd-relative config/profile.yml
        )
        if not proc.stdout.strip():
            return [], [f"  [{name}] no output ({proc.stderr.strip()[-160:]})"], False
        return json.loads(proc.stdout), [], False
    except subprocess.TimeoutExpired:
        return [], [f"  [{name}] cut: timed out after {timeout}s"], True
    except Exception as e:  # noqa: BLE001 — best-effort, partial results are fine
        return [], [f"  [{name}] failed: {e}"], False


SCRAPER_NAMES = {"jobspy": "jobspy_scan.py", "jobs_ch": "jobs_ch.py",
                 "stepstone": "stepstone_scan.py",
                 "efinancialcareers": "efinancialcareers_scan.py",
                 "jobscout24": "jobscout24_scan.py", "zuerijobs": "zuerijobs_scan.py",
                 "jobfishing": "jobfishing_scan.py"}


def resolve_scrapers(profile):
    """profile.yml scan.scrapers -> script list (absent = all; [] = none).
    Entries are short names (jobspy) or script filenames (jobspy_scan.py), in the
    order given. Unknown entry -> ValueError listing the valid names."""
    sel = (profile.get("scan") or {}).get("scrapers")
    if sel is None:
        return list(SCRAPERS)
    out = []
    for n in sel:
        f = SCRAPER_NAMES.get(n, n if n in SCRAPERS else None)
        if f is None:
            raise ValueError(f"scan.scrapers: unknown {n!r}; valid: "
                             f"{', '.join(SCRAPER_NAMES)}")
        out.append(f)
    return out


def run_scrapers(names, start, deadline, parallel=True, state=None):
    """Run `names`, return their jobs merged in `names` order.

    Each scraper's timeout = scraper_timeout() at submit time; ones that would
    start with <= SCRAPER_FLOOR left are skipped. Parallel: one thread per
    scraper, so wall time ~= the slowest one instead of the sum."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    state = {} if state is None else state
    results = {}

    def finish(name, res):  # main thread only -> whole blocks, no interleaving
        got, lines, _ = res
        for line in lines:
            print(line, file=sys.stderr)
        print(f"  {name}: {len(got)} jobs", file=sys.stderr)
        results[name] = res

    def skip(name):
        print(f"  deadline: skipping {name}", file=sys.stderr)
        state["deadline_hit"] = True

    if parallel and names:
        with ThreadPoolExecutor(max_workers=len(names)) as pool:
            futs = {}
            for s in names:
                tmo = scraper_timeout(start, deadline)
                if tmo is None:
                    skip(s)
                    continue
                futs[pool.submit(run_scraper, s, tmo)] = s
            for f in as_completed(futs):
                finish(futs[f], f.result())
    else:
        for s in names:
            tmo = scraper_timeout(start, deadline)
            if tmo is None:
                skip(s)
                continue
            finish(s, run_scraper(s, tmo))
    cut = [s for s in names if s in results and results[s][2]]
    if cut and remaining_budget(start, deadline, float("inf")) <= SCRAPER_FLOOR:
        print(f"  deadline: cut {', '.join(cut)}", file=sys.stderr)
        state["deadline_hit"] = True
    return [j for s in names if s in results for j in results[s][0]]


ATS_FULL_CHECKPOINT = HERE / "data" / "cache" / "ats-full-checkpoint.json"


def run_ats_full(profile_cfg, dry_run=False, max_cap=None):
    """Optional stage: `node scan-ats-full.mjs` — a reverse-ATS keyword sweep of
    the full public Greenhouse/Lever/Ashby/Workday/iCIMS datasets, filtered by
    portals.yml's own title_filter/location_filter (no company list needed, so
    it finds postings at companies not in portals.yml at all).

    Gated by profile.yml scan.ats_full (default false: a sweep takes ~100 min
    and would eat the whole scan deadline before any scraper starts). Unlike run_scraper(),
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
    if not cfg.get("ats_full", False):
        return 0
    cap = int(cfg.get("ats_full_cap_seconds", 900))
    if max_cap is not None:  # overall scan deadline wins over the stage cap
        if max_cap <= SCRAPER_FLOOR:
            print("  deadline: skipping ats-full", file=sys.stderr)
            return 0
        cap = min(cap, int(max_cap))
    before = len(HISTORY.read_text(errors="replace").splitlines()) if HISTORY.exists() else 0
    args = ["node", str(HERE / "scan-ats-full.mjs")]
    if ATS_FULL_CHECKPOINT.exists():
        args.append("--resume")
    if dry_run:
        args.append("--dry-run")
    try:
        proc = subprocess.run(args, capture_output=True, text=True,
                               timeout=cap, cwd=str(HERE))
        # A career-ops update that changes scan-ats-full.mjs defaults (e.g. v1.32.0
        # added bamboohr to SOURCES) makes the old checkpoint incompatible, and
        # --resume then fails on EVERY run forever. Re-pass the checkpoint's own
        # settings so the interrupted sweep finishes (keeping its unwritten
        # offers[]); once it completes the checkpoint is gone and new defaults apply.
        if proc.returncode != 0 and "different settings" in proc.stderr:
            try:
                cp = json.loads(ATS_FULL_CHECKPOINT.read_text())
                args += ["--ats", ",".join(cp["ats"])]
                if cp.get("limit") is not None:
                    args += ["--limit", str(cp["limit"])]
                if cp.get("includeUndated"):
                    args.append("--include-undated")
                print(f"  [ats-full] checkpoint predates current defaults (career-ops "
                      f"update?) — resuming with its settings: --ats {','.join(cp['ats'])}",
                      file=sys.stderr)
            except Exception:  # noqa: BLE001 — unreadable checkpoint: start fresh
                print("  [ats-full] unreadable incompatible checkpoint — deleting, "
                      "starting fresh", file=sys.stderr)
                ATS_FULL_CHECKPOINT.unlink(missing_ok=True)
                args.remove("--resume")
            proc = subprocess.run(args, capture_output=True, text=True,
                                   timeout=cap, cwd=str(HERE))
        # Any other checkpoint refusal (e.g. "company dataset changed since the
        # checkpoint" once the 24h ats-companies cache refetches between weekly
        # runs) would also fail on every run forever. No way to salvage it:
        # drop the checkpoint (its unwritten offers are lost) and sweep fresh.
        if (proc.returncode != 0 and "--resume" in args
                and "checkpoint" in proc.stderr):
            print(f"  [ats-full] checkpoint not resumable "
                  f"({proc.stderr.strip()[-160:]}) — deleting it, sweeping fresh",
                  file=sys.stderr)
            ATS_FULL_CHECKPOINT.unlink(missing_ok=True)
            args = ["node", str(HERE / "scan-ats-full.mjs")] + (["--dry-run"] if dry_run else [])
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


def run_tavily(profile_cfg, portals_cfg, start=None, deadline=None, state=None):
    """Run portals.yml search_queries via Tavily REST. Zero agent tokens.

    Stops the whole phase on the first HTTP 432 (credits exhausted: every
    further query would fail the same way) and when the overall scan deadline
    leaves < 5 s. `state` (dict) receives deadline_hit=True on a deadline stop.
    """
    import time
    import urllib.error
    start = time.monotonic() if start is None else start
    deadline = float("inf") if deadline is None else deadline
    state = {} if state is None else state
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
        left = remaining_budget(start, deadline, 30)
        if left < 5:
            print(f"  deadline: skipping remaining tavily queries (from {q.get('name','?')})",
                  file=sys.stderr)
            state["deadline_hit"] = True
            break
        try:
            req = urllib.request.Request(
                "https://api.tavily.com/search",
                data=json.dumps(payload).encode(),
                headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=left) as r:
                results = json.loads(r.read()).get("results", [])
        except urllib.error.HTTPError as e:
            if e.code == 432:
                print("  [tavily] HTTP 432 (credits exhausted) — stopping Tavily phase",
                      file=sys.stderr)
                break
            print(f"  [tavily] query failed ({q.get('name','?')}): {e}", file=sys.stderr)
            continue
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


# scan-history.tsv column order. Authority is upstream's
# lib/scan-history-columns.mjs (append-only list; v1.39 added 13-15). Read at
# runtime so a new upstream column never shifts us; the tuple is the fallback
# and the selftest asserts the two agree on every name we use.
_HISTORY_COLUMNS_FALLBACK = (
    "url", "first_seen", "portal", "title", "company", "status", "location",
    "fingerprint", "posted_at", "trust_score", "trust_flags",
    "normalized_company", "requisition_id", "language", "listing_key")
# Legacy layout this script wrote before 2026-11-07 (still in old rows).
_LEGACY_AGG_COLUMNS = ("url", "title", "company", "portal", "first_seen", "status")


def history_columns(mjs_path=None):
    p = Path(mjs_path) if mjs_path else HERE / "lib" / "scan-history-columns.mjs"
    try:
        body = re.search(r"SCAN_HISTORY_COLUMNS\s*=\s*Object\.freeze\(\[(.*?)\]\)",
                         p.read_text(), re.S).group(1)
        cols = tuple(re.findall(r"'([a-z_]+)'", body))
        if cols and cols[0] == "url":
            return cols
    except Exception:  # noqa: BLE001 — missing/reshaped file: fall back
        pass
    return _HISTORY_COLUMNS_FALLBACK


HISTORY_COLUMNS = history_columns()


def parse_history_row(line, columns=None):
    """One scan-history.tsv line -> dict keyed by column NAME ('' if absent).

    Canonical rows (scan.mjs, and this script since 2026-11-07) follow
    HISTORY_COLUMNS. Old rows this script wrote use _LEGACY_AGG_COLUMNS,
    recognised by a non-date column 1 and an ISO date in column 4. Header
    row -> None. Formula escaping (leading ' before =+-@) is undone.
    """
    parts = line.rstrip("\n").split("\t")
    if not parts or not parts[0].strip() or parts[0] == "url":
        return None
    cols = columns or HISTORY_COLUMNS
    if (len(parts) >= 5 and not _ISO_DATE.match(parts[1].strip())
            and _ISO_DATE.match(parts[4].strip())):
        cols = _LEGACY_AGG_COLUMNS
    def cell(i):
        v = parts[i].strip() if i < len(parts) else ""
        return re.sub(r"^'(?='*[=+\-@])", "", v)
    return {name: cell(i) for i, name in enumerate(cols)}


def history_line(url, first_seen, portal, title, company, status, location=""):
    """A canonical scan-history.tsv line (named columns, upstream order)."""
    rec = {"url": url, "first_seen": first_seen, "portal": portal, "title": title,
           "company": company, "status": status, "location": location}
    cells = [(rec.get(c) or "").replace("\t", " ").strip() for c in HISTORY_COLUMNS[:7]]
    return "\t".join(cells) + "\n"


def load_history():
    """Return (seen_urls, (title, company) pairs) from scan-history.tsv,
    read by column name via parse_history_row()."""
    seen = set()
    pairs = []
    if HISTORY.exists():
        for line in HISTORY.read_text(errors="replace").splitlines():
            row = parse_history_row(line)
            if not row:
                continue
            seen.add(row["url"])
            if row.get("title") or row.get("company"):
                pairs.append((row.get("title", ""), row.get("company", "")))
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
        # Missing company on either side (jobs.ch never has one, Tavily/triage
        # rows often don't) → no verdict possible, keep. Treating it as a 100%
        # company match let a token-subset title alone ("key account manager")
        # drop ~190 distinct postings per scan (2026-10-09); exact-URL dedup
        # upstream still catches true reposts.
        if not (company and oc):
            continue
        t_score = fuzz.token_set_ratio(title, ot)
        c_score = fuzz.token_set_ratio(company, oc)
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


CH_SIGNAL_TOKENS = (
    "schweiz", "switzerland", "suisse", "svizzera", "zürich", "zurich",
    "basel", "bern", "zug", "winterthur", "luzern", "lucerne", "st. gallen",
    "st.gallen", "schaffhausen", "aargau", "baar", "rotkreuz", "glattbrugg",
    "kloten", "opfikon",
)
CH_URL_TOKENS = (".ch/", "jobs.ch", "jobup.ch", "jobscout24.ch", "zueri.jobs",
                 "/in-schweiz", "switzerland", "schweiz", "zurich", "zuerich")


def has_ch_signal(title, url):
    """Any Switzerland evidence in title or URL — used to keep a location-less
    row from passing on title match alone."""
    t = (title or "").lower()
    u = (url or "").lower()
    return (any(tok in t for tok in CH_SIGNAL_TOKENS)
            or any(tok in u for tok in CH_URL_TOKENS))


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
    # Signals for the Phase 3 pre-assessment. Only what the source exposed —
    # never a guessed count. " · " (not "|") keeps the row's 3 pipe fields intact.
    extra = ""
    apl = str(j.get("applicants") or "").strip()
    if re.fullmatch(r"<?\d+\+?", apl):  # "37", "200+" (LinkedIn "Over 200"), "<25"
        extra += f" · applicants: {apl}"
    posted = (j.get("date_posted") or "").strip()[:10]
    if _ISO_DATE.match(posted):
        extra += f" · posted: {posted}"
    return (f"- [ ] {j.get('url','').strip()} | {company} | "
            f"{title}{suffix} — via {j.get('source','')}, triage{extra}\n")


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


ASSESSED_LOG = HERE / "data" / "scan-assessed.log"
_SCAN_BLOCK = re.compile(r"^## Scan (\d{4}-\d{2}-\d{2}) \(script layer")


def scan_blocks(pipeline_path=None):
    """[(key, date, header, open_rows)] for every `## Scan YYYY-MM-DD (script
    layer...)` block in pipeline.md. key = header + first URL (stable: the
    file is append-only and the reaper edits rows in place, never moves them)."""
    path = Path(pipeline_path) if pipeline_path else PIPELINE
    blocks, cur = [], None
    for line in (path.read_text(errors="replace").splitlines() if path.exists() else []):
        if line.startswith("## "):
            m = _SCAN_BLOCK.match(line)
            cur = [line, m.group(1), []] if m else None
            if cur:
                blocks.append(cur)
        elif cur is not None and line.startswith("- ["):
            cur[2].append(line)
    out = []
    for header, date, rows in blocks:
        m = _ROW_URL.search(rows[0]) if rows else None
        key = header + "\t" + (m.group(1) if m else "")
        out.append((key, date, header, [r for r in rows if r.startswith("- [ ]")]))
    return out


def unassessed_blocks(today, pipeline_path=None, log_path=None, window_days=14):
    """Scan blocks (<= window_days old) never shown to the user with a Phase 3
    glyph pass — i.e. launchd-populated rows. Old blocks are out of scope so
    the first run doesn't dump months of history."""
    log = Path(log_path) if log_path else ASSESSED_LOG
    done = set(log.read_text().splitlines()) if log.exists() else set()
    return [b for b in scan_blocks(pipeline_path)
            if b[0] not in done
            and (today - datetime.date.fromisoformat(b[1])).days <= window_days]


def mark_assessed(pipeline_path=None, log_path=None):
    """Record every current scan block as shown. Returns how many were new."""
    log = Path(log_path) if log_path else ASSESSED_LOG
    done = set(log.read_text().splitlines()) if log.exists() else set()
    new = [b[0] for b in scan_blocks(pipeline_path) if b[0] not in done]
    if new:
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a") as fh:
            fh.write("".join(k + "\n" for k in new))
    return len(new)


def selftest():
    """In-memory fuzzy-dedup assertions — no network, no real files touched."""
    import tempfile

    # location: German "…Schweiz" pseudonym regions must be blockable even
    # though they substring-match the CH allow token (Märkische Schweiz
    # borderline incident 2026-09-16) — block is checked before allow.
    _blk = ["märkische schweiz", "brandenburg"]
    assert not location_ok("Buckow (Märkische Schweiz)", ["schweiz"], _blk)
    assert location_ok("Zürich, Schweiz", ["schweiz"], _blk)
    assert title_bucket("Assistenzarzt Innere Medizin", [], ["assistenzarzt"]) == "drop"

    # tavily no-location demotion: a title-positive Tavily row with no
    # location and no CH signal anywhere must NOT pass outright (Coca-Cola
    # HBC Nigeria incident 2026-09-16) — it goes to borderline for triage.
    assert not has_ch_signal("Marketing Execution Lead, Key Accounts",
                             "https://www.aggregatorjobs.com/view/12345")
    assert has_ch_signal("Key Account Manager Zürich", "https://x.com/1")
    assert has_ch_signal("Sales Lead", "https://www.jobs.ch/en/vacancies/detail/abc/")

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

    # missing company on either side → no fuzzy verdict possible, keep (2026-10-09:
    # 199/199 fuzzy drops in one scan had no company to compare and only 10 were
    # the same title — "Business Development Manager" at South Pole was dropped
    # against a nameless historic "business development manager")
    row_no_co = {"title": "Business Development Manager", "company": "?",
                 "url": "https://example.com/job/4"}
    assert not is_dupe(row_no_co, [(normalize("Business Development Manager"), "")], [], 90), \
        "nameless title-only match wrongly flagged"
    row_co = {"title": "Business Development Manager", "company": "South Pole",
              "url": "https://example.com/job/5"}
    assert not is_dupe(row_co, [(normalize("Business Development Manager"), "")], [], 90), \
        "match against nameless history row wrongly flagged"

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
        # fuzzy corpus reads title/company from BOTH layouts
        g = globals()
        saved_hist, g["HISTORY"] = g["HISTORY"], tsv_path
        try:
            _, hp = load_history()
        finally:
            g["HISTORY"] = saved_hist
        assert ("Title A", "Company A") in hp and ("Title B", "Company B") in hp, hp

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

    # ats-full checkpoint recovery (2026-10-06): a stale checkpoint must never
    # wedge the stage. Fake node via a scripted stderr sequence; temp paths only.
    import tempfile, types
    global ATS_FULL_CHECKPOINT, HISTORY
    saved = (ATS_FULL_CHECKPOINT, HISTORY, subprocess.run)
    tmp = Path(tempfile.mkdtemp())
    ATS_FULL_CHECKPOINT, HISTORY = tmp / "cp.json", tmp / "h.tsv"
    calls = []

    def scripted(*errs):
        it = iter(errs)
        def run(a, **k):
            calls.append(list(a))
            e = next(it, "")
            return types.SimpleNamespace(returncode=1 if e else 0, stdout="", stderr=e)
        return run
    cfg = {"scan": {"ats_full": True, "ats_full_cap_seconds": 5}}
    settings = "Error: checkpoint was written with different settings"
    changed = "Error: icims company dataset changed since the checkpoint"
    try:
        # old-defaults checkpoint → resumed with its own settings
        ATS_FULL_CHECKPOINT.write_text(json.dumps({"ats": ["greenhouse"], "limit": 200, "includeUndated": True}))
        subprocess.run = scripted(settings); calls.clear(); run_ats_full(cfg)
        assert len(calls) == 2 and calls[1][-5:] == ["--ats", "greenhouse", "--limit", "200", "--include-undated"], calls
        # dataset changed → checkpoint dropped, fresh sweep
        subprocess.run = scripted(changed); calls.clear(); run_ats_full(cfg)
        assert len(calls) == 2 and "--resume" not in calls[1] and not ATS_FULL_CHECKPOINT.exists(), calls
        # chained: settings retry then dataset changed → fresh sweep with default sources
        ATS_FULL_CHECKPOINT.write_text(json.dumps({"ats": ["greenhouse"], "limit": None, "includeUndated": False}))
        subprocess.run = scripted(settings, changed); calls.clear(); run_ats_full(cfg)
        assert len(calls) == 3 and "--resume" not in calls[2] and "--ats" not in calls[2] and not ATS_FULL_CHECKPOINT.exists(), calls
    finally:
        ATS_FULL_CHECKPOINT, HISTORY, subprocess.run = saved

    # ── overall deadline: budget math (pure) ──
    assert remaining_budget(0, 600, 420, now=0) == 420          # cap binds
    assert remaining_budget(0, 600, 420, now=400) == 200        # deadline binds
    assert remaining_budget(0, 600, 420, now=700) == 0          # never negative
    assert scraper_timeout(0, 600, now=0) == 420
    assert scraper_timeout(0, 600, now=500) == 100
    assert scraper_timeout(0, 600, now=571) is None             # 29 s left -> skip
    assert scraper_timeout(0, 600, now=569) == 31

    # ── Tavily: first HTTP 432 stops the whole phase; deadline stops it too ──
    import io, urllib.error
    saved_open = urllib.request.urlopen
    hits = []
    def fake_432(req, timeout=None):
        hits.append(timeout)
        raise urllib.error.HTTPError("https://api.tavily.com/search", 432, "", {}, io.BytesIO())
    pcfg = {"tavily": {"api_key": "k"}}
    qcfg = {"search_queries": [{"name": f"q{i}", "query": f"x{i}"} for i in range(5)]}
    try:
        urllib.request.urlopen = fake_432
        assert run_tavily(pcfg, qcfg) == [] and len(hits) == 1, hits
        hits.clear(); st = {}
        import time as _t
        assert run_tavily(pcfg, qcfg, start=_t.monotonic() - 100, deadline=60, state=st) == []
        assert hits == [] and st.get("deadline_hit"), (hits, st)
    finally:
        urllib.request.urlopen = saved_open

    # ── scan-history: named columns (upstream lib/scan-history-columns.mjs) ──
    cols = history_columns()
    assert cols[:6] == ("url", "first_seen", "portal", "title", "company", "status"), cols
    assert set(_HISTORY_COLUMNS_FALLBACK) <= set(cols), "upstream renamed a column we know"
    canon15 = "\t".join(["https://x/1", "2026-11-01", "greenhouse", "Head of Strategy",
                         "Acme", "added", "Zürich", "fp", "2026-10-30", "0.9", "",
                         "acme", "R-1", "en", "lk"])
    r = parse_history_row(canon15)
    assert (r["title"], r["company"], r["first_seen"], r["requisition_id"],
            r["listing_key"]) == ("Head of Strategy", "Acme", "2026-11-01", "R-1", "lk"), r
    legacy = "https://x/2\tKAM\tBeta AG\tjobs.ch\t2026-10-01\tborderline"
    r = parse_history_row(legacy)
    assert (r["title"], r["company"], r["portal"], r["first_seen"]) == \
        ("KAM", "Beta AG", "jobs.ch", "2026-10-01"), r
    assert parse_history_row("url\tfirst_seen\tportal") is None
    assert parse_history_row("https://x/3\t2026-11-01\tp\t'=SUM(A1)\tC\tadded")["title"] == "=SUM(A1)"
    # our writer emits the canonical layout and reads back by name
    w = parse_history_row(history_line("https://x/4", "2026-11-07", "tavily", "T\tx", "Co", "added"))
    assert (w["first_seen"], w["portal"], w["title"], w["company"]) == \
        ("2026-11-07", "tavily", "T x", "Co"), w

    # ── applicants / posted in pipeline rows: shown when known, never invented ──
    row = pipeline_row({"url": "u", "company": "C", "title": "T", "source": "linkedin-guest",
                        "applicants": "12", "date_posted": "2026-11-05"})
    assert row.rstrip().endswith("triage · applicants: 12 · posted: 2026-11-05"), row
    assert "applicants" not in pipeline_row({"url": "u", "title": "T", "applicants": "over 100"})
    assert "applicants: 200+" in pipeline_row({"url": "u", "title": "T", "applicants": "200+"})

    # ── Phase 0: unassessed launchd blocks ──
    with tempfile.TemporaryDirectory() as td:
        pp, lp = Path(td) / "p.md", Path(td) / "a.log"
        pp.write_text("# Pipeline\n\n## Scan 2026-11-02 (script layer + tavily)\n\n"
                      "- [ ] https://a/1 | A | T1 — via tavily, triage\n"
                      "## Scan 2026-09-01 (script layer)\n\n- [ ] https://a/0 | Z | T0\n")
        d = datetime.date(2026, 11, 7)
        ub = unassessed_blocks(d, pp, lp)
        assert len(ub) == 1 and ub[0][1] == "2026-11-02" and len(ub[0][3]) == 1, ub
        assert mark_assessed(pp, lp) == 2 and unassessed_blocks(d, pp, lp) == []
        with pp.open("a") as fh:
            fh.write("\n## Scan 2026-11-02 (script layer)\n\n- [ ] https://a/9 | B | T9\n")
        assert [b[3] for b in unassessed_blocks(d, pp, lp)] == [["- [ ] https://a/9 | B | T9"]]

    # ── scrapers: parallel == sequential output; slow one cut without blocking ──
    import time as _t
    names = ["jobspy_scan.py", "jobs_ch.py", "stepstone_scan.py", "zuerijobs_scan.py"]
    ran, tmos = [], {}

    def fake_run(a, **k):
        n = Path(a[1]).name
        ran.append(n); tmos[n] = k["timeout"]
        if n == "zuerijobs_scan.py":           # slow: killed by its own timeout
            _t.sleep(0.5)
            raise subprocess.TimeoutExpired(a, k["timeout"])
        _t.sleep(0.4 if n == "jobspy_scan.py" else 0.1)  # first finishes last
        jobs = [{"url": f"https://{n}/{i}", "title": f"{n} {i}"} for i in range(2)]
        return types.SimpleNamespace(returncode=0, stdout=json.dumps(jobs), stderr="")
    saved_run = subprocess.run
    try:
        subprocess.run = fake_run
        t = _t.monotonic(); seq = run_scrapers(names, t, 600, parallel=False)
        t_seq = _t.monotonic() - t
        assert tmos == {n: 420 for n in names}, tmos
        t = _t.monotonic(); par = run_scrapers(names, t, 600, parallel=True)
        t_par = _t.monotonic() - t
        assert par == seq and len(par) == 6, (par, seq)
        assert [j["url"] for j in par][:2] == ["https://jobspy_scan.py/0", "https://jobspy_scan.py/1"]
        assert t_seq >= 1.0 and t_par < 0.8, (t_seq, t_par)   # max, not sum
        # scan.scrapers selection (short names or script filenames)
        assert resolve_scrapers({}) == SCRAPERS
        assert resolve_scrapers({"scan": {"scrapers": []}}) == []
        assert resolve_scrapers({"scan": {"scrapers": ["jobspy", "jobs_ch"]}}) == ["jobspy_scan.py", "jobs_ch.py"]
        try: resolve_scrapers({"scan": {"scrapers": ["nope"]}}); assert False
        except ValueError: pass
        two = resolve_scrapers({"scan": {"scrapers": ["jobs_ch.py", "jobspy"]}})
        assert two == ["jobs_ch.py", "jobspy_scan.py"], two
        ran.clear(); run_scrapers(two, _t.monotonic(), 600)
        assert sorted(ran) == sorted(two), ran
    finally:
        subprocess.run = saved_run

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
    ap.add_argument("--inject", metavar="JSON",
                    help="funnel an external JSON job list (agent web search, "
                         "deep/run_deep.py) through the same filters/dedup; "
                         "skips scrapers and ats-full")
    ap.add_argument("--deadline-seconds", type=float, default=None,
                    help=f"overall wall-clock budget (default: profile.yml "
                         f"scan.deadline_seconds, else {DEFAULT_DEADLINE})")
    ap.add_argument("--stamp", metavar="PATH",
                    help="touch PATH on success (raw>0, not dry-run) — the "
                         "launchd weekly-run success marker")
    ap.add_argument("--unassessed", action="store_true",
                    help="print recent `## Scan` blocks never given the Phase 3 "
                         "glyph pass (launchd rows), then exit")
    ap.add_argument("--mark-assessed", action="store_true",
                    help="record all current `## Scan` blocks as shown, then exit")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    import time
    t0 = time.monotonic()
    today = datetime.date.fromisoformat(args.date)

    if args.unassessed:
        blocks = unassessed_blocks(today)
        for _, _, header, rows in blocks:
            print(header)
            print("\n".join(rows) if rows else "  (no open rows left)")
            print()
        print(f"unassessed blocks: {len(blocks)}")
        return
    if args.mark_assessed:
        print(f"marked assessed: {mark_assessed()}")
        return

    portals, profile, pos, neg, allow, block = load_cfgs()
    deadline = float(args.deadline_seconds if args.deadline_seconds is not None
                     else (profile.get("scan") or {}).get("deadline_seconds",
                                                          DEFAULT_DEADLINE))
    state = {"deadline_hit": False}
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
    ats_full_new = 0 if args.inject else run_ats_full(
        profile, dry_run=args.dry_run,
        max_cap=remaining_budget(t0, deadline, float("inf")))
    print(f"  ats-full: {ats_full_new} new rows", file=sys.stderr)

    seen, history_pairs = load_history()
    applied_pairs = load_applications()
    static_corpus = [(normalize(t), normalize(c)) for t, c in history_pairs + applied_pairs]

    jobs = []
    # ponytail: --inject replaces the scraper stage, the funnel below is shared
    if args.inject:
        jobs = json.load(open(args.inject))
        print(f"  inject: {len(jobs)} jobs from {args.inject}", file=sys.stderr)
    else:
        jobs = run_scrapers(resolve_scrapers(profile), t0, deadline,
                            parallel=(profile.get("scan") or {}).get("parallel_scrapers", True),
                            state=state)
    if args.tavily:
        got = run_tavily(profile, portals, start=t0, deadline=deadline, state=state)
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
        # A location-less row (Tavily/aggregator) can't earn an outright pass
        # on title alone — without any CH signal in title or URL it may be
        # anywhere on earth (Coca-Cola HBC Nigeria, 2026-09-16). Demote to
        # borderline so triage judges it instead.
        if (bucket == "pass" and not (j.get("location") or "").strip()
                and not has_ch_signal(j.get("title"), url)):
            bucket = "borderline"
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
                fh.write(history_line(
                    j.get("url", "").strip(), args.date, j.get("source", ""),
                    j.get("title") or "", j.get("company") or "", status,
                    j.get("location") or ""))
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

    if args.stamp and raw > 0 and not args.dry_run:
        Path(args.stamp).touch()
    print(f"funnel: raw={raw} kept={len(passed) + len(borderline)} "
          f"elapsed={int(time.monotonic() - t0)}s "
          f"deadline_hit={'yes' if state['deadline_hit'] else 'no'}")
    # non-zero only when every layer came back empty (all scrapers dead,
    # Tavily out of credits, ...) so callers can tell "no jobs" from "broken"
    if raw == 0 and ats_full_new == 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
