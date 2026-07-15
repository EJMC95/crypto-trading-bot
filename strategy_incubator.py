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
import os
import sys
import time
from datetime import datetime, timezone

import bot_pnl_store as store
import fleet_tuning as tuning
import lighter_ticket_taker as tt
import lighter_ticket_replay as rp

KEY = "strategy-incubator"
QUEUE_KEY = "xp-queue"
TTL_SEC = int(os.environ.get("INCUBATOR_TTL_SEC", "10800"))
ELITE_N = int(os.environ.get("INCUBATOR_ELITE_N", "4"))
MIN_SNAPS = int(os.environ.get("INCUBATOR_MIN_SNAPS", "60"))

# TAKER genes: (tt attr, lever, discrete allele grid within registry bounds).
# The grid is the search space; offspring are points on it.
TAKER_GENES = {
    "BRK_RANGE": ("taker.brk_range", [0.90, 0.93, 0.95, 0.97]),
    "DIP_RANGE": ("taker.dip_range", [0.05, 0.08, 0.11, 0.15]),
    "MOMO_CHG": ("taker.momo_chg", [3.0, 4.0, 5.0, 6.0]),
    "TAKE_PROFIT": ("taker.tp", [0.03, 0.04, 0.05, 0.06]),
    "STOP_LOSS": ("taker.sl", [-0.04, -0.03, -0.02]),
    "MAX_HOLD_H": ("taker.max_hold_h", [24.0, 48.0, 72.0]),
}
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

def evaluate(genotype, tape):
    """Fitness of a TAKER genotype = replayed closed-net over the tape, with
    a both-halves-positive flag (an offspring that only wins one lucky half
    is not fit). Patches tt bars, always restores."""
    saved = {g: getattr(tt, g) for g in genotype}
    try:
        for g, v in genotype.items():
            setattr(tt, g, v)
        full = rp.replay(tape)["closed_net"]
        mid = len(tape) // 2
        h1 = rp.replay(tape[:mid])["closed_net"] if mid else 0.0
        h2 = rp.replay(tape[mid:])["closed_net"] if mid else 0.0
    finally:
        for g, v in saved.items():
            setattr(tt, g, v)
    return {"net": round(full, 3), "h1": round(h1, 3), "h2": round(h2, 3),
            "both_halves_pos": h1 > 0 and h2 > 0}


def rank(population, tape):
    scored = [{"genotype": gt, **evaluate(gt, tape)} for gt in population]
    # fittest = highest net, tie-broken toward both-halves-positive
    scored.sort(key=lambda s: (s["net"], s["both_halves_pos"]), reverse=True)
    return scored


# ---------------------------------------------------------------------------

def funding_proposals(judge_state, incubator_state):
    """Novel FUNDING genotypes not already run/queued — proposed for the
    experiment judge's paired bar. Diversity-ordered (single-gene changes
    first). Never pre-scored (no funding replay); the judge is the filter."""
    default = {g: tuning.get_lever(FUNDING_GENES[g][0],
                                   {"enter_apr": tt and 0.40}.get(g, None))
               for g in FUNDING_GENES}
    # env baseline for funding (the bot's own defaults)
    base = {"enter_apr": 0.40, "take_profit": 0.04, "max_hold_h": 72.0}
    tried = set()
    for v in (judge_state.get("verdicts") or []):
        nm = v.get("name")
        if nm:
            tried.add(nm)
    for p in (incubator_state.get("proposed") or []):
        tried.add(p.get("name"))
    props = []
    for g, (lever, grid) in FUNDING_GENES.items():
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
    leaderboard = []
    if len(tape) >= MIN_SNAPS:
        prior_elite = [e["genotype"] for e in (prior.get("elite") or [])]
        population = dedupe(seed_population(TAKER_GENES)
                            + breed(prior_elite, TAKER_GENES))
        scored = rank(population, tape)
        leaderboard = scored[:ELITE_N]
        top = leaderboard[0] if leaderboard else None
        if top:
            print(f"[incubator] fittest taker genotype net ${top['net']:+.2f} "
                  f"(h1 ${top['h1']:+.2f} h2 ${top['h2']:+.2f} "
                  f"both+={top['both_halves_pos']}) {top['genotype']}", flush=True)
    else:
        print(f"[incubator] tape too short ({len(tape)}/{MIN_SNAPS}) — "
              f"skipping taker breeding", flush=True)

    # --- FUNDING proposals (live-reachable, JUDGE-gated) -------------------
    judge_state = store.load_state("xp-judge") or {}
    props = funding_proposals(judge_state, prior)
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
        "elite": leaderboard,
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

    # funding proposals exclude already-tried names, cap, and map to xp levers
    js = {"verdicts": [{"name": "xp-enter_apr-0.3"}]}
    props = funding_proposals(js, {})
    names = {p["name"] for p in props}
    assert "xp-enter_apr-0.3" not in names, "already-tried excluded"
    assert all(list(p["levers"])[0].startswith("xp.funding.") for p in props)
    for p in props:                                     # every allele is in-registry
        (lever, val), = p["levers"].items()
        assert tuning.clamp(lever, val) == val, p
    print("strategy_incubator selftest OK (seed, dedupe, crossover+mutation "
          "on-grid, lever mapping/clamp, judge-gated funding proposals)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
