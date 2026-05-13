# Mode: apply — Live Application Assistant

Interactive mode for when the candidate is filling out an application form in Chrome. It reads what is on the screen, loads the previous context of the job, and generates personalized responses for each form question.

## Requirements

- **Best with Playwright in visible mode**: In visible mode, the candidate sees the browser and Claude can interact with the page.
- **Without Playwright**: the candidate shares a screenshot or pastes the questions manually.

## Workflow

```text
1. DETECT      → Read active Chrome tab (screenshot/URL/title)
2. IDENTIFY    → Extract company + role from the page
3. SEARCH      → Match against existing reports in reports/
4. LOAD        → Read full report + Section G (if it exists)
5. COMPARE     → Does the role on screen match the one evaluated? If it changed → notify
6. ANALYZE     → Identify ALL visible form questions
7. GENERATE    → For each question, generate a personalized response
8. PRESENT     → Show formatted responses for copy-paste
```

## Step 1 — Detect the job

**With Playwright:** Take a snapshot of the active page. Read title, URL, and visible content.

**Without Playwright:** Ask the candidate to:
- Share a screenshot of the form (Read tool can read images)
- Or paste the form questions as text
- Or say company + role so we can search for it

## Step 2 — Identify and search for context

1. Extract company name and role title from the page
2. Search in `reports/` by company name (case-insensitive grep)
3. If there is a match → load the full report
4. If there is a Section G → load previous draft answers as a base
5. If there is NO match → notify and offer to run a quick auto-pipeline

## Step 3 — Detect changes in the role

If the role on screen differs from the one evaluated:
- **Notify the candidate**: "The role has changed from [X] to [Y]. Do you want me to re-evaluate or adapt the responses to the new title?"
- **If adapt**: Adjust responses to the new role without re-evaluating
- **If re-evaluate**: Execute full A-F evaluation, update report, regenerate Section G
- **Update tracker**: Change role title in applications.md if applicable

## Step 4 — Analyze form questions

Identify ALL visible questions:
- Free text fields (cover letter, why this role, etc.)
- Dropdowns (how did you hear, work authorization, etc.)
- Yes/No (relocation, visa, etc.)
- Salary fields (range, expectation)
- Upload fields (resume, cover letter PDF)

Classify each question:
- **Already answered in Section G** → adapt the existing response
- **New question** → generate response from the report + cv.md

## Step 5 — Generate responses

For each question, generate the response following:

1. **Report context**: Use proof points from block B, STAR stories from block F
2. **Previous Section G**: If a draft response exists, use it as a base and refine
3. **"I'm choosing you" tone**: Same auto-pipeline framework
4. **Specificity**: Reference something specific from the JD visible on screen
5. **career-ops proof point**: Include in "Additional info" if there is a field for it

**Output format:**

```text
## Responses for [Company] — [Role]

Based on: Report #NNN | Score: X.X/5 | Archetype: [type]

---

### 1. [Exact form question]
> [Response ready for copy-paste]

### 2. [Next question]
> [Response]

...

---

Notes:
- [Any observations about the role, changes, etc.]
- [Personalization suggestions the candidate should review]
```

## Step 6 — Post-apply (optional)

If the candidate confirms that they submitted the application:
1. Update status in `applications.md` from "Evaluated" to "Applied"
2. Update Section G of the report with the final responses
3. Suggest next step: `/jobhunter contact` for LinkedIn outreach
4. Create Notion Job Op entry (Step 6.4 below)

### Step 6.4 — Notion Job Op entry

**Collect field values from session context:**

| Field | Source |
|---|---|
| Name | `{Company} — {Role}` |
| Position | Role title from Step 2 |
| ATS Platform | Detected from form URL (see table below) |
| Application date | Today (YYYY-MM-DD) |
| URL | Job posting URL from Step 1 |
| Status | `Applied` |
| Match Score | Score from loaded report, format `X.X/5`; blank if report not loaded |
| Location | Location from loaded report; blank if report not loaded |

**ATS platform detection — map URL to select value:**

| URL contains | Platform |
|---|---|
| `workday.com` | `Workday` |
| `greenhouse.io` | `Greenhouse` |
| `lever.co` | `Lever` |
| `ashbyhq.com` | `Ashby` |
| `join.com` | `join.com` |
| `smartrecruiters.com` | `SmartRecruiters` |
| `jobvite.com` | `Jobvite` |
| anything else | `Other` |

**Resolve output folder and PDF paths:**

Run `ls -t career-ops/output/` (from the repo root) and find the folder whose name contains the company slug (lowercase, spaces to hyphens). Take the most recently modified match.

Inside that folder:
- CV PDF: the `.pdf` file whose name does NOT end in `-cl-YYYY-MM-DD.pdf`
- CL PDF: the `.pdf` file whose name ends in `-cl-YYYY-MM-DD.pdf`

If no matching PDF is found for CV or CL, set that path to `""` and note it in the fallback block.

If no output folder matches, set both PDF paths to `""` (upload skipped, handled in fallback).

**Create the Notion page:**

Call the Notion MCP `create_page` tool with:
```json
{
  "parent": { "database_id": "5f2ad32d02bd4930b66c97006f2661ae" },
  "properties": {
    "Name": { "title": [{ "text": { "content": "{Company} — {Role}" } }] },
    "Position": { "rich_text": [{ "text": { "content": "{Role}" } }] },
    "ATS Platform": { "select": { "name": "{Platform}" } },
    "Application date": { "date": { "start": "{YYYY-MM-DD}" } },
    "URL": { "url": "{job-url}" },
    "Status": { "select": { "name": "Applied" } },
    "Match Score": { "rich_text": [{ "text": { "content": "{X.X/5 or blank}" } }] },
    "Location": { "rich_text": [{ "text": { "content": "{location or blank}" } }] }
  }
}
```

Save the returned `page_id` for the next calls.

**Upload CV and CL PDFs:**

If a Notion MCP file-upload tool is available (e.g. `upload_file`, `create_file`), call it for each PDF and attach the result to the CV / Cover Letter properties of the page.

If no file-upload tool is available, skip the property upload and add the local paths to the page body (handled in the Q&A block below).

If the upload tool is available but the upload call fails for CV or CL, log the failure inline and add the local path to the page body for that file:
```
⚠ CV upload failed — attach manually: career-ops/output/{folder}/{cv-filename}.pdf
⚠ CL upload failed — attach manually: career-ops/output/{folder}/{cl-filename}.pdf
```
Continue to the Q&A step regardless of upload outcome.

**Append Q&A and file paths to page body:**

From Step 5 output, collect responses to **substantive free-text questions only**: motivational questions, "why this company", competency / situation questions, cover letter fields.

**Exclude**: work authorization, relocation, visa, how-did-you-hear, salary, yes/no, and any other dropdown or numeric field.

If file upload was not possible (tool unavailable), prepend these lines to the body content:
```
CV:  career-ops/output/{folder}/{cv-filename}.pdf
CL:  career-ops/output/{folder}/{cl-filename}.pdf
```

Call `append_block_children` with the page_id:
```json
{
  "block_id": "{page_id}",
  "children": [
    {
      "type": "heading_2",
      "heading_2": { "rich_text": [{ "text": { "content": "Application Questions" } }] }
    },
    {
      "type": "heading_3",
      "heading_3": { "rich_text": [{ "text": { "content": "{Exact question text}" } }] }
    },
    {
      "type": "paragraph",
      "paragraph": { "rich_text": [{ "text": { "content": "{Answer text}" } }] }
    }
  ]
}
```

Repeat the heading_3 + paragraph pair for each substantive question.

- If file upload succeeded AND there are no substantive questions: skip the `append_block_children` call entirely.
- If file upload was not possible (local paths need to be written to the page body): always call `append_block_children`, even if there are no substantive Q&A answers, so the file paths are recorded.

**On any failure (MCP unavailable, OAuth expired, tool error, page creation fails):**

Do NOT stop Step 6. Print this block and continue:

```
──────────────────────────────────────────────
NOTION ENTRY — paste into Job Op database
──────────────────────────────────────────────
Name:         {Company} — {Role}
Position:     {Role}
ATS:          {Platform}
Applied:      {YYYY-MM-DD}
URL:          {url}
Match Score:  {X.X/5}
Location:     {location}
CV PDF:       career-ops/output/{folder}/{cv-filename}.pdf
CL PDF:       career-ops/output/{folder}/{cl-filename}.pdf
──────────────────────────────────────────────
```

If there are substantive Q&A answers, append them below the separator block in this format:
```
Q: {question}
A: {answer}
```

## Scroll handling

If the form has more questions than the visible ones:
- Ask the candidate to scroll and share another screenshot
- Or paste the remaining questions
- Process in iterations until the entire form is covered
