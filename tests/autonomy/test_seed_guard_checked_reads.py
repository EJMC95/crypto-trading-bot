"""The seed-on-failed-read class, closed for the living books' boot restores.

[2026-08-04] `bot_pnl_store.load_state()` collapses "no row" and "READ FAILED"
into the same None. Any bot that boots `load_state(bot_id) or fresh` and then
save_state()s every loop turns a Postgres blip into a SEEDED fresh book whose
very next save OVERWRITES the durable record — the 17-Jul perp-sniper
incident. The 4-Aug fleet review found the shape still live in Counterweight,
Index Rider and the Family books; the grep this file now enforces found it in
two MORE living books the review's matrix missed (🌾 carry's shadow arm and
🧲 Snap Back). Fixing instances is not closing the class — this file is the
class closure.

Three layers, mirroring how the bugs actually appear:

  1. THE SHARED DEGRADE (`bot_pnl_store.load_state_required`) behaves: no DB
     configured -> fresh (nothing durable exists, and nothing CAN be
     overwritten — save_state needs the same DB); clean read -> the state;
     persistent read failure -> SystemExit, never a seed.
  2. THE FAMILY BOOK restores a payload ITS OWN persist() built — never a
     hand-written fixture, per (hj) — and while the state is unreadable it
     neither seeds nor persists.
  3. THE WIRING, by AST (a page-wide substring scan is not a structural
     claim): no shipped living book reads its own key through the unchecked
     `load_state`. A retired book is a DECLARED exemption with a reason, not a
     silent hole.
"""
import ast
import json
import os
import types

import pytest

import bot_pnl_store as store

pytestmark = pytest.mark.autonomy

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# 1. The shared degrade: load_state_required
# ---------------------------------------------------------------------------

def test_required_no_db_is_fresh_and_reads_nothing(monkeypatch):
    """With no DATABASE_URL the helper answers None immediately — local smoke
    runs and inert backtests must keep working, and with no DB the write path
    cannot overwrite anything, so a fresh in-memory book is safe."""
    monkeypatch.setattr(store, "_DATABASE_URL", "")
    monkeypatch.setattr(store, "load_state_checked",
                        lambda bot: pytest.fail("no-DB path must not read"))
    assert store.load_state_required("any-bot") is None


def test_required_passes_a_clean_read_through(monkeypatch):
    monkeypatch.setattr(store, "_DATABASE_URL", "postgres://x")
    monkeypatch.setattr(store, "load_state_checked",
                        lambda bot: (True, {"positions": {"BTC": 1}}))
    assert store.load_state_required("b") == {"positions": {"BTC": 1}}
    # genuinely-no-row is a legitimate first run, not a refusal
    monkeypatch.setattr(store, "load_state_checked", lambda bot: (True, None))
    assert store.load_state_required("b") is None


def test_required_refuses_after_persistent_read_failure(monkeypatch):
    """The teeth: a read that keeps failing is a REFUSAL (SystemExit), never a
    fresh book. Mutating the helper to fall through to `saved` reddens here."""
    monkeypatch.setattr(store, "_DATABASE_URL", "postgres://x")
    calls = []
    monkeypatch.setattr(store, "load_state_checked",
                        lambda bot: calls.append(1) or (False, None))
    with pytest.raises(SystemExit):
        store.load_state_required("b", tries=3, sleep_s=0)
    assert len(calls) == 3, "every configured try must actually be attempted"


def test_required_recovers_when_the_blip_clears(monkeypatch):
    monkeypatch.setattr(store, "_DATABASE_URL", "postgres://x")
    seq = [(False, None), (True, {"meta": {"SPY": {}}})]
    monkeypatch.setattr(store, "load_state_checked", lambda bot: seq.pop(0))
    assert store.load_state_required("b", tries=3, sleep_s=0) == {
        "meta": {"SPY": {}}}


# ---------------------------------------------------------------------------
# 2. The family Book: publisher-built payload round-trip + the two refusals
# ---------------------------------------------------------------------------

def _mk_book():
    import lighter_family_bot as fam
    strat = fam.TrendMomo("test-family", tf="1d", stoploss=-0.15, max_open=4,
                          style="trendmomo-1d")
    return fam, fam.Book(strat, types.SimpleNamespace(), ["BTC"])


def test_family_failed_read_blocks_both_seed_and_persist(monkeypatch):
    fam, b = _mk_book()
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setattr(fam.store, "fetch_paper_aggregate", lambda bot: None)
    monkeypatch.setattr(fam.store, "load_daily_halt", lambda bot, day: False)
    monkeypatch.setattr(fam.store, "load_state_checked",
                        lambda bot: (False, None))
    written = []
    monkeypatch.setattr(fam.store, "save_state",
                        lambda bot, st: written.append((bot, st)) or True)

    b.restore()
    assert not b._restored, "a failed read must NOT count as restored"
    b.persist()
    assert not written, ("persist() wrote through a failed read — the exact "
                         "overwrite the guard exists to stop")

    # the blip clears -> the retry path restores and persistence resumes
    monkeypatch.setattr(fam.store, "load_state_checked", lambda bot: (True, None))
    b.restore()
    assert b._restored
    b.persist()
    assert len(written) == 1 and written[0][0] == "test-family-lshadow"


def test_family_no_db_boots_fresh(monkeypatch):
    """Local smoke (`--once` with no DATABASE_URL) must not deadlock every
    book into the un-restored skip branch."""
    fam, b = _mk_book()
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setattr(fam.store, "fetch_paper_aggregate", lambda bot: None)
    monkeypatch.setattr(fam.store, "load_daily_halt", lambda bot, day: False)
    monkeypatch.setattr(fam.store, "load_state_checked",
                        lambda bot: pytest.fail("no-DB restore must not read"))
    b.restore()
    assert b._restored


def test_family_restores_the_payload_its_own_persist_built(monkeypatch):
    """(hj): the consumer is tested against a payload its publisher built.
    Book #1's persist() writes the state; Book #2 restores it through the
    real JSON boundary (json_safe + dumps/loads, exactly what Postgres jsonb
    hands back) and must come out non-degenerate."""
    fam, b1 = _mk_book()
    monkeypatch.setenv("DATABASE_URL", "postgres://x")
    monkeypatch.setattr(fam.store, "fetch_paper_aggregate", lambda bot: None)
    monkeypatch.setattr(fam.store, "load_daily_halt", lambda bot, day: False)

    b1._restored = True                      # a clean boot, already read
    b1.broker.realized = 12.5
    b1.broker.pos = {"BTC": (0.01, 50_000.0)}
    b1.broker.marks = {"BTC": 51_000.0}
    b1.meta = {"BTC": {"entry": 50_000.0, "opened_ts": 123.0,
                       "tag": "trend_up", "accrued": -0.02}}
    b1.closed = [{"ts": 1.0, "pnl": 2.0, "pct": 0.01, "stop": False,
                  "pair": "BTC"}]
    b1.cooldown = {"BTC": 999.0}
    b1.guard_until = 555.0
    b1.fund_realized = -0.75
    b1.last_accrue = 1_700_000_000.0

    captured = {}
    monkeypatch.setattr(fam.store, "save_state",
                        lambda bot, st: captured.update(st) or True)
    b1.persist()
    assert captured, "persist() published nothing to capture"
    payload = json.loads(json.dumps(store.json_safe(captured)))

    fam2, b2 = _mk_book()
    monkeypatch.setattr(fam2.store, "load_state_checked",
                        lambda bot: (True, payload))
    b2.restore()
    assert b2._restored
    assert b2.broker.realized == 12.5
    assert b2.broker.pos == {"BTC": (0.01, 50_000.0)}
    assert b2.meta["BTC"]["tag"] == "trend_up"
    assert b2.cooldown == {"BTC": 999.0}
    assert b2.guard_until == 555.0
    assert b2.fund_realized == -0.75
    # the accrual clock came back bounded, not reset to boot time
    assert b2.last_accrue >= 1_700_000_000.0 - 1


# ---------------------------------------------------------------------------
# 3. The wiring, by AST: no living book's own-key restore uses the
#    unchecked read. This is the arm that keeps the class closed.
# ---------------------------------------------------------------------------

# Every living book that restores durable state at boot. A NEW book that
# save_state()s belongs in this list the day it ships.
GUARDED_BOOKS = [
    "funding_carry_bot.py",
    "lighter_dislocation_bot.py",
    "lighter_family_bot.py",
    "lighter_funding_spread_bot.py",
    "lighter_index_bot.py",
    "lighter_perp_sniper.py",
]

# Declared exemptions, with reasons — silence is not an option (BORN_DARK_OK
# idiom). A resurrection commit must MOVE the file into GUARDED_BOOKS.
RETIRED_OK = {
    "lighter_trend_bot.py": "🌊 Tide Rider RETIRED 1-Aug (if) — idles at boot "
                            "behind TIDE_RIDER_RETIRED_OVERRIDE; its restore "
                            "code cannot run in production.",
}


def _own_key_load_state_calls(tree):
    """Calls of `<anything>.load_state(arg)` whose arg involves `bot_id` —
    the self-restore shape. Literal-keyed reads (cross-organ consumption like
    load_state("market-pulse")) and constant-keyed gate reads (GOLIVE_KEY)
    are a different, fail-safe class and stay allowed."""
    hits = []
    for node in ast.walk(tree):
        if (isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "load_state" and node.args):
            for sub in ast.walk(node.args[0]):
                if ((isinstance(sub, ast.Name) and sub.id == "bot_id")
                        or (isinstance(sub, ast.Attribute)
                            and sub.attr == "bot_id")):
                    hits.append(node.lineno)
                    break
    return hits


def _uses_a_checked_read(tree):
    return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr in ("load_state_required", "load_state_checked")
               for n in ast.walk(tree))


@pytest.mark.parametrize("fname", GUARDED_BOOKS)
def test_no_living_book_restores_through_the_unchecked_read(fname):
    tree = ast.parse(open(os.path.join(ROOT, fname)).read())
    bad = _own_key_load_state_calls(tree)
    assert not bad, (
        f"{fname}:{bad} restores its own durable state through the UNCHECKED "
        f"load_state — a Postgres blip seeds a fresh book and the next "
        f"save_state overwrites the record. Use store.load_state_required "
        f"(single-book daemon) or load_state_checked + a persist gate "
        f"(multi-book container).")
    assert _uses_a_checked_read(tree), (
        f"{fname} has no checked state read at all — if its restore was "
        f"deleted rather than fixed, remove it from GUARDED_BOOKS with a "
        f"reason; if it was reverted, that is the regression this arm exists "
        f"to catch.")


def test_retired_exemptions_are_still_retired():
    """An exemption must not outlive the retirement that justified it."""
    for fname, why in RETIRED_OK.items():
        src = open(os.path.join(ROOT, fname)).read()
        assert "RETIRED" in src.upper(), (
            f"{fname} no longer looks retired but is exempted here: {why!r} — "
            f"move it into GUARDED_BOOKS and give it the checked read.")
        assert len(why) > 40, f"{fname} exemption needs a real reason"


# ---------------------------------------------------------------------------
# 4. The ORGAN tier — a key a file save_state()s must be read CHECKED, or a
#    blip seeds an amnesiac payload over the organ's own durable memory.
#    This is a RATCHET: a file added to GUARDED_ORGANS can never regress.
# ---------------------------------------------------------------------------

GUARDED_ORGANS = [
    "evidence_board.py",       # notified/seen: re-notify storms on a wipe
    "fleet_immune.py",         # notified/app_seen + the fleet-alerts RMW
    "fleet_regen.py",          # last_push: a wipe double-fires repair pages
    "lighter_scout_tuner.py",  # enacted baseline: phantom change-pushes
    "strategy_incubator.py",   # proposed: the LIFETIME dedup ledger + xp-queue
    # -- the 5-Aug second tranche --
    "fleet_clock.py",          # transition log: a wipe fabricates an event
    "fleet_respiration.py",    # hypoxia-transition memory: double-pages
    "fleet_risk.py",           # equity carry-forward: a wipe IS the false
                               # drawdown the carry exists to prevent
    "implementation_shortfall.py",  # push-gap memory
    "lighter_market_scout.py",  # _marks diff base — FAIL-OPEN, measured safe:
                               # the first-run defense fires nothing on empty
    "lighter_ticket_taker.py",  # shadow STATE_KEY — a run-once bot reboots
                               # every cycle; the live arm was fixed 17-Jul
    "market_pulse.py",         # the brain's hourly history: a wipe RESET it
    "regime_oracle.py",        # per-asset grade accrual (item-18 evidence)
]

# The remaining frontier (5-Aug census, updated after the second tranche) —
# declared, not silent. Each needs its own degrade analysis before joining:
#   * fleet_tuning — the growth rail's LEVER STORE: locked multi-author
#     read-modify-write (3 sites); a wrong degrade could strand or wipe live
#     levers. Its TTL-expiry semantics are load-bearing. Own pass required.
#   * fleet_proposals — same locked multi-author merge shape.
#   * market_context — five sites over three keys incl. the fleet-alerts
#     APPEND path (a wipe truncates the alert stream) and coin-vetoes.
#   * bot_learn (learning-brain read) — the brain's memory; the WRITE side is
#     I4-guarded and (hx) watches the timestamp skew; the read seam still
#     deserves its own pass with the era machinery in view.
#   * experiment_judge (xp-judge-release-request) — a request-queue RMW; the
#     judge's own KEY was fixed 17-Jul.
#   * retired cross_exchange_arb / listing_sniper — idle behind guards.


def _module_str_consts(tree):
    return {t.targets[0].id: t.value.value for t in tree.body
            if isinstance(t, ast.Assign) and len(t.targets) == 1
            and isinstance(t.targets[0], ast.Name)
            and isinstance(t.value, ast.Constant)
            and isinstance(t.value.value, str)}


def _key_of(node, consts):
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    if isinstance(node, ast.Name):
        return consts.get(node.id)
    return None


@pytest.mark.parametrize("fname", GUARDED_ORGANS)
def test_guarded_organ_reads_its_own_save_keys_checked(fname):
    tree = ast.parse(open(os.path.join(ROOT, fname)).read())
    consts = _module_str_consts(tree)
    saves, bad = set(), []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.args):
            k = _key_of(n.args[0], consts)
            if n.func.attr == "save_state" and k:
                saves.add(k)
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "load_state" and n.args):
            k = _key_of(n.args[0], consts)
            if k and k in saves:
                bad.append((n.lineno, k))
    assert not bad, (
        f"{fname}:{bad} reads a key this file save_state()s through the "
        f"UNCHECKED load_state — a blip seeds an amnesiac payload over the "
        f"organ's durable memory. Use load_state_checked and skip the cycle "
        f"(or the write) on ok=False.")
    assert any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
               and n.func.attr == "load_state_checked" for n in ast.walk(tree)), (
        f"{fname} has no checked read at all — if its self-state read was "
        f"deleted, remove it from GUARDED_ORGANS with a reason.")


def test_immune_skips_the_cycle_on_a_failed_read(monkeypatch):
    """Behavioral, for the worst member: a failed KEY read must produce NO
    payload and NO write — not a fresh `notified` that re-pages the fleet."""
    import fleet_immune as fi
    written = []
    monkeypatch.setattr(fi.store, "load_state_checked",
                        lambda k: (False, None), raising=False)
    monkeypatch.setattr(fi.store, "save_state",
                        lambda k, p: written.append(k) or True)
    assert fi.run_once() is None
    assert not written, "a skipped cycle must write NOTHING"
