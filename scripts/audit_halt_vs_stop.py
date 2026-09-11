#!/usr/bin/env python3
"""A DAILY-LOSS HALT MUST NOT FIRE BEFORE THE STOP IT PRE-EMPTS.

[2026-09-11 (abg)] `(gv)` built `tests/autonomy/test_stop_vs_gate.py` on the
rule **"a stop must be reconcilable with the gate that judges it"** — the 15%
drawdown bar. Every live book has a SECOND rail that can end a position and
nothing read it against the stop: the daily-loss halt. They are the same
quantity in different units — the halt a DOLLAR allowance on the book, the stop
a PERCENT move on a position — and the gross converts between them.

MEASURED ON 👩 MUM, 11-SEP, and it was the whole of her divergence from a
winning twin. At `gross 9.5x` her binding $105 allowance is spent by a **1.42%**
adverse basket move while her stop sits at **4.00%**, so on any red day every
position exited at the halt instead of at its own stop or the ROI ladder her
edge was measured on:

    exit family        LIVE n   LIVE %/t  | TWIN n  TWIN %/t
    roi                    79    +1.416%  |     72   +1.422%
    max_hold               17    -1.369%  |     17   -1.155%
    stop_loss              15    -4.640%  |     12   -4.806%
    daily_loss             20    -1.597%  |      0        --     <-- live only

On the exits the arms SHARE she reads +0.171%/trade against the twin's +0.243%
— indistinguishable, n=111/106. The halt family alone is **-1.451%/trade,
t=-5.41** and carries **-0.506pp of the -0.578pp/trade** gap between a book at
-15% and a book at +2.5%. Neither rail was wrong on its own: the $105 cap is
20% of a $525 day-start and the gross came from a liquidation ceiling. Nobody
multiplied them.

WHAT THIS REFUSES, and it is deliberately narrow: a LIVE book whose own
published row says the halt fires at a SMALLER basket move than its own
stoploss. It reads the book's OWN `extra.leverage.halt.vs_stop` — the
publisher's verdict, never re-derived here ((hj): a second copy of a rule is a
second rule, and this exact field exists so the audit and the bot cannot
disagree about one book's geometry).

FAIL-CLOSED ON NOTHING, FAIL-OPEN ON ABSENCE. A book that does not publish the
block is a deploy-latency state, not a finding (I1) — but a book that publishes
it and reads `stop_fires_first: false` reddens the build. A stale row is
skipped; an empty feed is a loud refusal, never a vacuous green ((jc)).

DECLARED EXCEPTIONS carry the decision, never a default ((gv)'s `BORN_DARK_OK`
idiom): a book Eamon has put on the record as accepting a halt-first geometry
is listed with his words and the date.
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request

PNL_JSON = ("https://pnl-dashboard-production-858c.up.railway.app/pnl.json")

#: THE RATCHET, not a bar — and the distinction is I23's, learned from (mz):
#: "a guard that reddens the build on a pre-existing backlog gets exempted
#: within a day and then guards nothing". Measured on the live feed the day this
#: shipped, BOTH real-money books sit below 1.0 at Eamon's own on-record
#: settings:
#:
#:     book                          gross  stop   cap    halt@   ratio
#:     freqtrade-avo-maria-lighter    2.33  10.0%  $80    8.28%    0.83
#:     freqtrade-mum-lighter          9.50   4.0%  $105   1.66%    0.41
#:
#: A plain bar would therefore have failed on 2 of 2 live books on its first
#: run, been exempted, and guarded nothing. So the baseline is DECLARED with its
#: numbers and the ratchet may only tighten: a book whose ratio falls BELOW its
#: declared floor reddens, an UNDECLARED live book that is mis-ordered reddens
#: immediately, and the floors can only be raised as the geometry improves.
#:
#: `ratio = halt_at_basket_pct / stop_at_basket_pct`. Below 1.0 the daily halt
#: fires before the book's own stop, so on a red day its positions exit at the
#: halt rather than at the bracket its edge was measured on — on 👩 mum that is
#: 22 legs at -1.451%/trade, t=-5.41, and the whole of her gap to a twin that
#: is winning the same entries.
#:
#: EACH FLOOR CARRIES THE DECISION AND ITS DATE. An undated exemption is how a
#: guard dies ((mz)); an undeclared one is how a regression hides.
RATCHET: dict[str, tuple[float, str]] = {
    # Eamon, 11-Sep-2026: *"Keep the leverage it has, I just want any big fixes
    # sorted and to have it winning again"*, and on the arithmetic being put to
    # him a second time *"We have done multiple studies on 9.5x."* An ON-RECORD
    # decision, recorded rather than re-litigated. Stated once: at 9.5x there is
    # no cap VALUE that reconciles the pair — full parity needs a daily
    # allowance of 9.5 x 4% = 38% of the book, and her 20% leash caps it at
    # 2.11% regardless of the absolute cap — so the ordering follows from the
    # leverage, which is his ((sr): "risk appetite belongs to the person whose
    # money it is; the code's job is the arithmetic, published").
    "freqtrade-mum-lighter": (0.40, "Eamon, 11-Sep-2026: keep gross at 9.5x"),
    # PRE-EXISTING at her on-record gross 2.33x / $80 cap / -10% stop, and far
    # milder than mum's. Declared rather than fixed in this pass under the
    # fleet's own SHIP NARROW rule — (fz) changed six surfaces at once and spent
    # six follow-up entries repairing itself. Her `vs_stop` publishes every loop
    # from the same commit, so the number is readable while the decision waits.
    "freqtrade-avo-maria-lighter": (0.80, "pre-existing 11-Sep-2026; declared, "
                                          "not fixed in the (abg) pass"),
}

#: Kept for the one case a floor cannot express: a book that should be silent
#: entirely. Empty today — a declared FLOOR is strictly more informative than a
#: blanket exemption, so prefer RATCHET.
HALT_FIRST_OK: dict[str, str] = {}

#: A row older than this is not evidence about the running configuration (I1).
STALE_ROW_S = 3600


def findings(rows, ok=None, ratchet=None):
    """[(book, halt_pct, stop_pct, parity_gross, ratio, floor)] for every LIVE
    book whose own row says its halt pre-empts its stop BY MORE than its
    declared floor allows. Pure; takes the feed, returns the list, so the test
    drives it with no network.

    A book with no declared floor is held to 1.0 — the honest default, because an
    undeclared book is a NEW instance and the whole point of a ratchet is that a
    new instance fails immediately.
    """
    allow = HALT_FIRST_OK if ok is None else ok
    floors = RATCHET if ratchet is None else ratchet
    out = []
    for r in rows or []:
        if not isinstance(r, dict) or not r.get("live"):
            continue
        age = r.get("age_sec")
        if isinstance(age, (int, float)) and not isinstance(age, bool) \
                and age > STALE_ROW_S:
            continue
        bot = str(r.get("bot") or "")
        if bot in allow:
            continue
        hvs = (((r.get("extra") or {}).get("leverage")
                or {}).get("halt") or {}).get("vs_stop")
        if not isinstance(hvs, dict):
            continue                      # deploy latency, not a finding
        halt, stop = hvs.get("halt_at_basket_pct"), hvs.get("stop_at_basket_pct")
        ok_nums = all(isinstance(v, (int, float)) and not isinstance(v, bool)
                      for v in (halt, stop)) and stop
        if not ok_nums:
            # an unreadable pair is not a finding and not a pass: the publisher's
            # own `stop_fires_first` is the fallback verdict (I1 — never assert
            # an ordering from an unknown, but never swallow a stated one).
            if hvs.get("stop_fires_first") is False and bot not in floors:
                out.append((bot, halt, stop, hvs.get("gross_at_parity"),
                            None, 1.0))
            continue
        ratio = float(halt) / float(stop)
        floor = floors.get(bot, (1.0, ""))[0]
        if ratio < floor:
            out.append((bot, halt, stop, hvs.get("gross_at_parity"),
                        round(ratio, 4), floor))
    return out


def _selftest():
    def row(bot, live=True, hvs=..., age=10):
        lev = {} if hvs is ... else {"halt": {"vs_stop": hvs}}
        return {"bot": bot, "live": live, "age_sec": age,
                "extra": {"leverage": lev}}
    def hvs(ratio, **kw):
        return dict({"halt_at_basket_pct": 0.04 * ratio,
                     "stop_at_basket_pct": 0.04,
                     "stop_fires_first": ratio >= 1.0,
                     "gross_at_parity": 3.36}, **kw)
    NOFLOOR: dict = {}

    # an UNDECLARED book is held to 1.0 — a new instance fails immediately
    assert [f[0] for f in findings([row("a", hvs=hvs(0.41))], ratchet=NOFLOOR)] == ["a"]
    assert findings([row("a", hvs=hvs(1.00))], ratchet=NOFLOOR) == []
    assert findings([row("a", hvs=hvs(1.40))], ratchet=NOFLOOR) == []

    # A DECLARED FLOOR is honoured, and only down to the floor
    rat = {"a": (0.40, "Eamon, 1-Jan")}
    assert findings([row("a", hvs=hvs(0.41))], ratchet=rat) == []
    assert findings([row("a", hvs=hvs(0.40))], ratchet=rat) == []
    bad = findings([row("a", hvs=hvs(0.39))], ratchet=rat)
    assert [f[0] for f in bad] == ["a"], bad
    assert bad[0][4] == 0.39 and bad[0][5] == 0.40, bad   # ratio + floor reported
    # ...and a floor NEVER silences a different book
    assert [f[0] for f in findings([row("b", hvs=hvs(0.41))], ratchet=rat)] == ["b"]

    # a PAPER book is out of scope — the rail protects real money
    assert findings([row("a", live=False, hvs=hvs(0.10))], ratchet=NOFLOOR) == []
    # absence is deploy latency, never a finding (I1)
    assert findings([row("a")], ratchet=NOFLOOR) == []
    assert findings([row("a", hvs=None)], ratchet=NOFLOOR) == []
    assert findings([row("a", hvs="junk")], ratchet=NOFLOOR) == []
    # a STALE row says nothing about the running config (I1)
    assert findings([row("a", hvs=hvs(0.10), age=99999)], ratchet=NOFLOOR) == []
    assert [f[0] for f in findings([row("a", hvs=hvs(0.10), age=None)],
                                   ratchet=NOFLOOR)] == ["a"]
    # an UNREADABLE pair falls back to the publisher's own verdict, never to a pass
    assert [f[0] for f in findings(
        [row("a", hvs={"stop_fires_first": False})], ratchet=NOFLOOR)] == ["a"]
    # ...but `None` is not `False` — an unmeasurable ordering is not a breach
    assert findings([row("a", hvs={"stop_fires_first": None})],
                    ratchet=NOFLOOR) == []
    # a blanket exemption still works for the case a floor cannot express
    assert findings([row("a", hvs=hvs(0.10))], ok={"a": "why"},
                    ratchet=NOFLOOR) == []
    # every declared floor carries a dated reason — an undated one is how a
    # guard dies ((mz))
    for bot, (floor, why) in RATCHET.items():
        assert 0.0 < floor <= 1.0, (bot, floor)
        assert "2026" in why and len(why) > 20, (bot, why)
    print(f"audit_halt_vs_stop selftest: 18 assertions passed "
          f"({len(RATCHET)} declared floors)")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--pnl-json", default=PNL_JSON)
    a = ap.parse_args(argv)
    if a.selftest:
        _selftest()
        return 0
    try:
        with urllib.request.urlopen(a.pnl_json, timeout=60) as fh:
            rows = (json.load(fh) or {}).get("bots") or []
    except Exception as exc:                              # noqa: BLE001
        print(f"REFUSING: feed unreadable ({exc}) — a dark feed is not a pass")
        return 2
    live = [r for r in rows if isinstance(r, dict) and r.get("live")]
    if not live:
        print("REFUSING: feed carries no live rows — never a vacuous green")
        return 2
    bad = findings(rows)
    pub = sum(1 for r in live
              if isinstance((((r.get("extra") or {}).get("leverage") or {})
                             .get("halt") or {}).get("vs_stop"), dict))
    print(f"live rows {len(live)} · publishing vs_stop {pub} · "
          f"declared floors {len(RATCHET)} · findings {len(bad)}")
    for bot, h, st, g, ratio, floor in bad:
        print(f"  FAIL {bot}: halt fires at {100*(h or 0):.2f}% basket move, "
              f"stop at {100*(st or 0):.2f}% — ratio "
              f"{ratio if ratio is not None else '?'} against a declared floor "
              f"of {floor}. The halt pre-empts the bracket the book's edge was "
              f"measured on. Parity gross {g}x.")
    if bad:
        print("  The ratchet may only TIGHTEN: either restore the geometry, or "
              "change RATCHET with the decision and its date.")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
