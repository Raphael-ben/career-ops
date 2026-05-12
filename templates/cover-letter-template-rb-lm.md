# cover-letter-template-rb-lm.tex — AI Agent Fill Guide

This guide is for the `fill_cover_letter_template()` function in `src/jobops/latex_filler.py`.
Font identity matches `cv-template-rb-lm.tex`: Latin Modern Sans, 11pt body.

---

## TL;DR — what to fill, what to never touch

**Fill these (via regex on `\newcommand` blocks):**
- `\CLDate` — formatted date
- `\CLCompanyName`, `\CLCompanyStreet`, `\CLCompanyCity` — recipient
- `\CLSubject`, `\CLSalutation`, `\CLClosing` — letter metadata

**Fill these (via region replacement):**
- `\CLParagraph{}` blocks between `%% AI-FILL-START` and `%% AI-FILL-END`

**Never touch:**
- `\CLName`, `\CLAddress`, `\CLPhone`, `\CLEmail` — Raphael's info, fixed in template
- `\CLGreeting` — defaults to "Yours sincerely,", not model-driven
- Spacing controls block
- Custom command definitions in the preamble
- Page geometry

---

## 1. Variable map — what goes where on the page

```
────────────────────────────────────────────────────────────
                                         [APPLICANT]        top header (right-aligned, gray)
                                         \CLName -- \CLAddress
                                         \CLEmail - \CLPhone
                                                 [DATE]     right-aligned
\CLCompanyName                                              left-aligned 3-line block
\CLCompanyStreet
\CLCompanyCity
Subject: \CLSubject                                        bold
\CLSalutation
[body paragraphs — AI-FILL-START … AI-FILL-END]
\CLClosing
\CLGreeting
\CLName                                                    plain weight
\CLEmail - \CLPhone                                        bottom left, gray
────────────────────────────────────────────────────────────
```

`\CLName`, `\CLAddress`, `\CLPhone`, `\CLEmail` appear in TWO places (top header + bottom
signature). Set once in the preamble — template renders them in both locations.

---

## 2. Model → template mapping

| `CoverLetter` model field | Template command | Notes |
|---|---|---|
| `header.date` (ISO YYYY-MM-DD) | `\CLDate` | Convert to "April 26\textsuperscript{th} 2026" |
| `header.recipient_block` line 0 | `\CLCompanyName` | Split on `\n` |
| `header.recipient_block` line 1 | `\CLCompanyStreet` | |
| `header.recipient_block` line 2 | `\CLCompanyCity` | |
| `cover_letter.subject` | `\CLSubject` | |
| `cover_letter.salutation` | `\CLSalutation` | |
| `cover_letter.closing` | `\CLClosing` | |
| `cover_letter.paragraphs` | `\CLParagraph{}` blocks | One block per paragraph |

---

## 3. User variables — exact format

```latex
\newcommand{\CLDate}{April 26\textsuperscript{th} 2026}
\newcommand{\CLCompanyName}{Company Name}
\newcommand{\CLCompanyStreet}{Street and number}
\newcommand{\CLCompanyCity}{ZIP City, Country}
\newcommand{\CLSubject}{Application -- Role Title}
\newcommand{\CLSalutation}{Dear Sir or Madam,}
\newcommand{\CLClosing}{I would welcome the chance to discuss.}
```

**Date ordinal suffixes:**
- 1st, 21st, 31st → `\textsuperscript{st}`
- 2nd, 22nd → `\textsuperscript{nd}`
- 3rd, 23rd → `\textsuperscript{rd}`
- all others → `\textsuperscript{th}`

**LaTeX special characters in any field:**
- `&` → `\&`, `%` → `\%`, `$` → `\$`, `#` → `\#`, `_` → `\_`
- En-dash → `--`, Em-dash → `---`
- `ü` → `\"u`, `é` → `\'e`, `ô` → `\^o`, `à` → `\`a`, `ç` → `\c{c}`

---

## 4. Body paragraphs — AI-FILL region

The filler replaces everything between `%% AI-FILL-START` and `%% AI-FILL-END` with
one `\CLParagraph{}` block per element in `cover_letter.paragraphs`.

```latex
%% AI-FILL-START
\CLParagraph{%
  Paragraph text here.
}

\CLParagraph{%
  Second paragraph text.
}
%% AI-FILL-END
```

**Rules:**
- 3 paragraphs target; 4 max
- 250 words total across all body paragraphs
- Never insert `\vspace`, `\\`, or `\par` inside a `\CLParagraph{}` block
- No blank lines between consecutive `\CLParagraph` calls — spacing is automatic

---

## 5. Closing block — fixed structure

`\letterClose` is called with no arguments. Never insert anything between the last
`\CLParagraph` block and `\letterClose`, and nothing after.

---

## 6. Hard rules — never violate

1. **No `\vspace` in the document body** — every gap governed by named lengths
2. **No `\\` or `\par` inside `\CLParagraph{}`** — body text is flowing prose
3. **No font-size overrides** in body content
4. **Single page only** — if content overflows, trim words; do not adjust geometry
5. **Banned words**: leveraged, utilized, spearheaded, harnessed, fostered, championed,
   passionate, excited, thrilled, eager, dynamic, synergies (as verb)
6. **No metric invention** — every number must come from the profile bank

---

## 7. Spacing controls (only when user explicitly asks)

| Variable | Default | What it controls |
|---|---|---|
| `\headerLineGap` | 2pt | Header line 1 → line 2 |
| `\afterHeaderGap` | 18pt | Header → date |
| `\afterDateGap` | 14pt | Date → company block |
| `\afterCompanyGap` | 14pt | Company → subject |
| `\afterSubjectGap` | 14pt | Subject → salutation |
| `\afterSalutationGap` | 10pt | Salutation → first paragraph |
| `\parBodyGap` | 10pt | Between body paragraphs |
| `\beforeClosingGap` | 4pt | Last paragraph → closing line |
| `\beforeGreetingGap` | 8pt | Closing line → greeting |
| `\beforeSignatureGap` | 12pt | Greeting → name |
| `\beforeContactGap` | 4pt | Name → bottom contact line |
