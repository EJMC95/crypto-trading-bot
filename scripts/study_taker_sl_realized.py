#!/usr/bin/env python3
"""
scripts/study_taker_sl_realized.py — 🎫 does the Ticket Taker's TP/SL/hold
SWEEP grade candidates on stop-loss fills the book cannot get?

THE FILED FINDING (21-Jul review): realized SL exits average −3.55% against a
−3% designed bar (realized reward:risk 1.02 vs designed 1.33); "sweep
economics should price realized exits". The implied fix was MEASUREMENT-side:
make lighter_ticket_replay price SL exits at bar + realized overshoot.

MECHANICS, QUOTED (so nobody re-argues them from prose):
  * The taker checks once per 300s cycle (tickettaker_loop.sh: `sleep 300`;
    run_all.sh:175 same) against the venue MARK, not a bar/candle
    (lighter_ticket_taker.py:303-305 mark_price from /api/v1/orderBookDetails;
    :483-494 exit_reason: `ret = (mark / entry - 1.0) ...; if ret <= STOP_LOSS:
    return "sl"`), and books the close AT that triggering mark
    (:1231 `broker.close(sym, mark)`; paper_broker.py models no slippage,
    4bps/side fees). Post-SL cooldown: :186-189 SL_COOLDOWN_H=2h default,
    stamped :1265-1269, enforced at entry :1380.
  * THE REPLAY DOES NOT PRICE SL AT THE BAR. lighter_ticket_replay.py:127-134:
    `mark = marks.get(sym); reason = tt.exit_reason(...); gross = m["clip"] *
    (mark / m["entry"] - 1.0) * sign` — the SL exit fills at the SNAPSHOT MARK
    that first breached the bar, i.e. bar + tape-cadence overshoot, minus
    2×4bps fees (:57, :134). The tuner's sweep (lighter_scout_tuner.py:118-121
    grid, :331-380 sweep_exits, :150-160 replay_with) inherits exactly this
    pricing, and the tape's snapshot cadence is the SAME 5 minutes as the
    live loop (measured: median gap 5.0 min, 1963 marks-bearing snapshots).

RESULTS 2026-07-22 (ledger 14→22 Jul, n=22 SL closes: 20 lshadow + 2 live —
above the n>=10 floor but still small; every number below moves with n):
  * Raw ledger SL mean −3.488% / median −3.318% / worst −5.152% (pnl_pct nets
    fees AND funding). vs a naive −3% bar: −0.488pp mean "overshoot".
  * BUT THE −3% PREMISE IS FALSE FOR 11 OF 22 CLOSES. The shadow arm trades
    the tuner's levers: bar-in-force reconstructed per close (extra.bars
    stamp > live-env > proprioception taker episode > env default) = 11
    closes at −3% (incl. both live), 7 at −4%, 4 at −2%.
  * vs the bar ACTUALLY in force: ledger-net overshoot mean −0.351pp, median
    −0.186pp; fee-adjusted (+8bps round trip) mean −0.271pp; candle-measured
    price-only overshoot mean −0.151pp / median −0.103pp / worst −1.834pp
    (5m Lighter candles: one-cycle crossing 7/22, already-past-bar 9/22 —
    mostly lever-expiry snap-back catching in-flight positions, delays up to
    58m — and no-trade-print-crossing 6/22: thin-book mark-vs-trade
    divergence, worst BOT −4.99% ledger vs −3.14% candle).
  * THE REPLAY'S OWN SL PRICING, measured on the same tape (1965 snapshots,
    median gap 5.0 min) at deployed bars: 22 replayed SL exits, mean −3.256%
    = −0.256pp past the bar (median −0.173, worst −0.840). That MATCHES the
    realized fee-adjusted overshoot vs bar-in-force (−0.271pp) — the sweep
    already prices realized cadence overshoot, because it fills at the
    breaching snapshot mark, not at the bar.
  * Forcing extra SL slip into the sweep anyway (net − n_sl·clip·slip, slip
    ∈ {0, 0.15pp, 0.40pp}): winner UNCHANGED at every slip on the full tape
    (tp=0.05/sl=−0.04/hold=48, $+15.29→$+12.29) and on each half (h1 same;
    h2 tp=0.05/sl=−0.03/hold=24, $+25.63→$+24.83). 0.40pp slip moves
    absolute nets ≤ $3 but every SL-taking candidate moves together — the
    ranking, and the fact that no candidate wins BOTH halves this week
    (h1/h2 winners differ, so the tuner's both-halves gate refuses enactment
    with or without slip), are untouched.
VERDICT: NO measurement-side change is supported. The −3.55%-vs-−3% headline
decomposes into (a) tuner lever stances — the bar in force was −4% (7) or
−2% (4) at close for 11/22 exits, (b) funding+fees inside pnl_pct, (c)
~0.1-0.3pp of true 5-min-cadence overshoot which lighter_ticket_replay
ALREADY charges by construction (its own measured overshoot −0.256pp ≈ the
book's realized −0.271pp). Realized-vs-designed R:R on the current ledger
(0.83: TP n=29 mean +2.892% / SL mean −3.488%) is a bar-stance-mixing
artifact, not un-priced slippage. Re-run before acting if n_sl grows past
~60 or the flap pattern changes; the real follow-up is the LEVER-FLAP
mechanism itself (a −4%→−3% expiry snap-back books the whole gap instantly —
9/22 closes were already past the close-time bar when caught), which is
tuner/TTL semantics, not sweep pricing — no code change proposed here
without both-halves evidence for one.
REGIMES: window 2026-07-14→22 is one falling-BTC regime slice of Lighter's
one-regime tape; per the 21-Jul review caveat this is a pass/measurement in
that regime only. Venue-pure: Lighter API + the fleet's own ledger/bus only.

USAGE:
  python3 scripts/study_taker_sl_realized.py --selftest   # offline, fixtures
  python3 scripts/study_taker_sl_realized.py              # full run (network)
  STUDY_CACHE=/path python3 ...                           # cache fetches
"""
import argparse
import bisect
import json
import os
import statistics as st
import sys
import time
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import lighter_ticket_replay as rp          # noqa: E402
import lighter_ticket_taker as tt           # noqa: E402

DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")
LIGHTER = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
CACHE = os.environ.get("STUDY_CACHE", "")
FEE = 4.0 / 10000.0                          # PaperBroker fee_bps=4, per side
DEFAULT_SL = -0.03                           # TT_SL shipped default
DEFAULT_TP = 0.04                            # TT_TP shipped default
TAKER_BOTS = ("lighter-ticket-taker-lshadow", "lighter-ticket-taker-lighter")
SWEEP_TP = [0.03, 0.04, 0.05, 0.06]          # the tuner's grid, verbatim
SWEEP_SL = [-0.02, -0.03, -0.04]
SWEEP_HOLD = [24.0, 48.0, 72.0]
SLIPS = [0.0, 0.0015, 0.004]                 # extra SL slip fractions to force


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _fetch_json(url):
    if CACHE:
        os.makedirs(CACHE, exist_ok=True)
        key = os.path.join(CACHE, urllib.parse.quote(url, safe="") + ".json")
        if os.path.exists(key):
            return json.load(open(key))
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                d = json.loads(r.read().decode())
            break
        except Exception:  # noqa: BLE001
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))
    if CACHE:
        json.dump(d, open(key, "w"))
    return d


def _lighter(path, **q):
    return _fetch_json(LIGHTER + path + ("?" + urllib.parse.urlencode(q) if q else ""))


# ---------------------------------------------------------------------------
# Pure helpers (selftested offline)
# ---------------------------------------------------------------------------

def taker_sl_episodes(prop_payload):
    """[(start_epoch, end_epoch, sl_value)] from the proprioception organ's
    taker-group lever episodes (the only durable record of the shadow arm's
    bar stances — fleet-tuning itself keeps no history on the bus)."""
    eps = []
    for e in (prop_payload.get("episodes") or []):
        if e.get("group") == "taker" and "taker.sl" in (e.get("stance") or {}):
            try:
                eps.append((float(e["start"]), float(e["end"]),
                            float(e["stance"]["taker.sl"])))
            except (TypeError, ValueError, KeyError):
                continue
    op = (prop_payload.get("open") or {}).get("taker") or {}
    if "taker.sl" in (op.get("stance") or {}):
        try:
            eps.append((float(op["start"]), 9e12, float(op["stance"]["taker.sl"])))
        except (TypeError, ValueError):
            pass
    return eps


def bar_in_force(row, episodes, default=DEFAULT_SL):
    """(sl_bar, source) for one ledger close. Seniority: the close's own
    extra.bars stamp (ships 21-Jul) > live arm = operator env default (live
    consumes NO taker.* levers — lighter_ticket_taker.apply_tuning returns {}
    for lighter_live) > shadow: proprioception episode overlapping closed_at
    > env default (levers expire back to it)."""
    stamped = ((row.get("extra") or {}).get("bars") or {}).get("sl")
    if stamped is not None:
        return float(stamped), "stamp"
    if str(row.get("bot", "")).endswith("-lighter"):
        return default, "live-env"
    try:
        ts = parse_ts(row["closed_at"]).timestamp()
    except (ValueError, TypeError, KeyError):
        return default, "default"
    for s, e, v in episodes:
        if s <= ts <= e:
            return v, "lever"
    return default, "default"


def classify_overshoot(entry, closes, bar, opened_ts, closed_ts, is_long):
    """Decompose one SL close against 5m candle CLOSES (the natural
    resolution: the taker checks every 5 min, intra-cycle lows never trigger).
    closes: {epoch_sec: close_px}. Returns dict(exit_ret, prev_ret, delay_min,
    cls) — cls: 'one-cycle' (bar first breached within the final cycle:
    cadence/gap overshoot), 'already-past' (position sat beyond the close-time
    bar earlier: lever-flap catch or missed cycles), 'no-crossing' (trade
    prints never breached the bar the MARK breached: mark-vs-trade
    divergence)."""
    sgn = 1.0 if is_long else -1.0
    ts_sorted = sorted(t for t in closes if opened_ts <= t <= closed_ts)
    if not entry or not ts_sorted:
        return None

    def ret_at(tsec):
        prior = [t for t in ts_sorted if t <= tsec]
        return (closes[max(prior)] / entry - 1.0) * sgn if prior else None

    exit_ret = ret_at(closed_ts)
    prev_ret = ret_at(closed_ts - 300)
    t_cross = next((t for t in ts_sorted
                    if (closes[t] / entry - 1.0) * sgn <= bar), None)
    if t_cross is None:
        return {"exit_ret": exit_ret, "prev_ret": prev_ret,
                "delay_min": None, "cls": "no-crossing"}
    cls = ("already-past" if prev_ret is not None and prev_ret <= bar
           else "one-cycle")
    return {"exit_ret": exit_ret, "prev_ret": prev_ret,
            "delay_min": (closed_ts - t_cross) / 60.0, "cls": cls}


def sl_count(rep):
    return sum((s.get("exits") or {}).get("sl", 0)
               for s in (rep.get("lenses") or {}).values())


def marked(rep):
    """The tuner's own score: closed net + end-of-tape unrealized."""
    return rep["closed_net"] + float(rep.get("unrealized") or 0.0)


def adjust_marked(rep, slip):
    """Sweep net under FORCED extra SL slip: every replayed SL exit charged
    an additional `slip` fraction of its clip (first-order model of 'price SL
    exits worse than the tape mark')."""
    clip = float((rep.get("bars") or {}).get("clip_usd") or tt.CLIP_USD)
    return marked(rep) - slip * clip * sl_count(rep)


class _SlSpy:
    """Context manager: records (ret, is_long) for every 'sl' verdict
    tt.exit_reason returns — measures at what distance past the bar the
    REPLAY (which prices at the breaching snapshot mark) fills SL exits."""

    def __init__(self):
        self.rets = []

    def __enter__(self):
        self._orig = tt.exit_reason

        def spy(entry, mark, opened, t_now, is_long=True):
            r = self._orig(entry, mark, opened, t_now, is_long)
            if r == "sl":
                self.rets.append((mark / entry - 1.0) * (1.0 if is_long else -1.0))
            return r
        tt.exit_reason = spy
        return self

    def __exit__(self, *a):
        tt.exit_reason = self._orig
        return False


def replay_with(tape, bars):
    """lighter_scout_tuner.replay_with, restated locally so the study does
    not import the tuner's Postgres-touching module top-level. Same contract:
    patch tt bars, replay, always restore."""
    saved = {k: getattr(tt, k) for k in bars}
    try:
        for k, v in bars.items():
            setattr(tt, k, v)
        return rp.replay(tape)
    finally:
        for k, v in saved.items():
            setattr(tt, k, v)


# ---------------------------------------------------------------------------
# Online sections
# ---------------------------------------------------------------------------

def fetch_ledger():
    rows = []
    for bot in TAKER_BOTS:
        d = _fetch_json(f"{DASH}/trades.json?source=paper&bot={bot}&limit=5000")
        rows += [dict(r, bot=bot) for r in
                 (d if isinstance(d, list) else d.get("trades") or [])]
    return rows


def fetch_bus(hours=200):
    return _fetch_json(f"{DASH}/bus.json?hours={hours}")


def tape_from_bus(bus):
    tape = []
    for h in (bus.get("history") or []):
        if h.get("key") != "lighter-market":
            continue
        p = h.get("payload") or {}
        if not p.get("marks"):
            continue
        try:
            dt = parse_ts(h.get("ts"))
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tape.append((dt, p))
    tape.sort(key=lambda x: x[0])
    return tape


def fetch_candles_5m(mid, t0, t1):
    out, end = {}, int(t1)
    while True:
        rows = _lighter("/api/v1/candles", market_id=mid, resolution="5m",
                        start_timestamp=max(int(t0), end - 500 * 300),
                        end_timestamp=end, count_back=500).get("c") or []
        for c in rows:
            out[int(c["t"]) // 1000] = float(c["c"])
        if not rows:
            break
        oldest = min(int(c["t"]) // 1000 for c in rows)
        if oldest <= t0:
            break
        end = oldest - 300
        time.sleep(0.25)
    return {t: v for t, v in out.items() if t0 <= t <= t1}


def run(args):
    print("=== 1. LEDGER: realized SL closes ===")
    rows = fetch_ledger()
    sl_rows = [r for r in rows if str(r.get("reason", "")).endswith("_sl")]
    tp_rows = [r for r in rows if str(r.get("reason", "")).endswith("_tp")]
    n = len(sl_rows)
    pcts = [r["pnl_pct"] * 100 for r in sl_rows]
    print(f"n={n} SL closes ({sum(1 for r in sl_rows if r['bot'].endswith('lshadow'))}"
          f" shadow + {sum(1 for r in sl_rows if r['bot'].endswith('-lighter'))} live)")
    if n < 10:
        print(f"n={n} < 10 — below the study's own floor; measurement only, "
              f"no recommendation can rest on this.")
    print(f"raw ledger pnl_pct: mean {st.mean(pcts):+.3f}%  median "
          f"{st.median(pcts):+.3f}%  worst {min(pcts):+.3f}%  best {max(pcts):+.3f}%")
    print(f"vs naive -3% bar: mean overshoot {st.mean(pcts) + 3:+.3f}pp "
          f"(pnl_pct nets 8bps fees AND funding — not a pure price number)")

    print("\n=== 2. BAR-IN-FORCE (stamp > live-env > lever episode > default) ===")
    bus = fetch_bus()
    eps = taker_sl_episodes(bus.get("proprioception") or {})
    bars = [bar_in_force(r, eps) for r in sl_rows]
    from collections import Counter
    print("bar mix:", dict(Counter(f"{b:+.2f}" for b, _ in bars)),
          "| source mix:", dict(Counter(s for _, s in bars)))
    ov_net = [p - b * 100 for p, (b, _) in zip(pcts, bars)]
    print(f"ledger-net overshoot vs bar-in-force: mean {st.mean(ov_net):+.3f}pp "
          f"median {st.median(ov_net):+.3f}pp | fee-adjusted (+0.08pp): "
          f"mean {st.mean(ov_net) + 0.08:+.3f}pp")

    print("\n=== 3. CANDLE DECOMPOSITION (5m Lighter candles, price-only) ===")
    obd = _lighter("/api/v1/orderBookDetails").get("order_book_details") or []
    ids = {o["symbol"]: o["market_id"] for o in obd}
    ovs, cls_n = [], Counter()
    for r, (bar, src) in zip(sl_rows, bars):
        sym = r["pair"].split("/")[0]
        mid = ids.get(sym)
        if mid is None:
            cls_n["no-book"] += 1
            continue
        o_ts, c_ts = parse_ts(r["opened_at"]).timestamp(), parse_ts(r["closed_at"]).timestamp()
        closes = fetch_candles_5m(mid, o_ts - 600, c_ts + 600)
        ent = [t for t in sorted(closes) if abs(t - o_ts) <= 300]
        entry = closes[min(ent, key=lambda t: abs(t - o_ts))] if ent else None
        d = classify_overshoot(entry, closes, bar, o_ts, c_ts,
                               r["reason"].startswith("long")) if entry else None
        if not d:
            cls_n["no-candles"] += 1
            continue
        cls_n[d["cls"]] += 1
        if d["exit_ret"] is not None:
            ovs.append((d["exit_ret"] - bar) * 100)
        print(f"  {sym:<9}{r['bot'].rsplit('-', 1)[-1]:<8}bar {bar:+.2f} ({src:<8}) "
              f"ledger {r['pnl_pct'] * 100:+.3f}%  candle "
              f"{(d['exit_ret'] or 0) * 100:+.3f}%  {d['cls']}"
              + (f" (delay {d['delay_min']:.0f}m)" if d["delay_min"] is not None else ""))
        time.sleep(0.15)
    if ovs:
        print(f"candle price-only overshoot vs bar-in-force: n={len(ovs)} mean "
              f"{st.mean(ovs):+.3f}pp median {st.median(ovs):+.3f}pp "
              f"worst {min(ovs):+.3f}pp | classes {dict(cls_n)}")

    print("\n=== 4. REPLAY'S OWN SL PRICING (the sweep's world) ===")
    tape = tape_from_bus(bus)
    gaps = [(b[0] - a[0]).total_seconds() / 60 for a, b in zip(tape, tape[1:])]
    print(f"tape: {len(tape)} marks-bearing snapshots, median gap "
          f"{st.median(gaps):.1f} min (live loop cadence: 300s)")
    with _SlSpy() as spy:
        rep0 = rp.replay(tape)
    r_ov = [(r - tt.STOP_LOSS) * 100 for r in spy.rets]
    if r_ov:
        print(f"replayed SL exits at deployed bars (sl={tt.STOP_LOSS}): "
              f"n={len(r_ov)} priced mean {st.mean(spy.rets) * 100:+.3f}% = "
              f"{st.mean(r_ov):+.3f}pp past the bar (median {st.median(r_ov):+.3f}, "
              f"worst {min(r_ov):+.3f}) — the replay fills at the breaching "
              f"snapshot mark (lighter_ticket_replay.py:127-134), NOT at the bar")
    print(f"baseline replay: marked ${marked(rep0):+.2f}, sl exits {sl_count(rep0)}")

    print("\n=== 5. SWEEP SENSITIVITY: force extra SL slip into the economics ===")
    span_h = (tape[-1][0] - tape[0][0]).total_seconds() / 3600 if tape else 0
    holds = [h for h in SWEEP_HOLD if h < span_h]
    mid_i = len(tape) // 2
    halves = {"full": tape, "h1": tape[:mid_i], "h2": tape[mid_i:]}
    reps = {}
    for tp in SWEEP_TP:
        for slb in SWEEP_SL:
            for hold in holds:
                key = (tp, slb, hold)
                reps[key] = {hn: replay_with(ht, {"TAKE_PROFIT": tp,
                                                  "STOP_LOSS": slb,
                                                  "MAX_HOLD_H": hold})
                             for hn, ht in halves.items()}
    for slip in SLIPS:
        for hn in ("full", "h1", "h2"):
            ranked = sorted(reps, key=lambda k: -adjust_marked(reps[k][hn], slip))
            top = ranked[0]
            print(f"  slip {slip * 100:.2f}pp {hn:>4}: winner tp={top[0]} "
                  f"sl={top[1]} hold={top[2]:.0f} "
                  f"(${adjust_marked(reps[top][hn], slip):+.2f}; "
                  f"#2 {ranked[1]} ${adjust_marked(reps[ranked[1]][hn], slip):+.2f})")
    stable = all(
        sorted(reps, key=lambda k: -adjust_marked(reps[k][hn], s))[0]
        == sorted(reps, key=lambda k: -adjust_marked(reps[k][hn], 0.0))[0]
        for s in SLIPS for hn in halves)
    print(f"winner stable across slips 0→0.40pp on full+both halves: {stable}")

    print("\n=== 6. R:R CONTEXT ===")
    if tp_rows:
        tps = [r["pnl_pct"] * 100 for r in tp_rows]
        non_default = sum(1 for b, _ in bars if abs(b - DEFAULT_SL) > 1e-12)
        print(f"TP closes n={len(tps)} mean {st.mean(tps):+.3f}% | realized "
              f"R:R mean_tp/|mean_sl| = {st.mean(tps) / abs(st.mean(pcts)):.2f} "
              f"(designed at env bars: {DEFAULT_TP / abs(DEFAULT_SL):.2f}) — but "
              f"{non_default}/{n} SL closes ran non-default bars, so 'designed' "
              f"was a moving target this window")
    print("\nVERDICT: see header docstring — no measurement-side change "
          "supported; the replay already prices SL at the breaching snapshot "
          "mark and its overshoot matches the realized fee-adjusted overshoot "
          "vs the bar actually in force.")


# ---------------------------------------------------------------------------
# Selftest — OFFLINE-GREEN: fixtures only, no network, exits 0
# ---------------------------------------------------------------------------

def selftest():
    # 1) bar_in_force seniority
    eps = [(1000.0, 2000.0, -0.04)]
    stamped = {"bot": "lighter-ticket-taker-lshadow",
               "closed_at": "1970-01-01T00:25:00+00:00",
               "extra": {"bars": {"sl": -0.02}}}
    assert bar_in_force(stamped, eps) == (-0.02, "stamp")
    live = {"bot": "lighter-ticket-taker-lighter",
            "closed_at": "1970-01-01T00:25:00+00:00", "extra": {}}
    assert bar_in_force(live, eps) == (DEFAULT_SL, "live-env")
    in_ep = {"bot": "lighter-ticket-taker-lshadow",
             "closed_at": "1970-01-01T00:25:00+00:00"}   # ts=1500 in episode
    assert bar_in_force(in_ep, eps) == (-0.04, "lever")
    gap = {"bot": "lighter-ticket-taker-lshadow",
           "closed_at": "1970-01-01T01:00:00+00:00"}     # ts=3600, no episode
    assert bar_in_force(gap, eps) == (DEFAULT_SL, "default")

    # 2) taker_sl_episodes parses closed + open stances, skips junk
    prop = {"episodes": [
        {"group": "taker", "start": 1.0, "end": 2.0, "stance": {"taker.sl": -0.04}},
        {"group": "taker", "start": 3.0, "end": 4.0, "stance": {"taker.tp": 0.06}},
        {"group": "scout", "start": 5.0, "end": 6.0, "stance": {"taker.sl": -0.02}}],
        "open": {"taker": {"start": 9.0, "stance": {"taker.sl": -0.04}}}}
    got = taker_sl_episodes(prop)
    assert got[0] == (1.0, 2.0, -0.04) and len(got) == 2 and got[1][2] == -0.04, got

    # 3) classify_overshoot: one-cycle vs already-past vs no-crossing
    t0 = 1_000_000
    one = classify_overshoot(100.0, {t0: 99.5, t0 + 300: 98.0, t0 + 600: 96.5},
                             -0.03, t0, t0 + 600, True)
    assert one["cls"] == "one-cycle" and abs(one["exit_ret"] + 0.035) < 1e-9, one
    past = classify_overshoot(100.0, {t0: 96.5, t0 + 300: 96.4, t0 + 600: 96.6},
                              -0.03, t0, t0 + 600, True)
    assert past["cls"] == "already-past" and past["delay_min"] == 10.0, past
    nox = classify_overshoot(100.0, {t0: 99.0, t0 + 300: 98.5},
                             -0.03, t0, t0 + 300, True)
    assert nox["cls"] == "no-crossing", nox
    shrt = classify_overshoot(100.0, {t0: 100.0, t0 + 300: 103.5},
                              -0.03, t0, t0 + 300, False)
    assert shrt["cls"] == "one-cycle" and abs(shrt["exit_ret"] + 0.035) < 1e-9, shrt

    # 4) THE CENTRAL MECHANICAL FACT, proven offline: the replay prices an SL
    # exit at the breaching SNAPSHOT MARK (here -4%), not at the -3% bar.
    def dt(h, mi=0):
        return datetime(2026, 7, 15, h, mi, tzinfo=timezone.utc)
    brk = {"sym": "AAA", "range_pos": 0.99, "vol_m": 5.0}
    tape = [(dt(0), {"marks": {"AAA": 100.0}, "tickets": {"breakout": [brk]}}),
            (dt(1), {"marks": {"AAA": 96.0}, "tickets": {}})]
    saved = (tt.STOP_LOSS, tt.TAKE_PROFIT, tt.BRK_RANGE, tt.BRK_VOL_M)
    try:
        tt.STOP_LOSS, tt.TAKE_PROFIT = -0.03, 0.04
        tt.BRK_RANGE, tt.BRK_VOL_M = 0.95, 1.0
        with _SlSpy() as spy:
            rep = rp.replay(tape, clip_usd=50.0, max_open=6)
        assert len(spy.rets) == 1 and abs(spy.rets[0] + 0.04) < 1e-9, \
            spy.rets                                  # mark, not the -3% bar
        assert sl_count(rep) == 1, rep["lenses"]
        want = 50.0 * -0.04 - 2 * 50.0 * FEE
        assert abs(rep["closed_net"] - round(want, 2)) < 0.02, rep["closed_net"]
        # 5) adjust_marked charges slip per SL exit
        assert abs(adjust_marked(rep, 0.004) - (marked(rep) - 0.004 * 50.0)) < 1e-9
        assert adjust_marked(rep, 0.0) == marked(rep)
    finally:
        tt.STOP_LOSS, tt.TAKE_PROFIT, tt.BRK_RANGE, tt.BRK_VOL_M = saved

    # 6) replay_with restores module bars even on error
    before = tt.STOP_LOSS
    try:
        replay_with(None, {"STOP_LOSS": -0.99})       # None tape -> TypeError
    except TypeError:
        pass
    assert tt.STOP_LOSS == before

    print("[study_taker_sl_realized] selftest OK (bar-in-force seniority, "
          "episode parsing, overshoot classes, replay-prices-at-mark, "
          "slip adjustment, bar restore)")


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--hours", type=int, default=200,
                    help="bus history lookback (dashboard caps at 200)")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    run(args)


if __name__ == "__main__":
    main()
