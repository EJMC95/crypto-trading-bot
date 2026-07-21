"""Tier 1 — EquityGuard: the dislocation guard on venue equity reads.

The 2026-07-11 incident: Lighter printed a ~-25% dislocated equity while every
held coin's book moved <1%; that print tripped the daily-loss rail and the
flatten sold into the dislocation. This guard exists to reject such a print
BEFORE it reaches the rail. It has an injectable, pure design (mid providers /
clock / persistence) — and had zero coverage. This file exercises every verdict
path: mark-cross-check, forced-fresh re-read, continuity, cash-move escape,
rebase self-heal, the boot double-read, and state restore.
"""
import pytest

from venues import equity_guard as eg
from venues.equity_guard import EquityGuard, EquityRejected, vet_account_read

T = 1_700_000_000.0  # fixed clock


@pytest.fixture(autouse=True)
def _default_env(monkeypatch):
    # Pin the guard's tolerances to their documented pilot defaults so a stray
    # CI env var can't loosen/tighten the bands under the tests.
    for k, v in {
        "LIGHTER_EQUITY_GUARD": "1",
        "LIGHTER_EQUITY_TOL_ABS": "1.0",
        "LIGHTER_EQUITY_TOL_NTL_PCT": "0.01",
        "LIGHTER_EQUITY_TOL_EQ_PCT": "0.002",
        "LIGHTER_EQUITY_REBASE_AFTER": "3",
        "LIGHTER_EQUITY_BOOT_CONFIRM_S": "5",
    }.items():
        monkeypatch.setenv(k, v)


def _guard(cached, fresh=None, **kw):
    """Build a guard with static mid providers and a frozen clock."""
    fresh = cached if fresh is None else fresh
    return EquityGuard(
        mids_cached=lambda coins: {c: cached.get(c) for c in coins},
        mids_fresh=lambda coins: {c: fresh.get(c) for c in coins},
        now=lambda: T,
        **kw,
    )


def _pos(size, entry, upnl=None):
    d = {"size": size, "entry": entry}
    if upnl is not None:
        d["upnl"] = upnl
    return d


# ── disabled / flat ──────────────────────────────────────────────────────────
def test_disabled_passthrough(monkeypatch):
    monkeypatch.setenv("LIGHTER_EQUITY_GUARD", "0")
    g = _guard({"BTC": 100.0})
    v = g.evaluate(999.0, 999.0, {"BTC": _pos(1, 100, upnl=0)})
    assert v.accepted and v.equity == 999.0 and v.reason == "disabled"


def test_flat_account_accepts_and_baselines():
    g = _guard({})
    v = g.evaluate(1000.0, 1000.0, {"BTC": _pos(0.0, 100)})  # zero size = flat
    assert v.accepted and v.reason == "flat"
    assert g.has_state


# ── mark cross-check ─────────────────────────────────────────────────────────
def test_mark_gap_rejects_phantom_print():
    # Book flat at 100, but venue claims -25 unrealized -> marks disagree w/ book.
    g = _guard({"BTC": 100.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert not v.accepted and v.reason == "mark_gap" and v.equity is None


def test_corroborated_crash_is_accepted():
    # A REAL crash: book actually fell to 75, venue upnl -25 agrees -> accept.
    g = _guard({"BTC": 75.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert v.accepted and v.reason == "ok"


def test_forced_fresh_read_rescues_a_fast_crash():
    # Cached ws mid is stale (still 100) so the first judge flags a gap, but the
    # forced-fresh REST read shows the true 75 and the print is corroborated.
    g = _guard(cached={"BTC": 100.0}, fresh={"BTC": 75.0})
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
    assert v.accepted and v.reason == "ok"


# ── continuity ───────────────────────────────────────────────────────────────
def _baseline(g):
    # Establish an accepted read: 1 BTC @100, book 100, equity 100.
    v = g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})
    assert v.accepted
    return g


def test_continuity_rejects_corrupt_total():
    # Same book (mid 100, unchanged size), but the venue total jumps to 75 with
    # no mid move to explain it. upnl omitted so only continuity can fire.
    g = _baseline(_guard({"BTC": 100.0}))
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert not v.accepted and v.reason == "continuity"


def test_cash_move_escape_accepts_a_deposit():
    # Baseline: 1 BTC, book 95, upnl -5, collateral 105, total 100.
    g = _guard({"BTC": 95.0})
    assert g.evaluate(100.0, 105.0, {"BTC": _pos(1, 100, upnl=-5.0)}).accepted
    # Deposit $30: collateral 135, total 130, positions & book unchanged. The
    # jump is fully explained by collateral (ledger-grade) -> ACCEPT not reject.
    v = g.evaluate(130.0, 135.0, {"BTC": _pos(1, 100, upnl=-5.0)})
    assert v.accepted and v.reason == "ok"


def test_deposit_heals_via_collateral_stable_rebase_on_drifting_book():
    # [2026-07-18] The regression that stuck the LIVE Funding Farmer + Ticket
    # Taker at equity=None after a deposit. The raw-total rebase can't fire here
    # because the total drifts with mids (|upnl| swings on the order of tol) while
    # |upnl| stays under tol so the cash-move escape also stays off. The
    # collateral-stable rebase heals it: collateral is fixed at the new balance,
    # so after `rebase_after` consistent continuity rejects the guard re-baselines.
    mids = {"BTC": 100.0}
    g = _guard(mids)   # cached=mids (mutable) so we can drift the book per read
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    accepted = reason = None
    for m in (99.4, 100.6, 99.5):          # wobble < $1 -> |upnl| < tol, total drifts > tol
        mids["BTC"] = m
        upnl = round(m - 100.0, 4)
        v = g.evaluate(round(130.0 + upnl, 4), 130.0, {"BTC": _pos(1, 100, upnl=upnl)})
        accepted, reason = v.accepted, v.reason
    assert accepted and reason == "rebase"
    assert g._last["equity"] == 129.5      # re-baselined at the fresh correct equity


def test_transient_collateral_glitch_shorter_than_rebase_does_not_heal():
    # Persistence gate: a phantom collateral level that reverts within
    # `rebase_after` reads must NOT rebase (it is not a real cash move).
    g = _guard({"BTC": 100.0})
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    for _ in range(2):                     # 2 < rebase_after(3): glitch, not yet trusted
        v = g.evaluate(60.0, 60.0, {"BTC": _pos(1, 100, upnl=0.0)})
        assert not v.accepted and v.reason == "continuity"
    v = g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})   # reverts to truth
    assert v.accepted and v.reason == "ok"
    assert g._last["equity"] == 100.0      # never re-baselined onto the glitch


def test_dark_book_does_not_collateral_stable_rebase():
    # Adversarial-review hole (closed): if mids are dark for every held coin,
    # STEP 1 can't corroborate upnl, so total == collateral + upnl is only a
    # venue-INTERNAL identity a phantom upnl move satisfies. The collateral-stable
    # rebase must NOT fire — the bot stays equity-unreadable rather than trusting
    # an uncorroborated total.
    g = _guard(cached={})                  # no mids, ever
    assert g.evaluate(1000.0, 1000.0, {"BTC": _pos(1, 1000, upnl=0.0)}).accepted
    # collateral held stable at 1000, but total wanders via a phantom upnl
    for total, upnl in ((800.0, -200.0), (760.0, -240.0), (830.0, -170.0)):
        v = g.evaluate(total, 1000.0, {"BTC": _pos(1, 1000, upnl=upnl)})
        assert not v.accepted and v.reason == "continuity"
    assert g._last["equity"] == 1000.0     # never rebased onto the phantom


def test_partial_darkness_phantom_leg_does_not_rebase():
    # Adversarial-review hole (closed): a tiny-notional coin kept dark can carry
    # an UNBOUNDED phantom upnl past STEP 1 while a big readable coin makes the
    # notional coverage look ~full. The rebase requires EVERY held coin's mid to
    # be readable, so a single dark leg blocks it.
    mids = {"A": 1000.0}                    # coin B has no mid -> dark
    g = _guard(mids)
    base = {"A": _pos(0.1, 1000, upnl=0.0), "B": _pos(0.002, 500, upnl=0.0)}
    assert g.evaluate(100.0, 100.0, base).accepted
    # collateral stable at 100; B injects a growing phantom upnl; A stays true
    for tot, ub in ((110.0, 10.0), (120.0, 20.0), (130.0, 30.0)):
        pos = {"A": _pos(0.1, 1000, upnl=0.0), "B": _pos(0.002, 500, upnl=ub)}
        v = g.evaluate(tot, 100.0, pos)
        assert not v.accepted and v.reason == "continuity"
    assert g._last["equity"] == 100.0      # phantom on the dark leg never trusted


def test_legacy_restore_without_entries_still_heals_deposit():
    # A guard restored from a PRE-FIX snapshot (no 'entries' key) must still heal
    # a deposit — otherwise this fix would re-strand the currently-stuck bots on
    # the very deploy that ships it. entries_match degrades gracefully until the
    # first fresh accept records entries.
    st = {"ts": T - 600.0, "equity": 100.0, "collateral": 100.0,
          "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}}     # legacy: no 'entries'
    mids = {"BTC": 100.0}
    g = _guard(mids, load_state=lambda: st)
    assert g.has_state and not g._last.get("entries")        # restored without entries
    accepted = reason = None
    for m in (99.4, 100.6, 99.5):
        mids["BTC"] = m
        upnl = round(m - 100.0, 4)
        v = g.evaluate(round(130.0 + upnl, 4), 130.0, {"BTC": _pos(1, 100, upnl=upnl)})
        accepted, reason = v.accepted, v.reason
    assert accepted and reason == "rebase"      # healed despite the missing baseline entries


def test_entry_corruption_phantom_does_not_rebase():
    # Adversarial-review hole (closed): STEP 1's gap cancels entry, so a venue
    # that lowers a held position's reported ENTRY and raises its upnl by the
    # matching amount keeps gap=0 (passes the mark check) while injecting an
    # unbounded phantom into total = collateral + sum(upnl). A held entry is
    # fixed, so the rebase requires it match the trusted baseline entry.
    mids = {"A": 50.0, "B": 100.0}
    g = _guard(mids)
    base = {"A": _pos(2, 50, upnl=0.0), "B": _pos(1, 100, upnl=0.0)}
    assert g.evaluate(200.0, 200.0, base).accepted   # equity 200 = collateral 200
    # collateral stable 200; A's real mid rises; B injects a phantom via a
    # LOWERED reported entry (100->70) with matching upnl so gap_B stays 0.
    for amid in (55.0, 60.0, 65.0):
        mids["A"] = amid
        ua = round(2 * (amid - 50.0), 4)             # A's real upnl
        pos = {"A": _pos(2, 50, upnl=ua),
               "B": _pos(1, 70, upnl=30.0)}          # entry 100->70, phantom upnl +30
        v = g.evaluate(round(200.0 + ua + 30.0, 4), 200.0, pos)
        assert not v.accepted and v.reason == "continuity"
    assert g._last["equity"] == 200.0      # phantom via corrupted entry never trusted


def test_corrupt_total_with_unchanged_collateral_still_rejects():
    # The dislocation this guard exists for: total_asset_value jumps but
    # collateral does NOT move to explain it -> the mark-verified escape must
    # NOT fire (d_total != d_collateral).
    g = _guard({"BTC": 100.0})
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    v = g.evaluate(70.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})  # collateral unchanged
    assert not v.accepted and v.reason == "continuity"


def test_deposit_without_verified_marks_still_rejects():
    # A collateral-matched jump but the marks were NOT verifiable (book mids
    # unreadable this read) and |upnl| is small -> no positive cash evidence,
    # so it must still reject rather than accept an unverified equity.
    g = _guard(cached={})                     # no mids readable at all
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    v = g.evaluate(130.0, 130.0, {"BTC": _pos(1, 100, upnl=0.0)})
    assert not v.accepted and v.reason == "continuity"


# ── rebase self-heal ─────────────────────────────────────────────────────────
def test_continuity_rebases_after_consistent_rejects():
    g = _baseline(_guard({"BTC": 100.0}))
    # rebase_after=3: two rejects, then the third consistent print rebases.
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)}).reason == "continuity"
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)}).reason == "continuity"
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert v.accepted and v.reason == "rebase" and v.equity == 75.0


def test_mark_gap_needs_4x_more_rejects_to_rebase():
    # mark_gap carries live counter-evidence, so its rebase bar is 4x higher:
    # three consistent mark-gap rejects must NOT rebase (still rejected).
    g = _guard({"BTC": 100.0})
    for _ in range(3):
        v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})
        assert not v.accepted and v.reason == "mark_gap"


# ── tolerance ────────────────────────────────────────────────────────────────
def test_tolerance_is_max_of_the_three_bands():
    g = _guard({})
    # abs floor dominates for tiny books
    assert g.tolerance(10.0, 10.0) == 1.0
    # notional band: 1% of gross
    assert g.tolerance(1000.0, 100.0) == pytest.approx(10.0)
    # equity band: 0.2% of |equity|
    assert g.tolerance(100.0, 10000.0) == pytest.approx(20.0)


# ── vet_account_read: boot double-read + wiring ──────────────────────────────
def test_vet_disabled_returns_raw(monkeypatch):
    monkeypatch.setenv("LIGHTER_EQUITY_GUARD", "0")
    g = _guard({"BTC": 100.0})
    got = vet_account_read(g, lambda: (123.0, 123.0, {}), sleep=lambda s: None)
    assert got == 123.0


def test_vet_cold_boot_double_reads():
    g = _guard({"BTC": 100.0})
    calls = {"fetch": 0, "slept": []}

    def fetch():
        calls["fetch"] += 1
        return (100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})

    got = vet_account_read(g, fetch, sleep=lambda s: calls["slept"].append(s))
    assert got == 100.0
    assert calls["fetch"] == 2          # boot demands two agreeing reads
    assert calls["slept"] == [5.0]      # spaced by boot_confirm_s


def test_vet_cold_boot_rejects_before_sleeping():
    g = _guard({"BTC": 100.0})
    slept = []

    def fetch():
        return (75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})  # dislocated

    with pytest.raises(EquityRejected):
        vet_account_read(g, fetch, sleep=lambda s: slept.append(s))
    assert slept == []                  # never slept — rejected on first read


def test_vet_warm_state_single_read():
    g = _baseline(_guard({"BTC": 100.0}))  # already has state
    calls = {"fetch": 0}

    def fetch():
        calls["fetch"] += 1
        return (100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})

    got = vet_account_read(g, fetch, sleep=lambda s: pytest.fail("should not sleep"))
    assert got == 100.0 and calls["fetch"] == 1


# ── persisted-state restore ──────────────────────────────────────────────────
def test_state_restore_within_age():
    st = {"ts": T - 3600.0, "equity": 100.0, "collateral": 100.0,
          "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}}
    g = _guard({"BTC": 100.0}, load_state=lambda: st)
    assert g.has_state and g._last["equity"] == 100.0


def test_state_restore_ignores_stale_snapshot():
    st = {"ts": T - 8 * 86400.0, "equity": 100.0, "collateral": 100.0,
          "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}}
    g = _guard({"BTC": 100.0}, load_state=lambda: st)
    assert not g.has_state           # >7d old snapshot proves nothing about today


# ── run-once relaunch: the reject STREAK must survive the process boundary ────
# [2026-07-18] The Ticket-Taker half of the deposit incident. The Taker is
# RUN-ONCE (tickettaker_loop.sh: `python3 lighter_ticket_taker.py; sleep 300`),
# so every cycle rebuilds the guard and self._rejects resets to []. Before the
# streak was persisted, the N-consecutive-rejects rebase could NEVER reach N —
# a legit deposit left the bot equity-blind (and its daily-loss rail off, since
# that needs a non-None equity) forever, while the Farmer (a while-True process
# with a long-lived guard) healed in minutes. These model the process boundary
# with a fresh guard per cycle sharing ONE persisted store.
class _Store:
    """A dict-backed persistence like bot_state, round-tripping through JSON so
    the reject tuples degrade to lists exactly as bot_pnl_store.save_state does."""
    def __init__(self, initial=None):
        import json
        self.blob = None if initial is None else json.loads(json.dumps(initial))

    def load(self):
        return self.blob

    def save(self, st):
        import json
        self.blob = json.loads(json.dumps(st))


def _run_once_guard(cached, store, fresh=None, **kw):
    """A guard as the RUN-ONCE Ticket Taker builds it (persist_reject_streak=True):
    the reject streak survives across relaunches. Each call models one fresh
    process reading a shared store."""
    return _guard(cached, fresh=fresh, load_state=store.load, save_state=store.save,
                  persist_reject_streak=True, **kw)


def test_run_once_relaunch_resumes_streak_and_heals_deposit():
    store = _Store()
    mids = {"BTC": 100.0}
    # cycle 0: an accepted baseline (pre-deposit) persists the last-accepted read.
    g0 = _run_once_guard(mids, store)
    assert g0.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    assert store.blob is not None and store.blob["rejects"] == []
    # deposit lands; each RELAUNCH is a brand-new guard reading the shared store.
    # The book drifts so the raw-total rebase can't fire — only the persisted
    # COLLATERAL-stable streak can heal it, and only if the streak crosses the
    # process boundary. Pre-fix this loop rejected forever.
    outcome = None
    for m in (99.4, 100.6, 99.5):
        mids["BTC"] = m
        upnl = round(m - 100.0, 4)
        g = _run_once_guard(mids, store)
        assert g.has_state                       # last-accepted restored each relaunch
        outcome = g.evaluate(round(130.0 + upnl, 4), 130.0,
                             {"BTC": _pos(1, 100, upnl=upnl)})
    assert outcome.accepted and outcome.reason == "rebase"   # healed ACROSS processes
    assert store.blob["rejects"] == []           # rebase cleared the persisted streak
    assert store.blob["last"]["equity"] == 129.5


def test_long_lived_guard_does_not_persist_reject_streak():
    # [2026-07-18] Funding Farmer regression guard (adversarial review, HIGH). A
    # long-lived bot's streak is memory-only and MUST reset on every redeploy;
    # persisting it would let a dislocation spanning a `railway up` rebase onto a
    # phantom. Persistence defaults OFF; the blob stays the flat last-accepted
    # shape and no reject is ever written, so a relaunch resets the count.
    store = _Store()
    g0 = _guard({"BTC": 100.0}, load_state=store.load, save_state=store.save)  # flag default False
    assert g0.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    assert "rejects" not in store.blob and store.blob.get("equity") == 100.0   # FLAT shape
    for _ in range(4):                           # a dislocation across 4 relaunches
        g = _guard({"BTC": 100.0}, load_state=store.load, save_state=store.save)
        v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})    # continuity phantom
        assert not v.accepted and v.reason == "continuity"    # never rebases across boundary
        assert "rejects" not in store.blob                    # streak never persisted


def test_run_once_does_not_launder_mark_gap_into_continuity_rebase():
    # [2026-07-18] Adversarial review (HIGH). Persisted high-bar mark_gap rejects
    # must not be counted at the low continuity bar. Two mark_gap rejects across
    # relaunches, then a continuity read (a mid goes dark): the reason change
    # resets the streak, so it must NOT rebase onto the phantom.
    store = _Store()
    g0 = _run_once_guard({"BTC": 100.0}, store)
    assert g0.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    for _ in range(2):                            # book flat 100, venue phantom -25
        g = _run_once_guard({"BTC": 100.0}, store)
        assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)}).reason == "mark_gap"
    g = _run_once_guard({}, store)                # BTC mid dark -> continuity, total still 75
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert not v.accepted                          # phantom NOT laundered into a rebase
    assert g._last["equity"] == 100.0              # never re-baselined onto 75


def test_run_once_refuses_total_stable_phantom_without_corroboration():
    # [2026-07-18] FIX C: the run-once path heals ONLY via the corroborated
    # coll_stable, never via bare total_stable. A stable phantom total with an
    # UNREADABLE book (no mark corroboration) must keep the bot equity-blind.
    store = _Store()
    g0 = _run_once_guard({"BTC": 100.0}, store)
    assert g0.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    for _ in range(4):                            # well past rebase_after
        g = _run_once_guard({}, store)            # book dark every cycle
        v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})   # total stuck 75, stable
        assert not v.accepted and v.reason == "continuity"
    assert store.blob["last"]["equity"] == 100.0  # never rebased onto the phantom


def test_reason_change_resets_the_streak():
    # [2026-07-18] A streak is "N consecutive SELF-CONSISTENT rejects": a reason
    # change resets it, so mark_gap and continuity rejects never mix in one
    # rebase window (this fires on the in-memory path too, not just persisted).
    g = _baseline(_guard({"BTC": 100.0}))
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)}).reason == "mark_gap"
    assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)}).reason == "mark_gap"
    assert len(g._rejects) == 2
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})    # upnl absent -> continuity
    assert v.reason == "continuity"
    assert len(g._rejects) == 1                   # reset on the reason change, not 3
    assert not v.accepted                          # so it does NOT rebase at need=3


def test_stale_persisted_reject_streak_is_dropped():
    # A reject streak whose newest reject is older than the max gap is not
    # 'consecutive' with a fresh read and must not count toward a rebase.
    old = T - eg._REJECT_STREAK_MAX_GAP_S - 1.0
    store = _Store({
        "last": {"ts": T - 100.0, "equity": 130.0, "collateral": 130.0,
                 "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0},
                 "entries": {"BTC": 100.0}},
        "rejects": [[old, 130.0, 130.0, "continuity"],
                    [old, 130.0, 130.0, "continuity"]],
    })
    g = _run_once_guard({"BTC": 100.0}, store)
    assert g.has_state                # last-accepted still restored (within 7d)
    assert g._rejects == []           # stale streak dropped — starts the count fresh


def test_persisted_streak_breaks_on_a_wide_gap():
    # Two rejects separated by more than the max gap are not 'consecutive': only
    # the contiguous recent run survives, so a dead episode can't be stitched to
    # a fresh reject a relaunch later.
    store = _Store({
        "last": {"ts": T - 100.0, "equity": 130.0, "collateral": 130.0,
                 "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}, "entries": {"BTC": 100.0}},
        "rejects": [[T - eg._REJECT_STREAK_MAX_GAP_S - 100.0, 130.0, 130.0, "continuity"],
                    [T - 50.0, 130.0, 130.0, "continuity"]],
    })
    g = _run_once_guard({"BTC": 100.0}, store)
    assert [r[0] for r in g._rejects] == [T - 50.0]   # only the recent reject survived


def test_accept_clears_persisted_reject_streak():
    # A transient reject episode that resolves must not leave a lingering streak
    # in the store that a later, unrelated reject could ride to a false rebase.
    store = _Store()
    g1 = _run_once_guard({"BTC": 100.0}, store)
    assert g1.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    g2 = _run_once_guard({"BTC": 100.0}, store)
    assert not g2.evaluate(70.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    assert store.blob["rejects"]                 # one reject persisted
    g3 = _run_once_guard({"BTC": 100.0}, store)
    assert g3.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    assert store.blob["rejects"] == []           # cleared on the next accept


def test_new_wrapped_blob_restores_last_accepted():
    # The last-accepted read must restore from the new {"last":…, "rejects":…}
    # shape just as it did from the old flat blob.
    store = _Store({
        "last": {"ts": T - 300.0, "equity": 100.0, "collateral": 100.0,
                 "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0},
                 "entries": {"BTC": 100.0}},
        "rejects": [],
    })
    g = _run_once_guard({"BTC": 100.0}, store)
    assert g.has_state and g._last["equity"] == 100.0 and g._last["entries"] == {"BTC": 100.0}


# ── legacy no-entries blob on the RUN-ONCE path: the deploy-blocker pair ──────
# [2026-07-18] Adversarial review (HIGH/CRITICAL, reproduced end-to-end): the
# live Taker's first post-deploy blob is the OLD flat shape with no `entries`,
# so entries_match degraded to True and an entry+upnl lockstep phantom rebased
# +13% into the daily-loss rail. The discriminator that closes it: a genuine
# deposit MOVES ledger collateral away from the trusted baseline; the lockstep
# phantom keeps collateral flat (its injection rides upnl). These two tests are
# the REQUIRED pair — the phantom must reject AND the honest deposit must heal;
# a fix that trades one for the other reintroduces a closed incident.
_LEGACY_2COIN = {"ts": T - 600.0, "equity": 200.0, "collateral": 200.0,
                 "mids": {"A": 50.0, "B": 100.0}, "sizes": {"A": 2.0, "B": 1.0}}


def test_legacy_blob_run_once_entry_corruption_phantom_rejects():
    # Baseline (legacy, no entries): 2 A @50 + 1 B @100, equity=collateral=200.
    # Venue corrupts B's entry 100->70 with matching phantom upnl +30 (STEP 1's
    # gap stays 0); collateral held FLAT at 200. Each relaunch is a fresh guard
    # sharing the store. Must never rebase onto the phantom.
    store = _Store(dict(_LEGACY_2COIN))
    mids = {"A": 50.0, "B": 100.0}
    for amid in (55.0, 60.0, 65.0, 70.0):
        mids["A"] = amid
        ua = round(2 * (amid - 50.0), 4)               # A's real upnl
        pos = {"A": _pos(2, 50, upnl=ua),
               "B": _pos(1, 70, upnl=30.0)}            # corrupted entry + phantom
        g = _run_once_guard(mids, store)
        v = g.evaluate(round(200.0 + ua + 30.0, 4), 200.0, pos)
        assert not v.accepted, "lockstep phantom must NOT rebase on a legacy blob"
    # the trusted baseline never moved onto the phantom
    blob = store.blob
    last = blob.get("last") if isinstance(blob, dict) and "last" in blob else blob
    assert last["equity"] == 200.0


def test_legacy_blob_run_once_honest_deposit_still_heals():
    # Same legacy no-entries shape, but an HONEST $30 deposit: collateral moves
    # 100 -> 130 (ledger cash), book drifts so only coll_stable can heal. The
    # discriminator must let this through — collateral moved from baseline.
    store = _Store({"ts": T - 600.0, "equity": 100.0, "collateral": 100.0,
                    "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}})
    mids = {"BTC": 100.0}
    outcome = None
    for m in (99.4, 100.6, 99.5):
        mids["BTC"] = m
        upnl = round(m - 100.0, 4)
        g = _run_once_guard(mids, store)
        assert g.has_state and not g._last.get("entries")   # legacy: no entries
        outcome = g.evaluate(round(130.0 + upnl, 4), 130.0,
                             {"BTC": _pos(1, 100, upnl=upnl)})
    assert outcome.accepted and outcome.reason == "rebase"
    # and the healing rebase re-armed entry verification for the next episode
    assert store.blob["last"]["entries"] == {"BTC": 100.0}


def test_future_timestamped_reject_does_not_break_streak_restore():
    # A future-stamped reject (clock skew / corrupt blob) must be dropped, not
    # anchor the walk and orphan the genuine recent streak behind it.
    store = _Store({
        "last": {"ts": T - 600.0, "equity": 130.0, "collateral": 130.0,
                 "mids": {"BTC": 100.0}, "sizes": {"BTC": 1.0}, "entries": {"BTC": 100.0}},
        "rejects": [[T - 300.0, 130.0, 130.0, "continuity"],
                    [T - 20.0, 130.0, 130.0, "continuity"],
                    [T + 7200.0, 130.0, 130.0, "continuity"]],   # future junk
    })
    g = _run_once_guard({"BTC": 100.0}, store)
    assert [r[0] for r in g._rejects] == [T - 300.0, T - 20.0]


# ── flag wiring: run-once bots opt in, long-lived bots stay memory-only ───────
def test_persist_flag_wiring():
    """The persist flag is load-bearing at three sites; none is covered by any
    runtime test (the live client needs the signer SDK), so pin the wiring:
      * EquityGuard defaults persist_reject_streak=False (long-lived-safe);
      * LighterClient defaults guard_persist_reject_streak=False and threads it
        into the guard;
      * the Ticket Taker (run-once) passes it; venue_context (the Funding
        Farmer's path) does NOT, so the Farmer keeps the default False."""
    import inspect
    from pathlib import Path
    import venues.lighter_client as lc

    assert inspect.signature(EquityGuard.__init__).parameters[
        "persist_reject_streak"].default is False
    assert inspect.signature(lc.LighterClient.__init__).parameters[
        "guard_persist_reject_streak"].default is False
    assert "persist_reject_streak=self._guard_persist_reject_streak" in \
        inspect.getsource(lc.LighterClient._make_guard)

    root = Path(__file__).resolve().parent.parent.parent
    taker_src = (root / "lighter_ticket_taker.py").read_text(encoding="utf-8")
    assert "guard_persist_reject_streak=live" in taker_src, \
        "the run-once Ticket Taker must opt in to streak persistence"
    ctx_src = (root / "venues" / "__init__.py").read_text(encoding="utf-8")
    assert "guard_persist_reject_streak" not in ctx_src, \
        "venue_context (Funding Farmer) must keep the default False"


# ── capital moves: deposits/withdrawals are NOT P&L ──────────────────────────
# [2026-07-21 review N1] The (ao) heal restored equity CONTINUITY after the
# 18-Jul deposits but nothing moved the P&L baseline, so both live rows printed
# the operator's ~$32 deposits as profit (+$64.77 of the dashboard's +$68.46).
# The guard is the only layer holding the last TRUSTED collateral, so it now
# records the ledger-grade delta on every cash-accepting path; the bots pop and
# fold it into their persisted capital ledger and pnl_abs subtracts it.
def test_cash_escape_records_capital_move():
    # the escape path: deposit $30 accepted immediately (collateral 105 -> 135)
    g = _guard({"BTC": 95.0})
    assert g.evaluate(100.0, 105.0, {"BTC": _pos(1, 100, upnl=-5.0)}).accepted
    assert g.pop_capital_moves() == []            # baseline accept records nothing
    v = g.evaluate(130.0, 135.0, {"BTC": _pos(1, 100, upnl=-5.0)})
    assert v.accepted
    moves = g.pop_capital_moves()
    assert len(moves) == 1 and moves[0]["delta"] == pytest.approx(30.0)
    assert moves[0]["how"] == "cash-escape"
    assert g.pop_capital_moves() == []            # pop clears

def test_cash_escape_records_a_withdrawal_negative():
    g = _guard({"BTC": 95.0})
    assert g.evaluate(100.0, 105.0, {"BTC": _pos(1, 100, upnl=-5.0)}).accepted
    v = g.evaluate(70.0, 75.0, {"BTC": _pos(1, 100, upnl=-5.0)})
    assert v.accepted
    moves = g.pop_capital_moves()
    assert len(moves) == 1 and moves[0]["delta"] == pytest.approx(-30.0)

def test_flat_to_flat_deposit_records_capital_move():
    # [2026-07-21 D1 gap] deposit landing while FLAT: two consecutive flat
    # reads, ledger collateral jumps $32 — capital, not P&L. The frequently-
    # flat Taker is the book this protects.
    g = _guard({})
    assert g.evaluate(100.0, 100.0, {}).accepted     # flat baseline
    assert g.pop_capital_moves() == []
    v = g.evaluate(132.0, 132.0, {})                 # flat + $32 deposit
    assert v.accepted and v.reason == "flat"
    moves = g.pop_capital_moves()
    assert len(moves) == 1 and moves[0]["delta"] == pytest.approx(32.0)
    assert moves[0]["how"] == "flat-cash"

def test_flat_to_flat_withdrawal_records_negative():
    g = _guard({})
    assert g.evaluate(100.0, 100.0, {}).accepted
    v = g.evaluate(70.0, 70.0, {})
    assert v.accepted
    moves = g.pop_capital_moves()
    assert len(moves) == 1 and moves[0]["delta"] == pytest.approx(-30.0)

def test_flat_to_flat_dust_records_nothing():
    # inside tolerance (tol_abs $1): no capital event
    g = _guard({})
    assert g.evaluate(100.0, 100.0, {}).accepted
    assert g.evaluate(100.6, 100.6, {}).accepted
    assert g.pop_capital_moves() == []

def test_held_to_flat_records_nothing():
    # the close's realized P&L moves collateral between a HELD read and a
    # flat read — that is trading, not capital; the flat-cash path must not
    # fire when the last accepted read had positions.
    g = _guard({"BTC": 100.0})
    assert g.evaluate(95.0, 95.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    assert g.evaluate(104.0, 104.0, {}).accepted     # closed; realized moved cash
    assert g.pop_capital_moves() == []

def test_collateral_stable_rebase_records_capital_move():
    # the (ao) heal path: deposit heals via coll_stable on a drifting book —
    # the recorded delta is collateral vs the LAST TRUSTED read (100 -> 130).
    mids = {"BTC": 100.0}
    g = _guard(mids)
    assert g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)}).accepted
    for m in (99.4, 100.6, 99.5):
        mids["BTC"] = m
        upnl = round(m - 100.0, 4)
        v = g.evaluate(round(130.0 + upnl, 4), 130.0, {"BTC": _pos(1, 100, upnl=upnl)})
    assert v.accepted and v.reason == "rebase"
    moves = g.pop_capital_moves()
    assert len(moves) == 1 and moves[0]["delta"] == pytest.approx(30.0)
    assert moves[0]["how"].startswith("rebase-")

def test_flat_collateral_rebase_records_no_capital_move():
    # a total-stable concession to model drift (collateral NEVER moved) is not
    # a cash move — recording it would misclassify P&L as capital, the inverse
    # of the bug this fixes.
    g = _baseline(_guard({"BTC": 100.0}))
    for _ in range(2):
        assert g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)}).reason == "continuity"
    v = g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100)})
    assert v.accepted and v.reason == "rebase"    # concedes to the stable total
    assert g.pop_capital_moves() == []            # …but records NO capital move

def test_ordinary_reads_record_no_capital_moves():
    g = _baseline(_guard({"BTC": 100.0}))
    g.evaluate(100.0, 100.0, {"BTC": _pos(1, 100, upnl=0.0)})       # accept
    g.evaluate(75.0, 100.0, {"BTC": _pos(1, 100, upnl=-25.0)})      # mark_gap reject
    assert g.pop_capital_moves() == []

def test_capital_adjust_wiring():
    """Pin the consumer wiring the runtime tests can't reach (both live bots'
    main loops need a signer): each live bot pops the guard's capital moves,
    persists the ledger, and subtracts capital from its published pnl."""
    from pathlib import Path
    import venues.lighter_client as lc
    import inspect
    assert "pop_capital_moves" in inspect.getsource(lc.LighterClient)
    root = Path(__file__).resolve().parent.parent.parent
    for fname in ("lighter_funding_bot.py", "lighter_ticket_taker.py"):
        src = (root / fname).read_text(encoding="utf-8")
        assert "pop_capital_moves" in src, f"{fname} must fold guard capital moves"
        assert "capital_adjust" in src, f"{fname} must persist the capital ledger"
        assert "CAPITAL_ADJUST_USD" in src, f"{fname} must honor the env backfill"
