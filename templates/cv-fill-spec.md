# CV Fill Spec — rb/write-cv

Compact syntax reference. Selection rules, standing rules, and ATS injection logic
are in `write-cv.md`. This file covers only *how to format* the LaTeX output.

---

## Output process

1. Read `cv-template-rb-lm.tex`. Copy lines 1–282 (preamble) verbatim.
2. Fill user variables (lines 76–87 of preamble) with job-specific values.
3. Write the document body from `\begin{document}` onward using the syntax below.

---

## User variables (lines 76–87 of preamble)

| Command | Purpose | Fixed value / Notes |
|---|---|---|
| `\CVName` | Full name | `Raphael Benyamine` — always fixed |
| `\CVTagline` | 1–2 line positioning | Tailored per role; **≤ 22 chars/line** (58 mm sidebar @ `\large\textbf`) |
| `\CVPhoto` | Photo filename | `cv-2.jpg` — always fixed (file is in the output folder) |
| `\CVAddress` | Address (use `\\` for line break) | `Schaffhauserstrasse 75\\8057 Zürich` — fixed |
| `\CVPhone` | Phone | `+41\,78\,621\,34\,68` — fixed |
| `\CVEmail` | Email | `raphael.benyamine@gmail.com` — fixed |
| `\photoScale` | Photo scale | `1.0` — leave unchanged |
| `\photoXshift` | Photo x-shift | `0pt` — leave unchanged |
| `\photoYshift` | Photo y-shift | `0pt` — leave unchanged |

**Tagline character limit is strict.** Count characters before writing. Abbreviate if needed
("Prog. Manager" instead of "Program Manager" if necessary).

---

## Sidebar blocks

```latex
\begin{sidebarBlock}{SECTION TITLE IN UPPERCASE}
  \sline{Full-width item (text longer than ~18 chars)}
  \pair{Short item}{Short item}    % each column ≤ 18 chars; leftover odd short item → \sline
\end{sidebarBlock}
```

Sections in order:
1. FOREIGN LANGUAGES
2. PERSONAL SKILLS
3. COMPUTER SKILLS
4. EXTRA-CURRICULAR ACTIVITIES

Do **not** touch `\begin{contactBlock}...\end{contactBlock}` — it is fixed in the template body.

---

## Experience blocks (most recent first)

```latex
\begin{experience}{date range}{job title}{company}{location}{company URL}
  \item Bullet text.
  \item Bullet text.
\end{experience}
```

**Date format:**
- Current role: `Since Nov.~2022` (spelled-out year for ongoing)
- Completed: `Aug.~'21 -- Jul.~'22`

**Month abbreviations:** Jan., Feb., Mar., Apr., May, June, July, Aug., Sept., Oct., Nov., Dec.

**Special chars in bullet text:** `\&` `\%` `\_` `\#` `\$`; use `$>$` and `$<$` for inequality symbols.
No curly quotes — use straight ASCII. No `\vspace`, `\par`, or `\\[Xpt]` anywhere in the body.

---

## Section break (experience → education)

```latex
\vspace{\sectionGap}
\mainSection[\faGraduationCap]{EDUCATION}
```

This is the **only** `\vspace` allowed in the document body.

---

## Education blocks

```latex
\begin{education}{date range}{degree}{institution}{location}{URL}
  \item Note or distinction.
  \item Second note if needed.
\end{education}
```

---

## Hard rules

- No `\vspace` in body except the single `\vspace{\sectionGap}` before EDUCATION.
- No `\par` or `\\[Xpt]` in body content — environments handle spacing.
- Single page only — trim bullets if content overflows; never adjust geometry.
- Never add new `\newcommand` or `\newenvironment` in the body.
