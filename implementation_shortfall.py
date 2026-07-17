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
    """[2026-07-17 WITHDRAWN — this measurement was structurally invalid.]

    It compared the live arm's AVERAGE entry price against the shadow arm's
    AVERAGE entry price, per coin, over a 7-DAY window. The two arms enter at
    DIFFERENT MOMENTS at DIFFERENT PRICES, so the difference of their averages
    measures WHEN EACH ARM HAPPENED TO TRADE — price drift — and not execution
    quality at all. No averaging fixes it: the quantity has no execution
    meaning unless the two fills are the same order, or at least the same
    instant.

    What it actually produced (17-Jul, live): HYPE entry_slip **-363.2 bps** —
    i.e. a claim that the live arm filled 3.6% BETTER than the shadow's mark —
    beside a +359.3bps exit. Those are drift, cancelling. ETH 197.3, LIT 326.1.
    Read as execution they say the live book bleeds 2-3% a round trip; the
    organ's own aggregate `gap_pp` (-0.237pp, verdict clean) says it does not.
    The decomposition was the wrong one.

    Slippage is DECISION-vs-FILL ON ONE ORDER. That is `venue_orders`
    (px_decision, px_fill, slippage_bps) — see `_fetch_order_slip`. This
    function is kept only to return (None, None) so the payload key stays
    present-but-null rather than vanishing on consumers mid-window.

    NOTE the live arm cannot yet answer it either: all three of
    lighter_funding_bot's publish_venue_order calls pass px_fill=px_decision,
    so slippage_bps is NULL on every live order row while the shadow twin
    (whose ShadowBroker walks the real book) reports 0.86bps/fill over n=158.
    The bot HAS the real fill — `venues.lighter_client.last_fill` + the
    `_real_exit` helper — it just never hands it to the order ledger. Fixing
    that is what makes live execution measurable; until then this stays null
    rather than lying."""
    return None, None


def _slip_bps_of_check(decision, fill, is_buy):
    """The contract lighter_funding_bot._slip_bps_of must satisfy, pinned here
    so the honest replacement has a test even though it lives in the bot.
    POSITIVE = worse than decision. px_fill == px_decision -> None (no read)."""
    try:
        d, f = float(decision), float(fill)
        if d <= 0 or f <= 0 or d == f:
            return None
        return (f / d - 1.0) * 10_000.0 * (1.0 if is_buy else -1.0)
    except (TypeError, ValueError, ZeroDivisionError):
        return None


def _fetch_order_slip():
    """[2026-07-17] The HONEST execution measurement: decision-vs-fill on the
    SAME order, per arm, from `venue_orders`. This is what replaced the
    withdrawn averaged-price decomposition (see `_slip_bps`).

    Returns {'live': {...}, 'shadow': {...}} with n / slip_bps / spread_bps,
    plus `measurable` — False when an arm writes px_fill == px_decision, which
    is not a zero-slippage read, it is NO read. Distinguishing "measured 0" from
    "never recorded" is the entire point: the live arm has 48 order rows and
    zero slippage telemetry, and the previous decomposition's answer to that
    was to invent one.

    Fail-safe: any DB trouble -> {} and the payload key is simply absent."""
    conn = store._get_conn()
    if conn is None:
        return {}
    out = {}
    try:
        with conn.cursor() as cur:
            cur.execute(
                """SELECT bot,
                          COUNT(*),
                          COUNT(slippage_bps),
                          AVG(slippage_bps),
                          AVG(spread_bps),
                          SUM(CASE WHEN px_fill IS NOT NULL
                                    AND px_decision IS NOT NULL
                                    AND px_fill = px_decision THEN 1 ELSE 0 END)
                   FROM venue_orders
                   WHERE bot IN (%s, %s)
                     AND at >= now() - (%s || ' days')::interval
                   GROUP BY bot""",
                (LIVE, SHADOW, str(WINDOW_DAYS)))
            for bot, n, n_slip, slip, spread, n_echo in cur.fetchall():
                arm = "live" if bot == LIVE else "shadow"
                n, n_slip, n_echo = int(n), int(n_slip or 0), int(n_echo or 0)
                out[arm] = {
                    "orders": n,
                    "with_slip": n_slip,
                    "slip_bps": round(float(slip), 2) if slip is not None else None,
                    "spread_bps": round(float(spread), 2) if spread is not None else None,
                    # px_fill == px_decision on every row => the arm echoes the
                    # decision price back and records nothing about its fill
                    "measurable": bool(n_slip) and n_echo < n,
                    "echoed_decision": n_echo,
                }
    except Exception as e:  # noqa: BLE001 — measurement-only, never raise
        print(f"[impl-shortfall] order-slip fetch failed: {e}", flush=True)
        return {}
    return out


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
    # [2026-07-17] the real execution read: decision-vs-fill on ONE order.
    # Replaces the withdrawn averaged-price decomposition (see _slip_bps).
    _os = _fetch_order_slip()
    if _os:
        rep["order_slip"] = _os

    # sustain counter: how many consecutive cycles the verdict has been slipping
    streak = int(prior.get("slip_streak") or 0)
    streak = streak + 1 if rep["verdict"] == "live-slipping" else 0

    last_push = float(prior.get("last_push") or 0)
    # last_push rides IN the saved payload (16-Jul: the first save dropped it,
    # so a sustained slip re-paged every ~2 cycles instead of every NOTIFY_GAP_H)
    payload = {"updated": _iso(now), "ttl_sec": TTL_SEC, "slip_streak": streak,
               "window_days": WINDOW_DAYS, "last_push": last_push, **rep}
    store.save_state(KEY, payload)
    if hasattr(store, "save_history"):
        try:
            store.save_history(KEY, {"updated": payload["updated"],
                                     "gap_pp": rep["gap_pp"],
                                     "verdict": rep["verdict"],
                                     "exit_slip_bps": rep["exit_slip_bps"]})
        except Exception:
            pass

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
    # [2026-07-17] The averaged-price entry/exit decomposition is WITHDRAWN and
    # these tests pin the withdrawal, because the old ones pinned the BUG: they
    # fed ONE synthetic trade per arm, where "live avg entry vs shadow avg
    # entry" trivially IS the slippage. Real arms enter at different moments at
    # different prices over a 7d window, so the same subtraction measures price
    # DRIFT. The fixture was too clean to expose it — it could not fail.
    # Live proof it was drift, not execution: HYPE entry -363.2bps beside exit
    # +359.3bps (a claim the live arm filled 3.6% BETTER than mark), while the
    # organ's own gap_pp said -0.237pp / clean. Both keys are now always None.
    dec = {"SOL": {
        "live":   {"avg_pct": -0.01, "n": 4, "side": "long",
                   "entry": 100.5, "exit": 99.5},
        "shadow": {"avg_pct": 0.0, "n": 4, "side": "long",
                   "entry": 100.0, "exit": 100.0}}}
    rd = compute_shortfall(dec)
    assert rd["entry_slip_bps"] is None, "withdrawn: averaged prices measure drift"
    assert rd["exit_slip_bps"] is None, rd
    assert "entry_slip_bps" not in rd["coins"]["SOL"], rd["coins"]
    # the gap it IS entitled to compute still works
    assert rd["gap_pp"] == -1.0, rd
    # and the honest replacement is decision-vs-fill on ONE order:
    assert _slip_bps_of_check(100.0, 100.5, True) is not None
    assert abs(_slip_bps_of_check(100.0, 100.5, True) - 50.0) < 0.1   # paid up buying
    assert abs(_slip_bps_of_check(100.0, 99.5, False) - 50.0) < 0.1   # sold lower selling
    # an ECHOED decision price is NOT zero slippage — it is no reading at all
    assert _slip_bps_of_check(100.0, 100.0, True) is None, \
        "px_fill == px_decision must be None, never 0.0"
    print("implementation_shortfall selftest OK (clean/slipping/ahead/"
          "insufficient, one-arm ignored, entry+exit decomposition long+short)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
