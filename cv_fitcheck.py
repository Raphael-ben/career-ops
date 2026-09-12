#!/usr/bin/env python3
"""
cv_fitcheck.py — REAL page-fill gate for the CV.

Measures the ACTUAL rendered fill of the compiled PDF, not a character estimate.
The previous char-heuristic version LIED: it reported 65/66 "full" while the
real main column was only 88.9% filled (~1 inch / 93pt of blank at the bottom).
This version opens the compiled PDF with PyMuPDF and measures the lowest text
baseline in the MAIN column versus the page height.

PROCESS THIS ENFORCES (mirrored in write-cv.md Step 9 / verify.md Step 0):
  1. write-cv emits the CV from the FULL humanized bullet set — the canonical,
     rule-compliant, em-dash-free content. Never rewrite/rephrase ad hoc.
  2. Compile to PDF (pdflatex).
  3. Run this script on the PDF.
  4. ADJUST BY SELECTION, then recompile and re-measure — loop until PASS:
       - overflow (>1 page) -> DROP the lowest-priority WHOLE bullet.
       - underfilled (<MIN_FILL) -> RESTORE a dropped humanized bullet, or swap
         in the fuller profile_bank variant of a bullet.
     NEVER invent prose, pad with em dashes, or stretch wording to hit the number.

Optional --ats flag adds an ATS text-extraction gate on top of the fill gate
(see USAGE below).

USAGE:
  python3 cv_fitcheck.py path/to/<cv.pdf>
  python3 cv_fitcheck.py path/to/<cv.pdf> --ats [--expect "STRING"]...
  exit 0 = PASS all requested gates; exit 1 = BLOCKER on any gate
"""
import os as _os
import sys as _sys

# Re-exec into the project venv that has PyMuPDF (root .venv preferred).
_HERE = _os.path.dirname(_os.path.abspath(__file__))
for _v in (_os.path.join(_os.path.dirname(_HERE), ".venv", "bin", "python3"),
           _os.path.join(_HERE, ".venv", "bin", "python3")):
    if _os.path.exists(_v) and _os.path.realpath(_sys.executable) != _os.path.realpath(_v):
        _os.execv(_v, [_v] + _sys.argv)
        break

import argparse
import re
import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    print("BLOCKER: PyMuPDF not installed in this venv (pip install pymupdf).",
          file=sys.stderr)
    sys.exit(2)

SIDEBAR_X = 180   # main column starts right of the ~62mm sidebar
MIN_FILL = 0.94   # below this the bottom looks empty -> EXPAND from humanized set
MIN_BLANK = 8     # pt of bottom breathing room REQUIRED — text closer than this
                  # to the page edge violates the margin (Microlino shipped at
                  # -1pt because this bound was missing; reference-good is ~10pt)

# ATS gate thresholds
ATS_MIN_CHARS = 500     # below this, page text looks rasterized/unparseable
ATS_MAX_TRANSITIONS = 3  # sidebar<->main block-order flips tolerated

EMAIL_RE = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
PHONE_RE = re.compile(r"\+\d[\d\s]{4,}\d")


def normalize_ws(text):
    """Join hyphen/newline line-wraps and collapse remaining whitespace to single
    spaces, so extracted text can be substring-matched regardless of how the PDF
    wrapped it across lines."""
    text = re.sub(r"-\s*\n\s*", "", text)   # de-hyphenate wrapped words
    text = re.sub(r"\s+", " ", text)        # collapse remaining whitespace/newlines
    return text.strip()


def check_fill(page, pages):
    """Original real-rendered-fill gate. Returns (fail: bool)."""
    H = page.rect.height
    main = [w for w in page.get_text("words") if w[0] > SIDEBAR_X]
    low = max((w[3] for w in main), default=0)
    fill = (low / H) if H else 0.0
    blank = H - low
    print(f"pages={pages}  page_height={H:.0f}pt  "
          f"main-column fill={100 * fill:.1f}%  bottom blank={blank:.0f}pt")

    fail = False
    if pages > 1:
        print(f"BLOCKER: overflow — {pages} pages. Drop the lowest-priority WHOLE "
              f"bullet, then recompile. Do not shrink geometry.")
        fail = True
    elif blank < MIN_BLANK:
        print(f"BLOCKER: overfull — only {blank:.0f}pt bottom blank (< {MIN_BLANK}pt). "
              f"Text violates the bottom margin. SWAP one bullet for its shorter "
              f"humanized variant, or drop the lowest-priority WHOLE bullet, then "
              f"recompile. Never shrink fonts/geometry, never rewrite prose ad hoc.")
        fail = True
    elif fill < MIN_FILL:
        print(f"BLOCKER: underfilled — {100 * fill:.1f}% < {100 * MIN_FILL:.0f}% "
              f"({blank:.0f}pt blank, ~{blank / 15:.0f} lines). RESTORE a humanized "
              f"bullet you dropped, or swap in the fuller profile_bank variant. "
              f"Never invent prose or pad with em dashes.")
        fail = True

    if not fail:
        print(f"PASS: full single page ({100 * fill:.1f}% main-column fill).")
    return fail


def check_column_transitions(page):
    """Count how often consecutive extracted text blocks flip between sidebar
    (x0 < SIDEBAR_X) and main column, in the natural order PyMuPDF extracts them.
    A high count means extraction alternates columns, which scrambles ATS parsing."""
    blocks = [b for b in page.get_text("blocks") if b[6] == 0 and b[4].strip()]
    cols = ["sidebar" if b[0] < SIDEBAR_X else "main" for b in blocks]
    return sum(1 for i in range(1, len(cols)) if cols[i] != cols[i - 1])


def check_ats(page, expects):
    """ATS text-extraction gate: plain-text yield, identity extractability, and
    column-order integrity. Returns (fail: bool)."""
    fail = False
    raw_text = page.get_text()
    norm_text = normalize_ws(raw_text)
    char_count = len(raw_text.strip())
    print(f"ats: extracted {char_count} chars of plain text")
    if char_count < ATS_MIN_CHARS:
        print(f"BLOCKER (ats): extracted text too short ({char_count} < {ATS_MIN_CHARS} "
              f"chars) — page may be a rasterized image, unreadable by ATS parsers.")
        fail = True

    if expects:
        for expect in expects:
            # Case-folded: CV templates routinely set the name in caps, so a
            # case-sensitive match reports a false blocker on a name that is
            # perfectly extractable.
            expect_norm = normalize_ws(expect).casefold()
            if expect_norm in norm_text.casefold():
                print(f"ats: identity string found: {expect!r}")
            else:
                print(f"BLOCKER (ats): identity string NOT extractable: {expect!r}")
                fail = True
    else:
        has_email = bool(EMAIL_RE.search(norm_text))
        has_phone = bool(PHONE_RE.search(norm_text))
        if not has_email:
            print("BLOCKER (ats): no email-looking token extractable from page text.")
            fail = True
        if not has_phone:
            print("BLOCKER (ats): no phone-looking token extractable from page text.")
            fail = True
        if has_email and has_phone:
            print("ats: identity heuristic passed (email + phone extractable).")

    transitions = check_column_transitions(page)
    print(f"ats: sidebar<->main block transitions={transitions}")
    if transitions > ATS_MAX_TRANSITIONS:
        print(f"BLOCKER (ats): column integrity — {transitions} sidebar<->main "
              f"transitions (> {ATS_MAX_TRANSITIONS}). Extraction order alternates "
              f"columns; ATS parsers will scramble sidebar/main text.")
        fail = True

    if not fail:
        print("PASS (ats): text extractable, identity present, column order stable.")
    return fail


def main():
    parser = argparse.ArgumentParser(
        description="Real rendered page-fill gate for a compiled CV PDF, "
                    "with an optional ATS text-extraction gate.")
    parser.add_argument("pdf", help="path to <cv.pdf>")
    parser.add_argument("--ats", action="store_true",
                         help="also run the ATS text-extraction gate")
    parser.add_argument("--expect", action="append", default=[],
                         help="identity string that must be extractable "
                              "(repeatable); only used with --ats")
    args = parser.parse_args()

    doc = fitz.open(args.pdf)
    pages = doc.page_count
    page = doc[0]

    fill_fail = check_fill(page, pages)

    ats_fail = False
    if args.ats:
        ats_fail = check_ats(page, args.expect)

    return 1 if (fill_fail or ats_fail) else 0


if __name__ == "__main__":
    sys.exit(main())
