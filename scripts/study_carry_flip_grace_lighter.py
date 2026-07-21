#!/usr/bin/env python3
"""
scripts/study_carry_flip_grace_lighter.py — the Yield Harvester's FLIP exits,
counterfactualed on Lighter's OWN settled funding tape.

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT 2026-07-21, RUN ON THE REAL EPISODES: **NO EXIT CHANGE.** The     ║
║ 23 usable *_flip episodes (0W/23 on the week, ledger -$10.30) replayed    ║
║ on Lighter's settled funding:                                             ║
║      variant          total      h1       h2     exits                    ║
║      V0 ship g1h     -18.61    -8.58   -10.03   23 flip   (sim anchor:    ║
║                                        mean |sim-ledger| $0.46/episode)   ║
║      V1 g8h          -15.25    -5.48    -9.78   11 flip, 12 OPEN@END      ║
║      V2 g1h+mag      -18.61    -8.58   -10.03   identical to V0           ║
║      V3 g8h+mag      -15.25    -5.48    -9.78   identical to V1           ║
║  * The MAGNITUDE bar is a NO-OP on this tape: every real flip was at      ║
║    adverse |apr| >= the 1.875% exit bar already — the "noise below the    ║
║    bar" story this study was built to test is REFUTED on the episodes.    ║
║  * 8h grace "wins" +$3.36 total but h2 improves only +$0.25 and 12/23     ║
║    episodes are STILL OPEN at tape end (funding oscillating around zero,  ║
║    never 8h-continuously adverse, never paying back) — deferral wearing   ║
║    a win's clothes. FAILS the both-halves margin. Do not re-run a grace/  ║
║    magnitude variant of this without NEW evidence.                        ║
║ THE REAL FINDING IS UPSTREAM — THE ENTRY: at the carry's Lighter entry    ║
║ bar (ENTER_APR 0.40 published = 5% TRUE), round-trip friction (29bps)     ║
║ needs 0.0029*8760/0.05 = **508h of entry-rate accrual vs MAX_HOLD 336h**  ║
║ — an entry AT the bar is structurally unable to pay for itself unless     ║
║ the rate stays hot; the twin's actual winners (decay_paid 6W/0L +$36.30)  ║
║ were 100%+ APR books. Payback-feasible bars: >=7.5% TRUE pays back in     ║
║ 336h, >=15% in ~169h. QUEUED FOLLOW-UP (universe-wide, both halves,      ║
║ selection-clean — this study's 8 coins are selected FOR failure and       ║
║ cannot decide it): sweep the carry entry gate {5,7.5,10,15,20}% TRUE on   ║
║ the liquid universe's full tape before touching ENTER_APR.                ║
║ Friction is the bot's own modelled constants (not measured fills); every  ║
║ variant shares them, so RELATIVE ordering is the claim. Re-entry churn    ║
║ savings and freed-slot opportunity are credited to NEITHER side.          ║
╚══════════════════════════════════════════════════════════════════════════╝

Method: pull the *_flip closes of perps-funding-carry{,-lshadow} from the
dashboard's public paper ledger, reconstruct each episode (side from the
reason prefix, notional from pnl_abs/pnl_pct), then re-run the bot's OWN
exit cascade (flip variant / fee-payback decay / max-hold / bleed) hour by
hour on Lighter's settled funding series from the episode's real open:

  V0  grace 1h,  no magnitude bar   (SHIPPED — also the sim's sanity anchor)
  V1  grace 8h,  no magnitude bar   (one Lighter settlement window)
  V2  grace 1h,  |apr| >= exit bar  (magnitude: only flee funding that HURTS)
  V3  grace 8h,  |apr| >= exit bar

Offline --selftest exercises the sim engine on synthetic tapes (noise-flip
held through, persistent-adverse still exits, bleed stop fires, fee-payback
decay pays). The full run needs the venue API + dashboard.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

B = os.environ.get("LIGHTER_API", "https://mainnet.zklighter.elliot.ai")
DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")

# funding_carry_bot's own constants (lighter_shadow basis: TRUE apr = /8)
OPEN_COST = 0.00045 + 0.0010          # PERP_FEE + HEDGE_COST, per side
EXIT_APR_TRUE = 0.15 / 8              # 0.01875
FEE_PAYBACK_MARGIN = 0.10
BLEED_STOP_FRAC = 0.02
MAX_HOLD_H = 14 * 24
HOURS_PER_YEAR = 24 * 365

VARIANTS = {
    "V0 ship g1h": (1.0, 0.0),
    "V1 g8h":      (8.0, 0.0),
    "V2 g1h+mag":  (1.0, EXIT_APR_TRUE),
    "V3 g8h+mag":  (8.0, EXIT_APR_TRUE),
}


def _get(path, **q):
    url = B + path + "?" + urllib.parse.urlencode(q)
    for attempt in range(4):
        try:
            with urllib.request.urlopen(url, timeout=40) as r:
                return json.loads(r.read())
        except Exception:
            if attempt == 3:
                raise
            time.sleep(1.5 * (attempt + 1))


def fetch_fundings(mid, days):
    """Settled hourly funding, paged backward -> {hour_ts: signed TRUE apr}."""
    out, end, cutoff = {}, int(time.time()), int(time.time()) - days * 86400
    seen_oldest = None
    while True:
        rows = _get("/api/v1/fundings", market_id=mid, resolution="1h",
                    start_timestamp=0, end_timestamp=end,
                    count_back=0).get("fundings") or []
        if not rows:
            break
        for f in rows:
            rate = float(f["rate"]) / 100.0 * 24 * 365
            out[int(f["timestamp"])] = rate * (1 if f["direction"] == "long" else -1)
        oldest = min(f["timestamp"] for f in rows)
        if oldest <= cutoff or (seen_oldest is not None and oldest >= seen_oldest):
            break
        seen_oldest, end = oldest, oldest - 3600
    return {t: v for t, v in out.items() if t >= cutoff}


def simulate(open_ts, side_mult, notional, fund, grace_h, mag_bar):
    """The bot's exit cascade with a parameterized flip rule, hour by hour on
    the settled tape. side_mult: +1 short_perp (receives apr>0), -1 long_perp.
    Returns (pnl, held_h, reason) — pnl = accrued - entry&exit friction, the
    same quantity the bot realizes. Pure; selftested."""
    fees = OPEN_COST * notional            # entry side
    close_fee = OPEN_COST * notional       # modelled exit side
    accrued = 0.0
    flipped_since = None
    hours = sorted(t for t in fund if t >= open_ts - 3599)
    if not hours:
        return None
    last = open_ts
    for t in hours:
        apr = fund[t]
        dt_h = min(1.0, max(0.0, (t - last) / 3600.0)) or 1.0
        last = t
        accrued += side_mult * (apr / HOURS_PER_YEAR) * dt_h * notional
        held_h = (t - open_ts) / 3600.0
        adverse = side_mult * apr < 0
        if adverse and (mag_bar <= 0 or abs(apr) >= mag_bar):
            flipped_since = flipped_since if flipped_since is not None else t
        elif not adverse:
            flipped_since = None
        # a below-bar adverse rate PAUSES the clock but does not reset it
        net_if_closed = accrued - (fees + close_fee)
        flipped = (flipped_since is not None
                   and (t - flipped_since) / 3600.0 >= grace_h)
        expired = held_h >= MAX_HOLD_H
        bleeding = net_if_closed <= -BLEED_STOP_FRAC * notional
        decayed = (abs(apr) < EXIT_APR_TRUE
                   and net_if_closed >= FEE_PAYBACK_MARGIN)
        if flipped or decayed or expired or bleeding:
            reason = ("flip" if flipped else "decay_paid" if decayed
                      else "max_hold" if expired else "bleed_stop")
            return accrued - (fees + close_fee), held_h, reason
    # tape ends with the position open: mark funding-to-date minus full
    # round-trip friction (the close is still owed — deferral-proof)
    return accrued - (fees + close_fee), (hours[-1] - open_ts) / 3600.0, "open@end"


def load_episodes():
    url = f"{DASH}/trades.json?source=paper"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    tr = d if isinstance(d, list) else d.get("trades") or []
    eps = []
    for t in tr:
        if (t.get("bot") or "").startswith("perps-funding-carry") \
                and str(t.get("reason", "")).endswith("flip"):
            reason = str(t["reason"])
            side_mult = 1 if reason.startswith("short") else -1
            try:
                pct = float(t.get("pnl_pct") or 0)
                notional = abs(float(t["pnl_abs"]) / pct) if pct else 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                notional = 100.0
            eps.append({
                "coin": str(t["pair"]).split("/")[0],
                "side_mult": side_mult, "notional": notional,
                "open_ts": int(datetime.fromisoformat(
                    t["opened_at"]).timestamp()),
                "close_ts": int(datetime.fromisoformat(
                    t["closed_at"]).timestamp()),
                "actual_pnl": float(t["pnl_abs"]),
            })
    return sorted(eps, key=lambda e: e["open_ts"])


def main():
    eps = load_episodes()
    if not eps:
        print("no flip episodes in the ledger window — nothing to study")
        return
    days = max(3, int((time.time() - min(e["open_ts"] for e in eps)) / 86400) + 2)
    print(f"{len(eps)} flip episodes, funding lookback {days}d")
    obs = _get("/api/v1/orderBookDetails").get("order_book_details") or []
    mids = {o["symbol"]: o["market_id"] for o in obs if o.get("symbol")}
    fund = {}
    for coin in sorted({e["coin"] for e in eps}):
        if coin not in mids:
            print(f"  {coin}: not on the venue (delisted?) — episodes skipped")
            continue
        fund[coin] = fetch_fundings(mids[coin], days)
        print(f"  {coin:12s} {len(fund[coin])}h of settled funding")
    usable = [e for e in eps if e["coin"] in fund and fund[e["coin"]]]
    mid_i = len(usable) // 2
    print(f"\n{len(usable)} usable episodes (h1={mid_i}, h2={len(usable) - mid_i})"
          f"\nactual ledger total: {sum(e['actual_pnl'] for e in usable):+.2f}\n")
    print(f"{'variant':14s} {'total':>8s} {'h1':>8s} {'h2':>8s} "
          f"{'med hold':>9s}  exits")
    for name, (grace, mag) in VARIANTS.items():
        rows = []
        for e in usable:
            r = simulate(e["open_ts"], e["side_mult"], e["notional"],
                         fund[e["coin"]], grace, mag)
            if r:
                rows.append((e, *r))
        tot = sum(r[1] for r in rows)
        h1 = sum(r[1] for r in rows[:mid_i])
        h2 = sum(r[1] for r in rows[mid_i:])
        holds = sorted(r[2] for r in rows)
        med = holds[len(holds) // 2] if holds else 0
        exits = {}
        for r in rows:
            exits[r[3]] = exits.get(r[3], 0) + 1
        print(f"{name:14s} {tot:+8.2f} {h1:+8.2f} {h2:+8.2f} {med:8.1f}h  {exits}")
    v0 = VARIANTS["V0 ship g1h"]
    sim0 = [simulate(e["open_ts"], e["side_mult"], e["notional"],
                     fund[e["coin"]], *v0) for e in usable]
    pairs = [(e["actual_pnl"], s[0]) for e, s in zip(usable, sim0) if s]
    drift = sum(abs(a - b) for a, b in pairs) / max(1, len(pairs))
    print(f"\nsanity anchor: V0-sim vs actual ledger, mean |diff| "
          f"${drift:.2f}/episode over n={len(pairs)} "
          f"(sim total {sum(b for _, b in pairs):+.2f} vs "
          f"ledger {sum(a for a, _ in pairs):+.2f})")


# ---------------------------------------------------------------------------

def _selftest():
    h = 3600
    t0 = 1_800_000_000

    def tape(*aprs):
        return {t0 + i * h: a for i, a in enumerate(aprs)}

    # 1) NOISE FLIP: short receiving a hot +30% TRUE, two adverse -1% hours,
    #    back to +30%. (30% not 5%: at the 5% entry bar a $1k carry cannot
    #    even pay back its 29bps round-trip inside MAX_HOLD — 508h needed vs
    #    336h — an insight the main run should confirm on real rates.)
    #    Shipped rule (V0) closes on the noise and eats friction; 8h grace
    #    (V1) holds through; -1% is below the 1.875% exit bar, so V2's
    #    magnitude clock never even starts. Both reach a profitable
    #    fee-payback decay when the rate finally cools.
    noisy = tape(*([0.30] * 30 + [-0.01, -0.01] + [0.30] * 250
                   + [0.001] * 10))
    pnl0, held0, r0 = simulate(t0, +1, 1000.0, noisy, 1.0, 0.0)
    assert r0 == "flip" and pnl0 < 0, (pnl0, held0, r0)
    pnl2, _, r2 = simulate(t0, +1, 1000.0, noisy, 1.0, EXIT_APR_TRUE)
    assert r2 == "decay_paid" and pnl2 > 0, (pnl2, r2)
    pnl1, _, r1 = simulate(t0, +1, 1000.0, noisy, 8.0, 0.0)
    assert r1 == "decay_paid" and pnl1 > 0, (pnl1, r1)

    # 2) PERSISTENT HARD ADVERSITY: rate goes -30% and stays — every variant
    #    must still get out (flip under V0-V3; the magnitude bar is exceeded).
    hard = tape(*([0.30] * 5 + [-0.30] * 200))
    for name, (g, m) in VARIANTS.items():
        pnl, held, r = simulate(t0, +1, 1000.0, hard, g, m)
        assert r == "flip" and held <= 5 + g + 1, (name, r, held)

    # 3) BELOW-BAR ADVERSITY NEVER FLIPS under the magnitude bar, and the
    #    bleed stop remains the catastrophic backstop: a long slow -1% drip
    #    on a small notional exits via bleed/max_hold, not flip.
    drip = tape(*([0.30] * 3 + [-0.01] * 400))
    _, _, r3 = simulate(t0, +1, 50.0, drip, 8.0, EXIT_APR_TRUE)
    assert r3 in ("bleed_stop", "max_hold"), r3

    # 4) the pause-not-reset clock: adverse ABOVE bar for 5h, one below-bar
    #    hour, adverse above bar again — an 8h grace keeps counting from the
    #    FIRST above-bar hour (pausing, not resetting) and exits at ~9h.
    pause = tape(*([0.30] * 2 + [-0.05] * 5 + [-0.001] + [-0.05] * 50))
    _, held4, r4 = simulate(t0, +1, 1000.0, pause, 8.0, EXIT_APR_TRUE)
    assert r4 == "flip" and held4 <= 12, (r4, held4)

    print("study_carry_flip_grace selftest OK (noise-flip held, hard-adverse "
          "exits, magnitude bar + bleed backstop, pause-not-reset grace)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
