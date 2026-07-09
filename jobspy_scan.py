#!/usr/bin/env python3
"""
jobspy_scan.py — JobSpy scraper for /jobhunter scan (Level 4).

Powered by python-jobspy: https://github.com/cullenwatson/JobSpy
License: MIT

Reads search config from config/profile.yml (jobspy block), scrapes all
supported boards concurrently via HTTP, deduplicates by URL, outputs
JSON array to stdout.

Usage:
  python jobspy_scan.py                      # run with profile.yml
  python jobspy_scan.py --config path.yml    # custom config path
  python jobspy_scan.py --dry-run            # return mock data, no HTTP
"""
import os as _os, sys as _sys

# If not already running inside the project venv, re-exec with it so that
# python-jobspy and pyyaml are always available regardless of which python3
# the caller used (agent subprocess, system python3, etc.).
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3")
if not _os.path.exists(_VENV_PY):
    _VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import sys
if sys.version_info < (3, 10):
    print(f"[]", flush=True)
    raise SystemExit(f"jobspy_scan: Python ≥3.10 required, got {sys.version.split()[0]}. "
                     f"Run with .venv/bin/python3 instead of system python3.")
import argparse
import json
import sys
from pathlib import Path


MOCK_JOB = {
    "title": "Head of Applied AI",
    "company": "Acme Corp",
    "url": "https://example.com/jobs/1",
    "source": "linkedin",
    "location": "Switzerland",
    "date_posted": "2026-05-12",
}

SUPPORTED_SITES = [
    "linkedin", "indeed", "google",
    # glassdoor removed — consistently returns API errors
    # google re-enabled 2026-07-09: aggregates company career pages + boards we don't reach
]


def load_config(config_path: str) -> dict:
    import yaml
    path = Path(config_path)
    if not path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        profile = yaml.safe_load(f) or {}
    return profile.get("jobspy", {})


def scrape(config: dict) -> list:
    import time
    from jobspy import scrape_jobs

    search_terms = config.get("search_terms", [])
    location = config.get("location", "")
    results_wanted = int(config.get("results_wanted", 20))
    hours_old = int(config.get("hours_old", 72))
    sleep_between = float(config.get("sleep_between_terms", 3.0))

    all_jobs = []
    for i, term in enumerate(search_terms):
        if i > 0:
            time.sleep(sleep_between)  # avoid LinkedIn 429 rate-limit
        try:
            df = scrape_jobs(
                site_name=SUPPORTED_SITES,
                search_term=term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                country_indeed="switzerland",
                description_format="markdown",
                linkedin_fetch_description=False,  # skip per-job detail fetch; halves request count
                # google board ignores search_term/location — needs its own literal query.
                # "since last week" biases Google Jobs toward fresh postings.
                google_search_term=f"{term} since last week",
            )
        except Exception as e:
            print(f"Warning: scrape failed for '{term}': {e}", file=sys.stderr)
            continue

        for _, row in df.iterrows():
            url = str(row.get("job_url", "") or "")
            if not url:
                continue
            all_jobs.append({
                "title": str(row.get("title", "") or ""),
                "company": str(row.get("company", "") or ""),
                "url": url,
                "source": str(row.get("site", "") or ""),
                "location": str(row.get("location", "") or ""),
                "date_posted": str(row.get("date_posted", "") or ""),
            })

    # Deduplicate by URL
    seen: set = set()
    unique: list = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)
    return unique


def main() -> None:
    parser = argparse.ArgumentParser(
        description="JobSpy scraper for /jobhunter scan (Level 4)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Return mock data without making HTTP requests"
    )
    parser.add_argument(
        "--config", default="config/profile.yml",
        help="Path to profile.yml (default: config/profile.yml)"
    )
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps([MOCK_JOB]))
        return

    config = load_config(args.config)
    try:
        jobs = scrape(config)
    except Exception as e:
        print(f"Error: scrape() crashed: {e}", file=sys.stderr)
        jobs = []
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
