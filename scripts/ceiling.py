#!/usr/bin/env python3
"""HOW HIGH CAN THIS BOOK GO? — the mirror of the go-live gate.

**Operator, 2026-08-20: "The discussion of the floor is too often had, where the
conversation of how high the ceiling goes is of little discussion... they know
the floor all too well."**

Count the bars this fleet measures a book against. The go-live gate asks six
questions and **every one is a floor**: >=30 days, >=30 closes, mean > 0,
t >= 2.0, both halves positive, maxDD < 15%. Six ways of asking *don't be bad*.
Add the stops, the vetoes, the class screens, the cages, the drawdown governor
and the halt — and there is not one instrument in the tree that asks **what is
the most this book could earn, and what is standing in the way.**

So the fleet optimises the only thing it measures. Measured 2026-08-20, slot
occupancy against each book's OWN cap, beside its own mean per trade:

    👩 mum          +4.658%/trade    100% of cap     0.18 closes/day
    🙏 avo          +1.085%           40%
    🌾 carry        +0.254%           49%
    🔮 georgia      +0.122%            9%   <- the CLOSEST book to the gate
    🎫 taker        -0.167%           74%
    🪁 kelly        -0.939%           23%
    🧘 douglas      -1.152%            9%
    ⚖️ counterweight -1.433%          102%   <- the WORST book, FULL
    🛢️ garrett      -1.460%           88%

**The two worst books in the fleet run at 88-102% of capacity; the best runs at
100% of a cap of four and takes one trade every five days.** Capital sits in
inverse proportion to measured edge, and no organ was ever asked the question
that would have shown it.

WHAT A CEILING IS, ARITHMETICALLY. A book's output decomposes exactly:

    $/day  =  rate  x  clip  x  mean_pct
              ^        ^        ^
              |        |        `- EDGE: what the strategy is. Not a lever.
              |        `---------- SIZE: per-trade % is INVARIANT to clip
              |                    ((hl), measured), so this is a FREE
              |                    multiplier up to depth and the maxDD bar.
              `------------------- RATE: bounded by cap / mean_hold, i.e. by
                                   slots and by how long each one is held.

Two of the three are pure capacity and neither costs expectancy. The fleet has
spent months on the third and capped the other two.

THE DISCIPLINE THAT KEEPS THIS FROM BEING RECKLESS — and it is the whole design:

  * **A ceiling is only computed on a book whose EDGE LOWER BOUND is positive**
    (I16: `max(0, mean - 1.28*SE)`, never the mean). Scale a book whose lower
    bound is zero and you scale a coin flip. For those books the ceiling
    question is a DIFFERENT one and this instrument asks it instead — see
    below.
  * **For an unproven book the ceiling lever is the rate of EVIDENCE, not the
    rate of money.** `closes_needed` to reach t=2.0 at its own measured
    mean/sd, and how many days that is now versus at full slot occupancy. That
    unifies I17's decidability with the ceiling: *how fast can this book learn
    what it is?* — which is the only ceiling an unproven book has.
  * **Widening rate by holding LESS is not ceiling, it is denominator
    shrinkage** ((hl) killed 25 of 30 candidates on exactly this). Rate headroom
    is computed from UNUSED SLOTS at the book's own measured hold, never from a
    shorter hold.
  * **A ceiling is what is REACHABLE, never a promise.** Rate headroom says
    "this book could run N times faster if its slots filled" — it does NOT say
    the signal exists to fill them. That is the next question and the book's
    own census is where it is answered; naming the ceiling without naming the
    supply would be the same overstatement `(gl)` warns about.
  * **The clip ceiling is bounded by the drawdown bar and by measured depth**,
    not by optimism: %-drawdown scales with clip against a fixed book, so the
    clip headroom is capped at `15% / measured_maxdd`, and separately by what
    the venue's own book will fill (`study_depth_vs_volume`).

It PROMOTES NOTHING and MOVES NOTHING. Like `golive_readiness`, it publishes.

    python3 scripts/ceiling.py
    python3 scripts/ceiling.py --publish
    python3 scripts/ceiling.py --selftest
"""
import argparse
import json
import math
import os
import statistics
import sys
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

DASH = os.environ.get(
    "PNL_DASH", "https://pnl-dashboard-production-858c.up.railway.app")

#: The go-live drawdown bar. The clip ceiling is bounded by it, because
#: %-drawdown scales with clip against a fixed book — doubling the clip doubles
#: the drawdown that has to fit under 15%.
MAXDD_BAR = 0.15
#: I16's one-sided z. Ranking on the mean rewards small samples that got lucky.
Z = 1.28
#: The `t` a book must reach to be gradeable. Used only to price DECIDABILITY
#: for unproven books — never as a bar here.
T_BAR = 2.0
#: Below this many closes nothing is said at all: a ceiling computed on four
#: trades is a number about four trades.
MIN_N = 8

TTL_SEC = 6 * 3600
KEY = "fleet-ceiling"


def _ts(s):
    if not s:
        return None
    s = str(s)
    if " " in s and "T" not in s:
        s = s.replace(" UTC", "+00:00").replace(" ", "T", 1)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    return d.replace(tzinfo=timezone.utc) if d.tzinfo is None else d


def edge(pcts):
    """-> (mean, se, lower_bound). The LOWER BOUND is what may be scaled."""
    n = len(pcts)
    if n < 2:
        return (statistics.fmean(pcts) if pcts else 0.0), None, 0.0
    m = statistics.fmean(pcts)
    sd = statistics.stdev(pcts)
    se = sd / math.sqrt(n) if sd > 0 else 0.0
    return m, se, max(0.0, m - Z * se)


def closes_for_t(pcts, t_bar=T_BAR):
    """How many closes at THIS mean and sd to reach `t_bar`.

    `t = mean/(sd/sqrt(n))`, so `n_req = (t_bar*sd/mean)^2`. None when the mean
    is <= 0 (no sample size reaches a bar the sign never will) or sd is 0.
    """
    n = len(pcts)
    if n < 2:
        return None
    m = statistics.fmean(pcts)
    sd = statistics.stdev(pcts)
    if m <= 0 or sd <= 0:
        return None
    return int(math.ceil((t_bar * sd / m) ** 2))


def book_ceiling(*, closes, span_days, concurrency, cap, clip, equity,
                 maxdd=None, depth_clip=None):
    """The whole reading for one book. Pure — every input is measured.

    `closes` is a list of per-trade fractional returns.
    """
    n = len(closes)
    out = {"n": n, "span_days": round(span_days, 2) if span_days else None}
    if n < MIN_N or not span_days or span_days <= 0:
        out["verdict"] = "TOO-THIN"
        out["binding"] = f"only {n} closes — a ceiling here is a number about {n} trades"
        return out

    mean, se, lb = edge(closes)
    rate = n / span_days
    hold_d = (concurrency / rate) if rate else None      # Little's law
    out.update({
        "mean_pct": round(mean * 100, 4),
        "lower_bound_pct": round(lb * 100, 4),
        "closes_per_day": round(rate, 3),
        "mean_hold_days": round(hold_d, 3) if hold_d else None,
        "concurrency": round(concurrency, 2),
        "cap": cap,
        "slot_use_pct": round(100 * concurrency / cap, 1) if cap else None,
        "clip_usd": clip,
        "deployed_usd": round(concurrency * clip, 2) if clip else None,
        "equity_usd": equity,
    })
    if clip and equity:
        out["capital_use_pct"] = round(100 * concurrency * clip / equity, 1)
    out["usd_per_day"] = (round(rate * clip * mean, 4)
                          if (clip and rate) else None)

    # ---- RATE headroom: unused SLOTS at the book's OWN measured hold.
    # Never from a shorter hold — that is denominator shrinkage, which (hl)
    # measured as the whole of 25 of 30 "more trades" candidates.
    rate_x = (cap / concurrency) if (cap and concurrency > 0) else None
    # ---- SIZE headroom: bounded by the drawdown bar and by measured depth.
    dd_x = (MAXDD_BAR / maxdd) if (maxdd and maxdd > 0) else None
    depth_x = (depth_clip / clip) if (depth_clip and clip) else None
    size_x = min([x for x in (dd_x, depth_x) if x] or [None] or [None]) \
        if (dd_x or depth_x) else None
    out["rate_headroom_x"] = round(rate_x, 2) if rate_x else None
    out["size_headroom_x"] = round(size_x, 2) if size_x else None
    out["size_bound_by"] = ("drawdown bar" if (dd_x and (not depth_x or dd_x <= depth_x))
                            else "measured depth" if depth_x else "unmeasured")

    if lb <= 0:
        # ---- UNPROVEN: the ceiling is DECIDABILITY, not dollars. The only
        # ceiling a book without an established edge has is how fast it can
        # find out what it is.
        need = closes_for_t(closes)
        out["verdict"] = "UNPROVEN"
        if need is None:
            out["binding"] = ("mean is <= 0 — no sample size reaches a bar the "
                              "SIGN never will. This is a keep-or-retire "
                              "question (I17), not a capacity one.")
            out["closes_to_t2"] = None
        else:
            remain = max(0, need - n)
            out["closes_to_t2"] = need
            out["days_to_t2_now"] = round(remain / rate, 1) if rate else None
            if rate_x and rate_x > 1.01:
                out["days_to_t2_at_full_slots"] = round(
                    remain / (rate * rate_x), 1)
                out["binding"] = (
                    f"DECIDABILITY. {remain} more closes to t=2.0: "
                    f"{out['days_to_t2_now']}d at today's {concurrency:.1f} of "
                    f"{cap} slots, {out['days_to_t2_at_full_slots']}d at full "
                    f"occupancy — a {rate_x:.1f}x speed-up that costs no "
                    "expectancy IF its supply can fill them; read the book's "
                    "own census for what stops them")
            else:
                out["binding"] = (
                    f"DECIDABILITY, and slots are NOT the answer — it is "
                    f"already at {out['slot_use_pct']}% of cap. "
                    f"{remain} closes to t=2.0 = {out['days_to_t2_now']}d. "
                    "Raising the cap or the signal supply is the only lever.")
        return out

    # ---- PROVEN edge: the ceiling is money, and it is the product of the two
    # capacity factors applied to the LOWER BOUND (never the mean).
    out["verdict"] = "PROVEN"
    floor_usd_day = rate * clip * lb if clip else None
    total_x = (rate_x or 1.0) * (size_x or 1.0)
    out["usd_per_day_lower_bound"] = (round(floor_usd_day, 4)
                                      if floor_usd_day is not None else None)
    out["ceiling_usd_per_day"] = (round(floor_usd_day * total_x, 4)
                                  if floor_usd_day is not None else None)
    out["headroom_x"] = round(total_x, 2)
    which = []
    if rate_x and rate_x > 1.05:
        which.append((rate_x, f"SLOTS — {concurrency:.1f} of {cap} used, "
                              f"{rate_x:.1f}x by filling its own capacity IF "
                              "supply allows (census says what stops it)"))
    if size_x and size_x > 1.05:
        which.append((size_x, f"CLIP — ${clip:.0f} against a {out['size_bound_by']} "
                              f"limit of {size_x:.1f}x"))
    if which:
        which.sort(reverse=True)
        out["binding"] = which[0][1]
        out["then"] = [w[1] for w in which[1:]]
    else:
        out["binding"] = ("AT ITS CEILING on both capacity factors — further "
                          "growth has to come from the EDGE itself")
    return out


# --------------------------------------------------------------------- I/O

def load_rows(limit=5000, ledger=None):
    if ledger:
        return json.load(open(ledger))["trades"]
    with urllib.request.urlopen(
            f"{DASH}/trades.json?source=paper&limit={int(limit)}",
            timeout=180) as r:
        return json.loads(r.read().decode())["trades"]


def load_books(feed=None):
    if feed:
        return json.load(open(feed))["bots"]
    with urllib.request.urlopen(f"{DASH}/pnl.json", timeout=90) as r:
        return json.loads(r.read().decode())["bots"]


#: Clip and cap for books that do not publish them in `extra.caps`. Read from
#: the module's own constant, and pinned by the test — a retyped constant is a
#: constant that drifts ((gn)'s lesson, on a harness that measured a book the
#: fleet does not run).
FALLBACK = {
    "perps-funding-carry-lshadow": (300.0, 12),
    "perps-funding-spread-lshadow": (20.0, 10),
    "lighter-ticket-taker-lshadow": (80.0, 6),
    "lighter-ticket-taker-lighter": (80.0, 6),
    "perps-funding-lighter-lshadow": (30.0, 6),
    "perps-funding-lighter-lighter": (30.0, 6),
    "band-garrett-lshadow": (25.0, 6),
    "freqtrade-georgia-lshadow": (50.0, 5),
    "freqtrade-avo-maria-lshadow": (50.0, 6),
    "freqtrade-avo-maria-lighter": (50.0, 6),
    "freqtrade-mum-lshadow": (50.0, 4),
    "lighter-perp-sniper-lshadow": (50.0, 4),
    "pm-albanese-lshadow": (50.0, 4),
    "pm-turnbull-lshadow": (50.0, 4),
}


def survey(rows, books):
    out = {}
    for b in books:
        bot = b.get("bot")
        tr = [r for r in rows if r.get("bot") == bot
              and _ts(r.get("closed_at")) and _ts(r.get("opened_at"))]
        if not tr:
            continue
        span = (max(_ts(r["closed_at"]) for r in tr)
                - min(_ts(r["opened_at"]) for r in tr)).total_seconds() / 86400
        hold = sum((_ts(r["closed_at"]) - _ts(r["opened_at"])).total_seconds()
                   / 3600 for r in tr)
        concur = hold / (span * 24) if span > 0 else 0.0
        caps = (b.get("extra") or {}).get("caps") or {}
        fb_clip, fb_cap = FALLBACK.get(bot, (None, None))
        clip = caps.get("clip_usd") or fb_clip
        cap = (caps.get("max_positions") or caps.get("legs")
               or caps.get("max_open") or fb_cap)
        pcts = [r["pnl_pct"] for r in tr
                if isinstance(r.get("pnl_pct"), (int, float))]
        out[bot] = book_ceiling(
            closes=pcts, span_days=span, concurrency=concur, cap=cap,
            clip=clip, equity=b.get("equity") or 1000.0)
    return out


def _cell(v, fmt, width):
    """f-strings cannot carry a backslash, and a nested quote needs one — so
    the formatting lives here rather than inline. Absent is an em dash, never
    a zero: a book with no measurable ceiling and a book with a ceiling of
    zero are different states."""
    if v is None:
        return f"{'—':>{width}}"
    return f"{format(v, fmt):>{width}}"


def render(res):
    L = []
    L.append(f"  {'book':<32}{'verdict':>9}{'n':>5}{'lb%/t':>8}{'slots':>13}"
             f"{'$/day':>9}{'ceiling':>9}{'x':>6}  binding")
    order = {"PROVEN": 0, "UNPROVEN": 1, "TOO-THIN": 2}
    for bot, r in sorted(res.items(),
                         key=lambda kv: (order.get(kv[1].get("verdict"), 3),
                                         -(kv[1].get("headroom_x") or 0))):
        slots = (f"{r.get('concurrency', 0):.1f}/{r.get('cap')} "
                 f"{r.get('slot_use_pct')}%") if r.get("cap") else "—"
        L.append(
            f"  {bot:<32}{r.get('verdict', '?'):>9}{r.get('n', 0):>5}"
            + _cell(r.get("lower_bound_pct"), ".3f", 8)
            + f"{slots:>13}"
            + _cell(r.get("usd_per_day"), "+.3f", 9)
            + _cell(r.get("ceiling_usd_per_day"), "+.3f", 9)
            + _cell(r.get("headroom_x"), ".1f", 6)
            + f"  {r.get('binding', '')[:96]}")
    return "\n".join(L)


def render_designs(res, books):
    """Each book's own design beside its measured headroom.

    [(sh)] The divergent half, and the reason `fleet_manifest` exists: a
    ceiling number alone tells a book to go faster; a ceiling number beside
    what that book is FOR tells it which direction is up. `flies_when` is
    written per book precisely because one fleet-wide notion of "better"
    cannot say that 🌾 carry flies by holding more, 🔮 georgia by becoming
    gradeable, and 🧮 Hull by simply surviving to thirty closes.
    """
    try:
        import fleet_manifest as FM
    except Exception:                                            # noqa: BLE001
        return ""
    extras = {b.get("bot"): (b.get("extra") or {}) for b in books}
    L = ["", "  ── what each book is FOR, and what flying looks like for IT ──"]
    for bot, r in sorted(res.items()):
        d = FM.design_for(bot, extras.get(bot))
        if not d:
            L.append(f"\n  {bot}  — NO DECLARED DESIGN")
            continue
        head = f"{d.get('emoji', '')}  {d.get('name', bot)}".strip()
        L.append(f"\n  {head}  ({bot})")
        if d.get("design"):
            L.append(f"     is for   : {d['design']}")
        if d.get("flies_when"):
            L.append(f"     flies when: {d['flies_when']}")
        if d.get("floor"):
            L.append(f"     never    : {d['floor']}")
        L.append(f"     measured : {r.get('verdict')} — {r.get('binding', '')}")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--ledger")
    ap.add_argument("--feed")
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--designs", action="store_true",
                    help="each book's declared design beside its headroom")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    _books = load_books(feed=a.feed)
    res = survey(load_rows(ledger=a.ledger), _books)
    print(render(res))
    proven = {k: v for k, v in res.items() if v.get("verdict") == "PROVEN"}
    if proven:
        tot = sum(v["usd_per_day_lower_bound"] or 0 for v in proven.values())
        ceil = sum(v["ceiling_usd_per_day"] or 0 for v in proven.values())
        print(f"\n  PROVEN books: ${tot:+.3f}/day at their measured lower "
              f"bound, ${ceil:+.3f}/day at their reachable ceiling "
              f"({(ceil / tot if tot else 0):.1f}x) — and NOT ONE of those "
              "dollars needs a better strategy, only its own unused capacity.")
    print("\n  A ceiling is computed only on a book whose EDGE LOWER BOUND is "
          "positive (I16).\n  For the rest the ceiling is DECIDABILITY — how "
          "fast it can learn what it is.\n  Rate headroom comes from UNUSED "
          "SLOTS at the book's own hold, never a shorter one.")
    if a.designs:
        print(render_designs(res, _books))
    if a.publish:
        import bot_pnl_store as store
        ok = store.save_state(KEY, {
            "updated": datetime.now(timezone.utc).isoformat(),
            "ttl_sec": TTL_SEC, "books": res})
        print(f"published {KEY}: {ok}")
        return 0 if ok else 1
    return 0


def selftest():
    good = [0.02] * 40                     # a clean, proven edge
    r = book_ceiling(closes=good, span_days=40, concurrency=1.0, cap=4,
                     clip=80.0, equity=1000.0, maxdd=0.03)
    assert r["verdict"] == "PROVEN", r
    assert r["rate_headroom_x"] == 4.0, r          # 1 of 4 slots used
    assert r["size_headroom_x"] == 5.0, r          # 15% bar / 3% measured dd
    assert r["headroom_x"] == 20.0, r
    assert r["ceiling_usd_per_day"] == round(
        r["usd_per_day_lower_bound"] * 20.0, 4), r
    # the BINDING factor is the LARGEST headroom — the single change that buys
    # most — and the runners-up are listed after it, so the reading is a
    # ranked plan rather than one number
    assert "CLIP" in r["binding"], r["binding"]        # 5.0x beats slots' 4.0x
    assert any("SLOTS" in t for t in r["then"]), r["then"]
    # …and when slots dominate, slots lead
    r_slots = book_ceiling(closes=good, span_days=40, concurrency=0.5, cap=10,
                           clip=80.0, equity=1000.0, maxdd=0.10)
    assert "SLOTS" in r_slots["binding"], r_slots["binding"]
    assert r_slots["rate_headroom_x"] == 20.0, r_slots

    # THE LOWER BOUND, not the mean, is what gets scaled — a lucky small sample
    # must not produce a big ceiling (I16)
    lucky = [0.05, -0.04, 0.06, -0.03, 0.07, -0.05, 0.08, -0.06, 0.09]
    r2 = book_ceiling(closes=lucky, span_days=9, concurrency=1.0, cap=4,
                      clip=80.0, equity=1000.0)
    assert r2["mean_pct"] > 0 and r2["lower_bound_pct"] == 0.0, r2
    assert r2["verdict"] == "UNPROVEN", r2
    assert "ceiling_usd_per_day" not in r2, "a coin flip was given a ceiling"

    # an unproven book gets DECIDABILITY, and filling its slots is the speed-up
    r3 = book_ceiling(closes=[0.01, -0.008] * 12, span_days=24,
                      concurrency=1.0, cap=5, clip=50.0, equity=1000.0)
    assert r3["verdict"] == "UNPROVEN" and r3["closes_to_t2"], r3
    assert r3["days_to_t2_at_full_slots"] < r3["days_to_t2_now"], r3
    assert "DECIDABILITY" in r3["binding"] and "5.0x" in r3["binding"], r3

    # a book already at cap is told slots are NOT the answer
    r4 = book_ceiling(closes=[0.01, -0.008] * 12, span_days=24,
                      concurrency=5.0, cap=5, clip=50.0, equity=1000.0)
    assert "slots are NOT the answer" in r4["binding"], r4["binding"]

    # a NEGATIVE mean is a keep-or-retire question, never a capacity one —
    # this instrument must never suggest scaling a loser
    r5 = book_ceiling(closes=[-0.01] * 30, span_days=30, concurrency=1.0,
                      cap=10, clip=80.0, equity=1000.0)
    assert r5["verdict"] == "UNPROVEN" and r5["closes_to_t2"] is None, r5
    assert "keep-or-retire" in r5["binding"], r5["binding"]

    # RATE headroom comes from unused SLOTS, never from a shorter hold: two
    # books with the same slots and different holds get the SAME rate headroom
    a1 = book_ceiling(closes=good, span_days=40, concurrency=2.0, cap=4,
                      clip=80.0, equity=1000.0, maxdd=0.03)
    a2 = book_ceiling(closes=[0.02] * 200, span_days=40, concurrency=2.0,
                      cap=4, clip=80.0, equity=1000.0, maxdd=0.03)
    assert a1["rate_headroom_x"] == a2["rate_headroom_x"] == 2.0, (a1, a2)

    # the drawdown bar binds the clip: a book already at 15% gets NO size room
    r6 = book_ceiling(closes=good, span_days=40, concurrency=4.0, cap=4,
                      clip=80.0, equity=1000.0, maxdd=MAXDD_BAR)
    assert r6["size_headroom_x"] == 1.0 and r6["headroom_x"] == 1.0, r6
    assert "AT ITS CEILING" in r6["binding"], r6["binding"]

    # too thin says so rather than inventing a number
    assert book_ceiling(closes=[0.01] * 4, span_days=4, concurrency=1.0,
                        cap=4, clip=80.0, equity=1000.0)["verdict"] == "TOO-THIN"

    # the design renderer names the book, its ceiling AND its floor — a
    # ceiling printed without the floor beside it is how "go higher" becomes
    # reckless, which is the whole reason the manifest carries both
    demo = {"perps-funding-carry-lshadow": {"verdict": "PROVEN",
                                            "binding": "SLOTS"}}
    txt = render_designs(demo, [{"bot": "perps-funding-carry-lshadow",
                                 "extra": {}}])
    assert "is for" in txt and "flies when" in txt and "never" in txt, txt
    assert "🌾" in txt and "SLOTS" in txt, txt
    # a book with no declared design SAYS SO rather than being skipped
    gap = render_designs({"mystery-book": {"verdict": "PROVEN"}},
                         [{"bot": "mystery-book", "extra": {}}])
    assert "NO DECLARED DESIGN" in gap, gap

    assert closes_for_t([0.01] * 10) is None      # sd == 0
    assert closes_for_t([-0.01, -0.02]) is None   # mean <= 0
    print("ceiling selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
