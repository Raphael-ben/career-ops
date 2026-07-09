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
import subprocess
import sys
import urllib.request
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PORTALS = HERE / "portals.yml"
PROFILE = HERE / "config" / "profile.yml"
HISTORY = HERE / "data" / "scan-history.tsv"
PIPELINE = HERE / "data" / "pipeline.md"
SCRAPERS = ["jobspy_scan.py", "jobs_ch.py", "stepstone_scan.py"]

# Tavily results that are search/directory pages, not individual postings
DIRECTORY_HINTS = ("/vacancies?", "/vacancies/?", "/occupations/", "/jobs?",
                   "/search?", "/en/jobs/", "/jobs/in-")


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


def run_tavily(profile_cfg, portals_cfg):
    """Run portals.yml search_queries via Tavily REST. Zero agent tokens."""
    key = ((profile_cfg.get("tavily") or {}).get("api_key") or "").strip()
    if not key:
        print("  [tavily] no api_key in profile.yml → skipped "
              "(agent MCP fallback per rb/scan.md)", file=sys.stderr)
        return []
    jobs = []
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
        payload = {"api_key": key, "query": query, "search_depth": "advanced",
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
            if not url or any(h in url for h in DIRECTORY_HINTS):
                continue  # directory/search page, not an individual posting
            jobs.append({"title": res.get("title", ""), "company": "",
                         "url": url, "source": "tavily",
                         "location": "", "date_posted": ""})
    return jobs


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
    seen = set()
    if HISTORY.exists():
        for line in HISTORY.read_text(errors="replace").splitlines():
            if line.strip():
                seen.add(line.split("\t")[0].strip())
    return seen


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--tavily", action="store_true",
                    help="also run portals.yml search_queries via Tavily REST")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()
    today = datetime.date.fromisoformat(args.date)

    portals, profile, pos, neg, allow, block = load_cfgs()
    max_age = int((profile.get("scan") or {}).get("max_age_days", 45))
    seen = load_history()

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

    passed, borderline, run_seen = [], [], set()
    dropped_neg = 0
    for j in lpass:
        url = (j.get("url") or "").strip()
        if not url or url in seen or url in run_seen:
            continue
        bucket = title_bucket(j.get("title"), pos, neg)
        if bucket == "drop":
            dropped_neg += 1
            continue
        run_seen.add(url)
        (passed if bucket == "pass" else borderline).append(j)

    print(f"\nFunnel: raw={raw}  fresh(<={max_age}d)={len(fresh)}  "
          f"location_ok={len(lpass)}  neg_dropped={dropped_neg}  "
          f"NEW pass={len(passed)}  NEW borderline={len(borderline)}")

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
