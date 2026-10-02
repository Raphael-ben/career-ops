# _custom.md — Raphael's procedural house rules (user layer, survives updates)

## No Playwright outside the apply flow

Playwright (or any browser automation) is used in EXACTLY ONE place: the
interactive `/jobhunter apply` flow driving Raphael's Brave + Dashlane browser.
Everywhere else — scan, pipeline, liveness, JD fetching, Notion entries — is
browserless. This overrides the system-layer "Offer Verification — MANDATORY
Playwright" rule in CLAUDE.md/AGENTS.md.

**Liveness checks (pipeline / pre-apply):**
- Use `node check-liveness.mjs {url}` — its ATS JSON API rung — or a plain
  curl HTTP status check. NEVER browser-verify.
- Anti-bot 403/challenge pages are NOT "dead" — treat non-404 as
  alive-inconclusive and defer the real confirmation to apply time, when the
  posting opens in Brave anyway.

**JD fetching (pipeline/notion-entry):**
- Primary: JD text already in session context.
- Fallback: Scrapling `Fetcher` with chrome impersonation (curl_cffi) via the
  local venv, or the `scrapling` MCP `get`/`fetch` tools. No PlaywrightFetcher,
  no StealthyFetcher (both launch browsers).
- If blocked: note "(JD fetch failed — paste manually from {url})" and move on.

## Clickable job links everywhere

Whenever a job is mentioned by name in ANY output (scan summaries,
pre-assessments, triage, tracker views, evaluation reports, apply flows),
render the name as a markdown link to the job ad URL: `[Title — Company](url)`.
Never print a bare job title when its URL is known.

## Notion-first already-applied check

Before treating any job as new/unapplied (triage, evaluate, apply), ALWAYS
also check the Notion JOB OP database via the Notion MCP (search the data
source whose id is in `config/profile.yml` → `tracker.notion.data_source_id`)
by company name (and role if ambiguous), in addition to `data/applications.md`
and scan-history fuzzy dedup. A Notion entry with status Applied/Interview/
Offer/Rejected means NOT new — surface the existing entry and its status
instead. If the Notion MCP is unavailable in the session, say so explicitly
and fall back to `data/applications.md`.

## System updates — ALWAYS via tools/update-guard.sh, never bare update-system.mjs apply

`bash tools/update-guard.sh` is the only sanctioned update path. It encodes 5 known
updater failure modes: (1) stale baseline from the commit-subject grep wrongly
preserving changed files, (2) VERSION lagging the release, (3) the PRUNE step
deleting fork-only files under updater-owned dirs (e.g. `templates/*-pro.tex`),
(4) partial-checkout drift of multi-file units, (5) interface lag on preserved
system files. It snapshots the tree, hashes `tools/protected-paths.txt`, applies,
restores any damaged protected file, stamps VERSION, and runs a smoke suite.
`--repair-only` re-verifies and restores from the last snapshot. Add new
fork-owned files to `tools/protected-paths.txt`.
