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
import fleet_bus as _bus            # [(su)] the ONE owner of the basket math
import fleet_tuning as tuning
from lighter_family_bot import (
    STRATEGIES, CandleCache, COINS, NONCRYPTO_UNIVERSE,
    regime_inputs_for, btc_regime_up, btc_tide_up, noncrypto_regimes,
    noncrypto_entry_blocked, brain_entry_gated, brain_clip_for,
    ledger_reason, ledger_tag,
    symcap_state, symcap_blocked, _interval_ms, MOMO_TIDE_GATE,
    NONCRYPTO_EFFECTIVE,
    # [(th)] the control arm's ONE owner (draw/settle/publish) + the throttle
    # carrier class the entry_rank stamp keys on — imported, never re-typed:
    # these are the numbers a go-live verdict is judged on.
    DayTraderGated, control_draw, control_settle, control_block,
    # [(ti)] the ONE policy-stamp builder, shared with the shadow host so
    # judge v2's parity precheck compares like with like.
    policy_stamp,
    # [2026-08-26] the ONE census owner for a no-entry verdict (mum's
    # uptrend_blocked split) — imported, never re-typed ((hj)).
    census_no_entry_why,
    # [2026-08-27] the ONE owner of a close's identity + open stamp — an
    # unknown open must never claim a colliding ':None' id ((hj)).
    close_identity,
)
from venues import marks
from venues.safety import (
    SafetyRails, open_notional, capital_adjusted_day_start, env_prefix)
from venues.fills import read_fill, measured_from_reason

# ---------------------------------------------------------------------------
# [2026-08-22 (sx)] THIS MODULE IS NOW A VARIANT HOST, and 🔮 georgia is the
# second instance. **Eamon, 22-Aug: "get georgia ready to go live on a new sub
# account ill deposit into later today prepared for 5x leverage".**
#
# NOT A NEW FILE — the 🛢️ Garrett rule ((lp)): one proven machine, every success
# instrument inherited free rather than re-implemented at 1,800 lines. What a
# copy would have had to re-earn, and would eventually drift on: claim_writer +
# standby, the latched daily halt, the capital-adjust equity guard, the venue-
# truth reconciler, the notional cap + `cap_slots` census, `diversified_order`,
# the (st) scan census, the MTM equity series, real-fill telemetry, the
# per-asset regime gate and the brain's restrict-only sizing.
#
# THE VARIANT IS THE BOOK, and everything else derives from it:
#   * `S` is still taken from the family REGISTRY by identity, so the live and
#     shadow arms of WHICHEVER book cannot drift;
#   * the whole leverage layer is already written against `S.stoploss` and
#     `S.max_open`, so it re-derives with no edit — georgia's -5% stop makes
#     `vol_target_gross_x(1)` read 3.0x where Avo's -10% reads 1.5x, and an
#     all-slots-stop at 5x costs her 25% against Avo's 50%;
#   * env vars carry a PER-BOOK PREFIX. Every existing `AVO_*` name resolves
#     exactly as before — that is the whole safety property of this change on a
#     real-money book, and `test_variant_host.py` pins it name by name.
#
# The default is unchanged, so a service with no `FAMILY_LIVE_BOOK` set is
# byte-identical to yesterday's Avo.
_BOOKS = {
    # book id -> (env prefix, live clip lever)
    "freqtrade-avo-maria": ("AVO", "live.avo.clip_scale"),
    "freqtrade-georgia": ("GEORGIA", "live.georgia.clip_scale"),
    # [2026-08-25] 👩 mum v2 — Eamon: launch her under her OWN sub-account.
    # Third variant, same machine. Unlike georgia's slot conversion ((ta)/(tb))
    # there is no predecessor to flatten: a FRESH sub-account gets FRESH keys,
    # created in the venue UI and pasted once into the new service — no
    # credential is ever read or moved from an existing service ((ml)).
    # Live-capable is PREP, not activation: nothing points at her row until
    # the service exists with FAMILY_LIVE_BOOK=freqtrade-mum, and the
    # feed-following registries (DECLARED_LIVE et al.) move only when the row
    # publishes venue=lighter_live. Runbook: MUM_GOLIVE_RUNBOOK.md.
    "freqtrade-mum": ("MUM", "live.mum.clip_scale"),
}
# ABSENT means Avo (today's behaviour, unchanged). SET-BUT-BLANK does NOT:
# `FAMILY_LIVE_BOOK=""` on georgia's service is a deploy typo, and silently
# resolving it to Avo would point her process at Avo's row, state key and live
# positions. Caught by `test_variant_host` on the "  " case while writing it.
_raw_book = os.environ.get("FAMILY_LIVE_BOOK")
BOT = "freqtrade-avo-maria" if _raw_book is None else _raw_book.strip()
if BOT not in _BOOKS:
    # An unknown book must not fall back to Avo — that would point georgia's
    # service at Avo's row, its state key and its real positions. Refuse.
    raise SystemExit(
        f"FAMILY_LIVE_BOOK={BOT!r} is not a live-capable book. "
        f"Known: {sorted(_BOOKS)}. A typo must never degrade to another "
        f"book's identity — it would trade the wrong row's positions.")
_PFX, LIVE_CLIP_LEVER = _BOOKS[BOT]

BOT_ROW = BOT + "-lighter"            # the LIVE row (venue_variant admits it)
SHADOW_ROW = BOT + "-lshadow"         # the control arm (family-lighter-shadow)
STATE_KEY = BOT_ROW + ":live"


def _env(name, default):
    """`AVO_X` for Avo, `GEORGIA_X` for georgia — one namespace per book, so
    two live services on one image can never read each other's sizing."""
    return os.environ.get(f"{_PFX}_{name}", default)


#: The configured strategy instance (from the family REGISTRY, `STRATEGIES`) —
#: SwingDip tf=4h stop=-10% for Avo, DayTraderGated tf=15m stop=-5% for georgia;
#: roi ladder, protections — taken from the family bot's OWN registry so the
#: two arms cannot drift. Identity (S is the registry object) is selftested.
S = next(s for s in STRATEGIES if s.bot == BOT)

LOOP_SECONDS = int(_env("LOOP_SECONDS", "300"))

#: [2026-08-27 (us)] TELEMETRY CADENCE — how often the ROW is refreshed from
#: the venue BETWEEN trading passes. **Eamon, 27-Aug: "Make sure the pnl
#: dashboard is actually reflecting the live positions, by the millisecond."**
#:
#: THE MEASUREMENT THAT MOTIVATED IT. The dashboard was never wrong — it was
#: BEHIND, and it said so. End-to-end: the bot polls the venue and publishes
#: every `LOOP_SECONDS` (300), `/pnl.json` holds no cache, and the page carries
#: `meta refresh 30`. Worst case ~330s, median ~165s; measured across 26
#: independent feed reads on 27-Aug the row age ran 3s -> 287s, uniform on
#: [0, 300] — exactly a 300s loop. So a position closed at 11:25 could still be
#: on the card at 11:29, which is what a live venue view disagreeing with the
#: dashboard actually looks like.
#:
#: WHY THIS IS NOT `LOOP_SECONDS`. Stops, ROI and the trail are evaluated ONCE
#: PER TRADING PASS, so shortening the trading loop tightens real exit
#: enforcement on real money — a behaviour change with a measurable price
#: (georgia already records the quantity it would cut, `stop_overshoot.p90_bps`
#: = 26.4) that owes an I19 measurement and would likely reset the (hm) era
#: clock on three live books. **This changes NO trading decision**: the trading
#: pass still runs exactly every `LOOP_SECONDS`; the loop merely stops sleeping
#: through the gap in one block and re-publishes what the venue says instead.
#: No entry, exit, sizing, gate, halt, order or ledger path is reachable from
#: it, and the MTM series that feeds the drawdown bar is explicitly excluded
#: (see `snapshot=` in `_publish_row`).
#:
#: THE COST IS REST, AND IT IS PRICED. A refresh costs `n_positions + 1` calls
#: (one order-book mid per held coin for the risk marks, plus one account
#: read). At 60s across the live trio that is ~11 calls/min of NEW load against
#: ~9/min today — roughly 2x. At 15s it would have been ~44/min, ~5x, and a
#: rate-limited account read on a real-money book can stop an EXIT, which is a
#: far worse failure than a stale card. 60s buys ~5x the freshness for ~2x the
#: load; that is the trade that was taken.
#:
#: FLOORED AT 20s so a typo cannot hammer a real-money venue path, and clamped
#: to `LOOP_SECONDS` so it can never publish more often than it sleeps. Set it
#: to `LOOP_SECONDS` (or higher) to disable the refresh entirely.
TELEMETRY_SECONDS = max(20, min(LOOP_SECONDS,
                                int(_env("TELEMETRY_SECONDS", "60"))))
DAILY_LOSS_LIMIT = float(_env("DAILY_LOSS", "0.10"))
DELIST_GIVEUP_H = float(_env("DELIST_GIVEUP_H", "6"))
#: Below this clip the book is dust — skip entries rather than spray sub-$5
#: orders on a real venue.
MIN_CLIP_USD = float(_env("MIN_CLIP_USD", "5"))
#: Coin-quality veto freshness (mirrors the taker's read of `coin-vetoes`).
QUALITY_VETO_TTL_S = float(_env("QUALITY_VETO_TTL_S", "5400"))

_PRINT = print  # selftest capture point


def iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S+00:00")


def now():
    return datetime.now(timezone.utc)


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


#: [2026-08-21 (sr)] GROSS LEVERAGE. Eamon, 21-Aug: *"increase clip size,
#: whatever we can do to let this fly, training wheels off, lets make it so avo
#: can use leverage to its advantage"* — on the same day he funded the book from
#: $62.93 to $230.70.
#:
#: `clip = equity * GROSS_X / max_open`, so at full occupancy the book's
#: deployed notional is exactly `GROSS_X * equity`. GROSS_X = 1.0 reproduces the
#: previous behaviour byte-for-byte, so this is inert until it is set.
#:
#: WHAT LEVERAGE DOES AND DOES NOT BUY, stated because I22 is emphatic and this
#: is the seventh time the fleet has been asked: it multiplies mean and sd
#: ALIKE, so `t` is INVARIANT — leverage moves NO book closer to the go-live
#: gate, and six prior studies rejected it on exactly that ground. What it does
#: move is DOLLARS and DRAWDOWN, together, in both directions. It is admissible
#: here on the one route I22 leaves open — as the OUTPUT of a drawdown budget
#: rather than an appetite — and the ceiling below is that budget.
#: Parsed defensively AT IMPORT: a bare `float(os.environ[...])` here raises
#: ValueError on a typo and takes the REAL-MONEY book down before `main()` runs
#: — the module-level crash `gross_x()`'s own NaN handling can never reach.
#: Caught by feeding the ladder "abc" while writing this. Unparseable degrades
#: to 1.0 (today's behaviour), never to a guess.
try:
    GROSS_X = float(_env("GROSS_X", "1.0"))
except (TypeError, ValueError):
    GROSS_X = 1.0

#: THE OPERATOR'S CEILING. **Eamon, 21-Aug: "set leverage to 5" / "i want this
#: bot to find a way so leverage can be used" / "no more training wheels".**
#: This is a risk appetite, and risk appetite belongs to the person whose money
#: it is — so it is an operator-set bound, not a number this file invents.
#:
#: **Eamon, 22-Aug: "let avo go up to 10x, and georgia also"** — so the ceiling
#: is 10.0. It is a CEILING, not a setting: `GROSS_X` is what each service runs.
#:
#: What the code owes him is the ARITHMETIC, published rather than argued (see
#: `vol_target_gross_x`, `liq_gap_pct`, `stop_reachable` and the row's
#: `leverage` block). Two of those numbers are new, and one of them changes
#: what 10x means:
#:
#: THE STOP HAS A CEILING OF ITS OWN. Liquidation arrives at `1/G - mmf`; the
#: protective stop fires at `|stoploss|`. Above `G = 1/(|stoploss| + mmf)` the
#: venue liquidates FIRST and the stop is dead code. At the venue's REAL worst
#: maintenance margin — **600bps**, measured 22-Aug across each book's own
#: universe (IWM/MSTR; ADA/DOT/AVAX/LINK), not the 300bps `(sr)` hardcoded:
#:     🙏 Avo   (-10% stop):  stop dead above **6.25x**
#:     🔮 georgia (-5% stop): stop dead above **9.09x**
#: At 10x both books liquidate on a **4.0%** adverse move, on baskets measuring
#: `N_eff` 1.2-1.5 — one bet wearing several names, so that is the central
#: case rather than a tail.
#:
#: This ceiling is deliberately NOT a clamp on that: risk appetite belongs to
#: the person whose money it is, and the row now publishes `stop_reachable`
#: and `stop_dead_above` every loop so the consequence is readable rather than
#: discovered. A dead stop is a fact about the configuration, not an opinion
#: about it.
GROSS_X_MAX = float(_env("GROSS_X_MAX", "10.0"))

#: [2026-08-25 (td)] OPERATOR-ATTESTED MANUAL-TRADE P&L. **Eamon, 25-Aug: "the
#: losses come from manual trades I made (have learned my lesson and will let
#: the bots do their thing lol)".** His manual fills on 🙏 Avo's sub-account
#: flowed straight into the row's `pnl_abs` (equity is venue truth and the
#: guard cannot tell his fills from the bot's), so the row read −$62.79 while
#: the BOT's own record was positive — and the evidence board's restrict
#: backstop cut her clip to 0.75x for losses that were never hers. This env is
#: the attestation: the cumulative net P&L of MANUAL trading on this
#: sub-account, held OUT of the bot's published P&L. A LEVEL, not an
#: increment — idempotent across restarts by construction; update it only if
#: manual trading ever happens again. Published on the row (`manual_pnl_usd`)
#: so the attribution is the record, never a silent adjustment (I23).
#: DECLARED LIMIT: it does NOT reach the daily-loss day anchor — a cumulative
#: level cannot say WHICH day the manual trades hit, so a same-day manual
#: loss can still trip the bot's daily rail (it did, 23/24-Aug). That residue
#: is accepted: the rail failing SAFE on ambiguous losses is the right
#: direction, and the fix is not trading manually on the bot's account.
#: Unparseable/non-finite degrades to 0.0 — never a guess.
try:
    MANUAL_PNL_USD = float(_env("MANUAL_PNL_USD", "0") or 0.0)
except (TypeError, ValueError):
    MANUAL_PNL_USD = 0.0
if MANUAL_PNL_USD != MANUAL_PNL_USD or \
        MANUAL_PNL_USD in (float("inf"), float("-inf")):
    MANUAL_PNL_USD = 0.0

#: The DIVERSIFICATION-EARNED number, published beside the operator's setting
#: rather than clamping it. `N_eff` is the correlation-aware count of
#: INDEPENDENT bets in the held basket (I22: market count is not bet count) —
#: measured 21-Aug on Lighter's own 200d daily tape:
#:   5 crypto majors           rho +0.845  N_eff 1.14  -> 1.60x
#:   what it held that day     rho +0.661  N_eff 1.37  -> 1.76x
#:   one per asset class       rho +0.155  N_eff 3.09  -> 2.64x
#: So diversifying the basket nearly DOUBLES what the same drawdown budget
#: supports — which is the lever worth pulling, and it costs no expectancy
#: because it turns away no signal, it only re-sizes.
#: MSTR belongs with crypto here, not equities: MSTR/BTC measured +0.859.
def worst_mmf(universe):
    """Worst (highest) maintenance-margin fraction across `universe`, or None.

    [2026-08-22 (sy)] THIS WAS A HARDCODED 0.03 AND THE VENUE SAYS 0.06.
    `(sr)` published `liq_gap_pct` off a literal 300bps sourced from a
    hand-check of NVDA/WTI/XCU, and the real worst across the books these two
    live arms actually trade is **600bps** — IWM and MSTR on 🙏 Avo's
    non-crypto set, ADA/DOT/AVAX/LINK once 🔮 georgia's crypto set is included.
    So the row has been publishing a liquidation gap TWICE as far away as it
    is: -17% at 5x where the truth is -14%.

    The data was already on the bus — `(se)` put the venue's whole margin
    surface there and nothing read it. Fail-CLOSED, inheriting
    `fleet_bus.market_margins`' contract verbatim: an unreadable margin returns
    **None**, and a caller that cannot read one must treat the book as if no
    leverage were available. The cost of a wrong default here is a
    liquidation, which is unrecoverable — so absence is never "no limit"."""
    try:
        import fleet_bus
        rows = fleet_bus.market_margins()
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(rows, dict):
        return None
    seen = []
    for sym in universe or ():
        row = rows.get(sym)
        try:
            bps = float((row or {}).get("mmf_bps"))
        except (TypeError, ValueError):
            continue
        if bps > 0:
            seen.append(bps / 10000.0)
    return max(seen) if seen else None


def liq_gap_pct(mmf, gross=None):
    """The signed adverse move that liquidates, or None when mmf is unknown.

    Liquidation when equity falls to maintenance: `1 - G*x = mmf*G`, so the
    move is `x = 1/G - mmf`. Published NEGATIVE (the direction that hurts a
    long book), matching `(sr)`'s convention."""
    if mmf is None:
        return None
    g = gross_x() if gross is None else gross
    if not g or g <= 0:
        return None
    return round(mmf - 1.0 / g, 4)


def stop_reachable(mmf, gross=None):
    """Does the book's own protective stop fire BEFORE the venue liquidates?

    [(sy)] THE QUESTION NOBODY HAD ASKED, and it is not a risk-appetite one —
    above a certain gross the stop is dead code, because liquidation arrives
    first. It has a closed form: the stop is reachable while
    `|stoploss| < 1/G - mmf`, i.e. up to `G = 1 / (|stoploss| + mmf)`.

    At the venue's real 600bps that ceiling is **6.25x for 🙏 Avo** (-10% stop)
    and **9.09x for 🔮 georgia** (-5% stop). Reported, never a gate — it does
    not clamp anything; it makes a dead stop visible instead of silent."""
    if mmf is None:
        return None, None
    sl = abs(float(S.stoploss))
    ceiling = round(1.0 / (sl + mmf), 2)
    g = gross_x() if gross is None else gross
    # [2026-08-25] STRICTLY inside, with a float guard. 👩 mum's -4% stop puts
    # her ceiling at EXACTLY 10.0x, and at that tie `1/10 - 0.06` floats to
    # 0.04000000000000001 — so the bare `<` published `stop_reachable: True`
    # by 1e-17 of headroom. At the tie the stop and liquidation are the SAME
    # price; claiming the stop fires first is the wrong direction for a
    # safety instrument, so the tie reads DEAD.
    return (sl < (1.0 / g - mmf) - 1e-9) if g and g > 0 else None, ceiling


def vol_target_gross_x(n_eff=1.0):
    """Gross that keeps an all-slots-stop inside the 15% go-live drawdown bar,
    credited for measured independence. n_eff=1 (fully correlated) returns the
    unlevered-basket answer, 1.5x."""
    try:
        ne = max(1.0, float(n_eff))
    except (TypeError, ValueError):
        ne = 1.0
    return round(0.15 / (abs(float(S.stoploss)) / (ne ** 0.5)), 4)


def gross_x():
    """The effective gross multiplier. Floors at 1.0 — this lever exists to
    deploy balance, and SHRINKING the clip is the live clip scale's job
    (`_clip_scale_now`), which stays restrict-only and senior."""
    try:
        g = float(GROSS_X)
    except (TypeError, ValueError):
        return 1.0
    if g != g or g in (float("inf"), float("-inf")):   # NaN / inf
        return 1.0
    return max(1.0, min(GROSS_X_MAX, g))


def clip_usd(equity):
    """Per-entry clip sized to the ACTUAL balance: equity * gross_x / slots.
    None when equity is unreadable — a live book does not size off a guess."""
    if equity is None or equity <= 0:
        return None
    return equity * gross_x() / float(S.max_open)


def cap_slots(clip, cap, slots):
    """How many of `slots` the operator's notional cap can still FUND once every
    slot is sized at `clip` — i.e. the steady state, not today's occupancy.

    [2026-08-21 (sr)] A DEPOSIT CAN BUY FEWER BETS, SILENTLY. Eamon added
    $167.76 to 🙏 Avo; equity $62.93 -> $230.70 and `clip = equity/max_open`
    re-sized every FUTURE entry $15.73 -> $57.68, exactly as designed. But
    `FREQTRADE_AVO_MARIA_MAX_NOTIONAL` is a FIXED DOLLAR figure and stayed at
    $200, and admission is `open_notional + add <= cap`: 3 slots x $57.68 =
    $173.02 fits, the 4th needs $230.70 and is refused. The book settles at
    3 of 4 and **$57.68 of the new balance is never deployed**.

    It is invisible three ways, which is why this is published rather than
    merely fixed: (1) `open_trades` reads 3 of a declared `max_open` 4 exactly
    as it does on a quiet day; (2) the refusal is DELAYED — held positions are
    priced at their OWN entry clip ((hl) `open_notional`), so while the three
    legacy $7.68 positions live a 4th entry still fits and the wall only
    arrives as they roll over; (3) a clip-vs-cap mismatch has no natural
    trigger — nothing fires, so nothing is counted. A standing arithmetic
    census is the only shape that can report a constraint that has not bitten
    YET. Same class as the carried `farmer-cap-collapses-slots-under-conviction`
    item, reached from the other direction: there a bigger CLIP collapses
    slots, here a bigger BALANCE does.

    Reported, never enforced — SafetyRails caps are operator-only, so this
    names the constraint and the operator moves it (I8: name the object that
    can be acted on). None when either input is unknown, never a guess.
    """
    try:
        c, k, n = float(clip), float(cap), int(slots)
    except (TypeError, ValueError):
        return None
    if not (c > 0) or not (k > 0) or n <= 0:
        return None
    return max(0, min(n, int(k // c)))


# ---------------------------------------------------------------------------
# [2026-08-21 (sr)] DIVERSIFICATION — Eamon: "diversify and addition is great",
# "i want this bot to find a way so leverage can be used".
#
# THE MEASUREMENT that motivates all of it (Lighter's own 200d daily tape,
# N_eff = n/(1+(n-1)*mean_pairwise_rho) over a 5-position hold):
#     5 crypto majors                rho +0.845  N_eff 1.14
#     QQQ,SPY,NVDA,TSLA,IWM          rho +0.661  N_eff 1.37   <- what it held
#     one per asset class            rho +0.155  N_eff 3.09
# A basket of 3 US index proxies is ~ONE BET. The SAME leverage over a spread
# basket carries far less joint-stop risk, and spreading costs NO expectancy —
# it changes WHICH qualifying signal fills a slot, never whether one is taken.
#
# WHY THE BOOK CONCENTRATED, and it is structural rather than bad luck: the
# entry loop scans `list(COINS) + list(NONCRYPTO_UNIVERSE)` IN LIST ORDER and
# takes the first qualifying signal, so 29 crypto names get first refusal on
# every slot and the diversifiers are last in line by construction. That is
# exactly the (hl) finding on 📊 Index Rider — *"the entry loop iterates SYMBOLS
# in order with incumbents holding slots, it would starve the LAST-listed
# diversifiers and RAISE correlation"* — reaching a second book.
#
# THE FIX IS THE SCAN ORDER, NOT THE ENTRY PATH. Every gate, veto, cap and
# sizing rule below is untouched; only the sequence in which candidates are
# offered changes. That keeps the real-money entry path byte-identical in
# behaviour for any single candidate, which is the whole point.
#
# IT COSTS NOTHING AT THE VENUE: `CandleCache` is one governed fetch per
# (coin, tf) per CLOSED candle shared across books, and the entry loop already
# calls `cache.get` for these symbols, so the correlations ride bars we have.
# [2026-08-22 (su)] THE MATH MOVED TO `fleet_bus`, WHICH IS NOW ITS ONE OWNER.
# 💸 the LIVE Funding Farmer needed exactly this measurement (it holds
# BTC/ETH/SOL/XAU at N_eff 1.389, its crypto leg at 1.11) and a second copy of
# a rule is a second rule ((hj)). `fleet_bus` is COPY'd into both images, so
# both real-money rows now compute independence the same way, once. These names
# stay as thin aliases: the (sr) tests and `diversified_order` below bind them,
# and re-pointing every call site on the same day would be churn, not clarity.
CORR_MIN_OVERLAP = _bus.CORR_MIN_OVERLAP
CORR_LOOKBACK = _bus.CORR_LOOKBACK
_bar_returns = _bus.bar_returns
_pair_corr = _bus.pair_corr
basket_n_eff = _bus.basket_n_eff


def diversified_order(universe, held, rets):
    """`universe` reordered so the candidate that most REDUCES the held
    basket's correlation is offered first.

    FAIL-SAFE IS THE WHOLE CONTRACT: anything unmeasurable keeps its original
    relative position and sorts AFTER the measured ones, and an empty/held-less
    /dark read returns the list unchanged — i.e. exactly today's behaviour. A
    correlation we could not measure must never jump a name up the queue.
    """
    try:
        held = [h for h in (held or []) if rets.get(h)]
        if not held or not universe:
            return list(universe)
        scored = []
        for i, sym in enumerate(universe):
            r = rets.get(sym)
            cs = [c for h in held
                  if (c := _pair_corr(r, rets[h])) is not None] if r else []
            # unmeasured -> (1, original index): after every measured name,
            # original order preserved among themselves.
            scored.append(((0, sum(cs) / len(cs), i) if cs else (1, 0.0, i), sym))
        scored.sort(key=lambda kv: kv[0])
        return [s for _, s in scored]
    except Exception:  # noqa: BLE001 — ordering is an enhancement, never a dependency
        return list(universe)


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
    min(1.0, ...), so this lever can only ever SHRINK Avo's clip. The registry
    cage (hi = 1.0) mirrors this exactly.

    [2026-08-21 (sr)] CORRECTED IN PLACE per I12 — this paragraph used to end
    *"gross notional can never exceed account equity — the book is 1.00x by
    construction and no lever reaches past it"*, and `AVO_GROSS_X` makes that
    FALSE. A safety sentence is a claim about behaviour ((sp)'s lesson), so it
    is restated rather than left to rot:
      * THIS lever is still restrict-only and still cannot reach past 1.0x. That
        half was never about the clip formula; it is the `min(1.0, ...)` clamp.
      * The book is NO LONGER 1.00x by construction. Gross at full occupancy is
        `GROSS_X * equity`, bounded by `GROSS_X_MAX` (a drawdown budget derived
        from this book's own stop and the 15% gate bar — see GROSS_X), and then
        by the operator-only SafetyRails notional cap, which is senior to both
        and is what actually refuses the order."""
    try:
        import fleet_tuning as tuning
        return max(0.25, min(1.0, float(
            tuning.get_lever(LIVE_CLIP_LEVER, 1.0))))
    except Exception:  # noqa: BLE001
        return 1.0


def roi_exit_due(age_min, profit, strategy=None):
    """freqtrade-style ROI ladder, byte-identical to the family Book's rule:
    the rung is the LARGEST minute key <= age, exit when profit >= its bar.
    [2026-08-26] takes the strategy explicitly so the manage_exit_reason seam
    reads the ladder of the book it was HANDED, never the module global S —
    a test driving georgia's ladder must not silently read avo's."""
    roi = (strategy or S).roi
    if not roi:
        return False
    rung = max((k for k in roi if k <= age_min), default=None)
    return rung is not None and profit >= roi[rung]


def manage_exit_reason(strategy, m, px, profit, age_min, sig, bars):
    """The family loop's exit stack, in the family loop's order (stop -> roi
    -> custom_exit -> exit signal), as ONE testable seam. Mutates m["stop_px"]
    (the ratchet HWM lives in durable meta, so a restart cannot lower it).

    [2026-08-26] TWO family semantics this host was missing, both found by
    pairing 🔮 georgia's live ledger against her shadow twin's — the (te)
    class again (the variant host not running the strategy's own policy):

    * THE TRAILING ATR RATCHET. The family runs DayTraderGated's stop as
      `atr_stop_dist` ratcheted from the high-water mark (106 of her 207
      shadow closes exit `trailing_stop_loss`); this host checked only the
      fixed `profit <= stoploss`, so her live arm had NO ratchet — zero
      trailing closes in 51, winners free to round-trip to -5%, and the one
      fixed-stop fill that did fire gapped to -7.17% (DOGE, 22-Aug). Ported
      verbatim; when bars are dark the fixed stop stays as the backstop (a
      deliberate divergence from the family, where bars always exist —
      a DayTrader position must never be stopless).

    * THE trend_breakout VETO on the exit signal. The family vetoes
      `range_top` for breakout entries — a breakout is by construction at the
      top of the range it just left, so the unvetoed signal exits it on the
      first fresh bar. Measured on the live row before this fix: 24 of 51
      closes were `long-trend-breakout_range_top` at 15m median hold, a
      combination the shadow's ledger cannot book at all (0 of 207), mean
      +0.079%/trade where the shadow rides the same tag to roi/trail.
    """
    reason = None
    if isinstance(strategy, DayTraderGated) and bars and bars.get("t"):
        dist = strategy.atr_stop_dist(m.get("tag"), bars, px)
        m["stop_px"] = max(float(m.get("stop_px") or 0.0), px * (1.0 - dist))
        if px <= m["stop_px"]:
            reason = "trailing_stop_loss"
    elif profit <= strategy.stoploss:
        reason = "stop_loss"
    if not reason and roi_exit_due(age_min, profit, strategy):
        reason = "roi"
    if not reason and hasattr(strategy, "custom_exit"):
        reason = strategy.custom_exit(m.get("tag"), age_min, profit)
    if not reason and sig and sig.get("exit") \
            and m.get("tag") != "trend_breakout":
        reason = sig.get("exit_reason", "exit_signal")
    return reason


def scan_census(verdicts, rsi_readings, rsi_bar, universe, held,
                ungraded, entries_shut, last_open_ts, last_close_ts, t_now):
    """WHY DID NOTHING OPEN? — the I18 rule, at the fleet's real-money
    directional row.

    🙏 avo published `open_trades: 3` and nothing else for its entire life, so
    when Eamon asked why it had not traded in days the row could not answer and
    neither could the shadow: `census = True` existed in this fleet exactly
    ONCE, on a $1,000 paper book (👩 mum v2), and never on the row holding real
    money. Everything below is REPORTED — nothing here gates a trade.

    WHAT THE ANSWER TURNED OUT TO BE, measured 22-Aug by driving the shipped
    `SwingDip.signals` over the venue's own 4h tape (65 fires / 15 days across
    23 coins): the book is **held-starved and gate-refused, not signal-
    starved**. 24 of 65 fires landed on the three coins it already holds, and
    12 more on IWM/XCU — non-crypto books the oracle cannot grade (172 and 194
    bars against its 203 floor), which `noncrypto_entry_blocked` refuses
    fail-closed. Both are correct behaviour. Neither was visible.

    `ungraded` is the (om) `gate_drift` shape: names this book will scan and
    can never enter until the oracle has enough history. Absent readings are
    ABSENT, never zero — a fabricated `rsi_min: 0.0` would read as a coin
    sitting AT the bar, the loudest possible signal from no data (I8).
    """
    counts = {}
    for sym in universe:
        counts[verdicts.get(str(sym), "not_evaluated")] = counts.get(
            verdicts.get(str(sym), "not_evaluated"), 0) + 1
    out = {"universe": len(universe), "held": len(held),
           "verdicts": dict(sorted(counts.items(), key=lambda kv: -kv[1]))}
    if entries_shut:
        out["entries_shut"] = entries_shut
    if ungraded:
        out["ungraded"] = sorted(ungraded)
    vals = sorted(v for v in rsi_readings.values()
                  if isinstance(v, (int, float)))
    if vals and rsi_bar:
        out["rsi_bar"] = rsi_bar
        out["rsi_min"] = round(vals[0], 1)
        out["rsi_med"] = round(vals[len(vals) // 2], 1)
        out["rsi_read"] = len(vals)
        out["near_bar"] = sum(1 for v in vals if v < rsi_bar + 8)
    for key, ts in (("idle_open_h", last_open_ts),
                    ("idle_close_h", last_close_ts)):
        if ts:
            out[key] = round(max(0.0, (t_now - float(ts))) / 3600.0, 2)
    return out


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
        mode = _env("VENUE", "").strip()
        if mode != "lighter_live":
            raise SystemExit(
                # [(sx)] the ACTUAL env name for THIS book — I8: a guard whose
                # output is an instruction must name something the operator can
                # find, and `GEORGIA_VENUE` is not `AVO_VENUE`.
                f"{_PFX}_VENUE must be EXACTLY 'lighter_live' (got "
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
            # [(sz)] DERIVED, not typed. This named Avo's cap env verbatim, so
            # under 🔮 georgia the one instruction the operator gets at boot
            # would have sent them to set the WRONG book's cap — I8, on the
            # message a real-money service prints as it refuses to start.
            f"lighter_live requires an explicit per-bot notional cap "
            f"({env_prefix(BOT)}_MAX_NOTIONAL) — refusing to start.")

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
    # [(te)] I22 spend census: the last MEASURED basket n_eff, carried across
    # cycles so the halt paths (which publish before the scan re-measures) can
    # report the last known value instead of nothing. None until first measured.
    spend_n_eff = None

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
        # [(st)] THE CENSUS'S DURABLE HALF. Kept across loops (and restored
        # across restarts) because this book decides on a 4h candle and
        # publishes every 90s: a per-CYCLE census would read "nothing
        # evaluated" on ~159 of every 160 loops, which is exactly the silence
        # it exists to break. `last_open_ts` is a one-element list so the
        # entry loop's closure can write it.
        scan_verdict = {str(k): str(v)
                        for k, v in (state.get("scan_verdict") or {}).items()}
        last_rsi = {str(k): float(v)
                    for k, v in (state.get("last_rsi") or {}).items()
                    if isinstance(v, (int, float))}
        last_open_ts = [float(state.get("last_open_ts") or 0.0)]
        baseline = state.get("initial_equity")
        capital_adjust = float((state.get("capital_adjust") or {}).get("total")
                               or 0.0)
        # [(te)] the arm's own birth instant, persisted — the I22 spend
        # census's days-to-gate FLOOR derives from it ((ks): every ETA a
        # floor). An arm restored without one adopts NOW, which overstates
        # the floor slightly — the fail-closed direction.
        born_ts = float(state.get("born_ts") or 0.0)
        if not born_ts:
            born_ts = t0
            state["born_ts"] = born_ts
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
        # [2026-08-26 (to)] the opt-in equity-scaled cap re-derives every loop
        # from the equity just read — inert unless EQUITY_SCALED_CAP is set on
        # the service; fail-safe on a dark equity read (cap keeps its value).
        rails.equity_scale(equity, gross_x())

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
        brain_expand_refused = brain_floored = 0
        notional_cap_skips = 0
        coin_vetoed = {}
        live_scale = 1.0
        # [(st)] NOT scan_verdict / last_rsi / last_open_ts / closed_win: this
        # block runs AFTER the state restore above, so defaulting them here
        # would blank the restored census (and the close window `entries_locked`
        # reads) on every single cycle. The earliest publish site is below the
        # restore, so they are always bound by the time the helper can run.
        cycle_verdict = {}
        entries_shut = None
        nc_verdicts = {}
        # [(sr)] None, not 1.0 — the halt/kill paths publish before the scan
        # computes these, and "not measured yet" must not read as "one bet".
        held_n_eff = held_rho = None
        # [(th)] durable instruments, living IN the state dict so a restart
        # cannot blank them: the control arm's paired accumulator ((rp) — the
        # number 👩 mum's revival is judged on) and the stop-overshoot record
        # (the quantity every future gross notch must price: G_max assumes
        # fire-at-level, and georgia's DOGE stop filled 217bps past its level
        # — 4.1x mum's entire 53bps liquidation headroom).
        ctrl = state.setdefault(
            "ctrl", {"n": 0, "sum": 0.0, "null_n": 0, "null_sum": 0.0})
        ov = state.setdefault(
            "overshoot", {"n": 0, "unmeasured_n": 0, "vals": []})

        def _persist_day(dse, day):
            state["day_start"] = {"day": day, "equity": dse}

        def _persist():
            state.update({
                "initial_equity": baseline, "meta": meta,
                "closed": closed_win[-200:], "cooldown": cooldown,
                "last_sig_ts": last_sig_ts, "last_accrue": t0,
                # [(st)] the census survives a restart, or every deploy would
                # blank the one instrument that says why the book is quiet.
                "scan_verdict": scan_verdict, "last_rsi": last_rsi,
                "last_open_ts": last_open_ts[0],
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
                         status="online", extra_extra=None, snapshot=True):
            # [(td)] manual trades are held OUT of the bot's P&L — the row
            # grades the BOT's record; equity stays venue truth everywhere
            # else (leverage, margin, drawdown arithmetic all unchanged).
            pnl = (eq - base_eq - cap_adj - MANUAL_PNL_USD) \
                if (eq is not None and base_eq is not None) else None
            # [(th)] CONTRIBUTED capital — the honest pnl_pct denominator:
            # birth equity plus every attested deposit/withdrawal since. Avo's
            # row read −96.9% on the birth-equity basis while the
            # capital-honest figure is −26%, because the $167.76 deposit grew
            # the capital and the old basis never saw it.
            _contrib = (base_eq + cap_adj) if base_eq is not None else None
            # [(th)] the venue margin state, read ONCE and shared by the
            # `margin` block and the headroom verdict below.
            _mstate = _margin_block(live_pos)
            try:
                _hd_ok, _hd_why = rails.headroom_check(
                    _mstate, abs(float(S.stoploss)))
            except Exception:  # noqa: BLE001
                _hd_ok, _hd_why = None, "error"
            _hd_gap = None
            if isinstance(_mstate, dict):
                _near = _mstate.get("nearest_liq")
                if isinstance(_near, dict):
                    try:
                        _d = float(_near.get("dist_frac"))
                        if _d == _d and _d > 0:
                            _hd_gap = round(_d / abs(float(S.stoploss)), 2)
                    except (TypeError, ValueError):
                        pass
            try:
                _open_ntl = open_notional(live_pos, meta, len(live_pos), 0.0)
            except Exception:  # noqa: BLE001
                _open_ntl = None
            # [(sr)] ONE effective clip, read by both `clip_usd` and `cap_slots`
            # — the cap census must describe the clip the row publishes, and a
            # second copy of this expression is how the two drift apart.
            _eff_clip = ((clip_usd(eq) or 0.0) * _clip_scale_now()) if eq else None
            # [(sy)] the venue's real margin surface for THIS book's universe,
            # read once per publish and shared by the three fields below.
            _mmf = worst_mmf(universe)
            _stop_ok, _stop_ceiling = stop_reachable(_mmf)
            payload = {
                "venue": "lighter_live", "style": S.style, "family": True,
                # [2026-08-25] derived from the variant — this was a hardcoded
                # "SwingDipV1 (live slot swap 13-Aug)", and 🔮 georgia's live
                # row published it verbatim while running DayTraderGated (I8:
                # the row must name the thing that is actually running).
                "strategy": f"{type(S).__name__} (variant host)",
                "max_open": S.max_open,
                "cap_usd": rails.max_notional,
                # [(to)] which rule set it: "env" (the operator's floor) or
                # "scaled" (equity x gross x 1.05 outgrew the floor).
                "cap_src": getattr(rails, "cap_src", "env"),
                # [2026-08-15 (mz)] the row's clip folds in live.clip_scale —
                # the actual stake is clip * scale, and a reader sizing risk
                # off the row was shown the unscaled number (correct only
                # while the board holds the lever at 1.0). Same clamped read
                # as the entry path; fail-open 1.0 keeps a dark rail honest.
                "clip_usd": (round(_eff_clip, 2) if _eff_clip else None),
                # [(sr)] how many of `max_open` the CAP can fund once every slot
                # sits at this clip. `cap_slots < max_open` means the operator's
                # fixed-dollar cap — not the signal — is what holds this book
                # below its declared capacity, and it is the ONLY field that
                # says so before the refusal happens. See cap_slots().
                "cap_slots": cap_slots(_eff_clip, rails.max_notional,
                                       S.max_open),
                # [(sr)] the book's gross leverage, PUBLISHED — the effective
                # multiplier and the drawdown-derived ceiling it is clamped to.
                # A book running above 1x must say so on its own row: every
                # downstream grader (maxDD, the allocation claim, the ceiling)
                # reads dollars, and dollars now carry a multiplier that is not
                # visible anywhere else.
                "gross_x": round(gross_x(), 4),
                "gross_x_max": GROSS_X_MAX,
                # [(sr)] THE LEVERAGE BLOCK — published so the operator's
                # setting and the diversification-earned number are readable
                # side by side, every loop, on the row itself. `vol_target` is
                # ADVISORY: it does not clamp `gross_x`, it says what the held
                # basket's measured independence would support. A gap between
                # them is not an error — it is the risk being taken, stated.
                "leverage": {
                    "set": round(gross_x(), 4),
                    "vol_target_at_neff1": vol_target_gross_x(1.0),
                    "vol_target_at_neff3": vol_target_gross_x(3.09),
                    "deployed_at_full": (round(_eff_clip * S.max_open, 2)
                                         if _eff_clip else None),
                    "all_slots_stop_pct": round(gross_x() * abs(float(S.stoploss)), 4),
                    # [(sr)] THE HELD BASKET'S MEASURED INDEPENDENCE. n_eff ~1
                    # means the slots are one bet wearing five names and the
                    # leverage above is riding a single position; n_eff near the
                    # slot count means it is genuinely spread. `vol_target_here`
                    # is what THIS basket's independence would support — the gap
                    # to `set` is the risk being taken, published not argued.
                    "n_eff": (round(held_n_eff, 3) if held_n_eff else None),
                    "basket_rho": (round(held_rho, 3) if held_rho is not None
                                   else None),
                    "vol_target_here": (vol_target_gross_x(held_n_eff)
                                        if held_n_eff else None),
                    # [(sy)] READ FROM THE VENUE, not a literal. The worst
                    # maintenance-margin fraction across the books this
                    # universe actually trades — 600bps, not the 300bps (sr)
                    # hardcoded — off the scout's own margin surface. None
                    # when unreadable: a fabricated liquidation distance on a
                    # levered real-money row is the one number that must never
                    # be guessed.
                    "mmf": (round(_mmf, 4) if _mmf is not None else None),
                    "liq_gap_pct": liq_gap_pct(_mmf),
                    # Does the book's own stop still fire before the venue
                    # liquidates? Above `stop_dead_above` it does not, and the
                    # protective stop is dead code. Reported, never a gate.
                    "stop_reachable": _stop_ok,
                    "stop_dead_above": _stop_ceiling,
                    # [(th)] THE RUIN GATE'S VERDICT, published — the fleet's
                    # only liquidation-aware gate guarded zero live dollars
                    # after the (ta) retirement of its sole caller, while the
                    # levered trio published telemetry nothing refused on.
                    # VERDICT ONLY, never a gate here: at Eamon's on-record
                    # 9.5x mum's gap is 1.13 stop-widths against the K=4 bar,
                    # so `too_close` is structural at his setting and refusing
                    # on it would re-litigate a decision made on the record.
                    # fleet_immune pages TRANSITIONS into the non-structural
                    # conditions; entry refusal stays Eamon's explicit call.
                    "headroom": {"ok": _hd_ok, "reason": _hd_why,
                                 "gap_stop_widths": _hd_gap},
                    # [(th)] THE DAILY HALT'S GEOMETRY, coupled to the gross —
                    # both rails are gross-BLIND (a fraction of equity and a
                    # fixed $), so at 9.5x the day ends on a ~1.05% adverse
                    # basket move and TWO slot-stops guarantee a halt. The
                    # constant (at full gross) and the live number (at current
                    # deployment) both publish, so neither overstates; whether
                    # the setting is right at this gross is Eamon's env
                    # decision ({PFX}_DAILY_LOSS), informed not argued.
                    "halt": {
                        "daily_loss_frac": DAILY_LOSS_LIMIT,
                        "abs_usd": getattr(rails, "max_daily_loss", None),
                        "basket_move_at_full_gross_pct": round(
                            DAILY_LOSS_LIMIT / gross_x(), 4),
                        "basket_move_now_pct": (
                            round(DAILY_LOSS_LIMIT * eq / _open_ntl, 4)
                            if (eq and _open_ntl) else None),
                        "binding": ("abs" if (
                            day_start_equity
                            and getattr(rails, "max_daily_loss", None)
                            is not None
                            and rails.max_daily_loss
                            < DAILY_LOSS_LIMIT * day_start_equity)
                            else "pct"),
                    },
                },
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
                    # [(sp)] the brain's two REFUSED sizings. `expand_refused`
                    # counts entries where the brain wanted this REAL-MONEY
                    # book bigger and was held at 1.0x (restrict-only, see the
                    # entry site); `floored` counts reduces that would have
                    # fallen under MIN_CLIP_USD and were floored to it instead
                    # of silently skipping the trade. Both are ZERO on a
                    # neutral brain, so a non-zero here always means something
                    # happened.
                    "brain_expand_refused": brain_expand_refused,
                    "brain_floored": brain_floored,
                    # [(sr)] entries the notional cap actually refused this
                    # loop. Zero on a book whose cap has room, so non-zero
                    # always means the cap turned a signal away.
                    "notional_cap_skips": notional_cap_skips,
                    "coin_veto": {c: coin_vetoed[c]
                                  for c in sorted(coin_vetoed)},
                    "live_clip_scale": live_scale,
                },
                "capital_adjust": round(cap_adj, 2),
                # [(td)] the operator's manual-trade attestation, always
                # published — 0.0 must be visibly "none attested", never
                # byte-identical to "the field does not exist" (I18).
                "manual_pnl_usd": round(MANUAL_PNL_USD, 2),
                # [(te)] THE I22 SPEND CENSUS, published every loop —
                # audit_book_spend's first real test was this host's own two
                # variants born after the 20-Aug cutoff. n_eff is the last
                # MEASURED correlation-aware basket count (1.0 for an empty
                # book — zero-to-one bet; never the raw symbol count, which
                # the guard itself rejects as gaming). days_to_gate_obs is a
                # FLOOR ((ks)): the 30d window remaining from the arm's own
                # birth; the close-rate term tightens it once the arm has a
                # rate worth quoting.
                "spend": {
                    "markets_scanned": len(universe),
                    "markets_held": len(live_pos or {}),
                    # unmeasured degrades to 1.0 — "assume ONE bet", the
                    # conservative direction for a leverage census (never
                    # diversification credit that was not measured; the same
                    # degrade the vol target takes).
                    "n_eff": (round(float(held_n_eff), 3)
                              if isinstance(held_n_eff, (int, float))
                              else (round(float(spend_n_eff), 3)
                                    if isinstance(spend_n_eff, (int, float))
                                    else 1.0)),
                    "sides": "long",
                    "gross_x": gross_x(),
                    "days_to_gate_obs": round(
                        max(0.0, 30.0 - (t0 - born_ts) / 86400.0), 1),
                },
                "initial_equity": base_eq,
                # [2026-08-16 (no)] THE VENUE'S OWN MARGIN TRUTH. Until now
                # "what leverage is this book at, and how close is it to a
                # liquidation?" could only be ESTIMATED from clip arithmetic
                # (clip x slots / equity) — the venue publishes margin_mode,
                # initial_margin_fraction and liquidation_price on every
                # position and this fleet read none of them. `None` when the
                # venue could not answer: an unreadable margin state must not
                # publish as a confident 1.0x.
                "margin": _mstate,
                # [(th)] the control arm's paired null — via the ONE owner
                # (family's control_block, by identity), ALWAYS present for a
                # control-arm book incl. n=0; {} for avo/georgia so their
                # payloads do not move. 👩 mum's go-live verdict and every
                # pre-registered leverage notch read THIS, from her own
                # real-money ledger, instead of a differently-supplied twin.
                **control_block(S, ctrl),
                # [(th)] stop overshoot — LIVE measured fills only, per-book,
                # published always so quiet (n=0) and dark are never the same
                # byte-string. p90 enters any future gross ceiling only
                # additively in the denominator (restrict-only by
                # construction); no gate may consume it below a declared n
                # floor.
                "stop_overshoot": {
                    "n": int(ov.get("n") or 0),
                    "unmeasured_n": int(ov.get("unmeasured_n") or 0),
                    "p90_bps": (sorted(ov["vals"])[
                        max(0, int(round(0.9 * len(ov["vals"]))) - 1)]
                        if ov.get("vals") else None),
                    "worst_bps": (max(ov["vals"]) if ov.get("vals")
                                  else None),
                },
                # [(st)] THE CENSUS — see scan_census(). The answer to "why
                # has this book not traded", on the row, every loop.
                "scan": scan_census(
                    scan_verdict, last_rsi, getattr(S, "RSI_MAX", None),
                    universe, live_pos,
                    # UNKNOWN, not "everything": an empty verdict map means the
                    # oracle was not read this cycle (the halt paths publish
                    # before it is), and listing every non-crypto name as
                    # ungraded off a dark read is the guess I8 forbids.
                    ([c for c in universe
                      if c in NONCRYPTO_EFFECTIVE and c not in nc_verdicts]
                     if nc_verdicts else None),
                    entries_shut, last_open_ts[0],
                    (closed_win[-1].get("ts") if closed_win else None), t0),
            }
            payload.update(extra_extra or {})
            try:
                store.publish(
                    BOT_ROW, status=status,
                    equity=(round(eq, 2) if eq is not None else None),
                    pnl_abs=(round(pnl, 2) if pnl is not None else None),
                    # [(th)] denominated on CONTRIBUTED capital (birth equity
                    # + attested deposits/withdrawals) — display-side only,
                    # the graded per-trade sample is untouched.
                    pnl_pct=(round(pnl / _contrib, 6)
                             if (pnl is not None and _contrib
                                 and _contrib > 0) else None),
                    open_trades=len(live_pos),
                    closed_trades=st["closed"], wins=st["wins"],
                    losses=st["closed"] - st["wins"],
                    extra=payload)
            except Exception:  # noqa: BLE001
                pass
            # [(us)] THE MTM SERIES STAYS ON THE TRADING CADENCE. This append
            # feeds `<bot>:equity`, which `golive_readiness.apply_mtm` reads for
            # the 15% max-drawdown BAR (I9) — a real-money gate. The telemetry
            # refresh below re-publishes the ROW several times per trading pass,
            # and letting it append here would silently change that gate's
            # SAMPLING BASIS mid-window (300s spacing before, 60s after) on a
            # series whose whole job is to find the deepest trough. A denser
            # series can only report an equal-or-worse maxDD, so this would have
            # tightened a live gate as a side effect of a display change — the
            # "a bar computed on the wrong sample means nothing" class.
            # Telemetry publishes pass snapshot=False; nothing else does.
            if snapshot:
                try:
                    store.snapshot_equity(BOT_ROW, eq, open_trades=len(live_pos))
                except Exception:  # noqa: BLE001
                    pass

        def _telemetry_sleep(t0, eq, base_eq, cap_adj, live_pos, st):
            """Sleep out the rest of the trading cycle, re-publishing the ROW
            from the venue every `TELEMETRY_SECONDS`. PUBLISHES ONLY.

            The trading pass still runs exactly every `LOOP_SECONDS` — this
            replaces one long `sleep` with several short ones and a venue READ
            in between, so the dashboard stops being up to a full trading cycle
            behind the book. Worst-case row age goes ~330s -> ~70s at the
            shipped 60s cadence (plus the page's own 10s refresh).

            WHAT IT CANNOT REACH, which is the whole safety argument:
              * no entry, exit, stop, trail, ROI or sizing evaluation — those
                live in the trading pass and are not called from here;
              * no order path, no `_flatten_all`, no ledger write;
              * no equity re-read, so `EquityGuard`'s capital-move detection
                and its corroboration cadence are untouched (the (sr) deposit
                path rebases on CONSECUTIVE reads — changing how often it is
                asked is a real-money accounting change, and this does not);
              * no `snapshot_equity`, so the MTM series behind the drawdown bar
                keeps its 300s sampling basis (`snapshot=False`);
              * no state persistence — `_persist` / `_persist_day` are the
                trading pass's.
            It re-reads the venue's OWN account payload, which is exactly the
            point: a position closed by hand, or liquidated, shows up here
            without waiting for the next trading pass.

            Never raises. A telemetry read must not be able to stop a live
            trading loop — the same rule `_margin_block` is written under."""
            deadline = t0 + LOOP_SECONDS
            while True:
                remain = deadline - time.time()
                if remain <= 0:
                    return
                time.sleep(max(1.0, min(TELEMETRY_SECONDS, remain)))
                # Do not spend a REST call when the trading pass is already
                # due: it is about to publish a strictly better row, and the
                # account read it needs must not queue behind ours.
                if time.time() >= deadline - 1.0:
                    return
                try:
                    _publish_row(
                        eq, base_eq, cap_adj, live_pos, st, snapshot=False,
                        extra_extra={
                            # Present ONLY on a refresh: its absence marks the
                            # authoritative trading pass. A reader that cares
                            # which one it is asks for the key; one that just
                            # wants the positions does not have to.
                            "telemetry_only": True,
                            "since_trading_pass_s": round(
                                time.time() - t0, 1)})
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
            # [(th)] the control pair settles through the ONE owner (family's
            # control_settle, by identity), at the real close's instant — one
            # venue mid read for the placebo coin, both legs or neither ((rp)).
            _np = m.get("null_pair")
            control_settle(S, ctrl, m, total, notional or 0.0,
                           marks.fresh_mid(venue, _np) if _np else None)
            # [(th)] STOP OVERSHOOT — the quantity every future gross notch
            # must price. G_max = 1/(|stop|+mmf) assumes the stop fires AT its
            # level; the honest ceiling divides by (|stop|+overshoot+mmf), and
            # the one datum on tape (DOGE −7.17% on a −5% stop, 217bps past)
            # exceeds mum's whole 53bps liquidation headroom 4.1x. MEASURED
            # fills only — an unmeasured fill imputed as zero overshoot would
            # bias the exact number a real-money gate will consume, so those
            # count in their own bucket instead (I14).
            _ob = None
            if was_stop and entry:
                if measured and exit_px:
                    try:
                        # [2026-08-26] the level a TRAILING close fired at is
                        # the ratchet's own stop_px, not the fixed level from
                        # entry — measuring a ratchet fill against the entry
                        # stop would book a bogus (usually flattering)
                        # overshoot into the number a gross gate consumes.
                        _si = float(m.get("stop_px") or 0.0) or \
                            entry * (1.0 + float(S.stoploss))
                        _obv = (_si - exit_px) / _si * 1e4
                        if _obv == _obv and abs(_obv) != float("inf"):
                            _ob = round(_obv, 1)
                            ov["n"] = int(ov.get("n") or 0) + 1
                            ov["vals"] = (ov.get("vals") or [])[-49:] + [_ob]
                    except Exception:  # noqa: BLE001
                        _ob = None
                else:
                    ov["unmeasured_n"] = int(ov.get("unmeasured_n") or 0) + 1
            # [(th)] the phantom signature — a $0.00 close with NO entry price
            # is a halt/flatten EVENT, not a trade (avo carried 9 of them,
            # five with closed_at before opened_at; one on a coin the book
            # cannot even hold). Tagged at the write site so graders can
            # exclude by SIGNATURE, never by reason string — georgia's TRX
            # −$3.87 daily_loss is a REAL forced-flatten loss and must stay
            # in the sample.
            _phantom = (float(total) == 0.0 and not entry)
            tf_s = _interval_ms(S.tf) / 1000.0
            closed_win.append({"ts": time.time(), "pnl": total, "pct": pct,
                               "stop": was_stop, "pair": sym})
            cooldown[sym] = time.time() + \
                S.protections.get("cooldown_candles", 1) * tf_s
            _PRINT(f"[avo-live] {iso(t_now)} CLOSE {sym} | price "
                   f"{price_pnl:+.2f} funding {fund:+.2f} [{reason}]"
                   f"{'' if measured else ' (exit UNMEASURED)'}")
            try:
                # [2026-08-27] id + open stamp from the ONE owner
                # (lighter_family_bot.close_identity): on THIS row an unknown
                # open claimed ':None', and the upsert overwrites on a PK
                # match — georgia's real -$0.84 LIT close was one halt event
                # away from being zeroed. The same None also stamped an open
                # LATER than the close on 8 rows.
                _tid, _opened_iso = close_identity(
                    sym, m.get("opened_ts"), t_now)
                store.publish_paper_trade(
                    BOT_ROW,
                    trade_id=_tid,
                    pnl_abs=float(total), pnl_pct=pct, pair=sym,
                    opened_at=_opened_iso,
                    closed_at=t_now.isoformat(),
                    reason=ledger_reason(m.get("tag"), reason),
                    entry_price=entry or None, exit_price=exit_px or None,
                    side="long", shadow=False,
                    extra={"policy": _policy(), "fill_measured": measured,
                           "fill_src": why, "clip": m.get("clip"),
                           # [(so)] I22 receipt: the brain scale this REAL
                           # stake was sized at. `clip` is base x strategy
                           # stake_mult x brain and cannot be decomposed.
                           "brain_mult": m.get("brain_mult"),
                           # [(th)] the open-site stamps, copied not computed:
                           # rank is born at the OPEN ((sv)); the pre-(th) 46
                           # georgia closes carry None and always will.
                           "entry_rank": m.get("entry_rank"),
                           **({"non_economic": True} if _phantom else {}),
                           **({"stop_overshoot_bps": _ob}
                              if _ob is not None else {})})
            except Exception:  # noqa: BLE001
                pass

        def _policy():
            """The stamp golive_readiness keys eras on — the RULES in force,
            not capacity levers ((jf): capacity is ordinary tuning).

            [(ti)] Built via the ONE builder shared with the shadow host
            (`policy_stamp`) so judge v2's parity precheck compares like with
            like — this host's scan is correlation-ordered
            (`diversified_order`), stated in the stamp, where the shadow
            scans in list order: a REAL entry-policy divergence the pairs
            must name rather than average over. ERA-SAFE by construction:
            the gate's boundary extractor (`stamp_state`) reads only
            POLICY_SIG_FIELDS and requires a `lenses` key these stamps
            deliberately lack, so family stamps are structurally invisible
            to `stamped_policy_boundary` and adding a field moves no era."""
            # [(uv)] `max_entries_per_hour=None` is this host ANSWERING, not
            # declining to: it enforces no hourly throttle (see the entry
            # loop's own comment — live rank is the UNCENSORED within-hour
            # ordinal), while the shadow's `DayTraderGated` caps at 3. Passing
            # the strategy's own cap here would stamp a throttle this host does
            # not apply, which is why the argument is the HOST's to answer.
            return {**policy_stamp(S, "lighter_live", "diversified", None),
                    "brain_gate": "row+shadow", "coin_veto": True}

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
        # [(st)] this cycle's verdicts, folded into the durable per-symbol map
        # at the bottom of the loop. Cycle-local so a coin the loop never
        # reached keeps its PREVIOUS verdict instead of being silently reset.
        cycle_verdict = {}

        def _verdict(sym, why, sig=None):
            """Record WHY `sym` did not become a trade this cycle. Telemetry
            only — it is called beside an existing `continue`, never instead of
            one, so no control flow depends on it."""
            cycle_verdict[str(sym)] = why

        brain_gated_tags = []
        # [(sp)] the two brain-sizing refusals, PUBLISHED. Neither is silent:
        # a refused expand and a floored reduce are both decisions this book
        # made about real money, and a decision nobody can see is the class
        # (so) was written to close.
        brain_expand_refused = brain_floored = 0
        notional_cap_skips = 0
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
            # [2026-08-25] custom_exit joined the stack (the host NEVER called
            # it — 🔮 georgia ran real money without her own timeouts, the
            # (te) audit's find). [2026-08-26] the WHOLE stack is now the
            # manage_exit_reason seam, which also carries the two family
            # semantics that audit missed: DayTraderGated's trailing ATR
            # ratchet and the trend_breakout veto on the exit signal — see the
            # seam's own docstring for the measured live cost of each.
            reason = manage_exit_reason(S, m, px, profit, age_min, sig, bars)
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
        # [(st)] WHEN THE WHOLE SCAN IS SHUT, say which precondition shut it.
        # `entries_ok` is five ANDed terms and a False was previously
        # indistinguishable from a universe with no signal — the same
        # ambiguity one level up from the per-coin census below.
        entries_shut = None if entries_ok else (
            "positions_unreadable" if not pos_readable else
            "equity_unreadable" if equity is None else
            "halt_unreadable" if halt_blind else
            "clip_unreadable" if clip is None else
            "clip_below_min" if clip < MIN_CLIP_USD else
            "protections_locked")
        # [(sr)] Returns for everything we might hold or take, off bars the
        # cache already holds (one governed fetch per closed candle, shared).
        # Built even when entries are shut, because `n_eff` describes the HELD
        # basket and the row must report it every loop, not only on scan days.
        _rets = {}
        for _s in set(list(pos) + list(universe)):
            try:
                _rets[_s] = _bar_returns(cache.get(_s, S.tf))
            except Exception:  # noqa: BLE001 — telemetry never breaks the loop
                _rets[_s] = {}
        held_n_eff, held_rho = basket_n_eff(_rets, list(pos))
        if isinstance(held_n_eff, (int, float)):
            spend_n_eff = held_n_eff          # [(te)] carried for the census

        if entries_ok:
            # THE ONLY BEHAVIOURAL CHANGE: the sequence candidates are offered
            # in. Every gate, veto, cap and sizing rule below is untouched, so
            # for any SINGLE candidate this path is byte-identical to before.
            #
            # [2026-08-22 (st)] AND THE CENSUS. `_verdict(sym, why)` stamps the
            # reason this candidate did not become a trade — it is pure
            # telemetry beside each existing `continue`, never a new one. See
            # `scan_census()` for why the verdicts are kept PER SYMBOL rather
            # than counted per cycle.
            for sym in diversified_order(universe, list(pos), _rets):
                if len(pos) >= S.max_open:
                    for _rest in universe:
                        if _rest not in pos and _rest not in meta:
                            _verdict(_rest, "slots_full")
                    break
                if sym in pos or sym in meta:
                    _verdict(sym, "held")
                    continue
                if t0 < cooldown.get(sym, 0.0):
                    _verdict(sym, "cooldown")
                    continue
                bars = cache.get(sym, S.tf)
                if not bars or not bars.get("t"):
                    _verdict(sym, "no_bars")
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
                # [(st)] the gauge: the SHIPPED rule's own rsi, kept per coin so
                # the row can say how FAR the market is from the bar, not only
                # that it did not clear it ((rr)'s reading, at this book).
                if sig and isinstance(sig.get("rsi"), (int, float)):
                    last_rsi[sym] = float(sig["rsi"])
                if not sig or not sig.get("enter"):
                    # [2026-08-26] the ONE census owner: 👩 mum's sub-bar RSI
                    # refused by the NOT-uptrend half now reads
                    # `uptrend_blocked`, not a `no_signal` byte-identical to
                    # "no low rsi anywhere" (I18).
                    _verdict(sym, census_no_entry_why(S, sig), sig=sig)
                    continue
                px = marks.fresh_mid(venue, sym)
                if not px:
                    _verdict(sym, "no_mark")
                    continue
                if noncrypto_entry_blocked(sym, r_up):
                    # THE REFUSAL THAT WAS INVISIBLE. Measured 22-Aug: both
                    # post-drought IWM signals died here, because the oracle
                    # cannot grade IWM (172 bars < its 203 floor) and the gate
                    # is fail-CLOSED. Working exactly as designed — and
                    # byte-identical to "no signal" on every reading of the row.
                    _verdict(sym, "noncrypto_ungated"
                             if sym not in (nc_verdicts or {})
                             else "noncrypto_not_long")
                    continue                      # fail-closed per-asset gate
                if fleet_long_veto:
                    _verdict(sym, "fleet_long_veto")
                    continue
                if fleet_headroom is not None and \
                        cycle_admitted >= fleet_headroom:
                    _verdict(sym, "budget_headroom")
                    continue
                if symcap_blocked(fleet_symcap, sym, cycle_sym):
                    _verdict(sym, "symcap")
                    continue
                if sym.split("/")[0] in coin_vetoed or sym in coin_vetoed:
                    _verdict(sym, "coin_veto")
                    _PRINT(f"[avo-live] {iso(t_now)} {sym} entry SKIPPED — "
                           f"coin veto: {coin_vetoed.get(sym) or coin_vetoed.get(sym.split('/')[0])}")
                    continue
                tag = sig["enter"]
                gated = False
                for gate_row in (BOT_ROW, SHADOW_ROW):
                    if brain_entry_gated(gate_row, tag):
                        gated = True
                if gated:
                    _verdict(sym, "brain_gate")
                    brain_gated_tags.append(f"{sym}:{ledger_tag(tag)}")
                    continue
                stake = clip * S.stake_mult(tag, bars)
                # [2026-08-20 (so)] ...and the brain's per-tag scale on top,
                # across BOTH rows — the same pair, the same `ledger_tag`
                # identity and the same fail-safe as the regime gate above, so
                # a gate and a size can never disagree about which bucket this
                # trade is in.
                #
                # [2026-08-20 (sp)] TWO CORRECTIONS, both to (so), both found
                # by driving the arithmetic against this book's REAL numbers
                # rather than reading the code.
                #
                # (1) **RESTRICT-ONLY, like every other lever that reaches this
                # book.** This module's own `_clip_scale_now` docstring states
                # the invariant: *"with clip = equity/max_open and stake_mult
                # <= 1.0, gross notional can never exceed account equity — the
                # book is 1.00x by construction and no lever reaches past it."*
                # (so) broke that silently. At the modelled live equity (~$63,
                # clip ~$15.70, cap $200) a brain rung of 6.39 puts TWO slots
                # at $99.98 = $199.96 gross = **3.19x equity** on a book
                # documented as 1.00x, with a -10% stop underneath it. Expanding
                # a real-money book past its own equity is a LEVERAGE decision,
                # and I22 is explicit that leverage adds no decidability and is
                # admissible only as the output of a measured vol target, which
                # this book does not have. So the brain may SHRINK Avo and not
                # grow it — the same `min(1.0, ...)` shape as `live.clip_scale`,
                # and the same reason. Its expand side is an operator/gate
                # decision, not a bus read. 💸 the Farmer keeps BOTH directions:
                # it has a real notional cap and, since (sp), a rail that TRIMS.
                #
                # (2) **A REDUCE MUST MAKE THE BOOK SMALLER, NOT RETIRE IT.**
                # The floor below is $5 against a $15.70 clip, so any rung at
                # or under 1/3.2 sent every entry to `continue` — the deep
                # rungs 1/4.5 ($3.49) and 1/6.7 ($2.34) BOTH do. That is a
                # 100% halt: zero entries for as long as the brain holds the
                # reduce, while the row keeps publishing `status: online` and
                # `clip_usd: 15.70`. Byte-identical to "no signals today", and
                # self-locking — a book that stops trading stops producing the
                # closes that would lift the reduce. Now it floors at
                # MIN_CLIP_USD, the smallest size the venue will take, and SAYS
                # SO on the row.
                stake, bmult = brain_clip_for((BOT_ROW, SHADOW_ROW), tag, stake)
                if bmult > 1.0:
                    stake, bmult = clip * S.stake_mult(tag, bars), 1.0
                    brain_expand_refused += 1
                if stake < MIN_CLIP_USD <= clip * S.stake_mult(tag, bars):
                    brain_floored += 1
                    stake = MIN_CLIP_USD
                if stake < MIN_CLIP_USD:
                    _verdict(sym, "clip_below_min")
                    continue
                open_ntl = open_notional(pos, meta, len(pos), stake)
                if not rails.notional_ok(open_ntl, stake):
                    _verdict(sym, "notional_cap")
                    # [(sr)] counted, not just logged — a log line dies with the
                    # container and no organ reads it. `cap_slots` below says the
                    # cap WILL bite; this says it DID.
                    notional_cap_skips += 1
                    _PRINT(f"[avo-live] {iso(t_now)} {sym} NOTIONAL_CAP_SKIP "
                           f"(deployed ${open_ntl:.2f} + ${stake:.2f} > cap "
                           f"${rails.max_notional})")
                    continue
                size = round(stake / px, 6)
                if size <= 0:
                    _verdict(sym, "size_rounds_to_zero")
                    continue
                try:
                    res = venue.market_open(sym, True, size)
                except Exception as e:  # noqa: BLE001
                    _verdict(sym, "venue_reject")
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
                # [(th)] entry_rank, born at the OPEN like the shadow's (sv)
                # stamp — the close can only copy what the open recorded. The
                # clock-hour bucket lives in the durable state so a mid-hour
                # restart cannot under-rank. DECLARED PORT DIVERGENCE: this
                # host enforces NO hourly throttle (the shadow's
                # MAX_ENTRIES_PER_HOUR censors its ranks), so live rank is the
                # UNCENSORED within-hour ordinal — a rank study must read the
                # two arms accordingly. Non-DayTrader books stamp None, never
                # a fake 1 ((sv)).
                if isinstance(S, DayTraderGated):
                    _hb = int(t0 // 3600)
                    if state.get("rank_bucket") != _hb:
                        state["rank_bucket"], state["rank_n"] = _hb, 0
                    state["rank_n"] = int(state.get("rank_n") or 0) + 1
                    meta[sym]["entry_rank"] = state["rank_n"]
                else:
                    meta[sym]["entry_rank"] = None
                # [(th)] the control arm's placebo, drawn through the ONE
                # owner (family's control_draw, by identity): the coin first,
                # then one venue mid read for it alone. {} for every
                # non-control book, so avo/georgia meta is unchanged.
                meta[sym].update(control_draw(
                    S, universe, sym, lambda c: marks.fresh_mid(venue, c)))
                pos[sym] = {"size": size, "entry": fpx or px}
                _verdict(sym, "opened")
                last_open_ts[0] = t0
                cycle_admitted += 1
                base = sym.split("/")[0]
                cycle_sym[base] = cycle_sym.get(base, 0) + 1
                _PRINT(f"[avo-live] {iso(t_now)} OPEN {sym} long "
                       f"${stake:.2f} @ {fpx or px:.6g} [{tag}]"
                       f"{'' if bmult == 1.0 else f' brain {bmult:.2f}x'}"
                       f"{'' if meas else ' (entry UNMEASURED)'}")

        # [(st)] fold this cycle's verdicts into the durable map. A coin the
        # loop never reached (the candle had not rolled) keeps its previous
        # verdict rather than being reset to nothing — the census describes the
        # last EVALUATION of each coin, which is the only reading that means
        # anything on a 4h book publishing every 90 seconds.
        scan_verdict.update(cycle_verdict)
        for _gone in [k for k in scan_verdict if k not in universe]:
            scan_verdict.pop(_gone, None)          # coin left the universe
        for _gone in [k for k in last_rsi if k not in universe]:
            last_rsi.pop(_gone, None)

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
        _telemetry_sleep(t0, equity, baseline, capital_adjust, pos, stats)


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

    # [(sz)] THIS SUITE IS SwingDip-SHAPED, and says so rather than half-running.
    # Its thirteen scenarios feed 4h dip bars and `dip_in_uptrend` tags, so under
    # 🔮 georgia (DayTraderGated, 15m) they exercise the generic machinery and
    # then fail at "dip signal must open" — a failure about the FIXTURE, not the
    # book. Refusing is the honest form: a suite that ran three of its thirteen
    # checks and exited 0 would report clean having inspected almost nothing,
    # which is the exact trap this repo has paid for.
    #
    # georgia's coverage is real and lives elsewhere:
    #   tests/autonomy/test_variant_host.py — identity, env namespacing, the
    #   refusal on an unknown book, the leverage/liquidation arithmetic, and a
    #   BOOT SMOKE that drives this same main() one cycle as her.
    if BOT != "freqtrade-avo-maria":
        raise SystemExit(
            f"--selftest is the 🙏 Avo SwingDip scenario suite; {BOT} is "
            f"covered by tests/autonomy/test_variant_host.py. Run it without "
            f"FAMILY_LIVE_BOOK set, or run pytest for the variant.")

    print("Running Avo LIVE self-test (stub venue)...\n")

    # The single most load-bearing fact: the strategy object IS the family
    # registry's instance — identity, not equality ((hj): pin re-use by
    # identity, a name check stays green against a hand-rolled copy).
    assert S is next(x for x in fam.STRATEGIES if x.bot == BOT), \
        "S must BE lighter_family_bot's configured instance"
    # [(sr)] 4 -> 5 slots, measured (see the registry comment in
    # lighter_family_bot). The STOP pin is doubly load-bearing: the whole
    # leverage layer derives from it — `vol_target_gross_x` (0.15/|stoploss|)
    # and `stop_reachable`'s ceiling (1/(|stoploss|+mmf)) — so a stop widened
    # without re-reading those silently changes what a leverage setting MEANS
    # on a real-money book.
    #
    # [(sz)] PER BOOK, now that this module is a variant host. Written as a
    # table rather than `whatever S says`, which would be vacuous: each book is
    # pinned to its OWN known geometry, and a book added to `_BOOKS` without an
    # entry here fails rather than running unpinned.
    _EXPECT = {"freqtrade-avo-maria": (5, -0.10),
               "freqtrade-georgia": (5, -0.05)}
    assert BOT in _EXPECT, f"{BOT} is live-capable but has no geometry pin"
    _slots, _stop = _EXPECT[BOT]
    assert S.max_open == _slots and abs(S.stoploss - _stop) < 1e-9, \
        f"{BOT} geometry moved: slots {S.max_open} stop {S.stoploss}"

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
            self.cap_src = "env"
            self._killed = killed

        def kill_check(self):
            return self._killed

        def equity_scale(self, equity, gross):
            return self.max_notional        # interface parity; stub never scales

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
        # [(sr)] READ the geometry, never retype it — this asserted `62.80 / 4`
        # and broke the moment the slot count moved, which is the "a retyped
        # constant is a constant that drifts" rule landing on the test itself.
        # Now it derives from the same two sources the bot sizes off, so it
        # follows a deliberate slot/leverage change and still fails a wrong one.
        _want = 62.80 * gross_x() / S.max_open
        assert abs(stake - _want) < 1.0, \
            (f"clip must be equity * gross_x / max_open "
             f"(~{_want:.2f} at {S.max_open} slots, {gross_x()}x), "
             f"got {stake:.2f}")
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
