#!/usr/bin/env python3
"""
audit_sdk_pin.py — the wheel that SIGNS REAL ORDERS must be PINNED, everywhere.

WHY THIS EXISTS (2026-07-17). `requirements.txt` carried `lighter-sdk>=1.1.1`.
1.1.2 shipped 10-Jul, so every image built after that silently resolved to it —
and that wheel is the SIGNER (`SignerClient`, `create_market_order`, the Go
binary, the nonce manager). The code moving real money changed version with no
commit, no review, no backtest. MEASURED on the live Funding Farmer's boot
banner (17-Jul 10:58Z): `lighter-sdk 1.1.2`, while the repo's own header still
claimed 1.1.1 was the verified one.

WHY A NEW SCRIPT AND NOT `audit_image_imports`. That guard reconstructs each
image's FILE set and walks repo-local imports — its own docstring says it
"verified the FILE and not the WHEEL", which is the 17-Jul (m) incident where
`lighter-sdk` was missing from an image entirely and the taker crash-looped for
an hour. A pip dependency is invisible to it BY CONSTRUCTION. This is the
sibling control for the layer it cannot see.

Dependency-free, milliseconds. Run it like the other guards.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# Packages whose version can move real money. A floating spec on ANY of these is
# a finding, wherever it is declared.
SIGNS_REAL_MONEY = ("lighter-sdk",)

# spec forms that FLOAT: >=, >, ~=, ^, *, or a bare name with no spec at all.
_FLOATS = re.compile(r"(>=|>|~=|\^|\*)")
_PINNED = re.compile(r"==\s*\d+(\.\d+)*")


def _decls():
    """(file, lineno, raw) for every place a watched package is installed."""
    out = []
    for p in sorted(ROOT.glob("requirements*.txt")) + sorted(ROOT.glob("Dockerfile*")):
        try:
            lines = p.read_text().splitlines()
        except Exception:  # noqa: BLE001
            continue
        for i, raw in enumerate(lines, 1):
            code = raw.split("#", 1)[0]          # comments are prose, not installs
            if not code.strip():
                continue
            for pkg in SIGNS_REAL_MONEY:
                if pkg in code:
                    out.append((p.relative_to(ROOT), i, code.strip(), pkg))
    return out


def audit():
    bad = []
    for rel, ln, code, pkg in _decls():
        # the spec that applies to THIS package on this line
        m = re.search(re.escape(pkg) + r"\s*([^\"' ]*)", code)
        spec = (m.group(1) if m else "") or ""
        if _PINNED.search(spec):
            continue
        if _FLOATS.search(spec) or spec == "":
            bad.append((rel, ln, code, pkg, spec or "<no spec>"))
    return bad


def _selftest():
    """The guard must FAIL on a floating spec — a guard that only ever passes on
    a clean repo is the vacuous bar `audit_image_imports` warns about."""
    assert _PINNED.search("==1.1.2")
    assert _PINNED.search("== 1.1.2")
    assert not _PINNED.search(">=1.1.1")
    for floating in (">=1.1.1", ">1.0", "~=1.1", "*"):
        assert _FLOATS.search(floating), floating
    # NEGATIVE FIXTURE: a floating spec anywhere must be caught
    assert _FLOATS.search(">=1.1.1") and not _PINNED.search(">=1.1.1"), \
        "the exact shape that shipped 1.1.2 onto real money must be a finding"
    # and a pinned one must not
    assert _PINNED.search("==1.1.2") and "==1.1.2".count("=") == 2
    print("audit_sdk_pin selftest OK (pins pass, floats fail, negative fixture)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    found = audit()
    if not found:
        n = len(_decls())
        print(f"audit_sdk_pin: OK — every real-money wheel is PINNED "
              f"({n} declaration(s) across requirements*/Dockerfile*).")
        sys.exit(0)
    print("FLOATING dependency on code that SIGNS REAL ORDERS:\n")
    for rel, ln, code, pkg, spec in found:
        print(f"  {rel}:{ln}")
        print(f"      {code}")
        print(f"      -> {pkg} is {spec}: the image resolves to PyPI's latest on")
        print(f"         BUILD DAY, so the signer can change with no commit.\n")
    print("  Fix: pin it (==X.Y.Z) to the version the live fleet is MEASURED to")
    print("  run — read the boot banner, never lighter.__version__ (it lies).")
    sys.exit(1)
