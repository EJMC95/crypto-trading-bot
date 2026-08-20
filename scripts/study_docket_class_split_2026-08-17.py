#!/usr/bin/env python3
"""study_docket_class_split_2026-08-17.py — how much of each I17 docket verdict
is computed on instruments the book's own class screen no longer admits?

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT 2026-08-17 (ru)/(rw) — FOUR DOCKET VERDICTS REST SUBSTANTIALLY ON ║
║ REMOVED POPULATIONS, AND TWO OF THE FOUR BOOKS ARE POSITIVE ON WHAT THEY  ║
║ CAN STILL TRADE.                                                          ║
║                                                                           ║
║   book                       pooled (the docket)   still-tradeable         ║
║   ⚖️ perps-funding-spread     n=91  −$31.16         n=70  +$5.32           ║
║   🎯 lighter-perp-sniper      n=29   −$3.08         n=6   +$2.21           ║
║   🌾 perps-funding-carry      n=10  −$15.45         n=1   −$0.49           ║
║   🎸 band-barnes              n=9    −$1.45         n=0                    ║
║                                                                           ║
║ `(pf)` measured the carry pair and named the right response in its own     ║
║ words — "REPORT the class split beside the pooled grade, do not re-cut the ║
║ sample" — then shipped the DECLARATION and left the REPORT, so the split   ║
║ stayed derivable and two consecutive reviews re-derived it BY HAND. `(ru)` ║
║ closed that: `golive_readiness.class_split` now publishes it on the book   ║
║ payload, the docket item and the CLI line. THIS SCRIPT IS THE EVIDENCE     ║
║ THAT LICENSED IT, kept so the numbers can be re-run rather than re-argued. ║
║                                                                           ║
║ SECTION 2 — the same question asked of the EXIT harness, and it is why     ║
║ `(rw)` refused a recommendation. 🎯 the Sniper's exit sweep fails its       ║
║ calibration gate (+0.301pp vs a 0.25pp tolerance), and split by class the  ║
║ ONLY subset that calibrates (+0.032pp) is the 16 NON-CRYPTO trades — the   ║
║ population `(lk)` screened off on 13-Aug. The 3 crypto trades it can still ║
║ take miss by +1.738pp. Candle coverage is a full 6 bars per hold window in ║
║ BOTH classes, so the hypothesis that closed underlying markets break the   ║
║ walk is REFUTED — it is sample size, not data. **The Sniper's exit         ║
║ question is answerable only on trades it has stopped taking.**             ║
║                                                                           ║
║ ALSO MEASURED HERE, and it corrected a claim in `(ru)`'s own report: the   ║
║ Sniper HAS a bracket (+15% tp / −10% sl, bare literals) and it is          ║
║ UNREACHABLE at its 6h horizon — median realised move 1.25%, p90 5.18%,     ║
║ max 10.68%, take-profit reached 0 times in 29 closes and the stop once.    ║
║ That is why every close reads `max_hold`: an arithmetically dead bracket,  ║
║ not an absent one.                                                         ║
║                                                                           ║
║ THIS SCRIPT PROMOTES NOTHING. I17 calls are the operator's, and a docketed ║
║ book gets a decision, "never another tuning pass". Measuring is not tuning ║
║ — what this buys is that the decision is made on the right sample.         ║
╚══════════════════════════════════════════════════════════════════════════╝

THE CALIBRATION GATE IS THE POINT, and it is this file's own `(gx)` rule: a
harness that cannot reproduce what DID happen may not say what WOULD have. Before
printing anything, `calibrate()` reproduces THREE independently published splits
— `(pf)`'s carry and Barnes numbers and its ⚖️ Counterweight decomposition — and
REFUSES the whole run on any mismatch. Those three were published by a different
session from different code; agreeing with them is the only reason to believe the
rest of the table.

READ-ONLY. No DB (both feeds are the public endpoints), no lever, no write.

Usage:
  python3 scripts/study_docket_class_split_2026-08-17.py            # section 1
  python3 scripts/study_docket_class_split_2026-08-17.py --sniper   # + section 2
  python3 scripts/study_docket_class_split_2026-08-17.py --selftest
"""
import argparse
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))
sys.path.insert(0, _HERE)

import golive_readiness as G          # noqa: E402  — the ONE owner of the sample

DASH = os.environ.get(
    "PNL_DASH", "https://pnl-dashboard-production-858c.up.railway.app")
LIMIT = int(os.environ.get("CLASS_SPLIT_LIMIT", "5000"))

#: The books this asks about: every one on the I17 docket plus the two graded
#: rows that carry a class screen. Not a curated evidence list — membership is
#: "is it on the docket", and the docket derives from the horizon.
DOCKET = (
    "perps-funding-spread-lshadow", "lighter-perp-sniper-lshadow",
    "perps-funding-carry-lshadow", "band-barnes-lshadow",
    "lighter-ticket-taker-lshadow", "perps-funding-lighter-lshadow",
    "perps-funding-lighter-lighter", "pm-albanese-lshadow",
    "pm-turnbull-lshadow", "freqtrade-georgia-lshadow",
)

#: [(ru)] THE CALIBRATION ANCHORS — (on_n, on_usd, off_n, off_usd) as published
#: by `(pf)` and `(nk)`, from a different session and different code. A mismatch
#: means THIS harness is selecting a different sample than the grader does, and
#: every other row becomes unciteable. Tolerance is 1 cent: these are sums of
#: recorded values, not estimates, so anything looser would hide a real drift.
PUBLISHED = {
    "perps-funding-carry-lshadow": (1, -0.49, 9, -14.96),      # (pf)
    "band-barnes-lshadow": (0, 0.00, 9, -1.45),                # (pf)/(nk)
    "perps-funding-spread-lshadow": (70, 5.32, 21, -36.48),    # (pf)
}
CALIB_TOL_USD = 0.01

#: [(rx)] EVERYTHING THE ANCHOR DEPENDS ON IS PINNED, because an anchor is a
#: HISTORICAL FACT and the feeds are LIVE. The first cut of this file calibrated
#: the published numbers against whatever `/trades.json` and `/pnl.json` said
#: today, so it began failing within the hour — and for two different reasons,
#: both of them the harness's fault rather than a real drift:
#:
#:   * ⚖️ Counterweight read 72/+$5.40 against a published 70/+$5.32. The book
#:     simply TRADED TWICE MORE. Fixed by `CALIB_AS_OF`: the calibration pass
#:     cuts the ledger at the instant the anchors were measured. The live table
#:     below still runs on the whole ledger — only the reproduction is frozen.
#:   * 🎸 Barnes read 54/14 against a published 0/9, because the book was
#:     RETIRED `(pm)` and left `/pnl.json`, so `retired_sleeves` found no payload,
#:     dropped nothing, and graded the dead `xsect` sleeve's 49 closes — the
#:     exact `(nk)` incident, arriving through a vanished publisher instead of a
#:     missing filter. Fixed by `CALIB_SLEEVES`: the sleeve state AS OF the
#:     anchor, declared here rather than fetched.
#:
#: The general rule, and it is why this is worth the twenty lines: a calibration
#: that reads live state is a gate that decays into noise, and a decaying gate
#: gets loosened until it passes. Pin the past; measure the present.
CALIB_AS_OF = "2026-08-17T00:00:00+00:00"
CALIB_SLEEVES = {
    # 🎸 Barnes at the anchor instant: `extreme` (ly) and `xsect` (nf) retired,
    # `carry` living. Its payload no longer publishes this — the book is gone.
    "band-barnes-lshadow": frozenset({"xsect", "extreme"}),
}


def _get(path):
    with urllib.request.urlopen(f"{DASH}{path}", timeout=60) as r:
        return json.loads(r.read().decode())


def parse(s):
    """Tolerant stamp parse that also passes datetimes through — `era_rows`
    hands its `parse` whatever the row carried."""
    if not s or isinstance(s, datetime):
        return s or None
    try:
        return datetime.fromisoformat(str(s).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None


def base_coin(pair):
    return str(pair or "").split("/")[0].split(":")[0].strip().upper()


def sleeve_tag(row):
    """The grader reads `enter_tag` (`<side>-<sleeve>`); the PAPER ledger carries
    `<side>-<sleeve>_<exit>` in `reason`. Strip the exit so
    `drop_retired_sleeves` sees the shape it documents.

    Measured: without this 🎸 Barnes grades at n=68 instead of n=9, i.e. the
    retired `xsect` sleeve's 49 closes stay in — the exact `(nk)` incident, from
    the other side of the feed.
    """
    t = row.get("tag")
    if t:
        return t
    rs = row.get("reason") or ""
    return rs.rsplit("_", 1)[0] if "-" in rs and "_" in rs else None


def graded_rows(bot, ledger, summary, as_of=None, sleeves=None):
    """The rows the go-live bars are ACTUALLY computed on, for one book.

    Composition before time, exactly as `golive_readiness.main` orders it:
    retired sleeves leave first `(nk)`, then `era_rows` picks the era. Both are
    the grader's own functions — re-deriving either here would be the second
    copy `(hq)` was extracted to prevent.
    """
    cut = parse(as_of) if as_of else None
    quads = []
    for r in ledger:
        if r.get("bot") != bot:
            continue
        ca = parse(r.get("closed_at"))
        if ca is None:
            continue
        # [(rx)] the as-of cut is on the CLOSE, because that is when a row
        # enters the ledger the grader reads. Calibration only — `as_of=None`
        # (the live table) keeps every row.
        if cut is not None and ca > cut:
            continue
        quads.append((float(r.get("pnl_pct") or 0), float(r.get("pnl_abs") or 0),
                      ca, parse(r.get("opened_at")), r.get("extra") or {},
                      sleeve_tag(r), r))
    quads.sort(key=lambda q: q[2])
    extra = (summary.get(bot) or {}).get("extra") or {}
    # [(rx)] a PINNED sleeve state wins over the live payload, and must: a
    # retired book has no payload at all, and `retired_sleeves` fail-OPEN then
    # drops nothing — which silently re-admits a dead sleeve's closes.
    retired = (sleeves or {}).get(bot) or G.retired_sleeves(extra) or None
    kept, _dropped = G.drop_retired_sleeves(quads, retired)
    ed = G.era_rows(bot, kept, parse=parse, detail=True)
    return [q[6] for q in ed["scoped_rows"]], ed["iso"], extra


def split_by_class(rows, is_crypto):
    """(on_class, off_class) rows. PURE — the selftest drives it directly."""
    on, off = [], []
    for r in rows:
        (on if is_crypto(base_coin(r.get("pair"))) else off).append(r)
    return on, off


def _usd(rows):
    return round(sum(float(r.get("pnl_abs") or 0) for r in rows), 2)


def calibrate(measured):
    """(ok, lines) — does this harness reproduce the independently published
    splits? Fail-CLOSED: a book missing from `measured` is a MISMATCH, not a
    pass, because a selector that silently drops a book would otherwise
    calibrate by omission."""
    lines, ok = [], True
    for bot, (on_n, on_usd, off_n, off_usd) in sorted(PUBLISHED.items()):
        got = measured.get(bot)
        if got is None:
            lines.append(f"   {bot}: ABSENT from this run — cannot calibrate")
            ok = False
            continue
        g_on, g_off = got
        good = (len(g_on) == on_n and len(g_off) == off_n
                and abs(_usd(g_on) - on_usd) <= CALIB_TOL_USD
                and abs(_usd(g_off) - off_usd) <= CALIB_TOL_USD)
        ok = ok and good
        lines.append(
            f"   {'OK  ' if good else 'MISS'} {bot}: "
            f"on {len(g_on)}/{_usd(g_on):+.2f} (published {on_n}/{on_usd:+.2f}) · "
            f"off {len(g_off)}/{_usd(g_off):+.2f} (published {off_n}/{off_usd:+.2f})")
    return ok, lines


def assemble(ledger, summary, is_crypto):
    """(ok, lines, measured, meta, absent) — PURE, and it RUNS the calibration
    rather than handing its input out.

    [(rx)] The calibrate call lives IN here, not in the I/O shell, because the
    one mutation that survived the first pass was `calibrate(measured)` in
    `section_1` — swapping the live pass for the pinned one, i.e. re-introducing
    the exact defect this file was rewritten to fix, in the one line no test
    reached. Returning a verdict instead of a set makes that mutation land in
    tested code; the shell can now only print.

    [(rx)] TWO PASSES, and the separation is the point. The CALIBRATION pass
    reproduces a historical measurement, so it runs against the pinned as-of and
    sleeve state; the REPORT pass answers "what is true now" and runs against
    everything. Sharing one pass between them is what made the first cut of this
    file un-runnable within the hour.
    """
    calib_set = {}
    for bot in PUBLISHED:
        rows, _era, _x = graded_rows(bot, ledger, summary,
                                     as_of=CALIB_AS_OF, sleeves=CALIB_SLEEVES)
        if rows:
            calib_set[bot] = split_by_class(rows, is_crypto)

    measured, meta, absent = {}, {}, []
    for bot in DOCKET:
        # [(rx)] I1 — LIVENESS BEFORE SEMANTICS. A book with no row on
        # /pnl.json is retired or dark, and its sleeve state is unreadable, so
        # `retired_sleeves` fail-OPEN drops nothing and a dead sleeve's closes
        # get graded: 🎸 Barnes reads n=68 instead of n=9 the moment `(pm)`
        # retires it. Grading that is worse than omitting it — and omitting it
        # SILENTLY is worse still, so it is named on its own line.
        if bot not in summary:
            absent.append(bot)
            continue
        rows, era, extra = graded_rows(bot, ledger, summary)
        if not rows:
            continue
        on, off = split_by_class(rows, is_crypto)
        measured[bot] = (on, off)
        meta[bot] = (era, G.published_class_screen(extra))
    ok, lines = calibrate(calib_set)
    return ok, lines, measured, meta, absent


def section_1():
    import fleet_bus
    ledger = (_get(f"/trades.json?source=paper&limit={LIMIT}") or {}).get("trades") or []
    summary = {r["bot"]: r for r in (_get("/pnl.json") or {}).get("bots") or []}
    print(f"ledger rows: {len(ledger)}   books on /pnl.json: {len(summary)}\n")
    ok, lines, measured, meta, absent = assemble(
        ledger, summary, fleet_bus.is_crypto)
    print(f"CALIBRATION against the independently published splits "
          f"((pf)/(nk)) as of {CALIB_AS_OF}, tolerance ${CALIB_TOL_USD:.2f}:")
    print("\n".join(lines))
    if not ok:
        print("\nCALIBRATION FAILED — every row below is WITHHELD. This harness "
              "is selecting a different sample than the grader; fix that before "
              "believing any number here ((gx)).")
        return 1
    print("   -> PASS. The rest of the table is citeable.\n")

    print(f"{'book':32s} {'screen':6s} {'n':>4s} {'pooled$':>9s} | "
          f"{'on n':>5s} {'on $':>9s} | {'off n':>5s} {'off $':>9s}")
    print("-" * 96)
    for bot, (on, off) in measured.items():
        era, screen = meta[bot]
        lab = {True: "crypto", False: "both", None: "UNPUB"}[screen]
        flag = "   <- REMOVED POPULATION" if (screen is True and off) else ""
        print(f"{bot:32s} {lab:6s} {len(on)+len(off):4d} "
              f"{_usd(on)+_usd(off):9.2f} | {len(on):5d} {_usd(on):9.2f} | "
              f"{len(off):5d} {_usd(off):9.2f}{flag}")
    for bot in absent:
        print(f"{bot:32s} {'—':6s}    —         — |     —         — |     —         —"
              f"   <- ABSENT from /pnl.json: retired or dark, NOT graded (I1)")
    print("\nAn UNPUB screen is reported and never read as a finding — an "
          "unpublished screen may neither manufacture one nor erase one (I6).")
    return 0


def section_2():
    """🎯 the Sniper's exit question, asked through the repo's own sweeper."""
    import statistics
    import fleet_bus
    import study_exit_sweep as S
    from study_exit_attribution import fetch_trades

    BOOK = "lighter-perp-sniper-lshadow"
    rows = [r for r in fetch_trades() if r.get("bot") == BOOK]
    trades, no_px, no_side = S.load_trades(BOOK, rows)
    print(f"\n{'='*96}\nSECTION 2 — 🎯 {BOOK}\n"
          f"usable {len(trades)}  (no price {no_px}, no side {no_side})")
    # [(rw)] the side gap is DRAINED HISTORY, not a live defect: every row
    # missing `side` opened <=3-Aug, every row from 5-Aug carries it (the 4-Aug
    # source-stamped tag). Stated because "9 rows have no side" reads like the
    # (kf) inversion class until the dates are checked.
    shipped = S.shipped_rule(BOOK)
    print(f"shipped rule, read from the module: {shipped}")

    ledger = [r for r in rows if r.get("pnl_pct") is not None]
    mv = sorted(abs(float(r["pnl_pct"])) for r in ledger)
    print(f"\nIS THE BRACKET REACHABLE? realised |move| over {len(mv)} closes: "
          f"median {statistics.median(mv)*100:.2f}%  "
          f"p90 {mv[int(.9*len(mv))-1]*100:.2f}%  max {max(mv)*100:.2f}%")
    print(f"   closes reaching tp {shipped.get('tp_pct',0)*100:.0f}%: "
          f"{sum(1 for r in ledger if float(r['pnl_pct']) >= shipped.get('tp_pct', 9))}"
          f"   ·   reaching sl {shipped.get('sl_pct',0)*100:.0f}%: "
          f"{sum(1 for r in ledger if float(r['pnl_pct']) <= -shipped.get('sl_pct', 9))}")

    ids = S.market_ids()
    lo = min(t["entry_ts"] for t in trades) - 3600
    hi = max(t["entry_ts"] for t in trades) + int(S.MAX_HORIZON_H * 3600)
    candles = {}
    for sym in sorted({t["sym"] for t in trades}):
        mid = ids.get(sym)
        if mid is not None:
            try:
                candles[sym] = S.fetch_candles(mid, lo, hi)
            except Exception as e:      # noqa: BLE001
                print(f"   candle fetch failed {sym}: {type(e).__name__}")

    key = {(t["sym"], t["entry_ts"]) for t in trades}
    used = [r for r in rows
            if (base_coin(r.get("pair")),
                int(parse(r.get("opened_at")).timestamp())
                if parse(r.get("opened_at")) else None) in key]

    print("\nCALIBRATION of the shipped rule, by instrument class:")
    for label, pick in (("ALL", lambda s: True),
                        ("CRYPTO", fleet_bus.is_crypto),
                        ("NON-CRYPTO", lambda s: not fleet_bus.is_crypto(s))):
        tr = [t for t in trades if pick(t["sym"])]
        lg = [r for r in used if pick(base_coin(r.get("pair")))]
        if not tr:
            continue
        sc = S.score(S.simulate(tr, candles, shipped))
        actual = 100 * statistics.fmean(float(r["pnl_pct"] or 0) for r in lg)
        good, _why = S.calibrate(sc, actual)
        print(f"   {label:11s} n={len(tr):3d}  replayed {sc['mean_pct']:+7.3f}%  "
              f"ledger {actual:+7.3f}%  gap {sc['mean_pct']-actual:+6.3f}pp  "
              f"-> {'CALIBRATES' if good else 'FAILS'}")
    return 0


def _selftest():
    """Offline and pure: the split, the sleeve tag, and the calibration gate's
    fail-CLOSED direction. No network, no DB — registered in SELFTEST_MODULES,
    so it must stay that way."""
    crypto = {"BTC", "KAITO"}

    def isc(s):
        return s in crypto

    rows = [{"pair": "BTC/USDC", "pnl_abs": 1.0},
            {"pair": "KAITO/USDC", "pnl_abs": -0.49},
            {"pair": "WTI/USD", "pnl_abs": -2.0},
            {"pair": "SPCX/USD", "pnl_abs": -1.0}]
    on, off = split_by_class(rows, isc)
    assert [r["pair"] for r in on] == ["BTC/USDC", "KAITO/USDC"], on
    assert [r["pair"] for r in off] == ["WTI/USD", "SPCX/USD"], off
    assert _usd(on) == 0.51 and _usd(off) == -3.0, (_usd(on), _usd(off))

    # the quote is split off before classifying — `(lc)` records the cost of not
    # doing it: a ledger-shaped `SKHY/USDC` missed the set and read as crypto.
    assert base_coin("SKHY/USDC") == "SKHY" and base_coin("XAU") == "XAU"

    # the sleeve tag round-trips to the shape drop_retired_sleeves documents
    assert sleeve_tag({"reason": "long-xsect_rebalance"}) == "long-xsect"
    assert G.sleeve_of(sleeve_tag({"reason": "long-xsect_rebalance"})) == "xsect"
    assert sleeve_tag({"reason": "long_max_hold"}) is None      # no sleeve
    assert sleeve_tag({"tag": "long-carry", "reason": "x_y"}) == "long-carry"

    # [(rx)] THE ANCHORS THEMSELVES ARE PINNED AS LITERALS. Every other arm
    # builds its fixture FROM `PUBLISHED`, so editing an anchor would move the
    # fixture with it and re-baseline the gate in silence — the mirror of the
    # tolerance defect one block down. These three numbers are `(pf)`/`(nk)`'s
    # published measurements, restated here so a change to them has to argue
    # with a test rather than pass unnoticed.
    assert PUBLISHED["perps-funding-carry-lshadow"] == (1, -0.49, 9, -14.96)
    assert PUBLISHED["band-barnes-lshadow"] == (0, 0.00, 9, -1.45)
    assert PUBLISHED["perps-funding-spread-lshadow"] == (70, 5.32, 21, -36.48)
    assert CALIB_AS_OF == "2026-08-17T00:00:00+00:00"
    assert CALIB_SLEEVES["band-barnes-lshadow"] == frozenset({"xsect", "extreme"})

    # CALIBRATION IS FAIL-CLOSED, and each arm is pinned separately.
    good = {b: ([{"pair": "X", "pnl_abs": v[1]}] * 0 or
                [{"pair": "X", "pnl_abs": v[1] / v[0]}] * v[0] if v[0] else [],
                [{"pair": "Y", "pnl_abs": v[3] / v[2]}] * v[2] if v[2] else [])
            for b, v in PUBLISHED.items()}
    ok, _ = calibrate(good)
    assert ok, "the published numbers must calibrate against themselves"
    # a book missing entirely FAILS rather than passing by omission
    partial = dict(good)
    partial.pop("band-barnes-lshadow")
    assert not calibrate(partial)[0], "an absent book must not calibrate"
    # a wrong count fails
    bad = dict(good)
    bad["band-barnes-lshadow"] = ([], [{"pair": "Y", "pnl_abs": -1.45}] * 8)
    assert not calibrate(bad)[0], "a wrong n must not calibrate"
    # a wrong dollar total fails
    bad2 = dict(good)
    bad2["perps-funding-carry-lshadow"] = (
        [{"pair": "X", "pnl_abs": -0.49}], [{"pair": "Y", "pnl_abs": -99.0}])
    assert not calibrate(bad2)[0], "a wrong total must not calibrate"
    # [(rx)] AND A GAP OF ONE CENT OVER TOLERANCE FAILS — the arm that pins the
    # TOLERANCE ITSELF. Without it, widening CALIB_TOL_USD to swallow a real
    # drift leaves every other arm green, which is how a gate gets "fixed" by
    # loosening until it passes (the survivor of this file's own mutation run).
    # The gap is a LITERAL, never derived from CALIB_TOL_USD — a fixture that
    # scales with the constant it is pinning widens along with it and asserts
    # nothing, which is what the first version of this arm did.
    assert CALIB_TOL_USD == 0.01, (
        "the calibration tolerance moved; these are sums of RECORDED values, "
        "not estimates, so a cent is already generous and widening it hides "
        "exactly the sample drift this gate exists to catch")
    edge = dict(good)
    n_on, usd_on, n_off, usd_off = PUBLISHED["perps-funding-carry-lshadow"]
    edge["perps-funding-carry-lshadow"] = (
        [{"pair": "X", "pnl_abs": usd_on / n_on}] * n_on if n_on else [],
        [{"pair": "Y", "pnl_abs": (usd_off - 0.02) / n_off}] * n_off)
    assert not calibrate(edge)[0], \
        "a 2-cent gap must exceed a 1-cent tolerance"

    # [(rx)] THE AS-OF CUT and THE PINNED SLEEVE STATE — the two things that
    # make a historical anchor reproducible against a live feed.
    led = [
        {"bot": "B", "pair": "BTC/USDC", "pnl_pct": 0.01, "pnl_abs": 1.0,
         "closed_at": "2026-08-16T12:00:00+00:00", "opened_at": "2026-08-16T06:00:00+00:00",
         "reason": "long-carry_flip"},
        {"bot": "B", "pair": "WTI/USD", "pnl_pct": -0.02, "pnl_abs": -2.0,
         "closed_at": "2026-08-16T13:00:00+00:00", "opened_at": "2026-08-16T06:00:00+00:00",
         "reason": "long-xsect_rebalance"},
        {"bot": "B", "pair": "ETH/USDC", "pnl_pct": 0.03, "pnl_abs": 3.0,
         "closed_at": "2026-08-18T00:00:00+00:00", "opened_at": "2026-08-17T20:00:00+00:00",
         "reason": "long-carry_flip"},                       # AFTER the cut
        # [(rx)] THE STRADDLER, and it is the row that makes the cut's BASIS
        # testable: opened BEFORE the anchor, closed AFTER it. A cut keyed on
        # the OPEN would keep this and reproduce a different number than the
        # grader, which reads the ledger as rows arrive — i.e. on the CLOSE.
        {"bot": "B", "pair": "SOL/USDC", "pnl_pct": 0.05, "pnl_abs": 5.0,
         "closed_at": "2026-08-17T09:00:00+00:00", "opened_at": "2026-08-16T09:00:00+00:00",
         "reason": "long-carry_flip"},
    ]
    cut = "2026-08-17T00:00:00+00:00"
    # no cut, no pins: everything grades, including the retired sleeve
    r_all, _e, _x = graded_rows("B", led, {})
    assert len(r_all) == 4, r_all
    # the as-of cut drops the later close and NOTHING else
    r_cut, _e, _x = graded_rows("B", led, {}, as_of=cut)
    assert len(r_cut) == 2 and all(x["closed_at"] < cut for x in r_cut), r_cut
    assert not any(x["pair"] == "SOL/USDC" for x in r_cut), \
        "the straddler CLOSED after the anchor — a cut on the OPEN would keep it"
    # the PINNED sleeve state drops xsect even with no payload to read it from
    r_pin, _e, _x = graded_rows("B", led, {}, as_of=cut,
                                sleeves={"B": frozenset({"xsect"})})
    assert [x["pair"] for x in r_pin] == ["BTC/USDC"], r_pin
    # ...and a live payload still works when there IS one (fail-open path)
    r_live, _e, _x = graded_rows(
        "B", led, {"B": {"extra": {"sleeves": {"xsect": {"retired": True}}}}},
        as_of=cut)
    assert [x["pair"] for x in r_live] == ["BTC/USDC"], r_live

    # [(rx)] THE TWO ARMS THAT USED TO LIVE BEHIND THE NETWORK. Both survived
    # mutation until `assemble` was extracted, which is the whole reason it is
    # a function: an untestable branch is where the first cut's defect lived.
    led2 = list(led) + [
        {"bot": "perps-funding-carry-lshadow", "pair": "KAITO/USDC",
         "pnl_pct": -0.0016, "pnl_abs": -0.49,
         "closed_at": "2026-08-16T10:00:00+00:00",
         "opened_at": "2026-08-16T04:00:00+00:00", "reason": "long_flip"},
        {"bot": "perps-funding-carry-lshadow", "pair": "WTI/USD",
         "pnl_pct": -0.02, "pnl_abs": -9.99,
         "closed_at": "2026-08-18T10:00:00+00:00",          # AFTER the anchor
         "opened_at": "2026-08-18T04:00:00+00:00", "reason": "long_flip"},
    ]
    summ = {"perps-funding-carry-lshadow": {"extra": {"caps": {"crypto_only": True}}}}
    ok2, lines2, meas, _meta, absent = assemble(
        led2, summ, lambda s: s in ("KAITO", "BTC", "ETH", "SOL"))
    # the fixture cannot match the REAL published anchors, so it must FAIL —
    # and failing is the assertion: it proves `assemble` ran the calibration on
    # its own pinned pass rather than on the live one. Under the live pass the
    # carry row would read on=1/off=1 and miss by a different amount; under the
    # pinned pass it reads on=1/off=0. Either way it fails, so the DISCRIMINATOR
    # is the reported line, not the boolean.
    assert ok2 is False and any("perps-funding-carry" in l for l in lines2)
    carry_line = next(l for l in lines2 if "perps-funding-carry" in l)
    assert "on 1/-0.49" in carry_line and "off 0/+0.00" in carry_line, carry_line
    # the REPORT pass sees everything, so it DOES carry the later close
    r_on, r_off = meas["perps-funding-carry-lshadow"]
    assert len(r_on) == 1 and len(r_off) == 1, (r_on, r_off)
    # every DOCKET book with no /pnl.json row is NAMED, never graded (I1)
    assert "band-barnes-lshadow" in absent and "band-barnes-lshadow" not in meas
    assert set(absent) <= set(DOCKET)

    print("study_docket_class_split selftest OK (class split, quote-stripped "
          "base, sleeve tag round-trip, calibration fail-closed on absent book "
          "/ wrong n / wrong total, anchors + as-of + sleeve state + tolerance "
          "pinned as literals, as-of cut keyed on the CLOSE, pinned sleeves "
          "beat an absent payload, assemble runs its own pinned pass)")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--sniper", action="store_true",
                    help="also run section 2 (fetches Lighter candles)")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    rc = section_1()
    if rc == 0 and a.sniper:
        rc = section_2()
    print("\nREAD-ONLY. Evidence for an I17 decision, not permission to tune a "
          "book that is waiting for one.")
    return rc


if __name__ == "__main__":
    sys.exit(main() or 0)
