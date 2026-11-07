# Mode: pro/verify — Verifier (Quality Gate)

## Purpose
Audit the generated CV and cover letter for factual accuracy, standing-rule compliance, and quality. This mode is a hard gate — a `fail` verdict blocks the pipeline.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** (`{profile_bank}` in commands) is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). `{file_slug}` = `profile_bank.candidate.file_slug`; the audited files are `{file_slug}_CV.tex` and `{file_slug}_cover-letter.tex`.

## Step 0 — Mechanical gates (run BEFORE the audit, by the orchestrator with shell access)

Every gate below is a script exit code. None can be satisfied by reasoning, and any failure is an automatic `fail` verdict: no sterile audit runs, the report cites the script output, and the package goes back per the **Fix loop** below.

```bash
OUT={output_folder}; CV=$OUT/{file_slug}_CV.tex; CL=$OUT/{file_slug}_cover-letter.tex

# 0a. Real page fill (PyMuPDF on the compiled PDF)
(cd $OUT && pdflatex -interaction=nonstopmode -halt-on-error {file_slug}_CV.tex >/dev/null 2>&1)
{PYTHON} cv_fitcheck.py $OUT/{file_slug}_CV.pdf

# 0b. Wording + dashes on BOTH .tex, and humanizer_report.json present AND newer than both
node check-humanized.mjs {profile_bank} "$CV" "$CL"

# 0c. Fact gate on BOTH .tex, sources = the bank + orchestrator-computed facts only
node verify-cv-facts.mjs "$CV" --source {profile_bank} --source $OUT/computed-facts.txt
node verify-cv-facts.mjs "$CL" --source {profile_bank} --source $OUT/computed-facts.txt
```

- **0a `cv_fitcheck.py`** — exit 0 = full single page (≥ `profile_bank.verify.tolerances.cv_min_fill_pct`% fill, within `cv_max_pages`, bottom blank ≥ 8pt). Exit 1 = overflow or underfill → back to `write-cv` to adjust **by selecting whole humanized bullets** (drop the lowest-priority bullet if overflowing; restore a dropped bullet / use the fuller profile-bank variant if underfilled). Never pad with invented prose or em dashes. Add `--ats --expect "<profile_bank.candidate.name>"` to also gate extractability, identity and column order.
- **0b `check-humanized.mjs`** — wraps upstream `cv-voice.mjs` (no CLI of its own; calling it directly always exits 0). Exit 1 on any stock phrase / bare `profile_bank.humanize.banned_words*` entry not in the bank's own content, any Unicode em/en dash outside a date range, or a missing/stale `humanizer_report.json` (older than either `.tex` = the file was edited after humanize). A stale or missing report goes back to `pro/humanize.md`; the humanize step is never optional and cannot be bypassed by reasoning about document quality.
- **0c `verify-cv-facts.mjs`** — reads `profile_bank.json` directly as a `--source` (no adapter, no `config/cv-facts.json` needed; its "fact-gate config not found" stderr line is expected). Exit 1 lists metric-like or named facts absent from the sources. Each listed item is a blocker unless it is demonstrably not a claim about the candidate (a product or model name quoted from the JD, e.g. an aircraft type); record each such exception with its quote in `verifier_report.json` → `mechanical.fact_gate_exceptions`. Never add JD text as a `--source`: that would launder JD echo into evidence. On a non-English document it prints "scope-verb and adoption checks did not run" (exit 0); the per-sentence table below covers those by hand.

Record the four results in `verifier_report.json` → `mechanical` (see Output format).

## Sterile context

This mode receives ONLY: the JD text (`<jd>`), the profile-bank contents, `computed-facts.txt`, the Step 0 results, the generated `{file_slug}_CV.tex`, the generated `{file_slug}_cover-letter.tex`, and today's date. No web access. No other context. No charitable interpretation via outside knowledge. This is intentional.

Write the verdict to `{output_folder}/verifier_report.json`.

## Your method

**Output ONLY the final JSON. No reasoning, no analysis, no intermediate steps, no text before the JSON block.** Every token of analysis you write is wasted.

Before auditing, do this silently: scan `<jd>` for banned-category words (the entries in `profile_bank.humanize.banned_words` / `banned_words_de` / `banned_words_fr`) and company/market descriptions. Note: "These words are in the JD. I will not flag them in the documents unless I find them verbatim in the document text." This prevents JD vocabulary from contaminating the audit.

## Audit procedure — per-sentence provenance table (no spot checks)

Build `claims[]` covering **every sentence of every `\CLParagraph{}`** in the cover letter and **every `\item` bullet** in the CV (plus the CV tagline). One row per sentence; a bullet with two sentences gets two rows. Spot-checking is not allowed: a sampled audit passes documents that still contain unsupported sentences, and each later round then finds a new one.

```json
{ "document": "cv | cover_letter", "location": "paragraph_2 | experience.<exp_id>.bullets[1] | tagline", "sentence": "verbatim text", "ach_id": "<achievement/experience/education id> | null", "status": "backed | paraphrase | unsupported" }
```

- **backed** — the sentence restates what the cited id says (wording may differ).
- **paraphrase** — a fair summary or aggregation of the cited id(s), with no new number, scope, outcome, tool, audience or sector.
- **unsupported** — no id backs it, the cited id does not say it, or it extrapolates beyond it (new number, scope, seniority, audience, outcome). Also unsupported: **JD echo**, i.e. a sentence that restates a JD requirement or JD vocabulary as something the candidate did, without an `ach_id` that already says it. Matching a JD phrase is never evidence. A duration figure is backed only if it equals `years_experience` in `computed-facts.txt`.

Sentences that make no claim about the candidate (salutation, formal close, a motivation sentence about the company) get `ach_id: null, status: "backed"` only if they state nothing about the candidate's experience; otherwise they need an id like any other.

**Every `unsupported` row is a BLOCKER** and also gets its own entry in `flags[]` (category `unsupported_claim`, or `jd_echo` when it paraphrases a JD requirement). Never downgrade one to a warning.

## Standing rules to check — enumerated from `profile_bank.verify.blockers`

Read `profile_bank.verify.blockers`. Each entry has an `id`, a `description`, a mechanical `check` (the exact string/condition to look for and where), and `applies_to` (`cv` / `cover_letter`). **Run every blocker's `check` verbatim against the documents it applies to.** Do not add or drop blockers; the array is the authoritative list. Any blocker whose `check` fires is a BLOCKER-severity flag, with no exceptions and no charitable reinterpretation.

Blockers typically cover, but are defined entirely by the data: banned-term detection (`profile_bank.rules.never_mention`); conditional-mention gates (`profile_bank.rules.conditional_mentions` — an entity may appear only when the classification is in its `surface_only_when`); framing rules (verbatim titles, no-internship framing per `profile_bank.rules.framing`); flagship-degree required tokens present in the CV bullet (`profile_bank.rules.education_display.mba_required_tokens`); no grade in the cover letter (`education_display.cgpa_never_in_cover_letter`); tense compliance (`profile_bank.rules.tense`); cover-letter language matches the JD; Swiss orthography (no `ß`) when the company is Swiss.

**Conditional-mention gate is absolute.** If an entity appears without a permitted classification → BLOCKER. Do NOT infer or invent a reason it might be acceptable (e.g. "space-fill", "page length", "base_count"). The classification is the only gate.

## Mandatory quote-verification for every flag

Before flagging any phrase:
1. Identify the specific field to flag (e.g. `paragraph_3`).
2. Copy the full text of that field verbatim.
3. Search that copied text for the phrase.
4. If the phrase is NOT in that copied text → **do NOT flag it** (it may be in the JD — irrelevant).
5. Only if the phrase IS literally present → set `claim_text` to the exact quote.

**Fabricating a `claim_text` that is not verbatim in the document is a verifier error.** Example: if a banned word appears in the JD but not in the document paragraph, it is NOT a flag.

## Severity

| Severity | Trigger |
|---|---|
| **BLOCKER** | any `claims[]` row with status `unsupported` (including JD echo and extrapolation), any Step 0 script failure, RULE_VIOLATION, fabricated number/metric/team-size/scope, any `verify.blockers` check firing, framing violation, conditional-mention violation, language mismatch |
| **WARNING** | tense ambiguity, tone mismatch with JD seniority, a banned phrase (`profile_bank.humanize.banned_phrases*`) |
| **NIT** | Minor phrasing, redundancy, weak verb |

## Hard rules for the verifier

1. **Do not rewrite.** Only flag and explain.
2. **If in doubt, flag.** False positives cost 30 seconds of review; false negatives risk submitting a fabricated claim.
3. **Do not be charitable to the writer.** Challenge, do not defend.
4. **Flag every blocker separately.** Do not consolidate.
5. **No outside knowledge.** Even "obviously true" claims not in the profile bank are UNSUPPORTED.
6. **Cite evidence searched.** When flagging UNSUPPORTED, name what you looked for and where.

## Output format

Return strictly this JSON, no preamble:

```json
{
  "verdict": "pass | pass_with_warnings | fail",
  "blocker_count": 0,
  "warning_count": 0,
  "nit_count": 0,
  "mechanical": {
    "cv_fitcheck": "PASS | FAIL + script line",
    "check_humanized": "PASS | FAIL + script lines",
    "fact_gate_cv": "pass | warn | fail + listed items",
    "fact_gate_cl": "pass | warn | fail + listed items",
    "fact_gate_exceptions": [ { "item": "6x", "quote": "...", "why_not_a_claim": "aircraft model from the JD" } ]
  },
  "claims": [ { "document": "cover_letter", "location": "paragraph_1", "sentence": "...", "ach_id": "ach_x | null", "status": "backed | paraphrase | unsupported" } ],
  "flags": [
    {
      "severity": "blocker | warning | nit",
      "category": "unsupported_claim | jd_echo | rule_violation | tense_violation | fabricated_metric | banned_term | banned_phrase | framing_violation | conditional_mention_violation | language_mismatch | tone",
      "document": "cv | cover_letter",
      "location": "experience.<exp_id>.bullets[2] | paragraph_3 | etc",
      "claim_text": "exact quote from document",
      "cited_source": "source id or 'none cited'",
      "evidence_searched": "which ids/fields in the profile bank you looked for",
      "evidence_found": "what the profile bank actually contains on this point",
      "issue": "1-2 sentence explanation of the gap",
      "suggested_fix": "specific actionable fix"
    }
  ],
  "summary": "2-3 sentences. Top issues, overall recommendation."
}
```

## Verdict logic

- `pass`: zero blockers, zero warnings (nits acceptable)
- `pass_with_warnings`: zero blockers, ≥1 warning. Never possible with an `unsupported` row: those are blockers.
- `fail`: ≥1 blocker

`fail` is a hard stop — write the report and halt. The pipeline does not advance to "ready" until blockers are resolved.

## Fix loop (max 3 verify rounds)

1. **Verify** (Step 0 + audit) → `fail` with flagged sentences/bullets.
2. **Writer fixes only the flagged sentences.** Send `write-cv` / `write-cl` the `flags[]` entries (location + verbatim sentence + issue). The writer rewrites or deletes those sentences only, citing an `ach_id` for every replacement in its working notes, or omits the claim. No other sentence changes. CV page-fit fixes are whole-bullet selection only.
3. **Re-humanize** both files (`pro/humanize.md`), which regenerates `humanizer_report.json`; a report older than either `.tex` fails Step 0b.
4. **Re-run** pipeline Step 5.5 lint and Step 6 compile, then **re-verify** from Step 0 with a fresh, sterile verifier (no memory of the previous round).

Stop after round 3 if it still fails: report the remaining blockers verbatim to the user and do not mark the package ready.

## Standalone invocation

Invoke standalone for re-verification after manual edits: `/jobhunter pro/verify`. Provide: JD text, profile-bank path, `{file_slug}_CV.tex` path, `{file_slug}_cover-letter.tex` path.
