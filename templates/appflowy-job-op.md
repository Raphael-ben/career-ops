# AppFlowy tracker (JOB OP grid)

[AppFlowy](https://appflowy.io) is a local, open-source Notion alternative. There is no live sync: `data/applications.md` stays the tracker of record, and AppFlowy is a view you fill or refresh from it.

## Set up

1. Install AppFlowy desktop (appflowy.io) and create a workspace.
2. Copy `templates/appflowy-job-op.csv` somewhere you can pick it (onboarding copies it to `{DATA_DIR}/appflowy-job-op.csv`).
3. New page, then Grid. Look for **Import** in the page or space menu (the exact label varies by version): "... → Import → CSV", and choose the file. The import creates every column as a text field and keeps the example row.
4. Set each field's type and options (below). Delete the Acme example row once you have your own.

| Column | Type | Options |
|---|---|---|
| Name | Text (primary) | Company only |
| Position | Text | Role title |
| Status | Single select | To apply, In progress, Applied, Interview, Rejected, No Answer |
| Application date | Date | |
| first answer date | Date | |
| First ITW | Date | First interview |
| Rejection date | Date | |
| Available From | Date | Your start date |
| URL | URL | Job posting |
| Location | Text | |
| Zipcode | Text | |
| ATS Platform | Single select | Workday, Greenhouse, Lever, SAP, Teamtailor, Direct, Other |
| Match Score | Number | e.g. 4.2 (out of 5) |
| Expected Salary | Text | Exactly as you wrote it, ranges allowed |
| Salary Currency | Single select | CHF, EUR, USD, GBP, Other |
| Current Salary | Number | Optional, private |
| CV | URL | Local path to the generated PDF |
| Cover Letter | URL | Local path to the generated PDF |
| Job description | Text | |
| Rejection reason | Text | |
| RAV Disclosed | Checkbox | Swiss unemployment-office disclosure; the CSV holds Yes/No, tick it by hand |

Name is the company only, never "Company - Role"; the role goes in Position.

## Status meaning

- To apply: evaluated, not applied yet.
- In progress: the employer answered (or an offer is pending), no interview yet.
- Applied: submitted.
- Interview: at least one interview scheduled or done.
- Rejected: the employer said no.
- No Answer: silence after a follow-up; set it by hand (the tracker has no equivalent).

## Add a row after applying

When you mark a job Applied, the assistant prints one CSV line and a list of property values. Add a grid row and paste the values, or paste the CSV line into the grid's first cell if your version splits it into columns. It never writes to AppFlowy itself.

## Refresh in bulk

```bash
node tools/appflowy-export.mjs
```

This writes `data/appflowy/job-op.csv` from `data/applications.md`: Name, Position, Status, Application date, URL, Match Score and the newest CV / cover letter path per company. Evaluated maps to To apply; Responded and Offer map to In progress; Hired maps to Interview (no Hired option); Discarded and SKIP rows are left out. Salary, ATS, Zipcode and Job description stay empty. Re-import the CSV as a new grid (re-apply the field types), or paste rows into your existing grid. Re-importing does not merge; delete the old grid when you are done.

## Limits

No API sync, no two-way status updates. If you change a status in AppFlowy, change it in the tracker too (`node set-status.mjs <#> <Status>`).
