# Smarter Job Triage — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the brittle positive-keyword scan filter with an LLM triage step that semantically scores job relevance before any processing work is done, and accumulates user feedback to improve over time.

**Architecture:** Scan stays unchanged (negative gate only). `portals.yml` loses its `title_filter.positive` block — more entries reach `pipeline.md`. Step 0.5 in `modes/rb/pipeline.md` scores all pending entries with a `claude-haiku-4-5` subagent before processing; pass entries flow through Steps 1–9 as before. Step 10.5 collects user feedback on incorrect verdicts and triggers synthesis when ≥20 entries accumulate.

**Tech Stack:** Claude Code Agent tool (`claude-haiku-4-5` for scoring, general-purpose for synthesis), YAML (`config/profile.yml`), JSONL (`data/triage-feedback.jsonl`), TSV (`data/scan-history.tsv`), Markdown (`modes/rb/pipeline.md`, `portals.yml`).

**Spec:** `career-ops/docs/superpowers/specs/2026-05-12-smarter-triage-design.md`

---

## File Map

| File | Action | Committed |
|------|--------|-----------|
| `career-ops/templates/portals.example.yml` | Remove `title_filter.positive` block, update comments | Yes |
| `career-ops/portals.yml` | Same change (user's live file) | No (gitignored) |
| `career-ops/.gitignore` | Add `data/triage-feedback.jsonl` and `data/triage-feedback.archive.jsonl` | Yes |
| `career-ops/config/profile.yml` | Add `triage:` block at end of file | No (gitignored) |
| `career-ops/modes/rb/pipeline.md` | Modify Step 0 "all" path + insert Step 0.5 + insert Step 10.5 | Yes |

---

## Task 1: portals.example.yml — remove positive keyword gate

**Files:**
- Modify: `career-ops/templates/portals.example.yml`

The `title_filter.positive` block (lines 28–101 in the current file) must be removed entirely. The scan agent, seeing no `positive:` key in portals.yml, will skip the positive-match requirement and let all titles through to the negative gate. Add a comment making this explicit.

- [ ] **Step 1: Read the current file**

```bash
grep -n "positive\|negative\|seniority\|CUSTOMIZE\|title_filter" \
  career-ops/templates/portals.example.yml | head -20
```

Expected: see `title_filter:`, `positive:`, `negative:`, `seniority_boost:` sections.

- [ ] **Step 2: Replace the HOW TO CUSTOMIZE comment block (lines 16–21)**

Find this block:
```yaml
# HOW TO CUSTOMIZE:
#   1. Copy this file to portals.yml in the project root
#   2. Edit title_filter.positive with YOUR target role keywords
#   3. Add/remove companies in tracked_companies
#   4. Adjust search_queries for your preferred job boards
#   5. Set enabled: false on companies you don't care about
```

Replace with:
```yaml
# HOW TO CUSTOMIZE:
#   1. Copy this file to portals.yml in the project root
#   2. Add keywords to title_filter.negative to block clearly irrelevant titles
#   3. Add/remove companies in tracked_companies
#   4. Adjust search_queries for your preferred job boards
#   5. Set enabled: false on companies you don't care about
#   (title_filter.positive removed — relevance screening now handled by LLM triage
#    in pipeline Step 0.5. Configure it via the triage: block in config/profile.yml)
```

- [ ] **Step 3: Replace the entire title_filter block (lines 23–101)**

Find this block (starting at `# -- Title filter --` through the end of `seniority_boost:`):
```yaml
# -- Title filter --
# The scanner uses these keywords to decide if a title is relevant.
# At least 1 positive must match AND 0 negatives must match (case-insensitive).

title_filter:
  positive:
    # [CUSTOMIZE] Add keywords matching YOUR target roles
    # -- AI/ML roles --
    - "AI"
    - "ML"
    ...
    - "Transformation"
  negative:
    # [CUSTOMIZE] Add keywords for roles you want to exclude
    - "Junior"
    ...
    - "COBOL"
  seniority_boost:
    # These prefixes add relevance but are not required
    - "Senior"
    ...
    - "Director"
```

Replace with:
```yaml
# -- Title filter --
# The scanner uses negative keywords to block clearly irrelevant titles.
# title_filter.positive has been removed — all titles now pass the positive gate.
# Semantic relevance screening happens in pipeline Step 0.5 (LLM triage).
# 0 negatives must match for an entry to reach the pipeline (case-insensitive).

title_filter:
  # positive: block removed — configure relevance in config/profile.yml triage: block
  negative:
    # [CUSTOMIZE] Add keywords for roles you want to exclude
    - "Junior"
    - "Intern"
    - ".NET"
    - "Java "
    - "iOS"
    - "Android"
    - "PHP"
    - "Ruby"
    - "Embedded"
    - "Firmware"
    - "FPGA"
    - "ASIC"
    - "Blockchain"
    - "Web3"
    - "Crypto"
    - "Salesforce Admin"
    - "SAP "
    - "Oracle EBS"
    - "Mainframe"
    - "COBOL"
  seniority_boost:
    # These prefixes add relevance but are not required
    - "Senior"
    - "Staff"
    - "Principal"
    - "Lead"
    - "Head"
    - "Director"
```

- [ ] **Step 4: Verify no `positive:` key remains (except in the comment)**

```bash
grep -n "^  positive:" career-ops/templates/portals.example.yml
```

Expected: no output (the `positive:` key as YAML is gone; the comment line `# positive: block removed` starts with `#` and won't match).

- [ ] **Step 5: Commit**

```bash
cd career-ops
git add templates/portals.example.yml
git commit -m "feat: remove title_filter.positive — replaced by LLM triage in pipeline Step 0.5"
```

---

## Task 2: portals.yml (user's live file) — remove positive keyword gate

**Files:**
- Modify: `career-ops/portals.yml` (gitignored — no commit needed)

The user's live `portals.yml` has a Swiss-market `title_filter.positive` block (lines 47–96). Remove it so scan immediately uses the new looser filter.

- [ ] **Step 1: Confirm the positive block exists**

```bash
grep -n "^  positive:" career-ops/portals.yml
```

Expected: one hit around line 47. If no hit, skip this task.

- [ ] **Step 2: Replace the title_filter comment + positive block**

Find this section (lines 43–96):
```yaml
# -- Title filter --
# At least 1 positive must match AND 0 negatives must match (case-insensitive).

title_filter:
  positive:
    # -- In-house Strategy & Corporate Development --
    - "Corporate Development"
    ...
    - "Value Creation"
  negative:
    ...
```

Replace the comment and remove the `positive:` block, keeping `negative:` and `seniority_boost:` intact:
```yaml
# -- Title filter --
# title_filter.positive removed — all titles now pass the positive gate.
# Semantic relevance screening happens in pipeline Step 0.5 (LLM triage).
# 0 negatives must match for an entry to reach the pipeline (case-insensitive).

title_filter:
  # positive: block removed — configure relevance in config/profile.yml triage: block
  negative:
    - "Intern"
    - "Internship"
    - "Praktikum"
    - "Trainee"
    - "Junior"
    - "Werkstudent"
    - "Real Estate"
    - "IT Strategy"
    - "HR Strategy"
    - "Tax"
    - "Legal"
    - "Compliance"
    - "Audit"
    - "TALENTPOOL"
    - "Talentpool"
  seniority_boost:
    - "Senior"
    - "Manager"
    - "Director"
    - "Head"
    - "Lead"
    - "Principal"
    - "VP"
```

- [ ] **Step 3: Verify**

```bash
grep -n "^  positive:" career-ops/portals.yml
```

Expected: no output.

---

## Task 3: .gitignore — add triage feedback files

**Files:**
- Modify: `career-ops/.gitignore`

- [ ] **Step 1: Append triage data entries to the `data/` section**

Find the existing data section in `.gitignore`:
```
data/applications.md
data/pipeline.md
data/scan-history.tsv
data/follow-ups.md
```

Add two lines immediately after `data/follow-ups.md`:
```
data/triage-feedback.jsonl
data/triage-feedback.archive.jsonl
```

- [ ] **Step 2: Verify**

```bash
grep "triage-feedback" career-ops/.gitignore
```

Expected:
```
data/triage-feedback.jsonl
data/triage-feedback.archive.jsonl
```

- [ ] **Step 3: Commit**

```bash
cd career-ops
git add .gitignore
git commit -m "chore: gitignore triage feedback files"
```

---

## Task 4: config/profile.yml — add triage: block

**Files:**
- Modify: `career-ops/config/profile.yml` (gitignored — no commit)

This file is the user's live profile. Append the `triage:` block at the end of the file.

- [ ] **Step 1: Confirm the block doesn't already exist**

```bash
grep -n "^triage:" career-ops/config/profile.yml
```

Expected: no output. If a `triage:` block already exists, skip this task.

- [ ] **Step 2: Append the triage block**

Read the current last line of the file to ensure there's a clean newline, then append:

```yaml

# ─────────────────────────────────────────────────────────────────────────────
# TRIAGE CONFIGURATION
# Controls LLM-based job relevance scoring in pipeline Step 0.5.
# The preferences block is the seed — it is rewritten automatically after
# every synthesis cycle (≥20 feedback entries).
# ─────────────────────────────────────────────────────────────────────────────

triage:
  model: claude-haiku-4-5
  borderline_bucket: true
  preferences: |
    Core target band: Senior Manager, Lead, Senior Lead, Manager (with clear
    seniority signal), Senior Associate — in strategy, M&A, BD, applied AI,
    operations, or transformation roles in Switzerland.

    "Head of" titles: pass only if the company is a startup or scale-up
    (<500 employees). Flag as borderline at mid-market, skip at enterprise
    (UBS, Nestlé, ABB, Novartis-scale).

    Skip: staffing/recruiting agencies, pure AE/SDR sales, HR, junior
    titles (Analyst, Associate without Senior), C-suite (too senior),
    Director/VP at large corporates, anything outside Switzerland unless
    explicitly remote.

    Exception: BD or GTM roles at product-led AI/tech companies are worth
    reviewing even if the title sounds generic — company context matters.
```

- [ ] **Step 3: Verify**

```bash
grep -A 5 "^triage:" career-ops/config/profile.yml
```

Expected: shows `triage:` followed by `model:`, `borderline_bucket:`, `preferences:`.

---

## Task 5: pipeline.md — Step 0 modification + Step 0.5 (triage agent)

**Files:**
- Modify: `career-ops/modes/rb/pipeline.md`

Two edits to this file in one task:
1. Modify Step 0's "all" path to route to Step 0.5 instead of directly looping
2. Insert the full Step 0.5 section after Step 0's closing `---`

- [ ] **Step 1: Modify Step 0's "all" path (line ~38)**

Find this exact line in Step 0:
```markdown
   - If the user says "all" or "process all": loop through each unchecked item sequentially, running Steps 1–9 for each, then mark each checkbox (`- [x]`) in pipeline.md when done.
```

Replace with:
```markdown
   - If the user says "all" or "process all": go to Step 0.5.
```

- [ ] **Step 2: Insert Step 0.5 after Step 0's closing separator**

Find the exact block at the end of Step 0:
```markdown
After successfully completing the pipeline for a job, mark its checkbox in `career-ops/data/pipeline.md` as done: change `- [ ]` to `- [x]`.

---

## Step 1 — Generate cv.md if stale
```

Replace with:
```markdown
After successfully completing the pipeline for a job, mark its checkbox in `career-ops/data/pipeline.md` as done: change `- [ ]` to `- [x]`.

---

## Step 0.5 — Triage pending entries

**Triggered by Step 0's "all" path only.** Skip entirely if the user provided a specific URL, JD text, or selected a single entry by number.

### Read triage preferences

Read `career-ops/config/profile.yml`. Extract `triage.preferences`.

If the `triage:` block is missing from `profile.yml`, stop and show:

```
Triage is not configured. Please add a triage: block to career-ops/config/profile.yml.

Minimum required:
  triage:
    model: claude-haiku-4-5
    borderline_bucket: true
    preferences: |
      Describe your target roles here. The LLM uses this to score each job.

After adding the block, re-run /jobhunter pipeline.
```

### Parse pending entries

From the `- [ ]` entries read in Step 0, extract `{title}` and `{company}` from each display line. The display format is `Company Name — Role Title`. If a line doesn't parse into that format, use the raw line as `title` and `"unknown"` as `company`. Build an indexed list: `[{index: 1, title: "...", company: "..."}, ...]`.

### Score entries (batches of 50)

For each batch of up to 50 entries, call the Agent tool:

- `subagent_type`: `"general-purpose"`
- `model`: `"haiku"`
- `description`: `"triage batch {start}–{end} of {total}"`
- `prompt`:

```
You are a job relevance screener for a specific candidate. Score each job below.

Candidate preferences:
{value of triage.preferences from config/profile.yml — paste verbatim}

For each job output EXACTLY one line in this format (no preamble, no extra text):
<index> | <verdict> | <one-line reason>

Verdicts:
- pass      — clear match with candidate profile
- borderline — plausible but uncertain (wrong company size, adjacent title, sector mismatch)
- skip      — clearly irrelevant

Jobs:
1. {title} — {company}
2. {title} — {company}
...
```

Parse each response line: extract `index` (integer), `verdict` (`pass` / `borderline` / `skip`), `reason` (text after the last `|`, trimmed). If a line cannot be parsed, default to `borderline` with reason `"parse error"`.

### Route entries

**pass** → entry stays as `- [ ]` in `data/pipeline.md`. No change to the file. Will be processed in Steps 1–9.

**borderline** → move entry from the `- [ ]` section to a `## Borderline` section at the bottom of `data/pipeline.md`. Create the section if it doesn't exist. Write:

```markdown
## Borderline

- [?] {Company} — {Role}
     {url}
     Triage: {reason}
```

**skip** → remove the `- [ ]` entry from `data/pipeline.md`. Append one TSV line to `data/scan-history.tsv` (create the file if it doesn't exist):

```
{YYYY-MM-DD}	{title}	{company}	skipped_triage	{reason}
```

(Tab-separated. Five fields. No header row needed if the file already has data; if creating from scratch, no header either — the file is append-only.)

### Display triage summary

After all routing is done, show:

```
Triage complete — {total} pending entries scored:
  ✓ {pass_count} pass  (will process)
  ~ {borderline_count} borderline  (review at end)
  ✗ {skip_count} skip

Processing {pass_count} offers...
```

If `pass_count` is 0:

```
Triage complete — 0 offers passed triage. Nothing to process.
Borderline entries are saved in data/pipeline.md under ## Borderline for manual review.
```

Then stop. Do NOT proceed to Steps 1–9.

### Process pass entries

For each entry that scored `pass`, run Steps 1–9 sequentially. After completing each entry, mark its checkbox as done (`- [x]`) in `data/pipeline.md`.

---

## Step 1 — Generate cv.md if stale
```

- [ ] **Step 3: Verify Step 0.5 was inserted**

```bash
grep -n "^## Step 0.5" career-ops/modes/rb/pipeline.md
```

Expected: one hit.

```bash
grep -n "^## Step 1" career-ops/modes/rb/pipeline.md
```

Expected: one hit, with a higher line number than Step 0.5.

- [ ] **Step 4: Verify Step 0's "all" path was updated**

```bash
grep -n "go to Step 0.5" career-ops/modes/rb/pipeline.md
```

Expected: one hit inside Step 0.

- [ ] **Step 5: Commit**

```bash
cd career-ops
git add modes/rb/pipeline.md
git commit -m "feat: add triage Step 0.5 — LLM-based relevance scoring before pipeline processing"
```

---

## Task 6: pipeline.md — Step 10.5 (feedback loop)

**Files:**
- Modify: `career-ops/modes/rb/pipeline.md`

Insert Step 10.5 after Step 9 (Summary) and before the `## Liveness check (optional)` section.

- [ ] **Step 1: Locate the insertion point**

```bash
grep -n "^## Step 9\|^## Liveness check" career-ops/modes/rb/pipeline.md
```

Expected: Step 9 at some line N, Liveness check at line M > N. Step 10.5 goes between them (after Step 9's trailing `---` separator).

- [ ] **Step 2: Insert Step 10.5**

Find this exact block at the end of Step 9:
```markdown
If `pass_with_warnings`: list warnings so user can decide whether to fix manually

**Parallel upgrade reminder:** Count the number of `Applied` entries in `career-ops/data/applications.md` that were generated after Fix #3 went live (Step 3.5 present, i.e. after 2026-05-04). When that count reaches 10 and this run has no verifier failures, append to the summary:

> "10 clean runs since the subagent refactor. Ready to enable parallel write-cv/write-cl? See: docs/superpowers/specs/2026-05-04-fix3-isolated-subagents-design.md — Parallel Upgrade Plan section."

---

## Liveness check (optional)
```

Replace with:
```markdown
If `pass_with_warnings`: list warnings so user can decide whether to fix manually

**Parallel upgrade reminder:** Count the number of `Applied` entries in `career-ops/data/applications.md` that were generated after Fix #3 went live (Step 3.5 present, i.e. after 2026-05-04). When that count reaches 10 and this run has no verifier failures, append to the summary:

> "10 clean runs since the subagent refactor. Ready to enable parallel write-cv/write-cl? See: docs/superpowers/specs/2026-05-04-fix3-isolated-subagents-design.md — Parallel Upgrade Plan section."

---

## Step 10.5 — Triage feedback

**Triggered only when Step 0.5 ran in this session** (queue mode, "all" path). Skip entirely if no entries were scored in Step 0.5, or if Step 0.5 produced 0 skip + 0 borderline results.

### Interaction A: Borderline review (skip if borderline_count = 0)

Display all entries routed to `borderline` in Step 0.5:

```
─────────────────────────────────────────────────────
Borderline review — process any of these now?

  {i}. {title} — {company}     [borderline: {reason}]

Enter numbers to process (runs full pipeline), or Enter to discard all.
Discarded entries are logged to scan-history.tsv.
─────────────────────────────────────────────────────
```

Wait for user input.

**For each number entered:** run Steps 1–9 for that entry immediately (same as a pass entry). After completing, mark its `[?]` entry in `data/pipeline.md` as done (`[x]`).

**For each number NOT entered** (discarded): append one TSV line to `data/scan-history.tsv`:

```
{YYYY-MM-DD}	{title}	{company}	discarded_borderline	{reason}
```

Remove the `[?]` entry from the `## Borderline` section of `data/pipeline.md`. If the `## Borderline` section becomes empty, remove the section header too.

### Interaction B: False negative feedback

Collect all entries from this session that ended up not processed: `skip` entries + borderline entries not chosen in Interaction A. If none remain, skip this interaction.

Display:

```
─────────────────────────────────────────────────────
Triage feedback — flag incorrectly scored

  Skipped:
    {i}. {title} — {company}     [skip: {reason}]

  Discarded borderline:
    {j}. {title} — {company}     [borderline: {reason}]

Enter numbers to flag for feedback (improves future triage),
or press Enter to skip.
─────────────────────────────────────────────────────
```

Wait for user input. If the user presses Enter with no input, skip the rest of this step.

### Write feedback entries

For each flagged number, append one JSON object to `data/triage-feedback.jsonl` (create the file if it doesn't exist; append mode, one object per line, no trailing comma, no wrapping array):

```json
{"date": "{YYYY-MM-DD}", "title": "{title}", "company": "{company}", "triage_verdict": "{skip|borderline}", "triage_reason": "{reason}", "user_verdict": "pass", "note": ""}
```

### Synthesis check

After writing, count total lines in `data/triage-feedback.jsonl`.

If count < 20: show `Feedback saved ({count}/20 before next synthesis).` Done.

If count ≥ 20:

1. Read all lines from `data/triage-feedback.jsonl`.
2. Call the Agent tool:
   - `subagent_type`: `"general-purpose"`
   - `description`: `"synthesize triage feedback"`
   - `prompt`:

```
You are updating a job triage preference profile based on user feedback corrections.

Here are the triage feedback entries (one JSON object per line):
{all lines from data/triage-feedback.jsonl — paste verbatim}

Instructions:
1. Identify patterns in what the user consistently flagged as incorrectly scored
   (jobs the triage scored skip/borderline but the user wanted to process).
2. Rewrite the preferences: value inside the triage: block in
   career-ops/config/profile.yml. Use a | block scalar. Max 20 lines.
   - Keep all rules that were never overridden.
   - Incorporate newly learned rules as clear additions or modifications.
3. Append all entries from data/triage-feedback.jsonl (verbatim, one per line)
   to data/triage-feedback.archive.jsonl (create if it doesn't exist, append mode).
4. Overwrite data/triage-feedback.jsonl with an empty file (0 bytes).
5. Report which rules changed and why.
```

Show the synthesis agent's report to the user.

---

## Liveness check (optional)
```

- [ ] **Step 3: Verify Step 10.5 was inserted**

```bash
grep -n "^## Step 10.5\|^## Liveness check" career-ops/modes/rb/pipeline.md
```

Expected: Step 10.5 at some line N, Liveness check at line M > N.

- [ ] **Step 4: Verify the synthesis prompt is complete (spot check)**

```bash
grep -c "Overwrite data/triage-feedback.jsonl" career-ops/modes/rb/pipeline.md
```

Expected: `1`

- [ ] **Step 5: Commit**

```bash
cd career-ops
git add modes/rb/pipeline.md
git commit -m "feat: add triage feedback Step 10.5 — user correction loop + synthesis trigger"
```

---

## Verification checklist (run after all tasks)

- [ ] `grep -n "^  positive:" career-ops/templates/portals.example.yml` → no output
- [ ] `grep -n "^  positive:" career-ops/portals.yml` → no output
- [ ] `grep "triage-feedback" career-ops/.gitignore` → two hits
- [ ] `grep -A2 "^triage:" career-ops/config/profile.yml` → shows `model:` and `borderline_bucket:`
- [ ] `grep -n "^## Step 0.5\|^## Step 10.5" career-ops/modes/rb/pipeline.md` → two hits
- [ ] `grep -n "go to Step 0.5" career-ops/modes/rb/pipeline.md` → one hit
- [ ] Run `/jobhunter pipeline` with an empty pipeline — should show "Triage is not configured" only if `triage:` block was not added (confirm triage block is present)
- [ ] Run `/jobhunter pipeline` with 2–3 test entries in `data/pipeline.md` — confirm triage summary displays before processing
