#!/usr/bin/env python3
"""Route triaged pipeline.md pending entries per data/triage-verdicts.json.

pass -> leave '- [ ]' line unchanged
borderline -> move to '## Borderline' section at EOF
skip -> remove line, append row to data/scan-history.tsv

Only operates on '- [ ]' lines at/after the first '## Scan 2026-07-09' line.
Idempotent: re-running after a completed route is a no-op (no more '- [ ]'
lines remain in the scanned region to move/remove).
"""
import json
import re
import sys
from datetime import date

PIPELINE = "data/pipeline.md"
VERDICTS = "data/triage-verdicts.json"
SCAN_HISTORY = "data/scan-history.tsv"
TODAY = "2026-07-09"
MARKER = "## Scan 2026-07-09"

with open(VERDICTS, encoding="utf-8") as f:
    verdicts = json.load(f)

with open(PIPELINE, encoding="utf-8") as f:
    lines = f.readlines()

# find first marker line (index in 0-based list)
start_idx = None
for i, line in enumerate(lines):
    if line.startswith(MARKER):
        start_idx = i
        break
if start_idx is None:
    print("Marker not found; nothing to do.")
    sys.exit(0)

before = lines[:start_idx]
region = lines[start_idx:]

LINE_RE = re.compile(r"^- \[ \] (.*)$")

counts = {"pass": 0, "borderline": 0, "skip": 0, "unmatched": 0}
kept_region = []
borderline_entries = []  # (company, title, url, reason)
skip_rows = []  # tsv rows

for line in region:
    stripped = line.rstrip("\n")
    m = LINE_RE.match(stripped)
    if not m:
        kept_region.append(line)
        continue

    body = m.group(1)
    parts = body.split(" | ")
    url = parts[0].strip()
    company = parts[1].strip() if len(parts) > 1 else "?"
    rest = " | ".join(parts[2:]) if len(parts) > 2 else ""
    title = re.sub(r"\s*—\s*via .*$", "", rest).strip()

    key = url if url else title
    entry = verdicts.get(key)
    if entry is None:
        # No verdict found for this line -- leave untouched (safe default).
        counts["unmatched"] += 1
        kept_region.append(line)
        continue

    verdict = entry["verdict"]
    reason = entry.get("reason", "")
    v_title = entry.get("title", title)
    v_company = entry.get("company", company)

    if verdict == "pass":
        counts["pass"] += 1
        kept_region.append(line)
    elif verdict == "borderline":
        counts["borderline"] += 1
        borderline_entries.append((v_company, v_title, url, reason))
        # line dropped from kept_region
    elif verdict == "skip":
        counts["skip"] += 1
        skip_rows.append(f"{url}\t{TODAY}\ttriage\t{v_title}\t{v_company}\tskipped_triage\n")
        # line dropped from kept_region
    else:
        counts["unmatched"] += 1
        kept_region.append(line)

# Strip any pre-existing '## Borderline' section from kept_region (idempotency)
# so we can rebuild it cleanly at EOF without duplicating old entries.
def split_out_borderline_section(region_lines):
    for idx, l in enumerate(region_lines):
        if l.rstrip("\n") == "## Borderline":
            return region_lines[:idx], region_lines[idx:]
    return region_lines, []

kept_region, old_borderline_section = split_out_borderline_section(kept_region)

# Parse existing borderline entries (if any) to preserve them across idempotent re-runs.
existing_borderline_lines = []
if old_borderline_section:
    # keep raw text minus header, re-parse into (company, title, url, reason) blocks
    text = "".join(old_borderline_section[1:])  # drop "## Borderline" header line
    blocks = [b for b in text.split("\n\n") if b.strip()]
    for b in blocks:
        bl = b.strip("\n").split("\n")
        if len(bl) >= 3:
            hdr = bl[0]
            url_line = bl[1].strip()
            reason_line = bl[2].strip()
            hm = re.match(r"^- \[\?\] (.*?) — (.*)$", hdr)
            if hm:
                existing_borderline_lines.append(
                    (hm.group(1), hm.group(2), url_line, reason_line.replace("Triage: ", "", 1))
                )

all_borderline = existing_borderline_lines + borderline_entries

# Rebuild pipeline.md
out = []
out.extend(before)
out.extend(kept_region)
if all_borderline:
    out.append("## Borderline\n")
    for company, title, url, reason in all_borderline:
        out.append(f"- [?] {company} — {title}\n")
        out.append(f"     {url}\n")
        out.append(f"     Triage: {reason}\n")
        out.append("\n")

with open(PIPELINE, "w", encoding="utf-8") as f:
    f.writelines(out)

if skip_rows:
    with open(SCAN_HISTORY, "a", encoding="utf-8") as f:
        f.writelines(skip_rows)

print(f"pass={counts['pass']} borderline={counts['borderline']} skip={counts['skip']} unmatched={counts['unmatched']}")
