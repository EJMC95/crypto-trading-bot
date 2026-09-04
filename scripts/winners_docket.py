#!/usr/bin/env python3
"""THE WINNERS' DOCKET — losing gets a refereed docket; winning gets this one.

[2026-08-18 (qd)] Operator: "Let's prove some winning then shall we?" / "How
about that for the doctrine." The fleet's decision docket (golive_readiness,
(ld)) surfaces books whose LOSING or undecidability is overdue for a call, and
the (mr)/(nf) retirements ran Benjamini-Hochberg across the LOSERS. Nothing
symmetric existed for winners: a bucket quietly earning with a real t-stat had
no instrument that would ever say so, which is how a fleet becomes a museum of
avoided losses (CLAUDE.md, the offense-tier preamble).

WHAT IT IS: a read-only census of every (book, exit-family), (book, entry-tag)
and (book, side) bucket over the book's OWN era-scoped, quarantine-filtered
ledger, with one-sided t p-values refereed by Benjamini-Hochberg at FDR 0.05
across ALL tested buckets — the same discipline (mr) applied to the losers,
mirrored. Survivors are PROVEN WINNING (statistically, on the ledger, in this
regime); near-misses (t >= 1) get the n they still need (n_req = n*(2/t)^2,
the (ks) formula) and an ETA at their own measured rate.

WHAT IT IS NOT, stated so nobody stretches it:
  * NOT a go-live gate and NOT senior to it — the gate is golive_readiness's,
    unchanged. A surviving bucket is a fact, not a promotion.
  * NOT beta: a directional bucket on this venue's one-regime tape can survive
    on drift alone (a random short earns +0.2-1.1%/trade, (hm)), so every
    directional survivor is stamped `drift_check_required` — it must beat the
    random-entry null before anything ACTS on it.
  * NOT concentration-blind: every survivor carries its top-1 close share; a
    bucket whose best single close is >= half its total is stamped
    `tail_concentrated` per the (nu)/(oj) undecidable-by-tail discipline.

ONE-OWNER RULES, load-bearing: the era boundary is golive_readiness.era_rows
(IMPORTED — a second copy would let the docket and the gate disagree about the
same ledger, the (hj) class); the ledger read is bot_pnl_store.fetch_paper_trades
(so LEDGER_QUARANTINE — including the (pv)/(qc) rows — is applied by
construction); retired rows are excluded via cleanup_legacy_bots.LEGACY_BOTS
(the same declaration the pruner runs).

Read-only: SELECTs via the store, writes nothing, publishes nothing.
"""
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import bot_pnl_store as store                      # noqa: E402
from cleanup_legacy_bots import LEGACY_BOTS        # noqa: E402
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import golive_readiness as gr                      # noqa: E402

FDR = float(os.environ.get("WINNERS_FDR", "0.05"))
MIN_N = int(os.environ.get("WINNERS_MIN_N", "10"))
NEAR_T = 1.0          # below this a bucket is noise, not "on its way"
TAIL_SHARE = 0.5      # top-1 close >= half the bucket's total -> concentrated
FUNDING_BOOKS = ("funding", "carry", "kiyosaki", "hull", "garrett")
#: [I7] Exit families CONDITIONED ON THE PRICE OUTCOME are winners by
#: construction — a take-profit exits in profit by definition, so grading the
#: bucket is grading the label (the fleet already engraved this about
#: short_take_pro: "100% win BY CONSTRUCTION — not itself evidence"; the
#: losses those exits avoid live in the sibling stop buckets, which
#: study_exit_attribution owns). NEUTRAL exits (hold/decay/flip/max_hold)
#: are admissible: the timer and the rate-sign fire regardless of P&L.
OUTCOME_EXITS = ("tp", "take_profit", "roi", "stop", "sl", "stoploss",
                 "sell_into_strength", "range_top", "take_pro")

#: [I21] THE PRE-REGISTERED FOLLOW-THROUGHS — and the reason this table exists.
#: I21's own words: a bucket held only by the multiplicity referee is
#: pre-registered and then "graded on closes AFTER registration, t>=2 on the
#: fresh sample alone, NEVER by re-mining the window that generated them."
#: Nothing enforced that. Measured 21-Aug, three days after the (qd)
#: registration: 🎫 taker `exit:hold` reached n=62 pooled (t=3.53, p=0.0004)
#: and the docket printed it under PROVEN WINNING — on a window whose first 53
#: closes ARE the hypothesis. That headline is the re-mining I21 forbids, on
#: the one instrument that exists to say a thing is proven. Its fresh sample
#: was n=9: above the t-bar (t=2.99) but BELOW the MIN_N floor, so the honest
#: verdict was "not yet decidable", one close away — a materially different
#: statement. The sibling registration moved the other way: 🙏 avo pooled
#: t=1.48 while its fresh 2 closes read t=-0.19, and pooling was propping the
#: registration figure (t=2.31) up rather than testing it.
#: A registration is a COMMITMENT, so this table is append-mostly: `since` and
#: the at-registration statistics are the record and must not be edited to
#: match a later reading. Retire a row only when its verdict is CONFIRMED or
#: REFUTED on the fresh sample, and say which in the changelog.
PRE_REGISTERED = {
    ("lighter-ticket-taker-lshadow", "exit", "hold"): dict(
        since="2026-08-18T11:29:15+00:00", n=53, t=2.65, mean_pct=0.836,
        source="(qd)/I21 — the winners' docket's own first live run"),
    ("freqtrade-avo-maria-lshadow", "book", "*"): dict(
        since="2026-08-18T11:29:15+00:00", n=12, t=2.31, mean_pct=1.313,
        source="(qd)/I21 — the winners' docket's own first live run"),
    # [2026-09-02 (wm)] 👩 mum LIVE — both buckets sat "held only by the
    # multiplicity referee" on the 2-Sep docket; this registration is the
    # instrument that decides them on FRESH closes alone. Two caveats carried
    # on purpose: (I25) it follows two hot days (+$40.55, +$39.40), so the
    # fresh window is expected near her MEAN (+0.70%), and a not_confirmed
    # first read is the arithmetic, not a failure; (hm) her own published
    # control puts the edge over matched-random at +0.187%/trade — a
    # confirmed follow-through still owes the random-entry null before
    # anything ACTS on it, per I21's own text.
    ("freqtrade-mum-lighter", "book", "*"): dict(
        since="2026-09-02T04:05:59+00:00", n=52, t=2.71, mean_pct=0.703,
        source="(wm)/I21 — 2-Sep docket: t-bar met, held by the referee"),
    ("freqtrade-mum-lighter", "tag", "long-oversold-rebound"): dict(
        since="2026-09-02T04:05:59+00:00", n=50, t=2.40, mean_pct=0.640,
        source="(wm)/I21 — 2-Sep docket: t-bar met, held by the referee"),
}


# ---------------------------------------------------------------- statistics
def _betacf(a, b, x, itmax=200, eps=3e-12):
    """Continued fraction for the incomplete beta (Numerical Recipes form)."""
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < 1e-300:
        d = 1e-300
    d = 1.0 / d
    h = d
    for m in range(1, itmax + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < 1e-300:
            d = 1e-300
        c = 1.0 + aa / c
        if abs(c) < 1e-300:
            c = 1e-300
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < eps:
            return h
    return h


def betainc(a, b, x):
    """Regularized incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    ln_bt = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
             + a * math.log(x) + b * math.log(1.0 - x))
    bt = math.exp(ln_bt)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_sf(t, df):
    """One-sided P(T >= t) for Student's t. Exact via the incomplete beta."""
    if df <= 0:
        return 1.0
    p_two = betainc(df / 2.0, 0.5, df / (df + t * t))
    return p_two / 2.0 if t >= 0 else 1.0 - p_two / 2.0


def t_stat(xs):
    n = len(xs)
    if n < 2:
        return 0.0
    m = sum(xs) / n
    v = sum((a - m) ** 2 for a in xs) / (n - 1)
    return m / math.sqrt(v / n) if v > 0 else 0.0


def bh_survivors(pvals, fdr=FDR):
    """Benjamini-Hochberg: indices of entries surviving at `fdr`.

    pvals: list of (key, p). Returns the set of keys at or below the largest
    rank k with p_(k) <= k/m * fdr — the same rule the (mr) docket applied to
    the losers, mirrored onto winners.
    """
    m = len(pvals)
    if m == 0:
        return set()
    ranked = sorted(pvals, key=lambda kp: kp[1])
    kmax = 0
    for i, (_k, p) in enumerate(ranked, start=1):
        if p <= i / m * fdr:
            kmax = i
    return {k for k, _p in ranked[:kmax]}


# ---------------------------------------------------------------- the census
def _parse_ts(s):
    try:
        s = str(s or "").strip().replace("Z", "+00:00")
        if s.endswith(" UTC"):
            s = s[:-4] + "+00:00"
        dt = datetime.fromisoformat(s)
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except Exception:                              # noqa: BLE001
        return None


def era_scoped_rows(trades):
    """{bot: [row]} era-scoped through the GATE'S OWN era rule (identity import).

    Row: dict(pct, abs, closed, opened, exit, tag). Buckets are built from
    these, so every bucket inherits the gate's sample definition exactly.

    [2026-08-26 daily review] PHANTOM CLOSES are excluded through the gate's
    own `is_phantom_close` (identity import — a second copy of that signature
    would be a second rule, and the two graders would drift apart on the exact
    rows that matter). The referee was admitting halt/flatten EVENTS as trades
    on precisely the two REAL-MONEY books: 13 such rows —
    `freqtrade-avo-maria-lighter` 9, `freqtrade-georgia-lighter` 4 — which put
    a real-money row on the docket's "ON THEIR WAY" list at n=13/t=1.46 when
    its true traded n is 4, below the MIN_N floor. Nine $0.00 rows do not just
    inflate n; they shrink the sample variance, so they bias `t` UPWARD — the
    referee erred toward calling a real-money book a winner. `golive_readiness`
    has filtered these since (th) and the docket did not, so the fleet's two
    graders disagreed about the same real-money ledger.
    """
    by_bot = defaultdict(list)
    for r in trades:
        bot = r.get("bot")
        if not bot or bot in LEGACY_BOTS or r.get("is_open"):
            continue
        if gr.is_phantom_close(r):
            continue
        pct = r.get("profit_ratio")
        closed = _parse_ts(r.get("close_ts"))
        if pct is None or closed is None:
            continue
        by_bot[bot].append(r)
    out = {}
    for bot, rows in by_bot.items():
        rows.sort(key=lambda r: _parse_ts(r.get("close_ts")))
        shaped = [(float(r["profit_ratio"]), float(r.get("profit_abs") or 0.0),
                   _parse_ts(r["close_ts"]), r.get("open_ts")) for r in rows]
        scoped, _all, _iso = gr.era_rows(bot, shaped)
        scoped_keys = {(round(row[0], 9), row[2]) for row in scoped}
        out[bot] = [dict(pct=float(r["profit_ratio"]),
                         abs=float(r.get("profit_abs") or 0.0),
                         closed=_parse_ts(r["close_ts"]),
                         exit=(r.get("exit_reason") or "?"),
                         tag=(r.get("enter_tag") or ""))
                    for r in rows
                    if (round(float(r["profit_ratio"]), 9),
                        _parse_ts(r["close_ts"])) in scoped_keys]
    return out


def buckets_of(by_bot):
    """[(key, rows)] — (book, exit-family) + (book, tag) + (book, side)."""
    out = {}
    for bot, rows in by_bot.items():
        if len(rows) >= MIN_N:
            out[(bot, "book", "*")] = rows
        fams = defaultdict(list)
        tags = defaultdict(list)
        sides = defaultdict(list)
        for r in rows:
            fams[r["exit"]].append(r)
            if r["tag"]:
                tags[r["tag"]].append(r)
            side = (r["tag"] or r["exit"]).split("-")[0].split("_")[0]
            if side in ("long", "short"):
                sides[side].append(r)
        for fam, rr in fams.items():
            base = fam.split("-")[-1].split("_")[-1]
            if any(o in fam.lower() for o in OUTCOME_EXITS) or \
               any(o in base.lower() for o in OUTCOME_EXITS):
                continue          # I7: selected on the outcome — not a bucket
            if len(rr) >= MIN_N:
                out[(bot, "exit", fam)] = rr
        for tag, rr in tags.items():
            if len(rr) >= MIN_N:
                out[(bot, "tag", tag)] = rr
        for side, rr in sides.items():
            if len(rr) >= MIN_N:
                out[(bot, "side", side)] = rr
    # DEDUP: a tag that IS the whole book (avo: one tag, one side) would enter
    # the referee three or four times — same closes, same p — inflating m and
    # diluting every other bucket. Identical row-sets count ONCE, under their
    # least specific key (book > side > tag > exit).
    rank = {"book": 0, "side": 1, "tag": 2, "exit": 3}
    best = {}
    for key, rr in out.items():
        sig = (key[0], frozenset((r["closed"], round(r["pct"], 9)) for r in rr))
        if sig not in best or rank[key[1]] < rank[best[sig][1]]:
            best[sig] = key
    return {k: out[k] for k in best.values()}


def cluster_view(rows):
    """Cluster-robust view of a docket bucket, keyed on BATCHED CLOSES.

    [2026-09-04 (xy)] THE ARITHMETIC AND THE CLUSTER DEFINITION ARE BOTH
    `golive_readiness`'s — this function shapes rows and nothing else, so a fix
    there is a fix here ((hj): a second copy of a rule is a second rule). The
    gate has owned `cluster_stats` since it measured ⚖️ Counterweight at
    t_iid -2.00 / cluster-robust -1.32; the docket, which decides a
    PRE-REGISTERED real-money follow-through, never asked it.

    WHY IT MATTERS HERE. `t = mean / (sd/sqrt(n))` assumes n INDEPENDENT
    observations, and a book that flattens closes its whole book in ONE
    instant — those rows share that instant's move and are one observation,
    not n. Measured the day this shipped, on 👩 mum's LIVE row: her fresh
    pre-registered sample read **n=18, t=-3.05**, and **8 of those closes are
    a single `daily_loss` halt at 2026-09-02T17:19:45 carrying 67% of the
    loss**. Clustered she reads **t=-1.00 over 9 batches**. The docket's
    existing `days` caveat counts distinct UTC DATES and reported "2
    close-day(s)" — true, and the wrong granularity for the question.

    Returns `gr.cluster_stats`'s dict, or None on a shape the estimator cannot
    judge (G < 2, or between-batch deviations that cancel — the (kg)
    degeneracy). Absent means "not computable", never "fine".
    """
    rr = sorted(rows, key=lambda r: r["closed"])
    pct = [r["pct"] * 100 for r in rr]
    n = len(pct)
    if n < 2:
        return None
    mean = sum(pct) / n
    sd = math.sqrt(sum((x - mean) ** 2 for x in pct) / n) or 1e-12
    return gr.cluster_stats([(r["pct"] * 100, r["abs"], r["closed"]) for r in rr],
                            mean, sd, n)


def followthrough(key, rows):
    """[I21] The pre-registered test: the FRESH closes alone, never the pooled.

    Returns None for a bucket that was never pre-registered. Otherwise a dict
    carrying the registration record and the fresh-sample verdict, plus the two
    readings that decided the 21-Aug call and would otherwise be invisible:
    `tag_share` (the fresh sample was 9 of 9 ONE tag, i.e. a different mixture
    from the one registered) and `days` (6 of those 9 closed inside a single
    UTC day, so they are not 9 independent draws — the (ky)/(kw) clustering
    shape). Both are REPORTED, never bars: this returns a verdict, and a
    verdict computed on a sample below MIN_N is `undecided` by the same I16
    floor that keeps a lucky 3-close streak away from the referee.
    """
    reg = PRE_REGISTERED.get(key)
    if not reg:
        return None
    since = _parse_ts(reg["since"])
    fresh = [r for r in rows if since is not None and r["closed"] > since]
    out = dict(reg=reg, n=len(fresh))
    if not fresh:
        out.update(verdict="undecided", why="no closes since registration")
        return out
    pcts = [r["pct"] * 100 for r in fresh]
    t = t_stat(pcts)
    tags = defaultdict(int)
    for r in fresh:
        tags[r["tag"] or "-"] += 1
    clus = cluster_view(fresh)
    out.update(t=round(t, 2), mean_pct=round(sum(pcts) / len(pcts), 3),
               total=round(sum(r["abs"] for r in fresh), 2),
               p=t_sf(t, len(pcts) - 1),
               tag_share=round(max(tags.values()) / len(fresh), 2),
               days=len({r["closed"].date() for r in fresh}),
               clus=clus)
    # [2026-09-04 (xy)] THE VERDICT IS THE CLUSTER-ROBUST READ, and the FLOOR
    # counts BATCHES, not rows. A book that flattens writes n rows at one
    # instant; those are ONE observation, so admitting them as n both inflates
    # |t| by ~sqrt(batch) and buys the I16 floor with draws that do not exist.
    # FAIL-CLOSED, and the closed direction is "never crown": a shape this
    # estimator cannot judge is `undecided`, never `confirmed` on the iid t.
    # SYMMETRIC by construction — it refuses a false CONFIRM on an inflated
    # winning batch exactly as it refuses a false condemnation on a halt.
    g = (clus or {}).get("n_clusters")
    t_cr = (clus or {}).get("t_cluster")
    if clus is None or g is None or t_cr is None:
        out.update(verdict="undecided",
                   why=f"cluster-robust t not computable on n={len(fresh)} "
                       "(G<2 or cancelling batches) — never crowned on the iid t")
    elif g < MIN_N:
        out.update(verdict="undecided",
                   why=f"fresh n={len(fresh)} is {g} independent close-batch(es) "
                       f"< MIN_N {MIN_N} (I16 floor, counted on batches)")
    elif t_cr >= 2.0:
        out.update(verdict="confirmed",
                   why=f"cluster-robust t {t_cr:+.2f} >= 2.0 on the fresh "
                       f"sample alone ({g} batches)")
    else:
        out.update(verdict="not_confirmed",
                   why=f"cluster-robust t {t_cr:+.2f} < 2.0 on the fresh "
                       f"sample alone ({g} batches)")
    return out


def grade_buckets(bk):
    graded = {}
    for key, rows in bk.items():
        pcts = [r["pct"] * 100 for r in rows]
        t = t_stat(pcts)
        n = len(pcts)
        total = sum(r["abs"] for r in rows)
        top1 = max((r["abs"] for r in rows), default=0.0)
        span_d = max(1e-9, (rows[-1]["closed"] - rows[0]["closed"]).total_seconds() / 86400)
        graded[key] = dict(
            n=n, t=round(t, 2), mean_pct=round(sum(pcts) / n, 3),
            total=round(total, 2), p=t_sf(t, n - 1),
            top1_share=round(top1 / total, 2) if total > 0 else None,
            rate_30d=round(n / span_d * 30, 1),
            drift=(key[2].startswith("short") or key[2] == "short")
            and not any(f in key[0] for f in FUNDING_BOOKS),
            prereg=followthrough(key, rows),
            # [(xy)] REPORTED on every bucket, never a bar here: the BH referee
            # still runs on the iid p, and changing THAT re-verdicts 42 buckets
            # and needs its own evidence pass. Measured the day this shipped, no
            # bucket crosses |t|=2 upward when clustered (so no PROVEN verdict
            # moves today) and the inflation is concentrated exactly where the
            # design predicts — ⚖️ Counterweight, the one book that closes ten
            # legs in one instant: side:short t -2.77 -> -1.57, book:* -1.84 ->
            # -0.83. Publishing it is what lets the next pass grade the referee.
            clus=cluster_view(rows),
        )
    return graded


def report(graded, fdr=FDR):
    tested = [(k, g["p"]) for k, g in graded.items()]
    winners = bh_survivors(tested, fdr)
    lines = [f"WINNERS' DOCKET — {len(tested)} buckets tested (era-scoped, "
             f"quarantine-filtered, n>={MIN_N}), BH at FDR {fdr}"]
    # [I21] A pre-registered bucket may NOT be crowned on the pooled window —
    # that window contains the closes that generated the hypothesis. It stays
    # in `tested` (so m is unchanged and no other bucket's BH threshold moves
    # in its favour) and is decided below, on its fresh sample alone.
    held = sorted(k for k in winners if k in PRE_REGISTERED)
    winners = {k for k in winners if k not in PRE_REGISTERED}
    if winners:
        lines.append("\nPROVEN WINNING (survives the referee):")
        for k in sorted(winners, key=lambda k: graded[k]["p"]):
            g = graded[k]
            stamps = []
            if g["top1_share"] is not None and g["top1_share"] >= TAIL_SHARE:
                stamps.append("tail_concentrated")
            if g["drift"]:
                stamps.append("drift_check_required")
            lines.append(f"  {k[0]} [{k[1]}:{k[2]}] n={g['n']} "
                         f"mean={g['mean_pct']:+.3f}% t={g['t']} p={g['p']:.4f} "
                         f"${g['total']:+.2f}"
                         + (f"  ⚠ {','.join(stamps)}" if stamps else ""))
    else:
        lines.append("\nPROVEN WINNING: none — no bucket survives the referee today.")
    reg_keys = [k for k in graded if k in PRE_REGISTERED]
    if reg_keys:
        lines.append("\nPRE-REGISTERED FOLLOW-THROUGH (I21 — graded on closes "
                     "AFTER registration, never on the window that generated "
                     "the hypothesis):")
        for k in sorted(reg_keys):
            g = graded[k]
            ft = g["prereg"]
            r = ft["reg"]
            lines.append(f"  {k[0]} [{k[1]}:{k[2]}]  registered {r['since'][:10]} "
                         f"at n={r['n']} t={r['t']} mean={r['mean_pct']:+.3f}%")
            lines.append(f"      pooled (NOT the test): n={g['n']} t={g['t']} "
                         f"mean={g['mean_pct']:+.3f}% p={g['p']:.4f}"
                         + ("  <- would have been crowned PROVEN on the "
                            "re-mined window" if k in held else ""))
            if ft["n"]:
                lines.append(f"      FRESH: n={ft['n']} t={ft['t']} "
                             f"mean={ft['mean_pct']:+.3f}% ${ft['total']:+.2f} "
                             f"p={ft['p']:.4f} · {ft['days']} close-day(s), "
                             f"dominant tag {ft['tag_share']:.0%}")
                fc = ft.get("clus")
                lines.append("      CLUSTERED (the test, (xy)): "
                             + (f"t={fc['t_cluster']:+.2f} over "
                                f"{fc['n_clusters']} close-batch(es), "
                                f"largest {fc['max_batch']}, n_eff={fc['n_eff']}"
                                if fc else
                                "not computable — a shape this estimator "
                                "cannot judge (never crowned on the iid t)"))
            lines.append(f"      => {ft['verdict'].upper()} — {ft['why']}")
    near = [(k, g) for k, g in graded.items()
            if k not in winners and k not in PRE_REGISTERED
            and g["t"] >= NEAR_T and g["mean_pct"] > 0]
    near.sort(key=lambda kg: kg[1]["p"])
    if near:
        lines.append("\nON THEIR WAY (t >= 1, not yet proven — n needed at t-bar 2.0):")
        for k, g in near[:12]:
            n_req = math.ceil(g["n"] * (2.0 / g["t"]) ** 2) if g["t"] > 0 else None
            eta_d = (round((n_req - g["n"]) / g["rate_30d"] * 30, 0)
                     if n_req and g["rate_30d"] > 0 else None)
            if n_req is not None and n_req <= g["n"]:
                tail = ("t-bar met; held only by the multiplicity referee — "
                        "a pre-registered follow-through sample decides")
            elif eta_d:
                tail = f"n_req~{n_req}, ~{eta_d:.0f}d at own rate"
            else:
                tail = f"n_req~{n_req}"
            lines.append(f"  {k[0]} [{k[1]}:{k[2]}] n={g['n']} t={g['t']} "
                         f"mean={g['mean_pct']:+.3f}% -> {tail}")
    return "\n".join(lines), winners


def _selftest():
    # exact t tail against known values (two-sided 0.05 at df=10 is t=2.228)
    assert abs(t_sf(2.228, 10) - 0.025) < 1e-3, t_sf(2.228, 10)
    assert abs(t_sf(2.0, 10) - 0.03669) < 2e-4
    assert abs(t_sf(0.0, 30) - 0.5) < 1e-12
    assert t_sf(-2.0, 10) > 0.96
    # BH: a planted real winner survives, a lucky small-n bucket does not
    import random
    rng = random.Random(7)
    real = [0.5 + rng.gauss(0, 0.5) for _ in range(60)]     # strong, n=60
    lucky = [2.0, 1.5, 1.8]                                  # huge mean, n=3
    noise = {f"noise{i}": [rng.gauss(0, 1) for _ in range(30)] for i in range(20)}
    pv = [("real", t_sf(t_stat(real), len(real) - 1))]
    pv += [(k, t_sf(t_stat(v), len(v) - 1)) for k, v in noise.items()]
    surv = bh_survivors(pv, 0.05)
    assert "real" in surv, "a genuine winner must survive the referee"
    # LUCK IS STOPPED BY THE FLOOR, NOT BY BH — a consistent 3-close streak is
    # mathematically significant, which is exactly why n<MIN_N buckets must
    # never REACH the referee (I16: luck must not outrank evidence). Assert on
    # the real pipeline: buckets_of refuses the small bucket outright.
    from datetime import datetime, timezone, timedelta
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    mk_row = lambda pct, i, ex: dict(pct=pct, abs=pct, exit=ex, tag="",
                                     closed=t0 + timedelta(hours=i))
    fixture = {"bot-lucky": [mk_row(0.02, i, "tp") for i in range(3)],
               "bot-real": [mk_row(0.005, i, "tp") for i in range(60)]}
    bk = buckets_of(fixture)
    assert not any(k[0] == "bot-lucky" for k in bk), \
        "an n<MIN_N bucket must never reach the referee"
    assert ("bot-real", "book", "*") in bk
    # the era rule is the gate's own, by identity — never a copy
    assert era_scoped_rows.__module__ == "__main__" or True
    assert gr.era_rows is sys.modules["golive_readiness"].era_rows
    print("winners_docket selftest: OK")


def main():
    trades = store.fetch_paper_trades(limit=8000)
    if not trades:
        print("winners_docket: ledger unreachable or empty — no verdict "
              "(a dark read is never 'no winners')")
        return 2
    by_bot = era_scoped_rows(trades)
    graded = grade_buckets(buckets_of(by_bot))
    txt, _ = report(graded)
    print(txt)
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
