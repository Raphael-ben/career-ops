# Mode: pro/write-cl — Cover Letter Writer

## Purpose
Generate a filled LaTeX cover letter tailored to a specific job description. Reads the profile bank and the candidate's cover-letter template, produces a filled `{file_slug}_cover-letter.tex` (`{file_slug}` = `profile_bank.candidate.file_slug`) in the output folder. Every placeholder is filled — no `%%FILL:` markers remain.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). Read it once; every candidate-specific value below comes from it.

## Inputs required before starting
- Job description text
- Classification output: `role_type`, `industry`, `seniority`, `language` (en/fr/de), `swiss` (true/false)
- Profile bank path (see Resolution)
- Cover-letter template + fill-spec: the candidate's `.tex` template and `cl-fill-spec.md` in `{DATA_DIR}/templates/`
- Output folder path
- Today's date (YYYY-MM-DD)

## Process

### Step 1 — Load inputs

Read `{output_folder}/profile-filtered.json` (pre-filtered profile; if missing, read the full profile bank). Read `{DATA_DIR}/templates/cl-fill-spec.md` for LaTeX syntax reference and the candidate's cover-letter `.tex` template to copy its preamble verbatim. All fill conventions are already in this mode file.

### Step 2 — Determine language and orthography

Language = classification's `language` field (en/fr/de). Write the entire letter in this language.

Swiss orthography: if `swiss: true`, use `ss` instead of `ß` throughout the entire letter body, including the greeting line. The compile script applies a second pass, but the mode output must already be clean.

### Step 3 — Determine availability

From `profile_bank.rules.tense.departure_date`, derive the availability phrase in the letter's language (e.g. DE "ab {Monat} {Jahr}", EN "from {Month} {Year}", FR "à partir de {mois} {année}"). State it as a simple fact only if the JD asks for a start date; otherwise omit availability entirely. Never write a placeholder like "[Datum]".

### Step 4 — Compose six paragraphs

**`profile_bank.verify.tolerances.cover_letter_min_words`–`cover_letter_max_words` words total across all six paragraphs.** Each paragraph does exactly one job. No filler. All factual claims are drawn from `profile_bank.experience` / `education`; the specific role and company references below come from the profile bank, never invented.

---

**Paragraph 1 — Application statement + profile formula + hook** (3-4 sentences)

State the position and company directly. Name the candidate's 2-3 most relevant domains as a simple list — never use an "at the intersection of" construction in any language (see `profile_bank.humanize.banned_phrases` / `banned_phrases_de` / `banned_phrases_fr`). If there is a genuine, specific reason the candidate would be interested in this company (a real industry connection, a sector they know), add one sentence. If no specific reason exists, omit it.

Do NOT start with the company name. Do NOT describe the company's market situation or challenges. The opening is about the candidate.

---

**Paragraph 2 — Current / most recent primary role, mapped to the JD** (3-4 sentences)

Name role and company (from `profile_bank.experience`). Describe what the candidate does in concrete terms — 2-3 specific activities from the profile bank. End with an explicit mapping sentence naming actual JD requirements (fold the JD requirements into a clean sentence; do not use a banned connector phrase).

Do not say "transferable experience" — name what it transfers to. **Tense:** apply `profile_bank.rules.tense` — a role whose `end_status` is `current_indefinite`/`contract_ending` (and end on/after today) is present tense; never place it in a past or subordinate-past clause ("Before I moved to…", "During my time at…" as past). A completed role is past tense.

---

**Paragraph 3 — Prior relevant role** (3 sentences)

Transition to the most relevant prior experience. State what the candidate did — 2-3 concrete verbs. Close with what this built — state the competency directly as a fact, not as a self-assessment, and without a formulaic "This experience strengthened my ability to…" opener (banned in every language).

---

**Paragraph 4 — Education + specific motivation** (2-3 sentences)

One sentence on education (name institutions/degrees from `profile_bank.education`). Then state specifically why this company or role is interesting to the candidate — tied to a real characteristic (sector, technology, culture, market position). This is the only paragraph where naming something about the company is acceptable, because it explains motivation.

---

**Paragraph 5 — Values alignment + desire to contribute** (2 sentences)

Name ONE specific, verifiable characteristic of this company — something concrete from the JD, its public positioning, or its sector context (not a generic "quality and client focus"). Do NOT use a generic rule-of-three. State why the candidate wants to contribute to that specifically. Brief — this is a close, not an analysis.

---

**Paragraph 6 — Formal close** (1-2 sentences)

Language-matched, offering an interview at the reader's convenience (DE / EN / FR as appropriate). If a start date applies, add the availability sentence before the formal close.

---

### Step 5 — Resolve company address (mandatory before filling template)

Read `profile_bank.rules.address_lookup`. **Do not guess. Do not use partial values. Execute the lookups below in order and stop at the first that returns a street + zip.**

**5a — Extract from JD (free, always try first).** Scan the JD text for a full address (street number + zip + city). If found, use it. Skip 5b–5d.

**5b–5d — Registry lookups, in the order given by `address_lookup.registry_domains`.** For each domain in that array, call `WebSearch` with `"{Company name}" site:{domain}`, open the matching result, and extract the registered street + zip. Stop at the first that returns a street. If the registry array is exhausted, try `"{Company name}" impressum OR contact address` and read the Impressum/Contact page.

**If all lookups fail to return a street:**
- Leave `\CLCompanyStreet{}` empty.
- Set `\CLCompanyCity` to `{ZIP} {City}, {Country}` using the city-centre code from `address_lookup.city_centre_zips[<city>]`.
- **The zip is mandatory** if `address_lookup.zip_mandatory` is true — never leave it blank.

---

### Step 6 — Fill the template

Filling conventions from the template's fill-spec:

**User variables** — fill via `\newcommand` blocks:
```latex
\newcommand{\CLDate}{<today, language-matched format>}
\newcommand{\CLCompanyName}{Company Name}
\newcommand{\CLCompanyStreet}{Street}                 % from Step 5
\newcommand{\CLCompanyCity}{ZIP City, Country}        % from Step 5 — zip mandatory
\newcommand{\CLSubject}{Application for [Role Title]}  % language-matched
\newcommand{\CLSalutation}{Dear Sir or Madam,}         % language-matched, never "Dear Hiring Manager"
\newcommand{\CLClosing}{}                               % ALWAYS empty string
```

**Date format**: EN uses an ordinal suffix ("April 26\textsuperscript{th} 2026"); DE "26. April 2026"; FR "26 avril 2026".

**Subject line** — language-matched, no em dashes (EN "Application for …"; DE "Bewerbung als … (m/w/d)" with gender marker if in the JD; FR "Candidature au poste de …").

**Salutation** — never "Dear Hiring Manager"/"Dear Hiring Team": EN "Dear Sir or Madam,"; DE "Sehr geehrte Damen und Herren," or a named recruiter if the JD gives one; FR "Madame, Monsieur,".

**`\CLClosing`**: ALWAYS empty string. The template prints name + contact automatically.

**`\CLGreeting`** (valediction) — by language + Swiss flag: EN "Yours sincerely,"; DE + `swiss:true` "Mit freundlichen Grüssen," (ss); DE + `swiss:false` "Mit freundlichen Grüßen,"; FR "Veuillez agréer l'expression de mes salutations distinguées,".

**Body paragraphs** — replace the `%% AI-FILL-START` … `%% AI-FILL-END` region with one `\CLParagraph{}` per paragraph. Never insert `\vspace`, `\\`, or `\par` inside a block. No blank lines between consecutive `\CLParagraph` calls. Escape `\&`, `\%`, `\_`, `\#`, `\$`; accented chars via LaTeX escapes.

### Step 7 — Write output

Write the filled `{file_slug}_cover-letter.tex` to `{output_folder}/{file_slug}_cover-letter.tex`.

## Hard rules — violations cause verifier to fail

1. **Source-bound claims.** Every factual claim maps to an experience/achievement id in the profile bank.
2. **Never use banned terms** (`profile_bank.rules.never_mention`).
3. **Apply conditional mentions and framing rules** (`profile_bank.rules.conditional_mentions`, `profile_bank.rules.framing` entries with `cover_letter` in `enforce_on`).
4. **Tense** per `profile_bank.rules.tense` — no past framing of a still-current role.
5. **No invented metrics.** No numbers not in the profile bank.
6. **No inferred sector specifics.**
7. **No university grades in the cover letter** if `profile_bank.rules.education_display.cgpa_never_in_cover_letter` is true. Never state CGPA/GPA/grade averages — not even parenthetically. Name education by institution and degree (and ranking if useful), never by grade.
8. **Every argument must directly support this application.** Cut anything that does not strengthen the case for this role at this company.
9. **Language.** Write in the JD's language. No switching mid-letter.
10. **`\CLClosing` is always empty string.**
11. **No dashes as clause connectors.** Never use `—` (em dash) or LaTeX `--` to connect prose phrases. Use commas, colons, or two sentences. Exception: `--` is fine for numeric ranges and date ranges.
12. **`cover_letter_min_words`–`cover_letter_max_words` words total** (`profile_bank.verify.tolerances`). Count words inside all `\CLParagraph{}` blocks before writing. If over the max, trim the least specific sentences first.
13. **Never devalue the profile.** No "without hierarchical power", no "the project wasn't complex".

## Banned phrases

Read `profile_bank.humanize.banned_phrases` (English), `banned_phrases_de`, and `banned_phrases_fr` — none may appear in the letter. In addition, avoid these genuine AI tells in any language: any sentence beginning with the company name that analyzes their business situation; a filler "dynamic" adjective (`banned_words` / `banned_words_de` / `banned_words_fr`); a generic "I am convinced I am the ideal candidate" construction; a generic "I look forward to hearing from you" in place of the Paragraph 6 formal close.
