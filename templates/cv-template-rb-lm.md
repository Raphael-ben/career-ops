# cv-template-rb-lm.tex — AI Agent Fill Guide

This is the instruction set for an AI agent generating CV content into
`cv-template-rb-lm.tex`. The template uses encapsulated environments and
named-length spacing — body content is purely declarative, and **the AI
must never add `\vspace`, `\par`, or `\\[Xpt]` inline**.

---

## TL;DR — what to fill, what to never touch

**Fill these:**
- User variables block (name, address, phone, email, photo path, tagline)
- Photo crop controls (`\photoScale`, `\photoXshift`, `\photoYshift`)
- The document body — sidebar blocks, experiences, education entries

**Never touch:**
- The `Spacing controls` block (only retune values when the user explicitly asks)
- The custom command and environment definitions in the preamble
- The minipage geometry (sidebar width, page margins)

---

## 1. User variables

At the top of the preamble:

```latex
\newcommand{\CVName}{FIRSTNAME LASTNAME}
\newcommand{\CVTagline}{Role line 1,\\[2pt]Role line 2}
\newcommand{\CVPhoto}{photo.jpg}             %% in same directory as the .tex
\newcommand{\CVAddress}{Street 75\\8057 City}
\newcommand{\CVPhone}{+41\,78\,621\,34\,68}
\newcommand{\CVEmail}{first.last@example.com}
```

**Photo crop (tune until the face is properly framed in the circle):**

```latex
\def\photoScale{1.15\linewidth}   %% larger = tighter crop
\def\photoXshift{6mm}             %% positive shifts image right
\def\photoYshift{0mm}             %% negative shifts image down
```

For a 16:9 landscape photo, `\photoScale` must be ≥ ~1.4× the circle radius
to fill vertically (otherwise the circle clips top and bottom).

---

## 2. Main column — experiences

One block per job. Order: most recent first.

```latex
\begin{experience}{date range}{job title}{company}{location}{company URL}
  \item First responsibility / achievement
  \item Second responsibility / achievement
\end{experience}
```

**Rules:**
- Use `\item` for every bullet — no other syntax allowed
- Do NOT add `\vspace` between entries — the environment handles it
- Bullet text can be any length; wrapping is automatic
- For symbols: `$>$` for greater-than, `$<$` for less-than, `\&` for ampersand
- For accented characters: standard LaTeX escapes (e.g. `\'e`, `\^o`)

---

## 3. Main column — education

Identical structure, semantic alias:

```latex
\begin{education}{date range}{degree / qualification}{institution}{location}{URL}
  \item Distinction, ranking, or program detail
  \item Subjects or notable projects
\end{education}
```

If the entry doesn't have a clean "degree" name (e.g. a preparatory class),
use a **short title** and put the program description as a bullet:

```latex
\begin{education}{Sept.~'09 -- Sept.~'11}{Engineering Preparatory Class (CPGE)}{Lycée X}{Lyon}{url}
  \item Intensive 2-year preparatory course for top engineering schools
\end{education}
```

**Section transition (last experience → EDUCATION title):**

The body must contain `\vspace{\sectionGap}` between the last `\end{experience}`
and `\mainSection[\faGraduationCap]{EDUCATION}`. This is the only `\vspace`
allowed in the body.

---

## 4. Sidebar — header

The sidebar header is fixed and renders in this order:

```latex
\cvName                 %% renders \CVName centred
\cvPhoto                %% renders the circular photo crop
\tagline{\CVTagline}    %% renders the tagline
```

Do not insert `\vspace` between these — gaps are controlled by
`\nameBelowGap`, `\photoBelowGap`, `\taglineBelowGap` in the preamble.

---

## 5. Sidebar — body sections (THE KEY RULE)

For each section (FOREIGN LANGUAGES, PERSONAL SKILLS, COMPUTER SKILLS,
EXTRA-CURRICULAR ACTIVITIES), use a `sidebarBlock`:

```latex
\begin{sidebarBlock}{SECTION TITLE IN UPPERCASE}
  ... items ...
\end{sidebarBlock}
```

Inside, you have **two item types**: `\sline` and `\pair`. Choose based on
content length and count, using this rule:

### Decision rule

Walk the items in order. For each item:

1. **If the text is too long to fit half the sidebar width** → use `\sline{text}` (single full-width line).
2. **Otherwise**, try to pair it with the *next* short item → `\pair{this}{next}` (two columns).
3. **If you reach the end with one short item left over** (odd count) → use `\sline{text}` for the leftover.

In one block, `\sline` and `\pair` can be freely mixed — render order is top to bottom.

### Examples (already present in the template)

```latex
%% All long → all sline
\begin{sidebarBlock}{FOREIGN LANGUAGES}
  \sline{French: Mother tongue}
  \sline{English: Bilingual}
  \sline{German: Fluent}
\end{sidebarBlock}

%% Six short pairs + one long trailing item
\begin{sidebarBlock}{PERSONAL SKILLS}
  \pair{Team Player}{Curious}
  \pair{Business Analysis}{Finance}
  \pair{Communication}{Pro-active}
  \pair{Manufacturing}{Luxury}
  \pair{Startups}{Innovation}
  \pair{Investment}{Due diligence}
  \sline{High-Tech \& Innovation knowledge}    %% too long for two columns
\end{sidebarBlock}

%% Three pairs + one odd leftover
\begin{sidebarBlock}{COMPUTER SKILLS}
  \pair{MS Office}{AI automations}
  \pair{VBA}{JAVA}
  \pair{C, C++}{SQL}
  \sline{SolidWorks}                            %% leftover, becomes sline
\end{sidebarBlock}

%% Two long lines + three short pairs
\begin{sidebarBlock}{EXTRA-CURRICULAR ACTIVITIES}
  \sline{CrossFit Level 1 trainer}              %% too long
  \sline{Aviation -- PPL(A)}                    %% too long
  \pair{Skiing}{Mountaineering}
  \pair{Triathlon}{Cycling}
  \pair{Rock Climbing}{Golf}
\end{sidebarBlock}
```

### Width reference

The sidebar inner width is roughly 50mm wide, so each `\pair` column is
~22mm. Items longer than ~22mm at 10pt (≈ 18-20 characters) won't fit
comfortably in a column — use `\sline` for those.

---

## 6. Sidebar — contact block (always last)

```latex
\begin{contactBlock}
  \address{Street 75\\8057 City}
  \phone{+41\,78\,621\,34\,68}
  \email{first.last@example.com}
\end{contactBlock}
```

**Rules:**
- Always the last block in the sidebar (pinned to bottom via internal `\vfill`)
- Use `\\` inside `\address{}` for line breaks
- `\phone{}` is plain text (no `tel:` link by design — Mac Preview's hyperref bug expanded the link annotation to the full sidebar in earlier tests).
- `\email{}` IS a clickable `mailto:` link, made Preview-safe by combining `\mbox{}` around the icon+text (forces a tight inline box) with `pdflinkmargin=0pt` in `\hypersetup` (zeroes the annotation padding). If Preview ever starts misbehaving again on a different macOS version, revert to plain text: `{\sidebarBodyFont\faEnvelope~#1}\par`.

---

## 7. Spacing controls (only when user asks)

All gaps live as named lengths in the `Spacing controls` block. Tune values,
never edit structure. Reference table:

| Variable | Default | What it controls |
|---|---|---|
| `\entryRowGap` | -3pt | Job title → company name (negative pulls them tight) |
| `\entryBottomGap` | 3pt | Company name → first bullet |
| `\entryGap` | 5pt | Between consecutive experience/education blocks |
| `\sectionGap` | 10pt | Extra gap before a new main section title |
| `\sectionRuleGap` | -3pt | Section title text → underline rule |
| `\sectionBodyGap` | 1pt | Underline rule → first entry below it |
| `\setul{D}{T}` | `1.5pt` / `0.4pt` | Company-name underline: D = distance from baseline, T = rule thickness. Smaller D = tighter underline. Below ~3pt, p/q descenders cross the rule (intentional, keeps gap consistent across all words). |
| `\sidebarLineGap` | 3pt | Between `\sline` / `\pair` items in a sidebarBlock |
| `\photoBelowGap` | 2pt | Below photo |
| `\nameBelowGap` | 5pt | Below name |
| `\taglineBelowGap` | 14pt | Below tagline (above first sidebar block) |
| `\sidebarBottomPad` | 8pt | At very bottom of sidebar (after contact) |
| `\sidebarBodyFont` | `\small` | Font size for ALL sidebar body items |

---

## 8. Compile

From the `templates/` directory:

```bash
pdflatex -interaction=nonstopmode -halt-on-error cv-template-rb-lm.tex
```

Output: `cv-template-rb-lm.pdf` in the same directory.

If compilation fails:
- Check that the photo file exists (the template falls back to a placeholder if not)
- Check for unescaped `&`, `%`, `_`, `#`, `$` in body text (escape with `\`)
- Make sure every `\begin{...}` has a matching `\end{...}`

---

## 9. Hard rules — never violate

1. **No `\vspace` in the document body**, except `\vspace{\sectionGap}` between the last experience and the EDUCATION header.
2. **No `\par` in body content** — environments handle paragraph breaks.
3. **No `\\[Xpt]` for spacing** — use `\sline` or `\pair` for sidebar lines.
4. **No raw `\skillrow` calls** — use `\pair` (semantic alias).
5. **No new `\newcommand` or `\newenvironment`** in the body — define in preamble only.
6. **No font-size overrides** in body content — `\sidebarBodyFont` controls all sidebar body sizes; entry titles/dates/companies are styled by the environment.
7. **Single page only** — if content overflows, trim bullets, do not adjust geometry.
