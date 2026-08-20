#!/usr/bin/env python3
"""🙏 Avo Maria LIVE — the SwingDip family book on real money, in the live
Ticket Taker's old slot.

    python3 lighter_avo_live_bot.py               # daemon (production)
    python3 lighter_avo_live_bot.py --once        # single cycle then exit
    python3 lighter_avo_live_bot.py --selftest    # offline stub-venue checks

THE SLOT SWAP (2026-08-13, operator decision). The live Ticket Taker's only
lens crossed its own realised veto bar on 11-Aug (n=27, mean −1.258%/trade,
t=−1.80) and the book halted itself — structurally frozen, an I17 shape on a
real-money row. The operator's call, made explicitly and recorded as his:
retire the Taker from the live slot and run 🙏 Avo Maria (SwingDipV1 on 4h)
on the same service, keys and sub-account, sized to the actual balance —
the 17-Jul Tide Rider → Ticket Taker swap pattern, third occupant.

EVIDENCE BASIS, stated honestly (I19): the shadow book's Lighter record at
the swap was n≈10 closes, +1.378%/trade, t=+1.68, 3/6 go-live bars
(closes/window/t binding), horizon "on_track". That does NOT pass the (fk)
gate. This go-live is an explicit operator act against the gate's advice,
which go-live has always been the operator's to make; the shadow twin keeps
running in family-lighter-shadow as the control arm, and this arm's own
ledger will grade the decision.

WHAT THIS FILE IS. A LIVE RUNNER, not a second strategy: every strategy
number — signal, ROI ladder, stoploss, protections, timeframe, slots — is
IMPORTED from lighter_family_bot's own configured instance (a retyped
constant is a constant that drifts; a second copy of a rule is a second
rule). What is new here is only the live plumbing, lifted from the fleet's
two proven live bots:

  * explicit identity (AVO_VENUE=lighter_live ONLY — the shadow arm already
    runs in family-lighter-shadow, so a second shadow writer would pool the
    graded ledger; refuse anything else)
  * one book one writer (claim_writer at the top of every cycle; the loser
    stands down on its own standby key)
  * SafetyRails: hard notional cap (FREQTRADE_AVO_MARIA_MAX_NOTIONAL,
    boot-refused if missing), kill switch flattens IN-LOOP (the taker's
    live_boot_gate rule: boot-refusing on an armed switch would strand the
    book on the next restart — the switch must reach the flatten)
  * equity through the EquityGuard (guard_state_key — an unvetted
    dislocated print once sold a book into the dislocation for a real −5.9%)
  * daily-loss rails: the family 10% day rail (confirm-debounced) AND the
    absolute-dollar rail, both against a capital-adjusted day anchor
  * fill telemetry on BOTH legs (venues.fills.read_fill; an unmeasured leg
    records the decision price, labelled, slippage NULL — never zero)
  * durable state under this row's OWN key, seed-guarded (a failed read
    must not seed a fresh book over the record)
  * policy stamped on every close so the go-live grader's era discipline is
    mechanical from birth ((jf)); veto/gate state PUBLISHED on the row from
    birth ((lw) — a gate that stops gating must not look like one that is
    correctly quiet)

SIZED TO THE BALANCE (the operator's ask): clip = equity / max_open at entry
time — at the swap that is ~$62.80 / 4 ≈ $15.70 — scaled by the strategy's
own stake_mult and the board's live.clip_scale lever, capped by the hard
notional rail. Protections' drawdown denominator is the live baseline, not
the shadow's $1,000 (20% of a paper grand would never bind on a $63 book).

[2026-08-20 (so)] THE LIVE ARM NOW SIZES OFF THE BRAIN. Eamon: "Implement
into live and other bots without it." This paragraph used to open "WHAT THE
LIVE ARM DELIBERATELY DOES NOT DO: read brain stake-mults (doctrine: no live
bot sizes off the brain)", and that clause is CORRECTED IN PLACE per I12
rather than left standing as history — a doctrine line that no longer
describes the system is a defect, and this one described a training wheel.
What replaces it is a rails argument, not a weaker rule: the mult returns a
NUMBER, and `rails.notional_ok` below still refuses it, the kill switch still
kills, the daily-loss halt still halts and SafetyRails' caps remain
operator-only. The multiplier proposes; the rails dispose. It reads BOTH rows
(live + its shadow control arm) under `ledger_tag`, exactly as the regime gate
five lines from the sizing site already did — an arm with n=3 of its own
cannot earn an opinion, and its designed control arm can (I14).

WHAT THE LIVE ARM STILL DELIBERATELY DOES NOT DO: read fleet_allocation (real
money never reads it — AST-pinned in tests/autonomy/test_allocation_consumer.py)
or consume any tuning lane of its own (env-only config, the Garrett/Kiyosaki
rule — a single-policy (hm) clock by construction). Restrict-only reads it
KEEPS: the fleet long-budget veto + per-symbol cap (it is a directional LONG
book), the brain's regime entry gate (restrict-only, fail-open), and the
coin-quality veto (measured venue toxicity, new entries only) — the same
live-entry hygiene the Farmer and the Taker run.
"""

import argparse
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import funding_basis
import fleet_tuning as tuning
from lighter_family_bot import (
    STRATEGIES, CandleCache, COINS, NONCRYPTO_UNIVERSE,
    regime_inputs_for, btc_regime_up, btc_tide_up, noncrypto_regimes,
    noncrypto_entry_blocked, brain_entry_gated, brain_clip_for,
    ledger_reason, ledger_tag,
    symcap_state, symcap_blocked, _interval_ms, MOMO_TIDE_GATE,
    NONCRYPTO_EFFECTIVE,
)
from venues import marks
from venues.safety import (
    SafetyRails, open_notional, capital_adjusted_day_start)
from venues.fills import read_fill, measured_from_reason

BOT = "freqtrade-avo-maria"
BOT_ROW = BOT + "-lighter"            # the LIVE row (venue_variant admits it)
SHADOW_ROW = BOT + "-lshadow"         # the control arm (family-lighter-shadow)
STATE_KEY = BOT_ROW + ":live"

#: The configured SwingDip instance (from the family REGISTRY, `STRATEGIES`) — tf=4h, stoploss=-0.10, max_open=4,
#: roi ladder, protections — taken from the family bot's OWN registry so the
#: two arms cannot drift. Identity (S is the registry object) is selftested.
S = next(s for s in STRATEGIES if s.bot == BOT)

LOOP_SECONDS = int(os.environ.get("AVO_LOOP_SECONDS", "300"))
DAILY_LOSS_LIMIT = float(os.environ.get("AVO_DAILY_LOSS", "0.10"))
DELIST_GIVEUP_H = float(os.environ.get("AVO_DELIST_GIVEUP_H", "6"))
#: Below this clip the book is dust — skip entries rather than spray sub-$5
#: orders on a real venue.
MIN_CLIP_USD = float(os.environ.get("AVO_MIN_CLIP_USD", "5"))
#: Coin-quality veto freshness (mirrors the taker's read of `coin-vetoes`).
QUALITY_VETO_TTL_S = float(os.environ.get("AVO_QUALITY_VETO_TTL_S", "5400"))

_PRINT = print  # selftest capture point


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def now():
    return datetime.now(timezone.utc)


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def clip_usd(equity):
    """Per-entry clip sized to the ACTUAL balance: equity / slots. None when
    equity is unreadable — a live book does not size off a guess."""
    if equity is None or equity <= 0:
        return None
    return equity / float(S.max_open)


LIVE_CLIP_LEVER = "live.avo.clip_scale"


def _clip_scale_now():
    """[(mz)] The clamped live clip scale the entry path applies, re-read at
    publish time so the row's clip_usd is the EFFECTIVE entry clip whichever
    code path publishes (the halt paths publish before the entry section
    refreshes its loop-local copy). Fail-open 1.0 on a dark rail.

    [2026-08-16 (nj)] THIS BOOK HAS ITS OWN ARM. It used to read
    `live.clip_scale` — the SHARED live dial — so 🙏 Avo was sized by a
    decision the evidence board made from 💸 the Farmer's metrics alone (Avo
    was not even in the board's LIVE_ROWS cohort).

    [2026-08-16, BRIDGE CLOSED] It shipped with a fallback to the shared
    lever, justified as "no protection gap during the deploy window". That
    was right for the window and WRONG the moment it closed: with no live
    clip lever in force (the steady state), Avo's own arm is absent on every
    read, so the fallback fires and the Farmer's dial steers Avo again the
    instant the board restricts it — restoring the exact coupling (nj)
    existed to remove. A bridge with no expiry is not a bridge, it is the
    old behaviour with extra steps. Both consumers are now deployed and
    verified by stamp (board in freqtrade-bots; this book at c317eb48e37b),
    and the board writes per-row — `live_released_ts` reads as a per-row map
    on the live payload — so the bridge is spent and removed. This book now
    reads ITS OWN arm and nothing else; absent means 1.0, the operator's env
    sizing, never another book's verdict.

    RESTRICT-ONLY, and that is structural rather than a policy: the clamp is
    min(1.0, ...), so this lever can only ever SHRINK Avo's clip. With
    clip = equity/max_open and stake_mult <= 1.0, gross notional can never
    exceed account equity — the book is 1.00x by construction and no lever
    reaches past it. The registry cage (hi = 1.0) mirrors this exactly."""
    try:
        import fleet_tuning as tuning
        return max(0.25, min(1.0, float(
            tuning.get_lever(LIVE_CLIP_LEVER, 1.0))))
    except Exception:  # noqa: BLE001
        return 1.0


def roi_exit_due(age_min, profit):
    """freqtrade-style ROI ladder, byte-identical to the family Book's rule:
    the rung is the LARGEST minute key <= age, exit when profit >= its bar."""
    if not S.roi:
        return False
    rung = max((k for k in S.roi if k <= age_min), default=None)
    return rung is not None and profit >= S.roi[rung]


def entries_locked(closed, t_now, baseline):
    """The family Book's protections (slguard + maxdd) on THIS arm's own
    closes, with the drawdown denominator the LIVE baseline instead of the
    shadow's $1,000 — 20% of a paper grand would never bind on a $63 book.
    Returns the lock-release ts (0.0 = unlocked) so the row can PUBLISH it."""
    tf_s = _interval_ms(S.tf) / 1000.0
    p = S.protections
    sg = p.get("slguard")
    if sg:
        win = [c for c in closed if t_now - c["ts"] <= sg["lookback"] * tf_s]
        if sum(1 for c in win if c.get("stop")) >= sg["trades"]:
            return t_now + sg["stop"] * tf_s
    dd = p.get("maxdd")
    ref = baseline if baseline and baseline > 0 else 1000.0
    if dd:
        win = [c for c in closed if t_now - c["ts"] <= dd["lookback"] * tf_s]
        if len(win) >= dd["trades"]:
            cum = peak = worst = 0.0
            for c in win:
                cum += c["pnl"]
                peak = max(peak, cum)
                worst = max(worst, (peak - cum) / ref)
            if worst >= dd["dd"]:
                return t_now + dd["stop"] * tf_s
    return 0.0


def main(_ctx=None, once=False):
    """One live SwingDip book against the venue. `_ctx` is a TEST-ONLY
    injection point ({venue, rails}); production calls main() with no args.
    It bypasses the identity guard so the order path can be driven offline —
    it does NOT bypass SafetyRails (kill switch + cap stay senior)."""
    # [IDENTITY — the TT_VENUE rule, same reasoning verbatim] This bot's row
    # and whether it trades REAL MONEY come from $AVO_VENUE, and it has no
    # default it can safely inherit. lighter_live is the ONLY accepted value:
    # the shadow arm already runs in family-lighter-shadow, so a second
    # shadow writer here would be two writers of one graded ledger — the (hp)
    # class this fleet has already paid for once.
    if _ctx is None:
        mode = os.environ.get("AVO_VENUE", "").strip()
        if mode != "lighter_live":
            raise SystemExit(
                "AVO_VENUE must be EXACTLY 'lighter_live' (got "
                f"{mode!r}). This file is the live arm only — the shadow "
                "book runs in family-lighter-shadow, and a second shadow "
                "writer would pool the graded ledger (one book, one writer).")

    if _ctx is None:
        from venues.lighter_client import LighterClient
        venue = LighterClient(
            net="mainnet", with_signer=True,
            # guard_state_key is load-bearing: without it vet_account_read
            # returns raw prints unvetted and the daily-loss rail runs on a
            # dislocated read — the 11-Jul −5.9% failure, verbatim.
            guard_state_key=BOT_ROW + ":eqguard",
            guard_persist_reject_streak=True)
        rails = SafetyRails(BOT, "lighter_live")
    else:
        venue = _ctx["venue"]
        rails = _ctx["rails"]

    # [BOOT GATE — the taker's live_boot_gate rule, daemon-adapted] The CAP is
    # a hard boot gate; the KILL SWITCH is not — an armed switch must reach
    # the in-loop flatten, because refusing to BOOT on it would strand the
    # book on the very next restart with no stop and no manager.
    if rails.live and rails.max_notional is None:
        try:
            store.set_status(BOT_ROW, "error")
        except Exception:  # noqa: BLE001
            pass
        raise SystemExit(
            "lighter_live requires an explicit per-bot notional cap "
            "(FREQTRADE_AVO_MARIA_MAX_NOTIONAL) — refusing to start.")

    cache = CandleCache(venue)
    universe = [c for c in (list(COINS) + list(NONCRYPTO_UNIVERSE))
                if venue.supports(c)]
    has_noncrypto = any(c in NONCRYPTO_EFFECTIVE for c in universe)

    _PRINT(f"[avo-live] {iso(now())} BOOT | {S.style} tf={S.tf} "
           f"stop={S.stoploss:.0%} slots={S.max_open} roi={S.roi} | "
           f"universe={len(universe)} | cap=${rails.max_notional} | "
           f"loop={LOOP_SECONDS}s", flush=True)

    # ---- durable state (seed-guarded) --------------------------------------
    restored = False
    state = {}
    stats = {"closed": 0, "wins": 0}

    def _restore():
        nonlocal restored, state, stats
        if not os.environ.get("DATABASE_URL", "").strip() and _ctx is None:
            restored, state = True, {}
            return
        ok, saved = store.load_state_checked(STATE_KEY)
        if not ok:
            _PRINT(f"[avo-live] {iso(now())} state read FAILED — refusing to "
                   f"seed a fresh book over the record; retrying next cycle",
                   flush=True)
            return
        restored, state = True, (saved or {})
        try:
            agg = store.fetch_paper_aggregate(BOT_ROW)
            if agg:
                stats.update(closed=agg["closed"], wins=agg["wins"])
        except Exception:  # noqa: BLE001
            pass

    _restore()

    # [2026-08-18 (pq)] The daily-loss latch lives ACROSS cycles, not inside
    # one. `_halt_day` is the UTC day the latch belongs to; a roll is the only
    # thing that clears it (see the read site in the loop).
    halted_today = False
    _halt_day = None

    while True:
        t0 = time.time()
        t_now = now()
        cur_day = t_now.date().isoformat()

        # ---- one book, one writer (top of the cycle, before any act) -------
        _ok_writer, _other = store.claim_writer(BOT_ROW)
        if not _ok_writer:
            _PRINT(f"[avo-live] {iso(t_now)} STANDING DOWN — {BOT_ROW} "
                   f"claimed by {_other}; skipping cycle", flush=True)
            try:
                store.save_state(BOT_ROW + ":standby", {
                    "standing_down": True, "book": BOT_ROW,
                    "duplicate_writer": _other,
                    "svc": store.service_name() or None,
                    "venue": "lighter_live",
                    "caps": {"max_open": S.max_open},
                    "updated": iso(t_now),
                    "ttl_sec": store.WRITER_CLAIM_TTL})
            except Exception:  # noqa: BLE001
                pass
            if once:
                return
            time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))
            continue

        if not restored:
            _restore()
            if not restored:
                try:
                    store.heartbeat(BOT_ROW)
                except Exception:  # noqa: BLE001
                    pass
                if once:
                    return
                time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))
                continue

        meta = {str(k): v for k, v in (state.get("meta") or {}).items()}
        closed_win = list(state.get("closed") or [])
        cooldown = {str(k): float(v)
                    for k, v in (state.get("cooldown") or {}).items()}
        last_sig_ts = dict(state.get("last_sig_ts") or {})
        baseline = state.get("initial_equity")
        capital_adjust = float((state.get("capital_adjust") or {}).get("total")
                               or 0.0)
        day_state = state.get("day_start") or {}
        day_start_equity = (day_state.get("equity")
                           if day_state.get("day") == cur_day else None)

        # ---- equity (guard-vetted) -----------------------------------------
        try:
            equity = venue.account_value()
        except Exception as e:  # noqa: BLE001 — guard rejected or venue down
            _PRINT(f"[avo-live] {iso(t_now)} account value unavailable: {e!r}")
            equity = None
        # capital moves fold into the adjust total, never into P&L
        try:
            _moves = venue.pop_capital_moves() or []
            _delta = sum(float(m.get("delta") or 0.0) for m in _moves
                         if isinstance(m, dict))
            if _delta:
                capital_adjust += _delta
                # [14-Aug (mi)] THE SHARED RULE, not a third copy of it.
                # `capital_adjusted_day_start` (venues/safety.py) is the one
                # source of this arithmetic precisely because a money rule with
                # two definitions is one edit from drifting — and this file's
                # inline copy had ALREADY drifted: the helper rounds the shifted
                # baseline to 2dp and the copy did not, so the two live bots'
                # daily-loss leashes were measuring from subtly different
                # anchors. Shifts only when a baseline exists AND a move folded,
                # so the None case below still adopts the capital-INCLUSIVE
                # equity and is not shifted twice.
                day_start_equity, _shifted = capital_adjusted_day_start(
                    day_start_equity, _delta)
                _PRINT(f"[avo-live] {iso(t_now)} capital move ${_delta:+.2f} "
                       f"folded (P&L stays trading-only)"
                       f"{f'; day-start -> {day_start_equity:.2f}' if _shifted else ''}")
        except Exception:  # noqa: BLE001
            pass
        if baseline is None and equity is not None:
            baseline = equity
            _PRINT(f"[avo-live] {iso(t_now)} LIVE BASELINE captured: "
                   f"${equity:.2f} (P&L reads from here)")
        if day_start_equity is None and equity is not None:
            day_start_equity = equity
            _PRINT(f"[avo-live] {iso(t_now)} day-start equity for {cur_day}: "
                   f"{equity:.2f}")

        # ---- venue truth: the positions the exits must manage --------------
        try:
            pos = dict(venue.positions() or {})
            pos_readable = True
        except Exception as e:  # noqa: BLE001
            _PRINT(f"[avo-live] {iso(t_now)} positions unreadable ({e!r}) — "
                   f"skipping cycle; never trade blind")
            pos, pos_readable = {}, False

        # [2026-08-18 (pq)] THE HALT IS LATCHED, AND A FAILED READ DOES NOT
        # CLEAR IT. This was `halted_today = bool(store.load_daily_halt(...))`
        # — RE-DERIVED from a database read on every single cycle, with no
        # memory of having halted. Two consequences on a real-money book:
        #   * `load_daily_halt` returned None for BOTH "not halted" and "the
        #     read failed" (its own docstring now says so), so one Postgres
        #     blip re-admitted entries on a day this book had already halted;
        #   * nothing re-armed it — `breach` at :621 is recomputed from live
        #     equity, so once equity sits above day_start*(1-LIMIT) the halt
        #     was simply gone for the rest of the day.
        # The sibling live book latches (lighter_funding_bot.py sets
        # halted_today True and clears it ONLY on the UTC day roll, :2219);
        # this is that shape. `halt_blind` carries "I could not find out" so
        # the entry gate can fail CLOSED without pretending to know — the
        # Farmer's `live_state_blind` idiom (:2688): block NEW entries while
        # blind, never block exits.
        if _halt_day != cur_day:            # UTC day roll: the only reset
            _halt_day, halted_today = cur_day, False
        halt_blind = False
        if _ctx is None or hasattr(store, "load_daily_halt_checked"):
            _hok, _halt = store.load_daily_halt_checked(BOT_ROW, cur_day)
            if not _hok:
                halt_blind = True
                _PRINT(f"[avo-live] {iso(t_now)} HALT READ FAILED — holding "
                       f"halted={halted_today} and blocking NEW entries this "
                       f"cycle; exits unaffected", flush=True)
            elif _halt:
                halted_today = True

        # Loop-scope defaults so the publish helper is callable from the
        # kill/halt paths, which run BEFORE the entry section assigns these.
        locked_until = 0.0
        fleet_long_veto = False
        brain_gated_tags = []
        coin_vetoed = {}
        live_scale = 1.0

        def _persist_day(dse, day):
            state["day_start"] = {"day": day, "equity": dse}

        def _persist():
            state.update({
                "initial_equity": baseline, "meta": meta,
                "closed": closed_win[-200:], "cooldown": cooldown,
                "last_sig_ts": last_sig_ts, "last_accrue": t0,
                "capital_adjust": {"total": round(capital_adjust, 2)}})
            ok = store.save_state(STATE_KEY, state)
            if ok is False:
                _PRINT(f"[avo-live] {iso(t_now)} CRITICAL: state WRITE "
                       f"FAILED — positions' meta (entry, tag, clocks) did "
                       f"NOT persist", flush=True)

        def _margin_block(live_pos):
            """The venue's margining view for the row, or None.

            [2026-08-16, CORRECTED] Marks came from this book's OWN
            `meta[coin]['last_px']` — a price recorded whenever the loop last
            touched that coin, not a live one. `dist_pct` / `nearest_liq` are
            RISK numbers, and venues/marks.py is the sanctioned source for
            those: live order-book mids only, because a stale price silently
            freezes a risk read while the real price runs away. Avo shows no
            `dist_pct` today (its longs have no liq price at 1x, so the branch
            never runs), which is precisely why this was worth fixing BEFORE
            it mattered — a latent wrong-price path on a real-money book is
            not less wrong for being currently unreachable.

            Never raises: a telemetry read must not be able to stop a live
            trading loop, and an exception degrades to 'unknown', not a number.
            """
            try:
                fn = getattr(venue, "margin_state", None)
                if not callable(fn):
                    return None
                live, blind = marks.stop_marks(venue, list(live_pos or []))
                st = fn(marks=live or None)
                if st is not None and blind:
                    st["mark_blind"] = sorted(blind)
                return st
            except Exception:  # noqa: BLE001
                return None

        def _publish_row(eq, base_eq, cap_adj, live_pos, st,
                         status="online", extra_extra=None):
            pnl = (eq - base_eq - cap_adj) \
                if (eq is not None and base_eq is not None) else None
            payload = {
                "venue": "lighter_live", "style": S.style, "family": True,
                "strategy": "SwingDipV1 (live slot swap 13-Aug)",
                "max_open": S.max_open,
                "cap_usd": rails.max_notional,
                # [2026-08-15 (mz)] the row's clip folds in live.clip_scale —
                # the actual stake is clip * scale, and a reader sizing risk
                # off the row was shown the unscaled number (correct only
                # while the board holds the lever at 1.0). Same clamped read
                # as the entry path; fail-open 1.0 keeps a dark rail honest.
                "clip_usd": (round((clip_usd(eq) or 0.0) * _clip_scale_now(),
                             2) if eq else None),
                "held": {c: (meta.get(c) or {}).get("tag")
                         for c in live_pos},
                "policy": _policy(),
                # [(lw) FROM BIRTH] every gate that can stop this book,
                # readable on the row — absence of a veto and a gate that
                # stopped gating must never be the same byte-string.
                "entry_vetoes": {
                    "locked_until": (iso(datetime.fromtimestamp(
                        locked_until, tz=timezone.utc))
                        if locked_until else None),
                    "fleet_long_veto": fleet_long_veto,
                    "brain_gated": brain_gated_tags,
                    "coin_veto": {c: coin_vetoed[c]
                                  for c in sorted(coin_vetoed)},
                    "live_clip_scale": live_scale,
                },
                "capital_adjust": round(cap_adj, 2),
                "initial_equity": base_eq,
                # [2026-08-16 (no)] THE VENUE'S OWN MARGIN TRUTH. Until now
                # "what leverage is this book at, and how close is it to a
                # liquidation?" could only be ESTIMATED from clip arithmetic
                # (clip x slots / equity) — the venue publishes margin_mode,
                # initial_margin_fraction and liquidation_price on every
                # position and this fleet read none of them. `None` when the
                # venue could not answer: an unreadable margin state must not
                # publish as a confident 1.0x.
                "margin": _margin_block(live_pos),
            }
            payload.update(extra_extra or {})
            try:
                store.publish(
                    BOT_ROW, status=status,
                    equity=(round(eq, 2) if eq is not None else None),
                    pnl_abs=(round(pnl, 2) if pnl is not None else None),
                    pnl_pct=(round(pnl / base_eq, 6)
                             if (pnl is not None and base_eq) else None),
                    open_trades=len(live_pos),
                    closed_trades=st["closed"], wins=st["wins"],
                    losses=st["closed"] - st["wins"],
                    extra=payload)
            except Exception:  # noqa: BLE001
                pass
            try:
                store.snapshot_equity(BOT_ROW, eq, open_trades=len(live_pos))
            except Exception:  # noqa: BLE001
                pass

        def _real_fill(sym, is_ask, fallback, leg, res=None):
            """Fill from the venue's own tape (price, measured, reason);
            decision price labelled UNMEASURED on any failure — never zero
            slippage. Delegates to venues.fills like both live bots."""
            detail = getattr(venue, "last_fill_detail", None)
            if detail is None:
                return fallback, False, "no-venue-method"
            try:
                px, measured, reason = read_fill(
                    detail, sym, is_ask=is_ask, since_ts=time.time() - 180,
                    client_id=(res or {}).get("client_order_index"),
                    tx_hash=(res or {}).get("tx_hash"),
                    settle_ms=(res or {}).get("settle_ms"))
            except Exception as e:  # noqa: BLE001
                return fallback, False, f"caller-error:{type(e).__name__}"
            if px is None:
                _PRINT(f"[avo-live] {sym} {leg} fill UNMEASURED — {reason} "
                       f"(recording decision {fallback:.6g}, slippage NULL)")
                return fallback, False, reason
            return px, measured, reason

        def _book_close(sym, exit_px, measured, why, reason):
            """One close: ledger row (entry/exit px + funding drag + policy
            stamp), protections window, cooldown, stats."""
            m = meta.pop(sym, None) or {}
            entry = float(m.get("entry") or 0.0)
            size = float(m.get("size") or 0.0)
            fund = float(m.get("accrued") or 0.0)
            price_pnl = (exit_px - entry) * size if entry and exit_px else 0.0
            total = price_pnl + fund
            notional = abs(size) * entry if entry else None
            pct = (total / notional) if notional else 0.0
            stats["closed"] += 1
            stats["wins"] += 1 if total > 0 else 0
            was_stop = "stop" in reason
            tf_s = _interval_ms(S.tf) / 1000.0
            closed_win.append({"ts": time.time(), "pnl": total, "pct": pct,
                               "stop": was_stop, "pair": sym})
            cooldown[sym] = time.time() + \
                S.protections.get("cooldown_candles", 1) * tf_s
            _PRINT(f"[avo-live] {iso(t_now)} CLOSE {sym} | price "
                   f"{price_pnl:+.2f} funding {fund:+.2f} [{reason}]"
                   f"{'' if measured else ' (exit UNMEASURED)'}")
            try:
                store.publish_paper_trade(
                    BOT_ROW,
                    trade_id=f"{sym}:{m.get('opened_ts')}",
                    pnl_abs=float(total), pnl_pct=pct, pair=sym,
                    opened_at=datetime.fromtimestamp(
                        float(m.get("opened_ts") or time.time()),
                        tz=timezone.utc).isoformat(),
                    closed_at=t_now.isoformat(),
                    reason=ledger_reason(m.get("tag"), reason),
                    entry_price=entry or None, exit_price=exit_px or None,
                    side="long", shadow=False,
                    extra={"policy": _policy(), "fill_measured": measured,
                           "fill_src": why, "clip": m.get("clip"),
                           # [(so)] I22 receipt: the brain scale this REAL
                           # stake was sized at. `clip` is base x strategy
                           # stake_mult x brain and cannot be decomposed.
                           "brain_mult": m.get("brain_mult")})
            except Exception:  # noqa: BLE001
                pass

        def _policy():
            """The stamp golive_readiness keys eras on — the RULES in force,
            not capacity levers ((jf): capacity is ordinary tuning)."""
            return {"strategy": S.style, "venue": "lighter_live",
                    "stoploss": S.stoploss, "roi": {str(k): v
                                                    for k, v in S.roi.items()},
                    "sides": ["long"], "brain_gate": "row+shadow",
                    "coin_veto": True}

        def _flatten_all(why):
            """Emergency flatten reads the VENUE, not meta — an untracked
            position still holds real risk. None from market_close means the
            venue did NOT close it: keep meta, retry next cycle."""
            for sym in list(pos):
                sz = float((pos.get(sym) or {}).get("size") or 0.0)
                if not sz:
                    continue
                mark_px = marks.fresh_mid(venue, sym) or \
                    float((meta.get(sym) or {}).get("last_px") or 0.0)
                try:
                    res = venue.market_close(sym)
                except Exception as e:  # noqa: BLE001
                    _PRINT(f"[avo-live] {iso(t_now)} flatten {sym}: {e!r}")
                    continue
                if res is None:
                    _PRINT(f"[avo-live] {iso(t_now)} flatten {sym}: venue "
                           f"reports NO position — leaving meta; retry next "
                           f"cycle (not booking a phantom close)")
                    continue
                fpx, meas, src = _real_fill(sym, is_ask=(sz > 0),
                                            fallback=mark_px or 0.0,
                                            leg="exit", res=res)
                _book_close(sym, fpx, meas, src, why)
                pos.pop(sym, None)

        # ---- kill switch: flatten + halt, in-loop ---------------------------
        if rails.kill_check():
            _PRINT(f"[avo-live] {iso(t_now)} KILL SWITCH ARMED — flattening "
                   f"the venue book and halting (no entries)")
            if pos_readable:
                _flatten_all("kill_switch")
            _publish_row(equity, baseline, capital_adjust, pos, stats,
                         status="halted", extra_extra={"kill": True})
            _persist()
            if once:
                return
            time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))
            continue

        # ---- daily-loss rails (pct + absolute, confirm-debounced) ----------
        breach = False
        if equity is not None and day_start_equity:
            breach = (equity <= day_start_equity * (1 - DAILY_LOSS_LIMIT)
                      or rails.daily_loss_hit(day_start_equity, equity))
        if breach and not halted_today:
            confirmed, equity = rails.confirm_daily_loss(
                day_start_equity, equity, DAILY_LOSS_LIMIT,
                venue.account_value)
            if confirmed:
                _PRINT(f"[avo-live] {iso(t_now)} DAILY LOSS LIMIT "
                       f"({equity:.2f} vs day start {day_start_equity:.2f}) "
                       f"— flatten + halt for the day")
                halted_today = True
                # [2026-08-18 (pq)] I4 — never discard a persistence result,
                # least of all a safety rail's. The in-memory latch above now
                # holds the halt for THIS process regardless; this write is
                # what carries it across a restart, so a silent failure means
                # a redeploy resumes trading on a halted day. Retried every
                # cycle by the idempotent flatten block below.
                if store.save_daily_halt(
                        BOT_ROW, cur_day, day_start_equity) is False:
                    _PRINT(f"[avo-live] {iso(t_now)} CRITICAL: daily-halt "
                           f"WRITE FAILED — the halt is held in memory but "
                           f"will NOT survive a restart today", flush=True)
        if halted_today:
            if pos_readable:
                _flatten_all("daily_loss")   # idempotent retry every cycle
            _publish_row(equity, baseline, capital_adjust, pos, stats,
                         status="halted",
                         extra_extra={"halted": True, "day": cur_day,
                                      "flatten_incomplete": bool(pos)})
            _persist_day(day_start_equity, cur_day)
            _persist()
            if once:
                return
            time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))
            continue

        # ---- shared context this cycle -------------------------------------
        try:
            fund = venue.funding_map()
        except Exception:  # noqa: BLE001
            fund = {}
        regime = btc_regime_up(cache)
        tide = btc_tide_up(cache)
        nc_verdicts = noncrypto_regimes() if has_noncrypto else {}
        dt_h = max(0.0, (t0 - float(state.get("last_accrue") or t0)) / 3600.0)

        # L2 fleet reads (restrict-only, fail-open) — this is a directional
        # LONG book, so the fleet long budget + symbol cap bind it like every
        # other long book. The SHADOW drawdown governor is deliberately NOT
        # read: live sizing takes the board's live.clip_scale lever instead.
        fleet_long_veto = False
        fleet_headroom = None
        fleet_symcap = None
        cycle_sym = {}
        try:
            fr = store.load_state("fleet-risk") or {}
            age = (t_now - parse_ts(fr.get("updated"))).total_seconds()
            if 0 <= age <= float(fr.get("ttl_sec") or 900):
                lb = fr.get("long_budget")
                lb = 10 ** 9 if lb is None else int(lb)
                if fr.get("mode") == "enforce":
                    held_longs = int(fr.get("long_positions") or 0)
                    fleet_headroom = max(0, lb - held_longs)
                    fleet_long_veto = held_longs >= lb
                fleet_symcap = symcap_state(fr)
        except Exception:  # noqa: BLE001
            pass

        # [2026-08-16 (nj)] ONE owner for the rule. This site used to re-type
        # the lever name and the clamp, so the entry path and the published
        # `clip_usd` could disagree about which arm steers this book the
        # moment either was edited — a second copy of a rule is a second rule.
        live_scale = _clip_scale_now()

        coin_vetoed = {}
        try:
            vp = store.load_state("coin-vetoes") or {}
            cv = vp.get("coins") or {}
            if isinstance(cv, dict) and cv:
                vage = (t_now - parse_ts(vp.get("updated")
                                         or vp.get("ts"))).total_seconds()
                if 0 <= vage <= float(vp.get("ttl_sec")
                                      or QUALITY_VETO_TTL_S):
                    coin_vetoed = cv
        except Exception:  # noqa: BLE001
            pass

        locked_until = entries_locked(closed_win, t0, baseline)
        brain_gated_tags = []
        cycle_admitted = 0

        # ---- manage venue truth: every held position, every cycle ----------
        managed = set()
        for sym in list(pos) + [s for s in list(meta) if s not in pos]:
            if sym in managed:
                continue
            managed.add(sym)
            vsz = float((pos.get(sym) or {}).get("size") or 0.0)
            m = meta.get(sym) or {}
            if not vsz:
                if m and pos_readable:
                    # meta says held, venue says flat — venue is the record;
                    # reconcile loudly rather than manage a phantom.
                    _PRINT(f"[avo-live] {iso(t_now)} {sym} in meta but NOT on "
                           f"the venue — dropping meta (venue is the record)")
                    meta.pop(sym, None)
                continue
            entry = float(m.get("entry")
                          or (pos.get(sym) or {}).get("entry") or 0.0)
            px = marks.fresh_mid(venue, sym)
            bars = cache.get(sym, S.tf)
            sig = None
            if bars and bars.get("t"):
                sig_ts = bars["t"][-1]
                if last_sig_ts.get(sym) != sig_ts:
                    sig = S.signals(bars, {"btc_regime_up": regime,
                                           **({"btc_tide_up": tide}
                                              if MOMO_TIDE_GATE else {})})
                    last_sig_ts[sym] = sig_ts
            if px:
                m.pop("no_px_since", None)
                m["last_px"] = px
                rate = (fund.get(sym) or {}).get("rate")
                if rate is not None and dt_h:
                    # ledger-side funding drag (long pays a positive rate);
                    # EQUITY takes the real charge from the venue itself.
                    m["accrued"] = float(m.get("accrued") or 0.0) - (
                        funding_basis.to_hourly(rate, "lighter")
                        * abs(vsz) * px * dt_h)
                m.setdefault("size", vsz)
                m.setdefault("entry", entry)
                meta[sym] = m
            else:
                first = m.get("no_px_since")
                if not isinstance(first, (int, float)):
                    m["no_px_since"] = t0
                    meta[sym] = m
                elif (t0 - first) / 3600.0 >= DELIST_GIVEUP_H:
                    try:
                        res = venue.market_close(sym)
                    except Exception as e:  # noqa: BLE001
                        _PRINT(f"[avo-live] {iso(t_now)} delist close {sym}: "
                               f"{e!r}")
                        continue
                    if res is not None:
                        zpx = float(m.get("last_px") or entry or 0.0)
                        _book_close(sym, zpx, False, "delist-give-up",
                                    "delisted")
                        pos.pop(sym, None)
                continue

            if not entry or not px:
                continue
            profit = (px - entry) / entry
            age_min = (t0 - float(m.get("opened_ts") or t0)) / 60.0
            reason = None
            if profit <= S.stoploss:
                reason = "stop_loss"
            if not reason and roi_exit_due(age_min, profit):
                reason = "roi"
            if not reason and sig and sig.get("exit"):
                reason = sig.get("exit_reason", "exit_signal")
            if reason:
                try:
                    res = venue.market_close(sym)
                except Exception as e:  # noqa: BLE001
                    _PRINT(f"[avo-live] {iso(t_now)} close {sym} failed: "
                           f"{e!r} — position keeps its manager")
                    continue
                if res is None:
                    _PRINT(f"[avo-live] {iso(t_now)} close {sym}: venue "
                           f"reports NO position — reconciling meta")
                    meta.pop(sym, None)
                    continue
                fpx, meas, src = _real_fill(sym, is_ask=True, fallback=px,
                                            leg="exit", res=res)
                try:
                    store.publish_venue_order(
                        BOT_ROW, venue="lighter", shadow=False, coin=sym,
                        side="sell", size=abs(vsz), px_decision=px,
                        px_fill=fpx,
                        slippage_bps=((px - fpx) / px * -1e4
                                      if meas and px else None),
                        raw={"leg": "close", "reason": reason,
                             "measured": meas, "fill_src": src})
                except Exception:  # noqa: BLE001
                    pass
                _book_close(sym, fpx, meas, src, reason)
                pos.pop(sym, None)

        # ---- entries (new candle only, every gate visible) ------------------
        clip = clip_usd(equity)
        if clip is not None:
            clip = clip * live_scale
        # [2026-08-18 (pq)] `not halt_blind` — when the daily-halt read failed
        # we do not know whether this book is halted, and "unknown" must not
        # buy. Entries only; the exit/flatten paths above already ran, because
        # a book must always be able to CLOSE (the Farmer's :2688 rule).
        entries_ok = (pos_readable and equity is not None
                      and not halt_blind
                      and clip is not None and clip >= MIN_CLIP_USD
                      and t0 >= locked_until)
        if entries_ok:
            for sym in universe:
                if len(pos) >= S.max_open:
                    break
                if sym in pos or sym in meta:
                    continue
                if t0 < cooldown.get(sym, 0.0):
                    continue
                bars = cache.get(sym, S.tf)
                if not bars or not bars.get("t"):
                    continue
                sig_ts = bars["t"][-1]
                if last_sig_ts.get(sym) == sig_ts:
                    continue                      # candle already acted on
                r_up, t_up = regime_inputs_for(sym, regime, tide, nc_verdicts)
                extra = {"btc_regime_up": r_up}
                if MOMO_TIDE_GATE:
                    extra["btc_tide_up"] = t_up
                sig = S.signals(bars, extra)
                last_sig_ts[sym] = sig_ts
                if not sig or not sig.get("enter"):
                    continue
                px = marks.fresh_mid(venue, sym)
                if not px:
                    continue
                if noncrypto_entry_blocked(sym, r_up):
                    continue                      # fail-closed per-asset gate
                if fleet_long_veto:
                    continue
                if fleet_headroom is not None and \
                        cycle_admitted >= fleet_headroom:
                    continue
                if symcap_blocked(fleet_symcap, sym, cycle_sym):
                    continue
                if sym.split("/")[0] in coin_vetoed or sym in coin_vetoed:
                    _PRINT(f"[avo-live] {iso(t_now)} {sym} entry SKIPPED — "
                           f"coin veto: {coin_vetoed.get(sym) or coin_vetoed.get(sym.split('/')[0])}")
                    continue
                tag = sig["enter"]
                gated = False
                for gate_row in (BOT_ROW, SHADOW_ROW):
                    if brain_entry_gated(gate_row, tag):
                        gated = True
                if gated:
                    brain_gated_tags.append(f"{sym}:{ledger_tag(tag)}")
                    continue
                stake = clip * S.stake_mult(tag, bars)
                # [2026-08-20 (so)] ...and the brain's per-tag scale on top,
                # across BOTH rows — the same pair, the same `ledger_tag`
                # identity and the same fail-safe as the regime gate above, so
                # a gate and a size can never disagree about which bucket this
                # trade is in. Applied BEFORE the min-clip floor and before the
                # notional rail on purpose: a reduced stake that falls under
                # MIN_CLIP_USD should not be sent at all, and an increased one
                # must be admitted against the cap it will actually fill.
                stake, bmult = brain_clip_for((BOT_ROW, SHADOW_ROW), tag, stake)
                if stake < MIN_CLIP_USD:
                    continue
                open_ntl = open_notional(pos, meta, len(pos), stake)
                if not rails.notional_ok(open_ntl, stake):
                    _PRINT(f"[avo-live] {iso(t_now)} {sym} NOTIONAL_CAP_SKIP "
                           f"(deployed ${open_ntl:.2f} + ${stake:.2f} > cap "
                           f"${rails.max_notional})")
                    continue
                size = round(stake / px, 6)
                if size <= 0:
                    continue
                try:
                    res = venue.market_open(sym, True, size)
                except Exception as e:  # noqa: BLE001
                    _PRINT(f"[avo-live] {iso(t_now)} open {sym} failed: {e!r}")
                    continue
                fpx, meas, src = _real_fill(sym, is_ask=False, fallback=px,
                                            leg="entry", res=res)
                try:
                    store.publish_venue_order(
                        BOT_ROW, venue="lighter", shadow=False, coin=sym,
                        side="buy", size=size, px_decision=px, px_fill=fpx,
                        slippage_bps=((fpx - px) / px * 1e4
                                      if meas and px else None),
                        raw={"leg": "open", "tag": tag, "clip": stake,
                             "measured": meas, "fill_src": src})
                except Exception:  # noqa: BLE001
                    pass
                meta[sym] = {"entry": fpx or px, "opened_ts": t0, "tag": tag,
                             "accrued": 0.0, "size": size,
                             # [(so)] I22 receipt, carried on the durable
                             # position record so it survives a restart and
                             # reaches the close row.
                             "brain_mult": round(bmult, 4),
                             "clip": round(stake, 2), "last_px": px}
                pos[sym] = {"size": size, "entry": fpx or px}
                cycle_admitted += 1
                base = sym.split("/")[0]
                cycle_sym[base] = cycle_sym.get(base, 0) + 1
                _PRINT(f"[avo-live] {iso(t_now)} OPEN {sym} long "
                       f"${stake:.2f} @ {fpx or px:.6g} [{tag}]"
                       f"{'' if bmult == 1.0 else f' brain {bmult:.2f}x'}"
                       f"{'' if meas else ' (entry UNMEASURED)'}")

        # ---- publish + persist ---------------------------------------------
        _publish_row(equity, baseline, capital_adjust, pos, stats)
        _persist_day(day_start_equity, cur_day)
        _persist()
        _PRINT(f"[avo-live] {iso(t_now)} equity "
               f"{'?' if equity is None else f'{equity:.2f}'} open "
               f"{len(pos)}/{S.max_open} closed {stats['closed']} "
               f"({stats['wins']}W/{stats['closed'] - stats['wins']}L) "
               f"clip=${0 if clip is None else clip:.2f} "
               f"locked={'yes' if t0 < locked_until else 'no'}", flush=True)

        if once:
            return
        time.sleep(max(1.0, LOOP_SECONDS - (time.time() - t0)))


def _supervised():
    """A crash marks the row ERROR instead of going quietly stale — the row
    must say WHY it stopped (taker/family shared pattern)."""
    try:
        main()
    except SystemExit:
        raise
    except BaseException as e:
        try:
            store.set_status(BOT_ROW, "error")
        except Exception:  # noqa: BLE001
            pass
        _PRINT(f"[avo-live] CRASH: {e!r}", flush=True)
        raise


# --------------------------------------------------------------------------
# Offline selftest — drives the REAL main() one cycle against a stub venue
# and asserts on what it PUBLISHED and SENT ((lh): behaviour, not source).

def _selftest():
    import lighter_family_bot as fam

    print("Running Avo LIVE self-test (stub venue)...\n")

    # The single most load-bearing fact: the strategy object IS the family
    # registry's instance — identity, not equality ((hj): pin re-use by
    # identity, a name check stays green against a hand-rolled copy).
    assert S is next(x for x in fam.STRATEGIES if x.bot == BOT), \
        "S must BE lighter_family_bot's configured instance"
    assert S.max_open == 4 and abs(S.stoploss - (-0.10)) < 1e-9

    captured = {"paper": [], "orders": [], "state": {}, "published": [],
                "halts": []}
    _real = {k: getattr(store, k) for k in
             ("publish_paper_trade", "publish_venue_order", "save_state",
              "load_state", "load_state_checked", "publish",
              "save_daily_halt", "load_daily_halt", "heartbeat",
              "claim_writer", "snapshot_equity", "set_status",
              "fetch_paper_aggregate", "service_name")}
    store.heartbeat = lambda bot: None
    store.claim_writer = lambda bot, now=None: (True, None)
    store.snapshot_equity = lambda bot, eq, open_trades=None, realized=None: True
    store.publish_paper_trade = lambda bot, **kw: captured["paper"].append((bot, kw))
    store.publish_venue_order = lambda bot, **kw: captured["orders"].append((bot, kw))
    store.publish = lambda bot, **kw: captured["published"].append((bot, kw))
    store.save_state = lambda k, v: captured["state"].__setitem__(k, v) or True
    store.load_state = lambda k: captured["state"].get(k)
    store.load_state_checked = lambda k: (True, captured["state"].get(k))
    store.save_daily_halt = lambda bot, day, eq=None: captured["halts"].append((bot, day))
    store.load_daily_halt = lambda bot, day: None
    store.set_status = lambda bot, st: None
    store.fetch_paper_aggregate = lambda bot: None
    store.service_name = lambda: "selftest"
    os.environ["DATABASE_URL"] = "postgres://selftest"     # engage seed path

    BARS = 240

    def _mk_bars(shape):
        """4h bars: 'dip' = uptrend + oversold last candle (SwingDip enter);
        'flat' = no signal; 'rally' = exit signal (rsi>65 near range top)."""
        t = list(range(BARS))
        if shape == "dip":
            c = [100 + i * 0.5 for i in range(BARS - 10)]
            c += [c[-1] - i * 6.0 for i in range(1, 11)]      # hard dip
        elif shape == "rally":
            c = [100 + i * 0.2 for i in range(BARS - 30)]
            c += [c[-1] + i * 2.5 for i in range(1, 31)]      # rip to highs
        else:
            c = [100.0] * BARS
        h = [x * 1.01 for x in c]
        l = [x * 0.99 for x in c]
        v = [1.0] * BARS
        return {"t": t, "o": c, "h": h, "l": l, "c": c, "v": v}

    class _StubVenue:
        def __init__(self, equity=62.80, pos=None, bars_shape="dip"):
            self._equity = equity
            self.pos = dict(pos or {})
            self.opens, self.closes = [], []
            self.bars_shape = bars_shape
            self.fail_close = set()

        def supports(self, coin):
            return coin in ("BTC", "ETH", "SPY")

        def account_value(self):
            return self._equity

        def pop_capital_moves(self):
            return []

        def positions(self):
            return dict(self.pos)

        def funding_map(self):
            return {}

        def candles(self, coin, interval, start_ms, end_ms):
            return []                       # CandleCache is stubbed below

        def market_open(self, coin, is_long, size):
            self.opens.append((coin, is_long, size))
            self.pos[coin] = {"size": size, "entry": 100.0}
            return {"client_order_index": 7}

        def market_close(self, coin):
            if coin in self.fail_close:
                raise RuntimeError("stub close failure")
            if coin not in self.pos:
                return None
            self.closes.append(coin)
            self.pos.pop(coin, None)
            return {"client_order_index": 8}

    class _StubRails:
        def __init__(self, cap=63.0, killed=False):
            self.live = True
            self.max_notional = cap
            self._killed = killed

        def kill_check(self):
            return self._killed

        def daily_loss_hit(self, ds, eq):
            return False

        def confirm_daily_loss(self, ds, eq, lim, rd, delay_s=0):
            return True, eq

        def notional_ok(self, open_ntl, add):
            return (open_ntl + add) <= self.max_notional + 1e-9

    # Patch the module's candle/mark surface: CandleCache.get -> shaped bars;
    # marks.fresh_mid -> last close. Regime/oracle reads -> neutral.
    g = globals()
    _saved = {n: g[n] for n in ("btc_regime_up", "btc_tide_up",
                                "noncrypto_regimes")}
    bars_box = {"shape": "dip", "px": None}

    class _StubCache:
        def __init__(self, venue):
            pass

        def get(self, coin, tf):
            return _mk_bars(bars_box["shape"])

    _saved_cache, _saved_marks = g["CandleCache"], marks.fresh_mid
    g["CandleCache"] = _StubCache
    g["btc_regime_up"] = lambda cache: True
    g["btc_tide_up"] = lambda cache: True
    g["noncrypto_regimes"] = lambda: {}
    marks.fresh_mid = lambda venue, coin: (
        bars_box["px"] or _mk_bars(bars_box["shape"])["c"][-1])

    def run(venue, rails):
        main(_ctx={"venue": venue, "rails": rails}, once=True)

    try:
        # ---- 1) identity guard: wrong/unset AVO_VENUE refuses -------------
        for bad in ("", "lighter_shadow", "hl_paper"):
            os.environ["AVO_VENUE"] = bad
            try:
                main(once=True)
                raise AssertionError(f"AVO_VENUE={bad!r} must refuse")
            except SystemExit as e:
                assert "lighter_live" in str(e)
        os.environ.pop("AVO_VENUE", None)

        # ---- 2) entry: sized to the BALANCE, order sent, gates published ---
        v, r = _StubVenue(equity=62.80), _StubRails(cap=63.0)
        run(v, r)
        assert len(v.opens) >= 1, "dip signal on live equity must open"
        coin, is_long, size = v.opens[0]
        assert is_long is True
        stake = size * _mk_bars("dip")["c"][-1]
        assert abs(stake - 62.80 / 4) < 1.0, \
            f"clip must be equity/max_open (~15.70), got {stake:.2f}"
        _pub = captured["published"][-1][1]
        ev = _pub["extra"]["entry_vetoes"]
        assert ev["coin_veto"] == {} and ev["fleet_long_veto"] is False
        assert _pub["extra"]["policy"]["strategy"] == S.style
        assert _pub["extra"]["initial_equity"] == 62.80
        _ord = captured["orders"][0][1]
        assert _ord["shadow"] is False and _ord["side"] == "buy"

        # ---- 3) notional cap is SENIOR: tiny cap -> nothing sent ----------
        captured["state"].clear()
        captured["published"].clear()
        v, r = _StubVenue(equity=62.80), _StubRails(cap=10.0)
        run(v, r)
        assert v.opens == [], f"cap-breaching entry sent: {v.opens}"

        # ---- 4) stop-loss closes through the VENUE + ledger row correct ---
        captured["state"].clear()
        captured["paper"].clear()
        bars_box["shape"] = "flat"
        # -12% on the POSITION (px 88 vs entry 100) while the DAY is only
        # -4.5% (equity 60 vs day-start 62.80): isolates the per-position
        # stop from the daily rail, which runs FIRST by design — the
        # fixture's first draft used equity 55 and correctly got
        # `_daily_loss` instead, which is the ordering working, not a bug.
        bars_box["px"] = 88.0
        v = _StubVenue(equity=60.0,
                       pos={"BTC": {"size": 0.15, "entry": 100.0}})
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80,
            "meta": {"BTC": {"entry": 100.0, "opened_ts": time.time() - 3600,
                             "tag": "dip_in_uptrend", "size": 0.15,
                             "accrued": 0.0}},
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        run(v, _StubRails())
        assert v.closes == ["BTC"], f"stop must close via venue: {v.closes}"
        _p = captured["paper"][-1][1]
        assert _p["reason"] == "long-dip-in-uptrend_stop_loss", _p["reason"]
        assert _p["side"] == "long" and _p["extra"]["policy"]["venue"] == \
            "lighter_live"
        assert _p["entry_price"] == 100.0 and _p["exit_price"] is not None
        assert _p["pnl_abs"] < 0

        # ---- 5) ROI ladder: 14d-old position at small profit exits 'roi' --
        captured["state"].clear()
        captured["paper"].clear()
        bars_box["px"] = 101.0                      # +1% >= roi[20160]=0.0
        v = _StubVenue(equity=64.0,
                       pos={"BTC": {"size": 0.15, "entry": 100.0}})
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80,
            "meta": {"BTC": {"entry": 100.0,
                             "opened_ts": time.time() - 20200 * 60,
                             "tag": "dip_in_uptrend", "size": 0.15,
                             "accrued": 0.0}},
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        run(v, _StubRails())
        assert v.closes == ["BTC"]
        assert captured["paper"][-1][1]["reason"] == \
            "long-dip-in-uptrend_roi", captured["paper"][-1][1]["reason"]

        # ---- 6) kill switch flattens the venue book + halts ---------------
        captured["state"].clear()
        captured["published"].clear()
        bars_box["px"] = 100.0
        v = _StubVenue(equity=60.0,
                       pos={"ETH": {"size": 0.1, "entry": 100.0}})
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80,
            "meta": {"ETH": {"entry": 100.0, "opened_ts": time.time() - 60,
                             "tag": "dip_in_uptrend", "size": 0.1}},
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        run(v, _StubRails(killed=True))
        assert v.closes == ["ETH"], "kill switch must flatten"
        assert captured["published"][-1][1]["status"] == "halted"
        assert v.opens == []

        # ---- 7) seed guard: failed state read -> no trading ----------------
        captured["state"].clear()
        store.load_state_checked = lambda k: (False, None)
        v = _StubVenue(equity=62.80)
        bars_box["shape"] = "dip"
        run(v, _StubRails())
        assert v.opens == [] and v.closes == [], \
            "un-restored book must not trade"
        store.load_state_checked = lambda k: (True, captured["state"].get(k))

        # ---- 8) claim lost -> standby key, no row publish ------------------
        captured["state"].clear()
        captured["published"].clear()
        store.claim_writer = lambda bot, now=None: (False, "other-svc (r2)")
        run(_StubVenue(equity=62.80), _StubRails())
        assert captured["published"] == [], "loser must not publish the row"
        sb = captured["state"].get(BOT_ROW + ":standby")
        assert sb and sb["duplicate_writer"] == "other-svc (r2)"
        store.claim_writer = lambda bot, now=None: (True, None)

        # ---- 9) protections: 2 recent stops lock entries, and the row
        #         SAYS so ((lw) from birth) --------------------------------
        captured["state"].clear()
        captured["published"].clear()
        _now = time.time()
        v = _StubVenue(equity=62.80)
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80,
            "closed": [{"ts": _now - 60, "pnl": -1.5, "pct": -0.1,
                        "stop": True, "pair": "BTC"},
                       {"ts": _now - 120, "pnl": -1.5, "pct": -0.1,
                        "stop": True, "pair": "ETH"}],
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        run(v, _StubRails())
        assert v.opens == [], "slguard (2 stops) must lock entries"
        assert captured["published"][-1][1]["extra"]["entry_vetoes"][
            "locked_until"] is not None, \
            "the lock must be PUBLISHED, not only enforced"

        # ---- 10) unreadable positions: no orders either way ----------------
        captured["state"].clear()

        class _Blind(_StubVenue):
            def positions(self):
                raise RuntimeError("stub: unreadable")

        v = _Blind(equity=62.80)
        run(v, _StubRails())
        assert v.opens == [] and v.closes == [], "never trade blind"

        # ---- 11) venue truth: meta-only phantom is reconciled, not closed -
        captured["state"].clear()
        captured["paper"].clear()
        v = _StubVenue(equity=62.80, pos={})
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80,
            "meta": {"BTC": {"entry": 100.0, "opened_ts": time.time() - 60,
                             "tag": "dip_in_uptrend", "size": 0.15}},
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        bars_box["shape"] = "flat"
        run(v, _StubRails())
        assert captured["paper"] == [], "phantom close must not book"
        _st = captured["state"][STATE_KEY]
        assert "BTC" not in (_st.get("meta") or {}), \
            "meta phantom must reconcile away"

        # ---- 12) a capital move keeps the daily-loss anchor NET of it ------
        # [14-Aug (mi)] This path had NO fixture: the stub's pop_capital_moves
        # returned [] in every case above, so the rail's capital-adjust arm was
        # unexercised and a mutation there survived silently — on a real-money
        # book. A same-day DEPOSIT must move day_start by the SAME amount (else
        # raw equity rises, day_start does not, and the rail cannot fire) and
        # must never read as profit.
        captured["state"].clear()
        captured["published"].clear()
        bars_box["shape"] = "flat"
        bars_box["px"] = 100.0

        class _DepositVenue(_StubVenue):
            def __init__(self, **kw):
                super().__init__(**kw)
                self._moves = [{"delta": 20.0}]

            def pop_capital_moves(self):
                m, self._moves = self._moves, []
                return m

        v = _DepositVenue(equity=82.80)       # 62.80 book + a $20 deposit
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80, "meta": {}, "closed": [],
            "day_start": {"day": now().date().isoformat(), "equity": 62.80}}
        run(v, _StubRails())
        _st = captured["state"][STATE_KEY]
        assert abs(_st["day_start"]["equity"] - 82.80) < 1e-9, \
            ("day-start must shift with the capital move (net-of-capital "
             f"rail), got {_st['day_start']['equity']}")
        assert abs(_st["capital_adjust"]["total"] - 20.0) < 1e-9, \
            f"capital_adjust must carry the move: {_st['capital_adjust']}"
        _pub = captured["published"][-1][1]
        assert abs(_pub["pnl_abs"]) < 0.01, \
            f"a deposit must not read as profit, got pnl_abs={_pub['pnl_abs']}"

        # ---- 13) the daily halt fails CLOSED on an unreadable halt --------
        # [18-Aug (pq)] `halted_today` was re-derived every cycle from
        # `bool(store.load_daily_halt(...))`, and that call returns None for
        # BOTH "not halted" and "the read failed" — so one Postgres blip
        # re-admitted entries on a day this real-money book had already
        # halted. Two properties, and the second is the fix:
        #   (a) a stored halt still halts (regression on the read itself);
        #   (b) an UNREADABLE halt opens nothing, while exits still run.
        # Only the ':halt' key fails here — the main state read must SUCCEED,
        # or the (7) seed guard would block trading for a different reason and
        # this test would pass vacuously ((hj): a fixture that encodes the bug).
        _sc = store.load_state_checked

        def _halt_blind_read(k):
            return (False, None) if k.endswith(":halt") else (True, captured["state"].get(k))

        # (a) stored halt -> halted, no entries
        captured["state"].clear()
        captured["published"].clear()
        _today = now().date().isoformat()
        captured["state"][BOT_ROW + ":halt"] = {
            "halted_date": _today, "day_start_equity": 62.80}
        bars_box["shape"] = "dip"
        v = _StubVenue(equity=62.80)
        run(v, _StubRails())
        assert v.opens == [], "a stored halt must block entries"
        assert captured["published"][-1][1]["status"] == "halted", \
            "a stored halt must publish status=halted"

        # (b) halt read FAILS -> no NEW entries, and the exit path still runs
        captured["state"].clear()
        captured["published"].clear()
        captured["state"][STATE_KEY] = {
            "initial_equity": 62.80, "meta": {}, "closed": [],
            "day_start": {"day": _today, "equity": 62.80}}
        store.load_state_checked = _halt_blind_read
        try:
            bars_box["shape"] = "dip"          # a signal that WOULD enter
            v = _StubVenue(equity=62.80)
            run(v, _StubRails())
            assert v.opens == [], (
                "an UNREADABLE daily-halt must block NEW entries — 'I could "
                "not find out' is not 'not halted'")

            # exits are NEVER blocked by halt-blindness: a held position that
            # hits its stop must still close, or the fix would trap real money
            captured["state"][STATE_KEY] = {
                "initial_equity": 62.80,
                "meta": {"ETH": {"entry": 100.0, "opened_ts": 0,
                                 "tag": "swing-dip-4h"}},
                "closed": [],
                "day_start": {"day": _today, "equity": 62.80}}
            bars_box["shape"] = "flat"
            bars_box["px"] = 50.0              # -50%: through the -10% stop
            v = _StubVenue(equity=62.80, pos={"ETH": {"size": 0.2}})
            run(v, _StubRails())
            assert "ETH" in v.closes, \
                "halt-blindness must never block an EXIT (stop-loss)"
        finally:
            store.load_state_checked = _sc
            bars_box["px"] = 100.0

        print("\nAll Avo LIVE self-tests passed:")
        print("  1 identity guard: only AVO_VENUE=lighter_live boots")
        print("  2 entry sized to the BALANCE (equity/slots), gates on the row")
        print("  3 notional cap is senior — cap-breaching entry never sends")
        print("  4 stop-loss closes via the venue; ledger row has px + policy")
        print("  5 ROI ladder exits (family-identical rule)")
        print("  6 kill switch flattens the venue book + halts")
        print("  7 seed guard: a failed state read trades nothing")
        print("  8 claim lost -> standby key, no row publish")
        print("  9 protections lock entries AND the row says so")
        print(" 10 unreadable positions: never trade blind")
        print(" 11 venue truth: meta phantoms reconcile, never book closes")
        print(" 12 a capital move shifts the day anchor, never reads as P&L")
        print(" 13 an unreadable daily-halt blocks ENTRIES, never EXITS")
    finally:
        for k, fn in _real.items():
            setattr(store, k, fn)
        for n, fn in _saved.items():
            g[n] = fn
        g["CandleCache"] = _saved_cache
        marks.fresh_mid = _saved_marks
        os.environ.pop("AVO_VENUE", None)
        os.environ.pop("DATABASE_URL", None)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
    elif a.once:
        main(once=True)
    else:
        _supervised()
