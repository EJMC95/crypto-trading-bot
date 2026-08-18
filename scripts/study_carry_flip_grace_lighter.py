#!/usr/bin/env python3
"""
scripts/study_carry_flip_grace_lighter.py — the Yield Harvester's FLIP exits,
counterfactualed on Lighter's OWN settled funding tape.

╔══════════════════════════════════════════════════════════════════════════╗
║ VERDICT 2026-07-30 (he) — **STILL NO EXIT CHANGE, BUT FOR THE OPPOSITE    ║
║ REASON, AND THE 21-JUL VERDICT BELOW IS RETRACTED AS A SAMPLE.**          ║
║                                                                           ║
║ The 21-Jul run's own text authorised a re-run "with NEW evidence". Three   ║
║ pieces arrived, and two of them are defects in THIS FILE:                  ║
║  1. THE SELECTOR POOLED A RETIRED CROSS-VENUE ARM. `startswith(           ║
║     "perps-funding-carry")` also matches the retired HYPERLIQUID-data     ║
║     arm — 41 closes, **15 of them flips**, 2-Jul..14-Jul — and every one   ║
║     was then replayed against LIGHTER's tape. That is the pool this        ║
║     repo's own rule forbids, and the same prefix hazard as the (gr)        ║
║     near-miss. Now matched EXACTLY (`LIVING_BOOK`).                        ║
║  2. THE LEDGER FETCH WAS TRUNCATED. No `limit`, so it took the            ║
║     endpoint's 500-row default — a few days of a 1,700-row fleet ledger.   ║
║     "23 usable episodes" was bounded by that page, not by the book's       ║
║     history. Measured: 20 episodes at the default vs **46 in-era flips**.  ║
║  3. THE ACCRUAL BASIS CHANGED ON 17-JUL ((hc)). 11 of the flips predate    ║
║     it. The era now comes from `golive_readiness.POLICY_ERA` — one owner.  ║
║                                                                           ║
║ Era-clean, arm-clean, untruncated: **44 usable episodes**, ledger -$15.13. ║
║      variant          total      h1       h2   med hold  exits             ║
║      V0 ship g1h     -35.22   -18.96   -16.26    10.9h   44 flip           ║
║      V1 g8h          -18.90    -9.51    -9.39    71.9h   26 flip, 18 open  ║
║      V2 g1h+mag      -35.23   -18.97   -16.27    10.9h   44 flip           ║
║      V3 g8h+mag      -18.90    -9.51    -9.39    71.9h   25 flip, 19 open  ║
║                                                                           ║
║ ON THE CORRECTED SAMPLE THE 8H GRACE PASSES THE BAR IT WAS REJECTED ON —   ║
║ +$16.32 total and BOTH halves better (-9.51 vs -18.96, -9.39 vs -16.26),   ║
║ where 21-Jul recorded h2 improving by only +$0.25 and called it deferral.  ║
║ **AND IT IS STILL NOT A RECOMMENDATION**, because the replay fails the new ║
║ CALIBRATION GATE: V0-sim totals **-$35.22 against a ledger of -$15.13**,   ║
║ i.e. it overstates the shipped rule's own losses by 2.3x. A variant        ║
║ measured against a baseline that wrong tells you nothing. (gx)'s rule: a   ║
║ harness that cannot reproduce what DID happen may not say what WOULD have. ║
║ This study printed that anchor from day one and NOTHING WAS GATED ON IT —  ║
║ the 21-Jul run's $0.46/episode drift is the SAME figure that fails today.  ║
║                                                                           ║
║ THE MISS IS SYSTEMATIC, NOT NOISE: mean|diff| $0.48 vs |mean diff| $0.46,  ║
║ so the sim is biased, not merely imprecise. One candidate has been tested  ║
║ and REFUTED: the window started at `open_ts - 3599` with a `... or 1.0`    ║
║ dt fallback, booking a FULL hour of funding before the position existed —  ║
║ a real bug, fixed, and it moved the total the WRONG way (-33.58 ->         ║
║ -35.22), so it was not the cause. Remaining candidates: the modelled       ║
║ 29bps round trip is a Hyperliquid taker fee + hedge cost on a venue this   ║
║ repo has MEASURED zero-fee, while the bot charges a MEASURED perp leg;     ║
║ and the sim accrues off SETTLED hourly rates where the bot accrues at the  ║
║ live rate every 5 minutes.                                                 ║
║                                                                           ║
║ HOW TO SETTLE IT, and it is now possible for the first time: (gr) ships    ║
║ `accrued` / `fees` / `held_h` / `entry_apr` / `exit_apr` on every carry     ║
║ close. Once those rows accumulate, friction and accrual can be compared to ║
║ the book's OWN recorded numbers SEPARATELY instead of only through their   ║
║ difference. Do not move FLIP_GRACE_H before that: the flip rule is a live  ║
║ open question, and the blocker is the replay's fidelity, not the sample.   ║
╚══════════════════════════════════════════════════════════════════════════╝

╔══════════════════════════════════════════════════════════════════════════╗
║ SUPERSEDED — VERDICT 2026-07-21, RUN ON THE REAL EPISODES: **NO EXIT      ║
║ CHANGE.** Kept because its REASONING about entry-side payback is still     ║
║ correct and load-bearing; its SAMPLE is retracted per (he) above. The      ║
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
    # [2026-07-30 (he) FIDELITY FIX] This was `t >= open_ts - 3599` with a
    # `... or 1.0` fallback on dt_h, which combined into an accrual for time the
    # position did not exist: for an episode opened at 10:30 the 10:00
    # settlement is in the window, `(t - last)` is NEGATIVE, `max(0.0, ...)` is
    # 0.0, and `0.0 or 1.0` is **1.0** — a FULL hour of funding booked before the
    # open. The settlement a position is actually exposed to is the first one at
    # or after its open, pro-rated from the open, which is what the bot's own
    # continuous live-rate accrual approximates. Measured effect on the 44
    # era-clean episodes: see the calibration line in the run output.
    hours = sorted(t for t in fund if t >= open_ts)
    if not hours:
        return None
    last = open_ts
    for t in hours:
        apr = fund[t]
        dt_h = min(1.0, max(0.0, (t - last) / 3600.0))
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


#: The LIVING arm, named exactly. [2026-07-30 (he)] This was
#: `startswith("perps-funding-carry")`, which also matches the RETIRED
#: Hyperliquid-data arm `perps-funding-carry` — 41 closes, **15 of them flips**,
#: 2-Jul..14-Jul — and every one of those episodes was then replayed against
#: LIGHTER's settled funding tape. That is the cross-venue pool this repo's own
#: rule forbids ("a backtest on another venue's data is not validation of a
#: Lighter bot"), and it is the same prefix hazard as the (gr) near-miss, where
#: a retired arm and its living twin share a name stem.
LIVING_BOOK = "perps-funding-carry-lshadow"


def era_since():
    """The policy-era epoch this book may be studied from, or None.

    ONE OWNER: read off `golive_readiness.POLICY_ERA` rather than retyped, so
    the era the gate grades on and the era a study samples cannot drift apart.
    `CARRY_ERA_SINCE=` (empty) deliberately disables the filter for anyone who
    wants the pooled run back — with the pooling then stated in the output, not
    silent."""
    env = os.environ.get("CARRY_ERA_SINCE")
    if env is not None:
        iso = env.strip()
    else:
        try:
            sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
            import golive_readiness as _g
            iso = (_g.POLICY_ERA.get("perps-funding-carry") or ("", ""))[0]
        except Exception:      # noqa: BLE001
            return None
    if not iso:
        return None
    d = datetime.fromisoformat(iso)
    return (d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp()


#: [2026-07-30 (he)] The ledger fetch was `?source=paper` with NO limit, so it
#: took whatever the endpoint's default page returns (500 rows) — a few days of
#: a 1,700-row fleet ledger. This study therefore sampled "the most recent
#: flips that happened to fit", and its 21-Jul verdict's "23 usable episodes"
#: was bounded by that page, not by the book's history. Measured today: 20
#: episodes at the default against 46 in-era flips in the ledger.
LEDGER_LIMIT = int(os.environ.get("CARRY_STUDY_LIMIT", "5000"))


def load_episodes():
    url = f"{DASH}/trades.json?source=paper&limit={LEDGER_LIMIT}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as r:
        d = json.loads(r.read())
    tr = d if isinstance(d, list) else d.get("trades") or []
    era, dropped_arm, dropped_era = era_since(), 0, 0
    eps = []
    for t in tr:
        bot = t.get("bot") or ""
        if bot != LIVING_BOOK and bot.startswith("perps-funding-carry"):
            if str(t.get("reason", "")).endswith("flip"):
                dropped_arm += 1
            continue
        if bot == LIVING_BOOK and str(t.get("reason", "")).endswith("flip"):
            reason = str(t["reason"])
            side_mult = 1 if reason.startswith("short") else -1
            try:
                pct = float(t.get("pnl_pct") or 0)
                notional = abs(float(t["pnl_abs"]) / pct) if pct else 100.0
            except (TypeError, ValueError, ZeroDivisionError):
                notional = 100.0
            open_ts = int(datetime.fromisoformat(t["opened_at"]).timestamp())
            # Keyed on the OPEN: the accrual basis that produced an episode is
            # the one in force when it was opened, and a straddler accrued in
            # both. Fail-closed, same contract as golive_readiness.in_era.
            if era is not None and open_ts < era:
                dropped_era += 1
                continue
            eps.append({
                "coin": str(t["pair"]).split("/")[0],
                "side_mult": side_mult, "notional": notional,
                "open_ts": open_ts,
                "close_ts": int(datetime.fromisoformat(
                    t["closed_at"]).timestamp()),
                "actual_pnl": float(t["pnl_abs"]),
            })
    # NO SILENT CAPS: say what was excluded and why, or a narrowed sample reads
    # as a smaller venue rather than a deliberate scope.
    if dropped_arm:
        print(f"excluded {dropped_arm} flip episodes from the RETIRED "
              f"Hyperliquid-data arm (cross-venue; would be replayed on "
              f"Lighter's tape)")
    if dropped_era:
        it = datetime.fromtimestamp(era, timezone.utc).date().isoformat()
        print(f"excluded {dropped_era} flip episodes opened before the "
              f"{it} policy era (pre-accrual-fix accounting)")
    return sorted(eps, key=lambda e: e["open_ts"])


#: [2026-07-30 (he)] THE CALIBRATION GATE, borrowed verbatim in spirit from
#: `study_exit_sweep.calibrate` (gx): **a harness that cannot reproduce what DID
#: happen may not say what WOULD have.** This study printed a "sanity anchor"
#: from the start and nothing was ever gated on it — it was a number at the
#: bottom of the output. Today it reads sim −13.61 against a ledger of −0.49 on
#: the same 20 episodes: the shipped-rule replay is wrong by 27x on the total,
#: so the ~$6 the 8h-grace variant appears to "save" is measured against a
#: baseline that does not exist. Two candidate causes, neither established here:
#: the sim charges a full modelled 29bps round trip (a Hyperliquid taker fee
#: plus a hedge cost) on a venue this repo has MEASURED as zero-fee, and it
#: accrues off the SETTLED hourly tape while the bot accrues at the live rate
#: every 5-minute loop — which diverge most on exactly these short hot holds.
#: Fail-CLOSED: beyond tolerance, the variant table still prints (it is the
#: evidence for the miscalibration) but every recommendation is WITHHELD.
CAL_TOL_PER_EP = float(os.environ.get("CARRY_CAL_TOL", "0.25"))   # $/episode
CAL_TOL_TOTAL = float(os.environ.get("CARRY_CAL_TOL_TOTAL", "3.0"))   # $ total


def calibrate(sim_total, ledger_total, n):
    """(ok, why) — may this run make a recommendation at all?

    Two bars because either failure mode alone invalidates a counterfactual: a
    per-episode drift larger than the effect sizes being compared, or a total
    that misses the book. Both are absolute dollars, not ratios — a ratio
    against a near-zero ledger total is undefined exactly when it matters."""
    if n < 5:
        return False, f"only {n} usable episodes — too few to calibrate against"
    per_ep = abs(sim_total - ledger_total) / n
    if per_ep > CAL_TOL_PER_EP:
        return False, (f"mean |sim-ledger| ${per_ep:.2f}/episode > "
                       f"${CAL_TOL_PER_EP:.2f} tolerance")
    if abs(sim_total - ledger_total) > CAL_TOL_TOTAL:
        return False, (f"sim total {sim_total:+.2f} vs ledger "
                       f"{ledger_total:+.2f} — off by "
                       f"${abs(sim_total - ledger_total):.2f} > "
                       f"${CAL_TOL_TOTAL:.2f}")
    return True, f"mean |sim-ledger| ${per_ep:.2f}/episode over n={n}"


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
    sim_tot, led_tot = sum(b for _, b in pairs), sum(a for a, _ in pairs)
    print(f"\nsanity anchor: V0-sim vs actual ledger, mean |diff| "
          f"${drift:.2f}/episode over n={len(pairs)} "
          f"(sim total {sim_tot:+.2f} vs ledger {led_tot:+.2f})")
    ok, why = calibrate(sim_tot, led_tot, len(pairs))
    if ok:
        print(f"CALIBRATED ({why}). The both-halves rule governs: a variant "
              f"must beat V0 on the full window AND both halves before "
              f"FLIP_GRACE_H moves, and friction is the bot's own modelled "
              f"constant — the claim is the RELATIVE ordering.")
    else:
        print(f"\n*** UNCALIBRATED — EVERY RECOMMENDATION WITHHELD: {why} ***\n"
              "The variant table above is printed as the EVIDENCE OF THE\n"
              "MISCALIBRATION, not as a result. A harness that cannot\n"
              "reproduce what DID happen may not say what WOULD have\n"
              "((gx)'s rule, and this study had no gate on its own anchor).\n"
              "Fix the replay before reading the columns: the two candidates\n"
              "are the modelled 29bps round trip (a Hyperliquid taker fee +\n"
              "hedge cost, on a venue MEASURED zero-fee) and accrual off the\n"
              "SETTLED hourly tape versus the bot's live 5-minute loop.")


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

    # 5) THE CALIBRATION GATE [(he)]. It is now the thing standing between a
    #    miscalibrated replay and a recommendation about a real book's exit, so
    #    it is selftested rather than trusted.
    assert calibrate(-0.60, -0.49, 20)[0] is True, calibrate(-0.60, -0.49, 20)
    #    today's ACTUAL numbers must be refused
    ok, why = calibrate(-13.61, -0.49, 20)
    assert ok is False and "episode" in why, (ok, why)
    #    a total that misses the book fails even with a tiny per-episode drift
    ok2, why2 = calibrate(+20.0, 0.0, 200)
    assert ok2 is False and "total" in why2, (ok2, why2)
    #    fail-CLOSED on a sample too thin to calibrate at all
    assert calibrate(0.0, 0.0, 4)[0] is False
    assert calibrate(0.0, 0.0, 5)[0] is True

    # 6a) THE CONSTANTS ARE RETYPED FROM THE BOT — so assert they still match.
    #     [(he)] Not imported, deliberately: this study must run offline with no
    #     DB and no venue, and importing the bot drags its publisher stack in.
    #     But a retyped constant is a constant that drifts, and a drifted one is
    #     worse than absent because the harness then measures a rule the fleet
    #     does not run. Measured today in the SIBLING study
    #     `backtest_carry_gate_lighter.py`: it pins `MAX_POSITIONS = 8` while
    #     the bot has shipped **12** since 30-Jul. Same class, caught by having
    #     looked; this arm makes looking automatic. Drift-arm pattern from
    #     `audit_lever_bounds`.
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(
            os.path.abspath(__file__))))
        import funding_carry_bot as _bot
    except Exception as _e:      # noqa: BLE001
        print(f"  (drift check skipped: cannot import the bot: {_e})")
    else:
        assert OPEN_COST == _bot.OPEN_COST, (OPEN_COST, _bot.OPEN_COST)
        assert MAX_HOLD_H == _bot.MAX_HOLD_H, (MAX_HOLD_H, _bot.MAX_HOLD_H)
        assert FEE_PAYBACK_MARGIN == _bot.FEE_PAYBACK_MARGIN
        assert BLEED_STOP_FRAC == _bot.BLEED_STOP_FRAC
        #  the exit bar is the bot's HL-denominated EXIT_APR converted to the
        #  lighter_shadow arm's TRUE basis (per-8h => /8), which is the ONE
        #  place this file re-does the bot's `_bars()` arithmetic.
        assert abs(EXIT_APR_TRUE - _bot.EXIT_APR / 8.0) < 1e-12, (
            EXIT_APR_TRUE, _bot.EXIT_APR)
        # [2026-08-18 (pr)] The shipped rule MOVED to 6h — on the (mf)
        # books-cohort measurement (a DIFFERENT harness, measured on the
        # cell's own gate/coins), not on this file's replay, whose
        # calibration failure ((he)) still stands and still gates ITS OWN
        # recommendations. V0 stays g1h because the ledger this file
        # calibrates against was produced under g1h; the drift check now
        # pins the bot at the (pr) value so a THIRD value appearing in the
        # bot is still caught.
        assert VARIANTS["V0 ship g1h"][0] == 1.0, (
            "V0 is the LEDGER-ERA rule (g1h); do not retag it")
        assert _bot.FLIP_GRACE_H == 6.0, (
            "the bot's FLIP_GRACE_H moved off the (pr) value "
            f"({_bot.FLIP_GRACE_H}) — update this pin WITH the measurement "
            "that moved it, the (he)/(pr) discipline")

    # 6) the era is read from ONE owner, not retyped here.
    src = open(os.path.abspath(__file__)).read()
    assert "import golive_readiness" in src and "POLICY_ERA" in src, (
        "the era must come from golive_readiness.POLICY_ERA, or the era a "
        "study samples can drift from the era the gate grades on")
    assert 'LIVING_BOOK = "perps-funding-carry-lshadow"' in src, (
        "the RETIRED Hyperliquid arm shares this book's name stem — it must be "
        "matched exactly, never by prefix")

    print("study_carry_flip_grace selftest OK (noise-flip held, hard-adverse "
          "exits, magnitude bar + bleed backstop, pause-not-reset grace, "
          "calibration gate, single-owner era + exact arm match)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        main()
