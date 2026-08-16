#!/usr/bin/env bash
# Give a Claude session its OWN worktree — the complete fix for the shared-tree
# damage that `session_commit.py` can only mitigate.
#
#   scripts/new_session_worktree.sh <name>     # create + print the workflow
#   scripts/new_session_worktree.sh --list     # what exists now
#   scripts/new_session_worktree.sh --selftest # offline checks
#
# WHY (2026-08-16 (nx)/(ny)). Three sessions share one worktree, which means one
# index and one set of files. `(lz)` recorded the damage; 16-Aug measured that
# the prescribed mitigation, `git commit -o <paths>`, ignores the shared INDEX
# but NOT the shared WORKING TREE — so a path list naming CHANGELOG.md or
# CLAUDE.md still commits whatever another session has written there. In one
# session that produced: four changelog-letter collisions, three of this
# session's edits swept into other sessions' commits, one entry destroyed
# (90 lines) by a global letter-rename, and commits repeatedly dropped by
# concurrent rebases.
#
# A worktree gives a session a PRIVATE index and a PRIVATE set of files, so none
# of that is reachable. The workflow cost is real and worth naming: git refuses
# to check out `main` in two worktrees at once, so each session works on its own
# branch and publishes by rebasing onto `origin/main`. **That is the point, not
# a tax** — two sessions appending to CHANGELOG.md now collide as a REBASE
# CONFLICT you must resolve, instead of one silently overwriting the other.
# Loud beats silent; every failure listed above was silent.
#
# WHAT THIS CANNOT DO: relocate a session that is already running. A shell's
# working directory is fixed when it starts. Existing sessions keep sharing the
# main worktree until they are restarted; this is for the next one.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# [(of)] Worktrees are registered against the MAIN worktree, never against the
# one you happen to be standing in. Running this from inside a worktree made
# $ROOT that worktree, so `$WT_DIR` matched nothing and `--prune-stale` reported
# a serene "0 stale, 0 kept" while every stale worktree sat untouched — a reaper
# that silently reaps nothing. `git worktree list` always prints the main
# worktree first; that is the anchor.
MAIN_ROOT="$(git -C "$ROOT" worktree list --porcelain 2>/dev/null | sed -n '1s/^worktree //p')"
[ -n "$MAIN_ROOT" ] || MAIN_ROOT="$ROOT"
WT_DIR="$MAIN_ROOT/.claude/worktrees"

usage() { sed -n '2,32p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

# Sanitise a session name into something safe for a branch and a directory.
# Pure, so --selftest can drive it: lowercase, non-alnum -> '-', squeeze and
# trim '-', cap length. A name that sanitises to nothing is rejected by the
# caller rather than silently becoming a directory called "-".
sanitize() {
  printf '%s' "$1" \
    | tr '[:upper:]' '[:lower:]' \
    | sed -e 's/[^a-z0-9]/-/g' -e 's/-\{2,\}/-/g' -e 's/^-//' -e 's/-$//' \
    | cut -c1-40
}

selftest() {
  local got
  for pair in "Feature X:feature-x" "  spaces  here :spaces-here" \
              "UPPER_case/slash:upper-case-slash" "a--b:a-b" "-lead-trail-:lead-trail"; do
    got="$(sanitize "${pair%%:*}")"
    [ "$got" = "${pair##*:}" ] || { echo "sanitize('${pair%%:*}') = '$got', want '${pair##*:}'" >&2; exit 1; }
  done
  [ -z "$(sanitize '!!!')" ] || { echo "a name with no usable chars must sanitize to empty" >&2; exit 1; }
  local longname; longname="$(sanitize "$(printf 'x%.0s' $(seq 80))")"
  [ "${#longname}" -le 40 ] || { echo "long names must be capped, got ${#longname}" >&2; exit 1; }
  # The exclude rule that keeps worktrees out of `git status` must be present,
  # or every session's worktree is untracked noise in every other's.
  # CHECK THE PATTERN, NOT A PATH: `git check-ignore` on a directory-only
  # pattern (`.claude/worktrees/`) only matches when that directory EXISTS, and
  # in a fresh worktree it does not — so the path-based form failed the selftest
  # from precisely the place sessions will run it. Caught by running this from
  # inside the first worktree it created.
  local excl; excl="$(git -C "$ROOT" rev-parse --git-common-dir)/info/exclude"
  grep -qE '(^|/)\.claude/worktrees/?$' "$excl" "$ROOT/.gitignore" 2>/dev/null \
    || { echo "FAIL: .claude/worktrees is not excluded — add it to $excl" >&2; exit 1; }
  grep -qx '\.venv' "$excl" 2>/dev/null \
    || { echo "FAIL: the .venv symlink is not excluded — add '.venv' to $excl" >&2; exit 1; }
  echo "new_session_worktree selftest OK (name sanitising incl. empty and over-long cases; worktrees are git-ignored)"
}

# [(of)] Reap worktrees nobody is using. EVERY gate must pass, because the cost
# of a wrong removal is another session's work: it must live under
# .claude/worktrees/, not be the one you are standing in, have NOTHING
# uncommitted or untracked, hold NO commit that is not already on origin/main,
# and have gone untouched for --days. Anything that fails a gate is REPORTED
# with the reason rather than skipped silently — a reaper you cannot audit is
# one you stop trusting. `--dry-run` shows the plan and removes nothing.
prune_stale() {
  local days="${1:-3}" dry="${2:-}"
  git -C "$MAIN_ROOT" fetch origin --quiet 2>/dev/null || true
  git -C "$MAIN_ROOT" worktree prune            # drop records whose path is gone
  local here removed=0 kept=0
  here="$(git rev-parse --show-toplevel 2>/dev/null || echo /nonexistent)"
  while IFS= read -r p; do
    case "$p" in "$WT_DIR"/*) ;; *) continue ;; esac    # ours only
    [ "$p" = "$here" ] && { echo "  KEEP  $(basename "$p") — you are in it"; kept=$((kept+1)); continue; }
    local dirty head uniq newest age_d
    dirty="$(git -C "$p" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
    if [ "$dirty" != "0" ]; then
      echo "  KEEP  $(basename "$p") — $dirty uncommitted/untracked file(s)"; kept=$((kept+1)); continue
    fi
    head="$(git -C "$p" rev-parse HEAD 2>/dev/null)"
    uniq="$(git -C "$MAIN_ROOT" rev-list --count "$head" ^origin/main 2>/dev/null || echo 999)"
    if [ "$uniq" != "0" ]; then
      echo "  KEEP  $(basename "$p") — $uniq commit(s) not on origin/main"; kept=$((kept+1)); continue
    fi
    newest="$(find "$p" -type f -not -path '*/.git/*' -not -path '*/.venv/*' \
              -newermt "-${days} days" -print -quit 2>/dev/null)"
    if [ -n "$newest" ]; then
      echo "  KEEP  $(basename "$p") — edited within ${days}d"; kept=$((kept+1)); continue
    fi
    if [ -n "$dry" ]; then
      echo "  WOULD REMOVE  $(basename "$p")"
    else
      git -C "$MAIN_ROOT" worktree remove "$p" && echo "  removed  $(basename "$p")"
    fi
    removed=$((removed+1))
  done < <(git -C "$MAIN_ROOT" worktree list --porcelain | sed -n 's/^worktree //p')
  echo "  ${removed} stale, ${kept} kept"
  # Branches left behind by a removed worktree, but ONLY when fully on
  # origin/main and referenced by no tracked file (the gate0 branch is named in
  # CLAUDE.md and must survive).
  git -C "$MAIN_ROOT" branch --list 'claude/*' --format='%(refname:short) %(worktreepath)' \
  | while read -r b wp; do
      [ -n "$wp" ] && continue
      [ "$(git -C "$MAIN_ROOT" rev-list --count "$b" ^origin/main 2>/dev/null || echo 999)" = "0" ] || continue
      git -C "$MAIN_ROOT" grep -q "${b#claude/}" HEAD -- '*.md' '*.py' '*.yml' 2>/dev/null \
        && { echo "  KEEP branch $b — referenced in a tracked file"; continue; }
      [ -n "$dry" ] && { echo "  WOULD DELETE branch $b"; continue; }
      git -C "$MAIN_ROOT" branch -D "$b" >/dev/null 2>&1 && echo "  deleted branch $b"
    done
}

case "${1:---help}" in
  --selftest) selftest; exit 0 ;;
  --list)
    git -C "$MAIN_ROOT" worktree list
    exit 0 ;;
  --prune-stale)
    shift
    DAYS=3; DRY=""
    while [ $# -gt 0 ]; do
      case "$1" in
        --days) DAYS="$2"; shift 2 ;;
        --dry-run) DRY=1; shift ;;
        *) echo "unknown option: $1" >&2; exit 1 ;;
      esac
    done
    prune_stale "$DAYS" "$DRY"
    exit 0 ;;
  -h|--help) usage; exit 0 ;;
esac

NAME="$(sanitize "$1")"
[ -n "$NAME" ] || { echo "error: '$1' has no usable characters for a name" >&2; exit 1; }
BRANCH="claude/$NAME"
PATH_WT="$WT_DIR/$NAME"

[ -e "$PATH_WT" ] && { echo "error: $PATH_WT already exists" >&2; exit 1; }

git -C "$MAIN_ROOT" fetch origin --quiet 2>/dev/null || true
BASE="origin/main"
git -C "$ROOT" rev-parse --verify --quiet "$BASE" >/dev/null || BASE="HEAD"

mkdir -p "$WT_DIR"
git -C "$MAIN_ROOT" worktree add -b "$BRANCH" "$PATH_WT" "$BASE" >/dev/null
echo "created worktree : $PATH_WT"
echo "on branch        : $BRANCH  (from $BASE)"

# The suite runs as `.venv/bin/python3`; a fresh worktree has no .venv and a
# second virtualenv would be a slow, drifting copy. Symlink the one at the root
# — it is gitignored, so it is not part of the checkout either way.
if [ -d "$ROOT/.venv" ] && [ ! -e "$PATH_WT/.venv" ]; then
  ln -s "$ROOT/.venv" "$PATH_WT/.venv"
  echo "linked .venv     : -> $ROOT/.venv"
fi
# .gitignore carries `.venv/` (trailing slash = directories only), which does
# NOT match the SYMLINK above — so without this every session's worktree shows
# a permanent `?? .venv`, i.e. untracked noise sitting in the blast radius of
# any `git add -A`. The exclude file is per-clone and untracked, so this is a
# local fix that needs no change to the shared .gitignore. Idempotent.
EXCL="$(git -C "$ROOT" rev-parse --git-common-dir)/info/exclude"
if [ -f "$EXCL" ] && ! grep -qx '\.venv' "$EXCL"; then
  printf '\n# [(ny)] the per-worktree .venv SYMLINK (.gitignore .venv/ misses it)\n.venv\n' >> "$EXCL"
  echo "excluded .venv   : $EXCL"
fi
# reports/ is gitignored and written by the daily jobs; create it so a report
# run in this worktree does not fail on a missing directory.
mkdir -p "$PATH_WT/reports"

cat <<EOF

Work here:
    cd "$PATH_WT"

Commit normally — your index and your files are PRIVATE, so a concurrent
\`git add\` or edit cannot reach them and yours cannot reach anyone else's.

Publish to main when green:
    git fetch origin && git rebase origin/main && git push origin HEAD:main

If two sessions touched CHANGELOG.md, that rebase CONFLICTS. That is the fix
working: resolve it by keeping BOTH entries. The alternative — the shared
worktree — resolved it by silently keeping one.

Clean up when the session ends:
    git worktree remove "$PATH_WT"   # add --force if it has stray files
EOF
