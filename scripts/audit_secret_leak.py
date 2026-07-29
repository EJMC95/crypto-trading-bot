#!/usr/bin/env python3
"""Secret-leak guard — no credential reaches a commit.

WHY THIS EXISTS
---------------
Credentials reached commits three times (14/15/16-Jul-2026). The mechanism:
`.claude/settings.local.json` stores approved commands VERBATIM, so any command
containing a secret became a stored secret, and a live Postgres URL accumulated
into the working copy one `git add .` from being permanent. Gitignoring that
file (22-Jul, b88be6b) stopped THAT bleed. It did not stop the next one, and
"remember not to paste secrets" is the same control that already failed 3x.

This is the sibling of the born-dark / sdk-pin / venue-purity guards: a
detective control that runs on every push, plus a pre-commit hook so the
failure is caught before the secret is even written to local history.

WHAT IT CHECKS
--------------
`gitleaks dir .` with this repo's `.gitleaks.toml`, which extends the default
ruleset with FOUR custom rules the default set misses:

  db-connection-uri   a database URI carrying inline credentials. MEASURED
                      29-Jul: the default ruleset scans a full Postgres URL
                      CLEAN. That is exactly the class that leaked here.
  private-key-block   PEM/OpenSSH key material, including single-line form
  aws-access-key-id   a bare AKIA… string (also missed by the default set)
  railway-token       Railway API/project tokens

--selftest (the negative fixture)
---------------------------------
Plants 8 known secrets and asserts ALL 8 are caught. A guard that cannot see
is worse than no guard, because it reports green. The first draft of the
allowlist matched the whole LINE against words like "example", and a live
GitHub PAT with a trailing `# example config` comment sailed straight through
— this selftest is what caught that.

Usage:
    python3 scripts/audit_secret_leak.py            # scan the tree
    python3 scripts/audit_secret_leak.py --selftest # prove the guard can see
    scripts/install_git_hooks.sh                    # install the pre-commit hook
"""
import json
import os
import shutil
import subprocess
import sys
import tempfile

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONFIG = os.path.join(REPO, ".gitleaks.toml")

# Each entry: (label, file content line). ALL must be caught by --selftest.
#
# Every value below is FAKE and exists only to prove the scanner can see.
# The `gitleaks:allow` comments exempt THIS source line — they are not written
# into the probe file (only the string value is), so the planted secrets are
# still fully live when the selftest scans them. Per-line exemption is
# deliberate: a path-wide allowlist here would blind the guard to a REAL
# secret someone later pastes into this file.
PLANTED = [
    ("postgres URI",
     'DB = "postgresql://fleetuser:Sup3rS3cretPassw0rd123@monorail.proxy.rlwy.net:41234/railway"'),  # gitleaks:allow
    ("AWS access key id",
     'AWS = "AKIA2E0A8F3B7C1D9E4G"'),  # gitleaks:allow
    ("AWS secret key",
     'AWS_SECRET = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYz9a1B2c3D4e5F6"'),  # gitleaks:allow
    ("GitHub PAT",
     'GH_PAT = "ghp_a1B2c3D4e5F6g7H8i9J0k1L2m3N4o5P6q7R8"'),  # gitleaks:allow
    ("Slack bot token",
     'SLACK = "xoxb-123456789012-1234567890123-aBcDeFgHiJkLmNoPqRsTuVwX"'),  # gitleaks:allow
    ("private key block",
     'PRIVATE = "-----BEGIN OPENSSH PRIVATE KEY-----b3BlbnNzaC1rZXktdjEA-----END OPENSSH PRIVATE KEY-----"'),  # gitleaks:allow
    # Regression fixture: an allowlist that matched the LINE let this through.
    ("PAT on a line saying 'example'",
     'SNEAKY = "ghp_z9Y8x7W6v5U4t3S2r1Q0p9O8n7M6l5K4j3I2"  # example config'),  # gitleaks:allow
    ("mysql URI",
     'MYSQL = "mysql://root:hunter2hunter2@10.0.0.5:3306/prod"'),  # gitleaks:allow
]


def _gitleaks():
    """Locate the gitleaks binary, or exit with install instructions."""
    for cand in (shutil.which("gitleaks"),
                 os.path.expanduser("~/.local/bin/gitleaks")):
        if cand and os.path.exists(cand):
            return cand
    sys.stderr.write(
        "FAIL: gitleaks not found.\n"
        "  Install:  scripts/install_git_hooks.sh --with-gitleaks\n"
        "  or:       https://github.com/gitleaks/gitleaks/releases\n"
        "This guard FAILS CLOSED — a missing scanner is not a pass.\n")
    sys.exit(2)


def _scan(target):
    """Run gitleaks on target; return the list of findings (redacted)."""
    gl = _gitleaks()
    with tempfile.NamedTemporaryFile("r", suffix=".json", delete=False) as fh:
        report = fh.name
    try:
        subprocess.run(
            [gl, "dir", target, "-c", CONFIG, "--no-banner", "--redact",
             "--report-format", "json", "--report-path", report,
             "--exit-code", "0", "--log-level", "error"],
            capture_output=True, text=True, timeout=300)
        with open(report) as fh:
            content = fh.read().strip()
        return json.loads(content) if content else []
    finally:
        os.path.exists(report) and os.unlink(report)


def selftest():
    """Plant known secrets; every one must be caught."""
    print("SELFTEST: planting 8 known secrets, all must be caught\n")
    tmpdir = tempfile.mkdtemp(prefix="gl_selftest_")
    try:
        # Inside the repo so path-scoped allowlists are exercised as in prod.
        probe = os.path.join(REPO, "_gitleaks_selftest_probe.py")
        with open(probe, "w") as fh:
            fh.write("\n".join(line for _, line in PLANTED) + "\n")
        try:
            findings = _scan(probe)
        finally:
            os.path.exists(probe) and os.unlink(probe)

        caught = {f.get("StartLine") for f in findings}
        missed = []
        for idx, (label, _) in enumerate(PLANTED, start=1):
            hit = idx in caught
            print(f"  {'PASS' if hit else 'FAIL'}  {label}")
            if not hit:
                missed.append(label)

        print(f"\n  caught {len(caught)}/{len(PLANTED)}")
        if missed:
            print("\nFAIL: the guard is BLIND to:")
            for m in missed:
                print(f"  - {m}")
            print("Fix .gitleaks.toml before trusting a green scan.")
            return 1
        print("\nPASS: the guard can see every planted secret.")
        return 0
    finally:
        shutil.rmtree(tmpdir, ignore_errors=True)


def main():
    if "--selftest" in sys.argv:
        return selftest()

    findings = _scan(REPO)
    if not findings:
        print("PASS: no secrets found in the working tree.")
        return 0

    print(f"FAIL: {len(findings)} potential secret(s) found.\n")
    for f in findings:
        print(f"  {f.get('File')}:{f.get('StartLine')}  [{f.get('RuleID')}]")
        print(f"    {f.get('Description','')}")
    print("\nIf a finding is a FALSE POSITIVE, add a DECLARED exception to")
    print(".gitleaks.toml with a reason (the BORN_DARK_OK convention).")
    print("Never silence a finding without writing down why.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
