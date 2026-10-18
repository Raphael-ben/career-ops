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

1. One-time setup: open `brave://extensions`, turn on Developer mode, remove the old "Claude Apply Assistant", and Load unpacked from `career-ops/extension/`.
2. One-time setup: paste the Anthropic API key under the panel's Settings. Never paste it in chat or in files.
3. Open the Workday step in Brave and open the Career-ops panel.
4. Pick the package folder in the panel. If the folder picker misbehaves, use "Or pick files" and select the package files instead.
5. Press "Fill this step". The panel fills what it can and reports what it left: type those fields yourself. For an unmatched dropdown or search result (Degree, Field of Study, Skills), "Ask Haiku" only picks one of the page's own options; it never writes answers.
6. Check the page, then press Save and Continue yourself.
7. Repeat on the My Experience step (work and education blocks are filled from `apply.json`).

Other steps and non-Workday forms are typed by hand. Never click Submit for the candidate.

---

## Step 2 — Post-apply

When the candidate confirms submission:

1. Update status in `career-ops/data/applications.md` from "Evaluated" to "Applied"
2. Create the application-tracker entry — read and follow `career-ops/modes/pro/tracker-entry.md` exactly; the tracker note records the package folder used
3. Suggest: `/jobhunter contact` for LinkedIn outreach
