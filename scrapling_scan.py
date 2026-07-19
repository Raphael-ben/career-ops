#!/usr/bin/env python3
"""
scrapling_scan.py — Scrapling-powered Level 1 career page scanner.

Fetches company career pages via HTTP, extracts job links using CSS selectors,
and outputs a JSON array to stdout. Targets tracked_companies entries that have
a careers_url but no api_provider (those are already handled by scan.mjs).

Uses Scrapling Selector for HTML parsing + standard requests for HTTP.

Usage:
  python3 scrapling_scan.py                # scan all eligible companies
  python3 scrapling_scan.py --dry-run      # print targets without fetching
"""
import os as _os, sys as _sys

# Re-exec with project venv so scrapling and requests are always available.
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3")
if not _os.path.exists(_VENV_PY):
    _VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import json
import sys
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from urllib.parse import urljoin, urlparse

import requests
import yaml
from scrapling import Selector

JOB_HREF_PATTERNS = [
    '/job', '/career', '/position', '/opening', '/vacancy', '/role',
    '/talent', '/hiring', '/work-with-us', '/join-us', '/offre', '/stelle',
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

TIMEOUT = 15


def _is_job_href(href: str) -> bool:
    h = href.lower()
    return any(p in h for p in JOB_HREF_PATTERNS)


def _same_domain(base_url: str, href: str) -> bool:
    base = urlparse(base_url).netloc
    target = urlparse(href).netloc
    return not target or target == base


def fetch_company(entry: dict) -> list[dict]:
    careers_url = entry.get('careers_url', '')
    company = entry.get('name', '')
    if not careers_url:
        return []

    try:
        resp = requests.get(careers_url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True)
        if resp.status_code >= 400:
            print(f'⚠️  {company}: HTTP {resp.status_code}', file=sys.stderr)
            return []

        page = Selector(resp.text)
        jobs = []
        seen: set[str] = set()

        for link in page.css('a[href]'):
            href = link.attrib.get('href', '').strip()
            if not href or href.startswith('#') or href.startswith('mailto:'):
                continue
            if not _is_job_href(href):
                continue

            full_url = urljoin(resp.url, href) if not href.startswith('http') else href

            # Stay on the same domain — skip cross-domain links
            if not _same_domain(resp.url, full_url):
                continue

            if full_url in seen:
                continue
            seen.add(full_url)

            title = (link.text or '').strip()
            if not title or len(title) < 3:
                continue

            jobs.append({
                'title': title,
                'url': full_url,
                'company': company,
                'location': '',
                'source': 'scrapling-l1',
            })

        return jobs

    except Exception as exc:
        print(f'⚠️  {company}: {exc}', file=sys.stderr)
        return []


def main() -> None:
    args = sys.argv[1:]
    dry_run = '--dry-run' in args

    portals_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'portals.yml')
    if not os.path.exists(portals_path):
        print('Error: portals.yml not found', file=sys.stderr)
        sys.exit(1)

    with open(portals_path) as f:
        config = yaml.safe_load(f)

    companies = [
        c for c in config.get('tracked_companies', [])
        if c.get('enabled', True)
        and c.get('careers_url')
        and not c.get('api_provider')
    ]

    if dry_run:
        print(f'Would scan {len(companies)} companies (no api_provider):', file=sys.stderr)
        for c in companies:
            print(f'  {c["name"]}: {c["careers_url"]}', file=sys.stderr)
        print('[]')
        return

    print(f'Scrapling Level 1: scanning {len(companies)} company career pages…', file=sys.stderr)

    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_company, c): c for c in companies}
        for fut in as_completed(futures):
            company_results = fut.result()
            results.extend(company_results)
            if company_results:
                name = futures[fut].get('name', '?')
                print(f'  ✓ {name}: {len(company_results)} job(s)', file=sys.stderr)

    print(f'\nScrapling Level 1 done: {len(results)} job link(s) found', file=sys.stderr)
    print(json.dumps(results))


if __name__ == '__main__':
    main()
