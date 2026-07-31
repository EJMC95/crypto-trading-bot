#!/usr/bin/env python3
"""
bot_learn.py — the fleet's learning loop ("brain"), v2.

WHAT IT DOES
  1. Pulls the durable trade ledger (the pnl-dashboard's /trades.json, which is
     backed by the Postgres bot_trades table and survives redeploys).
  2. Dissects every bot's closed trades along five axes: entry tag, exit
     reason, pair, hold-duration bucket, and UTC session.
  3. Keeps CUMULATIVE state across runs (Postgres bot_state key
     'learning-brain' when DATABASE_URL is set, else reports/brain_state.json):
     a candidate pattern ("hypothesis") must persist across >= PROMOTE_RUNS
     runs AND keep its sample growing before it is promoted to ACTIONABLE —
     one lucky/unlucky day never changes anything.
  4. Writes reports/lessons_latest.md: per-bot scorecards + PROPOSALS.
  5. [2026-07-14 L4 META-LABELING] Publishes NUMERIC, REDUCE-ONLY per-
     (bot, enter_tag) stake multipliers to bot_state 'brain-stake-mults'.
     Strategies read them at entry via fleet_bus.stake_multiplier() — the
     first brain output any bot actually trades on. Hard guardrails:
       - trade-count floor: n >= MULT_MIN_N (30) era trades on that tag
         for a 0.5x; a softer 0.75x needs n >= MULT_SOFT_N (15)
       - persistence: the reduction must recur on PROMOTE_RUNS (3)
         consecutive brain runs before it is PUBLISHED (streak-gated,
         same philosophy as hypothesis promotion)
       - reduce-only: v1 never publishes > 1.0x; boosting must earn its
         own evidence bar later
       - fail-safe: payload carries updated+ttl_sec; consumers go neutral
         when it is stale (see fleet_bus.py)
  6. [2026-07-14 VENUE A/B] Compares every paper book with its Lighter
     shadow twin (<bot> vs <bot>-lshadow, live -lighter rows too) from
     bot_pnl — the shadow-book data collected since 13 Jul — and reports
     the venue gap per strategy in lessons + state (key 'venue_ab').
  7. [2026-07-14b DIAGNOSIS] For every negative (bot, tag) bucket at sample
     size, classifies WHICH LEVER the loss lives in — exit_too_tight /
     venue_execution / fee_bleed / regime_timing / entry_quality — using
     exit-path splits, post-exit drift from public 1h candles (the
     mechanized form of the manual replay behind the 13-Jul stop widening),
     fee-scale tests, a regime-oracle-history join, and the venue A/B
     table. Publishes bot_state 'brain-diagnosis'; proposals now name the
     lever instead of defaulting to "tighten the entry gates" (the 92-run
     'flip' artifact this replaces).
     [2026-07-17 LIGHTER-FIRST] Those drift candles now come from LIGHTER's
     own book (was: Kraken spot — a RETIRED venue, and the wrong instrument
     for a perp close), gated to trades whose venue IS Lighter. See the
     block above _lighter_market_ids() for the measurement showing the old
     path was already dead (drift verdicts: 0 of 409 living-fleet losers)
     and what really gates coverage now: shadow brokers recording fills.

  8. [2026-07-16 v3 STATISTICS ENGINE — brain_stats.py] The qualification
     statistics grew up: decay-weighted buckets (half-life forgetting inside
     an era), Kish effective sample sizes, empirical-Bayes pooling (a tag's
     win rate shrinks toward its siblings on other bots, then the bot, then
     the fleet), Wilson bounds + weighted t-stats as evidence bars, richer
     bucket metrics, per-(bot,tag) REGIME SPLITS, episode-deduplicated lens
     grading (raw fields unchanged — consumers keep their contract), and a
     'brain-vitals' bot_state key exposing priors/watchlist/config.
     Validated by brain_replay.py (ledger replay, v2-vs-v3, both halves).
     BRAIN_MULT_ENGINE=v2 is the no-redeploy kill switch back to the
     frozen 14-Jul rules. Floors, streak gate, reduce-only grid and the
     fleet_bus [0.5,1.0] clamp are UNCHANGED — authority did not move.

WHAT IT NEVER DOES
  Change entry/exit logic, configs, or trades — and it never SIZES UP.
  The multipliers only throttle stakes on tags the ledger has repeatedly
  scored negative at sample size. Humans still ship logic changes; see
  NO_REAL_MONEY policy.

Run it anywhere: laptop (called by the 2-hourly research scan) or cloud.
"""
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

TRADES_URL = os.environ.get(
    "LEARN_TRADES_URL",
    "https://pnl-dashboard-production-858c.up.railway.app/trades.json?limit=2000")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
LOCAL_STATE = os.path.join(REPORTS_DIR, "brain_state.json")
LESSONS_MD = os.path.join(REPORTS_DIR, "lessons_latest.md")

MIN_N_FLAG = 8        # min closed trades before a pair/tag pattern counts
MIN_N_SESSION = 20    # sessions are noisier -> bigger sample required
PROMOTE_RUNS = 3      # a hypothesis must survive this many runs to be ACTIONABLE

# [2026-07-14 L4] Stake-multiplier floors. The design doc's non-negotiable:
# tiny samples must never masquerade as edge. 30 era-trades for the hard
# throttle mirrors the meta-labeling literature's minimum;
# 15 for the soft one because it only shaves a quarter of the stake.
MULT_MIN_N = 30       # era trades on a tag before a 0.5x may publish
MULT_SOFT_N = 15      # era trades before a 0.75x may publish
# [2026-07-21 EXPAND — operator: "brain needs to be able to widen too"]
# Two-way mults: a PROVEN tag may earn 1.25x/1.5x on brain_stats' mirror
# bars (Wilson LOWER bound, t >= +2.0/+2.5, full n floor, no family
# inheritance, no urgent path — see EXP_* there). v3-ONLY: the
# BRAIN_MULT_ENGINE=v2 kill switch zeroes the expand side too, and this
# dedicated switch stands down just the widening while reductions keep
# working. Consumers clamp at fleet_bus.MULT_CEIL (1.5) and only SHADOW
# books read mults — no live bot consumes them.
# [2026-07-21 AUDIT FIX] accept the full stand-down synonym set (+strip):
# the original `!= "off"` meant BRAIN_MULT_EXPAND=false / 0 / no / disabled
# / 'off ' all silently LEFT EXPANSION ARMED — a kill switch that only
# worked for one exact string (the PARLIAMENT_ENABLED / BRAIN_MULT_ENGINE
# typo class).
MULT_EXPAND = os.environ.get("BRAIN_MULT_EXPAND", "on").strip().lower() \
    not in ("off", "0", "false", "no", "disabled")
# [2026-07-22] EPISODE BASIS for the v3 evidence layer (the (bb) deferred
# item, brain_replay-validated): trades whose closes chain within this gap
# are ONE market event — dad+breakout-4h's "10 losses ≈ 1 correlated
# episode, identical pairs closed within 4 minutes". Raw floors stay on
# TRADES (the design doc's non-negotiable); only n_eff/wr_w/t collapse.
# Protects BOTH directions: a correlated loss-burst cannot condemn alone,
# a correlated win-burst cannot buy a (bh) raise. 0 = trade basis (the
# knob is its own kill switch); v2 engine never touches this path.
EP_GAP_SEC = float(os.environ.get("BRAIN_EP_GAP_SEC", "600"))
MULT_KEY = "brain-stake-mults"
MULT_TTL_SEC = 26000  # ~3.6 brain intervals (7200s) -> 3 missed runs = stale

# [2026-07-16 v3] brain_stats.py carries the statistics engine (decay
# weighting, EB pooling, Wilson/t bars). Import-guarded like every other
# optional organ: a checkout without it falls back to the frozen v2 rules,
# and BRAIN_MULT_ENGINE=v2 flips back without a code change.
try:
    import brain_stats as bstats
    _BSTATS_ERR = None
except Exception as _e:  # noqa: BLE001
    bstats = None
    _BSTATS_ERR = repr(_e)          # WHY it failed — missing file vs broken file
# [2026-07-17] The operator's INTENT, normalized. fleet_immune's born-dark
# detector parses this env the SAME way (.strip().lower()) — the two MUST
# agree or a case-typo'd kill switch silences the detector. Previously this
# was a raw `!= "v2"` compare here vs .strip().lower() there.
_ENGINE_INTENT = os.environ.get("BRAIN_MULT_ENGINE", "").strip().lower()
MULT_ENGINE = (_ENGINE_INTENT or "v3") if bstats else "v2"
# [2026-07-17 IMB-29b] the fallback must be LOUD: a checkout missing
# brain_stats silently ran frozen v2 rules (era-lifetime anchors, no decay,
# no EB pooling) for a DAY while everything downstream assumed v3 (the
# 17-Jul born-dark postmortem). Report the REAL error — "missing from the
# image" and "present but raises on import" need different fixes, and the
# old message asserted the former. Detection also lives in fleet_immune
# (brain-vitals engine=v2 without a deliberate kill switch -> phone) and
# prevention in scripts/audit_image_imports.py.
if bstats is None and _ENGINE_INTENT != "v2":
    print(f"[bot_learn] WARNING: brain_stats unimportable ({_BSTATS_ERR}) — "
          f"SILENT v2 fallback engaged (frozen rules, lifetime anchors, no "
          f"episode grading). BRAIN_MULT_ENGINE was not set to v2, so this "
          f"is NOT deliberate: check the image's COPY list.", flush=True)
if MULT_ENGINE not in ("v2", "v3"):
    # An unrecognized value used to be coerced to v3 SILENTLY — so
    # BRAIN_MULT_ENGINE=V2 (or a typo) meant the operator threw the kill
    # switch and nothing happened, with no signal anywhere. Say so.
    print(f"[bot_learn] WARNING: BRAIN_MULT_ENGINE={_ENGINE_INTENT!r} is not "
          f"'v2' or 'v3' — IGNORING it and running v3. If you meant to throw "
          f"the kill switch, it is NOT thrown.", flush=True)
    MULT_ENGINE = "v3"
HALF_LIFE_DAYS = float(os.environ.get("BRAIN_HALF_LIFE_DAYS", "14"))
VITALS_KEY = "brain-vitals"

# [2026-07-14b DIAGNOSIS LAYER] Discriminate WHERE a negative sleeve loses:
# entry quality / exit path / fee bleed / regime timing / venue execution.
# Born from the 92-run "tighten the 'flip' entry gates" artifact — the brain
# could find patterns but not tell an entry problem from an exit problem from
# a venue problem, so its prose pointed at the wrong lever.
DIAG_KEY = "brain-diagnosis"
DIAG_MIN_N = 10           # closed era trades before diagnosing a bucket
# [2026-07-15 LENS-FORWARD] counterfactual scout-lens scoreboard published for
# the taker (restrict-only veto) + the dashboard. Same freshness contract.
LENS_FWD_KEY = "brain-lens-forward"
LENS_HORIZONS = ((1, 3600), (4, 4 * 3600), (24, 24 * 3600))
DIAG_DRIFT_MAX_PAIRS = 30  # cap Lighter candle fetches per run (1/pair, cached)
STOPPISH = ("stop_loss", "trailing_stop_loss", "bleed_stop", "stoploss",
            "liquidation", "force_exit",
            # [2026-07-28 AUDIT FIX] the LIGHTER books' actual stop names —
            # the vocabulary above was freqtrade-era only, so rule 1
            # (exit_too_tight) was UNREACHABLE for the Ticket Taker ('sl',
            # split from '<side>-<lens>_sl'), the Farmer ('stop' /
            # 'stop_blind', split from '<side>_stop*') and every Parliament
            # book, regardless of drift evidence: 7 of 10 live diagnoses
            # carried worst_exit='sl' and structurally could not reach the
            # rule. The evidence bars (share/wr/reclaim/fwd) still gate.
            "sl", "stop", "stop_blind")
# Round-trip friction estimate per bot (fraction of stake). Kraken spot taker
# 0.26%/side is the freqtrade default; the perps ledger documented ~29bps.
#
# [2026-07-30 THE BRAIN WAS DEGRADING HERE — read this before touching it.]
# Three defects compounded, and the result was the brain attributing losses to
# a cost that does not exist while SUPPRESSING its only actionable diagnosis:
#
#   1. WRONG KEY FORM. `FEE_RT.get(bot, ...)` was called with the SUFFIXED row
#      name (`perps-funding-carry-lshadow`), while every table key is a BARE
#      base name. So not one entry ever matched and EVERY bot fell through to
#      the default. This is the identical defect the 23-Jul audit fixed for
#      ERA_START — five lines away, in this same function (see the
#      `_era_base` suffix-strip in main()).
#   2. A RETIRED VENUE'S FEE AS THE FLEET DEFAULT. 0.0052 is Kraken SPOT taker
#      round trip. Kraken was retired 14-Jul. Every Lighter book was being
#      charged it.
#   3. LIGHTER IS ZERO-FEE, MEASURED. All 203 active books report
#      `taker_fee 0.0000` / `maker_fee 0.0000` (2026-07-30, via
#      orderBookDetails). So the phantom cost was the WHOLE estimate.
#
# WHY IT CORRUPTED EVIDENCE RATHER THAN MERELY MIS-REPORTING: `diagnose()`
# rule 3 fires when `fee_rt / med_loser >= 0.5` and `med_loser <= 0.012`, and
# it RETURNS. With fee_rt = 0.0052 that condition holds for ANY bucket whose
# median loser is <= 1.04% — an extremely common loss size — so rule 3
# pre-empted rule 4 (`regime_timing`), which is the ONLY diagnosis kind
# carrying an actuator (`regime_gate`, main():1568). The brain could not
# recommend the one thing it is able to act on.
#
# HOW IT CANNOT CORRUPT AGAIN: the fee is now MEASURED, not asserted. The
# scout publishes the venue's own schedule (`lighter-market.fees`, max across
# active books) and `fee_rt_for()` prefers it. Note `is_taker_fee_enabled` is
# TRUE on every book with the rate at zero — the machinery is ON and the rate
# CAN change, so a hardcoded 0.0 would be this same mistake mirrored. A dark
# scout falls back to the declared per-venue constant, never to another
# venue's. `tests/autonomy/test_brain_fee_basis.py` pins all of it.
FEE_RT_DEFAULT = 0.0052
FEE_RT = {"perps-funding-carry": 0.0029, "perps-rsi-meanrev": 0.0029,
          "perps-donchian-breakout": 0.0029, "event-listing-sniper": 0.0060}
# Fallback round-trip for a Lighter row when the scout is dark. Lighter is
# measured zero-fee; this is deliberately NOT 0.0 so a dark scout cannot make
# the brain claim certainty it has not measured — it is small enough never to
# trip rule 3 on a realistic loser, and honest about being an estimate.
LIGHTER_FEE_RT_FALLBACK = float(os.environ.get("BRAIN_LIGHTER_FEE_RT", "0.0002"))
_LIGHTER_SUFFIXES = ("-lshadow", "-lighter", "-ltest")


def fee_base(bot):
    """The BARE bot name the FEE_RT table is keyed on — suffix-stripped, the
    same normalisation main() already does for ERA_START."""
    b = str(bot)
    for suf in _LIGHTER_SUFFIXES:
        if b.endswith(suf):
            return b[: -len(suf)]
    return b


def is_lighter_row(bot):
    return str(bot).endswith(_LIGHTER_SUFFIXES)


def fee_rt_for(bot, venue_fees=None):
    """Round-trip friction for `bot`, as a fraction of stake. ONE OWNER.

    A LIGHTER row uses the venue's MEASURED schedule when the scout provides
    one (`venue_fees` = the scout's `fees` block), else the declared Lighter
    fallback. It must NEVER inherit a non-Lighter default — that inheritance
    is precisely the defect documented above.

    A non-Lighter row uses the FEE_RT table by BASE name, else FEE_RT_DEFAULT.
    """
    if is_lighter_row(bot):
        try:
            taker = (venue_fees or {}).get("taker")
            if taker is not None:
                # round trip = both sides; a taker-only estimate is optimistic
                return max(0.0, float(taker) * 2.0)
        except (TypeError, ValueError):
            pass
        return LIGHTER_FEE_RT_FALLBACK
    return FEE_RT.get(fee_base(bot), FEE_RT_DEFAULT)

# [ERA AWARENESS] Hypotheses must come from trades taken by the CURRENT code.
# Without this the brain prosecutes today's strategy for yesterday's crimes
# (e.g. flagging pairs the dead 15m scalper bled on). Trades opened before a
# bot's era-start still show in lifetime tallies but generate no hypotheses.
# [2026-07-30 (hh)] THE SIX FAMILY/SPOT ERAS WERE STILL EARLIER THAN THE ACCRUAL
# FIX. Each was set for a STRATEGY change (13/14-Jul) and each was therefore
# still pooling pre-17-Jul closes whose `accrued` was 8x — `lighter_family_bot`
# publishes all six and carries "[2026-07-17 BASIS FIX ii]" on its accrual line.
# (hg) left this as a stated follow-up rather than a side effect of a real-money
# commit; this is that follow-up.
#
# THE RULE, so a future entry cannot get it wrong: **an era is the LATEST of
# every invalidating change that applies to the book.** Two eras do not compose
# into a range — a sample must exclude BOTH the old strategy and the old
# accounting, and 17-Jul > 14-Jul does exactly that. Moving these dates FORWARD
# therefore preserves each original reason instead of discarding it; the earlier
# reason is kept in the comment because it is what the date must never go BELOW.
# Strictly narrower, so strictly restrict-only: a bucket that falls under the
# n>=30 floor stops generating hypotheses, which is the fail-closed direction.
ERA_START = {
    # 13-Jul: range_meanrev retired + counter-trend stop 2.0->3.5x; 17-Jul accrual basis
    "crypto-intraday-15m": "2026-07-17T00:00",
    # ungated range -> validated dip + bounce (3-Jul); 17-Jul accrual basis
    "crypto-swing-daily":  "2026-07-17T00:00",
    # 14-Jul: BTC-tide gate on breakout entries (backtest-validated); 17-Jul accrual basis
    "crypto-breakout-4h":  "2026-07-17T00:00",
    "crypto-trendmomo-4h": "2026-07-03T06:00",   # 4h/20-alt -> 1d BTC+ETH 10/40 (RETIRED 12-Jul — pre-dates the accrual fix entirely, left as history)
    "perps-regime-switch": "2026-07-03T10:00",   # EMA-cross -> Donchian entries (RETIRED 12-Jul — same)
    # 13-Jul: same DayTraderV5Gated sleeve/stop changes; 17-Jul accrual basis
    "freqtrade-georgia":   "2026-07-17T00:00",
    # 14-Jul: whitelist curated to the 10 backtest-positive pairs; 17-Jul accrual basis
    "freqtrade-mum":       "2026-07-17T00:00",
    # 14-Jul: BTC-tide gate (same MomoBreakoutV1 carrier); 17-Jul accrual basis
    "freqtrade-dad":       "2026-07-17T00:00",
    # never had an era; same publisher, same accrual fix
    "freqtrade-avo-maria": "2026-07-17T00:00",
    # [2026-07-30 (hh)] 🎫 Ticket Taker — REAL MONEY, and it had no brain era at
    # all while the go-live gate gained one in (hg). It accrues (its divergence
    # lens exists to collect the credit) and carried the same 8x defect modelled
    # inline. Its own note: the inflated credit "flattered the one number that
    # could earn this bot a go-live" — and the brain's lens-forward grades are a
    # taker VETO, so an inflated number here reaches an actuator.
    "lighter-ticket-taker": "2026-07-17T00:00",
    # [2026-07-30 (hh)] ⚖️ Counterweight — the book whose own basis-fix note says
    # its "entire reported profit was this artifact". No brain era until now.
    "perps-funding-spread": "2026-07-17T00:00",
    # [2026-07-30 (hd)] 🌾 Yield Harvester. Not a strategy change — an
    # ACCOUNTING one, which is the purest case this table exists for. The
    # lighter_shadow arm's accrual basis was fixed from per-hour to the venue's
    # own per-8h settlement, and for a funding book `accrued` IS the reported
    # P&L and its win/loss call. So every pre-fix close is denominated in a unit
    # the book no longer uses. Measured (hc): 25 closes opened before it total
    # +$62.03; the 57 since total -$0.91. The brain was grading the two
    # together, and `brain-diagnosis` carries an ACTUATOR-bearing
    # `regime_gate` on this book's `long` bucket — a bucket whose entire
    # positive evidence is 3 pre-fix decay wins.
    # NOTE this key also matches the RETIRED HL arm `perps-funding-carry`,
    # harmlessly: it is in LEGACY_BOTS and the liveness filter drops it before
    # any era lookup. Keyed EXACTLY, not by substring — substring-matching this
    # same pair is the (gr) near-miss that would have exempted the living twin.
    "perps-funding-carry": "2026-07-17T00:00",
    # [2026-07-30 (hg)] 💸 Funding Farmer — the SAME accrual-basis fix, and this
    # key covers a REAL-MONEY row. `era_epoch_for` strips both suffixes, so one
    # entry scopes `perps-funding-lighter-lighter` (live) and `-lshadow`.
    # The bot's own accrual comment: the pre-fix figure "reaches the per-trade
    # ledger AND the win/loss call — an inflated carry credit inflates the win
    # rate of a book that COLLECTS carry". The brain grades WIN RATE (post_wr,
    # Wilson bounds, the whole v3 evidence stack) off that ledger, and it has
    # had jurisdiction over the live Farmer's tag since (bb). Measured: the live
    # row's win rate is 63% pooled and 50% in-era; the shadow twin's 56% -> 45%.
    # A brain reasoning about a real-money book from an inflated win rate is the
    # precise failure this table exists to prevent.
    "perps-funding-lighter": "2026-07-17T00:00",
}


def era_epoch_for(bot):
    """Era-start EPOCH for a ledger bot id, or None (= grade all-time).

    [2026-07-23 AUDIT FIX] Two bugs made era-awareness a fleet-wide NO-OP:
    (1) the ledger `bot` field carries a venue/shadow suffix — the family bots
        publish as `strat.bot + "-lshadow"` (lighter_family_bot.py) and live
        rows are `-lighter` — but ERA_START is keyed on the BARE names, so every
        `ERA_START.get(bot)` missed and every bot was graded on its WHOLE
        retained ledger (today's strategy prosecuted for yesterday's crimes —
        exactly what the era block exists to prevent).
    (2) callers compared `str(open_ts) >= era_string`; a space-formatted
        `"2026-07-14 15:.. UTC"` stamp (the listing sniper's format) sorts BELOW
        a `"2026-07-14T00:00"` era at char 10 (`' '` < `'T'`) and was wrongly
        excluded. Comparing PARSED epochs fixes both — every stamp normalises
        through `_epoch` regardless of format.

    [2026-07-30 (hg)] THIRD BUG, same function, and it needed a book whose OWN
    NAME ends in a venue suffix to surface. The strip was
    `.rsplit("-lshadow",1)[0].rsplit("-lighter",1)[0]` — two strips, always —
    and 💸 Funding Farmer is named `perps-funding-lighter`:

        perps-funding-lighter          -> 'perps-funding'          (misses itself)
        perps-funding-lighter-lighter  -> 'perps-funding-lighter'  (hits)
        perps-funding-lighter-lshadow  -> 'perps-funding'          (MISSES)

    So one declaration would have scoped the LIVE row and left the SHADOW twin
    pooled. Now: EXACT match first, then strip exactly ONE trailing suffix. No
    existing entry changes — every other row carries a single suffix, so
    one-strip and two-strip agree on all of them.
    """
    b = str(bot)
    if b in ERA_START:
        era = ERA_START[b]
    else:
        base = b
        for suf in ("-lshadow", "-lighter"):
            if b.endswith(suf):
                base = b[:-len(suf)]
                break
        era = ERA_START.get(base)
    return _epoch(era) if era else None

# [2026-07-15 LIVENESS] Generate hypotheses/diagnoses/multipliers ONLY for
# bots that are still part of the living fleet: not officially retired AND
# with a ledger close inside LIVENESS_DAYS. Before this, retired bots' rows
# never left the fetch window, their patterns re-fired every run, and the
# streak-retire path could never trigger — 10 of the 16 ACTIONABLE entries
# at run 120 prosecuted dead bots (EVIDENCE_AND_LEARNING_REVIEW_2026-07-15).
# Scorecards still print for everyone (analytics), and existing state
# entries decay to 'retired' through the normal 3-run path once generation
# stops. The retired set imports from cleanup_legacy_bots.LEGACY_BOTS — a
# superset of the dashboard's RETIRED_ROWS and already the fleet's one
# maintained list of officially-dead row names.
LIVENESS_DAYS = 7
try:
    from cleanup_legacy_bots import LEGACY_BOTS as _LEGACY
    RETIRED_BOTS = set(_LEGACY)
except Exception:              # laptop/partial checkouts keep working
    RETIRED_BOTS = set()

# ---------------------------------------------------------------------------


def _load_state():
    # Prefer the durable Postgres copy (cloud + survives laptop wipes).
    try:
        import bot_pnl_store as store
        s = store.load_state("learning-brain")
        if s:
            return s, "postgres"
    except Exception:
        pass
    try:
        with open(LOCAL_STATE) as f:
            return json.load(f), "local"
    except Exception:
        return {"runs": 0, "hypotheses": {}}, "fresh"


def _save_state(state):
    """Persist the brain's memory. Returns the list of sinks that ACCEPTED it.

    [2026-07-31 (hx)] A FAILED POSTGRES WRITE IS NO LONGER SILENT. This
    swallowed both the exception AND the False return, and it cost the brain
    three days of memory: `learning-brain.runs` sat at 337 with `updated`
    2026-07-28 while `brain-vitals.run` published 338 fresh every cycle. The
    brain reloaded the stale state each run, recomputed, published healthy
    vitals/mults/diagnosis, and could not remember — so `mult_streaks` froze
    and the 3-run promotion gate became UNREACHABLE. One multiplier survived,
    carrying `streak: 15` from before the freeze, against 20 living bots.
    Root cause was a non-finite float reaching `json.dumps` (see
    `bot_pnl_store.json_safe`); the fix there stops it recurring, and the
    shout here stops the NEXT cause of the same shape being invisible.
    """
    saved = []
    try:
        import bot_pnl_store as store
        if store.save_state("learning-brain", state):
            saved.append("postgres")
        else:
            # LOUD, EVERY RUN — not `_warn_once`. An organ that cannot remember
            # is not degraded, it is amnesiac, and every streak-gated decision
            # it makes is void. The one-shot warning underneath is precisely
            # how this stayed invisible for three days.
            print(f"[bot_learn] BRAIN MEMORY NOT PERSISTED — "
                  f"save_state('learning-brain') returned False. The next run "
                  f"reloads the LAST GOOD state, so mult_streaks cannot "
                  f"advance and the {PROMOTE_RUNS}-run promotion gate is "
                  f"UNREACHABLE.", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[bot_learn] BRAIN MEMORY NOT PERSISTED — save_state raised: "
              f"{e}", flush=True)
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(LOCAL_STATE, "w") as f:
            json.dump(state, f, indent=1)
        saved.append("local")
    except Exception:
        pass
    return saved


def _fetch_trades():
    # Freqtrade bots: the durable bot_trades ledger via the dashboard's HTTP feed.
    with urllib.request.urlopen(TRADES_URL, timeout=30) as r:
        d = json.loads(r.read().decode())
    trades = d if isinstance(d, list) else d.get("trades", d.get("data", []))
    trades = [t for t in trades if isinstance(t, dict) and not t.get("is_open")]
    # [2026-07-05 ALL-BOTS] Perps + sniper close to the paper_trades table, NOT
    # bot_trades, so they were invisible to the brain. Pull them directly (works
    # when DATABASE_URL is set — always true in the cloud container the brain now
    # runs in) and merge, so the fleet's learning covers EVERY bot, not just
    # freqtrade. Guarded: no DB / import error -> just the freqtrade set.
    try:
        import bot_pnl_store as store
        paper = store.fetch_paper_trades(limit=5000)
        if paper:
            trades.extend(t for t in paper if not t.get("is_open"))
    except Exception:
        pass
    return trades


def _bucketize(trades, key):
    out = defaultdict(lambda: {"n": 0, "w": 0, "pnl": 0.0})
    for t in trades:
        k = key(t)
        if k is None:
            continue
        b = out[str(k)]
        b["n"] += 1
        p = t.get("profit_abs") or 0.0
        b["pnl"] += p
        if p > 0:
            b["w"] += 1
    return out


def _dur_bucket(t):
    m = t.get("duration_min") or 0
    return "<30m" if m < 30 else "30-90m" if m < 90 else "90-240m" if m < 240 else ">240m"


def _session(t):
    ts = str(t.get("open_ts") or "")
    if len(ts) < 13:
        return None
    h = int(ts[11:13])
    return f"UTC{h - h % 3:02d}-{h - h % 3 + 2:02d}"


def _load_pulse_history():
    """Rolling mood snapshots from market_pulse.py — local file first, then the
    dashboard's /pulse.json. Returns [] when unavailable (correlation skipped)."""
    try:
        with open(os.path.join(REPORTS_DIR, "market_pulse_state.json")) as f:
            h = json.load(f).get("history", [])
            if h:
                return h
    except Exception:
        pass
    try:
        url = os.environ.get(
            "LEARN_PULSE_URL",
            "https://pnl-dashboard-production-858c.up.railway.app/pulse.json")
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode()).get("history", [])
    except Exception:
        return []


def _mood_at(history, open_ts):
    """Nearest mood snapshot within 2h of a trade's open, else None."""
    if not history or not open_ts:
        return None
    try:
        t = datetime.fromisoformat(str(open_ts).replace("Z", "+00:00"))
    except Exception:
        return None
    best, best_dt = None, 7200.0
    for h in history:
        try:
            ht = datetime.fromisoformat(h["ts"])
        except Exception:
            continue
        d = abs((ht - t).total_seconds())
        if d < best_dt:
            best, best_dt = h, d
    return best


def analyse_bot(bot, trades, pulse_hist=None):
    """Return (scorecard dict, list of candidate hypotheses).

"""
    n = len(trades)
    wins = sum(1 for t in trades if (t.get("profit_abs") or 0) > 0)
    pnl = sum(t.get("profit_abs") or 0 for t in trades)
    wr = wins / n if n else 0.0
    card = {"n": n, "wins": wins, "wr": round(wr * 100, 1), "pnl": round(pnl, 2),
            "by_tag": _bucketize(trades, lambda t: t.get("enter_tag") or "(untagged)"),
            "by_exit": _bucketize(trades, lambda t: t.get("exit_reason")),
            "by_dur": _bucketize(trades, _dur_bucket),
            "by_pair": _bucketize(trades, lambda t: t.get("pair")),
            "by_session": _bucketize(trades, _session)}
    hyps = []

    def hyp(key, kind, evidence, proposal):
        hyps.append({"key": f"{bot}|{key}", "kind": kind,
                     "evidence": evidence, "proposal": proposal})

    # Pair-level bleeders / earners.
    for pair, b in card["by_pair"].items():
        if b["n"] >= MIN_N_FLAG and b["w"] / b["n"] < 0.20 and b["pnl"] < 0:
            hyp(f"pair:{pair}:bleeder", "pair_bleeder",
                f"{pair}: {b['n']} trades, {b['w']/b['n']*100:.0f}% win, ${b['pnl']:+.2f}",
                f"consider dropping {pair} from {bot}'s whitelist")
        if b["n"] >= MIN_N_FLAG and b["w"] / b["n"] >= 0.55 and b["pnl"] > 0:
            hyp(f"pair:{pair}:earner", "pair_earner",
                f"{pair}: {b['n']} trades, {b['w']/b['n']*100:.0f}% win, ${b['pnl']:+.2f}",
                f"{pair} is a consistent earner for {bot} — protect it in any universe change")
    # [2026-07-14b] Entry-mode expectancy moved to the DIAGNOSIS layer in
    # main(): the old blanket "tighten the '{tag}' entry gates" prose fired on
    # any negative bucket regardless of whether the loss lived in the entry,
    # the exit path, fees, regime timing, or the venue — the 92-run 'flip'
    # artifact. diagnose() now names the lever, with drift/fee/regime evidence.
    # Stop-too-tight signature: fast deaths dominate losses AND ROI exits win.
    fast = card["by_dur"].get("<30m", {"n": 0, "w": 0, "pnl": 0})
    roi = card["by_exit"].get("roi", {"n": 0, "w": 0, "pnl": 0})
    if fast["n"] >= MIN_N_FLAG and fast["w"] / max(1, fast["n"]) < 0.10 and \
       roi["n"] >= 3 and roi["w"] == roi["n"]:
        hyp("stop_too_tight", "stop_too_tight",
            f"<30m holds: {fast['n']} trades at {fast['w']/fast['n']*100:.0f}% win "
            f"(${fast['pnl']:+.2f}) while ROI exits are {roi['w']}/{roi['n']} winners",
            f"widen {bot}'s stop / give entries room — winners need time to reach the ladder")
    # Session skew (needs the bigger sample).
    if n >= 60:
        for sess, b in card["by_session"].items():
            if b["n"] >= MIN_N_SESSION and wr > 0 and b["w"] / b["n"] <= wr * 0.4:
                hyp(f"session:{sess}", "session_dead_zone",
                    f"{sess}: {b['n']} trades at {b['w']/b['n']*100:.0f}% win vs {wr*100:.0f}% overall",
                    f"consider blocking new {bot} entries during {sess}")
            if b["n"] >= MIN_N_SESSION and b["w"] / b["n"] >= min(0.95, wr * 1.8) and b["pnl"] > 0:
                hyp(f"session:{sess}:hot", "session_hot_zone",
                    f"{sess}: {b['n']} trades at {b['w']/b['n']*100:.0f}% win vs {wr*100:.0f}% overall",
                    f"{sess} is {bot}'s best session — a future tweak could size up there")
    # Mood correlation (news/social pulse) — only meaningful once market_pulse
    # history overlaps enough trades; accumulates value from 2026-07-03 onward.
    if pulse_hist and n >= 30:
        buckets = {"neg": [0, 0], "mid": [0, 0], "pos": [0, 0]}
        matched = 0
        for t in trades:
            m = _mood_at(pulse_hist, t.get("open_ts"))
            if not m:
                continue
            matched += 1
            mood = m.get("mood") or 0.0
            k = "neg" if mood <= -0.15 else ("pos" if mood >= 0.15 else "mid")
            buckets[k][0] += 1
            if (t.get("profit_abs") or 0) > 0:
                buckets[k][1] += 1
        card["mood_matched"] = matched
        card["by_mood"] = {k: {"n": v[0], "w": v[1]} for k, v in buckets.items()}
        for k, v in buckets.items():
            if v[0] >= 10 and wr > 0:
                bwr = v[1] / v[0]
                if bwr <= wr * 0.5:
                    hyp(f"mood:{k}", "mood_dead_zone",
                        f"'{k}' mood: {v[0]} trades at {bwr*100:.0f}% win vs {wr*100:.0f}% overall",
                        f"consider halving/blocking {bot} entries when market mood is '{k}'")
                elif bwr >= min(0.95, wr * 1.7) and v[1] > 0:
                    hyp(f"mood:{k}:hot", "mood_hot_zone",
                        f"'{k}' mood: {v[0]} trades at {bwr*100:.0f}% win vs {wr*100:.0f}% overall",
                        f"{bot} performs best in '{k}' mood — candidate for informed size-up")
    return card, hyps


# --------------------------------------------------------------------------
# [2026-07-14b] Diagnosis evidence collectors
# --------------------------------------------------------------------------

# [2026-07-17 LIGHTER-FIRST] Post-exit drift is measured on LIGHTER's own 1h
# candles — the venue, and the instrument, the trade actually happened on.
#
# WHAT THIS REPLACED: a Kraken spot OHLC fetch (api.kraken.com), wrong twice
# over — Kraken was RETIRED 14-Jul, and it priced a LIGHTER PERP close off
# KRAKEN SPOT, a different instrument. audit_venue_purity.py flagged the host.
#
# MEASURED before shipping (17-Jul, real ledger, through the brain's own code
# path): the Kraken call was ALREADY unreachable for every living bot. All 409
# recent losers on the 15 alive bots are paper_trades rows, and fetch_paper_
# trades dropped entry_price/exit_price, so _post_exit_drift returned None at
# its rate guard BEFORE any candle fetch. Real coverage was 0 of 409, so the
# candle swap ALONE would have been 0 -> 0. Two things had to move together:
#   * bot_pnl_store.fetch_paper_trades now selects entry_price/exit_price/venue
#     (present in the table since day one, never read) -> open_rate/close_rate.
#   * drift is gated on venue == 'lighter' below, so the CEX listing sniper and
#     the HL-data carry book — both ALIVE — are never priced off Lighter's
#     book. That would repeat the very cross-venue error this commit removes.
#
# LIMITATION, stated plainly: only 3 of the 51 venue='lighter' losers in the
# ledger carry fill prices at all (the funding bot has recorded them since
# 15-Jul; no other Lighter book does). Coverage on today's tape is 0 -> 3. The
# binding constraint is now the SHADOW BROKERS recording fills, not this code.
# Nothing here changes trading: 'brain-diagnosis' has no consumer but the
# dashboard, and compute_stake_mults never reads drift.
LIGHTER_API = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
DRIFT_BARS = 500     # Lighter's HARD cap per /api/v1/candles call -> 500 1h
                     # bars ~= 20.8 days of lookback per pair.
_lighter_cache = {}  # pair -> list[(epoch_sec, o, h, l, c)] | None (per run)
_lighter_markets = None   # {lighter symbol: market_id} | None — fetched once
_drift_no_book = set()    # symbols that resolved to no Lighter book (warned)


def _lighter_market_ids():
    """{lighter symbol -> market_id} from the public order-book list, fetched
    ONCE per run (218 books today) and reused by every pair. {} on any failure,
    which makes every drift lookup return None: a dark feed asserts NOTHING,
    it never fabricates a 0."""
    global _lighter_markets
    if _lighter_markets is not None:
        return _lighter_markets
    out = {}
    try:
        with urllib.request.urlopen(
                f"{LIGHTER_API}/api/v1/orderBookDetails", timeout=20) as r:
            d = json.loads(r.read().decode())
        for b in d.get("order_book_details") or []:
            sym, mid = b.get("symbol"), b.get("market_id")
            if sym is not None and mid is not None:
                out[str(sym)] = int(mid)
    except Exception:
        out = {}
    _lighter_markets = out
    return out


def _drift_market(pair):
    """fleet pair -> (market_id, fleet->lighter PRICE multiplier), or None.

    PRECONDITION: call this ONLY for a trade already known to have executed on
    Lighter (_post_exit_drift checks the venue BEFORE it gets here). The DRIFT
    GAP warning below asserts "yet the trade closed on Lighter" — call it for a
    CEX row and that warning becomes a lie, and every foreign symbol the sniper
    ever touched turns into false alarm noise.

    The ledger spells one Lighter market up to three ways ('BONK', 'kBONK',
    '1000BONK/USDC'), and quotes it bare or suffixed ('ETH' vs 'NEAR/USDC'), so
    strip the quote and route the coin through venues/symbol_map — the fleet's
    one maintained mapping (do NOT fork it here).

    symbol_map returns a SIZE multiplier; PRICE scales INVERSELY, because
    notional is conserved (fleet_price*fleet_size == lighter_price*lighter_size).
    A raw-unit 'BONK' (size x0.001) therefore prices x1000 on the 1000BONK book,
    while 'kBONK'/'1000BONK' already count thousands -> x1. Getting this wrong
    would not fail loudly — it would silently report a ~99900% forward return.

    VERIFIED 17-Jul: all 43 distinct venue='lighter' ledger pairs resolve to a
    live market_id (0 unmappable). NOT verified against real fills: no 1000X row
    carries a recorded price yet, so the x1000 leg rests on symbol_map's
    convention — magnitude agrees (raw BONK ~3.3e-6 x1000 == the 1000BONK
    book's ~0.0033), but the first real 1000X fill should be spot-checked.
    """
    try:
        from venues.symbol_map import to_lighter
    except Exception:
        return None          # no map -> no claim (fail-safe)
    coin = str(pair or "").split("/")[0].strip()
    if not coin:
        return None
    sym, size_mult = to_lighter(coin)
    ids = _lighter_market_ids()
    if not ids:
        return None          # dark market list -> no claim, and no false alarm
    mid = ids.get(sym)
    if mid is None:
        # A REAL absence, not a "not listed here" shrug. The Kraken version
        # cached None for every perp alt Kraken never listed and moved on, which
        # is exactly how the drift sample got silently biased toward a retired
        # venue's spot universe. This trade CLOSED on Lighter, so its book
        # existed: if we cannot find it, that is a delisting or a stale
        # symbol_map, and it gets said OUT LOUD once per symbol.
        if sym not in _drift_no_book:
            _drift_no_book.add(sym)
            print(f"[bot_learn] DRIFT GAP: pair {pair!r} -> Lighter symbol "
                  f"{sym!r} has no book in the live market list, yet the trade "
                  f"closed on Lighter (delisted, or symbol_map is stale?) — no "
                  f"drift evidence for this pair", file=sys.stderr)
        return None
    if not size_mult:
        return None
    return mid, 1.0 / float(size_mult)


def _lighter_hourly(pair):
    """Up to DRIFT_BARS recent 1h candles for `pair` from Lighter's public
    /api/v1/candles, as [(epoch_SECONDS, o, h, l, c)] oldest-first, in LIGHTER
    price units. Cached per pair per run — ONE HTTP call per pair, the same
    budget discipline the Kraken version had (DIAG_DRIFT_MAX_PAIRS caps the
    distinct pairs; drift_budget caps the trades).

    500 bars is the API's hard cap, so the window reaches ~20.8 days back; a
    trade that closed before that simply gets no verdict (None), never a guess.
    `t` arrives in MILLISECONDS — divided here so callers can compare it to
    _epoch()'s seconds. None (also cached) on any failure or unknown book.
    """
    if pair in _lighter_cache:
        return _lighter_cache[pair]
    result = None
    m = _drift_market(pair)
    if m is not None:
        mid = m[0]
        try:
            now = int(datetime.now(timezone.utc).timestamp())
            url = (f"{LIGHTER_API}/api/v1/candles?market_id={mid}"
                   f"&resolution=1h&start_timestamp={now - DRIFT_BARS * 3600}"
                   f"&end_timestamp={now}&count_back={DRIFT_BARS}")
            with urllib.request.urlopen(url, timeout=20) as r:
                d = json.loads(r.read().decode())
            rows = [(int(c["t"]) // 1000, float(c["o"]), float(c["h"]),
                     float(c["l"]), float(c["c"])) for c in (d.get("c") or [])]
            rows.sort(key=lambda x: x[0])
            result = rows or None
        except Exception:
            result = None
    _lighter_cache[pair] = result
    return result


def _epoch(ts):
    try:
        s = str(ts).strip().replace("Z", "+00:00")
        if s.endswith(" UTC"):
            s = s[:-4] + "+00:00"   # listing sniper writes '... 15:05:04 UTC'
        return datetime.fromisoformat(s).timestamp()
    except Exception:
        return None


def _trade_side(trade):
    """'long' | 'short' | None — the direction this trade was actually held in.

    [2026-07-17] `_post_exit_drift` used LONG semantics on every row. Every
    drift-eligible Lighter row is a SHORT (measured: 12/12 with a known side,
    9 on the LIVE Funding Farmer), and for a LOSING short `any(high >= entry)`
    is true BY CONSTRUCTION — so the brain's reclaim rate pinned to 1.0 and its
    stop-too-tight rule fired tautologically. Direction must be READ, never
    assumed.

    Two sources, in order of authority, and NEITHER is a guess:
      1. `enter_tag` — bot_pnl_store sets it from the ledger's `side` column.
         Authoritative, but only 12 of 141 closed Lighter rows have it.
      2. the exit_reason PREFIX — every Lighter book stamps direction into the
         close reason by design: the funding bot writes ("long_"|"short_") +
         reason, the family bot and Ticket Taker write "<side>-<tag>_<exit>"
         (CLAUDE.md). MEASURED: this recovers 112 of the 129 side=NULL rows.
    Anything else -> None -> NO CLAIM. The remaining ~17 (perps-funding-carry's
    bare 'flip'/'decay_paid') stay ungraded rather than guessed: a wrong
    direction does not merely lose a verdict, it INVERTS one.
    """
    tag = str(trade.get("enter_tag") or "").strip().lower()
    if tag in ("long", "short"):
        return tag
    # [2026-07-17] The LENS-tagged shape, and why source 2 could not see it.
    # `bot_pnl_store.split_reason` runs BEFORE this function on every
    # paper_trades row: it partitions the direction prefix OUT of the reason and
    # INTO enter_tag. So a Ticket Taker close stored as `short-divergence_tp`
    # arrives here as enter_tag='short-divergence', exit_reason='tp' — the exact
    # prefix source 2 hunts for has already been moved into the field source 1
    # was only checking for equality. Both missed; every lens-tagged row
    # returned None.
    # MEASURED 17-Jul off the ledger, post-split, through this real function:
    # 'long-breakout_tp' -> None, 'short-divergence_tp' -> None, while the older
    # 'long_roi' -> 'long' still resolved. That is 100% of the LIVE Ticket
    # Taker's closed rows and every lens-tagged family close — i.e. exactly the
    # books the 17-Jul direction fix was written to protect — silently ungraded,
    # while the docstring's "112 of 129" was measured against the RAW `reason`
    # column this function never receives.
    for side in ("long", "short"):
        if tag.startswith(side + "-") or tag.startswith(side + "_"):
            return side
    reason = str(trade.get("exit_reason") or "").strip().lower()
    for side in ("long", "short"):
        # '_' = funding/spread books, '-' = family bot + Ticket Taker lenses.
        # Still load-bearing for UN-split rows: _fetch_trades also merges
        # `bot_trades` over HTTP, which carries the reason as stored.
        if reason.startswith(side + "_") or reason.startswith(side + "-"):
            return side
    return None


def _post_exit_drift(trade):
    """(reclaimed_entry_within_24h, fwd_return_24h) for one closed trade, from
    LIGHTER's public 1h candles after its close — the mechanized version of the
    manual replay that justified the 13-Jul stop widening. None when the trade
    did not happen on Lighter, when rates/candles are missing, or when fewer
    than 6 post-close hours exist yet.

    CONTRACT UNCHANGED (14-Jul): same return shape, same 24-bar window, same
    6-bar floor, same None-on-missing-data. Only the price SOURCE moved — from
    Kraken spot to the Lighter book the trade actually executed on.
    """
    close_ts = _epoch(trade.get("close_ts"))
    close_rate = trade.get("close_rate")
    open_rate = trade.get("open_rate")
    if not (close_ts and close_rate and open_rate):
        return None
    # [2026-07-17] Grade a trade ONLY on its own venue's book. The living fleet
    # also holds CEX-spot listing-sniper rows (BMNR/USDT & friends, most not on
    # Lighter at all) and the HL-data carry book; pricing either off Lighter
    # would be the same cross-venue category error as the Kraken fetch this
    # replaced. Absent/unknown venue -> no claim, never a guess.
    if str(trade.get("venue") or "").strip().lower() != "lighter":
        return None
    candles = _lighter_hourly(trade.get("pair"))
    if not candles:
        return None
    m = _drift_market(trade.get("pair"))
    if m is None:                      # unreachable if candles exist; belt+braces
        return None
    price_mult = m[1]
    # Convert the TRADE's rates into the candles' price basis (see _drift_market:
    # a raw-unit 1000X coin prices x1000 on Lighter). x1 for every ordinary coin.
    open_l = float(open_rate) * price_mult
    close_l = float(close_rate) * price_mult
    # [2026-07-17 FIX #1 — a `[:24]` slice is NOT a 24-HOUR window.] This was
    # `[c for c in candles if c[0] > close_ts][:24]`: the first 24 bars that
    # exist after the close, whatever their dates. Lighter's candle tape only
    # reaches back ~500 hourly bars (~20d), so once a trade is older than the
    # tape, "the 24h after close" silently becomes "the oldest 24 bars we
    # have" — days or MONTHS later. MEASURED on a flat-200 fixture: a trade
    # closed 40d ago yielded a window spanning 19.2-20.1d after close and
    # returned reclaimed=True, fwd=+100%. len(window)==24 in every such case,
    # so the 6-bar floor below can never catch it. Not hypothetical: the fetch
    # bounds by row count (limit=5000), not by date, and the Lighter books have
    # no ERA_START — it starts fabricating verdicts once the ledger passes the
    # tape depth. Bound the window by TIME, which is what it always claimed.
    window = [c for c in candles if close_ts < c[0] <= close_ts + 24 * 3600]
    if len(window) < 6:
        return None
    # [2026-07-17 FIX #2 — the grader was DIRECTION-BLIND on a 100%-SHORT
    # sample.] `reclaimed = any(high >= entry)` and `fwd = last/close - 1` are
    # LONG semantics: "did price come back UP to my entry, and did it keep
    # rising?". Every drift-eligible Lighter row is a SHORT — MEASURED: 12 of
    # 12 closed Lighter trades with a known side are short, NINE of them on
    # perps-funding-lighter-lighter, the LIVE REAL-MONEY Funding Farmer (the
    # funding bot shorts whenever apr>0, which is the venue's resting state).
    # For a LOSING SHORT the exit is ABOVE the entry by definition, so the
    # price is already above entry at close and `any(high >= entry)` is TRUE BY
    # CONSTRUCTION -> reclaim pins to 1.0 -> the "stop too tight" rule
    # (reclaim >= 0.6) fires tautologically and the "stop is fine" rule
    # (reclaim <= 0.35) is UNREACHABLE. The brain was advising on a coin flip
    # it could not lose. Direction is already ON the row (`enter_tag` =
    # 'short'|'long', bot_pnl_store sets it from the ledger's `side`) and was
    # simply never read.
    side = _trade_side(trade)
    if side is None:
        return None
    if side == "short":
        # mirror image: reclaimed = price fell back DOWN to the entry; a
        # favourable move after the close is a FALL, so the return is negated.
        reclaimed = any(lo <= open_l for _, _, _, lo, _ in window)
        fwd = -(window[-1][4] / close_l - 1.0)
    else:
        reclaimed = any(h >= open_l for _, _, h, _, _ in window)
        fwd = window[-1][4] / close_l - 1.0
    return reclaimed, fwd


def _load_regime_history():
    """regime-oracle snapshots (every 30 min since 7-Jul) -> [{'ts': epoch,
    'risk_off': bool}], newest first. [] when the DB isn't reachable."""
    try:
        import bot_pnl_store as store
        hist = store.fetch_state_history("regime-oracle", limit=800)
    except Exception:
        return []
    out = []
    for h in hist or []:
        ts = _epoch(h.get("ts"))
        read = str(((h.get("payload") or {}).get("fleet") or {}).get("read") or "")
        if ts:
            out.append({"ts": ts, "risk_off": read.startswith("risk-off")})
    return out


def _regime_at(regime_hist, open_ts):
    """Nearest oracle snapshot within 1h of a trade's open, else None."""
    t = _epoch(open_ts)
    if not (t and regime_hist):
        return None
    best, best_d = None, 3600.0
    for h in regime_hist:
        d = abs(h["ts"] - t)
        if d < best_d:
            best, best_d = h, d
    return best


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def diagnose(bot, tag, trades, regime_hist, venue_ab, drift_budget,
             venue_fees=None):
    """Classify WHY a negative (bot, tag) bucket loses. Returns a dict with
    'primary', 'proposal', and the evidence, or None below the sample floor.
    Rules are ordered by decisiveness; every piece of evidence is optional and
    its absence just removes that rule from contention (fail-soft)."""
    n = len(trades)
    pnl = sum(t.get("profit_abs") or 0 for t in trades)
    if n < DIAG_MIN_N or pnl >= 0:
        return None
    losers = [t for t in trades if (t.get("profit_abs") or 0) < 0]
    by_exit = _bucketize(trades, lambda t: t.get("exit_reason") or "?")
    gross_loss = sum(-(t.get("profit_abs") or 0) for t in losers) or 1e-9

    worst_exit, worst = max(by_exit.items(), key=lambda kv: -kv[1]["pnl"])
    worst_share = max(0.0, -worst["pnl"]) / gross_loss
    worst_wr = worst["w"] / worst["n"] if worst["n"] else 0.0
    working_exits = [k for k, v in by_exit.items()
                     if v["n"] >= 3 and v["w"] / v["n"] >= 0.6 and v["pnl"] > 0]

    drifts = []
    for t in losers:
        if len(_lighter_cache) >= DIAG_DRIFT_MAX_PAIRS and t.get("pair") not in _lighter_cache:
            continue
        if drift_budget.get("left", 0) <= 0:
            break
        # [2026-07-17 FIX #3] The budget was decremented for EVERY candidate,
        # including rows _post_exit_drift rejects for free. main() diagnoses
        # bots in SORTED order, so the CEX listing-sniper's rows (venue !=
        # lighter, rejected without any fetch) burned the 120-call budget on
        # no-ops, and the LIVE Funding Farmer — the book this evidence exists
        # for — could be starved before it was reached. The venue gate is the
        # cheap, decisive filter (a plain string compare, no network), so it
        # runs HERE and only rows that can actually cost a fetch are charged.
        # _post_exit_drift keeps its own identical gate: it is called from the
        # selftest too and must never price a foreign venue's trade.
        if str(t.get("venue") or "").strip().lower() != "lighter":
            continue
        d = _post_exit_drift(t)
        drift_budget["left"] -= 1
        if d is not None:
            drifts.append(d)
    reclaim = (sum(1 for r, _ in drifts if r) / len(drifts)) if drifts else None
    avg_fwd = (sum(f for _, f in drifts) / len(drifts)) if drifts else None

    med_loser = _median([abs(t.get("profit_ratio") or 0) for t in losers
                         if t.get("profit_ratio") is not None])
    fee_rt = fee_rt_for(bot, venue_fees)
    fee_share = (fee_rt / med_loser) if med_loser else None

    matched = counter = 0
    for t in losers:
        r = _regime_at(regime_hist, t.get("open_ts"))
        if r is not None:
            matched += 1
            counter += 1 if r["risk_off"] else 0
    counter_share = (counter / matched) if matched >= 8 else None

    # [2026-07-28 AUDIT FIX] venue_ab is keyed by BASE name but `bot` here is
    # the SUFFIXED ledger id (e.g. 'perps-funding-lighter-lshadow') — the old
    # lookup missed by construction for every living book. Strip the suffix
    # and read the OTHER arm (a shadow bucket's twin is the live row and
    # vice versa); the bare-id lookup stays as the legacy fallback.
    _ab_base = bot
    for _suf in ("-lshadow", "-lighter"):
        if _ab_base.endswith(_suf):
            _ab_base = _ab_base[: -len(_suf)]
            break
    ab = venue_ab.get(_ab_base) or venue_ab.get(bot) or {}
    if bot.endswith("-lshadow"):
        twin = ab.get("live") or {}
    elif bot.endswith("-lighter"):
        twin = ab.get("shadow") or {}
    else:
        twin = ab.get("shadow") or ab.get("live") or {}
    twin_pnl = twin.get("pnl_abs")
    twin_n = (twin.get("wins") or 0) + (twin.get("losses") or 0)

    ev = {"n": n, "pnl": round(pnl, 2), "worst_exit": worst_exit,
          "worst_share": round(worst_share, 2), "worst_wr": round(worst_wr, 2),
          "working_exits": working_exits, "drift_n": len(drifts),
          "reclaim": None if reclaim is None else round(reclaim, 2),
          "avg_fwd": None if avg_fwd is None else round(avg_fwd, 4),
          "med_loser_ratio": None if med_loser is None else round(med_loser, 4),
          "fee_share": None if fee_share is None else round(fee_share, 2),
          "regime_matched": matched,
          "counter_regime": None if counter_share is None else round(counter_share, 2),
          "twin_pnl": twin_pnl, "twin_n": twin_n}

    def out(primary, proposal):
        return {"primary": primary, "proposal": proposal, "evidence": ev}

    where = f"{bot}/{tag}" if tag != "(untagged)" else bot
    # 1. EXIT TOO TIGHT: a stop-family path eats the losses, almost never wins,
    #    and price reclaims entry after it fires — the exit cuts noise as danger.
    if (worst_exit in STOPPISH and worst_share >= 0.5 and worst_wr <= 0.15
            and reclaim is not None and len(drifts) >= 5
            and reclaim >= 0.6 and (avg_fwd or 0) > -0.005):
        return out("exit_too_tight",
                   f"widen/slow the '{worst_exit}' path on {where} — {reclaim:.0%} of "
                   f"losing exits reclaimed entry within 24h (fwd {avg_fwd:+.1%}); "
                   f"do NOT tighten entries")
    # 2. VENUE/EXECUTION: same signal is profitable on the Lighter twin.
    # [2026-07-17 IMB-29a, verify-corrected] the floor rises to DIAG_MIN_N
    # (was 5) and the message stops dressing a WHOLE-BOOK aggregate up as a
    # per-trade signal. Honest limitation, on the record: twin_pnl is the
    # twin row's lifetime, whole-book pnl_abs (incl. unrealized), not this
    # tag's bucket — a sign comparison across different books is a HINT,
    # not a measurement. The real fix (per-tag era bucket from the twin's
    # own trade ledger) is agenda item 14 follow-up; a per-trade transform
    # here was proven decision-inert (sign-preserving) by the verify pass.
    if twin_pnl is not None and twin_n >= DIAG_MIN_N and pnl < 0 < twin_pnl:
        return out("venue_execution",
                   f"{where}: signal survives on the Lighter twin "
                   f"(whole-book ${twin_pnl:+.2f} over {twin_n} closes — "
                   f"aggregate hint, not per-tag) vs this bucket "
                   f"${pnl:+.2f} — check venue/fees before blaming the "
                   f"strategy")
    # 3. FEE BLEED: median loss is fee-scale — costs, not direction.
    if fee_share is not None and fee_share >= 0.5 and med_loser <= 0.012:
        return out("fee_bleed",
                   f"{where} losses are fee-scale (median loser {med_loser:.2%} vs "
                   f"~{fee_rt:.2%} round-trip) — raise band/edge floors or move venue; "
                   f"signals are not the lever")
    # 4. REGIME TIMING: losses cluster in oracle risk-off windows.
    if counter_share is not None and counter_share >= 0.7:
        return out("regime_timing",
                   f"gate {where} entries on the shared regime — {counter_share:.0%} "
                   f"of matched losses opened during oracle risk-off")
    # 5. ENTRY QUALITY: price kept falling after losing exits — the exits were
    #    right, the entries were wrong. The ONLY case that earns the old
    #    "tighten the entry gates" prose.
    if reclaim is not None and len(drifts) >= 5 and reclaim <= 0.35 and (avg_fwd or 0) < 0:
        return out("entry_quality",
                   f"tighten the '{tag}' entry gates on {bot} — post-exit drift "
                   f"confirms the entries were wrong (only {reclaim:.0%} reclaimed, "
                   f"fwd {avg_fwd:+.1%})")
    return out("mixed_unclear",
               f"{where} is negative but no single lever dominates yet "
               f"(worst path '{worst_exit}' {worst_share:.0%} of losses) — keep sampling")


def derive_actions(hypotheses):
    """[2026-07-21 BRAIN ACTS] Actions from the hypothesis ledger — pure.

    v1: only ACTIONABLE `diag_regime_timing` findings become `regime_gate`
    actions (restrict-only; the consumer additionally requires the oracle to
    read risk-off RIGHT NOW). Candidate/retired findings act on nothing, so
    the existing PROMOTE_RUNS persistence is the streak gate and retirement
    is the automatic release. Nested {bot: {tag: {...}}} — the mults' shape,
    keyed by the ledger identity the consumer already uses."""
    actions = {}
    for hk, e in (hypotheses or {}).items():
        if e.get("status") != "ACTIONABLE" or e.get("kind") != "diag_regime_timing":
            continue
        try:
            hb, htag = hk.split("|tag:", 1)
        except ValueError:
            continue
        actions.setdefault(hb, {})[htag] = {
            "action": "regime_gate", "since_run": e.get("first_run"),
            "seen": e.get("seen")}
    return actions


# [2026-07-21 ORGAN CHANNEL] lens -> (lever, tighten direction sign on the
# registry span). entry_quality's prose has always SAID "tighten the entry
# gates"; this is that sentence as data, for the taker's four lenses only
# (the family bots' bars are not registry levers).
TAKER_TIGHTEN = {
    "divergence": ("taker.div_gap_pp", +1.0),
    "dip": ("taker.dip_range", -1.0),
    "breakout": ("taker.brk_range", +1.0),
    "momentum": ("taker.momo_chg", +1.0),
}


def derive_proposals(hypotheses):
    """[2026-07-21 ORGAN CHANNEL] ACTIONABLE `diag_entry_quality` findings on
    the Ticket Taker become QUEUED lever proposals: one notch tighter
    (0.25 x registry span) on that lens's conviction bar. Pure — returns
    [(lever, sign, bot, tag)]; the caller queues via fleet_proposals and the
    scout tuner enacts only if its replay gate agrees (bounded, TTL'd,
    auto-reverting; brain veto + proprioception stay senior downstream).
    Same streak-hardening as derive_actions: only ACTIONABLE entries (the
    PROMOTE_RUNS persistence) ever leave the ledger."""
    out = []
    for hk, e in (hypotheses or {}).items():
        if e.get("status") != "ACTIONABLE" or e.get("kind") != "diag_entry_quality":
            continue
        try:
            hb, htag = hk.split("|tag:", 1)
        except ValueError:
            continue
        if not hb.startswith("lighter-ticket-taker"):
            continue
        lens = htag.split("-", 1)[1] if "-" in htag else htag
        pair = TAKER_TIGHTEN.get(lens)
        if pair:
            out.append((pair[0], pair[1], hb, htag))
    return out


def compute_stake_mults(cards, state, run_no, era_trades=None, now_ts=None,
                        engine=None):
    """[2026-07-14 L4, 2026-07-16 v3, 2026-07-21 TWO-WAY] Per-(bot, tag)
    stake mults — reduce-only until 21-Jul; now also EXPAND (1.25x/1.5x) on
    brain_stats' mirror bars when the v3 engine runs with BRAIN_MULT_EXPAND
    armed (see MULT_EXPAND above). Expand rides the identical streak gate;
    it has no urgent fast-path by design.

    v2 rule table (frozen in brain_stats.qualify_v2, era trades only):
        n >= MULT_MIN_N,  pnl < 0, wr < 25%          -> 0.50x
        n >= MULT_MIN_N,  pnl < 0, wr < 40%          -> 0.75x
        MULT_SOFT_N <= n < MULT_MIN_N, pnl < 0, wr < 25% -> 0.75x
    v3 keeps the SAME raw-count floors and multiplier grid but judges the
    bucket on decay-weighted evidence: EB-shrunk win rate, Wilson upper
    bound and a weighted t-stat must all agree the tag is bad (brain_stats.
    qualify_v3). Decay means an old bleed heals on its own; pooling means
    ten noisy trades can't outvote what the tag's siblings know.
    Both engines share the streak gate: a reduction must recur on
    PROMOTE_RUNS consecutive runs before it publishes, and a tag that stops
    qualifying drops immediately — the brain forgives as gracefully as it
    forgets.
    Returns (published {bot: {tag: {...}}}, vitals {engine, priors,
    watchlist}). `engine` param overrides the env default (replay harness).
    """
    engine = engine or MULT_ENGINE
    if engine == "v3" and (bstats is None or era_trades is None):
        engine = "v2"
    streaks = state.setdefault("mult_streaks", {})
    seen = set()
    watchlist, priors_out = [], {}

    # v3 evidence layer: decay-weighted stats per (bot, tag) + pool priors.
    wstats = {}
    if engine == "v3":
        for bot, trs in era_trades.items():
            by_tag = defaultdict(list)
            for t in trs:
                tag = str(t.get("enter_tag") or "(untagged)")
                if tag != "(untagged)":
                    by_tag[tag].append(t)
            for tag, bucket in by_tag.items():
                # [2026-07-22] evidence on the EPISODE basis (see EP_GAP_SEC;
                # raw floors keep the trade count inside the stats dict)
                wstats[(bot, tag)] = bstats.weighted_bucket_episodes(
                    bucket, now_ts, HALF_LIFE_DAYS, EP_GAP_SEC)
        tag_pool, bot_pool = defaultdict(list), defaultdict(list)
        for (bot, tag), st in wstats.items():
            tag_pool[tag].append((bot, st))
            bot_pool[bot].append((tag, st))
        all_buckets = [st for st in wstats.values()]

    for bot, c in cards.items():
        for tag, b in c.get("by_tag", {}).items():
            if tag == "(untagged)":
                continue   # no strategy passes this tag — a mult here is pure noise
            n, w, pnl = b["n"], b["w"], b["pnl"]
            wr = w / n if n else 0.0
            ev = {}
            if engine == "v3" and (bot, tag) in wstats:
                st = wstats[(bot, tag)]
                prior = bstats.eb_prior(
                    [s for bb, s in tag_pool.get(tag, []) if bb != bot],
                    [s for tt, s in bot_pool.get(bot, []) if tt != tag],
                    [s for s in all_buckets if s is not st])
                mult, ev = bstats.qualify_v3(st, prior,
                                             min_n=MULT_MIN_N, soft_n=MULT_SOFT_N,
                                             expand=MULT_EXPAND)
                priors_out[f"{bot}|{tag}"] = {
                    "mu": ev["prior_mu"], "kappa": ev["prior_kappa"],
                    "src": ev["prior_src"]}
                # Watchlist: evidence pointing down but not yet at the bar —
                # the operator sees what is WARMING, not just what fired.
                # Advisory only (no actuator), so it may surface below the
                # publish floors (n >= 8 vs MULT_SOFT_N 15).
                if (mult is None and n >= 8 and ev["pnl_w"] < 0
                        and ev["post_wr"] < bstats.SOFT_POST_WR):
                    watchlist.append({"bot": bot, "tag": tag, "n": n, **ev})
                # [2026-07-21 AUDIT] the EXPAND mirror: L4 has published zero
                # mults in its life (measured: mults={} in all 31 payloads
                # over 48h — floors-vs-volume, largest bucket n=25 vs the 30
                # floor), and with two-way shipping today the operator needs
                # to SEE what is warming toward a boost, not just toward a
                # throttle. Advisory only, same sub-floor visibility rule.
                elif (mult is None and MULT_EXPAND and n >= 8
                        and ev["pnl_w"] > 0
                        and ev["post_wr"] > bstats.EXP_SOFT_POST_WR):
                    watchlist.append({"bot": bot, "tag": tag, "n": n,
                                      "warming": "expand", **ev})
            else:
                mult = (bstats.qualify_v2(n, w, pnl, MULT_MIN_N, MULT_SOFT_N)
                        if bstats else None)
                if bstats is None:   # frozen v2 rules, inline fallback
                    if n >= MULT_MIN_N and pnl < 0 and wr < 0.25:
                        mult = 0.5
                    elif n >= MULT_MIN_N and pnl < 0 and wr < 0.40:
                        mult = 0.75
                    elif MULT_SOFT_N <= n < MULT_MIN_N and pnl < 0 and wr < 0.25:
                        mult = 0.75
            if mult is None:
                continue
            key = f"{bot}|{tag}"
            seen.add(key)
            e = streaks.setdefault(key, {"streak": 0, "first_run": run_no})
            # [2026-07-21 AUDIT FIX] the streak is DIRECTION-SCOPED: one
            # counter per (bot,tag) meant 3 reduce-qualifying runs followed
            # by an expand qualification published the 1.25x on its FIRST
            # qualifying run — the exact opposite of (bh)'s "identical 3-run
            # streak gate" for the widening. A direction flip restarts the
            # count; severity moves within a direction keep it.
            dirn = "expand" if mult > 1.0 else "reduce"
            if e.get("dirn") != dirn:
                e["streak"] = 0
                e["dirn"] = dirn
                # a direction flip is a NEW claim — sticky publish (below)
                # must not carry across it
                e.pop("published", None)
            e["streak"] += 1
            e["last_run"] = run_no
            # [2026-07-28 AUDIT FIX] engine-downgrade honesty for ALL v3
            # fields, not just `urgent`: on the v2/fallback path ev={} and
            # the update below left a PRIOR v3 run's evidence keys
            # (post_wr/w_hi/t/priors/n_ep/...) dressed on an entry now
            # stamped engine='v2' — the same stale-label class the 21-Jul
            # fix closed for `urgent`, applied to its siblings.
            if not ev:
                for _k in ("post_wr", "w_hi", "w_lo", "t", "pnl_w", "n_eff",
                           "wr_w", "prior_mu", "prior_kappa", "prior_src",
                           "n_ep", "via"):
                    e.pop(_k, None)
            e.update({"mult": mult, "n": n, "wr": round(wr * 100, 1),
                      "pnl": round(pnl, 2), "engine": engine, **ev})
            # urgent must be re-earned EVERY run: ev={} on the v2/fallback
            # path, so a sticky True from an earlier v3 run would keep
            # fast-pathing straight through the BRAIN_MULT_ENGINE=v2 kill
            # switch (the streak gate exists precisely for that engine).
            e["urgent"] = bool(ev.get("urgent"))
    # Streak resets: qualification must be CONSECUTIVE runs.
    for key in list(streaks):
        if key not in seen:
            del streaks[key]
    # [2026-07-16b FAST-PATH] urgent entries (brain_stats EMER_* bars:
    # overwhelming evidence a streak gate protects nothing against) publish
    # on their FIRST qualifying run — the operator's "genuine no-brainer
    # window". Latency-only: grid/clamp/floors unchanged, and the entry
    # still resets like any other the moment it stops qualifying.
    published = defaultdict(dict)
    urgent_now = []
    for key, e in streaks.items():
        # [2026-07-28 AUDIT FIX] sticky-within-qualification: an EMER entry
        # that published on run 1 (urgent) but softened just past the EMER
        # bar on run 2 (still qualifying the SAME direction, streak 2 < 3)
        # used to DROP from the payload for a full brain interval — a one-run
        # flap back to 1.0x on a bucket the engine still condemned, then
        # republish on run 3. The fast-path was specified latency-only. Once
        # published, an entry keeps publishing while it keeps qualifying in
        # the same direction (a direction flip or a non-qualifying run still
        # clears it — see the dirn reset and the `seen` sweep above).
        if e["streak"] >= PROMOTE_RUNS or e.get("urgent") or e.get("published"):
            bot, tag = key.split("|", 1)
            e["published"] = True
            published[bot][tag] = {k: v for k, v in e.items()
                                   if k not in ("first_run", "last_run")}
            if e.get("urgent") and e["streak"] < PROMOTE_RUNS:
                urgent_now.append(key)
    vitals = {"engine": engine, "priors": priors_out,
              "urgent": urgent_now,
              # [2026-07-28 AUDIT FIX] strongest evidence first, EITHER
              # direction — ascending-t sorted reduce-warming first and cut
              # expand-warming entries at the [:20] cap, burying exactly what
              # the 21-Jul expand-visibility change existed to surface.
              "watchlist": sorted(watchlist,
                                  key=lambda x: -abs(x.get("t") or 0))[:20]}
    return dict(published), vitals


def _publish_stake_mults(published, effective_engine=None):
    """Write the multiplier payload to bot_state (+history) — guarded.

    [2026-07-21 AUDIT FIX] engine/mode are stamped from the engine the run
    ACTUALLY USED (compute_stake_mults downgrades to v2 at runtime when
    brain_stats is unimportable or the era-trades fetch fails), not the
    module constants — a degraded run used to publish engine=v3/mode=two-way
    while computing on v2 rules, an honest-label lie on the exact field the
    immune organ's engine-mismatch detector reads."""
    eng = effective_engine or MULT_ENGINE
    try:
        import bot_pnl_store as store
        payload = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "ttl_sec": MULT_TTL_SEC,
                   # [2026-07-21] two-way when the expand side is armed (v3 +
                   # BRAIN_MULT_EXPAND) — the mode string is the honest label
                   # consumers and dashboards read, not a behavior switch.
                   "mode": ("two-way" if (MULT_EXPAND and eng == "v3")
                            else "reduce-only"),
                   "min_n": MULT_MIN_N, "promote_runs": PROMOTE_RUNS,
                   "engine": eng, "half_life_days": HALF_LIFE_DAYS,
                   "mults": published}
        ok = store.save_state(MULT_KEY, payload)
        try:
            store.save_history(MULT_KEY, payload)
        except Exception:
            pass
        return bool(ok)
    except Exception:
        return False


def venue_ab_report():
    """[2026-07-14 REACH; 2026-07-28 RE-KEYED for the living fleet] A/B pairs
    from bot_pnl, keyed by BASE name.

    The original pairing required a BARE-named paper row as the anchor — and
    every bare-named twin retired with the 14-Jul Kraken cut, so venue_ab has
    been {} for two weeks and diagnose()'s venue_execution rule was dead with
    it (double-dead: the rule also looked the map up by the SUFFIXED ledger
    id — fixed there too). The living fleet's real A/B is '-lshadow' vs
    '-lighter' on the same base (Farmer + Ticket Taker: same code, shadow
    marks vs real fills — a persistent gap is execution/funding, not
    signal). Both pairings emitted; legacy paper anchor kept for any bare
    row that ever publishes again. gap_pnl is live-minus-shadow on a living
    pair (negative = live underperforms its model)."""
    try:
        import bot_pnl_store as store
        rows = store.fetch_bot_pnl()
        if not rows:
            return {}
        by_bot = {r["bot"]: r for r in rows}

        def _pick(row):
            return {"equity": row.get("equity"), "pnl_abs": row.get("pnl_abs"),
                    "wins": row.get("wins"), "losses": row.get("losses"),
                    "open": row.get("open_trades")}

        out = {}
        for name, r in by_bot.items():
            for suffix in ("-lshadow", "-lighter"):
                if not name.endswith(suffix):
                    continue
                base = name[: -len(suffix)]
                twin = by_bot.get(base)
                if not twin:
                    continue
                e = out.setdefault(base, {"paper": _pick(twin)})
                e["shadow" if suffix == "-lshadow" else "live"] = _pick(r)
                try:
                    e["gap_pnl"] = round((r.get("pnl_abs") or 0) - (twin.get("pnl_abs") or 0), 2)
                except Exception:
                    pass
        # the LIVING twins: '-lshadow' vs '-lighter' on one base
        for name, r in by_bot.items():
            if not name.endswith("-lshadow"):
                continue
            base = name[: -len("-lshadow")]
            live = by_bot.get(base + "-lighter")
            if live is None:
                continue
            e = out.setdefault(base, {})
            e["shadow"] = _pick(r)
            e["live"] = _pick(live)
            try:
                e["gap_pnl"] = round((live.get("pnl_abs") or 0)
                                     - (r.get("pnl_abs") or 0), 2)
            except Exception:
                pass
        return out
    except Exception:
        return {}


def grade_scout_lenses(max_snapshots=2200):
    """[2026-07-15 LENS-FORWARD] Counterfactual per-lens scoreboard: EVERY
    ticket the scout has emitted (bot_state_history 'lighter-market'), graded
    on forward returns from the snapshots' own liquid-book marks ('marks',
    present since 15 Jul). The taker fills ~6 tickets; the scout emits ~5,000
    a day — this is the sample size lens verdicts actually need. Shorts
    (divergence side) are sign-flipped. Returns {lens: {n4h, hit4h,
    avg4h_pct, ...}} or {} when history/marks are unavailable."""
    import bisect
    try:
        import bot_pnl_store as store
        hist = store.fetch_state_history("lighter-market", limit=max_snapshots)
    except Exception:
        return {}
    snaps = []
    for h in reversed(hist or []):          # newest-first -> oldest-first
        p = h.get("payload") or {}
        marks = p.get("marks") or {}
        if not marks:
            continue                        # pre-15-Jul snapshots carry no prices
        try:
            ts = datetime.fromisoformat(
                str(h.get("ts")).replace("Z", "+00:00")).timestamp()
        except (ValueError, TypeError):
            continue
        snaps.append((ts, marks, p.get("tickets") or {}))
    if len(snaps) < 3:
        return {}
    times = [s[0] for s in snaps]
    last_ts = times[-1]

    def mark_at(t_target, sym, tol=1800):
        i = bisect.bisect_left(times, t_target)
        for j in (i, i + 1, i - 1):
            if 0 <= j < len(snaps) and abs(times[j] - t_target) <= tol:
                m = snaps[j][1].get(sym)
                if m:
                    return m
        return None

    # [2026-07-16 v3 EPISODES] The scout re-emits a live ticket every cycle,
    # so raw counts are serially correlated (~200 emissions of one breakout
    # are one market opinion, not 200). Group each (lens, sym)'s emissions
    # into EPISODES (gap > EPISODE_GAP_SEC starts a new one) and grade the
    # FIRST emission of each — the moment a taker could first have acted.
    # RAW fields (n4h/hit4h/avg4h_pct...) keep their exact v2 semantics:
    # the taker's veto floor (TT_LENS_VETO_MIN_N) and the tuner were
    # calibrated on them. Episode stats land as NEW fields (eps*/ehit*/
    # eavg*, Wilson bounds, sym diversity) for consumers to adopt at review.
    emissions = defaultdict(list)      # (lens, sym) -> [ts, ...]
    for ts, marks, tickets in snaps:
        for lens, arr in (tickets or {}).items():
            for t in arr or []:
                if t.get("sym"):
                    emissions[(lens, t["sym"])].append(ts)
    ep_firsts = {}
    if bstats is not None:
        ep_firsts = {k: bstats.episode_firsts(v) for k, v in emissions.items()}

    agg = {}
    eagg = {}
    esyms = {}
    # [2026-07-29 (fn) BY-SIDE] The same episode aggregation, additionally keyed
    # by (lens, SIDE). A lens that emits BOTH directions gets ONE pooled grade
    # today, and `divergence` is 69% long / 31% short — so the losing long side
    # drags the pool under the veto's 0.500 bar and takes the winning short side
    # with it. That matters because a consumer can be restricted to ONE side
    # (the live Ticket Taker under TT_BULL_MODE trades short-divergence ONLY),
    # in which case the pooled grade is a verdict on a population it does not
    # trade. Published as a NESTED `by_side` block; every existing field keeps
    # its exact meaning, so no current consumer changes behaviour.
    esagg = {}
    essyms = {}
    for ts, marks, tickets in snaps:
        for lens, arr in (tickets or {}).items():
            for t in arr or []:
                sym = t.get("sym")
                entry = marks.get(sym)
                if not sym or not entry:
                    continue
                side = "short" if str(t.get("side", "long")) == "short" else "long"
                sign = -1.0 if side == "short" else 1.0
                is_first = ts in ep_firsts.get((lens, sym), ())
                for label, hsec in LENS_HORIZONS:
                    if ts + hsec > last_ts + 900:
                        continue            # horizon hasn't elapsed yet
                    px = mark_at(ts + hsec, sym)
                    if not px:
                        continue
                    fwd = sign * (px / entry - 1.0)
                    g = agg.setdefault(lens, {}).setdefault(
                        label, {"n": 0, "hit": 0, "sum": 0.0})
                    g["n"] += 1
                    g["hit"] += 1 if fwd > 0 else 0
                    g["sum"] += fwd
                    if is_first:
                        ge = eagg.setdefault(lens, {}).setdefault(
                            label, {"n": 0, "hit": 0, "sum": 0.0})
                        ge["n"] += 1
                        ge["hit"] += 1 if fwd > 0 else 0
                        ge["sum"] += fwd
                        esyms.setdefault(lens, set()).add(sym)
                        gs = esagg.setdefault((lens, side), {}).setdefault(
                            label, {"n": 0, "hit": 0, "sum": 0.0})
                        gs["n"] += 1
                        gs["hit"] += 1 if fwd > 0 else 0
                        gs["sum"] += fwd
                        essyms.setdefault((lens, side), set()).add(sym)
    out = {}
    for lens, hz in agg.items():
        o = {}
        for label, g in hz.items():
            o[f"n{label}h"] = g["n"]
            o[f"hit{label}h"] = round(g["hit"] / g["n"], 3) if g["n"] else None
            o[f"avg{label}h_pct"] = (round(100.0 * g["sum"] / g["n"], 3)
                                     if g["n"] else None)
        for label, g in (eagg.get(lens) or {}).items():
            o[f"eps{label}h"] = g["n"]
            if g["n"]:
                ehit = g["hit"] / g["n"]
                o[f"ehit{label}h"] = round(ehit, 3)
                o[f"eavg{label}h_pct"] = round(100.0 * g["sum"] / g["n"], 3)
                if bstats is not None and label == 4:
                    lo, hi = bstats.wilson(ehit, g["n"])
                    o["ehit4h_lo"] = round(lo, 3)
                    o["ehit4h_hi"] = round(hi, 3)
        o["n_syms"] = len(esyms.get(lens) or ())
        out[lens] = o
    # [2026-07-29 (fn)] attach the per-side episode grades. Same field names as
    # the lens level so a consumer can hand either dict to the SAME evidence
    # reader; only lenses that actually emitted that side get a block, so a
    # single-direction lens (breakout/dip/momentum are long-only) carries just
    # the one and a consumer's fallback never fires spuriously.
    for (lens, side), hz in esagg.items():
        if lens not in out:
            continue
        s = {}
        for label, g in hz.items():
            if not g["n"]:
                continue
            ehit = g["hit"] / g["n"]
            s[f"eps{label}h"] = g["n"]
            s[f"ehit{label}h"] = round(ehit, 3)
            s[f"eavg{label}h_pct"] = round(100.0 * g["sum"] / g["n"], 3)
            if bstats is not None and label == 4:
                lo, hi = bstats.wilson(ehit, g["n"])
                s["ehit4h_lo"] = round(lo, 3)
                s["ehit4h_hi"] = round(hi, 3)
        if s:
            s["n_syms"] = len(essyms.get((lens, side)) or ())
            out[lens].setdefault("by_side", {})[side] = s
    return out


def venue_ab_lines(venue_ab):
    """Render the venue A/B section: the same strategy on its paper twin vs its
    Lighter arm. Extracted from main() so a test can bind the CODE THAT RUNS —
    an inline block is only ever testable by a copy, and a copy of the rule is
    not the rule (this repo has paid for that lesson repeatedly).

    [2026-08-01 (hw)] THE BUG THIS EXISTS TO PIN: the loop guarded `arm in e`
    and then dereferenced `e["paper"]` UNGUARDED. Written when every book had a
    KRAKEN PAPER twin; Kraken was RETIRED 14-Jul, so no book has a paper arm
    any more and the first book carrying a shadow/live arm raised
    KeyError('paper'). It killed main() before `_save_state`, so the brain
    recomputed everything, published its four read-only keys, and then forgot
    the run — every cycle, invisibly, behind `|| true`.
    """
    out = []
    for base, e in sorted((venue_ab or {}).items()):
        if not isinstance(e, dict) or "paper" not in e:
            continue                 # no paper twin -> nothing to compare
        p = e["paper"]
        for arm in ("shadow", "live"):
            s = e.get(arm)
            if not s:
                continue
            out.append(
                f"- {base}: paper ${p.get('pnl_abs') or 0:+.2f} "
                f"({p.get('wins') or 0}W/{p.get('losses') or 0}L) vs {arm} "
                f"${s.get('pnl_abs') or 0:+.2f} "
                f"({s.get('wins') or 0}W/{s.get('losses') or 0}L)")
    return out


def main():
    trades = _fetch_trades()
    # [2026-07-16 v3] one epoch parse per trade — decay weighting and the
    # liveness check both key off it.
    for t in trades:
        t["_close_epoch"] = _epoch(t.get("close_ts"))
    state, src = _load_state()
    state["runs"] = int(state.get("runs", 0)) + 1
    run_no = state["runs"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    by_bot = defaultdict(list)
    for t in trades:
        by_bot[t.get("bot", "?")].append(t)

    pulse_hist = _load_pulse_history()
    now_ts = datetime.now(timezone.utc).timestamp()
    cards, all_hyps, era_trades = {}, [], {}
    for bot, trs in sorted(by_bot.items()):
        # [2026-07-23 AUDIT FIX] suffix-stripped, epoch-compared (see
        # era_epoch_for) — the old `ERA_START.get(bot)` + string compare made
        # era-filtering a fleet-wide no-op.
        _era_base = str(bot).rsplit("-lshadow", 1)[0].rsplit("-lighter", 1)[0]
        era = ERA_START.get(_era_base)
        era_epoch = era_epoch_for(bot)
        trs_era = ([t for t in trs if (_epoch(t.get("open_ts")) or 0.0) >= era_epoch]
                   if era_epoch else trs)
        era_trades[bot] = trs_era
        cards[bot], hyps = analyse_bot(bot, trs_era, pulse_hist)
        cards[bot]["n_lifetime"] = len(trs)
        cards[bot]["era"] = era or "all-time"
        # [2026-07-15 LIVENESS] retired or quiet > LIVENESS_DAYS -> scorecard
        # only; no new hypotheses (state entries decay via the normal path).
        last_close = max((e for e in (_epoch(t.get("close_ts")) for t in trs)
                          if e is not None), default=None)
        alive = (bot not in RETIRED_BOTS and last_close is not None
                 and now_ts - last_close <= LIVENESS_DAYS * 86400)
        cards[bot]["alive"] = alive
        if alive:
            all_hyps.extend(hyps)

    # [2026-07-14b DIAGNOSIS] For every negative (bot, tag) bucket at sample
    # size, name the LEVER (entry / exit / fee / regime / venue) instead of the
    # old blanket entry-gate prose. Reuses the same hypothesis keys
    # ('{bot}|tag:{tag}') so existing streaks carry over — the prose upgrades,
    # the persistence memory survives.
    venue_ab = venue_ab_report()
    regime_hist = _load_regime_history()
    # [2026-07-30] the venue's MEASURED fee schedule, from the scout. Without
    # this load the whole fee_rt_for() path would be another fed-by-nobody
    # consumer: it would silently take the dark-scout fallback forever and the
    # "measured, not asserted" claim above would be false. Fail-safe: any
    # doubt leaves `venue_fees` None and fee_rt_for uses the declared
    # per-venue fallback — never another venue's constant.
    venue_fees = None
    try:
        _lm = store.load_state("lighter-market") or {}
        _f = _lm.get("fees")
        if isinstance(_f, dict) and _f.get("taker") is not None:
            venue_fees = _f
            print(f"  venue fees (measured, {_f.get('n_books')} books): "
                  f"taker {_f['taker']} maker {_f.get('maker')}")
    except Exception:  # noqa: BLE001
        venue_fees = None
    drift_budget = {"left": 120}   # bounds Lighter candle work per run
    diagnoses = {}
    for bot, trs in sorted(era_trades.items()):
        if not (cards.get(bot) or {}).get("alive"):
            continue   # [2026-07-15 LIVENESS] don't diagnose the dead
        buckets = defaultdict(list)
        for t in trs:
            buckets[str(t.get("enter_tag") or "(untagged)")].append(t)
        for tag, bucket in sorted(buckets.items()):
            d = diagnose(bot, tag, bucket, regime_hist, venue_ab,
                         drift_budget, venue_fees=venue_fees)
            if d is None:
                continue
            diagnoses[f"{bot}|{tag}"] = d
            b = d["evidence"]
            all_hyps.append({
                "key": f"{bot}|tag:{tag}", "kind": f"diag_{d['primary']}",
                "evidence": (f"'{tag}': n={b['n']}, ${b['pnl']:+.2f}; worst path "
                             f"'{b['worst_exit']}' ({b['worst_share']:.0%} of losses, "
                             f"wr {b['worst_wr']:.0%}); drift n={b['drift_n']} "
                             f"reclaim={b['reclaim']} fwd={b['avg_fwd']}; "
                             f"fee_share={b['fee_share']}; "
                             f"counter_regime={b['counter_regime']}"),
                "proposal": d["proposal"],
            })

    # Reconcile hypotheses with cumulative state: persistence -> promotion.
    seen_now = {h["key"] for h in all_hyps}
    hstate = state.setdefault("hypotheses", {})
    for h in all_hyps:
        e = hstate.setdefault(h["key"], {"first_run": run_no, "seen": 0, "status": "candidate"})
        # [2026-07-21 AUDIT FIX x2, promotion semantics tightened now that
        # ACTIONABLE findings ACT (the (bc) regime_gate):
        #   RESURRECT — a retired pattern that REAPPEARS starts a fresh
        #   candidacy (seen=0, new first_run) instead of staying dead
        #   forever: one fade cycle used to permanently disarm the actuator
        #   for that finding, because 'retired' was terminal.
        #   CONSECUTIVE — a candidate's persistence count restarts after a
        #   missed run: seen accumulated across gaps (seen on runs 1,3,5
        #   promoted), so the gate was weaker than the streak gate it
        #   mirrors. ACTIONABLE entries keep retirement as their fade path.
        if e.get("status") == "retired":
            e.update({"status": "candidate", "seen": 0, "first_run": run_no})
        elif (e.get("status") == "candidate"
              and e.get("last_run") is not None
              and run_no - e["last_run"] > 1):
            e["seen"] = 0
        e["seen"] += 1
        e["last_run"] = run_no
        e["evidence"] = h["evidence"]
        e["proposal"] = h["proposal"]
        e["kind"] = h["kind"]
        if e["seen"] >= PROMOTE_RUNS and e["status"] == "candidate":
            e["status"] = "ACTIONABLE"
    for k, e in hstate.items():
        if k not in seen_now and e.get("status") != "retired" and \
           run_no - e.get("last_run", run_no) >= PROMOTE_RUNS:
            e["status"] = "retired"   # pattern faded — the brain forgets gracefully

    actionable = {k: e for k, e in hstate.items() if e["status"] == "ACTIONABLE"}
    candidates = {k: e for k, e in hstate.items() if e["status"] == "candidate"}

    # [2026-07-14 L4] Numeric stake multipliers — computed every run, streak-
    # gated, published reduce-only. Strategies consume via fleet_bus.
    # [2026-07-15 LIVENESS] living bots only: a throttle for a dead bot has
    # no consumer and would only be noise on the bus.
    alive_cards = {b: c for b, c in cards.items() if c.get("alive")}
    alive_trades = {b: era_trades[b] for b in alive_cards if b in era_trades}
    published_mults, mult_vitals = compute_stake_mults(
        alive_cards, state, run_no, era_trades=alive_trades, now_ts=now_ts)
    mults_saved = _publish_stake_mults(published_mults,
                                       effective_engine=mult_vitals.get("engine"))

    # [2026-07-16 v3 REGIME SPLITS] Per-(bot, tag) win/pnl conditioned on the
    # oracle regime at entry — the evidence that decides whether a tag is
    # bad or just badly timed. ADVISORY: published on brain-vitals for the
    # dashboard/board; no actuator reads it yet.
    regime_splits = {}
    for bot in sorted(alive_trades):
        buckets = defaultdict(list)
        for t in alive_trades[bot]:
            tag = str(t.get("enter_tag") or "(untagged)")
            if tag != "(untagged)":
                buckets[tag].append(t)
        for tag, bucket in buckets.items():
            if len(bucket) < DIAG_MIN_N:
                continue
            split = {"risk_on": {"n": 0, "w": 0, "pnl": 0.0},
                     "risk_off": {"n": 0, "w": 0, "pnl": 0.0}, "unmatched": 0}
            for t in bucket:
                r = _regime_at(regime_hist, t.get("open_ts"))
                if r is None:
                    split["unmatched"] += 1
                    continue
                s = split["risk_off" if r["risk_off"] else "risk_on"]
                s["n"] += 1
                s["pnl"] = round(s["pnl"] + (t.get("profit_abs") or 0.0), 2)
                if (t.get("profit_abs") or 0) > 0:
                    s["w"] += 1
            if split["risk_on"]["n"] + split["risk_off"]["n"] >= 8:
                regime_splits[f"{bot}|{tag}"] = split

    # [2026-07-14 REACH] Venue A/B computed above (feeds diagnosis too).
    state["venue_ab"] = venue_ab

    # [2026-07-14b] Publish the diagnoses — same freshness contract as the
    # multipliers. Advisory: consumers are humans + the dashboard; nothing
    # trades on this directly.
    # [2026-07-21 BRAIN ACTS — operator: "the brain also needs to be able to
    # implement its findings"] ...no longer entirely true: the payload now
    # carries ACTIONS derived from the hypothesis ledger's ACTIONABLE entries
    # (streak-hardened by the existing PROMOTE_RUNS persistence — a finding
    # must recur across consecutive runs before it acts, and a retired
    # finding's action lifts automatically). v1 is ONE action class,
    # restrict-only: `regime_gate` from diag_regime_timing — the diagnosis
    # whose evidence is "counter_share >= 0.7 of matched losses opened during
    # oracle risk-off" (n matched >= 8, bucket n >= DIAG_MIN_N). The consumer
    # (fleet_bus.entry_regime_gated -> family bot) skips NEW entries for that
    # (bot, tag) ONLY WHILE the same oracle currently reads risk-off — the
    # gate acts on exactly the signal the evidence measured, never a
    # different one (the SPY-vs-btc_regime_up lesson, item 18). Kill switch:
    # BRAIN_ACTIONS_MODE=advisory publishes the actions but consumers stand
    # down (the FLEET_RISK_MODE pattern). Expand-direction diagnosis classes
    # (exit_too_tight etc.) stay advisory — widening needs replay/backtest
    # per doctrine, and this door is restrict-only by construction.
    actions = derive_actions(state.get("hypotheses"))
    try:
        import bot_pnl_store as store
        diag_payload = {"updated": now, "ttl_sec": MULT_TTL_SEC,
                        "diagnoses": diagnoses,
                        "actions": actions,
                        "actions_mode": os.environ.get("BRAIN_ACTIONS_MODE",
                                                       "enforce")}
        store.save_state(DIAG_KEY, diag_payload)
        try:
            store.save_history(DIAG_KEY, diag_payload)
        except Exception:
            pass
    except Exception:
        pass
    # [2026-07-21 ORGAN CHANNEL] entry_quality findings on the taker QUEUE a
    # tighter-bar proposal (fleet_proposals) — the scout tuner enacts only if
    # its replay gate agrees. Failure-neutral: a dark channel drops nothing
    # but the appetite.
    try:
        import fleet_proposals as _fp
        import fleet_tuning as _ft
        import lighter_ticket_taker as _tt
        _defaults = {"taker.div_gap_pp": _tt.DIV_GAP_PP,
                     "taker.dip_range": _tt.DIP_RANGE,
                     "taker.brk_range": _tt.BRK_RANGE,
                     "taker.momo_chg": _tt.MOMO_CHG}
        _want = {}
        for _lever, _sign, _hb, _htag in derive_proposals(state.get("hypotheses")):
            _spec = _ft.LEVERS.get(_lever) or {}
            if _spec.get("lo") is None or _lever not in _defaults:
                continue
            _want[_lever] = {
                "value": _defaults[_lever] + _sign * 0.25 * (_spec["hi"] - _spec["lo"]),
                "direction": "restrict",
                "reason": f"ACTIONABLE entry_quality on {_hb} {_htag} — "
                          f"tighten the lens's conviction bar one notch",
                "evidence": "hypothesis ledger (PROMOTE_RUNS-hardened); "
                            "replay gate decides"}
        if _want:
            _fp.propose(_want, set_by="brain")
    except Exception:  # noqa: BLE001
        pass
    state["diagnoses"] = diagnoses

    # [2026-07-15 LENS-FORWARD] grade the scout's lenses on every ticket and
    # publish for the taker (restrict-only veto) + dashboard. Failure-neutral.
    lens_forward = {}
    try:
        lens_forward = grade_scout_lenses() or {}
    except Exception:
        lens_forward = {}
    state["lens_forward"] = lens_forward
    if lens_forward:
        try:
            import bot_pnl_store as store
            lf_payload = {"updated": now, "ttl_sec": MULT_TTL_SEC,
                          "lenses": lens_forward}
            store.save_state(LENS_FWD_KEY, lf_payload)
            try:
                store.save_history(LENS_FWD_KEY, lf_payload)
            except Exception:
                pass
        except Exception:
            pass

    # [2026-07-16 v3 VITALS] The engine's own instrumentation: which prior
    # every graded bucket shrank toward, what is WARMING toward a throttle,
    # regime splits, lens episode summaries, and the exact bars in force.
    # Advisory + fail-soft: a vitals failure must never cost a mult publish
    # (which already happened above).
    vitals_payload = {
        "updated": now, "ttl_sec": MULT_TTL_SEC, "run": run_no,
        "engine": mult_vitals.get("engine"),
        "half_life_days": HALF_LIFE_DAYS,
        "bars": ({"hard_post_wr": bstats.HARD_POST_WR, "hard_w_hi": bstats.HARD_W_HI,
                  "hard_t": bstats.HARD_T, "soft_post_wr": bstats.SOFT_POST_WR,
                  "soft_w_hi": bstats.SOFT_W_HI, "soft_t": bstats.SOFT_T}
                 if bstats else {}),
        "priors": mult_vitals.get("priors") or {},
        "urgent": mult_vitals.get("urgent") or [],
        "watchlist": mult_vitals.get("watchlist") or [],
        "regime_splits": regime_splits,
        "lens_episodes": {lens: {"eps4h": o.get("eps4h"), "ehit4h": o.get("ehit4h"),
                                 "eavg4h_pct": o.get("eavg4h_pct"),
                                 "ehit4h_lo": o.get("ehit4h_lo"),
                                 "n_syms": o.get("n_syms")}
                          for lens, o in (lens_forward or {}).items()},
        "counts": {"bots_alive": sum(1 for c in cards.values() if c.get("alive")),
                   "mults_published": sum(len(t) for t in published_mults.values()),
                   "watchlist": len(mult_vitals.get("watchlist") or []),
                   "diagnoses": len(diagnoses)},
    }
    try:
        import bot_pnl_store as store
        # [(hw)] a HEALTHY run clears the crash flag. A sticky error would
        # page once and then mean nothing — the detector must be able to say
        # "recovered", not only "died".
        vitals_payload["healthy"] = True
        vitals_payload.pop("error", None)
        vitals_payload.pop("error_where", None)
        store.save_state(VITALS_KEY, vitals_payload)
        try:
            store.save_history(VITALS_KEY, vitals_payload)
        except Exception:
            pass
    except Exception:
        pass
    state["vitals"] = {k: vitals_payload[k] for k in
                       ("engine", "half_life_days", "counts")}

    # ---- write lessons_latest.md ------------------------------------------
    os.makedirs(REPORTS_DIR, exist_ok=True)
    L = [f"# Fleet lessons — run {run_no} @ {now} (state: {src})", ""]
    L.append("Generated by bot_learn.py from the durable trade ledger. PROPOSALS ONLY — "
             "nothing here changes a bot until a human (or the trainer's promotion "
             "path) ships it.\n")
    # Only show entries the CURRENT era's data still supports this run —
    # stale ones decay to retired quietly instead of nagging.
    live_act = {k: e for k, e in actionable.items() if e.get("last_run") == run_no}
    live_cand = {k: e for k, e in candidates.items() if e.get("last_run") == run_no}
    if live_act:
        L.append("## ** ACTIONABLE ** (persisted across ≥%d runs of current-era data)" % PROMOTE_RUNS)
        for k, e in sorted(live_act.items()):
            L.append(f"- **{e['proposal']}**  \n  evidence: {e['evidence']} "
                     f"(seen {e['seen']} runs since run {e['first_run']})")
        L.append("")
    if live_cand:
        L.append("## Candidate hypotheses (watching — not yet actionable)")
        for k, e in sorted(live_cand.items()):
            L.append(f"- {e['proposal']}  \n  evidence: {e['evidence']} (seen {e['seen']}/{PROMOTE_RUNS})")
        L.append("")
    # [2026-07-14 L4] Published stake multipliers — the brain's live handle
    # on sizing. Empty section = every tag is trading at full stake.
    L.append("## Stake multipliers in force (bot_state '%s', reduce-only, engine %s)"
             % (MULT_KEY, mult_vitals.get("engine")))
    if published_mults:
        for bot, tags in sorted(published_mults.items()):
            for tag, m in sorted(tags.items()):
                v3ev = (f", post_wr={m['post_wr']}, t={m['t']}, "
                        f"prior={m.get('prior_src')}({m.get('prior_mu')})"
                        if m.get("post_wr") is not None else "")
                L.append(f"- **{bot} / {tag} -> {m['mult']}x**  "
                         f"(n={m['n']}, wr={m['wr']}%, pnl ${m['pnl']:+.2f}, "
                         f"streak {m['streak']} runs{v3ev})")
    else:
        L.append("- none — no tag currently clears the floor "
                 f"(n>={MULT_SOFT_N}, negative pnl, {PROMOTE_RUNS} consecutive runs)")
    L.append("")
    # [2026-07-16 v3] What is WARMING toward a throttle + regime splits.
    wl = mult_vitals.get("watchlist") or []
    if wl:
        L.append("## Watchlist (negative evidence below the bar — not throttled)")
        for e in wl[:10]:
            L.append(f"- {e['bot']} / {e['tag']}: n={e['n']} n_eff={e['n_eff']} "
                     f"post_wr={e['post_wr']} t={e['t']} pnl_w=${e['pnl_w']:+.2f} "
                     f"(prior {e['prior_src']} {e['prior_mu']})")
        L.append("")
    stark = {k: s for k, s in regime_splits.items()
             if s["risk_on"]["n"] >= 4 and s["risk_off"]["n"] >= 4}
    if stark:
        L.append("## Regime splits (entry-time oracle read — advisory)")
        for k, s in sorted(stark.items()):
            on, off = s["risk_on"], s["risk_off"]
            L.append(f"- {k}: risk-on {on['w']}/{on['n']} ${on['pnl']:+.2f} · "
                     f"risk-off {off['w']}/{off['n']} ${off['pnl']:+.2f}")
        L.append("")
    # [2026-07-15 LENS-FORWARD] scout lens scoreboard.
    if lens_forward:
        L.append("## Scout lens forward returns (counterfactual — EVERY ticket, "
                 "not just taker fills)")
        for lens, o in sorted(lens_forward.items()):
            ep = (f" · EPISODES 4h n={o.get('eps4h')} hit={o.get('ehit4h')} "
                  f"[{o.get('ehit4h_lo')},{o.get('ehit4h_hi')}] "
                  f"avg={o.get('eavg4h_pct')}% syms={o.get('n_syms')}"
                  if o.get("eps4h") else "")
            L.append(f"- **{lens}**: 4h n={o.get('n4h', 0)} "
                     f"hit={o.get('hit4h')} avg={o.get('avg4h_pct')}% · "
                     f"24h n={o.get('n24h', 0)} hit={o.get('hit24h')} "
                     f"avg={o.get('avg24h_pct')}%{ep}")
        L.append("")
    # [2026-07-14b] Diagnoses — WHY each negative sleeve loses (the lever).
    if diagnoses:
        L.append("## Diagnoses (which lever each negative sleeve needs)")
        for key, d in sorted(diagnoses.items()):
            L.append(f"- **[{d['primary']}]** {d['proposal']}")
        L.append("")
    # [2026-07-14 REACH] Venue A/B — same strategy, Kraken paper vs Lighter.
    ab_lines = venue_ab_lines(venue_ab)
    if ab_lines:
        L.append("## Venue A/B (paper vs Lighter twins — execution/funding gap, not signal)")
        L.extend(ab_lines)
        L.append("")
    L.append("## Per-bot scorecards (closed trades, all time in ledger)")
    for bot, c in sorted(cards.items()):
        if c["n"] == 0:
            continue
        era_note = "" if c.get("era") == "all-time" else \
            f" (current era since {str(c.get('era'))[:10]}; lifetime n={c.get('n_lifetime', c['n'])})"
        if not c.get("alive"):
            era_note += " [inactive/retired — analytics only, no new hypotheses]"
        L.append(f"\n### {bot} — n={c['n']}, win {c['wr']}%, pnl ${c['pnl']:+.2f}{era_note}")
        top_exit = sorted(c["by_exit"].items(), key=lambda x: -x[1]["n"])[:4]
        L.append("  exits: " + "; ".join(
            f"{k} n={v['n']} wr={v['w']/v['n']*100:.0f}% ${v['pnl']:+.2f}" for k, v in top_exit))
        durs = sorted(c["by_dur"].items())
        L.append("  holds: " + "; ".join(
            f"{k} n={v['n']} wr={v['w']/v['n']*100:.0f}%" for k, v in durs))
        if c.get("by_mood"):
            L.append("  mood: " + "; ".join(
                f"{k} n={v['n']} wr={(v['w']/v['n']*100 if v['n'] else 0):.0f}%"
                for k, v in c["by_mood"].items()) +
                f" (matched {c.get('mood_matched', 0)}/{c['n']})")
    # [2026-08-01 (hw)] THE ORDERING IS THE REAL BUG, and it is why one
    # KeyError cost 17 days of learning. `_save_state` used to run AFTER the
    # markdown report, so a fault anywhere in REPORT RENDERING — cosmetic,
    # every one of them — discarded the entire run's computed memory. The
    # durable state is now written FIRST: the report is a nice-to-have, the
    # streak counters are the product.
    #
    # WHAT IT COST, measured 2026-08-01: `learning-brain.runs` sat at 337
    # while `brain-vitals.run` read 338 — the state had not advanced. Since
    # `mult_streaks` needs THREE CONSECUTIVE runs to move a stake multiplier
    # and the streak lives in that state, no new evidence could ever
    # accumulate a streak. The brain recomputed everything correctly, published
    # its four read-only keys, and then died before it could remember any of
    # it. Every run. That is a learning loop that cannot learn.
    saved = _save_state(state)
    try:
        with open(LESSONS_MD, "w") as f:
            f.write("\n".join(L) + "\n")
    except Exception as _e:  # noqa: BLE001
        print(f"[bot_learn] report render failed ({_e!r}) — state ALREADY "
              f"saved ({'+'.join(saved) or 'NOT SAVED'}); learning is intact.")
    n_mults = sum(len(t) for t in published_mults.values())
    print(f"[bot_learn] run {run_no} ({mult_vitals.get('engine')}): "
          f"{len(trades)} closed trades, "
          f"{len(live_act)} actionable, {len(live_cand)} candidates (current-era), "
          f"{n_mults} stake-mults published ({'ok' if mults_saved else 'no-db'}), "
          f"watchlist {len(mult_vitals.get('watchlist') or [])}, "
          f"{len(regime_splits)} regime splits, "
          f"{len(diagnoses)} diagnoses, venue A/B pairs: {len(venue_ab)} "
          f"-> {LESSONS_MD} (state: {'+'.join(saved) or 'NOT SAVED'})")
    for key, d in sorted(diagnoses.items()):
        print(f"  DIAGNOSIS [{d['primary']}]: {d['proposal']}")
    for k, e in sorted(live_act.items()):
        print(f"  ACTIONABLE: {e['proposal']}")
    return 0


def _selftest():
    """[2026-07-17] Locks the LIGHTER drift contract. OFFLINE by construction:
    the market list is stubbed, so this runs in CI/on a laptop with no venue.

    Guards the failure this code is uniquely prone to — a price-BASIS slip on a
    1000X market fails SILENTLY (a x1000 error reads as a ~99900% forward
    return, not a crash) — plus every fail-safe: a foreign venue, a dark feed,
    a missing fill price and a too-young close must each return None, never a
    fabricated 0. Every detective control gets a negative fixture.
    """
    global _lighter_markets, _lighter_cache
    fails = []
    ran = []

    def ck(name, cond):
        ran.append(name)
        if not cond:
            fails.append(name)
        print(("  PASS  " if cond else "  FAIL  ") + name)

    _lighter_markets = {"ETH": 0, "1000BONK": 18}      # stub: no network
    _lighter_cache = {}

    # --- symbol + price-basis resolution -------------------------------------
    ck("bare 'ETH' -> id 0, price x1", _drift_market("ETH") == (0, 1.0))
    ck("suffixed 'ETH/USDC' strips quote", _drift_market("ETH/USDC") == (0, 1.0))
    ck("'kBONK' -> 1000BONK, price x1", _drift_market("kBONK") == (18, 1.0))
    ck("'1000BONK/USDC' -> same book x1", _drift_market("1000BONK/USDC") == (18, 1.0))
    m = _drift_market("BONK")            # raw units: size x0.001 -> price x1000
    ck("raw 'BONK' -> 1000BONK, price x1000",
       m is not None and m[0] == 18 and abs(m[1] - 1000.0) < 1e-6)
    ck("unknown symbol -> None", _drift_market("NOTACOIN") is None)
    ck("empty pair -> None", _drift_market("") is None and _drift_market(None) is None)

    # --- fail-safes: a dark feed must assert NOTHING --------------------------
    _lighter_markets = {}
    ck("DARK market list -> None (never a false 'no book')",
       _drift_market("ETH") is None)
    _lighter_markets = {"ETH": 0, "1000BONK": 18}

    # --- _post_exit_drift contract + gates ------------------------------------
    close_ts = "2026-07-01T00:00:00+00:00"
    t0 = _epoch(close_ts)
    # 24 synthetic 1h bars after the close; high 110 reclaims an open of 100.
    _lighter_cache["ETH"] = [(int(t0 + i * 3600), 100.0, 110.0, 90.0, 105.0)
                             for i in range(1, 25)]
    # [2026-07-17] `good` gains enter_tag: a trade's DIRECTION is now read, not
    # assumed (see _trade_side). This fixture had none, and the check below
    # asserted LONG semantics — which is precisely how the direction bug
    # survived review: the test encoded the bug's assumption as the contract.
    good = {"venue": "lighter", "pair": "ETH", "close_ts": close_ts,
            "open_rate": 100.0, "close_rate": 100.0, "enter_tag": "long"}
    d = _post_exit_drift(dict(good))
    ck("lighter LONG -> (bool, float) contract",
       isinstance(d, tuple) and d[0] is True and abs(d[1] - 0.05) < 1e-9)
    ck("venue=None refused", _post_exit_drift(dict(good, venue=None)) is None)
    ck("venue='kraken' refused", _post_exit_drift(dict(good, venue="kraken")) is None)
    ck("missing open_rate -> None", _post_exit_drift(dict(good, open_rate=None)) is None)
    ck("missing close_rate -> None", _post_exit_drift(dict(good, close_rate=None)) is None)
    ck("missing close_ts -> None", _post_exit_drift(dict(good, close_ts=None)) is None)

    # --- [2026-07-28] STOPPISH speaks Lighter: an 'sl'-worst bucket with the
    # full drift evidence must reach rule 1 (exit_too_tight). Mutation check:
    # removing 'sl' from STOPPISH drops this to mixed_unclear -> red. The
    # discriminating fixture: share 1.0, wr 0.0, reclaim 1.0 (the ETH cache
    # above reclaims), fwd +0.05 — every other rule's bar deliberately missed.
    _diag_trades = (
        [{"profit_abs": -10.0, "profit_ratio": -0.05, "exit_reason": "sl",
          "pair": "ETH", "venue": "lighter", "close_ts": close_ts,
          "open_rate": 100.0, "close_rate": 95.0, "enter_tag": "long"}
         for _ in range(7)]
        + [{"profit_abs": 2.0, "profit_ratio": 0.01, "exit_reason": "tp",
            "pair": "ETH", "venue": "lighter", "close_ts": close_ts,
            "open_rate": 100.0, "close_rate": 102.0, "enter_tag": "long"}
           for _ in range(3)])
    _dg = diagnose("some-bot", "long-dip", _diag_trades, [], {}, {"left": 120})
    ck("'sl'-worst bucket reaches exit_too_tight (STOPPISH speaks Lighter)",
       _dg is not None and _dg.get("primary") == "exit_too_tight")

    # --- [2026-07-28] venue_ab re-key: a SUFFIXED ledger id must find its
    # base-keyed twin, reading the OTHER arm. Mutation checks: reverting the
    # base-strip lookup OR reading the same arm turns this red (the fixture
    # only carries 'live', so a shadow bucket reading 'shadow' finds {}).
    _ab_trades = [{"profit_abs": -5.0, "profit_ratio": -0.05,
                   "exit_reason": "flip", "pair": "ETH", "venue": "hl",
                   "enter_tag": "long"} for _ in range(10)]
    _dg2 = diagnose("x-lshadow", "long-funding", _ab_trades, [],
                    {"x": {"live": {"pnl_abs": 50.0, "wins": 6, "losses": 6}}},
                    {"left": 0})
    ck("suffixed bot finds base-keyed twin -> venue_execution reachable",
       _dg2 is not None and _dg2.get("primary") == "venue_execution")

    # --- DIRECTION: the bug that made reclaim tautological -------------------
    # The tape rises to high=110 and never falls below low=90.
    # A LOSING SHORT (entry 95, exit 100): price is ABOVE entry at close, so
    # `any(high >= entry)` is True BY CONSTRUCTION — the pre-fix answer. The
    # short's real question is "did price fall back DOWN to 95?" -> low 90 <= 95
    # -> True here. Use entry 85 to make the honest answer False and prove the
    # long-shaped tautology is gone.
    sh = dict(good, enter_tag="short", open_rate=85.0, close_rate=100.0)
    d = _post_exit_drift(sh)
    ck("SHORT reclaim is NOT tautological (long logic would say True)",
       isinstance(d, tuple) and d[0] is False)
    ck("SHORT fwd is NEGATED (a price RISE is a loss for a short)",
       isinstance(d, tuple) and abs(d[1] - (-0.05)) < 1e-9)
    ck("SHORT reclaim=True only when price RETURNS DOWN to entry",
       _post_exit_drift(dict(good, enter_tag="short", open_rate=95.0,
                             close_rate=100.0))[0] is True)
    # direction recovered from the exit_reason prefix — for rows that still
    # CARRY one. Un-split shape: `bot_trades` over HTTP delivers the reason as
    # stored, so this path stays load-bearing.
    for reason, want in (("short_flip", "short"), ("long_rebalance", "long"),
                         ("short-divergence_tp", "short"), ("long-dip_exit", "long")):
        ck("side from exit_reason %r -> %s" % (reason, want),
           _trade_side({"exit_reason": reason}) == want)
    ck("enter_tag OUTRANKS the reason prefix",
       _trade_side({"enter_tag": "short", "exit_reason": "long_x"}) == "short")
    ck("UNKNOWN direction -> None (never a long-shaped guess)",
       _trade_side({"exit_reason": "flip"}) is None
       and _trade_side({}) is None)
    # [2026-07-17] THE SHAPE PRODUCTION ACTUALLY DELIVERS. The four cases above
    # hand-build `{"exit_reason": "short-divergence_tp"}` — a dict no paper row
    # ever looks like by the time it reaches this function, because
    # `split_reason` has already moved that prefix into enter_tag. The fixture
    # encoded the assumption under test, so it stayed green across the entire
    # window in which every lens-tagged row silently graded as directionless.
    # Fix: drive the REAL splitter, so the fixture cannot drift from the
    # producer. If split_reason's contract ever moves again, this fails here
    # instead of going quiet in the brain.
    import bot_pnl_store as _store          # module-scope import is lazy here
    for raw, want in (("short-divergence_tp", "short"), ("long-breakout_tp", "long"),
                      ("long-dip_hold", "long"), ("long_roi", "long"),
                      ("short_flip", "short")):
        _tg, _ex = _store.split_reason(raw)
        ck("POST-SPLIT %r (tag=%r exit=%r) -> %s" % (raw, _tg, _ex, want),
           _trade_side({"enter_tag": _tg, "exit_reason": _ex}) == want)
    # and the genuinely directionless rows STILL make no claim after splitting
    for raw in ("flip", "decay_paid"):
        _tg, _ex = _store.split_reason(raw)
        ck("POST-SPLIT %r stays UNGRADED (no guess)" % raw,
           _trade_side({"enter_tag": _tg, "exit_reason": _ex}) is None)
    ck("directionless trade gets NO drift claim",
       _post_exit_drift({k: v for k, v in good.items() if k != "enter_tag"}) is None)

    # --- the window is 24 HOURS, not "the first 24 bars we happen to have" ---
    # A trade older than the tape used to slice 24 bars from DAYS later and
    # return a confident verdict (measured: closed 40d ago -> reclaimed=True,
    # fwd=+100%). len(window)==24 there, so the 6-bar floor never caught it.
    _lighter_cache["ETH"] = [(int(t0 + i * 3600), 100.0, 110.0, 90.0, 105.0)
                             for i in range(1, 25)]
    stale = dict(good, close_ts="2026-05-01T00:00:00+00:00")   # 61d before the tape
    ck("trade OLDER than the tape -> None (no fabricated verdict)",
       _post_exit_drift(stale) is None)

    # < 6 post-close hours must abstain
    _lighter_cache["ETH"] = [(int(t0 + i * 3600), 100.0, 110.0, 90.0, 105.0)
                             for i in range(1, 6)]
    ck("<6 post-close bars -> None", _post_exit_drift(dict(good)) is None)
    # no candles at all
    _lighter_cache["ETH"] = None
    ck("no candles -> None", _post_exit_drift(dict(good)) is None)

    # --- [2026-07-21 BRAIN ACTS] derive_actions: only ACTIONABLE
    # regime_timing findings act; candidates/retired/other kinds never do ---
    _hyp = {
        "georgia|tag:long-trend-breakout": {"status": "ACTIONABLE",
                                            "kind": "diag_regime_timing",
                                            "first_run": 3, "seen": 5},
        "dad|tag:long-momo": {"status": "candidate",
                              "kind": "diag_regime_timing"},
        "mum|tag:long-x": {"status": "retired", "kind": "diag_regime_timing"},
        "avo|tag:long-y": {"status": "ACTIONABLE", "kind": "diag_exit_too_tight"},
        "malformed-key-no-sep": {"status": "ACTIONABLE",
                                 "kind": "diag_regime_timing"},
    }
    _acts = derive_actions(_hyp)
    ck("ACTIONABLE regime_timing -> regime_gate action",
       _acts.get("georgia", {}).get("long-trend-breakout", {}).get("action")
       == "regime_gate")
    ck("candidate does NOT act (streak gate)", "dad" not in _acts)
    ck("retired finding releases its action", "mum" not in _acts)
    ck("expand-direction kinds never act (restrict-only door)",
       "avo" not in _acts)
    ck("malformed key skipped, no crash", "malformed-key-no-sep" not in _acts)
    ck("empty/None ledger -> no actions", derive_actions(None) == {})

    # [2026-07-21 ORGAN CHANNEL] derive_proposals: ACTIONABLE entry_quality on
    # a TAKER row maps lens -> tighter-bar lever; family rows, other kinds,
    # and non-ACTIONABLE states propose nothing
    _hyp2 = {
        "lighter-ticket-taker-lshadow|tag:short-divergence":
            {"status": "ACTIONABLE", "kind": "diag_entry_quality"},
        "lighter-ticket-taker-lshadow|tag:long-dip":
            {"status": "candidate", "kind": "diag_entry_quality"},
        "freqtrade-georgia-lshadow|tag:long-trend-breakout":
            {"status": "ACTIONABLE", "kind": "diag_entry_quality"},
        "lighter-ticket-taker-lshadow|tag:long-breakout":
            {"status": "ACTIONABLE", "kind": "diag_regime_timing"},
    }
    _props = derive_proposals(_hyp2)
    ck("taker entry_quality -> tighter div bar proposal",
       [(p[0], p[1]) for p in _props] == [("taker.div_gap_pp", +1.0)])
    ck("empty/None ledger -> no proposals", derive_proposals(None) == [])

    # --- (fn) BY-SIDE lens grades -------------------------------------------
    # A lens that emits both directions must publish a per-side grade, because
    # a consumer restricted to ONE side (the bull-mode Ticket Taker trades
    # short-divergence only) is otherwise judged on trades it cannot make.
    # OFFLINE: the history fetch is stubbed, prices fall monotonically, so
    # every long grades negative and every short grades positive by
    # construction — the pooled number lands between them.
    import sys as _sys
    from datetime import timedelta
    _store = _sys.modules.get("bot_pnl_store")
    _real_fetch = getattr(_store, "fetch_state_history", None) if _store else None
    try:
        if _store is None:
            import bot_pnl_store as _store          # noqa: F811
            _real_fetch = _store.fetch_state_history
        _t0 = datetime(2026, 7, 20, tzinfo=timezone.utc)
        _syms = [f"L{i}" for i in range(6)] + [f"S{i}" for i in range(3)]
        _hist = []
        for i in range(24):                          # 24 x 30min = 11.5h span
            _ts = _t0 + timedelta(minutes=30 * i)
            _marks = {s: 100.0 * (0.99 ** i) for s in _syms}   # everything falls
            _tk = []
            if i < 12:            # emit each sym ONCE -> every emission is an
                for s in _syms:   # episode first, so eps == n emissions graded
                    if s.startswith("L" if i % 2 == 0 else "S"):
                        _tk.append({"sym": s, "side":
                                    "long" if s[0] == "L" else "short"})
            _hist.append({"ts": _ts.isoformat(),
                          "payload": {"marks": _marks,
                                      "tickets": {"divergence": _tk}}})
        _store.fetch_state_history = lambda key, limit=None: list(reversed(_hist))
        _g = grade_scout_lenses()
        _d = (_g or {}).get("divergence") or {}
        _bs = _d.get("by_side") or {}
        ck("by_side published for a two-sided lens",
           set(_bs) == {"long", "short"})
        ck("falling tape: long side grades NEGATIVE",
           (_bs.get("long") or {}).get("eavg4h_pct", 0) < 0)
        ck("falling tape: short side grades POSITIVE",
           (_bs.get("short") or {}).get("eavg4h_pct", 0) > 0)
        ck("per-side episodes sum to the pooled count",
           (_bs.get("long", {}).get("eps4h", 0)
            + _bs.get("short", {}).get("eps4h", 0)) == _d.get("eps4h"))
        ck("pooled fields still published unchanged (no consumer breaks)",
           _d.get("n4h") and _d.get("ehit4h") is not None
           and _d.get("n_syms") == len(_syms))
        # the taker's rule must read it: same payload, opposite verdicts
        import lighter_ticket_taker as _tt
        _pool_bad = {"divergence": {"eps4h": 100, "n_syms": 20,
                                    "eavg4h_pct": -0.09, "ehit4h": 0.483,
                                    "by_side": {"short": {
                                        "eps4h": 40, "n_syms": 15,
                                        "eavg4h_pct": 0.14, "ehit4h": 0.513}}}}
        ck("taker vetoes on the pooled grade without `sides`",
           _tt.vetoed_lenses(_pool_bad) == {"divergence"})
        ck("taker clears it when graded on the side it trades",
           _tt.vetoed_lenses(_pool_bad, sides={"divergence": "short"}) == set())
    except Exception as _ex:                          # noqa: BLE001
        ck(f"by_side selftest ran without error ({_ex!r})", False)
    finally:
        if _store is not None and _real_fetch is not None:
            _store.fetch_state_history = _real_fetch

    print("selftest: %d checks, %d FAILED%s"
          % (len(ran), len(fails), (" -> " + ", ".join(fails)) if fails else ""))
    return 1 if fails else 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    # [2026-08-01 (hw)] THE SHARED wrapper, not a bespoke one. run_all.sh runs
    # this behind `|| true`; without it the KeyError('paper') above ran on
    # EVERY cycle for weeks and nothing anywhere said so.
    sys.exit(store.organ_main(VITALS_KEY, main))
