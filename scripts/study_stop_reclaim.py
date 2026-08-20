#!/usr/bin/env python3
"""Which of this fleet's stops are firing on NOISE? — the offense-side exit study.

WHY THIS EXISTS. On 2026-07-13 the family book's counter-trend stop was widened
2.0x -> 3.5x ATR on one measurement: *"the 2.0x stop fired on noise, 77-89% of
stop-outs reclaimed entry within 24h"*. That was a real win-more move, and it
was applied to exactly TWO tags (`bounce_pullback`, `range_meanrev`) and never
asked of any other stop in the fleet. Meanwhile the live ledger says stops are
where the money goes:

    freqtrade-georgia  long-trend-breakout_trailing_stop_loss  n=66  -$17.11
                       long-trend-breakout_roi                 n=35  +$26.67
    ticket-taker       long-breakoutup_trail                   n=18   -$9.59
                       long-breakoutup_hold                    n=27  +$23.77
    ticket-taker       short-divergence_sl                     n=43  -$63.47
                       short-divergence_tp                     n=74  +$49.65

Each of those pairs is the SAME entry signal graded by two different exits, and
in every pair the stop is the negative half. That does not prove the stop is too
tight — a stop is supposed to lose money; it is insurance. It proves the
question is worth asking, per book and per tag, against the venue's own tape.

WHAT IT MEASURES. For every stop-shaped exit in a book's ledger:

    RECLAIM   — did price come back through the trade's ENTRY, in the trade's
                own direction, within H hours of the exit? (the July test)
    REGRET    — the return the position would have shown at H hours had it not
                been stopped, in the trade's direction, net of nothing (a
                gross number, deliberately: friction is already paid at the
                stop, so this is the marginal question "hold or fold").

AND THE CONTROL GROUP (I6 — an absence, or a presence, is evidence only against
a population). A reclaim rate means nothing on its own: on a volatile tape some
fraction of ANY level is revisited for free. So every stop-out is paired with
`--placebo` random start points drawn from the same coin over the same window,
asked for the SAME move over the SAME horizon. The finding is the EXCESS, and a
stop whose reclaim rate does not beat its own placebo is doing its job.

WHAT IT REFUSES TO DO. It recommends no value. A high reclaim rate says "this
stop fires on noise", which is a direction, not a number — the number comes from
`study_exit_sweep.py`, which replays the whole rule with throughput modelled.
Trades whose candles cannot be fetched are EXCLUDED and COUNTED in the output
(a silently shrunken sample is how a study lies); a symbol with no coverage at
all is named. Fail-closed: no candles, no claim.

    python3 scripts/study_stop_reclaim.py --bot freqtrade-georgia-lshadow
    python3 scripts/study_stop_reclaim.py --all --hours 24 --placebo 40
    python3 scripts/study_stop_reclaim.py --selftest
"""
import argparse
import json
import os
import random
import statistics
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)
sys.path.insert(0, os.path.dirname(HERE))

LIGHTER = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
DASH = os.environ.get(
    "PNL_DASH",
    "https://pnl-dashboard-production-858c.up.railway.app")

#: An exit is stop-shaped if its reason ends in one of these. Deliberately a
#: SUFFIX match on the reason's last token: the fleet tags closes
#: `<side>-<lens>_<exit>`, so a substring scan would catch `long-stoploss-test`
#: and miss nothing useful in exchange.
STOP_KINDS = ("sl", "stop", "stop_loss", "trailing_stop_loss", "trail",
              "ghoststop", "hard_stop", "catastrophic_stop")


def _get(path, **params):
    url = f"{LIGHTER}{path}?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url, timeout=30) as r:
        return json.loads(r.read().decode())


def market_ids():
    try:
        rows = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    except Exception as e:                                       # noqa: BLE001
        print(f"market_ids failed: {type(e).__name__}: {e}", file=sys.stderr)
        return {}
    return {str(r.get("symbol")): r.get("market_id") for r in rows
            if r.get("symbol") is not None and r.get("market_id") is not None}


def fetch_candles(market_id, start_ts, end_ts):
    """Hourly OHLC over [start, end] -> {hour_ts: (o, h, l, c)}.

    Paged backward at the venue's 500-bar cap — the shape
    `study_exit_sweep.fetch_candles` already proves against this API.
    """
    out, end = {}, int(end_ts)
    seen_oldest = None
    while end > start_ts:
        try:
            cs = _get("/api/v1/candles", market_id=market_id, resolution="1h",
                      start_timestamp=max(int(start_ts), end - 500 * 3600),
                      end_timestamp=end, count_back=500).get("c") or []
        except Exception:                                        # noqa: BLE001
            break
        if not cs:
            break
        for c in cs:
            try:
                out[int(c["t"]) // 1000] = (float(c["o"]), float(c["h"]),
                                            float(c["l"]), float(c["c"]))
            except (KeyError, TypeError, ValueError):
                continue
        oldest = min(int(c["t"]) // 1000 for c in cs)
        if oldest <= start_ts or (seen_oldest is not None
                                  and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if start_ts <= t <= end_ts}


# --------------------------------------------------------------- the measure

def is_stop(reason):
    """True when this exit is a stop rather than a target or a clock."""
    tail = str(reason or "").rsplit("_", 1)[-1].lower()
    whole = str(reason or "").lower()
    return tail in STOP_KINDS or any(
        whole.endswith("_" + k) for k in STOP_KINDS)


def reached(path, need_frac, is_long, ref_px):
    """Did the path move `need_frac` (a positive fraction) in the trade's
    direction away from `ref_px`? Uses the bar EXTREME, so this is the most
    generous reading available to the hold-instead-of-stop case — a finding
    that survives a generous test is worth more than one that needs a kind one.
    """
    if not path or ref_px <= 0 or need_frac is None:
        return None
    if is_long:
        target = ref_px * (1.0 + need_frac)
        return any(h >= target for _o, h, _l, _c in path)
    target = ref_px * (1.0 - need_frac)
    return any(l <= target for _o, _h, l, _c in path)


def excursion(path, is_long, ref_px):
    """Signed best-case return over the path, in the trade's direction."""
    if not path or ref_px <= 0:
        return None
    if is_long:
        return max(h for _o, h, _l, _c in path) / ref_px - 1.0
    return 1.0 - min(l for _o, _h, l, _c in path) / ref_px


def close_at(path, is_long, ref_px):
    """Return in the trade's direction at the END of the horizon — the honest
    'you held' number, as against `excursion`'s perfect-timing one."""
    if not path or ref_px <= 0:
        return None
    last = path[-1][3]
    return (last / ref_px - 1.0) if is_long else (1.0 - last / ref_px)


def window(candles, t0, hours):
    lo, hi = int(t0), int(t0) + int(hours) * 3600
    return [candles[t] for t in sorted(candles) if lo < t <= hi]


def ts(s):
    if not s:
        return None
    s = str(s)
    if " " in s and "T" not in s:
        s = s.replace(" UTC", "+00:00").replace(" ", "T", 1)
    try:
        d = datetime.fromisoformat(s)
    except ValueError:
        return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp()


def study(rows, candles_by_sym, hours=24, placebo=40, seed=7):
    """-> {(tag, reason): stats}. `rows` are one book's stop-shaped closes."""
    rnd = random.Random(seed)
    out = {}
    for r in rows:
        sym = str(r.get("pair") or "").split("/")[0].split("-")[0]
        cs = candles_by_sym.get(sym) or {}
        ent, ex = r.get("entry_price"), r.get("exit_price")
        t_ex = ts(r.get("closed_at"))
        is_long = str(r.get("side") or "long").lower() != "short"
        key = (r.get("_tag") or "-", r.get("reason") or "?")
        s = out.setdefault(key, {"n": 0, "excluded": 0, "reclaim": 0,
                                 "regret": [], "held": [], "usd": 0.0,
                                 "placebo_hits": 0, "placebo_n": 0})
        s["usd"] += float(r.get("pnl_abs") or 0.0)
        if not (cs and ent and ex and t_ex) or ent <= 0 or ex <= 0:
            s["excluded"] += 1
            continue
        path = window(cs, t_ex, hours)
        if not path:
            s["excluded"] += 1
            continue
        s["n"] += 1
        # how far back to the entry, as a positive fraction of the exit price
        need = (ent / ex - 1.0) if is_long else (1.0 - ent / ex)
        if reached(path, max(need, 0.0), is_long, ex):
            s["reclaim"] += 1
        e = excursion(path, is_long, ex)
        h = close_at(path, is_long, ex)
        if e is not None:
            s["regret"].append(e)
        if h is not None:
            s["held"].append(h)
        # ---- placebo: the same move, same horizon, random start, same coin
        if placebo and need > 0:
            times = sorted(cs)
            if len(times) > hours + 2:
                for _ in range(placebo):
                    t0 = times[rnd.randrange(0, len(times) - int(hours) - 1)]
                    ppath = window(cs, t0, hours)
                    if not ppath:
                        continue
                    ref = cs[t0][3]
                    s["placebo_n"] += 1
                    if reached(ppath, need, is_long, ref):
                        s["placebo_hits"] += 1
    return out


def render(bot, res, hours):
    keys = sorted(res, key=lambda k: res[k]["usd"])
    if not keys:
        return False
    print(f"\n{'=' * 96}\n{bot}   stop-shaped exits, {hours}h horizon, "
          f"Lighter's own hourly candles")
    print(f"  {'tag / exit':<44}{'n':>4}{'usd':>9}{'reclaim':>9}"
          f"{'placebo':>9}{'excess':>8}{'regret':>9}{'held':>9}{'excl':>6}")
    for k in keys:
        s = res[k]
        if not s["n"]:
            print(f"  {(k[0] + ' / ' + k[1])[:43]:<44}{0:>4}{s['usd']:>9.2f}"
                  f"{'—':>9}{'—':>9}{'—':>8}{'—':>9}{'—':>9}"
                  f"{s['excluded']:>6}")
            continue
        rc = s["reclaim"] / s["n"]
        pb = (s["placebo_hits"] / s["placebo_n"]) if s["placebo_n"] else None
        reg = statistics.fmean(s["regret"]) if s["regret"] else None
        hld = statistics.fmean(s["held"]) if s["held"] else None
        print(f"  {(k[0] + ' / ' + k[1])[:43]:<44}{s['n']:>4}{s['usd']:>9.2f}"
              f"{rc * 100:>8.0f}%"
              f"{(f'{pb * 100:.0f}%' if pb is not None else '—'):>9}"
              f"{(f'{(rc - pb) * 100:+.0f}pp' if pb is not None else '—'):>8}"
              f"{(f'{reg * 100:+.2f}%' if reg is not None else '—'):>9}"
              f"{(f'{hld * 100:+.2f}%' if hld is not None else '—'):>9}"
              f"{s['excluded']:>6}")
    return True


# ------------------------------------------------------------------- loading

def load_ledger(limit=5000):
    url = f"{DASH}/trades.json?source=paper&limit={int(limit)}"
    with urllib.request.urlopen(url, timeout=180) as r:
        return json.loads(r.read().decode()).get("trades") or []


def tag_of(reason):
    """`long-trend-breakout_trailing_stop_loss` -> `long-trend-breakout`."""
    s = str(reason or "")
    for k in sorted(STOP_KINDS, key=len, reverse=True):
        if s.endswith("_" + k):
            return s[: -len(k) - 1] or "-"
    return s.rsplit("_", 1)[0] if "_" in s else "-"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", action="append", default=[])
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--placebo", type=int, default=40)
    ap.add_argument("--min-n", type=int, default=3)
    ap.add_argument("--limit", type=int, default=5000)
    ap.add_argument("--ledger", default=None, help="local trades.json instead")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()

    rows = (json.load(open(a.ledger))["trades"] if a.ledger
            else load_ledger(a.limit))
    stops = [r for r in rows if is_stop(r.get("reason"))]
    for r in stops:
        r["_tag"] = tag_of(r.get("reason"))
    wanted = set(a.bot)
    books = {}
    for r in stops:
        books.setdefault(r["bot"], []).append(r)
    if not a.all:
        books = {b: v for b, v in books.items() if b in wanted}
    books = {b: v for b, v in books.items() if len(v) >= a.min_n}
    if not books:
        print("no book matched (try --all, or lower --min-n)", file=sys.stderr)
        return 1

    syms, lo, hi = set(), None, None
    for v in books.values():
        for r in v:
            syms.add(str(r.get("pair") or "").split("/")[0].split("-")[0])
            t = ts(r.get("closed_at"))
            if t:
                lo = t if lo is None else min(lo, t)
                hi = t if hi is None else max(hi, t)
    ids = market_ids()
    candles, missing = {}, []
    for s in sorted(syms):
        mid = ids.get(s)
        if mid is None:
            missing.append(s)
            continue
        c = fetch_candles(mid, int(lo) - 3600, int(hi) + a.hours * 3600 + 3600)
        if c:
            candles[s] = c
        else:
            missing.append(s)
    if missing:
        print(f"no candles for {len(missing)} symbol(s): "
              f"{', '.join(missing[:14])}", file=sys.stderr)

    for bot in sorted(books):
        render(bot, study(books[bot], candles, a.hours, a.placebo), a.hours)
    print(f"\nreclaim = price came back through the ENTRY within {a.hours}h of "
          f"the stop.\nplacebo = the same move, same horizon, random start in "
          f"the same coin (I6 control).\nregret  = best-case return in the "
          f"trade's direction after the stop; held = at +{a.hours}h.\n"
          f"A stop whose reclaim does NOT beat its placebo is doing its job.")
    return 0


def selftest():
    # a synthetic V: price falls to the stop then recovers straight through
    cs = {}
    for i in range(48):
        px = 100.0 - i if i < 10 else 90.0 + (i - 10)
        cs[1_800_000_000 + i * 3600] = (px, px + 0.5, px - 0.5, px)
    row = {"bot": "b", "pair": "X/USDC", "side": "long", "entry_price": 100.0,
           "exit_price": 90.0, "pnl_abs": -10.0, "reason": "long-t_sl",
           "closed_at": datetime.fromtimestamp(1_800_000_000 + 10 * 3600,
                                               timezone.utc).isoformat(),
           "_tag": "long-t"}
    r = study([row], {"X": cs}, hours=24, placebo=0)
    s = r[("long-t", "long-t_sl")]
    assert s["n"] == 1 and s["excluded"] == 0, s
    assert s["reclaim"] == 1, "a V-shaped recovery through entry must reclaim"
    assert s["regret"] and s["regret"][0] > 0.1, s["regret"]

    # a stop that keeps falling must NOT reclaim
    down = {1_800_000_000 + i * 3600: (100.0 - i, 100.0 - i + .2,
                                       100.0 - i - .2, 100.0 - i)
            for i in range(48)}
    row2 = dict(row, exit_price=95.0,
                closed_at=datetime.fromtimestamp(1_800_000_000 + 5 * 3600,
                                                 timezone.utc).isoformat())
    s2 = study([row2], {"X": down}, hours=24, placebo=0)[("long-t", "long-t_sl")]
    assert s2["reclaim"] == 0, "a one-way tape must not report a reclaim"
    assert s2["held"][0] < 0, s2["held"]

    # a SHORT is measured in its own direction
    row3 = {"bot": "b", "pair": "X/USDC", "side": "short", "entry_price": 90.0,
            "exit_price": 95.0, "pnl_abs": -5.0, "reason": "short-t_sl",
            "closed_at": datetime.fromtimestamp(1_800_000_000 + 5 * 3600,
                                                timezone.utc).isoformat(),
            "_tag": "short-t"}
    s3 = study([row3], {"X": down}, hours=24, placebo=0)[("short-t", "short-t_sl")]
    assert s3["reclaim"] == 1, "a short stopped into a falling tape reclaims"

    # an unfetchable coin is EXCLUDED and COUNTED, never silently dropped
    s4 = study([dict(row, pair="NOPE/USDC")], {}, hours=24, placebo=0)
    assert s4[("long-t", "long-t_sl")] == {
        "n": 0, "excluded": 1, "reclaim": 0, "regret": [], "held": [],
        "usd": -10.0, "placebo_hits": 0, "placebo_n": 0}, s4

    # the classifier: targets and clocks are NOT stops
    for good in ("long-t_sl", "short-divergence_sl", "x_trailing_stop_loss",
                 "long-breakoutup_trail", "long-snap_ghoststop", "y_stop"):
        assert is_stop(good), good
    for bad in ("short-divergence_tp", "long-breakoutup_hold", "roi",
                "short_decay_paid", "long_flip", "x_max_hold",
                "short-navband_converged", "long_rebalance"):
        assert not is_stop(bad), bad
    assert tag_of("long-trend-breakout_trailing_stop_loss") == \
        "long-trend-breakout", tag_of("long-trend-breakout_trailing_stop_loss")
    assert tag_of("short-divergence_sl") == "short-divergence"
    print("study_stop_reclaim selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
