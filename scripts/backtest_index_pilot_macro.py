#!/usr/bin/env python3
"""
VERDICT (2026-07-12): REJECTED — do not rebuild, do not re-test.
The SPY/QQQ macro gate failed the doctrine bars on BOTH windows (this short
HL window and the 2022-inclusive long window in backtest_index_pilot_macro_long.py):
it only helps one half, the mirror test does not fail symmetrically, and the
robustness sweep flips across lookbacks. The 2022 crash-dodge is real but is
paid back by a ~185pp miss on the 2023 re-entry, and the live Tide Rider
already dodges 2022 natively and better via its own crypto-trend signal.
See memory/index-pilot-lighter-rejected.md. This closed the LAST open Index
Pilot flavor (long-trend == Tide Rider; long/short regime == RegimeSwitchV1).

scripts/backtest_index_pilot_macro.py — does an EXOGENOUS equity-index regime
(SPY/QQQ risk-on/off) improve a crypto long on Lighter?  This is the one Index
Pilot variant NOT already covered by the fleet: Index Pilot as an *external macro
GATE* rather than a crypto-trend signal (the crypto-trend versions are already the
live Tide Rider [long] and the rejected RegimeSwitchV1 [short] — see
memory/index-pilot-lighter-rejected.md).

HYPOTHESIS: SPY/QQQ regime carries risk-on/off information that lets a crypto long
dodge the bear half. If true it should IMPROVE a pure-beta long (buy&hold) and/or
the incumbent trend long (tide_50_200), in BOTH sample halves, not just one.

METHOD (faithful to the doctrine — the GATE is the ONLY change):
  * Reuses backtest_strategy_shootout.py's engine verbatim: same 6 majors, 1x long
    Lighter perp, real HL funding drag, same fees/accounting, same both-halves split.
  * Equity regime = SPY (or QQQ) close > SMA(lookback), computed in equity-trading-day
    space and forward-filled onto crypto days (weekends hold Friday's state).
  * gated_long[i] = base_signal[i] AND equity_regime[i].  Engine holds day i on
    signal[i-1] (yesterday's close) so the gate uses only past equity data — no look-ahead.
  * ALL variants scored on the identical crypto day range (warmup 200) so the only
    difference between a base and its gated form is the gate.

DOCTRINE BARS the gate must clear to earn a build:
  1. Beat its OWN ungated base in BOTH halves (higher ret, or materially better
     ret/maxDD — the whole point of a risk gate is to cut the bear-half drawdown).
  2. MIRROR TEST: long-crypto-only-when-equities-RISK-OFF must score symmetrically
     WORSE. If long-in-risk-off is also fine, the 'gate' is just noise.
  3. ROBUSTNESS: hold up across index (SPY/QQQ) and lookback (100/150/200 + 50/200
     golden). A gate that only helps at one lookback and flips next door is a trap.

Equity data: Yahoo daily closes, cached to .index_pilot_equity_cache.json (offline reruns).
Usage:  python scripts/backtest_index_pilot_macro.py
"""
import bisect
import datetime
import importlib.util
import json
import os
import urllib.request

_spec = importlib.util.spec_from_file_location(
    "shoot", os.path.join(os.path.dirname(__file__), "backtest_strategy_shootout.py"))
S = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(S)

EQ_CACHE = os.path.join(os.path.dirname(__file__), ".index_pilot_equity_cache.json")
WARM = 200  # common warmup (crypto days) — tide EMA200 + equity SMA200 both warm


# ----------------------------------------------------------------------------- data
def fetch_equity(sym):
    p2 = int(datetime.datetime(2026, 7, 11).timestamp())
    p1 = p2 - int(4.5 * 365 * 86400)
    url = (f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}"
           f"?period1={p1}&period2={p2}&interval=1d")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    r = json.load(urllib.request.urlopen(req, timeout=30))
    res = r["chart"]["result"][0]
    ts, cl = res["timestamp"], res["indicators"]["quote"][0]["close"]
    # (ordinal date, close) — ordinal so weekend forward-fill is a clean integer compare
    out = []
    for t, c in zip(ts, cl):
        if c is None:
            continue
        d = datetime.datetime.utcfromtimestamp(t).date().toordinal()
        out.append((d, float(c)))
    out.sort()
    return out


def load_equity():
    if os.path.exists(EQ_CACHE):
        return {k: [tuple(x) for x in v] for k, v in json.load(open(EQ_CACHE)).items()}
    eq = {s: fetch_equity(s) for s in ("SPY", "QQQ")}
    json.dump(eq, open(EQ_CACHE, "w"))
    return eq


# ------------------------------------------------------------------ equity regimes
def _sma(a, n):
    out = [None] * len(a); s = 0.0
    for i in range(len(a)):
        s += a[i]
        if i >= n: s -= a[i - n]
        if i >= n - 1: out[i] = s / n
    return out


def equity_regime(series, kind):
    """Bool per equity trading day. kind: 'smaN' (price>SMAN) or 'golden' (EMA50>EMA200)."""
    closes = [c for _, c in series]
    if kind == "golden":
        e50, e200 = S.ema(closes, 50), S.ema(closes, 200)
        reg = [e50[i] > e200[i] if i >= 200 else None for i in range(len(closes))]
    else:
        n = int(kind[3:]); m = _sma(closes, n)
        reg = [None if m[i] is None else closes[i] > m[i] for i in range(len(closes))]
    return [d for d, _ in series], reg


def align_to_coin(coin_t, eq_dates, eq_reg, invert=False):
    """Forward-fill the equity regime onto a coin's daily timestamps (ms).
    regime_seq[i] = equity regime as of the last equity trading day <= crypto date i."""
    seq = []
    for tms in coin_t:
        d = datetime.datetime.utcfromtimestamp(tms / 1000).date().toordinal()
        j = bisect.bisect_right(eq_dates, d) - 1
        r = eq_reg[j] if j >= 0 else None
        if r is None:
            seq.append(False)                    # not warm -> flat (all within warmup)
        else:
            seq.append((not r) if invert else r)
    return seq


# --------------------------------------------------------------------- scoring
def score(data, base_seqs, gate_seqs, N, mid):
    """gate_seqs None => ungated base. Returns full/H1/H2 dicts from the shootout basket."""
    seqs = {}
    for c in data:
        if gate_seqs is None:
            seqs[c] = base_seqs[c]
        else:
            b, g = base_seqs[c], gate_seqs[c]
            seqs[c] = [b[i] and g[i] for i in range(len(b))]
    return (S.basket(data, seqs, WARM, 0, N),
            S.basket(data, seqs, WARM, 0, mid),
            S.basket(data, seqs, WARM, mid, N))


def rr(m):
    return m["ret"] / abs(m["mdd"]) if m["mdd"] else float("nan")


def row(tag, full, h1, h2, note=""):
    dur = "YES" if (h1["ret"] > 0.05 and h2["ret"] > 0.05) else (
          "half" if (h1["ret"] > 0.05 or h2["ret"] > 0.05) else "no")
    print(f"{tag:>22} | {full['ret']*100:>7.1f} {full['mdd']*100:>7.1f} {rr(full):>6.2f} "
          f"{full['pct_long']*100:>4.0f}% | {h1['ret']*100:>7.1f} {h2['ret']*100:>7.1f} "
          f"{dur:>4} | {note}")


def main():
    data = S.load_majors()
    N = min(len(d["c"]) for d in data.values()); mid = N // 2
    eq = load_equity()

    # base signals
    bases = {}
    for name in ("buy_hold", "tide_50_200"):
        bs = {}
        for c in data:
            s, _ = S.SIGNALS[name](data[c]["c"]); bs[c] = s
        bases[name] = bs

    def gate(sym, kind, invert=False):
        dts, reg = equity_regime(eq[sym], kind)
        return {c: align_to_coin(data[c]["t"], dts, reg, invert) for c in data}

    hdr = (f"{'variant':>22} | {'FULL%':>7} {'maxDD%':>7} {'ret/DD':>6} {'%lng':>4} "
           f"| {'H1%':>7} {'H2%':>7} {'dur':>4} | note")
    print("Index Pilot as an EXOGENOUS macro gate on a crypto long — 6 majors, 1x perp, "
          f"real HL funding, {N}d\nGate is the ONLY change vs each base. Scored on identical "
          f"days (warmup {WARM}).\n")
    print(hdr); print("-" * len(hdr))

    # 1) ungated baselines
    for b in ("buy_hold", "tide_50_200"):
        f, h1, h2 = score(data, bases[b], None, N, mid)
        row(f"{b} (UNGATED)", f, h1, h2, "reference")
    print("-" * len(hdr))

    # 2) macro-gated (primary hypothesis: SPY/QQQ sma200)
    for b in ("buy_hold", "tide_50_200"):
        for sym in ("SPY", "QQQ"):
            f, h1, h2 = score(data, bases[b], gate(sym, "sma200"), N, mid)
            row(f"{b} x {sym}>SMA200", f, h1, h2, "risk-on gate")
    print("-" * len(hdr))

    # 3) MIRROR TEST — long crypto only when equities RISK-OFF (must be symmetrically worse)
    for b in ("buy_hold", "tide_50_200"):
        f, h1, h2 = score(data, bases[b], gate("SPY", "sma200", invert=True), N, mid)
        row(f"{b} x SPY<SMA200", f, h1, h2, "MIRROR (risk-OFF) — should be worse")
    print("-" * len(hdr))

    # 4) ROBUSTNESS — lookback + definition sweep on the gate (buy_hold base = purest signal)
    print("\nRobustness of the SPY gate on buy_hold (does it hold across lookback/def?):")
    print(hdr); print("-" * len(hdr))
    for kind in ("sma100", "sma150", "sma200", "golden"):
        f, h1, h2 = score(data, bases["buy_hold"], gate("SPY", kind), N, mid)
        row(f"buy_hold x SPY {kind}", f, h1, h2, "")
    print("-" * len(hdr))

    print("\nREAD: the gate earns a build ONLY if a gated row beats its UNGATED base in "
          "BOTH halves (ret or ret/DD), the MIRROR is clearly worse (not similar), AND it "
          "holds across the robustness sweep. Same bar Tide Rider and the slope gate cleared.")


if __name__ == "__main__":
    main()
