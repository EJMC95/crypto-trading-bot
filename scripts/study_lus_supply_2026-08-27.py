#!/usr/bin/env python3
"""🇵🇹 THE LUS COHORT SUPPLY SEARCH — is there a cell to be born into?

Eamon, 27-Aug: *"Can you put the wire in? And put through the top three
candidates as famous Portuguese men and women"* -> *"Full permission to
proceed"*.

CLAUDE.md's own naming rule sets the order and this script is the first two
steps of it: **supply -> spend -> build -> name**. A Portuguese name clears
neither I20 nor I22, so the question in front of the build is not "what shall
we call them" but "is there an unclaimed cell whose design can be DECIDED
inside 60 days".

WHAT IT MEASURES, in the order that makes the last one believable:

  1. `--supply`   The venue's whole population, split by the venue's OWN
                  `strategy_index`, then CLAIMED vs UNCLAIMED against every
                  living book's actual universe. I20's first half: name the
                  supply, and name every living book whose gate admits it.
                  Claims are read from the modules themselves, never retyped
                  (a retyped constant is a constant that drifts).

  2. `--neff`     The whole premise, and the one number that can kill it.
                  I22: market count is not bet count. `N_eff` is computed
                  correlation-aware over DAILY returns from the venue's own
                  candles — `N_eff = (sum w)^2 / (w' R w)` at equal weight,
                  which is the standard effective-number-of-bets under a
                  correlation matrix R and reduces to n when R = I.
                  Reported for crypto, for the family's claimed non-crypto
                  ten, and for the unclaimed set — because the claim being
                  tested is that the unclaimed set is MORE INDEPENDENT, and
                  an unclaimed basket that reads N_eff 1.2 is worth nothing
                  however many names it has.

  3. `--sessions` The candidate AXIS. These are perps on underlyings that
                  keep SESSIONS, and 🧭 cook already measured (19-Aug) that
                  its dislocation edge concentrates when the underlying is
                  CLOSED (+0.409%/t=+2.34 vs +0.007%/t=+0.02 open). That is
                  a time axis, which I20 explicitly admits as differentiation
                  — but it is cook's measurement on cook's band, so it is a
                  HYPOTHESIS here and is labelled as one until measured on a
                  candidate's own rule.

REPORTED, NEVER RANKED: every correlation is over the window the venue
actually has, and a pair with too few overlapping days returns **None, never
0.0** — zero reads as perfectly diversifying and would BUY the very thing
this script exists to doubt (the (sr) fail-safe, same reason).

READ-ONLY. Prints and exits 0. Mints nothing, writes no lever, moves no
capital — the build is a separate, later act that this either justifies or
refuses.
"""
import argparse
import collections
import importlib.util
import math
import pathlib
import sys
import time

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fleet_bus                                            # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sse", ROOT / "scripts" / "study_sniper_exit_shape_2026-08-20.py")
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)
fetch_candles = _sse.fetch_candles
order_book_details = _sse.order_book_details

#: Turnover floor for a name to count as REAL supply. Not a round number:
#: (qq) measured the fleet's own fills at a MEAN 17.49bps and p90 398bps
#: below $0.1M/day, and 🧭 cook carries $0.5M for exactly that reason. A book
#: that cannot be filled has no supply however many rows the venue lists.
MIN_VOL = 5e5

#: Days of daily tape for the correlation matrix. Long enough that a single
#: news week cannot set the answer; short enough that every listed name has it.
CORR_DAYS = 180

#: A pair needs this many overlapping daily returns before its correlation is
#: allowed to speak. Below it the pair is None (unmeasurable), never 0.0.
MIN_OVERLAP = 60


# ------------------------------------------------------------------ population
def population():
    """Active markets -> [{sym, vol, cls, mmf, mid, created}], venue's own fields."""
    out = []
    for r in order_book_details():
        if r.get("status") != "active":
            continue
        try:
            out.append({
                "sym": r["symbol"],
                "mid": int(r["market_id"]),
                "vol": float(r.get("daily_quote_token_volume") or 0.0),
                "cls": r.get("strategy_index"),
                "mmf": int(r.get("maintenance_margin_fraction") or 0),
                "created": int(r.get("created_at") or 0) // 1000,
            })
        except (KeyError, TypeError, ValueError):
            continue
    return out


# ------------------------------------------------------------------- claimants
def claimants():
    """{symbol: [books whose universe admits it]} — READ FROM THE MODULES.

    I20's second half. Every entry here is imported or derived, never retyped:
    a hand-copied universe is the `backtest_carry_gate_lighter` defect, where
    a pinned MAX_POSITIONS=8 measured a book the fleet had already moved to 12.
    """
    who = collections.defaultdict(list)

    # 👩 mum · 🙏 avo · 🔮 georgia — one module, one universe.
    try:
        import lighter_family_bot as fam
        for c in list(fam.COINS):
            who[c].append("family(mum/avo/georgia)")
        for c in list(fam.NONCRYPTO_UNIVERSE):
            who[c].append("family(mum/avo/georgia)")
    except Exception as exc:                                # noqa: BLE001
        print(f"  ! family universe unreadable: {exc}")

    # 🧭 cook — top-N by volume above its own floor, NON-crypto by nature.
    try:
        import lighter_nav_cook_bot as cook
        who["__cook_floor__"] = [cook.MIN_VOL_M, cook.UNIVERSE_N]
    except Exception as exc:                                # noqa: BLE001
        print(f"  ! cook universe unreadable: {exc}")

    return who


def cook_admits(pop, who):
    """🧭 cook's universe is DERIVED (top-N by volume >= floor), so derive it."""
    cfg = who.get("__cook_floor__")
    if not cfg:
        return set()
    floor_m, n = cfg
    elig = [p for p in pop if p["vol"] >= float(floor_m) * 1e6]
    elig.sort(key=lambda p: -p["vol"])
    return {p["sym"] for p in elig[:int(n)]}


# ------------------------------------------------------------------- the census
def supply(args):
    pop = population()
    who = claimants()
    cookset = cook_admits(pop, who)
    for s in cookset:
        who[s].append("cook(band)")

    by_cls = collections.defaultdict(list)
    for p in pop:
        by_cls[p["cls"]].append(p)

    print(f"\nVENUE POPULATION — {len(pop)} active markets, "
          f"${sum(p['vol'] for p in pop)/1e6:,.1f}M/day")
    print(f"\n{'class':>6} {'n':>4} {'$M/day':>10}  {'n>=floor':>9}  sample")
    for c in sorted(by_cls, key=lambda x: (x is None, x)):
        rows = by_cls[c]
        v = sum(p["vol"] for p in rows)
        big = [p for p in rows if p["vol"] >= MIN_VOL]
        top = sorted(rows, key=lambda p: -p["vol"])[:5]
        tag = " (CRYPTO)" if c == fleet_bus.CRYPTO_STRATEGY_INDEX else ""
        print(f"{str(c):>6} {len(rows):>4} {v/1e6:>10.1f}  {len(big):>9}  "
              f"{', '.join(p['sym'] for p in top)}{tag}")

    nc = [p for p in pop
          if p["cls"] != fleet_bus.CRYPTO_STRATEGY_INDEX and p["vol"] >= MIN_VOL]
    nc.sort(key=lambda p: -p["vol"])

    # A directional CLAIM is what matters here: cook takes a premium EVENT on
    # its band, not a directional position, so it is reported separately.
    def dir_claims(sym):
        return [b for b in who.get(sym, []) if not b.startswith("cook")]

    claimed = [p for p in nc if dir_claims(p["sym"])]
    unclaimed = [p for p in nc if not dir_claims(p["sym"])]

    print(f"\nNON-CRYPTO AT OR ABOVE ${MIN_VOL/1e6:.1f}M/day: {len(nc)} markets, "
          f"${sum(p['vol'] for p in nc)/1e6:.1f}M/day")
    print(f"  DIRECTIONALLY CLAIMED : {len(claimed):>3} "
          f"(${sum(p['vol'] for p in claimed)/1e6:>7.1f}M/day)")
    print(f"  UNCLAIMED             : {len(unclaimed):>3} "
          f"(${sum(p['vol'] for p in unclaimed)/1e6:>7.1f}M/day)")

    print(f"\n{'symbol':<14}{'$M/day':>9} {'cls':>4} {'mmf':>6}  claimed by")
    for p in nc:
        d = dir_claims(p["sym"])
        ev = [b for b in who.get(p["sym"], []) if b.startswith("cook")]
        tag = ", ".join(d) if d else ("—" + ("  [+%s]" % ",".join(ev) if ev else ""))
        print(f"{p['sym']:<14}{p['vol']/1e6:>9.2f} {str(p['cls']):>4} "
              f"{p['mmf']:>5}b  {tag}")

    print("\nI20 NOTE — cook's admission is an EVENT gate on the premium band "
          "[45,60)bps,\n  not a directional claim on the name. It is listed "
          "in brackets so the\n  distinction is visible rather than assumed; a "
          "directional book on a name\n  cook can dislocate into is "
          "differentiated by AXIS, and that has to be\n  argued in the build, "
          "not waved at here.")
    return unclaimed


# ----------------------------------------------------------------------- N_eff
def daily_returns(mid, days=CORR_DAYS):
    """Daily log returns from the venue's own 1d candles -> {day_ts: ret}."""
    now = int(time.time())
    bars = fetch_candles(mid, now - days * 86400, now, resolution="1d")
    if not bars:
        return {}
    ts = sorted(bars)
    out = {}
    for a, b in zip(ts, ts[1:]):
        ca, cb = bars[a][3], bars[b][3]
        if ca > 0 and cb > 0:
            out[b] = math.log(cb / ca)
    return out


def corr(xs, ys):
    """Pearson over the OVERLAP only. None below MIN_OVERLAP — never 0.0."""
    common = sorted(set(xs) & set(ys))
    if len(common) < MIN_OVERLAP:
        return None
    a = [xs[t] for t in common]
    b = [ys[t] for t in common]
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a)
    vb = sum((y - mb) ** 2 for y in b)
    if va <= 0 or vb <= 0:
        return None
    cov = sum((x - ma) * (y - mb) for x, y in zip(a, b))
    return cov / math.sqrt(va * vb)


def n_eff(rets, names):
    """Effective number of bets at equal weight under the correlation matrix.

    `N_eff = (sum w)^2 / (w' R w)`; at equal weight that is `n^2 / sum(R_ij)`,
    which equals n when R = I and 1 when every pair is perfectly correlated.

    An UNMEASURABLE pair (too little overlap) is not silently treated as
    uncorrelated — that would inflate N_eff, i.e. manufacture the diversity
    this whole exercise is trying to establish. Such a pair takes the mean of
    the pairs that COULD be measured, which is the conservative substitution,
    and the count of them is reported so the reader can discount.
    """
    names = [s for s in names if rets.get(s)]
    n = len(names)
    if n == 0:
        return None, None, 0, 0
    if n == 1:
        return 1.0, None, 0, 0
    pairs, missing = [], 0
    grid = {}
    for i in range(n):
        for j in range(i + 1, n):
            c = corr(rets[names[i]], rets[names[j]])
            grid[(i, j)] = c
            if c is None:
                missing += 1
            else:
                pairs.append(c)
    if not pairs:
        return None, None, missing, n
    fill = sum(pairs) / len(pairs)
    total = float(n)                       # the n diagonal 1.0 terms
    for (i, j), c in grid.items():
        total += 2.0 * (fill if c is None else c)
    if total <= 0:
        return None, fill, missing, n
    # CAPPED AT n, and that cap is load-bearing rather than cosmetic. The ratio
    # `n^2 / sum(R)` exceeds n whenever the mean pairwise correlation is
    # NEGATIVE, and the first run of this script duly reported "N_eff 14.89"
    # from SIX names and "64.26" from six more — arithmetically correct for a
    # variance-reduction ratio and meaningless as a bet COUNT, which is the
    # quantity I22's `S_d^2 = SUM S_i^2` is additive in. Six sleeves cannot
    # earn a decision faster than six independent sleeves however they
    # co-move, so the honest number is min(ratio, n) and the raw ratio is
    # returned beside it rather than hidden.
    raw = (n * n) / total
    return min(raw, float(n)), fill, missing, n


def neff(args):
    pop = population()
    who = claimants()
    cookset = cook_admits(pop, who)

    crypto = [p for p in pop
              if p["cls"] == fleet_bus.CRYPTO_STRATEGY_INDEX and p["vol"] >= MIN_VOL]
    crypto.sort(key=lambda p: -p["vol"])
    nc = [p for p in pop
          if p["cls"] != fleet_bus.CRYPTO_STRATEGY_INDEX and p["vol"] >= MIN_VOL]
    nc.sort(key=lambda p: -p["vol"])

    def dir_claimed(sym):
        return [b for b in who.get(sym, []) if not b.startswith("cook")]

    baskets = {
        "crypto top-10 (what most books hold)":
            [p["sym"] for p in crypto[:10]],
        "family's claimed non-crypto 10":
            [p["sym"] for p in nc if dir_claimed(p["sym"])][:10],
        "UNCLAIMED non-crypto, top 10 by volume":
            [p["sym"] for p in nc if not dir_claimed(p["sym"])][:10],
        "UNCLAIMED non-crypto, all":
            [p["sym"] for p in nc if not dir_claimed(p["sym"])],
    }

    need = sorted({s for b in baskets.values() for s in b})
    mids = {p["sym"]: p["mid"] for p in pop}
    print(f"\nfetching {CORR_DAYS}d of daily tape for {len(need)} symbols "
          f"(venue throttle ~21/min, so this takes a minute)...")
    rets = {}
    for i, s in enumerate(need, 1):
        rets[s] = daily_returns(mids[s])
        if i % 10 == 0:
            print(f"  {i}/{len(need)}")

    print(f"\n{'basket':<42}{'n':>4}{'N_eff':>8}{'mean rho':>10}{'unmeas':>8}")
    for label, syms in baskets.items():
        ne, rho, miss, n = n_eff(rets, syms)
        ne_s = f"{ne:.2f}" if ne is not None else "—"
        rho_s = f"{rho:+.3f}" if rho is not None else "—"
        print(f"{label:<42}{n:>4}{ne_s:>8}{rho_s:>10}{miss:>8}")

    print("\nWHAT THIS DECIDES. I22: days-to-gate = (2/S_d)^2 and for "
          "independent\n  sleeves S_d^2 = SUM S_i^2 — so decidability velocity "
          "is ADDITIVE in\n  INDEPENDENT bets, not in market count. A basket "
          "whose N_eff is 1.2 earns\n  a decision at one sleeve's rate no "
          "matter how many rows it holds.")
    return rets


# -------------------------------------------------------------------- sessions
#: The underlying's own trading session, in UTC hours [open, close). The venue
#: runs the PERP 24/7; the underlying does not, which is the axis being tested.
#: DECLARED, not fetched — the venue's `market_config.trading_hours` is empty
#: on every row measured 27-Aug, so there is no on-venue source and these are
#: the standard sessions. Approximate by construction (no DST, no holidays),
#: which is why nothing here is a gate — it selects a bucket for MEASUREMENT.
SESSIONS = {
    "US-equity":   (13.5, 20.0),        # NYSE/Nasdaq 09:30-16:00 ET
    "KR-equity":   (0.0, 6.5),          # KRX 09:00-15:30 KST
    "CN-equity":   (1.5, 7.0),          # HKEX/SSE
    "EU-metal":    (7.0, 16.5),         # LBMA/LME core
    "energy":      (13.0, 18.5),        # NYMEX pit-equivalent core
}

CLASS_SESSION = {3: "EU-metal", 5: "US-equity", 6: "KR-equity", 4: None, 7: None}


def sessions(args):
    pop = population()
    who = claimants()
    nc = [p for p in pop
          if p["cls"] != fleet_bus.CRYPTO_STRATEGY_INDEX and p["vol"] >= MIN_VOL]
    nc.sort(key=lambda p: -p["vol"])

    def dir_claimed(sym):
        return [b for b in who.get(sym, []) if not b.startswith("cook")]

    print("\nTHE SESSION AXIS — unclaimed non-crypto by the underlying's own hours")
    print("  (I20 admits a TIME axis as differentiation; 🧭 cook measured the "
          "closed-\n   underlying concentration on ITS band, so this is a "
          "HYPOTHESIS here.)\n")
    buckets = collections.defaultdict(list)
    for p in nc:
        if dir_claimed(p["sym"]):
            continue
        buckets[CLASS_SESSION.get(p["cls"], None)].append(p)

    print(f"{'session':<12}{'UTC window':<16}{'n':>4}{'$M/day':>10}  names")
    for k in sorted(buckets, key=lambda x: (x is None, x)):
        rows = buckets[k]
        win = SESSIONS.get(k)
        w = f"{win[0]:04.1f}-{win[1]:04.1f}" if win else "—"
        names = ", ".join(p["sym"] for p in sorted(rows, key=lambda p: -p["vol"])[:8])
        print(f"{str(k):<12}{w:<16}{len(rows):>4}{sum(p['vol'] for p in rows)/1e6:>10.2f}  {names}")

    print("\n  A book whose positions sit in DIFFERENT session buckets holds "
          "bets whose\n  news arrives at different hours — which is the "
          "mechanical reason to expect\n  the low correlation `--neff` "
          "measures, rather than a hope that it is there.")


# ---------------------------------------------------------------- the basket
#: A book holds SLOTS, not a universe. `--neff` ranks by VOLUME because that is
#: how a naive selector picks, and (sr) measured that list-order selection is
#: exactly what collapses a basket to one bet. This asks the design question
#: instead: what is the BEST effective bet count reachable at a real cap, and
#: what does it cost in turnover to get there?
BASKET_K = 6


def _greedy_basket(rets, pool, k, seed=None):
    """Greedy max-N_eff subset. Not optimal; it is the (sr) `diversified_order`
    rule applied at DESIGN time — add the name that most raises N_eff next."""
    chosen = list(seed or [])
    pool = [s for s in pool if rets.get(s) and s not in chosen]
    if not chosen and pool:
        chosen = [pool[0]]
        pool = pool[1:]
    while len(chosen) < k and pool:
        best, best_ne = None, -1.0
        for s in pool:
            ne, _, _, _ = n_eff(rets, chosen + [s])
            if ne is not None and ne > best_ne:
                best, best_ne = s, ne
        if best is None:
            break
        chosen.append(best)
        pool.remove(best)
    return chosen


def basket(args):
    pop = population()
    who = claimants()
    mids = {p["sym"]: p["mid"] for p in pop}
    vols = {p["sym"]: p["vol"] for p in pop}

    crypto = sorted([p for p in pop
                     if p["cls"] == fleet_bus.CRYPTO_STRATEGY_INDEX
                     and p["vol"] >= MIN_VOL], key=lambda p: -p["vol"])
    nc = sorted([p for p in pop
                 if p["cls"] != fleet_bus.CRYPTO_STRATEGY_INDEX
                 and p["vol"] >= MIN_VOL], key=lambda p: -p["vol"])

    def dir_claimed(sym):
        return [b for b in who.get(sym, []) if not b.startswith("cook")]

    unclaimed = [p["sym"] for p in nc if not dir_claimed(p["sym"])]
    allnc = [p["sym"] for p in nc]
    cryp10 = [p["sym"] for p in crypto[:10]]

    need = sorted(set(unclaimed) | set(allnc) | set(cryp10))
    print(f"\nfetching {CORR_DAYS}d of daily tape for {len(need)} symbols...")
    rets = {}
    for i, s in enumerate(need, 1):
        rets[s] = daily_returns(mids[s])
        if i % 10 == 0:
            print(f"  {i}/{len(need)}")

    # ---- THE SPLIT. A greedy max-N_eff search over 180 days of history picks
    # the six names whose past correlations happened to be most negative, and
    # will report a spectacular in-sample number for any pool at all — that is
    # (oe)'s universe-churn finding wearing a different hat, and it is why this
    # measurement is worth nothing without a holdout. DESIGN on the older half,
    # SCORE on the newer half the design never saw.
    days = sorted({t for r in rets.values() for t in r})
    if len(days) < 2 * MIN_OVERLAP:
        print(f"\n  ! only {len(days)} daily observations — below "
              f"{2*MIN_OVERLAP} needed for an honest split. REFUSING to "
              f"report a designed basket.")
        return rets
    cut = days[len(days) // 2]
    train = {s: {t: v for t, v in r.items() if t < cut} for s, r in rets.items()}
    test = {s: {t: v for t, v in r.items() if t >= cut} for s, r in rets.items()}

    def show(label, syms, book=None):
        book = book or rets
        ne, rho, miss, n = n_eff(book, syms)
        ne_s = f"{ne:.2f}" if ne is not None else "—"
        rho_s = f"{rho:+.3f}" if rho is not None else "—"
        v = sum(vols.get(s, 0.0) for s in syms) / 1e6
        print(f"{label:<38}{n:>3}{ne_s:>7}{rho_s:>9}{v:>9.1f}M  "
              f"{', '.join(syms)}")

    print(f"\nBASKETS AT A REAL CAP (k={BASKET_K}) — FULL WINDOW (in-sample)")
    print(f"{'basket':<38}{'n':>3}{'N_eff':>7}{'rho':>9}{'turnover':>10}  names")
    show("crypto, volume-ranked", cryp10[:BASKET_K])
    show("unclaimed non-crypto, volume-ranked", unclaimed[:BASKET_K])
    des_all = _greedy_basket(rets, unclaimed, BASKET_K)
    show("unclaimed non-crypto, DESIGNED", des_all)

    print(f"\nTHE HOLDOUT — designed on days < {cut}, scored on days >= {cut}")
    print(f"{'basket':<38}{'n':>3}{'N_eff':>7}{'rho':>9}{'turnover':>10}  names")
    des_tr = _greedy_basket(train, unclaimed, BASKET_K)
    show("DESIGNED on train, scored on TRAIN", des_tr, train)
    show("  the same names, scored on TEST", des_tr, test)
    show("volume-ranked, scored on TEST", unclaimed[:BASKET_K], test)
    show("crypto volume-ranked, scored on TEST", cryp10[:BASKET_K], test)

    ne_tr, _, _, _ = n_eff(train, des_tr)
    ne_te, _, _, _ = n_eff(test, des_tr)
    ne_vol, _, _, _ = n_eff(test, unclaimed[:BASKET_K])
    print("\n  READ THE TEST ROW, NOT THE TRAIN ROW. The train number is what "
          "the design\n  was selected to maximise, so it is a restatement of "
          "the search, not a\n  finding. What decides the build is whether the "
          "DESIGNED basket still\n  beats the volume-ranked one on days the "
          "search never saw.")
    if None not in (ne_tr, ne_te, ne_vol):
        keep = (ne_te - 1.0) / (ne_tr - 1.0) if ne_tr > 1.0 else float("nan")
        print(f"\n  design held out : {ne_te:.2f} vs {ne_tr:.2f} in-sample "
              f"(kept {keep*100:.0f}% of the excess over 1 bet)")
        print(f"  vs volume-ranked: {ne_te:.2f} vs {ne_vol:.2f} — "
              f"{'DESIGN WINS' if ne_te > ne_vol else 'NO DESIGN PREMIUM'}")
    return rets


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--supply", action="store_true")
    ap.add_argument("--neff", action="store_true")
    ap.add_argument("--sessions", action="store_true")
    ap.add_argument("--basket", action="store_true")
    a = ap.parse_args()
    if not (a.supply or a.neff or a.sessions or a.basket):
        a.supply = a.neff = a.sessions = True
    if a.supply:
        supply(a)
    if a.sessions:
        sessions(a)
    if a.basket:
        basket(a)
    if a.neff:
        neff(a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
