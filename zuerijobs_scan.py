#!/usr/bin/env python3
"""
zuerijobs_scan.py — Züri.Jobs scraper for /jobhunter scan.

Same contract as jobs_ch.py/stepstone_scan.py: reads jobspy.search_terms from
config/profile.yml, outputs a JSON array, ALWAYS exits 0 (empty list on
failure/block).

INVESTIGATION NOTE (2026-07-18): the real domain is zueri.jobs (www.zueri.jobs
redirects fine; the punycode xn--zri-hoa.jobs form also resolves but zueri.jobs
is simpler and what the site itself links to). It's a Laravel-ish board with a
plain GET search: /jobs?q=<term>. Results are NOT server-rendered as HTML cards
— instead each page embeds
`window.jobsList = window.jobsList.concat([{...}, {...}]);`
script blocks holding full job objects (id, title, location, posted_at ISO
timestamp, employer.name, job_details_path) that the client-side JS renders
into the visible list. We read the JS array literal directly (it's valid JSON)
instead of scraping rendered HTML — cleanest, most complete data of the three
new scrapers (real ISO posted_at, unlike efc/jobscout24's relative-age tokens).
Small, Zürich-only board (~10-15 results per broad query) — that's the ceiling,
not a parsing gap.
# ponytail: JS-array-literal extraction, no per-job detail fetch — if the site
# switches to a fully client-fetched API, this degrades to [] via the regex
# fallback / exception handler and the scan continues.

Usage:
  python3 zuerijobs_scan.py            # live
  python3 zuerijobs_scan.py --dry-run  # mock, no HTTP
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3")
if not _os.path.exists(_VENV_PY):
    _VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, _HERE)
import scan_http

DOMAIN = "https://www.zueri.jobs"

MOCK_JOB = {
    "title": "Business Development Manager",
    "company": "",
    "url": "https://www.zueri.jobs/jobs/123456-example",
    "source": "zuerijobs",
    "location": "Zürich, Schweiz",
    "date_posted": "",
}


def load_terms(config_path="config/profile.yml"):
    import yaml
    path = Path(config_path)
    if not path.is_absolute():
        path = Path(_HERE) / config_path
    if not path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        return []
    profile = yaml.safe_load(path.read_text()) or {}
    return (profile.get("jobspy") or {}).get("search_terms", [])


def clean_query(term: str) -> str:
    """Strip the trailing Swiss location suffix our search_terms always carry
    ('... Switzerland' / '... Zürich') — the board is Zürich-only already, and
    keeping the literal word breaks keyword matching against job titles
    (verified: 'Business Development' finds 11 hits, 'Business Development
    Switzerland' finds 0)."""
    t = term.strip()
    for suffix in ("switzerland", "zürich", "zurich"):
        if t.lower().endswith(suffix):
            t = t[: -len(suffix)].strip()
    return t


def scrape_term(term: str) -> list:
    query = clean_query(term)
    if not query:
        return []
    url = f"{DOMAIN}/jobs?q={quote_plus(query)}"
    resp = scan_http.get(url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "no-response"
        print(f"Warning: zuerijobs {code} for '{term}'", file=sys.stderr)
        return []
    html = resp.text

    jobs, seen = [], set()
    raw_jobs = []
    for m in re.finditer(
            r"window\.jobsList = window\.jobsList\.concat\((\[.*?\])\);",
            html, re.S):
        try:
            raw_jobs.extend(json.loads(m.group(1)))
        except Exception as e:
            print(f"Warning: failed to parse zuerijobs jobsList block: {e}", file=sys.stderr)

    for j in raw_jobs:
        try:
            path = (j.get("job_details_path") or "").strip()
            title = (j.get("title") or "").strip()
            if not path or not title:
                continue
            href = DOMAIN + path if path.startswith("/") else path
            if href in seen:
                continue
            seen.add(href)

            employer = j.get("employer") or {}
            date_posted = (j.get("posted_at") or "")[:10]  # ISO timestamp -> date

            jobs.append({
                "title": title[:150],
                "company": (employer.get("name") or "").strip(),
                "url": href,
                "source": "zuerijobs",
                "location": (j.get("location") or "").strip(),
                "date_posted": date_posted,
            })
        except Exception as e:
            print(f"Warning: failed to parse zuerijobs job object: {e}", file=sys.stderr)

    # Regex fallback if the jobsList blocks were absent/reshaped but the page
    # still has job detail links embedded.
    if not jobs:
        for m in re.finditer(r'href="(/jobs/\d+-[^"?]+)"', html):
            href = DOMAIN + m.group(1)
            if href not in seen:
                seen.add(href)
                jobs.append({
                    "title": term,
                    "company": "",
                    "url": href,
                    "source": "zuerijobs",
                    "location": "",
                    "date_posted": "",
                })

    return jobs


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.dry_run:
        print(json.dumps([MOCK_JOB]))
        return

    all_jobs, seen = [], set()
    for i, term in enumerate(load_terms()):
        if i > 0:
            time.sleep(2)
        try:
            for j in scrape_term(term):
                if j["url"] not in seen:
                    seen.add(j["url"])
                    all_jobs.append(j)
        except Exception as e:
            print(f"Warning: zuerijobs scrape failed for '{term}': {e}", file=sys.stderr)
    print(json.dumps(all_jobs))


if __name__ == "__main__":
    main()
