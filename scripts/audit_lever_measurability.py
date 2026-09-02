#!/usr/bin/env python3
"""EVERY LEVER MUST BE MEASURABLE, AND NO LEVER MAY STEER A BOOK THAT IS GONE.

**Operator, 2026-08-20: "Fix this never recorded issue across the fleet, I am
so tired of going over the same trivial problem."** They are right, and it is
the same problem every time. Four instances landed in ONE session:

  * `taker.brk_trail` / `taker.brk_sl` — the give-back and the adverse
    excursion each lever cuts were tracked in memory and thrown away at close,
    so two widenings had to be WITHHELD while a harness reconstructed from
    hourly candles what the bot already knew to the loop;
  * `carry.payback_max_h` — same shape, fixed at birth only because the same
    session happened to be looking;
  * 🌾 carry's turnover floor — the cost it stood in for was declared
    "unmeasured" and left unmeasured for weeks, gating the fleet's best book
    to `eligible: 0`;
  * 🎫 the taker's `brk_range` / `max_hold_h` — steered by an actuator whose
    replay cannot fill the lens, so restrict enacted free and expand was
    arithmetically impossible.

Every one is the same defect wearing different clothes: **the thing that
decides is not measuring the thing it decides about.** Fixing them one at a
time is the circle. This guard closes the class.

WHAT IT ENFORCES, and both halves are ratchets rather than walls — the backlog
is real and a wall would just get switched off:

  1. **MEASURABLE.** A registered lever needs a `QUANTITIES` spec in
     `audit_lever_authority` — a named source and field that records the
     quantity the lever cuts — or an entry in `UNMEASURABLE_OK` with a reason
     and an owner. Measured the day this shipped: **45 of 64 levers had
     neither.** The count may only ever GO DOWN. A NEW lever that ships
     without a measurement path fails the build, which is what stops the pile
     growing while it drains.

  2. **ALIVE.** A lever whose book is in `pnl_dashboard.RETIRED_ROWS` steers
     nothing. Measured: **15 of the 21 `lighter-books` levers** point at books
     that no longer trade (`barnes.*`, `disloc.*`, `index.*`, `trend.*`).
     That is worse than unmeasurable — it is noise in every organ that
     reasons about headroom, and it inflates every "the rail can reach this"
     claim. Same ratchet: declared in `DEAD_LEVER_OK` or removed, and the
     count may only shrink.

WHY A RATCHET AND NOT A BAR. `audit_venue_purity`'s backtest arm took the same
shape at `(mz)` for the same reason: a guard that reddens the build on a
pre-existing backlog gets a blanket exemption within a day, and then it guards
nothing. A ratchet is the version that survives contact with the backlog.

WHAT IT CANNOT SEE, stated so nobody reads a green run as more than it is: it
checks that a measurement PATH EXISTS, not that anyone has walked it — a
`QUANTITIES` spec pointing at a field nothing ever writes still reads as
measurable here, and `audit_lever_authority --measure` is what grades that.
Same caveat as the doctrine guard's own: existence, not correctness.

    python3 scripts/audit_lever_measurability.py
    python3 scripts/audit_lever_measurability.py --selftest
"""
import argparse
import importlib.util
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import fleet_tuning                                             # noqa: E402

#: Lever prefix -> the dashboard ROW(s) it steers. Hand-written because no
#: mechanical mapping exists (a lever names a book by convention, and one
#: module serves several rows) — but NOT a place drift can hide: `check`
#: fails on any registered prefix missing from this map, so a new book's
#: levers cannot arrive unclassified.
LEVER_BOOK = {
    "carry": ("perps-funding-carry-lshadow",),
    "fundspread": ("perps-funding-spread-lshadow",),
    "sniper": ("lighter-perp-sniper-lshadow",),
    "taker": ("lighter-ticket-taker-lshadow",),
    "barnes": ("band-barnes-lshadow",),
    "disloc": ("lighter-dislocation-lshadow",),
    "index": ("equities-regime-lshadow",),
    "trend": ("crypto-trend-daily-lshadow",),
    # Organ lanes, not books. They steer a PUBLISHER or the fleet, so the
    # retired-row question does not apply to them; the measurability one does.
    "scout": (), "evsent": (), "gapscout": (), "risk": (),
    "live": (), "xp": (),
}

#: Levers with no path to measurement, DECLARED. An entry is a decision with a
#: reason — never a snooze — and the list may only shrink (see RATCHET below).
UNMEASURABLE_OK = {
    # [2026-09-02 (xl)] 👩 mum's DIP-VELOCITY band, all four twins. DECLARED
    # rather than backlogged, per I23's own rule that a NEW lever is measurable
    # or declared THE SAME DAY — and the declaration is narrow, because the
    # quantity is NOT unrecorded. It is published on her row every loop
    # (`scan.vel_med` / `vel_p90` / `vel_read` / `vel_band` / `vel_in_band`,
    # armed or not) and stamped on every close through `mum_bars`. What it
    # lacks is a source THIS PROFILER can read: every `QUANTITIES` spec pulls
    # from a scout-tape state key (`state:lighter-market`), and her RSI
    # velocity is a 1h per-carrier statistic that never enters the scout tape.
    # Closing it properly means teaching the profiler a per-book census
    # source, which is a change to the guard, not to the book.
    # OWNER: this repo. Revisit when a second carrier-statistic lever lands —
    # one is a declaration, two is a missing source type.
    "xp.mum.vel_lo": "recorded on the row (scan.vel_*) + mum_bars; no scout-tape source",
    "xp.mum.vel_hi": "recorded on the row (scan.vel_*) + mum_bars; no scout-tape source",
    "live.mum.vel_lo": "as xp.mum.vel_lo — judge-promoted twin",
    "live.mum.vel_hi": "as xp.mum.vel_hi — judge-promoted twin",
    # [2026-08-22 (sx)] 🔮 georgia's live clip arm, registered ahead of her
    # funding. Declared rather than counted against the ratchet, because a
    # NEW lever must be measurable or declared THE SAME DAY (I23) — and the
    # honest answer here is that a SIZE MULTIPLIER has no gated quantity.
    #
    # Every MEASURABLE spec in `QUANTITIES` profiles a lever against the
    # distribution of a TAPE variable it thresholds (funding apr, range_pos,
    # chg_pct). A clip scale thresholds nothing: it multiplies notional. The
    # quantity it cuts — the clip actually used — IS recorded, on every close
    # row (`extra.clip`, stamped from the position's entry meta), so this is
    # not the never-recorded class I23 exists to close. What is missing is a
    # tape-side distribution to profile it against, and inventing one would be
    # a spec pointing at a field nothing writes, which this guard's own header
    # names as the failure that "still reads as measurable".
    #
    # [2026-08-25] THE SIBLINGS ARE FOLDED IN — the standing owner note above
    # this entry said "fold the two siblings in here (backlog 30 -> 28) on the
    # next pass that touches this guard", and the pass that registered 👩 mum's
    # arm (`live.mum.clip_scale`, the fourth of this shape) is that pass. All
    # four share one consumer (`lighter_avo_live_bot._clip_scale_now` for the
    # variants; the Farmer's shared dial for `live.clip_scale`) and all four
    # record the quantity they cut on every close (`extra.clip`). The ratchet
    # dropped 30 -> 28 with the fold, so this declaration BOUGHT backlog
    # rather than spending it.
    "live.georgia.clip_scale":
        "size multiplier, gates no tape quantity; the clip it cuts IS recorded "
        "on every close (extra.clip). Owner: session.",
    "live.avo.clip_scale":
        "size multiplier, same shape as live.georgia.clip_scale; extra.clip "
        "records the cut on every close. Owner: session.",
    "live.clip_scale":
        "the Farmer's shared dial, same shape; extra.clip records the cut. "
        "Owner: session.",
    "live.mum.clip_scale":
        "👩 mum's arm ([2026-08-25], registered ahead of her live row); same "
        "shape, same shared consumer, extra.clip records the cut. "
        "Owner: session.",
}

#: Levers steering a RETIRED book, DECLARED. KEPT rather than deleted because
#: every one of these retirements is reversible by a single env var — flipping
#: the override brings the book back the same day, and a book that returns
#: without its levers is the registered-but-inert failure arriving by the back
#: door. Declaring costs the same fifteen lines as deleting and keeps the
#: reversal whole; what it BUYS is that the count drops to zero, so the ratchet
#: now fails on the NEXT dead lever instead of hiding it in a pile of fifteen.
#:
#: Read this list as the answer to "can the growth rail reach book X?" — for
#: these books the answer is "only if you first un-retire it", and every organ
#: that reasons about headroom should skip them.
DEAD_LEVER_OK = {
    # 🎸 band-barnes — I17 call 17-Aug (pm): ZERO independent evidence, 0 of 9
    # episodes on a coin 🌾 carry was not already holding. Two of its three
    # sleeves were already retired ((ly) extreme, (nf) xsect), so the two
    # sleeve-scoped levers below are dead twice over.
    "barnes.enter_apr": "BARNES_RETIRED_OVERRIDE=run",
    "barnes.max_positions": "BARNES_RETIRED_OVERRIDE=run",
    "barnes.persist_h": "BARNES_RETIRED_OVERRIDE=run",
    "barnes.k": "BARNES_RETIRED_OVERRIDE=run (xsect sleeve, also (nf))",
    "barnes.carry_min_vol": "BARNES_RETIRED_OVERRIDE=run",
    "barnes.extreme_min_vol": "BARNES_EXTREME_RETIRED_OVERRIDE=run ((ly))",
    "barnes.xsect_universe_n": "BARNES_XSECT_RETIRED_OVERRIDE=run ((nf))",
    # 🧲 lighter-dislocation — I17 call 4-Aug (jh) on the fleet's only
    # statistically significant LOSER (t=-2.97, n=175, both halves negative).
    # `disloc.exit_bps` was the fleet's FIRST exit lever; it outlived its book.
    "disloc.enter_pct": "SNAPBACK_RETIRED_OVERRIDE=run",
    "disloc.exit_bps": "SNAPBACK_RETIRED_OVERRIDE=run",
    "disloc.universe_n": "SNAPBACK_RETIRED_OVERRIDE=run",
    # 📊 equities-regime — I17 structural-undecidability call 13-Aug (lo):
    # ~17.2 closes/yr measured against a 30-close bar.
    "index.max_open": "INDEX_RIDER_RETIRED_OVERRIDE=run",
    # 🌊 crypto-trend-daily — I17 call 1-Aug (if): 9 buys / ZERO sells in 22
    # days while holding a third of the fleet's long budget.
    "trend.max_open": "TIDE_RIDER_RETIRED_OVERRIDE=run",
    "trend.min_vol_m": "TIDE_RIDER_RETIRED_OVERRIDE=run",
    "trend.rank_by_funding": "TIDE_RIDER_RETIRED_OVERRIDE=run",
    "trend.universe_n": "TIDE_RIDER_RETIRED_OVERRIDE=run",
}

#: THE RATCHET. Recorded on the day the guard shipped, from its own run. These
#: may be LOWERED freely and may never be raised: raising one is how a class
#: that is supposed to be draining quietly grows instead.
# [2026-08-25] 30 -> 28: live.avo.clip_scale + live.clip_scale folded into
# UNMEASURABLE_OK per that entry's own standing owner note, on the pass that
# added live.mum.clip_scale (declared, not backlogged).
RATCHET = {"unmeasurable": 28, "dead": 0}


def _quantities():
    """`audit_lever_authority.QUANTITIES`, imported by path.

    Imported rather than re-listed: a second copy of the spec table would let
    this guard and the profiler disagree about which levers are measurable,
    which is the second-copy-of-a-rule trap on a guard about measurement.
    """
    spec = importlib.util.spec_from_file_location(
        "_ala", os.path.join(HERE, "audit_lever_authority.py"))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["_ala"] = mod
    spec.loader.exec_module(mod)
    return dict(mod.QUANTITIES)


def retired_rows(src=None):
    """The dashboard's own `RETIRED_ROWS`, parsed from source.

    Parsed rather than imported because importing `pnl_dashboard` pulls a
    server; the set is a flat literal of string constants, so a regex over the
    braces is sound — and `check` fails if it comes back empty, so a parse
    that silently stops matching cannot read as "nothing is retired".
    """
    if src is None:
        with open(os.path.join(ROOT, "pnl_dashboard.py")) as fh:
            src = fh.read()
    m = re.search(r"RETIRED_ROWS\s*=\s*\{(.*?)\n\}", src, re.S)
    if not m:
        m = re.search(r"RETIRED_ROWS\s*=\s*\{(.*?)\}", src, re.S)
    if not m:
        return set()
    body = re.sub(r"#[^\n]*", "", m.group(1))          # strip comments first
    return set(re.findall(r'"([A-Za-z0-9_\-]+)"', body))


def classify(levers, quantities, retired):
    """-> {lever: verdict} over MEASURABLE / UNMEASURABLE / DEAD / declared."""
    out = {}
    for name, spec in sorted(levers.items()):
        prefix = name.split(".", 1)[0]
        books = LEVER_BOOK.get(prefix)
        if books is None:
            out[name] = "UNMAPPED"
            continue
        if books and all(b in retired for b in books):
            out[name] = "DEAD-OK" if name in DEAD_LEVER_OK else "DEAD"
            continue
        if name in quantities:
            out[name] = "MEASURABLE"
        elif name in UNMEASURABLE_OK:
            out[name] = "UNMEASURABLE-OK"
        else:
            out[name] = "UNMEASURABLE"
    return out


def check(levers=None, quantities=None, retired=None, ratchet=None):
    """-> (ok, lines, counts). Pure, so the selftest can drive every branch."""
    levers = fleet_tuning.LEVERS if levers is None else levers
    quantities = _quantities() if quantities is None else quantities
    retired = retired_rows() if retired is None else retired
    ratchet = RATCHET if ratchet is None else ratchet
    lines, ok = [], True

    if not retired:
        return False, ["FAIL: RETIRED_ROWS parsed EMPTY — this guard would "
                       "report every dead lever as alive. Fail-closed."], {}

    verdicts = classify(levers, quantities, retired)
    counts = {}
    for v in ("MEASURABLE", "UNMEASURABLE", "UNMEASURABLE-OK", "DEAD",
              "DEAD-OK", "UNMAPPED"):
        counts[v] = sum(1 for x in verdicts.values() if x == v)

    unmapped = [k for k, v in verdicts.items() if v == "UNMAPPED"]
    if unmapped:
        ok = False
        lines.append(
            f"FAIL: {len(unmapped)} lever(s) name a book this guard cannot "
            f"classify — add the prefix to LEVER_BOOK: {', '.join(unmapped)}")

    for kind, key, hint in (
            ("UNMEASURABLE", "unmeasurable",
             "give it a QUANTITIES spec (record the quantity it cuts) or "
             "declare it in UNMEASURABLE_OK with a reason and an owner"),
            ("DEAD", "dead",
             "the book is RETIRED — delete the lever, or declare it in "
             "DEAD_LEVER_OK because the retirement is env-reversible")):
        n = counts[kind]
        cap = ratchet.get(key)
        names = sorted(k for k, v in verdicts.items() if v == kind)
        if cap is None:
            continue
        if n > cap:
            ok = False
            lines.append(f"FAIL: {kind} levers {n} > ratchet {cap} — {hint}. "
                         f"New since the ratchet was set: check {names}")
        elif n < cap:
            lines.append(f"RATCHET CAN TIGHTEN: {kind} is {n}, ratchet says "
                         f"{cap} — lower RATCHET['{key}'] to {n} and keep it "
                         "from creeping back")
        else:
            lines.append(f"  {kind:<14} {n:>3} (at ratchet; draining is the "
                         f"job — {hint})")
    lines.append(f"  {'MEASURABLE':<14} {counts['MEASURABLE']:>3}")
    for k in ("UNMEASURABLE-OK", "DEAD-OK"):
        if counts[k]:
            lines.append(f"  {k:<14} {counts[k]:>3} (declared)")
    return ok, lines, counts


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--list", action="store_true",
                    help="print every lever's verdict")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    ok, lines, counts = check()
    if a.list:
        for name, v in sorted(classify(fleet_tuning.LEVERS, _quantities(),
                                       retired_rows()).items(),
                              key=lambda kv: (kv[1], kv[0])):
            print(f"  {v:<16} {name}")
        print()
    for ln in lines:
        print(ln)
    print("audit_lever_measurability: "
          + ("OK — no lever became unmeasurable or dead since the ratchet."
             if ok else "FAIL"))
    return 0 if ok else 1


def selftest():
    LV = {"carry.a": {}, "carry.b": {}, "trend.a": {}, "scout.a": {}}
    RET = {"crypto-trend-daily-lshadow"}
    Q = {"carry.a": {}}

    v = classify(LV, Q, RET)
    assert v == {"carry.a": "MEASURABLE", "carry.b": "UNMEASURABLE",
                 "trend.a": "DEAD", "scout.a": "UNMEASURABLE"}, v

    # an organ lane has no book, so it can never read DEAD however many rows
    # are retired — the retired question simply does not apply to it
    assert classify({"scout.a": {}}, {}, {"anything"})["scout.a"] \
        == "UNMEASURABLE"

    # the ratchet holds at equality, fails on growth, and INVITES tightening
    ok, lines, c = check(LV, Q, RET, {"unmeasurable": 2, "dead": 1})
    assert ok and c["UNMEASURABLE"] == 2 and c["DEAD"] == 1, (ok, c)
    ok2, l2, _ = check(LV, Q, RET, {"unmeasurable": 1, "dead": 1})
    assert not ok2 and any("UNMEASURABLE levers 2 > ratchet 1" in x
                           for x in l2), l2
    ok3, l3, _ = check(LV, Q, RET, {"unmeasurable": 3, "dead": 1})
    assert ok3 and any("RATCHET CAN TIGHTEN" in x for x in l3), l3

    # a declaration moves a lever out of the counted class, both kinds
    try:
        UNMEASURABLE_OK["carry.b"] = "declared for the selftest"
        DEAD_LEVER_OK["trend.a"] = "declared for the selftest"
        v2 = classify(LV, Q, RET)
        assert v2["carry.b"] == "UNMEASURABLE-OK" and v2["trend.a"] == "DEAD-OK"
        # `scout.a` is still undeclared, so UNMEASURABLE drops 2 -> 1, not to
        # zero — the declaration moves ONE lever, which is the property.
        ok4, _, c4 = check(LV, Q, RET, {"unmeasurable": 1, "dead": 0})
        assert ok4 and c4["UNMEASURABLE"] == 1 and c4["DEAD"] == 0, c4
    finally:
        UNMEASURABLE_OK.pop("carry.b", None)
        DEAD_LEVER_OK.pop("trend.a", None)

    # an unmapped prefix FAILS rather than being silently skipped — a new
    # book's levers must not arrive unclassified
    ok5, l5, _ = check({"newbook.x": {}}, {}, RET, {"unmeasurable": 99,
                                                    "dead": 99})
    assert not ok5 and any("LEVER_BOOK" in x for x in l5), l5

    # FAIL-CLOSED on an unparseable retired roster: reporting every dead lever
    # as alive is the one outcome that is wrong in the dangerous direction
    ok6, l6, _ = check(LV, Q, set(), None)
    assert not ok6 and "RETIRED_ROWS parsed EMPTY" in l6[0], l6

    # the real parse works and finds the rows the dashboard declares
    live = retired_rows()
    assert "band-barnes-lshadow" in live and "book-schwager-lshadow" in live, \
        sorted(live)[:8]
    assert "perps-funding-carry-lshadow" not in live, "a LIVING book read as retired"

    # every registered prefix is mapped, on the REAL registry
    unmapped = sorted({k.split(".", 1)[0] for k in fleet_tuning.LEVERS}
                      - set(LEVER_BOOK))
    assert not unmapped, f"unmapped lever prefixes: {unmapped}"
    print("audit_lever_measurability selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
