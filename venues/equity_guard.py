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
# [2026-07-18] max gap between two reject reads for them to count as the SAME
# consecutive streak (and max age of the newest reject on restore). A run-once
# bot relaunches every ~300s (tickettaker_loop.sh) and does 1-2 reads/process,
# so a live streak's gaps are seconds-to-300s; 900s (3 cadences) tolerates one
# skipped cycle while refusing to STITCH a dead sub-`need` episode to a fresh
# reject a relaunch later. Fail direction: a broken/short streak = stay
# equity-blind (recoverable); a rebase onto a bad number moves real money.
_REJECT_STREAK_MAX_GAP_S = 900.0


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
                 load_state=None, save_state=None, persist_reject_streak=False):
        """mids_cached/mids_fresh: callable(coins) -> {coin: mid} (cached =
        ws-first + TTL REST; fresh = force new REST snapshots, no caches).
        load_state/save_state persist the last ACCEPTED read across redeploys
        (same rationale as the durable daily-loss halt).

        persist_reject_streak: RUN-ONCE bots ONLY (the Ticket Taker, relaunched
        every ~300s by tickettaker_loop.sh). A run-once process rebuilds the
        guard every cycle, so the in-memory reject streak resets and the
        N-consecutive-rejects rebase can never fire — set this True to persist
        the streak across relaunches. A LONG-LIVED bot (the Funding Farmer's
        `while True`) MUST leave this False: its streak already lives in memory,
        and persisting it would strip the redeploy streak-reset it relies on,
        letting a dislocation spanning a `railway up` rebase onto a phantom
        (adversarial review, HIGH)."""
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
        self._persist_streak = bool(persist_reject_streak)
        self._last = None      # {ts, equity, collateral, mids:{c:px}, sizes:{c:sz}}
        self._rejects = []     # consecutive rejected reads: (ts, venue_total, collateral, reason)
        self._capital_moves = []   # accepted deposits/withdrawals awaiting pop (D1 2026-07-21)
        if load_state is not None:
            try:
                st = load_state() or {}
                # [2026-07-18] blob shape is {"last": <accepted>, "rejects": [...]}
                # so the reject STREAK survives a run-once relaunch. Without it a
                # run-once bot (Ticket Taker: `python … ; sleep 300` —
                # tickettaker_loop.sh) rebuilds the guard every cycle, self._rejects
                # resets to [] every process, and the N-consecutive-rejects rebase
                # can NEVER reach N — a legit deposit leaves the bot equity-BLIND
                # forever (MEASURED 2026-07-18: the Farmer, a `while True` process,
                # healed within minutes; the Taker, run-once, stayed None until
                # this). Old flat blobs (top-level "equity", no wrapper) read as
                # last-only.
                wrapped = ("last" in st) or ("rejects" in st)
                last_blob = (st.get("last") if wrapped else st) or {}
                age = self._now() - float(last_blob.get("ts") or 0)
                # last-accepted read restores for EVERY bot (unchanged); only a
                # run-once bot resumes the reject STREAK (below).
                if last_blob.get("equity") is not None and 0 <= age <= _PERSIST_MAX_AGE_S:
                    self._last = {
                        "ts": float(last_blob["ts"]), "equity": float(last_blob["equity"]),
                        "collateral": (float(last_blob["collateral"])
                                       if last_blob.get("collateral") is not None else None),
                        "mids": {str(k): float(v) for k, v in (last_blob.get("mids") or {}).items()},
                        "sizes": {str(k): float(v) for k, v in (last_blob.get("sizes") or {}).items()},
                        # [2026-07-18] entries MUST survive the redeploy too, or
                        # the collateral-stable rebase's entries_match gate is
                        # permanently False post-restart and the deposit-stuck
                        # symptom returns on the very deploy that ships the fix.
                        # Legacy snapshots have no entries -> {}; entries_match
                        # degrades gracefully (below) until the first fresh accept.
                        "entries": {str(k): float(v)
                                    for k, v in (last_blob.get("entries") or {}).items()
                                    if v is not None},
                    }
                    log.info("equity guard: restored last accepted read $%.2f "
                             "(age %.0f min)", self._last["equity"], age / 60.0)
                if self._persist_streak:
                    self._rejects = self._restore_rejects(st.get("rejects"))
                    if self._rejects:
                        log.info("equity guard: resumed reject streak of %d (%s)",
                                 len(self._rejects), self._rejects[-1][3])
            except Exception as e:  # noqa: BLE001 — cold start is always safe
                log.warning("equity guard: state restore failed (%s) — starting cold", e)

    def _restore_rejects(self, raw):
        """Rebuild the consecutive-reject streak a prior RUN-ONCE process
        persisted. Keeps only a CONTIGUOUS, SAME-REASON run ending at the most
        recent reject: the newest reject must be within _REJECT_STREAK_MAX_GAP_S
        of now, each earlier one within that gap of its successor, and all one
        reason. This refuses to (a) stitch a dead sub-`need` episode to a fresh
        reject a relaunch later, and (b) mix a high-bar mark_gap reject into a
        low-bar continuity window. Malformed input -> []. Fail toward NOT
        rebasing (staying equity-blind is recoverable; a bad rebase moves money).
        Trimmed to the last 4*rebase_after (the widest window _reject inspects)."""
        if not raw:
            return []
        now = self._now()
        parsed = []
        try:
            for r in raw:
                parsed.append((float(r[0]), float(r[1]),
                               None if r[2] is None else float(r[2]), str(r[3])))
        except (TypeError, ValueError, IndexError):
            return []
        # a future-stamped reject (clock skew / corrupt blob) would anchor the
        # walk and break the genuine streak behind it — drop it, mirroring the
        # `0 <= age` guard the last-accepted restore already has.
        parsed = [r for r in parsed if r[0] <= now + 60.0]
        parsed.sort(key=lambda x: x[0])
        out = []
        nxt = now          # anchor: the newest reject must be recent vs now
        reason = None
        for rec in reversed(parsed):
            if nxt - rec[0] > _REJECT_STREAK_MAX_GAP_S:
                break      # gap too wide -> the streak ends here
            if reason is None:
                reason = rec[3]
            elif rec[3] != reason:
                break      # a different failure mode -> not the same streak
            out.append(rec)
            nxt = rec[0]
        out.reverse()
        return out[-4 * self.rebase_after:]

    def _persist(self):
        """Persist guard state. A RUN-ONCE bot (persist_reject_streak) stores the
        last accepted read AND the reject streak, so a relaunch resumes the
        streak instead of restarting it at 0. A LONG-LIVED bot stores ONLY the
        last accepted read (exact pre-2026-07-18 behaviour) — its streak lives in
        memory and MUST reset on every redeploy, or a dislocation spanning a
        `railway up` rebases onto a phantom (adversarial review, HIGH)."""
        if self._save is None:
            return
        try:
            if self._persist_streak:
                self._save({"last": self._last,
                            "rejects": [list(r)
                                        for r in self._rejects[-4 * self.rebase_after:]]})
            else:
                self._save(self._last)
        except Exception:  # noqa: BLE001 — persistence is best-effort
            pass

    # -- capital moves (deposits / withdrawals are NOT P&L) ---------------------
    def _record_capital_move(self, now, delta, how):
        """[2026-07-21 review N1] A cash move the guard just accepted is CAPITAL,
        and the guard is the only layer that can tell it from P&L (it holds the
        last TRUSTED collateral). Record the ledger-grade delta so the bot can
        move its P&L baseline instead of printing the operator's own money as
        profit (MEASURED 2026-07-18: two ~$32 deposits printed as +$64.77 of
        live "P&L" on the dashboard — the (ao) heal restored equity continuity
        and nothing moved the baseline). Declared residual: a funding settlement
        big enough to breach the continuity tolerance ALONE would be
        misclassified as capital — orders of magnitude above the funding
        allowance already inside the band on these books, and every event is
        logged + persisted by the caller for audit."""
        try:
            d = round(float(delta), 2)
        except (TypeError, ValueError):
            return
        self._capital_moves.append({"ts": float(now), "delta": d, "how": str(how)})
        log.warning("equity guard: CAPITAL MOVE $%+.2f (%s) — the P&L baseline "
                    "should absorb this, not report it as profit.", d, how)

    def pop_capital_moves(self):
        """Return-and-clear capital-move events accepted since the last pop.
        In-memory only (declared residual: a crash between the accept and the
        caller's pop loses the event — the window is one loop iteration, and
        the CAPITAL_ADJUST_USD env knob is the manual recovery)."""
        out, self._capital_moves = self._capital_moves, []
        return out

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
            return self._accept(now, venue_total, collateral, mids, held, "ok")
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
                # (a real deposit then heals via the COLLATERAL-STABLE rebase in
                # _reject — persistence-gated, robust to book drift, safe).
                cash_like = (collateral is not None
                             and last.get("collateral") is not None
                             and upnl_all
                             and abs(upnl_sum) > tol
                             and abs(venue_total - (collateral + upnl_sum)) <= tol)
                if cash_like and abs(d_total - (collateral - last["collateral"])) <= tol_cont:
                    log.warning("equity guard: cash-side move $%+.2f accepted "
                                "(collateral moved with total; positions unchanged "
                                "— deposit/withdrawal/funding settlement).", d_total)
                    # capital, not P&L — the collateral delta is the ledger-grade
                    # size of the move (D1 2026-07-21)
                    self._record_capital_move(now, collateral - last["collateral"],
                                              "cash-escape")
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
    def _accept(self, now, venue_total, collateral, mids, held, reason):
        if self._rejects:
            log.info("equity guard: read accepted after %d reject(s).",
                     len(self._rejects))
        self._rejects = []
        # [2026-07-18] entries stored alongside sizes: a held position's entry is
        # FIXED, so the collateral-stable rebase can require the current payload
        # entry to match this trusted baseline. Without it, STEP 1's mark check
        # cancels entry (gap = upnl - size*(mid-entry)) so a venue that corrupts
        # upnl AND entry together keeps gap=0 while injecting an unbounded phantom
        # into total = collateral + sum(upnl) (adversarial review, MEDIUM).
        self._last = {"ts": now, "equity": float(venue_total),
                      "collateral": (float(collateral) if collateral is not None else None),
                      "mids": dict(mids),
                      "sizes": {c: p["size"] for c, p in held.items()},
                      "entries": {c: p.get("entry") for c, p in held.items()}}
        # persists {"last": self._last, "rejects": []} — the empty streak clears
        # any persisted rejects so the next process starts the counter fresh.
        self._persist()
        return Verdict(True, float(venue_total), reason)

    def _reject(self, now, venue_total, collateral, held, mids, problem):
        reason, detail = problem
        # [2026-07-18] a streak is "N consecutive SELF-CONSISTENT rejects" — a
        # change of reason (e.g. mark_gap -> continuity when a held coin's mid
        # goes dark) is a DIFFERENT failure mode, not the same one continuing.
        # Reset on a reason change so `need` (sized by reason) and the
        # value-stability window can never mix a high-bar mark_gap reject into a
        # low-bar continuity rebase (adversarial review, HIGH: persisted mark_gap
        # rejects were laundered into a continuity-bar total_stable rebase onto
        # the exact 2026-07-11 phantom class).
        if self._rejects and self._rejects[-1][3] != reason:
            self._rejects = []
        self._rejects.append((now, float(venue_total),
                              float(collateral) if collateral is not None else None,
                              reason))
        # hygiene: bound the in-memory streak (only the last `need` are read).
        if len(self._rejects) > 4 * self.rebase_after:
            del self._rejects[:-4 * self.rebase_after]
        # self-heal: the venue's number is what margining actually runs on, so
        # N consecutive SELF-CONSISTENT prints eventually win over our model.
        # mark_gap rejects carry live counter-evidence (book vs marks) so their
        # bar is 4x higher, but even they concede rather than blind the rail
        # forever.
        need = self.rebase_after * (4 if reason == "mark_gap" else 1)
        recent = self._rejects[-need:]
        vals = [v for _, v, _c, _r in recent]
        gross = sum(abs(p["size"]) * (mids.get(c) or p.get("entry") or 0.0)
                    for c, p in held.items())
        tol = self.tolerance(gross, venue_total)
        total_stable = max(vals) - min(vals) <= tol

        # [2026-07-18] COLLATERAL-STABLE rebase. total_stable compares raw TOTALS,
        # which drift with mids — so on a normally-volatile book it never fires
        # when |upnl| swings on the order of tol, and a deposit-induced continuity
        # reject leaves the bot equity-BLIND indefinitely. MEASURED: a live
        # operator deposit stuck BOTH real-money bots (Funding Farmer + Ticket
        # Taker) at equity=None until their guard state was cleared by hand;
        # equity=None also disables the daily-loss rail (it needs a non-None
        # equity), so the stuck state is itself a real-money hazard.
        # Collateral is the LEDGER cash figure — it does NOT drift with mids — so
        # a genuine deposit yields a STABLE collateral series while a transient
        # glitch reverts within `need` reads. Rebase when, across `need`
        # consecutive CONTINUITY rejects (not mark_gap — that is a marks-vs-book
        # disagreement, unrelated to cash), collateral has been stable AND the
        # current total is consistent with collateral + sum(upnl). The identity
        # gate means a total-ONLY dislocation (total glitches, collateral stays,
        # identity broken) still does NOT rebase this way — only a persistent,
        # ledger-consistent cash level does, and `need` reads of persistence is
        # the same bar the total-stable path already trusts.
        colls = [c for _, _v, c, _r in recent if c is not None]
        upnl_all = bool(held) and all(p.get("upnl") is not None for p in held.values())
        upnl_sum = sum(p["upnl"] for p in held.values() if p.get("upnl") is not None)
        identity_ok = (collateral is not None and upnl_all
                       and abs(venue_total - (collateral + upnl_sum)) <= tol)
        # [2026-07-18] marks_corroborated: identity_ok only proves the
        # venue-INTERNAL identity total == collateral + sum(upnl); a upnl-side
        # mismark satisfies it too. It is trustworthy ONLY when EVERY held coin's
        # mark was cross-checked against the live book this read (STEP 1 ran over
        # all of them; reason=='continuity' means it AGREED). A NOTIONAL-coverage
        # bound is NOT enough: a dark coin's phantom upnl = size*(mark-entry) is
        # UNBOUNDED by its notional (size*entry), so one dark low-notional leg can
        # inject an arbitrarily large uncorroborated phantom while covered_now
        # still ~= gross (adversarial review, HIGH). Require a readable mid for
        # EVERY held coin. Fail-safe: any dark leg keeps the bot equity-unreadable
        # rather than trusting a total a phantom could hide inside.
        marks_corroborated = bool(held) and all(mids.get(c) for c in held)
        # [2026-07-18] entries_match: STEP 1 cancels entry, so identity_ok +
        # marks_corroborated verify mark==mid but NOT that entry is real — a
        # venue that corrupts upnl AND entry together (gap held at 0) injects an
        # unbounded phantom into total = collateral + sum(upnl) (adversarial
        # review, MEDIUM). A HELD position's entry is fixed, so require every
        # current entry to match the entry recorded at the last accepted read.
        # Graceful degradation: a baseline with NO stored entries (a legacy
        # pre-fix snapshot restored across a redeploy, or a not-yet-accepted
        # guard) cannot verify entry — but skipping the check OUTRIGHT was a
        # CONFIRMED false-rebase hole (adversarial review, HIGH/CRITICAL,
        # reproduced end-to-end): the live Taker's first post-deploy blob is
        # exactly that legacy shape, and an entry+upnl lockstep phantom then
        # rebased +13% into the daily-loss rail. The DISCRIMINATOR that closes
        # it without re-stranding the honest deposit: a genuine deposit or
        # withdrawal MOVES ledger collateral away from the trusted baseline,
        # while the lockstep phantom leaves collateral flat (its injection
        # rides upnl, and identity_ok pins total = collateral + upnl). So when
        # entry verification is impossible, require |collateral - baseline
        # collateral| > tol before the rebase may fire. Honest deposit ->
        # collateral moved -> heals; phantom -> collateral flat -> stays
        # equity-blind (recoverable). The first fresh accept records entries
        # and full verification re-arms.
        # (Do NOT replace this with `not last_entries and not persist` — on the
        # persist path that collapses entries_match to False and re-strands the
        # honest legacy-blob deposit, the exact incident this file heals.)
        last_entries = (self._last or {}).get("entries") or {}
        if last_entries:
            entries_match = all(
                last_entries.get(c) is not None and p.get("entry") is not None
                and abs(float(p["entry"]) - float(last_entries[c]))
                <= 1e-6 * max(1.0, abs(float(last_entries[c])))
                for c, p in held.items())
        else:
            _last_coll = (self._last or {}).get("collateral")
            entries_match = (collateral is not None and _last_coll is not None
                             and abs(float(collateral) - float(_last_coll)) > tol)
        # With entries pinned to the trusted baseline, marks corroborated for
        # every coin, and sizes unchanged, the rebased equity = collateral +
        # book-corroborated upnl; the only residual error is O(tol) (STEP 1 and
        # identity_ok each carry a directional tol of slack that can stack to
        # ~2*tol) plus a PERSISTENT collateral corruption — the same tradeoff the
        # total-stable path already makes, not an unbounded phantom injection.
        coll_stable = (reason == "continuity" and len(colls) >= need
                       and max(colls) - min(colls) <= tol
                       and identity_ok and marks_corroborated and entries_match)

        # [2026-07-18] total_stable is the UN-corroborated "concede to a stable
        # total" path. On the RUN-ONCE persisted path it is the false-rebase
        # vector — a persistent phantom total (or a streak stitched across
        # relaunches) rebases with zero mark/entry corroboration (adversarial
        # review, HIGH). The deposit this whole path exists to heal is a
        # COLLATERAL move, which coll_stable (fully corroborated) catches — so a
        # run-once bot heals ONLY via coll_stable and stays equity-blind
        # (recoverable) on a total-only phantom rather than rebasing onto a bad
        # number. total_stable stays for LONG-LIVED bots, whose streak is
        # memory-only and reset by every redeploy (no cross-process stitch).
        allow_total_stable = total_stable and not self._persist_streak

        if len(self._rejects) >= need and (allow_total_stable or coll_stable):
            how = "collateral-stable" if (coll_stable and not allow_total_stable) else "consistent"
            # [2026-07-21 D1] a rebase that moved LEDGER collateral vs the last
            # trusted read is a cash move (the deposit-heal path) — record it
            # before _accept overwrites the baseline. Flat collateral (a
            # model-drift total_stable concession) records nothing.
            _lc = (self._last or {}).get("collateral")
            if collateral is not None and _lc is not None:
                _cap = float(collateral) - float(_lc)
                if abs(_cap) > tol:
                    self._record_capital_move(now, _cap, "rebase-" + how)
            log.error("equity guard: %d consecutive %s rejects — REBASING to "
                      "venue value $%.2f (last: %s).",
                      len(self._rejects), how, venue_total, detail)
            return self._accept(now, venue_total, collateral, mids, held, "rebase")
        # [2026-07-18] a run-once bot persists the growing streak so a relaunch
        # resumes it (`_accept` already persisted the cleared streak on a rebase).
        # A long-lived bot does NOT persist on reject — its streak is memory-only
        # by design (redeploy reset).
        if self._persist_streak:
            self._persist()
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
