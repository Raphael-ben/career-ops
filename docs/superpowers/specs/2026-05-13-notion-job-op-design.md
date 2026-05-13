# Notion Job Op Auto-Entry — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Automatically create a Notion Job Op database entry at the end of each successful application submission (apply.md Step 6), including file uploads for CV and CL PDFs and substantive Q&A answers in the page body.

**Constraint:** No quality change to any existing step. Notion entry creation is additive — it extends Step 6 without altering Steps 1–5 or the existing Step 6 tracker/report updates.

**Activation:** Fires whenever the candidate confirms submission in apply.md Step 6. Gracefully degrades if Notion MCP is unavailable.

---

## Section 1 — Problem

After each application submission, the candidate must manually create a Notion Job Op entry: copy/paste fields, upload CV and CL PDFs, and record motivational Q&A answers. This costs 5–10 minutes per application and is often skipped, leaving the Notion tracker stale.

---

## Section 2 — Architecture

### Trigger point

apply.md Step 6 ("Post-apply"), which already fires on submission confirmation. The Notion entry creation is appended as a new sub-step after the existing tracker and Section G updates.

### Execution flow

```
apply.md Step 6 (post-submission confirmation):
  [existing] 1. Update applications.md status → Applied
  [existing] 2. Update Section G with final responses
  [existing] 3. Suggest /jobhunter contact
  [new]      4. Create Notion Job Op entry
               a. Collect field values (see Section 3)
               b. Collect substantive Q&A from Step 5 output
               c. Call Notion MCP: create page with properties
               d. Upload CV PDF and CL PDF to file properties
               e. Append Q&A blocks to page body (if any)
               f. On any MCP failure: print fallback block
```

### Notion database

- **Database ID:** `5f2ad32d02bd4930b66c97006f2661ae`
- **MCP endpoint:** configured in `~/.claude.json` as `https://mcp.notion.com/mcp` (requires OAuth per session)

---

## Section 3 — Field Mapping

| Notion property | Value source | Type |
|---|---|---|
| **Name** | `{Company} — {Role}` | title |
| **Position** | Role title from report | text |
| **ATS Platform** | Detected from form URL (Workday, Greenhouse, Lever, Ashby, join.com, etc.) | select |
| **Application date** | Today (YYYY-MM-DD) | date |
| **URL** | Job posting URL (from report or Step 1 detection) | url |
| **Status** | `Applied` | select |
| **Match Score** | Score from report, format `X.X/5` | text |
| **Location** | Location from report/JD | text |
| **CV** | Upload PDF from `output/{folder}/{cv-filename}.pdf` | files |
| **Cover Letter** | Upload PDF from `output/{folder}/{cl-filename}.pdf` | files |

Fields left blank if data unavailable: Available From, Current Salary, Expected Salary, Rejection date, Rejection reason, Episode.

### ATS platform detection rules

| URL pattern | ATS Platform value |
|---|---|
| `workday.com` | `Workday` |
| `greenhouse.io` | `Greenhouse` |
| `lever.co` | `Lever` |
| `ashbyhq.com` | `Ashby` |
| `join.com` | `join.com` |
| `smartrecruiters.com` | `SmartRecruiters` |
| `jobvite.com` | `Jobvite` |
| other / unknown | `Other` |

---

## Section 4 — Page Body: Substantive Q&A

If the candidate answered any substantive free-text questions in Step 5, append them to the page body in this format:

```markdown
## Application Questions

### {Exact question text}
{Answer text}

### {Next question}
{Answer text}
```

**Substantive questions** = open-text motivational or competency questions:
- "Why do you want to work at {Company}?"
- "What makes you a good fit for this role?"
- "Describe a time when…"
- "What is your leadership style?"
- Cover letter or motivation letter fields

**Excluded** (do not capture):
- Dropdowns: work authorization, relocation willingness, how did you hear, visa status
- Yes/No: current employment, right to work
- Salary/numeric fields
- Upload fields

If there are no substantive questions, the page body is left empty.

---

## Section 5 — Output Folder Resolution

The CV and CL PDFs live in `career-ops/output/{folder}/`. The folder is set during the pipeline run (Steps 4a/4b) and is available in the report or from the context loaded in apply.md Step 2.

File naming conventions (from write-cv and write-cl modes):
- CV: `{company-slug}-{role-slug}-{YYYY-MM-DD}.pdf` (or `.tex`/`.md` variant)
- CL: `{company-slug}-{role-slug}-cl-{YYYY-MM-DD}.pdf`

If multiple PDFs exist in the folder (e.g., multiple revisions), use the most recently modified one.

If the output folder cannot be resolved (e.g., apply.md was started without pipeline context), skip the file upload and note it in the fallback block.

---

## Section 6 — Fallback

If the Notion MCP is unavailable (tools not loaded, OAuth expired, network error, or any tool call fails), print this block instead of failing silently:

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

If there are substantive Q&A answers, append them below the block in the same format as Section 4.

The fallback block is printed and the Step 6 flow continues normally — it does not block the tracker update or Section G update.

---

## Section 7 — Edge Cases

- **No output folder:** File upload skipped. Note in fallback: "CV/CL not found — upload manually."
- **Report not loaded (apply.md started without pipeline context):** Score and location left blank. Name derived from Step 2 detection.
- **Duplicate entry:** Notion does not enforce uniqueness by URL. If the candidate resubmits (e.g., after fixing a form error), a second entry is created. The candidate is responsible for deduplication in Notion.
- **MCP OAuth expired:** Treat as MCP unavailable → print fallback block. Remind user to re-authenticate Notion MCP at session start.
- **Partial MCP failure (page created but file upload fails):** Log which uploads failed, print the file paths so user can upload manually from Notion.
- **Notion MCP file upload not supported:** The official Notion MCP may only support `external` URL file references, not binary uploads. If binary upload is unavailable, leave the CV/CL properties empty and append the local file paths in the page body (e.g., `CV: career-ops/output/{folder}/{file}.pdf`) so the user can drag-upload them from Finder.

---

## Data Contract

| File | Change | Layer |
|---|---|---|
| `modes/apply.md` | Modified — Step 6 extended with Notion sub-step | System |
| `config/profile.yml` | No change | User |
| Notion database `5f2ad32d...` | New pages created at submission time | External |
