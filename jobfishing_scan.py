#!/usr/bin/env python3
"""
jobfishing_scan.py — jobfish.ing scraper for /jobhunter scan.

Same contract as stepstone_scan.py: outputs a JSON array, ALWAYS exits 0
(empty list on failure / no token).

Source: the hosted jobfish.ing job list (GET /api/v1/agent/jobs), the same
undocumented endpoint the official jobfishing-ai MCP server uses
(github.com/leoqingyu/jobfishing-ai). Jobs come pre-scored against the CV
uploaded to jobfish.ing; we keep only list_group 1 (Best) and 2 (Good) and
skip anything dismissed ("Not for me") in the jobfish.ing app.

Token: ~/.jobfishing/agent_token — the official MCP's own cache path, so
either tool can reuse the other's login. Get one with `--login` (device
flow, two non-blocking steps: `--login` prints the link, approve in the
browser, then `--finish` saves the token).
# ponytail: private endpoint, no schema guarantee — any error degrades to []
# and the scan continues. 401 = token revoked → rerun --login.

Usage:
  python3 jobfishing_scan.py --login    # one-time: print approval link
  python3 jobfishing_scan.py --finish   # after approving: save token
  python3 jobfishing_scan.py            # live
  python3 jobfishing_scan.py --dry-run  # mock, no HTTP
"""
import argparse
import json
import platform
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import quote

API = "https://app.jobfish.ing"
TOKEN_PATH = Path.home() / ".jobfishing" / "agent_token"
PENDING_PATH = Path.home() / ".jobfishing" / "pending_device_code"
MAX_GROUP = 2  # 1 Best, 2 Good, 3 Partial

MOCK_JOB = {
    "title": "Head of Strategy",
    "company": "Example AG",
    "url": "https://example.com/jobs/1",
    "source": "jobfishing",
    "location": "Zürich",
    "date_posted": "",
}


def http(method, path, token=None, body=None):
    req = urllib.request.Request(
        API + path, method=method,
        data=json.dumps(body).encode() if body is not None else None,
        # Cloudflare 403s urllib's default "Python-urllib/x.y" UA; any other UA passes.
        headers={"Content-Type": "application/json", "User-Agent": "career-ops-jobfishing/1.0",
                 **({"Authorization": f"Bearer {token}"} if token else {})})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.loads(r.read())


def _private_write(path, text):
    path.parent.mkdir(mode=0o700, exist_ok=True)
    path.write_text(text)
    path.chmod(0o600)


def login():
    """Step 1: start device auth, print the link, exit (non-blocking — `!` shells
    only show output once a command finishes)."""
    d = http("POST", "/api/v1/agent/device/start",
             body={"label": f"{platform.node()} (career-ops scan)"})
    _private_write(PENDING_PATH, d["device_code"])
    print(f"Open: {API}/app/agent-authorize?code={quote(str(d['user_code']), safe='')}")
    print(f"Code: {d['user_code']}  (expires in {d['expires_in']}s)")
    print("Approve it in the browser, then run: jobfishing_scan.py --finish")


def finish():
    """Step 2: poll once (a few retries) and save the token."""
    if not PENDING_PATH.exists():
        sys.exit("No pending authorization — run --login first")
    for _ in range(6):
        p = http("POST", "/api/v1/agent/device/poll",
                 body={"device_code": PENDING_PATH.read_text().strip()})
        if p.get("status") == "approved" and p.get("token"):
            _private_write(TOKEN_PATH, p["token"])
            PENDING_PATH.unlink()
            return print(f"Authorized. Token saved to {TOKEN_PATH}")
        if p.get("status") in {"denied", "expired", "delivered"}:
            PENDING_PATH.unlink()
            sys.exit(f"Authorization {p['status']} — rerun --login")
        time.sleep(5)
    sys.exit(f"Still {p.get('status')!r} — approve in the browser, then rerun --finish")


def to_record(j):
    loc = j.get("location")
    return {
        "title": j.get("title") or "",
        "company": j.get("company") or "",
        "url": j.get("job_url_direct") or j.get("url_direct") or j.get("url") or "",
        "source": "jobfishing",
        "location": loc if isinstance(loc, str) else "",
        "date_posted": str(j.get("date_posted") or j.get("created_at") or "")[:10],
    }


def scan():
    if not TOKEN_PATH.exists():
        print("  [jobfishing] no token — run: python3 jobfishing_scan.py --login", file=sys.stderr)
        return []
    jobs = http("GET", "/api/v1/agent/jobs", token=TOKEN_PATH.read_text().strip())["jobs"]
    keep = [j for j in jobs
            if (j.get("list_group") or 9) <= MAX_GROUP and not j.get("user_dismissed")
            and not j.get("is_agency")]  # staffing/recruiter postings hide the employer
    return [r for r in map(to_record, keep) if r["url"] and r["title"]]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--login", action="store_true")
    ap.add_argument("--finish", action="store_true")
    args = ap.parse_args()
    if args.login:
        return login()
    if args.finish:
        return finish()
    if args.dry_run:
        return print(json.dumps([MOCK_JOB]))
    try:
        out = scan()
    except urllib.error.HTTPError as e:
        print(f"  [jobfishing] HTTP {e.code}" + (" — token revoked, rerun --login" if e.code == 401 else ""),
              file=sys.stderr)
        out = []
    except Exception as e:  # noqa: BLE001 — best-effort source
        print(f"  [jobfishing] failed: {e}", file=sys.stderr)
        out = []
    print(json.dumps(out))


if __name__ == "__main__":
    main()
