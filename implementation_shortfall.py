#!/usr/bin/env python3
"""
implementation_shortfall.py — 📏 the live-vs-shadow EXECUTION-QUALITY tracker.

WHY (2026-07-15, operator: "is the live Funding Farmer slipping on exits?").
The live bot and its -lshadow twin run the SAME strategy on the SAME coins at
~the same time — the ONLY difference is execution: live fills at real book
prices (crossing the spread, paying slippage + real funding); shadow fills at
Lighter mark. So the per-trade return gap between them, on coins BOTH arms
closed, IS the implementation shortfall — the real cost of trading for money.

market_context already fires a threshold ALERT when the whole-book gap blows
past 1.5pp. This organ is the continuous TRACKER behind that alert: it
publishes the gap as a persistent metric (+ per-coin breakdown + a rolling
verdict + history) so "is live slipping, and where?" gets a clean, dated
answer instead of a one-shot warning — and it DECOMPOSES the gap into the
ENTRY side and the EXIT side once fill prices are on the ledger (funding bot
records them since 2026-07-15), so "slipping on exits" is answerable, not
guessed.

VERDICTS (per-trade gap = live − shadow, weighted by paired closes):
  insufficient   too few overlapping coins/closes to judge (stays quiet)
  clean          |gap| <= CLEAN_PP — live executes as well as the model
  live-ahead     gap > +CLEAN_PP — live BEATS shadow (real, seen 15-Jul)
  live-slipping  gap < −CLEAN_PP — live realizes less per trade than the
                 model; sustained across SUSTAIN cycles -> phone alert
Decomposition (when fill prices present): entry_slip_bps / exit_slip_bps —
how much of the shortfall the live arm paid getting IN vs getting OUT.

ADVISORY. Read-only on the ledger; publishes bot_state 'impl-shortfall'
(+ history), surfaced on the board. Run-once; run_all.sh loops it.
--selftest is offline.
"""
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store

KEY = "impl-shortfall"
TTL_SEC = int(os.environ.get("SHORTFALL_TTL_SEC", "3600"))
LIVE = os.environ.get("SHORTFALL_LIVE", "perps-funding-lighter-lighter")
SHADOW = os.environ.get("SHORTFALL_SHADOW", "perps-funding-lighter-lshadow")
WINDOW_DAYS = int(os.environ.get("SHORTFALL_WINDOW_DAYS", "7"))
MIN_COINS = int(os.environ.get("SHORTFALL_MIN_COINS", "2"))
MIN_CLOSES = int(os.environ.get("SHORTFALL_MIN_CLOSES", "4"))
CLEAN_PP = float(os.environ.get("SHORTFALL_CLEAN_PP", "0.5"))   # ±0.5pp/trade = clean
SUSTAIN = int(os.environ.get("SHORTFALL_SUSTAIN", "3"))         # cycles before alert
NOTIFY_GAP_H = float(os.environ.get("SHORTFALL_NOTIFY_GAP_H", "6"))


def now_ts():
    return time.time()


def _iso(ts=None):
    return datetime.fromtimestamp(ts or now_ts(), tz=timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# pure computation (selftested offline)
# ---------------------------------------------------------------------------

def compute_shortfall(per_coin):
    """per_coin: {coin: {'live': {'avg_pct', 'n', 'entry', 'exit'},
                         'shadow': {'avg_pct', 'n', 'entry', 'exit'}}}.
    Returns the overall weighted gap (live − shadow, in pp/trade), the
    per-coin gaps, overlap/close counts, entry/exit slip decomposition (bps,
    where both arms carry prices), and a verdict. Pure."""
    coins, diffs, weights = {}, [], []
    entry_slips, exit_slips, dw = [], [], []
    for coin, sides in sorted(per_coin.items()):
        lv, sh = sides.get("live"), sides.get("shadow")
        if not lv or not sh:
            continue
        w = min(int(lv["n"]), int(sh["n"]))
        if w <= 0:
            continue
        gap_pp = (float(lv["avg_pct"]) - float(sh["avg_pct"])) * 100.0
        coins[coin] = {"gap_pp": round(gap_pp, 3), "closes": w,
                       "live_pct": round(float(lv["avg_pct"]) * 100, 3),
                       "shadow_pct": round(float(sh["avg_pct"]) * 100, 3)}
        diffs.append(gap_pp)
        weights.append(w)
        # entry/exit decomposition (needs both arms' avg fill prices + a side)
        es, xs = _slip_bps(lv, sh)
        if es is not None:
            coins[coin]["entry_slip_bps"] = round(es, 1)
            coins[coin]["exit_slip_bps"] = round(xs, 1)
            entry_slips.append(es * w)
            exit_slips.append(xs * w)
            dw.append(w)

    n_overlap = len(coins)
    tot_w = sum(weights)
    gap = round(sum(d * w for d, w in zip(diffs, weights)) / tot_w, 3) if tot_w else None
    entry_slip = round(sum(entry_slips) / sum(dw), 1) if dw else None
    exit_slip = round(sum(exit_slips) / sum(dw), 1) if dw else None

    if n_overlap < MIN_COINS or tot_w < MIN_CLOSES:
        verdict = "insufficient"
    elif gap is None or abs(gap) <= CLEAN_PP:
        verdict = "clean"
    elif gap > 0:
        verdict = "live-ahead"
    else:
        verdict = "live-slipping"

    return {"gap_pp": gap, "verdict": verdict, "n_overlap": n_overlap,
            "paired_closes": tot_w, "coins": coins,
            "entry_slip_bps": entry_slip, "exit_slip_bps": exit_slip}


def _slip_bps(lv, sh):
    """(entry_slip_bps, exit_slip_bps) = how much WORSE the live arm's fills
    were than the shadow's, in bps, signed so POSITIVE = live paid more.
    Needs both arms' avg entry+exit price and a shared side; else (None,None).
    Buying (long): worse entry = higher price; worse exit = lower price. Short
    inverts. Shadow fills at mark, so this is the real spread/slippage cost."""
    try:
        le, lx = float(lv["entry"]), float(lv["exit"])
        se, sx = float(sh["entry"]), float(sh["exit"])
        if min(le, lx, se, sx) <= 0:
            return None, None
        side = lv.get("side") or sh.get("side") or "long"
        sgn = 1.0 if side == "long" else -1.0
        entry_bps = sgn * (le / se - 1.0) * 10_000.0      # paid more to enter
        exit_bps = sgn * (sx / lx - 1.0) * 10_000.0       # got less on exit
        return entry_bps, exit_bps
    except (TypeError, ValueError, KeyError, ZeroDivisionError):
        return None, None


# ---------------------------------------------------------------------------

def _fetch_per_coin():
    """Query paper_trades -> per_coin structure. Live=real fills, shadow=mark."""
    conn = store._get_conn()
    if conn is None:
        return {}
    per = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT bot, pair, AVG(pnl_pct), COUNT(*),
                          AVG(entry_price), AVG(exit_price),
                          MAX(side) FROM paper_trades
                   WHERE bot IN (%s, %s) AND pnl_pct IS NOT NULL
                     AND seen_at >= now() - (%s || ' days')::interval
                   GROUP BY bot, pair""",
                (LIVE, SHADOW, str(WINDOW_DAYS)))
            for bot, pair, avg_pct, n, ent, exi, side in cur.fetchall():
                arm = "live" if bot == LIVE else "shadow"
                per.setdefault(pair, {})[arm] = {
                    "avg_pct": float(avg_pct), "n": int(n),
                    "entry": float(ent) if ent is not None else None,
                    "exit": float(exi) if exi is not None else None,
                    "side": side}
    except Exception as e:  # noqa: BLE001
        print(f"[impl-shortfall] fetch failed: {e}", flush=True)
        return {}
    return per


def send_push(title, body):
    topic = os.environ.get("NTFY_TOPIC", "").strip()
    if not topic:
        return False
    try:
        server = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")
        req = urllib.request.Request(f"{server}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", "high")
        req.add_header("Tags", "straight_ruler")
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[impl-shortfall] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    rep = compute_shortfall(_fetch_per_coin())

    # sustain counter: how many consecutive cycles the verdict has been slipping
    streak = int(prior.get("slip_streak") or 0)
    streak = streak + 1 if rep["verdict"] == "live-slipping" else 0

    payload = {"updated": _iso(now), "ttl_sec": TTL_SEC, "slip_streak": streak,
               "window_days": WINDOW_DAYS, **rep}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "gap_pp": rep["gap_pp"],
                                     "verdict": rep["verdict"],
                                     "exit_slip_bps": rep["exit_slip_bps"]})
        except Exception:
            pass

    last_push = float(prior.get("last_push") or 0)
    if streak >= SUSTAIN and now - last_push >= NOTIFY_GAP_H * 3600:
        exitmsg = (f"; exit-slip {rep['exit_slip_bps']}bps / entry-slip "
                   f"{rep['entry_slip_bps']}bps" if rep["exit_slip_bps"] is not None
                   else " (fill-price decomposition still accruing)")
        if send_push(f"📏 LIVE slipping vs shadow {rep['gap_pp']}pp/trade",
                     f"{streak} cycles; {rep['paired_closes']} paired closes "
                     f"over {rep['n_overlap']} coins{exitmsg}"):
            payload["last_push"] = now
            store.save_state(KEY, payload)

    d = (f" exit-slip {rep['exit_slip_bps']}bps" if rep["exit_slip_bps"] is not None else "")
    print(f"[impl-shortfall] {_iso(now)} verdict={rep['verdict']} "
          f"gap={rep['gap_pp']}pp/trade over {rep['n_overlap']} coins "
          f"({rep['paired_closes']} closes){d} streak={streak}", flush=True)
    return payload


# ---------------------------------------------------------------------------

def _selftest():
    # clean: live and shadow near-identical per trade
    clean = {"SOL": {"live": {"avg_pct": 0.019, "n": 3},
                     "shadow": {"avg_pct": 0.020, "n": 5}},
             "ETH": {"live": {"avg_pct": 0.010, "n": 4},
                     "shadow": {"avg_pct": 0.011, "n": 4}}}
    r = compute_shortfall(clean)
    assert r["verdict"] == "clean" and abs(r["gap_pp"] + 0.1) < 0.05, r

    # live-slipping: live realizes ~2pp less per trade, enough closes
    slip = {"WIF": {"live": {"avg_pct": -0.02, "n": 4},
                    "shadow": {"avg_pct": 0.0, "n": 4}},
            "kBONK": {"live": {"avg_pct": -0.015, "n": 3},
                      "shadow": {"avg_pct": 0.005, "n": 3}}}
    r2 = compute_shortfall(slip)
    assert r2["verdict"] == "live-slipping" and r2["gap_pp"] < -1.0, r2

    # live-ahead: the real 15-Jul shape (live per-trade materially > shadow)
    ahead = {"a": {"live": {"avg_pct": 0.013, "n": 7},
                   "shadow": {"avg_pct": 0.006, "n": 14}},
             "b": {"live": {"avg_pct": 0.012, "n": 5},
                   "shadow": {"avg_pct": 0.005, "n": 5}}}
    ra = compute_shortfall(ahead)
    assert ra["verdict"] == "live-ahead" and ra["gap_pp"] > 0.5, ra

    # insufficient: only one overlapping coin
    thin = {"x": {"live": {"avg_pct": -0.05, "n": 9},
                  "shadow": {"avg_pct": 0.0, "n": 9}}}
    assert compute_shortfall(thin)["verdict"] == "insufficient"

    # a coin present on only one arm is ignored (no pairing)
    onearm = dict(clean, ONLY={"live": {"avg_pct": 0.9, "n": 9}})
    assert "ONLY" not in compute_shortfall(onearm)["coins"]

    # ENTRY/EXIT decomposition: a long where live bought higher (worse entry)
    # and sold lower (worse exit) than the shadow's mark fills
    dec = {"SOL": {
        "live":   {"avg_pct": -0.01, "n": 4, "side": "long",
                   "entry": 100.5, "exit": 99.5},
        "shadow": {"avg_pct": 0.0, "n": 4, "side": "long",
                   "entry": 100.0, "exit": 100.0}}}
    rd = compute_shortfall(dec)
    assert rd["entry_slip_bps"] is not None and rd["entry_slip_bps"] > 0, rd  # paid more in
    assert rd["exit_slip_bps"] > 0, rd                                        # got less out
    assert abs(rd["entry_slip_bps"] - 50.0) < 0.1                             # 100.5/100 - 1
    # a short inverts: worse entry = sold LOWER
    sh = {"WIF": {
        "live":   {"avg_pct": -0.01, "n": 4, "side": "short",
                   "entry": 99.5, "exit": 100.5},
        "shadow": {"avg_pct": 0.0, "n": 4, "side": "short",
                   "entry": 100.0, "exit": 100.0}}}
    assert compute_shortfall(sh)["entry_slip_bps"] > 0

    # missing prices -> no decomposition, but the pnl gap still computes
    assert compute_shortfall(clean)["exit_slip_bps"] is None
    print("implementation_shortfall selftest OK (clean/slipping/ahead/"
          "insufficient, one-arm ignored, entry+exit decomposition long+short)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
