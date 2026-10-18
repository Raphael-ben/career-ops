# Mode: pro/apply — Extension Application Assistant

Guides a Workday application using the Career-ops side panel in Brave. The panel fills form fields from the package's `apply.json`; this mode finds that file and walks the candidate through the steps. No answers are generated here and nothing is polled.

**NEVER suggest clicking Submit.** Stop before final submission — the candidate makes the final call.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). All personal form values come from `profile_bank.candidate.contact` — this mode holds no personal literals.

---

## Step 0 — Find the package

**Pre-flight: verify not already applied.** Per the Notion-first already-applied rule in `modes/_custom.md`, check the Notion JOB OP database for this exact company + role before filling anything. If a Notion entry already shows Applied/Interview/Offer/Rejected, stop and surface that entry and its status instead of proceeding with the form.

Find the package folder for this company + role in `output/` (`output/<Company>/<YYYYMMDD_Company_Role>/`). If `apply.json` is missing or older than the CV `.tex`, regenerate it:

```bash
node apply-data.mjs output/<Company>/<folder> {DATA_DIR}/config/profile_bank.json
```

If it exits 1 (no CV `.tex`, or a company name the bank cannot match), stop and report the stderr line.

---

## Step 1 — Walk the candidate through the form

Tell the candidate:

1. Open the Workday step in Brave and open the Career-ops panel.
2. Pick the package folder in the panel.
3. Press "Fill this step". The panel fills what it can and reports what it left: type those fields yourself, or press "Ask Haiku" next to a field for a draft answer.
4. Check the page, then press Save and Continue yourself.
5. Repeat on the My Experience step (work and education blocks are filled from `apply.json`).

Other steps and non-Workday forms are typed by hand. Never click Submit for the candidate.

---

## Step 2 — Post-apply

When the candidate confirms submission:

1. Update status in `career-ops/data/applications.md` from "Evaluated" to "Applied"
2. Update Section G of the report with the final responses used
3. Create the application-tracker entry — read and follow `career-ops/modes/pro/tracker-entry.md` exactly
4. Suggest: `/jobhunter contact` for LinkedIn outreach
