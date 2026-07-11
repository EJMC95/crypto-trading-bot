#!/usr/bin/env python3
"""
venues/equity_guard.py — robust-equity guard for venue account_value() reads.

WHY (live incident 2026-07-11): Lighter's /account total_asset_value printed a
dislocated equity — roughly -25% of deployed notional while every held coin's
live book moved <1% — and that single bad print tripped Trail Blazer's daily-
loss rail; the flatten then sold into the dislocation (phantom drawdown became
a real -5.9%). The 60s rail debounce that landed after the event
(SafetyRails.confirm_daily_loss) only survives dislocations SHORTER than the
confirm window — a print that stays wrong for >60s would still flatten. This
guard attacks the read itself: a venue equity print is only ACCEPTED when the
venue's own position marks agree with the LIVE order book, so a phantom print
never reaches the rail at all, however long it persists.

HOW — checks per read, all computed from data we already pay the governor for
(the account payload carries collateral + per-position unrealized_pnl in the
SAME weight-1 response; mids come from the ws book cache or the TTL-cached
REST snapshot fallback):

  1. MARK CROSS-CHECK (stateless — this is also what vets a boot / day-start
     baseline read): sum(venue unrealized_pnl) vs sum(size x (book_mid -
     entry)). Entry price cancels — the gap is effectively
     sum(size x (venue_mark - book_mid)) — so it is robust to entry/funding
     bookkeeping semantics. Divergence beyond tolerance means the venue is
     marking positions away from its own book: the print is dislocated ->
     REJECT. A REAL crash moves the book mids too, so it passes; this fires
     only when equity moved and the book did not (the incident class).
  2. CONTINUITY (stateful): the venue total is expected to move from the last
     ACCEPTED read by the mid-implied P&L delta (+ funding allowance). Catches
     a corrupted total_asset_value even when per-position marks look sane.
     Runs only while the position set is unchanged — a fill between reads
     legitimately moves realized P&L. The last accepted read is PERSISTED
     (bot_pnl_store bot_state) so a redeploy cannot re-anchor on a bad print.
  3. CASH-MOVE ESCAPE: if the jump in total is explained by the jump in
     collateral with an unchanged position set (deposit / withdrawal / funding
     settlement — ledger-grade numbers, not mark-derived), ACCEPT with a loud
     warning instead of rejecting. Applies only when the payload demonstrates
     collateral EXCLUDES unrealized P&L (self-calibrated per read from the
     identity total = collateral + sum(upnl); if collateral tracks total the
     escape would be a hole, so it is disabled).

A suspected dislocation triggers ONE forced-fresh REST book re-read for the
held coins (bypassing every cache) before the verdict, so 30s-stale ws mids
during a fast real crash cannot cause a false reject.

FAIL-SAFE DIRECTION: the guard only rejects on POSITIVE evidence that the
live book disagrees with the print. Large-but-corroborated moves pass (the
rail must fire during a real crash); unreadable mids widen tolerance rather
than block (the 60s rail debounce remains the backstop). A REJECT surfaces as
VenueError, which every caller already treats as "equity unreadable this
loop" — the rail waits, position management (mids-based stops) continues.

Rejects self-heal — the venue's number is what margining/liquidation actually
runs on, so it can never be ignored forever, only debounced:
  * continuity rejects: after REBASE_AFTER consecutive, mutually-consistent
    rejected prints the guard re-baselines (loudly). Covers deposits we could
    not verify and model drift.
  * mark-gap rejects: the book actively contradicts the marks, so the bar is
    4x REBASE_AFTER before conceding — but it still concedes eventually
    rather than leave a bot equity-blind (and its loss rail off) for good.

Env knobs (defaults sized for the $50-200 pilot books):
  LIGHTER_EQUITY_GUARD           1     (0 = passthrough, raw venue reads)
  LIGHTER_EQUITY_TOL_ABS         1.0   $ floor of every tolerance band
  LIGHTER_EQUITY_TOL_NTL_PCT     0.01  x gross position notional
  LIGHTER_EQUITY_TOL_EQ_PCT      0.002 x |equity|
  LIGHTER_EQUITY_REBASE_AFTER    3     consecutive consistent rejects -> rebase
  LIGHTER_EQUITY_BOOT_CONFIRM_S  5     boot double-read spacing (0 = off)

Pure logic with injected mid providers / clock / persistence, so
scripts/sim_equity_guard.py exercises the EXACT production flow
(vet_account_read) offline. No strategy signal is touched anywhere.
"""
from __future__ import annotations

import logging
import os
import time

log = logging.getLogger("venues.equity_guard")

# hourly funding on pilot books is ~0.01%/h of notional at the extreme; give
# the continuity band 2 bps of notional per hour elapsed (min 1h) on top of tol
_FUNDING_ALLOW_PER_H = 0.0002
# a held coin whose book is unreadable gets a 5%-of-its-notional move
# allowance instead of blocking the continuity check entirely
_UNREADABLE_NTL_ALLOW = 0.05
# persisted guard state older than this is ignored (positions/mids from a
# week-old process prove nothing about today's book)
_PERSIST_MAX_AGE_S = 7 * 86400.0


class EquityRejected(Exception):
    """A venue equity print failed the dislocation checks. Callers map this to
    VenueError ('equity unreadable this loop') — never to a zero equity."""


class Verdict:
    __slots__ = ("accepted", "equity", "reason", "detail")

    def __init__(self, accepted, equity, reason, detail=""):
        self.accepted = accepted
        self.equity = equity
        self.reason = reason
        self.detail = detail


def _env_flag(name, default="1"):
    return os.environ.get(name, default).strip().lower() not in ("0", "false", "no", "")


class EquityGuard:
    def __init__(self, mids_cached, mids_fresh, *, now=time.time,
                 load_state=None, save_state=None):
        """mids_cached/mids_fresh: callable(coins) -> {coin: mid} (cached =
        ws-first + TTL REST; fresh = force new REST snapshots, no caches).
        load_state/save_state persist the last ACCEPTED read across redeploys
        (same rationale as the durable daily-loss halt)."""
        self.enabled = _env_flag("LIGHTER_EQUITY_GUARD")
        self.tol_abs = float(os.environ.get("LIGHTER_EQUITY_TOL_ABS", "1.0"))
        self.tol_ntl_pct = float(os.environ.get("LIGHTER_EQUITY_TOL_NTL_PCT", "0.01"))
        self.tol_eq_pct = float(os.environ.get("LIGHTER_EQUITY_TOL_EQ_PCT", "0.002"))
        self.rebase_after = max(1, int(os.environ.get("LIGHTER_EQUITY_REBASE_AFTER", "3")))
        self.boot_confirm_s = float(os.environ.get("LIGHTER_EQUITY_BOOT_CONFIRM_S", "5"))
        self._mids_cached = mids_cached
        self._mids_fresh = mids_fresh
        self._now = now
        self._save = save_state
        self._last = None      # {ts, equity, collateral, mids:{c:px}, sizes:{c:sz}}
        self._rejects = []     # consecutive rejected reads: (ts, venue_total, reason)
        if load_state is not None:
            try:
                st = load_state() or {}
                age = self._now() - float(st.get("ts") or 0)
                if st.get("equity") is not None and 0 <= age <= _PERSIST_MAX_AGE_S:
                    self._last = {
                        "ts": float(st["ts"]), "equity": float(st["equity"]),
                        "collateral": (float(st["collateral"])
                                       if st.get("collateral") is not None else None),
                        "mids": {str(k): float(v) for k, v in (st.get("mids") or {}).items()},
                        "sizes": {str(k): float(v) for k, v in (st.get("sizes") or {}).items()},
                    }
                    log.info("equity guard: restored last accepted read $%.2f "
                             "(age %.0f min)", self._last["equity"], age / 60.0)
            except Exception as e:  # noqa: BLE001 — cold start is always safe
                log.warning("equity guard: state restore failed (%s) — starting cold", e)

    # -- public ----------------------------------------------------------------
    @property
    def has_state(self):
        return self._last is not None

    def tolerance(self, gross_ntl, equity):
        return max(self.tol_abs, self.tol_ntl_pct * gross_ntl,
                   self.tol_eq_pct * abs(equity))

    def evaluate(self, venue_total, collateral, positions) -> Verdict:
        """Judge one venue equity print. positions: {coin: {size, entry[, upnl]}}
        in venue-native units (size x px = USD). Never raises."""
        if not self.enabled:
            return Verdict(True, float(venue_total), "disabled")
        now = self._now()
        held = {c: p for c, p in positions.items() if p.get("size")}
        if not held:
            # flat account: no marks exist to dislocate; accept + (re)baseline
            return self._accept(now, venue_total, collateral, {}, {}, "flat")
        mids = {c: m for c, m in (self._mids_cached(list(held)) or {}).items() if m}
        problem = self._judge(now, venue_total, collateral, held, mids)
        if problem is not None:
            # suspected dislocation -> one forced-fresh book re-read. A fast
            # REAL crash with <=30s-stale ws mids lands here and must be
            # corroborated by a fresh book, not rejected.
            fresh = {c: m for c, m in (self._mids_fresh(list(held)) or {}).items() if m}
            if fresh:
                mids = {**mids, **fresh}
                problem = self._judge(now, venue_total, collateral, held, mids)
        if problem is None:
            return self._accept(now, venue_total, collateral, mids,
                                {c: p["size"] for c, p in held.items()}, "ok")
        return self._reject(now, venue_total, collateral, held, mids, problem)

    # -- checks ------------------------------------------------------------------
    def _judge(self, now, venue_total, collateral, held, mids):
        """None = credible; (reason, detail) = suspected dislocation."""
        gross = sum(abs(p["size"]) * (mids.get(c) or p.get("entry") or 0.0)
                    for c, p in held.items())
        tol = self.tolerance(gross, venue_total)

        # 1. venue marks vs live book. Entry cancels: gap ~ sum(size*(mark-mid)).
        gap = covered = upnl_sum = 0.0
        upnl_all = True
        for c, p in held.items():
            u = p.get("upnl")
            if u is None:
                upnl_all = False
                continue
            upnl_sum += u
            mid = mids.get(c)
            if mid is None:
                continue
            gap += u - p["size"] * (mid - (p.get("entry") or 0.0))
            covered += abs(p["size"]) * mid
        if covered > 0 and abs(gap) > tol + _UNREADABLE_NTL_ALLOW * max(0.0, gross - covered):
            return ("mark_gap",
                    f"venue marks vs book mids diverge ${gap:+.2f} "
                    f"(tol ${tol:.2f} on ${covered:.0f} covered ntl)")
        if covered <= 0:
            log.warning("equity guard: no book mids readable for %s — mark "
                        "cross-check skipped this read.", sorted(held))

        # 2. continuity vs the last ACCEPTED read (unchanged position set only)
        last = self._last
        if last is not None and self._same_book(last["sizes"], held):
            both = [c for c in held if c in mids and c in last["mids"]]
            explained_ntl = sum(abs(held[c]["size"]) * mids[c] for c in both)
            exp_delta = sum(held[c]["size"] * (mids[c] - last["mids"][c]) for c in both)
            dt_h = max((now - last["ts"]) / 3600.0, 0.0)
            tol_cont = (tol + gross * _FUNDING_ALLOW_PER_H * max(dt_h, 1.0)
                        + _UNREADABLE_NTL_ALLOW * max(0.0, gross - explained_ntl))
            d_total = venue_total - last["equity"]
            resid = d_total - exp_delta
            if abs(resid) > tol_cont:
                # 3. cash-move escape — only when this payload PROVES collateral
                # excludes upnl (identity total = collateral + sum(upnl)); if
                # collateral just tracks total this would be a hole. The proof
                # needs discriminating power: with |sum(upnl)| inside tolerance
                # both semantics satisfy the identity, so the escape stays OFF
                # (a real deposit then heals via rebase instead — slower, safe).
                cash_like = (collateral is not None
                             and last.get("collateral") is not None
                             and upnl_all
                             and abs(upnl_sum) > tol
                             and abs(venue_total - (collateral + upnl_sum)) <= tol)
                if cash_like and abs(d_total - (collateral - last["collateral"])) <= tol_cont:
                    log.warning("equity guard: cash-side move $%+.2f accepted "
                                "(collateral moved with total; positions unchanged "
                                "— deposit/withdrawal/funding settlement).", d_total)
                    return None
                return ("continuity",
                        f"equity moved ${d_total:+.2f} vs book-implied "
                        f"${exp_delta:+.2f} (resid ${resid:+.2f} > tol ${tol_cont:.2f}, "
                        f"{dt_h * 60.0:.0f}m since accepted ${last['equity']:.2f})")
        return None

    @staticmethod
    def _same_book(prev_sizes, held):
        cur = {c: p["size"] for c, p in held.items()}
        if set(cur) != set(prev_sizes or {}):
            return False
        return all(abs(cur[c] - prev_sizes[c]) <= 1e-9 * max(1.0, abs(cur[c]))
                   for c in cur)

    # -- verdicts ----------------------------------------------------------------
    def _accept(self, now, venue_total, collateral, mids, sizes, reason):
        if self._rejects:
            log.info("equity guard: read accepted after %d reject(s).",
                     len(self._rejects))
        self._rejects = []
        self._last = {"ts": now, "equity": float(venue_total),
                      "collateral": (float(collateral) if collateral is not None else None),
                      "mids": dict(mids), "sizes": dict(sizes)}
        if self._save is not None:
            try:
                self._save(self._last)
            except Exception:  # noqa: BLE001 — persistence is best-effort
                pass
        return Verdict(True, float(venue_total), reason)

    def _reject(self, now, venue_total, collateral, held, mids, problem):
        reason, detail = problem
        self._rejects.append((now, float(venue_total), reason))
        # self-heal: the venue's number is what margining actually runs on, so
        # N consecutive SELF-CONSISTENT prints eventually win over our model.
        # mark_gap rejects carry live counter-evidence (book vs marks) so their
        # bar is 4x higher, but even they concede rather than blind the rail
        # forever.
        need = self.rebase_after * (4 if reason == "mark_gap" else 1)
        vals = [v for _, v, _ in self._rejects[-need:]]
        gross = sum(abs(p["size"]) * (mids.get(c) or p.get("entry") or 0.0)
                    for c, p in held.items())
        if (len(self._rejects) >= need
                and max(vals) - min(vals) <= self.tolerance(gross, venue_total)):
            log.error("equity guard: %d consecutive consistent rejects — REBASING "
                      "to venue value $%.2f (last: %s).",
                      len(self._rejects), venue_total, detail)
            return self._accept(now, venue_total, collateral, mids,
                                {c: p["size"] for c, p in held.items()}, "rebase")
        log.warning("equity guard: REJECT #%d (%s) — %s",
                    len(self._rejects), reason, detail)
        return Verdict(False, None, reason, detail)


def vet_account_read(guard, fetch_fields, sleep=time.sleep):
    """The guarded account_value() flow — ONE implementation shared by
    LighterClient and scripts/sim_equity_guard.py so the simulator exercises
    exactly what production runs.

    fetch_fields() -> (venue_total, collateral, positions) and may raise.
    Returns the accepted equity, or raises EquityRejected.

    Boot rule: the FIRST-EVER read (nothing persisted, nothing accepted yet)
    becomes the day-start baseline downstream, and a dislocated-HIGH baseline
    makes every later correct read look like a rail breach — so a cold boot
    demands TWO agreeing reads boot_confirm_s apart before anything is trusted.
    """
    total, collateral, positions = fetch_fields()
    if guard is None or not guard.enabled:
        return float(total)
    if not guard.has_state and guard.boot_confirm_s > 0:
        v1 = guard.evaluate(total, collateral, positions)
        if not v1.accepted:
            raise EquityRejected(f"boot equity read rejected ({v1.reason}: {v1.detail})")
        sleep(guard.boot_confirm_s)
        total, collateral, positions = fetch_fields()
    v = guard.evaluate(total, collateral, positions)
    if not v.accepted:
        raise EquityRejected(f"equity read rejected ({v.reason}: {v.detail})")
    return v.equity
