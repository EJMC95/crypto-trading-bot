#!/usr/bin/env python3
"""[(xz)] THREE CONSTANTS IN THREE FILES DECIDE ONE BOOK'S BEHAVIOUR, AND
NOTHING READ THEM TOGETHER.

**Eamon, 3-Sep: *"Check on all 'relationships' in the fleet, we could be onto
something."*** He was right, and this is the general form of what we found.

A book's gross multiple `g` is a Railway env on its service. Its stop `s` is a
registry entry in `lighter_family_bot` or a module constant. Its daily-loss
fraction `f` is a third constant in whichever host runs it. Each is defensible
alone. Their RATIO decides whether the book's own strategy or the daily rail
gets to end its trades — and no guard read the three together.

    R1  the halt must not pre-empt the stops :  f / g  >=  s   i.e.  f >= g*s
    R2  an all-slots stop stays inside the
        go-live gate's drawdown bar          :  g * s  <   D   (D = 0.15)

    => the derived ceiling on leverage       :  g  <  D / s

MEASURED THE DAY THIS SHIPPED, and it had already been paid for three times:
  * `(hl)` 🌊 Tide Rider — *"at >=10 the -10% daily-loss halt becomes reachable
    before the -35% stop"*. Patched by capping that ONE book's `max_open`.
  * 👩 mum — 3.75x/4%/0.10 gave 0.71 stop-widths; she halted on a 4.0% basket
    move at 9 of 12 slots and lost a whole trading day to it.
  * 🙏 avo — 5.3x/10%/0.10 gave **0.19** stop-widths. Measured on her ledger:
    **14 of 22 live closes (64%) were `daily_loss` flattens.** Her strategy
    exited 8. She was not a book with a risk rail; she was a book being
    liquidated by one, two-thirds of the time.

AND `(sr)` HAD ALREADY DERIVED THE CEILING. `GROSS_X_MAX = 0.15/|stoploss|` is
exactly `D/s`, and mum's 3.75x was precisely that number. It was later made an
operator env — correctly, because risk appetite belongs to the person whose
money it is — and NOTHING replaced it as a REPORT. This is that report.

REPORTS, NEVER CLAMPS. The gross is the operator's ((sr)); this computes the
arithmetic and publishes it. A book outside the band is a decision, not a bug.

A RATCHET, NOT A BAR. Both live books deliberately sit outside R2 today
(g*s = 0.20 against D = 0.15) on Eamon's explicit call. A guard that reddens
the build on a pre-existing, DECIDED state gets exempted within a day and then
guards nothing ((mz)'s lesson, cited by I23) — so declared states are recorded
with a reason and only an UNDECLARED violation fails.

THE RELATIONSHIP IS DORMANT AT 1x, WHICH IS WHY IT KEEPS BEING MISSED. A book
at gross 1.0 caps its own day at `s` regardless of `f`; the trap opens the
moment leverage arrives, and leverage arrives on a service env far from either
constant. That is the whole mechanism, and it is why this is checked per book
rather than trusted to whoever sets the env.
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

#: The go-live gate's max-drawdown bar. IMPORTED from the gate, never retyped —
#: a second copy of a rule is a second rule ((hj)). Falls back only if the
#: grader cannot be imported at all, and says so in the output.
def gate_bar():
    try:
        sys.path.insert(0, HERE)
        import golive_readiness as gr
        for name in ("GOLIVE_MAX_DD", "MAX_DD", "MAXDD_BAR"):
            v = getattr(gr, name, None)
            if isinstance(v, (int, float)) and 0 < float(v) < 1:
                return float(v), name
    except Exception:  # noqa: BLE001
        pass
    return 0.15, "fallback-literal"


#: Books whose position OUTSIDE the band is a recorded decision, not a defect.
#: Every entry needs a reason and the value it was decided at — this is not a
#: place to park a book someone has not thought about.
DECLARED = {
    "freqtrade-mum": (
        "R2: g*s = 0.20 vs D = 0.15. Eamon, 3-Sep, explicitly, after being "
        "shown that an all-slots stop breaches the gate bar: he chose 5x gross "
        "with the daily fraction raised to 0.20 so the STOPS bind first (R1 "
        "holds at exactly 1.00 stop-widths). The cost — she can fail the "
        "drawdown bar in one session — was stated and accepted."),
    "freqtrade-avo-maria": (
        "R2: g*s = 0.20 vs D = 0.15. Eamon, 3-Sep, same call and same trade "
        "as mum's, chosen from a scored option set. Her stop "
        "is -10%, so matching one stop-width at her old 5.3x would have needed "
        "a 53% daily cap; the fix had to come out of gross (5.3 -> 2.0) "
        "instead. R1 now holds at exactly 1.00."),
}


def band(g, s, f, D):
    """Score one book. Returns None when the relationship does not bind."""
    try:
        g = float(g); s = abs(float(s)); D = float(D)
        f = None if f is None else float(f)
    except (TypeError, ValueError):
        return None
    if not (g > 0 and s > 0 and D > 0):
        return None
    gs = g * s
    out = {"g": g, "s": s, "f": f, "gs": gs, "ceiling": D / s,
           "r2": gs < D, "r1": None, "stop_widths": None}
    if f is not None and f > 0:
        out["stop_widths"] = (f / g) / s
        out["r1"] = out["stop_widths"] >= 1.0 - 1e-9
    return out


def rows_from_source():
    """(book, g, s, f, note) for every book whose constants this repo owns.

    Read from the OWNERS — `lighter_family_bot.STRATEGIES` for the family's
    stops and `RETIRED_BOOKS` for who is still living — never retyped here.
    `g` is the CODE DEFAULT: the live value is a service env this repo cannot
    see, which is exactly why `--pnl-json` exists.
    """
    os.environ.setdefault("FAMILY_LIVE_BOOK", "freqtrade-avo-maria")
    out = []
    try:
        import lighter_family_bot as fam
    except Exception as e:  # noqa: BLE001
        return out, f"family registry unreadable ({e!r})"
    retired = set(getattr(fam, "RETIRED_BOOKS", {}) or {})
    f_family = float(getattr(fam, "DAILY_LOSS_LIMIT", 0.10) or 0.10)
    for s in getattr(fam, "STRATEGIES", []):
        bot = getattr(s, "bot", None)
        if not bot or bot in retired or bot == "t":
            continue
        out.append((bot, 1.0, getattr(s, "stoploss", None), f_family,
                    "family shadow host, code default gross 1.0"))
    return out, None


def rows_from_feed(path_or_url):
    """(book, g, s, f, note) from the LIVE payload — the only place the real
    gross is visible. Fail-CLOSED: an unreadable feed returns an error, never
    a vacuous clean sheet."""
    try:
        if str(path_or_url).startswith("http"):
            import urllib.request
            raw = urllib.request.urlopen(path_or_url, timeout=60).read()
        else:
            with open(path_or_url) as fh:
                raw = fh.read()
        d = json.loads(raw)
    except Exception as e:  # noqa: BLE001
        return None, f"feed unreadable ({e!r})"
    rows = d if isinstance(d, list) else (d.get("bots") or d.get("rows") or [])
    if isinstance(rows, dict):
        rows = list(rows.values())
    out = []
    for r in rows:
        if not isinstance(r, dict):
            continue
        e = r.get("extra") or {}
        g = e.get("gross_x")
        pol = e.get("policy") if isinstance(e.get("policy"), dict) else {}
        s = pol.get("stoploss")
        h = ((e.get("leverage") or {}).get("halt") or {})
        f = h.get("daily_loss_frac")
        if g is None or s is None:
            continue
        out.append((str(r.get("bot")), g, s, f, "LIVE payload"))
    return out, None


def report(rows, D, bar_src, strict=True):
    print(f"gate drawdown bar D = {D} (from {bar_src})\n")
    hdr = (f"{'book':32} {'g':>5} {'s':>6} {'f':>5} {'g*s':>6} "
           f"{'widths':>7} {'R1':>5} {'R2':>5} {'g<D/s':>7}")
    print(hdr); print("-" * len(hdr))
    undeclared = []
    for bot, g, s, f, note in rows:
        b = band(g, s, f, D)
        if b is None:
            print(f"{bot:32} {'— relationship does not bind':>48}")
            continue
        base = bot.rsplit("-lighter", 1)[0].rsplit("-lshadow", 1)[0]
        r1 = "n/a" if b["r1"] is None else ("OK" if b["r1"] else "FAIL")
        r2 = "OK" if b["r2"] else "FAIL"
        w = "  n/a" if b["stop_widths"] is None else f"{b['stop_widths']:7.2f}"
        print(f"{bot:32} {b['g']:5.2f} {b['s']:6.3f} "
              f"{(b['f'] if b['f'] is not None else float('nan')):5.2f} "
              f"{b['gs']:6.3f} {w} {r1:>5} {r2:>5} {b['ceiling']:7.2f}x")
        bad = (b["r1"] is False) or (b["r2"] is False)
        if bad and base not in DECLARED:
            undeclared.append((bot, b))
    print()
    for bot, b in undeclared:
        why = []
        if b["r1"] is False:
            why.append(f"the daily halt fires at {b['stop_widths']:.2f} "
                       f"stop-widths — before this book's own stops")
        if b["r2"] is False:
            why.append(f"an all-slots stop costs {b['gs']*100:.1f}% of equity "
                       f"against a {D*100:.0f}% gate bar (ceiling {b['ceiling']:.2f}x)")
        print(f"UNDECLARED: {bot} — " + "; ".join(why))
    if undeclared:
        print("\nFIX: change the gross, the fraction or the stop so the band "
              "holds — or add the book to DECLARED with the reason and the "
              "value it was decided at. Reporting only; nothing is clamped.")
        return 1 if strict else 0
    print(f"audit_leverage_band: OK — {len(rows)} book(s) scored, "
          f"{len(DECLARED)} declared outside the band with reasons.")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--pnl-json", help="live feed (url or path); the only "
                                       "place the real gross is visible")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    D, src = gate_bar()
    if a.pnl_json:
        rows, err = rows_from_feed(a.pnl_json)
        if err:
            print(f"audit_leverage_band: REFUSED — {err}")
            return 2                      # fail-closed, never a vacuous green
        print("=== LIVE payload (real gross) ===")
        return report(rows, D, src)
    rows, err = rows_from_source()
    if err:
        print(f"audit_leverage_band: REFUSED — {err}")
        return 2
    print("=== source defaults (gross 1.0; live gross needs --pnl-json) ===")
    return report(rows, D, src)


def selftest():
    D = 0.15
    b = band(5.0, -0.04, 0.20, D)
    assert abs(b["gs"] - 0.20) < 1e-9 and b["r1"] and not b["r2"], b
    assert abs(b["ceiling"] - 3.75) < 1e-9, b          # (sr)'s own derivation
    b = band(5.3, -0.10, 0.10, D)                      # avo before tonight
    assert abs(b["stop_widths"] - 0.1886792) < 1e-6, b
    assert not b["r1"] and not b["r2"], b
    b = band(1.0, -0.04, 0.10, D)                      # dormant at 1x
    assert b["r1"] and b["r2"], b
    assert band(0, -0.04, 0.1, D) is None
    assert band(1.0, 0, 0.1, D) is None
    assert band("x", -0.04, 0.1, D) is None
    b = band(1.0, -0.05, None, D)                      # no daily halt at all
    assert b["r1"] is None and b["stop_widths"] is None and b["r2"], b
    print("audit_leverage_band selftest OK "
          "(band arithmetic, (sr)'s 3.75x ceiling reproduced, avo's 0.19 "
          "reproduced, dormant at 1x, junk -> None, no-halt -> R1 n/a)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
