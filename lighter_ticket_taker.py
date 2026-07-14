#!/usr/bin/env python3
"""
lighter_ticket_taker.py — 🎫 Ticket Taker: the scanner's designated trader (SHADOW).

WHAT / WHY (2026-07-14, user ask: "when a scanner finds something incredible,
the bot designated to that particular find absorbs the scanner's findings and
makes a trade")
  Lighter Scout publishes per-strategy TICKETS (breakout / dip / momentum
  lenses over every liquid Lighter book). Until now nothing traded them —
  publish-first doctrine. This bot is the designated consumer: a $1,000
  SHADOW book that takes only the HIGH-CONVICTION subset of each lens (the
  "incredible" bars below), models fills at Lighter's own mark price via
  PaperBroker (fees included), accrues hourly funding drag from the venue's
  funding feed, and exits on TP / SL / max-hold.

  Every close is tagged long_<lens>_<exit> in the durable paper_trades
  ledger, so the LEARNING BRAIN grades each lens on real forward returns
  (bot_learn already ingests that ledger). That closes the loop the user
  asked for: scanner finds -> designated bot trades -> brain learns which
  lens actually has an edge -> only graded lenses ever graduate.

  UNVALIDATED BY DESIGN (like every new shadow book: Perp Sniper, Snap Back):
  the lens rules cannot be backtested — they need forward data, which is
  exactly what this book collects. There is NO live path at all: pure paper
  on public keyless data. Run-once process; run_all.sh loops it every 5 min.
  Broker state + entry metadata persist in bot_state so redeploys continue
  the same equity curve.

Usage:
    python3 lighter_ticket_taker.py            # one management cycle
    python3 lighter_ticket_taker.py --selftest # offline accounting checks
"""
import json
import os
import sys
import urllib.request
from datetime import datetime, timezone

import bot_pnl_store as store
from paper_broker import PaperBroker

BOT_ROW = "lighter-ticket-taker-lshadow"
STATE_KEY = "lighter-ticket-taker"
SCOUT_KEY = "lighter-market"
API_BASE = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")

START_EQUITY = 1000.0
CLIP_USD = float(os.environ.get("TT_CLIP_USD", "50"))
MAX_OPEN = int(os.environ.get("TT_MAX_OPEN", "6"))
TAKE_PROFIT = float(os.environ.get("TT_TP", "0.04"))       # +4%
STOP_LOSS = float(os.environ.get("TT_SL", "-0.03"))        # -3%
MAX_HOLD_H = float(os.environ.get("TT_MAX_HOLD_H", "48"))

# "Incredible" — the conviction bars. A ticket must clear its lens's bar to
# be taken; ordinary tickets stay advisory for the weekly lens grading.
BRK_RANGE = float(os.environ.get("TT_BRK_RANGE", "0.95"))  # at the daily high
BRK_VOL_M = float(os.environ.get("TT_BRK_VOL_M", "1.0"))   # >= $1M/day
DIP_RANGE = float(os.environ.get("TT_DIP_RANGE", "0.05"))  # pinned to the low
MOMO_CHG = float(os.environ.get("TT_MOMO_CHG", "5.0"))     # >= +5% day
MOMO_VOL_M = float(os.environ.get("TT_MOMO_VOL_M", "2.0")) # >= $2M/day


def now():
    return datetime.now(timezone.utc)


def iso(dt):
    return dt.isoformat(timespec="seconds")


def parse_ts(s):
    return datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def _get(path):
    req = urllib.request.Request(API_BASE + path,
                                 headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_marks_and_funding():
    """{sym: mark_price}, {sym: hourly_funding_rate} from the keyless API."""
    obd = _get("/api/v1/orderBookDetails")
    marks = {}
    for b in obd.get("order_book_details") or []:
        try:
            if b.get("status") == "active" and float(b.get("mark_price") or 0) > 0:
                marks[b["symbol"]] = float(b["mark_price"])
        except (TypeError, ValueError):
            continue
    fr = _get("/api/v1/funding-rates")
    funding = {}
    for r in fr.get("funding_rates") or []:
        try:
            if r.get("exchange") == "lighter" and r.get("rate") is not None:
                funding[r["symbol"]] = float(r["rate"])
        except (TypeError, ValueError):
            continue
    return marks, funding


# ---------------------------------------------------------------------------
# PURE DECISION LOGIC (unit-tested offline)
# ---------------------------------------------------------------------------

def incredible(tickets):
    """The high-conviction subset of the scout's tickets, per lens."""
    out = []
    for t in (tickets.get("breakout") or []):
        if t.get("range_pos", 0) >= BRK_RANGE and t.get("vol_m", 0) >= BRK_VOL_M:
            out.append(("breakout", t))
    for t in (tickets.get("dip") or []):
        if t.get("range_pos", 1) <= DIP_RANGE:
            out.append(("dip", t))
    for t in (tickets.get("momentum") or []):
        if t.get("chg_pct", 0) >= MOMO_CHG and t.get("vol_m", 0) >= MOMO_VOL_M:
            out.append(("momentum", t))
    return out


def exit_reason(entry, mark, opened, t_now):
    """tp / sl / hold / None for a long held from `opened`."""
    if not entry or entry <= 0 or not mark or mark <= 0:
        return None
    ret = mark / entry - 1.0
    if ret >= TAKE_PROFIT:
        return "tp"
    if ret <= STOP_LOSS:
        return "sl"
    if (t_now - opened).total_seconds() >= MAX_HOLD_H * 3600:
        return "hold"
    return None


# ---------------------------------------------------------------------------


def main():
    try:
        marks, funding = fetch_marks_and_funding()
    except Exception as e:  # noqa: BLE001 — keyless API down: skip this cycle
        print(f"[ticket-taker] {iso(now())} fetch failed (skipping): {e!r}")
        return

    saved = store.load_state(STATE_KEY) or {}
    broker = PaperBroker(start_equity=START_EQUITY, fee_bps=4.0)
    broker.restore_state(saved.get("broker") or {})
    meta = saved.get("meta") or {}          # sym -> {lens, opened, accrued_to}
    stats = saved.get("stats") or {"closed": 0, "wins": 0, "losses": 0}
    t_now = now()

    # 1) mark + hourly funding drag on held positions (longs pay positive rate)
    for sym in list(broker.pos):
        mark = marks.get(sym)
        if mark:
            broker.mark(sym, mark)
        m = meta.get(sym) or {}
        try:
            last = parse_ts(m.get("accrued_to") or m.get("opened"))
            hours = max(0.0, (t_now - last).total_seconds() / 3600.0)
        except (ValueError, TypeError):
            hours = 0.0
        rate = funding.get(sym)
        if hours > 0 and rate and mark:
            size, _entry = broker.pos[sym]
            drag = abs(size) * mark * rate * hours     # long pays positive rate
            broker.fees += drag
            m["funding_paid"] = round(float(m.get("funding_paid") or 0.0) + drag, 6)
            m["accrued_to"] = iso(t_now)
            meta[sym] = m

    # 2) exits
    for sym in list(broker.pos):
        mark = marks.get(sym)
        m = meta.get(sym) or {}
        try:
            opened = parse_ts(m.get("opened"))
        except (ValueError, TypeError):
            opened = t_now
        reason = exit_reason(broker.pos[sym][1], mark, opened, t_now)
        if not reason:
            continue
        pnl = broker.close(sym, mark)
        drag = float(m.get("funding_paid") or 0.0)
        fees = 2 * CLIP_USD * broker.fee
        net = pnl - drag - fees
        stats["closed"] += 1
        stats["wins" if net > 0 else "losses"] += 1
        lens = m.get("lens") or "ticket"
        store.publish_paper_trade(
            BOT_ROW, trade_id=f"{sym}-{m.get('opened')}",
            pnl_abs=round(net, 4),
            pnl_pct=round(net / CLIP_USD, 6),
            pair=f"{sym}/USDC",
            opened_at=m.get("opened"), closed_at=iso(t_now),
            reason=f"long_{lens}_{reason}")
        print(f"[ticket-taker] {iso(t_now)} CLOSE {sym} ({lens}) {reason} "
              f"pnl {pnl:+.2f} funding -{drag:.3f} net {net:+.2f}")
        meta.pop(sym, None)

    # 3) entries — only from a FRESH scout snapshot, only the incredible subset
    scout = store.load_state(SCOUT_KEY) or {}
    fresh = False
    try:
        age = (t_now - parse_ts(scout.get("updated"))).total_seconds()
        fresh = age <= float(scout.get("ttl_sec") or 900)
    except (ValueError, TypeError):
        fresh = False
    opened_syms, opened_lenses = set(), set()
    if fresh:
        for lens, t in incredible(scout.get("tickets") or {}):
            sym = t.get("sym")
            # one NEW position per lens per cycle; never add to a held symbol
            if (not sym or sym in broker.pos or sym in opened_syms
                    or lens in opened_lenses):
                continue
            if broker.open_count() >= MAX_OPEN:
                break
            mark = marks.get(sym)
            if not mark:
                continue
            broker.open(sym, True, CLIP_USD / mark, mark)
            meta[sym] = {"lens": lens, "opened": iso(t_now),
                         "accrued_to": iso(t_now), "funding_paid": 0.0,
                         "evidence": {k: t.get(k) for k in
                                      ("range_pos", "chg_pct", "vol_m",
                                       "prem_bps", "apr_pct")}}
            opened_syms.add(sym)
            opened_lenses.add(lens)
            print(f"[ticket-taker] {iso(t_now)} OPEN {sym} ({lens}) @ {mark} "
                  f"evidence={meta[sym]['evidence']}")

    # 4) persist + publish
    equity = broker.equity()
    store.save_state(STATE_KEY, {"broker": broker.to_state(), "meta": meta,
                                 "stats": stats})
    store.publish(
        BOT_ROW, status="online",
        equity=round(equity, 2),
        pnl_abs=round(equity - START_EQUITY, 2),
        pnl_pct=round(equity / START_EQUITY - 1.0, 6),
        open_trades=broker.open_count(),
        closed_trades=stats["closed"], wins=stats["wins"], losses=stats["losses"],
        extra={"venue": "lighter_shadow", "strategy": "scout tickets (shadow)",
               "open_pos": [{"pair": f"{s}/USDC",
                             "tag": f"long_{(meta.get(s) or {}).get('lens', 'ticket')}"}
                            for s in broker.pos],
               "scout_fresh": fresh})
    print(f"[ticket-taker] {iso(t_now)} equity {equity:+.2f} "
          f"open {broker.open_count()}/{MAX_OPEN} closed {stats['closed']} "
          f"({stats['wins']}W/{stats['losses']}L) scout_fresh={fresh}")


# ---------------------------------------------------------------------------


def selftest():
    print("Running Ticket Taker offline self-test...\n")
    # conviction bars
    tk = {"breakout": [{"sym": "A", "range_pos": 0.96, "vol_m": 2.0},
                       {"sym": "B", "range_pos": 0.91, "vol_m": 2.0}],   # below bar
          "dip": [{"sym": "C", "range_pos": 0.04},
                  {"sym": "D", "range_pos": 0.08}],                      # below bar
          "momentum": [{"sym": "E", "chg_pct": 6.0, "vol_m": 3.0},
                       {"sym": "F", "chg_pct": 6.0, "vol_m": 1.0}]}      # thin
    picks = incredible(tk)
    assert [(l, t["sym"]) for l, t in picks] == \
        [("breakout", "A"), ("dip", "C"), ("momentum", "E")], picks

    # exit ladder
    t0 = now()
    from datetime import timedelta
    assert exit_reason(100.0, 104.1, t0, t0) == "tp"
    assert exit_reason(100.0, 96.9, t0, t0) == "sl"
    assert exit_reason(100.0, 101.0, t0 - timedelta(hours=49), t0) == "hold"
    assert exit_reason(100.0, 101.0, t0, t0) is None

    # accounting round-trip incl. funding drag
    b = PaperBroker(start_equity=1000.0, fee_bps=4.0)
    b.open("A", True, 0.5, 100.0)           # $50 clip
    b.mark("A", 105.0)
    drag = 0.5 * 105.0 * 0.0001 * 10        # 10h at 1bp/h
    b.fees += drag
    pnl = b.close("A", 105.0)
    assert abs(pnl - 2.5) < 1e-9
    exp = 1000.0 + 2.5 - (0.5*100*0.0004) - (0.5*105*0.0004) - drag
    assert abs(b.equity() - exp) < 1e-9, (b.equity(), exp)

    print("All Ticket Taker self-tests passed (bars, exits, accounting).")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        selftest()
    else:
        main()
