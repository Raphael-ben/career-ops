#!/usr/bin/env python3
"""
cv_fitcheck.py — REAL page-fill gate for the RB CV.

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
       - overflow (>1 page) -> DROP the lowest-priority WHOLE bullet
         (Prépa -> Serpentine bullet 3 -> weakest PwC bullet).
       - underfilled (<MIN_FILL) -> RESTORE a dropped humanized bullet, or swap
         in the fuller profile_bank variant of a bullet.
     NEVER invent prose, pad with em dashes, or stretch wording to hit the number.

USAGE:
  python3 cv_fitcheck.py path/to/***REMOVED***_CV.pdf
  exit 0 = full single page; exit 1 = overflow or underfilled (BLOCKER)
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

import sys

try:
    import fitz  # PyMuPDF
except ImportError:
    print("BLOCKER: PyMuPDF not installed in this venv (pip install pymupdf).",
          file=sys.stderr)
    sys.exit(2)

SIDEBAR_X = 180   # main column starts right of the ~62mm sidebar
MIN_FILL = 0.94   # below this the bottom looks empty -> EXPAND from humanized set


def main():
    if len(sys.argv) < 2:
        print("usage: cv_fitcheck.py <cv.pdf>", file=sys.stderr)
        return 2
    doc = fitz.open(sys.argv[1])
    pages = doc.page_count
    page = doc[0]
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
              f"bullet (Prépa -> Serpentine bullet 3 -> weakest PwC bullet), then "
              f"recompile. Do not shrink geometry.")
        fail = True
    elif fill < MIN_FILL:
        print(f"BLOCKER: underfilled — {100 * fill:.1f}% < {100 * MIN_FILL:.0f}% "
              f"({blank:.0f}pt blank, ~{blank / 15:.0f} lines). RESTORE a humanized "
              f"bullet you dropped, or swap in the fuller profile_bank variant. "
              f"Never invent prose or pad with em dashes.")
        fail = True

    if not fail:
        print(f"PASS: full single page ({100 * fill:.1f}% main-column fill).")
    return 1 if fail else 0


if __name__ == "__main__":
    sys.exit(main())
