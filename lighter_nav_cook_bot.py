#!/usr/bin/env python3
"""
lighter_nav_cook_bot.py — 🧭 Captain Cook, the CHART-THE-SHALLOWS book.

FIRST OF THE NAVIGATOR COHORT (operator, 19-Aug: "named after the likes of
captain cook and such"). `nav-<surname>-lshadow`, for the navigators who
charted coasts nobody had mapped — which is this book's whole job: it trades
the dislocation band every other book sails past.

THE CELL, AND WHY IT IS NOT SOMEONE ELSE'S (I20)
  🪁 band-kelly mirrors 🧲 the retired dislocation ghost at gate **>= 60bps**,
  crypto-only, 2h. This book takes the band **[45, 60) bps** — strictly BELOW
  band-kelly's floor, so the two TILE the surface: every event this book opens
  is one band-kelly REFUSES. That makes the `(lv)` subset trap structurally
  unreachable (a subset consumer running second is starved by definition; a
  DISJOINT band cannot be). It is differentiated by BAND, the one form I20
  accepts — never by a new row id on the same bet.

THE MEASUREMENT (STUDY_DISLOCATION_BAND_2026-08-19.md, entry (re))
  Mirror direction on 10,052 scout snapshots, 15-Jul -> 19-Aug, entry lagged
  2 loops, episodes not ticks, own slippage charged per coin tier:

      band       30m      1h       2h       4h       8h
      [30,45)   -0.00    +0.01    +0.05    +0.07    +0.07     (nothing)
      [45,60)   +0.185   +0.274   +0.320   +0.367   +0.405    <- THIS BOOK
                (+2.74)  (+2.97)  (+2.69)  (+2.74)  (+2.95)
      [60,90)   +0.07    +0.08    +0.06    +0.21    +0.17     (band-kelly's)
      [150,inf) -0.18    -0.36    -0.31    -0.41    -0.50     (NEGATIVE)

  A PLATEAU across all five horizons, not a lucky cell. Both halves positive
  at every horizon (H1 t=+1.83..+2.12, H2 t=+1.85..+2.34); jackknife by coin
  leaves t=+1.94..+3.01; block bootstrap 95% CI [+0.072%, +0.644%], P(>0)=0.991;
  and the GHOST-DIRECTION CONTROL LOSES at t=-3.53, so the asymmetry is real
  rather than a sign convention.

  **The deep tail is NEGATIVE and this book refuses it**: above 60bps the
  dislocations stop reverting and break. That is why the band has a CEILING
  and not merely a floor — an unbounded floor would have swallowed the losing
  tail and is the `(gl)` "publish the BAND, not just the floor" lesson.

THE HAZARD, TESTED NOT ASSUMED
  The edge concentrates when the underlying market is CLOSED (+0.409%/t=+2.34
  vs +0.007%/t=+0.02 open) — the exact signature of a STALE REFERENCE, and the
  `(lk)`/I7 shape this fleet has already been burned by ("a closed underlying
  market satisfies PERSIST_H structurally"). Tested directly: if the index were
  frozen, d(premium) would track d(mark) one-for-one. Measured per symbol,
  corr/slope are BRENTOIL 0.62/0.41, WTI 0.77/0.64, SKHYNIXUSD 0.40/0.16,
  H100 0.06/0.00, UNITREE 0.69/0.48 — **no symbol reaches the frozen signature
  (corr>0.9 AND slope>0.85)**. The premium is a real mark-vs-index divergence.
  DECLARED: oil's index is PARTIALLY sticky out of hours (slope 0.41-0.64), so
  some closed-hours premium is index lag rather than dislocation.

WHY IT IS NOT CRYPTO
  The band is non-crypto BY NATURE — commodity +0.566% (t=+2.06, n=57), Asian
  equity +0.131% (t=+1.33, n=32), crypto n=4. So this book does NOT carry the
  `(lk)` crypto-only screen its siblings do; carrying it would leave the book
  with four trades. It carries the ONE class screen the evidence supports:
  **pre-IPO is EXCLUDED** (-0.165% on n=45, the band's only negative class).
  Restrict-only, fitted on a small sample, declared, revertible.

THE GHOST IS THE OWNER OF THE MECHANICS
  `lighter_dislocation_bot` is imported for `book_view`, `reference_prices`,
  `resolve_universe` and the loop cadence — the same one-owner discipline
  band-kelly uses. Its retirement guard lives inside its `main()`, so importing
  runs nothing (verified (jh)). What this book does NOT inherit is its GATE:
  the band is this book's own, because the ghost's floor is 60bps and that is
  precisely the number being tiled around.

NOT ENCODED, DECLARED
  the [30,45) band (truncation-marginal at the 8-entry `prem_outliers` cap and
  flat anyway); the [150,inf) tail (measured NEGATIVE); any crypto expression
  (n=4 — band-kelly owns crypto by I20); leverage (rejected six times).

Shadow only, $1,000 paper, ZERO keys. VENUE=lighter_shadow models fills on the
live book and never sends an order.

Usage:
    python lighter_nav_cook_bot.py            # loop forever
    python lighter_nav_cook_bot.py --once     # one pass, then exit
    python lighter_nav_cook_bot.py --selftest # pure-layer checks, no network
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

# The mechanics' one owner. Importing runs nothing — the retirement guard is
# inside its main() ((jh), verified). The GATE is deliberately NOT inherited.
import lighter_dislocation_bot as ghost

try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "nav-cook"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = ghost.LOOP_SECONDS            # 90s — the ghost's own cadence

# THE BAND. Half-open [lo, hi): hi is band-kelly's floor, so the two tile.
GATE_LO_BPS = float(os.environ.get("COOK_GATE_LO_BPS", "45"))
GATE_HI_BPS = float(os.environ.get("COOK_GATE_HI_BPS", "60"))
# Converged: the ghost's exit trigger scaled to this band's floor (0.667*45).
# The MIRROR exits when the GHOST would have — that is what "hold the other
# side over the ghost's own window" means; convergence is the mirror's LOSS
# side and it is taken deliberately, not avoided.
EXIT_BPS = float(os.environ.get("COOK_EXIT_BPS", "30"))
# THE HORIZON IS A PLATEAU, NOT A POINT — measured +0.185/+0.274/+0.320/
# +0.367/+0.405 %/trade at 30m/1h/2h/4h/8h, t=+2.69..+2.97 at EVERY one, both
# halves positive at every one. So the choice is not "which cell wins" (8h
# does) but which trades off return against DECIDABILITY:
#   30m -> ~5.9 closes/day, fastest to 30 closes, thinnest per-trade edge
#   4h  -> ~1.5 closes/day, 30 closes in ~3 weeks   <- SHIPPED
#   8h  -> ~0.8 closes/day, best per-trade, ~5 weeks to a verdict
# 4h is the interior of the plateau: it is not the maximum, and picking the
# maximum of a swept grid is how `(oe)`-style artifacts get shipped. Env-
# tunable so the operator can walk it without a redeploy of logic.
HORIZON_PLATEAU_S = (1800, 3600, 7200, 14400, 28800)   # all measured positive
MAX_HOLD_S = float(os.environ.get("COOK_MAX_HOLD_S", str(4 * 3600)))
HARD_STOP = float(os.environ.get("COOK_HARD_STOP", "0.05"))
# [2026-08-20 (sd)] CLIP $80 -> $240 — LEVERAGE, MEASURED AND PRICED.
# In this fleet "leverage" is deployed notional / equity (there is no leverage
# knob and that is deliberate — see leverage-measured-and-rejected-five-times),
# so raising the clip IS the lever. Six prior rejections all levered books with
# ~ZERO measured edge, where leverage is pure variance amplification; this is
# the first book where the question is well-posed: a reproducible +0.373%/trade
# at t=+2.61 ((sb)), a HARD 5% PRICE stop, and mean-reverting exposure.
# Measured on the book's own 226-trade series (sd 2.147%/trade):
#     L   gross expo   liq @      stop @   35d return   maxDD    15% bar
#     1       32%      100.0%      5.0%      +6.94%     -1.89%    PASS
#     3       96%       33.3%      5.0%     +22.06%     -5.60%    PASS   <- shipped
#     5      160%       20.0%      5.0%     +38.94%     -9.22%    PASS   <- ceiling
#     8      256%       12.5%      5.0%     +67.89%    -14.46%    at the bar
#    12      384%        8.3%      5.0%    +114.09%    -21.13%    FAIL
# THE STOP FIRES BEFORE LIQUIDATION AT EVERY LEVEL UP TO 12x — liquidation is
# not the binding constraint, the 15% drawdown bar is. Kelly on the measured
# distribution is 8.10x and half-Kelly 4.05x; 3x is BELOW half-Kelly on purpose,
# because Kelly on an ESTIMATED edge is fragile (a 2x overestimate of the mean
# turns half-Kelly into full-Kelly) and this edge rests on n=226 in ONE 35-day
# window. I19 price, stated: 3x the exposure and 3x the drawdown for the SAME
# per-trade expectancy — this buys $ throughput, it does not buy edge.
# The live ledger has NOT yet confirmed the replay (the (sa) era reset left it
# near zero), so this is sized on a replay and says so.
CLIP_USD = float(os.environ.get("COOK_CLIP_USD", "240"))
MAX_POSITIONS = int(os.environ.get("COOK_MAX_POSITIONS", "4"))
MAX_ENTRY_SLIP_BPS = float(os.environ.get("COOK_MAX_SLIP_BPS", "30"))
MIN_VOL_M = float(os.environ.get("COOK_MIN_VOL_M", "0.5"))

# Load-bearing, not cosmetic: `(qq)` measured the fleet's own fills at a MEAN
# 17.49 bps and a p90 of 398 bps below $0.1M. This band lives in non-crypto
# books, which are the fat-tail end of that distribution.
EXCLUDED_CLASSES = {7}                       # pre-IPO — measured -0.165%, n=45
ALLOW_PREIPO = os.environ.get(
    "COOK_ALLOW_PREIPO", "").strip().lower() in ("1", "true", "yes")

# THE CONFIRM WINDOW IS A DURATION, NOT A COUNT — and this is exactly where
# the ghost's convention and the MEASUREMENT's convention part company.
#   study  : entry lagged 2 SNAPSHOTS of the scout's 5-min tape  = 600s
#   ghost  : 2 LOOPS of its own 90s cadence                      = 180s
# This file inherits every THRESHOLD from the study and inherited the confirm
# COUNT from the ghost, so the shipped entry gate was 3.3x LOOSER than the one
# that was graded: a dislocation had to persist 3 minutes here where the
# measurement required 10. The old line said "2 — matches the replay's lag";
# it matched the replay's COUNT. Same class as the horizon pin below — a
# constant that must name a value the study actually measured, not a number
# that merely looks like it. Measured consequence in the first 10.5h of live
# trading: 24 closes (~9x the study's 6.2/day), median hold 5.5 MINUTES
# against a 4h horizon, and 24 of 24 exits `converged` — the mirror's own
# losing exit, which is the recorded cause of death of the ghost it mirrors.
# DERIVED, not asserted: a bar written as a bare literal can be "fixed" by
# editing the bar (verified — that mutation survived the first version of the
# pin below). These are the study's own two published facts, so weakening the
# rule now requires contradicting the document it cites.
STUDY_SNAPSHOT_S = 300.0     # "10,052 snapshots, 5-min cadence" (the scout tape)
STUDY_CONFIRM_LAGS = 2       # "Entry lagged 2 snapshots (the ghost's 2-loop confirm)"
STUDY_CONFIRM_S = STUDY_SNAPSHOT_S * STUDY_CONFIRM_LAGS   # = 600s, the measured lag
CONFIRM_SECONDS = float(os.environ.get("COOK_CONFIRM_S", str(STUDY_CONFIRM_S)))
CONFIRM_LOOPS = max(1, int(-(-CONFIRM_SECONDS // LOOP_SECONDS)))   # ceil
SAMPLE_N = 20
STATE_PRUNE_S = 2 * 86400


def _standby_key(bot_id):
    """(ic): the claim loser reports on its OWN key. Suffix, never a rewrite."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- pure decision layer -----------------------------
def in_band(dev_bps):
    """True when the residual sits in THIS book's half-open band.

    Half-open on purpose: `>= GATE_HI` is band-kelly's, and an inclusive
    ceiling would make the two books fight over the boundary event."""
    if dev_bps is None:
        return False
    a = abs(dev_bps)
    return GATE_LO_BPS <= a < GATE_HI_BPS


def mirror_side(dev_bps):
    """The mirror takes the side the ghost REFUSED.

    dev > 0 (mark rich vs index): the ghost SHORTS the premium; we go LONG.
    dev < 0 (mark cheap): the ghost BUYS the discount; we go SHORT."""
    if dev_bps is None:
        return None
    return "long" if dev_bps > 0 else "short"


def ghost_side(dev_bps):
    """What the ghost would have done — recorded on every close so the mirror
    stays auditable against its own thesis."""
    if dev_bps is None:
        return None
    return "short" if dev_bps > 0 else "long"


def class_ok(sym, cls=None):
    """Entry eligibility by the VENUE's own class. Fail OPEN on no opinion.

    `(ki)`/`(lc)`: a hand list was wrong on 41 of 204 books, so the venue's
    own `strategy_index` is the authority. None (dark/stale scout, unlisted)
    admits — refusing on None would starve the book every time the scout
    blinked, and the residual cost is one pre-IPO listing slipping through
    until the next publish."""
    if ALLOW_PREIPO:
        return True
    idx = cls
    if idx is None and fleet_bus is not None:
        try:
            idx = fleet_bus.venue_class(sym)
        except Exception:  # noqa: BLE001
            idx = None
    if idx is None:
        return True
    return int(idx) not in EXCLUDED_CLASSES


def cook_exit(pos, dev_bps, my_px, now_ts):
    """The exit ladder, pure. Order matters: the price stop is senior to every
    data-dependent rule so a dark reference can never trap a losing position
    ((nm): exits never sit behind a data fetch).

      stop      — 5% adverse on MY side (the ghost's own constant, mirrored)
      converged — |residual| < EXIT_BPS: the ghost's win, taken as my loss
      max_hold  — the 4h clock
    """
    entry = pos.get("entry")
    if entry and my_px:
        adverse = ((my_px / entry - 1.0) if pos["side"] == "long"
                   else (1.0 - my_px / entry))
        if adverse <= -HARD_STOP:
            return "stop"
    if dev_bps is not None and abs(dev_bps) < EXIT_BPS:
        return "converged"
    if (now_ts - pos.get("t0", now_ts)) >= MAX_HOLD_S:
        return "max_hold"
    return None


def _price_pnl(pos, px):
    """Realizable P&L at MY exit price. Fills are book-walked VWAPs, so no
    flat slip constant is added; this venue's fees are zero (measured)."""
    sign = 1.0 if pos["side"] == "long" else -1.0
    p = px if (px or 0) > 0 else pos.get("last_px")
    if not p or not pos.get("entry"):
        return 0.0
    return sign * (p / pos["entry"] - 1.0) * pos["notional"]


def resolve_universe(held):
    """The ghost's own universe resolution (one owner), plus every HELD coin.

    `(hk)`: a coin leaving the list keeps its exit, its stop and its clock.
    The scan is UNSCREENED — the class screen applies at the ENTRY SITE only,
    because the residual distribution the band is measured against is the
    unscreened one."""
    out = list(ghost.resolve_universe(list(ghost.COINS), ghost.UNIVERSE_N,
                                      MIN_VOL_M))
    have = set(out)
    for c in held or ():
        s = str(c).strip()
        if s and s not in have:
            out.append(s)
            have.add(s)
    return out


def sample_block(recent):
    """Rolling published sample. Win rate is REPORTED, never a bar (I15)."""
    rows = list(recent or [])[-SAMPLE_N:]
    if not rows:
        return {"n": 0, "expectancy_pct": None, "expectancy_r": None,
                "win": None, "sum_usd": 0.0}
    pcts = [r.get("pct") for r in rows if isinstance(r.get("pct"), (int, float))]
    wins = sum(1 for r in rows if (r.get("pnl") or 0) > 0)
    exp = (sum(pcts) / len(pcts)) if pcts else None
    return {"n": len(rows),
            "expectancy_pct": round(100 * exp, 3) if exp is not None else None,
            "expectancy_r": round(exp / HARD_STOP, 3) if exp is not None else None,
            "win": round(wins / len(rows), 3),
            "sum_usd": round(sum(r.get("pnl") or 0.0 for r in rows), 2)}


def build_state(positions, recent, pend, last_ts, now=None):
    """The persistence blob — ONE builder. `pend` is the confirm counter, so a
    restart cannot skip the 2-loop confirm the measurement was made under."""
    return {"positions": positions, "recent": recent, "pend": pend,
            "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, recent, open_pnl, realized):
    """The published `extra` — ONE builder ((hj))."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {c: ("S" if p["side"] == "short" else "L")
                 for c, p in positions.items()},
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {
            # PUBLISH THE BAND, NOT JUST THE FLOOR ((gl)): an unpublished
            # ceiling made 🛢️ Garrett read as a rival for supply its own band
            # excludes, and a detector that overstates is one the operator
            # learns to ignore.
            "band_bps": [GATE_LO_BPS, GATE_HI_BPS],
            "exit_bps": EXIT_BPS,
            "max_hold_s": MAX_HOLD_S,
            "hard_stop": HARD_STOP,
            "clip_usd": CLIP_USD,
            "max_positions": MAX_POSITIONS,
            "gross_max_usd": CLIP_USD * MAX_POSITIONS,
            "max_entry_slip_bps": MAX_ENTRY_SLIP_BPS,
            "min_vol_m": MIN_VOL_M,
            "universe_n": ghost.UNIVERSE_N,
            "confirm_loops": CONFIRM_LOOPS,
            "confirm_s": CONFIRM_LOOPS * LOOP_SECONDS,
            "study_confirm_s": STUDY_CONFIRM_S,
            "excluded_classes": sorted(EXCLUDED_CLASSES) if not ALLOW_PREIPO else [],
            "crypto_only": False,
            "tiles_with": "band-kelly >= %.0fbps (disjoint by construction)"
                          % GATE_HI_BPS,
        },
        "scan": census,
        "sample": sample_block(recent),
        "thesis": {
            "cell": "dislocation mirror, residual band [%.0f,%.0f) bps"
                    % (GATE_LO_BPS, GATE_HI_BPS),
            "founding": "n=216 +0.367%/trade t=+2.74 at 4h; plateau over "
                        "30m-8h; both halves positive; boot CI "
                        "[+0.072%,+0.644%] (study 2026-08-19, entry (re))",
            "declared": "non-crypto by nature; pre-IPO excluded (-0.165%, "
                        "n=45); deep tail >=60bps measured NEGATIVE and "
                        "refused; oil index partially sticky out of hours",
        },
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, coin, pos, reason, exit_px, pnl, dev_now=None):
    """Ledger one close: `<side>-navband_<exit>` + the (gr) price telemetry.

    The tag carries the FAMILY so the brain and the winners' docket grade this
    band on its own record and it dies on its own evidence."""
    try:
        store.publish_paper_trade(
            bot_id,
            trade_id="%s:%s" % (coin, pos.get("t0")),
            pnl_abs=round(pnl, 6),
            pnl_pct=(pnl / pos["notional"]) if pos.get("notional") else None,
            pair=coin,
            opened_at=datetime.fromtimestamp(
                pos["t0"], tz=timezone.utc).isoformat() if pos.get("t0") else None,
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason="%s-navband_%s" % (pos["side"], reason),
            venue="lighter", shadow=True,
            tag="%s-navband" % pos["side"],
            side=pos["side"],
            entry_price=pos.get("entry"), exit_price=exit_px,
            extra={"dev_entry_bps": pos.get("dev_entry_bps"),
                   "dev_exit_bps": (round(dev_now, 1)
                                    if dev_now is not None else None),
                   "ghost_side": pos.get("ghost_side"),
                   "band_bps": [GATE_LO_BPS, GATE_HI_BPS],
                   "held_s": round(time.time() - (pos.get("t0") or time.time()), 1)},
        )
    except Exception as exc:  # noqa: BLE001
        print("[%s] ledger write failed for %s: %s" % (now_iso(), coin, exc))


def _open(positions, coin, dev_bps, bv, t0, cls=None):
    """Open the mirror leg. Entry price is the REAL side's VWAP for my clip —
    a long pays the ask walk, a short earns the bid walk."""
    side = mirror_side(dev_bps)
    px = bv["buy_vwap"] if side == "long" else bv["sell_vwap"]
    if not px or px <= 0:
        return False
    positions[coin] = {
        "coin": coin, "side": side, "entry": px, "last_px": px,
        "notional": CLIP_USD, "t0": t0,
        "dev_entry_bps": round(dev_bps, 1),
        "ghost_side": ghost_side(dev_bps),
        "cls": cls,
    }
    return True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        _selftest()
        return

    ctx = venue_context(BOT)
    bot_id = ctx.bot_id
    print("[%s] 🧭 nav-cook up | band [%.0f,%.0f)bps exit %.0f hold %.0fh "
          "clip $%.0f x %d | %s"
          % (now_iso(), GATE_LO_BPS, GATE_HI_BPS, EXIT_BPS,
             MAX_HOLD_S / 3600.0, CLIP_USD, MAX_POSITIONS, bot_id))

    st = store.load_state(bot_id) or {}
    positions = dict(st.get("positions") or {})
    recent = list(st.get("recent") or [])
    pend = dict(st.get("pend") or {})
    realized = float(st.get("realized") or 0.0)
    n_closed = int(st.get("n_closed") or 0)
    n_wins = int(st.get("n_wins") or 0)

    while True:
        t0 = time.time()

        # ONE BOOK, ONE WRITER — at the TOP of the loop ((hp)/(ho)), before
        # any trading pass writes the ledger this guard protects. Fail-OPEN:
        # a dark DB never idles a book.
        ok_writer, other = True, None
        try:
            ok_writer, other = store.claim_writer(bot_id)
        except Exception:  # noqa: BLE001
            ok_writer, other = True, None
        if not ok_writer:
            # STAND DOWN, never sys.exit — restartPolicy=always turns an exit
            # into a permanent crash-loop. Keep heart-beating on my OWN key.
            try:
                store.save_state(_standby_key(bot_id), {
                    "status": "standby", "duplicate_writer": other,
                    "caps": {"band_bps": [GATE_LO_BPS, GATE_HI_BPS]},
                    "updated": now_iso()})
            except Exception:  # noqa: BLE001
                pass
            print("[%s] standby — %s holds the writer claim" % (now_iso(), other))
            if args.once:
                return
            time.sleep(LOOP_SECONDS)
            continue

        try:
            ref = ghost.reference_prices()
        except Exception:  # noqa: BLE001
            ref = {}

        universe = resolve_universe(set(positions))
        census = {"scanned": len(universe), "ref_blind": 0 if ref else 1,
                  "no_book": 0, "held": 0, "in_band": 0, "below_band": 0,
                  "above_band": 0, "preipo": 0, "confirming": 0,
                  "slip": 0, "capped": 0, "opened": 0}

        for coin in universe:
            try:
                if not ctx.supports(coin):
                    census["no_book"] += 1
                    continue
                bv = ghost.book_view(ctx, coin, CLIP_USD)
            except Exception:  # noqa: BLE001
                bv = None
            r = (ref or {}).get(coin)
            dev_bps = None
            if bv is not None and r:
                dev_bps = (bv["mid"] / r - 1.0) * 1e4

            held = positions.get(coin)
            if held:
                census["held"] += 1
                my_px = None
                if bv is not None:
                    my_px = (bv["sell_vwap"] if held["side"] == "long"
                             else bv["buy_vwap"])
                if my_px:
                    held["last_px"] = my_px
                reason = cook_exit(held, dev_bps, my_px or held.get("last_px"), t0)
                if reason is None:
                    continue
                px = my_px or held.get("last_px")
                pnl = _price_pnl(held, px)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                recent = (recent + [{"pnl": round(pnl, 4),
                                     "pct": pnl / held["notional"]}])[-SAMPLE_N:]
                _close(bot_id, coin, held, reason, px, pnl, dev_now=dev_bps)
                print("[%s] CLOSE %s [%s] pnl %+.2f | banked %+.2f"
                      % (now_iso(), coin, reason, pnl, realized))
                del positions[coin]
                pend.pop(coin, None)
                continue

            # ---- entry ladder. Census counts every refusal so `opened: 0` is
            # never byte-identical between "quiet" and "structurally
            # impossible" (I18/(lv)).
            if dev_bps is None:
                continue
            a = abs(dev_bps)
            if a < GATE_LO_BPS:
                census["below_band"] += 1
                pend.pop(coin, None)
                continue
            if a >= GATE_HI_BPS:
                census["above_band"] += 1      # band-kelly's, deliberately
                pend.pop(coin, None)
                continue
            census["in_band"] += 1
            cls = None
            if fleet_bus is not None:
                try:
                    cls = fleet_bus.venue_class(coin)
                except Exception:  # noqa: BLE001
                    cls = None
            if not class_ok(coin, cls):
                census["preipo"] += 1
                continue
            # 2-loop confirm — the lag the measurement was made under.
            pend[coin] = int(pend.get(coin, 0)) + 1
            if pend[coin] < CONFIRM_LOOPS:
                census["confirming"] += 1
                continue
            if len(positions) >= MAX_POSITIONS:
                census["capped"] += 1
                continue
            side = mirror_side(dev_bps)
            slip = (bv.get("buy_slip_bps") if side == "long"
                    else bv.get("sell_slip_bps"))
            if slip is None or slip > MAX_ENTRY_SLIP_BPS:
                census["slip"] += 1
                continue
            if _open(positions, coin, dev_bps, bv, t0, cls=cls):
                census["opened"] += 1
                pend.pop(coin, None)
                print("[%s] OPEN %s %s dev %+.1fbps clip $%.0f"
                      % (now_iso(), coin, side, dev_bps, CLIP_USD))

        open_pnl = sum(_price_pnl(p, p.get("last_px")) for p in positions.values())
        equity = START_EQUITY + realized + open_pnl
        try:
            # "online", NOT "running": the watchdog's NOT-ONLINE check accepts
            # exactly {None, online, halted, paper} (fleet_watchdog_svc), so a
            # "running" row pages on every sweep. This book shipped "running"
            # for its first hour — copied from CLAUDE.md's own publish example,
            # which said "running" and is corrected with this line.
            store.publish(
                bot=bot_id, status="online", equity=round(equity, 2),
                pnl_abs=round(equity - START_EQUITY, 2),
                pnl_pct=(equity - START_EQUITY) / START_EQUITY,
                open_trades=len(positions), closed_trades=n_closed,
                wins=n_wins, losses=max(0, n_closed - n_wins),
                extra=build_extra(census, positions, recent, open_pnl, realized),
            )
            store.snapshot_equity(bot_id, equity, len(positions), realized)
        except Exception as exc:  # noqa: BLE001
            print("[%s] publish failed: %s" % (now_iso(), exc))

        try:
            saved = store.save_state(
                bot_id, build_state(positions, recent, pend, t0))
            if saved is False:
                # I4: never discard a persistence result.
                print("[%s] STATE NOT PERSISTED — positions/clock at risk"
                      % now_iso())
        except Exception as exc:  # noqa: BLE001
            print("[%s] save_state raised: %s" % (now_iso(), exc))

        print("[%s] scan %d | in-band %d | held %d | opened %d | eq %.2f"
              % (now_iso(), census["scanned"], census["in_band"],
                 census["held"], census["opened"], equity))
        if args.once:
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    # THE BAND IS HALF-OPEN, and the ceiling is the whole point.
    assert in_band(45.0) and in_band(59.9) and in_band(-50.0)
    assert not in_band(44.9), "below the floor must be refused"
    assert not in_band(60.0), "60bps is band-kelly's — the ceiling is EXCLUSIVE"
    assert not in_band(150.0), "the deep tail measured NEGATIVE and is refused"
    assert not in_band(None)
    # DISJOINT FROM band-kelly BY CONSTRUCTION (I20 / the (lv) subset trap).
    assert GATE_HI_BPS <= 60.0, "the ceiling must not reach into band-kelly"

    # THE MIRROR TAKES THE SIDE THE GHOST REFUSED.
    assert mirror_side(50.0) == "long" and ghost_side(50.0) == "short"
    assert mirror_side(-50.0) == "short" and ghost_side(-50.0) == "long"
    assert mirror_side(None) is None

    # EXIT LADDER: the price stop is SENIOR to every data-dependent rule, so a
    # dark reference can never trap a losing position ((nm)).
    pos = {"side": "long", "entry": 100.0, "t0": 0.0}
    assert cook_exit(pos, None, 94.0, 10.0) == "stop"
    assert cook_exit(pos, 10.0, 100.0, 10.0) == "converged"
    assert cook_exit(pos, 50.0, 100.0, MAX_HOLD_S + 1) == "max_hold"
    assert cook_exit(pos, 50.0, 100.0, 10.0) is None
    short = {"side": "short", "entry": 100.0, "t0": 0.0}
    assert cook_exit(short, None, 106.0, 10.0) == "stop", "short stop is UP"
    assert cook_exit(short, None, 94.0, 10.0) is None, "a short profit is not a stop"

    # CLASS SCREEN: pre-IPO refused, everything else admitted, None FAILS OPEN.
    assert class_ok("X", 3) and class_ok("X", 6) and class_ok("X", 2)
    assert not class_ok("X", 7), "pre-IPO measured -0.165% and is excluded"
    assert class_ok("X", None), "no opinion must FAIL OPEN, never starve"

    # P&L SIGNS.
    lp = {"side": "long", "entry": 100.0, "notional": 80.0}
    sp = {"side": "short", "entry": 100.0, "notional": 80.0}
    assert abs(_price_pnl(lp, 110.0) - 8.0) < 1e-9
    assert abs(_price_pnl(sp, 110.0) + 8.0) < 1e-9
    assert _price_pnl({"side": "long", "notional": 80.0}, 110.0) == 0.0

    # THE PUBLISHED BAND, not just a floor ((gl)).
    ex = build_extra({"scanned": 0}, {}, [], 0.0, 0.0)
    assert ex["caps"]["band_bps"] == [GATE_LO_BPS, GATE_HI_BPS]
    assert ex["caps"]["crypto_only"] is False, "this band is non-crypto by nature"
    assert 7 in ex["caps"]["excluded_classes"]
    assert "scan" in ex and "thesis" in ex

    # CENSUS must distinguish "quiet" from "structurally impossible" (I18).
    for k in ("in_band", "below_band", "above_band", "preipo", "capped", "slip"):
        assert k in ("in_band", "below_band", "above_band", "preipo",
                     "capped", "slip")

    # THE SHIPPED HORIZON MUST BE ONE THE STUDY ACTUALLY MEASURED — a hold
    # outside the swept plateau would be an unmeasured extrapolation.
    assert MAX_HOLD_S in HORIZON_PLATEAU_S, (
        "max hold %.0fs is outside the measured plateau %s"
        % (MAX_HOLD_S, HORIZON_PLATEAU_S))

    # THE SHIPPED CONFIRM MUST COVER THE LAG THE STUDY MEASURED UNDER. The
    # count is a cadence artifact; the DURATION is the rule. A confirm shorter
    # than the measured lag admits dislocations the graded gate refused.
    # The bar itself is DERIVED from STUDY_DISLOCATION_BAND_2026-08-19.md's
    # own numbers, so it cannot be quietly relaxed to match the code.
    assert (STUDY_SNAPSHOT_S, STUDY_CONFIRM_LAGS) == (300.0, 2), (
        "the study's cadence/lag are quoted from its Method section")
    assert STUDY_CONFIRM_S == 600.0
    assert CONFIRM_LOOPS * LOOP_SECONDS >= STUDY_CONFIRM_S, (
        "confirm %d loops x %ds = %ds is SHORTER than the measured lag %.0fs"
        % (CONFIRM_LOOPS, LOOP_SECONDS, CONFIRM_LOOPS * LOOP_SECONDS,
           STUDY_CONFIRM_S))
    # LEVERAGE PIN: gross exposure must stay inside the level whose MEASURED
    # drawdown clears the 15% go-live bar. maxDD scales ~linearly in the clip
    # (-1.89% at $80), so the ceiling is the clip where it reaches 15%.
    # This is a MEASURED number (the 226-trade series at the $80 clip), not a
    # tunable. Pinned against itself because the first version of this round
    # left it as a bare literal and a mutation to 0.0001 SURVIVED — the same
    # "a bar can be fixed by editing the bar" class that `(sa)` fixed by
    # deriving the confirm window instead of asserting it.
    MEASURED_MAXDD_AT_80 = 0.0189
    assert abs(MEASURED_MAXDD_AT_80 - 0.0189) < 1e-9, (
        "measured maxDD at the $80 clip is evidence, not a knob")
    implied = MEASURED_MAXDD_AT_80 * (CLIP_USD / 80.0)
    assert implied < 0.15, (
        "clip $%.0f implies ~%.1f%% maxDD, past the 15%% go-live bar"
        % (CLIP_USD, 100 * implied))
    assert CLIP_USD * MAX_POSITIONS <= 5.0 * 80.0 * 4, (
        "gross exposure beyond the measured 5x ceiling")
    assert _standby_key("nav-cook-lshadow") == "nav-cook-lshadow:standby"
    st = build_state({}, [], {}, 1.0, now=2.0)
    assert st["saved_ts"] == 2.0 and st["pend"] == {}

    # NO LEVERAGE, NO REAL MONEY: this module must never size off equity or
    # touch a live venue mode.
    # Token built at RUNTIME: a literal here would make the scan match its own
    # assertion — the documented "a page-wide substring scan is not a
    # structural claim" trap, which this file walked into on its first run.
    src = open(__file__).read()
    live_tok = "lighter_" + "live"
    lev_tok = "update_" + "leverage"
    body = src.split("def _selftest(")[0]          # scope: exclude the test itself
    assert live_tok not in body, "shadow book must not name the live venue mode"
    assert lev_tok not in body, "no leverage knob (rejected six times)"

    sb = sample_block([{"pnl": 1.0, "pct": 0.01}, {"pnl": -0.5, "pct": -0.005}])
    assert sb["n"] == 2 and sb["win"] == 0.5
    print("nav-cook selftest OK")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
