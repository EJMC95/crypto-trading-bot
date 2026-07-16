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
import brain_stats as bs
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
    "BRK_RANGE": ("taker.brk_range", [0.90, 0.93, 0.95, 0.97]),
    "DIP_RANGE": ("taker.dip_range", [0.05, 0.08, 0.11, 0.15]),
    "MOMO_CHG": ("taker.momo_chg", [3.0, 4.0, 5.0, 6.0]),
    # [2026-07-17] DIV_GAP_PP was the one taker lever in the fleet_tuning
    # registry (taker.div_gap_pp, bounds 300-700) that the taker consumes and
    # the scout tuner walks, but the GENE POOL omitted — so the fleet's only
    # SHORT lens was unevolvable and the genome was long-only. On the measured
    # tape divergence is also the only lens not losing (+$2.10 — on n=1, which
    # is itself the point). The tuner's ladder only ever WIDENS (500->300);
    # this grid also explores TIGHTENING, which nothing else in the fleet does.
    "DIV_GAP_PP": ("taker.div_gap_pp", [300.0, 400.0, 500.0, 600.0, 700.0]),
    "TAKE_PROFIT": ("taker.tp", [0.03, 0.04, 0.05, 0.06]),
    "STOP_LOSS": ("taker.sl", [-0.04, -0.03, -0.02]),
    "MAX_HOLD_H": ("taker.max_hold_h", [24.0, 48.0, 72.0]),
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
    "enter_apr": ("xp.funding.enter_apr", [0.30, 0.40, 0.50]),
    "take_profit": ("xp.funding.take_profit", [0.04, 0.05, 0.06]),
    "max_hold_h": ("xp.funding.max_hold_h", [48.0, 72.0, 96.0]),
}


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


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


def live_lenses(lens_fwd):
    """The lenses the LIVE taker is currently ALLOWED to fill (2026-07-17).

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
    return set(LENS_GENE) - tt.vetoed_lenses(lens_fwd)


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
    about a bot that does not exist and must not enter the fitness."""
    out = []
    for l, s in (rep.get("lenses") or {}).items():
        if lenses is None or l in lenses:
            out.extend(s.get("pnl_usd") or [])
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

def evaluate(genotype, tape, lenses=None):
    """Fitness of a TAKER genotype = replayed MARKED net over the tape (see
    _marked), with a both-halves-positive flag (an offspring that only wins
    one lucky half is not fit), the closed-trade COUNT (the real evidence
    unit) and a lower confidence bound. `lenses` restricts the score to the
    lenses the live taker may actually fill. Patches tt bars, restores."""
    saved = {g: getattr(tt, g) for g in genotype}
    try:
        for g, v in genotype.items():
            setattr(tt, g, v)
        full = rp.replay(tape)
        mid = len(tape) // 2
        h1 = _marked(rp.replay(tape[:mid]), lenses) if mid else 0.0
        h2 = _marked(rp.replay(tape[mid:]), lenses) if mid else 0.0
    finally:
        for g, v in saved.items():
            setattr(tt, g, v)
    pnl = _pnl_usd(full, lenses)
    return {"net": round(_marked(full, lenses), 3), "h1": round(h1, 3),
            "h2": round(h2, 3), "closes": len(pnl),
            "lcb": round(net_lcb(pnl), 3),
            # both-halves POSITIVE-BY-MARGIN — a +$0.01 half is noise, not edge
            "both_halves_pos": h1 >= HALF_MARGIN and h2 >= HALF_MARGIN}


def rank(population, tape, lenses=None):
    scored = [{"genotype": gt, **evaluate(gt, tape, lenses)} for gt in population]
    # [2026-07-17] fittest = highest LOWER BOUND, not the highest point
    # estimate. Ranking a population by its max point estimate IS the winner's
    # curse this file's header warns about; net only breaks ties between
    # equally-evidenced genotypes.
    scored.sort(key=lambda s: (s["lcb"], s["net"]), reverse=True)
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
    inbreed toward a converged elite the way a pure elite-carry GA would."""
    return [s for s in scored
            if s["closes"] >= min_closes and s["both_halves_pos"]][:n]


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

def funding_proposals(judge_state, incubator_state, hurting=None):
    """Novel FUNDING genotypes not already run/queued — proposed for the
    experiment judge's paired bar. Diversity-ordered (single-gene changes
    first). Never pre-scored (no funding replay); the judge is the filter.
    [16-Jul consumer support] 🦾 a gene whose LIVE counterpart lever is
    currently proprioception-graded HURTING is skipped this cycle — the
    live lane just measured that knob bad; don't spend a 7-day judge slot
    re-proposing it while the verdict holds. Restrict-only (only removes
    proposals) and fail-safe (a dark organ skips nothing)."""
    # [2026-07-17 IMB-23] the baseline is the funding bot's OWN env defaults
    # (the same env names it reads), not a hard-coded snapshot: if the
    # operator drifts an env, an allele equal to the REAL baseline is a
    # no-op and must be skipped, not proposed as a 7-day experiment. (The
    # old get_lever `default` dict here was dead code — computed, never
    # read — and the literals it shadowed could silently diverge.)
    base = {"enter_apr": float(os.environ.get("FUNDING_ENTER_APR", "0.40")),
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
    props = []
    for g, (lever, grid) in FUNDING_GENES.items():
        if lever.replace("xp.", "live.", 1) in hurting:
            continue      # live lane measured this knob bad — wait it out
        for allele in grid:
            if allele == base[g]:
                continue
            name = f"xp-{g}-{allele:g}"
            if name in tried:
                continue
            levers = {lever: allele}
            props.append({"name": name, "levers": levers})
    return props[:6]


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    tape, used = rp.load_tape(source="auto")

    # --- TAKER breeding (shadow-only, replay-scored) -----------------------
    leaderboard, champion = [], None
    scored_lenses = set(LENS_GENE)      # fail-safe open: veto nothing
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
        allowed = scored_lenses = live_lenses(lens_fwd)
        genes, gene_dropped = evolvable_genes(genes, allowed)
        if gene_dropped:
            print(f"[incubator] lens veto — brain grades "
                  f"{sorted(set(LENS_GENE) - allowed)} negative at sample "
                  f"size; genes {gene_dropped} dropped and their fills "
                  f"excluded from fitness (breeding a vetoed lens optimizes a "
                  f"bot that does not exist)", flush=True)
        prior_elite = conform([e.get("genotype") for e in
                               (prior.get("elite") or [])], genes)
        population = dedupe(seed_population(genes) + breed(prior_elite, genes))
        scored = rank(population, tape, allowed)
        # [2026-07-17] GAMETES (who breeds) and the CHAMPION (what we would
        # trust) are now separate questions. The elite are robustness-filtered
        # so noise cannot reproduce; the fittest genotype is still assessed and
        # published either way, so its confidence reason explains WHY it is not
        # a champion instead of the card just going quiet.
        leaderboard = select_elite(scored, ELITE_N, MIN_GT_CLOSES)
        default_gt = {g: getattr(tt, g) for g in genes}
        default_net = next((s["net"] for s in scored
                            if s["genotype"] == default_gt), 0.0)
        top = scored[0] if scored else None
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
    else:
        print(f"[incubator] tape too short ({len(tape)}/{MIN_SNAPS}) — "
              f"skipping taker breeding", flush=True)

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
    if hurting:
        print(f"[incubator] 🦾 proprioception hurting levers honored: "
              f"{sorted(hurting)}", flush=True)
    if props:
        q = store.load_state(QUEUE_KEY) or {}
        existing = {p["name"] for p in (q.get("candidates") or [])}
        merged = (q.get("candidates") or []) + [p for p in props
                                                if p["name"] not in existing]
        store.save_state(QUEUE_KEY, {"updated": _iso(now), "ttl_sec": TTL_SEC,
                                     "candidates": merged[:20],
                                     "source": "strategy-incubator"})
        print(f"[incubator] proposed {len(props)} funding candidate(s) to "
              f"xp-queue (judge-gated): {[p['name'] for p in props]}", flush=True)

    payload = {
        "updated": _iso(now), "ttl_sec": TTL_SEC,
        "tape_snaps": len(tape), "tape_source": used,
        "elite": leaderboard, "champion": champion,
        # [2026-07-17] what the fitness was actually scored on — a champion
        # means nothing without the lens set the live taker could fill.
        "lenses_scored": sorted(scored_lenses),
        "lenses_vetoed": sorted(set(LENS_GENE) - scored_lenses),
        "proposed": (prior.get("proposed") or []) + props,
    }
    payload["proposed"] = payload["proposed"][-20:]
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "top_net": leaderboard[0]["net"] if leaderboard else None,
                                     "n_proposed": len(props)})
        except Exception:
            pass
    print(f"[incubator] {_iso(now)} elite={len(leaderboard)} "
          f"funding_proposed={len(props)}", flush=True)
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
    js = {"verdicts": [{"name": "xp-enter_apr-0.3"}]}
    props = funding_proposals(js, {})
    names = {p["name"] for p in props}
    assert "xp-enter_apr-0.3" not in names, "already-tried excluded"
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
    held = conform([{"MAX_HOLD_H": 72.0}], reachable_genes(TAKER_GENES, 43.0)[0])
    assert held[0]["MAX_HOLD_H"] == 72.0, "off-grid allele in force is kept"

    # [2026-07-17] IMB-10: unreachable max-hold alleles dropped, and only those
    g2, dropped = reachable_genes(TAKER_GENES, 43.0)
    assert dropped == [48.0, 72.0], dropped
    assert g2["MAX_HOLD_H"][1] == [24.0], g2["MAX_HOLD_H"]
    assert g2["TAKE_PROFIT"] == TAKER_GENES["TAKE_PROFIT"], "other genes intact"
    assert reachable_genes(TAKER_GENES, 200.0)[1] == [], "all reachable -> no-op"
    assert reachable_genes(TAKER_GENES, 0.0)[1] == [], "unknown span -> no-op"
    assert reachable_genes(TAKER_GENES, 10.0)[1] == [], "never strip the grid bare"

    # _marked prices DEFERRAL: closed_net alone would score this +$2
    assert _marked({"closed_net": 2.0, "unrealized": -5.0}) == -3.0
    assert _marked({"closed_net": 2.0}) == 2.0          # absent -> closed only

    # net_lcb: the winner's curse priced. Zero spread -> bound == total; a
    # noisy sample is discounted; one trade evidences no edge, ever.
    assert net_lcb([]) == 0.0
    assert net_lcb([5.0]) == 0.0 and net_lcb([-2.0]) == -2.0
    assert abs(net_lcb([1.0] * 20) - 20.0) < 1e-9
    coin = [1.96, -1.54] * 6                            # the tape's real shape
    assert net_lcb(coin) < sum(coin), "spread must be discounted"
    # the SAME per-trade mean/sd with more evidence -> a less punitive bound
    assert net_lcb([1.96, -1.54] * 30) / 30 > net_lcb(coin) / 6
    assert t90(1) == 3.078 and t90(4) == 1.533 and t90(500) == bs.Z80
    assert t90(0) == float("inf")

    # GAMETE SELECTION: the noise genotype the champion gate rejects must not
    # BREED either, and an unmeasurable genotype is not a gamete however fit.
    sc = [{"genotype": {"A": 1}, "net": 9.0, "h1": 0.01, "h2": 8.99,
           "closes": 40, "lcb": 8.0, "both_halves_pos": False},   # one-half win
          {"genotype": {"A": 3}, "net": 8.0, "h1": 4.0, "h2": 4.0,
           "closes": 3, "lcb": 7.0, "both_halves_pos": True},     # 3 trades
          {"genotype": {"A": 2}, "net": 5.0, "h1": 2.5, "h2": 2.5,
           "closes": 40, "lcb": 4.0, "both_halves_pos": True}]    # robust
    el = select_elite(sc, 4, 12)
    assert [e["genotype"] for e in el] == [{"A": 2}], el
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

    print("strategy_incubator selftest OK (seed, dedupe, crossover+mutation "
          "on-grid, lever mapping/clamp, judge-gated funding proposals, "
          "proprioception hurting-gene skip, IMB-10 marked/reachable-holds, "
          "t-LCB winner's-curse ranking, gamete selection, anti-overfit "
          "champion gate incl. the closes floor)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
