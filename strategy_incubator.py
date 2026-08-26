#!/usr/bin/env python3
"""
strategy_incubator.py — 🧬 the fleet's REPRODUCTION organ.

WHY (2026-07-15, operator: "build reproduction"). Everything else ADAPTS
existing bots one knob at a time. This organ BREEDS: it generates whole
GENOTYPES (multi-parameter combinations — crossover + mutation of the best
performers), evaluates the population, and lets the winners reproduce.

TWO SUBSTRATES, and the safety line is drawn between them:

  TAKER genotypes (SHADOW-only, evaluated instantly). The Ticket Taker is a
    $1k shadow book with a replay harness, so a genotype's fitness is the
    replayed closed-net over the recorded tape (both-halves-positive). The
    incubator breeds a population each cycle, ranks by fitness, keeps the
    elite, and publishes the leaderboard. Fully autonomous, zero real money
    — no genotype here can ever reach a live book.

  FUNDING candidates (LIVE-reachable, but GATED). The Funding Farmer is
    live; there is no cheap funding replay, so the incubator cannot pre-
    score funding offspring. It therefore PROPOSES novel funding genotypes
    to bot_state 'xp-queue', and the EXPERIMENT JUDGE runs each through the
    identical paired promotion bar (>=7d, >=30 shadow closes, beats live on
    the window AND both halves) before ANY of it touches real money. An
    offspring gets NO shortcut a human-written candidate wouldn't get.

INVENTION vs ADAPTATION — the honest boundary (unchanged): the incubator
recombines parameters WITHIN the fleet_tuning registry bounds. It does not
write new trading LOGIC. Genuinely new strategy code stays a human +
backtest job; autonomy covers the search over known genes, not the
invention of new ones. Nothing here bypasses NO_REAL_MONEY or the judge.

Publishes bot_state 'strategy-incubator' (leaderboard + elite) and appends
to 'xp-queue'. Run-once; run_all.sh loops it. --selftest is offline.
"""
import json
import math
import os
import statistics
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
# [2026-07-17] LOUD-fail import: brain_stats is integral to gamete scoring
# now, so a missing/broken file must still crash this run-once organ (no
# silent degrade) — but VISIBLY. run_all.sh's `|| true` swallowed the
# traceback and the reproduction organ would simply go dark (the exact
# born-dark class the 17-Jul Dockerfile audit closed).
try:
    import brain_stats as bs
except Exception as _e:  # noqa: BLE001
    print(f"[incubator] FATAL: brain_stats unimportable ({_e!r}) — the "
          f"reproduction organ CANNOT run; check the image's COPY list "
          f"(see 17-Jul born-dark postmortem)", flush=True)
    raise
import fleet_tuning as tuning
import lighter_ticket_taker as tt
import lighter_ticket_replay as rp

try:
    import fleet_proprioception as proprio   # outcome grades (optional import)
except Exception:  # noqa: BLE001
    proprio = None

KEY = "strategy-incubator"
QUEUE_KEY = "xp-queue"
TTL_SEC = int(os.environ.get("INCUBATOR_TTL_SEC", "10800"))
ELITE_N = int(os.environ.get("INCUBATOR_ELITE_N", "4"))
MIN_SNAPS = int(os.environ.get("INCUBATOR_MIN_SNAPS", "60"))
# [2026-07-15 ANTI-OVERFIT] The max-over-a-population on a SHORT tape is biased
# upward — you select the luckiest genotype, not the best. (First live cycle:
# the "fittest" scored +$2.35 but h1 was +$0.01 — all edge in one half = noise
# wearing a both-halves badge.) A genotype is only a trusted CHAMPION when:
#   the tape carries >= MIN_CLOSES closed trades AND spans >= MIN_TAPE_HOURS,
#   each half clears HALF_MARGIN (not just >0), it beats the DEFAULT genome by
#   EDGE_MARGIN, AND it stays the champion for PERSIST_CYCLES independent
#   cycles. Until then the leaderboard is published but explicitly flagged
#   tentative (noise-risk) — trusted by nothing.
#
# [2026-07-17 DENOMINATION] Those gates were denominated in HOURS and DOLLARS.
# The fleet's quantum of evidence is ONE FILL. Measured on the real tape
# (15-Jul 04:27Z -> 16-Jul 23:03Z, 42.7h): 11 closed trades, 10 of them the
# same stop-loss. At clip $50 / TP +4% / SL -3% one trade flipping SL->TP
# swings $3.50 — MORE than the old EDGE_MARGIN ($2.00), and one take-profit
# (+$1.96) alone cleared the old HALF_MARGIN ($1.00). Every anti-overfit gate
# was satisfiable by a single lucky fill; they looked strict and were not.
# Both margins are now denominated in TRADE SWINGS, and the champion gate
# counts CLOSES — hours are not evidence (a 200h tape with 11 closes passed
# MIN_TAPE_HOURS and was still noise). An explicit env override still wins.
MIN_TAPE_HOURS = float(os.environ.get("INCUBATOR_MIN_TAPE_HOURS", "48"))
PERSIST_CYCLES = int(os.environ.get("INCUBATOR_PERSIST", "3"))
# closed trades on the tape before ANY genotype can be crowned. ~6 closes/day
# at the observed rate, so ~7 days of tape — and >=20 per half for the
# both-halves test to mean anything.
MIN_CLOSES = int(os.environ.get("INCUBATOR_MIN_CLOSES", "40"))
# closed trades a genotype needs to enter the BREEDING pool (see select_elite)
MIN_GT_CLOSES = int(os.environ.get("INCUBATOR_MIN_GT_CLOSES", "12"))
EDGE_TRADES = float(os.environ.get("INCUBATOR_EDGE_TRADES", "2.0"))   # vs default
HALF_TRADES = float(os.environ.get("INCUBATOR_HALF_TRADES", "1.0"))   # each half


def _env_f(name, derived):
    """Explicit operator override wins; otherwise the trade-denominated bar."""
    v = os.environ.get(name)
    return float(v) if v not in (None, "") else derived


# $ swing of ONE fill flipping SL->TP at the default genome — the smallest
# unit of evidence this tape can produce. Any gate below it is noise.
TRADE_SWING = abs(tt.TAKE_PROFIT - tt.STOP_LOSS) * tt.CLIP_USD
HALF_MARGIN = _env_f("INCUBATOR_HALF_MARGIN", HALF_TRADES * TRADE_SWING)
EDGE_MARGIN = _env_f("INCUBATOR_EDGE_MARGIN", EDGE_TRADES * TRADE_SWING)

# TAKER genes: (tt attr, lever, discrete allele grid within registry bounds).
# The grid is the search space; offspring are points on it.
TAKER_GENES = {
    # [2026-08-20 (sk)] the 0.97 allele is gone — see the cage note in
    # fleet_tuning. An allele the registry clamps is a gene that silently
    # breeds to a different value than the one scored, and this one bred
    # TIGHTER than the operator's default on a lens the replay cannot fill.
    "BRK_RANGE": ("taker.brk_range", [0.90, 0.93, 0.95]),
    "DIP_RANGE": ("taker.dip_range", [0.05, 0.08, 0.11, 0.15]),
    "MOMO_CHG": ("taker.momo_chg", [3.0, 4.0, 5.0, 6.0]),
    # [2026-07-17] DIV_GAP_PP was the one taker lever in the fleet_tuning
    # registry (taker.div_gap_pp, bounds 300-700) that the taker consumes and
    # the scout tuner walks, but the GENE POOL omitted — so the fleet's only
    # SHORT lens was unevolvable and the genome was long-only. On the measured
    # tape divergence is also the only lens not losing (+$2.10 — on n=1, which
    # is itself the point). The tuner's ladder only ever WIDENS (500->300);
    # this grid also explores TIGHTENING, which nothing else in the fleet does.
    # [2026-07-17 BASIS FIX] grid /8 with the fleet-wide funding basis — the
    # apr these pp measure was 8x TRUE. Same alleles, true units; every one
    # must stay inside the (also /8) registry bounds 37.5-87.5.
    "DIV_GAP_PP": ("taker.div_gap_pp", [37.5, 50.0, 62.5, 75.0, 87.5]),
    "TAKE_PROFIT": ("taker.tp", [0.03, 0.04, 0.05, 0.06]),
    "STOP_LOSS": ("taker.sl", [-0.04, -0.03, -0.02]),
    # [(sk)] the 24h allele is gone with the cage — see BRK_RANGE above.
    "MAX_HOLD_H": ("taker.max_hold_h", [48.0, 72.0]),
}
# The gene whose alleles the TAPE must be long enough to exercise (see
# reachable_genes) — a hold >= the span never fires.
HOLD_GENE = "MAX_HOLD_H"
# lens -> the ENTRY gene that acts on that lens ALONE. The exit genes
# (TAKE_PROFIT/STOP_LOSS/MAX_HOLD_H) are pleiotropic — exit_reason() is
# lens-blind, so one allele acts on every lens at once — and are never dropped.
LENS_GENE = {"breakout": "BRK_RANGE", "dip": "DIP_RANGE",
             "momentum": "MOMO_CHG", "divergence": "DIV_GAP_PP"}
# FUNDING genes (live-reachable, judge-gated): allele grids within xp bounds.
FUNDING_GENES = {
    # [2026-07-17 BASIS FIX] /8 — TRUE apr; must sit inside the (also /8)
    # registry bounds 0.03125-0.075, which these do (0.0375/0.05/0.0625).
    "enter_apr": ("xp.funding.enter_apr", [0.0375, 0.05, 0.0625]),
    "take_profit": ("xp.funding.take_profit", [0.04, 0.05, 0.06]),
    # [2026-07-29 AUDIT R2] max_hold_h REMOVED from the grid. The hold-cap
    # knob is refuted at ANY number (21-Jul review + CHANGELOG: "2/59 twin
    # closes hit max_hold; no cap value can move the paired mean by the
    # judge's +0.5pp bar — a 7-day slot wasted at ANY number"). The 28-Jul
    # queue-TTL fix retired the STORED hold-48/-96 candidates, but this grid
    # could REGENERATE them under the same names once the rolling dedup caps
    # (judge verdicts[-10:], incubator memory[-20:]) overflow — permanence
    # must be structural, not two rolling windows. Selftest pins the absence;
    # re-adding the gene is a deliberate act against a recorded refutation.
}


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


def queue_carry(queue, now):
    """[2026-07-28 §3b residual] Which stored xp-queue candidates carry
    forward into this cycle's republish: the payload's OWN updated+ttl_sec
    decides, fail-CLOSED — exactly the read the judge's candidate_pool now
    does on the consumer side. A stale or unstamped queue carries NOTHING:
    that is what retires dead entries (the 17-Jul tape-refuted rows the
    28-Jul review found) instead of resurrecting them under a fresh stamp.
    Pure — selftested."""
    q = queue or {}
    cands = [c for c in (q.get("candidates") or []) if isinstance(c, dict)]
    try:
        upd = datetime.fromisoformat(
            str(q.get("updated")).replace("Z", "+00:00")).timestamp()
        if float(now) - upd > float(q.get("ttl_sec") or 0):
            return []
    except Exception:      # noqa: BLE001
        return []
    return cands


# ---------------------------------------------------------------------------
# evidence (pure — selftested)
# ---------------------------------------------------------------------------

# One-sided 90% Student-t quantiles, df 1..30, converging to brain_stats.Z80
# (the fleet's evidence convention). At the n<20 this tape yields, the normal
# approximation is far too generous — t prices the small sample honestly.
_T90 = (3.078, 1.886, 1.638, 1.533, 1.476, 1.440, 1.415, 1.397, 1.383, 1.372,
        1.363, 1.356, 1.350, 1.345, 1.341, 1.337, 1.333, 1.330, 1.328, 1.325,
        1.323, 1.321, 1.319, 1.318, 1.316, 1.315, 1.314, 1.313, 1.311, 1.310)


def t90(df):
    """One-sided 90% t quantile; Z80 past the table (df -> inf)."""
    if df < 1:
        return float("inf")
    return _T90[df - 1] if df <= len(_T90) else bs.Z80


#: [2026-08-26] THE UP-REGIME RESOLVER — built ONCE PER CYCLE in run_once and
#: threaded through rank() into evaluate()'s three replays.
#:
#: WHY IT EXISTS, and why its absence made every hatchling stillborn:
#: `lighter_ticket_replay.replay(up_resolver=None)` forces `up=False` for the
#: breakout lens, so the taker's relabel to `breakoutup` NEVER fires and that
#: lens cannot appear in the report at all (`rp.UNREACHABLE_WITHOUT_RESOLVER`
#: says so in the harness's own words). `lighter_scout_tuner` passes a resolver
#: and reads the whole book; this organ did not, and scored a DIFFERENT BOOK
#: from the one the taker runs — the tuner's baseline over production's own
#: 2200-snapshot window read +$22.21 with `breakoutup` contributing +$34.39
#: over 22 closes, while the incubator's IDENTICAL default genome read
#: -$62.02. An $84.23 gap against gates that are $3.50 (half) and $7.00 (edge)
#: wide, and the population died at every one: h1>0 in 0 of 1519 genotypes,
#: both_halves_pos 0, elite 0. Lowering HALF_MARGIN to $0.00 still yielded
#: zero survivors — the bars were never the cause, the BASIS was.
#:
#: BUILT ONCE, NOT PER GENOTYPE: a cycle scores ~1519 genotypes x 3 replays,
#: and the resolver fetches daily candles per symbol. Per-genotype construction
#: would be ~4500 builds of the same object.
#:
#: WHY THIS IS A LOCAL BUILDER RATHER THAN AN IMPORT OF THE TUNER'S. The RULE
#: is `rp.daily_up_resolver` and it is IMPORTED, never re-implemented — no
#: second copy of the regime logic exists here. What is local is the gate:
#: `lighter_scout_tuner.build_up_resolver` is guarded by the TUNER's own
#: `SCOUT_TUNER_UP_RESOLVER` switch and logs under the tuner's name, so
#: importing it would (a) give this organ no kill switch of its own and
#: (b) let one organ's kill switch silently revert ANOTHER organ's fitness to
#: the exact defect above, unannounced ([[a-kill-switch-must-reach-the-consumer]],
#: I8 on the log line). The two builders are ~6 lines of tape traversal each.
UP_RESOLVER_ON = os.environ.get(
    "INCUBATOR_UP_RESOLVER", "1").strip().lower() not in ("0", "off", "false", "no")


def tape_symbols(tape):
    """Every symbol the tape ever ticketed, sorted. Pure — selftested."""
    return sorted({t.get("sym") for _, p in (tape or [])
                   for arr in ((p or {}).get("tickets") or {}).values()
                   for t in (arr or []) if isinstance(t, dict) and t.get("sym")})


def build_up_resolver(tape, _factory=None):
    """Per-cycle `up(sym, ts)` resolver over every symbol the tape ticketed.

    Returns None on ANY trouble — the caller must treat that as REDUCED
    COVERAGE (breakout/breakoutup unreachable), never as an error. `_factory`
    is injectable so the selftest never touches the network."""
    if not (UP_RESOLVER_ON and tape):
        return None
    try:
        syms = tape_symbols(tape)
        if not syms:
            return None
        make = _factory or rp.daily_up_resolver
        return make(syms, tape[0][0].timestamp(), tape[-1][0].timestamp())
    except Exception as exc:      # noqa: BLE001 — coverage is best-effort
        print(f"[incubator] up-resolver unavailable: {type(exc).__name__}: {exc}",
              flush=True)
        return None


def live_lenses(lens_fwd, realised=None):
    """The lenses the LIVE taker is currently ALLOWED to fill (2026-07-17).

    [2026-08-02] THE THIRD CONSUMER, and the one CLAUDE.md predicted: the veto
    was extracted into a single authority because "a third copy was about to
    land in the incubator". It never became a copy — but it called that
    authority with HALF THE EVIDENCE, which produces the same wrong answer by a
    different route. Passing no `realised` means the lens's OWN closes are
    invisible, so this excluded `divergence` — the only lens the live arm may
    fill — on the 4h forward proxy `(ij)` proved is the wrong horizon for a
    book that holds a bracket. The incubator would then breed genes for the
    lenses the live book CANNOT trade, which is the very fiction this function
    was written to stop.

    The replay is deliberately veto-blind — "external bus state isn't in this
    tape" — which is right for a pure harness and which each CONSUMER is then
    expected to correct for. The tuner does (it never widens a brain-vetoed
    lens). The incubator did NOT, and it was breeding a fiction: measured
    16-Jul, the brain grades breakout (n=2241, avg4h -0.184%, hit 40.5%), dip
    (n=2110, -0.438%, 42.6%) and momentum (n=1178, -0.233%, 41.0%) negative at
    sample size, so the live taker vetoes all three and only DIVERGENCE
    (n=2463, +0.041%, 55.2%) can fill. Ten of the tape's eleven closes came
    from lenses the live bot refuses to trade.

    Fail-safe OPEN, matching the taker's own documented direction: no grades =
    nothing vetoed. Freshness is the caller's job (see fresh_lens_fwd)."""
    return set(LENS_GENE) - tt.vetoed_lenses(lens_fwd, realised=realised)


def scored_lens_set(allowed, mults_payload=None, bot_row=None):
    """The lenses whose P&L may ENTER the fitness — `allowed` plus, when it is
    not self-vetoed, the taker-internal `breakoutup`.

    WHY IT IS A SEPARATE SET FROM `allowed`. `LENS_GENE` is a map of lens -> the
    ENTRY GENE that acts on that lens ALONE, and `breakoutup` has no gene of its
    own: it is a RELABELLED SUBSET of the breakout population, admitted through
    the same `BRK_RANGE` bar in `tt.incredible` and renamed afterwards. Adding
    it to `LENS_GENE` would therefore make `evolvable_genes` drop `BRK_RANGE`
    whenever EITHER name is vetoed, which is a tightening nobody measured. So
    the scored set widens and the gene map does not.

    THE VETO IS THE TAKER'S, ASYMMETRIC, AND IMPORTED — never re-derived here.
    `lighter_ticket_taker` relabels BEFORE it applies `lens_vetoed` (see the
    entry loop's "(dk) breakout_up RELABEL — BEFORE the veto"), which is exactly
    how the up-regime subset escapes the broad `breakout` veto and keeps
    filling. So a vetoed `breakout` does NOT imply a vetoed `breakoutup`, and
    gating this on `breakout in allowed` would reproduce the defect in
    production, where the brain vetoes breakout/dip/momentum and only
    `divergence` survives. `breakoutup` earns its own veto from its own
    `long-breakoutup` closes via `tt.breakoutup_self_vetoed`, which is
    restrict-only and fail-OPEN on a missing/thin grade.

    FRESHNESS IS THE CALLER'S JOB — that function's own docstring says so
    ("The CALLER owns freshness"), mirroring the lens-forward read. Pass `{}`
    (or None) for a dark/stale brain stake-mults payload and nothing is vetoed,
    documented degrade. Pure — selftested."""
    out = set(allowed or ())
    try:
        if not tt.breakoutup_self_vetoed(mults_payload,
                                         bot_row if bot_row is not None else tt.BOT_ROW):
            out.add("breakoutup")
    except Exception:      # noqa: BLE001 — fail-OPEN, matching the taker
        out.add("breakoutup")
    return out


def fresh_lens_fwd(state, now):
    """The brain's lens grades if they are FRESH, else {} (which vetoes
    nothing). Mirrors the tuner's lf_fresh check. Pure — selftested."""
    try:
        u = datetime.fromisoformat(str((state or {}).get("updated"))
                                   .replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        if (now - u.timestamp()) <= float((state or {}).get("ttl_sec") or 0):
            return (state or {}).get("lenses") or {}
    except (ValueError, TypeError, AttributeError):
        pass
    return {}


#: [2026-08-26] THE ONE HALF THAT COULD NOT BE WIRED IN THIS PASS — DECLARED,
#: not taken silently.
#:
#: `tt.breakoutup_self_vetoed` needs the RAW brain stake-mults payload: it
#: reads the bucket's `n` as well as its `mult`, and `fleet_bus.brain_mults`
#: drops `n` on the way through the [MULT_FLOOR, MULT_CEIL] clamp, so no
#: mediated accessor can answer the question. Reading that key here is exactly
#: the taker's own (dm) pattern — a BOOLEAN veto, never a size — and the fleet
#: guard `tests/autonomy/test_brain_sizing_reaches_every_book.py` requires any
#: such reader to be DECLARED in its `RAW_READ_OK` map with a reason (the taker
#: is the one entry there today). That test file was outside this pass's
#: ownership, so the read is WITHHELD rather than smuggled past a substring
#: scan by importing the key from elsewhere.
#:
#: CONSEQUENCE, stated rather than discovered later: the self-veto is fail-OPEN
#: here, so a `breakoutup` the brain has DECISIVELY graded a loser still enters
#: this organ's fitness. That is strictly better than the defect it replaces
#: (the lens was excluded ALWAYS, winner or loser) and strictly worse than the
#: taker's own behaviour. It is published in the funnel every cycle so it
#: cannot rot into folklore.
#:
#: TO CLOSE IT, two lines: add `"strategy_incubator.py"` to that guard's
#: `RAW_READ_OK` with the taker's reason, then make `stake_mults_payload()`
#: return the brain's stake-mults bot_state payload and flip the flag. The
#: KEY STRING is deliberately absent from this module: that guard is a plain
#: substring scan over the file text, so even naming the key in prose trips
#: it — which is itself the honest signal that the declaration is owed.
BRKUP_VETO_WIRED = False


def stake_mults_payload():
    """The brain's raw per-close-tag grades, or {} while the read is withheld.

    Kept as a seam rather than an inline `{}` so the freshness path above stays
    exercised and closing the gap is a one-line body change."""
    return {}


def fresh_stake_mults(state, now):
    """The brain's stake-mults payload if FRESH, else {} (vetoes nothing).

    `tt.breakoutup_self_vetoed` states that the CALLER owns freshness, and the
    taker's own read allows a 26000s fallback TTL — mirrored here rather than
    invented, so the two consumers cannot disagree about what 'fresh' means.
    A future-dated stamp reads NOT fresh (the taker's `0 <= age` guard).
    Pure — selftested."""
    try:
        u = datetime.fromisoformat(str((state or {}).get("updated"))
                                   .replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=timezone.utc)
        age = now - u.timestamp()
        if 0 <= age <= float((state or {}).get("ttl_sec") or 26000):
            return state or {}
    except (ValueError, TypeError, AttributeError):
        pass
    return {}


def evolvable_genes(genes, allowed):
    """Drop the ENTRY gene of any lens the taker is vetoing: its allele cannot
    move a single live fill, so breeding it is search over a bot that does not
    exist. Restrict-only; pleiotropic exit genes are always kept. Returns
    (genes, dropped)."""
    out, dropped = dict(genes), []
    for lens, gene in LENS_GENE.items():
        if lens not in allowed and gene in out:
            del out[gene]
            dropped.append(gene)
    return out, sorted(dropped)


def _marked(rep, lenses=None):
    """[2026-07-17 IMB-10 parity — mirrors lighter_scout_tuner._marked]
    closed_net + end-of-tape unrealized, optionally restricted to `lenses`
    (the ones the live taker may actually fill — see live_lenses).

    closed_net ALONE is blind to DEFERRAL: a genotype 'wins' by pushing losses
    past the tape's end, where open positions are valued at entry and invisible
    to the very gate accepting on them. The tuner's gates went deferral-proof
    first; the bred leaderboard/champion (dashboard-only today) must not keep a
    bias a future consumer would inherit. It is not hypothetical here: the real
    tape shows ZERO hold-exits and 10-of-11 closes are stop-losses, so "never
    close anything" was the strongest gradient in the landscape — and the
    MAX_HOLD grid offered 48h/72h alleles on a 42.7h tape to express it with."""
    if lenses is None:
        return float(rep["closed_net"]) + float(rep.get("unrealized") or 0.0)
    net = sum(float(s.get("net") or 0.0)
              for l, s in (rep.get("lenses") or {}).items() if l in lenses)
    upnl = sum(float(o.get("upnl") or 0.0)
               for o in (rep.get("open") or []) if o.get("lens") in lenses)
    return net + upnl


def _pnl_usd(rep, lenses=None):
    """Every closed trade's net $ (replay field, 17-Jul), optionally only for
    the lenses the live taker may fill — a vetoed lens's fills are evidence
    about a bot that does not exist and must not enter the fitness.

    This is the EVIDENCE COUNT's series (closed trades only — an open position
    is not evidence of a closed edge). For the series the LCB must PRICE, see
    _marked_series: these two are deliberately different questions."""
    out = []
    for l, s in (rep.get("lenses") or {}).items():
        if lenses is None or l in lenses:
            out.extend(s.get("pnl_usd") or [])
    return out


def _marked_series(rep, lenses=None):
    """[2026-07-17 AUDIT] The per-trade series the LCB must price: every closed
    trade PLUS each end-of-tape open position marked at its unrealized — the
    per-trade decomposition of _marked, so sum(_marked_series) == _marked (to
    rounding) and the bound prices exactly the quantity `net` reports.

    _pnl_usd ALONE is the censored sample _marked exists to fix (see :227). It
    was the PRIMARY sort key while net/h1/h2 were marked, so `rank` selected on
    precisely the deferral-blind measure the line above it disclaims: a genotype
    that pushed a $50 loss past the tape's end scored lcb=+20 on a marked net of
    -$30 and took rank 1 — and run_once assesses ONLY scored[0], so the deferrer
    also evicted the genuinely-best genotype from ever being assessed. Not
    hypothetical: the real tape has ZERO hold-exits, so "never close anything"
    is the strongest gradient in the landscape."""
    out = list(_pnl_usd(rep, lenses))
    for o in (rep.get("open") or []):
        if lenses is None or o.get("lens") in lenses:
            out.append(float(o.get("upnl") or 0.0))
    return out


def net_lcb(pnl_usd):
    """One-sided 90% LOWER CONFIDENCE BOUND on the total net of these trades.

    The winner's curse: a max-over-population on a POINT estimate selects the
    luckiest genotype, not the best. This file's header said exactly that in
    July and then ranked the breeding elite on... the point estimate. The LCB
    prices uncertainty, so a thin or noisy genotype cannot out-rank a robust
    one on luck alone. Std error of a SUM of n draws is sd*sqrt(n)."""
    n = len(pnl_usd)
    if n == 0:
        return 0.0
    total = float(sum(pnl_usd))
    if n == 1:
        return min(total, 0.0)          # one trade evidences no edge, ever
    return total - t90(n - 1) * statistics.stdev(pnl_usd) * math.sqrt(n)


def reachable_genes(genes, tape_hours):
    """[2026-07-17 IMB-10] Drop MAX_HOLD alleles the tape cannot exercise: a
    hold >= the span never fires, so its 'edge' is unpriced open risk rather
    than evidence. Mirrors lighter_scout_tuner's _skipped_holds. Returns
    (genes, dropped). No-op when the span is unknown or nothing is unreachable
    — and never strips the grid bare (a filter that leaves no allele is a
    filter that has stopped measuring anything)."""
    spec = genes.get(HOLD_GENE)
    if not spec or tape_hours <= 0:
        return genes, []
    lever, grid = spec
    keep = [h for h in grid if h < tape_hours]
    dropped = [h for h in grid if h >= tape_hours]
    if not keep or not dropped:
        return genes, []
    return dict(genes, **{HOLD_GENE: (lever, keep)}), dropped


# ---------------------------------------------------------------------------
# genetics (pure — selftested)
# ---------------------------------------------------------------------------

def seed_population(genes):
    """The founding genotypes: the env-default genome + each single-gene
    neighbour (the axis probes). Deterministic — no RNG (Math.random is
    unavailable in this runtime anyway, and reproducibility aids testing)."""
    default = {g: getattr(tt, g) for g in genes}
    pop = [dict(default)]
    for g, (_lever, grid) in genes.items():
        for allele in grid:
            if allele != default[g]:
                pop.append({**default, g: allele})
    return dedupe(pop)


# [2026-07-29] JOINT-SPACE EXPLORATION (operator: "give it everything it needs
# to explore every option possible").
#
# THE BLOCKER, measured before building: the organ was searching ONE DIMENSION
# from ONE POINT, forever. seed_population emits the default genome plus its
# single-gene AXIS PROBES — it never varies two genes at once — and the only
# thing that explores interactions is breed(), which returns [] when the elite
# is empty. select_elite demands both_halves_pos, and no genotype on this tape
# clears it (the whole taker surface is negative), so the elite IS empty and
# the population collapses to 11 axis probes per cycle. Gene INTERACTIONS were
# unreachable by construction.
#
# And the budget was never the constraint: one evaluate() is ~32ms on a
# 2200-snap tape, so the old cycle spent ~0.4s of an hourly (3600s) loop. The
# full 7-gene product is 11,520 genotypes — ~370s, comfortably affordable.
#
# So: enumerate the JOINT product deterministically and walk it with a
# persistent CURSOR, covering a bounded slice each cycle and wrapping. Over
# successive cycles the organ sweeps the ENTIRE legal space rather than
# resampling one neighbourhood — the same coverage-cursor pattern the fleet
# already uses, and the reason the (f7cad49) explore-zero bug is worth not
# repeating: a cursor that never sweeps is a search that never explores.
# Deterministic (no RNG — reproducible, and the runtime has no seeded source
# this organ should depend on).
EXPLORE_N = int(os.environ.get("INCUBATOR_EXPLORE_N", "1500"))
# what lands in the durable register per cycle; the rest are scored, ranked
# and discarded. Without this a 1500-genotype cycle would evict every dormant
# entry and the register would stop being durable.
REGISTER_TOP_N = int(os.environ.get("INCUBATOR_REGISTER_TOP_N", "24"))


# [2026-07-29] RESEARCH SPACE — exploring BEYOND the registry cage.
#
# WHY THIS IS SAFE, and the reasoning must survive: the incubator has NO
# ACTUATOR. Its only consumer is the dashboard (verified: nothing outside
# pnl_dashboard.py reads bot_state 'strategy-incubator'). The fleet_tuning
# cages bound what the SCOUT TUNER may ENACT on the shadow taker; they were
# never a bound on what this organ may MEASURE. Clamping the search to them
# bought no safety and cost the whole out-of-cage question.
#
# WHAT IS ACTUALLY AT RISK is confusion, not money: an out-of-cage genotype
# scoring well could be mistaken for something shippable. So every scored
# genotype is stamped `enactable`, the published CHAMPION is drawn ONLY from
# the enactable subset (the champion is the thing a human might act on), and
# out-of-cage results are reported separately as the FRONTIER.
#
# The dividend is a question the fleet could not previously ask: IS THE CAGE
# IN THE WRONG PLACE? If the best genotypes pile up against a bound, that
# bound is binding and the evidence for moving it is right there — which is
# how a cage widening should be justified, rather than by an argument about
# what values are reachable (the A1 non-sequitur this session already found).
#
# Grids extend a step or two past each bound and are deliberately MODEST:
# under today's vetoes the research space is ~900 genotypes (~29s), a full
# sweep in one cycle. Kill switch: INCUBATOR_RESEARCH=off returns the search
# to the cage exactly.
RESEARCH_MODE = os.environ.get("INCUBATOR_RESEARCH", "on").lower() != "off"
RESEARCH_GENES = {
    # [(sk)] UNCHANGED, deliberately: RESEARCH grids are required to extend
    # BEYOND the cage (`is_enactable` is what gates action, and the selftest
    # fails a research grid that never leaves it). Only TAKER_GENES — the
    # ENACTABLE pool — lost the alleles the (sk) cage now refuses.
    "BRK_RANGE":   ("taker.brk_range",   [0.85, 0.90, 0.93, 0.95, 0.97, 0.99]),
    "DIP_RANGE":   ("taker.dip_range",   [0.03, 0.05, 0.08, 0.11, 0.15, 0.20]),
    "MOMO_CHG":    ("taker.momo_chg",    [2.0, 3.0, 4.0, 5.0, 6.0, 8.0]),
    "DIV_GAP_PP":  ("taker.div_gap_pp",  [25.0, 37.5, 50.0, 62.5, 75.0, 87.5, 100.0]),
    "TAKE_PROFIT": ("taker.tp",          [0.02, 0.03, 0.04, 0.05, 0.06, 0.08]),
    "STOP_LOSS":   ("taker.sl",          [-0.06, -0.04, -0.03, -0.02, -0.015]),
    # [(sk)] UNCHANGED for the same reason as BRK_RANGE above.
    "MAX_HOLD_H":  ("taker.max_hold_h",  [12.0, 24.0, 48.0, 72.0, 96.0]),
}


def is_enactable(genotype, genes=None):
    """Could this genotype ever be ENACTED — i.e. does every allele survive
    its lever's registry clamp unchanged? Pure; fail-CLOSED (an unknown gene
    or an unclampable value reads NOT enactable, because the honest answer to
    'could this ship?' under uncertainty is no)."""
    genes = genes or TAKER_GENES
    for g, v in (genotype or {}).items():
        spec = genes.get(g) or RESEARCH_GENES.get(g)
        if not spec:
            return False
        try:
            if tuning.clamp(spec[0], v) != v:
                return False
        except Exception:      # noqa: BLE001
            return False
    return True


def cage_analysis(scored, genes=None):
    """Is the CAGE binding? For each gene: the best-scoring allele among
    enactable genotypes, whether it sits ON a registry bound, and whether any
    out-of-cage allele scored better. A gene whose best result is pinned to a
    bound AND beaten from outside — BY A GENOTYPE WITH A POSITIVE LOWER BOUND
    — is evidence that the bound, not the strategy, is the limit.

    [2026-07-29] That lcb condition is not decoration; the first version of
    this function lacked it and fired a FALSE "widen the cage" on its very
    first live run. It flagged STOP_LOSS because -0.06 (out-of-cage) beat the
    -0.04 bound on net. Adversarially checked: mean net improves MONOTONICALLY
    as the stop widens, across all 180 configs per value (-15.10 at -0.015 ->
    -2.37 at -0.06) — the textbook "a wider stop stops realising losses that
    later revert" artifact, the same shape that produced and then WITHDREW the
    funding STOP verdict. Even the widest stop is mean-NEGATIVE, so the bound
    was never what stood between this book and an edge. Comparing MAX point
    estimates over a large sweep is the winner's curse this file's own rank()
    exists to avoid, so the bar is a positive LOWER bound: the evidence
    doctrine that governs crowning a champion also governs asking to move a
    cage. Publish-only; proposes nothing. Pure."""
    genes = genes or TAKER_GENES
    out = {}
    for g, (lever, grid) in genes.items():
        best_in = best_out = None
        for s in (scored or []):
            v = (s.get("genotype") or {}).get(g)
            if v is None:
                continue
            net = s.get("net")
            if not isinstance(net, (int, float)):
                continue
            try:
                inside = tuning.clamp(lever, v) == v
            except Exception:      # noqa: BLE001
                inside = False
            lcb = s.get("lcb")
            lcb = lcb if isinstance(lcb, (int, float)) else None
            # champion-grade = the bar for crowning, applied to the bar for
            # asking to move a cage: positive in its own right, positive
            # LOWER bound, and positive in BOTH halves.
            grade = bool(net > 0 and lcb is not None and lcb > 0
                         and s.get("both_halves_pos"))
            cur = best_in if inside else best_out
            if cur is None or net > cur[1]:
                if inside:
                    best_in = (v, net, lcb, grade)
                else:
                    best_out = (v, net, lcb, grade)
        if best_in is None:
            continue
        lo, hi = min(grid), max(grid)
        at_bound = best_in[0] in (lo, hi)
        beaten = bool(best_out and best_out[1] > best_in[1])
        # THE WINNER'S-CURSE GUARD. A MAX over a large sweep is not evidence,
        # and a positive lower bound on that max is not enough either — pick
        # the best of 900 and some lcb will be positive by chance. The claim
        # is only earned by a CHAMPION-GRADE result (positive, positive lower
        # bound, positive in both halves). Measured on the first live sweep:
        # 17 of 900 genotypes were both-halves-positive and EVERY one had a
        # negative lcb, so nothing in the research space clears this — which
        # is the correct answer, not a missing feature.
        credible = bool(best_out and best_out[3])
        out[g] = {"best_in_cage": best_in[0], "net_in": round(best_in[1], 2),
                  "at_cage_bound": at_bound,
                  "best_out_of_cage": best_out[0] if best_out else None,
                  "net_out": round(best_out[1], 2) if best_out else None,
                  "lcb_out": (round(best_out[2], 2)
                              if best_out and best_out[2] is not None else None),
                  "cage_may_bind": bool(at_bound and beaten and credible)}
    return out


def joint_space_size(genes):
    """How many genotypes the full product contains. Pure."""
    n = 1
    for _g, (_lever, grid) in sorted(genes.items()):
        n *= max(1, len(grid))
    return n


def explore_slice(genes, cursor, n):
    """(population, next_cursor, space_size) — the next `n` genotypes of the
    JOINT gene product, walked deterministically from `cursor` and wrapping.

    Enumeration is over sorted gene names and their grids, so the order is
    stable across cycles and processes: the cursor means the same thing next
    hour as it did this hour. `n <= 0` explores nothing (a clean kill switch);
    a space smaller than `n` is returned once, whole, with the cursor advanced
    modulo the space so coverage keeps its meaning. Pure — selftested."""
    if not genes or n <= 0:
        return [], int(cursor or 0), joint_space_size(genes or {})
    names = sorted(genes)
    grids = [genes[g][1] for g in names]
    size = joint_space_size(genes)
    start = int(cursor or 0) % size
    take = min(n, size)
    pop = []
    for k in range(take):
        idx = (start + k) % size
        gt, rem = {}, idx
        for name, grid in zip(names, grids):
            gt[name] = grid[rem % len(grid)]
            rem //= len(grid)
        pop.append(gt)
    return dedupe(pop), (start + take) % size, size


def dedupe(pop):
    seen, out = set(), []
    for gt in pop:
        k = tuple(sorted(gt.items()))
        if k not in seen:
            seen.add(k)
            out.append(gt)
    return out


def conform(genotypes, genes):
    """Project stored genotypes onto the CURRENT gene set (2026-07-17).

    The gene set is now DYNAMIC — alleles are dropped when the tape cannot
    exercise them (reachable_genes), the entry gene of a brain-vetoed lens is
    dropped (evolvable_genes), and DIV_GAP_PP was added — so a genotype
    carried forward in prior['elite'] can disagree with `genes` in BOTH
    directions. breed() indexes a[g] for every g in genes, so one stale elite
    entry would KeyError the whole organ on its next cycle: the currently
    published elite were bred before the divergence gene existed. Missing
    genes take the module default; unknown genes are dropped. An off-grid
    allele survives (breed's mutation no-ops on it; genotype_to_levers clamps
    it), because a value the operator is really running is not invalid."""
    out = []
    for gt in genotypes or []:
        if isinstance(gt, dict):
            out.append({g: gt.get(g, getattr(tt, g)) for g in genes})
    return dedupe(out)


def breed(elite, genes):
    """Next generation from the elite: CROSSOVER (gene-wise pairing of the
    top two) + MUTATION (each elite genome, each gene stepped to its adjacent
    allele). Deterministic and bounded to the allele grids."""
    if not elite:
        return []
    offspring = list(elite)
    # crossover: for each adjacent elite pair, swap each gene one at a time
    for a, b in zip(elite, elite[1:]):
        for g in genes:
            if a[g] != b[g]:
                offspring.append({**a, g: b[g]})
                offspring.append({**b, g: a[g]})
    # mutation: nudge each gene to its neighbouring allele on the grid
    for gt in elite:
        for g, (_lever, grid) in genes.items():
            if gt[g] in grid:
                i = grid.index(gt[g])
                for j in (i - 1, i + 1):
                    if 0 <= j < len(grid):
                        offspring.append({**gt, g: grid[j]})
    return dedupe(offspring)


def genotype_to_levers(genotype, genes):
    """Map a genotype (tt-attr keyed) to fleet_tuning lever names + values,
    clamped + registry-validated. Drops any gene that fails the registry."""
    out = {}
    for g, val in genotype.items():
        lever = genes.get(g, (None,))[0]
        if lever is None:
            continue
        c = tuning.clamp(lever, val)
        if c is not None:
            out[lever] = c
    return out


# ---------------------------------------------------------------------------
# fitness (taker: replay over the tape)
# ---------------------------------------------------------------------------

def evaluate(genotype, tape, lenses=None, up_resolver=None):
    """Fitness of a TAKER genotype = replayed MARKED net over the tape (see
    _marked), with a both-halves-positive flag (an offspring that only wins
    one lucky half is not fit), the closed-trade COUNT (the real evidence
    unit) and a lower confidence bound. `lenses` restricts the score to the
    lenses the live taker may actually fill. Patches tt bars, restores.

    `up_resolver` is the cycle's ONE resolver (see build_up_resolver) and is
    passed to EVERY replay here — the full tape and both halves. Passing it to
    some and not others would grade a genotype's halves on different lens
    COVERAGE from its own total, which is worse than being blind three times.
    None is the pre-2026-08-26 behaviour: breakout/breakoutup unreachable."""
    saved = {g: getattr(tt, g) for g in genotype}
    try:
        for g, v in genotype.items():
            setattr(tt, g, v)
        full = rp.replay(tape, up_resolver=up_resolver)
        mid = len(tape) // 2
        h1 = _marked(rp.replay(tape[:mid], up_resolver=up_resolver), lenses) if mid else 0.0
        h2 = _marked(rp.replay(tape[mid:], up_resolver=up_resolver), lenses) if mid else 0.0
    finally:
        for g, v in saved.items():
            setattr(tt, g, v)
    pnl = _pnl_usd(full, lenses)
    return {"net": round(_marked(full, lenses), 3), "h1": round(h1, 3),
            "h2": round(h2, 3), "closes": len(pnl),
            # [2026-07-17 AUDIT] bound the MARKED series, not the censored
            # closed-only one — `closes` stays the closed-trade evidence count
            "lcb": round(net_lcb(_marked_series(full, lenses)), 3),
            # both-halves POSITIVE-BY-MARGIN — a +$0.01 half is noise, not edge
            "both_halves_pos": h1 >= HALF_MARGIN and h2 >= HALF_MARGIN}


def rank(population, tape, lenses=None, up_resolver=None):
    scored = [{"genotype": gt, **evaluate(gt, tape, lenses, up_resolver=up_resolver)}
              for gt in population]
    # [2026-07-17] fittest = highest LOWER BOUND, not the highest point
    # estimate. Ranking a population by its max point estimate IS the winner's
    # curse this file's header warns about; net only breaks ties between
    # equally-evidenced genotypes.
    #
    # [2026-07-17 AUDIT] `closes > 0` leads the key because net_lcb([]) == 0.0
    # — "no evidence" scored a bound of ZERO, which beats every genotype with
    # evidence of LOSS. On a net-negative tape (today's: the brain grades 3 of
    # 4 lenses negative) rank 1 therefore went to a genotype that never fired,
    # and since run_once assesses only scored[0], NO genotype that trades could
    # ever be crowned — the champion card read "no champion yet" by
    # construction, not by measurement. Fixed HERE and not in net_lcb because
    # `lcb` is published: -inf would be invalid JSON and Postgres JSONB would
    # reject the whole payload. select_elite already refuses these genotypes
    # (min_closes); this makes rank agree with it.
    scored.sort(key=lambda s: (s["closes"] > 0, s["lcb"], s["net"]),
                reverse=True)
    return scored


def select_elite(scored, n, min_closes):
    """GAMETE SELECTION (2026-07-17, operator: "an egg needs good sperm and
    good eggs to fertilise to produce good offspring").

    The old code took scored[:ELITE_N] ranked by raw net, with both_halves_pos
    only breaking exact float ties — i.e. never. So the very noise genotype
    assess_champion REJECTS still bred, and elite feed forward into the next
    cycle's population (run_once reads prior['elite']), so noise compounded
    across generations. The champion gate protected the REPORT; nothing
    protected the GENE POOL. Selection ran at birth, not at the gametes.

    A genotype is a gamete only if its OWN result is trustworthy:
      MEASURABLE — enough closed trades to have a fitness at all. This biases
        toward looser bars, which is correct rather than a bug: you cannot
        select a genotype you cannot measure, and it is the same "starving
        lens earns its grading diet" logic the scout tuner already runs.
      ROBUST — both halves clear HALF_MARGIN. The birth gate, moved upstream.

    Diversity needs no explicit distance floor: seed_population re-injects the
    default plus every single-gene neighbour every cycle, so the pool cannot
    inbreed toward a converged elite the way a pure elite-carry GA would.

    [2026-07-29] ENACTABILITY IS ENFORCED HERE, not at the call site. The
    research sweep scores genotypes outside the registry cage, and a gamete
    is by definition something the next generation inherits — so an
    out-of-cage genome must never enter this list. Putting the filter in the
    caller left the property untested and un-enforced: a mutation that passed
    the unfiltered `scored` list survived the whole suite, because a selftest
    cannot see run_once's argument. The rule belongs to the rule's function
    ([[a-kill-switch-must-reach-the-consumer]])."""
    return [s for s in scored
            if s["closes"] >= min_closes and s["both_halves_pos"]
            and is_enactable(s.get("genotype"))][:n]


def assess_champion(top, default_net, tape_hours, prior_champ, prior_streak):
    """Is the fittest genotype a TRUSTWORTHY champion, or noise? Returns
    (is_champion, streak, stable, confidence, reason). Pure — selftested.
    This is the anti-overfit gate: too few CLOSED TRADES, a short tape, a weak
    half, or a thin edge over the default genome all read 'tentative' no
    matter how high the net."""
    if not top:
        return False, 0, False, "none", "no population"
    # [2026-07-17] CLOSES first — hours are not evidence. The tape crossed the
    # 48h floor at 04:27Z today carrying 11 closed trades; without this gate
    # the organ would have started minting champions off a dozen fills this
    # afternoon, and PERSIST_CYCLES=3 hourly cycles would call one "stable"
    # by evening. Every other bar below is meaningless under it.
    closes = int(top.get("closes") or 0)
    if closes < MIN_CLOSES:
        return (False, 0, False, "tentative",
                f"{closes} closed trades < {MIN_CLOSES} min — no fitness "
                f"signal yet (hours are not evidence)")
    if tape_hours < MIN_TAPE_HOURS:
        return (False, 0, False, "tentative",
                f"tape {tape_hours:.0f}h < {MIN_TAPE_HOURS:g}h min (noise-risk)")
    half = min(top["h1"], top["h2"])
    if half < HALF_MARGIN:
        return (False, 0, False, "tentative",
                f"weak half ${half:+.2f} < ${HALF_MARGIN:g} (one-half win = noise)")
    edge = top["net"] - default_net
    if edge < EDGE_MARGIN:
        return (False, 0, False, "tentative",
                f"edge vs default ${edge:+.2f} < ${EDGE_MARGIN:g}")
    same = prior_champ == top["genotype"]
    streak = (int(prior_streak or 0) + 1) if same else 1
    stable = streak >= PERSIST_CYCLES
    return (True, streak, stable, "stable" if stable else "candidate",
            f"beats default ${edge:+.2f}, both halves ≥ ${HALF_MARGIN:g}, "
            f"streak {streak}/{PERSIST_CYCLES}")


# ---------------------------------------------------------------------------

def _funding_candidates(judge_state, incubator_state, hurting=None):
    """(generatable_count, untried_props) — the SINGLE source of "what funding
    experiments exist and which are still unminted". funding_proposals() and
    proposal_capacity() both read it so the emitter and its capacity report
    can never disagree about whether this organ is sterile. Pure."""
    # [2026-07-17 IMB-23] the baseline is the funding bot's OWN env defaults
    # (the same env names it reads), not a hard-coded snapshot: if the
    # operator drifts an env, an allele equal to the REAL baseline is a
    # no-op and must be skipped, not proposed as a 7-day experiment. (The
    # old get_lever `default` dict here was dead code — computed, never
    # read — and the literals it shadowed could silently diverge.)
    base = {"enter_apr": float(os.environ.get("FUNDING_ENTER_APR", "0.05")),  # /8 basis fix
            "take_profit": float(os.environ.get("FUNDING_TAKE_PROFIT", "0.04")),
            "max_hold_h": float(os.environ.get("FUNDING_MAX_HOLD_H", "72"))}
    tried = set()
    for v in (judge_state.get("verdicts") or []):
        nm = v.get("name")
        if nm:
            tried.add(nm)
    for p in (incubator_state.get("proposed") or []):
        tried.add(p.get("name"))
    hurting = set(hurting or ())
    props, generatable = [], 0
    for g, (lever, grid) in FUNDING_GENES.items():
        if lever.replace("xp.", "live.", 1) in hurting:
            continue      # live lane measured this knob bad — wait it out
        for allele in grid:
            if allele == base[g]:
                continue
            generatable += 1
            name = f"xp-{g}-{allele:g}"
            if name in tried:
                continue
            levers = {lever: allele}
            props.append({"name": name, "levers": levers})
    return generatable, props


def funding_proposals(judge_state, incubator_state, hurting=None):
    """Novel FUNDING genotypes not already run/queued — proposed for the
    experiment judge's paired bar. Diversity-ordered (single-gene changes
    first). Never pre-scored (no funding replay); the judge is the filter.
    [16-Jul consumer support] 🦾 a gene whose LIVE counterpart lever is
    currently proprioception-graded HURTING is skipped this cycle — the
    live lane just measured that knob bad; don't spend a 7-day judge slot
    re-proposing it while the verdict holds. Restrict-only (only removes
    proposals) and fail-safe (a dark organ skips nothing)."""
    return _funding_candidates(judge_state, incubator_state, hurting)[1][:6]


def proposal_capacity(judge_state, incubator_state, hurting=None):
    """Can this organ still mint a NEW funding experiment? — publish-only.

    [2026-07-29] The reproduction organ can go STERILE in total silence, and
    on 29-Jul it had: `funding_proposals` marks a name tried if it appears in
    the incubator's own lifetime `proposed` ledger, that ledger held all 8
    names ever minted, and those 8 cover EVERY name FUNDING_GENES can
    generate — so props was [] on every cycle with nothing anywhere saying so.
    The judge's serial pool quietly became "the two statics, then 28-day
    retries of already-decided experiments" (pick_candidate's DONE_RETRY_D
    fallback — the pipeline does not die, it stops learning anything new).

    Deliberately NOT fixed by re-proposing from lifetime memory: 7 of those 8
    names are refuted (0.3/0.5 clamp to the already-run 0.075, both hold-caps
    are recorded-refuted, 0.0375/0.0625 sit in the region Lighter's own tape
    measured worst), so a resurrection would spend 7-day judge slots
    re-running known answers. Refilling needs NEW alleles with Lighter-tape
    evidence ([[backtest-on-lighter-only]]) — a research decision, not a
    config edit. This function only makes the state VISIBLE so it cannot rot
    unnoticed. Pure; selftested."""
    gen, props = _funding_candidates(judge_state, incubator_state, hurting)
    return {"generatable": gen, "untried": len(props),
            "names": [p["name"] for p in props],
            # `gen` is 0 only when every gene is hurting-skipped — a transient
            # organ verdict, not sterility, so it must not read as exhausted.
            "exhausted": bool(gen) and not props}


# ---------------------------------------------------------------------------
# the PROSPECT REGISTER (2026-07-22, operator: "the incubator has no list of
# the prospective bots its created and their stats — can this be fixed").
# Until now each cycle scored a whole population and published only the ≤4
# viable gametes + one champion; everything else it bred was DISCARDED at
# publish, and the funding proposals were bare names with no judge outcome.
# The register is the durable answer: every genotype ever scored, merged
# across cycles with latest + best-ever stats, and every funding candidate
# joined to its judge lifecycle. Publish-only — nothing reads it to trade.
# ---------------------------------------------------------------------------

PROSPECT_CAP = int(os.environ.get("INCUBATOR_PROSPECT_CAP", "64"))


def _sig(gt):
    """Canonical genotype signature — stable across cycles and float reprs
    (0.05 and 0.05000000001 must not mint two prospects)."""
    return "|".join(f"{k}={v:g}" if isinstance(v, (int, float)) else f"{k}={v}"
                    for k, v in sorted((gt or {}).items()))


def _age_h(then_iso, now_iso):
    """Hours between two register stamps; None if either is unparseable.

    [2026-07-29] Exists so a DORMANT entry's frozen stats cannot be read as a
    current measurement. Fail-safe to None rather than 0.0: an unknown age
    must not read as 'fresh' — that is the whole failure this stamp prevents."""
    try:
        a = datetime.fromisoformat(str(then_iso).replace("Z", "+00:00"))
        b = datetime.fromisoformat(str(now_iso).replace("Z", "+00:00"))
        return round((b - a).total_seconds() / 3600.0, 2)
    except Exception:      # noqa: BLE001
        return None


def update_prospects(prior_list, scored, seeds, default_gt, champion, elite,
                     now_iso, cap=None):
    """Merge this cycle's scored population into the durable register.

    Per entry: latest replay stats (net/h1/h2/closes/lcb/both_halves_pos),
    best-ever net + lcb (never regress on a worse re-score), born /
    last_seen / cycles, origin FIXED at first sighting (default genome |
    seed axis-probe | bred offspring), and a role recomputed every cycle:
    fittest (rank 1 this cycle) / gamete (breeding elite) / scored /
    unmeasured (0 closes). Entries absent from this cycle's population go
    'dormant' (the gene set drifted, or they fell out of the bred pool) and
    compete for the remaining slots by best-ever lcb — evidence-first, the
    same lower-bound doctrine rank() uses. Pure; bounded at `cap`; output
    order = this cycle's rank order, then dormants.

    [2026-07-29 STALENESS IS STAMPED — a dormant carry is NOT a measurement.]
    A dormant entry keeps the net/h1/h2/closes/lcb it had when it was last
    scored; only `role` used to change. Read straight off the payload those
    frozen numbers are indistinguishable from a current reading, and they are
    not close: measured today by scripts/study_prospect_admission.py, the top
    dormant's carried net **+$39.81** re-scores to **-$11.12** on the live
    tape — a ~$51 gap in a field that looks current. `last_seen` always made
    the staleness DERIVABLE (compare it to the payload's `updated`), but every
    consumer had to think of it; one that did not simply read a stale number
    confidently. Now every entry states it: `stats_current` (scored this
    cycle?) and `stats_age_h` (hours since `last_seen`, None if unparseable —
    unknown must never read as fresh). Publish-only; nothing trades on it.
    `best_net`/`best_lcb` remain HIGH-WATER MARKS by design ("never regress on
    a worse re-score") — right for a register, never an admission decision."""
    cap = PROSPECT_CAP if cap is None else cap
    by_sig = {}
    for e in (prior_list or []):
        if isinstance(e, dict) and isinstance(e.get("genotype"), dict):
            by_sig[_sig(e["genotype"])] = e
    seed_sigs = {_sig(g) for g in (seeds or [])}
    default_sig = _sig(default_gt) if default_gt else None
    champ_sig = (_sig((champion or {}).get("genotype"))
                 if isinstance((champion or {}).get("genotype"), dict) else None)
    elite_sigs = {_sig(e.get("genotype")) for e in (elite or [])
                  if isinstance(e, dict) and isinstance(e.get("genotype"), dict)}

    out, current = [], set()
    for s in (scored or []):
        gt = s.get("genotype")
        if not isinstance(gt, dict):
            continue
        k = _sig(gt)
        current.add(k)
        pe = by_sig.get(k) or {}
        net, lcb = s.get("net"), s.get("lcb")
        bests = [x for x in (net, pe.get("best_net")) if isinstance(x, (int, float))]
        bestl = [x for x in (lcb, pe.get("best_lcb")) if isinstance(x, (int, float))]
        out.append({
            "genotype": gt,
            "born": pe.get("born") or now_iso,
            "last_seen": now_iso,
            "cycles": int(pe.get("cycles") or 0) + 1,
            "origin": (pe.get("origin")
                       or ("default" if k == default_sig
                           else "seed" if k in seed_sigs else "bred")),
            "net": net, "h1": s.get("h1"), "h2": s.get("h2"),
            "closes": s.get("closes"), "lcb": lcb,
            "both_halves_pos": bool(s.get("both_halves_pos")),
            # [2026-07-29] scored THIS cycle — the stats below are current.
            # The dormant carry stamps the opposite; see _age_h.
            "stats_current": True,
            "stats_age_h": 0.0,
            "best_net": max(bests) if bests else None,
            "best_lcb": max(bestl) if bestl else None,
            "role": ("fittest" if champ_sig and k == champ_sig
                     else "gamete" if k in elite_sigs
                     else "scored" if (s.get("closes") or 0) > 0
                     else "unmeasured"),
        })
    dorm = [dict(e, role="dormant",
                 stats_current=False,
                 stats_age_h=_age_h(e.get("last_seen"), now_iso))
            for k, e in by_sig.items() if k not in current]
    dorm.sort(key=lambda d: (d["best_lcb"]
                             if isinstance(d.get("best_lcb"), (int, float))
                             else float("-inf")), reverse=True)
    return (out + dorm[:max(0, cap - len(out))])[:cap]


# [2026-07-29] REGISTER HYGIENE — "learning ... so it doesn't make or
# duplicate bots that don't achieve anything, dead genotypes disposed of"
# (operator). Three measured defects, all in the REGISTER (the breeding side
# was already protected: select_elite demands both_halves_pos, so a losing
# genotype cannot become a gamete):
#
#  1. DUPLICATES. 30 register rows were 16 distinct experiments — the rest
#     differed ONLY in genes the current veto makes unevolvable (measured by
#     scripts/study_prospect_admission.py). Two genotypes the organ can no
#     longer tell apart are one candidate, and showing both invents a roster.
#  2. NO DISPOSAL. Nothing ever left the register except by cap pressure.
#  3. IMMORTAL CORPSES — the worst of the three. Cap eviction sorted dormants
#     by `best_lcb`, a HIGH-WATER MARK: one lucky historical score outranked
#     every recently-measured genotype forever. Combined with (2), the
#     register fills with the luckiest dead entries and crowds out live ones.
#
# Disposal is denominated in the fleet's own units — CYCLES seen (PERSIST-
# style repetition) and the LATEST reading, never the best-ever — and it is
# REPORTED, never silent: the payload carries what was retired and why.
DEAD_MIN_CYCLES = int(os.environ.get("INCUBATOR_DEAD_CYCLES", "3"))
DEAD_AGE_H = float(os.environ.get("INCUBATOR_DEAD_AGE_H", "24"))


def prune_register(entries, live_genes, now_iso, min_cycles=None,
                   dead_age_h=None, cap=None):
    """(kept, summary) — collapse duplicates, dispose of dead genotypes, and
    rank the survivors on RECENT evidence instead of a high-water mark.

    `live_genes` is the set of gene NAMES currently evolvable (run_once has it
    from evolvable_genes); entries are compared on their genotype REDUCED to
    those genes, so two rows the organ can no longer distinguish collapse into
    one — the survivor being the one with the most recent scoring, then the
    better latest lcb.

    A genotype is DEAD when it is dormant (not scored this cycle), has been
    seen >= `min_cycles`, is staler than `dead_age_h`, and its LATEST reading
    lost (net <= 0). Latest, never best_net: the whole failure this fixes is a
    lucky historical score outliving the measurement that refuted it.

    Fail-safe: an entry whose staleness is UNKNOWN (`stats_age_h` None) is
    never retired — disposal must not run on data it cannot read. Entries
    scored THIS cycle are never retired regardless of result; one bad read is
    not a verdict. Pure; selftested."""
    min_cycles = DEAD_MIN_CYCLES if min_cycles is None else min_cycles
    dead_age_h = DEAD_AGE_H if dead_age_h is None else dead_age_h
    cap = PROSPECT_CAP if cap is None else cap
    rows = [e for e in (entries or [])
            if isinstance(e, dict) and isinstance(e.get("genotype"), dict)]

    def _num(x):
        return x if isinstance(x, (int, float)) else None

    def _reduced(e):
        return _sig({g: v for g, v in e["genotype"].items() if g in live_genes})

    # ---- 1. collapse duplicates under the CURRENT gene set ----------------
    groups = {}
    for e in rows:
        groups.setdefault(_reduced(e), []).append(e)
    collapsed, merged = [], 0
    for _k, grp in groups.items():
        if len(grp) > 1:
            merged += len(grp) - 1
        # freshest first (age None sorts last), then better latest lcb
        grp.sort(key=lambda e: (e.get("stats_current") is True,
                                -(e.get("stats_age_h")
                                  if _num(e.get("stats_age_h")) is not None
                                  else 1e9),
                                _num(e.get("lcb")) if _num(e.get("lcb"))
                                is not None else float("-inf")),
                 reverse=True)
        rep = dict(grp[0])
        if len(grp) > 1:
            rep["merged_dupes"] = len(grp) - 1
        collapsed.append(rep)

    # ---- 2. dispose of the measured dead ---------------------------------
    kept, retired = [], []
    for e in collapsed:
        age = _num(e.get("stats_age_h"))
        net = _num(e.get("net"))
        cycles = int(e.get("cycles") or 0)
        closes = _num(e.get("closes"))
        dead = (not e.get("stats_current")
                and age is not None and age >= dead_age_h
                and cycles >= min_cycles
                and net is not None and net <= 0)
        if dead:
            # WHICH kind of dead, because they are not the same failure and
            # an operator reading the disposal log needs to tell them apart:
            # INERT never fired at all (achieves nothing), LOSING fired and
            # lost (achieves worse than nothing).
            kind = "INERT" if not closes else "LOSING"
            why = (f"{kind}: dormant {age:.0f}h over {cycles} cycles, "
                   + (f"never traded (0 closes)" if kind == "INERT"
                      else f"last measured net {net:+.2f} on {closes:g} closes"))
            retired.append({"genotype": e["genotype"], "net": net,
                            "cycles": cycles, "age_h": age, "kind": kind,
                            "closes": closes, "why": why})
        else:
            kept.append(e)

    # ---- 3. rank on RECENT evidence, not the high-water mark -------------
    def _rank_key(e):
        cur = 1 if e.get("stats_current") else 0
        lcb = _num(e.get("lcb"))
        return (cur, lcb if lcb is not None else float("-inf"))

    kept.sort(key=_rank_key, reverse=True)
    summary = {"in": len(rows), "kept": len(kept), "merged_dupes": merged,
               "retired": len(retired),
               "distinct_experiments": len(groups),
               "examples": retired[:5]}
    return kept[:cap], summary


def funding_prospects_view(proposed, queue_candidates, judge_state):
    """The funding substrate's prospect list: each proposal joined to its
    judge lifecycle. Status precedence: running/promoted (the judge's
    CURRENT candidate) > a verdict row (promoted/abandoned/faded/invalid,
    latest wins) > completed (in `done` but the verdict aged out of the
    judge's last-10 window) > queued (sitting in xp-queue) > proposed.
    Stats are the judge's own eval numbers, whitelisted. Pure; tolerant of
    absent/partial/junk states (dark judge -> everything reads 'proposed'
    or 'queued', never raises)."""
    js = judge_state if isinstance(judge_state, dict) else {}
    phase, current = js.get("phase"), js.get("current")
    done = {d for d in (js.get("done") or []) if isinstance(d, str)}
    queued = {c.get("name") for c in (queue_candidates or [])
              if isinstance(c, dict)}
    latest_v = {}
    for v in (js.get("verdicts") or []):    # chronological — last wins
        if isinstance(v, dict) and v.get("name"):
            latest_v[v["name"]] = v
    KEEP = ("why", "n_shadow", "n_live", "shadow_mean_pct", "live_mean_pct")

    def _stats(ev):
        return ({k: ev[k] for k in KEEP if k in ev}
                if isinstance(ev, dict) else None)

    out = []
    for p in (proposed or []):
        if not isinstance(p, dict) or not p.get("name"):
            continue
        name = p["name"]
        e = {"name": name, "levers": p.get("levers") or {}}
        if p.get("at"):
            e["at"] = p["at"]
        stats = ts = None
        if name == current and phase in ("running", "promoted"):
            e["status"] = phase
            stats = _stats(js.get("last_eval"))
        elif name in latest_v:
            v = latest_v[name]
            e["status"] = str(v.get("verdict") or "done").lower()
            ts, stats = v.get("ts"), _stats(v.get("eval"))
        elif name in done:
            e["status"] = "completed"
        elif name in queued:
            e["status"] = "queued"
        else:
            e["status"] = "proposed"
        if ts:
            e["ts"] = ts
        if stats:
            e["stats"] = stats
        out.append(e)
    return out


def run_once():
    now = now_ts()
    # [2026-08-05 SEED GUARD] the CHECKED read — `prior.proposed` is the
    # LIFETIME dedup ledger: a failed read that fell through as {} would
    # re-propose genes the judge already refuted, and the save at the end
    # overwrites the durable ledger with the amnesia. Standard organ degrade:
    # skip the cycle.
    _ok, _prior = store.load_state_checked(KEY)
    if not _ok:
        print("[incubator] state read FAILED — skipping this cycle rather "
              "than seed over the proposed ledger", flush=True)
        return None
    prior = _prior or {}
    tape, used = rp.load_tape(source="auto")

    # --- TAKER breeding (shadow-only, replay-scored) -----------------------
    leaderboard, champion = [], None
    # fail-safe OPEN: veto nothing, and score `breakoutup` (a dark brain
    # vetoes nothing, exactly as the taker's own read degrades)
    scored_lenses = scored_lens_set(set(LENS_GENE))
    funnel = {"scored_this_cycle": False,
              "why": "tape too short — no genotype was scored"}
    if len(tape) >= MIN_SNAPS:
        tape_hours = ((tape[-1][0] - tape[0][0]).total_seconds() / 3600.0
                      if len(tape) >= 2 else 0.0)
        # [2026-07-17 IMB-10] a hold the tape can never reach is deferral, not
        # edge — drop those alleles before selection can reward them.
        genes, dropped = reachable_genes(TAKER_GENES, tape_hours)
        if dropped:
            print(f"[incubator] max-hold alleles {dropped} excluded — tape "
                  f"spans {tape_hours:.0f}h; an unreachable hold never fires "
                  f"(deferral, not edge)", flush=True)
        # [2026-07-17] Honor the brain's LENS VETO, as the tuner already does.
        # The replay is veto-blind by design, so without this the fitness is
        # dominated by fills the live taker refuses to make.
        lens_fwd = fresh_lens_fwd(store.load_state("brain-lens-forward"), now)
        # [2026-08-02] The LIVE arm's own closes, senior to the forward proxy
        # ((ij)). Read here, not inside `live_lenses`, so that stays pure —
        # and fail-safe open, so a dark ledger degrades to the forward grade.
        try:
            _realised = tt.realised_lens_evidence(
                store.fetch_paper_trades(limit=4000),
                tt.BOT + "-lighter", sides=tt.restricted_sides()) or {}
        except Exception:                       # noqa: BLE001
            _realised = {}
        allowed = live_lenses(lens_fwd, realised=_realised)
        # [2026-08-26] `breakoutup` joins the SCORED set (see scored_lens_set):
        # a relabelled subset of breakout, vetoed only by its OWN closes via the
        # taker's `breakoutup_self_vetoed`. Freshness is the caller's job, so it
        # is checked HERE and the payload is passed in — a dark or stale grade
        # vetoes nothing, the taker's own degrade. See BRKUP_VETO_WIRED for why
        # that payload is empty today and what closes it.
        scored_lenses = scored_lens_set(
            allowed, fresh_stake_mults(stake_mults_payload(), now), tt.BOT_ROW)
        if not BRKUP_VETO_WIRED and "breakoutup" in scored_lenses:
            print("[incubator] breakoutup SELF-VETO UNWIRED (fail-OPEN) — its "
                  "grade needs the RAW brain stake-mults payload, whose reader "
                  "must be declared in the fleet's raw-read guard; the lens is "
                  "scored regardless of that grade. See BRKUP_VETO_WIRED.",
                  flush=True)
        genes, gene_dropped = evolvable_genes(genes, allowed)
        if gene_dropped:
            print(f"[incubator] lens veto — brain grades "
                  f"{sorted(set(LENS_GENE) - allowed)} negative at sample "
                  f"size; genes {gene_dropped} dropped and their fills "
                  f"excluded from fitness (breeding a vetoed lens optimizes a "
                  f"bot that does not exist)", flush=True)
        # DECLARED, not silent: `breakoutup` fills through BRK_RANGE, so when
        # the broad `breakout` veto drops that gene the lens is SCORED but not
        # EVOLVABLE — its P&L is a constant across the population rather than a
        # search direction. Visible every cycle instead of inferred later.
        if "breakoutup" in scored_lenses and "BRK_RANGE" in gene_dropped:
            print("[incubator] breakoutup is SCORED but not EVOLVABLE this "
                  "cycle — its entry gene BRK_RANGE was dropped with the "
                  "vetoed `breakout` lens it shares, so its fills enter the "
                  "fitness at the module default bar and move with no allele",
                  flush=True)
        prior_elite = conform([e.get("genotype") for e in
                               (prior.get("elite") or [])], genes)
        seeds = seed_population(genes)
        # [2026-07-29] JOINT-SPACE sweep alongside the axis probes and the
        # elite's offspring. This is what makes gene INTERACTIONS reachable at
        # all: breed() is empty whenever no genotype clears both_halves_pos,
        # which is the standing state on a negative surface, so without this
        # the population is the 11 axis probes and nothing else.
        # [2026-07-29] the SWEEP may range over the RESEARCH space (beyond the
        # registry cage); seeds and breeding stay IN-CAGE so the champion's
        # lineage is shippable by construction and `conform` stays a no-op.
        search_genes = genes
        if RESEARCH_MODE:
            r_all, _rdrop = evolvable_genes(RESEARCH_GENES, allowed)
            search_genes = {g: spec for g, spec in r_all.items() if g in genes}
        explored, explore_cursor, space_size = explore_slice(
            search_genes, prior.get("explore_cursor"), EXPLORE_N)
        population = dedupe(seeds + breed(prior_elite, genes) + explored)
        print(f"[incubator] 🔍 exploring {len(population)} genotypes "
              f"({len(seeds)} axis probes + {len(explored)} joint-space, "
              f"cursor -> {explore_cursor}/{space_size} = "
              f"{100.0 * min(explore_cursor or space_size, space_size) / space_size:.0f}% "
              f"of the legal space swept)", flush=True)
        # [2026-08-26] ONE resolver for the whole cycle — ~1519 genotypes x 3
        # replays share it, and every comparison in this cycle is therefore
        # scored on identical lens coverage. None = REDUCED COVERAGE, said out
        # loud, never an error (build_up_resolver's contract).
        up_res = build_up_resolver(tape)
        if up_res is None and UP_RESOLVER_ON:
            print("[incubator] REDUCED COVERAGE — breakout/breakoutup cannot "
                  "appear in this cycle's replays; every genotype is scored on "
                  "the remaining lenses only.", flush=True)
        scored = rank(population, tape, scored_lenses, up_resolver=up_res)
        # [2026-07-29] stamp every result with whether it could EVER ship.
        for s in scored:
            s["enactable"] = is_enactable(s["genotype"])
        enactable = [s for s in scored if s["enactable"]]
        frontier = next((s for s in scored if not s["enactable"]), None)
        # [2026-07-17] GAMETES (who breeds) and the CHAMPION (what we would
        # trust) are now separate questions. The elite are robustness-filtered
        # so noise cannot reproduce; the fittest genotype is still assessed and
        # published either way, so its confidence reason explains WHY it is not
        # a champion instead of the card just going quiet.
        # [2026-07-29] BOTH are drawn from the ENACTABLE subset: the champion
        # and the gametes are the two things a human or a later cycle might
        # act on, so an out-of-cage genotype must never become either. The
        # frontier is published separately, clearly marked, and acts on
        # nothing.
        leaderboard = select_elite(enactable, ELITE_N, MIN_GT_CLOSES)
        default_gt = {g: getattr(tt, g) for g in genes}
        default_net = next((s["net"] for s in scored
                            if s["genotype"] == default_gt), 0.0)
        top = enactable[0] if enactable else None
        is_champ, streak, stable, conf, why = assess_champion(
            top, default_net, tape_hours,
            (prior.get("champion") or {}).get("genotype"),
            (prior.get("champion") or {}).get("streak"))
        if top:
            champion = {"genotype": top["genotype"], "net": top["net"],
                        "h1": top["h1"], "h2": top["h2"], "confidence": conf,
                        "streak": streak, "stable": stable,
                        "closes": top["closes"], "lcb": top["lcb"],
                        "vs_default": round(top["net"] - default_net, 3)}
            print(f"[incubator] fittest net ${top['net']:+.2f} (lcb "
                  f"${top['lcb']:+.2f} on {top['closes']} closes) vs default "
                  f"${default_net:+.2f} (h1 ${top['h1']:+.2f} h2 "
                  f"${top['h2']:+.2f}) | {conf.upper()}: {why}", flush=True)
        print(f"[incubator] gametes: {len(leaderboard)}/{len(scored)} genotypes "
              f"viable (>= {MIN_GT_CLOSES} closes AND both halves >= "
              f"${HALF_MARGIN:.2f})", flush=True)
        # [2026-08-26] THE FUNNEL. `elite: []` used to be byte-identical
        # between "the population died at a gate" and "the surface is
        # negative", and `assess_champion`'s failing-bar `why` was printed to
        # stdout and never published — so answering the operator's first
        # question required a code run against the live tape. It is now on the
        # payload every cycle. CUMULATIVE, in select_elite's own order, so the
        # counts are readable as a funnel and each step is <= the one above it.
        _closes_ok = [s for s in scored if s["closes"] >= MIN_GT_CLOSES]
        _halves_ok = [s for s in _closes_ok if s["both_halves_pos"]]
        _enact_ok = [s for s in _halves_ok if s["enactable"]]
        funnel = {
            "scored_this_cycle": True,
            "generated": len(population),
            "scored": len(scored),
            "closes_ok": len(_closes_ok),
            "both_halves_pos": len(_halves_ok),
            "enactable": len(_enact_ok),
            "elite": len(leaderboard),
            # side counts (NOT part of the cumulative chain — an independent
            # read of each bar over the whole scored population)
            "any_closes": sum(1 for s in scored if s["closes"] > 0),
            "enactable_all": len(enactable),
            "bars": {"min_gt_closes": MIN_GT_CLOSES,
                     "half_margin": round(HALF_MARGIN, 4),
                     "edge_margin": round(EDGE_MARGIN, 4),
                     "min_closes": MIN_CLOSES,
                     "min_tape_hours": MIN_TAPE_HOURS,
                     "elite_n": ELITE_N},
            # the champion's verdict IN THE PAYLOAD, not only on stdout
            "champion_is": bool(is_champ),
            "champion_why": str(why),
            "champion_confidence": conf,
            "default_net": round(float(default_net), 3),
            # coverage + scope: what the fitness was computed OVER
            "up_resolver": up_res is not None,
            "unreachable_lenses": ([] if up_res is not None
                                   else sorted(rp.UNREACHABLE_WITHOUT_RESOLVER)),
            "lenses_scored": sorted(scored_lenses),
            "genes_evolvable": sorted(genes),
            "genes_dropped": list(gene_dropped),
            # a DECLARED gap, published so it cannot rot into folklore — see
            # BRKUP_VETO_WIRED for the two lines that close it
            "breakoutup_veto": ("wired" if BRKUP_VETO_WIRED else
                                "unwired — fail-OPEN; the raw brain grade is "
                                "not read here (see BRKUP_VETO_WIRED)"),
        }
        print(f"[incubator] 🧪 funnel: generated {funnel['generated']} -> "
              f"closes>={MIN_GT_CLOSES} {funnel['closes_ok']} -> both_halves "
              f"{funnel['both_halves_pos']} -> enactable {funnel['enactable']} "
              f"-> elite {funnel['elite']} | champion: {why}", flush=True)
        # [2026-07-22] the PROSPECT REGISTER: every genotype this cycle
        # scored, merged into the durable across-cycles list (see
        # update_prospects) — the population is no longer discarded at
        # publish.
        # [2026-07-29] Only the RANKED TOP land in the durable register. With
        # a 1500-genotype sweep, registering every scored genome would fill
        # the cap with one cycle's population and evict every dormant entry —
        # the register would stop being the durable "every genotype and its
        # stats" the 22-Jul ask asked for. rank() already sorts, so this is
        # the best of the sweep, not an arbitrary slice.
        prospects = update_prospects(prior.get("prospects"),
                                     scored[:REGISTER_TOP_N], seeds,
                                     default_gt, champion, leaderboard,
                                     _iso(now))
        # [2026-07-29] HYGIENE: collapse what the current gene set can no
        # longer tell apart, dispose of the measured dead, and re-rank on the
        # LATEST reading. Only runs when we actually scored — pruning off a
        # dark cycle would retire genotypes on data we did not take.
        prospects, prune = prune_register(prospects, set(genes), _iso(now))
        cages = cage_analysis(scored, genes)
        _bind = [g for g, c in cages.items() if c.get("cage_may_bind")]
        if _bind:
            print(f"[incubator] 🔓 cage may BIND on {_bind} — the best "
                  f"in-cage allele sits ON a registry bound and an "
                  f"out-of-cage allele scored better. Evidence for a bound "
                  f"widening; enacts nothing.", flush=True)
    else:
        print(f"[incubator] tape too short ({len(tape)}/{MIN_SNAPS}) — "
              f"skipping taker breeding", flush=True)
        # nothing scored: carry the register unchanged (a short tape must
        # not demote or age anyone)
        prospects = [e for e in (prior.get("prospects") or [])
                     if isinstance(e, dict)]
        prune = {"skipped": "tape too short — no scoring, no disposal"}
        # the cursor must NOT advance on a cycle that scored nothing, or the
        # sweep would skip a slice it never actually measured
        explore_cursor = prior.get("explore_cursor") or 0
        space_size, explored = 0, []
        frontier, cages = None, {}

    # --- FUNDING proposals (live-reachable, JUDGE-gated) -------------------
    judge_state = store.load_state("xp-judge") or {}
    hurting = set()
    if proprio is not None:
        try:
            hurting = set(proprio.hurting_levers(
                store.load_state(proprio.KEY) or {}, now))
        except Exception:
            hurting = set()
    props = funding_proposals(judge_state, prior, hurting=hurting)
    # [2026-07-29] STERILITY IS NOW REPORTED, not silent. props==[] used to be
    # indistinguishable from "nothing new this cycle"; when the gene space runs
    # out it is permanent, and the judge degrades to 28-day retries of decided
    # experiments with nobody told. See proposal_capacity().
    capacity = proposal_capacity(judge_state, prior, hurting=hurting)
    if capacity["exhausted"]:
        print(f"[incubator] ⚠️  FUNDING GENE SPACE EXHAUSTED — all "
              f"{capacity['generatable']} generatable alleles are already in "
              f"lifetime `proposed` memory; this organ can mint NO new funding "
              f"experiment. The judge falls back to 28d retries of decided "
              f"candidates. Refill needs NEW alleles with Lighter-tape "
              f"evidence (a research decision, not a config edit).", flush=True)
    if hurting:
        print(f"[incubator] 🦾 proprioception hurting levers honored: "
              f"{sorted(hurting)}", flush=True)
    # [2026-07-28 §3b residual] QUEUE HEARTBEAT. The judge consumes xp-queue
    # only while FRESH by its own updated+ttl_sec (fail-closed since today's
    # review), so a queue written only on NEW proposals dies of old age in
    # ~TTL and every still-endorsed candidate expires unseen while the judge
    # is mid-candidate. Two halves, both restrict-safe: the READ carries
    # forward only a still-fresh queue (queue_carry, fail-closed — retires
    # dead entries rather than re-stamping them), and the WRITE now happens
    # EVERY cycle, props or not, so the endorsed queue stays alive as long as
    # this organ breathes (fresh-empty != dark, and the judge's statics are
    # untouched either way). Accepted residual: an incubator outage > TTL
    # loses queued names permanently (lifetime `proposed` memory dedups
    # re-proposal); the only rebuild source is that same lifetime memory,
    # which also holds tape-refuted names the judge never ran — fail-closed
    # wins over a resurrection risk.
    # [2026-08-05 SEED GUARD] the CHECKED read, second key: merging into an
    # unreadable queue would overwrite it, and stamping these proposals into
    # the `proposed` ledger without actually queueing them loses them FOREVER
    # (the lifetime dedup blocks re-proposal). Nothing is written on a failed
    # read — the whole cycle is skipped, same degrade as the KEY read above.
    _ok_q, _q_prior = store.load_state_checked(QUEUE_KEY)
    if not _ok_q:
        print("[incubator] xp-queue read FAILED — skipping this cycle "
              "(queue untouched, proposals deferred, ledger preserved)",
              flush=True)
        return None
    candidates_now = queue_carry(_q_prior, now)
    if props:
        existing = {p["name"] for p in candidates_now}
        merged = candidates_now + [p for p in props
                                   if p["name"] not in existing]
        candidates_now = merged[:20]
        print(f"[incubator] proposed {len(props)} funding candidate(s) to "
              f"xp-queue (judge-gated): {[p['name'] for p in props]}", flush=True)
    store.save_state(QUEUE_KEY, {"updated": _iso(now), "ttl_sec": TTL_SEC,
                                 "candidates": candidates_now,
                                 "source": "strategy-incubator"})

    # the incubator's OWN proposed ledger stamps birth time; the queue copy
    # stays exactly {name, levers} (the judge's contract, untouched)
    proposed_all = ((prior.get("proposed") or [])
                    + [dict(p, at=_iso(now)) for p in props])[-20:]
    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC,
        "tape_snaps": len(tape), "tape_source": used,
        "elite": leaderboard, "champion": champion,
        # [2026-07-17] what the fitness was actually scored on — a champion
        # means nothing without the lens set the live taker could fill.
        "lenses_scored": sorted(scored_lenses),
        # [2026-08-26] over the TAKER's full lens set, not just the gene map:
        # `breakoutup` has no entry gene of its own, so `set(LENS_GENE)` could
        # never report it as vetoed and a self-veto was invisible here.
        "lenses_vetoed": sorted(set(tt.ALL_LENSES) - scored_lenses),
        # [2026-08-26] the per-gate population counts + the champion's failing
        # bar (see the funnel build in the breeding block).
        "funnel": funnel,
        "proposed": proposed_all,
        # [2026-07-22] the PROSPECT REGISTER (operator: "no list of the
        # prospective bots its created and their stats") — both substrates:
        # every taker genotype ever scored (durable, stats + best-ever),
        # and every funding proposal joined to its judge lifecycle.
        "prospects": prospects,
        "funding_prospects": funding_prospects_view(proposed_all,
                                                    candidates_now,
                                                    judge_state),
        # [2026-07-29] can this organ still mint a NEW funding experiment?
        # Publish-only; nothing trades on it. See proposal_capacity().
        "proposal_capacity": capacity,
        # [2026-07-29] what register hygiene did this cycle — merged dupes,
        # retired dead genotypes and why. Disposal must be auditable, never
        # silent (an organ that quietly deletes its own evidence is worse
        # than one that hoards it). See prune_register().
        "register_hygiene": prune,
        # [2026-07-29] the joint-space sweep: where the cursor is, how big the
        # legal space is, and how much of it this cycle covered. A search that
        # cannot be seen to be sweeping is indistinguishable from one that has
        # silently stopped (the explore-zero lesson). See explore_slice().
        "explore_cursor": explore_cursor,
        "exploration": {"space_size": space_size, "swept_this_cycle": len(explored),
                        "cursor": explore_cursor, "budget_n": EXPLORE_N,
                        "research_mode": RESEARCH_MODE,
                        "coverage_pct": (round(100.0 * min(explore_cursor or space_size,
                                                           space_size) / space_size, 1)
                                         if space_size else None)},
        # [2026-07-29] the RESEARCH FRONTIER: the best genotype that could NOT
        # be enacted (outside the registry cage), and the per-gene read on
        # whether a cage BOUND is what is limiting results. Publish-only and
        # deliberately kept OUT of `champion`/`elite` — nothing may act on it.
        # A `cage_may_bind: true` gene is the evidence for a bound widening;
        # widening remains an operator decision, and this is the argument it
        # should be made from.
        "frontier": frontier,
        "cage_analysis": cages,
    }
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "top_net": leaderboard[0]["net"] if leaderboard else None,
                                     "n_proposed": len(props),
                                     "n_prospects": len(prospects)})
        except Exception:
            pass
    if prune.get("retired") or prune.get("merged_dupes"):
        print(f"[incubator] 🧹 register hygiene: {prune['in']} entries -> "
              f"{prune['kept']} kept ({prune['merged_dupes']} duplicate(s) "
              f"collapsed under the current gene set, {prune['retired']} "
              f"retired as measured-dead). Retired: "
              f"{[r['why'] for r in prune['examples']]}", flush=True)
    print(f"[incubator] {_iso(now)} elite={len(leaderboard)} "
          f"prospects={len(prospects)} funding_proposed={len(props)}",
          flush=True)
    return payload


def _selftest():
    genes = {"A": ("x.a", [1, 2, 3]), "B": ("x.b", [10, 20])}

    class _Fake:
        A = 1
        B = 10
    global tt
    real_tt = tt
    tt = _Fake()
    try:
        pop = seed_population(genes)
        # default + single-gene neighbours: {1,10}, {2,10}, {3,10}, {1,20}
        assert {tuple(sorted(g.items())) for g in pop} == {
            (("A", 1), ("B", 10)), (("A", 2), ("B", 10)),
            (("A", 3), ("B", 10)), (("A", 1), ("B", 20))}, pop
        # dedupe
        assert len(dedupe(pop + pop)) == len(pop)
        # breeding produces crossover + mutation offspring, all on-grid, deduped
        elite = [{"A": 2, "B": 10}, {"A": 1, "B": 20}]
        kids = breed(elite, genes)
        for k in kids:
            assert k["A"] in genes["A"][1] and k["B"] in genes["B"][1]
        # crossover of the two elites yields the corners
        kset = {tuple(sorted(g.items())) for g in kids}
        assert (("A", 2), ("B", 20)) in kset or (("A", 1), ("B", 10)) in kset
        assert len(kids) == len(dedupe(kids)), "breed output must be deduped"
        # empty elite -> no offspring
        assert breed([], genes) == []
    finally:
        tt = real_tt

    # genotype_to_levers clamps + drops unknowns against the REAL registry
    lv = genotype_to_levers({"DIP_RANGE": 0.99, "NOPE": 1}, TAKER_GENES)
    assert lv == {"taker.dip_range": 0.15}, lv          # clamped to ceiling, unknown dropped
    # [2026-07-17] the divergence gene (the fleet's only SHORT lens) reaches
    # taker.div_gap_pp, and EVERY allele in its grid is registry-legal in both
    # directions — the tuner's ladder only ever widens (500->300).
    for allele in TAKER_GENES["DIV_GAP_PP"][1]:
        assert genotype_to_levers({"DIV_GAP_PP": allele}, TAKER_GENES) == \
            {"taker.div_gap_pp": allele}, allele
    for gene, (lever, grid) in TAKER_GENES.items():     # no dead alleles anywhere
        for allele in grid:
            assert tuning.clamp(lever, allele) == allele, (gene, lever, allele)

    # funding proposals exclude already-tried names, cap, and map to xp levers
    js = {"verdicts": [{"name": "xp-enter_apr-0.0375"}]}
    props = funding_proposals(js, {})
    names = {p["name"] for p in props}
    assert "xp-enter_apr-0.0375" not in names, "already-tried excluded"
    assert all(list(p["levers"])[0].startswith("xp.funding.") for p in props)
    for p in props:                                     # every allele is in-registry
        (lever, val), = p["levers"].items()
        assert tuning.clamp(lever, val) == val, p
    # 🦾 a gene whose LIVE lever is proprioception-graded HURTING is skipped
    # this cycle; other genes unaffected; empty/absent hurting skips nothing
    ph = funding_proposals({}, {}, hurting={"live.funding.enter_apr"})
    assert not any("enter_apr" in p["name"] for p in ph), ph
    assert any("take_profit" in p["name"] for p in ph), ph
    assert funding_proposals({}, {}, hurting=set()) == funding_proposals({}, {})
    assert funding_proposals({}, {}, hurting=None) == funding_proposals({}, {})
    # [2026-07-29 AUDIT R2] the refuted hold-cap knob can NEVER be proposed
    # again — the 28-Jul TTL fix retired the stored candidates, this pins the
    # SOURCE: no grid, no regeneration under the rolling dedup caps.
    assert not any(p["name"].startswith("xp-max_hold_h")
                   for p in funding_proposals({}, {})), \
        "hold-cap candidates are refuted at ANY number (21-Jul review)"
    assert "max_hold_h" not in FUNDING_GENES, \
        "re-adding the hold gene needs the recorded refutation overturned first"
    # [2026-07-29] STERILITY IS REPORTED. A fresh organ has capacity; an organ
    # whose lifetime `proposed` memory already holds every generatable name is
    # EXHAUSTED and must say so (this is the live 29-Jul state — 8 minted
    # names covering all 4 non-baseline alleles, props == [] forever).
    _cap0 = proposal_capacity({}, {})
    assert _cap0["generatable"] > 0 and _cap0["untried"] == _cap0["generatable"]
    assert _cap0["exhausted"] is False, _cap0
    _all_minted = {"proposed": [{"name": n} for n in _cap0["names"]]}
    _cap1 = proposal_capacity({}, _all_minted)
    assert _cap1["untried"] == 0 and _cap1["exhausted"] is True, _cap1
    assert _cap1["generatable"] == _cap0["generatable"], "capacity is the SPACE"
    # emitter and reporter read ONE source — they cannot disagree about sterility
    assert funding_proposals({}, _all_minted) == [], "emitter agrees: sterile"
    # a fully-HURTING organ is transiently silent, NOT sterile: generatable
    # collapses to 0, and 0 untried out of 0 must not read as exhaustion.
    _cap2 = proposal_capacity({}, {}, hurting={"live.funding.enter_apr",
                                               "live.funding.take_profit"})
    assert _cap2["generatable"] == 0 and _cap2["exhausted"] is False, _cap2
    # [2026-07-17] LENS VETO: the incubator must not breed a lens the live
    # taker refuses to fill. These are the REAL 16-Jul grades.
    real_lf = {"breakout": {"n4h": 2241, "avg4h_pct": -0.184, "hit4h": 0.405},
               "dip": {"n4h": 2110, "avg4h_pct": -0.438, "hit4h": 0.426},
               "momentum": {"n4h": 1178, "avg4h_pct": -0.233, "hit4h": 0.410},
               "divergence": {"n4h": 2463, "avg4h_pct": 0.041, "hit4h": 0.552}}
    assert live_lenses(real_lf) == {"divergence"}, live_lenses(real_lf)
    assert live_lenses({}) == set(LENS_GENE), "no grades -> fail-safe OPEN"
    assert live_lenses(None) == set(LENS_GENE)
    # a negative lens UNDER the floor is not vetoed (evidence, not opinion)
    assert "dip" in live_lenses({"dip": {"n4h": 5, "avg4h_pct": -9.0,
                                         "hit4h": 0.0}})
    # only the vetoed lens's ENTRY gene is dropped; pleiotropic exits stay
    ev, evd = evolvable_genes(TAKER_GENES, {"divergence"})
    assert evd == ["BRK_RANGE", "DIP_RANGE", "MOMO_CHG"], evd
    assert "DIV_GAP_PP" in ev and "TAKE_PROFIT" in ev and "MAX_HOLD_H" in ev
    assert evolvable_genes(TAKER_GENES, set(LENS_GENE))[1] == [], "none vetoed"
    # fitness restricted to the allowed lenses only
    rep = {"closed_net": 10.0, "unrealized": 1.0,
           "lenses": {"dip": {"net": 8.0, "pnl_usd": [8.0]},
                      "divergence": {"net": 2.0, "pnl_usd": [1.0, 1.0]}},
           "open": [{"lens": "dip", "upnl": 5.0},
                    {"lens": "divergence", "upnl": -4.0}]}
    assert _marked(rep) == 11.0                       # unrestricted
    assert _marked(rep, {"divergence"}) == -2.0       # 2.0 net + (-4.0) upnl
    assert _pnl_usd(rep) == [8.0, 1.0, 1.0] or _pnl_usd(rep) == [1.0, 1.0, 8.0]
    assert _pnl_usd(rep, {"divergence"}) == [1.0, 1.0]
    assert _pnl_usd(rep, set()) == []

    # fresh_lens_fwd: stale/absent/unparseable grades veto nothing
    fresh = {"updated": _iso(1000.0), "ttl_sec": 600, "lenses": real_lf}
    assert fresh_lens_fwd(fresh, 1300.0) == real_lf          # inside ttl
    assert fresh_lens_fwd(fresh, 2000.0) == {}               # aged out
    assert fresh_lens_fwd({"updated": "garbage", "lenses": real_lf}, 1.0) == {}
    assert fresh_lens_fwd(None, 1.0) == {} and fresh_lens_fwd({}, 1.0) == {}

    # conform: a stale elite from an OLDER gene set must not KeyError breed().
    # This is the real upgrade path — the published elite predate DIV_GAP_PP.
    old_elite = [{"BRK_RANGE": 0.93, "DIP_RANGE": 0.05, "MOMO_CHG": 5.0,
                  "TAKE_PROFIT": 0.04, "STOP_LOSS": -0.03, "MAX_HOLD_H": 48.0}]
    conformed = conform(old_elite, TAKER_GENES)
    assert set(conformed[0]) == set(TAKER_GENES), conformed
    assert conformed[0]["DIV_GAP_PP"] == tt.DIV_GAP_PP, "missing -> default"
    breed(conformed, TAKER_GENES)                    # must not raise
    # extra/unknown genes are dropped; junk entries ignored; off-grid survives
    narrow, _ = evolvable_genes(TAKER_GENES, {"divergence"})
    c2 = conform(old_elite, narrow)
    assert "BRK_RANGE" not in c2[0] and "DIV_GAP_PP" in c2[0], c2
    breed(c2, narrow)                                # must not raise
    assert conform([None, "nope", 42], TAKER_GENES) == []
    assert conform(None, TAKER_GENES) == []
    held = conform([{"MAX_HOLD_H": 72.0}], reachable_genes(TAKER_GENES, 60.0)[0])
    assert held[0]["MAX_HOLD_H"] == 72.0, "off-grid allele in force is kept"

    # [2026-07-17] IMB-10: unreachable max-hold alleles dropped, and only those
    # [2026-08-20 (sk)] span re-anchored 43h -> 60h. The grid lost its 24h rung
    # with the registry cage (the breakoutup ratchet fix), so a 43h span now
    # makes EVERY allele unreachable and trips the never-strip-bare branch —
    # which would have left this block asserting a different property than the
    # one it was written for. 60h keeps the shape: 48 reachable, 72 not.
    g2, dropped = reachable_genes(TAKER_GENES, 60.0)
    assert dropped == [72.0], dropped
    assert g2["MAX_HOLD_H"][1] == [48.0], g2["MAX_HOLD_H"]
    assert g2["TAKE_PROFIT"] == TAKER_GENES["TAKE_PROFIT"], "other genes intact"
    assert reachable_genes(TAKER_GENES, 200.0)[1] == [], "all reachable -> no-op"
    assert reachable_genes(TAKER_GENES, 0.0)[1] == [], "unknown span -> no-op"
    assert reachable_genes(TAKER_GENES, 10.0)[1] == [], "never strip the grid bare"

    # _marked prices DEFERRAL: closed_net alone would score this +$2
    assert _marked({"closed_net": 2.0, "unrealized": -5.0}) == -3.0
    assert _marked({"closed_net": 2.0}) == 2.0          # absent -> closed only

    # [2026-07-17 AUDIT] _marked_series = the per-trade decomposition of
    # _marked. The deferrer below closes 2 winners and sits on a -$50 loser:
    # the closed-only series calls it +$4, the marked series prices the truth.
    _def = {"lenses": {"divergence": {"pnl_usd": [2.0, 2.0], "net": 4.0}},
            "open": [{"lens": "divergence", "upnl": -50.0}]}
    assert _pnl_usd(_def, {"divergence"}) == [2.0, 2.0]        # evidence count
    assert _marked_series(_def, {"divergence"}) == [2.0, 2.0, -50.0]
    assert abs(sum(_marked_series(_def, {"divergence"}))
               - _marked(_def, {"divergence"})) < 1e-9, "series must sum to _marked"
    assert net_lcb(_marked_series(_def, {"divergence"})) < 0, "deferral priced"
    assert net_lcb(_pnl_usd(_def, {"divergence"})) > 0, "censored sample lies"
    # an open position on a lens we do NOT score must not leak into the bound
    _other = {"lenses": {"divergence": {"pnl_usd": [1.0], "net": 1.0}},
              "open": [{"lens": "breakout", "upnl": -99.0}]}
    assert _marked_series(_other, {"divergence"}) == [1.0]

    # net_lcb: the winner's curse priced. Zero spread -> bound == total; a
    # noisy sample is discounted; one trade evidences no edge, ever.
    # [2026-07-17 AUDIT] 0.0-on-empty is a JSON-SAFE SENTINEL, not a verdict of
    # "riskless": it out-ranks every genotype with evidence of loss, so it is
    # `rank`'s job (closes>0 leads the key) to keep no-evidence off rank 1 —
    # asserted below. -inf would say it better and would break the payload.
    assert net_lcb([]) == 0.0
    assert net_lcb([5.0]) == 0.0 and net_lcb([-2.0]) == -2.0
    assert abs(net_lcb([1.0] * 20) - 20.0) < 1e-9
    coin = [1.96, -1.54] * 6                            # the tape's real shape
    assert net_lcb(coin) < sum(coin), "spread must be discounted"
    # the SAME per-trade mean/sd with more evidence -> a less punitive bound
    assert net_lcb([1.96, -1.54] * 30) / 30 > net_lcb(coin) / 6
    assert t90(1) == 3.078 and t90(4) == 1.533 and t90(500) == bs.Z80
    assert t90(0) == float("inf")

    # [2026-07-17 AUDIT] rank's two failure modes, driven through the REAL
    # rank()/evaluate() with a faked replay keyed off the patched bar. Both
    # fixtures FAIL on the pre-audit sort key — the population is otherwise
    # identical, so the sort key is the only variable.
    _saved_replay = rp.replay
    try:
        def _fake_replay(tape, up_resolver=None, **_kw):
            # DIV_GAP_PP 37.5 = never fires; 50.0 = defers a $50 loss past the
            # tape's end; 62.5 = the real tape's shape, honestly closed.
            bar = getattr(tt, "DIV_GAP_PP")
            if bar == 37.5:
                return {"lenses": {"divergence": {"pnl_usd": [], "net": 0.0}},
                        "open": [], "closed_net": 0.0, "unrealized": 0.0}
            if bar == 50.0:
                return {"lenses": {"divergence": {"pnl_usd": [2.0] * 20,
                                                  "net": 40.0}},
                        "open": [{"lens": "divergence", "upnl": -50.0}],
                        "closed_net": 40.0, "unrealized": -50.0}
            return {"lenses": {"divergence": {"pnl_usd": [3.0] * 20,
                                              "net": 60.0}},
                    "open": [], "closed_net": 60.0, "unrealized": 0.0}
        rp.replay = _fake_replay
        _pop = [{"DIV_GAP_PP": 37.5}, {"DIV_GAP_PP": 50.0}, {"DIV_GAP_PP": 62.5}]
        _sc = rank(_pop, [1, 2], {"divergence"})
        # the honest closer wins; the deferrer's marked net is NEGATIVE despite
        # 20 closed winners; the do-nothing genotype ranks LAST, not first.
        assert _sc[0]["genotype"]["DIV_GAP_PP"] == 62.5, _sc[0]
        assert _sc[-1]["genotype"]["DIV_GAP_PP"] == 37.5, _sc[-1]
        assert _sc[-1]["closes"] == 0 and _sc[-1]["lcb"] == 0.0   # the sentinel
        _defr = [s for s in _sc if s["genotype"]["DIV_GAP_PP"] == 50.0][0]
        assert _defr["net"] == -10.0 and _defr["lcb"] < 0, _defr
    finally:
        rp.replay = _saved_replay

    # [2026-08-26] THE UP-RESOLVER IS THREADED, and the fitness MOVES with it.
    # A substring test would pass against a resolver that is built and dropped,
    # so this drives the real evaluate() with a fake replay that reports a
    # DIFFERENT book depending on whether it received one — the shape of the
    # live defect (breakoutup unreachable ⇒ 39% of the book invisible).
    _saved_replay = rp.replay
    try:
        def _cov_replay(tape, up_resolver=None, **_kw):
            if up_resolver is None:          # the pre-fix world
                return {"lenses": {"divergence": {"pnl_usd": [-1.0] * 4,
                                                  "net": -4.0}},
                        "open": [], "closed_net": -4.0, "unrealized": 0.0}
            return {"lenses": {"divergence": {"pnl_usd": [-1.0] * 4, "net": -4.0},
                               "breakoutup": {"pnl_usd": [5.0] * 4, "net": 20.0}},
                    "open": [], "closed_net": 16.0, "unrealized": 0.0}
        rp.replay = _cov_replay
        _lenses = {"divergence", "breakoutup"}
        _blind = evaluate({"DIV_GAP_PP": 62.5}, [1, 2], _lenses)
        _seen = evaluate({"DIV_GAP_PP": 62.5}, [1, 2], _lenses,
                         up_resolver=(lambda s, t: True))
        assert _blind["net"] == -4.0 and _seen["net"] == 16.0, (_blind, _seen)
        assert _seen["closes"] == 8 and _blind["closes"] == 4
        # BOTH halves must carry the resolver too — a half scored blind against
        # a full-coverage total is the deferral trap in coverage clothing.
        assert _seen["h1"] == 16.0 and _seen["h2"] == 16.0, _seen
        # ...and rank must forward it, not swallow it.
        _rk = rank([{"DIV_GAP_PP": 62.5}], [1, 2], _lenses,
                   up_resolver=(lambda s, t: True))
        assert _rk[0]["net"] == 16.0, _rk
    finally:
        rp.replay = _saved_replay

    # the resolver's own contract: kill switch reaches it, junk degrades to
    # None (REDUCED COVERAGE), and it is built from the tape's own symbols.
    class _T:                               # minimal (dt, payload) tape shape
        def __init__(self, ts):
            self._ts = ts

        def timestamp(self):
            return self._ts
    # ZEC appears ONLY in the LAST snapshot — a resolver built from the first
    # row alone would silently leave that coin unresolvable for the whole
    # cycle, so the fixture has to be able to see the difference.
    _tape = [(_T(0.0), {"tickets": {"breakout": [{"sym": "SOL"}, {"sym": None}],
                                    "dip": [{"sym": "BTC"}], "momentum": None}}),
             (_T(60.0), {"tickets": {"breakout": [{"sym": "SOL"},
                                                  {"sym": "ZEC"}]}})]
    assert tape_symbols(_tape) == ["BTC", "SOL", "ZEC"], tape_symbols(_tape)
    assert tape_symbols([]) == [] and tape_symbols(None) == []
    _built = []

    def _fac(syms, lo, hi):
        _built.append((tuple(syms), lo, hi))
        return lambda s, t: True
    assert build_up_resolver(_tape, _factory=_fac) is not None
    assert _built == [(("BTC", "SOL", "ZEC"), 0.0, 60.0)], _built
    assert build_up_resolver([], _factory=_fac) is None      # empty tape
    assert build_up_resolver([(_T(0.0), {})], _factory=_fac) is None  # no syms

    def _boom(*_a, **_k):
        raise RuntimeError("candles down")
    assert build_up_resolver(_tape, _factory=_boom) is None, \
        "any trouble must degrade to None, never raise"
    # the KILL SWITCH must reach the builder. It is read at import, so the env
    # form is exercised by the pytest guard (fresh interpreter); here the
    # resolved flag is flipped, which is the value the builder actually reads.
    global UP_RESOLVER_ON
    _sw = UP_RESOLVER_ON
    try:
        UP_RESOLVER_ON = False
        _built.clear()
        assert build_up_resolver(_tape, _factory=_fac) is None, \
            "INCUBATOR_UP_RESOLVER=0 must turn the resolver off"
        assert _built == [], "a disabled resolver must not even be constructed"
    finally:
        UP_RESOLVER_ON = _sw

    # [2026-08-26] the SCORED lens set: breakoutup rides in on its own veto,
    # never on the scout's `breakout` grade (the taker relabels BEFORE it
    # vetoes, so the two are independent), and it never enters LENS_GENE.
    _row = real_tt.BOT_ROW

    def _mults(tag):
        return {"mults": {_row: {"long-breakoutup": tag}}}
    assert "breakoutup" in scored_lens_set({"breakout", "divergence"}, {}, _row)
    assert "breakoutup" in scored_lens_set({"divergence"}, {}, _row), \
        "a vetoed `breakout` must NOT veto `breakoutup` — the taker relabels first"
    assert "breakoutup" in scored_lens_set(set(), None, _row)      # dark => open
    assert "breakoutup" not in scored_lens_set(
        {"breakout"}, _mults({"mult": 0.5, "n": 99}), _row), "decisive self-veto"
    assert "breakout" in scored_lens_set(
        {"breakout"}, _mults({"mult": 0.5, "n": 99}), _row), \
        "the self-veto is breakoutup's alone — it must not touch `breakout`"
    assert "breakoutup" in scored_lens_set(
        {"breakout"}, _mults({"mult": 0.75, "n": 99}), _row), "mild => collect"
    assert scored_lens_set({"dip"}, {}, _row) >= {"dip"}, "allowed is preserved"
    assert "breakoutup" not in LENS_GENE and set(LENS_GENE) == {
        "breakout", "dip", "momentum", "divergence"}, LENS_GENE

    # freshness is the CALLER's job, and this is the caller's read
    assert fresh_stake_mults({"updated": _iso(now_ts()), "ttl_sec": 600,
                              "mults": {}}, now_ts()).get("mults") == {}
    assert fresh_stake_mults({"updated": _iso(now_ts() - 9999), "ttl_sec": 600},
                             now_ts()) == {}, "stale => {} => vetoes nothing"
    assert fresh_stake_mults({"updated": _iso(now_ts() + 9999), "ttl_sec": 600},
                             now_ts()) == {}, "future stamp => not fresh"
    assert fresh_stake_mults({"updated": "junk"}, now_ts()) == {}
    assert fresh_stake_mults(None, now_ts()) == {}
    # no ttl_sec => the taker's own 26000s fallback, mirrored not invented
    assert fresh_stake_mults({"updated": _iso(now_ts() - 100)}, now_ts()) != {}

    # GAMETE SELECTION: the noise genotype the champion gate rejects must not
    # BREED either, and an unmeasurable genotype is not a gamete however fit.
    # [2026-07-29] fixtures use REAL in-cage genes: select_elite now enforces
    # enactability itself, so a synthetic gene name would (correctly) be
    # filtered and the test would pass for the wrong reason.
    _a1, _a2, _a3 = [{"TAKE_PROFIT": v} for v in TAKER_GENES["TAKE_PROFIT"][1][:3]]
    sc = [{"genotype": _a1, "net": 9.0, "h1": 0.01, "h2": 8.99,
           "closes": 40, "lcb": 8.0, "both_halves_pos": False},   # one-half win
          {"genotype": _a3, "net": 8.0, "h1": 4.0, "h2": 4.0,
           "closes": 3, "lcb": 7.0, "both_halves_pos": True},     # 3 trades
          {"genotype": _a2, "net": 5.0, "h1": 2.5, "h2": 2.5,
           "closes": 40, "lcb": 4.0, "both_halves_pos": True}]    # robust
    el = select_elite(sc, 4, 12)
    assert [e["genotype"] for e in el] == [_a2], el
    # ...and an OUT-OF-CAGE genotype is refused however fit — enforced by
    # select_elite itself, so no call site can opt out (the mutation that
    # passed an unfiltered list survived until this moved in here).
    _oc = {"TAKE_PROFIT": max(RESEARCH_GENES["TAKE_PROFIT"][1])}
    assert not is_enactable(_oc)
    assert select_elite([{"genotype": _oc, "net": 99.0, "h1": 9.0, "h2": 9.0,
                          "closes": 99, "lcb": 9.0,
                          "both_halves_pos": True}], 4, 12) == [], \
        "an out-of-cage genome must never become a gamete"
    assert select_elite(sc, 0, 12) == [], "elite cap honored"
    assert select_elite([], 4, 12) == []

    # anti-overfit champion gate. Every case carries enough closes to reach
    # the bar under test — MIN_CLOSES is checked FIRST and shadows the rest.
    def _c(**kw):
        return dict({"genotype": {"A": 2}, "closes": MIN_CLOSES}, **kw)

    # too few closed trades -> tentative no matter how good it looks
    thin = _c(net=99.0, h1=49.0, h2=50.0, closes=MIN_CLOSES - 1)
    isc0, _, _, conf0, why0 = assess_champion(thin, 0.0, 200, None, 0)
    assert not isc0 and conf0 == "tentative" and "closed trades" in why0, why0
    # the +$0.01-half case is REJECTED as noise
    noise = _c(net=2.35, h1=0.01, h2=2.34)
    isc, _, _, conf, why = assess_champion(noise, 0.0, 200, None, 0)
    assert not isc and conf == "tentative" and "half" in why, (conf, why)
    # a single lucky fill can no longer clear the gates: one SL->TP swing is
    # TRADE_SWING, and both bars are now denominated above it
    assert HALF_MARGIN >= TRADE_SWING and EDGE_MARGIN > TRADE_SWING
    one_fill = _c(net=TRADE_SWING, h1=1.96, h2=1.96)
    isc_f, _, _, _, why_f = assess_champion(one_fill, 0.0, 200, None, 0)
    assert not isc_f, (why_f, TRADE_SWING)
    # short tape -> tentative even with a strong, balanced result
    strong = _c(net=8.0 + EDGE_MARGIN, h1=4.0 + HALF_MARGIN, h2=4.0 + HALF_MARGIN)
    isc2, _, _, conf2, why2 = assess_champion(strong, 0.0, 10, None, 0)
    assert not isc2 and "min" in why2, why2
    # thin edge over default -> tentative
    isc3, _, _, conf3, _ = assess_champion(strong, strong["net"] - 0.01, 200, None, 0)
    assert not isc3 and conf3 == "tentative"
    # a genuine champion: enough closes, long tape, both halves strong, beats
    # default, and persistence promotes candidate -> stable across cycles
    isc4, streak4, stable4, conf4, _ = assess_champion(strong, 0.0, 200, None, 0)
    assert isc4 and streak4 == 1 and not stable4 and conf4 == "candidate"
    isc5, streak5, stable5, conf5, _ = assess_champion(
        strong, 0.0, 200, {"A": 2}, 2)          # same champ, 3rd cycle
    assert isc5 and streak5 == 3 and stable5 and conf5 == "stable"
    # a DIFFERENT champion resets the streak (no free ride on prior stability)
    other = _c(genotype={"A": 3}, net=strong["net"] + 1, h1=4.5 + HALF_MARGIN,
               h2=4.5 + HALF_MARGIN)
    _, streak6, stable6, _, _ = assess_champion(other, 0.0, 200, {"A": 2}, 5)
    assert streak6 == 1 and not stable6

    # [2026-07-22] PROSPECT REGISTER (operator: "the incubator has no list of
    # the prospective bots its created and their stats"). Merge across
    # cycles; origin sticks at birth; roles recompute; best-ever never
    # regresses; dormants kept by best-lcb; cap keeps the current cycle
    # whole; junk tolerated.
    assert _sig({"B": 10, "A": 0.05}) == "A=0.05|B=10"
    assert _sig({"A": 0.05}) == _sig({"A": 0.05 + 1e-13}), "float repr stable"
    sc1 = [{"genotype": {"A": 2, "B": 10}, "net": 5.0, "h1": 2.0, "h2": 3.0,
            "closes": 20, "lcb": 4.0, "both_halves_pos": True},
           {"genotype": {"A": 1, "B": 10}, "net": 1.0, "h1": 0.5, "h2": 0.5,
            "closes": 8, "lcb": 0.4, "both_halves_pos": False},
           {"genotype": {"A": 3, "B": 20}, "net": 0.0, "h1": 0.0, "h2": 0.0,
            "closes": 0, "lcb": 0.0, "both_halves_pos": False}]
    seeds1 = [{"A": 1, "B": 10}, {"A": 2, "B": 10}]
    p1 = update_prospects(None, sc1, seeds1, {"A": 1, "B": 10},
                          {"genotype": {"A": 2, "B": 10}},
                          [{"genotype": {"A": 2, "B": 10}}], "T1")
    assert [e["role"] for e in p1] == ["fittest", "scored", "unmeasured"], p1
    assert [e["origin"] for e in p1] == ["seed", "default", "bred"], p1
    assert all(e["born"] == "T1" and e["cycles"] == 1 for e in p1)
    # cycle 2: new fittest; the old one leaves the population -> dormant,
    # ranked by best lcb; born/cycles/best-ever carry forward
    sc2 = [{"genotype": {"A": 1, "B": 10}, "net": 6.0, "h1": 3.0, "h2": 3.0,
            "closes": 30, "lcb": 5.0, "both_halves_pos": True}]
    p2 = update_prospects(p1, sc2, seeds1, {"A": 1, "B": 10},
                          {"genotype": {"A": 1, "B": 10}}, [], "T2")
    top2 = p2[0]
    assert (top2["cycles"] == 2 and top2["born"] == "T1"
            and top2["last_seen"] == "T2" and top2["role"] == "fittest")
    assert top2["best_net"] == 6.0 and top2["best_lcb"] == 5.0
    dorm = [e for e in p2 if e["role"] == "dormant"]
    assert [d["genotype"] for d in dorm] == [{"A": 2, "B": 10},
                                             {"A": 3, "B": 20}], dorm
    # a worse re-score updates latest but never the best-ever
    sc3 = [{"genotype": {"A": 1, "B": 10}, "net": -2.0, "h1": -1.0,
            "h2": -1.0, "closes": 35, "lcb": -3.0, "both_halves_pos": False}]
    p3 = update_prospects(p2, sc3, seeds1, {"A": 1, "B": 10}, None, [], "T3")
    assert p3[0]["net"] == -2.0 and p3[0]["best_net"] == 6.0
    assert p3[0]["best_lcb"] == 5.0 and p3[0]["role"] == "scored"
    # cap: current cycle survives whole, dormants fill what remains
    many = [{"genotype": {"A": i, "B": 0}, "net": 0.0, "h1": 0.0, "h2": 0.0,
             "closes": 1, "lcb": float(-i), "both_halves_pos": False}
            for i in range(10)]
    pc = update_prospects(p3, many, [], {}, None, [], "T4", cap=6)
    assert len(pc) == 6 and all(e["last_seen"] == "T4" for e in pc), pc
    # junk prior entries are dropped, not fatal
    pj = update_prospects([{"nope": 1}, None, 42], sc2, [], {}, None, [], "T")
    assert pj[0]["cycles"] == 1 and len(pj) == 1

    # [2026-07-29] STALENESS STAMP — a dormant carry must not read as a
    # measurement. Live shape: a dormant's carried net was +$39.81 while a
    # re-score on the same day's tape read -$11.12.
    t0, t1 = "2026-07-28T01:45:00+00:00", "2026-07-29T07:45:00+00:00"
    s_a = update_prospects(None, sc1, seeds1, {"A": 1, "B": 10},
                           {"genotype": {"A": 2, "B": 10}}, [], t0)
    assert all(e["stats_current"] is True and e["stats_age_h"] == 0.0
               for e in s_a), "scored this cycle => current, age 0"
    s_b = update_prospects(s_a, sc2, seeds1, {"A": 1, "B": 10},
                           {"genotype": {"A": 1, "B": 10}}, [], t1)
    fresh = [e for e in s_b if e["role"] != "dormant"]
    stale = [e for e in s_b if e["role"] == "dormant"]
    assert fresh and stale, s_b
    assert all(e["stats_current"] is True and e["stats_age_h"] == 0.0
               for e in fresh)
    assert all(e["stats_current"] is False for e in stale)
    assert all(e["stats_age_h"] == 30.0 for e in stale), stale   # t0 -> t1
    # the frozen numbers themselves are UNCHANGED — the stamp is the fix,
    # not a rewrite of history (best-ever semantics stay intact)
    d_old = [e for e in s_a if e["genotype"] == {"A": 2, "B": 10}][0]
    d_new = [e for e in stale if e["genotype"] == {"A": 2, "B": 10}][0]
    assert d_new["net"] == d_old["net"] and d_new["best_net"] == d_old["best_net"]
    # UNKNOWN age must never read as fresh (the whole point of the stamp)
    assert _age_h("not-a-date", t1) is None and _age_h(t0, None) is None
    s_c = update_prospects(s_a, sc2, seeds1, {"A": 1, "B": 10}, None, [], "T2")
    assert all(e["stats_age_h"] is None for e in s_c
               if e["role"] == "dormant"), "unparseable => None, not 0.0"

    # [2026-07-29] JOINT-SPACE SWEEP. The property that matters is COVERAGE:
    # walking the cursor must eventually visit EVERY genotype in the product,
    # deterministically, and gene INTERACTIONS must be reachable (the axis
    # probes alone can never produce a genotype with two genes off-default).
    _g2 = {"A": ("l.a", [1, 2, 3]), "B": ("l.b", [10, 20])}
    assert joint_space_size(_g2) == 6
    # a full sweep in slices covers the space EXACTLY once, then wraps
    seen_all, cur = [], 0
    for _ in range(3):
        pop, cur, size = explore_slice(_g2, cur, 2)
        seen_all += [tuple(sorted(g.items())) for g in pop]
    assert size == 6 and len(seen_all) == 6, seen_all
    assert len(set(seen_all)) == 6, "every genotype visited exactly once"
    assert cur == 0, "cursor wraps to the start after a full sweep"
    # DETERMINISM ACROSS PROCESSES, pinned STRUCTURALLY. Comparing two calls
    # in one process is not enough — that passes even with `set()` ordering
    # (caught by mutation: the intra-process check survived it). A persisted
    # cursor must mean the same genotype NEXT hour, in a fresh interpreter,
    # so the enumeration is pinned to sorted gene names with the first name
    # varying fastest — a property `set()` iteration cannot satisfy.
    assert explore_slice(_g2, 0, 1)[0] == [{"A": 1, "B": 10}], "index 0"
    assert explore_slice(_g2, 1, 1)[0] == [{"A": 2, "B": 10}], "A varies fastest"
    assert explore_slice(_g2, 3, 1)[0] == [{"A": 1, "B": 20}], "then B rolls"
    assert explore_slice(_g2, 2, 3)[0] == explore_slice(_g2, 2, 3)[0]
    # ...and it is a JOINT sweep — genotypes with BOTH genes off-default exist,
    # which is exactly what seed_population's axis probes can never emit
    full = explore_slice(_g2, 0, 99)[0]
    dflt = {"A": 1, "B": 10}
    assert any(g["A"] != dflt["A"] and g["B"] != dflt["B"] for g in full), \
        "joint space must reach gene INTERACTIONS, not just axes"
    # the mirror half, on REAL genes (seed_population reads tt for defaults):
    # no axis probe ever varies two genes at once, so the interaction above is
    # unreachable without the joint sweep.
    _gr = {g: TAKER_GENES[g] for g in ("DIP_RANGE", "TAKE_PROFIT")}
    _rd = {g: getattr(tt, g) for g in _gr}
    assert not any(gt["DIP_RANGE"] != _rd["DIP_RANGE"]
                   and gt["TAKE_PROFIT"] != _rd["TAKE_PROFIT"]
                   for gt in seed_population(_gr)), "axis probes vary ONE gene"
    assert any(gt["DIP_RANGE"] != _rd["DIP_RANGE"]
               and gt["TAKE_PROFIT"] != _rd["TAKE_PROFIT"]
               for gt in explore_slice(_gr, 0, 999)[0]), "the sweep reaches them"
    # a space smaller than the budget returns whole, cursor still meaningful
    pop_s, cur_s, _ = explore_slice(_g2, 0, 1000)
    assert len(pop_s) == 6 and cur_s == 0
    # kill switch + empty genes claim nothing and cannot raise
    assert explore_slice(_g2, 0, 0)[0] == []
    assert explore_slice({}, 0, 10)[0] == []
    assert explore_slice(_g2, None, 2)[1] == 2, "None cursor starts at 0"

    # [2026-07-29] RESEARCH SPACE — search beyond the cage, but NEVER let an
    # out-of-cage genotype become something a human might act on.
    _in = {g: getattr(tt, g) for g in TAKER_GENES}
    assert is_enactable(_in), "the shipped genome must be enactable"
    for g, (lever, grid) in TAKER_GENES.items():
        assert is_enactable({g: grid[0]}) and is_enactable({g: grid[-1]}), g
    # every RESEARCH grid must extend BEYOND its cage — otherwise the research
    # space is the cage wearing a different name and buys nothing
    for g, (lever, rgrid) in RESEARCH_GENES.items():
        assert any(not is_enactable({g: v}) for v in rgrid), \
            f"{g}: research grid never leaves the cage"
        assert any(is_enactable({g: v}) for v in rgrid), \
            f"{g}: research grid must still contain shippable alleles"
    # fail-CLOSED: unknown gene, or an unclampable value, is NOT enactable
    assert is_enactable({"NOT_A_GENE": 1}) is False
    assert is_enactable({"TAKE_PROFIT": 99.0}) is False
    assert is_enactable({}) is True                      # nothing to violate
    # cage_analysis: flags a bound as BINDING only when the best in-cage
    # allele sits ON the bound AND an out-of-cage allele beat it.
    _hi = max(TAKER_GENES["TAKE_PROFIT"][1])
    _out = max(RESEARCH_GENES["TAKE_PROFIT"][1])
    _tp = {"TAKE_PROFIT": TAKER_GENES["TAKE_PROFIT"]}
    _ch = {"both_halves_pos": True}          # champion-grade out-of-cage win
    binds = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _hi}, "net": 5.0, "lcb": 1.0, **_ch},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 9.0, "lcb": 3.0, **_ch},
    ], _tp)
    assert binds["TAKE_PROFIT"]["cage_may_bind"] is True, binds
    assert binds["TAKE_PROFIT"]["best_out_of_cage"] == _out, binds
    # ...and NOT when the out-of-cage allele lost (a bound that is not
    # costing anything must not read as binding)
    ok = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _hi}, "net": 5.0, "lcb": 1.0},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 1.0, "lcb": 0.5},
    ], _tp)
    assert ok["TAKE_PROFIT"]["cage_may_bind"] is False, ok
    # ...nor when the best in-cage result is INTERIOR (bound not reached)
    _mid = TAKER_GENES["TAKE_PROFIT"][1][1]
    interior = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _mid}, "net": 5.0, "lcb": 1.0},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 9.0, "lcb": 3.0},
    ], _tp)
    assert interior["TAKE_PROFIT"]["cage_may_bind"] is False, interior
    # THE WINNER'S-CURSE GUARD, and it is the assertion that matters most:
    # a MAX over a big sweep with a NEGATIVE lower bound is not evidence.
    # Without this the detector fired a false "widen the cage" on STOP_LOSS
    # on its first live run — the wider-stop artifact wearing a good net.
    curse = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _hi}, "net": 5.0, "lcb": -2.0},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 99.0, "lcb": -1.0},
    ], _tp)
    assert curse["TAKE_PROFIT"]["cage_may_bind"] is False, curse
    assert curse["TAKE_PROFIT"]["net_out"] == 99.0, "still REPORTED, not hidden"
    assert curse["TAKE_PROFIT"]["lcb_out"] == -1.0, curse
    # a missing lcb is not a positive one (fail-closed on absent evidence)
    nolcb = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _hi}, "net": 5.0},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 9.0},
    ], _tp)
    assert nolcb["TAKE_PROFIT"]["cage_may_bind"] is False, nolcb
    # THE LIVE SHAPE that fooled v1: a big net and a POSITIVE lcb, but the
    # halves disagree. Champion-grade means all three; two out of three is
    # the wider-stop artifact, and it must not license moving a cage.
    half = cage_analysis([
        {"genotype": {"TAKE_PROFIT": _hi}, "net": 12.86, "lcb": -1.5,
         "both_halves_pos": False},
        {"genotype": {"TAKE_PROFIT": _out}, "net": 16.34, "lcb": 2.01,
         "both_halves_pos": False},
    ], _tp)
    assert half["TAKE_PROFIT"]["cage_may_bind"] is False, half
    # THE SAFETY PROPERTY: select_elite must never hand an out-of-cage
    # genotype forward as a gamete. run_once filters to `enactable` first;
    # this pins that an unfiltered list WOULD have leaked one, so the filter
    # is load-bearing and not decorative.
    _leak = {"genotype": {"TAKE_PROFIT": _out}, "net": 99.0, "lcb": 99.0,
             "h1": 9.0, "h2": 9.0, "closes": 99, "both_halves_pos": True}
    assert select_elite([_leak], 4, 1) == [], \
        "select_elite itself refuses an out-of-cage gamete (see its own test)"

    # [2026-07-29] REGISTER HYGIENE — dedupe / dispose / re-rank.
    def _pe(gt, net, lcb, cycles, age, current=False):
        return {"genotype": gt, "net": net, "lcb": lcb, "cycles": cycles,
                "stats_age_h": age, "stats_current": current}
    # (a) DEDUPE: two entries differing only in a gene that is NOT evolvable
    #     are ONE experiment. The freshest representative survives.
    dup = [_pe({"BRK_RANGE": 0.95, "DIP_RANGE": 0.05}, 5.0, 4.0, 5, 40.0),
           _pe({"BRK_RANGE": 0.90, "DIP_RANGE": 0.05}, 9.0, 8.0, 5, 2.0)]
    kept, sm = prune_register(dup, {"DIP_RANGE"}, "T", dead_age_h=1e9)
    assert len(kept) == 1 and sm["merged_dupes"] == 1, (kept, sm)
    assert kept[0]["genotype"]["BRK_RANGE"] == 0.90, "freshest survives"
    assert kept[0]["merged_dupes"] == 1
    # ...and with that gene evolvable they stay two distinct candidates
    kept2, sm2 = prune_register(dup, {"BRK_RANGE", "DIP_RANGE"}, "T",
                                dead_age_h=1e9)
    assert len(kept2) == 2 and sm2["merged_dupes"] == 0, sm2
    # (b) DISPOSAL is on the LATEST reading, never the high-water mark: this
    #     entry's best_net is glorious and its last measurement lost.
    corpse = _pe({"A": 1}, -4.0, -6.0, 5, 48.0)
    corpse["best_net"], corpse["best_lcb"] = 99.0, 99.0
    corpse["closes"] = 12
    kept3, sm3 = prune_register([corpse], {"A"}, "T")
    assert kept3 == [] and sm3["retired"] == 1, (kept3, sm3)
    assert sm3["examples"][0]["kind"] == "LOSING", sm3
    assert "last measured net -4.00 on 12 closes" in sm3["examples"][0]["why"], sm3
    # INERT vs LOSING are distinguished — "never fired" and "fired and lost"
    # are different failures and the disposal log must say which.
    inert = _pe({"A": 2}, 0.0, 0.0, 5, 48.0); inert["closes"] = 0
    _k, sm3b = prune_register([inert], {"A"}, "T")
    assert sm3b["examples"][0]["kind"] == "INERT", sm3b
    assert "never traded" in sm3b["examples"][0]["why"], sm3b
    # (c) FAIL-SAFES: never retire on unknown staleness, on a fresh scoring,
    #     on too few cycles, or on a positive latest reading.
    for e, why in ((_pe({"A": 1}, -4.0, -6.0, 5, None), "unknown age"),
                   (_pe({"A": 1}, -4.0, -6.0, 5, 48.0, current=True), "scored now"),
                   (_pe({"A": 1}, -4.0, -6.0, 1, 48.0), "too few cycles"),
                   (_pe({"A": 1}, 4.0, 2.0, 5, 48.0), "latest is positive"),
                   (_pe({"A": 1}, -4.0, -6.0, 5, 2.0), "not stale yet")):
        k, s = prune_register([e], {"A"}, "T")
        assert len(k) == 1 and s["retired"] == 0, (why, k, s)
    # (d) RANKING is by the LATEST lcb — a lucky best-ever must not outrank a
    #     currently-better genotype (the immortal-corpse bug).
    lucky = _pe({"A": 1}, 0.5, 0.5, 9, 5.0); lucky["best_lcb"] = 99.0
    good = _pe({"A": 2}, 8.0, 7.0, 2, 5.0); good["best_lcb"] = 7.0
    kept4, _ = prune_register([lucky, good], {"A"}, "T", dead_age_h=1e9)
    assert kept4[0]["genotype"] == {"A": 2}, kept4
    # entries scored THIS cycle outrank any dormant, whatever its lcb
    fresh_lo = _pe({"A": 3}, -1.0, -1.0, 1, 0.0, current=True)
    kept5, _ = prune_register([lucky, fresh_lo], {"A"}, "T", dead_age_h=1e9)
    assert kept5[0]["genotype"] == {"A": 3}, kept5
    # (e) junk in, no crash; cap honoured
    assert prune_register(None, {"A"}, "T")[0] == []
    assert prune_register([{"nope": 1}, None, 7], {"A"}, "T")[0] == []
    many = [_pe({"A": i}, 1.0, float(i), 1, 1.0) for i in range(10)]
    assert len(prune_register(many, {"A"}, "T", cap=4)[0]) == 4

    # funding prospect view: status precedence + stats whitelist + dark states
    fp = funding_prospects_view(
        [{"name": "xp-a", "levers": {"xp.funding.take_profit": 0.05},
          "at": "T0"},
         {"name": "xp-b", "levers": {}}, {"name": "xp-c", "levers": {}},
         {"name": "xp-d", "levers": {}}, {"name": "xp-e", "levers": {}},
         "junk", {"levers": {}}],
        [{"name": "xp-c"}],
        {"phase": "running", "current": "xp-a",
         "last_eval": {"why": "warming", "n_shadow": 12, "promote": False},
         "done": ["xp-d"],
         "verdicts": [{"name": "xp-b", "verdict": "ABANDONED", "ts": "V1",
                       "eval": {"why": "14d"}},
                      {"name": "xp-b", "verdict": "PROMOTED", "ts": "V2",
                       "eval": {"n_live": 11, "bogus": 9}}]})
    by = {e["name"]: e for e in fp}
    assert len(fp) == 5, fp
    assert by["xp-a"]["status"] == "running" and by["xp-a"]["at"] == "T0"
    assert by["xp-a"]["stats"] == {"why": "warming", "n_shadow": 12}
    assert by["xp-b"]["status"] == "promoted" and by["xp-b"]["ts"] == "V2"
    assert by["xp-b"]["stats"] == {"n_live": 11}, "stats are whitelisted"
    assert by["xp-c"]["status"] == "queued"
    assert by["xp-d"]["status"] == "completed"
    assert by["xp-e"]["status"] == "proposed"
    fp2 = funding_prospects_view([{"name": "x", "levers": {}}], None, None)
    assert fp2[0]["status"] == "proposed" and "stats" not in fp2[0]

    # [2026-07-28 §3b residual] queue_carry — the heartbeat's fresh-gated
    # read. Mutation check: dropping the staleness gate turns the stale/
    # unstamped asserts red (dead entries would republish under a fresh
    # stamp); dropping the carry turns the fresh assert red (every republish
    # would orphan the endorsed queue).
    _qn = now_ts()
    _fresh_q = {"updated": _iso(_qn - 60), "ttl_sec": 10800,
                "candidates": [{"name": "xp-a", "levers": {}}, "junk"]}
    assert [c["name"] for c in queue_carry(_fresh_q, _qn)] == ["xp-a"], \
        "a fresh queue carries its dict candidates (junk dropped, not fatal)"
    _stale_q = dict(_fresh_q, updated=_iso(_qn - 11 * 86400))
    assert queue_carry(_stale_q, _qn) == [], \
        "a stale queue carries NOTHING (dead entries retire, not re-stamp)"
    assert queue_carry({"candidates": _fresh_q["candidates"]}, _qn) == [], \
        "an unstamped queue fails closed"
    assert queue_carry(None, _qn) == [] and queue_carry({}, _qn) == []

    print("strategy_incubator selftest OK (seed, dedupe, crossover+mutation "
          "on-grid, lever mapping/clamp, judge-gated funding proposals, "
          "proprioception hurting-gene skip, IMB-10 marked/reachable-holds, "
          "t-LCB winner's-curse ranking, gamete selection, anti-overfit "
          "champion gate incl. the closes floor, prospect register "
          "merge/roles/best-ever/cap, funding prospect lifecycle join)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(store.organ_main('strategy-incubator', run_once))
