# Mode: scan — Portal Scanner

Scans configured job portals, filters by title relevance, and adds new offers to the pipeline for later evaluation.

> **Note (v1.5+):** The default scanner (`scan.mjs` / `npm run scan`) is **zero-token** and queries Greenhouse, Ashby, and Lever public APIs directly. The Playwright/WebSearch levels described below are the **agent** flow (run by Claude), not what `scan.mjs` does. If a company has no Greenhouse/Ashby/Lever API, `scan.mjs` will skip it — for those cases the agent must complete Level 1 (Playwright) or Level 3 (WebSearch) manually.

## Recommended execution

Run as a subagent to preserve the main context window:

```
Agent(
    subagent_type="general-purpose",
    prompt="[content of this file + invocation-specific data]",
    run_in_background=True
)
```

## Configuration

Read `portals.yml` which contains:
- `search_queries`: WebSearch queries with `site:` filters per portal (broad discovery)
- `tracked_companies`: Specific companies with `careers_url` for direct navigation
- `title_filter`: Positive/negative/seniority_boost keywords for title filtering

## Discovery strategy (4 levels)

### Level 1 — Direct Playwright (PRIMARY)

**For each company in `tracked_companies`:** Navigate to its `careers_url` with Playwright (`browser_navigate` + `browser_snapshot`), read ALL visible job listings, and extract title + URL from each. This is the most reliable method because:
- Reads the page in real time (no cached Google results)
- Works with SPAs (Ashby, Lever, Workday)
- Detects new offers instantly
- Does not depend on Google indexing

**Every company MUST have `careers_url` in portals.yml.** If missing, find it once, save it, and use it in future scans.

### Level 2 — ATS APIs / Feeds (COMPLEMENTARY)

For companies with a public API or structured feed, use the JSON/XML response as a fast complement to Level 1. Faster than Playwright and reduces visual scraping errors.

**Supported providers (`{}` = variable):**
- **Greenhouse**: `https://boards-api.greenhouse.io/v1/boards/{company}/jobs`
- **Ashby**: `https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams`
- **BambooHR**: list `https://{company}.bamboohr.com/careers/list`; detail `https://{company}.bamboohr.com/careers/{id}/detail`
- **Lever**: `https://api.lever.co/v0/postings/{company}?mode=json`
- **Teamtailor**: `https://{company}.teamtailor.com/jobs.rss`
- **Workday**: `https://{company}.{shard}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs`

**Parsing convention per provider:**
- `greenhouse`: `jobs[]` → `title`, `absolute_url`
- `ashby`: GraphQL `ApiJobBoardWithTeams` with `organizationHostedJobsPageName={company}` → `jobBoard.jobPostings[]` (`title`, `id`; build public URL if not in payload)
- `bamboohr`: list `result[]` → `jobOpeningName`, `id`; build detail URL `https://{company}.bamboohr.com/careers/{id}/detail`; to read full JD, GET the detail and use `result.jobOpening` (`jobOpeningName`, `description`, `datePosted`, `minimumExperience`, `compensation`, `jobOpeningShareUrl`)
- `lever`: root array `[]` → `text`, `hostedUrl` (fallback: `applyUrl`)
- `teamtailor`: RSS items → `title`, `link`
- `workday`: `jobPostings[]` → `title`, `externalPath` or URL constructed from host

### Level 3 — WebSearch queries (BROAD DISCOVERY)

`search_queries` with `site:` filters cover portals cross-sectionally (all Ashby, all Greenhouse, etc.). Useful for discovering NEW companies not yet in `tracked_companies`, but results may be stale.

### Level 4 — JobSpy (BROAD COVERAGE)

Scrapes LinkedIn, Indeed, Glassdoor, Google Jobs, ZipRecruiter, Bayt, and Naukri via
HTTP. Zero LLM tokens. Runs as a shell step inside the scan subagent.

**Prerequisites:** `python-jobspy` installed in `.venv` (`pip install python-jobspy`) or system-wide.
Search terms and location are read from the `jobspy:` block in `config/profile.yml`.

**Execute** (always run from the `career-ops/` directory):

```bash
# Prefer the project venv — it has python-jobspy installed
PYTHON=".venv/bin/python3"
[ -f "$PYTHON" ] || PYTHON="python3"
$PYTHON jobspy_scan.py
```

If `.venv/bin/python3` exists use it (it has `python-jobspy`). The script exits with `[]` and a clear error if the Python version is below 3.10.

Parse the JSON array from stdout. Each item has: `title`, `company`, `url`, `source`,
`location`, `date_posted`.

Add each item to the candidates list (dedup with Levels 1–3 by URL).

**If `jobspy_scan.py` fails or is not installed:** log a warning in the scan summary
and continue — Levels 1–3 results are still valid.

**Execution priority:**
1. Level 1: Playwright → all `tracked_companies` with `careers_url`
2. Level 2: API → all `tracked_companies` with `api:`
3. Level 3: WebSearch → all `search_queries` with `enabled: true`
4. Level 4: JobSpy → all `search_terms` from `config/profile.yml` jobspy block

All levels are additive — run all, mix and deduplicate results.

## Workflow

1. **Read configuration**: `portals.yml`
2. **Read history**: `data/scan-history.tsv` → already-seen URLs
3. **Read dedup sources**: `data/applications.md` + `data/pipeline.md`

4. **Level 1 — Playwright scan** (parallel in batches of 3–5):
   For each company in `tracked_companies` with `enabled: true` and `careers_url` defined:
   a. `browser_navigate` to the `careers_url`
   b. `browser_snapshot` to read all job listings
   c. If the page has department filters, navigate relevant sections
   d. For each job listing extract: `{title, url, company}`
   e. If paginated, navigate additional pages
   f. Accumulate in candidates list
   g. If `careers_url` fails (404, redirect), try `scan_query` as fallback and note for URL update

5. **Level 2 — ATS APIs / feeds** (parallel):
   For each company in `tracked_companies` with `api:` defined and `enabled: true`:
   a. WebFetch the API/feed URL
   b. If `api_provider` is defined, use its parser; otherwise infer from domain
   c. For **Ashby**, send POST with:
      - `operationName: ApiJobBoardWithTeams`
      - `variables.organizationHostedJobsPageName: {company}`
      - GraphQL query `jobBoardWithTeams` + `jobPostings { id title locationName employmentType compensationTierSummary }`
   d. For **BambooHR**, the list returns only basic metadata. For each relevant item, read `id`, GET `https://{company}.bamboohr.com/careers/{id}/detail`, extract full JD from `result.jobOpening`. Use `jobOpeningShareUrl` as public URL if available; otherwise use the detail URL.
   e. For **Workday**, send POST JSON with at least `{"appliedFacets":{},"limit":20,"offset":0,"searchText":""}` and paginate via `offset` until exhausted
   f. Normalize each extracted job: `{title, url, company}`
   g. Accumulate in candidates list (dedup with Level 1)

6. **Level 3 — WebSearch queries** (parallel where possible):
   For each query in `search_queries` with `enabled: true`:
   a. Execute WebSearch with the defined `query`
   b. Extract from each result: `{title, url, company}`
      - **title**: from result title (before " @ " or " | ")
      - **url**: result URL
      - **company**: after " @ " in title, or extracted from domain/path
   c. Accumulate in candidates list (dedup with Levels 1+2)

6.5. **Level 4 — JobSpy** (shell step):
   Run `python3 jobspy_scan.py` (reads `config/profile.yml` `jobspy:` block).
   a. If the script fails or is not installed: log warning in scan summary and continue
   b. From each item in the JSON array extract: `{title, company, url, source, location, date_posted}`
   c. Accumulate in candidates list (dedup with Levels 1+2+3 by URL)

7. **Filter by title** using `title_filter` from `portals.yml`:
   - At least 1 keyword from `positive` must appear in the title (case-insensitive)
   - 0 keywords from `negative` must appear
   - `seniority_boost` keywords give priority but are not required

8. **Deduplicate** against 3 sources:
   - `scan-history.tsv` → exact URL already seen
   - `applications.md` → company + normalized role already evaluated
   - `pipeline.md` → exact URL already pending or processed

8.5. **Verify liveness of WebSearch results (Level 3)** — BEFORE adding to pipeline:

   WebSearch results can be stale (Google caches results for weeks or months). To avoid evaluating expired offers, verify with Playwright each new URL from Level 3. Levels 1 and 2 are inherently real-time and do not require this check.

   For each new Level 3 URL (sequential — NEVER Playwright in parallel):
   a. `browser_navigate` to the URL
   b. `browser_snapshot` to read content
   c. Classify:
      - **Active**: job title visible + role description + Apply/Submit control visible in main content. Do not count generic header/navbar/footer text.
      - **Expired** (any of these signals):
        - Final URL contains `?error=true` (Greenhouse redirects this way when offer is closed)
        - Page contains: "job no longer available" / "no longer open" / "position has been filled" / "this job has expired" / "page not found"
        - Only navbar and footer visible, no JD content (content < ~300 chars)
   d. If expired: record in `scan-history.tsv` with status `skipped_expired` and discard
   e. If active: continue to step 9

   **Do not abort the entire scan if one URL fails.** If `browser_navigate` errors (timeout, 403, etc.), mark as `skipped_expired` and continue.

9. **For each new verified offer that passes filters**:
   a. Add to `pipeline.md` Pending section: `- [ ] {url} | {company} | {title}`
   b. Record in `scan-history.tsv`: `{url}\t{date}\t{query_name}\t{title}\t{company}\tadded`

10. **Title-filtered offers**: record in `scan-history.tsv` with status `skipped_title`
11. **Duplicate offers**: record with status `skipped_dup`
12. **Expired offers (Level 3)**: record with status `skipped_expired`

## Extracting title and company from WebSearch results

WebSearch results come in format: `"Job Title @ Company"` or `"Job Title | Company"` or `"Job Title — Company"`.

Extraction patterns by portal:
- **Ashby**: `"Senior AI PM (Remote) @ EverAI"` → title: `Senior AI PM`, company: `EverAI`
- **Greenhouse**: `"AI Engineer at Anthropic"` → title: `AI Engineer`, company: `Anthropic`
- **Lever**: `"Product Manager - AI @ Temporal"` → title: `Product Manager - AI`, company: `Temporal`

Generic regex: `(.+?)(?:\s*[@|—–-]\s*|\s+at\s+)(.+?)$`

## Private URLs

If a non-publicly-accessible URL is found:
1. Save the JD in `jds/{company}-{role-slug}.md`
2. Add to pipeline.md as: `- [ ] local:jds/{company}-{role-slug}.md | {company} | {title}`

## Scan History

`data/scan-history.tsv` tracks ALL seen URLs:

```
url	first_seen	portal	title	company	status
https://...	2026-02-10	Ashby — AI PM	PM AI	Acme	added
https://...	2026-02-10	Greenhouse — SA	Junior Dev	BigCo	skipped_title
https://...	2026-02-10	Ashby — AI PM	SA AI	OldCo	skipped_dup
https://...	2026-02-10	WebSearch — AI PM	PM AI	ClosedCo	skipped_expired
```

## Scan summary output

```
Portal Scan — {YYYY-MM-DD}
━━━━━━━━━━━━━━━━━━━━━━━━━━
Queries run: N
Offers found: N total
Filtered by title: N relevant
Duplicates: N (already evaluated or in pipeline)
Expired discarded: N (dead links, Level 3)
New added to pipeline.md: N

  + {company} | {title} | {query_name}
  ...

→ Run /jobhunter pipeline to evaluate new offers.
```

## Managing careers_url

Every company in `tracked_companies` must have `careers_url` — the direct URL to its jobs page. This avoids searching each time.

**RULE: Always use the company's own corporate URL; fall back to the ATS endpoint only if no corporate page exists.**

The `careers_url` should point to the company's own jobs page whenever available. Many companies use Workday, Greenhouse, or Lever underneath but expose vacancy IDs only through their corporate domain. Using the ATS URL directly when a corporate page exists can cause false 410 errors because the job IDs don't match.

| ✅ Correct (corporate) | ❌ Incorrect as first option (direct ATS) |
|---|---|
| `https://careers.mastercard.com` | `https://mastercard.wd1.myworkdayjobs.com` |
| `https://openai.com/careers` | `https://job-boards.greenhouse.io/openai` |
| `https://stripe.com/jobs` | `https://jobs.lever.co/stripe` |

Fallback: if you only have the direct ATS URL, navigate to the company's website first and locate its corporate jobs page. Use the direct ATS URL only if the company has no corporate page.

**Known patterns by platform:**
- **Ashby:** `https://jobs.ashbyhq.com/{slug}`
- **Greenhouse:** `https://job-boards.greenhouse.io/{slug}` or `https://job-boards.eu.greenhouse.io/{slug}`
- **Lever:** `https://jobs.lever.co/{slug}`
- **BambooHR:** list `https://{company}.bamboohr.com/careers/list`; detail `https://{company}.bamboohr.com/careers/{id}/detail`
- **Teamtailor:** `https://{company}.teamtailor.com/jobs`
- **Workday:** `https://{company}.{shard}.myworkdayjobs.com/{site}`
- **Custom:** company's own URL (e.g. `https://openai.com/careers`)

**API/feed patterns by platform:**
- **Ashby API:** `https://jobs.ashbyhq.com/api/non-user-graphql?op=ApiJobBoardWithTeams`
- **BambooHR API:** list `https://{company}.bamboohr.com/careers/list`; detail `https://{company}.bamboohr.com/careers/{id}/detail`
- **Lever API:** `https://api.lever.co/v0/postings/{company}?mode=json`
- **Teamtailor RSS:** `https://{company}.teamtailor.com/jobs.rss`
- **Workday API:** `https://{company}.{shard}.myworkdayjobs.com/wday/cxs/{company}/{site}/jobs`

**If `careers_url` does not exist** for a company:
1. Try the pattern for its known platform
2. If that fails, do a quick WebSearch: `"{company}" careers jobs`
3. Navigate with Playwright to confirm it works
4. **Save the found URL in portals.yml** for future scans

**If `careers_url` returns 404 or redirect:**
1. Note in scan summary output
2. Try `scan_query` as fallback
3. Flag for manual update

## portals.yml maintenance

- **Always save `careers_url`** when adding a new company
- Add new queries as new portals or interesting roles are discovered
- Disable noisy queries with `enabled: false`
- Adjust filter keywords as target roles evolve
- Add companies to `tracked_companies` when worth tracking closely
- Periodically verify `careers_url` — companies change ATS platforms
