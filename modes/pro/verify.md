# Mode: pro/verify — Verifier (Quality Gate)

## Purpose
Audit the generated CV and cover letter for factual accuracy, standing-rule compliance, and quality. This mode is a hard gate — a `fail` verdict blocks the pipeline.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). `{file_slug}` = `profile_bank.candidate.file_slug`; the audited files are `{file_slug}_CV.tex` and `{file_slug}_cover-letter.tex`.

## Step 0 — Real page-fill gate (run BEFORE the audit)

The orchestrator (which has shell access) MUST compile the CV and measure its **actual** rendered fill before the sterile LLM audit:

```bash
cd {output_folder} && pdflatex -interaction=nonstopmode -halt-on-error {file_slug}_CV.tex >/dev/null 2>&1
cd - >/dev/null && {PYTHON} cv_fitcheck.py {output_folder}/{file_slug}_CV.pdf
```

`cv_fitcheck.py` opens the compiled PDF with PyMuPDF and measures real main-column fill (lowest text baseline ÷ page height), replacing the old character-count heuristic which lied. Add `--ats --expect "<profile_bank.candidate.name>"` to also gate machine-extractability, identity presence, and column-order stability. Exit codes:
- **exit 0** → full single page (≥ `profile_bank.verify.tolerances.cv_min_fill_pct`% fill, within `cv_max_pages`, non-negative bottom margin). Proceed to the LLM audit.
- **exit 1** → BLOCKER. Either overflow or underfilled. Return a `fail` verdict citing the script output and send the CV back to `write-cv` to adjust **by selecting whole humanized bullets** (drop the lowest-priority bullet if overflowing; restore a dropped bullet / use the fuller profile-bank variant if underfilled). Never let write-cv pad with invented prose or em dashes.

This gate is non-negotiable and cannot be satisfied by reasoning — it is a measured fill percentage.

Before the sterile audit, the orchestrator MUST also confirm `{output_folder}/humanizer_report.json` exists and lists both `{file_slug}_CV.tex` and `{file_slug}_cover-letter.tex` (or a per-doc report exists for each). Missing report → automatic `fail`, no sterile audit runs. Return a `fail` verdict citing the missing file and send the package back to `pro/humanize.md` first — the humanize step is never optional or skippable and cannot be bypassed by reasoning about the document quality.

## Sterile context

This mode receives ONLY: the JD text (`<jd>`), the profile-bank contents, the generated `{file_slug}_CV.tex`, the generated `{file_slug}_cover-letter.tex`, and today's date. No web access. No other context. No charitable interpretation via outside knowledge. This is intentional.

Write the verdict to `{output_folder}/verifier_report.json`.

## Your method

**Output ONLY the final JSON. No reasoning, no analysis, no intermediate steps, no text before the JSON block.** Every token of analysis you write is wasted.

Before auditing, do this silently: scan `<jd>` for banned-category words (the entries in `profile_bank.humanize.banned_words` / `banned_words_de` / `banned_words_fr`) and company/market descriptions. Note: "These words are in the JD. I will not flag them in the documents unless I find them verbatim in the document text." This prevents JD vocabulary from contaminating the audit.

## Audit procedure

For each factual claim about the candidate in the two documents:
1. **Identify the claim.** Quote the exact text.
2. **Find the source.** Look up referenced entries in the profile bank.
3. **Classify:**
   - **SUPPORTED** — direct match, possibly rephrased.
   - **INFERRED_OK** — reasonable summary/aggregation, no new specifics.
   - **INFERRED_RISKY** — extrapolation beyond the profile bank (new numbers, scope, outcomes).
   - **UNSUPPORTED** — no basis in the profile bank, or cited source does not support it.
   - **RULE_VIOLATION** — violates a standing rule.

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
| **BLOCKER** | UNSUPPORTED claim, RULE_VIOLATION, fabricated number/metric/team-size/scope, any `verify.blockers` check firing, framing violation, conditional-mention violation, language mismatch |
| **WARNING** | INFERRED_RISKY, tense ambiguity, tone mismatch with JD seniority, a banned phrase (`profile_bank.humanize.banned_phrases*`) |
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
  "flags": [
    {
      "severity": "blocker | warning | nit",
      "category": "unsupported_claim | rule_violation | tense_violation | fabricated_metric | banned_term | banned_phrase | framing_violation | conditional_mention_violation | language_mismatch | tone",
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
- `pass_with_warnings`: zero blockers, ≥1 warning
- `fail`: ≥1 blocker

`fail` is a hard stop — write the report and halt. The pipeline does not advance to "ready" until blockers are resolved.

## Standalone invocation

Invoke standalone for re-verification after manual edits: `/jobhunter pro/verify`. Provide: JD text, profile-bank path, `{file_slug}_CV.tex` path, `{file_slug}_cover-letter.tex` path.
