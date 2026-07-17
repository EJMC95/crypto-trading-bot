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
# [2026-07-17 AUDIT] The judge's experiment arm, read from ITS OWN env var with
# ITS OWN default — so if the operator re-points either organ, they still agree
# about whether SHADOW is a control or an experiment. Hard-coding the row here
# would let the two drift apart silently, which is how the collision below went
# unnoticed for as long as it did. Not imported from experiment_judge on
# purpose: that would add a heavy import (and a born-dark surface) to read one
# string.
XPJ_SHADOW_BOT = os.environ.get("XPJ_SHADOW_BOT", "perps-funding-lighter-lshadow")
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

def compute_shortfall(per_coin, xp_running=False, drift=None):
    """per_coin: {coin: {'live': {'avg_pct', 'n', 'entry', 'exit'},
                         'shadow': {'avg_pct', 'n', 'entry', 'exit'}}}.
    Returns the overall weighted gap (live − shadow, in pp/trade), the
    per-coin gaps, overlap/close counts, entry/exit slip decomposition (bps,
    where both arms carry prices), and a verdict. Pure.

    `xp_running`: the experiment judge has a candidate on the shadow arm, so
    the arms differ by STRATEGY as well as execution -> gap is reported but
    NOT judged (verdict 'xp-contaminated'). See the note in run_once.

    [2026-07-17 AUDIT] This organ's premise (:5-10) is that the two arms run
    "the SAME strategy on the SAME coins ... the ONLY difference is execution".
    That is FALSE whenever the judge is running a candidate, because SHADOW
    (:45) and experiment_judge.SHADOW_BOT (:62) are THE SAME ROW — the judge
    calls it "the EXPERIMENT arm: runs the current candidate's bars via xp.*
    levers", and lighter_funding_bot maps lighter_shadow -> "xp.funding.",
    moving enter_apr/take_profit/max_hold_h. Both loop in the same container.
    This organ had ZERO references to xp-judge.

    The thresholds collide EXACTLY:
        judge MARGIN_PP 0.5 / MIN_DAYS 7   |   isf CLEAN_PP 0.5 / WINDOW_DAYS 7
    So ANY candidate clearing the judge's promotion bar by any margin — i.e.
    every SUCCESS — forces gap < -CLEAN_PP here and reports 'live-slipping',
    phoning the operator "LIVE slipping vs shadow" every 6h for the
    candidate's 7+ day run, with perfectly clean execution. Inverted, a LOSING
    candidate reports 'live-ahead': a strategy handicap read as execution
    alpha, which the board surfaces as `expand`. The A/B rule this fleet
    already learned the hard way: vary exactly ONE variable, or the headline
    can point the opposite way to the truth."""
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
    elif drift:
        # [2026-07-17 ARM DRIFT] The two arms are running DIFFERENT CODE, so
        # this gap contains a strategy delta and cannot be attributed to
        # execution. Identical reasoning to xp-contaminated below, and ranked
        # ABOVE it: an experiment is a difference we CHOSE and are measuring on
        # purpose; drift is one nobody chose and nobody could see.
        # WHY IT HAPPENS: each live bot's `-lshadow` control arm lives in a
        # DIFFERENT Railway service (Farmer: trail-blazer-live vs
        # funding-farmer-shadow; Taker: tide-rider-lighter-live vs the organ
        # container). Separate deploy clocks, so any ship that moves one arm and
        # not the other silently makes this organ's number a lie — and the
        # judge's promotion bar too, which spends REAL MONEY on it.
        # MEASURED 17-Jul: 4 arms across 4 services, aligned only because they
        # happened to be deployed inside the same 23 minutes. Nothing said so.
        # Refuse the verdict, report the number, name both builds.
        verdict = "arm-drift"
    elif xp_running:
        # the control arm is an EXPERIMENT arm — this gap measures strategy +
        # execution together and cannot be attributed to either. Report the
        # number, refuse the verdict. Deliberately NOT 'clean': the honest
        # answer is "cannot tell", and a false CLEAN would hide real slippage
        # for the 7+ days a candidate runs. Never phones (run_once's streak
        # only counts 'live-slipping').
        verdict = "xp-contaminated"
    elif gap is None or abs(gap) <= CLEAN_PP:
        verdict = "clean"
    elif gap > 0:
        verdict = "live-ahead"
    else:
        verdict = "live-slipping"

    return {"gap_pp": gap, "verdict": verdict, "n_overlap": n_overlap,
            "paired_closes": tot_w, "coins": coins,
            "entry_slip_bps": entry_slip, "exit_slip_bps": exit_slip,
            "xp_running": bool(xp_running), "drift": drift or None}


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


def arm_drift(rows, live=None, shadow=None):
    """(None | {'live','shadow'}) — are the two arms running DIFFERENT CODE?

    Pure; `rows` is bot_pnl as fetch_bot_pnl returns it. Each bot stamps
    `extra.build` via the central hook in bot_pnl_store.publish (build_id.py):
    a hash of the BYTES it loaded, never a deploy label. That distinction is the
    whole point — `RAILWAY_GIT_*` reads 0 on every service whether connected or
    not, `railway status` meta.branch is blank for every `railway up`, and
    `lighter.__version__` reports a release that does not exist. All three are
    labels a system applies to itself. Bytes cannot lie about being bytes.

    FAIL-SAFE TOWARD SILENCE, unlike _xp_running below — and the asymmetry is
    deliberate. A missing stamp means "an arm has not published since the hook
    shipped", which is the NORMAL state during any rollout; treating unknown as
    drift would fire on every deploy of this very feature and teach the operator
    to ignore it (`convergent-metric-is-not-a-health-check` cuts both ways —
    a check that fires on healthy cadence is as useless as one that never
    fires). We only ever claim drift on POSITIVE evidence: two stamps present,
    two stamps different. Absence stays quiet and stays visible in the payload.
    """
    live = live or LIVE
    shadow = shadow or SHADOW
    by = {str(r.get("bot")): r for r in (rows or [])}
    a, b = by.get(live), by.get(shadow)
    if not a or not b:
        return None
    ba = ((a.get("extra") or {}) or {}).get("build")
    bb = ((b.get("extra") or {}) or {}).get("build")
    if not ba or not bb:
        return None          # not yet stamped — no claim
    if ba == bb:
        return None
    return {"live": ba, "shadow": bb}


def _xp_running(now):
    """Is the experiment judge running a candidate on OUR shadow arm right now?

    [2026-07-17 AUDIT] The shadow arm is the judge's EXPERIMENT arm whenever a
    candidate is in force, so this organ's execution premise does not hold —
    see compute_shortfall. FAIL-SAFE toward CONTAMINATED: a dark/stale/
    unreadable xp-judge returns True, because the dangerous error is assuming
    a clean control we cannot verify. Being wrong this way costs a few quiet
    cycles; being wrong the other way phones the operator "LIVE slipping"
    about a candidate that is WINNING. Only skipped when the judge positively
    reports a non-running phase on a FRESH payload — the same shape as every
    other consumer contract in the fleet.

    Scoped by row: if the judge's shadow arm isn't the one we measure, its
    phase is irrelevant to us."""
    if SHADOW != XPJ_SHADOW_BOT:
        return False
    try:
        st = store.load_state("xp-judge")
        if not st:
            return True                     # no ledger visible -> assume running
        u, ttl = st.get("updated"), float(st.get("ttl_sec") or 10800)
        age = now - datetime.fromisoformat(
            str(u).replace("Z", "+00:00")).timestamp()
        if not (0 <= age <= ttl):
            return True                     # stale -> cannot vouch for the arm
        return str(st.get("phase") or "") == "running"
    except Exception:                       # noqa: BLE001
        return True                         # unreadable -> assume contaminated


def run_once():
    now = now_ts()
    prior = store.load_state(KEY) or {}
    xp = _xp_running(now)
    try:
        _drift = arm_drift(store.fetch_bot_pnl() or [])
    except Exception:      # noqa: BLE001 — a dark sensor accuses nobody
        _drift = None
    rep = compute_shortfall(_fetch_per_coin(), xp_running=xp, drift=_drift)
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
    # [2026-07-17 AUDIT] THE CONTROL ARM IS AN EXPERIMENT ARM. A candidate that
    # CLEARS the judge's promotion bar (shadow beats live by >= MARGIN_PP=0.5)
    # is, to this organ, gap <= -CLEAN_PP=0.5 -> 'live-slipping'. Same rows,
    # same 7d window, same 0.5pp bar. So every judge SUCCESS phoned the operator
    # "LIVE slipping vs shadow" for 7+ days, with EXECUTION PERFECTLY CLEAN.
    # Fixture: identical fills on both arms (zero real shortfall), shadow ahead
    # purely on the candidate's bars.
    _xp_rows = {"ETH": {"live":   {"avg_pct": 0.001, "n": 10, "entry": 100.0, "exit": 100.1},
                        "shadow": {"avg_pct": 0.010, "n": 10, "entry": 100.0, "exit": 100.1}},
                "BTC": {"live":   {"avg_pct": 0.002, "n": 9,  "entry": 100.0, "exit": 100.2},
                        "shadow": {"avg_pct": 0.011, "n": 9,  "entry": 100.0, "exit": 100.2}}}
    _dirty = compute_shortfall(_xp_rows, xp_running=False)
    assert _dirty["verdict"] == "live-slipping" and _dirty["gap_pp"] < -0.5, _dirty
    assert _dirty["gap_pp"] == round(-0.9, 3), _dirty        # the false alarm
    _honest = compute_shortfall(_xp_rows, xp_running=True)
    assert _honest["verdict"] == "xp-contaminated", _honest
    assert _honest["gap_pp"] == _dirty["gap_pp"], "report the number, refuse the verdict"
    assert _honest["xp_running"] is True
    # ...and it must NOT be called 'clean' — that would hide real slippage for
    # the 7+ days a candidate runs. Only 'live-slipping' phones (run_once's
    # streak), so xp-contaminated is silent by construction.
    assert _honest["verdict"] != "clean"
    # the INVERSE: a LOSING candidate read as execution alpha ('live-ahead'),
    # which the board surfaces as `expand`
    _lose = {c: {"live": v["shadow"], "shadow": v["live"]} for c, v in _xp_rows.items()}
    assert compute_shortfall(_lose, xp_running=False)["verdict"] == "live-ahead"
    assert compute_shortfall(_lose, xp_running=True)["verdict"] == "xp-contaminated"
    # with NO candidate running, a real slip still reports normally
    assert compute_shortfall(_xp_rows, xp_running=False)["verdict"] == "live-slipping"
    # thin data still wins over contamination (nothing to contaminate)
    assert compute_shortfall({"ETH": {"live": {"avg_pct": 0.0, "n": 1},
                                      "shadow": {"avg_pct": 0.0, "n": 1}}},
                             xp_running=True)["verdict"] == "insufficient"

    # _xp_running fails SAFE toward contaminated: only a FRESH, positively
    # non-running judge licenses a verdict.
    _t = 1_784_000_000.0
    _real_ls = store.load_state

    def _judge(st):
        store.load_state = lambda k: st if k == "xp-judge" else None
        return _xp_running(_t)
    try:
        _fresh = datetime.fromtimestamp(_t - 60, tz=timezone.utc).isoformat()
        _old = datetime.fromtimestamp(_t - 99999, tz=timezone.utc).isoformat()
        assert _judge({"phase": "idle", "updated": _fresh, "ttl_sec": 10800}) is False
        assert _judge({"phase": "running", "updated": _fresh, "ttl_sec": 10800}) is True
        assert _judge({"phase": "idle", "updated": _old, "ttl_sec": 10800}) is True, \
            "a STALE judge cannot vouch for the arm -> assume contaminated"
        assert _judge(None) is True, "no ledger visible -> assume contaminated"
        assert _judge({"phase": "idle"}) is True, "unstamped -> assume contaminated"
    finally:
        store.load_state = _real_ls

    # --- ARM DRIFT (17-Jul) -------------------------------------------------
    # Synthetic rows: asserts the DETECTOR, never tonight's fleet. It must keep
    # passing when the arms are aligned (which is the normal, healthy state).
    def _row(bot, build=None):
        return {"bot": bot, "extra": ({"build": build} if build else {})}

    # POSITIVE: two stamps, different -> drift, and it NAMES both builds
    d = arm_drift([_row(LIVE, "aaaaaaaaaaaa"), _row(SHADOW, "bbbbbbbbbbbb")])
    assert d == {"live": "aaaaaaaaaaaa", "shadow": "bbbbbbbbbbbb"}, d
    # NEGATIVE 1: same build -> silent. The healthy state must never fire.
    assert arm_drift([_row(LIVE, "aaaaaaaaaaaa"), _row(SHADOW, "aaaaaaaaaaaa")]) is None
    # NEGATIVE 2: unstamped arms -> NO CLAIM. This is the rollout state — the
    # hook ships before the bots restart. Firing here would make the feature's
    # own deploy its first false alarm, which is how an alarm gets muted.
    assert arm_drift([_row(LIVE), _row(SHADOW)]) is None
    assert arm_drift([_row(LIVE, "aaaaaaaaaaaa"), _row(SHADOW)]) is None, \
        "one arm unstamped is UNKNOWN, not drift"
    # NEGATIVE 3: an arm missing entirely -> no claim (not both present)
    assert arm_drift([_row(LIVE, "aaaaaaaaaaaa")]) is None
    assert arm_drift([]) is None and arm_drift(None) is None

    # the VERDICT wiring: drift outranks xp-contamination and refuses the number
    _pair = {"BTC": {"live": {"avg_pct": 1.0, "n": 40}, "shadow": {"avg_pct": 1.0, "n": 40}},
             "ETH": {"live": {"avg_pct": 1.0, "n": 40}, "shadow": {"avg_pct": 1.0, "n": 40}}}
    r_ok = compute_shortfall(_pair)
    assert r_ok["verdict"] == "clean" and r_ok["drift"] is None, r_ok
    r_d = compute_shortfall(_pair, drift={"live": "a", "shadow": "b"})
    assert r_d["verdict"] == "arm-drift", r_d
    assert r_d["gap_pp"] == r_ok["gap_pp"], "report the NUMBER, refuse the VERDICT"
    # drift beats xp: an experiment is a difference we CHOSE; drift is not
    assert compute_shortfall(_pair, xp_running=True,
                             drift={"live": "a", "shadow": "b"})["verdict"] == "arm-drift"
    # and it must not phone: run_once's streak only counts 'live-slipping'
    assert r_d["verdict"] != "live-slipping"

    print("implementation_shortfall selftest OK (xp-contaminated control arm, "
          "clean/slipping/ahead/"
          "insufficient, one-arm ignored, entry+exit decomposition long+short, "
          "arm-drift: fires on 2 differing builds, silent on same/unstamped/absent)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        run_once()
