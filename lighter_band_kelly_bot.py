#!/usr/bin/env python3
"""
lighter_band_kelly_bot.py — 🪁 band-kelly, the MIRROR book (Paul Kelly —
from little things big things grow).

WHAT THIS IS (2026-08-18, operator: "Make a bot that does the exact opposite
of all of the major losing sequences and trends, flipping but also using
every enhancement and knowledge we have to ride an uptrend - expansion is
the premise. Being able to fly high and generate that free energy gliding
down.")
  One $1,000 shadow book that holds the OPPOSITE side of the fleet's
  measured losers, over exactly the windows the loser would have traded:
  enter when the ghost enters, hold the other side, exit when the ghost
  exits. At mark on a zero-fee venue the mirror's per-trade return is the
  exact negation of the ghost's, so a loser ledger at t <= -2 is founding
  evidence at t >= +2 here. Third of the Australian-musician cohort
  (barnes, garrett taken; young designed-and-refuted).

THE ROSTER IS MEASURED, NOT ASSUMED (scripts/study_band_kelly_2026-08-18.py
— verdict logic pre-declared in its header; STUDY_BAND_KELLY_2026-08-18.md):
  * SHIPPED — `snapfade`: 🧲 Snap Back's whole book inverted. The ghost
    faded Lighter's mid-vs-index dislocations (long when cheap, short when
    rich) and retired 4-Aug (jh) as the fleet's strongest measured loser
    (t=-2.97, 100% era exits `converged` — the dislocations it faded kept
    going). The mirror RIDES them: LONG when rich (fly high — the majority
    side, +0.464%/t, t=+4.72 on crypto), SHORT when cheap (the glide,
    +0.816%/t, t=+3.77). Crypto-only founding claim: n=65, +0.605%/trade,
    t=+5.71, both halves and both sides positive, cluster-robust t=+2.84
    on the full set, ex-best-coin t=+5.08, win 82% (REPORTED, never a bar
    — I15). Median hold 0.09h, where the tape's drift term is 861x below
    the mean — alpha, not beta ((hm) in mirror form).
  * REFUSED — `brkfade` (breakout-4h/dad inverted): the (nt) calibration
    control killed it — over 578d the ghost family does NOT lose (+$126,
    t=+0.90, tail-driven), so its mirror shorts a fat right tail: every
    stop cell negative, maxDD ~23%, random-short P=0.78. A 21-close
    ledger's inverse is a 21-close bet.
  * LIVE-PROBE — `dipfade` (taker dip lens inverted): admitted 18-Aug by
    OPERATOR OVERRIDE of the I16 floor (the risk-up decision, on the
    record): n=13 < 30, but t=-2.66 as a single pre-registered candidate
    puts the mirror's 95% CI at ~[+0.28%,+2.05%]/trade, entirely positive.
    $40 probe clip x2, own tag (`short-dip_*`) so it is graded alone and
    dies on its own record; the ghost is the taker's own conviction bar
    and bracket, drift-pinned against the taker's real constants in tests.
  * OWNED — impulse-continuation inverted IS 🧘 book-douglas (I20): the
    largest measured loser's inversion is already minted, not re-taken.
  The refused/waiting families publish in `extra.roster` every loop so the
  premise stays visible and falsifiable, not folklore.

THE GHOST IS THE RETIRED MODULE'S OWN CODE — never a re-implementation.
  `lighter_dislocation_bot` is imported for its gate math and constants,
  frozen at the retirement-day config: adaptive percentile entry gate
  (p98 of live |residuals|, floored at EXIT_BPS*1.5=60bps, capped 150),
  2-loop confirmation, 30bps clip-slip gate, converged at 40bps, ghost
  hard-stop 5%, max-hold 2h, non-convergence embargo. The selftest pins
  the import identity (a second copy of a rule is a second rule).

MIRROR MECHANICS
  * ghost long (dev<0, venue cheap)  -> mirror SHORT  (ride the discount)
  * ghost short (dev>0, venue rich)  -> mirror LONG   (ride the premium)
  * exits, all on the ghost's terms: `conv` (|dev| <= 40bps — the basis
    cleared), `ghoststop` (the ghost's 5% stop = the mirror's profit-side
    cover), `maxhold` (the ghost's 2h), plus the mirror's OWN protective
    `stop` (5% adverse on MY side — the one declared deviation from pure
    negation, same constant as the ghost's own; a mirror with no stop of
    its own is unbounded against a 2h market move) and `delisted`.
  * after a `maxhold` the coin is embargoed until |dev| <= EXIT_BPS once —
    the ghost's own (2026-07-21) non-convergence quarantine, mirrored.
  * fills: the ghost's own fill model — clip VWAP walked through the live
    book (`book_view`). The GHOST-side event check is priced at the
    ghost's own 30bps gate AT ITS OWN $10 clip (the event definition is
    the ghost's, never mine); MY side gates at 60bps ([18-Aug risk-up],
    was 30). Venue fee zero (measured); no flat slip constant is added on
    top of a book-walked fill.
  * DECLARED DEVIATIONS from pure negation, priced where measurable:
    crypto-only entries ((lk) — the screen CONCENTRATES the edge: ghost's
    crypto subset t=-5.71 against -2.82 pooled; revert
    KELLY_ALLOW_NONCRYPTO=1); the $250 clip against the ghost's $10
    ([18-Aug risk-up, operator decision pre-first-close]: per-trade % is
    clip-invariant, larger clips meet more slip, and the my_slip census
    keeps the cost visible — I18); the 60bps MY-side slip tolerance (pays
    up to ~30bps extra on marginal fills against a +60bps/trade mean —
    the accepted price of taking more of the ghost's events at size).
    Worst instant with every slot stopped: 4x$250x5% + 2x$40x4% ~ -$53 ~
    5.3% of the book, inside the 15% bar; gross max ~$1,080 ~ 1.08x
    equity, declared.

WHAT IS DELIBERATELY ABSENT
  * No regime gate: at a 5-minute median hold a 4h EMA gate is horizon-
    mismatched and unmeasured (I19 — a widening OR a restriction is paid
    for in evidence). "Ride the uptrend" is the measured LONG side itself.
  * The ghost's -5% DAILY-LOSS HALT is NOT simulated — declared, not an
    oversight. Implementing it would mean the mirror stops entering when
    the GHOST's virtual day is down 5%, i.e. exactly when the mirror's day
    is UP 5% — capping the winning days the thesis exists to ride — and a
    shadow halt is the (hl) trap besides (it suspends the scan, exits
    included). The founding ledger EMBEDS the halt's selection (the
    ghost's post-halt events on its worst days — the mirror's best — never
    reached its ledger), so the founded sample is CONSERVATIVE relative to
    forward behavior: forward takes strictly more of the thesis's best
    days, not different trades.
  * No tuning lane (the Garrett choice): env-only config, single-policy
    (hm) clock by construction. Levers are a day-31 decision.
  * No brain mults, no allocation scale: the founding claim is the ghost's
    negated ledger; consuming a sizing signal would make the forward
    record a different policy than the founded one.

SUPPLY, NAMED (I20): dislocation-momentum on the venue's liquid crypto set.
  The ghost is RETIRED — nothing else trades this signal in either
  direction; 🎫 the Taker's lenses, 🧘 Douglas's 1h impulse fades and the
  funding books share coins but not signals or horizon (5-minute holds).
  The one standing collision to watch is DECLARED: if the taker's vetoed
  dip lens is ever un-vetoed while `dipfade` ships here, the fleet would
  hold a bet and its anti-bet — that pairing is refused until then anyway.

ZERO KEYS, SHADOW ONLY, $1,000, NO TOP-UPS. VENUE=lighter_shadow only.
Fresh 30-day clock from first publish; ~2.8 crypto closes/day measured on
the ghost's ledger -> gradeable ~mid-Sep on ITS OWN ledger (I14).

Usage:
    VENUE=lighter_shadow python lighter_band_kelly_bot.py          # daemon
    VENUE=lighter_shadow python lighter_band_kelly_bot.py --once   # smoke
    python lighter_band_kelly_bot.py --selftest                    # offline
"""
import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
from venues import venue_context

# THE GHOST: the retired loser's own module — gate math and constants frozen
# at the retirement-day config. Its retirement guard sits inside main(), so
# importing it runs nothing ((jh); verified). One owner for every rule the
# mirror negates: adaptive_enter_bps, book_view, resolve_universe and the
# constants below are THEIRS, imported, never copied.
import lighter_dislocation_bot as ghost

# Universe class screen comes from the bus. Guarded: a dark import keeps the
# ghost's configured list ((hk): the widening is an enhancement, never a
# dependency). COPY lands in Dockerfile.bandkelly in this commit (born-dark).
try:
    import fleet_bus
except Exception:  # noqa: BLE001
    fleet_bus = None

BOT = "band-kelly"

# --------------------------- configuration ----------------------------------
START_EQUITY = 1000.0
LOOP_SECONDS = ghost.LOOP_SECONDS          # 90s — the ghost's own cadence

# ---- the mirror's own knobs (env-only; everything else is the ghost's) -----
# [18-Aug RISK-UP, operator decision pre-first-close — "look at options,
# even though risk will be higher": $250 x 4 deploys the whole book in a
# storm (was $80 x 4 = $320 max working). Per-trade % is clip-invariant, so
# this scales $ throughput ~3.1x on the same measured edge; the accepted
# price is deeper book-walks (the named KAITO-depth risk), bounded by the
# widened MY-side slip gate below and visible in the my_slip census.
CLIP_USD = float(os.environ.get("KELLY_CLIP_USD", "250"))
MAX_POSITIONS = int(os.environ.get("KELLY_MAX_POSITIONS", "4"))
# MY-side slip tolerance, widened 30 -> 60bps in the same decision: take
# events the ghost validated even when my clip walks deeper. The GHOST-side
# event check stays at the ghost's own 30bps AT THE GHOST'S OWN $10 clip —
# the event definition is the ghost's, never mine.
MY_MAX_SLIP_BPS = float(os.environ.get("KELLY_MAX_SLIP_BPS", "60"))

# ---- dipfade: the second mirror family, admitted at PROBE size ---------------
# [18-Aug OPERATOR OVERRIDE OF THE I16 FLOOR, on the record: n=13 < 30, but
# t=-2.66 as a single pre-registered candidate puts the mirror's 95% CI at
# ~[+0.28%, +2.05%]/trade, entirely positive. Probe clip bounds the cost of
# being wrong to ~friction on $40; own tag (short-dip) so the brain and the
# referee grade it alone and it dies on its own record if the CI lied.]
# The ghost is the taker's VETOED dip lens: a dip ticket the taker's own
# conviction bar (range_pos <= 0.05) would have bought, held long under the
# taker's bracket (tp +4% / sl -3% / 48h). The mirror holds the SHORT over
# that same window: the ghost's tp is my loss side (-4%), its sl my win
# (+3%). Bracket constants are DECLARED literals drift-pinned against the
# taker's real values in tests/autonomy/test_band_kelly_mirror.py — the
# taker module must not enter this image's import graph.
DIP_CLIP_USD = float(os.environ.get("KELLY_DIP_CLIP_USD", "40"))
DIP_MAX_POSITIONS = int(os.environ.get("KELLY_DIP_MAX_POSITIONS", "2"))
DIP_RANGE_MAX = 0.05          # the taker's TT_DIP_RANGE conviction bar
DIP_GHOST_TP = 0.04           # taker TT_TP  — ghost long's target = my stop
DIP_GHOST_SL = 0.03           # taker |TT_SL| — ghost long's stop = my win
DIP_MAX_HOLD_S = 48 * 3600.0  # taker TT_MAX_HOLD_H
DIP_COOLDOWN_S = 2 * 3600.0   # taker SL_COOLDOWN_H, as a re-entry cooldown
SCOUT_KEY = "lighter-market"  # the taker's own ticket source
# The one declared deviation from pure negation: the mirror's own protective
# stop, 5% adverse on MY side — the ghost's own HARD_STOP constant, mirrored.
# Well inside the 15% go-live drawdown bar ((gv) reconciliation).
MY_HARD_STOP = float(os.environ.get("KELLY_HARD_STOP", "0.05"))

ALLOW_NONCRYPTO = os.environ.get(
    "KELLY_ALLOW_NONCRYPTO", "").strip().lower() in ("1", "true", "yes")

SAMPLE_N = 20                              # rolling published sample (I15)
STATE_PRUNE_S = 2 * 86400

# The measured roster — published every loop so the premise stays visible.
# Statuses move only with a new measured study, never silently.
MIRROR_ROSTER = {
    "snapfade": {"status": "live",
                 "ghost": "lighter-dislocation-lshadow (retired (jh))",
                 "founding": "crypto n=65 +0.605%/t t=+5.71; both sides "
                             "positive (study 2026-08-18)"},
    "brkfade": {"status": "refused",
                "why": "calibration control: ghost family +$126/t=+0.90 "
                       "over 578d — mirror shorts the fat tail; every stop "
                       "cell negative, random-short P=0.78"},
    "dipfade": {"status": "live-probe",
                "why": "OPERATOR OVERRIDE of the I16 floor, 18-Aug (risk-up "
                       "decision): n=13, t=-2.66, mirror 95% CI "
                       "[+0.28%,+2.05%]/trade as a single named candidate; "
                       "$40 probe clip, own tag, dies on its own record",
                "ghost": "taker dip lens (vetoed, untraded)"},
    "impulse_cont": {"status": "owned",
                     "why": "the inversion is 🧘 book-douglas (I20)"},
}


def _standby_key(bot_id):
    """(ic): the claim loser reports on its OWN key. Suffix, never a rewrite."""
    return f"{bot_id}:standby"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


# --------------------------- pure decision layer -----------------------------
def mirror_side(dev_bps):
    """The whole thesis in one line: the ghost fades (long when cheap), the
    mirror rides. dev>0 = venue rich = ghost shorts = mirror LONGS."""
    return "long" if dev_bps > 0 else "short"


def ghost_side(dev_bps):
    """The ghost's own rule, stated for the ledger: is_long = dev < 0."""
    return "long" if dev_bps < 0 else "short"


def mirror_exit(pos, dev_bps, exit_px, ghost_exit_px, now_ts):
    """Exit decision for one mirror position, evaluated on the LIVE book
    every loop ((nm): never behind a data-fetch gate; a stop that is only
    checked when an endpoint answers is not a stop). Priority: the basis
    clearing, then the ghost's stop, then my own, then the clock.

    `exit_px` is MY side's book-walked exit; `ghost_exit_px` the ghost's.
    `dev_bps` may be None (reference dark) — then only the price stop and
    the clock can fire, which is the fail-safe direction.
    Returns 'conv'/'ghoststop'/'stop'/'maxhold'/None."""
    if dev_bps is not None and abs(dev_bps) <= ghost.EXIT_BPS:
        return "conv"
    g_long = pos["ghost_side"] == "long"
    if ghost_exit_px and pos.get("ghost_entry"):
        ge = pos["ghost_entry"]
        if g_long and ghost_exit_px <= ge * (1.0 - ghost.HARD_STOP):
            return "ghoststop"          # the ghost dies = the mirror banks
        if not g_long and ghost_exit_px >= ge * (1.0 + ghost.HARD_STOP):
            return "ghoststop"
    if exit_px and pos.get("entry"):
        me = pos["entry"]
        if pos["side"] == "long" and exit_px <= me * (1.0 - MY_HARD_STOP):
            return "stop"
        if pos["side"] == "short" and exit_px >= me * (1.0 + MY_HARD_STOP):
            return "stop"
    if now_ts - pos["opened_ts"] >= ghost.MAX_HOLD_S:
        return "maxhold"
    return None


def dip_ghost_takes(ticket, crypto_ok):
    """Would the taker's dip policy have BOUGHT this ticket? Its own
    conviction bar (range_pos <= 0.05), plus the (lk) class screen the
    whole fleet runs at entries. The scout's own `noncrypto` stamp is
    honoured when present; absent means no opinion."""
    try:
        sym = str(ticket.get("sym") or "").strip()
        if not sym:
            return None
        if float(ticket.get("range_pos", 1.0)) > DIP_RANGE_MAX:
            return None
        if ticket.get("noncrypto") is True:
            return None
        if crypto_ok and sym not in crypto_ok:
            return None
        return sym
    except Exception:  # noqa: BLE001
        return None


def dip_exit(pos, exit_px, now_ts):
    """Exit for a dipfade mirror SHORT: the ghost long's bracket, mirrored.
    Ghost tp (+4%) is my loss side; ghost sl (-3%) my win; 48h the clock;
    my own 5% stop stays senior only beyond the ghost's own bounds.
    Returns 'ghosttp'/'ghostsl'/'maxhold'/None."""
    e = pos.get("entry")
    if exit_px and e:
        if exit_px >= e * (1.0 + DIP_GHOST_TP):
            return "ghosttp"          # the ghost banked = the mirror pays
        if exit_px <= e * (1.0 - DIP_GHOST_SL):
            return "ghostsl"          # the ghost died = the mirror banks
    if now_ts - pos["opened_ts"] >= DIP_MAX_HOLD_S:
        return "maxhold"
    return None


def fresh_scout(state, now_ts):
    """The taker's own freshness contract on the scout payload: within its
    declared ttl, and never future-dated. Stale/dark -> None (no tickets is
    'no opinion', never 'no dip exists')."""
    try:
        from datetime import datetime as _dt
        upd = str((state or {}).get("updated") or "")
        ts = _dt.fromisoformat(upd.replace("Z", "+00:00")).timestamp()
        ttl = float(state.get("ttl_sec") or 900)
        if 0 <= now_ts - ts <= ttl:
            return state
    except Exception:  # noqa: BLE001
        pass
    return None


def _price_pnl(pos, px):
    """Realizable P&L at MY exit price `px`. Fills are book-walked VWAPs, so
    no flat slip constant is added; fees are zero on this venue (measured)."""
    sign = 1.0 if pos["side"] == "long" else -1.0
    p = px if (px or 0) > 0 else pos.get("last_px")
    if not p or not pos.get("entry"):
        return 0.0
    return sign * (p / pos["entry"] - 1.0) * pos["notional"]


def resolve_universe(held):
    """The ghost's own universe resolution (its configured 16 + the scout up
    to 40 at >= $0.5M — imported, one owner), plus every held coin ((hk): a
    coin leaving the list keeps its exit, stop and clock).

    THE SCAN IS THE GHOST'S, UNSCREENED — the (lk) crypto screen applies at
    the ENTRY SITE, never here. The adaptive gate is a PERCENTILE of the
    residuals seen this loop, so screening the scan would compute the gate
    over a different distribution than the ghost's and select different
    events than the ones the founding ledger negates (caught in the 18-Aug
    win-review before the first close — the (hm) clock had not started).
    Returns (scan_list, crypto_ok_set): entries outside crypto_ok are
    refused and censused; [] from the classifier means "no opinion, refuse
    nothing" — the bus's own documented contract ((hk)/(lk) fail-OPEN)."""
    out = list(ghost.resolve_universe(list(ghost.COINS), ghost.UNIVERSE_N,
                                      ghost.UNIVERSE_MIN_VOL_M))
    have = set(out)
    for c in held or ():
        s = str(c).strip()
        if s and s not in have:
            out.append(s)
            have.add(s)
    crypto_ok = set(out)
    if not ALLOW_NONCRYPTO and fleet_bus is not None:
        try:
            kept = fleet_bus.crypto_only(out)
            if kept:
                crypto_ok = set(kept)   # ENTRY eligibility only; exits on a
        except Exception:  # noqa: BLE001  # held coin never consult this
            pass
    return out, crypto_ok


def sample_block(recent):
    """Rolling published sample: expectancy in % and in R (risk = the
    predefined MY_HARD_STOP), win rate REPORTED never a bar (I15)."""
    rows = list(recent or [])[-SAMPLE_N:]
    if not rows:
        return {"n": 0, "expectancy_pct": None, "expectancy_r": None,
                "win": None, "sum_usd": 0.0}
    pcts = [r.get("pct") for r in rows if isinstance(r.get("pct"), (int, float))]
    wins = sum(1 for r in rows if (r.get("pnl") or 0) > 0)
    exp_pct = (sum(pcts) / len(pcts)) if pcts else None
    return {"n": len(rows),
            "expectancy_pct": round(100 * exp_pct, 3) if exp_pct is not None else None,
            "expectancy_r": (round(exp_pct / MY_HARD_STOP, 3)
                             if exp_pct is not None else None),
            "win": round(wins / len(rows), 3),
            "sum_usd": round(sum(r.get("pnl") or 0.0 for r in rows), 2)}


def build_state(positions, recent, pend, noconv, enter_bps_eff, last_ts,
                now=None, dip_cd=None):
    """The persistence blob — ONE builder. `pend` is the ghost's confirm
    counter, `noconv` its non-convergence embargo; both are the ghost's own
    memory, so a restart cannot re-enter an event the ghost had retired.
    `dip_cd` is the dipfade re-entry cooldown (the taker's own shape)."""
    return {"positions": positions, "recent": recent, "pend": pend,
            "noconv": noconv, "enter_bps_eff": enter_bps_eff,
            "dip_cd": dict(dip_cd or {}),
            "last_ts": last_ts,
            "saved_ts": float(now if now is not None else time.time())}


def build_extra(census, positions, recent, open_pnl, realized, enter_bps_eff):
    """The published `extra` — ONE builder ((hj))."""
    return {
        "mode": "dry-run",
        "venue": "lighter",
        "held": {p["coin"]: ("S" if p["side"] == "short" else "L")
                 for p in positions.values()},
        "open_pnl": round(open_pnl, 2),
        "realized": round(realized, 2),
        "caps": {"clip_usd": CLIP_USD, "max_positions": MAX_POSITIONS,
                 "my_hard_stop": MY_HARD_STOP,
                 "my_max_slip_bps": MY_MAX_SLIP_BPS,
                 "dip": {"clip_usd": DIP_CLIP_USD,
                         "max_positions": DIP_MAX_POSITIONS,
                         "ghost_tp": DIP_GHOST_TP, "ghost_sl": DIP_GHOST_SL,
                         "max_hold_s": DIP_MAX_HOLD_S,
                         "range_max": DIP_RANGE_MAX,
                         "i16_override": "operator 18-Aug, n=13 probe"},
                 "gross_max_usd": CLIP_USD * MAX_POSITIONS
                 + DIP_CLIP_USD * DIP_MAX_POSITIONS,
                 "gate_bps": round(enter_bps_eff, 1),
                 "gate_floor_bps": ghost.EXIT_BPS * ghost.ENTER_FLOOR_MULT,
                 "gate_cap_bps": ghost.ENTER_BPS,
                 "exit_bps": ghost.EXIT_BPS,
                 "ghost_stop": ghost.HARD_STOP,
                 "max_hold_s": ghost.MAX_HOLD_S,
                 "confirm_loops": ghost.CONFIRM_LOOPS,
                 "max_entry_slip_bps": ghost.MAX_ENTRY_SLIP_BPS,
                 "universe_n": ghost.UNIVERSE_N,
                 "min_vol_m": ghost.UNIVERSE_MIN_VOL_M,
                 "crypto_only": not ALLOW_NONCRYPTO,
                 "ghost_config": "lighter-dislocation retirement (jh), frozen"},
        "scan": census,
        "roster": MIRROR_ROSTER,
        "sample": sample_block(recent),
    }


# --------------------------- the loop ----------------------------------------
def _close(bot_id, key, pos, reason, exit_px, pnl, dev_now=None):
    """Ledger one close: `<side>-snap_<exit>` + the (gr) price telemetry —
    entry/exit prices from the position's own records, never literals. The
    ghost's side and the residual at entry/exit ride in extra so the mirror
    stays auditable against the thesis (was this really a ghost event?)."""
    t = time.time()
    held_h = (t - pos["opened_ts"]) / 3600.0
    entry_px = pos.get("entry")
    try:
        store.publish_paper_trade(
            bot_id, trade_id=f"{key}:{pos['opened_ts']:.0f}",
            pnl_abs=pnl, pnl_pct=pnl / pos["notional"], pair=pos["coin"],
            opened_at=datetime.fromtimestamp(
                pos["opened_ts"], timezone.utc).isoformat(),
            closed_at=datetime.now(timezone.utc).isoformat(),
            reason=f"{pos['side']}-{pos.get('family') or 'snap'}_" + reason,
            venue="lighter", shadow=True, side=pos["side"],
            entry_price=entry_px, exit_price=exit_px,
            extra={"family": pos.get("family") or "snap",
                   "ghost_side": pos.get("ghost_side"),
                   "ghost_entry": pos.get("ghost_entry"),
                   "dev_at_entry_bps": pos.get("dev_at_entry"),
                   "dev_at_exit_bps": dev_now,
                   "spread_bps_entry": pos.get("spread_bps_entry"),
                   "notional": pos.get("notional"),
                   "held_h": round(held_h, 3)})
    except Exception:  # noqa: BLE001
        pass


def _open_mirror(positions, coin, dev_bps, bv, t0, ref):
    """Open one mirror position at MY side's book-walked VWAP. SIGNATURE IS
    THE CONSISTENCY RULE: no streak, no last-outcome, no equity parameter
    exists, so size cannot vary with results without changing this
    function's shape (the douglas pin, kept). Returns the position or None
    (unpriceable/slip-refused on MY side — the ghost's side was already
    gated by the caller, because the ghost's gate decides whether the event
    EXISTS and mine whether it is tradeable)."""
    side = mirror_side(dev_bps)
    g_side = ghost_side(dev_bps)
    my_fill = bv["buy_vwap"] if side == "long" else bv["sell_vwap"]
    my_slip = bv["buy_slip_bps"] if side == "long" else bv["sell_slip_bps"]
    g_fill = bv["buy_vwap"] if g_side == "long" else bv["sell_vwap"]
    if my_fill is None or my_slip is None or not my_fill > 0:
        return None
    if my_slip > MY_MAX_SLIP_BPS:
        return None
    positions[coin] = {"coin": coin, "family": "snap",
                       "side": side, "ghost_side": g_side,
                       "notional": CLIP_USD, "size": CLIP_USD / my_fill,
                       "entry": my_fill, "ghost_entry": g_fill,
                       "last_px": my_fill, "opened_ts": t0,
                       "dev_at_entry": round(dev_bps, 1),
                       "ref_at_entry": ref,
                       "spread_bps_entry": bv.get("spread_bps")}
    return positions[coin]


def _open_dip(positions, sym, bv, t0, ticket):
    """Open one dipfade mirror SHORT at MY side's book-walked VWAP. Same
    consistency-rule signature discipline as _open_mirror: no streak, no
    outcome, no equity input. The ghost's entry is the same mark the taker
    would have bought (its buy vwap at its own read) — recorded for the
    audit trail, not for exits (the dip bracket is %-of-MY-entry)."""
    my_fill = bv["sell_vwap"]
    my_slip = bv["sell_slip_bps"]
    if my_fill is None or my_slip is None or not my_fill > 0:
        return None
    if my_slip > MY_MAX_SLIP_BPS:
        return None
    positions[sym] = {"coin": sym, "family": "dip",
                      "side": "short", "ghost_side": "long",
                      "notional": DIP_CLIP_USD,
                      "size": DIP_CLIP_USD / my_fill,
                      "entry": my_fill, "ghost_entry": bv.get("buy_vwap"),
                      "last_px": my_fill, "opened_ts": t0,
                      "range_pos": ticket.get("range_pos"),
                      "chg_pct": ticket.get("chg_pct"),
                      "spread_bps_entry": bv.get("spread_bps")}
    return positions[sym]


def main():
    p = argparse.ArgumentParser(
        description="🪁 band-kelly — the mirror of the measured losers")
    p.add_argument("--once", action="store_true", help="single scan then exit")
    args = p.parse_args()

    _mode = os.environ.get("VENUE", "lighter_shadow").strip() or "lighter_shadow"
    if _mode != "lighter_shadow":
        raise SystemExit(
            f"VENUE={_mode}: band-kelly (🪁 the mirror) runs "
            "VENUE=lighter_shadow ONLY. $1,000 shadow, fills modelled on the "
            "live book; go-live is a separate operator act behind the "
            "standard gate, never an env flip.")

    ctx = venue_context(bot=BOT, paper_start=START_EQUITY)
    bot_id = ctx.bot_id                      # band-kelly-lshadow

    realized, n_closed, n_wins = 0.0, 0, 0
    try:
        agg = store.fetch_paper_aggregate(bot_id)
        if agg:
            realized, n_closed, n_wins = agg["realized"], agg["closed"], agg["wins"]
    except Exception:  # noqa: BLE001
        pass

    positions = {}       # coin -> mirror position
    recent = []          # rolling closed-trade sample (published, I15)
    pend = {}            # coin -> ghost confirm counter (CONFIRM_LOOPS)
    noconv = {}          # coin -> ts of ghost maxhold (embargo till basis clears)
    dip_cd = {}          # coin -> ts of last dipfade entry/exit (cooldown)
    enter_bps_eff = ghost.ENTER_BPS
    try:
        _saved = store.load_state_required(bot_id, sleep_s=LOOP_SECONDS)
        if _saved:
            if isinstance(_saved.get("positions"), dict):
                positions = _saved["positions"] or {}
            if isinstance(_saved.get("recent"), list):
                recent = _saved["recent"][-SAMPLE_N:]
            if isinstance(_saved.get("pend"), dict):
                pend = {str(k): int(v) for k, v in _saved["pend"].items()
                        if isinstance(v, (int, float))}
            if isinstance(_saved.get("noconv"), dict):
                noconv = {str(k): float(v) for k, v in _saved["noconv"].items()
                          if isinstance(v, (int, float))}
            if isinstance(_saved.get("dip_cd"), dict):
                dip_cd = {str(k): float(v) for k, v in _saved["dip_cd"].items()
                          if isinstance(v, (int, float))}
            if isinstance(_saved.get("enter_bps_eff"), (int, float)):
                enter_bps_eff = float(_saved["enter_bps_eff"])
            print(f"[{now_iso()}] restored {len(positions)} position(s), "
                  f"gate {enter_bps_eff:.0f}bps, {len(recent)}-trade sample")
    except Exception:  # noqa: BLE001
        pass

    print(f"[{now_iso()}] 🪁 band-kelly start | venue lighter | MIRROR of "
          f"🧲 snap-back (ride dislocations, never fade) | gate p{100*ghost.ENTER_PCT:.0f} "
          f"floored {ghost.EXIT_BPS * ghost.ENTER_FLOOR_MULT:.0f}bps | "
          f"${CLIP_USD:.0f}x{MAX_POSITIONS} | crypto_only={not ALLOW_NONCRYPTO} | "
          f"realized so far ${realized:+.2f} ({n_closed} closed)")

    last_ts = time.time()

    while True:
        t0 = time.time()
        # SOLE-WRITER ENFORCEMENT AT THE TOP OF THE LOOP ((hp)/(ic)).
        _ok_writer, _other = store.claim_writer(bot_id)
        if not _ok_writer:
            print(f"[{now_iso()}] STANDING DOWN — {bot_id} is claimed by "
                  f"another container ({_other}); holding until the claim "
                  f"expires ({store.WRITER_CLAIM_TTL}s).", flush=True)
            try:
                store.save_state(_standby_key(bot_id), {
                    "standing_down": True, "book": bot_id,
                    "duplicate_writer": _other,
                    "svc": store.service_name() or None,
                    "venue": _mode,
                    "caps": {"clip_usd": CLIP_USD,
                             "max_positions": MAX_POSITIONS},
                    "updated": now_iso(),
                    "ttl_sec": store.WRITER_CLAIM_TTL,
                })
            except Exception:  # noqa: BLE001
                pass
            time.sleep(LOOP_SECONDS)
            continue

        # The ghost's reference: the venue's own index_price per coin. A dark
        # reference blinds ENTRIES and the conv exit only — my price stop and
        # the clock still run on every held position ((nm): exits never sit
        # behind a data fetch).
        try:
            ref = ghost.reference_prices()
        except Exception:  # noqa: BLE001
            ref = {}

        universe, crypto_ok = resolve_universe(set(positions))
        census = {"scanned": len(universe), "ref_blind": 0 if ref else 1,
                  "noncrypto": 0, "no_book": 0, "held": 0,
                  "events": 0, "below_gate": 0, "confirming": 0,
                  "embargoed": 0, "ghost_slip": 0, "my_slip": 0,
                  "capped": 0, "opened": 0}
        devs_this_loop = []

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
                devs_this_loop.append(dev_bps)
                if abs(dev_bps) >= ghost.PRE_BPS:
                    census["events"] += 1

            held = positions.get(coin)
            if held:
                census["held"] += 1
                my_px = None
                g_px = None
                if bv is not None:
                    my_px = (bv["sell_vwap"] if held["side"] == "long"
                             else bv["buy_vwap"])
                    g_px = (bv["sell_vwap"] if held["ghost_side"] == "long"
                            else bv["buy_vwap"])
                if my_px is None:
                    first = held.setdefault("no_px_since", t0)
                    if (t0 - first) / 3600.0 >= ghost.DELIST_GIVEUP_H:
                        px = held.get("last_px")
                        pnl = _price_pnl(held, px)
                        realized += pnl
                        n_closed += 1
                        n_wins += 1 if pnl > 0 else 0
                        recent = (recent + [{"pnl": round(pnl, 4),
                                             "pct": pnl / held["notional"]}]
                                  )[-SAMPLE_N:]
                        _close(bot_id, coin, held, "delisted", px, pnl,
                               dev_now=dev_bps)
                        print(f"[{now_iso()}] CLOSE {coin} [delisted] "
                              f"pnl {pnl:+.2f} | banked {realized:+.2f}")
                        del positions[coin]
                    continue
                held.pop("no_px_since", None)
                held["last_px"] = my_px
                if held.get("family") == "dip":
                    reason = dip_exit(held, my_px, t0)
                    # my 5% stop stays senior beyond the ghost's own bounds
                    # (a gap through the bracket must still close the book)
                    if reason is None and my_px >= held["entry"] * (1.0 + MY_HARD_STOP):
                        reason = "stop"
                else:
                    reason = mirror_exit(held, dev_bps, my_px, g_px, t0)
                if reason is None:
                    continue
                pnl = _price_pnl(held, my_px)
                realized += pnl
                n_closed += 1
                n_wins += 1 if pnl > 0 else 0
                recent = (recent + [{"pnl": round(pnl, 4),
                                     "pct": pnl / held["notional"]}]
                          )[-SAMPLE_N:]
                held_h = (t0 - held["opened_ts"]) / 3600.0
                # the ghost's own non-convergence quarantine, mirrored: a
                # maxhold means the basis did NOT clear inside the hold —
                # the coin sits out until |dev| <= EXIT_BPS proves it did.
                if reason == "maxhold" and held.get("family") != "dip":
                    noconv[coin] = t0
                if held.get("family") == "dip":
                    dip_cd[coin] = t0            # taker-shape re-entry cooldown
                _close(bot_id, coin, held, reason, my_px, pnl, dev_now=dev_bps)
                print(f"[{now_iso()}] CLOSE {coin} {held['side']} after "
                      f"{held_h:.2f}h [{reason}] pnl {pnl:+.2f} | dev "
                      f"{dev_bps if dev_bps is None else round(dev_bps, 1)} | "
                      f"banked {realized:+.2f}")
                del positions[coin]
                continue

            # ---- entry: the ghost's event, the mirror's side --------------
            if dev_bps is None:
                if bv is None:
                    census["no_book"] += 1
                continue
            if coin in noconv:
                if abs(dev_bps) <= ghost.EXIT_BPS:
                    noconv.pop(coin, None)      # basis cleared — re-armed
                else:
                    census["embargoed"] += 1
                    pend[coin] = 0
                    continue
            tradeable = abs(dev_bps) >= enter_bps_eff
            # the ghost's own counter semantics, exactly: +1 on a tradeable
            # loop, hard 0 on a quiet one, UNTOUCHED on a blind one, and NOT
            # reset by a slip refusal (the ghost retried while the
            # dislocation persisted). A stricter counter here is a mirror
            # that misses events the ghost took.
            pend[coin] = pend.get(coin, 0) + 1 if tradeable else 0
            if not tradeable:
                census["below_gate"] += 1
                continue
            if pend[coin] < ghost.CONFIRM_LOOPS:
                census["confirming"] += 1
                continue
            if sum(1 for p in positions.values()
                   if p.get("family") != "dip") >= MAX_POSITIONS:
                census["capped"] += 1
                continue
            # the ghost's own slip gate decides whether the EVENT exists —
            # and it is priced AT THE GHOST'S OWN $10 CLIP, never mine: at
            # $250 my walk would refuse events the real ghost took, and the
            # error grows with clip size (caught in the 18-Aug risk-up
            # review). One extra book fetch only at this rare entry moment.
            g_side = ghost_side(dev_bps)
            try:
                bv_g = ghost.book_view(ctx, coin, ghost.ORDER_USD)
            except Exception:  # noqa: BLE001
                bv_g = None
            g_slip = None
            if bv_g is not None:
                g_slip = (bv_g["buy_slip_bps"] if g_side == "long"
                          else bv_g["sell_slip_bps"])
            if g_slip is None or g_slip > ghost.MAX_ENTRY_SLIP_BPS:
                census["ghost_slip"] += 1
                continue
            # the (lk) class screen, at the ENTRY SITE — the event is real
            # (it fed the gate and the census); the mirror declines the
            # class. Revert KELLY_ALLOW_NONCRYPTO=1.
            if coin not in crypto_ok:
                census["noncrypto"] += 1
                continue
            pos = _open_mirror(positions, coin, dev_bps, bv, t0, r)
            if pos is None:
                census["my_slip"] += 1
                continue
            pend[coin] = 0
            census["opened"] += 1
            print(f"[{now_iso()}] OPEN {coin} {pos['side'].upper()} "
                  f"${CLIP_USD:.0f} @ {pos['entry']:.6g} | dev "
                  f"{dev_bps:+.1f}bps (gate {enter_bps_eff:.0f}) | riding "
                  f"the {'premium' if dev_bps > 0 else 'discount'} the ghost "
                  f"would fade")

        # ---- dipfade entries (the second family, probe size) ---------------
        # The taker's own ticket source, its own freshness contract; the
        # ghost bar is its conviction filter. No tickets / dark scout is
        # "no opinion", never "no dip exists".
        census["dip_tickets"] = 0
        census["dip_opened"] = 0
        census["dip_cooldown"] = 0
        census["dip_capped"] = 0
        census["dip_slip"] = 0
        try:
            scout = fresh_scout(store.load_state(SCOUT_KEY), t0)
        except Exception:  # noqa: BLE001
            scout = None
        if scout:
            tickets = (scout.get("tickets") or {}).get("dip") or []
            census["dip_tickets"] = len(tickets)
            for tk in tickets:
                sym = dip_ghost_takes(tk, crypto_ok)
                if not sym or sym in positions:
                    continue
                if t0 - dip_cd.get(sym, 0.0) < DIP_COOLDOWN_S:
                    census["dip_cooldown"] += 1
                    continue
                if sum(1 for p in positions.values()
                       if p.get("family") == "dip") >= DIP_MAX_POSITIONS:
                    census["dip_capped"] += 1
                    break
                try:
                    if not ctx.supports(sym):
                        continue
                    bv_d = ghost.book_view(ctx, sym, DIP_CLIP_USD)
                except Exception:  # noqa: BLE001
                    bv_d = None
                if bv_d is None:
                    continue
                pos = _open_dip(positions, sym, bv_d, t0, tk)
                if pos is None:
                    census["dip_slip"] += 1
                    continue
                dip_cd[sym] = t0
                census["dip_opened"] += 1
                print(f"[{now_iso()}] OPEN {sym} SHORT ${DIP_CLIP_USD:.0f} "
                      f"[dipfade probe] range_pos "
                      f"{tk.get('range_pos')} chg {tk.get('chg_pct')}% | "
                      f"the ghost the taker vetoed buys the dip; the "
                      f"mirror sells it")

        # zeroed counters drop; a coin the loop could not SEE keeps its
        # counter (the ghost's own behavior — a blind loop is not a quiet
        # one). Age-capped so a delisted coin cannot hold a slot forever.
        pend = {c: n for c, n in pend.items() if n > 0}
        if len(pend) > 3 * ghost.UNIVERSE_N:
            pend = {}
        noconv = {c: t for c, t in noconv.items()
                  if t0 - t < STATE_PRUNE_S}
        dip_cd = {c: t for c, t in dip_cd.items()
                  if t0 - t < STATE_PRUNE_S}

        # the NEXT loop's adaptive gate, from every book seen THIS loop —
        # the ghost's own recompute, its own function, its own constants,
        # over the ghost's own UNSCREENED scan (the gate's distribution is
        # part of the founded policy). The observed distribution publishes
        # beside the gate so a drifted percentile is falsifiable from the
        # payload alone (I18), not just asserted.
        enter_bps_eff = ghost.adaptive_enter_bps(
            devs_this_loop, ghost.ENTER_PCT, ghost.EXIT_BPS,
            ghost.ENTER_FLOOR_MULT, ghost.ENTER_BPS, ghost.ENTER_MIN_N)
        if devs_this_loop:
            _a = sorted(abs(d) for d in devs_this_loop)
            census["dev_n"] = len(_a)
            census["dev_med_bps"] = round(_a[len(_a) // 2], 1)
            # SAME nearest-rank convention as the gate's own function, or the
            # census cannot falsify the gate: with one 170bps outlier in 40
            # books the gate's p98 is the SECOND-largest (index round(.98*39))
            # while a naive int(.98*n) shows the max — measured 19-Aug, that
            # mismatch read as a stuck gate and cost an investigation.
            _i = min(len(_a) - 1, max(0, int(round(0.98 * (len(_a) - 1)))))
            census["dev_p98_bps"] = round(_a[_i], 1)
            census["dev_max_bps"] = round(_a[-1], 1)

        # ---- publish -------------------------------------------------------
        open_pnl = sum(_price_pnl(p, p.get("last_px")) for p in positions.values())
        equity = START_EQUITY + realized + open_pnl
        extra = build_extra(census, positions, recent, open_pnl, realized,
                            enter_bps_eff)
        try:
            store.publish(
                bot_id, status="online", equity=equity,
                pnl_abs=realized + open_pnl,
                pnl_pct=(equity / START_EQUITY - 1.0),
                open_trades=len(positions),
                closed_trades=n_closed, wins=n_wins,
                losses=n_closed - n_wins, extra=extra)
            # MTM equity series from DAY ONE ((hq)/I9).
            store.snapshot_equity(bot_id, equity, len(positions), realized)
        except Exception:  # noqa: BLE001
            pass
        try:
            store.save_state(bot_id, build_state(
                positions, recent, pend, noconv, enter_bps_eff, last_ts, t0,
                dip_cd=dip_cd))
        except Exception:  # noqa: BLE001
            pass
        last_ts = t0

        held_s = ", ".join(
            f"{c}:{p['side'][0].upper()}" for c, p in sorted(positions.items())
        ) or "none"
        print(f"[{now_iso()}] scan ok | {census['scanned']} coins | gate "
              f"{enter_bps_eff:.0f}bps | open: {held_s} | open_pnl "
              f"{open_pnl:+.2f} | banked {realized:+.2f} | events "
              f"{census['events']}, below_gate {census['below_gate']}, "
              f"opened {census['opened']}")

        if args.once:
            print(f"[{now_iso()}] --once smoke test complete.")
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


# --------------------------- selftest ----------------------------------------
def _selftest():
    """Offline. Pins the four things a future edit could silently break:
    the mirror inversion itself, the ghost import identity (one owner, no
    second copy), the exit ladder on both sides, and the publish/state
    builders' contracts."""
    import inspect

    # 1) THE THESIS: the mirror is ALWAYS the ghost's opposite, at every
    #    residual sign — the finding, pinned as a property.
    for dev in (-500.0, -60.1, -0.01, 0.01, 60.1, 500.0):
        assert mirror_side(dev) != ghost_side(dev), dev
    assert mirror_side(75.0) == "long"       # rich -> ride the premium
    assert mirror_side(-75.0) == "short"     # cheap -> ride the discount
    assert ghost_side(-75.0) == "long"       # the fader bought the dip

    # 2) ONE OWNER: the gate math is the retired module's own callable, not
    #    a copy ((hj): a second copy of a rule is a second rule). The
    #    fixture values are the ghost's own selftest cases.
    assert ghost.adaptive_enter_bps([0.0] * 25, 0.98, 40.0, 1.5, 150.0, 20) == 60.0
    assert ghost.adaptive_enter_bps([500.0] * 25, 0.98, 40.0, 1.5, 150.0, 20) == 150.0
    assert ghost.adaptive_enter_bps([], 0.98, 40.0, 1.5, 150.0, 20) == 150.0
    assert ghost.EXIT_BPS == 40.0 and ghost.HARD_STOP == 0.05
    assert ghost.MAX_HOLD_S == 7200.0 and ghost.CONFIRM_LOOPS == 2

    # 3) THE EXIT LADDER, both sides. Mirror LONG from a ghost SHORT:
    pos = {"coin": "X", "side": "long", "ghost_side": "short",
           "entry": 100.0, "ghost_entry": 100.0, "notional": 80.0,
           "opened_ts": 1000.0, "last_px": 100.0}
    # basis cleared -> conv, senior to everything
    assert mirror_exit(pos, 10.0, 100.0, 100.0, 1001.0) == "conv"
    # ghost short stopped (+5% on ghost's exit px) = my profit-side cover
    assert mirror_exit(pos, 80.0, 105.2, 105.2, 1001.0) == "ghoststop"
    # my own 5% adverse stop (price fell against my long)
    assert mirror_exit(pos, 80.0, 94.9, 94.9, 1001.0) == "stop"
    # the ghost's 2h clock
    assert mirror_exit(pos, 80.0, 101.0, 101.0, 1000.0 + 7200.0) == "maxhold"
    # nothing fired
    assert mirror_exit(pos, 80.0, 101.0, 101.0, 1001.0) is None
    # dark reference: conv unreachable, price stop still live ((nm))
    assert mirror_exit(pos, None, 94.9, 94.9, 1001.0) == "stop"
    # Mirror SHORT from a ghost LONG:
    pos_s = {"coin": "X", "side": "short", "ghost_side": "long",
             "entry": 100.0, "ghost_entry": 100.0, "notional": 80.0,
             "opened_ts": 1000.0, "last_px": 100.0}
    assert mirror_exit(pos_s, -80.0, 94.7, 94.7, 1001.0) == "ghoststop"
    assert mirror_exit(pos_s, -80.0, 105.1, 105.1, 1001.0) == "stop"

    # 4) P&L arithmetic, both signs.
    assert abs(_price_pnl(pos, 102.0) - 1.6) < 1e-9           # long +2% on $80
    assert abs(_price_pnl(pos_s, 102.0) - (-1.6)) < 1e-9      # short -2%
    assert _price_pnl({"side": "long", "entry": None, "notional": 80.0,
                       "last_px": None}, 0.0) == 0.0

    # 5) CONSISTENCY RULE: _open_mirror's signature carries no streak, no
    #    outcome, no equity — size cannot vary with results without
    #    changing this function's shape (the douglas pin, kept).
    params = list(inspect.signature(_open_mirror).parameters)
    assert params == ["positions", "coin", "dev_bps", "bv", "t0", "ref"], params
    # and it fills at MY side's vwap, slip-gated
    ps = {}
    bv = {"mid": 100.0, "buy_vwap": 100.02, "sell_vwap": 99.98,
          "buy_slip_bps": 2.0, "sell_slip_bps": 2.0, "spread_bps": 4.0}
    got = _open_mirror(ps, "Y", 75.0, bv, 5.0, 99.2)
    assert got and got["side"] == "long" and got["ghost_side"] == "short"
    assert got["entry"] == 100.02 and got["ghost_entry"] == 99.98
    assert _open_mirror({}, "Z", 75.0, dict(bv, buy_slip_bps=MY_MAX_SLIP_BPS + 1),
                        5.0, 99.2) is None                      # my slip gate
    assert _open_mirror({}, "Z2", 75.0, dict(bv, buy_slip_bps=45.0),
                        5.0, 99.2) is not None  # 45bps admitted (60 gate)

    # 6b) DIPFADE, the probe family: the taker's conviction bar decides the
    #     event; the ghost long's bracket mirrors into my exits; my slip
    #     gate holds at entry; the ladder's win/loss sides cannot swap.
    assert dip_ghost_takes({"sym": "AAA", "range_pos": 0.04}, {"AAA"}) == "AAA"
    assert dip_ghost_takes({"sym": "AAA", "range_pos": 0.06}, {"AAA"}) is None
    assert dip_ghost_takes({"sym": "AAA", "range_pos": 0.01,
                            "noncrypto": True}, {"AAA"}) is None
    assert dip_ghost_takes({"sym": "WTI", "range_pos": 0.01}, {"AAA"}) is None
    dpos = {"coin": "A", "family": "dip", "side": "short",
            "entry": 100.0, "notional": 40.0, "opened_ts": 0.0,
            "last_px": 100.0}
    assert dip_exit(dpos, 104.1, 1.0) == "ghosttp"     # ghost banked = I pay
    assert _price_pnl(dict(dpos), 104.1) < 0
    assert dip_exit(dpos, 96.9, 1.0) == "ghostsl"      # ghost died = I bank
    assert _price_pnl(dict(dpos), 96.9) > 0
    assert dip_exit(dpos, 100.5, 1.0) is None
    assert dip_exit(dpos, 100.5, DIP_MAX_HOLD_S) == "maxhold"
    import inspect as _insp
    assert list(_insp.signature(_open_dip).parameters) == [
        "positions", "sym", "bv", "t0", "ticket"]      # consistency rule
    dbv = {"mid": 100.0, "buy_vwap": 100.02, "sell_vwap": 99.98,
           "buy_slip_bps": 2.0, "sell_slip_bps": 2.0, "spread_bps": 4.0}
    got_d = _open_dip({}, "B", dbv, 5.0, {"range_pos": 0.03})
    assert got_d and got_d["family"] == "dip" and got_d["side"] == "short"
    assert got_d["notional"] == DIP_CLIP_USD
    assert _open_dip({}, "C", dict(dbv, sell_slip_bps=MY_MAX_SLIP_BPS + 1),
                     5.0, {}) is None
    st_f = fresh_scout({"updated": "2000-01-01T00:00:00+00:00",
                        "ttl_sec": 900}, 4102444800.0)
    assert st_f is None                                # stale scout = None

    # 6) Publish/state builders: contracts a consumer reads.
    ex = build_extra({"scanned": 1}, ps, [], 0.5, -0.25, 61.0)
    assert ex["caps"]["crypto_only"] is True
    assert ex["caps"]["clip_usd"] == CLIP_USD
    assert ex["caps"]["gate_bps"] == 61.0
    assert ex["roster"]["snapfade"]["status"] == "live"
    assert ex["roster"]["brkfade"]["status"] == "refused"
    assert ex["held"] == {"Y": "L"}
    st = build_state(ps, [], {"Y": 1}, {"Z": 9.0}, 61.0, 4.0, now=5.0)
    assert st["positions"] is ps and st["enter_bps_eff"] == 61.0
    assert st["saved_ts"] == 5.0
    assert _standby_key("band-kelly-lshadow") == "band-kelly-lshadow:standby"

    # 7) the scan is the GHOST'S, unscreened — the class screen lives at the
    #    ENTRY (crypto_ok), because the adaptive gate's percentile is part
    #    of the founded policy. And an empty classifier ("no opinion")
    #    refuses nothing ((hk)/(lk) fail-OPEN).
    if fleet_bus is not None:
        _orig = fleet_bus.crypto_only
        try:
            fleet_bus.crypto_only = lambda s: []
            uni, ok = resolve_universe(set())
            assert uni, "empty screen emptied the universe — (hk) violated"
            assert ok == set(uni), "no-opinion classifier must refuse nothing"
            fleet_bus.crypto_only = lambda s: [x for x in s if x != "BTC"]
            uni2, ok2 = resolve_universe(set())
            assert "BTC" in uni2, (
                "the SCAN must stay the ghost's own — screening it moves the "
                "adaptive gate's distribution off the founded policy")
            assert "BTC" not in ok2, "the screen must still bind at ENTRY"
        finally:
            fleet_bus.crypto_only = _orig

    # 8) sample block: win rate reported, never gated on.
    sb = sample_block([{"pnl": 1.0, "pct": 0.0125}, {"pnl": -0.5, "pct": -0.00625}])
    assert sb["n"] == 2 and sb["win"] == 0.5
    assert abs(sb["expectancy_r"] - round(((0.0125 - 0.00625) / 2) / MY_HARD_STOP, 3)) < 1e-9

    print("selftest ok — the mirror inverts, the ghost's math is imported "
          "not copied, both exit ladders fire, contracts hold")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    main()
