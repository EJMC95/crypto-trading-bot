#!/bin/bash
# Install this repo's git hooks.
#
# WHY A SCRIPT: git hooks live in .git/hooks/, which is NOT tracked by git.
# A hook cannot be shipped by committing it — every clone, and every sibling
# worktree in .claude/worktrees/, needs it installed explicitly. CI is the
# backstop for anyone who never runs this; the hook is the fast local catch.
#
#   scripts/install_git_hooks.sh                  install hooks
#   scripts/install_git_hooks.sh --with-gitleaks  also fetch the gitleaks binary
#   scripts/install_git_hooks.sh --uninstall      remove hooks
#
# The pre-commit hook runs `gitleaks git --staged`, which scans ONLY what you
# are about to commit. Bypass in a genuine emergency with `git commit
# --no-verify` — and then go fix whatever made that necessary.

set -euo pipefail

GITLEAKS_VERSION="8.30.1"
# Pinned checksums for every platform we run on (dev = darwin/arm64,
# CI = linux/x64). A binary that scans for secrets must not float — same
# doctrine as audit_sdk_pin.py. An unverifiable download is REFUSED, not
# installed with a warning.
GITLEAKS_SHA256_darwin_arm64="b40ab0ae55c505963e365f271a8d3846efbc170aa17f2607f13df610a9aeb6a5"
GITLEAKS_SHA256_darwin_x64="dfe101a4db2255fc85120ac7f3d25e4342c3c20cf749f2c20a18081af1952709"
GITLEAKS_SHA256_linux_arm64="e4a487ee7ccd7d3a7f7ec08657610aa3606637dab924210b3aee62570fb4b080"
GITLEAKS_SHA256_linux_x64="551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOOK_DIR="$REPO_ROOT/.git/hooks"

if [ ! -d "$REPO_ROOT/.git" ]; then
  echo "ERROR: $REPO_ROOT/.git not found (worktree? run from the main checkout)"
  exit 1
fi

if [ "${1:-}" = "--uninstall" ]; then
  rm -f "$HOOK_DIR/pre-commit"
  echo "Removed $HOOK_DIR/pre-commit"
  exit 0
fi

if [ "${1:-}" = "--with-gitleaks" ]; then
  echo "Installing gitleaks ${GITLEAKS_VERSION} -> ~/.local/bin/gitleaks"
  ARCH="$(uname -m)"
  case "$(uname -s)" in
    Darwin) OS=darwin ;;
    Linux)  OS=linux  ;;
    *) echo "ERROR: unsupported OS $(uname -s)"; exit 1 ;;
  esac
  case "$ARCH" in
    arm64|aarch64) A=arm64 ;;
    x86_64)        A=x64   ;;
    *) echo "ERROR: unsupported arch $ARCH"; exit 1 ;;
  esac
  TARBALL="gitleaks_${GITLEAKS_VERSION}_${OS}_${A}.tar.gz"
  URL="https://github.com/gitleaks/gitleaks/releases/download/v${GITLEAKS_VERSION}/${TARBALL}"
  TMP="$(mktemp -d)"
  trap 'rm -rf "$TMP"' EXIT
  curl -sSL --max-time 180 -o "$TMP/$TARBALL" "$URL"
  # Fail CLOSED: no pinned checksum for this platform => refuse.
  VARNAME="GITLEAKS_SHA256_${OS}_${A}"
  EXPECTED="${!VARNAME:-}"
  if [ -z "$EXPECTED" ]; then
    echo "ERROR: no pinned checksum for ${OS}/${A} — REFUSING to install."
    echo "Add GITLEAKS_SHA256_${OS}_${A} from the release's checksums.txt."
    exit 1
  fi
  if command -v shasum >/dev/null 2>&1; then
    GOT="$(shasum -a 256 "$TMP/$TARBALL" | awk '{print $1}')"
  else
    GOT="$(sha256sum "$TMP/$TARBALL" | awk '{print $1}')"
  fi
  if [ "$GOT" != "$EXPECTED" ]; then
    echo "ERROR: checksum mismatch — REFUSING to install"
    echo "  expected $EXPECTED"
    echo "  got      $GOT"
    exit 1
  fi
  echo "  checksum verified (${OS}/${A})"
  mkdir -p "$HOME/.local/bin"
  tar xzf "$TMP/$TARBALL" -C "$TMP" gitleaks
  mv "$TMP/gitleaks" "$HOME/.local/bin/gitleaks"
  chmod +x "$HOME/.local/bin/gitleaks"
  xattr -d com.apple.quarantine "$HOME/.local/bin/gitleaks" 2>/dev/null || true
  echo "  installed: $("$HOME/.local/bin/gitleaks" version)"
fi

mkdir -p "$HOOK_DIR"
cat > "$HOOK_DIR/pre-commit" <<'HOOK'
#!/bin/bash
# Secret-leak pre-commit hook. Installed by scripts/install_git_hooks.sh.
# Scans ONLY staged changes. Bypass: git commit --no-verify (then fix the cause).
REPO_ROOT="$(git rev-parse --show-toplevel)"
GL=""
for c in "$(command -v gitleaks 2>/dev/null)" "$HOME/.local/bin/gitleaks"; do
  [ -n "$c" ] && [ -x "$c" ] && GL="$c" && break
done

if [ -z "$GL" ]; then
  echo "pre-commit: gitleaks not found — install with:"
  echo "  scripts/install_git_hooks.sh --with-gitleaks"
  echo "REFUSING the commit (this guard fails CLOSED)."
  exit 1
fi

if ! "$GL" git "$REPO_ROOT" --staged -c "$REPO_ROOT/.gitleaks.toml" \
      --no-banner --redact --log-level error; then
  cat <<'MSG'

------------------------------------------------------------------
COMMIT BLOCKED — a secret was found in your STAGED changes.

  * Remove the secret. Read it from an env var instead.
  * If it is a FALSE POSITIVE, add a DECLARED exception to
    .gitleaks.toml with a REASON (the BORN_DARK_OK convention).
    Never silence a finding without writing down why.
  * Genuine emergency: git commit --no-verify

Note: a secret already written to .git history is not removed by
deleting the line in a later commit. Rotate it.
------------------------------------------------------------------
MSG
  exit 1
fi
exit 0
HOOK

chmod +x "$HOOK_DIR/pre-commit"
echo "Installed $HOOK_DIR/pre-commit"
echo
echo "Verify with:  python3 scripts/audit_secret_leak.py --selftest"
