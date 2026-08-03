#!/usr/bin/env python3
"""audit_lever_bounds.py — THE CAGE MUST FIT THE VALUE.

[2026-07-30, operator: "if the bounds don't correlate properly then
recalibrate individually"]

A lever is three things that must agree:

  1. the REGISTRY cage      fleet_tuning.LEVERS[name]["lo"/"hi"]
  2. the DECLARED default   fleet_tuning.LEVERS[name]["env_default"]
  3. the CONSUMER's default the `os.environ.get(VAR, "X")` the bot actually runs

Until today only (1) was machine-readable. (2) lived in PROSE inside each
lever's `note`, and (3) lived in a different file entirely — so nothing could
check that the three agreed, and they had already drifted: `scout.ticket_top_n`
was moved 6 -> 12 in the code on 2026-07-30 and its registry note still said
"default 6" the same afternoon. A registry that misdescribes the running value
is worse than no registry: every organ that reasons about headroom — the
board's step ladder, the judge's candidate queue, a human reading the cage —
reasons from a number the fleet is not using.

WHAT THIS ENFORCES
  A. every registered lever carries a machine-readable `env_default`
     (or is DECLARED below with a reason);
  B. that default lies INSIDE its own [lo, hi] — a default outside its cage
     means the very first `get_lever` clamps it, silently changing behaviour
     the operator never asked for;
  C. the declared default MATCHES the consumer's real code default, parsed
     from the consuming file. This is the drift check, and it is the one that
     would have caught the stale note above;
  D. bounds are non-degenerate (lo < hi) — a collapsed cage is a lever that
     cannot move, i.e. dead weight that reads as a growth surface;
  E. every book lever's `step` actually moves INSIDE the cage and terminates
     (a step of 0, or one pointing away from both bounds, is an author that
     can never act).

WHAT IT ONLY REPORTS (not a failure)
  * ONE-SIDED cages — a default pinned at lo or hi. Often correct: an
    emission bar sitting at its most restrictive end has all its room in the
    growth direction. Printed so the asymmetry is visible and deliberate.

Exit 0 = every cage fits. Exit 1 = breaches, named.
`--selftest` proves the detector can still see (negative fixtures).
"""
import ast
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

import fleet_tuning as tuning  # noqa: E402

# lever -> (consuming file, the env var that carries its default).
# A lever absent from this map is not drift-checked (C) but is still checked
# for A/B/D/E. Add an entry when you wire a new consumer — that is the whole
# point: the map is what makes registry-vs-code drift detectable at all.
CONSUMERS = {
    "evsent.min_sources": ("event_sentinel.py", "EVSENT_MIN_SOURCES"),
    "evsent.severity_bar": ("event_sentinel.py", "EVSENT_SEVERITY_BAR"),
    "scout.ticket_top_n": ("lighter_market_scout.py", "SCOUT_TICKET_TOP_N"),
    "scout.brk_range_min": ("lighter_market_scout.py", "SCOUT_BRK_RANGE_MIN"),
    "scout.dip_range_max": ("lighter_market_scout.py", "SCOUT_DIP_RANGE_MAX"),
    "scout.div_gap_pp": ("lighter_market_scout.py", "SCOUT_DIV_GAP"),
    "scout.momo_chg_min": ("lighter_market_scout.py", "SCOUT_MOMO_CHG_MIN"),
    "taker.dip_range": ("lighter_ticket_taker.py", "TT_DIP_RANGE"),
    "taker.brk_range": ("lighter_ticket_taker.py", "TT_BRK_RANGE"),
    "taker.momo_chg": ("lighter_ticket_taker.py", "TT_MOMO_CHG"),
    "taker.div_gap_pp": ("lighter_ticket_taker.py", "TT_DIV_GAP"),
    "taker.tp": ("lighter_ticket_taker.py", "TT_TP"),
    "taker.sl": ("lighter_ticket_taker.py", "TT_SL"),
    "taker.max_hold_h": ("lighter_ticket_taker.py", "TT_MAX_HOLD_H"),
    "taker.sl_cooldown_h": ("lighter_ticket_taker.py", "TT_SL_COOLDOWN_H"),
    "xp.funding.enter_apr": ("lighter_funding_bot.py", "FUNDING_ENTER_APR"),
    "live.funding.enter_apr": ("lighter_funding_bot.py", "FUNDING_ENTER_APR"),
    "xp.funding.take_profit": ("lighter_funding_bot.py", "FUNDING_TAKE_PROFIT"),
    "live.funding.take_profit": ("lighter_funding_bot.py", "FUNDING_TAKE_PROFIT"),
    "xp.funding.max_hold_h": ("lighter_funding_bot.py", "FUNDING_MAX_HOLD_H"),
    "live.funding.max_hold_h": ("lighter_funding_bot.py", "FUNDING_MAX_HOLD_H"),
    "xp.funding.min_vol": ("lighter_funding_bot.py", "FUNDING_MIN_VOL"),
    "live.funding.min_vol": ("lighter_funding_bot.py", "FUNDING_MIN_VOL"),
    "xp.funding.explore_k": ("lighter_funding_bot.py", "SCAN_EXPLORE_K"),
    "live.funding.explore_k": ("lighter_funding_bot.py", "SCAN_EXPLORE_K"),
    "carry.enter_apr": ("funding_carry_bot.py", "CARRY_ENTER_APR"),
    "carry.max_positions": ("funding_carry_bot.py", "CARRY_MAX_POSITIONS"),
    "carry.min_vol": ("funding_carry_bot.py", "CARRY_MIN_VOL"),
    "fundspread.k": ("lighter_funding_spread_bot.py", "FUNDSPREAD_K"),
    "fundspread.universe_n": ("lighter_funding_spread_bot.py",
                              "FUNDSPREAD_UNIVERSE_N"),
    "disloc.enter_pct": ("lighter_dislocation_bot.py", "DISLOC_ENTER_PCT"),
    "disloc.universe_n": ("lighter_dislocation_bot.py", "DISLOC_UNIVERSE_N"),
    "index.max_open": ("lighter_index_bot.py", "INDEX_MAX_OPEN"),
    "sniper.surge_mult": ("lighter_perp_sniper.py", "SNIPER_SURGE_MULT"),
}

# lever -> reason it carries no machine-readable default. Silence is not an
# option; a missing default must be DECLARED, the BORN_DARK_OK pattern.
DEFAULT_OK = {
    "gapscout.extra_exchanges":
        "list-valued lever (uses `allowed`, not lo/hi) — Gap Scout RETIRED 17-Jul",
}
# Consumers whose default is computed, not a literal, so (C) cannot parse it.
# [2026-07-30 (hl)] `index.max_open` was HERE and is now gone. It was the one
# lever whose consumer default tracked the universe (`str(len(SYMBOLS))`), so
# the drift arm — the whole point of this guard — was blind to precisely the
# lever most able to drift. And it HAD drifted: the registry said 10 while the
# code computed 9. The consumer is now a literal, so the exemption is
# unnecessary; re-adding it would re-blind the guard.
# LESSON, general: an entry here is a hole in the guard. Prefer making the
# consumer literal over declaring the exemption.
DRIFT_OK = {
    "xp.funding.conviction_hi": "default is _CDHI, a mode-dependent tuple unpack",
    "live.funding.conviction_hi": "default is _CDHI, a mode-dependent tuple unpack",
    "xp.funding.slope_gate": "consumer default is the string 'on', mapped to 1",
    "live.funding.slope_gate": "consumer default is the string 'on', mapped to 1",
    "trend.rank_by_funding": "consumer default is the string '1', parsed to bool",
    "live.clip_scale": "no env var: the neutral 1.0 is the call-site default",
    "gapscout.prefilter_gap": "Gap Scout RETIRED 17-Jul — consumer idles behind a guard",
    "gapscout.max_book_fetches": "Gap Scout RETIRED 17-Jul — consumer idles behind a guard",
}


def _literal_env_default(path, var):
    """The literal in `os.environ.get("VAR", "<literal>")` in `path`, or None
    when the call is absent or the default is computed rather than literal."""
    try:
        tree = ast.parse((ROOT / path).read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return None
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        if not (isinstance(f, ast.Attribute) and f.attr == "get"):
            continue
        if not (isinstance(f.value, ast.Attribute) and f.value.attr == "environ"):
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if node.args[0].value != var or len(node.args) < 2:
            continue
        d = node.args[1]
        if isinstance(d, ast.Constant):
            return d.value
        return None                       # computed default — not drift-checkable
    return None


def _as_number(raw):
    """'10e6' -> 10000000.0, '12' -> 12.0, 'on' -> None."""
    try:
        return float(str(raw).strip())
    except (TypeError, ValueError):
        return None


def check(levers=None, consumers=None):
    levers = tuning.LEVERS if levers is None else levers
    consumers = CONSUMERS if consumers is None else consumers
    problems, onesided = [], []

    for name, spec in sorted(levers.items()):
        lo, hi = spec.get("lo"), spec.get("hi")
        dflt = spec.get("env_default")

        if lo is None or hi is None:
            if name not in DEFAULT_OK:
                problems.append(f"{name}: no lo/hi bounds and not declared in "
                                f"DEFAULT_OK")
            continue

        # (D) a collapsed cage is a lever that cannot move
        if not lo < hi:
            problems.append(f"{name}: degenerate cage lo={lo} hi={hi} — "
                            f"a lever that cannot move is not a growth surface")

        # (A) machine-readable default, or a declared reason
        if dflt is None:
            if name not in DEFAULT_OK:
                problems.append(f"{name}: no machine-readable `env_default` "
                                f"(prose in `note` is not checkable)")
            continue

        # (B) the default must live inside its own cage
        if not lo <= dflt <= hi:
            problems.append(f"{name}: DEFAULT {dflt} IS OUTSIDE its cage "
                            f"[{lo}, {hi}] — the first get_lever clamps it, "
                            f"silently changing behaviour nobody asked for")
        elif dflt in (lo, hi):
            onesided.append(f"{name}: default {dflt} sits AT "
                            f"{'lo' if dflt == lo else 'hi'} "
                            f"[{lo}, {hi}] — all its room is in one direction")

        # (C) THE DRIFT CHECK: registry default vs the consumer's real default
        ent = consumers.get(name)
        if ent and name not in DRIFT_OK:
            path, var = ent
            raw = _literal_env_default(path, var)
            got = _as_number(raw)
            if raw is None:
                problems.append(f"{name}: consumer default not found — "
                                f"`os.environ.get({var!r}, ...)` absent from "
                                f"{path} (renamed var, or the consumer is gone)")
            elif got is None:
                problems.append(f"{name}: consumer default {raw!r} in {path} "
                                f"is not numeric and is not declared in DRIFT_OK")
            elif abs(got - float(dflt)) > 1e-9:
                problems.append(
                    f"{name}: REGISTRY/CODE DRIFT — registry says "
                    f"env_default={dflt}, {path} actually runs {var}={got}. "
                    f"Every organ reasoning about this lever's headroom is "
                    f"reasoning from the wrong number.")

        # (E) a book lever's step must move inside the cage and terminate
        step = spec.get("step")
        if step is not None and spec.get("lane") == "lighter-books":
            if step == 0 and lo != hi and spec["kind"] != "int":
                problems.append(f"{name}: step is 0 — its author can never act")
            elif step:
                nxt = tuning.clamp(name, dflt + step)
                if nxt is None:
                    problems.append(f"{name}: step {step} clamps to None")
                elif nxt == dflt and lo < dflt < hi:
                    problems.append(f"{name}: step {step} does not move the "
                                    f"value off its default ({dflt})")

    print(f"lever bounds: {len(levers)} registered, "
          f"{len(consumers)} drift-checked against their consumer, "
          f"{len(DEFAULT_OK)} default-exempt, {len(DRIFT_OK)} drift-exempt")
    for line in onesided:
        print(f"  one-sided cage (informational): {line}")
    if problems:
        print("\nBOUNDS DO NOT CORRELATE:")
        for p in problems:
            print(f"  * {p}")
        print(f"\naudit_lever_bounds: {len(problems)} problem(s).")
        return 1
    print("audit_lever_bounds: OK — every cage fits its value, and every "
          "registry default matches the code its consumer actually runs.")
    return 0


def _selftest():
    """Negative fixtures — the detector must still SEE each breach class."""
    base = {"kind": "float", "lo": 0.0, "hi": 1.0, "lane": "paper-scanner"}

    # (B) default outside its cage
    assert check({"x.a": {**base, "env_default": 2.0}}, {}) == 1
    # (A) no machine-readable default
    assert check({"x.b": {**base}}, {}) == 1
    # (D) degenerate cage
    assert check({"x.c": {**base, "lo": 1.0, "hi": 1.0, "env_default": 1.0}},
                 {}) == 1
    # (C) registry/code drift — registry says 0.5, the file runs 0.25
    drift = {"scout.div_gap_pp": {"kind": "float", "lo": 0.0, "hi": 100.0,
                                  "lane": "lighter-scout", "env_default": 0.5}}
    assert check(drift, {"scout.div_gap_pp": ("lighter_market_scout.py",
                                              "SCOUT_DIV_GAP")}) == 1
    # ...and a missing consumer var is caught too
    assert check({"x.d": {**base, "env_default": 0.5}},
                 {"x.d": ("lighter_market_scout.py", "NO_SUCH_VAR_XYZ")}) == 1
    # a clean lever passes
    assert check({"x.e": {**base, "env_default": 0.5}}, {}) == 0
    print("audit_lever_bounds --selftest OK "
          "(outside-cage, no-default, degenerate, DRIFT, missing-var, clean)")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else check())
