# Mode: rb/pipeline — Full Job Application Pipeline

## Purpose
Process a job posting end-to-end: classify → write CV + cover letter → humanize → compile LaTeX → verify → save package.

## Inputs
- Job URL or JD text (optional — if omitted, read queue from `career-ops/data/pipeline.md`)
- Override language (optional — auto-detected from JD if omitted)

---

## Step 0 — Resolve input

If a job URL or JD text was provided: use it. Go to Step 1.

If nothing was provided:
1. Read `career-ops/data/pipeline.md`
2. Extract all unchecked items (`- [ ]`) — these are the pending URLs
3. Display them exactly like career-ops pipeline does:

```
📋 Pending jobs in queue (career-ops/data/pipeline.md):

  1. Company Name — Role Title
     URL

  2. Company Name — Role Title
     URL
  ...

Which job would you like to process? Enter a number, or paste a URL/JD text directly.
```

4. Wait for user selection.
   - If the user enters a number: use the corresponding URL. Go to Step 1.
   - If the user pastes a URL or JD text: use that directly. Go to Step 1.
   - If the user says "all" or "process all": loop through each unchecked item sequentially, running Steps 1–9 for each, then mark each checkbox (`- [x]`) in pipeline.md when done.

After successfully completing the pipeline for a job, mark its checkbox in `career-ops/data/pipeline.md` as done: change `- [ ]` to `- [x]`.

---

## Step 1 — Generate cv.md if stale

```bash
node generate-cv-md.mjs
```

Stale = `profile_bank.json` file modification time is newer than `cv.md`, or `cv.md` is missing. The script checks this automatically and skips if up to date.

---

## Step 2 — Extract JD

Record the input URL now as `source_url` — before attempting any fetch. This value must appear in the classification regardless of whether the fetch succeeds or fails.

If URL provided: use Playwright (`browser_navigate` + `browser_snapshot`) first. Fall back to WebFetch. Fall back to WebSearch.

If text provided: `source_url` is null.

---

## Step 3 — Classify

Apply the classifier rules below to produce a classification object. This gates which profile_bank achievements get surfaced to the writer.

```json
{
  "source_url": "the input URL recorded in Step 2 — ALWAYS set this, even if the JD fetch failed",
  "company": "Company Name",
  "role_title": "Job Title",
  "classifications": ["strategy", "consulting"],
  "primary_function": "strategy | consulting | M&A | operations | engineering | finance | product | other",
  "sector": "luxury | manufacturing | industrial | tech | finance | consumer | healthcare | aviation | other",
  "seniority": "junior | mid | senior | lead | director | executive",
  "language": "en | fr | de",
  "swiss": true,
  "chopard_eligible": true,
  "confidence": "high | medium | low",
  "fit_grade": "A | B | C | D",
  "fit_rationale": "one sentence explaining the grade",
  "company_signals": {
    "name": "extracted company name or null",
    "size": "startup | scale-up | mid-market | large | enterprise | unknown",
    "location": "extracted location or null"
  }
}
```

### Classification taxonomy

`classifications` is a list (1-3 tags) drawn from this fixed set:
- `strategy` — strategic planning, corp dev, transformation
- `consulting` — advisory, project-based client work
- `M&A` — deals, due diligence, integration
- `luxury` — luxury goods/manufacturing context
- `manufacturing` — industrial production, plant operations
- `industrial` — heavy industry, B2B industrial
- `tech` — software, digital products
- `aviation` — aerospace, GA, airline ops
- `finance` — banking, PE, VC, treasury
- `operations` — ops management, supply chain, process
- `general` — fallback when no specific tag fits

Pick the smallest set that captures the role. A "Strategy Manager at LVMH" is `["strategy", "luxury"]`. An "M&A Senior Associate at PwC" is `["consulting", "M&A"]`. A "Plant Operations Director at a luxury watchmaker" is `["operations", "luxury", "manufacturing"]`.

### Language detection

`language` is the primary language of the JD body, not the company's home country. A Swiss German company posting in English gets `"en"`.

### Swiss detection

`swiss: true` when location contains any of:
Switzerland, Schweiz, Suisse, Svizzera, Zürich, Zurich, Geneva, Genève, Bern, Basel, Lausanne, Zug, Dietikon, Winterthur, St. Gallen, Schaffhausen, Lucerne, Luzern, Lugano, Thun, Biel, Bienne, Neuchâtel, Fribourg, Solothurn.

### Chopard eligibility

`chopard_eligible: true` when sector or classifications include: luxury, manufacturing, industrial, consumer goods, FMCG, watchmaking.

### Confidence

- `high`: clear sector + function + seniority signals
- `medium`: some ambiguity but classifiable
- `low`: very thin JD or genuinely unusual role

If `low`, surface the classification to the user for confirmation before drafting.

### Fit grade

Score how well this role matches Raphael's profile (PwC M&A/strategy, Rolex ops, financial modeling, Swiss/French/English):

- `A`: Strong fit — ≥3 profile strengths directly required; seniority matches; location compatible
- `B`: Good fit — 2 clear matches, minor gaps in sector or seniority
- `C`: Partial fit — 1 strong match; significant gaps or stretch on seniority/sector
- `D`: Weak fit — profile misalignment; role requires skills/background not in profile

`fit_rationale`: one sentence explaining the grade. Example: "Strong M&A + strategy match at senior level; Swiss location fits relocation plans."

---

## Step 3.5 — Create output folder and prepare context files

**Determine the output folder name** (sanitize: replace spaces with `-`, drop special chars except `-` and `_`):

```
output/{Company}/YYYYMMDD_{Company}_{Role}/
```

If the company name is unknown or null (recruiter-only posting), use the recruiter/job-board name + job reference instead:

```
output/{Recruiter}/YYYYMMDD_{Recruiter}_{JobRef}_{Role}/
```

Example (known company): `Novartis`, role `VP M&A Transactions`, date `2026-04-27` →
`output/Novartis/20260427_Novartis_VP-MA-Transactions/`

Example (unknown company): recruiter `Michael-Page`, ref `JN-052026-7010863`, role `International-Sales-Engineer`, date `2026-05-09` →
`output/Michael-Page/20260509_Michael-Page_JN-052026-7010863_International-Sales-Engineer/`

**Create the folder and write three context files the subagents will read:**

```bash
mkdir -p output/{folder}

# 1. Save JD text (subagents don't have access to this session's context)
cat > output/{folder}/jd.txt << 'JDEOF'
{full JD text verbatim}
JDEOF

# 2. Save classification JSON
cat > output/{folder}/classification.json << 'CLEOF'
{classification JSON}
CLEOF

# 3. Filter profile bank to job-relevant achievements
node profile-for-job.mjs output/{folder}/classification.json \
  > output/{folder}/profile-filtered.json
```

If `profile-for-job.mjs` fails or produces empty output, note the fallback in Step 9 and use `~/Claude-code/job-hunter-data/config/profile_bank.json` as the profile path in subsequent steps instead of `profile-filtered.json`.

---

## Step 4 — Write CV and cover letter (isolated subagents)

Select mode files based on classification:

```
swiss: true AND language: "de"  → modes/rb/de-ch/write-cv.md  +  modes/rb/de-ch/write-cl.md
otherwise                        → modes/rb/write-cv.md         +  modes/rb/write-cl.md
```

### Step 4a — Write CV

Read `{write-cv-mode-path}` to load the CV writer instructions into memory.

Call the Agent tool:
- `subagent_type`: `"general-purpose"`
- `description`: `"write CV — {Company} {Role}"`
- `prompt`: the full content of the write-cv mode file, followed by:

```
---
## Orchestrator context for this run

JD text is in: output/{folder}/jd.txt
Classification is in: output/{folder}/classification.json
Profile (filtered) is in: output/{folder}/profile-filtered.json
Output folder: output/{folder}
Today's date: {YYYY-MM-DD}

Write Raphael-Benyamine_CV.tex to the output folder.
```

Check: if the Agent returns an error or `output/{folder}/Raphael-Benyamine_CV.tex` is missing → report error, stop.

### Step 4b — Write cover letter

Read `{write-cl-mode-path}` to load the cover letter writer instructions into memory.

Call the Agent tool:
- `subagent_type`: `"general-purpose"`
- `description`: `"write cover letter — {Company} {Role}"`
- `prompt`: the full content of the write-cl mode file, followed by:

```
---
## Orchestrator context for this run

JD text is in: output/{folder}/jd.txt
Classification is in: output/{folder}/classification.json
Profile (filtered) is in: output/{folder}/profile-filtered.json
Output folder: output/{folder}
Today's date: {YYYY-MM-DD}

Write Raphael-Benyamine_cover-letter.tex to the output folder.
```

Check: if the Agent returns an error or `output/{folder}/Raphael-Benyamine_cover-letter.tex` is missing → report error, stop.

---

## Step 5 — Humanize (isolated subagent)

Read `modes/rb/humanize.md` to load the humanizer instructions into memory.

Call the Agent tool:
- `subagent_type`: `"general-purpose"`
- `description`: `"humanize — {Company} {Role}"`
- `prompt`: the full content of `modes/rb/humanize.md`, followed by:

```
---
## Orchestrator context for this run

CV: output/{folder}/Raphael-Benyamine_CV.tex
Cover letter: output/{folder}/Raphael-Benyamine_cover-letter.tex
Language: {en|fr|de} (from classification)

Rewrite bullet text in Raphael-Benyamine_CV.tex and paragraph text in Raphael-Benyamine_cover-letter.tex in-place.
```

Check: if the Agent returns an error, warn user and ask whether to proceed. If both files are unchanged after the call (compare mtime before and after), warn — possible silent failure.

---

## Step 5.5 — LaTeX lint (cover letter)

Run these four checks before compiling. If **any** check produces output, report the findings, **stop**, and ask the user to fix before proceeding to Step 6.

```bash
CL="output/{folder}/Raphael-Benyamine_cover-letter.tex"

echo "--- [1] Connector dashes ---"
# Catches both "word -- word" and line-end "word --" (the humanizer misses line-end ones)
grep -n " --" "$CL" \
  | grep -v "^[0-9]*:[ ]*%" \
  | grep -v "\\\\newcommand" \
  | grep -v "[0-9]--[0-9]" \
  | grep -v "~'[0-9][0-9] --" \
  || echo "(none)"

echo "--- [2] CGPA / numeric grade ---"
grep -n "CGPA\|GPA\|[0-9]\.[0-9][0-9]/[0-9]" "$CL" \
  | grep -v "^[0-9]*:[ ]*%" \
  || echo "(none)"

echo "--- [3] Unescaped ampersands ---"
grep -n "&" "$CL" \
  | grep -v "^[0-9]*:[ ]*%" \
  | grep -v "\\\\&\|href{" \
  || echo "(none)"

echo "--- [4] Word count ---"
WORDS=$(awk '/AI-FILL-START/,/AI-FILL-END/' "$CL" \
  | grep -v '^%%\|\\CLParagraph\|^}$\|^$\|AI-FILL' \
  | sed 's/\\[a-zA-Z]*{[^}]*}//g; s/\\[a-zA-Z]*//g; s/[{}\\]//g' \
  | wc -w | tr -d ' ')
echo "$WORDS words (limit: 360)"
[ "$WORDS" -gt 360 ] && echo "OVER LIMIT — trim required" || echo "OK"
```

Fix criteria:
- Check 1: any `--` hit that is not a numeric/date range → **fix before compile**
- Check 2: any CGPA/GPA or decimal grade → **remove score, keep ranking**
- Check 3: any unescaped `&` in body text → **escape as `\&`**
- Check 4: > 360 words → **trim least-specific sentences until ≤ 360**

---

## Step 6 — Compile LaTeX

```bash
node generate-latex-rb.mjs output/{folder}/Raphael-Benyamine_CV.tex output/{folder}/Raphael-Benyamine_CV.pdf [--swiss-german if swiss:true]
node generate-latex-rb.mjs output/{folder}/Raphael-Benyamine_cover-letter.tex output/{folder}/Raphael-Benyamine_cover-letter.pdf [--swiss-german if swiss:true]
```

If compilation fails: report errors and stop. Do NOT proceed to verify.

Review the JSON output from each compilation call:
- `pageCount` > 1 for Raphael-Benyamine_CV.pdf → alert user (CV must be single page, trim bullets)
- `pageCount` > 1 for Raphael-Benyamine_cover-letter.pdf → alert user (trim)
- `warnings` array non-empty → report each warning to the user immediately (e.g. missing photo file)

---

## Step 7 — Verify (isolated subagent)

Read `modes/rb/verify.md` to load the verifier instructions into memory.

Call the Agent tool:
- `subagent_type`: `"general-purpose"`
- `description`: `"verify — {Company} {Role}"`
- `prompt`: the full content of `modes/rb/verify.md`, followed by:

```
---
## Orchestrator context for this run

Profile (filtered): output/{folder}/profile-filtered.json
CV: output/{folder}/Raphael-Benyamine_CV.tex
Cover letter: output/{folder}/Raphael-Benyamine_cover-letter.tex
JD text: output/{folder}/jd.txt

Write the verdict to output/{folder}/verifier_report.json.
```

Check: if the Agent returns an error or `output/{folder}/verifier_report.json` is missing → treat as fail, stop.

If verdict is `fail`: report blockers to user. **Stop** — do NOT mark as ready.
If verdict is `pass` or `pass_with_warnings`: continue.

---

## Step 9 — Summary

Report to user:
- Output folder path
- Verifier verdict + any warnings
- PDF paths and page counts
- Any standing rules triggered (Chopard included/excluded, Swiss orthography applied, etc.)
- If `pass_with_warnings`: list warnings so user can decide whether to fix manually

**Parallel upgrade reminder:** Count the number of `Applied` entries in `career-ops/data/applications.md` that were generated after Fix #3 went live (Step 3.5 present, i.e. after 2026-05-04). When that count reaches 10 and this run has no verifier failures, append to the summary:

> "10 clean runs since the subagent refactor. Ready to enable parallel write-cv/write-cl? See: docs/superpowers/specs/2026-05-04-fix3-isolated-subagents-design.md — Parallel Upgrade Plan section."

---

## Liveness check (optional)

Before Step 4, optionally run career-ops liveness check if a job URL was provided:

```bash
node career-ops/check-liveness.mjs {job_url}
```

If liveness returns `dead`: warn user and ask whether to proceed. If the user says no, stop. If yes, proceed with the JD text already extracted.

---

## Output folder structure

```
output/Company/YYYYMMDD_Company_Role/
├── jd.txt                  ← saved in Step 3.5, consumed by all subagents
├── classification.json     ← saved in Step 3.5
├── profile-filtered.json   ← generated in Step 3.5 by profile-for-job.mjs
├── Raphael-Benyamine_CV.tex                  ← written by write-cv subagent (Step 4a)
├── Raphael-Benyamine_CV.pdf                  ← compiled in Step 6
├── Raphael-Benyamine_cover-letter.tex        ← written by write-cl subagent (Step 4b)
├── Raphael-Benyamine_cover-letter.pdf        ← compiled in Step 6
└── verifier_report.json    ← written by verify subagent (Step 7)
```

`cv.md` is in the repo root (build artifact, gitignored). Never put `cv.md` in the output folder.
