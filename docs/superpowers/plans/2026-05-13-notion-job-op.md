# Notion Job Op Auto-Entry Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `modes/apply.md` Step 6 to automatically create a Notion Job Op entry on submission confirmation, uploading CV/CL PDFs and recording substantive Q&A answers.

**Architecture:** Single markdown mode file edit — Step 6 gains a new sub-step (6.4) with field collection, Notion MCP calls, and a printed fallback block. No new files, no code changes outside apply.md.

**Tech Stack:** Notion MCP (`mcp.notion.com/mcp`), markdown

---

## File Structure

| File | Change |
|---|---|
| `career-ops/modes/apply.md` | Modify lines 95–101: extend Step 6 with sub-step 6.4 |

---

## Task 1: Extend apply.md Step 6 with Notion entry creation

**Files:**
- Modify: `career-ops/modes/apply.md` (lines 95–101)

This task has no automated tests — it is a prompt-file edit. Verification is done by reading the result and checking it for completeness.

- [ ] **Step 1: Read the current Step 6**

Run:
```bash
sed -n '95,101p' career-ops/modes/apply.md
```

Expected output:
```
## Step 6 — Post-apply (optional)

If the candidate confirms that they submitted the application:
1. Update status in `applications.md` from "Evaluated" to "Applied"
2. Update Section G of the report with the final responses
3. Suggest next step: `/jobhunter contact` for LinkedIn outreach
```

- [ ] **Step 2: Replace Step 6 with the extended version**

Replace lines 95–101 with this exact content (everything up to but not including `## Scroll handling`):

```markdown
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

Run `ls -t career-ops/output/` and find the folder whose name contains the company slug (lowercase, spaces to hyphens). Take the most recently modified match.

Inside that folder:
- CV PDF: the `.pdf` file whose name does NOT end in `-cl-YYYY-MM-DD.pdf`
- CL PDF: the `.pdf` file whose name ends in `-cl-YYYY-MM-DD.pdf`

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

Repeat the heading_3 + paragraph pair for each substantive question. If there are no substantive questions and file upload succeeded, skip the `append_block_children` call entirely.

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
```

- [ ] **Step 3: Verify the edit**

Run:
```bash
grep -n "Step 6" career-ops/modes/apply.md
```

Expected: lines for `## Step 6`, `### Step 6.4`, and the `## Scroll handling` section still present below.

Then run:
```bash
grep -c "5f2ad32d02bd4930b66c97006f2661ae" career-ops/modes/apply.md
```

Expected: `1`

- [ ] **Step 4: Commit**

```bash
cd career-ops
git add modes/apply.md
git commit -m "feat: auto-create Notion Job Op entry on application submission

Extends apply.md Step 6 with sub-step 6.4: collects field values from
session context, calls Notion MCP to create a page in the Job Op
database, uploads CV/CL PDFs, appends substantive Q&A to page body.
Graceful fallback printed when Notion MCP is unavailable.

Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
```
