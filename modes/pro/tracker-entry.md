# Sub-mode: pro/tracker-entry — Record the application in the tracker

Fires after confirmed submission. Records one application in whatever tracker the candidate configured. Successor of the old Notion-only entry mode.

## Resolution — machine paths and profile bank

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. The **profile bank** is `{DATA_DIR}/config/profile_bank.json` (fallback: repo `config/profile_bank.json`).

## Step 0 — Read tracker config from `profile.yml`

Read `config/profile.yml` `tracker:` block. Branch on `tracker.type`:

- **`markdown`** or **`dashboard`** → the entry is the `data/applications.md` row only (set to Applied by `apply.md` Step 2 via `set-status.mjs`). Do Steps 1–3, then the "applications.md row" section below. No Notion, no `tracker-links.tsv`.
- **`notion`** → follow Steps 1–5 (Notion flow). Use `tracker.notion.applications_db_id` as the database id and `tracker.notion.data_source_id` as the data source wherever an id is needed. Never hardcode ids in this mode.
- **`none`** (or the `tracker:` block / `tracker.type` is absent) → same as `markdown`: skip the Notion flow, do Steps 1–3, then the "applications.md row" section below. Done.
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

### applications.md row (`markdown` / `dashboard` / `none` / obsidian fallback)

The row normally exists already and is `Applied` (`apply.md` Step 2 ran `node set-status.mjs <#> Applied`). Never hand-edit the table and never append a second row for the same opening. Record the extra fields as a note on that row:

```bash
node set-status.mjs <tracker#> Applied --note "{City}, {Country} {zip} · ATS {platform} · pkg output/{folder}"
```

If no row exists (apply started outside the pipeline), add it through a tracker-additions TSV + `node merge-tracker.mjs` (see AGENTS.md "TSV Format for Tracker Additions"), then run the command above. Then stop — Steps 4–5 apply only to the Notion flow.

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

**Page body** — use `notion-update-page` with `insert_content` after creation. This covers the header/role/framing sections only — **do NOT paste the Job Description or upload PDFs yourself**, that is Step 4b below:

```markdown
## {Company} — {Role title}
**Score:** {X.X}/5 — Applied {YYYY-MM-DD}
**ATS:** {Platform}
**URL:** [{job posting URL}]({job posting URL})

## Role
{1–2 paragraph role summary from report}

## CV framing
{bullets showing which experiences map to this role}

## Key gaps
{bullets listing gaps and mitigations}

## Comp
{comp analysis from report if available}
```

If the report does not exist (apply started without pipeline context), omit Role / CV framing / Key gaps / Comp and write only the header.

---

## Step 4b — Attach PDFs + verbatim JD (Notion flow only)

The agent never pastes or summarizes JD text into the page; the JD goes in as a file, byte for byte. PDFs are real file attachments, never external links or local paths.

**Primary route: Notion MCP file upload** (works without any token). For each of `{output_folder}/{file_slug}_CV.pdf`, `{output_folder}/{file_slug}_cover-letter.pdf` and `{output_folder}/jd.txt` (write the full JD verbatim to `jd.txt` first if it is not already there):

1. `notion-create-file-upload` with `filename` = the file's basename (omit `content_type`; it is inferred from the extension).
2. POST the bytes once to the returned `upload_url`, with every header from `upload_headers`:
   ```bash
   curl -sS -X POST "<upload_url>" -H "<each upload_headers entry>" -F "file=@{path}"
   ```
3. `notion-update-page` on the Step 4 page, inserting the returned `suggested_markdown` / `markdown_source` (e.g. `<pdf src="file-upload://<id>"></pdf>`): both PDFs under a `## Documents` heading, `jd.txt` under `## Job Description`.
4. `notion-fetch` the page and confirm three attachments are present. Any step failing = Step 5.

**Optional route: `notion_finalize.py`**, only when `NOTION_ACCESS_TOKEN` is set in `career-ops/.env` (never set one up without asking the user). It uploads both PDFs and pastes the JD as text blocks, then prints PASS/FAIL:

```bash
{PYTHON} notion_finalize.py <page_url> --jd {output_folder}/jd.txt --cv {output_folder}/{file_slug}_CV.pdf --cl {output_folder}/{file_slug}_cover-letter.pdf
```

A non-zero exit falls back to the MCP route above, not to Step 5.

### Step 4c — Record the link (Notion flow only, mandatory)

After the page exists and the PDFs are attached, append one line to `data/tracker-links.tsv` (create the file if missing, no header):

```bash
printf '%s\t%s\t%s\t%s\n' "<tracker#>" "<Company>" "<page_url>" "$(date +%F)" >> data/tracker-links.tsv
```

`<tracker#>` is the `applications.md` row number (the `#` passed to `set-status.mjs`), not a report number. `<page_url>` is the page URL from Step 4; the Stop hook (`.claude/hooks/notion-gate.mjs`) accepts `https://www.notion.so/…` and `https://app.notion.com/…` forms. Without this line the hook blocks the end of the turn for every row set to Applied this session.

---

## Step 5 — Handle failures (Notion flow only)

**If the Notion MCP is unreachable** (tools not loaded, OAuth expired, a call fails after one retry), tell the user explicitly, in plain words, which step failed, the error, and what is still missing (page / PDFs / JD / `tracker-links.tsv` line). Do not end the turn as if the application were recorded, and do not substitute a "paste this block" printout for the entry. The Stop hook will block the turn anyway while a row set to Applied has no `tracker-links.tsv` line; resolving that means either completing the entry once Notion is back or the user deciding otherwise.

---

## Rules

- **Name is company only.** Never "Company — Role" or "Company - Position". The Position field holds the role title.
- **Job description goes in the page body, not the property field** (the property truncates at ~2000 chars), as the verbatim `jd.txt` attachment (MCP route) or the script's text blocks (`notion_finalize.py`) — the agent never pastes or summarizes JD text into the page itself.
- **PDFs are uploaded as real files** in Step 4b (MCP file upload, or `notion_finalize.py` when a token exists), never as external links and never as a pasted local folder path.
- **Every Notion entry ends with its `data/tracker-links.tsv` line** (Step 4c): `<tracker#>\t<Company>\t<page_url>\t<YYYY-MM-DD>`. The Stop hook checks it.
- **Status goes through `set-status.mjs`**, never a hand edit of `data/applications.md`.
- **Location has no modifiers.** `{City}, {Country}` only — never "hybrid", "remote", "on-site", or parentheses.
- **Zipcode is mandatory** when `address_lookup.zip_mandatory` — always run the lookup; never skip because it seems minor.
- **Match Score is a decimal from the report, or blank.** Never convert a letter grade to a number.
- **Never fill Expected Salary** unless the form explicitly asked and a specific number was submitted. Store it verbatim (ranges OK); never fabricate a midpoint. Never fill Salary Currency unless Expected Salary is set.
- **Never write local file paths** into the CV / Cover Letter URL properties — those expect URLs; attachments live in the page body (Step 4b).
- **RAV Disclosed is always `__NO__`.**
- **One entry per submission.** If the candidate resubmits after a form error, create a second entry.
