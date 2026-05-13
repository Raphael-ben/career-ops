# Token Optimization — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Eliminate main-session context accumulation for queue runs (Approach B) and halve write-cv/write-cl wall-clock time (Approach C), without any quality change to generated CVs, cover letters, or verifier behaviour.

**Constraint:** Quality must not drop. Same models, same mode files, same steps — only where the work runs changes.

**Activation:** Both changes are gated behind flags in `config/profile.yml`. They activate together when the user accepts the 10-clean-runs upgrade prompt already embedded in Step 9 of `pipeline.md`.

---

## Section 1 — Problem

The "all" queue path in `modes/rb/pipeline.md` runs Steps 2–9 inline in the main session for each job. Every job appends its full JD text, classification reasoning, tool outputs, and summary to the main session context. For 40 jobs this accumulates ~80,000+ tokens in the main session, causing:

- **Allocation drain:** Max 5x budget exhausted mid-batch
- **Context bloat:** Session slows and degrades as context fills

Steps 4a, 4b, 5, and 7 are already isolated subagents — their outputs don't pollute the main session. The problem is Steps 2, 3, 3.5, 5.5, 6, and 9, which all run inline.

---

## Section 2 — Architecture

### Current (queue "all" path)

```
Main session:
  Step 0.5  triage (haiku subagents) ← already isolated
  Step 1    cv.md freshness check (once)
  For each pass entry [INLINE]:
    Step 2    JD extraction → JD lands in main session
    Step 3    classify → reasoning + JSON in main session
    Step 3.5  folder creation + profile-for-job.mjs
    Step 4a   write-cv subagent
    Step 4b   write-cl subagent (sequential)
    Step 5    humanize subagent
    Step 5.5  LaTeX lint (bash)
    Step 6    compile (bash)
    Step 7    verify subagent
    Step 9    summary (inline, accumulates in main session)
  Step 10.5  triage feedback ← already isolated
```

### After (B + C activated)

```
Main session:
  Step 0.5  triage (unchanged)
  Step 1    cv.md freshness check (unchanged, once)
  For each pass entry:
    dispatch per-job subagent → receives one compact result line
    mark pipeline.md checkbox
  [optional] 10-run upgrade prompt (if threshold met)
  Step 10.5  triage feedback (unchanged)

Per-job subagent (reads modes/rb/pipeline-job.md):
  Step 2    JD extraction
  Step 3    classify
  Step 3.5  folder + profile-for-job.mjs
  Step 4a + 4b  write-cv || write-cl (parallel ← Approach C)
  Step 5    humanize
  Step 5.5  lint
  Step 6    compile
  Step 7    verify
  returns   compact result line
```

Main session growth per job drops from ~2,000 tokens (JD + reasoning + summary) to ~60 tokens (one compact result line). For 40 jobs: ~97% reduction in main-session accumulation.

---

## Section 3 — New file: `modes/rb/pipeline-job.md`

A new mode file that contains exactly the content of current Steps 2–9, with one change: Steps 4a and 4b dispatch their Agent calls in the same message (parallel).

### What the per-job subagent receives

The main session passes these values in the prompt:

```
URL (or JD text if no URL)
Profile bank path: ~/Claude-code/job-hunter-data/config/profile_bank.json
Output base folder: career-ops/output/
Today's date: YYYY-MM-DD
Write-CV mode: modes/rb/write-cv.md  (or modes/rb/de-ch/write-cv.md)
Write-CL mode: modes/rb/write-cl.md  (or modes/rb/de-ch/write-cl.md)
Humanize mode: modes/rb/humanize.md
Verify mode:   modes/rb/verify.md
```

The mode-file selection (standard vs de-ch) cannot be done before classification — the per-job subagent must select the right mode files after Step 3, exactly as today.

### Compact result format

On success:
```
{Company} | {Role} | {output_folder} | fit:{grade} | verifier:{pass|pass_with_warnings|fail}
```

On error (subagent failed, file missing, compile error):
```
ERROR | {Company or URL} | {output_folder or ""} | {one-line reason}
```

The main session collects these lines, displays them as a batch summary after all jobs complete, and marks `pipeline.md` checkboxes for successful entries only.

### Parallel Steps 4a + 4b (Approach C)

Inside `pipeline-job.md`, the dispatch block for Steps 4a and 4b is:

```
Call the Agent tool twice in the same response (parallel):
  - Agent 1: write-cv subagent (same prompt as today's Step 4a)
  - Agent 2: write-cl subagent (same prompt as today's Step 4b)
Wait for both to complete before proceeding to Step 5.
```

Both agents read from the same input files (jd.txt, classification.json, profile-filtered.json) and write to different output files — no conflict.

### 10-run upgrade prompt

The upgrade prompt stays in `pipeline.md`'s inline Step 9. It fires on the pre-activation queue path (when `per_job_isolation` is absent or false). Once activation has occurred, the prompt is no longer reached (the per-job isolation branch is taken instead).

The prompt is updated to reference both B and C:

> "10 clean runs since the subagent refactor. Ready to activate token optimisation (per-job isolation + parallel CV/CL)? See: `docs/superpowers/specs/2026-05-13-token-optimization-design.md`."

When the user accepts, the activation step (Section 4 below) runs.

---

## Section 4 — Changes to `modes/rb/pipeline.md`

### Step 0 "all" branch

Two paths based on `config/profile.yml`:

**If `pipeline.per_job_isolation` is absent or false** (current behaviour):
```
loop through each pass entry sequentially, running Steps 1–9 for each
```

**If `pipeline.per_job_isolation: true`** (B activated):
```
Run Step 1 once.
For each pass entry, call the Agent tool:
  subagent_type: "general-purpose"
  description:   "pipeline job — {company} {role}"
  prompt: |
    Read career-ops/modes/rb/pipeline-job.md and execute it for this job.

    URL: {url}
    Profile bank: ~/Claude-code/job-hunter-data/config/profile_bank.json
    Output base: career-ops/output/
    Today: {YYYY-MM-DD}
    Standard CV mode:  career-ops/modes/rb/write-cv.md
    DE-CH CV mode:     career-ops/modes/rb/de-ch/write-cv.md
    Standard CL mode:  career-ops/modes/rb/write-cl.md
    DE-CH CL mode:     career-ops/modes/rb/de-ch/write-cl.md
    Humanize mode:     career-ops/modes/rb/humanize.md
    Verify mode:       career-ops/modes/rb/verify.md
    Select standard vs de-ch after Step 3 classification (swiss:true AND language:de → de-ch).

    Return exactly one compact result line in this format:
    {Company} | {Role} | {output_folder} | fit:{grade} | verifier:{pass|pass_with_warnings|fail}
    Or on error:
    ERROR | {Company or URL} | {output_folder or ""} | {one-line reason}

Collect all result lines. After all jobs complete, display the batch summary.
For each successful result, mark the corresponding pipeline.md checkbox as done.
For each ERROR result, report to user — do not mark as done.
```

### Step 9 — remove from main pipeline.md

Step 9 moves into `pipeline-job.md`. In the "all" + isolation path, the main session batch summary replaces per-job Step 9 output:

```
Batch complete — {n} jobs processed:
  ✓ {success_count} pass
  ⚠ {warn_count} pass with warnings
  ✗ {error_count} errors

{result lines...}
```

Step 9 stays in `pipeline.md` for single-URL and number-selection paths (those don't use the per-job subagent).

---

## Section 5 — Activation mechanism

### Flags in `config/profile.yml` (user layer, gitignored)

```yaml
pipeline:
  per_job_isolation: true   # Approach B — per-job subagent for queue runs
  parallel_cv_cl: true      # Approach C — parallel write-cv + write-cl
```

Both default to absent = false. The pipeline checks for these keys at the start of each run.

`parallel_cv_cl` is read by `pipeline-job.md` to decide whether to dispatch Steps 4a+4b in the same response (parallel) or sequentially.

### When the user accepts the upgrade prompt

The pipeline writes both flags to `config/profile.yml` under the `pipeline:` key (creating the key if absent). After writing, it confirms:

```
Token optimisation activated.
  ✓ per_job_isolation: true
  ✓ parallel_cv_cl: true
Next queue run will use per-job subagents with parallel CV/CL.
```

### Rollback

Set either flag to `false` in `config/profile.yml`. No code changes needed. The pipeline falls back to inline processing for that flag.

---

## Section 6 — Edge cases

- **Single URL or number selection:** Per-job subagent is never used. Steps 2–9 run inline as today, regardless of flags. The flags only affect the "all" queue path.
- **de-ch mode selection:** The per-job subagent selects write-cv/write-cl mode files after Step 3 (classification), exactly as today. The orchestrator context in the prompt provides both paths so the subagent can choose.
- **Error in per-job subagent:** Returns `ERROR` line. Main session marks the entry as not done, reports to user, continues to next entry. Does not stop the entire batch.
- **profile-for-job.mjs failure:** Per-job subagent falls back to full `profile_bank.json`, same as today's pipeline fallback in Step 3.5.
- **Compile failure:** Per-job subagent returns `ERROR` line with reason. User sees it in batch summary.
- **parallel_cv_cl: false with per_job_isolation: true:** Valid combination. Runs per-job subagents but with sequential write-cv → write-cl inside. Both flags are independent.

---

## Data contract

| File | Change | Committed |
|------|--------|-----------|
| `modes/rb/pipeline-job.md` | New — Steps 2–9 for single job, parallel 4a+4b | Yes |
| `modes/rb/pipeline.md` | Modified — "all" path adds isolation branch, Step 9 updated | Yes |
| `config/profile.yml` (`pipeline:` block) | User — written at activation time | No (gitignored) |
| `modes/rb/write-cv.md` | Unchanged | — |
| `modes/rb/write-cl.md` | Unchanged | — |
| `modes/rb/humanize.md` | Unchanged | — |
| `modes/rb/verify.md` | Unchanged | — |
