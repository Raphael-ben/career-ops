# Mode: pro/onboarding — Friend setup conversation

This file handles `/jobhunter onboarding` and the auto-entry when `node doctor.mjs --json` reports `onboardingNeeded: true`. Run it inline in the main session (it is a conversation, never a subagent). Re-running it on a configured install redoes setup: say so, and pass `--force` only after the friend confirms.

**Hard rules (never violate):**
1. **No other mode until Phase 8 passes.** No scan, pipeline, evaluate, apply, or tracker work before `onboardingNeeded: false` and both dry-runs succeed.
2. **No user file is written before the Phase 7 "yes"** (`cv.md`, `config/`, `portals.yml`, `data/`, `modes/_profile.md`, `{DATA_DIR}`). Phases 0–6 only ask, read, and run checks; the dependency installs the friend accepts in Phase 1 and the dashboard build in Phase 6 are the only exceptions. Collect every answer in a running answer sheet in the conversation.
3. **Never accept "flexible", "depends", or "all equal" for the priority ranking.** Ask the tie-break ("If you had to give up one: X or Y?") until the order is total.
4. **Never invent profile_bank content.** Every employer, title, date, number, achievement, and skill comes from the friend's CV or their own words in this conversation. Missing → ask; still missing → leave it out.
5. **Never hand-write a field `onboard-write.mjs` owns** (candidate contact, target_roles, compensation, location, spend_tier, cv.max_pages, narrative, title_filter, max_posting_age_days). To change one, rerun the writer. `location_filter` is the exception: the writer is called with empty `countries`/`cities`, and the agent owns the whole `location_filter` block afterwards (Phase 7 step 5).
6. Ask one topic at a time. Short questions. Play back what you understood before moving on.

## Resolution — machine paths

`{DATA_DIR}` and `{PYTHON}` are decided in Phase 2 and written to `modes/_profile.md` in Phase 7 (lines `DATA_DIR: ...` / `PYTHON: ...`, the shape every pro mode reads). Until then use `{PYTHON}` = `../.venv/bin/python3` if it exists, else `python3`. All commands run from `career-ops/`. Data stays in the repo's gitignored user layer (`cv.md`, `config/`, `portals.yml`, `data/`) plus `{DATA_DIR}`; do not set `CAREER_OPS_DATA_DIR` or `.career-ops-data`.

---

## Phase 0 — Explainer-lite (print, then ask to start)

Print exactly this, then ask "Ready? It takes 30–45 minutes.":

```
This sets up your own job-hunt system. It runs on this Mac only.
1. It scans job boards weekly and keeps only roles that match YOUR definition of a good job.
2. It writes a tailored one-page CV and cover letter per role, from facts you give it, never invented.
3. It tracks every application (Notion, a markdown file, or a local dashboard).
Your data stays in gitignored files on this machine. Nothing is shared with the person who gave you this.
```

## Phase 1 — Dependencies

```bash
node doctor.mjs --json
```

Read `missing`, `warnings`, and the check list. Ask **only** about what is missing:
- **Node ≥ 18** missing → `brew install node`, rerun doctor.
- **Python venv** (`../.venv`) missing → `bash ../setup.sh` (builds the venv and installs the scrapers). Then `{PYTHON}` = `../.venv/bin/python3`.
- **pdflatex** missing → offer MacTeX/BasicTeX (`brew install --cask basictex`); the pro pipeline requires LaTeX; if they decline, set `cv.output_format: html` and they use the upstream generic `pdf` pipeline instead of the pro CV/letter templates.
- **Tavily key** → explain: free tier at https://tavily.com, powers the web search layer of the scan (job boards with no API). Record the key on the answer sheet as `tavily.api_key`; skipping is fine (scan runs script-only).
- **Brave + `extension/`** for `/jobhunter apply` form filling → only if the friend wants form filling; record `apply.browser: brave`.
- **Notion MCP** → only needed if they pick `notion` in Phase 6; ask then.

Do not fix anything the friend declines. Note declined items for the Phase 7 playback.

## Phase 2 — Identity, CV, profile bank

1. **CV.** Ask the friend to paste their CV (text, PDF path, or LinkedIn export). Draft `cv.md` in the shape AGENTS.md "Step 1: CV" requires (`## Experience`, `### Company — Location`, bold title line, dates line, a `Skills` heading). Show the draft; corrections go in now.
2. **Contact + identity:** full name, email, phone, LinkedIn, city, country (onboard-write requires `location.country`), timezone, years of experience (compute from CV dates, then confirm; never guess).
3. **Profile bank.** Build `{DATA_DIR}/config/profile_bank.json` in conversation: read `config/profile_bank.schema.json` (required: `candidate`, `education`, `experience`, `rules`) and use `config/profile_bank.example.json` as the shape only (its person is fictional; copy no facts). For each experience entry ask: context line, 3–6 achievement bullets with numbers the friend confirms, skills it surfaces. Ask per entry: always include, or only for certain role types (→ `include_only_if: [tags]`). Ask for `rules.never_mention` (anything they never want on a CV) and `rules.tense` (current role present tense, past roles past tense). Copy `humanize.*` (all seven lists) and `verify.tolerances` verbatim from the example. `candidate.file_slug` = `Firstname_Lastname`.
4. **Machine paths.** `DATA_DIR` default `~/jobhunter-data` (expanded to an absolute path; ask if they want another). `PYTHON` = absolute path of `../.venv/bin/python3`.
5. **Pro assets** (copied in Phase 7) into `{DATA_DIR}/templates/`:
   - `templates/cv-template-pro.tex` → `cv-template-pro.tex`
   - `templates/cover-letter-template-pro.tex` → `cover-letter-template-pro.tex`
   - `templates/cv-fill-spec.pro.md` → `cv-fill-spec.md`
   - `templates/cl-fill-spec.pro.md` → `cl-fill-spec.md`
   Optional photo → `{DATA_DIR}/templates/photo.jpg` (ask; none is fine).
6. Answer sheet gets `sharing.role: friend`.

## Phase 3 — Location branch

Ask exactly: **"Where are you hunting, and how far will you commute (minutes, by car or transit)?"**

**A. Swiss, within reach of Zürich/Zug/Basel/Bern:**
- Plan: copy `templates/portals.zurich.yml` sections (`location_filter`, `search_queries`, `tracked_companies`) into `portals.yml`, copy `templates/blacklist.starter.md` → `data/blacklist.md`, keep all Swiss scrapers (omit `scan.scrapers`, absent = all seven).
- **Rewrite `location_filter.allow`** from the friend's own commute: propose the towns reachable within their stated minutes and mode (start from their home town, list it, let them add/remove). The pack's `allow` list is a starting menu, never the final list. Keep the pack's `location_filter.block` as is.
- `tracked_companies`: group the pack's ~100 companies by industry yourself (from names and notes), show the groups with counts, ask which industries to keep. Trimmed groups are deleted at copy time.
- `jobspy.location`: their city, e.g. `"Zürich, Switzerland"`; `jobspy.country_indeed: switzerland`.

**B. Anywhere else:**
- `scan.scrapers: [jobspy]` (the other scrapers are Swiss-only).
- Discovery: read `modes/discover.md`. Ask for 10–20 target employers in their area (or propose from their industries), then preview with `node discover-ats.mjs <Name> <Name> ... --summary` (writes nothing). After the first real scan, `node discover-new-companies.mjs --summary` finds more.
- WebSearch (or Tavily if a key was given) for the 5–10 main job boards in their city/country and the local LinkedIn location string (e.g. `"Munich, Bavaria, Germany"`). Each board with a searchable site becomes a `search_queries` entry (`site:<board> "<title>" <city>`).
- `jobspy.location` = the LinkedIn location string; `jobspy.country_indeed` = their country (ISO-2 code or English name, e.g. `de` / `germany`).
- Commute → `location_filter.allow` = the towns in range only (never the country: a country entry admits every job in it), `block` = regions out of range they name. No `always_allow`.
- Target employers go in a YAML file `{DATA_DIR}/discovery.yml` of shape `companies: [{name, slug?, website?}]` (written in Phase 7; the Phase 3 preview passes the names as positional args instead).

Record on the answer sheet: commute minutes + mode (→ `compensation.location_flexibility`, e.g. `"≤60 min by transit"`), the town list, the company/board list.

## Phase 4 — Goal-job deep dive (the crucial part)

Leave this phase with every artifact below, each explicit:

| Artifact | Minimum | Written to |
|---|---|---|
| Acceptable titles / functions | ≥ 5 concrete titles, ≥ 2 functions | `target_roles.primary`, `title_filter.positive`, `jobspy.search_terms` (EN + local language, ≥ 8 terms) |
| Unacceptable titles / functions | ≥ 3 | `title_filter.negative`, `triage.preferences` |
| Priorities, force-ranked | total order over at least: salary, commute, industry, seniority, remote share, company size, growth/learning | `triage.preferences` (ranked list header) |
| Deal-breakers | ≥ 2 or explicit "none" | `triage.preferences` |
| Commute cap | minutes + mode | `compensation.location_flexibility`, `location_filter.allow/block` |
| Salary floor + target + currency | all three | `compensation.minimum/target_range/currency` |
| Seniority band | e.g. senior IC / manager / head | `triage.preferences`, `title_filter` |
| Company type & size | startup / scale-up / corporate / public; consulting yes/no | `triage.preferences`, blacklist opt-in |
| Languages of work | list | `candidate.languages`, `jobspy.search_terms` |
| Visa / permit status | one line | `location.visa_status` |

**Method.** Open questions first: "Walk me through the last job ad you were excited about, and the last one you closed in two seconds." Extract titles, functions, deal-breakers, and company types from both stories, then fill gaps with direct questions. For the ranking, list the seven priorities and ask for an order; on any hesitation or tie, switch to pairwise choice ("salary +10% or 20 minutes less commute?") until the order is total (hard rule 3). Titles: get ≥ 5 real titles they would apply to today, then translate into the local language(s) for `jobspy.search_terms` (≥ 8 terms total). Consulting: ask **"Do you want consulting and advisory firms excluded?"** Yes (branch A) → uncomment the consulting block in `data/blacklist.md` at copy time: on each line `<!-- | X | ... | -->` remove the leading `<!-- ` and trailing ` -->`. Yes (branch B) → add the firms they name as `| Firm | today | all | Consulting — in-house only |` rows.

**`triage.preferences`** — written as a YAML block scalar in the shape `modes/pro/pipeline.md` triage consumes:

```yaml
triage:
  model: claude-haiku-4-5
  borderline_bucket: true
  preferences: |
    ## Ranked priorities
    1. <first> — <one line why / threshold>
    ... (all seven, total order)
    ## In range / out of range
    In range: <towns/regions within the commute cap, remote share accepted>
    Out of range: <regions beyond the cap, relocation stance>
    ## Hard rules
    - Target titles: <list>. Seniority band: <band>.
    - Never: <unacceptable titles/functions>.
    - Deal-breakers: <list or "none">.
    - Company type: <types>, size <range>; consulting <yes/no>.
    - Salary floor <floor> <currency>; target <target>.
```

## Phase 5 — Language

Ask: **"Which language should your CVs and cover letters be written in?"** Normalize the answer **before** checking: lowercase, take the part before `-`/`_`, map names → codes (`German`/`Deutsch`/`allemand`/`de-CH`/`de_DE` → `de`; `English`/`Englisch`/`anglais`/`en-GB`/`en_US` → `en`; `French`/`Français`/`Französisch`/`fr-CH`/`fr_FR` → `fr`; other languages → their ISO 639-1 code).

If the code is `en`, `de`, or `fr` → proceed. Otherwise print this block and ask "Use `en` instead, or proceed at your own risk?":

```
⚠️ Language warning
Humanization and AI-tell removal are tuned for English, German and French only (modes/pro/humanize.md).
The banned-word verifier has no list for this language, so CVs and cover letters may read as machine-written.
Options: use English (en) as the output language, or proceed in <language> at your own risk.
```

Answer sheet: `language.output: <code>` and `language.warned: true` (always set once this question is answered, so the pipeline reminds once per run instead of re-asking).

## Phase 6 — Tracker

Ask which tracker: `tracker.type` ∈ `notion` | `markdown` | `dashboard`.

- **notion** — needs the Notion connector enabled in claude.ai and a JOB OP-style applications database. Ask for the database URL. `applications_db_id` = the 32-hex id in the URL path (strip dashes and `?v=`). Get `data_source_id` with one `notion-fetch` of that database (the `collection://` id). Test with one `notion-search` scoped to it; it must return without error. Tell them: marking a role Applied then requires a Notion entry (the Applied gate, `.claude/hooks/notion-gate.mjs`, blocks the session end otherwise). Answer sheet: `tracker.notion.applications_db_id`, `tracker.notion.data_source_id`.
- **markdown** — `data/applications.md` is the tracker. Print:
  ```
  1. Install Obsidian (obsidian.md) → "Open folder as vault" → choose career-ops/data
  2. Open applications.md: it is your tracker table, updated by the system.
  3. Optional: install the Dataview plugin to filter by status.
  ```
- **dashboard** — tell them this builds the local web dashboard once, takes a few minutes and needs network. Run `npm --prefix web ci && npm run ui`; when it prints the URL, confirm it loads, stop it (Ctrl-C), and print the launch line: `cd career-ops && npm run ui` → http://localhost:3000 (loopback only, no login). It reads the same `data/applications.md`; the Applied gate treats it like markdown.

## Phase 7 — Playback, then write

Print the full answer sheet as one table with columns `item | value | → key`, covering: identity + contact, CV summary (entries, dates), profile_bank entries with their include rules, `DATA_DIR`/`PYTHON`, location branch (A/B) + towns + companies/boards, all ten Phase 4 artifacts, language (+ warning shown?), tracker, Tavily (set/skipped), declined dependencies. Ask: **"Is this correct? Reply yes to write the files."** Anything but an explicit yes → fix and replay.

On yes, in this order:

1. `node doctor.mjs --json --init-templates` (copies `modes/_profile.md`, `_custom.md`, `_brief.md`, `voice-dna.md` templates).
2. Write `cv.md`.
3. `node onboard-write.mjs --answers - --force` with ONE JSON on stdin built from the table (shape: `node onboard-write.mjs --help`): `candidate` (full_name, email, location, phone, linkedin, years_of_experience), `target_roles` (acceptable titles), `compensation` (target_range, currency, minimum, location_flexibility), `location` (country, city, timezone, visa_status), `spend_tier` (ask: economy/standard/premium; default standard), `cv: {max_pages: 1, strict_pages: true}`, `narrative.headline`, `portals` (`positive` = acceptable titles + variants, `negative` = unacceptable titles, `countries: []`, `cities: []`, `max_posting_age_days: 45`). Empty countries/cities on purpose: a country passed here lands in `location_filter.always_allow`, which outranks `block` in `scan.mjs` and would admit every job in the country, overriding the commute cap. It prints `{"written":[...],"kept":[...]}`; both files must be in `written`.
4. Edit `config/profile.yml` for the keys the writer does not own. Where the writer already emitted the top-level block (`language:`, `cv:`, `candidate:`), add the keys inside it; never create a second block with the same name. Everything else is appended at the end:
   - `candidate.languages: [...]`; `language.output`, `language.warned: true`
   - `cv.output_format: "latex"`, `cv.template_cv: "{DATA_DIR}/templates/cv-template-pro.tex"`, `cv.template_cl: "{DATA_DIR}/templates/cover-letter-template-pro.tex"`, `cv.photo: "{DATA_DIR}/templates/photo.jpg"` (only if given). Delete the writer's example `cover_letter.language_learning` entry unless the friend stated one.
   - `sharing:` with `role: friend` as its **first** key (the friend-guard hook regex depends on it)
   - `scan.scrapers: [jobspy]` (branch B only; branch A omits it), `scan.parallel_scrapers: true`
   - `jobspy:` `search_terms` (≥ 8), `location`, `country_indeed` (Swiss: `switzerland`), `results_wanted: 20`, `hours_old: 72`
   - `triage:` block from Phase 4; `tracker.type` (+ `tracker.notion.*`); `tavily.api_key` (if given); `apply.browser` (if given)
5. `portals.yml` — the agent owns `location_filter` in both branches: it has `allow` = the friend's commute towns only, `block` as below, and **no** `always_allow` and no country in `allow` (delete any the writer emitted). Branch A → replace `search_queries` and `tracked_companies` with the pack's sections (trimmed industries removed) and `location_filter` with `allow` = the friend's town list plus the pack's `block`; copy `templates/blacklist.starter.md` → `data/blacklist.md` (uncomment the consulting block on yes). Branch B → write `{DATA_DIR}/discovery.yml`, empty the example `tracked_companies`, then `node discover-ats.mjs --in {DATA_DIR}/discovery.yml --write` appends the resolved ones, replace `search_queries` with the board queries, set `location_filter` (towns `allow`, regions `block`); copy `templates/blacklist.example.md` → `data/blacklist.md` if missing.
6. `mkdir -p {DATA_DIR}/config {DATA_DIR}/templates`; write `{DATA_DIR}/config/profile_bank.json`; copy the four pro assets (Phase 2 step 5) and the photo. Check it parses and has the schema's required keys: `node -e 'const b=require(process.argv[1]);for(const k of require("./config/profile_bank.schema.json").required)if(!(k in b))throw k' {DATA_DIR}/config/profile_bank.json`.
7. Append to `modes/_profile.md`:
   ```
   ## Machine paths for the `pro/` CV pipeline (DATA_DIR / PYTHON)

   DATA_DIR: <absolute DATA_DIR>
   PYTHON: <absolute path to ../.venv/bin/python3>
   ```
   Then personalize the rest of `_profile.md` and `_brief.md` from the answer sheet (archetypes = acceptable functions, North Star = Phase 4 rank 1–3), so doctor's `unpersonalized` is empty.
8. Create `data/applications.md` with the tracker header from AGENTS.md "Step 4" if missing.

## Phase 8 — Verification

Run each; all must pass before Phase 9:

```bash
node doctor.mjs --json                                  # onboardingNeeded must be false; fix every missing/unpersonalized entry
{PYTHON} scan_aggregate.py --dry-run --deadline-seconds 120   # writes nothing but hits the network (1–2 min)
node scan.mjs --dry-run
```

Check in the `{PYTHON} scan_aggregate.py --dry-run` output that only the configured scrapers ran (branch B: jobspy only) and that the funnel is non-zero after the title filter. A zero funnel means the titles or location filter are too narrow: show the funnel, adjust with the friend by editing `portals.yml` directly: title changes = `title_filter.positive`/`negative`, town changes = `location_filter.allow`. Do NOT rerun `onboard-write.mjs --only portals`: it rebuilds `portals.yml` from `portals.example.yml` and wipes the pack's `search_queries` and `tracked_companies` (or the discovery results); if you ever do rerun it, re-apply ALL of Phase 7 step 5 afterwards. Then rerun the checks. Errors → fix and rerun (`node scan.mjs --dry-run` too); never skip to Phase 9.

## Phase 9 — Explainer and update briefing (print this block as is)

```
You're set up. Commands (type /jobhunter <command>):
  scan        find new jobs on all your sources (weekly is enough)
  pipeline    triage the scan results against your priorities, then build CV + letter for the good ones
  evaluate    deep evaluation of one job ad (paste a URL or the text)
  pdf         regenerate the CV/cover letter PDFs for a role
  apply       open the application form and fill it with the side panel (you always click Submit yourself)
  applied     mark a role as applied: updates the tracker (and Notion, if you chose it)
  tracker     show your applications and their status
  follow      follow-up reminders for applications that went quiet
  interview   prepare for an interview at a specific company
  onboarding  rerun this setup to change your targets

Weekly automatic scan: optional. `bash scripts/install-launchd.sh` in the repo root installs it
(scripts/launchd/*.tmpl; Mondays). Off by default.

Costs: large pipeline batches can exhaust your Claude plan's monthly cap; run them in small batches.
Tavily credits run out on the free tier: HTTP 432 in the scan log means the web layer is off until renewal.

Privacy: cv.md, config/, portals.yml, data/ and your data folder are gitignored. Never commit them,
never share your data folder. What leaves your machine: this Claude conversation (your CV, profile
and job ads are sent to Claude, unredacted), Tavily search queries, Notion entries (if you chose
Notion), and requests to the job boards. Personal-detail redaction applies only to the optional
third-party LLM runners (OpenRouter / OpenAI / Gemini), not to Claude, Tavily or Notion.

Updates: run `bash tools/update.sh` in the repo root once a month, or when the session-start message
says your system is over 30 days old. Never run update-system.mjs apply directly.
```

Then offer the first real scan (`/jobhunter scan`).
