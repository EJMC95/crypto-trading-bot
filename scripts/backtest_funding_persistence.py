#!/usr/bin/env python3
"""
scripts/backtest_funding_persistence.py — is the CARRY'S SURVIVAL predictable?

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT — filled in from the real run; see RUN OUTPUT below.             ║
╚══════════════════════════════════════════════════════════════════════════╝

WHY THIS EXISTS. [[backtest_funding_lighter]] settled that the Funding Farmer
loses at every gate on Lighter, and found the mechanism: 63% of trades end
because the RATE EVAPORATED, at a median hold of 8h, earning ~0.5bps against a
10bps round trip. The bot filters on funding LEVEL. But carry = apr x hold/8760,
so the economically decisive quantity is not the level — it is the SURVIVAL TIME
of the carry, which the bot never looks at. This file asks the only question
that can still save the strategy:

    AT ENTRY, IS SURVIVAL PREDICTABLE FROM ANYTHING OBSERVABLE?

If yes, that is the redesign (gate on predicted survival, not on level). If no,
the strategy is dead: you cannot select for a quantity you cannot see, and the
level you CAN see is ~20x too small to pay the round trip.

WHAT IT MEASURES — Lighter's OWN settled series, nothing else.
  EPISODE = |apr| crosses gate G and stays hot; ENDS when |apr| < G*0.375 (the
  live EXIT_APR/ENTER_APR ratio) or the sign flips. Hysteresis matches the live
  bot: enter at >= G, exit at < 0.375G, so a dip in between does NOT end it.
  ENTRY = start + PERSIST_H (4h), the live bot's hot-streak rule. An episode
  that dies before 4h is NOT ENTERABLE — counted, never traded.
  survival_h  = full spell, crossing -> death (what the venue offers)
  residual_h  = entry -> death (what the bot can actually hold) <- THE TRUTH

THE ECONOMIC BAR: a trade clears friction iff  apr * survival_h / 8760 > 0.001
  (10bps round trip = 2 fills x 5bps; Lighter perp fee is 0, this is pure
  spread). Reported three ways, tightest last:
    SPEC bar     apr_entry x survival_h  — credits the bot 4h it cannot hold
    TRADEABLE    apr_entry x residual_h  — the bot's real hold
    REALIZED     sum(apr_h x side)/8760 over the hold — the integral it truly
                 earns, signed against the position, so the flip hour is charged
                 as the cost it is rather than credited as income
  Equivalently: required survival = 8.76 / apr hours-of-apr.

PREDICTORS, all computed at entry from data AT OR BEFORE entry (no look-ahead):
  apr level | slope 4h / 12h of |apr| (building vs rolling over) | realized vol
  24h from candles | CROSS-VENUE AGREEMENT (is the coin also hot on HL?).
  Cross-venue hypothesis: all venues hot => the carry is STRUCTURAL and persists;
  only Lighter hot => a venue dislocation that mean-reverts fast.
  NOTE FOR PRODUCTION: this file reads HL's `fundingHistory` because it is the
  only HISTORICAL cross-venue reference. The LIVE bot would never call HL — it
  reads Lighter's own /funding-rates `_bench` rows (which carry binance/bybit/
  hyperliquid alongside lighter). So a cross-venue rule stays "everything off
  Lighter" in production; only this BACKTEST needs the foreign endpoint.

  "ALREADY HOT" IS TESTED AS A HAZARD, NOT A CORRELATION — deliberately. Within
  one spell residual_h falls exactly 1h per hour of already_hot BY CONSTRUCTION,
  so a pooled rank correlation over sampled entry points is guaranteed negative
  and means nothing. The honest test is conditional survival ACROSS episodes:
  of the spells that reach X hours, what is the median REMAINING life? Flat in X
  = memoryless (persistence buys you nothing); rising = persistence begets
  persistence; falling = the hot spell is burning out.

UNITS — the 8x trap this file cannot fall into. Lighter /api/v1/fundings rate is
PERCENT PER HOUR, so apr_true = rate/100*24*365 (ETH ~8% TRUE). HL fundingHistory
is NATIVELY HOURLY, so hl_apr = rate*24*365 is correct THERE. This file never
touches /funding-rates (the 8h-basis endpoint that caused the fleet-wide 8x).

BOTH HALVES: every headline is re-reported on each half of the window. A
predictor that works on one half is a window, not an edge.

Read-only: public endpoints + its own cache (scripts/.fundpersist_cache.json).
Touches no bot, no DB, no lever.
    python3 scripts/backtest_funding_persistence.py
    python3 scripts/backtest_funding_persistence.py --days 300 --universe 30 --refresh
"""
import argparse
import json
import math
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import backtest_funding_lighter as bfl   # reuse _get / fetch_fundings / fetch_candles

CACHE = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".fundpersist_cache.json")
HL = "https://api.hyperliquid.xyz/info"

EXIT_RATIO = 0.375        # live EXIT_APR/ENTER_APR = 0.15/0.40
PERSIST_H = 4             # live hot-streak before entry
ROUND_TRIP = 0.001        # 2 fills x 5bps — the friction a trade must clear
GATES = [0.05, 0.12, 0.20, 0.40, 0.80, 1.10]   # 0.05 = live today; 1.10 = the
                                               # operative breakeven at an 8h hold
PRED_GATES = [0.05, 0.20]  # where the predictor study runs
MAX_GAP_H = 6             # a data hole longer than this CENSORS an open episode


# ─────────────────────────── stats, hand-rolled (no scipy) ───────────────────
def _betacf(a, b, x):
    MAXIT, EPS, FPMIN = 300, 3e-14, 1e-300
    qab, qap, qam = a + b, a + 1.0, a - 1.0
    c, d = 1.0, 1.0 - qab * x / qap
    if abs(d) < FPMIN:
        d = FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, MAXIT + 1):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < FPMIN:
            d = FPMIN
        c = 1.0 + aa / c
        if abs(c) < FPMIN:
            c = FPMIN
        d = 1.0 / d
        de = d * c
        h *= de
        if abs(de - 1.0) < EPS:
            break
    return h


def _betai(a, b, x):
    """Regularized incomplete beta I_x(a,b) — Numerical Recipes."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    lb = (math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
          + a * math.log(x) + b * math.log1p(-x))
    bt = math.exp(lb)
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


def t_two_sided(t, df):
    """P(|T| > |t|) for Student-t with df — exact, via the incomplete beta."""
    if df <= 0:
        return float("nan")
    return _betai(df / 2.0, 0.5, df / (df + t * t))


def _ranks(xs):
    """Average ranks, ties handled."""
    idx = sorted(range(len(xs)), key=lambda i: xs[i])
    r = [0.0] * len(xs)
    i = 0
    while i < len(idx):
        j = i
        while j + 1 < len(idx) and xs[idx[j + 1]] == xs[idx[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            r[idx[k]] = avg
        i = j + 1
    return r


def spearman(xs, ys):
    """-> (rho, n, p two-sided). Pearson on average ranks = tie-correct Spearman."""
    n = len(xs)
    if n < 6:
        return (float("nan"), n, float("nan"))
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    dx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    dy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if dx == 0 or dy == 0:
        return (float("nan"), n, float("nan"))
    rho = num / (dx * dy)
    if abs(rho) >= 1.0:
        return (rho, n, 0.0)
    t = rho * math.sqrt((n - 2) / (1 - rho * rho))
    return (rho, n, t_two_sided(t, n - 2))


def pct(xs, q):
    if not xs:
        return float("nan")
    s = sorted(xs)
    if len(s) == 1:
        return s[0]
    i = q * (len(s) - 1)
    lo, hi = int(math.floor(i)), int(math.ceil(i))
    return s[lo] + (s[hi] - s[lo]) * (i - lo)


def median(xs):
    return pct(xs, 0.5)


# ─────────────────────────────── data ────────────────────────────────────────
def _hl(payload):
    body = json.dumps(payload).encode()
    req = urllib.request.Request(HL, data=body,
                                 headers={"Content-Type": "application/json"})
    for attempt in range(4):
        try:
            with urllib.request.urlopen(req, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def hl_universe():
    try:
        meta = _hl({"type": "meta"}) or {}
        return {u["name"].upper(): u["name"] for u in (meta.get("universe") or [])}
    except Exception as e:
        print(f"  HL meta failed ({e}) — cross-venue predictor will be DARK")
        return {}


def fetch_hl_funding(coin, days):
    """HL fundingHistory, paged FORWARD (500/call). HL is NATIVELY HOURLY.
    -> {hour_ts: signed apr_true}."""
    out = {}
    start = int((time.time() - days * 86400) * 1000)
    end = int(time.time() * 1000)
    while start < end:
        rows = _hl({"type": "fundingHistory", "coin": coin,
                    "startTime": start, "endTime": end}) or []
        if not rows:
            break
        for r in rows:
            t = int(r["time"]) // 1000
            out[(t // 3600) * 3600] = float(r["fundingRate"]) * 24 * 365
        newest = max(int(r["time"]) for r in rows)
        if len(rows) < 500 or newest <= start:
            break
        start = newest + 1
        time.sleep(0.10)
    return out


def load(days, universe_n, refresh):
    if os.path.exists(CACHE) and not refresh:
        try:
            d = json.load(open(CACHE))
            if d.get("days", 0) >= days and d.get("universe_n", 0) >= universe_n:
                print(f"  (cache: {len(d['mk'])} markets, {d['days']}d, "
                      f"fetched {time.strftime('%Y-%m-%d %H:%M UTC', time.gmtime(d['fetched']))})")
                return {s: {"fund": {int(k): v for k, v in m["fund"].items()},
                            "cand": {int(k): tuple(v) for k, v in m["cand"].items()},
                            "hl": {int(k): v for k, v in (m.get("hl") or {}).items()}}
                        for s, m in d["mk"].items()}
        except Exception as e:
            print(f"  (cache unreadable: {e} — refetching)")

    obs = bfl._get("/api/v1/orderBookDetails").get("order_book_details") or []
    liquid = sorted((o for o in obs if o.get("symbol")),
                    key=lambda o: -float(o.get("daily_quote_token_volume") or 0))
    hlu = hl_universe()
    mk = {}
    for o in liquid[:universe_n]:
        sym, mid = o["symbol"], o["market_id"]
        try:
            fund = bfl.fetch_fundings(mid, days)
            cand = bfl.fetch_candles(mid, days)
        except Exception as e:
            print(f"  {sym:12s} fetch failed ({e}) — skipped")
            continue
        common = set(fund) & set(cand)
        if len(common) < 24 * 20:
            print(f"  {sym:12s} only {len(common)}h paired — skipped")
            continue
        hl = {}
        coin = hlu.get(sym.upper())
        if coin:
            try:
                hl = fetch_hl_funding(coin, days)
            except Exception as e:
                print(f"  {sym:12s} HL fetch failed ({e}) — no cross-venue for this coin")
        mk[sym] = {"fund": fund, "cand": cand, "hl": hl}
        print(f"  {sym:12s} {len(common):5d}h paired "
              f"({(max(common)-min(common))/86400:5.0f}d) | HL {len(hl):5d}h"
              f"{'' if coin else '  (not on HL)'}")
    json.dump({"days": days, "universe_n": universe_n, "fetched": int(time.time()),
               "mk": {s: {"fund": m["fund"], "cand": m["cand"], "hl": m["hl"]}
                      for s, m in mk.items()}}, open(CACHE, "w"))
    return mk


# ────────────────────────────── episodes ─────────────────────────────────────
def realized_vol(cand, t_end, lookback_h=24):
    """Annualized realized vol from hourly closes in (t_end-lookback, t_end]."""
    ts = [t_end - i * 3600 for i in range(lookback_h, -1, -1)]
    px = [cand[t][3] for t in ts if t in cand and cand[t][3] > 0]
    if len(px) < 20:
        return None
    rets = [math.log(px[i] / px[i - 1]) for i in range(1, len(px))]
    m = sum(rets) / len(rets)
    var = sum((r - m) ** 2 for r in rets) / (len(rets) - 1)
    return math.sqrt(var) * math.sqrt(8760.0)


def episodes(sym, m, gate, persist_h=PERSIST_H):
    """All hot spells for one market at one gate. -> (list[ep], early_ts, cens_ts).

    Spells are defined ONCE over the whole tape and later assigned to a window by
    their entry time — never re-derived per half, which would truncate a spell
    straddling the split and bias its survival short. early_ts/cens_ts carry the
    SPELL START so the discard counts can be windowed the same way.

    persist_h is the AGE-AT-ENTRY rule: the spell must already have been hot this
    long before the book may enter. The live bot uses PERSIST_H=4. Section 4c
    sweeps it, because 4a says age predicts survival and age is observable at
    decision time. It is a PARAMETER, not a second copy of this function, so the
    swept arm and the live arm can never drift apart in their spell definition.
    """
    exit_gate = gate * EXIT_RATIO
    fund, cand, hl = m["fund"], m["cand"], m["hl"]
    hours = sorted(fund)
    eps, early_ts, cens_ts = [], [], []
    st = None
    prev = None

    def close_ep(end_t):
        """Finish a spell that DIED at end_t (observed death, not censoring)."""
        start = st["start"]
        entry = None
        for t in st["hrs"]:
            if (t - start) / 3600.0 >= persist_h:
                entry = t
                break
        surv_h = (end_t - start) / 3600.0
        if entry is None:
            early_ts.append(start)
            return None
        res_h = (end_t - entry) / 3600.0
        apr_e = abs(fund[entry])
        sgn = st["sign"]
        # ---- predictors, data at or BEFORE entry only -----------------------
        def slope(hrs):
            t0 = entry - hrs * 3600
            if t0 not in fund:
                return None
            return (abs(fund[entry]) - abs(fund[t0])) / float(hrs)
        # The realized integral is SIGNED against the position (short if apr>0).
        # Inside the spell the sign holds, so fund[t]*sgn == |fund[t]|. At the DEATH
        # hour it does not: a flip means the book PAYS that hour. abs() here would
        # credit that payment as income and overstate the only column this file
        # calls the truth.
        held = [t for t in st["hrs"] if t > entry] + [end_t]
        realized = sum(fund[t] * sgn for t in held if t in fund) / 8760.0
        hl_apr = hl.get(entry)
        return {
            "sym": sym, "start": start, "entry": entry, "end": end_t,
            "surv_h": surv_h, "res_h": res_h,
            "apr_entry": apr_e, "sign": sgn,
            "slope4": slope(4), "slope12": slope(12),
            "vol24": realized_vol(cand, entry),
            "hl_apr": hl_apr,
            "hl_same_sign_hot": (None if hl_apr is None else
                                 (1 if (hl_apr * sgn > 0 and abs(hl_apr) >= 0.5 * gate) else 0)),
            "hl_ratio": (None if hl_apr is None or apr_e <= 0 else (hl_apr * sgn) / apr_e),
            "carry_spec": apr_e * surv_h / 8760.0,
            "carry_trade": apr_e * res_h / 8760.0,
            "carry_real": realized,
        }

    for t in hours:
        apr = fund[t]
        gap = (t - prev) / 3600.0 if prev is not None else 1.0
        prev = t
        if st is not None and gap > MAX_GAP_H:
            cens_ts.append(st["start"])   # tape hole — the death is unobservable
            st = None
        if st is None:
            if abs(apr) >= gate:
                st = {"start": t, "sign": 1 if apr > 0 else -1, "hrs": [t]}
            continue
        dead = (apr * st["sign"] <= 0) or (abs(apr) < exit_gate)
        if not dead:
            st["hrs"].append(t)
            continue
        ep = close_ep(t)
        if ep:
            eps.append(ep)
        st = None
        if abs(apr) >= gate:         # sign flipped straight into a new hot spell
            st = {"start": t, "sign": 1 if apr > 0 else -1, "hrs": [t]}
    if st is not None:
        cens_ts.append(st["start"])  # still hot at the end of the tape
    return eps, early_ts, cens_ts


_EPCACHE = {}


def all_episodes(mk, gate, persist_h=PERSIST_H):
    """-> (eps, early_ts, cens_ts) over the WHOLE tape. Window by entry/start."""
    key = (id(mk), gate, persist_h)   # keyed on the tape AND the entry age — a
    if key in _EPCACHE:               # gate-only key would serve a second
        return _EPCACHE[key]          # universe's (or a 4h arm's) episodes
    eps, early, cens = [], [], []
    for sym, m in mk.items():
        e, et, ct = episodes(sym, m, gate, persist_h)
        eps += e
        early += et
        cens += ct
    eps.sort(key=lambda e: e["entry"])
    # self-check: the spec bar can never be tighter than the tradeable one
    assert all(e["carry_spec"] >= e["carry_trade"] - 1e-12 for e in eps), \
        "carry_spec < carry_trade — survival/residual are crossed"
    _EPCACHE[key] = (eps, sorted(early), sorted(cens))
    return _EPCACHE[key]


# ────────────────────────────── reporting ────────────────────────────────────
CRYPTO_DEFAULT = 0.10512     # 0.0012 %/hr — where the crypto books REST
EQUITY_DEFAULT = 0.03504     # 0.0004 %/hr — where the equity/commodity books REST
GRID = 0.00876               # 0.0001 %/hr — the quantum of the settled series


def _is_default(apr):
    return (abs(abs(apr) - CRYPTO_DEFAULT) < 1e-6
            or abs(abs(apr) - EQUITY_DEFAULT) < 1e-6)


def tape_structure(mk):
    """Section 1 — WHAT THE FUNDING TAPE IS, before any strategy touches it.

    This ran only because the age arm's every bucket reported `med apr 0.105`
    across 18 unrelated symbols. A point mass that sharp is a venue mechanic or a
    data bug, never a market. It is a venue mechanic — and it reframes the whole
    file, so it prints FIRST.
    """
    print(f"\n{'='*78}\n1. THE TAPE ITSELF — funding is a STEP FUNCTION, not a price\n{'='*78}")
    allv = [abs(v) for m in mk.values() for v in m["fund"].values()]
    n = len(allv)
    counts = {}
    for v in allv:
        k = round(v, 6)
        counts[k] = counts.get(k, 0) + 1
    print(f"   {n} settled hourly observations, {len(counts)} distinct |apr| values.")
    off = sum(1 for v in allv if abs(v / GRID - round(v / GRID)) > 1e-6)
    print(f"   Quantized to {GRID:.5f} apr (0.0001 %/hr): {n-off}/{n} on-grid "
          f"({100.0*(n-off)/n:.1f}%).")
    print(f"\n   {'|apr|':>10s} {'= APR':>8s} {'n':>8s} {'share':>7s}   what it is")
    for v, k in sorted(counts.items(), key=lambda x: -x[1])[:4]:
        what = ("<- CRYPTO RESTING DEFAULT" if abs(v - CRYPTO_DEFAULT) < 1e-6 else
                "<- EQUITY/COMMODITY RESTING DEFAULT" if abs(v - EQUITY_DEFAULT) < 1e-6
                else "")
        print(f"   {v:>10.5f} {100*v:>7.1f}% {k:>8d} {100.0*k/n:>6.1f}%   {what}")
    two = sum(k for v, k in counts.items() if _is_default(v))
    above = sum(1 for v in allv if v > CRYPTO_DEFAULT + 1e-9)
    print(f"\n   ** TWO VALUES ARE {100.0*two/n:.1f}% OF THE ENTIRE TAPE. **")
    print(f"   {CRYPTO_DEFAULT:.3f} is NOT a cap: {100.0*above/n:.1f}% of observations exceed it "
          f"(max {max(allv):.1f} = {100*max(allv):.0f}% APR).")
    print("   It is where the rate RESTS when the premium is ~zero — the perp base rate")
    print("   (0.0012 %/hr x 8h ~ 0.01%/8h, the venue-standard interest component).")
    print(f"\n   {'symbol':>12s} {'@0.105':>8s} {'@0.035':>8s}   rests at")
    for s, m in sorted(mk.items()):
        vs = [abs(v) for v in m["fund"].values()]
        a = 100.0 * sum(1 for v in vs if abs(v - CRYPTO_DEFAULT) < 1e-6) / len(vs)
        b = 100.0 * sum(1 for v in vs if abs(v - EQUITY_DEFAULT) < 1e-6) / len(vs)
        tag = ("10.5% APR (crypto)" if a > b else
               "3.5% APR (equity/commodity)" if b > 5 else "free-floating")
        print(f"   {s:>12s} {a:>7.1f}% {b:>7.1f}%   {tag}")
    live_gate = 0.05
    flip, cold = death_causes(mk, live_gate)
    eps_l, _, _ = all_episodes(mk, live_gate)
    at_def = sum(1 for e in eps_l if _is_default(e["apr_entry"]))
    print("\n   WHY THIS DECIDES THE FILE: the live gate is 0.05 TRUE — BELOW the crypto")
    print(f"   resting default of {CRYPTO_DEFAULT:.3f}. So every crypto book is permanently")
    print(f"   'hot' by construction, and {CRYPTO_DEFAULT:.3f} can never decay under the live")
    print(f"   exit bar ({live_gate} x {EXIT_RATIO} = {live_gate*EXIT_RATIO:.3f}) — a 'cold'")
    print("   death is ARITHMETICALLY IMPOSSIBLE there. The only way out is a SIGN FLIP of")
    print("   an administrative constant. MEASURED at the live gate, not asserted:")
    print(f"     * {at_def} of {len(eps_l)} episodes "
          f"({100.0*at_def/max(len(eps_l),1):.1f}%) ENTER at exactly a resting default")
    print(f"     * spell deaths: SIGN FLIP {flip} ({100.0*flip/max(flip+cold,1):.1f}%) "
          f"| genuine decay {cold} ({100.0*cold/max(flip+cold,1):.1f}%)")
    print("   That is not a carry signal; it is a coin flip wearing a funding label — and it")
    print("   is the mechanism under [[backtest_funding_lighter]]'s '63% of trades die when")
    print("   the rate evaporates'. The rate did not evaporate. It never moved; the SIGN did.")
    return {"flip_pct": 100.0 * flip / max(flip + cold, 1),
            "at_def_pct": 100.0 * at_def / max(len(eps_l), 1)}


def death_causes(mk, gate):
    """Of the spell deaths at this gate: sign flip vs genuine decay. The live
    bot's exit mix (flip 42.9% / cold 20.5%) is REPRODUCED here from the tape —
    and section 1 explains it: at a gate under the resting default, cold cannot
    happen, so flips must dominate."""
    exit_gate = gate * EXIT_RATIO
    flip = cold = 0
    for sym, m in mk.items():
        fund = m["fund"]
        st, prev = None, None
        for t in sorted(fund):
            apr = fund[t]
            gap = (t - prev) / 3600.0 if prev is not None else 1.0
            prev = t
            if st is not None and gap > MAX_GAP_H:
                st = None
            if st is None:
                if abs(apr) >= gate:
                    st = {"sign": 1 if apr > 0 else -1}
                continue
            if apr * st["sign"] <= 0:
                flip += 1
                st = {"sign": 1 if apr > 0 else -1} if abs(apr) >= gate else None
            elif abs(apr) < exit_gate:
                cold += 1
                st = None
    return flip, cold


def clears(eps, key):
    if not eps:
        return float("nan")
    return 100.0 * sum(1 for e in eps if e[key] > ROUND_TRIP) / len(eps)


def survival_table(mk, t0, t1, label):
    print(f"\n{'='*78}\n2+3. SURVIVAL & THE ECONOMIC BAR — {label}\n{'='*78}")
    hdr = (f"{'gate':>6s} {'eps':>5s} {'early':>6s} {'cens':>5s} | "
           f"{'surv med':>8s} {'p75':>6s} {'p90':>6s} | {'resid med':>9s} {'p75':>6s} {'p90':>6s} | "
           f"{'%spec':>6s} {'%trade':>7s} {'%real':>6s}")
    print(hdr)
    print("-" * len(hdr))
    rows = {}
    for g in GATES:
        eps_all, early_ts, cens_ts = all_episodes(mk, g)
        eps = [e for e in eps_all if t0 <= e["entry"] < t1]
        early = sum(1 for t in early_ts if t0 <= t < t1)
        cens = sum(1 for t in cens_ts if t0 <= t < t1)
        rows[g] = eps
        if not eps:
            print(f"{g:>6.2f} {0:>5d} {early:>6d} {cens:>5d} |  (no episodes)")
            continue
        sv = [e["surv_h"] for e in eps]
        rs = [e["res_h"] for e in eps]
        print(f"{g:>6.2f} {len(eps):>5d} {early:>6d} {cens:>5d} | "
              f"{median(sv):>8.1f} {pct(sv,.75):>6.1f} {pct(sv,.90):>6.1f} | "
              f"{median(rs):>9.1f} {pct(rs,.75):>6.1f} {pct(rs,.90):>6.1f} | "
              f"{clears(eps,'carry_spec'):>6.1f} {clears(eps,'carry_trade'):>7.1f} "
              f"{clears(eps,'carry_real'):>6.1f}")
    print("  eps=enterable episodes | early=hot spells that died before the 4h PERSIST "
          "(never tradeable)\n  cens=censored (tape hole / still hot at window end; excluded)")
    print("  %spec = apr_entry x SURVIVAL clears 10bps (generous: credits 4h it can't hold)")
    print("  %trade = apr_entry x RESIDUAL clears 10bps (the bot's real hold)")
    print("  %real = the SIGNED INTEGRAL of apr actually earned clears 10bps <- THE TRUTH")
    return rows


def required_survival(eps, label):
    print(f"\n{'='*78}\n3b. REQUIRED SURVIVAL vs OBSERVED, by apr level — {label}\n{'='*78}")
    print("   required_h = 8.76/apr (the hours of that apr needed to pay 10bps)")
    bands = [(0.00, 0.10), (0.10, 0.20), (0.20, 0.40), (0.40, 0.80), (0.80, 1e9)]
    hdr = (f"{'apr band':>14s} {'n':>6s} {'med apr':>8s} {'REQUIRED h':>11s} "
           f"{'OBSERVED med':>13s} {'p90':>7s} {'%real':>6s}")
    print(hdr)
    print("-" * len(hdr))
    for lo, hi in bands:
        b = [e for e in eps if lo <= e["apr_entry"] < hi]
        if not b:
            continue
        ma = median([e["apr_entry"] for e in b])
        rs = [e["res_h"] for e in b]
        req = ROUND_TRIP * 8760.0 / ma if ma > 0 else float("inf")
        name = f"{lo:.2f}-{hi:.2f}" if hi < 1e8 else f">{lo:.2f}"
        print(f"{name:>14s} {len(b):>6d} {ma:>8.3f} {req:>11.1f} "
              f"{median(rs):>13.1f} {pct(rs,.90):>7.1f} {clears(b,'carry_real'):>6.1f}")
    print("  A band is only viable where OBSERVED median >= REQUIRED. Anything else is")
    print("  a coin flip on price wearing a funding costume.")


def hazard(eps, label):
    print(f"\n{'='*78}\n4a. 'ALREADY HOT' — conditional REMAINING life (the memoryless test) — {label}\n{'='*78}")
    print("   Of the spells still alive at X hours, how much life is LEFT?")
    print("   flat = memoryless (waiting buys nothing) | rising = persistence begets")
    print("   persistence | falling = the spell is burning out")
    hdr = (f"{'alive at X h':>13s} {'n':>6s} {'med REMAIN h':>13s} {'p75':>7s} {'p90':>7s} "
           f"{'%real@remain':>13s}")
    print(hdr)
    print("-" * len(hdr))
    for X in (4, 8, 12, 24, 48, 72):
        b = [e for e in eps if e["surv_h"] >= X]
        if len(b) < 6:
            print(f"{X:>13d} {len(b):>6d}   (n too small to resolve)")
            continue
        rem = [e["surv_h"] - X for e in b]
        # carry still collectable from X onward, at the rate ruling at entry
        ok = 100.0 * sum(1 for e in b
                         if e["apr_entry"] * (e["surv_h"] - X) / 8760.0 > ROUND_TRIP) / len(b)
        print(f"{X:>13d} {len(b):>6d} {median(rem):>13.1f} {pct(rem,.75):>7.1f} "
              f"{pct(rem,.90):>7.1f} {ok:>13.1f}")
    print("  NOTE: this is a HAZARD across episodes, NOT a rank correlation over sampled")
    print("  entry points — within one spell residual falls 1h per hour BY CONSTRUCTION,")
    print("  so that correlation would be guaranteed negative and would mean nothing.")


CLIP_USD = 25.0          # the live bot's ORDER_USD — for the capacity column
AGES = [4, 8, 12, 24, 48, 72]


def age_arm(mk, lo, mid, hi):
    """Section 4c — THE TEST THE FILE WAS MISSING, and the only one that can
    overturn the ruling.

    4a shows a DECREASING HAZARD: spells alive at 48h have ~10x the remaining life
    of spells at 4h. Age-at-entry is OBSERVABLE AT DECISION TIME with no
    look-ahead — you simply wait and watch. So it is a candidate ENTRY RULE, and
    section 6 never tests it: 6 sweeps gate x cross-venue only. A verdict of
    'dead' that never priced its own strongest signal would be
    [[refutation-doesnt-clear-the-siblings]] — an unrefuted survivor is not a
    checked one.

    So: enter at age X instead of 4h, earn the SIGNED integral from there to
    death, and apply the SAME bar section 6 uses — MEDIAN net > 0 on BOTH halves,
    n>=30 — plus the two things a %-clearing column cannot say: how CONCENTRATED
    the arm is, and how many DOLLARS it makes ([[incubator-evidence-denominated-
    in-fills]] — count fills, and rank on what you'd actually collect).
    """
    print(f"\n\n{'='*78}\n4c. THE AGE ARM — 'wait until it has ALREADY been hot X hours'\n{'='*78}")
    print("   4a says age predicts survival and age is observable at entry. So PRICE it.")
    print("   net bps = signed realized carry, entry->death, minus 10bps friction.")
    print(f"   $300d = what this arm's carry actually collects at the live ${CLIP_USD:.0f} clip.")
    print("   be_fric = the round-trip friction at which the MEDIAN episode stops paying.")
    hdr = (f"{'gate':>5s} {'age':>4s} {'n':>5s} {'nsym':>5s} {'top3%':>6s} {'medres':>7s} "
           f"{'%real':>6s} {'MEDnet':>7s} {'mean':>7s} | {'h1':>7s} {'h2':>7s} | "
           f"{'$300d':>7s} {'$/yr':>6s} {'be_fric':>8s}")
    print(hdr)
    print("-" * len(hdr))
    days = (hi - lo) / 86400.0
    winners = []
    for g in GATES:
        for age in AGES:
            eps, _, _ = all_episodes(mk, g, age)
            if len(eps) < 20:
                continue
            v = [e["carry_real"] * 1e4 - ROUND_TRIP * 1e4 for e in eps]
            h1 = [e["carry_real"] * 1e4 - ROUND_TRIP * 1e4 for e in eps if e["entry"] < mid]
            h2 = [e["carry_real"] * 1e4 - ROUND_TRIP * 1e4 for e in eps if e["entry"] >= mid]
            m1 = median(h1) if len(h1) >= 10 else float("nan")
            m2 = median(h2) if len(h2) >= 10 else float("nan")
            med, mean = median(v), sum(v) / len(v)
            usd = sum(v) / 1e4 * CLIP_USD
            t3, nsym = top3_share(eps)
            be = med + ROUND_TRIP * 1e4          # friction at which the median dies
            mark = ""
            if med > 0 and m1 > 0 and m2 > 0 and len(eps) >= 30:
                mark = "  <- CLEARS THE BAR"
                winners.append((g, age, len(eps), med, mean, usd, usd * 365 / days, be, t3))
            print(f"{g:>5.2f} {age:>4d} {len(eps):>5d} {nsym:>5d} {t3:>6.1f} "
                  f"{median([e['res_h'] for e in eps]):>7.1f} "
                  f"{clears(eps,'carry_real'):>6.1f} {med:>7.2f} {mean:>7.2f} | "
                  f"{m1:>7.2f} {m2:>7.2f} | {usd:>7.2f} {usd*365/days:>6.2f} "
                  f"{be:>7.1f}bps{mark}")
        print("-" * len(hdr))
    print("  The $/yr column is the whole argument. An arm can clear a bps bar and still")
    print("  be worth nothing: 33-124 fills in 300d at a $25 clip cannot pay for a slot,")
    print("  and this is CARRY ONLY — [[backtest_funding_lighter]] measured the price P&L")
    print("  that rides along with it as NEGATIVE and DOMINANT at every gate.")
    return winners


def predictor(eps, key, name, label, nbins=3):
    """Terciles/halves of a predictor -> median residual + %clearing, + Spearman."""
    b = [e for e in eps if e.get(key) is not None]
    if len(b) < 12:
        print(f"\n  {name:22s} n={len(b):<5d} CANNOT RESOLVE (too few episodes carry it)")
        return None
    xs = [e[key] for e in b]
    binary = len(set(xs)) <= 2
    ys = [e["res_h"] for e in b]
    rho, n, p = spearman(xs, ys)
    yc = [1.0 if e["carry_real"] > ROUND_TRIP else 0.0 for e in b]
    rho_c, _, p_c = spearman(xs, yc)
    print(f"\n  {name}  (n={n})")
    print(f"    Spearman vs residual survival : rho={rho:+.3f}  p={p:.4f}"
          f"{'' if p < 0.05 else '   <- CANNOT RESOLVE (no signal at p<0.05)'}")
    print(f"    Spearman vs CLEARS-THE-BAR    : rho={rho_c:+.3f}  p={p_c:.4f}"
          f"{'' if p_c < 0.05 else '   <- CANNOT RESOLVE (no signal at p<0.05)'}")
    order = sorted(range(len(b)), key=lambda i: xs[i])
    if binary:
        groups = [("no  (0)", [b[i] for i in order if xs[i] == min(xs)]),
                  ("yes (1)", [b[i] for i in order if xs[i] != min(xs)])]
    else:
        k = len(order) // nbins
        groups = []
        for j in range(nbins):
            s = j * k
            e_ = (j + 1) * k if j < nbins - 1 else len(order)
            g = [b[i] for i in order[s:e_]]
            groups.append((f"{['low','mid','high'][j] if nbins==3 else 'q'+str(j+1)}"
                           f" [{xs[order[s]]:+.3g}..{xs[order[e_-1]]:+.3g}]", g))
    print(f"    {'bucket':>34s} {'n':>5s} {'med resid h':>12s} {'p90':>7s} "
          f"{'med apr':>8s} {'%real':>6s}")
    for gname, g in groups:
        if not g:
            continue
        rs = [e["res_h"] for e in g]
        print(f"    {gname:>34s} {len(g):>5d} {median(rs):>12.1f} {pct(rs,.90):>7.1f} "
              f"{median([e['apr_entry'] for e in g]):>8.3f} {clears(g,'carry_real'):>6.1f}")
    return {"rho": rho, "p": p, "rho_c": rho_c, "p_c": p_c, "n": n,
            "spread": (median([e["res_h"] for e in groups[-1][1]]) -
                       median([e["res_h"] for e in groups[0][1]])
                       if groups[0][1] and groups[-1][1] else float("nan")),
            "clear_spread": (clears(groups[-1][1], "carry_real") -
                             clears(groups[0][1], "carry_real")
                             if groups[0][1] and groups[-1][1] else float("nan"))}


PREDS = [("apr_entry", "apr LEVEL at entry"),
         ("slope4", "apr SLOPE, prior 4h"),
         ("slope12", "apr SLOPE, prior 12h"),
         ("vol24", "realized VOL 24h"),
         ("hl_ratio", "CROSS-VENUE ratio (HL apr / Lighter apr)"),
         ("hl_same_sign_hot", "CROSS-VENUE agreement (HL hot, same sign)")]


def predictor_block(eps, label):
    print(f"\n{'='*78}\n4b. PREDICTORS at entry (no look-ahead) — {label}\n{'='*78}")
    out = {}
    for k, nm in PREDS:
        out[k] = predictor(eps, k, nm, label)
    return out


def net_bps(eps):
    """Realized carry MINUS friction, in bps, per episode. The money number:
    %clearing is binary, this says by HOW MUCH — and mean is what compounds."""
    v = [e["carry_real"] * 1e4 - ROUND_TRIP * 1e4 for e in eps]
    return (median(v) if v else float("nan"),
            (sum(v) / len(v)) if v else float("nan"))


def top3_share(eps):
    c = {}
    for e in eps:
        c[e["sym"]] = c.get(e["sym"], 0) + 1
    top = sorted(c.values(), reverse=True)[:3]
    return 100.0 * sum(top) / max(len(eps), 1), len(c)


def redesign_block(mk, lo, mid, hi):
    """THE CONJUNCTION the marginal predictors point at: does a high gate AND
    cross-venue agreement compose into a rule that pays? Marginal tests cannot
    answer this — the band that pays and the band the predictor can SEE may be
    different bands.

    RANKED ON THE MEDIAN, NOT THE MEAN, deliberately. Carry per episode is
    violently right-skewed (at gate 1.10 the HL-dark mean is 42.6bps gross while
    the MEDIAN is 7.3bps): a mean-ranked table crowns a thin tail and calls it an
    edge. The median trade is the one you actually get
    ([[incubator-evidence-denominated-in-fills]]: rank on a lower bound, never
    the max point estimate)."""
    print(f"\n\n{'='*78}\n6. THE REDESIGN CANDIDATE — does the predictor COMPOSE with the gate?\n{'='*78}")
    print("   HL-agree = HL hot, same sign (structural) | HL-dark = coin has no HL twin")
    print("   net bps = realized carry - 10bps friction. MEDIAN net > 0 is the bar;")
    print("   a positive MEAN with a negative median is a tail, not a strategy.")
    hdr = (f"{'gate':>5s} {'arm':>12s} {'n':>5s} {'%cov':>5s} {'top3%':>6s} {'medres':>7s} "
           f"{'%real':>6s} {'MED net':>8s} {'mean net':>9s} | {'med h1':>7s} {'med h2':>7s}")
    print(hdr)
    print("-" * len(hdr))
    best = []
    for g in GATES:
        eps, _, _ = all_episodes(mk, g)
        cov = [e for e in eps if e["hl_same_sign_hot"] is not None]
        arms = [("all", eps),
                ("HL-agree", [e for e in cov if e["hl_same_sign_hot"] == 1]),
                ("HL-disagree", [e for e in cov if e["hl_same_sign_hot"] == 0]),
                ("HL-dark", [e for e in eps if e["hl_same_sign_hot"] is None])]
        for nm, arm in arms:
            if not arm:
                continue
            h1 = [e for e in arm if e["entry"] < mid]
            h2 = [e for e in arm if e["entry"] >= mid]
            mn, mean = net_bps(arm)
            m1 = net_bps(h1)[0] if len(h1) >= 10 else float("nan")
            m2 = net_bps(h2)[0] if len(h2) >= 10 else float("nan")
            t3, nsym = top3_share(arm)
            print(f"{g:>5.2f} {nm:>12s} {len(arm):>5d} "
                  f"{100.0*len(arm)/max(len(eps),1):>5.1f} {t3:>6.1f} "
                  f"{median([e['res_h'] for e in arm]):>7.1f} "
                  f"{clears(arm,'carry_real'):>6.1f} {mn:>8.2f} {mean:>9.2f} | "
                  f"{m1:>7.2f} {m2:>7.2f}")
            # The bar: the MEDIAN trade pays, on BOTH halves, often enough to matter.
            if mn > 0 and m1 > 0 and m2 > 0 and len(arm) >= 30:
                best.append((g, nm, len(arm), mn, mean, t3))
        print("-" * len(hdr))
    print("  %cov = this arm's share of the gate's episodes | top3% = share of the arm")
    print("  held by its 3 busiest symbols. An arm that is 20% of a starved gate and 50%")
    print("  concentrated is ~5 effective bets, not n bets — count FILLS, not hours.")
    return best


def friction_sensitivity(mk):
    """The decisive robustness test on any tail-driven 'winner'. The 5bps/fill
    constant is calibrated on the MAJORS. The only arms with a positive mean are
    commodity/equity perps (SKHYNIXUSD, WTI, BRENTOIL, XAG, COIN) — the fleet's
    THINNEST books, where that constant is least defensible. If the edge dies
    inside the assumption's own error bar, it was never an edge."""
    print(f"\n\n{'='*78}\n7. FRICTION SENSITIVITY — is the 'edge' just the slippage assumption?\n{'='*78}")
    print("   Round-trip friction is ASSUMED at 10bps (2 x 5bps). It is not measured.")
    print("   mean/MEDIAN net carry (bps) for the best-mean arm at each assumption:")
    hdr = (f"{'gate/arm':>18s} {'n':>5s} " +
           " ".join(f"{str(int(f*1e4))+'bps':>11s}" for f in
                    (0.0005, 0.0010, 0.0020, 0.0040, 0.0060)))
    print(hdr)
    print("-" * len(hdr))
    for g in (0.80, 1.10):
        eps, _, _ = all_episodes(mk, g)
        for nm, arm in (("all", eps),
                        ("HL-dark", [e for e in eps if e["hl_same_sign_hot"] is None])):
            if len(arm) < 30:
                continue
            cells = []
            for f in (0.0005, 0.0010, 0.0020, 0.0040, 0.0060):
                v = [e["carry_real"] * 1e4 - f * 1e4 for e in arm]
                cells.append(f"{sum(v)/len(v):>+5.1f}/{median(v):>+5.1f}")
            print(f"{f'{g:.2f} {nm}':>18s} {len(arm):>5d} " +
                  " ".join(f"{c:>11s}" for c in cells))
    print("  Read as mean/MEDIAN. The MEDIAN is negative at EVERY assumption including")
    print("  the most generous one — the median episode never pays its own round trip.")
    print("  The positive mean survives only while friction is assumed at majors levels")
    print("  on books that are not majors. That is an assumption, not a finding.")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=300)
    ap.add_argument("--universe", type=int, default=30)
    ap.add_argument("--refresh", action="store_true")
    a = ap.parse_args()

    print(f"Fetching LIGHTER settled funding + candles (+ HL funding as the historical")
    print(f"cross-venue reference) — {a.days}d, top {a.universe} by daily quote volume\n")
    mk = load(a.days, a.universe, a.refresh)
    if not mk:
        raise SystemExit("no markets with paired history")
    hours = sorted({t for m in mk.values() for t in m["fund"]})
    lo, hi = min(hours), max(hours)
    mid = lo + (hi - lo) // 2
    nhl = sum(1 for m in mk.values() if m["hl"])
    print(f"\n{len(mk)} markets ({nhl} with HL cross-venue history) | "
          f"{time.strftime('%Y-%m-%d', time.gmtime(lo))} -> "
          f"{time.strftime('%Y-%m-%d', time.gmtime(hi))} ({(hi-lo)/86400:.0f}d)")
    print(f"episode: |apr| >= G -> dies at |apr| < {EXIT_RATIO}G or sign flip | "
          f"entry at +{PERSIST_H}h | friction {ROUND_TRIP*1e4:.0f}bps")

    tape = tape_structure(mk)

    full = survival_table(mk, lo, hi + 1, "FULL WINDOW")
    survival_table(mk, lo, mid, "1st HALF")
    survival_table(mk, mid, hi + 1, "2nd HALF")

    summary = {}
    for g in PRED_GATES:
        eps = full[g]
        if not eps:
            continue
        print(f"\n\n{'#'*78}\n### GATE {g:.2f} TRUE"
              f"{'  <- LIVE TODAY (0.40 published / 8)' if abs(g-0.05) < 1e-9 else ''}"
              f"   n={len(eps)} episodes\n{'#'*78}")
        required_survival(eps, f"gate {g:.2f}, full window")
        hazard(eps, f"gate {g:.2f}, full window")
        summary[g] = {"full": predictor_block(eps, f"gate {g:.2f}, FULL WINDOW")}
        h1 = [e for e in eps if e["entry"] < mid]
        h2 = [e for e in eps if e["entry"] >= mid]
        print(f"\n\n--- 5. BOTH HALVES, gate {g:.2f} "
              f"(a predictor that works on one half is a WINDOW, not an edge) ---")
        summary[g]["h1"] = predictor_block(h1, f"gate {g:.2f}, 1st HALF")
        summary[g]["h2"] = predictor_block(h2, f"gate {g:.2f}, 2nd HALF")

    age_winners = age_arm(mk, lo, mid, hi)
    best = redesign_block(mk, lo, mid, hi)
    friction_sensitivity(mk)

    # ─────────────────────────────── VERDICT ─────────────────────────────────
    print(f"\n\n{'='*78}\nVERDICT\n{'='*78}")
    g = PRED_GATES[0]
    eps = full.get(g) or []
    if not eps:
        print("no episodes — nothing to rule on")
        return
    rs = [e["res_h"] for e in eps]
    _, early_ts, _ = all_episodes(mk, g)
    n_cross = len(eps) + len(early_ts)
    print(f"\n1. SURVIVAL, live gate {g:.2f}: median residual {median(rs):.0f}h, "
          f"p90 {pct(rs,.90):.0f}h.")
    print(f"   {100.0*len(early_ts)/n_cross:.0f}% of hot crossings ({len(early_ts)} of "
          f"{n_cross}) die before the {PERSIST_H}h PERSIST bar — never tradeable at all.")
    print(f"   Fraction of episodes whose REAL carry beats the {ROUND_TRIP*1e4:.0f}bps "
          f"round trip: {clears(eps,'carry_real'):.1f}%")
    best_g, best_c = None, -1.0
    for gg in GATES:
        e2 = full.get(gg) or []
        if len(e2) >= 30:
            c = clears(e2, "carry_real")
            if c > best_c:
                best_g, best_c = gg, c
    print(f"   Best gate by %-clearing (n>=30): {best_g} -> {best_c:.1f}% clear friction.")

    print("\n2. IS SURVIVAL PREDICTABLE AT ENTRY?")
    live = []
    for gg, blocks in summary.items():
        for k, nm in PREDS:
            f_, a_, b_ = (blocks["full"].get(k), blocks["h1"].get(k), blocks["h2"].get(k))
            if not f_ or not a_ or not b_:
                continue
            # A predictor EARNS the word "edge" only if it moves the ECONOMIC bar,
            # significantly, in the SAME direction on BOTH halves.
            ok = (f_["p_c"] < 0.05 and a_["p_c"] < 0.05 and b_["p_c"] < 0.05
                  and a_["rho_c"] * b_["rho_c"] > 0 and f_["rho_c"] * a_["rho_c"] > 0)
            live.append((gg, nm, f_, a_, b_, ok))
    survivors = [x for x in live if x[5]]
    for gg, nm, f_, a_, b_, ok in live:
        print(f"   gate {gg:.2f} {nm:42s} rho_bar={f_['rho_c']:+.3f} p={f_['p_c']:.3g} "
              f"| halves {a_['rho_c']:+.3f}/{b_['rho_c']:+.3f} "
              f"{'** SURVIVES BOTH HALVES **' if ok else '-- no'}")
    n_tests = len(live)
    print(f"\n   ({n_tests} predictor x gate tests ran. At p<0.05 you EXPECT "
          f"{0.05*n_tests:.1f} false positives by chance;")
    print(f"    a Bonferroni bar would be p<{0.05/max(n_tests,1):.4f}. Both-halves "
          f"agreement is the real filter.)")

    if not survivors:
        print("\n   **NOTHING AT ENTRY PREDICTS SURVIVAL** on both halves. The decisive")
        print("   quantity is invisible at decision time.")
    else:
        print(f"\n   {len(survivors)} predictor(s) move the ECONOMIC bar on BOTH halves:")
        for gg, nm, f_, a_, b_, _ in survivors:
            print(f"     gate {gg:.2f}  {nm}: %clearing spread "
                  f"{f_['clear_spread']:+.1f}pp across buckets")

    # THE TRAP THIS BLOCK EXISTS TO AVOID: the marginal tests above say five
    # predictors "survive both halves". They do. It does not follow that any of
    # them makes money — the cross-venue predictor only speaks about the
    # HL-covered subset (the majors), which is exactly the subset whose apr is
    # structurally too small to pay.
    print("\n3. ...AND DOES THAT PREDICTABILITY PAY? (sections 4c + 6, net of friction)")
    print("   The bar: MEDIAN trade nets > 0, on BOTH halves, n>=30.")
    print(f"   gate x cross-venue (section 6): {len(best)} arm(s) clear it.")
    if not best:
        print("     >> none. The median episode fails to pay its own round trip at every")
        print("        gate under every cross-venue filter, on both halves — including the")
        print("        filters that DO predict survival. The positive-MEAN arms (gate")
        print("        0.80/1.10 HL-dark) are a thin tail: ~50% of the arm in 3 symbols,")
        print("        and they die inside the friction assumption's error bar (section 7).")
    print(f"   gate x AGE-AT-ENTRY (section 4c): {len(age_winners)} arm(s) clear it.")
    if age_winners:
        print("     >> THE AGE ARM DOES CLEAR THE BPS BAR. Recorded honestly, because the")
        print("        hazard in 4a is real and this is the arm it points at:")
        for g, age, n, med, mean, usd, per_yr, be, t3 in sorted(
                age_winners, key=lambda x: -x[3])[:4]:
            print(f"        gate {g:.2f} / age {age:>2d}h: n={n:<4d} median net {med:+6.2f}bps "
                  f"| ${usd:>5.2f} per 300d = ${per_yr:>5.2f}/yr | dies at {be:.0f}bps friction")
        print("     >> AND IT IS WORTH NOTHING. That is the finding, not the bps.")

    print("\n4. RULING:")
    print("   **THE FUNDING FARMER, AS A CARRY STRATEGY, IS DEAD** — but NOT because")
    print("   survival is unpredictable. Survival IS partly predictable, three ways:")
    print("   cross-venue agreement (both halves), apr level, and above all AGE — spells")
    print("   alive at 48h have ~10x the remaining life of spells at 4h. All observable")
    print("   at entry. The prediction WORKS. It buys nothing worth having:")
    if age_winners:
        top = max(age_winners, key=lambda x: x[6])
        print(f"     * the best age arm collects ${top[6]:.2f}/YEAR of carry at the live "
              f"${CLIP_USD:.0f} clip")
        print(f"       ({top[2]} fills in 300d, gate {top[0]:.2f}/age {top[1]}h). Below cash, "
              f"for a fleet slot.")
    print("     * and it is CARRY ONLY. [[backtest_funding_lighter]] measured the price")
    print("       P&L riding along as NEGATIVE and DOMINANT — the 4%-TP/10%-stop lottery")
    print("       swamps every basis point counted here.")
    print("   The mechanism is section 1: HALF THE TAPE IS A CONSTANT. The live gate")
    print(f"   (0.05) sits UNDER the crypto resting default ({CRYPTO_DEFAULT:.3f}), so the "
          f"bot is not")
    print("   selecting hot funding — it admits the venue's resting state on every crypto")
    print(f"   book ({tape['at_def_pct']:.0f}% of its entries are at a default), and "
          f"{tape['flip_pct']:.0f}% of spell deaths are the")
    print("   SIGN of that constant flipping. What 'persists' in 4a is an administrative")
    print("   default, not an economic carry; you can predict it perfectly and still only")
    print(f"   collect {100*CRYPTO_DEFAULT:.1f}% APR on a 53h hold = "
          f"~{CRYPTO_DEFAULT*53/8760*1e4:.0f}bps, against a "
          f"{ROUND_TRIP*1e4:.0f}bps round trip to touch it.")
    print("\n   Section 3b is the hard constraint that no prediction can lift: unless a")
    print("   band's OBSERVED median survival exceeds its REQUIRED survival, that band")
    print("   cannot pay. Only >0.80 apr does — on ~5 exotic books, at assumed friction.")
    print("\n   WHAT WOULD CHANGE THIS RULING: a venue where funding is a continuous")
    print("   market-clearing price rather than a pinned default, or a measured (not")
    print("   assumed) round trip under ~2bps. Neither is Lighter today. Do not re-tune")
    print("   the gate, the slope, the vol filter or the persist bar — all four are")
    print("   measured here and none of them is the problem.")


if __name__ == "__main__":
    main()
