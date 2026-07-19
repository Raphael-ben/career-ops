#!/usr/bin/env python3
"""One-shot: cull directory/profile/listing noise from the 2026-07-09 scan
sections of data/pipeline.md. Idempotent. Reuses scan_aggregate.is_directory."""
import re
from pathlib import Path
from scan_aggregate import is_directory

PIPE = Path("data/pipeline.md")

# Liveness-verified dead / out-of-scope (pass is_directory but must be marked).
HARD = {
    "linkedin.com/jobs/view/4216585313": " | DEAD: Sanoptis M&A closed (verified 2026-07-09)",
    "linkedin.com/jobs/view/4415077840": " | DEAD: UBS strategy closed (verified 2026-07-09)",
    "linkedin.com/jobs/view/4053368073": " | DEAD: Deel corp-dev expired 1yr (verified 2026-07-09)",
    "builtin.com/job/business-development-manager-quantum-technology/8537747":
        " | SKIP: Zurich Instruments BD is Boston USA, out of scope",
}

text = PIPE.read_text()
start = text.index("## Scan 2026-07-09")
head, body = text[:start], text[start:]

url_re = re.compile(r"(https?://\S+)")
total = marked = remaining = 0
survivors = []
out = []

for line in body.split("\n"):
    if not line.startswith("- [ ]") and not line.startswith("- [!]"):
        out.append(line)
        continue
    m = url_re.search(line)
    url = m.group(1) if m else ""
    if line.startswith("- [ ]"):
        total += 1
    else:  # already [!] — count toward total but never double-mark
        total += 1
        out.append(line)
        continue

    # match full key OR its trailing id/segment (real URLs embed a slug before the id)
    hard = next((r for u, r in HARD.items()
                 if u in url or u.rsplit("/", 1)[-1] in url), None)
    if hard is not None:
        out.append("- [!]" + line[5:] + hard)
        marked += 1
    elif is_directory(url):
        out.append("- [!]" + line[5:] + " | culled: directory/profile/listing (auto)")
        marked += 1
    else:
        remaining += 1
        # title is between first "| ... |" pair, before the "— via" tail
        parts = line.split(" — via")[0]
        title = parts.split("|")[-1].strip() if "|" in parts else parts
        survivors.append((title, url))
        out.append(line)

PIPE.write_text(head + "\n".join(out))

print(f"total 2026-07-09 entries: {total}")
print(f"newly/marked [!]:         {marked}")
print(f"remaining [ ]:            {remaining}")
print("\n--- SURVIVORS (title | url) ---")
for t, u in survivors:
    print(f"{t} | {u}")
