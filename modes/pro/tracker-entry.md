# Sub-mode: pro/tracker-entry — Record the application in the tracker

Fires after confirmed submission. Records one application in whatever tracker the candidate configured. Successor of the old Notion-only entry mode.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`).

## Step 0 — Read tracker config from `profile.yml`

Read `config/profile.yml` `tracker:` block. Branch on `tracker.type`:

- **`notion`** → follow Steps 1–5 (Notion flow). Use `tracker.notion.applications_db_id` as the database id and `tracker.notion.data_source_id` as the data source wherever an id is needed. Never hardcode ids in this mode.
- **`none`** (or the `tracker:` block / `tracker.type` is absent) → skip the Notion flow. Do Steps 1–2 (collect fields + resolve zipcode), then append one row to `data/applications.md` (see "none: applications.md row" below). Done.
- **`obsidian`** → print `Obsidian tracker not implemented — see docs/TRACKERS.md` and fall back to the `none` flow.

---

## Step 1 — Collect field values

Gather from the current session context (report, JD, application):

| Field | Value to collect |
|---|---|
| Company | From report title or URL |
| Role title | Full job title from JD |
| Job posting URL | The URL from Step 1 of apply.md |
| Job description | Full JD text — see fetch procedure below |
| Location (city) | City name from JD |
| Match Score | Numeric score from report (e.g. `3.8`) |
| Expected Salary | Only if explicitly asked during the application AND a number was submitted |
| Salary Currency | Currency of expected salary if applicable (default `CHF` for Swiss roles) |
| Output folder | Path to the pipeline output folder |

### Job description — fetch procedure

**Primary:** use the full JD text already in session context (from the report or apply.md Step 1). Always preferred — no extra cost.

**Fallback — browserless Scrapling fetch if JD text is missing or incomplete** (NEVER PlaywrightFetcher/StealthyFetcher — browser automation is apply-flow only, see `modes/_custom.md`):

```bash
{PYTHON} -c "
from scrapling.fetchers import Fetcher
page = Fetcher().get('JOB_URL_HERE', impersonate='chrome')
print(page.get_all_text(ignore_tags=('script','style','nav','footer','header')))
" 2>/dev/null
```

Replace `JOB_URL_HERE` with the real URL. Copy stdout verbatim as the JD. (The `scrapling` MCP `get` tool is an equivalent alternative.) If both fail, keep the `## Job Description` section with a note: `(JD fetch failed — paste manually from {job posting URL})`.

---

## Step 2 — Resolve Zipcode (mandatory — do NOT skip)

**You may not proceed until Zipcode is resolved** (if `profile_bank.rules.address_lookup.zip_mandatory` is true).

If the full address is in the JD, extract the zip directly. Otherwise run a WebSearch, preferring the registries in `profile_bank.rules.address_lookup.registry_domains`:

> Search: `{Company name} {City} address postal code site:maps.google.com OR site:{registry_domain_1} OR site:{registry_domain_2}`

Fallback: `"{Company name}" "{City}" Postleitzahl` (DE) or `"{Company name}" "{City}" postal code` (EN).

Use the zip for the company's specific office/district if a street address is found; otherwise fall back to the city-centre code from `profile_bank.rules.address_lookup.city_centre_zips[<city>]`.

Leave Zipcode blank **only** if the city itself cannot be determined from the JD or company name.

---

### `none`: applications.md row

If `data/applications.md` does not exist, create it with this header:

```markdown
# Applications Tracker

| # | Date | Company | Role | Score | Status | PDF | Report | Notes |
|---|------|---------|------|-------|--------|-----|--------|-------|
```

For `tracker.type: none`/absent/obsidian-fallback, append one row to `data/applications.md` capturing: Company, Role title, Status (`Applied`), Application date (today YYYY-MM-DD), Job posting URL, Location (`{City}, {Country}`, no modifiers), Zipcode (from Step 2), ATS Platform (Step 3 below), Match Score (decimal from report or blank), and the output-folder path. Match the existing format already in `data/applications.md`; if absent, create it with the canonical header above. Then stop — Steps 3–5 below apply only to the Notion flow (Step 3's ATS detection is still used to fill the ATS field here).

---

## Step 3 — Detect ATS Platform

Match the job posting URL to a platform:

| URL pattern | ATS Platform value |
|---|---|
| `workday.com` | `Workday` |
| `greenhouse.io` | `Greenhouse` |
| `lever.co` | `Lever` |
| `successfactors.com` or `jobs.sap.com` | `SAP` |
| `teamtailor.com` | `Teamtailor` |
| Company's own careers page (no ATS path) | `Direct` |
| Any other ATS (Ashby, SmartRecruiters, join.com, Jobvite…) | `Other` |

---

## Step 4 — Create Notion page (Notion flow only)

Call `notion-create-pages` with database id `tracker.notion.applications_db_id` (from profile.yml).

**Properties to set:**

```
Name:                     {Company}   ← company name only, no role title
Position:                 {Role title}
Status:                   Applied
date:Application date:start: {YYYY-MM-DD}  (today)
userDefined:URL:          {job posting URL}
Location:                 {City, Country}   ← no modifiers: no "hybrid", "remote", "(on-site)"
Zipcode:                  {zip — resolved in Step 2, never blank unless city unknown}
ATS Platform:             {Workday | Greenhouse | Lever | SAP | Teamtailor | Direct | Other}
Match Score:              {decimal from report header, e.g. 3.8; blank if report uses a letter grade only}
RAV Disclosed:            __NO__
```

> ⚠️ Do NOT set `Job description` as a property — Notion's rich_text property has a ~2000 character limit and silently truncates. The full JD goes in the page body.

Set only if explicitly captured during the application:
```
Expected Salary:          {number}
Salary Currency:          {CHF | EUR | USD | GBP | Other}
```

Leave blank (do not set): CV, Cover Letter, First ITW, Available From, Rejection date, Rejection reason, first answer date, Current Salary, Number of applications this month.

**Page body** — use `notion-update-page` with `insert_content` after creation. This is where the full JD lives:

```markdown
## {Company} — {Role title}
**Score:** {X.X}/5 — Applied {YYYY-MM-DD}
**ATS:** {Platform}
**URL:** [{job posting URL}]({job posting URL})

## Job Description
{Full JD text — every section verbatim: overview, responsibilities, qualifications, requirements, details. No summarising, no truncation.}

## Role
{1–2 paragraph role summary from report}

## CV framing
{bullets showing which experiences map to this role}

## Key gaps
{bullets listing gaps and mitigations}

## Comp
{comp analysis from report if available}

## PDFs
Upload from:
`career-ops/output/{folder}/`
```

If the report does not exist (apply started without pipeline context), omit Role / CV framing / Key gaps / Comp and write only the header, Job Description, and PDFs sections.

---

## Step 5 — Handle failures (Notion flow only)

**If Notion MCP is unavailable** (tools not loaded, OAuth expired, any call fails), print this fallback block instead:

```
──────────────────────────────────────────────
TRACKER ENTRY — paste into applications database
──────────────────────────────────────────────
Name:         {Company}
Position:     {Role title}
Status:       Applied
Applied:      {YYYY-MM-DD}
URL:          {job posting URL}
Job desc:     {JD summary}
Location:     {City}
Zipcode:      {zip or blank}
ATS:          {Platform}
Match Score:  {X.X}
──────────────────────────────────────────────
CV/CL: career-ops/output/{folder}/
```

If Expected Salary was captured, append: `Expected Salary: {amount} {currency}`. The fallback block does not block the rest of the post-apply flow.

---

## Rules

- **Name is company only.** Never "Company — Role" or "Company - Position". The Position field holds the role title.
- **Job description goes in the page body, not the property field** (the property truncates at ~2000 chars). Never summarise, never truncate the body copy.
- **Location has no modifiers.** `{City}, {Country}` only — never "hybrid", "remote", "on-site", or parentheses.
- **Zipcode is mandatory** when `address_lookup.zip_mandatory` — always run the lookup; never skip because it seems minor.
- **Match Score is a decimal from the report, or blank.** Never convert a letter grade to a number.
- **Never fill Expected Salary** unless the form explicitly asked and a specific number was submitted. Store it verbatim (ranges OK); never fabricate a midpoint. Never fill Salary Currency unless Expected Salary is set.
- **Never write local file paths** into the CV / Cover Letter URL properties — those expect URLs. Note the local path in the page body (PDFs section) instead; upload the PDFs rather than pasting a folder path.
- **RAV Disclosed is always `__NO__`.**
- **One entry per submission.** If the candidate resubmits after a form error, create a second entry.
