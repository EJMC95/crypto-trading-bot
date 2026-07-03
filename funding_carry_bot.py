#!/usr/bin/env python3
"""
funding_carry_bot.py — DRY-RUN Hyperliquid funding-rate carry harvester.

WHY THIS BOT EXISTS (2026-07-03)
  The fleet's trend bots are (correctly) flat in risk-off chop, so nothing
  earns while the tide is out. Funding carry is the classic all-weather
  income strategy: perp funding is paid every hour by the crowded side of
  the book, and a DELTA-NEUTRAL position (perp on one side, hedge on the
  other) collects it without directional exposure. In extreme-fear regimes
  funding often runs hot on the short side — exactly when the trend bots
  sit out.

MODEL (paper, deliberately explicit about what is and is not simulated)
  - Reads REAL hourly funding rates from Hyperliquid mainnet public info
    (no keys, read-only, no orders ever).
  - When a liquid coin's funding annualizes above ENTER_APR, "open" a carry:
    funding > 0 (longs pay shorts)  -> short perp + long spot hedge
    funding < 0 (shorts pay longs)  -> long perp + short spot hedge
  - While open, accrue funding on the notional at the LIVE hourly rate each
    loop (rates decay — accrual follows them down, no entry-rate anchoring).
  - Costs: perp taker both sides + hedge-leg fees/spread both sides, charged
    half at open, half at close (HEDGE_COST covers that the hedge lives on
    another venue/spot book).
  - Close when annualized funding decays below EXIT_APR, flips against the
    position, or MAX_HOLD_H passes.
  NOT modelled: basis drift between perp and hedge venue, hedge borrow cost
  for the short-spot case, and liquidation risk (delta-neutral at 1x has
  none in practice). Treat results as the honest-but-favourable case.

  Realized episodes are mirrored into the shared Postgres paper_trades
  ledger (same scheme as the sniper) so cumulative P&L survives restarts.

Usage:
    python funding_carry_bot.py            # dry-run forever (the only mode)
    python funding_carry_bot.py --once     # single scan then exit (smoke test)
"""

import argparse
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store  # guarded Postgres publisher (no-op without DATABASE_URL)

BOT = "perps-funding-carry"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
NOTIONAL = 200.0          # quote notional per carry position
MAX_POSITIONS = 5         # at most 5 concurrent carries (=$1000 fully deployed)
MIN_DAY_VOLUME = 5e6      # only coins with >= $5M 24h notional volume

# Funding thresholds, ANNUALIZED (hourly rate * 24 * 365). Hyperliquid's
# baseline funding is ~0.0000125/h ~= 11%/yr; we want clearly-hot funding.
ENTER_APR = 0.20          # open when |annualized funding| >= 20%
EXIT_APR = 0.08           # close when it decays below 8% (or flips sign)
MAX_HOLD_H = 7 * 24       # recycle capital after a week regardless

# Round-trip friction, as fractions of notional per SIDE of the round trip.
PERP_FEE = 0.00045        # HL taker per perp fill (conservative base tier)
HEDGE_COST = 0.0010       # hedge-leg fee + spread per fill (other venue/spot)
OPEN_COST = PERP_FEE + HEDGE_COST    # charged at open; same again at close

LOOP_SECONDS = 300        # funding is hourly; 5-min polling is plenty

HOURS_PER_YEAR = 24 * 365


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def fetch_funding(info):
    """Return {coin: {"rate": hourly_funding, "mark": mark_px, "vol": day_ntl_vol}}
    for every perp on Hyperliquid mainnet. Public data, no keys."""
    meta, ctxs = info.meta_and_asset_ctxs()
    out = {}
    for asset, ctx in zip(meta["universe"], ctxs):
        try:
            out[asset["name"]] = {
                "rate": float(ctx.get("funding") or 0.0),
                "mark": float(ctx.get("markPx") or 0.0),
                "vol": float(ctx.get("dayNtlVlm") or 0.0),
            }
        except (TypeError, ValueError):
            continue
    return out


def main():
    p = argparse.ArgumentParser(description="DRY-RUN Hyperliquid funding-carry harvester")
    p.add_argument("--once", action="store_true", help="Single scan then exit.")
    args = p.parse_args()

    try:
        from hyperliquid.info import Info
        from hyperliquid.utils import constants
    except ImportError:
        print("Missing hyperliquid-python-sdk (see requirements.txt)")
        sys.exit(1)

    # MAINNET public info for REAL funding rates. Read-only — this bot never
    # constructs an Exchange object and cannot place orders.
    info = Info(constants.MAINNET_API_URL, skip_ws=True)

    # Cumulative realized P&L survives restarts via the Postgres ledger.
    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(BOT)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:
        pass

    positions = {}  # coin -> dict(side, notional, opened_ts, accrued, fees, entry_apr)

    # [2026-07-03 PERSIST] Restore open carries from Postgres so a redeploy keeps
    # accrued funding + entry levels (realized already restores from the ledger
    # above). Saved after every published loop below.
    try:
        _saved = store.load_state(BOT)
        if _saved and isinstance(_saved.get("positions"), dict) and _saved["positions"]:
            positions = _saved["positions"]
            print(f"[{now_iso()}] restored {len(positions)} open carry position(s) "
                  f"from saved state")
    except Exception:
        pass

    print(f"[{now_iso()}] funding-carry DRY-RUN start | enter>={ENTER_APR:.0%} APR "
          f"exit<{EXIT_APR:.0%} | ${NOTIONAL:.0f} x max {MAX_POSITIONS} | "
          f"friction {2*OPEN_COST*1e4:.0f}bps round-trip | realized so far "
          f"${realized:+.2f} ({n_closed} closed)")

    last_ts = time.time()
    while True:
        t0 = time.time()
        try:
            fund = fetch_funding(info)
        except Exception as e:
            print(f"[{now_iso()}] funding fetch failed ({e!r}); retrying next loop")
            fund = None

        if fund:
            dt_h = (t0 - last_ts) / 3600.0
            last_ts = t0

            # ---- manage open carries ------------------------------------
            for coin in list(positions):
                pos = positions[coin]
                f = fund.get(coin)
                if f is None:
                    continue  # coin missing this poll; accrual just pauses
                rate = f["rate"]
                apr = rate * HOURS_PER_YEAR
                # Accrue at the LIVE rate: we receive |funding| while it keeps
                # our sign, and PAY it if the rate flips before we exit.
                sign = -1.0 if pos["side"] == "short_perp" else 1.0
                pos["accrued"] += (-sign) * rate * dt_h * pos["notional"]
                held_h = (t0 - pos["opened_ts"]) / 3600.0

                flipped = (pos["side"] == "short_perp" and apr < 0) or \
                          (pos["side"] == "long_perp" and apr > 0)
                decayed = abs(apr) < EXIT_APR
                expired = held_h >= MAX_HOLD_H
                if not (flipped or decayed or expired):
                    continue

                pos["fees"] += OPEN_COST * pos["notional"]  # closing friction
                pnl = pos["accrued"] - pos["fees"]
                reason = "flip" if flipped else ("decay" if decayed else "max_hold")
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                print(f"[{now_iso()}] CLOSE {coin} {pos['side']} after {held_h:.1f}h "
                      f"| accrued {pos['accrued']:+.2f} fees {pos['fees']:.2f} "
                      f"| pnl {pnl:+.2f} [{reason}] | realized {realized:+.2f}")
                try:
                    store.publish_paper_trade(
                        BOT, trade_id=f"{coin}:{pos['opened_ts']:.0f}",
                        pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=coin,
                        opened_at=datetime.fromtimestamp(
                            pos["opened_ts"], timezone.utc).isoformat(),
                        closed_at=datetime.now(timezone.utc).isoformat(),
                        reason=reason)
                except Exception:
                    pass
                del positions[coin]

            # ---- scan for new carries ------------------------------------
            if len(positions) < MAX_POSITIONS:
                candidates = sorted(
                    ((c, f) for c, f in fund.items()
                     if c not in positions and f["vol"] >= MIN_DAY_VOLUME
                     and abs(f["rate"] * HOURS_PER_YEAR) >= ENTER_APR),
                    key=lambda cf: -abs(cf[1]["rate"]))
                for coin, f in candidates[:MAX_POSITIONS - len(positions)]:
                    apr = f["rate"] * HOURS_PER_YEAR
                    side = "short_perp" if f["rate"] > 0 else "long_perp"
                    positions[coin] = {
                        "side": side, "notional": NOTIONAL, "opened_ts": t0,
                        "accrued": 0.0, "fees": OPEN_COST * NOTIONAL,
                        "entry_apr": apr,
                    }
                    print(f"[{now_iso()}] OPEN {coin} {side} ${NOTIONAL:.0f} "
                          f"| funding {apr:+.1%} APR (hedged delta-neutral)")

            # ---- publish snapshot ----------------------------------------
            open_pnl = sum(p["accrued"] - p["fees"] for p in positions.values())
            top = sorted(fund.items(), key=lambda cf: -abs(cf[1]["rate"]))[:3]
            try:
                store.publish(
                    BOT, status="online",
                    equity=START_EQUITY + realized + open_pnl,
                    pnl_abs=realized,
                    open_trades=len(positions),
                    closed_trades=n_closed, wins=n_wins, losses=n_closed - n_wins,
                    extra={"mode": "dry-run", "open_pnl": round(open_pnl, 2),
                           # NOT "positions": the dashboard reserves that key for
                           # the stock bots' list-of-dicts holdings format.
                           "carries": {c: f"{p['side']}@{p['entry_apr']:+.0%}"
                                       for c, p in positions.items()},
                           "hottest_funding_apr": {
                               c: f"{f['rate']*HOURS_PER_YEAR:+.1%}" for c, f in top}},
                )
            except Exception:
                pass

            # [2026-07-03 PERSIST] Durable open-carry state -> Postgres.
            try:
                store.save_state(BOT, {"positions": positions})
            except Exception:
                pass

            held = ", ".join(f"{c}({p['side'][0]})" for c, p in positions.items()) or "none"
            print(f"[{now_iso()}] scan ok | {len(fund)} perps | open: {held} "
                  f"| open_pnl {open_pnl:+.2f} | realized {realized:+.2f}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


if __name__ == "__main__":
    main()
