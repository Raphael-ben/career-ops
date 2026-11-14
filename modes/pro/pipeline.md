# Mode: pro/pipeline — Full Job Application Pipeline

## Purpose
Process a job posting end-to-end: classify → write CV + cover letter → humanize → compile LaTeX → verify → save package.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** (`{profile_bank}` in commands below) is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). `{file_slug}` = `profile_bank.candidate.file_slug` — all generated artefacts use it (`{file_slug}_CV.tex`, `{file_slug}_cover-letter.tex`, and PDFs).

## Inputs
- Job URL or JD text (optional — if omitted, read queue from `career-ops/data/pipeline.md`)
- Override language (optional — auto-detected from JD if omitted)

---

## Step 0 — Resolve input

If a job URL or JD text was provided: use it. Go to Step 1.

If nothing was provided: default scope is the **entire queue** — every `- [ ]` entry in `career-ops/data/pipeline.md`. Go to Step 0.5.

**Unseen launchd scan blocks first.** If `data/pipeline.md` holds a scan block written by the weekly launchd scan that has not yet been shown to the user, run the pre-assessment glyph pass from `modes/pro/scan.md` Phase 3 on it before triage (that text is owned by scan.md; do not restate it here).

`scan_aggregate.py`'s reaper runs at the start of every scan and closes (`- [ ]` → `- [x] ... EXPIRED`) entries older than `config/profile.yml` `scan.pipeline_max_age_days` (default 45), so this queue stays bounded to recent inflow instead of growing forever — its counts (`reaped=N undatable=M open_remaining=K`) print in the scan summary, worth a glance before a full triage run.

After successfully completing the pipeline for a job, mark its checkbox in `career-ops/data/pipeline.md` as done: `- [ ]` → `- [x]`.

---

## Step 0.5 — Triage pending entries

**Runs whenever Step 0 falls through to the full queue** (no URL/JD text/single entry was given directly) — this is now the default path, not an opt-in. Skip entirely when the user handed over a specific URL, JD text, or a single entry to process.

Before recommending any `pass`/`borderline` entry onward, cross-check it against the Notion JOB OP database per the Notion-first already-applied rule in `modes/_custom.md` — `data/applications.md` and scan-history dedup alone can lag the tracker.

### Read triage preferences

Read `career-ops/config/profile.yml`. Extract `triage.preferences`. If the `triage:` block is missing, stop and show:

```
Triage is not configured. Please add a triage: block to career-ops/config/profile.yml.

Minimum required:
  triage:
    model: claude-haiku-4-5
    borderline_bucket: true
    preferences: |
      Describe your target roles here. The LLM uses this to score each job.

After adding the block, re-run /jobhunter pipeline with no URL/JD to triage the full queue.
```

### Parse pending entries

From the `- [ ]` entries in Step 0, extract `{url}`, `{title}`, `{company}`. Line format in `data/pipeline.md`:

```
- [ ] {url} | {company} | {title}
```

Strip the leading `- [ ] `, split on ` | ` — field 0 url, 1 company, 2 title. If no ` | `, use the raw line as `title`, `"unknown"` company, `""` url. Build an indexed list.

**Applicant count.** If the row carries ` · applicants: N` (written by `scan_aggregate.py` only when the source reported a number), keep `applicants = N` with the entry and append `(applicants: N)` after `{company}` in the triage prompt line. Absent → `applicants = null`. Never estimate it. Triage uses it only as a tie-breaker between `pass` and `borderline` (see Step 3 fit grade: <25 is a plus, >200 is crowded).

**`⚑ RESCUED` entries jump to the front.** If a title field starts with `⚑ RESCUED ` (a human pre-assessed it as a strong fit during a reaper backlog sweep — see `scan_aggregate.py`), move it to the front of the indexed list ahead of everything else before batching, so it lands in the first triage batch.

### Score entries (batches of ~40)

For each batch of up to 40, call the Agent tool with `subagent_type: "general-purpose"`, `model: "haiku"`, `description: "triage batch {start}–{end} of {total}"`, and prompt:

```
You are a job relevance screener for a specific candidate. Score each job below.

Candidate preferences:
{value of triage.preferences from config/profile.yml — paste verbatim}

For each job output EXACTLY one line in this format (no preamble, no extra text):
<index> | <verdict> | <one-line reason>

Verdicts:
- pass       — clear match with candidate profile
- borderline — plausible but uncertain (wrong company size, adjacent title, sector mismatch)
- skip       — clearly irrelevant

Tie-breaker only: a job shown with "(applicants: N)" where N < 25 may move borderline → pass;
N > 200 (crowded) may move pass → borderline. It never turns a skip into anything else.

Jobs:
1. {title} — {company}
2. {title} — {company}
...
```

Parse each line: `index` (int), `verdict` (`pass`/`borderline`/`skip`), `reason`. Unparseable line → `borderline` / `"parse error"`.

### Route entries

**pass** → stays as `- [ ]` in `data/pipeline.md`. No change. Processed in Steps 1–9.

**borderline** → move from the `- [ ]` section to a `## Borderline` section at the bottom. Create if missing:

```markdown
## Borderline

- [?] {Company} — {Role}
     {url}
     Triage: {reason}
```

Separate each `- [?]` from the previous with a blank line.

**skip** → remove the `- [ ]` entry. Append one TSV line to `data/scan-history.tsv` (write the header first only if creating the file):

```
url	first_seen	portal	title	company	status
```
```
{url}	{YYYY-MM-DD}	triage	{title}	{company}	skipped_triage
```

(Tab-separated. `url` empty string if unavailable. `portal` = `triage`. `status` = `skipped_triage`.)

### Display triage summary

```
Triage complete — {total} pending entries scored:
  ✓ {pass_count} pass  (will process)
  ~ {borderline_count} borderline  (review at end)
  ✗ {skip_count} skip

Processing {pass_count} offers...
```

If `pass_count` is 0, show the "0 offers passed" message and stop (do NOT proceed to Steps 1–9 or 10.5).

### Process pass entries

For each `pass` entry, run Steps 1–9 sequentially. After each, mark its checkbox `- [x]`.

---

## Step 1 — Load the profile bank and compute years of experience

The pipeline reads `profile_bank.json` directly (see Resolution); there is no `cv.md` build step. The repo-root `cv.md` is NOT a source for this pipeline and may be stale, which is why Step 6 skips upstream's cv.md-based fact gate and verify Step 0 points `verify-cv-facts.mjs` at the bank instead.

Compute the candidate's experience duration from the bank, once per run (sum of employed periods; roles are non-contiguous, so first-job-to-today is wrong; `end: null` = today; month granularity, rounded down, so it never overstates):

```bash
{PYTHON} - {profile_bank} <<'PY'
import json, sys, datetime as d
b = json.load(open(sys.argv[1])); t = d.date.today()
m = lambda s: int(s[:4]) * 12 + int(s[5:7]) if s else t.year * 12 + t.month
months = sum(m(e.get('end')) - m(e['start']) for e in b['experience'])
print(f"years_experience={months // 12} (employed months={months})")
PY
```

Keep `years_experience` for this run. It is the ONLY duration figure anyone may use: Step 3 compares it against a JD's years threshold, Step 3.5 writes it to `computed-facts.txt`, and Step 4 pastes it into both writer prompts. Never state or brief a duration from impression.

---

## Step 2 — Extract JD

Record the input URL now as `source_url` — before any fetch. This value must appear in the classification regardless of fetch success.

If URL provided: fetch browserless — `{PYTHON} -c "from scrapling.fetchers import Fetcher; print(Fetcher().get('URL', impersonate='chrome').get_all_text())"` (the resolved `{PYTHON}` must have curl_cffi). Or the `scrapling` MCP `get` tool. Fall back to WebFetch, then WebSearch. NEVER Playwright here (see `modes/_custom.md` — browser automation is apply-flow only).

If text provided: `source_url` is null.

**Never stage the fetched JD under a shared/generic temp path** (e.g. a fixed `jd.txt` in the session scratchpad). Parallel pipeline runs share that directory, and a concurrent run will silently overwrite it between your write and your read — you then classify and write a CV against another job's JD. Keep the JD in context until Step 3.5 creates the output folder and write it straight to `output/{folder}/jd.txt`; if you must spill to disk first, make the filename unique to this run (include the company slug).

---

## Step 3 — Classify

Apply the classifier rules below to produce a classification object. This gates which profile-bank achievements get surfaced to the writer.

```json
{
  "source_url": "the input URL from Step 2 — ALWAYS set, even if the fetch failed",
  "company": "Company Name",
  "role_title": "Job Title",
  "classifications": ["strategy", "consulting"],
  "primary_function": "strategy | consulting | M&A | operations | engineering | finance | product | other",
  "sector": "luxury | manufacturing | industrial | tech | finance | consumer | healthcare | aviation | other",
  "seniority": "junior | mid | senior | lead | director | executive",
  "language": "en | fr | de",
  "swiss": true,
  "conditional_flags": { "<conditional_mentions entity>": true },
  "confidence": "high | medium | low",
  "fit_grade": "A | B | C | D",
  "fit_rationale": "one sentence explaining the grade",
  "applicants": "integer from the pipeline row or JD, else null — never estimated",
  "company_signals": { "name": "…or null", "size": "startup | scale-up | mid-market | large | enterprise | unknown", "location": "…or null" }
}
```

### Classification taxonomy

`classifications` is a list (1-3 tags) from this fixed market-geography set (person-agnostic):
`strategy`, `consulting`, `M&A`, `luxury`, `manufacturing`, `industrial`, `tech`, `aviation`, `finance`, `operations`, `general`.

Pick the smallest set that captures the role. A "Strategy Manager at a fashion group" is `["strategy", "luxury"]`; a "Post-Merger Integration Lead at a bank" is `["M&A", "finance"]`; a "Plant Operations Director at a turbine maker" is `["operations", "industrial", "manufacturing"]`.

### Language detection

`language` is the primary language of the JD body, not the company's home country. A Swiss-German company posting in English gets `"en"`.

### Swiss detection

`swiss: true` when location contains any of: Switzerland, Schweiz, Suisse, Svizzera, Zürich, Zurich, Geneva, Genève, Bern, Basel, Lausanne, Zug, Dietikon, Winterthur, St. Gallen, Schaffhausen, Lucerne, Luzern, Lugano, Thun, Biel, Bienne, Neuchâtel, Fribourg, Solothurn.

### Conditional-inclusion flags

For each entry in `profile_bank.rules.conditional_mentions`, set `conditional_flags[<entity>] = true` when the JD's sector/classifications satisfy that entity's `surface_only_when`. These flags drive the writer's conditional blocks (e.g. a luxury/manufacturing-only experience block). Do NOT hardcode entity names here — read them from the profile bank.

### Confidence

`high`: clear sector + function + seniority. `medium`: some ambiguity but classifiable. `low`: very thin or unusual JD — surface the classification to the user for confirmation before drafting.

### Fit grade

Score how well this role matches the candidate's profile. Read the candidate's strengths from `config/profile.yml` (`target_roles`, `narrative`) and `profile_bank.experience`; do not hardcode a person's background here.

- `A`: strong fit — ≥3 profile strengths directly required; seniority matches; location compatible
- `B`: good fit — 2 clear matches, minor gaps in sector or seniority
- `C`: partial fit — 1 strong match; significant gaps or stretch
- `D`: weak fit — profile misalignment

`fit_rationale`: one sentence explaining the grade.

**Years threshold.** If the JD states a minimum years of experience, compare it to `years_experience` from Step 1, never to an impression.

**Applicant count (tie-breaker only).** `applicants` = the integer from the pipeline row (` · applicants: N`) or a count stated in the JD/posting page; otherwise `null`. Never infer or invent it. When the grade sits between two letters, `applicants < 25` is a plus (round up) and `applicants > 200` means crowded (round down); mention it in `fit_rationale` when it decided the grade. It never moves a grade by more than one letter and never overrides a location/seniority mismatch.

---

## Step 3.5 — Create output folder and prepare context files

**Output folder name** (sanitize: spaces → `-`, drop special chars except `-`/`_`):

```
output/{Company}/YYYYMMDD_{Company}_{Role}/
```

If company is unknown/null (recruiter-only posting), use the recruiter/job-board name + job reference:

```
output/{Recruiter}/YYYYMMDD_{Recruiter}_{JobRef}_{Role}/
```

**Create the folder and write three context files the subagents will read:**

```bash
mkdir -p output/{folder}

# 1. Save JD text
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

# 4. Orchestrator-computed facts (extra evidence for the verify Step 0 fact gate)
echo "years_experience: {years_experience} years of professional experience" \
  > output/{folder}/computed-facts.txt
```

`computed-facts.txt` holds only figures computed from the bank in Step 1, so a writer that states "{years_experience} years" passes `verify-cv-facts.mjs` while any other duration fails it. Never write anything from the JD into it.

If `profile-for-job.mjs` fails or produces empty output, note the fallback in Step 9 and use the full profile bank (`{DATA_DIR}/config/profile_bank.json`, fallback repo `config/profile_bank.json`) in subsequent steps instead of `profile-filtered.json`.

Then check every `always_include: true` experience block in `profile-filtered.json` has a non-empty achievement list (the `surface_in` filter can empty one). If one is empty, restore that block's achievements unfiltered from the bank and tell the writer and verifier why; otherwise the writer must render a bullet with no source.

---

## Step 4 — Write CV and cover letter (isolated subagents)

Always use `modes/pro/write-cv.md` + `modes/pro/write-cl.md`. Swiss orthography (`swiss:true` → `ss`) and cover-letter language (`de/fr/en`) come from the classification fields passed in context.

### Step 4a — Write CV

Read `modes/pro/write-cv.md` to load the CV writer into memory. Call the Agent tool with `subagent_type: "general-purpose"`, `description: "write CV — {Company} {Role}"`, and `prompt` = the full mode-file content followed by:

```
---
## Orchestrator context for this run

JD text is in: output/{folder}/jd.txt
Classification is in: output/{folder}/classification.json
Profile (filtered) is in: output/{folder}/profile-filtered.json
Output folder: output/{folder}
Today's date: {YYYY-MM-DD}
years_experience (computed in pipeline Step 1, the only duration you may state): {years_experience}

Write {file_slug}_CV.tex to the output folder.
```

**Writer briefing rule.** Add to this context block only file paths, the computed `years_experience`, achievement ids, and explicitly stated gaps. Never a list of JD phrases to "mirror" or "honest overlaps" worded in the JD's vocabulary: the writer reads that as approved wording and the verifier then fails it as unsupported JD echo. Point at an overlap by id ("`<ach_id>` backs the X angle"), never as a ready-made phrase.

Check: if the Agent errors or `output/{folder}/{file_slug}_CV.tex` is missing → report error, stop.

### Step 4b — Write cover letter

Same pattern with `modes/pro/write-cl.md`, `description: "write cover letter — {Company} {Role}"`, writing `{file_slug}_cover-letter.tex`, same context block (including `years_experience`) and same briefing rule. Check for the file; error → stop.

---

## Step 5 — Humanize (isolated subagent)

This step is NEVER optional or skippable — verify Step 0 hard-fails without its report.

Read `modes/pro/humanize.md`. Call the Agent tool with `subagent_type: "general-purpose"`, `description: "humanize — {Company} {Role}"`, `prompt` = the full mode-file content followed by:

```
---
## Orchestrator context for this run

CV: output/{folder}/{file_slug}_CV.tex
Cover letter: output/{folder}/{file_slug}_cover-letter.tex
Language: {en|fr|de} (from classification)

Rewrite bullet text in the CV and paragraph text in the cover letter in-place.
```

Check: if the Agent errors, warn and ask whether to proceed. If both files are unchanged (compare mtime before/after), warn — possible silent failure.

---

## Step 5.5 — LaTeX lint (CV + cover letter)

Run these checks before compiling. If **any** produces output (or `check-humanized.mjs` exits 1), report, **stop**, and ask the user to fix before Step 6. A fix edits the `.tex`, so it must go back through Step 5 (humanize regenerates the report) before this lint can pass again.

```bash
CV="output/{folder}/{file_slug}_CV.tex"
CL="output/{folder}/{file_slug}_cover-letter.tex"

echo "--- [0] Wording, dashes, stale humanizer report (both files) ---"
node check-humanized.mjs {profile_bank} "$CV" "$CL"
```

`check-humanized.mjs` wraps upstream `cv-voice.mjs` (which has no CLI of its own: `node cv-voice.mjs <tex>` prints nothing and exits 0, so never call it directly as a gate). Per file it fails on: a cv-voice stock phrase or any bare (unqualified) entry of `profile_bank.humanize.banned_words` / `_de` / `_fr` / `banned_bullet_openers` that the bank's own content does not contain; a Unicode em/en dash outside a date range; and `humanizer_report.json` missing or older than the `.tex` (the .tex was edited after humanize). Numbers are left to the verify Step 0 fact gate.

```bash
echo "--- [1] Connector dashes (CL body + CV bullets; stored titles/sidebar labels keep their --) ---"
{ grep -n " --" "$CL"; grep -n " --" "$CV" | grep "\\\\item"; } \
  | grep -v "^[0-9]*:[ ]*%" \
  | grep -v "\\\\newcommand" \
  | grep -v "[0-9]--[0-9]" \
  | grep -v "~'[0-9][0-9] --" \
  || echo "(none)"

echo "--- [5] Swiss orthography (only if classification.swiss is true) ---"
grep -n "ß" "$CV" "$CL" || echo "(none)"

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
echo "$WORDS words (limit: profile_bank.verify.tolerances.cover_letter_max_words)"
```

Fix criteria: Check 0 — reword the flagged phrase / replace the dash (then re-humanize), or re-run Step 5 if only the report is stale. Check 1 — any `--` not a numeric/date range → fix before compile. Check 5 — any `ß` when `swiss: true` → `ss` (this replaces the old compile-time ß→ss rewrite; nothing rewrites text at compile time any more). Check 2 — any CGPA/GPA or decimal grade (only if `education_display.cgpa_never_in_cover_letter`) → remove score, keep ranking. Check 3 — unescaped `&` → escape as `\&`. Check 4 — over `cover_letter_max_words` → trim least-specific sentences.

---

## Step 6 — Compile LaTeX

```bash
node generate-latex.mjs output/{folder}/{file_slug}_CV.tex output/{folder}/{file_slug}_CV.pdf --compile-only --skip-fact-check
node generate-latex.mjs output/{folder}/{file_slug}_cover-letter.tex output/{folder}/{file_slug}_cover-letter.pdf --compile-only --skip-fact-check
```

- `--compile-only`: the pro templates are not upstream's `cv-template.tex`, so upstream's structure validator would reject them; this flag compiles any user-owned `.tex`.
- `--skip-fact-check`, deliberately: upstream's built-in gate reads `cv.md` + `article-digest.md` from the data root, and this pipeline has no maintained `cv.md` (Step 1). Running it would check against a stale file, or skip silently when none exists. The fact gate runs instead in verify Step 0 with the right sources (`verify-cv-facts.mjs --source {profile_bank} --source computed-facts.txt`), as a blocker.
- No text normalising happens at compile time. Em/en dashes and stock wording are caught by Step 5.5 Check 0, connector `--` by Check 1, `ß` by Check 5, and curly quotes by humanize pattern 19; the old compile-time silent rewrite script is gone.
- Engine: `generate-latex.mjs` prefers tectonic when installed, else pdflatex (current machine: pdflatex). If tectonic appears and the pro template renders differently, `cv_fitcheck.py` still gates the result.

If compilation fails (`"compiled": false` in the JSON, exit 1): report `compileError` and stop. Do NOT proceed to verify. Page fit is not judged here: `cv_fitcheck.py` in verify Step 0 is the only page-fit gate.

---

## Step 7 — Verify (isolated subagent)

Read `modes/pro/verify.md`. Call the Agent tool with `subagent_type: "general-purpose"`, `description: "verify — {Company} {Role}"`, `prompt` = the full mode-file content followed by:

```
---
## Orchestrator context for this run

Profile (filtered): output/{folder}/profile-filtered.json
Profile bank: {profile_bank}
Computed facts: output/{folder}/computed-facts.txt
CV: output/{folder}/{file_slug}_CV.tex
Cover letter: output/{folder}/{file_slug}_cover-letter.tex
JD text: output/{folder}/jd.txt

Write the verdict to output/{folder}/verifier_report.json.
```

Note: verify.md Step 0 (the mechanical gates: cv_fitcheck, check-humanized, verify-cv-facts) runs with shell access before the sterile audit. Check: if the Agent errors or `verifier_report.json` is missing → treat as fail, stop. `fail` → run the verify.md **Fix loop** (writer fixes only the flagged sentences → Step 5 re-humanize → Step 5.5 → Step 6 → Step 7 again), max 3 verify rounds in total; after round 3 still `fail`, **stop**, report the remaining blockers, do NOT mark ready. `pass` / `pass_with_warnings` → continue. Any `unsupported` claim is a blocker, so `pass_with_warnings` can only carry non-provenance warnings (tone, tense ambiguity, banned phrase).

---

## Step 9 — Summary

First run `node apply-data.mjs output/{folder} {DATA_DIR}/config/profile_bank.json` (writes `apply.json` for the Workday panel). Include its summary line in the report; on exit 1, include the stderr line as a warning and continue (the CV and letter stay valid).

Report: output folder path; verifier verdict + warnings; PDF paths and page counts; any standing rules triggered (conditional-mention blocks included/excluded, Swiss orthography applied, etc.). If `pass_with_warnings`, list warnings so the user can decide whether to fix manually.

**Parallel upgrade reminder:** count `Applied` entries in `career-ops/data/applications.md` generated after the isolated-subagent refactor went live (Step 3.5 present, i.e. after 2026-05-04). When that count reaches 10 and this run has no verifier failures, append:

> "10 clean runs since the subagent refactor. Ready to enable parallel write-cv/write-cl? See the fix-3 isolated-subagents design doc — Parallel Upgrade Plan section."

---

## Step 10.5 — Triage feedback

**Triggered only when Step 0.5 ran in this session** (full-queue mode, the default when no URL/JD/single entry was given). Skip if no entries were scored, or if Step 0.5 produced 0 skip + 0 borderline.

### Interaction A: Borderline review (skip if borderline_count = 0)

Display all `borderline` entries:

```
─────────────────────────────────────────────────────
Borderline review — process any of these now?

  {i}. {title} — {company}     [borderline: {reason}]

Enter numbers to process (runs full pipeline), or Enter to discard all.
Discarded entries are logged to scan-history.tsv.
─────────────────────────────────────────────────────
```

For each number entered: run Steps 1–9 for that entry; then change its `[?]` to `[x]` in `## Borderline`. For each not entered (discarded): append one TSV line to `data/scan-history.tsv`:

```
{url}	{YYYY-MM-DD}	triage	{title}	{company}	discarded_borderline
```

Then **delete the entire `[?]` entry** (and indented sub-lines) from `## Borderline`. If the section becomes empty, delete its header too.

### Interaction B: False negative feedback

Collect entries not processed this session (`skip` + borderline not chosen in A). If none, skip. Display them grouped (Skipped / Discarded borderline) and ask for numbers to flag (or Enter to skip).

### Write feedback entries

For each flagged number, append one JSON object to `data/triage-feedback.jsonl` (create if missing; append mode, one object per line):

```json
{"date": "{YYYY-MM-DD}", "title": "{title}", "company": "{company}", "triage_verdict": "{skip|borderline}", "triage_reason": "{reason}", "user_verdict": "pass", "note": ""}
```

### Synthesis check

Count total lines in `data/triage-feedback.jsonl`. If < 20: show `Feedback saved ({count}/20 before next synthesis).` and done.

If ≥ 20:
1. Read all lines.
2. Call the Agent tool (`subagent_type: "general-purpose"`, `description: "synthesize triage feedback"`) with prompt:

```
You are updating a job triage preference profile based on user feedback corrections.

Here are the triage feedback entries (one JSON object per line):
{all lines from data/triage-feedback.jsonl — paste verbatim}

Instructions:
1. Identify patterns in what the user consistently flagged as incorrectly scored
   (jobs scored skip/borderline but the user wanted to process).
2. Rewrite the preferences: value inside the triage: block in
   career-ops/config/profile.yml. Use a | block scalar. Max 20 lines.
   Keep all rules never overridden; incorporate newly learned rules.
3. Append the entries pasted above (verbatim, one per line)
   to data/triage-feedback.archive.jsonl (create if missing, append mode).
4. Overwrite data/triage-feedback.jsonl with an empty file (0 bytes).
5. Write all changes to disk (you have file-write access).
6. Report which preference rules changed and why.
```

Show the synthesis agent's report to the user.

---

## Liveness check (optional)

Before Step 4, optionally run the liveness check if a job URL was provided:

```bash
node career-ops/check-liveness.mjs {job_url}
```

If liveness returns `dead`: warn and ask whether to proceed (see `modes/_custom.md` — 403/challenge pages are not "dead"; never browser-verify).

---

## Output folder structure

```
output/Company/YYYYMMDD_Company_Role/
├── jd.txt                  ← Step 3.5, consumed by all subagents
├── classification.json     ← Step 3.5
├── profile-filtered.json   ← Step 3.5 (profile-for-job.mjs)
├── computed-facts.txt      ← Step 3.5 (years_experience from Step 1; fact-gate source)
├── humanizer_report.json   ← humanize subagent (Step 5); must be newer than both .tex
├── {file_slug}_CV.tex                  ← write-cv subagent (Step 4a)
├── {file_slug}_CV.pdf                  ← compiled (Step 6)
├── {file_slug}_cover-letter.tex        ← write-cl subagent (Step 4b)
├── {file_slug}_cover-letter.pdf        ← compiled (Step 6)
├── apply.json  ← Step 9 (apply-data.mjs), read by the Workday panel
└── verifier_report.json    ← verify subagent (Step 7)
```

This pipeline does not read or write `cv.md`.
