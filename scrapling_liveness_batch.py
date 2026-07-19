#!/usr/bin/env python3
"""
scrapling_liveness_batch.py — concurrent liveness sweep over many job URLs.

Reuses scrapling_liveness.check() but refines confidence so JS-rendered SPA
pages (Workday, Greenhouse, Ashby, LinkedIn) are NOT falsely marked expired:
their raw HTML is near-empty, which the single-URL script reads as "insufficient
content". Here that downgrades to `uncertain` instead of `expired`.

Only HIGH-confidence signals mark a posting dead:
  - HTTP 404/410
  - redirect to ?error=true
  - hard expired text pattern ("no longer available", etc.)
  - listing-page redirect (job gone, bounced to search)

Usage:
  python3 scrapling_liveness_batch.py <urls.json> <out.json>
  # urls.json: [{"marker":" ","url":"...","label":"..."}, ...]
"""
import os as _os, sys as _sys
_HERE = _os.path.dirname(_os.path.abspath(__file__))
_VENV_PY = _os.path.join(_HERE, ".venv", "bin", "python3")
if _os.path.exists(_VENV_PY) and _os.path.realpath(_sys.executable) != _os.path.realpath(_VENV_PY):
    _os.execv(_VENV_PY, [_VENV_PY] + _sys.argv)

import json
from concurrent.futures import ThreadPoolExecutor, as_completed

from scrapling_liveness import check

WORKERS = 12


def refine(url: str, verdict: dict) -> dict:
    status = verdict.get("status")
    reason = verdict.get("reason", "")
    # SPA pages render empty over plain HTTP — don't kill them on content size.
    if status == "expired" and "insufficient content" in reason:
        return {"status": "uncertain", "reason": "SPA/empty over HTTP — needs browser render"}
    if status == "uncertain" and "no apply signal" in reason:
        return {"status": "uncertain", "reason": "SPA likely — needs browser render"}
    return verdict


def run(url: str) -> dict:
    return refine(url, check(url))


def main() -> None:
    urls = json.load(open(_sys.argv[1]))
    pending = [u for u in urls if u.get("marker") == " " and u.get("url")]
    results = []
    with ThreadPoolExecutor(max_workers=WORKERS) as ex:
        futs = {ex.submit(run, u["url"]): u for u in pending}
        for fut in as_completed(futs):
            u = futs[fut]
            try:
                v = fut.result()
            except Exception as exc:  # noqa: BLE001
                v = {"status": "uncertain", "reason": f"runner error: {exc}"}
            results.append({**u, **v})

    out_path = _sys.argv[2] if len(_sys.argv) > 2 else "/tmp/liveness_results.json"
    json.dump(results, open(out_path, "w"), indent=0)

    from collections import Counter
    counts = Counter(r["status"] for r in results)
    print(f"Checked {len(results)} pending URLs")
    print(f"  active:    {counts.get('active', 0)}")
    print(f"  expired:   {counts.get('expired', 0)}")
    print(f"  uncertain: {counts.get('uncertain', 0)}")
    print("\n=== EXPIRED (high confidence) ===")
    for r in results:
        if r["status"] == "expired":
            print(f"  ✗ {r['label']}  →  {r['reason']}\n     {r['url']}")
    print("\n=== ACTIVE (static apply signal) ===")
    for r in results:
        if r["status"] == "active":
            print(f"  ✓ {r['label']}")


if __name__ == "__main__":
    main()
