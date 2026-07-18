#!/usr/bin/env python3
"""
stepstone_scan.py — StepStone scraper for /jobhunter scan (Level 4c).

Same contract as jobs_ch.py: reads jobspy.search_terms from config/profile.yml,
outputs a JSON array, ALWAYS exits 0 (empty list on failure/block).

INVESTIGATION NOTE (2026-07-18): stepstone.ch is dead — the entire domain
301-redirects unconditionally to hotelcareer.ch (a hospitality-only board, no
BDM/corporate listings) regardless of path. This isn't a bot-block, the .ch
site was decommissioned. The live Swiss-market channel is stepstone.de with a
"/in-schweiz" location suffix on the search URL — verified to return real
Swiss (and DACH-wide) listings for every search_terms entry tried. Listings
are plain server-rendered HTML (no JSON-LD JobPosting data, no useful
__PRELOADED_STATE__ job payload) — each result is an
<article data-testid="job-item"> card with data-at="job-item-title" /
-company-name / -location / -timeago children. We parse those directly.
# ponytail: CSS-attribute parse, no per-job detail fetch — if StepStone
# changes markup or blocks curl_cffi impersonation too, this degrades to
# [] via the regex fallback / exception handler and the scan continues.

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
import datetime
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, _HERE)
import scan_http

DOMAIN = "https://www.stepstone.de"

MOCK_JOB = {
    "title": "Business Development Manager",
    "company": "",
    "url": "https://www.stepstone.de/stellenangebote--Example--12345-inline.html",
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


def slugify(term: str) -> str:
    """'Business Development Manager Switzerland' -> 'business-development-manager'.
    Strips the Swiss location suffix our search_terms always carry (the
    /in-schweiz URL segment already scopes the search to Switzerland)."""
    t = term.strip().lower()
    for suffix in ("switzerland", "zürich", "zurich"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    t = re.sub(r"[^a-z0-9äöüß\s-]", " ", t)
    return re.sub(r"\s+", "-", t).strip("-")


def parse_age(raw: str) -> str:
    """German relative-age token ('vor 3 Tagen', 'vor 1 Woche', 'Heute', …)
    -> ISO date. Returns '' if no recognized token."""
    text = raw.strip().lower()
    today = datetime.date.today()
    if text == "heute":
        return today.isoformat()
    if text == "gestern":
        return (today - datetime.timedelta(days=1)).isoformat()
    m = re.match(r"^vor\s+(\d+)\s+(stunde|tag|woche|monat)", text)
    if m:
        n, unit = int(m.group(1)), m.group(2)
        days = {"stunde": 0, "tag": 1, "woche": 7, "monat": 30}[unit] * n
        return (today - datetime.timedelta(days=days)).isoformat()
    return ""


def scrape_term(term: str) -> list:
    from scrapling import Selector

    slug = slugify(term)
    url = f"{DOMAIN}/jobs/{slug}/in-schweiz"
    resp = scan_http.get(url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "no-response"
        print(f"Warning: stepstone {code} for '{term}'", file=sys.stderr)
        return []
    html = resp.text

    jobs, seen = [], set()
    try:
        page = Selector(html)
        cards = page.css('[data-testid="job-item"]')
    except Exception:
        cards = []

    for card in cards:
        try:
            title_els = card.css('[data-at="job-item-title"]')
            if not title_els:
                continue
            title_el = title_els[0]
            href = title_el.attrib.get("href", "") or ""
            title = title_el.get_all_text().strip()
            if not href or not title or len(title) < 3:
                continue
            if href.startswith("/"):
                href = DOMAIN + href
            if href in seen:
                continue
            seen.add(href)

            comp_els = card.css('[data-at="job-item-company-name"]')
            loc_els = card.css('[data-at="job-item-location"]')
            time_els = card.css('[data-at="job-item-timeago"]')
            company = comp_els[0].get_all_text().strip() if comp_els else ""
            location = loc_els[0].get_all_text().strip() if loc_els else ""
            timeago = time_els[0].get_all_text().strip() if time_els else ""

            jobs.append({
                "title": title[:150],
                "company": company,
                "url": href,
                "source": "stepstone",
                "location": location,
                "date_posted": parse_age(timeago),
            })
        except Exception as e:
            print(f"Warning: failed to parse stepstone card: {e}", file=sys.stderr)

    # Regex fallback if the CSS parser found no cards (markup change) but
    # the page still has job links embedded.
    if not jobs:
        for m in re.finditer(r'href="(/stellenangebote--[^"?]+)"', html):
            href = DOMAIN + m.group(1)
            if href not in seen:
                seen.add(href)
                jobs.append({
                    "title": term,
                    "company": "",
                    "url": href,
                    "source": "stepstone",
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
            print(f"Warning: stepstone scrape failed for '{term}': {e}", file=sys.stderr)
    print(json.dumps(all_jobs))


if __name__ == "__main__":
    main()
