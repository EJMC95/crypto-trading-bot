#!/usr/bin/env python3
"""study_taker_divergence_stop_2026-09-02.py — price the divergence stop.

THE SIGNAL WITHOUT A PRICE (carried row `taker-divergence-stop-unpriced`).
🎫 the taker's SHADOW arm measured its short-divergence stop at +28pp reclaim
excess and +2.10% held at 24h over n=22 — stopped shorts tend to reclaim, so
the stop looks like it cuts winners. That is a SIGNAL. Its VALUE is what a
wider stop would have earned through the taker's OWN decision code over the
recorded scout tape — and `lighter_ticket_replay` is the calibrated
instrument for exactly that question (a candle walk has no short branch).

METHOD. Entries are HELD CONSTANT by construction — every arm replays the
same tape through the same entry gates with the same up-resolver, so the
ONLY variable is `tt.STOP_LOSS` (the reversion bracket's stop, which
divergence uses; the trend exit governs breakout lenses and is untouched).
Candidates: the cage-reachable -0.04 (`taker.sl` lo), then -0.05/-0.06/OFF
as informational reach beyond the cage. Scored `_marked`-style (closed net +
end-of-tape unrealized at last marks — the IMB-10 rule, so a wide stop
cannot 'win' by deferring losses past the tape), full + both halves, with
the divergence lens sliced out beside the whole book.

CALIBRATION GATE ((gx): a harness that cannot reproduce what DID happen may
not say what WOULD have). The baseline replay's divergence exits are compared
against the SHADOW book's real divergence closes over the same window; beyond
tolerance the study REFUSES to recommend — it still prints, labelled REFUSED.

Read-only. Touches no bot, no lever, no ledger. Acting on a positive verdict
is a separate, recorded act (`taker.sl` is a shadow-lane lever, cage
[-0.04, -0.02]).

Usage:
  DATABASE_URL=... python3 scripts/study_taker_divergence_stop_2026-09-02.py
  python3 scripts/study_taker_divergence_stop_2026-09-02.py --selftest
"""
import argparse
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import lighter_ticket_replay as rp        # noqa: E402
import lighter_ticket_taker as tt         # noqa: E402

#: shipped first, then the cage-reachable notch, then informational reach.
SL_GRID = [None, -0.04, -0.05, -0.06, -0.99]      # None = shipped (baseline)
#: |replayed - realised| divergence mean tolerance, percentage points. The
#: exit-sweep calibration gate uses the same order of magnitude; beyond this
#: the instrument may describe, never recommend.
CALIB_TOL_PP = 0.60


def _marked(rep):
    """closed net + end-of-tape unrealized — the tuner's own IMB-10 metric."""
    return rep["closed_net"] + float(rep.get("unrealized") or 0.0)


def _div(rep):
    """The divergence lens bucket (side-pooled, as the replay reports it)."""
    return (rep.get("lenses") or {}).get("divergence") or {}


def run_arm(tape, sl, up_resolver):
    """Replay with tt.STOP_LOSS patched; always restores (replay_with's rule)."""
    saved = tt.STOP_LOSS
    try:
        if sl is not None:
            tt.STOP_LOSS = sl
        mid = len(tape) // 2
        full = rp.replay(tape, up_resolver=up_resolver)
        h1 = rp.replay(tape[:mid], up_resolver=up_resolver)
        h2 = rp.replay(tape[mid:], up_resolver=up_resolver)
        return {"sl": sl if sl is not None else saved,
                "full": _marked(full), "h1": _marked(h1), "h2": _marked(h2),
                "div": _div(full), "rep": full}
    finally:
        tt.STOP_LOSS = saved


def realised_divergence(window_h):
    """The shadow book's REAL divergence closes over ~the tape window:
    (n, mean_pct) or (0, None). Reads the durable ledger via bot_pnl_store."""
    import datetime as dt
    import bot_pnl_store as store
    # limit 20000: 4000 most-recent rows fleet-wide spans ~a week and
    # missed the taker's own 12-20 Aug divergence closes on first run.
    rows = store.fetch_paper_trades(limit=20000) or []
    cut = dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=window_h)
    pcts = []
    for r in rows:
        if r.get("bot") != "lighter-ticket-taker-lshadow":
            continue
        reason = str(r.get("reason") or "")
        if "divergence" not in reason:
            continue
        ts = str(r.get("closed_at") or r.get("close_ts") or "")
        try:
            t = dt.datetime.fromisoformat(ts.replace("Z", "+00:00"))
            if t.tzinfo is None:
                t = t.replace(tzinfo=dt.timezone.utc)
        except ValueError:
            continue
        if t < cut:
            continue
        p = r.get("profit_ratio") if r.get("profit_ratio") is not None \
            else r.get("pnl_pct")
        if isinstance(p, (int, float)):
            pcts.append(100.0 * float(p))
    n = len(pcts)
    return n, (sum(pcts) / n if n else None)


def _selftest():
    assert _marked({"closed_net": 1.0, "unrealized": 0.5}) == 1.5
    assert _marked({"closed_net": 1.0, "unrealized": None}) == 1.0
    assert _div({"lenses": {"divergence": {"net": 2.0}}}) == {"net": 2.0}
    assert _div({}) == {}
    # the shipped arm must be FIRST in the grid so every delta is vs shipped
    assert SL_GRID[0] is None
    # patch/restore: run_arm must not leak a mutated stop
    keep = tt.STOP_LOSS
    try:
        run_arm([], -0.06, None)
    except Exception:  # noqa: BLE001 — an empty tape may raise; leak is the test
        pass
    assert tt.STOP_LOSS == keep, "run_arm leaked a patched STOP_LOSS"
    print("selftest OK")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--hours", type=int, default=336)
    ap.add_argument("--limit", type=int, default=12000)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    tape, tape_src = rp.load_tape(source="auto", hours=a.hours, limit=a.limit)
    if not tape:
        print("NO TAPE — nothing to price (needs DATABASE_URL)")
        return 2
    span_h = (tape[-1][0] - tape[0][0]).total_seconds() / 3600.0
    print(f"tape[{tape_src}]: {len(tape)} snapshots, {span_h:.1f}h "
          f"({tape[0][0]} -> {tape[-1][0]})")
    # NO up-resolver, deliberately: it costs minutes of throttled candle
    # fetches and governs only the breakout lenses. With it absent those
    # lenses stay dark IDENTICALLY across every arm, so the exit-only delta
    # this study prices is unaffected; the second-order slot-competition
    # difference vs production is declared, not hidden.
    up = None

    arms = [run_arm(tape, sl, up) for sl in SL_GRID]
    base = arms[0]

    # calibration: the baseline's replayed divergence vs the book's record
    d0 = base["div"]
    dn = int(d0.get("closed") or 0)
    _pcts = d0.get("pnl_pcts") or []
    if _pcts and dn:
        dmean = 100.0 * sum(_pcts) / dn
    elif dn:                       # pnl_pcts absent: derive from net/clip —
        dmean = 100.0 * float(d0.get("net") or 0.0) / (dn * (tt.CLIP_USD or 1))
    else:                          # first run printed a fake +0.000% here
        dmean = None
    rn, rmean = realised_divergence(span_h)
    ok = (dmean is not None and rmean is not None
          and abs(dmean - rmean) <= CALIB_TOL_PP)
    print(f"\ncalibration: replayed divergence n={dn} mean="
          f"{'—' if dmean is None else f'{dmean:+.3f}%'} vs realised n={rn} "
          f"mean={'—' if rmean is None else f'{rmean:+.3f}%'} "
          f"(tol {CALIB_TOL_PP}pp) -> {'OK' if ok else 'REFUSED'}")

    hdr = (f"\n{'SL':>7s} {'full$':>8s} {'h1$':>8s} {'h2$':>8s} "
           f"{'div n':>6s} {'div$':>8s} {'div sl_n':>8s}  vs shipped")
    print(hdr)
    print("-" * len(hdr))
    for arm in arms:
        d = arm["div"]
        sl_exits = (d.get("exits") or {}).get("sl", 0)
        tag = "  <- SHIPPED" if arm is base else f"  {arm['full']-base['full']:>+8.2f}"
        print(f"{arm['sl']:>7.2f} {arm['full']:>8.2f} {arm['h1']:>8.2f} "
              f"{arm['h2']:>8.2f} {int(d.get('closed') or 0):>6d} "
              f"{float(d.get('net') or 0.0):>8.2f} {sl_exits:>8d}{tag}")

    if not ok:
        print("\nVERDICT: REFUSED — the instrument does not reproduce the "
              "book's own divergence record on this window, so it may not "
              "recommend a stop. The table above is descriptive only.")
        return 1
    best = max(arms[1:2], key=lambda x: x["full"])   # the cage-reachable notch
    both = best["h1"] > base["h1"] and best["h2"] > base["h2"]
    print(f"\nVERDICT: cage-reachable SL -0.04 delta "
          f"{best['full']-base['full']:+.2f} full, both-halves "
          f"{'YES' if both else 'no'} — "
          f"{'candidate for the taker.sl lever' if both else 'no action'}; "
          "beyond-cage rows are reach, not recommendations.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
