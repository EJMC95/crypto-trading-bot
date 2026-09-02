#!/bin/bash
# [2026-09-02 (xh)] MAKE THE LOCAL SUITE HONEST FROM THE FIRST COMMAND.
#
# THE INCIDENT. A remote session's container never ran this repo's own install,
# so `python3 -m pytest tests/` reported EIGHT failures that had nothing to do
# with the tree: seven `ModuleNotFoundError: psycopg2` and one
# `VenueError: lighter-sdk missing`. Both packages are DECLARED correctly —
# `requirements-test.txt` carries `psycopg2-binary>=2.9` and `requirements.txt`
# pins `lighter-sdk==1.1.2` — and CI installs both. Only the session was wrong.
#
# WHY THAT COSTS SOMETHING RATHER THAN BEING A NUISANCE: a suite with a standing
# red floor cannot be used as a pre-push check. Every run needed a human to
# decide, again, which reds were "the environment" — and the day this shipped
# that judgement had to be made three separate times before a REAL-MONEY push.
# A baseline of 8 expected failures is exactly where the 9th hides. Same shape
# as this repo's own rule that empty output is not a negative result: a red you
# have learned to ignore is a detector you have turned off.
#
# THE VERSION IS NEVER TYPED HERE. `requirements.txt` is the single source of
# truth `scripts/audit_sdk_pin.py` enforces, and the real-money signer binaries
# ride that pin — so this greps the pin exactly as `.github/workflows/tests.yml`
# does. A second copy of the version would be a second rule ((hj)), and this one
# decides how real money is signed.
set -euo pipefail

# Remote sessions only: a local machine has its own venv and its own opinions,
# and a startup hook that installs into it uninvited is a worse bug than the one
# this closes.
if [ "${CLAUDE_CODE_REMOTE:-}" != "true" ]; then
  exit 0
fi

cd "${CLAUDE_PROJECT_DIR:-.}"

# NO `pip install --upgrade pip` here, deliberately, though the CI job does it:
# this image's pip is Debian-managed, so the upgrade dies with "Cannot uninstall
# pip 24.0, RECORD file not found" and `set -e` takes the whole hook down with
# it — a session would then start with NO deps because of a line that installs
# none of them. Caught by running the hook rather than reading it.
python3 -m pip install --quiet -r requirements-test.txt

# The wheel version comes from requirements.txt — never hardcoded here, where it
# could drift from what the live images actually sign with.
grep -E '^(lighter-sdk|websockets)' requirements.txt \
  | sed 's/#.*//' \
  | xargs python3 -m pip install --quiet

# Both imports are ASSERTED, mirroring the CI job's own guard ("a silent skip is
# the rot this job exists to prevent"). A hook that installs nothing and exits 0
# is byte-identical to one that worked, which is the failure this repo names in
# CLAUDE.md: a check that inspects nothing reports clean.
python3 - <<'PY'
import importlib.metadata as md
import psycopg2  # noqa: F401 — the import IS the assertion
import lighter   # noqa: F401
print(f"session-start: psycopg2 {md.version('psycopg2-binary')} · "
      f"lighter-sdk {md.version('lighter-sdk')} — suite deps ready")
PY
