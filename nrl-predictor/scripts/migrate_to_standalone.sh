#!/usr/bin/env bash
# Migrate nrl-predictor/ out of crypto-trading-bot into its own repo,
# preserving this directory's commit history via git subtree split.
#
# Prereq: the empty private repo exists (create at
#   https://github.com/new?name=nrl-predictor&visibility=private — no README).
# Run from anywhere inside the crypto-trading-bot clone:
#   bash nrl-predictor/scripts/migrate_to_standalone.sh [remote-url]
set -euo pipefail

REMOTE="${1:-https://github.com/EJMC95/nrl-predictor.git}"
SRC_BRANCH="claude/nrl-predictor-phases-1-2-vtb133"
cd "$(git rev-parse --show-toplevel)"

git fetch origin "$SRC_BRANCH"
git checkout "$SRC_BRANCH" 2>/dev/null || git checkout -b "$SRC_BRANCH" "origin/$SRC_BRANCH"
git subtree split --prefix=nrl-predictor -b nrl-predictor-standalone
git push "$REMOTE" nrl-predictor-standalone:main
git branch -D nrl-predictor-standalone
echo "Done: $REMOTE (branch main). Re-download data with: pip install -r requirements.txt && python scripts/run_phase1.py"
