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

NOTE: Run via the project venv to ensure python-jobspy is available:
  .venv/bin/python3 jobspy_scan.py
"""
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
    "linkedin", "indeed", "glassdoor", "google",
    "zip_recruiter", "bayt", "naukri",
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
    from jobspy import scrape_jobs

    search_terms = config.get("search_terms", [])
    location = config.get("location", "")
    results_wanted = int(config.get("results_wanted", 20))
    hours_old = int(config.get("hours_old", 72))

    all_jobs = []
    for term in search_terms:
        try:
            df = scrape_jobs(
                site_name=SUPPORTED_SITES,
                search_term=term,
                location=location,
                results_wanted=results_wanted,
                hours_old=hours_old,
                description_format="markdown",
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
    jobs = scrape(config)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
