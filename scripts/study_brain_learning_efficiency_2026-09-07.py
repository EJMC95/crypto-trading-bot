#!/usr/bin/env python3
"""STUDY (read-only, moves nothing): how efficiently does the BRAIN learn?

[2026-09-07 (ze)] Eamon: *"The brain needs to be smarter... I want our
intelligence to be elite."* This is the measurement that came back, and the
answer was not the one the question implies: the brain's STATISTICS are sound
and its bars are calibrated — what it is short of is EVIDENCE PER BUCKET, and
every conditional axis anyone could point it at is empty at today's sample.

FOUR ARMS, each answering one question the fleet could not previously answer:

  --funnel        Of every era bucket on a living book, which gate BINDS?
                  (I18: diagnose a stall by naming the gate that binds, not
                  the ones with room.) Measured 7-Sep: 37 buckets, 23
                  positive, 12 of those 23 blocked by the raw n>=30 floor,
                  6 by t<2.0, 1 by WIN RATE alone.

  --naive-null    The brain's OWN `analyse_bot` pair/session rules, run
                  against a PERMUTATION NULL that shuffles the pair and
                  open-hour labels WITHIN each book — preserving n per cell,
                  the book's win rate and its P&L, destroying only the
                  cell<->outcome association. Measured 7-Sep: `pair_earner`
                  REAL 22 vs null mean 25.8, P(null>=real)=0.905. Chance
                  produces MORE "consistent earners" than the tape does.

  --conditional   The same axes under a REFEREE the naive rules lack: judged
                  against the book's own mean (I25), cluster-robust on
                  distinct UTC open-days ((uf)), Benjamini-Hochberg at FDR
                  0.05 across every test ((qd)/I21). Categorical axes AND the
                  continuous per-trade covariates the books already stamp and
                  the brain has never read. Measured 7-Sep: 0 of 106
                  categorical and 0 of 20 continuous survive.

  --selfgrade     `brain_stats.selfgrade_mult` on the live ledger: does the
                  brain's own multiplier earn? Measured 7-Sep: 891 stamped
                  closes, 4 buckets graded, all NEUTRAL.

WHY THE AXIS FILTER IS AN ALLOW-LIST AND NOT A DENY-LIST — this cost two
wrong answers while the study was being written, both in the reassuring
direction, and both are I7:
  * the first cut graded `exit_reason` and hold-duration and found 68
    "effects"; 35 were take-profit buckets, which win BY CONSTRUCTION;
  * the second cut deny-listed four outcome names and still admitted
    `price_pnl` (a COMPONENT of the P&L), `peak_ret`, `mae_ret` and
    `accrued`, all reading rho > 0.84.
A deny-list must anticipate every field a new book invents. A covariate is
admissible here iff its value is DETERMINED AT THE OPEN, so the admissible
set is named (ENTRY_KNOWN) and everything else is refused and COUNTED.

OWNERS ARE IMPORTED, NEVER COPIED ((hj): a second copy of a rule is a second
rule): `bot_pnl_store.normalize_paper_row` (the ledger->brain normalisation,
the (yi) single owner), `bot_learn._epoch` / `era_epoch_for` / `RETIRED_BOTS`
/ `LIVENESS_DAYS` / `analyse_bot` / the n floors, `brain_stats.*` (the
evidence layer, the verdict and the self-grade), `golive_readiness.
is_phantom_close`.

CALIBRATION GATE ((gx): a harness that cannot reproduce what DID happen may
not say what WOULD have): every multiplier the live brain currently publishes
must reproduce here — mult exact, n exact, t within 0.02 — or the study
REFUSES (exit 2) and prints nothing. Fail-CLOSED on a dark or stale bus.

    python3 scripts/study_brain_learning_efficiency_2026-09-07.py --all
    python3 scripts/study_brain_learning_efficiency_2026-09-07.py --funnel \
        --ledger trades.json --bus bus.json
"""
import argparse
import collections
import json
import math
import os
import random
import statistics
import sys
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bot_pnl_store as store          # noqa: E402
import bot_learn as bl                 # noqa: E402
import brain_stats as bs               # noqa: E402

DEFAULT_FEED = ("https://pnl-dashboard-production-858c.up.railway.app"
                "/trades.json?source=paper&limit=5000")
DEFAULT_BUS = "https://pnl-dashboard-production-858c.up.railway.app/bus.json"

# A covariate is admissible iff its value is DETERMINED AT THE OPEN. See the
# module docstring: this is an ALLOW-LIST on purpose.
ENTRY_KNOWN = {
    "rsi_entry", "entry_rank", "spread_bps_entry", "dev_at_entry_bps",
    "apr_pct", "chg_pct", "gap_pct", "prem_bps", "range_pos", "vol_m",
    "notional", "brain_mult", "ghost_entry", "oi_m", "funding_apr", "age_d",
    "stress_bps", "clip_usd", "equity_at_entry", "entry_apr",
    "entry_prem_bps", "atr_frac", "sl_frac", "brk_quality", "p_win",
    "alloc_scale", "mmf_factor", "clip",
}
MIN_N_CELL = 10          # closes in a cell before it is tested
MIN_N_FEAT = 25          # closes carrying a covariate before it is tested
MIN_DAYS = 5             # distinct UTC open-days: the cluster count IS n
FDR_Q = 0.05
DRAWS = 200


# --------------------------------------------------------------------------
# statistics (pure)
# --------------------------------------------------------------------------
def norm_p_two(t):
    """Two-sided tail of the standard normal."""
    return math.erfc(abs(t) / math.sqrt(2.0))


def bh_survivors(pvals, q=FDR_Q):
    """Indices surviving Benjamini-Hochberg at FDR q."""
    if not pvals:
        return set()
    order = sorted(range(len(pvals)), key=lambda i: pvals[i])
    m, kmax = len(pvals), -1
    for rank, i in enumerate(order, start=1):
        if pvals[i] <= q * rank / m:
            kmax = rank
    return set(order[:kmax]) if kmax > 0 else set()


def welch(a, b):
    """(t, delta) for mean(a) - mean(b); None when it cannot be formed."""
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = statistics.mean(a), statistics.mean(b)
    se = math.sqrt(statistics.variance(a) / len(a)
                   + statistics.variance(b) / len(b))
    if se <= 1e-12:
        return None
    return (ma - mb) / se, ma - mb


def spearman(xs, ys):
    def rank(v):
        s = sorted(range(len(v)), key=lambda i: v[i])
        out, i = [0.0] * len(v), 0
        while i < len(s):
            j = i
            while j + 1 < len(s) and v[s[j + 1]] == v[s[i]]:
                j += 1
            for k in range(i, j + 1):
                out[s[k]] = (i + j) / 2.0 + 1
            i = j + 1
        return out
    a, b = rank(xs), rank(ys)
    ma, mb = statistics.mean(a), statistics.mean(b)
    num = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    den = math.sqrt(sum((x - ma) ** 2 for x in a)
                    * sum((y - mb) ** 2 for y in b))
    return num / den if den > 1e-12 else 0.0


def day_of(t):
    ts = str(t.get("open_ts") or "")
    return ts[:10] if len(ts) >= 10 else None


def cluster_means(rows):
    """Mean per-trade % within each distinct UTC open-day."""
    g = collections.defaultdict(list)
    for r in rows:
        d, pr = day_of(r), r.get("profit_ratio")
        if d and pr is not None:
            g[d].append(float(pr) * 100.0)
    return [statistics.mean(v) for v in g.values()]


# --------------------------------------------------------------------------
# ingest — through the owners
# --------------------------------------------------------------------------
def _read(src):
    if os.path.exists(src):
        return json.load(open(src))
    with urllib.request.urlopen(src, timeout=60) as r:
        return json.loads(r.read().decode())


def load(feed):
    d = _read(feed)
    raw = d if isinstance(d, list) else d.get("trades", d.get("data", []))
    rows, withheld = [], 0
    for r in raw:
        n = store.normalize_paper_row(
            r.get("bot"), r.get("pair"), r.get("pnl_abs"), r.get("pnl_pct"),
            r.get("opened_at"), r.get("closed_at"), r.get("reason"),
            r.get("extra"), (r.get("extra") or {}).get("venue"),
            r.get("entry_price"), r.get("exit_price"), r.get("tag"))
        if n is None:
            withheld += 1
            continue
        n["_close_epoch"] = bl._epoch(r.get("closed_at"))
        rows.append(n)
    return rows, withheld, len(raw)


def living(rows, days=None):
    """The brain's OWN liveness rule: not officially retired AND a close
    inside LIVENESS_DAYS. Never re-derived — RETIRED_BOTS is imported."""
    days = bl.LIVENESS_DAYS if days is None else days
    last, now = {}, 0.0
    for r in rows:
        e = r.get("_close_epoch")
        if not e:
            continue
        now = max(now, e)
        if last.get(r["bot"], 0) < e:
            last[r["bot"]] = e
    return {b for b, e in last.items()
            if b not in bl.RETIRED_BOTS and (now - e) / 86400.0 < days}


def era_scoped(rows, live):
    """{bot: [close]} inside each book's POLICY_ERA, keyed on the OPEN — the
    gate's own convention (a trade's policy is fixed when it is taken)."""
    out = collections.defaultdict(list)
    for r in rows:
        if r["bot"] not in live:
            continue
        e0 = bl.era_epoch_for(r["bot"])
        ot = bl._epoch(r.get("open_ts")) or r.get("_close_epoch")
        if e0 and ot and ot < e0:
            continue
        out[r["bot"]].append(r)
    return out


def bucket_stats(era, now_ts):
    """{(bot, tag): weighted_bucket_episodes} — the brain's own evidence."""
    w = {}
    for bot, trs in era.items():
        by_tag = collections.defaultdict(list)
        for t in trs:
            tag = str(t.get("enter_tag") or "(untagged)")
            if tag != "(untagged)":
                by_tag[tag].append(t)
        for tag, bucket in by_tag.items():
            w[(bot, tag)] = bs.weighted_bucket_episodes(
                bucket, now_ts, bs.HALF_LIFE_DAYS, bl.EP_GAP_SEC)
    return w


def verdicts(wstats):
    """[(bot, tag, stats, ev, mult)] via the brain's OWN qualify_v3."""
    tag_pool, bot_pool = collections.defaultdict(list), collections.defaultdict(list)
    for (b, t), st in wstats.items():
        tag_pool[t].append((b, st))
        bot_pool[b].append((t, st))
    allb = list(wstats.values())
    out = []
    for (bot, tag), st in wstats.items():
        prior = bs.eb_prior([s for bb, s in tag_pool[tag] if bb != bot],
                            [s for tt, s in bot_pool[bot] if tt != tag],
                            [s for s in allb if s is not st])
        mult, ev = bs.qualify_v3(st, prior, min_n=bl.MULT_MIN_N,
                                 soft_n=bl.MULT_SOFT_N, expand=bl.MULT_EXPAND)
        out.append((bot, tag, st, ev, mult))
    return out


# --------------------------------------------------------------------------
# CALIBRATION GATE — fail-CLOSED
# --------------------------------------------------------------------------
def calibrate(rows_v, bus):
    live_mults = ((bus or {}).get("brain_stake_mults") or {}).get("mults") or {}
    if not live_mults:
        print("REFUSED: the live brain publishes no multipliers on this bus "
              "(dark or stale feed) — a harness that cannot reproduce what DID "
              "happen may not say what WOULD have.")
        return False
    here = {(b, t): (m, st, ev) for b, t, st, ev, m in rows_v}
    ok = True
    print("== CALIBRATION against the live brain ==")
    for bot, tags in sorted(live_mults.items()):
        for tag, e in sorted(tags.items()):
            got = here.get((bot, tag))
            if not got:
                print(f"  MISS {bot} {tag}: bucket absent here"); ok = False; continue
            m, st, ev = got
            good = (m == e.get("mult") and st["n"] == e.get("n")
                    and abs((ev["t"] or 0) - (e.get("t") or 0)) <= 0.02)
            print(f"  {'OK ' if good else 'BAD'} {bot:30s} {tag:22s} "
                  f"mult live {e.get('mult')} here {m} | n live {e.get('n')} "
                  f"here {st['n']} | t live {e.get('t')} here {ev['t']}")
            ok = ok and good
    return ok


# --------------------------------------------------------------------------
# ARM 1 — the funnel
# --------------------------------------------------------------------------
def arm_funnel(rows_v):
    print("\n== ARM 1: THE FUNNEL — which gate binds on every living bucket? ==")
    pos = [r for r in rows_v if r[3]["pnl_w"] > 0]
    n30 = [r for r in pos if r[2]["n"] >= bl.MULT_MIN_N]
    neff = [r for r in n30 if r[3]["n_eff"] >= bs.MIN_N_EFF_HARD]
    tok = [r for r in neff if r[3]["t"] >= bs.EXP_SOFT_T]
    pub = [r for r in pos if r[4] is not None]
    print(f"  era buckets on living books               : {len(rows_v)}")
    print(f"    positive (expand candidates)            : {len(pos)}")
    print(f"    ...reaching the raw n>={bl.MULT_MIN_N} floor          : {len(n30)}"
          f"   [-{len(pos)-len(n30)} blocked by SAMPLE]")
    print(f"    ...and n_eff>={bs.MIN_N_EFF_HARD}                      : {len(neff)}"
          f"   [-{len(n30)-len(neff)}]")
    print(f"    ...and t>={bs.EXP_SOFT_T} (expectancy)             : {len(tok)}"
          f"   [-{len(neff)-len(tok)} blocked by EXPECTANCY]")
    print(f"    ...and BOTH win-rate bars               : {len(pub)}"
          f"   [-{len(tok)-len(pub)} blocked by WIN RATE alone]")
    held = [r for r in tok if r[4] is None]
    if held:
        print("\n  I15 WATCH — t>=2.0 and positive, held at 1.0x by win rate alone:")
        for bot, tag, st, ev, _m in held:
            print(f"    {bot}|{tag}  n={st['n']} t={ev['t']} "
                  f"post_wr={ev['post_wr']} w_lo={ev['w_lo']} "
                  f"exp_pct={None if st['exp_pct'] is None else round(st['exp_pct'],3)}")
        print("    -> (wu) pre-registered the response: RE-RUN "
              "scripts/study_brain_floors_2026-09-02.py, NEVER move a bar.")
    return {"buckets": len(rows_v), "positive": len(pos), "n30": len(n30),
            "t_ok": len(tok), "published": len(pub), "i15_held": len(held)}


# --------------------------------------------------------------------------
# ARM 2 — the brain's own naive rules against a permutation null
# --------------------------------------------------------------------------
NAIVE_KINDS = ("pair_earner", "pair_bleeder",
               "session_hot_zone", "session_dead_zone")


def _naive_counts(by_bot):
    c = collections.Counter()
    for bot, tr in by_bot.items():
        _card, hyps = bl.analyse_bot(bot, tr, None)
        for h in hyps:
            if h["kind"] in NAIVE_KINDS:
                c[h["kind"]] += 1
    return c


def arm_naive_null(rows, live, draws=DRAWS, seed=20260907):
    print("\n== ARM 2: the brain's OWN pair/session rules vs a permutation null ==")
    by_bot = collections.defaultdict(list)
    for r in rows:
        if r["bot"] in live:
            by_bot[r["bot"]].append(r)
    real = _naive_counts(by_bot)
    rng = random.Random(seed)
    draws_by = collections.defaultdict(list)
    for _ in range(draws):
        sh = {}
        for bot, tr in by_bot.items():
            pairs = [t["pair"] for t in tr]
            ots = [t["open_ts"] for t in tr]
            rng.shuffle(pairs)
            rng.shuffle(ots)
            sh[bot] = [dict(t, pair=p, open_ts=o)
                       for t, p, o in zip(tr, pairs, ots)]
        c = _naive_counts(sh)
        for k in NAIVE_KINDS:
            draws_by[k].append(c.get(k, 0))
    print(f"  {draws} draws; pair and open-hour labels shuffled WITHIN each book,")
    print("  so n per cell, the book's win rate and its P&L are preserved.")
    print(f"  {'rule':20s} {'REAL':>5s} {'null mean':>10s} {'null p90':>9s} "
          f"{'null max':>9s} {'P(null>=real)':>14s}")
    out = {}
    for k in NAIVE_KINDS:
        v = sorted(draws_by[k])
        r = real.get(k, 0)
        p = sum(1 for x in v if x >= r) / len(v)
        out[k] = {"real": r, "null_mean": statistics.mean(v), "p": p}
        print(f"  {k:20s} {r:5d} {statistics.mean(v):10.1f} "
              f"{v[int(0.9*len(v))]:9d} {max(v):9d} {p:14.3f}")
    return out


# --------------------------------------------------------------------------
# ARM 3 — the referee the naive rules lack
# --------------------------------------------------------------------------
def a_pair(t):
    return t.get("pair")


def a_hour6(t):
    ts = str(t.get("open_ts") or "")
    return "h%02d" % (int(ts[11:13]) // 6 * 6) if len(ts) >= 13 else None


def a_side(t):
    s = str(t.get("enter_tag") or "").split("-")[0]
    return s if s in ("long", "short") else None


CAT_AXES = {"pair": a_pair, "hour6": a_hour6, "side": a_side}


def referee_categorical(rows, live, q=FDR_Q):
    by_bot = collections.defaultdict(list)
    for r in rows:
        if r["bot"] in live:
            by_bot[r["bot"]].append(r)
    tests = []
    for bot, tr in by_bot.items():
        if len(tr) < 3 * MIN_N_CELL:
            continue
        for axis, fn in CAT_AXES.items():
            cells = collections.defaultdict(list)
            for t in tr:
                k = fn(t)
                if k is not None:
                    cells[str(k)].append(t)
            if len(cells) < 2:
                continue
            for cell, ct in cells.items():
                rest = [t for t in tr
                        if fn(t) is not None and str(fn(t)) != cell]
                if len(ct) < MIN_N_CELL or len(rest) < MIN_N_CELL:
                    continue
                A, B = cluster_means(ct), cluster_means(rest)
                if len(A) < MIN_DAYS or len(B) < MIN_DAYS:
                    continue
                got = welch(A, B)
                if not got:
                    continue
                tt, delta = got
                tests.append({"axis": axis, "bot": bot, "cell": cell,
                              "n": len(ct), "days": len(A), "t": tt,
                              "delta_pp": delta, "p": norm_p_two(tt)})
    surv = bh_survivors([x["p"] for x in tests], q)
    for i, x in enumerate(tests):
        x["bh"] = i in surv
    return tests


def referee_continuous(rows, live, q=FDR_Q):
    by = collections.defaultdict(list)
    refused = collections.Counter()
    admitted = set()
    for r in rows:
        if r["bot"] not in live or r.get("profit_ratio") is None:
            continue
        f = {}
        for k, v in (r.get("extra") or {}).items():
            if not isinstance(v, (int, float)) or isinstance(v, bool):
                continue
            if k in ENTRY_KNOWN:
                f[k] = float(v)
                admitted.add(k)
            else:
                refused[k] += 1
        by[(r["bot"], r.get("enter_tag"))].append((r, f))
    tests = []
    for (bot, tag), rows_f in by.items():
        if len(rows_f) < MIN_N_FEAT:
            continue
        cnt = collections.Counter()
        for _r, f in rows_f:
            cnt.update(f.keys())
        for feat, c in cnt.items():
            if c < MIN_N_FEAT:
                continue
            sub = [(r, f) for r, f in rows_f if feat in f]
            xs = [f[feat] for _r, f in sub]
            if len(set(xs)) < 5:
                continue
            ys = [float(r["profit_ratio"]) * 100.0 for r, _f in sub]
            g = len({day_of(r) for r, _f in sub if day_of(r)})
            if g < MIN_DAYS:
                continue
            rho = spearman(xs, ys)
            tt = rho * math.sqrt(max(g - 2, 1) / max(1e-9, 1 - rho * rho))
            tests.append({"bot": bot, "tag": tag, "feat": feat, "n": len(sub),
                          "days": g, "rho": rho, "t": tt,
                          "p": norm_p_two(tt)})
    surv = bh_survivors([x["p"] for x in tests], q)
    for i, x in enumerate(tests):
        x["bh"] = i in surv
    return tests, admitted, refused


def arm_conditional(rows, live, draws=DRAWS, seed=20260907):
    print("\n== ARM 3: the REFEREE the naive rules lack "
          "(book's own mean, cluster-robust, BH-FDR 0.05) ==")
    cat = referee_categorical(rows, live)
    hits = [x for x in cat if x["bh"]]
    print(f"  CATEGORICAL entry-known axes {sorted(CAT_AXES)}:")
    print(f"    {len(cat)} tests over "
          f"{len({x['bot'] for x in cat})} living books -> {len(hits)} survive")
    for x in sorted(hits, key=lambda z: -abs(z["t"])):
        print(f"      {x['axis']:6s} {x['bot'][:30]:30s} {x['cell'][:14]:14s} "
              f"n={x['n']:4d} d={x['days']:3d} delta={x['delta_pp']:+7.3f}pp "
              f"t={x['t']:+6.2f}")
    con, admitted, refused = referee_continuous(rows, live)
    chits = [x for x in con if x["bh"]]
    print(f"  CONTINUOUS covariates the brain has never read:")
    print(f"    admitted as entry-known: {len(admitted)} "
          f"{sorted(admitted)}")
    print(f"    REFUSED as outcome/identity ({len(refused)}): "
          f"{sorted(refused)[:14]}{' ...' if len(refused) > 14 else ''}")
    print(f"    {len(con)} tests over "
          f"{len({(x['bot'], x['tag']) for x in con})} buckets -> "
          f"{len(chits)} survive")
    for x in sorted(con, key=lambda z: -abs(z["t"]))[:6]:
        print(f"      {'BH' if x['bh'] else '  '} {x['bot'][:26]:26s}"
              f"|{str(x['tag'])[:18]:18s} {x['feat']:17s} n={x['n']:4d} "
              f"d={x['days']:3d} rho={x['rho']:+.3f} t={x['t']:+6.2f}")
    rng = random.Random(seed)
    by_bot = collections.defaultdict(list)
    for r in rows:
        if r["bot"] in live:
            by_bot[r["bot"]].append(r)
    counts = []
    for _ in range(draws):
        sh = []
        for bot, tr in by_bot.items():
            pr = [t["profit_ratio"] for t in tr]
            rng.shuffle(pr)
            sh.extend(dict(t, profit_ratio=p) for t, p in zip(tr, pr))
        counts.append(sum(1 for x in referee_categorical(sh, live) if x["bh"]))
    counts.sort()
    p = sum(1 for c in counts if c >= len(hits)) / len(counts)
    print(f"  PERMUTATION NULL ({draws} draws, outcome shuffled within book): "
          f"mean {statistics.mean(counts):.2f} p90 {counts[int(0.9*len(counts))]} "
          f"max {max(counts)} P(null>=real) {p:.3f}")
    return {"cat_tests": len(cat), "cat_hits": len(hits),
            "con_tests": len(con), "con_hits": len(chits),
            "null_mean": statistics.mean(counts), "null_p": p}


# --------------------------------------------------------------------------
# ARM 4 — the brain's own multiplier
# --------------------------------------------------------------------------
def arm_selfgrade(era):
    print("\n== ARM 4: does the brain's OWN multiplier earn? "
          "(brain_stats.selfgrade_mult) ==")
    out = bs.selfgrade_mult(era)
    print(f"  coverage {json.dumps(out['coverage'])}")
    print(f"  pooled   {json.dumps(out['pooled'])}")
    for b in sorted(out["buckets"],
                    key=lambda z: (z["verdict"] == "undecidable",
                                   -abs(z["t"] or 0))):
        t = "  n/a" if b["t"] is None else f"{b['t']:+5.2f}"
        d = "    n/a  " if b["delta_pp"] is None else f"{b['delta_pp']:+7.3f}pp"
        print(f"    {b['bot'][:26]:26s}|{str(b['tag'])[:16]:16s} {b['dirn']:4s} "
              f"n={b['n_sized']:4d}/{b['n_flat']:<4d} d={b['days_sized']:3d}/"
              f"{b['days_flat']:<3d} t={t} delta={d}  {b['verdict']}"
              f"{'' if not b['why'] else ' (' + b['why'] + ')'}")
    return out["pooled"]


# --------------------------------------------------------------------------
def _selftest():
    # BH: under a uniform null nothing should survive; a single tiny p does.
    assert bh_survivors([0.9, 0.8, 0.7, 0.6]) == set()
    assert 0 in bh_survivors([1e-9, 0.8, 0.7, 0.6])
    # ...and BH is monotone in q: a looser FDR can only admit more.
    ps = [0.001, 0.02, 0.2, 0.5]
    assert bh_survivors(ps, 0.01) <= bh_survivors(ps, 0.5)
    assert bh_survivors([]) == set()

    # welch: identical arms give t=0; a clean separation gives a big |t|;
    # zero variance is None (not a divide-by-zero verdict).
    assert abs(welch([1, 2, 3], [1, 2, 3])[0]) < 1e-9
    assert welch([10, 11, 12], [0, 1, 2])[0] > 5
    assert welch([2, 2, 2], [2, 2, 2]) is None
    assert welch([1], [1, 2]) is None

    # spearman is rank-based: a monotone but non-linear map reads +1.
    assert abs(spearman([1, 2, 3, 4], [1, 4, 9, 16]) - 1.0) < 1e-9
    assert abs(spearman([1, 2, 3, 4], [16, 9, 4, 1]) + 1.0) < 1e-9

    # THE CLUSTER RULE ((uf)): five copies of one day carry one day's
    # information. cluster_means must collapse them; a raw pool must not be
    # what this study reports.
    rows = [{"open_ts": "2026-09-01T00:00:00+00:00", "profit_ratio": 0.01}] * 5
    rows += [{"open_ts": "2026-09-02T00:00:00+00:00", "profit_ratio": 0.03}] * 5
    assert cluster_means(rows) == [1.0, 3.0]
    assert day_of({"open_ts": "2026-09-01T00:00:00+00:00"}) == "2026-09-01"
    assert day_of({}) is None

    # THE ALLOW-LIST IS THE POINT: the four fields that fooled this study's
    # own first two cuts must be REFUSED, and they are all pure outcome.
    for outcome in ("price_pnl", "peak_ret", "mae_ret", "accrued",
                    "held_h", "give_back", "dev_at_exit_bps", "fees"):
        assert outcome not in ENTRY_KNOWN, outcome
    # ...while the covariates a book genuinely knows at the open are admitted.
    for known in ("rsi_entry", "entry_rank", "spread_bps_entry", "brain_mult"):
        assert known in ENTRY_KNOWN, known

    # the naive-rule kinds this study nulls must be kinds the brain ACTUALLY
    # emits — a null against a kind nobody publishes measures nothing.
    src = open(os.path.join(ROOT, "bot_learn.py")).read()
    for kind in NAIVE_KINDS:
        assert f'"{kind}"' in src, kind

    # owners are imported, not copied: the verdict comes from qualify_v3 and
    # the self-grade from brain_stats, so this file must not define either.
    # (matched at line start: the names appear in this very list, so a bare
    # substring check fails on its own assertion — (po), landing on the test
    # written to honour it)
    mine = open(os.path.abspath(__file__)).read()
    for owned in ("qualify_v3", "selfgrade_mult", "normalize_paper_row",
                  "weighted_bucket"):
        assert ("\ndef " + owned) not in mine, owned

    # MOVES NOTHING — call sites, checked the same line-anchored way.
    for forbidden in ("write_levers(", "save_state(", "market_open(",
                      "get_lever("):
        assert ("." + forbidden) not in mine, forbidden
    print("study_brain_learning_efficiency selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", default=DEFAULT_FEED)
    ap.add_argument("--bus", default=DEFAULT_BUS)
    ap.add_argument("--draws", type=int, default=DRAWS)
    ap.add_argument("--funnel", action="store_true")
    ap.add_argument("--naive-null", action="store_true")
    ap.add_argument("--conditional", action="store_true")
    ap.add_argument("--selfgrade", action="store_true")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        return 0
    if not any((a.funnel, a.naive_null, a.conditional, a.selfgrade)):
        a.all = True

    rows, withheld, n_raw = load(a.ledger)
    live = living(rows)
    now_ts = max((r.get("_close_epoch") or 0) for r in rows)
    era = era_scoped(rows, live)
    wst = bucket_stats(era, now_ts)
    rows_v = verdicts(wst)
    print(f"rows {n_raw} -> {len(rows)} admissible ({withheld} withheld by "
          f"is_quarantined) · living books {len(live)} · era buckets {len(wst)}")

    bus = None
    try:
        bus = _read(a.bus)
    except Exception:
        bus = None
    if not calibrate(rows_v, bus):
        print("\nREFUSED (exit 2): the harness does not reproduce the live "
              "brain, so it may not speak about it.")
        return 2

    if a.all or a.funnel:
        arm_funnel(rows_v)
    if a.all or a.naive_null:
        arm_naive_null(rows, live, a.draws)
    if a.all or a.conditional:
        arm_conditional(rows, live, a.draws)
    if a.all or a.selfgrade:
        arm_selfgrade(era)
    return 0


if __name__ == "__main__":
    sys.exit(main())
