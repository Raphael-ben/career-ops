# deep/ — scan Phase 1c (deep layer)

One entrypoint, one blocking command:

```bash
cd career-ops && {PYTHON} deep/run_deep.py            # default: 300 s budget, postings <= 7 days
{PYTHON} deep/run_deep.py --dry-run                    # harvest + funnel report, writes nothing
{PYTHON} deep/run_deep.py --only linkedin,jobsch       # subset of steps
{PYTHON} deep/run_deep.py --selftest                   # parser fixtures, no network
```

Run it in the foreground. Never as a background job, never behind a Monitor.
On 2026-11-06 the scan agent launched rebuilt copies of these harvesters in the
background from `/private/tmp`, ended its turn waiting on a Monitor, and never
woke up. This directory is the in-repo replacement.

## What it does

| Step | Source | Endpoint | Step cap |
|------|--------|----------|----------|
| `linkedin` | LinkedIn guest search | `linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search` (first page per query, `f_TPR` = `--days`) | 110 s |
| `linkedin-detail` | LinkedIn guest posting | `linkedin.com/jobs-guest/jobs/api/jobPosting/<id>`, for up to `linkedin.detail_max` (30) postings that pass the title/location gates and are not in history. Drops closed postings, captures `applicants` | 45 s |
| `jobsch` | jobs.ch public API | `jobs.ch/api/v1/public/search` (newest first, `jobsch.max_pages` pages per query, inactive dropped) | 60 s |
| `ats` | company boards, 12 threads | Workday CXS (`/wday/cxs/<tenant>/<site>/jobs`, Switzerland facet when the tenant has one), SmartRecruiters (`?country=ch`), Greenhouse, Lever, Ashby (CH locations only) | 70 s |

The harvested rows are deduped by URL, written to `data/cache/deep-<date>.json`,
and passed to `scan_aggregate.py --inject`, which applies the same funnel as
every other source: recency gate, `portals.yml` title/location filters,
`data/blacklist.md`, URL + fuzzy dedup against `scan-history.tsv` and
`applications.md`. New rows land in `data/pipeline.md` under a
`## Scan <date> (script layer)` block and in `scan-history.tsv` (canonical
column layout).

**Inputs:** `deep/boards.yml` (Workday tenants, SR/GH/Lever/Ashby slugs,
display aliases; no search terms), `config/profile.yml` (`scan.deep_deadline_seconds`;
search terms = `scan.deep_queries` / `scan.deep_workday_keywords` if set, else
`target_roles.primary` + `target_roles.archetypes[].name`; none -> one warning, layer skipped),
`portals.yml` filters, `data/scan-history.tsv`.

**Outputs:** `data/cache/deep-<date>.json` (raw harvest), then whatever
`--inject` writes. Last stdout line:
`deep: raw=N elapsed=Ss deadline_hit=yes|no inject_rc=R`. Exit 0 when the funnel
ran, 1 when nothing was harvested or the funnel failed.

## Runtime

Overall deadline 300 s by default (`--deadline-seconds`, or
`profile.yml scan.deep_deadline_seconds`). Each step stops at its own cap or
when the overall budget minus a 20 s reserve for the funnel runs out,
whichever comes first. Every request has a timeout of at most 15 s and never
more than the time left, so the worst-case wall time is the deadline plus one
request timeout. A step that hits the budget keeps what it already has.

## Rate limits

- LinkedIn guest API: 1.5 s between requests. The first HTTP 429 stops the
  LinkedIn step for that run (the remaining queries would all fail too).
- jobs.ch: 0.5 s between pages.
- ATS APIs: public JSON endpoints, 12 parallel workers, one request per
  board (Workday: one facet probe plus one request per keyword).

## Applicant counts

Only from the LinkedIn posting page, and only when it states one:
`37 applicants` -> `37`, `Over 200 applicants` -> `200+`,
`Be among the first 25 applicants` -> `<25`. No count shown means no
`applicants` field. A count is never estimated. The pipeline row then reads
`... — via linkedin-guest, triage · applicants: 37 · posted: 2026-11-05`, which
the Phase 3 pre-assessment reads (see `modes/pro/scan.md`).

## Caveats

- **The LinkedIn guest API is best-effort.** It is unauthenticated and
  undocumented. LinkedIn can change the HTML, rate-limit, or block it at any
  time. When it breaks, the other steps still run. The selftest only checks
  the parsers against fixtures, so a markup change shows up as `linkedin: 0`
  in a real run, not as a selftest failure.
- LinkedIn and jobs.ch are aggregators: a row from them is unconfirmed until
  the role is found at the employer (AGENTS.md, "Aggregator Listings").
- Workday "Posted N Days Ago" is converted to a date. "30+ Days Ago" becomes
  30 days, which the `--days` window then drops.

## Provenance

Recovered 2026-11-07 from the 2026-11-06 scan session's scratch scripts
(`harvest.py`, `harvest_ats.py`, `harvest_wd2.py`, `filter.py`, `check.py`,
`live.py`). The three harvesters are merged into `run_deep.py`, with the
hardcoded dates, absolute paths, exec() chaining and background launch
removed. `filter.py` (its own title/location/dedup regexes) is replaced by
`scan_aggregate.py --inject`. `check.py` and `live.py` were one-off
liveness checks on hand-picked companies and are not carried over: liveness
is checked at apply time, and the LinkedIn detail fetch here only drops
postings LinkedIn itself marks closed.
