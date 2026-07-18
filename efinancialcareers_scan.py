#!/usr/bin/env python3
"""
efinancialcareers_scan.py — eFinancialCareers scraper for /jobhunter scan.

Same contract as jobs_ch.py/stepstone_scan.py: reads jobspy.search_terms from
config/profile.yml, outputs a JSON array, ALWAYS exits 0 (empty list on
failure/block).

INVESTIGATION NOTE (2026-07-18): efinancialcareers.ch is an Angular-Universal
(SSR) DHI Group site. The obvious guess — a JSON API at /v1/efc/jobs/search —
is live but sits behind an AWS WAF "Human Verification" challenge (405) the
moment a keyword/pageSize query string is attached; scan_http's tier-2
escalation (curl_cffi Chrome impersonation) would be the way past that, but
curl_cffi isn't installed in this venv, so that path is currently unusable —
documented ceiling, not faked.
The workaround: /jobs/{slug} category pages (e.g. /jobs/business-development)
render server-side and embed the full first page of results as inline JSON in
<script id="dataTransfer">function transferredData(){ return {...} }</script>
— window.ssdl.searchObj.jobs, ~15 rows, no separate XHR needed. The URL slug
IS the search keyword (spaces -> hyphens, trailing "switzerland"/"zürich"/
"zurich" stripped since the search itself is global, not CH-scoped by the
domain). Results are worldwide (Zürich sits next to Dubai/Hong Kong postings)
— left unfiltered here, scan_aggregate.py's location_filter allow/block list
already drops the non-Swiss rows downstream (verified: "Zürich, Schweiz"
matches the allow list, "Genf, Schweiz"/"Hongkong" get blocked/dropped there).
No posting-date field exists in the job objects, so date_posted is always "".
Ceiling: only page 1 (~15 results) per term — no discovered pagination param;
adding one is a small follow-up if term coverage ever looks thin.
# ponytail: single-page inline-JSON scrape, no per-job detail fetch — if EFC
# changes the dataTransfer payload shape, this degrades to [] via the
# exception handler and the scan continues.

Usage:
  python3 efinancialcareers_scan.py            # live
  python3 efinancialcareers_scan.py --dry-run  # mock, no HTTP
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

sys.path.insert(0, _HERE)
import scan_http

DOMAIN = "https://www.efinancialcareers.ch"

MOCK_JOB = {
    "title": "Business Development Manager",
    "company": "",
    "url": "https://www.efinancialcareers.ch/jobs-Switzerland-Zurich-Example.id12345",
    "source": "efc",
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
    Strips the Swiss location suffix our search_terms always carry — EFC's
    /jobs/{slug} pages are keyword-only (global scope), so the suffix would
    otherwise become part of the search keyword and return nothing."""
    t = term.strip().lower()
    for suffix in ("switzerland", "zürich", "zurich"):
        if t.endswith(suffix):
            t = t[: -len(suffix)].strip()
    t = re.sub(r"[^a-z0-9äöüß&\s-]", " ", t)
    return re.sub(r"\s+", "-", t).strip("-")


def scrape_term(term: str) -> list:
    slug = slugify(term)
    if not slug:
        return []
    url = f"{DOMAIN}/jobs/{slug}"
    resp = scan_http.get(url)
    if resp is None or resp.status_code != 200:
        code = resp.status_code if resp is not None else "no-response"
        print(f"Warning: efc {code} for '{term}'", file=sys.stderr)
        return []
    html = resp.text

    jobs, seen = [], set()
    m = re.search(
        r'<script id="dataTransfer"[^>]*>function transferredData\(\) \{ return (.*)$',
        html, re.S)
    if m:
        try:
            data, _ = json.JSONDecoder().raw_decode(m.group(1))
            raw_jobs = data["window"]["ssdl"]["searchObj"]["jobs"]
            for j in raw_jobs:
                href = (j.get("destination_url") or "").strip()
                title = (j.get("job_title") or "").strip()
                if not href or not title:
                    continue
                if href.startswith("/"):
                    href = DOMAIN + href
                if href in seen:
                    continue
                seen.add(href)
                jobs.append({
                    "title": title[:150],
                    "company": (j.get("company_name") or "").strip(),
                    "url": href,
                    "source": "efc",
                    "location": (j.get("job_location") or "").strip(),
                    "date_posted": "",  # not present in EFC's job payload
                })
        except Exception as e:
            print(f"Warning: failed to parse efc dataTransfer payload: {e}", file=sys.stderr)

    # Regex fallback if the inline-JSON parser found nothing (payload shape
    # changed) but the page still has destination_url links embedded.
    if not jobs:
        for match in re.finditer(r'"destination_url":"(/jobs-[^"]+)"', html):
            href = DOMAIN + match.group(1)
            if href not in seen:
                seen.add(href)
                jobs.append({
                    "title": term,
                    "company": "",
                    "url": href,
                    "source": "efc",
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
            print(f"Warning: efc scrape failed for '{term}': {e}", file=sys.stderr)
    print(json.dumps(all_jobs))


if __name__ == "__main__":
    main()
