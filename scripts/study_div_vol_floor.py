#!/usr/bin/env python3
"""
scripts/study_div_vol_floor.py — evidence table for TT_DIV_VOL_M, a proposed
24h-volume floor ($M) on lighter_ticket_taker.incredible()'s DIVERGENCE
branch. (21 Jul 2026, pre-review.) Divergence is the only conviction bar with
NO liquidity check (breakout requires vol_m>=1.0, momentum >=2.0).

CONTEXT: a prior verifier REFUTED the naive causal story that thin books
drove the shadow divergence bleed (first-half positive / second-half
negative over 37 closes) — the claim failed its counterfactual. This study
is the repair: measure, per candidate floor, what the ledger would have
netted WITHOUT the excluded closes, on the full window AND both halves.

METHOD (fill-ledger counterfactual — Lighter's own tape, venue-pure):
  * Ledger: /trades.json?source=paper&limit=5000 (endpoint caps at 5000;
    1,671 rows on 21-Jul = the WHOLE paper_trades ledger, verified). Take
    all lighter-ticket-taker-lshadow closes whose reason contains
    "divergence" (closes are tagged `<side>-divergence_<exit>`).
  * vol_m at OPEN time: /bus.json?hours=168 history, key `lighter-market`
    (the scout's ~5-min snapshots; history payloads carry `tickets` with
    per-symbol `vol_m`, plus `funding_extremes`/`prem_outliers` with
    `vol_m`; `marks` is NOT in history payloads — current-snapshot only).
    For each close: nearest snapshot AT-OR-BEFORE opened_at (forward
    fallback within tolerance 30 min), symbol looked up in tickets (any
    lens — vol_m is a property of the BOOK, identical across lenses) then
    the vol_m-bearing sections. Unresolvable closes are COUNTED and KEPT
    (a floor never excludes a close it can't price — conservative).
  * Halves: fixed on the UNFILTERED divergence ledger, chronological by
    closed_at, H1 = first floor(n/2). Floors are then applied INSIDE each
    half — the both-halves rule (same bar the scout tuner uses).
  * Floors {0.0, 0.25, 0.5, 1.0, 2.0}: recompute net P&L, WR, n kept /
    n excluded per cell. Support bar for SHIPPING an enabled floor:
    filtered net STRICTLY BETTER than baseline in BOTH halves.
  * Same table for the LIVE taker (lighter-ticket-taker-lighter), n=5,
    INFORMATIONAL ONLY — n=5 supports nothing.

VERDICT (21 Jul 2026; 37 shadow closes opened 15→20 Jul; 42/42 vol
lookups resolved from the at-or-before divergence-ticket snapshot,
median gap ~1 min):
  NO FLOOR IMPROVES BOTH HALVES — there is NO supported enable value for
  TT_DIV_VOL_M on this tape. If the knob ships at all, it ships DISABLED
  (default 0.0).
  * EVERY candidate floor degrades H1, because H1's thin prints were net
    WINNERS (excluded-set sums: <0.25 +1.86, <0.5 +3.57, <1.0 +1.71,
    <2.0 +4.80).
  * 0.25 hurts BOTH halves (dH1 -1.86, dH2 -1.14 — H2's thinnest prints
    include winners MRVL +3.36 @ $0.12M and USELESS +0.98 @ $0.10M).
  * 0.5/1.0/2.0 help ONLY H2 (dH2 +3.89 / +9.82 / +8.70). The seductive
    cell is 1.0: full-window +10.32 vs +2.21 baseline, WR 62% vs 49% —
    but dH1 is -1.71, so it is a single-half effect: exactly the shape
    the both-halves rule exists to reject, and the same thin-books story
    the verifier already refuted, now wearing a threshold.
  * Mechanism check CONFIRMS the refutation: thin-print P&L flips sign
    between halves (H1 thin = net positive, H2 thin = net negative), so
    volume is not a stable loss predictor here. The H2 bleed at <1.0 is
    a handful of symbol episodes (SOXL -2.39/-2.57, NBIS -2.17/-1.41,
    BOT -2.37/-1.44, SNDK -2.70, MSTR -3.23) interleaved with thin
    winners in the SAME half.
  * LIVE arm n=5 (informational only): baseline +0.50; floors would have
    excluded 1-4 of 5 closes; n=5 supports nothing either way.
  Per repo convention this header already REJECTS enabling TT_DIV_VOL_M
  at ANY of {0.25, 0.5, 1.0, 2.0} on the 15→20 Jul window — do not
  re-test that window. Re-run only once the divergence ledger has
  materially grown (say n>=60 closes) so new closes dominate the table.

LIMITATIONS (state them, don't bury them):
  * n=37, ~5 trading days, ONE venue regime. Serial correlation is heavy:
    15 unique symbols; NBIS 8, 1000BONK 6, SOXL 5, SNDK 4 closes — the
    "both halves" are not 37 independent draws, more like ~15 episodes.
    Several closes share a day and a symbol; treat every delta as
    episode-level, not trade-level, evidence.
  * vol_m at open comes from the scout's ~5-min snapshot cadence, not the
    exchange at fill time; the taker may have consumed the adjacent
    emission. All 42 lookups resolved from tickets.divergence at the
    at-or-before snapshot (median gap 1.0 min shadow / 1.8 min live).
  * The 168h bus history window only just covers this ledger. A re-run
    weeks later MUST pass a saved bus dump via --bus, or older opens fall
    off the history and are counted unresolvable (and conservatively
    KEPT at every floor — stated in the output, never silent).
  * H1/H2 baseline sums here (+8.49/-6.29) differ slightly from the
    verifier's quoted +7.37/-5.16: same n=37, but the ledger rolled
    between snapshots. The shape (H1 positive, H2 negative) is unchanged.

Usage:
  python3 scripts/study_div_vol_floor.py                    # live endpoints
  python3 scripts/study_div_vol_floor.py --trades paper.json --bus bus168.json
"""
import argparse
import bisect
import json
import sys
import urllib.request
from datetime import datetime, timezone

DASH = "https://pnl-dashboard-production-858c.up.railway.app"
TRADES_URL = DASH + "/trades.json?source=paper&limit=5000"
BUS_URL = DASH + "/bus.json?hours=168"

FLOORS = (0.0, 0.25, 0.5, 1.0, 2.0)
SHADOW_BOT = "lighter-ticket-taker-lshadow"
LIVE_BOT = "lighter-ticket-taker-lighter"
TOL_MIN = 30.0          # max snapshot->open gap accepted for a vol lookup
# vol_m-bearing sections of a lighter-market history payload, in preference
# order after the tickets themselves.
VOL_SECTIONS = ("funding_extremes", "prem_outliers", "vol_surges", "oi_moves")
LENSES = ("divergence", "breakout", "momentum", "dip")


def load(src):
    """Load JSON from a local path or an http(s) URL."""
    if src.startswith("http://") or src.startswith("https://"):
        with urllib.request.urlopen(src, timeout=60) as r:
            return json.load(r)
    with open(src) as f:
        return json.load(f)


def pt(ts):
    """Parse the ledger's two timestamp shapes to aware-UTC."""
    ts = ts.replace(" UTC", "+00:00")
    if " " in ts:
        ts = ts.replace(" ", "T")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def snapshots(bus):
    """(ts, payload) list for every lighter-market history entry, sorted."""
    out = [(pt(h["ts"]), h["payload"]) for h in bus.get("history", [])
           if h.get("key") == "lighter-market" and h.get("payload")]
    out.sort(key=lambda p: p[0])
    return out


def vol_at_open(snaps, stimes, sym, t_open, tol_min=TOL_MIN):
    """24h volume ($M) for sym at t_open from the nearest usable snapshot.

    Prefers the at-or-before snapshot, walking outward (before, then after)
    up to tol_min. Within a snapshot, any ticket or vol_m-bearing section
    row for the symbol serves — vol_m is a property of the book, not the
    lens. Returns (vol_m, source, gap_minutes) or (None, None, None).
    """
    i = bisect.bisect_right(stimes, t_open) - 1
    order = []
    for k in range(0, 8):           # 0, -1, +1, -2, +2, ... around i
        for j in (i - k, i + k) if k else (i,):
            if 0 <= j < len(snaps) and j not in order:
                order.append(j)
    for j in order:
        ts, p = snaps[j]
        gap = abs((ts - t_open).total_seconds()) / 60.0
        if gap > tol_min:
            continue
        tk = p.get("tickets") or {}
        for lens in LENSES:
            for t in (tk.get(lens) or []):
                if t.get("sym") == sym and t.get("vol_m") is not None:
                    return float(t["vol_m"]), "tickets." + lens, gap
        for sec in VOL_SECTIONS:
            for t in (p.get(sec) or []):
                if t.get("sym") == sym and t.get("vol_m") is not None:
                    return float(t["vol_m"]), sec, gap
    return None, None, None


def div_closes(trades, bot):
    rows = [t for t in trades
            if t.get("bot") == bot and "divergence" in (t.get("reason") or "")]
    rows.sort(key=lambda t: pt(t["closed_at"]))
    return rows


def annotate(rows, snaps, stimes):
    """Attach vol_m-at-open to each close. Returns (rows, n_unresolved)."""
    n_miss = 0
    for t in rows:
        sym = t["pair"].split("/")[0]
        vol, src, gap = vol_at_open(snaps, stimes, sym, pt(t["opened_at"]))
        t["_sym"], t["_vol"], t["_vsrc"], t["_vgap"] = sym, vol, src, gap
        if vol is None:
            n_miss += 1
    return rows, n_miss


def stats(rows):
    n = len(rows)
    pnl = sum(t["pnl_abs"] for t in rows)
    wins = sum(1 for t in rows if t["pnl_abs"] > 0)
    wr = (wins / n) if n else float("nan")
    return n, pnl, wr


def floor_table(rows, label):
    """Markdown evidence table for one bot's divergence closes."""
    n_all = len(rows)
    h1, h2 = rows[:n_all // 2], rows[n_all // 2:]

    def kept(sub, floor):
        # unresolved vol (None) is KEPT at every floor — conservative
        return [t for t in sub if t["_vol"] is None or t["_vol"] >= floor]

    lines = []
    lines.append("### %s — %d divergence closes "
                 "(H1=first %d, H2=last %d, by close time)"
                 % (label, n_all, len(h1), len(h2)))
    lines.append("")
    lines.append("| floor $M | n kept | n excl | net P&L | WR | "
                 "H1 n | H1 P&L | dH1 | H2 n | H2 P&L | dH2 | both halves? |")
    lines.append("|---|---|---|---|---|---|---|---|---|---|---|---|")
    _, base1, _ = stats(h1)
    _, base2, _ = stats(h2)
    supported = []
    for f in FLOORS:
        ka, k1, k2 = kept(rows, f), kept(h1, f), kept(h2, f)
        na, pa, wa = stats(ka)
        n1, p1, _ = stats(k1)
        n2, p2, _ = stats(k2)
        d1, d2 = p1 - base1, p2 - base2
        both = (f > 0) and (d1 > 0) and (d2 > 0)
        if both:
            supported.append(f)
        lines.append(
            "| %.2f | %d | %d | %+0.2f | %s | %d | %+0.2f | %+0.2f | "
            "%d | %+0.2f | %+0.2f | %s |"
            % (f, na, n_all - na, pa,
               ("%.0f%%" % (100 * wa)) if na else "-",
               n1, p1, d1, n2, p2, d2,
               "YES" if both else ("baseline" if f == 0 else "no")))
    lines.append("")
    return "\n".join(lines), supported


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[1])
    ap.add_argument("--trades", default=TRADES_URL,
                    help="paper ledger JSON (path or URL)")
    ap.add_argument("--bus", default=BUS_URL,
                    help="bus history JSON with lighter-market snapshots")
    args = ap.parse_args()

    trades_doc = load(args.trades)
    trades = trades_doc["trades"] if isinstance(trades_doc, dict) else trades_doc
    bus = load(args.bus)
    snaps = snapshots(bus)
    if not snaps:
        sys.exit("no lighter-market history in the bus payload — pass a "
                 "--bus dump that covers the ledger's open times")
    stimes = [s[0] for s in snaps]
    print("ledger rows: %d   lighter-market snapshots: %d  (%s -> %s)"
          % (len(trades), len(snaps),
             stimes[0].strftime("%m-%d %H:%M"),
             stimes[-1].strftime("%m-%d %H:%M")))
    print()

    verdicts = {}
    for bot, label, informational in (
            (SHADOW_BOT, "SHADOW " + SHADOW_BOT, False),
            (LIVE_BOT, "LIVE %s (INFORMATIONAL ONLY)" % LIVE_BOT, True)):
        rows = div_closes(trades, bot)
        if not rows:
            print("### %s — no divergence closes in the ledger\n" % label)
            continue
        rows, n_miss = annotate(rows, snaps, stimes)
        gaps = sorted(t["_vgap"] for t in rows if t["_vgap"] is not None)
        srcs = {}
        for t in rows:
            if t["_vsrc"]:
                srcs[t["_vsrc"]] = srcs.get(t["_vsrc"], 0) + 1
        tbl, supported = floor_table(rows, label)
        print(tbl)
        print("vol lookups: %d/%d resolved (%d unresolved -> KEPT at every "
              "floor); median snapshot gap %.1f min; sources: %s"
              % (len(rows) - n_miss, len(rows), n_miss,
                 gaps[len(gaps) // 2] if gaps else float("nan"),
                 ", ".join("%s=%d" % kv for kv in sorted(srcs.items()))))
        syms = {}
        for t in rows:
            syms[t["_sym"]] = syms.get(t["_sym"], 0) + 1
        top = sorted(syms.items(), key=lambda kv: -kv[1])[:5]
        print("serial correlation: %d unique symbols / %d closes; top: %s"
              % (len(syms), len(rows),
                 ", ".join("%s x%d" % kv for kv in top)))
        print()
        if not informational:
            verdicts[bot] = supported

    sup = verdicts.get(SHADOW_BOT, [])
    print("=" * 72)
    if sup:
        print("VERDICT: floor(s) %s improve BOTH halves on the shadow ledger."
              % sup)
        print("Cross-check against the header before acting — if the header "
              "already rejected this window, the ledger must have GROWN "
              "since 21-Jul for this to be new evidence.")
    else:
        print("VERDICT: NO floor improves both halves — no supported enable "
              "value for TT_DIV_VOL_M on this tape. Ship the knob disabled "
              "(default 0.0).")
    print("=" * 72)


if __name__ == "__main__":
    main()
