#!/usr/bin/env python3
"""fleet_bus.py — READ-side client for the fleet's shared bot_state keys.

[2026-07-14 CONSUMPTION WIRING] The intelligence organs (bot_learn brain,
fleet_risk light, regime oracle, market pulse) have been publishing since
7 Jul with ZERO consumers — the Jul-14 enforcement review found every layer
built and nobody reading it. This module is the one place strategies import
to consume the bus, so the fail-safe contract lives in exactly one file:

  FAIL-SAFE CONTRACT (same as the publishers'):
    - no DATABASE_URL / import error / DB down  -> neutral (1.0x, no veto)
    - payload missing or STALE (updated+ttl_sec) -> neutral
    - anything unparseable                       -> neutral
  In `freqtrade backtesting` DATABASE_URL is unset, so every helper here
  returns neutral and backtests exercise pure strategy logic — live-only
  inputs can never contaminate a backtest.

Reads are cached per-process for CACHE_SEC so 4 bots x N pairs don't hammer
Postgres. Shipped in Dockerfile.freqtrade next to bot_pnl_store.py (CWD
/freqtrade), so strategies use the same `import` mechanics that already
work for the market-pulse reads.
"""
import math
import os

from datetime import datetime, timedelta, timezone

CACHE_SEC = 300
_cache = {}   # key -> {"ts": datetime, "payload": dict|None}

# TWO-WAY guardrails for the brain's L4 stake multipliers (reduce-only
# until 21-Jul): whatever the brain publishes, a strategy sizes inside
# [0.5, 2.0] since (sm) — reductions as before, boosts only on the v3 mirror bars
# (Wilson LOWER bound + t, full n floor, 3-run streak — bot_learn/
# brain_stats EXP_*). Neutral 1.0 on any doubt.
# [2026-08-20 (sn)] 6.7x EITHER WAY (Eamon, explicitly). The floor is DERIVED
# from the ceiling rather than typed, so "either way" is true by construction
# and the next move needs one edit, not two that can drift apart.
#: [2026-08-22 (ta)] LIVE ARMS THAT NO LONGER TRADE REAL MONEY.
#:
#: **Eamon, 22-Aug: "just replace farmer with georgia as weve done so many
#: times before".** DECLARED HERE, not in the bot, because two processes in two
#: IMAGES have to agree about it and they cannot import each other: 💸 the
#: Farmer's live arm runs in `trail-blazer-live` off `Dockerfile.fundinglighter`
#: and the 🧪 experiment judge runs in `freqtrade-bots`, which does not (and
#: must not) carry a real-money trading module. `fleet_bus` is in both images
#: already, so this is the one place both can read.
#:
#: The judge is the consumer that matters: its whole job is promoting
#: `live.funding.*` levers onto this exact row, and its paired bar needs
#: `live >= 10` closes — so a flat arm silences it CORRECTLY but INVISIBLY,
#: `{promotions: 0}` reading identically for "no candidate cleared" and "there
#: is no live arm to promote onto" (I18). It stands down out loud instead.
#: Measured at the retirement: ZERO `live.*` levers open, so nothing is
#: stranded by this.
#:
#: THE OVERRIDE IS PARSED IDENTICALLY BY EVERY READER — the `BRAIN_MULT_ENGINE`
#: rule, where a detector and its subject disagreeing about one env var is how
#: a kill switch goes silent. Resurrecting the arm therefore means setting the
#: override on BOTH services; that is stated in the retirement entry rather
#: than hidden, because a half-set override is a book trading with no judge.
RETIRED_LIVE_ARMS = {
    "perps-funding-lighter-lighter": {
        "since": "2026-08-22",
        "entry": "(ta)",
        "override": "FARMER_LIVE_RETIRED_OVERRIDE",
        "successor": "freqtrade-georgia-lighter",
        "why": "horizon `unreachable` on BOTH arms at the fleet's own grader "
               "(live n=91 mean -0.160%/trade t=-0.88 halves +2.51/-7.65; "
               "shadow n=161 mean -0.195% t=-0.95 halves +5.71/-18.32). "
               "The shadow twin keeps trading as the control arm.",
    },
}


def live_arm_retired(row):
    """True when `row` is a live arm the fleet has retired.

    Fail-safe direction is KEEP TRADING: an unknown row is not retired, so a
    typo here can never silence a living book. The dangerous direction — a
    retired arm reading as live — needs the row to be spelled exactly right in
    the table above, which is the direction a mistake is loud in."""
    spec = RETIRED_LIVE_ARMS.get(row)
    if not spec:
        return False
    return os.environ.get(spec["override"], "").strip().lower() \
        not in ("run", "1", "true")


# ---------------------------------------------------------------------------
# [2026-08-25 (ti)] JUDGE V2 — THE PAIR REGISTRY AND THE PHASE VOCABULARY,
# single-owned here because the judge (freqtrade-bots) and the live hosts
# (avolive / fundinglighter images) cannot import each other and BOTH must
# agree about what is judged and what the states mean (the RETIRED_LIVE_ARMS
# pattern, one table up).
#
# Eamon, 25-Aug: *"The judge has malfunctioned several times for this sole
# reason, and it's well overdue for v2."* The sole reason, confirmed on the
# bus: a SINGLE-pair machine hardwired to the Farmer's funding lanes, stood
# down since (ta) with a successor it structurally cannot judge. v2 judges
# every live/shadow twin from THIS registry; a pair whose live_bot is None or
# retired is stood_down BY CONSTRUCTION.
#
# `policy_fields` is each pair's (jf) era signature — the fields whose change
# resets a comparison window. `strip_exits` are exit-reason FAMILIES excluded
# from BOTH arms of the paired sample before any count (forced flattens and
# legacy marks are halt events, not candidate outcomes; counts publish so the
# reduction is visible). `economic_exits` is the CLOSED vocabulary of exit
# families the paired bar may count — a close matching neither set makes the
# pair `unjudgeable:unknown_exit_reason` NAMING the novel string (fail-loud
# on novelty: this fleet mints new exit reasons constantly, and a silent
# default in either direction re-opens the F1 contamination class).
# `growth` empty = the fast path is STRUCTURALLY unreachable for the pair,
# not merely flagged off.
#
# [2026-08-26] `policy_waived` — the DECLARED PARITY WAIVER, per pair, in the
# `BORN_DARK_OK` / `UNJUDGED_OK` / `STALE_WRITER_OK` idiom: a mapping from the
# waived FIELD to a reason string carrying the MEASUREMENT that makes it inert
# on THAT pair and the condition that reopens it. Three properties are the
# whole safety of it, and each is driven by
# `tests/autonomy/test_judge_policy_waiver.py`:
#   1. THE FIELD STAYS IN `policy_fields`. Deleting it would hide the
#      divergence; the waiver removes the BLOCK, never the visibility, and the
#      judge republishes the waived field with both arms' values every loop.
#   2. IT IS PER-PAIR, NEVER A FLEET RULE. A waiver is a claim about one pair's
#      measured occupancy; the same field on another pair still blocks.
#   3. IT NEVER COVERS DARKNESS. A waived field whose value is missing or
#      unreadable on either arm is `parity_unreadable`, not waived — an
#      assumed-equal dark input is exactly the F1 handicap this stage exists to
#      close, and a waiver must not smuggle it back in.
#
# [2026-08-26] `policy_stamp_required` — THE WAIVER'S MIRROR, and the reason a
# `policy_fields` entry can be trusted at all. A field NEITHER host stamps
# compares None-to-None, reads EQUAL, and passes the parity rung in silence —
# so the registry would claim to police a divergence it structurally cannot
# see. This map (field -> the reason, carrying the measurement and the exact
# stamp work) makes the absence BLOCK: the pair reads
# `unjudgeable:policy_unstamped` naming the field and the two publisher files,
# and it self-closes the moment both hosts stamp the key. PRESENCE is the test,
# never truthiness — `None` is the honest stamp for "this host has no such
# rule", and a host that says so has answered.
JUDGED_PAIRS = {
    "avo": {
        "live_bot": "freqtrade-avo-maria-lighter",
        "shadow_bot": "freqtrade-avo-maria-lshadow",
        "xp_prefix": "xp.avo.",
        "live_names": (),
        "live_service": "tide-rider-lighter-live",
        "shadow_service": "family-lighter-shadow",
        "pnl_form": "price",
        "strip_exits": ("daily_loss", "kill_switch", "v1_legacy"),
        "economic_exits": ("roi", "stop", "custom", "signal", "exit",
                           "bounce_take", "range_top", "max_hold", "trade",
                           "delisted", "trend_breakdown", "flip"),
        "policy_fields": ("strategy", "venue", "stoploss", "roi", "sides",
                          "scan_order"),
        "growth": {},
        "control_role": "load_bearing",
        "host_file": "lighter_avo_live_bot.py",
    },
    "georgia": {
        "live_bot": "freqtrade-georgia-lighter",
        "shadow_bot": "freqtrade-georgia-lshadow",
        "xp_prefix": "xp.georgia.",
        "live_names": (),
        # [(tl)] CORRECTED from "georgia-live": she runs the Farmer's old
        # service since the (ta) slot swap — service names lie, and this
        # registry lied for a day until aiming a real one-shot at it forced
        # the check. The audit-scope lesson's registry twin.
        "live_service": "trail-blazer-live",
        "shadow_service": "family-lighter-shadow",
        "pnl_form": "price",
        "strip_exits": ("daily_loss", "kill_switch", "v1_legacy"),
        "economic_exits": ("roi", "stop", "custom", "signal", "exit",
                           "bounce_take", "range_top", "max_hold", "trade",
                           "delisted", "trend_breakdown", "flip"),
        "policy_fields": ("strategy", "venue", "stoploss", "roi", "sides",
                          "scan_order", "max_entries_per_hour"),
        # [2026-08-26] THE SECOND ENTRY-POLICY DIVERGENCE ON THIS PAIR, and it
        # is NOT waived: it is MEASURED MATERIAL, and neither host stamps it
        # yet, so it is declared REQUIRED and blocks until they do.
        "policy_stamp_required": {
            "max_entries_per_hour":
                "THE ARMS RUN DIFFERENT ENTRY POLICIES AND NEITHER STAMPS IT. "
                "The shadow throttles entries per clock hour "
                "(lighter_family_bot.DayTraderGated.MAX_ENTRIES_PER_HOUR = 3, "
                "env GEORGIA_MAX_ENTRIES_PER_HOUR, applied at "
                "`throttle_ok()` and refused at the entry site); the live "
                "host enforces NO throttle and says so in its own comment — "
                "'this host enforces NO hourly throttle ... so live rank is "
                "the UNCENSORED within-hour ordinal'. MEASURED on the two "
                "arms' own ledgers (phantom halt rows excluded): entries per "
                "ACTIVE hour, shadow {1: 108h, 2: 44h, 3: 4h} = at-or-over "
                "the cap in 2.6% of active hours; live {1: 16h, 2: 5h, 3: 3h, "
                "4: 1h, 9: 1h} = 19.2%, and it reaches NINE in one hour. The "
                "difference is systematic in a quantity the book's own ledger "
                "shows matters: shadow entry_rank 1 = -0.443%/trade (n=24), "
                "rank 2 = +0.828% (n=9), rank 3 = -7.752% (n=3). One arm is "
                "rank-censored at 3 and the other is uncensored, so a paired "
                "bar over these two samples compares different entry "
                "populations — the F1 handicap judge v2 exists to close. "
                "THE STAMP WORK, exactly: `lighter_family_bot.policy_stamp()` "
                "is the ONE builder both hosts call, so it takes one new "
                "argument each host answers for itself — the shadow "
                "`DayTraderGated.MAX_ENTRIES_PER_HOUR` (or None for a book "
                "with no throttle), the live host None. Once both stamp it, "
                "this rung passes and the PARITY rung takes over: 3 vs None "
                "diverges and still blocks, correctly, until the arms are "
                "aligned or someone waives it on ITS OWN evidence. Neither "
                "file is this pass's to edit; declared here so the hole is "
                "visible and blocking rather than silent.",
        },
        # [2026-08-26] THE ONE DECLARED WAIVER IN THE FLEET, and it is narrow
        # on purpose — see the `policy_waived` note above JUDGED_PAIRS.
        "policy_waived": {
            "scan_order":
                "MEASURED INERT ON THIS PAIR. The live host scans via "
                "`lighter_avo_live_bot.diversified_order` and the shadow "
                "scans in list order (`lighter_family_bot`), so the arms "
                "really do diverge — but scan ORDER can only change WHICH "
                "candidate is taken while the book is CHOOSING, i.e. at or "
                "near its position cap. Time-weighted occupancy from each "
                "arm's own ledger (episodes built from opened_at/closed_at, "
                "phantom halt rows excluded on golive_readiness."
                "is_phantom_close's signature): freqtrade-georgia-lshadow "
                "cap 5, 208 episodes over 44.4d — flat 66.3% of the time, "
                "mean occupancy 0.56 of 5, AT CAP 0.6%; "
                "freqtrade-georgia-lighter cap 5, 47 episodes over 4.2d — "
                "flat 51.3%, mean occupancy 0.90 of 5, AT CAP 5.0%. Both "
                "arms are SIGNAL-limited, not slot-limited, so the ordering "
                "rule is unreachable for ~95-99% of the pair's life and "
                "cannot materially bias a paired comparison. "
                "NOT A FLEET RULE — this is why avo and mum carry no waiver "
                "and must keep reading `policy_mismatch` on the same field: "
                "avo's live arm was measured sitting at its ceiling 21.7% of "
                "the time ((sr)), an ORDER OF MAGNITUDE more often, so the "
                "same divergence is not inert there. "
                "REVISIT — delete this waiver and port the divergence across "
                "instead — when EITHER arm's at-cap time exceeds 10% of its "
                "trailing window (2x the live arm's measured 5.0%, and the "
                "point at which the scan order begins to choose), or if the "
                "live arm's cap or clip changes such that it fills. The live "
                "reading rests on a 4.2d window and n=47, so it is the half "
                "to re-measure first.",
        },
        "growth": {},
        "control_role": "load_bearing",
        "host_file": "lighter_avo_live_bot.py",
    },
    "mum": {
        "live_bot": "freqtrade-mum-lighter",
        "shadow_bot": "freqtrade-mum-lshadow",
        "xp_prefix": "xp.mum.",
        "live_names": (),
        "live_service": "mum-live",
        "shadow_service": "family-lighter-shadow",
        "pnl_form": "price",
        "strip_exits": ("daily_loss", "kill_switch", "v1_legacy"),
        "economic_exits": ("roi", "stop", "custom", "signal", "exit",
                           "bounce_take", "range_top", "max_hold", "trade",
                           "delisted", "trend_breakdown", "flip"),
        "policy_fields": ("strategy", "venue", "stoploss", "roi", "sides",
                          "scan_order"),
        "growth": {},
        "control_role": "load_bearing",
        "host_file": "lighter_avo_live_bot.py",
    },
    # The Farmer pair, parked: its live arm is in RETIRED_LIVE_ARMS above, so
    # v2 stands it down by construction with the wake condition published.
    # Its xp.funding./live.funding. surface stays REGISTERED (deleting it
    # would orphan the (na) registrations and silently moot Hull's pre-named
    # ~4-Sep min-vol-2e6 overlap decision); the six static CANDIDATES park
    # behind the judgeable-pair admission gate — no slot burns into a dead
    # pair.
    "farmer": {
        "live_bot": "perps-funding-lighter-lighter",
        "shadow_bot": "perps-funding-lighter-lshadow",
        "xp_prefix": "xp.funding.",
        "live_names": (),
        # [(tl)] None: the retired arm HAS no service — trail-blazer-live
        # hosts 🔮 georgia since the (ta) swap, and a registry naming one
        # service for two books is how a one-shot lands on the wrong row.
        "live_service": None,
        "shadow_service": "funding-farmer-shadow",
        "pnl_form": "funding",
        "strip_exits": ("long_retired", "short_retired", "daily_loss"),
        "economic_exits": ("decay_paid", "flip", "bleed", "max_hold",
                           "stop", "trade", "exit"),
        "policy_fields": ("venue", "enter_apr", "sides"),
        "growth": {},
        "control_role": "independent",
        "host_file": "lighter_funding_bot.py",
    },
}

#: Live-capable books DELIBERATELY outside the judge, each with a reason —
#: the BORN_DARK_OK idiom. The roster test additionally injects a synthetic
#: entry so the mechanism is under test whatever this dict holds.
UNJUDGED_OK = {
    "lighter-ticket-taker-lighter":
        "live arm stood down 13-Aug (ma) — its sub-account moved to 🙏 Avo; "
        "the shadow arm keeps grading, and there is no live account to "
        "promote onto. Re-pairs if the taker ever gets a live slot again.",
}

#: THE PHASE VOCABULARY — one constant, imported by the judge (publisher),
#: fleet_immune (validator) and fleet_regen (restorer). F4's structural
#: closure: there is no second list to forget, and the judge's own selftest
#: asserts its published phases are a subset of THIS constant, so a new phase
#: string fails the PUBLISHER'S build instead of being erased downstream.
XP_JUDGE_PHASES = ("idle", "running", "promoted", "stood_down", "unjudgeable")
#: Running-state HOLD annotations (published state, never buried in
#: last_eval — the count alone is what hides a stall, I18/(sa)).
XP_JUDGE_HOLDS = ("arm_skew", "arm_drift", "floors", "assert_fail")
#: UNJUDGEABLE reasons — Stage-0 fairness prechecks emit these INSTEAD of a
#: biased bar. Every reason names the object the operator can act on (I8).
XP_JUDGE_UNJUDGEABLE = (
    "policy_unstamped", "policy_mismatch", "capacity_mismatch",
    "parity_unreadable", "no_live_arm", "live_row_dark",
    "shadow_row_dark",
    "pnl_form_mismatch", "unknown_exit_reason")


MULT_FLOOR = 1.0 / 6.7
# [2026-07-21 TWO-WAY MULTS — operator: "brain needs to be able to widen
# too"] Ceiling raised 1.0 -> 1.5: the brain may now publish EXPAND mults
# (1.25/1.5) for tags proving out on the v3 mirror bars (Wilson LOWER
# bound, t >= +2, full n floor, streak-gated, no urgent path — brain_stats
# EXP_*). The clamp still bounds whatever arrives; only SHADOW books read
# mults. Deliberate scope expansion of the documented reduce-only
# contract, recorded in CLAUDE.md the same day.
# [2026-08-20 (sm)] 1.5 -> 2.0. The clamp is what a CONSUMER may express, and
# it was one notch below what the brain can now SAY: `brain_stats` gained a
# 2.0x ceiling step (post_wr>0.65, Wilson lo>0.60, t>=3.5, n_eff>=30 — above
# every headline this fleet has re-measured and lost, at-or-below the two that
# survived). Leaving the clamp at 1.5 would have made that tier emit-and-be-
# swallowed, which is the registered-but-inert failure with extra steps.
# [2026-08-20 (so)] "SHADOW ONLY: no live bot reads a brain multiplier" stood
# here and is CORRECTED IN PLACE per I12 — it no longer describes the fleet.
# Eamon: "Implement into live and other bots without it." Both real-money rows
# read the brain now, and the sentence that made that sound forbidden was the
# doctrine half of the same training wheel (sm) took off the number. What
# replaces it is not a weaker rule, it is a DIFFERENT one, and it is the reason
# this is safe: the multiplier PROPOSES a size, and every senior rail still
# DISPOSES — SafetyRails.notional_ok, the kill switch, the daily-loss halt and
# the fleet long-budget veto all sit downstream, untouched and operator-owned.
MULT_CEIL = 6.7


def _now_utc(current_time):
    if current_time is None:
        return datetime.now(timezone.utc)
    if current_time.tzinfo is None:
        return current_time.replace(tzinfo=timezone.utc)
    return current_time


def _load(key, current_time):
    """Cached bot_state read; None on any failure."""
    now = _now_utc(current_time)
    c = _cache.get(key)
    if c is not None and abs((now - c["ts"]).total_seconds()) < CACHE_SEC:
        return c["payload"]
    payload = None
    try:
        import bot_pnl_store as store
        payload = store.load_state(key) or None
    except Exception:
        payload = None
    _cache[key] = {"ts": now, "payload": payload}
    return payload


def is_fresh(payload, current_time):
    """True only when the payload self-reports as current (updated + ttl_sec)."""
    try:
        updated = datetime.fromisoformat(str(payload["updated"]).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        ttl = float(payload.get("ttl_sec") or 0)
        return timedelta(0) <= (_now_utc(current_time) - updated) <= timedelta(seconds=ttl)
    except Exception:
        return False


#: The brain's mult payload, RESOLVED: parsed, validated, clamped, and the
#: freshness window pre-computed. Rebuilt only when `_load` actually re-reads
#: (its `ts` changes), which is at most once per CACHE_SEC.
_resolved_mults = {"ent": None, "map": {}, "from": None, "until": None}


def _resolve_mults(current_time):
    """({bot: {tag: clamped float}}, valid_from, valid_until) — cached.

    [2026-08-20 (sp)] Eamon: *"Optimise the lookup ... and ensure the brain
    doesn't cause problems."* Three things, and only one of them is speed:

    **ATOMICITY, which is the one that was actually a bug.** `brain_mult_multi`
    calls the raw read once per bucket, and each of those called `_load` +
    `is_fresh` independently. `_load`'s cache expires on a clock, not on a call
    boundary — so a two-bucket lookup straddling that expiry could take ⚖️
    Counterweight's LONG leg from one payload and its SHORT leg from the next.
    One clip, two sources of truth, on the book whose whole design is that its
    two legs are the same size. Resolving ONCE per call fixes it by
    construction, and it holds the same way across a per-coin entry loop.

    **JUNK IS NOW "NO OPINION", NOT A 6.7x CUT.** The old path did
    `max(MULT_FLOOR, min(MULT_CEIL, float(m["mult"])))`, so a payload carrying
    `-1` — a publisher bug, not a size opinion — clamped to MULT_FLOOR and
    quietly shrank every clip on that bucket to **0.149x**. Now a value that is
    non-numeric, NaN, zero or negative is DROPPED, and a dropped bucket is
    silent (neutral 1.0), matching this module's contract everywhere else: any
    doubt is 1.0. A legitimately extreme opinion (0.05) still CLAMPS to the
    floor — that is evidence outside the cage, which is a different thing from
    corruption.

    **SPEED, third and least.** `is_fresh` parses an ISO-8601 timestamp on
    every call and was ~60% of the cost of a lookup (measured: 0.93us of
    1.55us). The window is derived once here and the per-call check becomes two
    datetime comparisons — so the semantics of `is_fresh` are preserved
    EXACTLY, including its future-stamp guard, rather than traded away for a
    memo that could serve a payload up to CACHE_SEC past its own TTL.
    """
    _load("brain-stake-mults", current_time)          # populates/refreshes _cache
    ent = _cache.get("brain-stake-mults")
    payload = (ent or {}).get("payload")
    r = _resolved_mults
    # Keyed on the CACHE ENTRY's identity, not on its timestamp. `_load`
    # replaces the entry dict wholesale on every re-read, so identity tracks
    # the payload exactly — and it also tracks a DIRECT poke at `_cache`, which
    # a timestamp does not: the selftest below writes a stale payload under the
    # same `_now` object, and a ts-keyed memo happily served the previous
    # resolution to it. That is not a test artifact; `fleet_regen` and any
    # future in-process injector do the same thing. The memo holds its own
    # reference to `ent`, so the id cannot be recycled underneath it.
    if r["ent"] is not None and r["ent"] is ent:
        return r["map"], r["from"], r["until"]

    out, frm, until = {}, None, None
    try:
        updated = datetime.fromisoformat(
            str(payload["updated"]).replace("Z", "+00:00"))
        if updated.tzinfo is None:
            updated = updated.replace(tzinfo=timezone.utc)
        frm = updated
        until = updated + timedelta(seconds=float(payload.get("ttl_sec") or 0))
    except Exception:                                # noqa: BLE001
        frm = until = None
    raw = (payload or {}).get("mults") if isinstance(payload, dict) else None
    if until is not None and isinstance(raw, dict):
        for bot, tags in raw.items():
            if not isinstance(tags, dict):
                continue
            clean = {}
            for tag, rec in tags.items():
                try:
                    v = float(rec.get("mult") if isinstance(rec, dict) else rec)
                except (TypeError, ValueError, AttributeError):
                    continue
                if v != v or v <= 0:                 # NaN / zero / negative
                    continue
                clean[str(tag)] = max(MULT_FLOOR, min(MULT_CEIL, v))
            if clean:
                out[str(bot)] = clean
    r["ent"], r["map"], r["from"], r["until"] = ent, out, frm, until
    return out, frm, until


def brain_mults(current_time=None):
    """The whole FRESH mults map, `{bot: {tag: clamped float}}`, or `{}`.

    One resolved read for any consumer that wants more than a single bucket —
    a monitor, the dashboard, or an organ asking "what is the brain currently
    saying to anyone?". Empty on a dark, stale or unparseable payload.
    """
    m, frm, until = _resolve_mults(current_time)
    if until is None:
        return {}
    now = _now_utc(current_time)
    return m if frm <= now <= until else {}


def stake_multiplier(bot, entry_tag, current_time=None):
    """The brain's L4 per-(bot, enter_tag) stake multiplier — TWO-WAY since
    21-Jul (Eamon: "brain needs to be able to widen too"), clamped to
    [MULT_FLOOR, MULT_CEIL] = [1/6.7, 6.7] since (sn) — 6.7x either way.

    Published by bot_learn.py to bot_state 'brain-stake-mults'. Reduce side
    (0.5/0.75): a tag's negative expectancy clears the trade-count floor AND
    persists across >= PROMOTE_RUNS consecutive brain runs. Expand side
    (1.25/1.5): the v3 MIRROR bars only (brain_stats.EXP_* — Wilson lower
    bound, t >= +2.0/+2.5, full n floor, no family-praise inheritance, no
    urgent fast-path; kill switches BRAIN_MULT_ENGINE=v2 /
    BRAIN_MULT_EXPAND=off zero it). Neutral 1.0 on any doubt.

    [2026-08-20 (so)] "SHADOW books only — no live bot reads mults" was here
    and is CORRECTED IN PLACE (I12): every living book reads this now, real
    money included. See MULT_CEIL's note for why that is a rails question and
    not a clamp question. Prefer `brain_clip`/`brain_clip_multi` at a sizing
    site — they carry the fail-safe and hand back the mult to STAMP (I23).
    """
    m = brain_mult_raw(bot, entry_tag, current_time)
    return 1.0 if m is None else m


def brain_mult_raw(bot, entry_tag, current_time=None):
    """The brain's clamped mult for ONE bucket, or **None when it has no
    opinion** — the distinction `stake_multiplier` cannot express.

    `stake_multiplier` returns 1.0 for "absent" and for "exactly 1.0" alike.
    For a single bucket those mean the same thing (do not resize) and the
    conflation is harmless. It stops being harmless the moment a size spans
    SEVERAL buckets: combined with `min`, a silent bucket would out-vote an
    opining one and the brain's only live opinions would be silently discarded
    by the arms that have none.
    """
    try:
        return brain_mults(current_time).get(str(bot), {}).get(str(entry_tag))
    except Exception:                                # noqa: BLE001
        return None


def brain_mult_multi(buckets, current_time=None):
    """ONE multiplier for a size that spans one or more (row, tag) buckets.

    **RULE: the MINIMUM over the buckets that HAVE an opinion; 1.0 when none
    does.** Two shapes in this fleet need it and both are the same shape:

    * ⚖️ Counterweight takes ONE clip and opens a long leg AND a short leg
      with it. The brain buckets those closes separately (`long`, `short`), so
      a per-side mult would size the two legs differently and the book would
      stop being dollar-neutral — it would quietly become a directional book
      wearing a spread book's name. One clip, one scale.
    * 🙏 Avo's LIVE arm has n=3 of its own and a designed shadow control arm
      beside it. `brain_entry_gated` already consults BOTH rows three lines
      above the sizing site; this reads the same pair.

    Why `min` and not a mean: a reduce is heard from ANY bucket (restrict-
    biased, which is what a size that spans several records should be), while
    an expand needs every bucket that has spoken to agree. A SILENT bucket
    never blocks an expansion — that is the whole reason `brain_mult_raw`
    exists, and it is what lets the live arm size off its control arm's
    evidence when its own record is too thin to have any (I14: the record
    decides, and where there is no record the designed proxy speaks).

    Fail-safe: any doubt is 1.0.
    """
    try:
        # ONE resolved snapshot for every bucket in this call — see
        # `_resolve_mults` for why that is atomicity and not just speed.
        snap = brain_mults(current_time)
        seen = [v for v in (snap.get(str(b), {}).get(str(t))
                            for b, t in buckets) if v is not None]
    except Exception:                                # noqa: BLE001
        return 1.0
    return min(seen) if seen else 1.0


#: [2026-08-20 (sp)] THE BOOK-LEVEL GROSS BOUND, as a multiple of a book's OWN
#: DESIGNED gross (`max_positions x base_clip`). Eamon: *"ensure the brain
#: doesn't cause problems."*
#:
#: THE PROBLEM, measured on the code as (so) shipped it. Several books multiply
#: the brain's scale on top of scales they already carry, and nothing bounded
#: the product on a book with no SafetyRails cap:
#:
#:    🌾 carry          300 x alloc 4.0 x brain 6.7 x 12 slots = $96,480 gross
#:    🪁 kelly          250 x brain 6.7 x 4                    =  $6,700
#:    🧭 cook           240 x brain 6.7 x 4                    =  $6,432
#:    ⚖️ Counterweight   20 x alloc 4.0 x brain 6.7 x 10 legs   =  $5,360
#:
#: — every one of them a **$1,000 paper book**, carry at **96x its own
#: equity**. That is not an aggressive book, it is a modelling error: the flat
#: `SLIP_COST * notional` these books charge is calibrated at their real clip
#: and is fiction at 6.7x it, so the P&L would be optimistic in exactly the
#: direction that makes a bad book look gradeable.
#:
#: WHY 2.0, AND WHY IT IS NOT A RE-CAGING. **The per-POSITION multiplier is
#: untouched — the brain may still take a single position to 6.7x.** What it
#: may not do is hold 6.7x in EVERY slot at once, because that is leverage, and
#: this fleet's own I22 says leverage adds no decidability (it scales mean and
#: sd alike, so `t` is invariant), multiplies drawdown against the 15% bar, and
#: is admissible only as the OUTPUT of a volatility target on a book whose
#: N_eff has been measured — which no book here has. So a book's designed gross
#: is its intended exposure, and the brain gets to CONCENTRATE it, not inflate
#: it. A book running one 6.7x position and three empty slots is fully
#: expressive under this bound; that shape is what conviction actually looks
#: like.
#:
#: NOT FOR REAL MONEY. The two live rows already have a bound and it is
#: `SafetyRails.notional_ok` with an OPERATOR-SET cap — operator-owned by
#: design. A second ceiling there would be redundant at best and could
#: contradict the operator's at worst. This exists for the shadow books, which
#: have no rail at all.
BRAIN_GROSS_X = float(os.environ.get("BRAIN_GROSS_X", "2.0"))


def brain_gross_cap(max_positions, base_clip_usd, factor=None):
    """A book's gross budget for the brain: `factor x max_positions x clip`.

    Derived from the book's OWN constants at its OWN call site, so changing a
    clip or a cap moves the bound with it — a retyped budget is a budget that
    drifts. Returns None (no bound) on anything unusable.

    **PASS THE BOOK'S OWN MODULE CONSTANTS — the designed cap and the designed
    clip — NOT a clip another organ has already scaled.** Measured on the live
    payload the day this shipped, which is why it is stated this strongly: 🌾
    carry is the fleet's ONLY book with a measured allocation claim, and it
    sits AT the organ's 4.0 ceiling right now (`delta_usd: +13,500` on a
    $1,000 book). So its post-allocation base is $1,200 and its gross is
    already **$14,400 on a $1,000 book** before the brain says a word.

    Budgeting off that base would set the bound at 2 x 12 x $1,200 = $28,800
    and hand the brain another $24,000 of room on the one book that least
    needs it. Budgeting off the CONSTANTS sets it at 2 x 12 x $300 = $7,200 —
    already spent — so the brain gets no room there at all, which is the right
    answer, while the `max(base, ...)` floor leaves the allocation organ's
    $14,400 exactly as it was. The bound binds where the danger is and
    restricts nothing that predates it.

    (The allocation organ's own 4.0 ceiling on a 12-slot $300-clip book is a
    real finding and it is NOT this function's to fix — it is carried in
    HANDOFF.md with its numbers.)
    """
    try:
        n, c = float(max_positions), float(base_clip_usd)
        f = BRAIN_GROSS_X if factor is None else float(factor)
    except (TypeError, ValueError):
        return None
    if not (n > 0 and c > 0 and f > 0):
        return None
    return n * c * f


def brain_clip_multi(buckets, base_usd, current_time=None,
                     deployed_usd=None, gross_cap_usd=None, slots=1):
    """`base_usd` scaled by `brain_mult_multi(buckets)` -> (scaled_usd, mult).

    THE ONE CALL SHAPE for every book, so the rule has one owner and each
    book's wiring is a single line at its own sizing site.

    [2026-08-20 (so)] **Eamon: "Implement into live and other bots without
    it."** Until today the brain's sizing reached only the family books, the
    freqtrade strategies and the Parliament — thirteen books, BOTH real-money
    rows among them, sized off a constant while the organ holding every close
    this fleet has ever made had nothing to say to them. And it was not
    hypothetical: measured on the live payload the morning this shipped, the
    brain's ENTIRE published opinion was two mults —
    `lighter-ticket-taker-lshadow|short-divergence 0.75` (streak 11) and
    `perps-funding-spread-lshadow|long 0.75` (streak **91**) — and *neither
    book could hear it*. Ninety-one consecutive runs of an organ asking one
    book to take less risk, into a consumer that did not exist. That is I18's
    unreachable-lever shape with the arrow reversed: not a knob with no reader,
    a READER with no knob.

    WHAT THIS DOES **NOT** DO: it returns a NUMBER. Every senior rail sits
    downstream and is untouched — the kill switch still kills, the daily-loss
    halt still halts, the fleet long-budget veto still vetoes, and
    `SafetyRails`' caps remain operator-owned.

    **[CORRECTED IN PLACE, (sp), and this is the important one.** (so) said
    "the multiplier proposes; the rails dispose", meaning a cap would harmlessly
    refuse an over-size clip. **That was wrong in the consequential direction,
    and an adversarial audit of the change measured how wrong.** `notional_ok`
    is a BOOLEAN: the caller's `continue` discards the whole CANDIDATE, not the
    excess. On the shipped live Farmer config (order_usd $37.50, cap $150) a
    brain rung of 4.5 asks $168.75 — over the cap FROM AN EMPTY BOOK — so every
    candidate would be skipped every loop, forever. **The brain rewarding a
    book for its evidence would have stopped it trading.** And the same rail
    inverts selection below that point: a 1.0x entry is refused only once the
    book is FULL, while a 6.7x entry is refused when it is EMPTY.
    Nine of the thirteen wired books had no notional bound at all, so there the
    sentence was not merely wrong but vacuous.
    The claim is true NOW because it was MADE true: the Farmer's rail TRIMS the
    brain's increase to what fits (never below the pre-brain clip) instead of
    refusing; 🙏 Avo's brain is restrict-only, preserving the 1.00x-by-
    construction invariant its own module docstring states; and the shadow
    books that have no rail got one — `BRAIN_GROSS_X`. A safety sentence is a
    claim about behaviour, and it has to be driven, not asserted.**

    Returns the mult beside the clip so the caller can STAMP it on the row.
    That is I22's receipt rule applied to itself: a term that scales every
    stake must record what it applied, or the next session reconstructs it from
    candles like every other unrecorded knob.

    Fail-safe: any doubt returns `(base_usd, 1.0)` — a dark brain, a stale
    payload or a junk value must never resize a book.
    """
    try:
        base = float(base_usd)
    except (TypeError, ValueError):
        return base_usd, 1.0
    try:
        m = float(brain_mult_multi(buckets, current_time))
    except Exception:                                            # noqa: BLE001
        return base, 1.0
    if not (m > 0) or m != m:                    # NaN-safe
        return base, 1.0
    want = base * m
    # [(sp)] THE BOOK-LEVEL GROSS BOUND. See BRAIN_GROSS_X for the measurement
    # and the I22 argument. Two properties make this a bound and not a cage:
    #
    #   1. IT NEVER RETURNS LESS THAN `base`. With the brain neutral, reducing,
    #      dark or stale, the caller's behaviour is BYTE-IDENTICAL to a caller
    #      that never passed these arguments. A safety argument that quietly
    #      shrinks a book when the safety condition is not even active is a
    #      step back wearing a safety costume, and this cannot do that.
    #   2. IT IS PER-BOOK, NOT PER-POSITION. A single 6.7x position is
    #      untouched while the book has room; what runs out is the book's
    #      budget, which is the honest thing to run out of.
    #
    # **[CORRECTED IN PLACE, same day, and the first version was WRONG — I3.**
    # The first draft bounded the brain's INCREASE against
    # `cap - deployed - base`, which is algebraically `min(want, cap-deployed)`
    # — so the FIRST position could take the entire budget and every later one
    # still got its full `base` on top. Driven against carry's real constants
    # through this real accessor: advertised cap $7,200, per-position sizes
    # `[7200, 1200 x 11]`, **actual gross $20,400** — 2.8x the cap it
    # advertised. A bound asserted only on its own arithmetic and never on the
    # SEQUENCE it is supposed to bound is the "check that inspects nothing"
    # rule ((po)) wearing a unit test. The selftest below now drives the whole
    # 12-slot sequence and asserts the TOTAL.
    #
    # THE HONEST BOUND, stated as arithmetic rather than as a round number:
    # one position may reach `cap - deployed`, and the remaining `N-1` still
    # take `base`, so total gross <= `cap + (N-1) * base`. With `cap` set by
    # `brain_gross_cap` to `X * N * base`, that is `(X + 1 - 1/N) * N * base`
    # — about 2.9x the book's no-brain gross at X=2, N=12. Not 2x. Saying 2x
    # here and shipping 2.9x is how a bound becomes folklore.
    #
    # Absent/unusable arguments mean NO BOUND — every existing caller and the
    # two real-money rows (bounded by the operator's SafetyRails cap instead)
    # are unaffected.
    try:
        if want > base and deployed_usd is not None and gross_cap_usd is not None:
            # `slots` — HOW MANY POSITIONS THIS ONE CLIP WILL SIZE. Most books
            # size per-candidate and re-read their deployed total each time, so
            # slots=1 is right for them. Two do NOT: 🌾 carry hoists ONE
            # `_notional` above its census (the (sk) depth probe has to price
            # the clip it is admitting) and ⚖️ Counterweight rebinds ONE
            # `order_usd` at the top of its loop for every leg of the
            # rebalance. For those the bound was evaluated ONCE and applied N
            # times, which is not a bound at all.
            #
            # **[FOUND BY THE AUDIT, DRIVEN NOT READ.** With carry's real
            # constants: cap $7,200, one loop from an EMPTY book sizes the clip
            # at $7,200 and then opens up to TWELVE positions at it —
            # **$86,400**, against the $96,480 the bound was introduced to
            # prevent. It bought almost nothing. The first version of this
            # bound failed on the SEQUENCE; this one failed on the CALL
            # PATTERN, and both failures are the same mistake: testing the
            # arithmetic of one call instead of the behaviour of the loop.**
            room = (float(gross_cap_usd) - float(deployed_usd)) / max(1, int(slots))
            if room != room:                                     # NaN
                raise ValueError
            want = max(base, min(want, room))
    except (TypeError, ValueError):
        want = base * m
    return want, (want / base if base else m)


def brain_clip(bot, entry_tag, base_usd, current_time=None,
               deployed_usd=None, gross_cap_usd=None, slots=1):
    """The single-bucket case of `brain_clip_multi` -> (scaled_usd, mult)."""
    return brain_clip_multi([(bot, entry_tag)], base_usd, current_time,
                            deployed_usd=deployed_usd,
                            gross_cap_usd=gross_cap_usd, slots=slots)


def allocation_scale(bot, current_time=None):
    """💰 fleet_allocation's evidence-weighted capital scale for one SHADOW
    book: `books[bot].target_usd / book_usd`, clamped to [0.25, 4.0], or
    None on any doubt.

    [2026-08-05 (jr) S1 — operator decision "proceed"] The allocation organ
    ranked capital by claim (`max(0, mean − 1.28·SE)`) for four days with
    zero consumers; S1 flips it from advisory to ACTING on the shadow
    notionals of the three funding books — the trio holding every measured
    claim in the fleet. The ORGAN is unchanged (still publish-only,
    `moves_capital: False` — it moves nothing; consumers choosing to read it
    is the same bus pattern as brain stake-mults). Floor 0.25 mirrors the
    organ's own PROBE_FLOOR (I17: a book cannot earn evidence with no
    capital); cap 4.0 keeps a $1k paper book's clip inside sane slippage
    modelling. Scale applies to NEW entries only, at each consumer.

    REAL MONEY NEVER READS THIS — every consumer gates on its shadow arm,
    and `tests/autonomy/test_allocation_consumer.py` pins that. Kill switch:
    `FLEET_ALLOCATION_MODE=advisory` on a service returns None here, i.e.
    every consumer reverts to its env-default clip on the next loop — the
    central-accessor pattern, so the switch reaches the consumer without a
    redeploy ([[a-kill-switch-must-reach-the-consumer]]).

    [2026-08-13 (lx)] EXPANSION IS PRICED ON THE BOOK'S OWN ERA. The organ
    ranks on the ALL-TIME pooled sample — `(kc)` measured that era-scoping the
    ranked claim leaves zero claimants on 15 of 15 days, i.e. it turns the
    organ off, so that is deliberately unchanged. But the ranked claim and the
    thing this accessor DOES are different questions, and the gap between them
    was live: measured 13-Aug, 🌾 carry's 0.149%/trade claim came from n=101
    all-time of which **91 closes predate its own declared era boundary** — the
    17-Jul→29-Jul window in which TWO containers wrote that ledger. The organ
    published the honest number right beside it (`claim_era: null`, n_era=10,
    below its own MIN_N) and this accessor read straight past it and returned
    **4.0x** on new entries. In-era that book reads mean -0.155%, t=-4.48.
    A claim computed on two books' trades is not this book's record (I16), and
    a sample the go-live gate's `integrity` precondition excludes cannot be the
    thing that quadruples a clip.

    THE RULE, and it is one-directional on purpose: a book may be scaled ABOVE
    the flat allocation only while its ERA-scoped claim is a positive number.
    Everything else is untouched — the 25% probe floor still comes from the
    all-time claim, so this can only ever make a book SMALLER, never larger,
    and never smaller than the floor (I17: a book cannot earn evidence with no
    capital). It reverses itself with no intervention the moment the book's own
    era sample reaches MIN_N with a positive bound. Absent/None/NaN `claim_era`
    is "the era has no opinion" and declines the expansion — fail-CLOSED in the
    widening direction, against the usual degrade-to-permissive habit, because
    here the cost of a wrong default is a 4x clip on a sample nobody stands
    behind (the I10 shape, at shadow scale).

    Fail-safe: dark/stale organ, unknown book, junk numbers -> None, and a
    None consumer MUST keep its env default (scale nothing).
    """
    try:
        if os.environ.get("FLEET_ALLOCATION_MODE", "act").strip().lower() \
                != "act":
            return None
        p = _load("fleet-allocation", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        row = (p.get("books") or {}).get(str(bot))
        base = float(p.get("book_usd") or 0.0)
        if not isinstance(row, dict) or base <= 0:
            return None
        return allocation_scale_for(row, base)
    except Exception:
        return None


#: The consumer-side clamp. FLOOR mirrors the organ's own PROBE_FLOOR (I17: a
#: book cannot earn evidence with no capital); CEIL keeps a $1k paper book's
#: clip inside sane slippage modelling.
ALLOC_SCALE_FLOOR = 0.25
ALLOC_SCALE_CEIL = 4.0


def allocation_scale_for(row, base):
    """The effective scale one PUBLISHED allocation row yields — the clamp and
    the era gate, and nothing else. None on an unusable row.

    [2026-08-16 (oy)] EXTRACTED so the organ can PUBLISH the number instead of
    leaving every reader to re-derive it. `allocation_scale` above keeps the
    parts that are about the CALLER — the kill switch, payload freshness, the
    book lookup — and this keeps the parts that are about the ROW. Splitting it
    that way is what lets `fleet_allocation` show its own gated outcome without
    a second copy of the rule ((hj)): there is still exactly one place where
    `target_usd` becomes a scale, and one place where the era decides.

    Deliberately NOT env-aware: a service running
    `FLEET_ALLOCATION_MODE=advisory` gets None from `allocation_scale`
    regardless, and no published field can know that. The organ's published
    number is therefore "what this row yields", never "what every consumer
    will use" — stated here because a field that overstates its own reach is
    the defect this exists to remove.
    """
    try:
        t = float(row.get("target_usd"))
    except (TypeError, ValueError):
        return None
    if t != t or t < 0 or not base or base <= 0:   # NaN / negative / no base
        return None
    scale = max(ALLOC_SCALE_FLOOR, min(ALLOC_SCALE_CEIL, t / base))
    if scale > 1.0 and not era_supports_expansion(row):
        return 1.0
    return scale


def era_supports_expansion(row):
    """True only when a published allocation row's ERA-scoped claim is a
    positive number — the gate on `allocation_scale` growing a book past flat.

    [2026-08-13 (lx)] Deliberately NOT a re-derivation of the era rule. That
    rule has exactly one owner (`golive_readiness.era_rows`, which
    `fleet_allocation._era_twin` imports rather than copies) and a second copy
    of a rule is a second rule ((hj)). This reads the published number and asks
    one question of it.

    A REAL number, not a coercible one. `set_era_twin` writes a float or None,
    so anything else is a shape surprise, and a shape surprise in the WIDENING
    direction declines — the first draft used `float(ce)` and the test caught
    it granting 4.0x off the string `"0.5"`. `bool` is excluded explicitly
    because `isinstance(True, int)` is True in Python and `True > 0.0` would
    otherwise read as evidence. `float('nan') > 0.0` is already False, so NaN
    needs no special case; None, a missing key and every junk type land on
    "no expansion" too.

    [2026-08-26] ...AND `float('inf')` DID NEED ONE. `inf > 0.0` is True, so
    this returned True and GRANTED the expansion the paragraph above promises to
    decline — the one shape surprise that walked straight through the guard
    written for shape surprises. `nan` was fine (`nan > 0.0` is False) and
    `-inf` was fine; only the widening direction leaked, which is the direction
    that matters here.

    HONEST SCOPE, so nobody over-reads it: `bot_pnl_store.json_safe` nulls
    non-finite floats at the write boundary (I5), so a PUBLISHED `inf` is
    unreachable and no consumer can hold one today. This is defence-in-depth on
    the organ's own IN-PROCESS path — `set_era_twin` computes `scale_effective`
    from the raw float before publish, so an in-process `inf` would publish
    `scale_effective` beside `claim_era: null`, an internally contradictory row.
    **Not a live bug; a contract the code did not keep.**

    `math.isfinite` is chosen for INTENT — a non-finite value is not a
    measurement — and NOT because it catches more: `ce == float('inf')` is
    behaviourally identical here, since `-inf > 0.0` and `nan > 0.0` are
    already False. That was verified by a mutation, which SURVIVED; the claim
    that `isfinite` also rescues `-inf` was wrong and is recorded here rather
    than left standing. What the tests pin is that `inf` DECLINES, which is the
    property that matters.
    Note `import math` had to be ADDED to this module — it had none, and
    without it the NameError is swallowed by `allocation_scale`'s blanket
    `except`, silently returning None for every book and disabling the organ
    fleet-wide. A patch that looks like one line is two.
    """
    ce = row.get("claim_era")
    if isinstance(ce, bool) or not isinstance(ce, (int, float)):
        return False
    if not math.isfinite(ce):
        return False
    return ce > 0.0


def lever_outcome(lever, current_time=None):
    """🦾 fleet_proprioception's per-lever OUTCOME verdict: 'helping' |
    'hurting' | 'neutral' | 'insufficient' | None.

    [2026-07-16 CONSUMER SUPPORT] The proprioception organ grades every
    growth-rail lever episode retrospectively (taker = replay counterfactual
    $, scout = grading throughput, gapscout = census activity, live =
    per-trade vs pre-window + shadow twin). This accessor is the ONE
    supported way for any strategy/bot to consume those grades — same
    fail-safe contract as every helper here: dark/stale/absent organ or
    unknown lever -> None, and a None consumer MUST treat it as 'no
    evidence' (restrict nothing, earn nothing). First-party consumers
    (scout tuner, evidence board, experiment judge, incubator) read the
    payload directly on their own cadences; this is the client for
    everyone else.
    """
    try:
        p = _load("fleet-proprioception", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        v = (p.get("verdicts") or {}).get(str(lever))
        vd = v.get("verdict") if isinstance(v, dict) else None
        return vd if vd in ("helping", "hurting", "neutral", "insufficient") \
            else None
    except Exception:
        return None


def long_entries_blocked(current_time=None):
    """L2 fleet-risk veto: True when the fleet's LONG book is at/over budget.

    Uses the side-specific count (long_positions vs long_budget), NOT the
    blended light, so a blown SHORT budget can't freeze long-only spot bots.
    Only enforces when fleet_risk publishes mode='enforce' — flipping the
    service's FLEET_RISK_MODE env to 'advisory' is the central kill switch,
    no strategy redeploy needed. Stale/missing payload -> False (never
    dead-man-switch the whole fleet on a publisher outage).
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("mode")) != "enforce":
            return False
        return int(p.get("long_positions", 0)) >= int(p.get("long_budget", 10**9))
    except Exception:
        return False


def entry_regime_gated(bot, entry_tag, current_time=None):
    """[2026-07-21 BRAIN ACTS] True when the brain has an ACTIONABLE
    regime_timing finding for (bot, entry_tag) AND the regime oracle
    currently reads risk-off — i.e. the exact condition under which this
    tag's losses were measured to cluster (counter_share >= 0.7, streak-
    hardened across PROMOTE_RUNS brain runs before it ever acts).

    Restrict-only (can only SKIP a new entry, never take one), and the gate
    lifts by itself two ways: the oracle turns risk-on (condition ends), or
    the finding retires from the hypothesis ledger (evidence faded). Uses
    the SAME oracle signal the diagnosis measured (`fleet.read` risk-off) —
    never a different regime proxy (the SPY-vs-btc_regime_up lesson).

    Fail-safe OPEN everywhere: stale/missing brain payload, actions_mode !=
    'enforce' (BRAIN_ACTIONS_MODE=advisory is the central kill switch), no
    action for the pair, stale/missing oracle, or any parse error -> False.
    """
    try:
        p = _load("brain-diagnosis", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        if str(p.get("actions_mode")) != "enforce":
            return False
        act = ((p.get("actions") or {}).get(str(bot)) or {}).get(str(entry_tag))
        if not act or act.get("action") != "regime_gate":
            return False
        o = _load("regime-oracle", current_time)
        if not o or not is_fresh(o, current_time):
            return False
        return str((o.get("fleet") or {}).get("read") or "").startswith("risk-off")
    except Exception:
        return False


def oracle_asset_regimes(current_time=None):
    """{sym: verdict} for every pair the regime oracle currently grades, or
    {} when the oracle is dark/stale/absent/malformed.

    [2026-07-30 PER-ASSET GATE — item-18 step 2, operator call] The ONE
    supported read for a per-asset regime consumer (first: the family bot's
    non-crypto gate). Verdicts are the oracle's own strings (LONG-window /
    SHORT-window / dir-flat / chop-gated), passed through untouched.
    Standard accessor fail-safe: any doubt -> {}. NOTE the consumer-side
    rule for NON-CRYPTO entries is fail-CLOSED (a missing sym in this map
    means NO entry — never a BTC fallback); that rule lives at the
    consumer, because this accessor cannot know which symbols a caller
    needs. Crypto consumers keep their own validated gates and should not
    read this.
    """
    try:
        p = _load("regime-oracle", current_time)
        if not p or not is_fresh(p, current_time):
            return {}
        out = {}
        for sym, v in (p.get("pairs") or {}).items():
            vd = v.get("verdict") if isinstance(v, dict) else None
            if isinstance(vd, str) and vd:
                out[str(sym)] = vd
        return out
    except Exception:
        return {}


def long_symbol_blocked(base, current_time=None):
    """[2026-07-21 PER-SYMBOL PILEUP CAP] True when opening ANOTHER long on
    `base` would stack past the fleet's per-symbol cap.

    Companion to long_entries_blocked with the identical contract: enforces
    ONLY when fleet_risk publishes symbol_cap.mode='enforce', restrict-only,
    and fail-safe OPEN — stale/missing payload, absent block, cap<=0, or any
    parse error all return False. [2026-07-22] The published default is now
    ENFORCE — the operator made the review call ("can we fix the budget
    saturation") after (bw) re-measured saturation worse (red 55.9%/48h,
    16/20 slots on 5 symbols); FLEET_SYMBOL_CAP_MODE=advisory on the
    fleet-risk service is the kill switch, and FLEET_RISK_MODE=advisory
    stays SENIOR (a stood-down risk layer publishes the cap as advisory).
    Rationale measured over 168h: 20 long slots behaving as ~7.7 independent
    bets; true LONG-side 4-stacks in ~8.7% of samples (the first-draft 37.1%
    was side-blind — corrected same day; see fleet_risk.py) — de-pileup
    frees budget without raising gross. Wired consumer: the family bot
    (lighter_family_bot.symcap_state/symcap_blocked — same payload plus
    in-cycle stacking awareness across its seven books). Review caution, on
    record from the verify pass and STILL HONOURED: do NOT wire the shadow
    TAKER to this cap — its book is the lens-grading instrument, and
    crowding-capped entries would starve the episode floors and skew the
    live-vs-shadow baselines that steer real money. Family/strategy lanes
    only.
    """
    try:
        p = _load("fleet-risk", current_time)
        if not p or not is_fresh(p, current_time):
            return False
        sc = p.get("symbol_cap") or {}
        if str(sc.get("mode")) != "enforce":
            return False
        cap = int(sc.get("cap") or 0)
        if cap <= 0:
            return False
        held = (sc.get("long_by_symbol") or {}).get(str(base).split("/")[0], 0)
        return int(held) >= cap
    except Exception:
        return False


def market_margins(sym=None, current_time=None):
    """[2026-08-20 (se)] The venue's OWN margin surface, per market.

    Returns `{sym: {"max_lev": float, "imf_bps": float, "mmf_bps": float}}`, or
    a single market's dict when `sym` is given, or `None`/`{}` when the scout is
    dark or stale.

    WHY THIS EXISTS — operator mandate, 2026-08-20: *"you have not set the bots
    up in any way that we could ever really even use leverage."* That is exactly
    right and the cause was mechanical: the venue publishes
    `default_initial_margin_fraction` and `maintenance_margin_fraction` on every
    row of an endpoint the scout already fetched, and NOTHING in this fleet read
    them. Measured across 212 active books the day this shipped: 20x available
    on 21 markets (BTC ETH WTI US100), 15x on 24 (SOL XAU NVDA AAPL), 10x on 88
    — while every Lighter book sizes a flat dollar clip at 1x. The only
    `LEVERAGE` constant in the tree belonged to a RETIRED Hyperliquid bot.

    THE CONTRACT IS FAIL-CLOSED, and it is the OPPOSITE of this module's usual
    one. Every other accessor here degrades to "keep your configured default",
    because the cost of being wrong is a missed shadow trade. Here the cost of a
    wrong default is a LIQUIDATION, which is an unrecoverable loss of the whole
    book — so a dark scout, a stale payload or an absent symbol returns None,
    and a caller that cannot read a margin MUST size as if no leverage were
    available. Never invent a limit; never treat absence as "no limit".
    """
    snap = _load("lighter-market", current_time)
    if not isinstance(snap, dict) or not is_fresh(snap, current_time):
        return None if sym else {}
    m = snap.get("margins")
    if not isinstance(m, dict):
        return None if sym else {}
    if sym is not None:
        row = m.get(sym)
        return row if isinstance(row, dict) and (row.get("max_lev") or 0) > 0 else None
    return {k: v for k, v in m.items()
            if isinstance(v, dict) and (v.get("max_lev") or 0) > 0}


def max_leverage(sym, default=1.0, current_time=None):
    """[2026-08-20 (se)] The venue's max leverage for one market, or `default`.

    `default=1.0` is deliberate and load-bearing: an unreadable margin means the
    caller gets UNLEVERED sizing, never a guess. Raising the default would turn
    a dark bus into leverage nobody chose.
    """
    row = market_margins(sym, current_time=current_time)
    try:
        return float(row["max_lev"]) if row else float(default)
    except (TypeError, ValueError, KeyError):
        return float(default)


def scout_universe(min_vol_m=0.0, limit=None, current_time=None):
    """[2026-07-30 FLEET UNIVERSE — operator: "full universe ... every bot
    needs every tool"] The venue's LIVE tradable universe, as the market
    scout sees it: `[sym, ...]` ordered by 24h $volume descending, filtered
    to `min_vol_m` ($M) and truncated to `limit`.

    WHY THIS EXISTS. Books carried hand-typed watchlists written when
    Lighter was much smaller — Counterweight ranked 30 of 202 books (15%),
    Snap Back 16 (8%), Tide Rider 6, Index Rider 3.

    [2026-07-30 (hk) WHO ACTUALLY CONSUMES THIS — the earlier text implied all
    four did.] Shipped consumers: lighter_dislocation_bot (Snap Back),
    lighter_funding_spread_bot (Counterweight) and, since (hk),
    lighter_trend_bot (Tide Rider, 6 -> 16 measured on the live bus).
    lighter_index_bot (Index Rider) STILL DOES NOT: its signal comes from
    Yahoo equity dailies, not Lighter candles, so a scout-added book without a
    verified YAHOO_REF mapping would publish nulls behind a log warning. Its
    universe is 10 of the venue's 94 non-crypto books and widening it is a
    separate job with its own prerequisite.

    A ranked selector cannot pick a winner it never sees, and unlike loosening a gate,
    enlarging the candidate set does not weaken the selection rule at all:
    Counterweight still takes its top-K/bottom-K, just from a real
    cross-section. The scout already scans every book each cycle, so this
    is a read of work already done — no extra venue load.

    Standard accessor fail-safe: dark/stale/malformed scout -> `[]`, and
    EVERY caller must treat `[]` as "keep my configured list", never as
    "trade nothing". Delisted symbols are excluded (the scout publishes
    them); that is the one filter applied here rather than at the consumer,
    because trading a delisted book is never what any caller wants.
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return []
        # `vols` is the public $M map (2026-07-30). `_marks` is the scout's
        # private diff base, {sym: [qvol, oi]} in raw $ — read as a FALLBACK
        # only, so a consumer shipped ahead of the scout's next deploy still
        # sees the universe instead of going quietly dark.
        vols = p.get("vols")
        if not isinstance(vols, dict) or not vols:
            vols = {}
            for sym, row in (p.get("_marks") or {}).items():
                try:
                    vols[sym] = float(row[0]) / 1e6
                except (TypeError, ValueError, IndexError, KeyError):
                    continue
        if not vols:
            return []
        dead = {str(s) for s in (p.get("delisted") or [])}
        floor = float(min_vol_m or 0.0)
        rows = []
        for sym, vol in vols.items():
            if str(sym) in dead:
                continue
            try:
                vol = float(vol)
            except (TypeError, ValueError):
                continue
            if vol >= floor:
                rows.append((vol, str(sym)))
        rows.sort(reverse=True)
        out = [s for _, s in rows]
        if limit is not None and int(limit) > 0:
            out = out[:int(limit)]
        return out
    except Exception:
        return []


def scout_funding(current_time=None):
    """{sym: apr_pct} — the scout's venue-wide funding map (annualised %,
    signed: positive = longs pay shorts). `{}` on any doubt.

    The single supported read for "what is funding doing across the whole
    venue", so a book no longer has to fetch what the scout already has.
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return {}
        f = p.get("funding")
        if not isinstance(f, dict):
            return {}
        out = {}
        for sym, apr in f.items():
            try:
                out[str(sym)] = float(apr)
            except (TypeError, ValueError):
                continue
        return out
    except Exception:
        return {}


def recorded_cost_bps(sym=None, current_time=None):
    """The fleet's OWN MEASURED execution cost per coin — `{sym: {...}}`, or a
    single coin's dict when `sym` is given. `{}` / `None` on any doubt.

    [2026-08-27] **THE FLEET HAS BEEN RECORDING THIS SINCE 9-JUL AND NOTHING
    HAS EVER READ IT.** Eamon, 27-Aug: *"I think we record things far too
    slowly and it impairs our judgement."* He is right, and the mechanism is
    worse than slow — it was structurally unreachable:

      * `venues/shadow.py` writes `spread_bps` + `slippage_bps` to
        `venue_orders` on EVERY fill. Measured 27-Aug: **3,230 book-walk rows**
        going back to 9-Jul, including SKHYNIXUSD n=409 and SNDK n=112.
      * `market_context.coin_quality()` folds them 14-daily and publishes
        `coin-quality` — **135 coins**, live.
      * And that payload carried `{ts, coins}` and **no `updated` / `ttl_sec`**,
        so `is_fresh` returned False on it FOREVER. A consumer obeying the bus
        contract could never read it, which is why none was ever written.

    The cost of that gap is not hypothetical. The books that needed this number
    gate on a **24h-turnover PROXY** (`MIN_VOL`) — a stand-in `(px)` declared
    as *"per-book slippage here is unmeasured"* while it was being measured —
    and the (ur) study, needing a spread the bus could not give it, fell back
    to **Roll's estimator and overstated the good names 5-12x**, producing a
    refusal on the wrong binding constraint.

    CONTRACT, identical to every sibling here: any doubt returns `{}` (or
    `None` for a single symbol), and **a caller must read that as "I have no
    measurement", never as "the cost is zero"** — a missing cost that defaults
    to free is the same defect this accessor exists to correct, pointed the
    other way. Fields per coin, all optional: `spread_bps` (FULL spread, so
    cost per side is HALF), `slip_bps`, `orders_14d`, `measured_14d`.
    """
    try:
        p = _load("coin-quality", current_time)
        if not p or not is_fresh(p, current_time):
            return None if sym else {}
        coins = p.get("coins")
        if not isinstance(coins, dict):
            return None if sym else {}
        if sym is not None:
            v = coins.get(str(sym))
            return v if isinstance(v, dict) else None
        return {str(k): v for k, v in coins.items() if isinstance(v, dict)}
    except Exception:
        return None if sym else {}


def recorded_half_spread_bps(sym, current_time=None):
    """Cost of ONE side, in bps, for `sym` — or `None` when unmeasured.

    `venue_orders.spread_bps` is `(ask - bid) / mid * 1e4`, i.e. the FULL
    spread, and crossing it costs about HALF per side. That halving is done
    here, in one place, because a caller doing it inline is a second copy of a
    unit convention and this fleet has already paid for one of those (the
    8x funding-basis error).
    """
    rec = recorded_cost_bps(sym, current_time)
    if not rec:
        return None
    try:
        v = float(rec.get("spread_bps"))
    except (TypeError, ValueError):
        return None
    return v / 2.0 if v >= 0 else None


def scout_prem_outliers(current_time=None):
    """[{sym, prem_bps, vol_m}, ...] — the scout's venue-wide premium outliers,
    the same rows the dislocation family's entry gate is measured against.
    `[]` on any doubt, matching every sibling here.

    [2026-08-20] WHY THIS EXISTS, and it is not a widening. A book that trades
    a PREMIUM BAND resolves its universe by VOLUME first, so a dislocation on a
    coin below its volume floor never enters the scan and cannot appear in its
    census at all. `{in_band: 1}` is then byte-identical between "the band is
    quiet" and "the band is busy with names I do not scan" — the exact `(lv)`
    ambiguity I18 exists to remove, arriving one layer earlier than usual
    (the universe filter, not the entry gate).

    MEASURED on 🧭 nav-cook the day this shipped: over 23.9h its [45,60)bps
    band produced **252 confirmed in-band events and the book could trade 3**.
    The other 249 were H100 ($0.02M), UNITREE/CXMT/MRNA/ANSEM (class 7,
    pre-IPO) and USDKRW ($0.02M) — every one refused by a screen the book
    MEASURED and should keep. The book was not stalled; it was correctly
    refusing a supply that had rotated, and nothing it published could say so.

    READ-ONLY and REPORT-ONLY by construction: this returns what the scout
    already computed, and its consumer must use it for the census only. It
    must never widen a gate — the coins it names are excluded ON PURPOSE.

    NOTE the scout hard-caps this list at 8 entries, so it is a view of the
    most extreme outliers, not the whole cross-section. A consumer must not
    read an absence here as "no dislocation".
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return []
        rows = p.get("prem_outliers")
        if not isinstance(rows, list):
            return []
        out = []
        for r in rows:
            if not isinstance(r, dict):
                continue
            sym = r.get("sym")
            if sym is None:
                continue
            rec = {"sym": str(sym)}
            for src, dst in (("prem_bps", "prem_bps"), ("vol_m", "vol_m")):
                try:
                    rec[dst] = float(r.get(src))
                except (TypeError, ValueError):
                    rec[dst] = None
            if rec.get("prem_bps") is None:
                continue          # a row with no premium says nothing
            out.append(rec)
        return out
    except Exception:
        return []


def venue_stress_bps(current_time=None):
    """The scout's venue premium stress in bps, or None when unreadable.

    Same number the Ticket Taker's stress veto reads, so any book can crouch
    on the SAME evidence instead of inventing its own. None = no opinion;
    consumers must fail OPEN on it (a dark scout must never halt a book).
    """
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        st = p.get("stress")
        if isinstance(st, dict):
            # the scout's own key is `med` (see lighter_market_scout.stress);
            # the *_bps aliases are accepted so a future rename cannot
            # silently turn this into a permanent None.
            for k in ("med", "med_bps", "median_bps", "bps"):
                if st.get(k) is not None:
                    return float(st[k])
            return None
        return float(st) if st is not None else None
    except Exception:
        return None


# ---------------------------------------------------------------------------
# [2026-08-05 (ki)] IS THIS BOOK CRYPTO? — one owner, because there were FOUR.
#
# Lighter lists ~27 non-crypto perps (tokenised equities, indices, FX,
# commodities) beside its crypto books, and a FUNDING-RANK book that ranks the
# whole venue by |APR| will happily take them: the extremes of a funding
# cross-section are exactly where the odd instruments sit. Measured on
# ⚖️ Counterweight's own ledger: CRYPTO legs n=69 at +0.227%/trade, NON-CRYPTO
# legs n=19 at **-9.209%/trade, t=-2.80**, both halves negative, -$34.52 — and
# the split survives a BLOCK permutation over close-minute groups at P=0.002
# (legs close in batches, so the effective n is ~23, not 88).
#
# WHY A NEW OWNER RATHER THAN A FIFTH LIST: the fleet already had four, and
# they had drifted — `lighter_ticket_taker.TRADFI_BASES` (58 names, the true
# superset), `fleet_risk.EQUITY_BASES` (28, no commodities or FX),
# `regime_oracle.NONCRYPTO` (10, a category map) and
# `lighter_family_bot.NONCRYPTO_UNIVERSE` (10). The last two are DELIBERATELY
# narrower — "books we have a regime for" and "books the family may trade" are
# different questions from "is this crypto" — so this seeds from the superset
# and a test pins that relationship instead of collapsing them.
NONCRYPTO_BASES = {s.strip().upper() for s in os.environ.get(
    "FLEET_NONCRYPTO_BASES",
    # equities + indices
    "SPY,QQQ,IWM,US100,US500,SOXL,AMD,MU,HOOD,RKLB,TSLA,NVDA,AAPL,MSFT,META,"
    "GOOGL,GOOG,AMZN,COIN,MSTR,PLTR,TSM,INTC,SKHYNIX,AMAT,EWY,LITE,CRCL,BMNR,"
    "SNDK,NBIS,MRVL,ASML,BABA,DELL,ORCL,QCOM,AVGO,ARM,SMCI,SPCX,ZHIPU,CBRS,"
    # commodities (PAXG is gold-backed: a metal price, not a crypto funding
    # signal, and it was one of the five legs 🎸 Barnesy held when this shipped)
    "WTI,BRENTOIL,NATGAS,USOIL,XAU,XAG,XCU,XPD,XPT,PAXG,WHEAT,CORN,"
    # FX
    "USDJPY,AUDUSD,EURUSD,GBPUSD,USDCNH,"
    # [2026-08-06] THE 41 THIS LIST WAS MISSING, from the venue's own
    # `strategy_index` (see `is_crypto`). Kept in sync with the live field so
    # a dark scout falls back to the RIGHT answer rather than to yesterday's.
    # Grouped by the venue's class so the next reconciliation is readable.
    # 4=FX
    "NZDUSD,USDCAD,USDCHF,USDHKD,USDKRW,"
    # 3=commodities
    "H100,URA,"
    # 5=US equities — BB (BlackBerry), BE (Bloom Energy), WEN (Wendy's), BOT,
    # CAP and QNT are the reason this is read and not eyeballed: every one of
    # them reads as a crypto ticker.
    "AAOI,BB,BE,BOT,BOTZ,CRWV,DRAM,GEV,GME,IBM,NOK,NOW,QNT,STRC,TTWO,WEN,"
    # 6=Asian equities
    "BYD,HYUNDAIUSD,MINIMAX,POPMART,SAMSUNGUSD,SKHY,SKHYNIXUSD,SMIC,TENCENT,"
    "XIAOMI,"
    # 7=pre-IPO / private
    "ADI,ANSEM,ANTHROPIC,CAP,CXMT,FOLKS,OPENAI,UNITREE,"
    # [2026-08-20 (ty)] THE EIGHT THIS LIST HAD DRIFTED BY, measured against
    # the venue's own `strategy_index` the same way (ki) measured the original
    # 41: of 101 active non-crypto books, EIGHT were absent from this fallback.
    # With a live scout the screen was right (tier 2 answers); with a DARK or
    # STALE scout every crypto-screened book in the fleet — 🌾 carry, 🏦 Rich
    # Dad, 🪁 band-kelly, 🎫 the Taker, 🎯 the sniper — failed OPEN on these
    # eight, which is precisely the "an organ outage must not silently
    # re-admit equities to a funding-rank book" contract this tier exists to
    # keep. All eight are RECENT listings, which is the drift mechanism: the
    # list is reconciled by hand and the venue lists weekly.
    # 5=US equities · 6=Asian equities · 7=exotic
    "AXTI,SOXS,WDC,KIOXIA,KORU,CASHCAT,MRNA,US10Y").split(",")
    if s.strip()}


#: [2026-08-06] The venue's own class for a crypto book, from the
#: `strategy_index` field on `/api/v1/orderBookDetails` — published by the
#: market scout as `lighter-market.classes`. Everything else it lists
#: (3=commodities, 4=FX, 5=US equities, 6=Asian equities, 7=pre-IPO) is not.
CRYPTO_STRATEGY_INDEX = 2

#: Symbols where the fleet DELIBERATELY overrules the venue's class. The venue
#: files PAXG under crypto (it is a token); the fleet trades it as a metal
#: price, which is the question `is_crypto` is actually asked. Declared here
#: rather than silently, because an override is a judgement call and the next
#: reader is entitled to see whose it was — and (ki) mutation-tested exactly
#: this entry being "corrected" back out.
NONCRYPTO_OVERRIDE = {"PAXG"}


def _venue_class(sym, current_time=None):
    """The venue's own `strategy_index` for `sym`, or None when the scout is
    dark, stale, or has no entry. Never raises."""
    try:
        p = _load("lighter-market", current_time)
        if not p or not is_fresh(p, current_time):
            return None
        classes = p.get("classes")
        if not isinstance(classes, dict):
            return None
        v = classes.get(sym)
        if isinstance(v, bool) or not isinstance(v, (int, float)):
            return None
        return int(v)
    except Exception:      # noqa: BLE001
        return None


def venue_class(sym, current_time=None):
    """The venue's own `strategy_index` for `sym`, or None when unknown.

    Public accessor over `_venue_class` so a consumer that needs the CLASS
    (not merely "is it crypto") reads the venue's own answer instead of
    keeping a hand list — the defect `(ki)`/`(lc)` measured at 41 wrong books
    of 204. Splits the quote off first, exactly as `is_crypto` does.

    Contract: None means NO OPINION (dark/stale scout, unlisted symbol), and
    every caller must fail OPEN on it — refusing on None would silently starve
    a book every time the scout blinked.
    Known indices: 2=crypto 3=commodities 4=FX 5=US equities 6=Asian equities
    7=pre-IPO.
    """
    try:
        s = str(sym or "").strip().upper().split("/")[0]
    except Exception:      # noqa: BLE001
        return None
    if not s:
        return None
    return _venue_class(s, current_time)


def is_crypto(sym, current_time=None):
    """True when `sym` is a crypto book on this venue.

    [2026-08-06] THE VENUE CLASSIFIES ITS OWN INSTRUMENTS AND WE WERE GUESSING.
    `(ki)` made this the ONE owner of the question a day earlier, seeded from
    the widest hand list the fleet had. Measured against the venue's own
    `strategy_index` the next morning, that list was wrong on **41 of 204
    active books** — every FX cross but four, every tokenised Asian equity,
    the whole pre-IPO shelf (ANTHROPIC, OPENAI), and six US tickers that read
    as crypto slang (BB, BE, WEN, BOT, CAP, QNT). A hand list cannot track a
    venue that lists new instruments weekly; this reads the fact instead.

    Order of authority, most specific first:
      1. `NONCRYPTO_OVERRIDE` — the fleet's declared judgement calls;
      2. the scout's published `classes` — the venue's own answer;
      3. `NONCRYPTO_BASES` — the fallback for a dark or stale scout. It is
         kept in sync with (2) rather than retired: an organ outage must not
         silently re-admit 41 equities to a funding-rank book.

    Fail-OPEN at the end: an unrecognised symbol is treated as CRYPTO, because
    the venue lists new crypto books constantly and a closed default would
    silently starve a book every time one appeared. The residual cost is a
    genuinely new non-crypto listing slipping through until the scout's next
    publish — hours now, not "until a human notices"."""
    try:
        # [2026-08-06 (lc)] SPLIT THE QUOTE OFF FIRST. This accepted a BASE
        # only, so every ledger-shaped pair — `SKHY/USDC`, `DRAM/USDC` — missed
        # the set and returned True, i.e. "crypto", fail-open.
        #
        # THE COST, measured: it was used to audit 🎫 the live Taker's ledger
        # for non-crypto positions and reported ZERO. The real count is
        # **19 all-time (−$1.97) and 5 in-era short-divergence** (DRAM,
        # MINIMAX, SKHY, last opened 4-Aug) — over a THIRD of the in-era
        # sample the go-live gate is grading on the book nearest real money.
        # The audit was blind by construction: `pnl_trades.pair` is always
        # `BASE/QUOTE`, and this function only ever compared the whole string.
        # `lighter_ticket_taker._is_crypto` has split on "/" since it was
        # written; the canonical owner did not.
        s = str(sym or "").strip().upper().split("/")[0]
    except Exception:      # noqa: BLE001
        return True
    if not s:
        return True
    if s in NONCRYPTO_OVERRIDE:
        return False
    idx = _venue_class(s, current_time)
    if idx is not None:
        return idx == CRYPTO_STRATEGY_INDEX
    return s not in NONCRYPTO_BASES


#: [2026-08-20 (ty)] Class-7 books that are NOT priced here. `strategy_index 7`
#: is the venue's grab-bag, and its members do not share an answer to the
#: question `venue_priced` asks: ANSEM and CASHCAT are crypto-native tokens
#: whose ONLY market is this book, while ANTHROPIC, OPENAI, SPCX and UNITREE
#: are wrappers around companies priced in private rounds, and US10Y is a bond
#: yield with no spot market at all. The venue publishes no field that splits
#: them, so this is a declared list — kept SMALL and auditable for exactly that
#: reason, and biased toward the safe side: a class-7 name absent from here is
#: treated as venue-priced, which is the direction that admits a new memecoin
#: debut rather than silently starving the source that exists to trade one.
EXOTIC_EXTERNALLY_PRICED = {s.strip().upper() for s in os.environ.get(
    "FLEET_EXOTIC_EXTERNAL",
    # tokenised pre-IPO / private equity — a real company, priced elsewhere
    "ANTHROPIC,OPENAI,SPCX,UNITREE,CXMT,ZHIPU,FOLKS,"
    # listed equities the venue happens to file under 7
    "MRNA,ADI,"
    # not an instrument with a spot market at all
    "US10Y").split(",") if s.strip()}

#: Venue classes whose instruments are always priced somewhere far deeper than
#: this venue: commodities, FX, US equities, Asian equities.
EXTERNALLY_PRICED_CLASSES = {3, 4, 5, 6}

#: The crypto-native class-7 names that `NONCRYPTO_BASES` carries. That list
#: answers "is this class 2", so it correctly excludes them — but `venue_priced`
#: asks a different question and must NOT inherit that exclusion when the scout
#: is dark. Kept as the explicit complement rather than derived, because the
#: venue's class-7 membership is only knowable from the live field; the
#: selftest pins that this set stays disjoint from EXOTIC_EXTERNALLY_PRICED and
#: that every member actually appears in NONCRYPTO_BASES, so a name added to
#: one list and forgotten in the other turns the build red instead of silently
#: re-imposing the screen.
_VENUE_PRICED_EXOTICS = {"ANSEM", "CAP", "CASHCAT"}


def venue_priced(sym, current_time=None):
    """Is THIS VENUE where `sym` is priced?  [2026-08-20 (ty)]

    A DIFFERENT question from `is_crypto`, and the one the (lk) instrument-class
    screen was really asking. That screen's argument was never about class — it
    was that *"a surge-long on USDKRW/BOTZ is a timer-held drift bet on an
    instrument whose venue volume surge is its UNDERLYING's market event,
    already priced where the underlying trades"*. That turns on whether a DEEP
    PRIMARY MARKET exists elsewhere, not on `strategy_index == 2`.

    The distinction is load-bearing because the venue files crypto-native
    memecoin debuts under **class 7**, beside tokenised pre-IPO equity. Asking
    `is_crypto` therefore refuses ANSEM and CASHCAT — the exact cohort a debut
    sniper exists to trade — while a book like 🌾 carry, which wants "is this a
    crypto FUNDING signal", is right to keep asking `is_crypto`. Both questions
    are legitimate; they are not the same question, and (ty) measured the cost
    of conflating them at a source that sat at ZERO admissible candidates for
    66 days while its cohort arrived at ~1.7-2.0 births/30d throughout.

    Order of authority mirrors `is_crypto`: the fleet's declared override, then
    the venue's own class, then the dark-scout fallback. Fail-OPEN on an
    unknown symbol, for the same reason `is_crypto` does — the venue lists new
    books constantly and a closed default silently starves a source.
    """
    try:
        s = str(sym or "").strip().upper().split("/")[0]
    except Exception:      # noqa: BLE001
        return True
    if not s:
        return True
    # The fleet's deliberate disagreements with the venue apply here too: PAXG
    # is a metal price, and a metal is priced far from this book.
    if s in NONCRYPTO_OVERRIDE:
        return False
    if s in EXOTIC_EXTERNALLY_PRICED:
        return False
    idx = _venue_class(s, current_time)
    if idx is not None:
        return idx not in EXTERNALLY_PRICED_CLASSES
    # Dark/stale scout: fall back to the same list `is_crypto` uses, MINUS the
    # class-7 venue-priced names it (correctly, for its own question) carries.
    # Without this subtraction a dark scout would refuse ANSEM/CASHCAT here as
    # well, and the fallback would silently re-impose the very screen this
    # function exists to replace.
    return s not in (NONCRYPTO_BASES - _VENUE_PRICED_EXOTICS)


def crypto_only(symbols):
    """`symbols` with the venue's non-crypto books removed, order preserved.

    Never raises and never returns None — a caller that gets [] must read it as
    "no opinion, keep your configured list", the same contract as
    `scout_universe`."""
    try:
        return [s for s in (symbols or []) if is_crypto(s)]
    except Exception:      # noqa: BLE001
        return list(symbols or [])


# ---------------------------------------------------------------------------
# [2026-08-22 (su)] BASKET INDEPENDENCE — I22's "market count is not bet count",
# with ONE owner.
#
# `(sr)` measured 🙏 Avo holding QQQ/SPY/NVDA at N_eff 1.18 and shipped these
# three functions inside `lighter_avo_live_bot`. The very next measurement
# found 💸 the LIVE Funding Farmer holding BTC/ETH/SOL/XAU at **N_eff 1.389
# (mean rho +0.627)** — and its crypto leg alone at **N_eff 1.11, rho +0.851**:
# three names, one bet, on the fleet's other real-money row, publishing
# `open_trades: 4` with no independence number anywhere. August is what that
# costs — SOL -$2.69, BTC -$2.00, XAU -$1.97, ETH -$1.30, all four losing
# together because they were one position wearing four names.
#
# The second book could have had a COPY of the math. It lives here instead
# because a second copy of a rule is a second rule ((hj)) — and `fleet_bus` is
# already COPY'd into both images (Dockerfile.avolive, Dockerfile.fundinglighter),
# so this costs neither a new dependency nor a born-dark risk.
#
# CONTRACT, unchanged from (sr) and load-bearing: anything unmeasurable is
# **None**, never 0.0. A zero correlation reads as "perfectly diversifying" and
# is the one error that would BUY leverage.
CORR_MIN_OVERLAP = 30      # bars of shared history before a pair is measurable
CORR_LOOKBACK = 180        # bars used per symbol


def bar_returns(bars, n=CORR_LOOKBACK):
    """{bar_ts: simple return} from the newest `n` bars. {} when unusable —
    never a partial series a correlation could be computed off."""
    if not bars:
        return {}
    ts, cs = bars.get("t") or [], bars.get("c") or []
    if len(ts) != len(cs) or len(cs) < CORR_MIN_OVERLAP + 1:
        return {}
    out = {}
    for i in range(max(1, len(cs) - n), len(cs)):
        prev = cs[i - 1]
        try:
            if prev:
                out[ts[i]] = float(cs[i]) / float(prev) - 1.0
        except (TypeError, ValueError, ZeroDivisionError):
            continue
    return out


def pair_corr(a, b):
    """Pearson correlation over the SHARED timestamps. None when the overlap is
    too short or either leg is flat — unknown, never 0.0."""
    days = sorted(set(a) & set(b))
    if len(days) < CORR_MIN_OVERLAP:
        return None
    xs = [a[d] for d in days]
    ys = [b[d] for d in days]
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    vx = sum((v - mx) ** 2 for v in xs)
    vy = sum((v - my) ** 2 for v in ys)
    if vx <= 0 or vy <= 0:
        return None
    cov = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    return cov / ((vx ** 0.5) * (vy ** 0.5))


def basket_n_eff(rets, names):
    """(N_eff, mean_rho) for a basket — the correlation-aware count of
    INDEPENDENT bets. (None, None) when nothing is measurable, so a dark read
    is never credited as independence."""
    names = [n for n in names if rets.get(n)]
    if len(names) < 2:
        return (float(len(names)) if names else None), None
    cs = []
    for i in range(len(names)):
        for j in range(i + 1, len(names)):
            c = pair_corr(rets[names[i]], rets[names[j]])
            if c is not None:
                cs.append(c)
    if not cs:
        return None, None
    rho = sum(cs) / len(cs)
    n = len(names)
    denom = 1.0 + (n - 1) * rho
    return (n / denom if denom > 0 else float(n)), rho


if __name__ == "__main__":
    # offline selftest: prime the cache directly, exercise the fail-safe
    # contract (no DB touched)
    _now = datetime.now(timezone.utc)
    _fresh_p = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 2700,
                "verdicts": {"taker.dip_range": {"verdict": "hurting"},
                             "scout.dip_range_max": {"verdict": "helping"},
                             "weird": {"verdict": "banana"}}}
    _cache["fleet-proprioception"] = {"ts": _now, "payload": _fresh_p}
    assert lever_outcome("taker.dip_range", _now) == "hurting"
    assert lever_outcome("scout.dip_range_max", _now) == "helping"
    assert lever_outcome("taker.tp", _now) is None, "unknown lever -> None"
    assert lever_outcome("weird", _now) is None, "unknown verdict value -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": dict(
        _fresh_p, updated="2020-01-01T00:00:00+00:00")}
    assert lever_outcome("taker.dip_range", _now) is None, "stale -> None"
    _cache["fleet-proprioception"] = {"ts": _now, "payload": None}
    assert lever_outcome("taker.dip_range", _now) is None, "absent -> None"

    # [2026-07-21] per-symbol pileup cap accessor: fail-safe open everywhere
    _risk = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 900,
             "symbol_cap": {"cap": 3, "mode": "enforce",
                            "long_by_symbol": {"ETH": 3, "LTC": 2}}}
    _cache["fleet-risk"] = {"ts": _now, "payload": _risk}
    assert long_symbol_blocked("ETH", _now) is True, "at cap + enforce -> True"
    assert long_symbol_blocked("ETH/USDT", _now) is True, "base-normalizes"
    assert long_symbol_blocked("LTC", _now) is False, "under cap -> False"
    assert long_symbol_blocked("BTC", _now) is False, "unheld -> False"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], mode="advisory"))}
    assert long_symbol_blocked("ETH", _now) is False, "advisory -> inert"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, symbol_cap=dict(_risk["symbol_cap"], cap=0))}
    assert long_symbol_blocked("ETH", _now) is False, "cap 0 -> disabled"
    _cache["fleet-risk"] = {"ts": _now, "payload": dict(
        _risk, updated="2020-01-01T00:00:00+00:00")}
    assert long_symbol_blocked("ETH", _now) is False, "stale -> open"
    _cache["fleet-risk"] = {"ts": _now, "payload": None}
    assert long_symbol_blocked("ETH", _now) is False, "absent -> open"

    # [2026-07-21 BRAIN ACTS] entry_regime_gated: gates ONLY when the brain's
    # streak-hardened action exists AND the oracle reads risk-off right now
    _diag = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
             "actions_mode": "enforce",
             "actions": {"freqtrade-georgia-lshadow":
                         {"long-trend-breakout": {"action": "regime_gate"}}}}
    _orc_off = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 14400,
                "fleet": {"read": "risk-off downtrend"}}
    _orc_on = dict(_orc_off, fleet={"read": "risk-on uptrend"})
    _cache["brain-diagnosis"] = {"ts": _now, "payload": _diag}
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is True, "action + risk-off -> gated"
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-range-on",
                              _now) is False, "no action for tag -> open"
    assert entry_regime_gated("freqtrade-mum-lshadow", "long-trend-breakout",
                              _now) is False, "no action for bot -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_on}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "risk-on -> gate lifts"
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(
        _orc_off, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale oracle -> open"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, actions_mode="advisory")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "advisory kill switch -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": dict(
        _diag, updated="2020-01-01T00:00:00+00:00")}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "stale brain -> open"
    _cache["brain-diagnosis"] = {"ts": _now, "payload": None}
    assert entry_regime_gated("freqtrade-georgia-lshadow", "long-trend-breakout",
                              _now) is False, "absent brain -> open"

    # [2026-07-30 PER-ASSET GATE] oracle_asset_regimes: verdict map passes
    # through fresh; junk rows skipped; stale/absent -> {} (the consumer
    # fails CLOSED on a missing sym — pinned at the family bot's selftest)
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(_orc_off, pairs={
        "SPY": {"verdict": "LONG-window", "class": "equity-index"},
        "XAU": {"verdict": "SHORT-window", "class": "commodity"},
        "BTC": {"verdict": "chop-gated", "class": "crypto"},
        "JUNK": "not-a-dict", "EMPTY": {}, "NONE": {"verdict": None}})}
    assert oracle_asset_regimes(_now) == {
        "SPY": "LONG-window", "XAU": "SHORT-window", "BTC": "chop-gated"}, \
        "fresh pairs pass through; junk/verdictless rows are skipped"
    _cache["regime-oracle"] = {"ts": _now, "payload": dict(
        _orc_off, pairs={"SPY": {"verdict": "LONG-window"}},
        updated="2020-01-01T00:00:00+00:00")}
    assert oracle_asset_regimes(_now) == {}, "stale oracle -> {}"
    _cache["regime-oracle"] = {"ts": _now, "payload": _orc_off}
    assert oracle_asset_regimes(_now) == {}, "no pairs block -> {}"
    _cache["regime-oracle"] = {"ts": _now, "payload": None}
    assert oracle_asset_regimes(_now) == {}, "absent oracle -> {}"

    # [2026-07-21 TWO-WAY MULTS] the clamp passes expand values and still
    # bounds both directions
    _mults = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
              "mults": {"freqtrade-avo-maria-lshadow":
                        {"long-swing-dip": {"mult": 1.25},
                         # [(sn)] 2.0 and 0.25 are now INSIDE the range, so
                         # they no longer test the clamp — they test that the
                         # clamp stopped flattening them, which is the change.
                         # The clamp itself needs values outside 6.7x either
                         # way.
                         "long-deep": {"mult": 0.25},
                         "long-huge": {"mult": 99.0},
                         "long-big": {"mult": 2.0},
                         "long-bad": {"mult": 0.0001}}}}
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-swing-dip",
                            _now) == 1.25, "expand mult passes the clamp"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-huge",
                            _now) == MULT_CEIL == 6.7, \
        "over-ceiling clamps to MULT_CEIL (6.7 since (sn))"
    # …and the two the clamp USED to flatten now pass through untouched
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-big",
                            _now) == 2.0, "2.0x was flattened by the old ceiling"
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-deep",
                            _now) == 0.25, "0.25x was flattened by the old floor"
    # [(sn)] 6.7x EITHER WAY — the floor is the ceiling's reciprocal, derived
    # rather than typed, so the two can never drift apart.
    assert abs(MULT_FLOOR * MULT_CEIL - 1.0) < 1e-12, (MULT_FLOOR, MULT_CEIL)
    assert stake_multiplier("freqtrade-avo-maria-lshadow", "long-bad",
                            _now) == MULT_FLOOR, "under-floor clamps"

    # [2026-08-20 (so)] brain_mult_raw / brain_mult_multi / brain_clip: the
    # accessors every book's sizing site now calls. The property that carries
    # the whole design is the SILENT bucket — it must not out-vote an opining
    # one, because that is precisely the case both real users of the multi
    # form are (⚖️'s untraded side, 🙏's thin live arm).
    assert brain_mult_raw("freqtrade-avo-maria-lshadow", "long-swing-dip",
                          _now) == 1.25, "raw returns the clamped value"
    assert brain_mult_raw("freqtrade-avo-maria-lshadow", "nope", _now) is None, \
        "no opinion is None, NOT 1.0 — the distinction the multi rule needs"
    assert brain_mult_raw("no-such-book", "long", _now) is None, "absent row"
    _b = "freqtrade-avo-maria-lshadow"
    assert brain_mult_multi([(_b, "long-swing-dip"), (_b, "nope")],
                            _now) == 1.25, \
        "a SILENT bucket must not flatten an opining one to 1.0"
    assert brain_mult_multi([(_b, "long-swing-dip"), (_b, "long-deep")],
                            _now) == 0.25, "restrict wins over expand"
    assert brain_mult_multi([(_b, "nope"), (_b, "nope2")], _now) == 1.0, \
        "nobody has an opinion -> neutral"
    assert brain_mult_multi([], _now) == 1.0, "no buckets -> neutral"
    assert brain_clip(_b, "long-swing-dip", 80.0, _now) == (100.0, 1.25)
    assert brain_clip(_b, "nope", 80.0, _now) == (80.0, 1.0), "silent -> base"
    assert brain_clip(_b, "long-swing-dip", None, _now) == (None, 1.0), \
        "an unusable base is returned UNCHANGED, never coerced"
    assert brain_clip_multi([(_b, "long-swing-dip"), (_b, "long-deep")],
                            80.0, _now) == (20.0, 0.25)

    # [(sp)] THE BOOK-LEVEL GROSS BOUND. The property that makes it a bound and
    # not a cage is asserted FIRST: with the brain neutral or REDUCING, passing
    # the bound must change nothing at all.
    assert brain_gross_cap(4, 250.0) == 4 * 250.0 * BRAIN_GROSS_X
    assert brain_gross_cap(0, 250.0) is None and brain_gross_cap(4, 0) is None
    assert brain_gross_cap(4, "x") is None and brain_gross_cap(None, 1) is None
    assert brain_clip(_b, "nope", 80.0, _now,
                      deployed_usd=1e9, gross_cap_usd=1.0) == (80.0, 1.0), \
        "a NEUTRAL brain must be unaffected by the bound — no silent shrink"
    assert brain_clip(_b, "long-deep", 80.0, _now,
                      deployed_usd=1e9, gross_cap_usd=1.0) == (20.0, 0.25), \
        "a REDUCING brain must be unaffected by the bound"
    # ...and it never returns less than the unscaled clip, however full.
    _u, _mm = brain_clip(_b, "long-swing-dip", 80.0, _now,
                         deployed_usd=1e9, gross_cap_usd=1.0)
    assert _u == 80.0 and _mm == 1.0, (_u, _mm)
    # room for the whole increase -> the full 1.25x lands
    assert brain_clip(_b, "long-swing-dip", 80.0, _now,
                      deployed_usd=0.0, gross_cap_usd=1000.0) == (100.0, 1.25)
    # room for HALF the increase -> exactly half of it
    _u, _mm = brain_clip(_b, "long-swing-dip", 80.0, _now,
                         deployed_usd=0.0, gross_cap_usd=90.0)
    assert abs(_u - 90.0) < 1e-9 and abs(_mm - 90.0 / 80.0) < 1e-9, (_u, _mm)
    # the returned mult is the EFFECTIVE one, so the (I23) receipt records what
    # was applied rather than what was wanted — a stamp of 1.25 on a trimmed
    # clip would send the next reader looking for a 25% position that is not
    # there.
    assert abs(_mm - 1.125) < 1e-9, _mm
    # one argument alone is not a bound (both or neither)
    assert brain_clip(_b, "long-swing-dip", 80.0, _now,
                      deployed_usd=0.0) == (100.0, 1.25)
    assert brain_clip(_b, "long-swing-dip", 80.0, _now,
                      gross_cap_usd=90.0) == (100.0, 1.25)
    # junk bound -> no bound, never a refusal
    assert brain_clip(_b, "long-swing-dip", 80.0, _now,
                      deployed_usd="x", gross_cap_usd=90.0) == (100.0, 1.25)
    assert brain_clip(_b, "long-swing-dip", 80.0, _now,
                      deployed_usd=float("nan"),
                      gross_cap_usd=90.0) == (100.0, 1.25)
    # THE MEASURED CASE, DRIVEN AS A SEQUENCE — which is the only way a gross
    # bound can be tested at all. The first version of this bound passed a
    # per-call arithmetic assertion and let carry reach $20,400 against an
    # advertised $7,200, because nothing walked the 12 slots. A bound asserted
    # only on one call is not asserted.
    _cache["brain-stake-mults"] = {"ts": _now, "payload": {
        "updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
        "mults": {"c": {"long": {"mult": 6.7}, "short": {"mult": 6.7}}}}}
    _N, _BASE = 12, 300.0 * 4.0                       # carry x allocation 4.0
    _cap = brain_gross_cap(_N, _BASE)
    assert _cap == _N * _BASE * BRAIN_GROSS_X, _cap
    _dep, _sizes = 0.0, []
    for _ in range(_N):
        _u, _ = brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                                 deployed_usd=_dep, gross_cap_usd=_cap)
        _sizes.append(_u)
        _dep += _u
    # every position is at least the unscaled clip (no silent shrink)...
    assert min(_sizes) >= _BASE - 1e-9, _sizes
    # ...and the TOTAL respects the stated worst case `cap + (N-1)*base`.
    assert _dep <= _cap + (_N - 1) * _BASE + 1e-6, (_dep, _cap)
    assert _dep <= 40800.0 + 1e-6, _dep
    # the unbounded call is what it is bounding AGAINST — assert the contrast,
    # or a bound that happens to be inert reads as a bound that works.
    _un = sum(brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now)[0]
              for _ in range(_N))
    assert _un > _dep, (_un, _dep)

    # ...AND THE PER-LOOP CALL PATTERN, which is a different failure. 🌾 carry
    # and ⚖️ Counterweight size ONE clip per loop and apply it to every entry
    # that loop opens, so a bound that reads `deployed` once and is then used N
    # times is not a bound: driven with carry's real constants it sized $7,200
    # from an EMPTY book and opened twelve at it — **$86,400**, against the
    # $96,480 it was introduced to prevent. `slots` is what makes the per-call
    # bound a per-LOOP bound.
    _free = _N
    _clip1, _ = brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                                 deployed_usd=0.0, gross_cap_usd=_cap,
                                 slots=_free)
    assert _clip1 * _free <= _cap + 1e-6 or _clip1 == _BASE, (_clip1, _cap)
    # slots=1 (the default, and what a per-CANDIDATE book wants) is unchanged
    assert brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                            deployed_usd=0.0, gross_cap_usd=_cap) == \
        brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                         deployed_usd=0.0, gross_cap_usd=_cap, slots=1)
    # a junk or zero slot count must not divide by zero or widen the bound
    for _bad in (0, -3, None, "x"):
        _u, _ = brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                                 deployed_usd=0.0, gross_cap_usd=_cap,
                                 slots=_bad)
        assert _u <= _cap + 1e-6, (_bad, _u)
    # and the no-shrink floor survives `slots`: a full book still gets `base`
    _u, _ = brain_clip_multi([("c", "long"), ("c", "short")], _BASE, _now,
                             deployed_usd=1e9, gross_cap_usd=_cap, slots=_N)
    assert _u == _BASE, _u
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}
    _cache["brain-stake-mults"] = {"ts": _now, "payload": dict(
        _mults, updated="2020-01-01T00:00:00+00:00")}
    assert brain_mult_raw(_b, "long-swing-dip", _now) is None, "stale -> None"
    assert brain_clip(_b, "long-swing-dip", 80.0, _now) == (80.0, 1.0), \
        "a stale brain must never resize a book"
    _cache["brain-stake-mults"] = {"ts": _now, "payload": None}
    assert brain_clip(_b, "long-swing-dip", 80.0, _now) == (80.0, 1.0), \
        "a DARK brain must never resize a book"
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}

    # [2026-08-20 (sp)] THE RESOLVER: atomicity, junk handling, and the memo.
    # JUNK IS NEUTRAL, NOT A 6.7x CUT. The old path clamped whatever arrived,
    # so a publisher bug writing -1 or 0 shrank that bucket to MULT_FLOOR
    # (0.149x) on every entry, silently. A corrupt value is not a size opinion.
    _junk = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 26000,
             "mults": {"j": {"neg": {"mult": -1.0},
                             "zero": {"mult": 0.0},
                             "nan": {"mult": float("nan")},
                             "text": {"mult": "big"},
                             "nomult": {"note": "no mult key"},
                             "listy": [1, 2, 3],
                             "tiny": {"mult": 0.001},     # REAL, clamps
                             "huge": {"mult": 900.0},     # REAL, clamps
                             "ok": {"mult": 1.25}},
                       "bad-book": "not-a-dict"}}
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _junk}
    for _bad in ("neg", "zero", "nan", "text", "nomult", "listy"):
        assert brain_mult_raw("j", _bad, _now) is None, _bad
        assert brain_clip("j", _bad, 80.0, _now) == (80.0, 1.0), _bad
    assert brain_mult_raw("j", "tiny", _now) == MULT_FLOOR, "extreme still clamps"
    assert brain_mult_raw("j", "huge", _now) == MULT_CEIL, "extreme still clamps"
    assert brain_mult_raw("j", "ok", _now) == 1.25
    assert brain_mult_raw("bad-book", "ok", _now) is None, "non-dict book"
    # ...and a junk bucket beside a real one must not drag the pair down: the
    # multi rule takes the min over buckets that HAVE an opinion, and junk has
    # none.
    assert brain_mult_multi([("j", "ok"), ("j", "neg")], _now) == 1.25

    # the whole-map accessor, and its emptiness contracts
    _all = brain_mults(_now)
    assert set(_all) == {"j"} and set(_all["j"]) == {"tiny", "huge", "ok"}, _all
    _cache["brain-stake-mults"] = {"ts": _now, "payload": dict(
        _junk, updated="2020-01-01T00:00:00+00:00")}
    assert brain_mults(_now) == {}, "stale -> empty map"
    _cache["brain-stake-mults"] = {"ts": _now, "payload": dict(
        _junk, updated="not-a-timestamp")}
    assert brain_mults(_now) == {}, "unparseable -> empty map"
    _cache["brain-stake-mults"] = {"ts": _now, "payload": None}
    assert brain_mults(_now) == {}, "dark -> empty map"

    # ATOMICITY: one call must see ONE payload. Swap the cache entry from
    # inside the bucket iteration; the resolved snapshot is taken before the
    # first lookup, so both buckets come from the payload that was current
    # when the call began.
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _junk}

    class _Swapping(list):
        def __iter__(self):
            for _i, _b in enumerate(list.__iter__(self)):
                if _i == 1:
                    _cache["brain-stake-mults"] = {
                        "ts": _now, "payload": {
                            "updated": _now.isoformat(timespec="seconds"),
                            "ttl_sec": 26000,
                            "mults": {"j": {"ok": {"mult": 0.5}}}}}
                yield _b

    assert brain_mult_multi(_Swapping([("j", "ok"), ("j", "ok")]), _now) == 1.25, \
        "a mid-call cache refresh must not mix two payloads into one clip"
    _cache["brain-stake-mults"] = {"ts": _now, "payload": _mults}
    # [2026-07-30 FLEET UNIVERSE] scout accessors: shape, ordering, the
    # volume floor, delist exclusion, and the fail-safe EMPTY that every
    # caller must read as "keep my configured list".
    _scout = {"updated": _now.isoformat(timespec="seconds"), "ttl_sec": 900,
              "vols": {"BTC": 120.0, "SOL": 30.0, "TINY": 0.2, "DEAD": 99.0,
                       "JUNK": "x"},
              "delisted": ["DEAD"],
              "funding": {"BTC": 10.5, "SOL": -3.0, "BAD": "x"},
              "stress": {"n": 98, "max": 50.3, "med": 3.8, "p90": 19.3}}
    _cache["lighter-market"] = {"ts": _now, "payload": _scout}
    assert scout_universe(current_time=_now) == ["BTC", "SOL", "TINY"], \
        "vol-descending, delisted dropped, junk rows skipped"
    assert scout_universe(min_vol_m=1.0, current_time=_now) == ["BTC", "SOL"], \
        "volume floor applied"
    assert scout_universe(limit=1, current_time=_now) == ["BTC"], "limit applied"
    assert scout_funding(_now) == {"BTC": 10.5, "SOL": -3.0}, \
        "funding map coerced, unparseable dropped"
    # the scout's real key is `med` — this assertion is what would have
    # caught the first cut of this accessor, which read a `med_bps` that
    # does not exist and returned None against every real payload.
    assert venue_stress_bps(_now) == 3.8, "stress read from the scout's own `med`"
    # `_marks` FALLBACK: a scout that has not yet redeployed publishes no
    # `vols`, and the consumer must still see the universe (raw $ -> $M).
    _old = {k: v for k, v in _scout.items() if k != "vols"}
    _old["_marks"] = {"BTC": [120e6, 1.0], "SOL": [30e6, 2.0], "BAD": ["x", 0]}
    _cache["lighter-market"] = {"ts": _now, "payload": _old}
    assert scout_universe(current_time=_now) == ["BTC", "SOL"], \
        "pre-deploy scout: _marks fallback keeps the consumer alive"
    _cache["lighter-market"] = {"ts": _now, "payload": _scout}
    # fail-safe: a STALE scout must return neutral-empty, never a partial
    # universe — a book widened onto this accessor falls back to its own
    # configured list, it does not stop trading.
    _stale = dict(_scout)
    _stale["updated"] = (_now - timedelta(hours=3)).isoformat(timespec="seconds")
    _cache["lighter-market"] = {"ts": _now, "payload": _stale}
    assert scout_universe(current_time=_now) == [] and scout_funding(_now) == {}
    assert venue_stress_bps(_now) is None, "stale scout has NO opinion on stress"
    _cache["lighter-market"] = {"ts": _now, "payload": None}
    assert scout_universe(current_time=_now) == [] and scout_funding(_now) == {}
    assert venue_stress_bps(_now) is None

    # ---- (su) basket independence -----------------------------------------
    _ts = list(range(100))
    _a = {t: (0.01 if t % 2 else -0.01) for t in _ts}
    _b = dict(_a)                                              # identical
    _c = {t: -v for t, v in _a.items()}                         # mirrored
    assert pair_corr({1: 0.01, 2: -0.01}, {1: 0.01, 2: -0.01}) is None, \
        "2 bars is under the overlap floor"
    assert abs(pair_corr(_a, _b) - 1.0) < 1e-9
    assert abs(pair_corr(_a, _c) + 1.0) < 1e-9
    assert pair_corr(_a, {t: 0.0 for t in _ts}) is None, \
        "a flat leg is UNKNOWN, never 0.0 — 0.0 would read as perfect diversification"
    _n, _rho = basket_n_eff({"x": _a, "y": _b}, ["x", "y"])
    assert abs(_n - 1.0) < 1e-9 and abs(_rho - 1.0) < 1e-9, \
        "two identical legs are ONE bet"
    assert basket_n_eff({"x": _a}, ["x"]) == (1.0, None)
    assert basket_n_eff({}, ["x"]) == (None, None), \
        "a dark read is never credited as independence"
    assert bar_returns({"t": [1, 2], "c": [1.0, 1.1]}) == {}, \
        "a series under the overlap floor yields NO returns"

    print("fleet_bus selftest OK (lever_outcome fresh/unknown/stale/absent; "
          "long_symbol_blocked enforce/advisory/cap0/stale/absent; "
          "entry_regime_gated act+off/no-tag/no-bot/risk-on/stale-oracle/"
          "advisory/stale-brain/absent; "
          "oracle_asset_regimes fresh/junk-skip/stale/no-pairs/absent; "
          "basket n_eff identical/mirrored/flat-leg/single/dark)")
