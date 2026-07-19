# Mode: pro/humanize — Job Application Humanizer

> Adapted from [blader/humanizer](https://github.com/blader/humanizer) — LaTeX-specific fork with 29 rules tuned for job application CVs and cover letters.
> Original work Copyright (c) 2025 Siqi Chen, MIT License.

## Purpose
Remove AI writing patterns from CV and cover letter LaTeX content. This mode is self-contained — all 29 humanization rules are embedded below. No external skill is required.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). The concrete banned-word/phrase LISTS below come from `profile_bank.humanize.*`; the 29 conceptual patterns are person-agnostic and stay in this file. `{file_slug}` = `profile_bank.candidate.file_slug`.

---

## Hard constraints (enforced throughout — override everything else)

1. Do NOT change any factual content: companies, roles, dates, metrics, headcounts, percentages
2. Do NOT change document structure: sections, ordering, paragraph count, bullet count
3. Do NOT shorten content beyond removing banned patterns
4. Do NOT add new claims not present in the input
5. Return ONLY the improved text — no preamble, no explanation, no "Here is the revised version:"

---

## What to touch

**CV (`{file_slug}_CV.tex`)**: `\item` bullet text only. One bullet at a time. Do not touch LaTeX commands, section headers, company names, dates, or numeric metrics.

**Cover letter (`{file_slug}_cover-letter.tex`)**: text inside `\CLParagraph{%...}` blocks only. Do not touch salutation, `\CLDate`, `\CLCompanyName`, `\CLSenderName`, or any other header variable.

## What NOT to touch

- LaTeX commands: `\textbf`, `\href`, `\section`, `\item` itself, `\begin`/`\end`, `\\`, `%`
- Company names, role titles, degree names
- Dates and date ranges
- Numeric metrics (percentages, headcounts, monetary figures, CHF/EUR/USD amounts)
- Proper nouns and acronyms
- The `\CLParagraph{%` wrapper — only the text inside it

---

## Job-application-specific bans (in addition to the 29 patterns below)

These are data-driven. Read the lists from the profile bank and ban every entry, in whatever language the document is written:

- **Verbs / openers** — `profile_bank.humanize.banned_bullet_openers` (also `banned_words`): replace with concrete action verbs.
- **Adjectives / filler words** — `profile_bank.humanize.banned_words` (+ `banned_words_de`, `banned_words_fr`): remove or replace with evidence.
- **Phrases / constructions** — `profile_bank.humanize.banned_phrases` (+ `banned_phrases_de`, `banned_phrases_fr`): remove or rewrite (e.g. cover-letter clichés, "at the intersection of" constructions).

**Constructions to also restructure** (concept-level, language-agnostic): "-ing" pileups ("fostering collaboration, ensuring delivery, championing change" → restructure); a verb used as a false synergy noun.

**Em dashes and clause-connector dashes:**
- Replace `—` (U+2014) with a comma or restructure.
- Replace LaTeX `--` used as a **clause connector** (pattern: `word -- word` in prose) with a comma, colon, or two sentences. Example: "My background combines X -- each tested in Y" → "My background combines X, each tested in Y."
- Exception: keep `--` for **numeric ranges** (e.g. `3--5M`, `CHF 1--5M`, `Aug.~'21 -- Jul.~'22`) and date ranges. The test: is the `--` between two numbers/dates? Keep it. Connecting prose phrases? Replace it.

---

## Language-agnostic enforcement (CRITICAL)

All 29 patterns and bans above describe **concepts**, not English words. Apply them to any language — German, French, or English — by detecting the equivalent phrasing. The rules fire on the concept regardless of language. The concrete word lists in `profile_bank.humanize.*_de` / `*_fr` are seeds, not the full set — also catch the conceptual equivalents below.

### German-language patterns to watch (most common AI tells in DE cover letters)

**False ranges (#12):** `von X bis hin zu Y`, `von X über Y bis Z` → list items directly.
**Generic positive conclusions (#25):** `Ich freue mich auf die Möglichkeit, Sie … kennenzulernen`, `Ich freue mich darauf, … beizutragen`, `Ich bin überzeugt, dass…` → cut or state the specific reason.
**Negative parallelisms (#9):** `nicht als X, sondern als Y`, `nicht nur X, sondern auch Y` → state the positive directly.
**"At its core" equivalents (#27):** `im Kern`, `im Wesentlichen`, `letztlich`, `im Grunde` → remove; state the point.
**Formulaic callbacks:** `Diese Erfahrung passt zur Position als…`, `Diese Erfahrung hat meine Fähigkeit gestärkt, …`, `insbesondere in Bezug auf` → cut or fold in.
**Promotional (#4):** `ein Fundament, das X mit Y verbindet`, `an der Schnittstelle von X und Y` (remove if vague), `passt genau zu dem, was … benötigt` → show the fit through facts.
**Generic closings:** any variant of `Vielen Dank für die Berücksichtigung meiner Bewerbung` → keep short; `Ich freue mich auf ein persönliches Gespräch` acceptable only if brief and at the very end.

### French-language patterns to watch

**False ranges:** `de X à Y` when not a real scale.
**Generic conclusions:** `Je me réjouis de vous rencontrer`, `Je reste à votre disposition`.
**Negative parallelisms:** `non pas X, mais Y`.
**Promotional:** `à l'interface de`, `qui allie X et Y`, `correspond exactement à`.

---

## 29 Humanization Patterns

Apply all of these. Source: blader/humanizer SKILL.md v2.5.1, based on Wikipedia's "Signs of AI writing" guide.

### Content Patterns

**1. Significance inflation** — Words: stands/serves as, is a testament/reminder, vital/significant/crucial/pivotal/key role, underscores/highlights its importance, reflects broader, symbolizing, contributing to, setting the stage for, marks a shift, key turning point, evolving landscape, indelible mark. Fix: state the fact directly.

**2. Notability name-dropping** — Words: independent coverage, local/national media outlets, active social media presence. Fix: cite specifically or remove.

**3. Superficial -ing analyses** — Words: highlighting, underscoring, emphasizing, ensuring, reflecting, symbolizing, contributing to, cultivating, fostering, encompassing, showcasing (tacked on to add fake depth). Fix: remove the dangling participle or replace with a concrete fact.
> Before: "led the integration, contributing to a 20% efficiency gain, highlighting the team's…"
> After: "led the integration, achieving a 20% efficiency gain"

**4. Promotional language** — Words: boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, nestled, in the heart of, groundbreaking, renowned, breathtaking, stunning. Fix: neutral factual language.

**5. Vague attributions / weasel words** — Words: Industry reports, Observers have cited, Experts argue, Some critics argue. Fix: name the source or remove.

**6. Formulaic challenges sections** — Words: Despite its…faces challenges, Despite these challenges, Challenges and Legacy, Future Outlook. Fix: specific facts about actual challenges.

### Language Patterns

**7. AI vocabulary overuse** — Replace: actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry, testament, underscore (verb), valuable, vibrant. Fix: plain, specific words.

**8. Copula avoidance (serves as / stands as)** — Words: serves as, stands as, marks, represents [a], boasts, features, offers [a] — when used instead of "is/are/has". Fix: use simple is/are/has.

**9. Negative parallelisms and tailing negations** — "It's not just about X; it's about Y", "not merely X, it's Y", clipped endings like ", no guessing". Fix: state the point directly.

**10. Rule of three overuse** — LLMs force ideas into groups of three. Fix: use the natural number of items.

**11. Elegant variation / synonym cycling** — Excessive synonym substitution. Fix: repeat the clearest word.

**12. False ranges** — "from X to Y" where X and Y aren't on a meaningful scale. Fix: list topics directly.

**13. Passive voice / subjectless fragments** — Hiding the actor or dropping the subject. Fix: name the actor when it adds clarity.

### Style Patterns

**14. Em dash overuse** — Replace `—` with comma, parentheses, or a new sentence. (Covered in job-application bans above.)

**15. Boldface overuse** — Remove bold from inline prose; keep only where the LaTeX template requires it.

**16. Inline-header vertical lists** — Pattern: `\item \textbf{Topic:} Topic description`. Fix: rewrite as a single clean bullet.

**17. Title case in headings** — Fix: sentence case only (LaTeX section commands handle formatting).

**18. Emojis** — Remove all emojis from text content.

**19. Curly quotation marks** — Replace curly quotes with straight quotes if they appear inside LaTeX text.

**26. Hyphenated word pair overuse** — Common over-hyphenated pairs: third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end. Fix: drop hyphens on common compound adjectives; keep them where ambiguity would result.

**27. Persuasive authority tropes** — Phrases: The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter. Fix: state the ordinary point directly.

**28. Signposting and announcements** — Phrases: Let's dive in, let's explore, let's break this down, here's what you need to know, without further ado. Fix: start with the content.

**29. Fragmented headers / filler openers** — A heading/bullet opener followed by a generic sentence that restates it before the real content. Fix: remove the filler sentence.

### Communication Patterns

**20. Chatbot artifacts** — I hope this helps, Of course!, Certainly!, Would you like, let me know, here is a…. Fix: remove entirely.

**21. Knowledge-cutoff disclaimers** — as of [date], up to my last training update, while specific details are limited. Fix: remove.

**22. Sycophantic tone** — Great question!, You're absolutely right!, That's an excellent point. Fix: respond directly.

### Filler and Hedging

**23. Filler phrases** — "In order to achieve" → "To achieve"; "Due to the fact that" → "Because"; "At this point in time" → "Now"; "In the event that" → "If"; "has the ability to" → "can"; "It is important to note that" → remove.

**24. Excessive hedging** — Fix: one hedge word maximum per claim.

**25. Generic positive conclusions** — the future looks bright, exciting times lie ahead, journey toward excellence, major step in the right direction. Fix: specific facts or plans.

---

## Process

1. Read the full `.tex` file
2. Identify all text regions (bullets and cover letter paragraphs)
3. For each text region:
   a. Apply hard constraints filter first (mark anything that would change facts/structure as off-limits)
   b. Scan against all 29 patterns + the `profile_bank.humanize.*` bans
   c. Rewrite only the flagged phrases; leave everything else identical
4. Final pass: "What still reads as obviously AI-generated?" — fix any remaining tells
5. **Cover-letter-specific checks (run after pattern pass):**
   a. **Grades**: if `profile_bank.rules.education_display.cgpa_never_in_cover_letter` is true, scan `\CLParagraph{}` blocks for any numeric grade (`CGPA`, `GPA`, or any decimal next to `/6` / `/4` / `/5`). Remove the numeric score entirely — keep only institution and degree name.
   b. **Word count**: count words inside all `\CLParagraph{}` blocks combined. If the total exceeds `profile_bank.verify.tolerances.cover_letter_max_words`, trim the longest paragraph(s) by cutting generic or repeated observations until within limit. Never cut factual claims or the formal close. Report the trim in `changes`.
6. Output the full `.tex` file with LaTeX structure intact and only text regions changed

---

## Output

Return the full file content (not just changed sections) with LaTeX structure identical to input and only prose text improved.

After writing the humanized `.tex` files, write `humanizer_report.json` to the same output folder:

```json
{
  "ran_at": "ISO-8601 timestamp",
  "documents": ["{file_slug}_CV.tex", "{file_slug}_cover-letter.tex"],
  "flags_found": 0,
  "rewrites_applied": 0,
  "changes": [
    { "document": "{file_slug}_CV.tex", "pattern": "<pattern name from the 29-pattern list>", "before": "<original>", "after": "<rewritten>" }
  ],
  "summary": "<one sentence: how many flags, what was changed, any patterns with zero hits>"
}
```

If a document had no flags and no rewrites, still include it in `documents` with zero counts. Always write the file even if no changes were made — its presence confirms the humanizer ran.
