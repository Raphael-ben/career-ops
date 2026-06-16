#!/usr/bin/env python3
"""
jobs_ch.py — jobs.ch scraper for /jobhunter scan (Level 4b).

Reads search_terms from config/profile.yml (jobspy block), hits the
jobs.ch SSR search page per term, extracts job links, outputs JSON.

Usage:
  python jobs_ch.py                      # run with profile.yml
  python jobs_ch.py --config path.yml    # custom config path
  python jobs_ch.py --dry-run            # return mock data, no HTTP
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
    "url": "https://www.jobs.ch/en/vacancies/detail/12345678-0000-0000-0000-000000000000/",
    "source": "jobsch",
    "location": "Zürich",
    "date_posted": "",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "en-US,en;q=0.9",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
}


def load_config(config_path: str) -> dict:
    import yaml
    path = Path(config_path)
    if not path.exists():
        print(f"Error: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)
    with open(path) as f:
        profile = yaml.safe_load(f) or {}
    return profile.get("jobspy", {})


def clean_title(raw: str) -> str:
    """Strip jobs.ch card metadata from raw link text, leaving only the job title."""
    text = raw.strip()
    # Strip leading date tokens: "3 days ago", "Last week", "Yesterday", "2 hours ago", "Just now"
    text = re.sub(r'^\d+\s+\w+\s+ago\s*', '', text, flags=re.IGNORECASE).strip()
    text = re.sub(r'^(?:last\s+\w+|yesterday|just\s+now)\s*', '', text, flags=re.IGNORECASE).strip()
    # Strip leading "New" badge
    text = re.sub(r'^New\s+', '', text, flags=re.IGNORECASE).strip()
    # Truncate at the first card metadata marker
    for marker in ('Place of work:', 'Workload:', 'Contract type:', 'Is this job relevant', 'Easy apply'):
        idx = text.lower().find(marker.lower())
        if idx != -1:
            text = text[:idx].strip()
    return re.sub(r'\s+', ' ', text).strip()


def scrape_term(session, term: str) -> list:
    """Fetch one search results page and extract job listings."""
    from scrapling import Selector

    url = f"https://www.jobs.ch/en/vacancies/?term={quote_plus(term)}&region=Zurich"
    try:
        resp = session.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
    except Exception as e:
        print(f"Warning: jobs.ch request failed for '{term}': {e}", file=sys.stderr)
        return []

    html = resp.text
    jobs: list = []
    seen_hrefs: set = set()

    # Parse with Scrapling CSS selectors
    try:
        page = Selector(html)
        links = page.css('a[href*="/vacancies/detail/"]')
    except Exception:
        links = []

    for link in links:
        try:
            href = ""
            try:
                href = link.attrib.get("href", "") or ""
            except (AttributeError, TypeError):
                try:
                    href = link["href"] or ""
                except Exception:
                    pass

            if not href or "/vacancies/detail/" not in href:
                continue

            # Normalize to absolute URL, strip query params
            if href.startswith("/"):
                href = "https://www.jobs.ch" + href
            href = href.split("?")[0].rstrip("/") + "/"

            if href in seen_hrefs:
                continue
            seen_hrefs.add(href)

            # Extract title from all text inside the <a> element, then strip card metadata
            raw = ""
            try:
                raw = link.get_all_text().strip()
            except AttributeError:
                try:
                    raw = link.text_content().strip()
                except Exception:
                    pass

            title = clean_title(raw)
            if not title or len(title) < 5 or len(title) > 200:
                continue

            jobs.append({
                "title": title,
                "company": "",
                "url": href,
                "source": "jobsch",
                "location": "Zürich",
                "date_posted": "",
            })
        except Exception as e:
            print(f"Warning: failed to parse jobs.ch link: {e}", file=sys.stderr)

    # Regex fallback if Scrapling returned nothing (parser failure)
    if not jobs:
        for match in re.finditer(r'href="(/en/vacancies/detail/[^"?]+)', html):
            href = "https://www.jobs.ch" + match.group(1).rstrip("/") + "/"
            if href not in seen_hrefs:
                seen_hrefs.add(href)
                jobs.append({
                    "title": term,
                    "company": "",
                    "url": href,
                    "source": "jobsch",
                    "location": "Zürich",
                    "date_posted": "",
                })

    return jobs


def scrape(config: dict) -> list:
    import requests

    search_terms = config.get("search_terms", [])
    if not search_terms:
        return []

    session = requests.Session()
    all_jobs: list = []

    for i, term in enumerate(search_terms):
        if i > 0:
            time.sleep(2)  # polite delay between terms
        try:
            jobs = scrape_term(session, term)
            all_jobs.extend(jobs)
        except Exception as e:
            print(f"Warning: jobs.ch scrape failed for '{term}': {e}", file=sys.stderr)

    # Deduplicate by URL across all terms
    seen: set = set()
    unique: list = []
    for job in all_jobs:
        if job["url"] not in seen:
            seen.add(job["url"])
            unique.append(job)

    return unique


def main() -> None:
    parser = argparse.ArgumentParser(description="jobs.ch scraper for /jobhunter scan")
    parser.add_argument("--dry-run", action="store_true",
                        help="Return mock data without HTTP requests")
    parser.add_argument("--config", default="config/profile.yml",
                        help="Path to profile.yml (default: config/profile.yml)")
    args = parser.parse_args()

    if args.dry_run:
        print(json.dumps([MOCK_JOB]))
        return

    config = load_config(args.config)
    jobs = scrape(config)
    print(json.dumps(jobs))


if __name__ == "__main__":
    main()
