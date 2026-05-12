# Mode: rb/humanize — Job Application Humanizer

> Adapted from [blader/humanizer](https://github.com/blader/humanizer) — LaTeX-specific fork with 29 rules tuned for job application CVs and cover letters.

## Purpose
Remove AI writing patterns from CV and cover letter LaTeX content. This mode is self-contained — all 29 humanization rules are embedded below. No external skill is required.

---

## Hard constraints (enforced throughout — override everything else)

1. Do NOT change any factual content: companies, roles, dates, metrics, headcounts, percentages
2. Do NOT change document structure: sections, ordering, paragraph count, bullet count
3. Do NOT shorten content beyond removing banned patterns
4. Do NOT add new claims not present in the input
5. Return ONLY the improved text — no preamble, no explanation, no "Here is the revised version:"

---

## What to touch

**CV (`Raphael-Benyamine_CV.tex`)**: `\item` bullet text only. One bullet at a time. Do not touch LaTeX commands, section headers, company names, dates, or numeric metrics.

**Cover letter (`Raphael-Benyamine_cover-letter.tex`)**: text inside `\CLParagraph{%...}` blocks only. Do not touch salutation, `\CLDate`, `\CLCompanyName`, `\CLSenderName`, or any other header variable.

## What NOT to touch

- LaTeX commands: `\textbf`, `\href`, `\section`, `\item` itself, `\begin`/`\end`, `\\`, `%`
- Company names, role titles, degree names
- Dates and date ranges
- Numeric metrics (percentages, headcounts, monetary figures, CHF/EUR/USD amounts)
- Proper nouns and acronyms
- The `\CLParagraph{%` wrapper — only the text inside it

---

## Job-application-specific bans (in addition to the 29 patterns below)

**Verbs / openers** — replace with concrete action verbs:
- leveraged, utilized, spearheaded, harnessed, fostered, championed

**Adjectives** — remove or replace with evidence:
- passionate (without specific evidence), excited, thrilled, eager, dynamic / dynamisch / dynamique

**Constructions:**
- "-ing" pileups: "fostering collaboration, ensuring delivery, championing change" → restructure
- "I am writing to apply…"
- "track record of"
- "results-driven"
- "synergies" used as a verb

**Em dashes and clause-connector dashes:**
- Replace `—` (U+2014) with a comma or restructure.
- Replace LaTeX `--` used as a **clause connector** (pattern: `word -- word` in prose) with a comma, colon, or rewrite as two sentences. Example: "My background combines X -- each tested in Y" → "My background combines X, each tested in Y." or split into two sentences.
- Exception: keep `--` for **numeric ranges** (e.g. `3--5M`, `CHF 1--5M`, `Aug.~'21 -- Jul.~'22`) and date ranges. The test: is the `--` between two numbers/dates? Keep it. Is it connecting prose phrases? Replace it.

---

## Language-agnostic enforcement (CRITICAL)

All 29 patterns and bans above describe **concepts**, not English words. Apply them to any language — German, French, or English — by detecting the equivalent phrasing. The rules fire on the concept regardless of language.

### German-language patterns to watch (most common AI tells in DE cover letters)

**False ranges (#12):**
- `von X bis hin zu Y` → list items directly instead
- `von X über Y bis Z` → same

**Generic positive conclusions (#25):**
- `Ich freue mich auf die Möglichkeit, Sie … kennenzulernen` → cut or make specific
- `Ich freue mich darauf, … beizutragen` → same
- `Ich bin überzeugt, dass…` → state the specific reason instead

**Negative parallelisms (#9):**
- `nicht als X, sondern als Y` → state the positive directly
- `nicht nur X, sondern auch Y` → restructure if adding no information

**"At its core" equivalents (#27):**
- `im Kern`, `im Wesentlichen`, `letztlich`, `im Grunde` → remove; state the point

**Formulaic callbacks (AI pattern):**
- `Diese Erfahrung passt zur Position als…` → cut; the match is shown by the experience itself
- `Diese Erfahrung hat meine Fähigkeit gestärkt, …` → cut; state the concrete outcome instead
- `insbesondere in Bezug auf` → cut or fold into the preceding sentence

**Promotional language (#4) in German:**
- `ein Fundament, das X mit Y verbindet` → state what the degree taught specifically
- `an der Schnittstelle von X und Y` → acceptable if precise; remove if vague
- `passt genau zu dem, was … benötigt` → cut; show the fit through facts

**Generic closing sentences:**
- Any variant of `Vielen Dank für die Berücksichtigung meiner Bewerbung` → keep short; `Für Rückfragen stehe ich gerne zur Verfügung.` is fine
- `Ich freue mich auf ein persönliches Gespräch` → acceptable if brief and at the end; flag if the paragraph IS the closing

### French-language patterns to watch

**False ranges:** `de X à Y` when not a real scale
**Generic conclusions:** `Je me réjouis de vous rencontrer`, `Je reste à votre disposition`
**Negative parallelisms:** `non pas X, mais Y`
**Promotional:** `à l'interface de`, `qui allie X et Y`, `correspond exactement à`

---

## 29 Humanization Patterns

Apply all of these. Source: blader/humanizer SKILL.md v2.5.1, based on Wikipedia's "Signs of AI writing" guide.

### Content Patterns

**1. Significance inflation**
Words: stands/serves as, is a testament/reminder, vital/significant/crucial/pivotal/key role, underscores/highlights its importance, reflects broader, symbolizing, contributing to, setting the stage for, marks a shift, key turning point, evolving landscape, indelible mark
Fix: State the fact directly. Remove the puffery.
> Before: "marking a pivotal moment in the evolution of regional statistics"
> After: "established in 1989 to collect regional statistics independently"

**2. Notability name-dropping**
Words: independent coverage, local/national media outlets, active social media presence
Fix: Cite specifically or remove.
> Before: "cited in The New York Times, BBC, Financial Times"
> After: "In a 2024 NYT interview, she argued…"

**3. Superficial -ing analyses**
Words: highlighting, underscoring, emphasizing, ensuring, reflecting, symbolizing, contributing to, cultivating, fostering, encompassing, showcasing (when tacked onto a sentence to add fake depth)
Fix: Remove the dangling participle phrase or replace with a concrete fact.
> Before: "led the integration, contributing to a 20% efficiency gain, highlighting the team's…"
> After: "led the integration, achieving a 20% efficiency gain"

**4. Promotional language**
Words: boasts a, vibrant, rich (figurative), profound, enhancing its, showcasing, exemplifies, commitment to, nestled, in the heart of, groundbreaking, renowned, breathtaking, stunning
Fix: Neutral factual language.
> Before: "leveraging groundbreaking tools to enhance stakeholder value"
> After: "using process automation to cut reporting time by 30%"

**5. Vague attributions / weasel words**
Words: Industry reports, Observers have cited, Experts argue, Some critics argue
Fix: Name the source or remove.
> Before: "Experts believe it plays a crucial role"
> After: "according to the 2023 McKinsey report"

**6. Formulaic challenges sections**
Words: Despite its…faces challenges, Despite these challenges, Challenges and Legacy, Future Outlook
Fix: Specific facts about actual challenges.
> Before: "Despite challenges, continues to thrive"
> After: "Reduced headcount by 15% while maintaining output"

### Language Patterns

**7. AI vocabulary overuse**
High-frequency words to replace: actually, additionally, align with, crucial, delve, emphasizing, enduring, enhance, fostering, garner, highlight (verb), interplay, intricate/intricacies, key (adjective), landscape (abstract noun), pivotal, showcase, tapestry, testament, underscore (verb), valuable, vibrant
Fix: Use plain, specific words.
> Before: "Additionally, showcasing an intricate interplay of skills"
> After: "combining financial modeling with stakeholder management"

**8. Copula avoidance (serves as / stands as)**
Words: serves as, stands as, marks, represents [a], boasts, features, offers [a] — when used instead of "is/are/has"
Fix: Use simple is/are/has.
> Before: "serves as the primary interface for…"
> After: "is the primary interface for…"

**9. Negative parallelisms and tailing negations**
Constructions: "It's not just about X; it's about Y", "not merely X, it's Y", clipped endings like ", no guessing" or ", no wasted motion"
Fix: State the point directly.
> Before: "It's not just about deal execution; it's about building trust"
> After: "Deal execution requires building trust with management"

**10. Rule of three overuse**
Problem: LLMs force ideas into groups of three.
Fix: Use the natural number of items.
> Before: "innovation, inspiration, and industry insights"
> After: "new analytical frameworks"

**11. Elegant variation / synonym cycling**
Problem: Excessive synonym substitution due to repetition penalty.
Fix: Repeat the clearest word.
> Before: "the protagonist… the main character… the central figure… the hero"
> After: "the protagonist" (repeated)

**12. False ranges**
Construction: "from X to Y" where X and Y aren't on a meaningful scale.
Fix: List topics directly.
> Before: "from strategy to execution, from ideation to delivery"
> After: "strategy, financial modeling, and execution"

**13. Passive voice / subjectless fragments**
Problem: Hiding the actor or dropping the subject entirely.
Fix: Name the actor when it adds clarity.
> Before: "No configuration needed. Results are preserved automatically."
> After: "You do not need to configure anything. The system saves results automatically."

### Style Patterns

**14. Em dash overuse**
Fix: Replace `—` with comma, parentheses, or a new sentence. (Already covered in job-application bans above.)

**15. Boldface overuse**
Problem: Mechanically bolding phrases.
Fix: Remove bold from inline prose; keep only where LaTeX template requires it.

**16. Inline-header vertical lists**
Pattern: `\item \textbf{Topic:} Topic description`
Fix: Rewrite as a single clean bullet.
> Before: `\item \textbf{Speed:} Code generation is significantly faster, reducing friction.`
> After: `\item Automated test generation cut cycle time by 40%.`

**17. Title case in headings**
Problem: Capitalizing all main words.
Fix: Sentence case only (LaTeX section commands handle formatting).

**18. Emojis**
Fix: Remove all emojis from text content.

**19. Curly quotation marks**
Fix: Replace curly `"..."` with straight `"..."` if they appear inside LaTeX text.

**26. Hyphenated word pair overuse**
Common over-hyphenated pairs: third-party, cross-functional, client-facing, data-driven, decision-making, well-known, high-quality, real-time, long-term, end-to-end
Fix: Drop hyphens on common compound adjectives. Keep them for technical compound modifiers where ambiguity would result.
> Before: "cross-functional team delivered a data-driven analysis"
> After: "cross functional team delivered a data driven analysis"

**27. Persuasive authority tropes**
Phrases: The real question is, at its core, in reality, what really matters, fundamentally, the deeper issue, the heart of the matter
Fix: State the ordinary point directly.
> Before: "At its core, what really matters is execution speed"
> After: "Execution speed determines deal outcomes"

**28. Signposting and announcements**
Phrases: Let's dive in, let's explore, let's break this down, here's what you need to know, without further ado
Fix: Start with the content.
> Before: "Let's explore how I led the integration…"
> After: "Led the integration of three business units…"

**29. Fragmented headers / filler openers**
Pattern: A heading or bullet opener followed by a generic sentence that restates it before the real content.
Fix: Remove the filler sentence; let the real content follow the opener directly.

### Communication Patterns

**20. Chatbot artifacts**
Phrases: I hope this helps, Of course!, Certainly!, Would you like, let me know, here is a…
Fix: Remove entirely.

**21. Knowledge-cutoff disclaimers**
Phrases: as of [date], up to my last training update, while specific details are limited
Fix: Remove. State facts or remove the claim.

**22. Sycophantic tone**
Phrases: Great question!, You're absolutely right!, That's an excellent point
Fix: Respond directly.

### Filler and Hedging

**23. Filler phrases**
- "In order to achieve" → "To achieve"
- "Due to the fact that" → "Because"
- "At this point in time" → "Now"
- "In the event that" → "If"
- "has the ability to" → "can"
- "It is important to note that" → remove

**24. Excessive hedging**
Fix: One hedge word maximum per claim.
> Before: "could potentially possibly be argued that… might have some"
> After: "may affect"

**25. Generic positive conclusions**
Phrases: the future looks bright, exciting times lie ahead, journey toward excellence, major step in the right direction
Fix: Specific facts or plans.
> Before: "I am excited to contribute to your journey toward excellence"
> After: "I want to apply the transaction experience from PwC directly to your M&A pipeline"

---

## Process

1. Read the full `.tex` file
2. Identify all text regions (bullets and cover letter paragraphs)
3. For each text region:
   a. Apply hard constraints filter first (mark anything that would change facts/structure as off-limits)
   b. Scan against all 29 patterns + job-application bans
   c. Rewrite only the flagged phrases; leave everything else identical
4. Do a final pass: "What still reads as obviously AI-generated?" — fix any remaining tells
5. **Cover-letter-specific checks (run after pattern pass):**
   a. **CGPA / grades**: Scan `\CLParagraph{}` blocks for any numeric grade (`CGPA`, `GPA`, `4.98`, `4,98`, any decimal score next to `/6` or `/4` or `/5`). Remove the numeric score entirely — keep only institution and degree name. Example: "My HSG MBA (CGPA 4.98/6.0, ranked #6 in Europe)" → "My HSG MBA (ranked #6 in Europe by FT 2021)".
   b. **Word count**: Count words inside all `\CLParagraph{}` blocks combined. If total > 360, trim the longest paragraph(s) by cutting generic or repeated observations until the total reaches ≤ 360. Never cut factual claims or the formal close. Report the trim count in `changes`.
6. Output the full `.tex` file with LaTeX structure intact and only text regions changed

---

## Output

Return the full file content (not just changed sections) with LaTeX structure identical to input and only prose text improved.

After writing the humanized `.tex` files, write `humanizer_report.json` to the same output folder:

```json
{
  "ran_at": "ISO-8601 timestamp",
  "documents": ["Raphael-Benyamine_CV.tex", "Raphael-Benyamine_cover-letter.tex"],
  "flags_found": <total count of patterns triggered across both documents>,
  "rewrites_applied": <total count of phrases actually rewritten>,
  "changes": [
    {
      "document": "Raphael-Benyamine_CV.tex",
      "pattern": "<pattern name from the 29-pattern list>",
      "before": "<original phrase>",
      "after": "<rewritten phrase>"
    }
  ],
  "summary": "<one sentence: how many flags, what was changed, any patterns with zero hits>"
}
```

If a document had no flags and no rewrites, still include it in `documents` with zero counts. Always write the file even if no changes were made — its presence confirms the humanizer ran.
