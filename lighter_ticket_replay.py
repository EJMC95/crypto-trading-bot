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
  * No delist give-up — the taker force-closes a position whose book stays
    unpriceable for TT_DELIST_GIVEUP_H (16-Jul zombie guard); the replay
    has no such clock. Since 16-Jul the tape's marks cover ALL active books
    (not liquid-only), so a position can only go unpriceable here when the
    book truly leaves the venue — rare, and it is valued at ENTRY (flat) at
    tape end rather than force-closed.

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

def replay(tape, clip_usd=None, max_open=None, coin_veto=None):
    """Run the taker's decision code over the tape. Returns the report dict.

    `coin_veto`: an iterable of coin bases the production taker would refuse
    (bot_state 'coin-vetoes'). PASSED IN, never read from live state here —
    applying TODAY's veto set to HISTORICAL tape would be an anachronism that
    silently rewrites the past. Default None = no veto, which reproduces the
    pre-22-Jul taker exactly, so existing callers are unchanged.
    """
    clip_usd = clip_usd or tt.CLIP_USD
    max_open = max_open or tt.MAX_OPEN
    pos = {}          # sym -> {lens, side, entry, opened(dt), clip}
    lens_stats = defaultdict(lambda: {"taken": 0, "closed": 0, "wins": 0,
                                      "net": 0.0, "pnl_pcts": [], "nets": [],
                                      "exits": defaultdict(int)})
    seen = defaultdict(int)             # raw tickets seen per lens
    vetoed_cycles = 0
    # [2026-07-21 PARITY] mirror of the live loop's post-STOP cooldown
    # (sl_block, TT_SL_COOLDOWN_H — ON by default since the same-day churn
    # fix). Without this the replay judged every lever/study on rules the
    # production taker no longer runs: a candidate could earn its enactment
    # partly from re-entry churn the real bot now refuses. Same semantics:
    # per-SYMBOL, sl exits only (tp/hold re-enter freely), module attr read
    # at stamp time so replay_with(..., {"SL_COOLDOWN_H": x}) ladders it.
    sl_until = {}     # sym -> datetime the entry embargo lifts
    # [2026-07-22 PARITY] mirror of the live loop's COIN-QUALITY veto, added
    # the same day the taker gained it. This is the SECOND time this exact
    # class has bitten: the 21-Jul sl_block parity note above records the
    # first. Any rule the production taker gains must land here in the same
    # commit, or every replay-gated actuator downstream — scout tuner walks,
    # fleet_proprioception's $ counterfactual (the ONLY lane with one), the
    # incubator's offspring scores — silently grades candidates on rules the
    # real bot no longer runs. Normalised the same way the taker does.
    _veto = {str(c).split("/")[0] for c in (coin_veto or ())}
    for snap_dt, p in tape:
        marks = p.get("marks") or {}
        # 1) exits — same rule object the live loop uses
        for sym in list(pos):
            m = pos[sym]
            mark = marks.get(sym)
            # [2026-07-24 TREND EXIT PARITY] track the peak FAVOURABLE return so
            # exit_reason can run its trailing-from-peak exit (TT_TRAIL_PCT). A
            # position's peak only ratchets up. Harmless when the trend exit is
            # OFF (TRAIL_PCT=0): exit_reason ignores peak_ret, so this reproduces
            # the fixed-bracket replay byte-for-byte for every existing caller.
            if mark:
                _sgn = 1.0 if m["side"] == "long" else -1.0
                _r = (mark / m["entry"] - 1.0) * _sgn
                if _r > m.get("peak_ret", 0.0):
                    m["peak_ret"] = _r
            # [2026-07-24] per-lens exit under BULL_MODE (breakout -> trend exit,
            # others -> fixed bracket); (None, None) otherwise = unchanged.
            _ebars, _etrail = tt.bull_exit(m["lens"])
            reason = tt.exit_reason(m["entry"], mark, m["opened"], snap_dt,
                                    m["side"] == "long", bars=_ebars,
                                    peak_ret=m.get("peak_ret"), trail=_etrail)
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
            s["nets"].append(net)
            s["exits"][reason] += 1
            if reason == "sl" and tt.SL_COOLDOWN_H > 0:
                sl_until[sym] = snap_dt + timedelta(hours=tt.SL_COOLDOWN_H)
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
            if sym in sl_until and snap_dt < sl_until[sym]:
                continue          # post-stop cooldown — the live loop's rule
            if _veto and str(sym).split("/")[0] in _veto:
                continue          # coin-quality veto — the live loop's rule
            side = "short" if str(t.get("side", "long")) == "short" else "long"
            # [2026-07-24] BULL DUAL-MODE gate parity (no-op unless TT_BULL_MODE):
            # short-divergence uses the ticket's oracle regime stamp (up=None ->
            # _up_from_ticket). BREAKOUT is forced INERT here (up=False -> long
            # refused): the shadow arm gates breakout on up_read's CANDLE-EMA
            # regime, which the replay cannot reproduce (no venue.candles), so a
            # stamp-gated breakout leg would be non-comparable and would pollute
            # the tuner's leaderboard. The shadow arm is the breakout instrument.
            _up = False if lens == "breakout" else None
            if tt.BULL_MODE and not tt.bull_entry_ok(lens, side, t, up=_up):
                continue
            pos[sym] = {"lens": lens, "side": side, "entry": mark,
                        "opened": snap_dt, "clip": clip_usd, "peak_ret": 0.0}
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
            # [2026-07-17] per-trade net $, ADDITIVE (no existing field moved).
            # The mean alone cannot price uncertainty: strategy_incubator needs
            # the spread to rank genotypes on a lower CONFIDENCE BOUND instead
            # of a point estimate (winner's curse) at the n<20 this tape yields.
            "pnl_usd": [round(x, 4) for x in s["nets"]],
            "exits": dict(s["exits"]),
        }
    for lens, n in seen.items():        # lenses that never produced a fill
        lenses.setdefault(lens, {"seen": n, "taken": 0, "closed": 0, "wins": 0,
                                 "net": 0.0, "avg_pnl_pct": None,
                                 "pnl_usd": [], "exits": {}})
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

    # [2026-07-21 PARITY] cooldown mirror: BBB stops out at t2; the SAME
    # momentum ticket re-offered 45 minutes later must be refused at the
    # production default (2h) and taken with the cooldown off — the replay
    # now runs the live loop's post-stop rule, so lever candidates are
    # judged on the code that would run them.
    tape_cd = tape[:4] + [snap(2, {"BBB": 100.0, "DDD": 201.0, "AAA": 105.0},
                               {"momentum": [momo]}, mi=45)] + tape[4:]
    _saved_cd = tt.SL_COOLDOWN_H
    try:
        tt.SL_COOLDOWN_H = 0.0
        assert replay(tape_cd, clip_usd=50.0,
                      max_open=6)["lenses"]["momentum"]["taken"] == 2, \
            "cooldown 0 must fill the re-offer (baseline behaviour)"
        tt.SL_COOLDOWN_H = 2.0
        rep_cd = replay(tape_cd, clip_usd=50.0, max_open=6)
        assert rep_cd["lenses"]["momentum"]["taken"] == 1, \
            "re-entry 45m after the sl must be refused at the 2h default"
    finally:
        tt.SL_COOLDOWN_H = _saved_cd
    # [2026-07-22 PARITY] coin-quality veto mirror. AAA takes a breakout at t0
    # in the baseline; with AAA vetoed the entry must be REFUSED, and the veto
    # must be inert when empty (so every existing caller is unchanged) and
    # normalise a pair form the same way the taker does.
    base_taken = replay(tape, clip_usd=50.0, max_open=6)["lenses"]["breakout"]["taken"]
    assert base_taken >= 1, "fixture must take a breakout to be non-vacuous"
    assert replay(tape, clip_usd=50.0, max_open=6,
                  coin_veto=None)["lenses"]["breakout"]["taken"] == base_taken, \
        "coin_veto=None must reproduce the pre-22-Jul taker exactly"
    assert replay(tape, clip_usd=50.0, max_open=6,
                  coin_veto=set())["lenses"]["breakout"]["taken"] == base_taken, \
        "an EMPTY veto set must veto nothing (fail-open)"
    # NOTE the tape carries TWO breakout tickets (AAA at t0, DDD at t2), so
    # vetoing AAA drops the count by exactly one — it does not zero it. The
    # first draft of this fixture asserted ==0 and failed IDENTICALLY with and
    # without the guard, which is the fingerprint of an assertion that never
    # depended on the code under test. Vet both the partial and the total case.
    for veto in ({"AAA"}, {"AAA/USDC"}):
        rep_cv = replay(tape, clip_usd=50.0, max_open=6, coin_veto=veto)
        assert rep_cv["lenses"]["breakout"]["taken"] == base_taken - 1, \
            f"vetoing AAA must refuse exactly its own entry (veto={veto})"
        assert "AAA" not in {o["sym"] for o in rep_cv["open"]}, rep_cv["open"]
    rep_all = replay(tape, clip_usd=50.0, max_open=6, coin_veto={"AAA", "DDD"})
    assert rep_all["lenses"].get("breakout", {}).get("taken", 0) == 0, \
        "vetoing every breakout coin must leave the lens with no entries"
    # The veto SET is normalised at construction, so a bare-symbol tape can
    # never exercise the SYMBOL-side split — mutation-testing proved it (break
    # the symbol normalisation and every assertion above still passes). Today
    # the scout emits bare bases and 0/719 coin-quality keys carry a '/', so
    # that half is defensive; this fixture is what keeps it from being
    # defensive AND unverified, which is how dead guards rot into false comfort.
    pair_brk = {"sym": "FFF/USDC", "range_pos": 0.99, "vol_m": 5.0}
    tape_pair = [snap(0, {"FFF/USDC": 100.0}, {"breakout": [pair_brk]}),
                 snap(1, {"FFF/USDC": 101.0})]
    assert replay(tape_pair, clip_usd=50.0,
                  max_open=6)["lenses"]["breakout"]["taken"] == 1, \
        "pair-form fixture must be non-vacuous (it enters when unvetoed)"
    assert replay(tape_pair, clip_usd=50.0, max_open=6,
                  coin_veto={"FFF"})["lenses"].get("breakout", {}).get("taken", 0) == 0, \
        "a BARE veto key must refuse a PAIR-form ticket symbol (FFF vs FFF/USDC)"
    assert replay(tape, clip_usd=50.0, max_open=6,
                  coin_veto={"ZZZ"})["lenses"]["breakout"]["taken"] == base_taken, \
        "vetoing an unrelated coin must not change anything"
    print("[replay] selftest OK (tp/sl/hold, dip bar, stress veto, "
          "one-per-lens, fee accounting, sl-cooldown mirror, coin-veto mirror)")


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
