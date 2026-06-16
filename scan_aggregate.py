#!/usr/bin/env python3
"""
scan_aggregate.py — Level 4a/4b aggregator for /jobhunter scan (rb).

WHY THIS EXISTS (read before deleting):
  scan.mjs is system-layer and `update-system.mjs` overwrites it on every
  career-ops update — it has TWICE wiped the JobSpy/jobs.ch wiring (v1.8.1,
  v1.10.0). This script is UNTRACKED on purpose so updates can never touch it.
  It is the durable home for the broad-net scrape→filter→dedup→append pipeline
  that used to live (and kept dying) inside scan.mjs.

WHAT IT DOES:
  1. Runs jobspy_scan.py (LinkedIn+Indeed) and jobs_ch.py (jobs.ch).
  2. Applies portals.yml title_filter (positive/negative) and location_filter
     (allow/block, block wins) — same semantics as the old scan.mjs.
  3. Dedups by URL against data/scan-history.tsv.
  4. Appends survivors to data/scan-history.tsv and data/pipeline.md.
  5. Prints a funnel summary + the list of new jobs.

USAGE:
  python3 scan_aggregate.py                 # full run, writes results
  python3 scan_aggregate.py --dry-run       # report only, writes nothing
  python3 scan_aggregate.py --date 2026-06-14   # override header date
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import argparse
import datetime
import json
import subprocess
import sys
from pathlib import Path

import yaml

HERE = Path(__file__).resolve().parent
PORTALS = HERE / "portals.yml"
HISTORY = HERE / "data" / "scan-history.tsv"
PIPELINE = HERE / "data" / "pipeline.md"
SCRAPERS = ["jobspy_scan.py", "jobs_ch.py"]


def run_scraper(name):
    """Run a scraper, return its JSON list. Never raises — returns [] on failure."""
    try:
        proc = subprocess.run(
            [sys.executable, str(HERE / name)],
            capture_output=True, text=True, timeout=240,
            cwd=str(HERE),  # scrapers read cwd-relative config/profile.yml
        )
        if not proc.stdout.strip():
            print(f"  [{name}] no output ({proc.stderr.strip()[-160:]})", file=sys.stderr)
            return []
        return json.loads(proc.stdout)
    except Exception as e:  # noqa: BLE001 — best-effort, partial results are fine
        print(f"  [{name}] failed: {e}", file=sys.stderr)
        return []


def load_cfg():
    cfg = yaml.safe_load(PORTALS.read_text()) or {}
    tf = cfg.get("title_filter", {}) or {}
    lf = cfg.get("location_filter", {}) or {}
    return (
        [p.lower() for p in (tf.get("positive") or [])],
        [n.lower() for n in (tf.get("negative") or [])],
        [a.lower() for a in (lf.get("allow") or [])],
        [b.lower() for b in (lf.get("block") or [])],
    )


def load_history():
    seen = set()
    if HISTORY.exists():
        for line in HISTORY.read_text(errors="replace").splitlines():
            if line.strip():
                seen.add(line.split("\t")[0].strip())
    return seen


def title_ok(title, pos, neg):
    t = (title or "").lower()
    if neg and any(n in t for n in neg):
        return False
    if pos and not any(p in t for p in pos):
        return False
    return True


def location_ok(loc, allow, block):
    """Empty location → keep (sparse data). block wins. allow gate if non-empty."""
    l = (loc or "").strip().lower()
    if not l:
        return True
    if block and any(b in l for b in block):
        return False
    if allow and not any(a in l for a in allow):
        return False
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--date", default=datetime.date.today().isoformat())
    args = ap.parse_args()

    pos, neg, allow, block = load_cfg()
    seen = load_history()

    jobs = []
    for s in SCRAPERS:
        got = run_scraper(s)
        print(f"  {s}: {len(got)} jobs", file=sys.stderr)
        jobs.extend(got)

    raw = len(jobs)
    tpass = [j for j in jobs if title_ok(j.get("title"), pos, neg)]
    lpass = [j for j in tpass if location_ok(j.get("location"), allow, block)]

    # dedup against history AND within this run
    new, run_seen = [], set()
    for j in lpass:
        url = (j.get("url") or "").strip()
        if not url or url in seen or url in run_seen:
            continue
        run_seen.add(url)
        new.append(j)

    print(f"\nFunnel: raw={raw}  title_ok={len(tpass)}  location_ok={len(lpass)}  NEW={len(new)}")

    if new and not args.dry_run:
        with HISTORY.open("a") as fh:
            for j in new:
                fh.write("\t".join([
                    j.get("url", "").strip(),
                    (j.get("title") or "").replace("\t", " ").strip(),
                    (j.get("company") or "").replace("\t", " ").strip(),
                    j.get("source", "").strip(),
                    args.date,
                    "added",
                ]) + "\n")
        with PIPELINE.open("a") as fh:
            fh.write(f"\n## Scan {args.date} (script layer — JobSpy + jobs.ch)\n\n")
            for j in new:
                company = (j.get("company") or "?").strip() or "?"
                title = (j.get("title") or "").strip()
                loc = (j.get("location") or "").strip()
                src = j.get("source", "")
                suffix = f" ({loc})" if loc else ""
                fh.write(f"- [ ] {j.get('url','').strip()} | {company} | {title}{suffix} — via {src}, triage\n")
        print(f"Wrote {len(new)} new → data/scan-history.tsv + data/pipeline.md")
    elif args.dry_run:
        print("(dry-run: nothing written)")

    for j in new[:40]:
        print(f"  • {(j.get('title') or '')[:68]:68} | {j.get('source')}")
    if len(new) > 40:
        print(f"  … and {len(new) - 40} more")


if __name__ == "__main__":
    main()
