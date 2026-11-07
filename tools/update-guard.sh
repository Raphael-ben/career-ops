#!/usr/bin/env bash
# update-guard.sh -- the ONLY sanctioned way to update career-ops.
#
# CONTRACT: update-guard either leaves career-ops at the new version with the
# smoke green, or rolls back to the previous commit. Never partial.
#   - pre-flight: the smoke must be green BEFORE apply (else nothing is applied:
#     a broken environment is not the update's fault and must be fixed first)
#   - any failure after apply starts (updater error, unrestorable protected
#     file, red smoke, Ctrl-C) -> git reset --hard <pre-update SHA>, red banner,
#     exit 1
#
# Never run a bare `node update-system.mjs apply`. Known updater failure modes
# this wrapper neutralizes:
#   1. stale baseline (commit-subject grep) wrongly "preserving" changed files
#   2. VERSION lagging the release after apply
#   3. stale-file PRUNE deleting fork-only files under updater-owned dirs
#   4. partial-checkout drift (siblings not refreshed) -> broken imports
#   5. interface lag on preserved system files (e.g. providers/_http.mjs)
#   6. upstream renaming/dropping a flag or config key the fork depends on
#      (scan-ats-full.mjs defaults wedged ats-full in v1.32) -> drift WARN list
#   7. a "green" smoke that never ran the real scanner -> smoke runs
#      `node scan.mjs --dry-run` and import-closure checks every pro/ script
#
# Usage:
#   tools/update-guard.sh                    full guarded update
#   tools/update-guard.sh --check            pre-flight: drift check + smoke, applies nothing
#   tools/update-guard.sh --repair-only      verify manifest, restore from snapshot
#   tools/update-guard.sh --smoke-only       run the smoke suite only
#   tools/update-guard.sh --refresh-manifest re-hash protected files at HEAD
#                                            (run after committing a protected-file edit)
#
# Env: JOBHUNTER_PYTHON (default ../.venv/bin/python3), GUARD_SCAN_TIMEOUT
# (seconds for the scan.mjs dry run, default 600), JOBHUNTER_PII_PATTERNS.

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
export PY
SCAN_TIMEOUT="${GUARD_SCAN_TIMEOUT:-600}"

VERSION_BEFORE=""
VERSION_AFTER=""
REMOTE_VERSION=""
SNAPSHOT_SHA=""
REPAIR_COMMIT="none"
RESTORED=()
SMOKE_RESULTS=()
SMOKE_FAILED=0
FIRST_FAIL=""
FIRST_FAIL_LOG=""
DRIFT_WARNS=()
APPLYING=0
DONE=0

log() { printf '[update-guard] %s\n' "$*"; }
loud() { printf '\n!!!!!! [update-guard] %s\n\n' "$*" >&2; }
red() { if [ -t 2 ]; then printf '\033[1;31m%s\033[0m\n' "$*" >&2; else printf '%s\n' "$*" >&2; fi; }

# with_timeout SECS cmd... -- macOS has no timeout(1). Runs cmd in its own
# process group; on expiry TERM then KILL the whole group, exit 124.
with_timeout() {
  local secs="$1"; shift
  perl -e '
    my $t = shift; my $pid = fork // die "fork: $!";
    if (!$pid) { setpgrp(0, 0); exec @ARGV or exit 127 }
    $SIG{ALRM} = sub { kill "TERM", -$pid; sleep 2; kill "KILL", -$pid; exit 124 };
    alarm $t; waitpid($pid, 0);
    exit($? & 127 ? 128 + ($? & 127) : $? >> 8)' "$secs" "$@"
}

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
      -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
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

refresh_manifest() {
  local dirty
  dirty="$(git status --porcelain -- $(protected_list))"
  if [ -n "$dirty" ]; then
    loud "uncommitted protected files; commit them first:"; printf '%s\n' "$dirty" >&2
    return 1
  fi
  SNAPSHOT_SHA="$(git rev-parse HEAD)"
  mkdir -p "$GUARD_DIR"
  printf '%s\n' "$SNAPSHOT_SHA" > "$SNAPSHOT_FILE"
  build_manifest
  log "manifest refreshed at ${SNAPSHOT_SHA:0:8} ($(wc -l < "$MANIFEST" | tr -d ' ') files)"
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
      -m "Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>"
    REPAIR_COMMIT="$(git rev-parse --short HEAD)"
  fi
}

# ---------------------------------------------------------------- rollback

rollback() { # reason
  set +e
  local reason="$1" pkg_changed=0 f
  git diff --quiet "$SNAPSHOT_SHA" -- package.json package-lock.json 2>/dev/null || pkg_changed=1
  git reset -q --hard "$SNAPSHOT_SHA"
  # untracked, non-ignored files the updater dropped in during this run
  while IFS= read -r f; do
    [ -f "$f" ] && [ "$f" -nt "$SNAPSHOT_FILE" ] && rm -f -- "$f"
  done < <(git ls-files --others --exclude-standard)
  [ "$pkg_changed" -eq 1 ] && with_timeout 300 npm install --silent >/dev/null 2>&1
  local now; now="$(git rev-parse HEAD)"
  red ""
  red "=================================================================="
  red " UPDATE ROLLED BACK: $reason"
  red "=================================================================="
  if [ -n "$FIRST_FAIL_LOG" ] && [ -f "$FIRST_FAIL_LOG" ]; then
    red " output (last 40 lines of $FIRST_FAIL_LOG):"
    tail -40 "$FIRST_FAIL_LOG" >&2
  fi
  red " career-ops is back at ${now:0:8} (snapshot ${SNAPSHOT_SHA:0:8}), VERSION $(version_of)"
  [ "$now" = "$SNAPSHOT_SHA" ] || red " WARNING: HEAD != snapshot; inspect manually"
  red "=================================================================="
}

on_exit() {
  local rc=$?
  if [ "$APPLYING" -eq 1 ] && [ "$DONE" -eq 0 ]; then
    APPLYING=0
    rollback "${FIRST_FAIL:-update aborted (exit $rc) before the smoke went green}"
    exit 1
  fi
  exit "$rc"
}

# ---------------------------------------------------------------- smoke

smoke() { # name secs cmd-string   (cmd runs in bash -c, cwd ROOT, $PY exported)
  local name="$1" secs="$2" cmd="$3" rc=0
  local logf="$GUARD_DIR/smoke-$(printf '%s' "$name" | tr -c 'a-zA-Z0-9' '_' | cut -c1-40).log"
  with_timeout "$secs" bash -c "$cmd" >"$logf" 2>&1 || rc=$?
  if [ "$rc" -eq 0 ]; then
    SMOKE_RESULTS+=("PASS  $name")
  else
    [ "$rc" -eq 124 ] && name="$name (TIMEOUT ${secs}s)"
    SMOKE_RESULTS+=("FAIL  $name")
    SMOKE_FAILED=1
    loud "SMOKE FAILED: $name -- see $logf"
    tail -15 "$logf" >&2
    [ -n "$FIRST_FAIL" ] || { FIRST_FAIL="smoke: $name"; FIRST_FAIL_LOG="$logf"; }
  fi
}

# Scripts the fork's prompt layer calls (modes/pro + _custom) plus the fork's
# own scripts from protected-paths. Missing file = FAIL.
fork_scripts() {
  {
    grep -ohE '(node|\{PYTHON\}|python3) +(career-ops/)?[A-Za-z0-9_./-]+\.(mjs|js|py)' modes/pro/*.md modes/_custom.md 2>/dev/null \
      | awk '{print $2}' | sed 's#^career-ops/##'
    protected_list | grep -E '\.(mjs|py)$' | grep -v '^tests/'
    printf '%s\n' scan.mjs scan-ats-full.mjs doctor.mjs
  } | sort -u
}

# Relative-import closure of .mjs entry points (argv): every ./ ../ import must
# exist on disk. node --check cannot see a missing imported module.
IMPORT_CLOSURE_JS="$(cat <<'JS'
import {readFileSync, existsSync} from "node:fs";
import {resolve, dirname} from "node:path";
const re = /(?:^|[\s;])(?:import|export)\s[^;]*?from\s*["'](\.{1,2}\/[^"']+)["']|import\(\s*["'](\.{1,2}\/[^"']+)["']\s*\)|^\s*import\s*["'](\.{1,2}\/[^"']+)["']/gm;
const seen = new Set(); let bad = 0;
const walk = (f, from) => {
  if (seen.has(f)) return; seen.add(f);
  if (!existsSync(f)) { console.error("UNRESOLVED import " + f + " (from " + from + ")"); bad++; return; }
  if (!/\.m?js$/.test(f)) return;
  const src = readFileSync(f, "utf8").replace(/\/\*[\s\S]*?\*\//g, "").replace(/^\s*\/\/.*$/gm, ""); // comments carry example imports
  for (const m of src.matchAll(re)) walk(resolve(dirname(f), m[1] || m[2] || m[3]), f);
};
for (const f of process.argv.slice(1)) if (/\.mjs$/.test(f) && existsSync(f)) walk(resolve(f), "(entry)");
process.exit(bad ? 1 : 0);
JS
)"
export IMPORT_CLOSURE_JS

run_smoke() {
  mkdir -p "$GUARD_DIR"

  smoke "doctor.mjs --json (onboardingNeeded==false)" 60 '
    out="$(node doctor.mjs --json 2>&1)" || true
    printf "%s" "$out" | node -e '\''
      let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{
        const i=s.indexOf("{");let j;
        try{j=JSON.parse(s.slice(i));}catch(e){console.error("doctor: unparseable JSON\n"+s.slice(0,2000));process.exit(1);}
        if(j.onboardingNeeded!==false){console.error("doctor: onboardingNeeded="+j.onboardingNeeded);process.exit(1);}
      })'\'''

  smoke "venv python + scraper deps importable" 60 \
    '"$PY" -c "import sys, yaml, requests, rapidfuzz, scrapling, jobspy, curl_cffi; print(sys.executable, sys.version.split()[0])"'

  smoke "scan_aggregate.py --selftest" 180 '"$PY" scan_aggregate.py --selftest'
  smoke "notion_finalize.py --selftest" 60 '"$PY" notion_finalize.py --selftest'

  # existence + parse for every script the fork calls; relative-import closure
  # for every .mjs (catches the v1.17 "scan.mjs imports a file upstream never
  # shipped" crash that node --check cannot see)
  local list; list="$(fork_scripts | tr '\n' ' ')"
  smoke "fork scripts exist + parse + import closure" 120 '
    bad=0
    for f in '"$list"'; do
      [ -f "$f" ] || { echo "MISSING: $f"; bad=1; continue; }
      case "$f" in
        *.py) "$PY" -c "import ast,sys; ast.parse(open(sys.argv[1]).read(), sys.argv[1])" "$f" || { echo "PARSE: $f"; bad=1; } ;;
        *.mjs|*.js) node --check "$f" || { echo "PARSE: $f"; bad=1; } ;;
      esac
    done
    node --input-type=module -e "$IMPORT_CLOSURE_JS" '"$list"' || bad=1
    exit $bad'

  smoke "provider load-check (providers/*.mjs)" 60 '
    node --input-type=module -e '\''
      import {readdirSync} from "node:fs";
      import {pathToFileURL} from "node:url";
      import {resolve} from "node:path";
      const dir=resolve("providers");let bad=0;
      for(const f of readdirSync(dir)){
        if(!f.endsWith(".mjs"))continue;
        try{await import(pathToFileURL(resolve(dir,f)).href);}
        catch(e){bad++;console.error("provider load failed: "+f+": "+(e&&e.message));}
      }
      process.exit(bad?1:0);'\'''

  smoke "scan-ats-full.mjs --help" 30 'node scan-ats-full.mjs --help >/dev/null'
  smoke "profile-for-job.mjs runs (missing-arg usage path)" 30 \
    'out="$(node profile-for-job.mjs 2>&1)"; rc=$?; echo "$out"; ! printf "%s" "$out" | grep -qE "ERR_MODULE_NOT_FOUND|SyntaxError|ReferenceError|is not a function" && [ $rc -le 2 ]'

  # The real scanner path: network, all providers, no writes.
  smoke "scan.mjs --dry-run (real scanner path)" "$SCAN_TIMEOUT" '
    node scan.mjs --dry-run --quiet 2>&1; rc=$?
    exit $rc'
  if grep -qE 'ERR_MODULE_NOT_FOUND|SyntaxError:|ReferenceError:|TypeError: .* is not a function' \
       "$GUARD_DIR/smoke-scan_mjs___dry_run__real_scanner_path_.log" 2>/dev/null; then
    SMOKE_RESULTS+=("FAIL  scan.mjs --dry-run printed a crash signature")
    SMOKE_FAILED=1
    [ -n "$FIRST_FAIL" ] || { FIRST_FAIL="smoke: scan.mjs --dry-run crash signature"; FIRST_FAIL_LOG="$GUARD_DIR/smoke-scan_mjs___dry_run__real_scanner_path_.log"; }
  fi

  smoke "leak-check --worktree (docs/*.svg tolerated)" 120 '
    leak="$(bash tools/leak-check.sh --worktree . ${JOBHUNTER_PII_PATTERNS:+"$JOBHUNTER_PII_PATTERNS"} 2>&1)"; lrc=$?
    [ $lrc -eq 0 ] && exit 0
    [ $lrc -ge 2 ] && { echo "$leak"; exit 1; }
    rest="$(printf "%s\n" "$leak" | grep -vE "docs/.*\.svg" | grep -v "^$" || true)"
    [ -z "$rest" ] || { echo "$rest"; exit 1; }'
}

# ---------------------------------------------------------------- drift

# CLI/format surface the fork depends on, one fact per line. Diffed pre/post.
surface() {
  local f
  for f in scan.mjs scan-ats-full.mjs; do
    [ -f "$f" ] && grep -oE "'--[a-z0-9-]+'" "$f" | tr -d "'" | sort -u | sed "s#^#$f flag #"
  done
  [ -f scan.mjs ] && grep -oE "'url\\\\tfirst_seen[^']*'" scan.mjs | head -1 | sed 's#^#scan.mjs history-header #'
  return 0
}

# HEURISTIC, grep-based, WARN only. Lists flags/keys the fork uses that the
# current upstream files no longer mention.
drift_check() {
  local before="${1:-}" w f flag key
  local tmp; tmp="$(mktemp)"
  surface > "$tmp"
  if [ -n "$before" ] && [ -f "$before" ]; then
    while IFS= read -r w; do DRIFT_WARNS+=("upstream removed/changed: $w"); done < <(comm -23 "$before" "$tmp")
  fi
  rm -f "$tmp"

  # scan-ats-full.mjs flags + checkpoint keys passed/read by scan_aggregate.py
  for flag in $(grep -E '\bargs\b' scan_aggregate.py | grep -v add_argument | grep -oE '"--[a-z0-9-]+"' | tr -d '"' | sort -u); do
    grep -qF -- "'$flag'" scan-ats-full.mjs 2>/dev/null || DRIFT_WARNS+=("scan_aggregate.py passes $flag; scan-ats-full.mjs no longer lists it")
  done
  for key in $(grep -oE 'cp(\[|\.get\()"[A-Za-z_]+"' scan_aggregate.py | grep -oE '"[A-Za-z_]+"' | tr -d '"' | sort -u); do
    grep -qw -- "$key" scan-ats-full.mjs 2>/dev/null || DRIFT_WARNS+=("scan_aggregate.py reads checkpoint key '$key'; scan-ats-full.mjs no longer mentions it")
  done

  # flags the prompt layer passes to upstream node scripts
  while IFS= read -r line; do
    f="$(printf '%s' "$line" | grep -oE 'node +(career-ops/)?[A-Za-z0-9_./-]+\.mjs' | head -1 | awk '{print $2}' | sed 's#^career-ops/##')"
    [ -f "$f" ] || continue
    for flag in $(printf '%s' "$line" | grep -oE -- ' --[a-z0-9-]+' | sort -u); do
      grep -qF -- "$flag" "$f" || DRIFT_WARNS+=("modes/pro calls '$f $flag'; $f no longer mentions it")
    done
  done < <(grep -hE 'node +(career-ops/)?[A-Za-z0-9_./-]+\.mjs' modes/pro/*.md 2>/dev/null)

  # portals.yml keys nobody reads (upstream scanner or fork layer)
  if [ -f portals.yml ]; then
    local keys
    keys="$(node --input-type=module -e '
      import * as yaml from "js-yaml"; import {readFileSync} from "node:fs";
      const p=yaml.load(readFileSync("portals.yml","utf8"))||{}; const k=new Set(Object.keys(p));
      for(const c of p.tracked_companies||[]) Object.keys(c).forEach(x=>k.add(x));
      for(const s of ["title_filter","location_filter"]) Object.keys(p[s]||{}).forEach(x=>k.add(x));
      for(const q of p.search_queries||[]) Object.keys(q).forEach(x=>k.add(x));
      console.log([...k].join("\n"));' 2>/dev/null || true)"
    for key in $keys; do
      case "$key" in notes|careers_page) continue ;; esac  # careers_page: deliberately unread (dodges provider auto-detect for websearch entries)
      grep -qw -- "$key" ./*.mjs providers/*.mjs plugins/*.mjs scan_aggregate.py modes/*.md modes/pro/*.md 2>/dev/null \
        || DRIFT_WARNS+=("portals.yml key '$key' is read by no career-ops script or mode")
    done
  fi

  printf '\n---------- interface drift (HEURISTIC, grep-based, warn only) ----------\n'
  if [ "${#DRIFT_WARNS[@]}" -eq 0 ]; then
    printf '  none\n'
  else
    for w in "${DRIFT_WARNS[@]}"; do printf '  WARN  %s\n' "$w"; done
  fi
  printf -- '-------------------------------------------------------------------------\n'
}

summary() {
  printf '\n========== update-guard summary ==========\n'
  printf 'version:        %s -> %s\n' "${VERSION_BEFORE:-?}" "${VERSION_AFTER:-?}"
  printf 'snapshot sha:   %s\n' "${SNAPSHOT_SHA:0:8}"
  printf 'restored files: %s\n' "${RESTORED[*]:-none}"
  printf 'repairs commit: %s\n' "$REPAIR_COMMIT"
  printf 'drift warnings: %s\n' "${#DRIFT_WARNS[@]}"
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
  log "check: ${check:0:200}"
  status="$(printf '%s' "$check" | node -e 'let s="";process.stdin.on("data",d=>s+=d).on("end",()=>{try{const j=JSON.parse(s);console.log(j.status+" "+(j.remote||""))}catch(e){console.log("error ")}})')"
  REMOTE_VERSION="${status#* }"
  if [ "${status%% *}" != "update-available" ]; then
    log "no update to apply (status: ${status%% *}); up-to-date"
    exit 0
  fi

  log "pre-flight smoke (must be green before anything is applied)"
  run_smoke
  if [ "$SMOKE_FAILED" -ne 0 ]; then
    summary
    red "PRE-FLIGHT FAILED ($FIRST_FAIL): environment is broken BEFORE the update. Nothing applied. Fix it, then re-run."
    exit 1
  fi
  surface > "$GUARD_DIR/surface.before"
  SMOKE_RESULTS=(); FIRST_FAIL=""; FIRST_FAIL_LOG=""

  APPLYING=1   # from here on, any exit without DONE=1 rolls back
  log "applying update to v$REMOTE_VERSION (rollback target ${SNAPSHOT_SHA:0:8})"
  if ! node update-system.mjs apply --confirm; then
    log "apply --confirm failed; retrying without flag"
    node update-system.mjs apply || { FIRST_FAIL="update-system.mjs apply failed"; exit 1; }
  fi

  # Pre-repair: updater may have committed; manifest check is on the working tree.
  if ! repair_protected; then FIRST_FAIL="protected files could not be restored"; exit 1; fi
  stamp_version
  VERSION_AFTER="$(version_of)"
  remove_stray_baks
  drift_check "$GUARD_DIR/surface.before"
  run_smoke
  if [ "$SMOKE_FAILED" -ne 0 ]; then summary; exit 1; fi   # EXIT trap rolls back
  commit_repairs
  DONE=1
  APPLYING=0
  summary
  log "update OK: v$VERSION_BEFORE -> v$VERSION_AFTER, smoke green"
}

main() {
  trap on_exit EXIT
  trap 'exit 130' INT TERM
  case "${1:-}" in
    --repair-only)
      VERSION_BEFORE="$(version_of)"; VERSION_AFTER="$VERSION_BEFORE"
      rc=0; repair_protected || rc=$?
      summary; return "$rc" ;;
    --smoke-only)
      VERSION_BEFORE="$(version_of)"; VERSION_AFTER="$VERSION_BEFORE"
      run_smoke; summary; return "$SMOKE_FAILED" ;;
    --check)
      VERSION_BEFORE="$(version_of)"; VERSION_AFTER="$VERSION_BEFORE"
      log "update-system check: $(node update-system.mjs check 2>&1 | head -c 200)"
      drift_check
      run_smoke; summary; return "$SMOKE_FAILED" ;;
    --refresh-manifest) refresh_manifest ;;
    "") do_update ;;
    *) echo "usage: $0 [--check|--repair-only|--smoke-only|--refresh-manifest]" >&2; return 2 ;;
  esac
}

# Single line on purpose: the updater may rewrite this file while it runs;
# bash has already parsed main() and exits before reading further.
main "$@"; exit $?
