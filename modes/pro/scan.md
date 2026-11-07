# Mode: pro/scan — Unified scan

This file handles ALL `/jobhunter scan` invocations:

| Command | Behaviour |
|---------|-----------|
| `/jobhunter scan` | Full scan — script layer + Tavily web queries |
| `/jobhunter scan --light` | Light scan — script layer only (no web queries, no LLM cost) |

**Script-only policy.** Every phase below is a single scripted command. Do NOT hand-process scraper output, and do NOT run per-query MCP searches in a loop — that is exactly what burned hundreds of k tokens per scan before. The scripts do the filtering, deduping, and appending deterministically.

**Blocking-only rule.** The scan agent never ends its turn waiting on a background job or a Monitor. Every step below is one blocking command with a timeout (`scan_aggregate.py` and `deep/run_deep.py` enforce their own deadlines; give the Bash call a timeout above them). No `run_in_background`, no `&`, no Monitor, no "I'll report when it finishes". If a step fails or times out, report that and continue with the next step.

## Resolution — machine paths

Resolve `{DATA_DIR}` and `{PYTHON}` from `modes/_profile.md` (lines `DATA_DIR: ...` / `PYTHON: ...`). If absent, `{DATA_DIR}` defaults to the repo's `config/` and `{PYTHON}` to `python3`. All scan config (search queries, title/location filters, recency window, Tavily key) lives in `config/profile.yml` and `portals.yml` — this mode holds no personal literals.

---

## Phase 0 — Unassessed launchd rows (always, first thing)

The Monday launchd job (`scan_aggregate.py --tavily`) appends `## Scan YYYY-MM-DD (script layer…)` blocks to `data/pipeline.md` that nobody has looked at yet. Before anything else:

```bash
cd career-ops && {PYTHON} scan_aggregate.py --unassessed
```

It prints every `## Scan` block from the last 14 days not yet shown to the user, with its open rows. If it lists any, give those rows the Phase 3 pre-assessment (glyph + reason + applicants/posted) right away, under a heading `Unreviewed from earlier runs`, then continue with Phase 1. Blocks are recorded as shown by the `--mark-assessed` call at the end of Phase 3.

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

Show the combined "new offers" count from 1a + 1b (+ 1c).

The aggregator stops itself at its deadline (`--deadline-seconds`, default `profile.yml scan.deadline_seconds`, else 600 s): each scraper gets `min(420, time left)`, scrapers that would start with ≤30 s left are skipped (`deadline: skipping X`), and Tavily stops on the first HTTP 432 (credits exhausted). Its last line is `funnel: raw=N kept=M elapsed=Ss deadline_hit=yes|no`; exit 1 means every layer came back empty, which is a broken scan, not "no jobs". Report `deadline_hit=yes` and which scrapers were skipped.

### Phase 1c — Deep layer (LinkedIn guest API, jobs.ch API, company ATS boards)

Runs after the aggregator, as ONE blocking command, never a background job, never a Monitor:

```bash
cd career-ops && {PYTHON} deep/run_deep.py
```

It harvests in the foreground with per-step caps and a 300 s overall deadline, then feeds everything through `scan_aggregate.py --inject` (same filters/dedup, same pipeline.md writer), and captures LinkedIn applicant counts where the posting states one. Last line: `deep: raw=N elapsed=Ss deadline_hit=yes|no inject_rc=R`. Sources, limits and caveats: `deep/README.md`. The LinkedIn guest API is best-effort; `linkedin: 0` with the other sources non-zero is a degraded run, not a failure. Do NOT rebuild harvest scripts in `/tmp` or the scratchpad; if `deep/run_deep.py` is broken, report it and move on.

Time budget: scan.mjs (~3.5 min) + aggregator (≤10 min) + deep (≤5 min). When the user wants a quick scan, pass `--deadline-seconds 300` to the aggregator and `--deadline-seconds 180` to the deep layer.

**If `--light` was passed:** skip Phase 1c and Phase 2, then go straight to Phase 3: the summary AND the pre-assessment for every entry the script layer found. `--light` never skips the pre-assessment.

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

## Phase 3 — Unified summary + pre-assessment (mandatory, every invocation)

**This runs even if the invoking prompt specifies its own report format.** Extra report instructions ADD to Phase 3; they never replace it. A scan reply without the pre-assessment list is incomplete, including `--light` runs and runs invoked by an orchestrator with its own template.

After the phases complete, show:

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

Line format:

```
✓ | ~ | ✗  [Title — Company](url)  <reason ≤8 words>  [applicants: N | n/a] [posted: Xd]
```

- **applicants**: read it from the pipeline row (`· applicants: N`, written when the source exposed it: LinkedIn guest detail, some boards). `<25` is a strong plus, 25–100 neutral, >200 crowded (`200+` counts as crowded); a low count can lift `~` to `✓` when the title fits. No count in the row → `applicants: n/a`. **Never invent or estimate a count.**
- **posted**: age in days from the row's `· posted: YYYY-MM-DD` (or the source's date), `n/a` if unknown. Count and age go together: 30 applicants on a 1-day-old post is busier than 30 on a 3-week-old one.

Judge this ONLY from title, company, location, source, applicant count and age against `profile.yml` → `triage.preferences`. Do **not** fetch the JD and do **not** make any web calls for this step — it is a first glance, not a decision. The pipeline's LLM-triage step remains the real evaluation; this pass just gives the user a quick read before that happens. Borderline entries especially need this line, since they exist precisely because the keyword filter couldn't classify them.

After printing the pre-assessment (including any Phase 0 rows), record the blocks as shown so Phase 0 doesn't repeat them:

```bash
cd career-ops && {PYTHON} scan_aggregate.py --mark-assessed
```
