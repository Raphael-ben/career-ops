#!/usr/bin/env bash
# leak-check.sh — PII leak verifier for job-hunter repos.
#
# Usage:
#   leak-check.sh --worktree|--history|--messages [repo_path] [patterns_file]
#
#   repo_path      defaults to "."
#   patterns_file  defaults to $JOBHUNTER_PII_PATTERNS, else
#                  $HOME/Claude-code/job-hunter-data/pii-patterns.txt
#
#   NOTE: that fallback path is machine-specific (this developer's own
#   home directory layout). Anyone else running this tool on another
#   machine or repo MUST pass their own patterns_file explicitly — the
#   fallback is a convenience for one person, never a requirement.
#
# Modes:
#   --worktree  scans currently tracked files (git ls-files) for PII
#               patterns. Fast, catches what's live right now.
#   --history   scans every blob ever committed, reachable from any ref,
#               for PII patterns. Catches things removed from HEAD but
#               still sitting in git history (the far more common leak).
#               Binary blobs (PDFs, images) are still scanned — via
#               `strings` — because a tracked PDF/CV can carry PII in
#               otherwise-uncompressed text runs that a naive binary-skip
#               would miss.
#   --messages  scans commit METADATA (author/committer names+emails) and
#               commit MESSAGES across all refs. Blob scanners are blind
#               to these by construction — a name quoted inside a commit
#               message lives in the commit object, not any blob.
#
# Exit code: 1 if any match found, 0 if clean, 2 on usage/setup error.
#
# If trufflehog is on PATH, this script prints a note suggesting a
# deeper secret scan with it. It never invokes trufflehog itself.

set -euo pipefail

mode="${1:-}"
repo="${2:-.}"
patterns="${3:-${JOBHUNTER_PII_PATTERNS:-$HOME/Claude-code/job-hunter-data/pii-patterns.txt}}"

if [[ "$mode" != "--worktree" && "$mode" != "--history" && "$mode" != "--messages" ]]; then
  echo "Usage: $0 --worktree|--history|--messages [repo_path] [patterns_file]" >&2
  exit 2
fi

if [[ ! -f "$patterns" ]]; then
  echo "leak-check.sh: patterns file not found: $patterns" >&2
  exit 2
fi

if command -v trufflehog >/dev/null 2>&1; then
  echo "note: trufflehog is on PATH — for a deeper secret scan also run:" >&2
  echo "  trufflehog git file://$repo" >&2
fi

hits=0

if [[ "$mode" == "--worktree" ]]; then
  matches="$(git -C "$repo" ls-files -z | xargs -0 grep -lIiEf "$patterns" 2>/dev/null || true)"
  if [[ -n "$matches" ]]; then
    echo "$matches"
    hits=1
  fi
  exit "$hits"
fi

if [[ "$mode" == "--messages" ]]; then
  # Commit metadata + full messages, all refs. %B = raw body incl. subject.
  matches="$(git -C "$repo" log --all --format='%H %an <%ae> %cn <%ce>%n%B' \
    | grep -iEf "$patterns" || true)"
  if [[ -n "$matches" ]]; then
    echo "$matches"
    hits=1
  fi
  exit "$hits"
fi

# --history: walk every blob reachable from any ref.
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

git -C "$repo" rev-list --objects --all > "$tmp/objects.txt"

# Batch the type check (one git process for all objects) so we only
# do per-object work for actual blobs.
awk '{print $1}' "$tmp/objects.txt" \
  | git -C "$repo" cat-file --batch-check='%(objectname) %(objecttype)' \
  | awk '$2=="blob"{print $1}' > "$tmp/blobs.txt"

while IFS= read -r sha; do
  [[ -z "$sha" ]] && continue
  # strings first: works uniformly for text and binary blobs (a binary
  # PDF/JPG with embedded plaintext still yields matchable printable runs).
  match="$(git -C "$repo" cat-file blob "$sha" 2>/dev/null | strings | grep -iEf "$patterns" -m1 || true)"
  if [[ -n "$match" ]]; then
    path="$(awk -v s="$sha" '$1==s{$1=""; sub(/^ /,""); print; exit}' "$tmp/objects.txt")"
    pattern_hit=""
    while IFS= read -r p; do
      [[ -z "$p" ]] && continue
      if grep -qiE "$p" <<<"$match"; then
        pattern_hit="$p"
        break
      fi
    done < "$patterns"
    printf '%s\t%s\t%s\n' "$sha" "${path:-<no-path-in-history>}" "$pattern_hit"
    hits=1
  fi
done < "$tmp/blobs.txt"

exit "$hits"
