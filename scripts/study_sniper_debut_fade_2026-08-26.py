#!/usr/bin/env python3
"""🎯 THE DEBUT FADE — why the sniper never flew, measured on Lighter's own tape.

Operator, 26-Aug: *"let listing sniper fly like it used to."*

It used to fly as `listing_sniper.py`, sniping SPOT listings across ~100 CEXes,
where a fresh listing is a buying event and LONG is the trade. This book snipes
PERP listings on ONE venue, and a perp lists AFTER the spot hype. This script
measures whether those are the same trade. They are not.

THREE MEASUREMENTS, in the order that makes the third believable:

  1. `--gradient`  Unconditional LONG return by AGE BAND, every hour of every
                   venue-priced book's own tape. No invented signal, no slice.
                   An earlier pass DID invent a slice ("the youngest eighth of
                   the band") and it returned OPPOSITE SIGNS on the same window
                   at identical n — so the slice was dropped rather than tuned,
                   and this reports the plain unconditional number.

  2. `--control`   The falling-tape objection, answered rather than waved off.
                   Item 18: this venue's whole tape is ONE falling-BTC regime,
                   so a short wins on almost anything by construction. Two
                   controls, both PAIRED WITHIN COIN so market drift cannot
                   produce the result — young vs the coin's OWN whole tape, and
                   young vs the coin's OWN mature band — plus the decisive one:
                   the identical bracket run on the SAME coins when MATURE.

  3. `--bracket`   The book's REAL exit (tp +15%, sl -10%, timer), because (ml)
                   is explicit that a mean says nothing about what a bracket
                   books. The STOP is checked BEFORE the target inside each
                   bar, so the convention is the conservative one.

REPORTED, NEVER RANKED: `t` is given both pooled and BY COIN. By-coin is the
honest unit — hours inside one coin overlap heavily, so the pooled `t` is
inflated by construction and is shown only so the gap is visible.
"""
import argparse
import datetime
import importlib.util
import math
import pathlib
import statistics as st
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import fleet_bus                                            # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "sse", ROOT / "scripts" / "study_sniper_exit_shape_2026-08-20.py")
_sse = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(_sse)
fetch_candles = _sse.fetch_candles
order_book_details = _sse.order_book_details

TP, SL = 0.15, 0.10          # the book's own bracket
BANDS = [("0-7d", 0, 7), ("8-21d", 8, 21), ("22-40d", 22, 40),
         ("41-60d", 41, 60), ("61-90d", 61, 90)]
MAX_COINS = 45
#: A book needs this many days of its own tape before it can contribute a
#: mature control band. Books younger than this are EXCLUDED from --control
#: rather than compared against a band they do not have.
CONTROL_MIN_AGE_D = 125


def _now():
    return int(datetime.datetime.now(datetime.timezone.utc).timestamp())


def cohort(min_age_d=8, limit=MAX_COINS):
    """Venue-priced books with usable tape, richest first.

    VENUE-PRICED, not `is_crypto`: (ty) established that the venue files
    crypto-native memecoin debuts under class 7, and that the axis this book
    cares about is "priced where the underlying trades". Externally-priced
    debuts (tokenised equity/pre-IPO) are a different cohort with a measured
    NEGATIVE short — they are excluded here, not silently pooled.
    """
    now, out = _now(), []
    for b in order_book_details():
        sym = b.get("symbol")
        try:
            born = int(b["created_at"]) // 1000
        except (KeyError, TypeError, ValueError):
            continue
        if not sym or not fleet_bus.venue_priced(sym):
            continue
        if (now - born) / 86400.0 < min_age_d:
            continue
        out.append((sym, int(b.get("market_id")), born,
                    float(b.get("daily_quote_token_volume") or 0) / 1e6))
    out.sort(key=lambda c: -c[3])
    return out[:limit]


def _bars(mid, start, end):
    try:
        return sorted(fetch_candles(mid, start, end, resolution="1h").items())
    except Exception:                                       # noqa: BLE001
        return []


def _agg(v):
    if len(v) < 2:
        return None
    m = st.mean(v)
    return m, st.stdev(v) / math.sqrt(len(v)), len(v)


def _line(label, pooled, by_coin):
    a, b = _agg(pooled), _agg(by_coin)
    if not a or not b:
        return f"{label:<11}   (insufficient sample)"
    return (f"{label:<11}{a[2]:>7}{a[0]:>10.3f}%{a[0]/a[1]:>8.2f}"
            f"   | by coin: n={b[2]:>3} {b[0]:>+7.3f}% t={b[0]/b[1]:>+6.2f}")


def gradient():
    """LONG, unconditional, by age band. The question: does a young book fade?"""
    cs = cohort()
    print(f"venue-priced books: {len(cs)}  "
          f"(vol24 ${cs[-1][3]:.3f}M .. ${cs[0][3]:.3f}M)\n")
    per = {}
    for sym, mid, born, _v in cs:
        bars = _bars(mid, born, min(_now(), born + 91 * 86400))
        if len(bars) < 48:
            continue
        close = {t: c[3] for t, c in bars}
        for name, lo, hi in BANDS:
            for hold in (6, 24):
                w = [t for t, _ in bars
                     if lo * 86400 <= (t - born) < (hi + 1) * 86400
                     and t + hold * 3600 in close and close[t]]
                if len(w) < 12:
                    continue
                r = [100.0 * (close[t + hold * 3600] / close[t] - 1.0) for t in w]
                per.setdefault((name, hold), []).append(r)
    for hold in (6, 24):
        print(f"--- LONG, {hold}h hold ---")
        print(f"{'age band':<11}{'n':>7}{'mean':>11}{'t':>8}")
        for name, _, _ in BANDS:
            rs = per.get((name, hold), [])
            print(_line(name, [x for c in rs for x in c],
                        [st.mean(c) for c in rs if len(c) > 1]))
        print()


def control():
    """Is the fade an AGE effect, or this venue's falling tape? Paired by coin."""
    cs = cohort(min_age_d=CONTROL_MIN_AGE_D)
    hold = 24
    rows = []
    for sym, mid, born, _v in cs:
        bars = _bars(mid, born, min(_now(), born + 121 * 86400))
        if len(bars) < 24 * 30:
            continue
        close = {t: c[3] for t, c in bars}

        def band(lo, hi):
            w = [t for t, _ in bars if lo * 86400 <= (t - born) < (hi + 1) * 86400
                 and t + hold * 3600 in close and close[t]]
            return [100.0 * (close[t + hold * 3600] / close[t] - 1.0) for t in w]
        y, mature, whole = band(0, 21), band(61, 120), band(0, 120)
        if len(y) < 50 or len(mature) < 50:
            continue
        rows.append((sym, st.mean(y), st.mean(whole), st.mean(mature)))
    if not rows:
        print("REFUSED: no coin has both a young and a mature band.")
        return
    print(f"coins with BOTH a young and a mature band: {len(rows)}  "
          f"(LONG, {hold}h)\n")
    for label, idx in (("A  young − own WHOLE TAPE ", 2),
                       ("B  young − own MATURE band", 3)):
        d = [r[1] - r[idx] for r in rows]
        m, se, n = _agg(d)
        print(f"{label}: {m:+.3f} pp/{hold}h   t={m/se:+.2f}   "
              f"coins below zero: {sum(1 for x in d if x < 0)}/{n}")
    print(f"\nraw coin-mean   young 0-21d {st.mean([r[1] for r in rows]):+.3f}%"
          f"   mature 61-120d {st.mean([r[3] for r in rows]):+.3f}%")


def _walk(bars, i, hold_h, short):
    """(pct, reason) — STOP checked before target inside each bar."""
    ent = bars[i][1][3]
    if not ent:
        return None
    tp_px = ent * (1 - TP) if short else ent * (1 + TP)
    sl_px = ent * (1 + SL) if short else ent * (1 - SL)
    for j in range(i + 1, min(i + 1 + hold_h, len(bars))):
        _t, c = bars[j]
        hi, lo = c[1], c[2]
        if (hi >= sl_px) if short else (lo <= sl_px):
            return -SL * 100, "sl"
        if (lo <= tp_px) if short else (hi >= tp_px):
            return TP * 100, "tp"
    j = min(i + hold_h, len(bars) - 1)
    px = bars[j][1][3]
    return ((ent - px) / ent if short else (px - ent) / ent) * 100, "max_hold"


def bracket(side="short", lo=0, hi=21, min_age_d=30):
    short = side == "short"
    cs = cohort(min_age_d=min_age_d)
    print(f"{side.upper()} through the book's real bracket "
          f"(tp+{TP:.0%}/sl-{SL:.0%}), ages {lo}-{hi}d, {len(cs)} coins\n")
    for hold_h in (6, 24, 72):
        pooled, by_coin, reasons = [], [], {}
        for sym, mid, born, _v in cs:
            bars = _bars(mid, born + lo * 86400,
                         min(_now(), born + (hi + 2) * 86400))
            if len(bars) < hold_h + 24:
                continue
            rs = []
            for i in range(0, len(bars) - hold_h, 6):
                r = _walk(bars, i, hold_h, short)
                if r:
                    rs.append(r[0])
                    reasons[r[1]] = reasons.get(r[1], 0) + 1
            if len(rs) >= 8:
                by_coin.append(st.mean(rs))
                pooled += rs
        if not pooled:
            continue
        tot = sum(reasons.values())
        print(_line(f"hold {hold_h}h", pooled, by_coin))
        print("             exits: " + "  ".join(
            f"{k}={v} ({100*v/tot:.1f}%)" for k, v in sorted(reasons.items())))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gradient", action="store_true")
    ap.add_argument("--control", action="store_true")
    ap.add_argument("--bracket", action="store_true")
    ap.add_argument("--mature-bracket", action="store_true",
                    help="the SAME bracket on the SAME coins when mature")
    ap.add_argument("--all", action="store_true")
    a = ap.parse_args()
    if not any((a.gradient, a.control, a.bracket, a.mature_bracket, a.all)):
        ap.print_help()
        return 0
    if a.all or a.gradient:
        print("=" * 74, "\n1 · AGE GRADIENT\n", "=" * 74, sep=""); gradient()
    if a.all or a.control:
        print("=" * 74, "\n2 · IS IT AGE, OR THE FALLING TAPE?\n", "=" * 74, sep=""); control()
    if a.all or a.bracket:
        print("=" * 74, "\n3 · THE SHORT, THROUGH THE REAL BRACKET\n", "=" * 74, sep="")
        bracket()
    if a.all or a.mature_bracket:
        print("=" * 74, "\n4 · MATURE CONTROL — same bracket, same coins, 61-120d\n",
              "=" * 74, sep="")
        bracket(lo=61, hi=120, min_age_d=CONTROL_MIN_AGE_D)
    return 0


if __name__ == "__main__":
    sys.exit(main())
