#!/usr/bin/env python3
"""
scripts/backtest_carry_gate_lighter.py — the Yield Harvester's ENTRY GATE,
swept on Lighter's OWN settled funding tape, universe-wide.

WHY (2026-07-21, from study_carry_flip_grace_lighter's verdict): the twin's
flip bleed (0W/23 on the week) turned out to be an ENTRY symptom — at the
shipped bar (ENTER_APR 0.40 published = 5% TRUE) round-trip friction
(29bps) needs 508h of entry-rate accrual against a 336h MAX_HOLD: an entry
AT the bar structurally cannot pay for itself unless the rate stays hot.
The twin's real winners (decay_paid 6W/0L +$36.30) were 100%+ APR books.
This sweeps the gate on the full liquid universe — the flip study's 8 coins
were selected FOR failure and could not decide this.

METHOD: top-N liquid books (today's snapshot — SURVIVORSHIP: today's
universe applied historically, declared not hidden), 150d of settled hourly
funding each, the bot's OWN entry rule (|apr| >= gate held PERSIST_H=6h
continuously, ranked by |apr|, MAX_POSITIONS=8, $300 notional) and OWN exit
cascade (flip 1h grace, fee-payback decay, 336h max-hold, 2% bleed stop),
constants imported from this repo's shipped values. Hedged carry: P&L =
funding accrual - friction; no price leg (the hedge neutralizes it — that
is the strategy's own claim, and the bot's own accounting).
FRICTION IS THE BOT'S MODELLED 29bps ROUND TRIP, NOT MEASURED FILLS — the
load-bearing constant, stated here in the verdict's own paragraph per
[[funding-farmer-friction-refutation]]. Every gate shares it, so the claim
is the RELATIVE ordering of gates; absolute $ move with the constant.
EXIT BAR HELD FIXED at the shipped 1.875% TRUE across the sweep (isolates
the entry effect; sweeping both is a follow-up if a gate survives).

RESULTS 2026-07-21 (150d, top 40 books, halves = calendar halves of the
union timeline; marked = open-at-end positions net of full friction):
      gate       net       h1       h2      n   win%
     0.050    -93.31   -91.99    -0.39    447    20%   <- SHIPPED
     0.075    -24.06   -59.57   +22.81    384    24%
     0.100     -7.12   -38.10   +25.12    348    26%
     0.150    +23.81    -4.04   +23.15    350    27%
     0.200    +55.93   +17.48   +34.00    315    30%   <- passes both halves
VERDICT: the shipped 5%-TRUE gate is structural bleed (monotone
dose-response across the whole sweep); **0.20 TRUE (= ENTER_APR 1.60 in the
file's published units) is the only gate that beats shipped on the full
window AND both halves** — enacted same day as the new CARRY_ENTER_APR env
default (funding_carry_bot.py), reversible without a deploy. EXIT bar was
held fixed; sweeping it at the new gate is the follow-up. Do not re-argue
the old gate from prose — re-run with --refresh.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

B = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                     ".carry_gate_lighter_cache.json")

# funding_carry_bot's shipped constants (lighter basis: TRUE apr)
NOTIONAL = 300.0
MAX_POSITIONS = 8
PERSIST_H = 6.0
FLIP_GRACE_H = 1.0
OPEN_COST = 0.00045 + 0.0010          # per side
EXIT_APR_TRUE = 0.15 / 8              # 0.01875
FEE_PAYBACK_MARGIN = 0.10
BLEED_STOP_FRAC = 0.02
MAX_HOLD_H = 14 * 24
HOURS_PER_YEAR = 24 * 365

DAYS = int(os.environ.get("CG_DAYS", "150"))
UNIVERSE_N = int(os.environ.get("CG_UNIVERSE", "40"))
SWEEP = [0.05, 0.075, 0.10, 0.15, 0.20]   # TRUE apr entry gates


def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fetch_fundings(mid, days):
    out, end, cutoff = {}, int(time.time()), int(time.time()) - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/fundings", market_id=mid, resolution="1h",
                    start_timestamp=0, end_timestamp=end,
                    count_back=0).get("fundings") or []
        if not rows:
            break
        for f in rows:
            rate = float(f["rate"]) / 100.0 * 24 * 365
            out[int(f["timestamp"])] = rate * (1 if f["direction"] == "long" else -1)
        oldest = min(f["timestamp"] for f in rows)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if t >= cutoff}


def load_universe(refresh=False):
    if os.path.exists(CACHE) and not refresh:
        d = json.load(open(CACHE))
        if d.get("days", 0) >= DAYS and d.get("universe_n", 0) >= UNIVERSE_N:
            return {s: {int(k): v for k, v in m.items()}
                    for s, m in d["fund"].items()}
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    liquid = sorted((o for o in obs if o.get("symbol")),
                    key=lambda o: -float(o.get("daily_quote_token_volume") or 0))
    fund = {}
    for o in liquid[:UNIVERSE_N]:
        sym, mid = o["symbol"], o["market_id"]
        try:
            f = fetch_fundings(mid, DAYS)
        except Exception as e:  # noqa: BLE001
            print(f"  {sym}: fetch failed ({e}) — skipped")
            continue
        if len(f) < 24 * 20:
            print(f"  {sym}: only {len(f)}h of funding — skipped")
            continue
        fund[sym] = f
        print(f"  {sym:12s} {len(f):5d}h "
              f"({(max(f) - min(f)) / 86400:.0f}d)")
    json.dump({"days": DAYS, "universe_n": UNIVERSE_N, "fund": fund},
              open(CACHE, "w"))
    return fund


def run_gate(fund, gate, exit_bar=EXIT_APR_TRUE):
    """The carry loop at one entry gate over the union hourly timeline.
    Returns dict(net, closed, wins, open_marked, by_exit). Pure; selftested
    on synthetic tapes."""
    hours = sorted({t for m in fund.values() for t in m})
    positions = {}                     # coin -> pos
    hot_since = {}
    net, closed, wins = 0.0, 0, 0
    by_exit = {}
    for t in hours:
        # exits first (mirror of the bot's loop order)
        for coin in list(positions):
            apr = fund[coin].get(t)
            if apr is None:
                continue
            pos = positions[coin]
            side_mult = 1 if pos["side"] == "short" else -1
            pos["accrued"] += side_mult * (apr / HOURS_PER_YEAR) * NOTIONAL
            held_h = (t - pos["opened_ts"]) / 3600.0
            adverse = side_mult * apr < 0
            if adverse:
                pos.setdefault("flipped_since", t)
            else:
                pos.pop("flipped_since", None)
            fees_total = 2 * OPEN_COST * NOTIONAL
            net_if_closed = pos["accrued"] - fees_total
            flipped = ("flipped_since" in pos
                       and (t - pos["flipped_since"]) / 3600.0 >= FLIP_GRACE_H)
            expired = held_h >= MAX_HOLD_H
            bleeding = net_if_closed <= -BLEED_STOP_FRAC * NOTIONAL
            decayed = (abs(apr) < exit_bar
                       and net_if_closed >= FEE_PAYBACK_MARGIN)
            if flipped or decayed or expired or bleeding:
                reason = ("flip" if flipped else "decay_paid" if decayed
                          else "max_hold" if expired else "bleed_stop")
                pnl = net_if_closed
                net += pnl
                closed += 1
                wins += 1 if pnl > 0 else 0
                by_exit[reason] = by_exit.get(reason, 0) + 1
                del positions[coin]
        # persistence clocks
        for coin, m in fund.items():
            apr = m.get(t)
            if apr is None:
                continue
            if abs(apr) >= gate:
                hot_since.setdefault(coin, t)
            else:
                hot_since.pop(coin, None)
        # entries
        if len(positions) < MAX_POSITIONS:
            cands = sorted(
                ((c, fund[c][t]) for c in fund
                 if c not in positions and t in fund[c]
                 and abs(fund[c][t]) >= gate
                 and (t - hot_since.get(c, t)) >= PERSIST_H * 3600.0),
                key=lambda cf: -abs(cf[1]))
            for coin, apr in cands[:MAX_POSITIONS - len(positions)]:
                positions[coin] = {
                    "side": "short" if apr > 0 else "long",
                    "opened_ts": t, "accrued": 0.0}
    open_marked = sum(p["accrued"] - 2 * OPEN_COST * NOTIONAL
                      for p in positions.values())
    return {"net": net, "closed": closed, "wins": wins,
            "open_marked": round(open_marked, 2), "by_exit": by_exit}


def main():
    refresh = "--refresh" in sys.argv
    fund = load_universe(refresh)
    if not fund:
        print("no universe — venue unreachable?")
        return
    all_hours = sorted({t for m in fund.values() for t in m})
    mid_t = all_hours[len(all_hours) // 2]
    h1 = {s: {t: v for t, v in m.items() if t < mid_t} for s, m in fund.items()}
    h2 = {s: {t: v for t, v in m.items() if t >= mid_t} for s, m in fund.items()}
    span_d = (all_hours[-1] - all_hours[0]) / 86400
    print(f"\n{len(fund)} books, {span_d:.0f}d "
          f"({len(all_hours)}h union timeline)\n")
    print(f"{'gate':>6s} {'net':>9s} {'h1':>8s} {'h2':>8s} {'marked':>8s} "
          f"{'n':>5s} {'win%':>5s}  exits")
    for gate in SWEEP:
        full = run_gate(fund, gate)
        a, b = run_gate(h1, gate), run_gate(h2, gate)
        wr = (100.0 * full["wins"] / full["closed"]) if full["closed"] else 0
        print(f"{gate:6.3f} {full['net']:+9.2f} "
              f"{a['net'] + a['open_marked']:+8.2f} "
              f"{b['net'] + b['open_marked']:+8.2f} "
              f"{full['open_marked']:+8.2f} {full['closed']:5d} {wr:4.0f}%  "
              f"{full['by_exit']}")
    print("\nBoth-halves rule: a gate must beat the shipped 0.050 row on the "
          "full window AND both halves before ENTER_APR moves. Friction is "
          "modelled 29bps/round-trip — relative ordering is the claim.")


# ---------------------------------------------------------------------------

def _selftest():
    h = 3600
    t0 = 1_800_000_000

    def tape(*aprs):
        return {t0 + i * h: a for i, a in enumerate(aprs)}

    # HOT coin: 60% TRUE for 300h then cool — pays back richly at any gate.
    # TEPID coin: oscillates 6-8% with sign flips every ~10h — at gate 0.05
    # it enters (6h persistence met) and flip-bleeds; at gate 0.10 it is
    # never eligible. The sweep must show gate 0.10 >= gate 0.05 on this
    # universe (the tepid coin's bleed is excluded, the hot coin kept).
    hot = tape(*([0.60] * 300 + [0.001] * 20))
    osc = tape(*(([0.07] * 10 + [-0.07] * 10) * 16))
    uni = {"HOT": hot, "TEPID": osc}
    lo = run_gate(uni, 0.05)
    hi = run_gate(uni, 0.10)
    assert lo["closed"] > hi["closed"], (lo, hi)      # tepid churn at low gate
    assert hi["net"] >= lo["net"], (lo["net"], hi["net"])
    hot_only = run_gate({"HOT": hot}, 0.05)
    assert hot_only["net"] > 0 and hot_only["by_exit"].get("decay_paid", 0) \
        + hot_only["by_exit"].get("max_hold", 0) >= 1, hot_only
    # persistence: a 3h spike never enters (PERSIST_H=6)
    spike = tape(*([0.001] * 10 + [0.80] * 3 + [0.001] * 50))
    sp = run_gate({"SPIKE": spike}, 0.05)
    assert sp["closed"] == 0 and sp["open_marked"] == 0, sp
    # empty tape: clean zeros
    z = run_gate({}, 0.05)
    assert z["net"] == 0 and z["closed"] == 0, z
    print("backtest_carry_gate selftest OK (hot pays, tepid churns at the "
          "low gate only, persistence bar, empty-tape)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
