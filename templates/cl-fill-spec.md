# Cover Letter Fill Spec — rb/write-cl

Compact syntax reference. Paragraph structure, standing rules, and language rules
are in `write-cl.md`. This file covers only *how to format* the LaTeX output.

---

## Output process

1. Read `cover-letter-template-rb-lm.tex`. Copy lines 1–173 (preamble) verbatim.
2. Fill user variables (lines 57–80 of preamble) with job-specific values.
3. Write the document body using the syntax below.

---

## User variables (lines 57–80 of preamble)

| Command | Purpose | Notes |
|---|---|---|
| `\CLLanguage` | Babel language | `ngerman` \| `french` \| `english` |
| `\CLDate` | Letter date | DE: `3. Mai 2026` · FR: `3 mai 2026` · EN: `May 3\textsuperscript{rd} 2026` |
| `\CLCompanyName` | Company name | Exact name |
| `\CLCompanyStreet` | Street address | |
| `\CLCompanyCity` | City / country | |
| `\CLSubject` | Subject line (rendered bold) | Language-matched — see write-cl.md Step 5 |
| `\CLSalutation` | Opening salutation | Language-matched — see write-cl.md Step 5 |
| `\CLClosing` | Closing sentence | **Always empty string `{}`** — never put text here |
| `\CLGreeting` | Valediction | `Mit freundlichen Grüssen,` (DE+swiss) · `Mit freundlichen Grüßen,` (DE) · `Yours sincerely,` (EN) · `Veuillez agréer l'expression de mes salutations distinguées,` (FR) |

**Do not change:** `\CLName`, `\CLAddress`, `\CLPhone`, `\CLEmail` — Raphael's info is pre-filled.

---

## Document body

Replace everything between `%% AI-FILL-START` and `%% AI-FILL-END` with one
`\CLParagraph{}` block per paragraph. The Pilatus structure requires **6 paragraphs**
(see write-cl.md Step 4 for full paragraph-by-paragraph rules):

```latex
%% AI-FILL-START
\CLParagraph{%
  Para 1 — Application statement + profile formula.
}

\CLParagraph{%
  Para 2 — PwC, mapped to the JD.
}

\CLParagraph{%
  Para 3 — Prior relevant role.
}

\CLParagraph{%
  Para 4 — Education + specific motivation.
}

\CLParagraph{%
  Para 5 — Values alignment.
}

\CLParagraph{%
  Para 6 — Formal close.
}
%% AI-FILL-END
```

**Rules:**
- No `\vspace`, `\\`, or `\par` inside any `\CLParagraph{}` block.
- No blank lines between consecutive `\CLParagraph` calls.
- `\letterClose` is called automatically after the fill region — do not add it.

---

## Special chars

| Symbol | LaTeX |
|---|---|
| & | `\&` |
| % | `\%` |
| $ | `\$` |
| # | `\#` |
| _ | `\_` |
| En-dash | `--` |
| Em-dash | `---` |
| ü | `\"u` |
| é | `\'e` |
| ô | `\^o` |
| à | `` \`a `` |
| ç | `\c{c}` |

---

## Hard rules

- `\CLClosing` **must always be empty string** — the template auto-prints name and contact.
- Single page only — trim words if content overflows; never adjust geometry.
- No em dashes anywhere — use commas or semicolons instead.
- No new `\newcommand` or `\newenvironment` in the body.
