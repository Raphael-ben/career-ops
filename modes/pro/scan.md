# Mode: pro/scan — Unified scan

This file handles ALL `/jobhunter scan` invocations:

| Command | Behaviour |
|---------|-----------|
| `/jobhunter scan` | Full scan — script layer + Tavily web queries |
| `/jobhunter scan --light` | Light scan — script layer only (no web queries, no LLM cost) |

**Script-only policy.** Every phase below is a single scripted command. Do NOT hand-process scraper output, and do NOT run per-query MCP searches in a loop — that is exactly what burned hundreds of k tokens per scan before. The scripts do the filtering, deduping, and appending deterministically.

## Resolution — machine paths

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. All scan config (search queries, title/location filters, recency window, Tavily key) lives in `config/profile.yml` and `portals.yml` — this mode holds no personal literals.

---

## Phase 1 — Script layer (always runs)

Two independent sub-steps. Run BOTH; a failure in one must not block the other.

> ⚠️ **Why 1b is separate.** `scan.mjs` is system-layer — `update-system.mjs` overwrites it on every career-ops update, which has twice wiped the JobSpy/jobs.ch wiring. The current upstream `scan.mjs` runs **only ATS providers**, not JobSpy or jobs.ch. So this mode runs the aggregator scrapers itself in Phase 1b. Never rely on `scan.mjs` for the aggregator layer.

### Phase 1a — ATS providers (zero-token)

```bash
cd career-ops && node scan.mjs
```

Covers tracked companies in `portals.yml` via ATS providers (Workday, Greenhouse, Lever, Ashby, SmartRecruiters, Recruitee, Workable, SolidJobs). Note the "New offers added" count from its summary block.

### Phase 1b — Aggregator scrapers (LinkedIn/Indeed/Google + jobs.ch/jobup + Stepstone)

Run ONE command — `scan_aggregate.py` does the whole pipeline deterministically (runs all scrapers, applies the recency gate + `portals.yml` filters with a three-way pass/borderline/drop split, dedups against `data/scan-history.tsv`, appends new jobs to `data/scan-history.tsv` and `data/pipeline.md`):

```bash
cd career-ops && {PYTHON} scan_aggregate.py --date $(date +%F)
```

Notes on the funnel:
- **Recency gate**: postings older than `profile.yml scan.max_age_days` are dropped. Unknown dates pass (triage/liveness catches stale ones).
- **Borderline bucket**: titles matching no positive keyword (but no negative either) land in a `### Borderline` section of pipeline.md. **The LLM triage step MUST evaluate them like any other entry** — they exist precisely because the keyword list mislabels roles like "Business Manager" or "Founder's Office Lead". Never delete the borderline section unprocessed.

> ⚠️ **Do NOT hand-process the scraper output.** Each scraper returns ~180 jobs (~350 total); filtering/deduping that many by hand in-context is the exact thing that "didn't work" before. Always use `scan_aggregate.py`. It is UNTRACKED on purpose so career-ops updates can't wipe it (unlike `scan.mjs`).

The script prints a funnel summary (`raw → title_ok → location_ok → NEW`) and the list of new jobs. Report that count. Use `--dry-run` to preview without writing. The scrapers it calls self-re-exec into the project venv and always exit 0, so partial failures degrade gracefully.

The wide net is intentional — consulting/irrelevant roles that slip past the title filter are culled later by the pipeline LLM-triage step, not here.

Show the combined "new offers" count from 1a + 1b.

**If `--light` was passed: stop here.** Do not run Phase 2. Show the script summary and exit.

---

## Phase 2 — Tavily web queries (skip if `--light`)

**Scripted — zero agent tokens.** Phase 2 is part of `scan_aggregate.py`: it calls the Tavily REST API directly (key: `profile.yml → tavily.api_key`), maps `site:` operators to `include_domains`, drops directory/roll-up URLs, and pushes results through the same recency/filter/dedup/borderline funnel as Phase 1b.

Run Phases 1b + 2 together as ONE command (instead of the Phase 1b call above):

```bash
cd career-ops && {PYTHON} scan_aggregate.py --tavily --date $(date +%F)
```

Do NOT run per-query MCP searches — the multi-query MCP loop is exactly what burned hundreds of k tokens per scan.

**Fallback only** if the script prints `[tavily] no api_key in profile.yml`: fall back to the Tavily MCP `tavily_search` per query (strip `site:` → `include_domains`, `country: "Switzerland"`, `search_depth: "advanced"`, `max_results: 8`; keep individual postings only; dedup against scan-history.tsv; apply title+location filters; append to scan-history.tsv and pipeline.md as in Phase 1b).

---

## Phase 3 — Unified summary

After both phases complete, show:

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Scan complete — {date}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ATS providers (scan.mjs):                    A new
Script layer (JobSpy/jobs.ch/jobup/Stepstone
              + Tavily) — pass:              N new
                        — borderline:        B for triage
─────────────────────────────────────────
Total new in pipeline:                  N+M

→ Run /jobhunter pipeline to evaluate new offers.
```

List every new entry from this run (pass AND borderline), grouped by source, one line each:

```
- [Title — Company](url) · source · verdict reason
```

Render the job name as a markdown link to its URL — never a bare title when the URL is known.

**Pre-assessment (mandatory, cheap first-glance).** For every new entry above, output a verdict glyph and a ≤8-word reason:

- `✓` strong fit / `~` worth a look / `✗` likely skip

Judge this ONLY from title, company, location, and source against `profile.yml` → `triage.preferences`. Do **not** fetch the JD and do **not** make any web calls for this step — it is a first glance, not a decision. The pipeline's LLM-triage step remains the real evaluation; this pass just gives the user a quick read before that happens. Borderline entries especially need this line, since they exist precisely because the keyword filter couldn't classify them.
