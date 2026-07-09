#!/usr/bin/env python3
"""
stepstone_scan.py — stepstone.ch scraper for /jobhunter scan (Level 4c).

Same contract as jobs_ch.py: reads jobspy.search_terms from config/profile.yml,
outputs a JSON array, ALWAYS exits 0 (empty list on failure/block).

Stepstone sits behind bot protection; we fetch with curl_cffi Chrome
impersonation (installed via scrapling[ai]).
# ponytail: listing-page regex parse, no per-job detail fetch — if Stepstone
# changes markup or hard-blocks, this degrades to [] and the scan continues.

Usage:
  python3 stepstone_scan.py            # live
  python3 stepstone_scan.py --dry-run  # mock, no HTTP
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

MOCK_JOB = {
    "title": "Business Development Manager",
    "company": "",
    "url": "https://www.stepstone.ch/stellenangebote--Example--12345-inline.html",
    "source": "stepstone",
    "location": "",
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


def scrape_term(term: str) -> list:
    from curl_cffi import requests as cffi_requests

    # Stepstone CH search; ag=age_1w server-side filters to postings ≤7 days old
    kw = quote_plus(term.replace(" Switzerland", "").replace(" Zürich", ""))
    url = f"https://www.stepstone.ch/work/{kw}?ag=age_1w"
    try:
        resp = cffi_requests.get(url, impersonate="chrome", timeout=20)
        if resp.status_code != 200:
            print(f"Warning: stepstone {resp.status_code} for '{term}'", file=sys.stderr)
            return []
        html = resp.text
    except Exception as e:
        print(f"Warning: stepstone request failed for '{term}': {e}", file=sys.stderr)
        return []

    jobs, seen = [], set()
    # Job links: /stellenangebote--Title-Location-Company--ID-inline.html
    for m in re.finditer(
            r'href="(/stellenangebote--([^"]+?)--\d+-inline\.html)[^"]*"', html):
        href = "https://www.stepstone.ch" + m.group(1)
        if href in seen:
            continue
        seen.add(href)
        title = m.group(2).replace("-", " ").strip()  # slug → readable guess
        if len(title) < 5:
            continue
        jobs.append({
            "title": title[:150],
            "company": "",
            "url": href,
            "source": "stepstone",
            "location": "",
            "date_posted": "",  # ag=age_1w keeps results ≤7 days old
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
            print(f"Warning: stepstone scrape failed for '{term}': {e}", file=sys.stderr)
    print(json.dumps(all_jobs))


if __name__ == "__main__":
    main()
