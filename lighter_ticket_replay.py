#!/usr/bin/env python3
"""
lighter_ticket_replay.py — 🎬 replay the recorded scout tape through the
Ticket Taker's REAL decision code.

WHY (2026-07-15, from EVIDENCE_AND_LEARNING_REVIEW_2026-07-15.md)
  The Lighter-native fleet validates by forward-shadow only: every rule
  tweak costs DAYS of wall-clock evidence. But the scout already records
  the exact tape a replay needs — bot_state_history 'lighter-market'
  snapshots every ~5 min carrying tickets + liquid-book marks (marks since
  15-Jul). This harness replays that history through the taker's own
  `incredible()` conviction bars and `exit_reason()` TP/SL/max-hold logic,
  so a candidate bar change (env-tunable TT_* vars) is judged against
  recorded reality in seconds, not days:

      python3 lighter_ticket_replay.py --hours 48            # as deployed
      TT_TP=0.06 TT_BRK_RANGE=0.90 python3 lighter_ticket_replay.py ...
                                                             # a variant

  IMPORTED, NOT REIMPLEMENTED: entries/exits come from lighter_ticket_taker
  (the same module the live loop runs), so the replay can't drift from the
  bot. Same cadence too — decisions once per snapshot ≈ the 5-min loop.

HONEST DIVERGENCES from the live shadow book (all conservative-by-omission,
documented so a replay number is never mistaken for a shadow number):
  * No funding accrual — the tape has no per-symbol rates. Long lenses read
    slightly RICH (longs pay funding), divergence shorts read POOR (their
    whole thesis is collecting the credit).
  * Fixed CLIP_USD sizing — the tape has no daily ranges for vol_clip().
    Per-lens hit-rates and pnl_pct are unaffected (the brain grades on
    pnl_pct for exactly this reason).
  * No fleet long-budget veto / drawdown governor / lens veto — external
    bus state isn't in this tape. Stress veto IS replayed (snapshots carry
    stress.med).

READ-ONLY: fetches history (Postgres when DATABASE_URL is set, else the
dashboard's public /bus.json), writes nothing anywhere.
"""
import argparse
import json
import os
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone

import lighter_ticket_taker as tt

DASH_URL = os.environ.get(
    "REPLAY_BUS_URL",
    "https://pnl-dashboard-production-858c.up.railway.app/bus.json")
FEE = 4.0 / 10000.0          # PaperBroker fee_bps=4.0, same as the taker


# ---------------------------------------------------------------------------
# Tape loading
# ---------------------------------------------------------------------------

def _from_db(limit):
    import bot_pnl_store as store
    hist = store.fetch_state_history("lighter-market", limit=limit)
    return [(h.get("ts"), h.get("payload") or {}) for h in reversed(hist or [])]


def _from_bus(hours):
    url = f"{DASH_URL}?hours={int(hours)}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read().decode())
    return [(h.get("ts"), h.get("payload") or {})
            for h in (d.get("history") or []) if h.get("key") == "lighter-market"]


def load_tape(source="auto", hours=48, limit=2200):
    """[(datetime, payload)] oldest-first, marks-bearing snapshots only."""
    if source == "db" or (source == "auto" and os.environ.get("DATABASE_URL")):
        raw, used = _from_db(limit), "db"
    else:
        raw, used = _from_bus(hours), "bus"
    tape = []
    for ts, p in raw:
        if not (p or {}).get("marks"):
            continue                    # pre-15-Jul snapshots carry no prices
        try:
            dt = tt.parse_ts(ts)
        except (ValueError, TypeError):
            continue
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        tape.append((dt, p))
    tape.sort(key=lambda x: x[0])
    return tape, used


# ---------------------------------------------------------------------------
# Replay core (pure — unit-tested via --selftest)
# ---------------------------------------------------------------------------

def replay(tape, clip_usd=None, max_open=None):
    """Run the taker's decision code over the tape. Returns the report dict."""
    clip_usd = clip_usd or tt.CLIP_USD
    max_open = max_open or tt.MAX_OPEN
    pos = {}          # sym -> {lens, side, entry, opened(dt), clip}
    lens_stats = defaultdict(lambda: {"taken": 0, "closed": 0, "wins": 0,
                                      "net": 0.0, "pnl_pcts": [],
                                      "exits": defaultdict(int)})
    seen = defaultdict(int)             # raw tickets seen per lens
    vetoed_cycles = 0
    for snap_dt, p in tape:
        marks = p.get("marks") or {}
        # 1) exits — same rule object the live loop uses
        for sym in list(pos):
            m = pos[sym]
            mark = marks.get(sym)
            reason = tt.exit_reason(m["entry"], mark, m["opened"], snap_dt,
                                    m["side"] == "long")
            if not reason:
                continue
            sign = 1.0 if m["side"] == "long" else -1.0
            gross = m["clip"] * (mark / m["entry"] - 1.0) * sign
            net = gross - 2 * m["clip"] * FEE
            s = lens_stats[m["lens"]]
            s["closed"] += 1
            s["wins"] += 1 if net > 0 else 0
            s["net"] += net
            s["pnl_pcts"].append(net / m["clip"])
            s["exits"][reason] += 1
            del pos[sym]
        # 2) entries — stress veto + the taker's own conviction bars
        tickets = p.get("tickets") or {}
        for lens, arr in tickets.items():
            seen[lens] += len(arr or [])
        med = (p.get("stress") or {}).get("med")
        if med is not None and med >= tt.STRESS_VETO_BPS:
            vetoed_cycles += 1
            continue
        opened_syms, opened_lenses = set(), set()
        for lens, t in tt.incredible(tickets):
            sym = t.get("sym")
            if (not sym or sym in pos or sym in opened_syms
                    or lens in opened_lenses):
                continue
            if len(pos) >= max_open:
                break
            mark = marks.get(sym)
            if not mark:
                continue
            side = "short" if str(t.get("side", "long")) == "short" else "long"
            pos[sym] = {"lens": lens, "side": side, "entry": mark,
                        "opened": snap_dt, "clip": clip_usd}
            lens_stats[lens]["taken"] += 1
            opened_syms.add(sym)
            opened_lenses.add(lens)
    # end of tape: mark survivors at the last snapshot's prices (unrealized)
    open_report, unrealized = [], 0.0
    if tape:
        last_marks = tape[-1][1].get("marks") or {}
        for sym, m in pos.items():
            mark = last_marks.get(sym) or m["entry"]
            sign = 1.0 if m["side"] == "long" else -1.0
            u = m["clip"] * (mark / m["entry"] - 1.0) * sign
            unrealized += u
            open_report.append({"sym": sym, "lens": m["lens"],
                                "side": m["side"], "upnl": round(u, 2)})
    lenses = {}
    for lens, s in sorted(lens_stats.items()):
        n = len(s["pnl_pcts"])
        lenses[lens] = {
            "seen": seen.get(lens, 0), "taken": s["taken"],
            "closed": s["closed"], "wins": s["wins"],
            "net": round(s["net"], 2),
            "avg_pnl_pct": round(100 * sum(s["pnl_pcts"]) / n, 3) if n else None,
            "exits": dict(s["exits"]),
        }
    for lens, n in seen.items():        # lenses that never produced a fill
        lenses.setdefault(lens, {"seen": n, "taken": 0, "closed": 0, "wins": 0,
                                 "net": 0.0, "avg_pnl_pct": None, "exits": {}})
    return {
        "snapshots": len(tape),
        "span": (f"{tape[0][0].isoformat(timespec='seconds')} -> "
                 f"{tape[-1][0].isoformat(timespec='seconds')}") if tape else None,
        "stress_vetoed_cycles": vetoed_cycles,
        "lenses": lenses,
        "closed_net": round(sum(s["net"] for s in lens_stats.values()), 2),
        "open": open_report,
        "unrealized": round(unrealized, 2),
        "bars": {"TT_BRK_RANGE": tt.BRK_RANGE, "TT_BRK_VOL_M": tt.BRK_VOL_M,
                 "TT_DIP_RANGE": tt.DIP_RANGE, "TT_MOMO_CHG": tt.MOMO_CHG,
                 "TT_MOMO_VOL_M": tt.MOMO_VOL_M, "TT_DIV_GAP": tt.DIV_GAP_PP,
                 "TT_TP": tt.TAKE_PROFIT, "TT_SL": tt.STOP_LOSS,
                 "TT_MAX_HOLD_H": tt.MAX_HOLD_H,
                 "TT_STRESS_VETO_BPS": tt.STRESS_VETO_BPS,
                 "clip_usd": clip_usd, "max_open": max_open},
    }


def print_report(rep, used):
    print(f"[replay] tape: {rep['snapshots']} marks-bearing snapshots "
          f"({used}) span {rep['span']} | stress-vetoed cycles: "
          f"{rep['stress_vetoed_cycles']}")
    print(f"[replay] bars: {rep['bars']}")
    for lens, s in sorted(rep["lenses"].items()):
        wr = (100.0 * s["wins"] / s["closed"]) if s["closed"] else None
        print(f"  {lens:11s} seen={s['seen']:4d} taken={s['taken']:3d} "
              f"closed={s['closed']:3d} "
              f"wr={'—' if wr is None else f'{wr:.0f}%':>4s} "
              f"net=${s['net']:+7.2f} avg={s['avg_pnl_pct']}% "
              f"exits={s['exits']}")
    print(f"[replay] closed net ${rep['closed_net']:+.2f} | "
          f"open {len(rep['open'])} (unrealized ${rep['unrealized']:+.2f}) "
          f"{rep['open']}")


# ---------------------------------------------------------------------------

def selftest():
    """Offline: synthetic 6-snapshot tape exercising TP, SL, max-hold, the
    dip bar, the stress veto, and the one-per-lens rule. No network, no DB."""
    def dt(h, mi=0):
        return datetime(2026, 7, 15, h, mi, tzinfo=timezone.utc)

    def snap(h, marks, tickets=None, stress=None, mi=0):
        p = {"marks": marks, "tickets": tickets or {}}
        if stress is not None:
            p["stress"] = {"med": stress}
        return (dt(h, mi), p)

    brk = {"sym": "AAA", "range_pos": 0.99, "vol_m": 5.0}
    brk2 = {"sym": "EEE", "range_pos": 0.99, "vol_m": 5.0}
    momo = {"sym": "BBB", "chg_pct": 9.0, "vol_m": 5.0}
    dip_weak = {"sym": "CCC", "range_pos": 0.50}          # fails DIP bar
    slow = {"sym": "DDD", "range_pos": 0.99, "vol_m": 5.0}
    tape = [
        # t0: AAA + BBB enter (one per lens); CCC fails its bar
        snap(0, {"AAA": 100.0, "BBB": 100.0, "CCC": 100.0},
             {"breakout": [brk], "momentum": [momo], "dip": [dip_weak]}),
        # t1: stress veto — EEE's incredible breakout must NOT fill
        snap(1, {"AAA": 101.0, "BBB": 99.0, "EEE": 100.0},
             {"breakout": [brk2]}, stress=99.0),
        # t2: AAA hits TP (+5%), BBB hits SL (-4%); DDD enters (breakout slot free)
        snap(2, {"AAA": 105.0, "BBB": 96.0, "DDD": 200.0},
             {"breakout": [slow]}),
        # t3..: DDD drifts sideways past MAX_HOLD -> 'hold' exit
        snap(3, {"DDD": 201.0}),
        snap(3, {"DDD": 201.0}, mi=30),
    ]
    # final snapshot: past DDD's max-hold window (opened t2) -> 'hold' exit
    tape.append((dt(2) + timedelta(hours=tt.MAX_HOLD_H, minutes=5),
                 {"marks": {"DDD": 202.0}, "tickets": {}}))
    rep = replay(tape, clip_usd=50.0, max_open=6)
    L = rep["lenses"]
    assert L["breakout"]["taken"] == 2 and L["breakout"]["closed"] == 2, L
    assert L["breakout"]["exits"] == {"tp": 1, "hold": 1}, L["breakout"]
    assert L["momentum"]["exits"] == {"sl": 1}, L["momentum"]
    assert "dip" not in L or L["dip"]["taken"] == 0, L.get("dip")
    assert rep["stress_vetoed_cycles"] == 1, rep["stress_vetoed_cycles"]
    aaa_net = 50 * 0.05 - 2 * 50 * FEE          # TP leg
    bbb_net = 50 * -0.04 - 2 * 50 * FEE         # SL leg
    ddd_net = 50 * (202.0 / 200.0 - 1) - 2 * 50 * FEE
    assert abs(rep["closed_net"] - round(aaa_net + bbb_net + ddd_net, 2)) < 0.02, rep
    assert rep["open"] == [] and rep["unrealized"] == 0.0, rep["open"]
    print("[replay] selftest OK (tp/sl/hold, dip bar, stress veto, "
          "one-per-lens, fee accounting)")


def main():
    ap = argparse.ArgumentParser(description="Replay the scout tape through "
                                             "the Ticket Taker's real code")
    ap.add_argument("--hours", type=int, default=48,
                    help="bus-source lookback (dashboard caps at 200)")
    ap.add_argument("--limit", type=int, default=2200,
                    help="db-source max snapshots")
    ap.add_argument("--source", choices=("auto", "db", "bus"), default="auto")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return
    tape, used = load_tape(args.source, args.hours, args.limit)
    if not tape:
        print("[replay] no marks-bearing snapshots in range — marks publish "
              "since 15-Jul ~04:27Z; widen --hours or try later.")
        return
    print_report(replay(tape), used)


if __name__ == "__main__":
    main()
