#!/usr/bin/env python3
"""study_mum_noncrypto_sleeve_2026-09-02.py — is 👩 mum's NON-CRYPTO sleeve
losing, and has the sample earned the right to say so?

WHY. Eamon, 2-Sep: "How do we fix mum" / "if it makes any bot make more money
then implement." Her live arm's one apparently-weak sleeve on the day she was
asked about: the non-crypto names read 7 closes at −0.383%/trade (t −1.66),
five of seven `max_hold` losers; the shadow twin agrees (7 closes, −0.540%,
t −2.38). The iid upper bound sits just below zero.

**[CORRECTED IN PLACE, same day, per I12 — THE FIRST VERSION OF THIS FILE
NAMED A MECHANISM THAT IS FALSIFIED ON ITS OWN DISCRIMINATOR, AND WROTE A CUT
RULE THAT WOULD HAVE FIRED ON A SAMPLE WITH NO MEASURED EXCLUSION. Both are
corrected below and the refutation is kept, because a refuted mechanism that
is quietly deleted is a lesson nobody can re-check.]**

THE CLAIM THAT WAS MADE AND IS NOW REFUTED: "a tokenised equity or commodity
book prints through its underlying's CLOSED hours, so a 1h oversold read there
is a flat tape, the rebound cannot arrive before the underlying reopens, and
the 24h cap books the position at a loss." Its own discriminator kills it. Of
the 10 `max_hold` losses across both arms, **ZERO expired before the underlying
reopened** — every one carried 27%–96% of its hold inside the open session
(SPY/QQQ 390 of ~1443 min; XAU/XCU 1381–1389 of ~1443). The one trade in the
pooled sample with NO open minutes at all (XAU entered Fri 28-Aug 22:01Z, into
the weekend) exited `roi` at **+0.070%** — a win, the opposite of the
prediction. And the direction reverses: entry-while-underlying-OPEN reads
−0.521%/trade against entry-while-CLOSED −0.383%, on each arm independently.
XAU/XCU trade ~23h on COMEX and have no meaningful closed-hours shape at all,
yet they carry the two largest live losses.

THREE THINGS THE SAMPLE ACTUALLY SAYS, each re-measured through the fleet's own
owners (`golive_readiness.cluster_se`, `fleet_allocation.t_crit`):

1. **THERE IS NO MEASURED EXCLUSION — the closes are not 7 decisions.** Three
   of the live arm's seven share a byte-identical `opened_at`
   (2026-09-01T09:03:49.764115Z) and G = **4 entry days**, not 7. Clustered:
   live t goes −1.665 (iid) → −1.135 (open-day), and the UPPER BOUND — the
   thing I17-as-amended requires before anything is cut — is ≤ 0 **only on the
   iid read** (−0.052%) and turns POSITIVE under every day-level cluster
   (+0.170% open-day, +0.296% close-day, +0.048% open-instant). The twin's
   day-clustered ub is −0.002%, i.e. zero.
2. **GIVEN THE DAY, THE CLASS LABEL CARRIES NO INFORMATION (I25).** The raw
   non-crypto-minus-crypto gap is −0.983pp live / −1.045pp shadow and **flips
   sign under a close-day fixed effect** to **+0.184pp / +0.207pp**. On 2-Sep,
   the day carrying 4 of the 7 rows and all the batched losses, the CRYPTO
   sleeve lost more than twice as much per trade (live −1.638% vs the
   non-crypto −0.791%). Judging the sleeve against the window that motivated
   looking at it is the exact I25 error.
3. **MOST OF THE RAW GAP IS SELECTION BY EXIT.** `max_hold` is negative BY
   CONSTRUCTION — the roi ladder's terminal rung is 1440min:0.0 — and measured
   across all 114 era closes on both arms it is **0 positive / 18 negative**
   while `roi` is 81 of 82 positive. The non-crypto sleeve is 71% `max_hold`
   against crypto's ~8%. **Conditional on reaching the cap, non-crypto does no
   worse than crypto** (live −0.705% vs −1.001%; shadow −0.848% vs −0.821%).

THE MECHANISM THAT *IS* SUPPORTED, and it points the other way: the non-crypto
names are **LOW-VOLATILITY against a bracket calibrated on crypto**. Realised
mean |return| is 0.623% vs 1.746% (2.80× live, 2.61× shadow) against a first
roi rung needing +2.0% inside 4h, so **5 of 7 non-crypto trades run the full
24h cap against 4 of 52 crypto** — binomial P(≥5 of 7 at crypto's own rate)
= **5.0e-05**, established even at n=7. The sleeve therefore resolves as a
near-coin-flip at the terminal zero rung, and 2 wins of 7 under a fair coin is
P=0.227 — noise. **That reframes the remedy from a CUT to a class-aware ladder
or hold (the I26 feed-it direction), and that remedy owes its own measurement
before anything ships.**

**[(xn)] IT WAS MEASURED, AND BOTH HALVES ARE CORRECTED IN PLACE per I12.**
(1) **The 2.80× is a SEVEN-CLOSE artifact.** On 10,020 non-crypto and 12,418
crypto episodes of her own mechanical entry over the full 1h tape, the gap is
**1.29×** (median favourable excursion 1.203% vs 1.554%), the non-crypto p90
is HIGHER (2.903% vs 2.744%), and **66.0% still reach a rung** against crypto's
74.5%. The direction survives; the size does not. (2) **The remedy is REFUSED.**
Halving the ladder is the best cell (+0.0325%/bar-day) but shuffling the class
labels and re-running the whole best-of-N selection gives a MEDIAN advantage of
+0.0363% against the real half's +0.0304% — **p=0.5885**, so the gain is the
selection procedure, not the class. The CRYPTO control moves the opposite way,
monotone in the dose (−0.022 / −0.080 / −0.176 %/bar-day at k=0.5/0.35/0.25) on
the half that actually earns, so a whole-book lowering is **refuted**, not
merely untested. Full working: `STUDY_MUM_CLASS_LADDER_2026-09-02.md`.

THE PRE-REGISTERED RULE, as corrected (`PRE_REGISTERED`, since 2026-09-02):
read when the live arm has **G >= MIN_N distinct ENTRY DAYS** on the sleeve —
the fleet's computability floor applied to the unit of independence, not to
the close count — or on 16-Sep, whichever first. **CUT only when ALL of:** the
DAY-CLUSTERED upper bound (mean + t_crit(G)·cluster_se) <= 0, AND the sleeve is
worse than the CRYPTO sleeve on a close-day-MATCHED basis (the control the book
already carries, because the raw gap flips sign without it). **KEEP when the
sleeve's mean > 0.** Else NOT DECIDABLE, with the days still required. The
twin is REPORTED and is no longer part of the condition: it shares 6 of 7
coin-days with the live arm, so it corroborates direction and supplies no
independent evidence. The act is
`FAMILY_NONCRYPTO_EXCLUDE="freqtrade-mum:*"` on BOTH hosts — the WHOLE
non-crypto half, so the act matches the graded population exactly — ENTRY-ONLY
(a held name keeps its bracket), reversible by unsetting it, era untouched (a
universe edit is ordinary tuning per (hc)).

Read-only: grades, moves nothing. Through the grader's owners
(`edge_audit.load_trades`/`shape` -> `golive_readiness.era_rows`/`stats`/
`cluster_se`, `fleet_allocation.t_crit`, `fleet_bus.is_crypto`).

    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py             # public feed
    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py --ledger t.json
    python3 scripts/study_mum_noncrypto_sleeve_2026-09-02.py --selftest  # offline
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import edge_audit as ea                  # noqa: E402
import fleet_allocation as fa            # noqa: E402
import golive_readiness as gr            # noqa: E402

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
LIVE, SHADOW = "freqtrade-mum-lighter", "freqtrade-mum-lshadow"
MIN_N = int(getattr(fa, "MIN_N", 10))

PRE_REGISTERED = {
    "id": "mum-noncrypto-sleeve",
    "since": "2026-09-02T11:00:00+00:00",
    "min_g": MIN_N,          # DISTINCT ENTRY DAYS, not closes — the unit of
                             # independence. 3 of the first 7 closes were one
                             # decision (one `opened_at`), so a close count is
                             # not a sample size here.
    "min_n": MIN_N,
    "read_by": "2026-09-16",
    "rule": ("CUT only when the live sleeve has G>=min_g distinct ENTRY DAYS "
             "AND its DAY-CLUSTERED upper bound (mean + t_crit(G)*cluster_se) "
             "<= 0 AND it is worse than the CRYPTO sleeve on a close-day-"
             "MATCHED basis; KEEP when the sleeve mean > 0; else NOT DECIDABLE."),
    # THE ACT IS THE POPULATION, EXACTLY. The claim is about a CLASS, and the
    # sample is every non-crypto close, so the act is the whole non-crypto half
    # via the `*` wildcard, never a ticker list. A list would be graded on one
    # population and applied to another, and would drift the day a (vd)
    # extension name crossed the oracle's 203-bar floor and began trading.
    "act": ("FAMILY_NONCRYPTO_EXCLUDE='freqtrade-mum:*' — the carrier's WHOLE "
            "non-crypto half, set on mum-live AND family-lighter-shadow "
            "together; ENTRY-ONLY (a held name keeps its bracket, "
            "lighter_family_bot.carrier_universe); era untouched; "
            "revert = unset"),
    "population": "every non-crypto close on the arm, by fleet_bus.is_crypto",
    "at_registration": {"live": "n=7 G=4 -0.383%/t t_iid=-1.66 t_cl=-1.14 "
                                "ub_iid -0.052% but ub_cl +0.170% (NO exclusion)",
                        "shadow": "n=7 G=4 -0.540%/t t_cl=-1.64 ub_cl -0.002%",
                        "day_matched": "+0.184pp live / +0.207pp shadow — the raw "
                                       "gap FLIPS SIGN under a close-day effect"},
    # the twin is corroboration of DIRECTION only: it shares 6 of 7 coin-days
    # with the live arm, so it is the same trades at a different size and is
    # reported, never a condition (the first version made it one).
    "twin": "reported, not a condition",
    "mechanism": ("vol/bracket mismatch: realised |return| 2.8x below the ladder's "
                  "first rung, so 5 of 7 run the 24h cap vs 4 of 52 crypto "
                  "(binomial P=5.0e-05) and resolve at the terminal zero rung. "
                  "THE CLOSED-HOURS STORY IS REFUTED — 0 of 10 max_hold losses "
                  "expired before the underlying reopened, and entry-while-OPEN "
                  "is WORSE than entry-while-CLOSED."),
    "remedy_if_cut_fails": ("a class-aware roi ladder / hold (I26 feed-it), "
                            "measured on its own before anything ships"),
}


def _is_crypto(coin):
    try:
        import fleet_bus as fb
        return bool(fb.is_crypto(coin))
    except Exception:            # noqa: BLE001
        return None


def _bounds(quads):
    rows = [(q[0], q[1], q[2]) for q in quads]
    s = gr.stats(rows) if len(rows) >= 2 else {"n": len(rows)}
    n = s.get("n", 0)
    out = {"n": n, "usd": round(sum(q[1] for q in quads), 2),
           "exits": dict(Counter(ea.exit_of(q[7]) for q in quads if len(q) > 7)),
           "coins": sorted({str(q[6]).split("/")[0] for q in quads})}
    if n < 2 or s.get("se_pct") is None:
        return out
    crit = fa.t_crit(n)
    m, se = 100 * s["mean_pct"], 100 * s["se_pct"]
    out.update(mean_pct=round(m, 4), t=round(s["t"], 3), se_pct=round(se, 4), crit=round(crit, 3),
               lb_pct=round(m - crit * se, 4), ub_pct=round(m + crit * se, 4),
               win=round(sum(1 for q in quads if q[0] > 0) / n, 3))
    # THE DAY-CLUSTERED READ IS THE ONE THE RULE USES. Three of this sleeve's
    # first seven closes shared ONE `opened_at`, so the iid SE is the SE of a
    # sample that does not exist. `cluster_se` is the grader's own owner
    # ((kw)/(ky)) — never a second copy — and `t_crit` takes G, not n.
    out.update(g=None, cse_pct=None, t_cl=None, ub_cl_pct=None, days=[])
    try:
        keys = [str(q[3])[:10] for q in quads]
        cse, g, maxc = gr.cluster_se([q[0] for q in quads], keys)
        # G AND THE DAYS ARE RECORDED EVEN WHEN THE SE IS NOT. `cluster_se`
        # returns None for a SINGLE cluster — 14 closes on one entry day — and
        # that is precisely the state the day floor exists to refuse, so
        # dropping `g` with the SE would hide the refusal's own reason.
        out.update(g=g, max_in_day=maxc, days=sorted(set(keys)))
        if cse:
            cse *= 100
            out.update(cse_pct=round(cse, 4), crit_g=round(fa.t_crit(max(g, 2)), 3),
                       t_cl=round(m / cse, 3),
                       ub_cl_pct=round(m + fa.t_crit(max(g, 2)) * cse, 4))
    except Exception:            # noqa: BLE001 — a dark clusterer never cuts
        pass
    return out


def day_matched(sleeve, other):
    """`sleeve` mean minus `other` mean, matched on CLOSE DAY (I25).

    The unmatched gap is judged against whatever mix of days each side
    happened to close on. Measured here at registration: the raw class gap is
    −0.98pp and the day-matched one is **+0.18pp** — opposite signs, because
    the day carrying most of the sleeve's rows was a bad day for the whole
    book. Returns None when no day carries both, which is a REFUSAL to judge,
    never a zero.
    """
    a, b = defaultdict(list), defaultdict(list)
    for q in sleeve:
        a[str(q[2])[:10]].append(q[0])
    for q in other:
        b[str(q[2])[:10]].append(q[0])
    shared = sorted(set(a) & set(b))
    if not shared:
        return None
    num = sum((100 * sum(a[d]) / len(a[d]) - 100 * sum(b[d]) / len(b[d])) * len(a[d]) for d in shared)
    den = sum(len(a[d]) for d in shared)
    return {"pp": round(num / den, 4), "days": shared,
            "raw_pp": round(100 * sum(q[0] for q in sleeve) / max(len(sleeve), 1)
                            - 100 * sum(q[0] for q in other) / max(len(other), 1), 4)}


def split(quads, crypto=None):
    """{'crypto': [...], 'noncrypto': [...], 'unknown': [...]} by the venue's class."""
    out = defaultdict(list)
    for q in quads:
        coin = str(q[6] or "").split("/")[0]
        c = crypto.get(coin) if isinstance(crypto, dict) else _is_crypto(coin)
        out["crypto" if c else "noncrypto" if c is False else "unknown"].append(q)
    return out


def decide(live, twin=None, matched=None, min_g=MIN_N):
    """CUT / KEEP / NOT DECIDABLE on the live sleeve. The twin is REPORTED.

    Three things must all hold before a cut, and each closes a way the first
    version of this rule would have been wrong:
      * **G >= min_g DISTINCT ENTRY DAYS**, because 3 of the first 7 closes
        were one decision and a close count is not a sample size (I16's floor
        applied to the unit of independence);
      * the **DAY-CLUSTERED** upper bound at or below zero — the iid bound was
        the only read that said cut, and every clustered one is positive
        (I17-as-amended: a retirement needs a MEASURED exclusion);
      * the sleeve **worse than the CRYPTO sleeve on matched close-days**,
        because the raw class gap flips sign under a day effect (I25).
    Anything missing degrades to NOT DECIDABLE — never to a cut.
    """
    n, g = live.get("n", 0), live.get("g")
    ub = live.get("ub_cl_pct")
    if (live.get("mean_pct") or 0.0) > 0:
        return {"verdict": "keep", "why": f"live sleeve mean {live['mean_pct']:+.3f}% > 0"}
    if not g or g < min_g:
        need = max(min_g - (g or 0), 0)
        return {"verdict": "not_decidable",
                "why": f"live sleeve G={g or 0} entry day(s) < {min_g} (n={n} closes)",
                "g_req": need}
    if ub is None:
        return {"verdict": "not_decidable", "why": "no clustered bound — refusing to cut on the iid read"}
    if ub > 0:
        return {"verdict": "undecided",
                "why": f"day-clustered ub {ub:+.3f}% > 0 on G={g} — the sample has excluded nothing"}
    if matched is None:
        return {"verdict": "not_decidable",
                "why": "no close-day-matched control — the raw gap is not a finding (I25)"}
    if matched.get("pp", 0.0) >= 0:
        return {"verdict": "undecided",
                "why": f"day-matched vs crypto {matched['pp']:+.3f}pp is not worse "
                       f"(raw {matched.get('raw_pp')}pp) — the class label carries no information"}
    return {"verdict": "cut",
            "why": f"clustered ub {ub:+.3f}% <= 0 on G={g}; day-matched {matched['pp']:+.3f}pp worse than crypto"
                   + (f"; twin {twin.get('mean_pct'):+.3f}% (reported)" if twin and twin.get("mean_pct") is not None else "")}


def run(shaped, since=None, crypto=None):
    out = {"registered": PRE_REGISTERED, "arms": {}}
    for arm in (LIVE, SHADOW):
        quads = (shaped.get(arm) or {}).get("rows") or []
        if since is not None:
            quads = [q for q in quads if ea._ts(q[3]) and ea._ts(q[3]) > since]
        sp = split(quads, crypto)
        out["arms"][arm] = {k: _bounds(v) for k, v in sp.items()}
        out["arms"][arm]["n_total"] = len(quads)
    live = out["arms"][LIVE].get("noncrypto", {"n": 0})
    twin = out["arms"][SHADOW].get("noncrypto", {"n": 0})
    lq = (shaped.get(LIVE) or {}).get("rows") or []
    if since is not None:
        lq = [q for q in lq if ea._ts(q[3]) and ea._ts(q[3]) > since]
    lsp = split(lq, crypto)
    out["matched"] = day_matched(lsp["noncrypto"], lsp["crypto"])
    out["decision"] = decide(live, twin, out["matched"])
    return out


def render(res):
    L = ["# mum non-crypto sleeve — pre-registered read (read-only)"]
    for arm, d in res["arms"].items():
        L.append(f"\n## {arm} · n={d['n_total']}")
        L.append("| sleeve | n | G | mean% | t_iid | t_cl | ub_iid% | ub_cl% | win | $ | exits | coins |")
        L.append("|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|")
        for k in ("crypto", "noncrypto", "unknown"):
            g = d.get(k)
            if g and g.get("n"):
                L.append(f"| {k} | {g['n']} | {g.get('g', '—')} | {g.get('mean_pct', '—')} | {g.get('t', '—')} | "
                         f"{g.get('t_cl', '—')} | {g.get('ub_pct', '—')} | {g.get('ub_cl_pct', '—')} | "
                         f"{g.get('win', '—')} | {g['usd']} | {g['exits']} | {','.join(g['coins'])} |")
    m = res.get("matched")
    if m:
        L.append(f"\nCLOSE-DAY-MATCHED noncrypto − crypto: {m['pp']:+.4f}pp "
                 f"(raw {m['raw_pp']:+.4f}pp) over {len(m['days'])} shared day(s) — "
                 "the raw gap is not a finding without this (I25)")
    else:
        L.append("\nCLOSE-DAY-MATCHED: no day carries both sleeves — REFUSING to judge the class gap")
    L.append(f"\nVERDICT: {res['decision']['verdict']} — {res['decision']['why']}"
             + (f" (needs {res['decision']['g_req']} more entry day(s))"
                if res['decision'].get('g_req') else ""))
    return "\n".join(L)


# ---------------------------------------------------------------- selftest

def _quad(coin, pct, i, t0, reason="long-oversold-rebound_roi", hours=3):
    o = t0 + timedelta(hours=hours * i)
    c = o + timedelta(hours=6)
    r = {"pair": f"{coin}/USDC", "side": "long", "reason": reason, "opened_at": o.isoformat()}
    return (pct, pct * 100, c, o.isoformat(), None, reason, f"{coin}/USDC", r)


def _synth(seed, nc_mu, n_nc=12, n_c=40, c_mu=0.006, batch=False):
    """A book whose sleeves each open on their OWN day, so G == n by default.

    The two sleeves are INTERLEAVED across the same days on purpose: the
    close-day-matched control needs days that carry both, and a fixture whose
    classes never share a day would make that control unreachable — a check
    that inspects nothing.

    `batch=True` puts every non-crypto entry on ONE day — the live arm's real
    shape at registration (3 of 7 closes shared one `opened_at`) — which is
    what the G floor exists to refuse.
    """
    rnd = random.Random(seed)
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n_c):
        rows.append(_quad("BTC" if i % 2 else "SOL", rnd.gauss(c_mu, 0.012), i, t0, hours=25))
    for i in range(n_nc):
        rows.append(_quad(("XAU", "SPY", "QQQ", "XCU")[i % 4], rnd.gauss(nc_mu, 0.006),
                          0 if batch else i, t0, "long-oversold-rebound_max_hold",
                          hours=25))
    rows.sort(key=lambda q: q[2])
    return rows


def _selftest():
    crypto = {"BTC": True, "SOL": True, "XAU": False, "SPY": False, "QQQ": False, "XCU": False}
    # POSITIVE CONTROL: a losing sleeve, spread over its own days, worse than
    # crypto on matched days, IS cut. Without this arm the rule below could be
    # a rule that never fires, which is trivially safe and useless (I3).
    shaped = {LIVE: {"rows": _synth(1, -0.012, n_nc=14)}, SHADOW: {"rows": _synth(2, -0.010, n_nc=14)}}
    r = run(shaped, crypto=crypto)
    live = r["arms"][LIVE]["noncrypto"]
    assert live["g"] >= MIN_N and live["ub_cl_pct"] < 0, live
    assert r["decision"]["verdict"] == "cut", (r["decision"], r["matched"])
    assert live["exits"] == {"max_hold": 14}
    # PLACEBO, AS A RATE NOT A DRAW. A single seed here is a coin flip and
    # picking the one that passes is seed-fishing, so this draws the sleeve
    # from the SAME distribution as crypto twenty times and requires the cut
    # to be rare. It is the false-positive rate of the whole rule.
    # MEASURED at 300 draws: cut 6.3%, and it decomposes exactly as designed —
    # the clustered bound fires at 9.7% (its own one-sided level, i.e. t_crit
    # is calibrated) and the day-matched control at 51.0% (a coin flip on a
    # null, as it must be), and 0.097 x 0.51 = 0.049. The bar below is set far
    # above that so the arm tests the RULE and not the seed; a rule that fired
    # at 20% would redden it.
    DRAWS = 200
    cuts = sum(run({LIVE: {"rows": _synth(1000 + k, 0.0, n_nc=14, c_mu=0.0)},
                    SHADOW: {"rows": _synth(5000 + k, 0.0, n_nc=14, c_mu=0.0)}},
                   crypto=crypto)["decision"]["verdict"] == "cut"
               for k in range(DRAWS))
    assert cuts <= 0.20 * DRAWS, f"placebo cut {cuts}/{DRAWS} — the rule fires on noise"
    # a WINNING sleeve is KEPT
    assert run({LIVE: {"rows": _synth(5, 0.008, n_nc=14)},
                SHADOW: {"rows": _synth(6, 0.008, n_nc=14)}}, crypto=crypto)["decision"]["verdict"] == "keep"
    # THE BATCHED SAMPLE — the live arm's REAL shape at registration. Fourteen
    # closes, all on one entry day, is ONE decision: G=1, refused, with the
    # days still owed. This is the arm the first version of this rule missed.
    rb = run({LIVE: {"rows": _synth(7, -0.012, n_nc=14, batch=True)},
              SHADOW: {"rows": _synth(8, -0.012, n_nc=14, batch=True)}}, crypto=crypto)
    assert rb["arms"][LIVE]["noncrypto"]["n"] == 14, rb["arms"][LIVE]["noncrypto"]
    assert rb["arms"][LIVE]["noncrypto"]["g"] == 1, rb["arms"][LIVE]["noncrypto"]["g"]
    assert rb["decision"]["verdict"] == "not_decidable" and rb["decision"]["g_req"] == MIN_N - 1, rb["decision"]
    # THE CLUSTERED BOUND IS THE ONE THAT DECIDES: negative mean, enough days,
    # but a clustered upper bound still above zero is `undecided`, never a cut.
    neg_open = {"n": 14, "g": 12, "mean_pct": -0.8333, "t": -1.32,
                "se_pct": 0.4000, "cse_pct": 0.6300,
                "ub_pct": round(-0.8333 + fa.t_crit(14) * 0.40, 4),
                "ub_cl_pct": round(-0.8333 + fa.t_crit(12) * 0.63, 4)}
    assert neg_open["ub_pct"] < 0 < neg_open["ub_cl_pct"], neg_open
    assert decide(neg_open, matched={"pp": -0.5})["verdict"] == "undecided", decide(neg_open, matched={"pp": -0.5})
    # and the one that HAS excluded a positive mean cuts
    exc = dict(neg_open, ub_cl_pct=-0.15)
    assert decide(exc, matched={"pp": -0.5})["verdict"] == "cut"
    # THE DAY-MATCHED CONTROL IS A CONDITION, not a report: a sleeve that is
    # not worse than crypto on shared days is never cut, whatever its bound.
    assert decide(exc, matched={"pp": +0.18})["verdict"] == "undecided"
    assert decide(exc, matched=None)["verdict"] == "not_decidable"
    # and it must be able to FLIP a raw gap, which is the whole reason it exists
    t0 = datetime(2026, 9, 1, tzinfo=timezone.utc)
    # one BAD day carrying the whole sleeve, where crypto did WORSE, plus good
    # days crypto alone traded — the live arm's exact shape on 2026-09-02.
    nc = [_quad("SPY", -0.008, 0, t0, hours=48)]
    cr = ([_quad("BTC", -0.030, 0, t0, hours=48)]
          + [_quad("BTC", +0.020, k, t0, hours=48) for k in (1, 2, 3)])
    dm = day_matched(nc, cr)
    assert dm is not None and dm["raw_pp"] < 0 < dm["pp"], dm
    assert len(dm["days"]) == 1, dm
    assert day_matched(nc, [_quad("BTC", 0.01, 0, datetime(2030, 1, 1, tzinfo=timezone.utc))]) is None
    # THE TWIN IS REPORTED, NOT A CONDITION — a positive twin cannot block a
    # cut the live arm's own clustered evidence supports, and a negative one
    # cannot rescue a cut it does not.
    assert decide(exc, twin={"n": 9, "mean_pct": +0.9}, matched={"pp": -0.5})["verdict"] == "cut"
    assert decide(neg_open, twin={"n": 9, "mean_pct": -0.9}, matched={"pp": -0.5})["verdict"] == "undecided"
    # THE CRITICAL VALUE IS THE FLEET'S, BY IDENTITY (the (hj) pin) — a
    # hardcoded normal quantile is the (ua) defect, and it is the UNSAFE
    # direction here because it narrows the interval that gates a cut.
    for _n in (10, 12, 20, 40):
        assert fa.t_crit(_n) > 1.2816, _n
    _b = _bounds(_synth(11, -0.012, n_nc=12, n_c=0))
    assert _b["crit"] == round(fa.t_crit(_b["n"]), 3), _b
    assert _b["crit_g"] == round(fa.t_crit(_b["g"]), 3), _b
    # the split never guesses a class: an unknown coin lands in `unknown`
    assert list(split([_quad("ZZZ", 0.01, 0, t0)], crypto={})) == ["unknown"]
    # `since` restricts to fresh opens, and a fresh-empty sample never cuts
    r6 = run(shaped, since=datetime(2030, 1, 1, tzinfo=timezone.utc), crypto=crypto)
    assert r6["arms"][LIVE]["n_total"] == 0 and r6["decision"]["verdict"] == "not_decidable"
    assert PRE_REGISTERED["min_g"] == MIN_N and "ENTRY DAYS" in PRE_REGISTERED["rule"]
    assert "REFUTED" in PRE_REGISTERED["mechanism"], "the refuted mechanism must stay named"
    with open(os.path.abspath(__file__)) as fh:
        src = fh.read()
    for banned in ("write_levers", "get_lever(", "market_open", "save_state(", "publish("):
        assert src.count(banned) <= 1, banned
    print("study_mum_noncrypto_sleeve selftest OK — planted sleeve CUT, placebo not, winner KEPT, "
          "a BATCHED sample is one decision, the CLUSTERED bound decides, the day-matched control "
          "can flip a raw gap and is a condition, the twin is reported, t_crit by identity, "
          "class never guessed, fresh split, moves nothing")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--ledger")
    ap.add_argument("--limit", type=int, default=5000,
                    help="ledger row cap; a count equal to it is REFUSED as truncation ((qz))")
    ap.add_argument("--pooled", action="store_true",
                    help="grade the WHOLE window instead of the registered fresh sample — NOT the registered read")
    ap.add_argument("--json")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    # [(xk)] through edge_audit's ONE loader, so the (qz) truncation refusal
    # applies here too — a row count equal to the cap is a sampled ledger.
    trades = ea.load_trades(a.ledger, a.limit)
    shaped = ea.shape(trades)
    # [(xk)] THE REGISTERED READ IS THE FRESH ONE, BY DEFAULT — I21 as
    # amended at (tt): a pre-registered bucket is decided on closes taken
    # AFTER registration, never by re-mining the window that generated it.
    # `--pooled` is the explicit opt-out and is NOT the registered read.
    since = None if a.pooled else ea._ts(PRE_REGISTERED["since"])
    if a.pooled:
        print("NOTE: --pooled — this is the motivating window, not the registered read (I21).")
    res = run(shaped, since=since)
    print(render(res))
    if a.json:
        with open(a.json, "w") as fh:
            json.dump(res, fh, indent=1, default=str)
    return 0


if __name__ == "__main__":
    sys.exit(main())
