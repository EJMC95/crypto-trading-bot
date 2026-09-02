#!/usr/bin/env python3
"""STUDY (read-only, moves nothing): the brain's EXPANSION floors.

[2-Sep (wu)] The edge audit's growth half named this measurement: how many
(bot, tag) buckets qualify at each expand rung of `brain_stats.EXPAND_LADDER`,
which bar binds for the ones that do not, and what qualifying buckets earned
FORWARD — on the trades OPENED in the day after each qualification, which is
what a published multiplier actually sizes — under the shipped ladder and
three pre-declared alternatives, judged against each bucket's OWN era mean
(I25: never against the window that produced the qualification).

OWNERS ARE IMPORTED, NEVER COPIED: `bot_pnl_store.split_reason` (the bucket
key), `bot_pnl_store.is_quarantined` + `golive_readiness.is_phantom_close`
(the graded sample), `bot_learn.era_epoch_for` / `_epoch` / the n floors,
`brain_stats.weighted_bucket_episodes` / `eb_prior` / `qualify_v3` (the
brain's own evidence and verdict). The variant ladders are by definition not
the owner's; the owner's verdict is cross-checked against this file's copy of
the shipped ladder on every bucket-day and the disagreement count is printed.

CALIBRATION GATE (the (gx) rule — a harness that cannot reproduce what DID
happen may not say what WOULD have): every multiplier the live brain currently
publishes must reproduce here (mult exact, n exact, t within 0.02) or the
study REFUSES (exit 2) and prints nothing forward-looking.

LIVENESS: the brain generates for LIVING bots only (retired set + 7d close
recency). A bucket is eligible on walk day D iff its bot closed a trade in the
7 days before D — the same rule, so a book that stopped trading stops
qualifying on its own, and a retired CEX-era ledger cannot carry the table.

    python3 scripts/study_brain_floors_2026-09-02.py --ledger trades.json --bus bus.json
    python3 scripts/study_brain_floors_2026-09-02.py --feed https://.../trades.json --bus https://.../bus.json
"""
import argparse, bisect, collections, json, os, sys, urllib.request
from datetime import datetime, timezone, timedelta

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT); sys.path.insert(0, os.path.join(ROOT, "scripts"))
import bot_pnl_store as store          # noqa: E402
import bot_learn as bl                 # noqa: E402
import brain_stats as bs               # noqa: E402
import golive_readiness as gr          # noqa: E402

LIVENESS_S = 7 * 86400.0
DEFAULT_FEED = "https://pnl-dashboard-production-858c.up.railway.app/trades.json?source=paper&limit=5000"
DEFAULT_BUS = "https://pnl-dashboard-production-858c.up.railway.app/bus.json"

# The shipped ladder, strongest rung first, exactly as qualify_v3 walks it:
# the (sm)/(sn) table, then the 1.5x and 1.25x rungs on the EXP_* bars.
SHIPPED = list(bs.EXPAND_LADDER) + [
    (1.5, bs.EXP_HARD_POST_WR, bs.EXP_HARD_W_LO, bs.EXP_HARD_T, bs.MIN_N_EFF_HARD),
    (1.25, bs.EXP_SOFT_POST_WR, bs.EXP_SOFT_W_LO, bs.EXP_SOFT_T, bs.MIN_N_EFF_HARD)]

VARIANTS = {
    "V0 shipped": None,                                             # owner verdict
    "V1 expectancy-only (win-rate bars dropped)": dict(use_wr=False),
    "V2 expectancy-only, every t bar -0.5": dict(use_wr=False, tshift=0.5),
    "V3 shipped, n floor 20": dict(min_n=20),
}


def _load(src):
    if src.startswith(("http://", "https://")):
        with urllib.request.urlopen(src, timeout=60) as fh:
            return json.load(fh)
    with open(src) as fh:
        return json.load(fh)


def enter_tag_of(r):
    """The ledger's bucket key, by the owner's rule: a stored tag beats the
    reason prefix ('long-funding' beats 'long'); reason-derived direction is
    the fallback for pre-stamp rows."""
    tag = r.get("tag")
    if tag:
        d, _ = store.split_reason(tag)
        if d:
            return d
    return store.split_reason(r.get("reason"))[0]


def shape(rows):
    """raw feed rows -> the brain's era-scoped tagged sample, bucketed."""
    trades, dropped = [], collections.Counter()
    for r in rows:
        if r.get("side") == "skip":
            dropped["skip"] += 1; continue
        if gr.is_phantom_close(r):
            dropped["phantom"] += 1; continue
        if store.is_quarantined(r.get("bot"), r.get("pair"), r.get("closed_at")):
            dropped["quarantine"] += 1; continue
        tag = enter_tag_of(r)
        if not tag:
            dropped["untagged"] += 1; continue
        oe, ce = bl._epoch(r.get("opened_at")), bl._epoch(r.get("closed_at"))
        if oe is None or ce is None:
            dropped["no_ts"] += 1; continue
        trades.append({"bot": r["bot"], "enter_tag": tag,
                       "profit_abs": float(r.get("pnl_abs") or 0.0),
                       "profit_ratio": r.get("pnl_pct"),
                       "open_ts": r.get("opened_at"), "close_ts": r.get("closed_at"),
                       "_open_epoch": oe, "_close_epoch": ce, "pair": r.get("pair")})
    by_bot = collections.defaultdict(list)
    for t in trades:
        by_bot[t["bot"]].append(t)
    buckets = collections.defaultdict(list)
    for bot, trs in by_bot.items():
        ep = bl.era_epoch_for(bot)
        for t in trs:
            if ep is None or t["_open_epoch"] >= ep:
                buckets[(bot, t["enter_tag"])].append(t)
    closes = {b: sorted(t["_close_epoch"] for t in trs) for b, trs in by_bot.items()}
    return buckets, closes, dropped, len(rows)


def alive_at(closes, bot, when):
    cl = closes.get(bot) or []
    i = bisect.bisect_left(cl, when)
    return i > 0 and cl[i - 1] >= when - LIVENESS_S


def rung(ev, n, use_wr=True, tshift=0.0, min_n=bl.MULT_MIN_N):
    """This file's copy of the shipped ladder, parameterised for the variants."""
    if ev["pnl_w"] <= 0 or n < min_n:
        return None
    for m, pw, wl, tb, ne in SHIPPED:
        ok = ev["n_eff"] >= ne and ev["t"] >= tb - tshift
        if use_wr:
            ok = ok and ev["post_wr"] > pw and ev["w_lo"] > wl
        if ok:
            return m
    return None


def binding_bar(ev, n):
    """The first failing bar for the 1.25x rung, in the order the owner checks."""
    if ev["pnl_w"] <= 0:
        return "pnl_w<=0"
    if n < bl.MULT_MIN_N:
        return f"n {n}<{bl.MULT_MIN_N}"
    if ev["n_eff"] < bs.MIN_N_EFF_HARD:
        return f"n_eff {ev['n_eff']}<{bs.MIN_N_EFF_HARD}"
    if not ev["post_wr"] > bs.EXP_SOFT_POST_WR:
        return f"post_wr {ev['post_wr']}<={bs.EXP_SOFT_POST_WR}"
    if not ev["w_lo"] > bs.EXP_SOFT_W_LO:
        return f"w_lo {ev['w_lo']}<={bs.EXP_SOFT_W_LO}"
    if ev["t"] < bs.EXP_SOFT_T:
        return f"t {ev['t']}<{bs.EXP_SOFT_T}"
    return "clears 1.25x"


def evaluate(buckets, closes, when, min_hist=8, alive_only=True):
    """key -> (stats, n_hist, owner_mult, evidence) at `when`, from closes before it."""
    st = {}
    for key, trs in buckets.items():
        if alive_only and not alive_at(closes, key[0], when):
            continue
        hist = [t for t in trs if t["_close_epoch"] < when]
        if len(hist) < min_hist:
            continue
        st[key] = (bs.weighted_bucket_episodes(hist, when, bl.HALF_LIFE_DAYS, bl.EP_GAP_SEC), len(hist))
    all_st = [s for s, _ in st.values()]
    out = {}
    for key, (s, n) in st.items():
        bot, tag = key
        prior = bs.eb_prior([ss for (b, tg), (ss, _) in st.items() if tg == tag and b != bot],
                            [ss for (b, tg), (ss, _) in st.items() if b == bot and tg != tag],
                            [ss for ss in all_st if ss is not s])
        m, ev = bs.qualify_v3(s, prior, min_n=bl.MULT_MIN_N, soft_n=bl.MULT_SOFT_N, expand=True)
        out[key] = (s, n, m, ev)
    return out


def calibrate(buckets, closes, bus):
    """Every published mult must reproduce at the payload's own instant."""
    p = (bus.get("brain_stake_mults") or bus.get("brain-stake-mults") or {})
    p = p.get("payload", p)
    upd = bl._epoch(p.get("updated"))
    mults = p.get("mults") or {}
    if not upd or not isinstance(mults, dict):
        return None, "no brain-stake-mults payload with `updated` + `mults` in the bus", []
    ev_all = evaluate(buckets, closes, upd, alive_only=False)
    rows, ok = [], True
    for bot, tags in mults.items():
        if not isinstance(tags, dict):
            continue
        for tag, rec in tags.items():
            want = rec.get("mult") if isinstance(rec, dict) else rec
            s, n, m, ev = ev_all.get((bot, tag), (None, 0, None, {}))
            good = (m == want and n == (rec.get("n") if isinstance(rec, dict) else n)
                    and abs((ev.get("t") or 0.0) - float((rec.get("t") if isinstance(rec, dict) else ev.get("t")) or 0.0)) <= 0.02)
            ok = ok and good
            rows.append((bot, tag, want, m, rec.get("n") if isinstance(rec, dict) else None, n,
                         rec.get("t") if isinstance(rec, dict) else None, ev.get("t"), good))
    return ok, f"payload {p.get('updated')} run-mode {p.get('mode')} engine {p.get('engine')}", rows


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger", help="trades.json (paper) file; default: fetch --feed")
    ap.add_argument("--feed", default=DEFAULT_FEED)
    ap.add_argument("--bus", default=DEFAULT_BUS, help="bus.json file or URL (calibration targets)")
    ap.add_argument("--start", default="2026-07-01", help="first walk day (UTC)")
    ap.add_argument("--out", help="write the full result as JSON here")
    a = ap.parse_args(argv)

    raw = _load(a.ledger or a.feed)
    rows = raw["trades"] if isinstance(raw, dict) else raw
    bus = _load(a.bus)
    buckets, closes, dropped, n_raw = shape(rows)
    END = max(t["_close_epoch"] for trs in buckets.values() for t in trs)
    print(f"rows {n_raw} -> era-scoped tagged trades {sum(len(v) for v in buckets.values())} in {len(buckets)} buckets; "
          f"dropped {dict(dropped)}; ledger end {datetime.fromtimestamp(END, timezone.utc):%Y-%m-%d %H:%MZ}")
    print(f"floors: MULT_MIN_N={bl.MULT_MIN_N} MULT_SOFT_N={bl.MULT_SOFT_N} MIN_N_EFF_HARD={bs.MIN_N_EFF_HARD} "
          f"half_life={bl.HALF_LIFE_DAYS}d ep_gap={bl.EP_GAP_SEC}s; ladder {[(m, pw, wl, t, ne) for m, pw, wl, t, ne in SHIPPED]}")

    ok, note, rows_c = calibrate(buckets, closes, bus)
    print(f"\n== CALIBRATION against the live brain ({note}) ==")
    for bot, tag, want, got, n_live, n_here, t_live, t_here, good in rows_c:
        print(f"  {'OK ' if good else 'BAD'} {bot:30s} {tag:22s} mult live {want} here {got} | n live {n_live} here {n_here} | t live {t_live} here {t_here}")
    if not ok:
        print("REFUSED: the study does not reproduce the brain's own published mults; nothing forward-looking is printed.")
        return 2
    if not rows_c:
        print("  (brain publishes no mults — nothing to calibrate against; continuing, stated)")

    # ---- Q1: today ----
    today = evaluate(buckets, closes, END + 1.0)
    print("\n== TODAY: living buckets with n>=15, by t  (V0 = owner rung | binding bar for 1.25x | V1 rung) ==")
    tbl = sorted(((ev["t"], key, n, m, ev) for key, (s, n, m, ev) in today.items() if n >= 15), key=lambda r: -r[0])
    for t, key, n, m, ev in tbl:
        print(f"  t={t:5.2f} {key[0][:28]:28s} {key[1][:22]:22s} n={n:3d} n_eff={ev['n_eff']:5.1f} post={ev['post_wr']:.3f} "
              f"w_lo={ev['w_lo']:.3f} pnl_w={ev['pnl_w']:8.2f} | V0 {str(m):5s} | {binding_bar(ev, n):24s} | V1 {rung(ev, n, use_wr=False)}")

    # ---- Q2: forward walk ----
    start = datetime.strptime(a.start, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    end = datetime.fromtimestamp(END, timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    own_mean = {k: sum((t["profit_ratio"] or 0.0) for t in v) / len(v) for k, v in buckets.items()}
    Z = lambda: {"days": collections.Counter(), "n": collections.Counter(), "pct": collections.Counter(),
                 "abs": collections.Counter(), "uplift": collections.Counter(), "own": collections.Counter()}
    res = {v: Z() for v in VARIANTS}
    per_bucket = {v: collections.defaultdict(lambda: {"rungs": set(), "days": 0, "n": 0, "pct": 0.0, "abs": 0.0, "uplift": 0.0}) for v in VARIANTS}
    ctrl = {"days": 0, "n": 0, "pct": 0.0, "own": 0.0}
    agree = disagree = 0
    D = start
    while D < end:
        D_ts = D.timestamp(); D1 = D_ts + 86400.0
        for key, (s, n, m_owner, ev) in evaluate(buckets, closes, D_ts).items():
            fwd = [t for t in buckets[key] if D_ts <= t["_open_epoch"] < D1]
            fpct = sum((t["profit_ratio"] or 0.0) for t in fwd); fabs = sum(t["profit_abs"] for t in fwd)
            m0 = m_owner if (m_owner is not None and m_owner > 1.0) else None
            if m0 == rung(ev, n):
                agree += 1
            else:
                disagree += 1
            if rung(ev, n, use_wr=False) is None and ev["pnl_w"] > 0 and n >= bl.MULT_MIN_N:
                ctrl["days"] += 1; ctrl["n"] += len(fwd); ctrl["pct"] += fpct; ctrl["own"] += own_mean[key] * len(fwd)
            for vname, kw in VARIANTS.items():
                m = m0 if kw is None else rung(ev, n, **kw)
                if m is None:
                    continue
                r = res[vname]
                r["days"][m] += 1; r["n"][m] += len(fwd); r["pct"][m] += fpct; r["abs"][m] += fabs
                r["uplift"][m] += (m - 1.0) * fabs; r["own"][m] += own_mean[key] * len(fwd)
                pb = per_bucket[vname][key]
                pb["rungs"].add(m); pb["days"] += 1; pb["n"] += len(fwd); pb["pct"] += fpct; pb["abs"] += fabs; pb["uplift"] += (m - 1.0) * fabs
        D += timedelta(days=1)

    print(f"\n== FORWARD WALK {start:%d-%b} -> {end:%d-%b} daily, LIVING buckets only; owner-vs-copy on V0: {agree} agree / {disagree} disagree ==")
    print("  variant | rung | bucket-days | fwd trades | fwd %/trade | own-mean %/trade | excess pp | fwd $ at 1x | extra $ at rung")
    out_fwd = {}
    for vname, r in res.items():
        if not r["days"]:
            print(f"  {vname}: never qualifies"); out_fwd[vname] = {}; continue
        for m in sorted(r["days"], reverse=True):
            n = r["n"][m]; fw = (r["pct"][m] / n * 100) if n else float("nan"); own = (r["own"][m] / n * 100) if n else float("nan")
            print(f"  {vname[:44]:44s} | {m:4} | {r['days'][m]:5d} | {n:5d} | {fw:+8.3f} | {own:+8.3f} | {fw - own:+7.3f} | {r['abs'][m]:+8.2f} | {r['uplift'][m]:+8.2f}")
        tn = sum(r["n"].values()); tp = sum(r["pct"].values())
        print(f"  {'':44s} | ALL  | {sum(r['days'].values()):5d} | {tn:5d} | {(tp / tn * 100 if tn else float('nan')):+8.3f} | "
              f"{(sum(r['own'].values()) / tn * 100 if tn else float('nan')):+8.3f} | {'':7s} | {sum(r['abs'].values()):+8.2f} | {sum(r['uplift'].values()):+8.2f}")
        out_fwd[vname] = {str(m): {"days": r["days"][m], "n": r["n"][m], "pct_sum": r["pct"][m], "abs": r["abs"][m], "uplift": r["uplift"][m]} for m in r["days"]}
    if ctrl["n"]:
        print(f"  CONTROL (positive, n>=30, NOT qualified under V1): {ctrl['days']} bucket-days, {ctrl['n']} fwd trades, "
              f"fwd {ctrl['pct'] / ctrl['n'] * 100:+.3f}%/trade vs own mean {ctrl['own'] / ctrl['n'] * 100:+.3f}%")
    print("\n== WHO QUALIFIED (per variant, per bucket): rungs reached | bucket-days | fwd trades | fwd %/trade | own mean | extra $ at rung ==")
    out_pb = {}
    for vname, pbs in per_bucket.items():
        print(f"  -- {vname} --")
        out_pb[vname] = []
        for key, pb in sorted(pbs.items(), key=lambda kv: -kv[1]["uplift"]):
            fw = (pb["pct"] / pb["n"] * 100) if pb["n"] else float("nan")
            print(f"     {key[0][:28]:28s} {key[1][:22]:22s} rungs {sorted(pb['rungs'])} | {pb['days']:3d} | {pb['n']:4d} | {fw:+8.3f} | {own_mean[key] * 100:+8.3f} | {pb['uplift']:+8.2f}")
            out_pb[vname].append({"bot": key[0], "tag": key[1], "rungs": sorted(pb["rungs"]), "days": pb["days"], "n": pb["n"],
                                  "fwd_pct": fw, "own_mean_pct": own_mean[key] * 100, "uplift": pb["uplift"]})
    if a.out:
        payload = {"calibration_ok": ok,
                   "today": [{"bot": k[0], "tag": k[1], "n": n, "mult": m, **ev} for k, (s, n, m, ev) in today.items()],
                   "forward": out_fwd, "per_bucket": out_pb, "control": ctrl, "agree": agree, "disagree": disagree}
        with open(a.out, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, indent=1, default=str)
        print(f"\nwrote {a.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
