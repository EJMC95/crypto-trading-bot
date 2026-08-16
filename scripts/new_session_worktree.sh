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
WT_DIR="$ROOT/.claude/worktrees"

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

case "${1:---help}" in
  --selftest) selftest; exit 0 ;;
  --list)
    git -C "$ROOT" worktree list
    exit 0 ;;
  -h|--help) usage; exit 0 ;;
esac

NAME="$(sanitize "$1")"
[ -n "$NAME" ] || { echo "error: '$1' has no usable characters for a name" >&2; exit 1; }
BRANCH="claude/$NAME"
PATH_WT="$WT_DIR/$NAME"

[ -e "$PATH_WT" ] && { echo "error: $PATH_WT already exists" >&2; exit 1; }

git -C "$ROOT" fetch origin --quiet 2>/dev/null || true
BASE="origin/main"
git -C "$ROOT" rev-parse --verify --quiet "$BASE" >/dev/null || BASE="HEAD"

mkdir -p "$WT_DIR"
git -C "$ROOT" worktree add -b "$BRANCH" "$PATH_WT" "$BASE" >/dev/null
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
