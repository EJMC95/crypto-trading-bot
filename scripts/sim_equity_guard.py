#!/usr/bin/env python3
"""
scripts/sim_equity_guard.py — simulation evidence for venues/equity_guard.py.

The 11 Jul live event (a venue-side mark dislocation, not a market move) is
not reproducible in a candle backtest, so the guard is validated the way the
rail-debounce was: by driving the EXACT production read path
(equity_guard.vet_account_read + EquityGuard, virtual clock, fake venue)
through calibrated scenarios plus a Monte Carlo sweep.

Scenarios (each asserts; exit 0 = all pass):
  A  11 Jul replay — transient mark dislocation trips the raw rail; the 60s
     debounce alone survives only if the dislocation clears inside the
     confirm window; the guard rejects the print outright in BOTH variants.
  B  real crash — mids corroborate the drop; the guard must NOT delay the
     rail: read accepted, rail trips, debounce confirms, flatten happens.
  B2 fast crash with 30s-stale ws mids — first judge is suspicious, the
     forced-fresh book re-read corroborates, read accepted (no false reject).
  C  dislocated-HIGH boot baseline — the cold-boot read is vetoed, the rail
     adopts the first honest read late, no phantom breach later.
  D  deposit mid-day — accepted via the cash-move escape when the payload
     proves collateral excludes upnl; under degenerate semantics (collateral
     tracks total) the escape stays DISABLED and recovery is via rebase.
  E  persistent total corruption (marks sane) — continuity rejects, then
     self-heals by rebase after REBASE_AFTER consistent prints.
  E2 persistent mark dislocation — the book contradicts the marks, so the
     rebase bar is 4x REBASE_AFTER; asserts no early rebase, eventual concede.
  F  Monte Carlo — random-walk prices + funding drift + random transient
     dislocation injections; asserts zero dislocated prints accepted and a
     ~zero false-reject rate on honest reads; reports the REST budget cost.

Run: python3 scripts/sim_equity_guard.py
"""
from __future__ import annotations

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# deterministic guard config for the sim (same as production defaults)
os.environ.update({
    "LIGHTER_EQUITY_GUARD": "1",
    "LIGHTER_EQUITY_TOL_ABS": "1.0",
    "LIGHTER_EQUITY_TOL_NTL_PCT": "0.01",
    "LIGHTER_EQUITY_TOL_EQ_PCT": "0.002",
    "LIGHTER_EQUITY_REBASE_AFTER": "3",
    "LIGHTER_EQUITY_BOOT_CONFIRM_S": "5",
})

from venues.equity_guard import EquityGuard, EquityRejected, vet_account_read  # noqa: E402

DAILY_LOSS_LIMIT = 0.05   # the bots' 5% rail
DEBOUNCE_S = 60.0         # SafetyRails.confirm_daily_loss delay

FAILS = []


def check(name, cond, detail=""):
    tag = "PASS" if cond else "FAIL"
    print(f"  [{tag}] {name}" + (f" — {detail}" if detail else ""))
    if not cond:
        FAILS.append(name)


# --------------------------- fake venue world --------------------------------
class World:
    """True prices + a venue that reports (total, collateral, positions) with
    injectable dislocations. Book mids = true prices (optionally ws-lagged)."""

    def __init__(self, collateral=50.0, semantics="excl"):
        self.t = 0.0
        self.semantics = semantics       # 'excl': collateral excludes upnl
        self.collateral = collateral
        self.size, self.entry = {}, {}
        self._px_hist = {}               # coin -> [(t, px)]
        self.mark_off = {}               # venue mark = px * (1 + off)
        self.total_shift = 0.0           # corrupts total_asset_value directly
        self.ws_lag = 0.0
        self.fetches = 0
        self.cached_calls = 0
        self.fresh_calls = 0

    # -- time / prices ---------------------------------------------------------
    def now(self):
        return self.t

    def sleep(self, s):
        self.t += s

    def open_pos(self, coin, size, px):
        self.size[coin], self.entry[coin] = size, px
        self.set_px(coin, px)

    def set_px(self, coin, px):
        self._px_hist.setdefault(coin, []).append((self.t, px))

    def px(self, coin, at=None):
        at = self.t if at is None else at
        hist = self._px_hist.get(coin) or []
        best = hist[0][1] if hist else 0.0
        for ts, p in hist:
            if ts <= at:
                best = p
        return best

    # -- venue payload ----------------------------------------------------------
    def upnl(self, coin):
        mark = self.px(coin) * (1.0 + self.mark_off.get(coin, 0.0))
        return self.size[coin] * (mark - self.entry[coin])

    def total(self):
        return self.collateral + sum(self.upnl(c) for c in self.size) + self.total_shift

    def fetch_fields(self):
        self.fetches += 1
        pos = {c: {"size": self.size[c], "entry": self.entry[c],
                   "upnl": self.upnl(c)} for c in self.size if self.size[c]}
        total = self.total()
        coll = total if self.semantics == "incl" else self.collateral
        return total, coll, pos

    # -- book mids ---------------------------------------------------------------
    def mids_cached(self, coins):
        self.cached_calls += 1
        return {c: self.px(c, at=self.t - self.ws_lag) for c in coins}

    def mids_fresh(self, coins):
        self.fresh_calls += 1
        return {c: self.px(c) for c in coins}

    def guard(self, **kw):
        return EquityGuard(self.mids_cached, self.mids_fresh, now=self.now, **kw)


def reader(world, guard):
    """account_value() as the bots see it: float or None (VenueError path)."""
    def _read():
        try:
            return vet_account_read(guard, world.fetch_fields, sleep=world.sleep)
        except EquityRejected:
            return None
    return _read


def rail_loop(world, read, loops, loop_s=3600.0, day_start=None):
    """The bots' daily-loss flow: boot capture (if day_start None), late
    adoption, breach check, 60s debounce, flatten. Returns (flattened,
    day_start, equity_series)."""
    series = []
    if day_start is None:
        day_start = read()          # boot capture (None if vetoed)
    flattened = False
    for _ in range(loops):
        world.sleep(loop_s)
        eq = read()
        series.append(eq)
        if day_start is None and eq is not None:
            day_start = eq          # [LATE BASELINE] as in the bots
        if (not flattened and eq is not None and day_start
                and eq <= day_start * (1 - DAILY_LOSS_LIMIT)):
            world.sleep(DEBOUNCE_S)   # confirm_daily_loss semantics
            eq2 = read()
            if eq2 is None or eq2 <= day_start * (1 - DAILY_LOSS_LIMIT):
                flattened = True
                break
    return flattened, day_start, series


def pilot_world(**kw):
    """Trail-Blazer-like pilot book: $65 equity, 2 positions x ~$27 notional."""
    w = World(collateral=65.0 - 0.30 - 0.40, **kw)   # small existing upnl
    w.open_pos("HYPE", 0.60, 44.0)    # ~$26.4 ntl
    w.set_px("HYPE", 43.5)            # upnl -0.30
    w.open_pos("SOL", 0.18, 152.0)    # ~$27.4 ntl
    w.set_px("SOL", 149.78)           # upnl -0.40
    return w


# ------------------------------- scenarios -----------------------------------
def scenario_a():
    print("\nA. 11 Jul replay — transient venue mark dislocation (~ -$3.9 phantom)")
    for persist_s, label in ((30.0, "clears inside debounce"),
                             (600.0, "persists past debounce")):
        # RAW (guard off = pre-fix behavior, but with the landed 60s debounce)
        w = pilot_world()
        read = reader(w, None)                     # None guard = raw venue read
        day_start = read()
        w.sleep(3600.0)
        w.mark_off = {"HYPE": -0.075, "SOL": -0.075}   # ~ -$4.0 on ~$54 ntl
        t_end = w.t + persist_s

        def raw_step():
            if w.t >= t_end:
                w.mark_off = {}
            return read()

        eq = raw_step()
        raw_flat = False
        if eq is not None and eq <= day_start * (1 - DAILY_LOSS_LIMIT):
            w.sleep(DEBOUNCE_S)
            eq2 = raw_step()
            raw_flat = eq2 is None or eq2 <= day_start * (1 - DAILY_LOSS_LIMIT)
        expect_raw = persist_s > DEBOUNCE_S
        check(f"raw+debounce ({label}): flatten={expect_raw}", raw_flat == expect_raw,
              f"phantom print {eq:.2f} vs day start {day_start:.2f}")

        # GUARDED — same worlds, same schedule
        w = pilot_world()
        g = w.guard()
        read = reader(w, g)
        day_start = read()
        w.sleep(3600.0)
        w.mark_off = {"HYPE": -0.075, "SOL": -0.075}
        eq = read()
        check(f"guard ({label}): dislocated print rejected", eq is None)
        guard_flat = eq is not None and eq <= day_start * (1 - DAILY_LOSS_LIMIT)
        check(f"guard ({label}): rail never trips", not guard_flat)
        w.mark_off = {}
        w.sleep(3600.0)
        eq = read()
        check(f"guard ({label}): honest read re-accepted after", eq is not None,
              f"eq={eq}")


def scenario_b():
    print("\nB. real crash — the guard must NOT delay the rail")
    w = pilot_world()
    g = w.guard()
    read = reader(w, g)
    day_start = read()
    w.sleep(3600.0)
    for c in ("HYPE", "SOL"):                     # true -12% move, book agrees
        w.set_px(c, w.px(c) * 0.88)
    eq = read()
    check("crash read accepted", eq is not None, f"eq={eq}")
    breach = eq is not None and eq <= day_start * (1 - DAILY_LOSS_LIMIT)
    check("rail trips on the crash", breach)
    w.sleep(DEBOUNCE_S)
    eq2 = read()
    check("debounce confirms (flatten proceeds)",
          eq2 is not None and eq2 <= day_start * (1 - DAILY_LOSS_LIMIT))

    print("\nB2. fast crash with 30s-stale ws mids — fresh re-read must corroborate")
    w = pilot_world()
    w.ws_lag = 30.0
    g = w.guard()
    read = reader(w, g)
    read()                                        # boot/baseline
    w.sleep(3600.0)
    for c in ("HYPE", "SOL"):
        w.set_px(c, w.px(c) * 0.90)               # crash JUST happened
    fresh_before = w.fresh_calls
    eq = read()
    check("stale-mid crash read accepted", eq is not None, f"eq={eq}")
    check("forced-fresh re-read was used", w.fresh_calls > fresh_before)


def scenario_c():
    print("\nC. dislocated-HIGH boot baseline (day-start validation)")
    w = pilot_world()
    g = w.guard()
    read = reader(w, g)
    w.mark_off = {"HYPE": 0.20, "SOL": 0.20}      # venue marks +20% at boot
    flattened, day_start, series = rail_loop(
        w, lambda: (w.mark_off.clear() if w.t >= 3600.0 else None) or read(),
        loops=4)
    honest = w.total()
    check("boot read vetoed, honest baseline adopted late",
          day_start is not None and abs(day_start - honest) < 1.0,
          f"day_start={day_start} honest={honest:.2f}")
    check("no phantom breach later", not flattened)


def scenario_d():
    print("\nD. deposit mid-day")
    # normal semantics: collateral excludes upnl -> cash-move escape applies
    # (needs |sum(upnl)| > tol so the payload PROVES the semantics)
    w = pilot_world()
    w.set_px("HYPE", 47.0)            # upnl +1.8: identity has discriminating power
    g = w.guard()
    read = reader(w, g)
    read()
    w.sleep(3600.0)
    w.collateral += 50.0
    eq = read()
    check("deposit accepted in-place (cash-move escape)", eq is not None,
          f"eq={eq}")
    # degenerate semantics (collateral tracks total) + large upnl: the identity
    # total = collateral + sum(upnl) FAILS, so the escape must stay OFF and a
    # cash-side jump is rejected, then self-heals by rebase (consistent prints)
    w = World(collateral=64.30, semantics="incl")
    w.open_pos("HYPE", 0.60, 44.0)
    w.set_px("HYPE", 47.0)            # upnl +1.8 (> tol, but identity fails)
    g = w.guard()
    read = reader(w, g)
    read()
    w.sleep(3600.0)
    w.collateral += 50.0
    outs = []
    for _ in range(4):
        outs.append(read())
        w.sleep(300.0)
    check("degenerate semantics: escape disabled (first read rejected)",
          outs[0] is None)
    check("...but self-heals by rebase within REBASE_AFTER reads",
          any(o is not None for o in outs), f"outs={outs}")


def scenario_e():
    print("\nE. persistent total corruption (marks sane) -> rebase after 3")
    w = pilot_world()
    g = w.guard()
    read = reader(w, g)
    read()
    w.sleep(3600.0)
    w.total_shift = -10.0                          # corrupt total, marks fine
    outs = [read()]
    for _ in range(3):
        w.sleep(300.0)
        outs.append(read())
    check("continuity rejects first", outs[0] is None)
    check("rebase accepts by the 3rd consistent print",
          outs[2] is not None or outs[1] is not None, f"outs={outs}")

    print("\nE2. persistent MARK dislocation -> rebase bar is 4x (12 reads)")
    w = pilot_world()
    g = w.guard()
    read = reader(w, g)
    read()
    w.sleep(3600.0)
    w.mark_off = {"HYPE": -0.075, "SOL": -0.075}
    outs = []
    for _ in range(13):
        outs.append(read())
        w.sleep(300.0)
    check("no early rebase (first 11 rejected)",
          all(o is None for o in outs[:11]), f"first accept at #{next((i for i, o in enumerate(outs) if o is not None), None)}")
    check("eventually concedes (venue number wins by #12)",
          any(o is not None for o in outs), f"outs tail={outs[-3:]}")


def scenario_f():
    print("\nF. Monte Carlo — random walks + funding drift + phantom injections")
    rng = random.Random(11)
    phantom_accepted = honest_rejected = honest_total = phantom_total = 0
    fresh_calls = reads = 0
    for seed in range(6):
        rng.seed(100 + seed)
        w = pilot_world()
        g = w.guard()
        read = reader(w, g)
        read()
        for step in range(400):
            w.sleep(300.0)
            for c in list(w.size):
                w.set_px(c, w.px(c) * (1.0 + rng.gauss(0.0, 0.003)))
            w.collateral -= 0.0005                # funding drip, ~$0.14/day
            dislocated = rng.random() < 0.02
            if dislocated:
                kind = rng.random()
                if kind < 0.5:
                    off = rng.choice([-1, 1]) * rng.uniform(0.05, 0.30)
                    w.mark_off = {c: off for c in w.size}
                else:
                    w.total_shift = rng.choice([-1, 1]) * rng.uniform(3.0, 15.0)
            eq = read()
            reads += 1
            if dislocated:
                phantom_total += 1
                if eq is not None:
                    phantom_accepted += 1
            else:
                honest_total += 1
                if eq is None:
                    honest_rejected += 1
            w.mark_off, w.total_shift = {}, 0.0   # injections are transient
        fresh_calls += w.fresh_calls
    fr = honest_rejected / max(honest_total, 1)
    print(f"    {reads} reads | {phantom_total} dislocated prints | "
          f"{honest_total} honest | fresh-REST re-reads {fresh_calls} "
          f"({fresh_calls / reads:.2%} of reads)")
    check("zero dislocated prints accepted", phantom_accepted == 0,
          f"{phantom_accepted}/{phantom_total}")
    check("honest false-reject rate < 0.5%", fr < 0.005,
          f"{honest_rejected}/{honest_total} = {fr:.3%}")


def main():
    print("equity-guard simulation (production path: vet_account_read)")
    scenario_a()
    scenario_b()
    scenario_c()
    scenario_d()
    scenario_e()
    scenario_f()
    print()
    if FAILS:
        print(f"{len(FAILS)} FAILURE(S): {FAILS}")
        return 1
    print("ALL SCENARIOS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
