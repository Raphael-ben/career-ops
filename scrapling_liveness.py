#!/usr/bin/env python3
"""
scrapling_liveness.py — Fast HTTP liveness pre-check for job posting URLs.

Mirrors the patterns in liveness-core.mjs using requests for HTTP status +
Scrapling Selector for HTML text extraction. Returns a JSON verdict before
Playwright ever launches, saving browser startup time for clear-cut cases.

Exit codes: 0 always (result is in stdout JSON).

Usage:
  python3 scrapling_liveness.py <url>
  # → {"status": "active"|"expired"|"uncertain", "reason": "..."}
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
import re
import sys

import requests
from scrapling import Selector

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'en-US,en;q=0.9',
}

TIMEOUT = 10
MIN_CONTENT_CHARS = 300

HARD_EXPIRED_PATTERNS = [
    r'job (is )?no longer available',
    r'job.*no longer open',
    r'position has been filled',
    r'this job has expired',
    r'job posting has expired',
    r'no longer accepting applications',
    r'this (position|role|job) (is )?no longer',
    r'this job (listing )?is closed',
    r'job (listing )?not found',
    r'the page you are looking for doesn.t exist',
    r'applications?\s+(?:(?:have|are|is)\s+)?closed',
    r'closed on \d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)',
    r'diese stelle (ist )?(nicht mehr|bereits) besetzt',
    r'offre (expirée|n.est plus disponible)',
]

LISTING_PAGE_PATTERNS = [
    r'\d+\s+jobs?\s+found',
    r'search for jobs page is loaded',
]

APPLY_PATTERNS = [
    r'\bapply\b',
    r'\bsolicitar\b',
    r'\bbewerben\b',
    r'\bpostuler\b',
    r'submit application',
    r'easy apply',
    r'start application',
    r'ich bewerbe mich',
]


def _match_any(patterns: list[str], text: str) -> str | None:
    for p in patterns:
        if re.search(p, text, re.I):
            return p
    return None


def check(url: str) -> dict:
    try:
        resp = requests.get(
            url, headers=HEADERS, timeout=TIMEOUT, allow_redirects=True
        )
        final_url = resp.url
        status = resp.status_code

        if status in (404, 410):
            return {'status': 'expired', 'reason': f'HTTP {status}'}

        if '?error=true' in final_url:
            return {'status': 'expired', 'reason': f'redirect to {final_url}'}

        # Use Scrapling to extract clean text (strips scripts, styles, nav noise)
        page = Selector(resp.text)
        body = page.css('body').first
        text = body.get_all_text() if body else resp.text

        matched = _match_any(HARD_EXPIRED_PATTERNS, text)
        if matched:
            return {'status': 'expired', 'reason': f'pattern: {matched}'}

        listing = _match_any(LISTING_PAGE_PATTERNS, text)
        if listing:
            return {'status': 'expired', 'reason': f'listing page: {listing}'}

        if len(text.strip()) < MIN_CONTENT_CHARS:
            return {'status': 'expired', 'reason': 'insufficient content — likely nav/footer only'}

        apply_hit = _match_any(APPLY_PATTERNS, text)
        if apply_hit:
            return {'status': 'active', 'reason': 'apply signal found'}

        return {'status': 'uncertain', 'reason': 'content present but no apply signal — SPA likely'}

    except requests.exceptions.Timeout:
        return {'status': 'uncertain', 'reason': 'request timeout'}
    except Exception as exc:
        return {'status': 'uncertain', 'reason': str(exc)}


def main() -> None:
    if len(sys.argv) < 2:
        print('Usage: python3 scrapling_liveness.py <url>', file=sys.stderr)
        sys.exit(1)
    print(json.dumps(check(sys.argv[1])))


if __name__ == '__main__':
    main()
