#!/usr/bin/env python3
"""
jobscout24_scan.py — JobScout24 scraper for /jobhunter scan.

Same contract as jobs_ch.py/stepstone_scan.py: reads jobspy.search_terms from
config/profile.yml, outputs a JSON array, ALWAYS exits 0 (empty list on
failure/block).

INVESTIGATION NOTE (2026-07-18): jobscout24.ch's visible search box posts to
/en/jobs/search/ (CSRF-token form, method="post") — but the plain listing page
/en/jobs/ also accepts the same field as a GET query string
(?SearchWhat=<term>) and returns the filtered result set server-rendered, no
token needed (verified: 90300 unfiltered vacancies on the bare listing page vs
432 with ?SearchWhat=Business+Development). Each result is a
<li class="job-list-item" data-job-detail-url="/en/job/<uuid>/"> with a
`.job-title` link, a `.job-attributes` paragraph (two <span> children: company,
location) and a `.job-date` paragraph carrying an abbreviated relative age token
("1 d", "5 d", "1 w", "3 w", "1+m") that we convert to an ISO date.
# ponytail: CSS-attribute parse, no per-job detail fetch — if JobScout24
# changes markup or the GET-query search path stops working, this degrades to
# [] via the regex fallback / exception handler and the scan continues.

Usage:
  python3 jobscout24_scan.py            # live
  python3 jobscout24_scan.py --dry-run  # mock, no HTTP
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3")
if not _os.path.exists(_VENV_PY):
    _VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import argparse
import datetime
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import quote_plus

sys.path.insert(0, _HERE)
import scan_http

DOMAIN = "https://www.jobscout24.ch"

MOCK_JOB = {
    "title": "Business Development Manager",
    "company": "",
    "url": "https://www.jobscout24.ch/en/job/00000000-0000-0000-0000-000000000000/",
    "source": "jobscout24",
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


def parse_age(raw: str) -> str:
    """Abbreviated relative-age token ('1 d', '5 d', '1 w', '3 w', '1+m')
    -> ISO date. Returns '' if no recognized token."""
    text = raw.strip().lower()
    today = datetime.date.today()
    m = re.match(r"^(\d+)\+?\s*(d|w|m)$", text)
    if not m:
        return ""
    n, unit = int(m.group(1)), m.group(2)
    days = {"d": 1, "w": 7, "m": 30}[unit] * n
    return (today - datetime.timedelta(days=days)).isoformat()


def scrape_term(term: str) -> list:
    from scrapling import Selector

    url = f"{DOMAIN}/en/jobs/?SearchWhat={quote_plus(term)}"
    resp = scan_http.get(url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "no-response"
        print(f"Warning: jobscout24 {code} for '{term}'", file=sys.stderr)
        return []
    html = resp.text

    jobs, seen = [], set()
    try:
        page = Selector(html)
        cards = page.css("li.job-list-item")
    except Exception:
        cards = []

    for card in cards:
        try:
            href = card.attrib.get("data-job-detail-url", "") or ""
            title_els = card.css("a.job-title")
            title = title_els[0].get_all_text().strip() if title_els else ""
            if not href or not title:
                continue
            if href.startswith("/"):
                href = DOMAIN + href
            if href in seen:
                continue
            seen.add(href)

            attr_spans = card.css("p.job-attributes span")
            company = attr_spans[0].get_all_text().strip() if len(attr_spans) > 0 else ""
            location = attr_spans[1].get_all_text().strip() if len(attr_spans) > 1 else ""
            date_els = card.css("p.job-date")
            date_raw = date_els[0].get_all_text().strip() if date_els else ""

            jobs.append({
                "title": title[:150],
                "company": company,
                "url": href,
                "source": "jobscout24",
                "location": location,
                "date_posted": parse_age(date_raw),
            })
        except Exception as e:
            print(f"Warning: failed to parse jobscout24 card: {e}", file=sys.stderr)

    # Regex fallback if the CSS parser found no cards (markup change) but the
    # page still has job detail links embedded.
    if not jobs:
        for m in re.finditer(r'data-job-detail-url="(/en/job/[^"]+)"', html):
            href = DOMAIN + m.group(1)
            if href not in seen:
                seen.add(href)
                jobs.append({
                    "title": term,
                    "company": "",
                    "url": href,
                    "source": "jobscout24",
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
            print(f"Warning: jobscout24 scrape failed for '{term}': {e}", file=sys.stderr)
    print(json.dumps(all_jobs))


if __name__ == "__main__":
    main()
