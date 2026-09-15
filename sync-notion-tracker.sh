#!/bin/bash
# Weekly JOB OP (Notion) -> applications.md status sync.
# Invoked by launchd every Monday 09:00, and runnable by hand any time:
#   bash career-ops/sync-notion-tracker.sh
#   bash career-ops/sync-notion-tracker.sh --dry-run   # resolve config only, no network calls
#
# ponytail: headless claude -p; if the claude.ai Notion connector isn't
# authenticated in headless mode the run logs an error and no-ops — check the log.
#
# All identifying config (repo path, Notion database/data-source ids, tokens)
# is resolved at runtime from this script's own location and from
# config/profile.yml / .env — nothing personal is hardcoded here, so this
# file is safe to track in git. Per-user secrets stay in the gitignored
# config/profile.yml and .env.

set -uo pipefail
export PATH="$HOME/.local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin"
export ECC_GATEGUARD=off   # skip the fact-forcing edit gate in unattended mode

DRY_RUN=0
if [[ "${1:-}" == "--dry-run" ]]; then
  DRY_RUN=1
fi

# Repo root = the directory this script lives in (career-ops/), resolved
# relative to the script itself so this works from any checkout location.
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO="$SCRIPT_DIR"
PROFILE_YML="$REPO/config/profile.yml"
ENV_FILE="$REPO/.env"
LOG="$REPO/data/notion-sync.log"

cd "$REPO" || { echo "$(date '+%F %T') repo missing" >>"$LOG"; exit 1; }

# ---------------------------------------------------------------------------
# Resolve tracker config (DB id, data source id) from config/profile.yml.
# Prefer yq if installed; fall back to grep/sed (no interpreter dependency).
#
# 2026-09-15 (#defect-C): the previous python3+PyYAML fallback silently
# emptied both IDs for weeks (2026-09-07, 2026-09-14 runs both no-op'd as
# "not configured") even though profile.yml was correctly populated. Cause:
# this script's sanitized PATH resolves `python3` to a bare interpreter
# (Homebrew's, no PyYAML installed — the repo's PyYAML lives only in
# .venv/, which this PATH deliberately excludes), so `import yaml` raised
# and the swallowed stderr (`2>/dev/null`) turned that failure into two
# empty strings instead of a loud error. grep/sed has no module to be
# missing, so it can't fail the same way. The two ids are flat, single-
# occurrence scalar keys, so this is exact for the current shape; if
# `tracker.notion` ever grows a second block, switch to a real yq install.
# ---------------------------------------------------------------------------
APPLICATIONS_DB_ID=""
DATA_SOURCE_ID=""

if [[ -f "$PROFILE_YML" ]]; then
  if command -v yq >/dev/null 2>&1; then
    APPLICATIONS_DB_ID="$(yq -r '.tracker.notion.applications_db_id // ""' "$PROFILE_YML" 2>/dev/null)"
    DATA_SOURCE_ID="$(yq -r '.tracker.notion.data_source_id // ""' "$PROFILE_YML" 2>/dev/null)"
  else
    APPLICATIONS_DB_ID="$(grep -m1 'applications_db_id:' "$PROFILE_YML" | sed -E 's/.*applications_db_id:[[:space:]]*"?([^"[:space:]]*)"?[[:space:]]*$/\1/')"
    DATA_SOURCE_ID="$(grep -m1 'data_source_id:' "$PROFILE_YML" | sed -E 's/.*data_source_id:[[:space:]]*"?([^"[:space:]]*)"?[[:space:]]*$/\1/')"
  fi
fi

# Optional: a Notion integration token from .env (not required — the
# claude.ai Notion connector used below handles its own auth). Read it only
# so a future direct-API path has it available without another lookup.
NOTION_ACCESS_TOKEN=""
if [[ -f "$ENV_FILE" ]]; then
  NOTION_ACCESS_TOKEN="$(grep -E '^NOTION_ACCESS_TOKEN=' "$ENV_FILE" 2>/dev/null | tail -1 | cut -d= -f2-)"
fi

if [[ -z "$DATA_SOURCE_ID" ]]; then
  echo "sync-notion-tracker.sh: no tracker.notion.data_source_id in $PROFILE_YML — skipping (set tracker.type: notion first)." >&2
  [[ "$DRY_RUN" == 1 ]] && exit 0
  echo "$(date '+%F %T') skipped: no data_source_id configured" >>"$LOG"
  exit 0
fi

if [[ "$DRY_RUN" == 1 ]]; then
  echo "sync-notion-tracker.sh --dry-run"
  echo "  repo:                 $REPO"
  echo "  profile.yml:          $PROFILE_YML"
  echo "  applications_db_id:   ${APPLICATIONS_DB_ID:-<unset>}"
  echo "  data_source_id:       ${DATA_SOURCE_ID:-<unset>}"
  echo "  notion token in .env: $([[ -n "$NOTION_ACCESS_TOKEN" ]] && echo yes || echo no)"
  echo "  would sync data/applications.md against collection://$DATA_SOURCE_ID (no network calls made)"
  exit 0
fi

PROMPT="$(cat <<EOF
Run the weekly JOB OP Notion -> jobhunter tracker sync. Work in career-ops (cwd).

1. Query the Notion JOB OP data source (collection://$DATA_SOURCE_ID)
   via the Notion MCP tools. For every page read: Name (company), Position (role),
   Status, Application date, Rejection date, Rejection reason, First ITW (interview date).
2. Read data/applications.md. It is a pipe table:
   # | Date | Company | Role | Score | Status | PDF | Report | Notes
   Canonical statuses: Evaluated, Applied, Responded, Interview, Offer, Rejected, Discarded, SKIP.
3. Match each Notion page to a tracker row by Company (=Notion Name) + Role (=Position),
   case-insensitive, allowing obvious variants (AG suffix, punctuation).
   MULTI-APPLICATION COMPANIES (#defect-C, found 2026-09-15): when a company has more
   than one tracker row but only ONE Notion page, the page's structured Status/Position
   reflect only ONE of the applications — a second application's outcome can be buried
   as free text inside that same page's Rejection reason (e.g. "rejection received for
   the SECOND application only: <role>..."). Before leaving any same-company tracker
   row unmatched, read that company's Rejection reason (and Job description) text for a
   second role name + outcome and reconcile it against the otherwise-unmatched row too.
4. If the Notion Status maps to a DIFFERENT canonical status than the row currently has,
   UPDATE the Status column and append a dated note. Mapping:
     Applied     -> Applied
     Rejected    -> Rejected   (append "Rejected {rejection date}: {reason}" to Notes)
     Interview   -> Interview  (append "Interview {First ITW}" to Notes)
     No Answer   -> keep Applied, append "No answer as of {today}" to Notes
     In progress -> Evaluated
     To apply    -> Evaluated
5. Only UPDATE existing rows. NEVER add new rows. Change ONLY the Status and Notes columns.
   Status field: no markdown bold, no dates inside the status cell.
6. After edits run: node normalize-statuses.mjs && node verify-pipeline.mjs
7. Print a concise summary: rows changed (company: old -> new), plus any Notion entries
   with no tracker match (list them; do NOT add them). Edit no file except data/applications.md.
   Submit nothing.
EOF
)"

echo "===== $(date '+%F %T') sync start =====" >>"$LOG"
claude -p "$PROMPT" \
  --dangerously-skip-permissions >>"$LOG" 2>&1
echo "===== $(date '+%F %T') sync end (exit $?) =====" >>"$LOG"
