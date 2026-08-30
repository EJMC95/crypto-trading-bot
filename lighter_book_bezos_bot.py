#!/usr/bin/env python3
"""
lighter_book_bezos_bot.py — 🚀 Jeff Bezos-inspired shadow book.

Design: "Day 1 Flywheel" using the proven Douglas execution engine with a
faster, highly liquid, continuation-tilted profile for Lighter-only shadow
deployment.
"""
from __future__ import annotations

import os
import sys

# Bezos profile defaults (all overridable through env):
# - slightly lower impulse bar to increase opportunity rate
# - asymmetric bracket toward upside capture
# - shorter max hold and higher liquidity floor
os.environ.setdefault("DOUGLAS_IMPULSE_K", "2.2")
os.environ.setdefault("DOUGLAS_SL_ATR", "0.9")
os.environ.setdefault("DOUGLAS_TP_ATR", "1.8")
os.environ.setdefault("DOUGLAS_MAX_HOLD_H", "8")
os.environ.setdefault("DOUGLAS_CLIP_USD", "100")
os.environ.setdefault("DOUGLAS_MAX_POSITIONS", "5")
os.environ.setdefault("DOUGLAS_MIN_VOL_M", "2.0")
os.environ.setdefault("DOUGLAS_UNIVERSE_N", "24")
os.environ.setdefault("DOUGLAS_ALLOW_NONCRYPTO", "0")

import lighter_book_douglas_bot as core  # noqa: E402

core.BOT = "book-bezos"
core.START_EQUITY = float(os.environ.get("BEZOS_START_EQUITY_USD", "100"))


def main() -> None:
    core.main()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        core._selftest()
        sys.exit(0)
    # (vw) route through the shared organ wrapper so a crash records on the
    # book's own bot_state key instead of dying silently behind run_all.sh's
    # `|| true` (audit_organ_silence — I13: a dead loop runs no handler).
    import bot_pnl_store as store  # noqa: E402
    sys.exit(store.organ_main("book-bezos", main))
