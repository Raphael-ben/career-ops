#!/usr/bin/env bash
# update-guard.sh -- the ONLY sanctioned way to update career-ops.
# Never run a bare `node update-system.mjs apply`. This wrapper neutralizes
# five known updater failure modes:
#   1. stale baseline (commit-subject grep) wrongly "preserving" changed files
#   2. VERSION lagging the release after apply
#   3. stale-file PRUNE deleting fork-only files under updater-owned dirs
#   4. partial-checkout drift (siblings not refreshed) -> broken imports
#   5. interface lag on preserved system files (e.g. providers/_http.mjs)
#
# Usage:
#   tools/update-guard.sh               full guarded update
#   tools/update-guard.sh --repair-only verify manifest, restore from snapshot
#   tools/update-guard.sh --smoke-only  run the smoke suite only
#
# PII patterns: $JOBHUNTER_PII_PATTERNS, else leak-check.sh's own default.

set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

GUARD_DIR=".update-guard"
MANIFEST="$GUARD_DIR/manifest.txt"
SNAPSHOT_FILE="$GUARD_DIR/snapshot-sha"
PATHS_FILE="tools/protected-paths.txt"
PY="${JOBHUNTER_PYTHON:-$ROOT/../.venv/bin/python3}"
[ -x "$PY" ] || PY="python3"

VERSION_BEFORE=""
VERSION_AFTER=""
REMOTE_VERSION=""
SNAPSHOT_SHA=""
REPAIR_COMMIT="none"
RESTORED=()
SMOKE_RESULTS=()
SMOKE_FAILED=0

log() { printf '[update-guard] %s\n' "$*"; }
loud() { printf '\n!!!!!! [update-guard] %s\n\n' "$*" >&2; }

protected_list() {
  grep -vE '^[[:space:]]*(#|$)' "$PATHS_FILE" | sed 's/[[:space:]]*$//'
}

version_of() {
  [ -f VERSION ] && awk 'NR==1{print $1}' VERSION || echo "unknown"
}

ensure_gitignore() {
  if ! grep -qxF '.update-guard/' .gitignore 2>/dev/null; then
    printf '\n# update-guard working state\n.update-guard/\n' >> .gitignore
    log "added .update-guard/ to .gitignore"
  fi
}

snapshot_working_state() {
  local changed
  changed="$(git status --porcelain --untracked-files=no)"
  if [ -n "$changed" ]; then
    log "modified tracked files found; committing snapshot"
    git add -u
    git commit -q -m "chore: snapshot pre-update working state" \
      -m "Files:" -m "$(printf '%s\n' "$changed")" \
      -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
  fi
  SNAPSHOT_SHA="$(git rev-parse HEAD)"
  mkdir -p "$GUARD_DIR"
  printf '%s\n' "$SNAPSHOT_SHA" > "$SNAPSHOT_FILE"
}

build_manifest() {
  mkdir -p "$GUARD_DIR"
  : > "$MANIFEST"
  local p
  while IFS= read -r p; do
    if [ -f "$p" ]; then
      shasum -a 256 "$p" >> "$MANIFEST"
    else
      loud "protected path missing before update: $p"
    fi
  done < <(protected_list)
}

# Verify manifest; restore failed/missing paths from the snapshot commit.
repair_protected() {
  [ -f "$MANIFEST" ] && [ -f "$SNAPSHOT_FILE" ] || { loud "no manifest/snapshot; run a full update first"; return 1; }
  SNAPSHOT_SHA="$(cat "$SNAPSHOT_FILE")"
  local bad=() line p
  while IFS= read -r line; do
    p="${line#*  }"
    if ! printf '%s\n' "$line" | shasum -a 256 -c - >/dev/null 2>&1; then
      bad+=("$p")
    fi
  done < "$MANIFEST"
  if [ "${#bad[@]}" -eq 0 ]; then
    log "manifest OK: all protected files intact"
    return 0
  fi
  for p in "${bad[@]}"; do
    loud "protected file changed/missing, restoring from ${SNAPSHOT_SHA:0:8}: $p"
    mkdir -p "$(dirname "$p")"
    local mode
    mode="$(git ls-tree "$SNAPSHOT_SHA" -- "$p" | awk '{print $1}')"
    if [ -z "$mode" ]; then
      loud "not present in snapshot, cannot restore: $p"
      continue
    fi
    git show "$SNAPSHOT_SHA:$p" > "$p"
    [ "$mode" = "100755" ] && chmod +x "$p"
    RESTORED+=("$p")
  done
  # re-verify
  local still=0
  for p in "${RESTORED[@]}"; do
    line="$(grep -F "  $p" "$MANIFEST" | head -1)"
    printf '%s\n' "$line" | shasum -a 256 -c - >/dev/null 2>&1 || { loud "STILL FAILING after restore: $p"; still=1; }
  done
  return "$still"
}

stamp_version() {
  [ -n "$REMOTE_VERSION" ] || return 0
  local cur
  cur="$(version_of)"
  if [ "$cur" != "$REMOTE_VERSION" ]; then
    log "stamping VERSION $cur -> $REMOTE_VERSION"
    if [ -f VERSION ] && grep -q 'x-release-please-version' VERSION; then
      printf '%s # x-release-please-version\n' "$REMOTE_VERSION" > VERSION
    else
      printf '%s\n' "$REMOTE_VERSION" > VERSION
    fi
  fi
}

remove_stray_baks() {
  # The updater writes *.bak next to preserved files; they are gitignored
  # (*.bak*) so just delete the ones it created during this run.
  local f n=0
  while IFS= read -r f; do
    rm -f "$f"; n=$((n + 1))
  done < <(find . -path ./.git -prune -o -path ./node_modules -prune -o -path ./.update-guard -prune -o \
             -name '*.bak' -type f -newer "$SNAPSHOT_FILE" -print)
  log "removed $n stray .bak file(s)"
}

commit_repairs() {
  local paths=("${RESTORED[@]}")
  [ -f VERSION ] && paths+=(VERSION)
  if [ "${#paths[@]}" -gt 0 ]; then
    git add -- "${paths[@]}" 2>/dev/null || true
  fi
  if ! git diff --cached --quiet; then
    git commit -q -m "chore: post-update guard repairs (v${VERSION_AFTER})" \
      -m "Restored: ${RESTORED[*]:-none}" \
      -m "Co-Authored-By: Claude Fable 5 <noreply@anthropic.com>"
    REPAIR_COMMIT="$(git rev-parse --short HEAD)"
  fi
}

smoke_record() { # name rc
  if [ "$2" -eq 0 ]; then SMOKE_RESULTS+=("PASS  $1")
  else SMOKE_RESULTS+=("FAIL  $1"); SMOKE_FAILED=1; loud "SMOKE FAILED: $1"; fi
}

run_smoke() {
  local rc out

  rc=0
  out="$(node doctor.mjs --json 2>&1)" || rc=$?
  if [ "$rc" -eq 0 ] || [ -n "$out" ]; then
    printf '%s' "$out" | node -e '
      let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
        const i=s.indexOf("{");let j;
        try{j=JSON.parse(s.slice(i));}catch(e){console.error("doctor: unparseable JSON");process.exit(1);}
        if(j.onboardingNeeded!==false){console.error("doctor: onboardingNeeded="+j.onboardingNeeded);process.exit(1);}
      })' || rc=1
  fi
  smoke_record "doctor.mjs --json (onboardingNeeded==false)" "$rc"

  rc=0; "$PY" scan_aggregate.py --selftest >/dev/null 2>&1 || rc=$?
  smoke_record "scan_aggregate.py --selftest" "$rc"

  rc=0; "$PY" notion_finalize.py --selftest >/dev/null 2>&1 || rc=$?
  smoke_record "notion_finalize.py --selftest" "$rc"

  rc=0
  node --input-type=module -e '
    import {readdirSync} from "node:fs";
    import {pathToFileURL} from "node:url";
    import {resolve} from "node:path";
    const dir=resolve("providers");let bad=0;
    for(const f of readdirSync(dir)){
      if(!f.endsWith(".mjs")||f.startsWith("_"))continue;
      try{await import(pathToFileURL(resolve(dir,f)).href);}
      catch(e){bad++;console.error("provider load failed: "+f+": "+(e&&e.message));}
    }
    process.exit(bad?1:0);' >"$GUARD_DIR/provider-load.log" 2>&1 || rc=$?
  [ "$rc" -ne 0 ] && cat "$GUARD_DIR/provider-load.log" >&2
  smoke_record "provider load-check (providers/*.mjs)" "$rc"

  rc=0
  local leak lrc=0
  leak="$(bash tools/leak-check.sh --worktree . ${JOBHUNTER_PII_PATTERNS:+"$JOBHUNTER_PII_PATTERNS"} 2>&1)" || lrc=$?
  if [ "$lrc" -ge 2 ]; then rc=1; printf '%s\n' "$leak" >&2
  elif [ "$lrc" -eq 1 ]; then
    local rest
    rest="$(printf '%s\n' "$leak" | grep -vE 'docs/.*\.svg' | grep -v '^$' || true)"
    if [ -n "$rest" ]; then rc=1; printf '%s\n' "$rest" >&2; fi
  fi
  smoke_record "leak-check --worktree (docs/*.svg tolerated)" "$rc"
}

summary() {
  printf '\n========== update-guard summary ==========\n'
  printf 'version:        %s -> %s\n' "${VERSION_BEFORE:-?}" "${VERSION_AFTER:-?}"
  printf 'snapshot sha:   %s\n' "${SNAPSHOT_SHA:0:8}"
  printf 'restored files: %s\n' "${RESTORED[*]:-none}"
  printf 'repairs commit: %s\n' "$REPAIR_COMMIT"
  printf 'smoke:\n'
  local r; for r in "${SMOKE_RESULTS[@]:-}"; do [ -n "$r" ] && printf '  %s\n' "$r"; done
  printf '==========================================\n'
}

do_update() {
  ensure_gitignore
  VERSION_BEFORE="$(version_of)"
  snapshot_working_state
  build_manifest

  local check status
  check="$(node update-system.mjs check)"
  log "check: $check"
  status="$(printf '%s' "$check" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{const j=JSON.parse(s);console.log(j.status+" "+(j.remote||""))}catch(e){console.log("error ")}})')"
  REMOTE_VERSION="${status#* }"
  if [ "${status%% *}" != "update-available" ]; then
    log "no update to apply (status: ${status%% *}); up-to-date"
    exit 0
  fi

  log "applying update to v$REMOTE_VERSION"
  if ! node update-system.mjs apply --confirm; then
    log "apply --confirm failed; retrying without flag"
    node update-system.mjs apply
  fi

  # Pre-repair: updater may have committed; manifest check is on the working tree.
  local rrc=0
  repair_protected || rrc=$?
  stamp_version
  VERSION_AFTER="$(version_of)"
  remove_stray_baks
  commit_repairs
  [ "$rrc" -ne 0 ] && SMOKE_FAILED=1
  run_smoke
  summary
  [ "$SMOKE_FAILED" -eq 0 ] || { loud "update-guard finished WITH FAILURES"; exit 1; }
}

case "${1:-}" in
  --repair-only)
    VERSION_BEFORE="$(version_of)"; VERSION_AFTER="$VERSION_BEFORE"
    rc=0; repair_protected || rc=$?
    summary; exit "$rc" ;;
  --smoke-only)
    mkdir -p "$GUARD_DIR"; VERSION_BEFORE="$(version_of)"; VERSION_AFTER="$VERSION_BEFORE"
    run_smoke; summary; exit "$SMOKE_FAILED" ;;
  "") do_update ;;
  *) echo "usage: $0 [--repair-only|--smoke-only]" >&2; exit 2 ;;
esac
