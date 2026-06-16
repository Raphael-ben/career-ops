#!/usr/bin/env python3
"""
cv_fitcheck.py — enforced page-fill gate for the RB CV (Step 9 of write-cv.md).

WHY THIS EXISTS:
  Step 9 used to be a manual table the agent computed by hand and self-reported
  as PASS. The Cerrion CV (2026-06-16) shipped at ~72 estimated lines against a
  66-line "100% fill" ceiling because the self-check was skipped/under-counted.
  This script makes the check deterministic and enforceable — verify.md runs it
  and treats total > MAX as a BLOCKER. UNTRACKED on purpose (survives updates).

FORMULA (mirrors write-cv.md Step 9):
  total = section_headers(2*2) + section_gap(1)
        + 4 * experience_blocks + 4 * education_blocks
        + sum over bullets of: 1 line (<90 chars) | 2 (90-175) | 3 (>175)
  Targets: 60-64 ideal, 66 = ~100% fill (ceiling). >66 => overfilled.

ALSO ENFORCES bullet-length variety:
  - no bullet > 175 rendered chars (would wrap to 3 lines)
  - at least MIN_SHORT bullets < 90 chars (punchy, for visual rhythm)

USAGE:
  python3 cv_fitcheck.py path/to/***REMOVED***_CV.tex
  exit 0 = within budget; exit 1 = overfilled / variety violation (BLOCKER)
"""
import re
import sys

MAX_LINES = 66          # ceiling = ~100% fill (overflow above this)
MIN_LINES = 62          # floor: below this the page looks too empty -> EXPAND
MAX_THREELINE = 6       # cap on 3-line bullets (avoids uniform wall-of-text)
MIN_SHORT = 2           # at least this many short bullets (<90) for rhythm
# Goal: a FULL single page. Aim near MAX_LINES (62-66), not the floor.


def rendered_chars(s: str) -> int:
    s = re.sub(r"\\[a-zA-Z]+\{([^}]*)\}", r"\1", s)  # \cmd{x} -> x
    s = re.sub(r"\\[a-zA-Z]+", "", s)                 # bare \cmd
    s = re.sub(r"[\\${}~^]", "", s)
    return len(s.strip())


def main():
    if len(sys.argv) < 2:
        print("usage: cv_fitcheck.py <cv.tex>", file=sys.stderr)
        return 2
    lines_in = [l for l in open(sys.argv[1]).read().splitlines()
                if not l.lstrip().startswith("%")]  # ignore comment lines
    body = "\n".join(lines_in)

    exp_blocks = len(re.findall(r"\\begin\{experience\}", body))
    edu_blocks = len(re.findall(r"\\begin\{education\}", body))
    bullets = re.findall(r"\\item\s+(.*)", body)

    bullet_lines = 0
    short = 0
    three_line = 0
    print(f"{'chars':>5}  {'lines':>5}  bullet")
    for b in bullets:
        c = rendered_chars(b)
        ln = 1 if c < 90 else (2 if c <= 175 else 3)
        bullet_lines += ln
        if c < 90:
            short += 1
        if ln == 3:
            three_line += 1
        print(f"{c:>5}  {ln:>5}  {b[:58]}")

    headers, gap = 4, 1
    total = headers + gap + 4 * exp_blocks + 4 * edu_blocks + bullet_lines
    print(f"\nexp_blocks={exp_blocks} edu_blocks={edu_blocks} "
          f"bullet_lines={bullet_lines} short={short} three_line={three_line}")
    print(f"TOTAL = {total}  (target {MIN_LINES}-{MAX_LINES} — aim near "
          f"{MAX_LINES} for a FULL page)")

    fail = False
    if total > MAX_LINES:
        print(f"BLOCKER: overfilled — {total} > {MAX_LINES}. Trim "
              f"{total - MAX_LINES + 1} line(s) (shorten 3-line bullets).")
        fail = True
    elif total < MIN_LINES:
        print(f"BLOCKER: underfilled — {total} < {MIN_LINES}. Too much blank "
              f"space; EXPAND {MIN_LINES - total}+ line(s): lengthen bullets "
              f"with real profile_bank detail, restore a trimmed bullet, or add "
              f"Prépa. Do NOT ship a half-empty page.")
        fail = True
    if three_line > MAX_THREELINE:
        print(f"BLOCKER: {three_line} three-line bullets (> {MAX_THREELINE}) — "
              f"wall-of-text risk. Shorten some to 1-2 lines for rhythm.")
        fail = True
    if short < MIN_SHORT:
        print(f"BLOCKER: only {short} bullet(s) < 90 chars; need >= {MIN_SHORT} "
              f"for rhythm (mix short punchy bullets with longer ones).")
        fail = True

    if not fail:
        print(f"PASS: full page ({MIN_LINES}-{MAX_LINES}), good rhythm.")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
