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

# [2026-09-01 (vw)] DECLARED HAZARD, not fixed: these are the ENGINE's env
# names, so a service-level `DOUGLAS_*` var set for any reason steers this
# wrapper too (service envs are process-global in the freqtrade container).
# Acceptable while 🧘 douglas runs in its OWN service; revisit if that changes.

import lighter_book_douglas_bot as core  # noqa: E402

core.BOT = "book-bezos"
# [2026-09-01 (vw)] $1,000 — THE FLEET STANDARD ("$1,000 paper each, no
# top-ups"). PR #238 shipped "100", which against the engine's fixed $100 clip
# x 5 slots minted an accidental 5x-gross book on the 1x paper broker — the
# exact ruin-invisible fiction (vu) measured the same week. At $1k the same
# profile runs 0.5x, and the census below now says the number out loud.
core.START_EQUITY = float(os.environ.get("BEZOS_START_EQUITY_USD", "1000"))
# [2026-09-01 (vw)] I22 birth stamp — variant-owned, so the engine stays
# variant-agnostic. Dated 1-Sep: the day this book first actually RUNS. It
# merged 30-Aug missing its engine COPY and crash-looped without ever
# publishing, so stamping the merge day would spend window it never had.
core.BOOK_BORN_TS["book-bezos"] = 1788220800.0   # 2026-09-01T00:00:00Z


def main() -> None:
    core.main()


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        core._selftest()
        sys.exit(0)
    # [2026-09-01 (vw)] the shared death-recorder: run_all.sh launches this
    # behind `|| true`, so a bare crash is INVISIBLE — which is exactly how
    # this bot crash-looped for two days after #238 shipped it without its
    # engine COPY. `audit_organ_silence` was red on that from merge day.
    import bot_pnl_store as store  # noqa: E402
    sys.exit(store.organ_main("book-bezos", main))
