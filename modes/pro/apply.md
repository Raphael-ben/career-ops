# Mode: pro/apply — Extension Application Assistant

Handles job application form filling via the browser extension + HTTP bridge. The extension sends form fields; this mode generates answers and writes the response. The candidate reviews answers in the sidebar before anything is injected.

**NEVER suggest clicking Submit.** Stop before final submission — the candidate makes the final call.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`). All personal form values come from `profile_bank.candidate.contact` — this mode holds no personal literals.

---

## Step 0 — Start bridge server

```bash
node career-ops/bridge-server.mjs &
```

Confirm: "Bridge server listening on http://localhost:7823". Tell the candidate: "Open the application form in your browser and click the extension icon to open the side panel."

---

## Step 1 — Request loop

Watch for `career-ops/data/fill-request.json`. When it appears:

### 1a — Load job context

Read the `url` field. Extract company name and role title from the URL and any recognisable ATS path patterns (e.g. `greenhouse.io/company`, `ashby.com/company/role`).

Search `career-ops/reports/` for a matching report:
```bash
grep -ri "{company}" career-ops/reports/ -l
```
If found → load the full report; if Section G exists → load previous draft answers as base. If not found → generate answers from `career-ops/cv.md` alone, and note in each answer: "(no report — based on CV only)".

### 1b — Classify and answer each field

For each field in fill-request.json `fields` array, apply this classification:

**Personal fields → `action: fill` from `profile_bank.candidate.contact`:**

| Label signal | Value (from profile bank) |
|---|---|
| first / given name | first token of `candidate.name` |
| last / family / surname | remaining tokens of `candidate.name` |
| email | `candidate.contact.email` |
| phone / mobile | `candidate.contact.phone` |
| address / street | `candidate.contact.address` (street portion) |
| city | `candidate.contact.city` |
| zip / postal | `candidate.contact.zip` |
| country | `candidate.contact.country` |
| linkedin | `candidate.contact.linkedin` if present |
| work authorization / right to work / visa | `candidate.contact.work_authorization` (verbatim) |

**Substantive free-text fields → generate then humanize:**

Signals: `type=textarea`, or label contains "why", "motivation", "tell us", "describe", "cover letter", "additional information", "what interests you", "passion", "fit", or any open-ended question.

Generate the response from report context (proof points block B, STAR stories block F, Section G if it exists). Then dispatch the humanizer subagent:

> Read `career-ops/modes/pro/humanize.md` and apply its vocabulary and style rules (and the `profile_bank.humanize.*` ban lists) to this plain-text response. Ignore any LaTeX-specific instructions. Return only the improved text.

Use the humanized text as the answer.

**Checkboxes → `action: fill`:**

- "I currently work here" for the current role → `true` only if that role's `experience[].end_status` is `current_indefinite` or `contract_ending` (and its end is on/after today). Otherwise leave it unchecked.
- All other checkboxes without a clear profile match → `action: skip`, `note: "check manually"`.

**Skip fields → `action: skip` with note and suggested value:**

- Dropdowns / selects → `note: "select manually"`, `answer: "{suggested option from profile}"`
- File uploads → `note: "upload manually"`, `answer: "career-ops/output/{folder}/{filename}.pdf"` (search output/ for the most recent matching folder)
- Salary fields → `note: "fill manually"`, `answer: "{target from config/profile.yml if present}"`
- CAPTCHA / SSO buttons → `note: "complete manually"`

**Action buttons (type=action_button) → `action: click` or `action: skip`:**

"Add Work Experience", "Add Education", "Add Another", "+" buttons that reveal repeating blocks. For each:
1. Identify what section it expands.
2. Count how many blocks of that type are already visible (repeated field groups).
3. Compare to how many entries to fill: work experience = number of `experience[]` entries selected per the CV assembly rules; education = number of `education[]` entries; other sections = match to cv.md content.
4. If `existing blocks < needed entries` → `action: click`. If `existing blocks >= needed entries` → `action: skip, note: "enough blocks"`.

The extension polls every 1.5s after a click — each cycle only sends NEW (empty) fields. Fill each new block's fields and re-evaluate the button. Never click Submit/Save/Next buttons.

### 1c — Write response

Write `career-ops/data/fill-response.json`. Each entry MUST use the keys `id`, `label`, `answer`, `action` (and optional `note`) — never `answers`/`value`:

```json
{
  "fields": [
    { "id": "field-123", "label": "First name", "answer": "<first name>", "action": "fill" },
    { "id": "field-456", "label": "Why us?", "answer": "humanized…", "action": "fill" },
    { "id": "field-789", "label": "CV upload", "answer": "career-ops/output/…/cv.pdf", "action": "skip", "note": "upload manually" }
  ]
}
```

### 1d — Loop

Delete `career-ops/data/fill-request.json`. Wait for the next request. The extension polls every 1.5s and auto-sends new fields as they appear. You do not need to prompt the candidate between cycles.

---

## Step 2 — Post-apply

When the candidate confirms submission:

1. Update status in `career-ops/data/applications.md` from "Evaluated" to "Applied"
2. Update Section G of the report with the final responses used
3. Create the application-tracker entry — read and follow `career-ops/modes/pro/tracker-entry.md` exactly
4. Suggest: `/jobhunter contact` for LinkedIn outreach
5. Stop bridge server: `kill %1` (or `pkill -f bridge-server.mjs`)
