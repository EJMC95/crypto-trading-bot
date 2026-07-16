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
#   tape spans >= MIN_TAPE_HOURS, each half clears HALF_MARGIN (not just >0),
#   it beats the DEFAULT genome by EDGE_MARGIN, AND it stays the champion for
#   PERSIST_CYCLES independent cycles. Until then the leaderboard is published
#   but explicitly flagged tentative (noise-risk) — trusted by nothing.
MIN_TAPE_HOURS = float(os.environ.get("INCUBATOR_MIN_TAPE_HOURS", "48"))
HALF_MARGIN = float(os.environ.get("INCUBATOR_HALF_MARGIN", "1.0"))      # $ each half
EDGE_MARGIN = float(os.environ.get("INCUBATOR_EDGE_MARGIN", "2.0"))      # $ vs default
PERSIST_CYCLES = int(os.environ.get("INCUBATOR_PERSIST", "3"))

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

    def _marked(rep):
        # [2026-07-17 IMB-10 parity] closed + end-of-tape unrealized — the
        # tuner's gates went deferral-proof; the bred leaderboard/champion
        # (dashboard-only today) must not keep the bias a future consumer
        # would inherit.
        return rep["closed_net"] + float(rep.get("unrealized") or 0.0)

    try:
        for g, v in genotype.items():
            setattr(tt, g, v)
        full = _marked(rp.replay(tape))
        mid = len(tape) // 2
        h1 = _marked(rp.replay(tape[:mid])) if mid else 0.0
        h2 = _marked(rp.replay(tape[mid:])) if mid else 0.0
    finally:
        for g, v in saved.items():
            setattr(tt, g, v)
    return {"net": round(full, 3), "h1": round(h1, 3), "h2": round(h2, 3),
            # both-halves POSITIVE-BY-MARGIN — a +$0.01 half is noise, not edge
            "both_halves_pos": h1 >= HALF_MARGIN and h2 >= HALF_MARGIN}


def rank(population, tape):
    scored = [{"genotype": gt, **evaluate(gt, tape)} for gt in population]
    # fittest = highest net, tie-broken toward both-halves-positive
    scored.sort(key=lambda s: (s["net"], s["both_halves_pos"]), reverse=True)
    return scored


def assess_champion(top, default_net, tape_hours, prior_champ, prior_streak):
    """Is the fittest genotype a TRUSTWORTHY champion, or noise? Returns
    (is_champion, streak, stable, confidence, reason). Pure — selftested.
    This is the anti-overfit gate: short tape, a weak half, or a thin edge
    over the default genome all read 'tentative' no matter how high the net."""
    if not top:
        return False, 0, False, "none", "no population"
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
    if len(tape) >= MIN_SNAPS:
        prior_elite = [e["genotype"] for e in (prior.get("elite") or [])]
        population = dedupe(seed_population(TAKER_GENES)
                            + breed(prior_elite, TAKER_GENES))
        scored = rank(population, tape)
        leaderboard = scored[:ELITE_N]
        default_gt = {g: getattr(tt, g) for g in TAKER_GENES}
        default_net = next((s["net"] for s in scored
                            if s["genotype"] == default_gt), 0.0)
        tape_hours = ((tape[-1][0] - tape[0][0]).total_seconds() / 3600.0
                      if len(tape) >= 2 else 0.0)
        top = leaderboard[0] if leaderboard else None
        is_champ, streak, stable, conf, why = assess_champion(
            top, default_net, tape_hours,
            (prior.get("champion") or {}).get("genotype"),
            (prior.get("champion") or {}).get("streak"))
        if top:
            champion = {"genotype": top["genotype"], "net": top["net"],
                        "h1": top["h1"], "h2": top["h2"], "confidence": conf,
                        "streak": streak, "stable": stable,
                        "vs_default": round(top["net"] - default_net, 3)}
            print(f"[incubator] fittest net ${top['net']:+.2f} vs default "
                  f"${default_net:+.2f} (h1 ${top['h1']:+.2f} h2 ${top['h2']:+.2f}) "
                  f"| {conf.upper()}: {why}", flush=True)
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
    # 🦾 a gene whose LIVE lever is proprioception-graded HURTING is skipped
    # this cycle; other genes unaffected; empty/absent hurting skips nothing
    ph = funding_proposals({}, {}, hurting={"live.funding.enter_apr"})
    assert not any("enter_apr" in p["name"] for p in ph), ph
    assert any("take_profit" in p["name"] for p in ph), ph
    assert funding_proposals({}, {}, hurting=set()) == funding_proposals({}, {})
    assert funding_proposals({}, {}, hurting=None) == funding_proposals({}, {})
    # anti-overfit champion gate: the +$0.01-half case is REJECTED as noise
    noise = {"genotype": {"A": 2}, "net": 2.35, "h1": 0.01, "h2": 2.34}
    isc, _, _, conf, why = assess_champion(noise, 0.0, 200, None, 0)
    assert not isc and conf == "tentative" and "half" in why, (conf, why)
    # short tape -> tentative even with a strong, balanced result
    strong = {"genotype": {"A": 2}, "net": 8.0, "h1": 4.0, "h2": 4.0}
    isc2, _, _, conf2, why2 = assess_champion(strong, 0.0, 10, None, 0)
    assert not isc2 and "min" in why2, why2
    # thin edge over default -> tentative
    isc3, _, _, conf3, _ = assess_champion(strong, 7.0, 200, None, 0)
    assert not isc3 and conf3 == "tentative"
    # a genuine champion: long tape, both halves strong, beats default, and
    # persistence promotes candidate -> stable across cycles
    isc4, streak4, stable4, conf4, _ = assess_champion(strong, 0.0, 200, None, 0)
    assert isc4 and streak4 == 1 and not stable4 and conf4 == "candidate"
    isc5, streak5, stable5, conf5, _ = assess_champion(
        strong, 0.0, 200, {"A": 2}, 2)          # same champ, 3rd cycle
    assert isc5 and streak5 == 3 and stable5 and conf5 == "stable"
    # a DIFFERENT champion resets the streak (no free ride on prior stability)
    other = {"genotype": {"A": 3}, "net": 9.0, "h1": 4.5, "h2": 4.5}
    _, streak6, stable6, _, _ = assess_champion(other, 0.0, 200, {"A": 2}, 5)
    assert streak6 == 1 and not stable6

    print("strategy_incubator selftest OK (seed, dedupe, crossover+mutation "
          "on-grid, lever mapping/clamp, judge-gated funding proposals, "
          "proprioception hurting-gene skip, anti-overfit champion gate)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
