"""`scripts/audit_boot_stagger.py` — the boot-stagger reachability guard.

WHY THIS EXISTS (2026-08-16). `run_all.sh` starts every organ behind a boot
stagger, and a push is a deploy that resets all of them. Measured that day: 25
successful redeploy runs in 98 minutes, median gap 3.0 min — shorter than four
organs' staggers. Nothing in the fleet could report it, because an organ that
never reaches its first run is not sick: no exception, no stale-key alarm from
the organ itself, every liveness contract green.

The guard's calibration is the whole design, and it was wrong twice before it
was right — both errors are pinned below so it cannot regress into either:

  * FAILING ON A STARVE RATE flagged healthy organs. `evidence_board` lost 75%
    of its races and still published at a median gap of exactly its interval.
  * FAILING ON `burst > interval` flagged 🕐 `fleet_clock` for missing ONE
    five-minute advisory cycle.

The rule that survived: fail only when the burst outlasts what CONSUMERS
tolerate (`ttl_sec`, else a declared 3x-interval proxy), because past the TTL a
reader goes neutral and the silence has actually cost something.

Tests live here rather than behind a `--selftest` flag because registering one
means editing `tests/test_selftests.py`, which a concurrent session holds.
"""
import importlib.util
import pathlib

import pytest

SRC = pathlib.Path(__file__).resolve().parents[2] / "scripts" / "audit_boot_stagger.py"
spec = importlib.util.spec_from_file_location("audit_boot_stagger", SRC)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)


PERIODIC = """
( sleep 900
  while true; do
    python3 /freqtrade/scripts/golive_readiness.py --publish || true
    sleep "${GOLIVE_INTERVAL_SEC:-21600}"
  done ) &
"""

MITIGATED = """
( python3 /freqtrade/fleet_immune.py || true
  sleep 540
  while true; do
    python3 /freqtrade/fleet_immune.py || true
    sleep "${IMMUNE_INTERVAL_SEC:-900}"
  done ) &
"""

SUPERVISOR = """
( sleep 360
  while true; do
    python3 /freqtrade/parliament_main.py || true
    echo "[supervisor] parliament exited — restarting in 30s"
    sleep 30
  done ) &
"""


def test_the_parser_finds_organs_at_all():
    """THE REAPER-THAT-REAPS-NOTHING CASE. The closing token is `done ) &`, so
    `)` is not at the start of its line; an anchor of `^\\s*\\)` matches nothing
    and the audit reports a serene '0 organs' while every stagger sits there.
    That is exactly how `(of)`'s worktree reaper shipped broken, and it is the
    first thing this guard must not do."""
    blocks = mod.parse_blocks(mod.RUN_ALL.read_text())
    assert len(blocks) >= 15, f"parsed only {len(blocks)} organs from run_all.sh"
    names = {b["organ"] for b in blocks}
    for expected in ("golive_readiness", "bot_learn", "fleet_clock", "parliament_main"):
        assert expected in names, f"{expected} missing from {sorted(names)}"


EARLY_THEN_LONG = """
( sleep 20
  python3 /freqtrade/fleet_regen.py || true
  sleep 660
  while true; do
    python3 /freqtrade/fleet_regen.py || true
    sleep "${REGEN_INTERVAL_SEC:-900}"
  done ) &
"""


def test_stagger_is_TIME_TO_FIRST_RUN_not_the_sum_of_pre_loop_sleeps():
    """THE REGRESSION PIN for the bug that nearly cost four needless fixes.

    `( sleep 20; run; sleep 660; while true; ... )` runs the organ at boot+20.
    Summing every pre-loop sleep reads it as 680s and reports FAIL. FOUR organs
    use exactly this shape — fleet_radar (35s), fleet_regen (20s),
    fleet_proprioception (10s), implementation_shortfall (30s) — and all four
    were accused before the blocks were read. A guard that invents work is
    worse than no guard.
    """
    b = mod.parse_blocks(EARLY_THEN_LONG)[0]
    assert b["stagger_s"] == 20, f"time-to-first-run is 20s, got {b['stagger_s']}"
    assert b["interval_s"] == 900
    # ...and at the fleet's real cadence that organ must NOT fail
    assert mod.assess([b], [60.0] * 60)[0]["verdict"] == "report"


def test_the_four_real_organs_are_not_accused():
    """Read from the LIVE run_all.sh, so a future edit that reintroduces a long
    time-to-first-run on any of them is caught here rather than in production."""
    blocks = {b["organ"]: b for b in mod.parse_blocks(mod.RUN_ALL.read_text())}
    for organ, ceiling in (("fleet_radar", 60), ("fleet_regen", 60),
                           ("fleet_proprioception", 60),
                           ("implementation_shortfall", 60)):
        b = blocks.get(organ)
        assert b, f"{organ} vanished from run_all.sh"
        assert b["stagger_s"] <= ceiling, (
            f"{organ} now waits {b['stagger_s']}s before its first run")


def test_stagger_and_interval_are_read_off_the_real_block():
    b = mod.parse_blocks(PERIODIC)[0]
    assert b["organ"] == "golive_readiness"
    assert b["stagger_s"] == 900
    assert b["interval_s"] == 21600, "the ${VAR:-default} form must be read"
    assert b["kind"] == "periodic"


def test_reachability_is_expressed_as_time_to_first_run():
    """An organ that runs BEFORE its long sleep is reachable however fast
    deploys arrive, and the model says so through `stagger_s`, not a flag.
    🛡️ fleet_immune's shape (run, THEN sleep) is time-to-first-run ZERO."""
    immune = mod.parse_blocks(MITIGATED)[0]
    assert immune["stagger_s"] == 0, "an organ that runs first waits 0s"
    assert mod.assess([immune], [30.0] * 80)[0]["verdict"] == "report"
    assert mod.parse_blocks(PERIODIC)[0]["stagger_s"] == 900


def test_the_staleness_gated_form_is_flagged_mitigated():
    """`mitigated` now means specifically the CHEAP early run — reachable AND
    free when the key is already fresh. That is the pattern worth spreading,
    so it is worth naming separately from a plain unconditional early run."""
    assert mod.parse_blocks(PERIODIC)[0]["mitigated"] is False
    gated = PERIODIC.replace("--publish || true",
                             "--publish --publish-if-stale 21600 || true")
    assert mod.parse_blocks(gated)[0]["mitigated"] is True


def test_a_supervisor_is_not_a_periodic_publisher():
    """🏛️ parliament_main's trailing `sleep 30` is a restart backoff, not an
    interval. It has no repeated invocation to gate, so it can never fail."""
    b = mod.parse_blocks(SUPERVISOR)[0]
    assert b["kind"] == "supervisor"
    rows = mod.assess([b], [60.0] * 40)
    assert rows[0]["verdict"] == "report"


def _row(stagger, interval, gaps, tol=None):
    b = {"organ": "x", "stagger_s": stagger, "interval_s": interval,
         "mitigated": False, "kind": "periodic"}
    return mod.assess([b], gaps, tol or {})[0]


def test_it_fails_only_when_the_burst_outlasts_what_consumers_tolerate():
    """THE LOAD-BEARING RULE. 20 deploys 60s apart = a 20-minute burst against
    a 5-minute interval (15-minute proxy tolerance) -> the organ was unreachable
    past the point readers go neutral."""
    r = _row(stagger=300, interval=300, gaps=[60.0] * 20)
    assert r["verdict"] == "FAIL", r["why"]
    assert r["worst_burst_s"] == pytest.approx(1200)


def test_missing_ONE_cycle_is_not_a_failure():
    """The `fleet_clock` case that killed the previous calibration: a burst
    longer than the interval but well inside the tolerance is a delay, not an
    outage, and must pass."""
    r = _row(stagger=200, interval=300, gaps=[100.0] * 6)   # 10 min burst
    assert r["worst_burst_s"] == pytest.approx(600)
    assert r["worst_burst_s"] > 300, "burst does exceed the interval..."
    assert r["verdict"] == "report", "...but must NOT fail inside the tolerance"


def test_a_high_starve_rate_alone_never_fails():
    """`evidence_board` lost 75% of its races and was healthy. Losing races is
    not the question; outlasting the tolerance is."""
    gaps = [60.0, 6000.0] * 10          # every other gap is far longer
    r = _row(stagger=300, interval=600, gaps=gaps)
    starved = sum(1 for g in gaps if g < 300)
    assert starved / len(gaps) == pytest.approx(0.5)
    assert r["verdict"] == "report", "a long gap breaks the burst — never stale"


def test_the_published_ttl_beats_the_proxy_when_available():
    """The TTL is the contract consumers actually gate on; the 3x-interval
    proxy is a declared fallback and must say which was used."""
    gaps = [60.0] * 20                                    # 20-minute burst
    proxy = _row(stagger=300, interval=300, gaps=gaps)
    assert proxy["tolerance_src"] == "3x interval (proxy)"
    assert proxy["verdict"] == "FAIL"
    generous = _row(stagger=300, interval=300, gaps=gaps,
                    tol={"x": (7200.0, "published ttl_sec")})
    assert generous["tolerance_src"] == "published ttl_sec"
    assert generous["verdict"] == "report", "a 2h TTL tolerates a 20m burst"


def test_the_key_alias_is_used_so_the_real_ttl_is_found(monkeypatch):
    """A silent fall-back to the 3x-interval PROXY is not harmless: measured
    16-Aug, the proxy was wrong in BOTH directions — impl-shortfall's real TTL
    is 60 min against a 90 min proxy (too generous, would miss a real outage)
    and fleet-regen's is 40 against 45. Several organs publish under a key that
    is not their module name, so without the alias table the guard quietly
    grades the whole fleet on a number it made up.
    """
    seen = []

    class _FakeStore:
        @staticmethod
        def load_state(key):
            seen.append(key)
            # only the ALIAS resolves — the module-name guesses must miss
            return {"ttl_sec": 3600} if key == "impl-shortfall" else None

    monkeypatch.setitem(__import__("sys").modules, "bot_pnl_store", _FakeStore)
    tol = mod.tolerances(["implementation_shortfall"])
    assert tol.get("implementation_shortfall") == (3600.0, "published ttl_sec"), \
        f"alias not used; tried {seen}"
    assert "impl-shortfall" in seen
    # and the alias table must still cover the organs whose key really differs
    for organ in ("implementation_shortfall", "bot_learn", "lighter_market_scout"):
        assert organ in mod.KEY_ALIASES, f"{organ} publishes under another name"


def test_no_deploy_history_asserts_nothing():
    """Fail-safe: an unavailable cadence must not manufacture a verdict."""
    r = _row(stagger=900, interval=600, gaps=[])
    assert r["verdict"] == "report" and r["starve_rate"] is None


def test_a_declared_exemption_is_honoured_and_must_carry_a_reason():
    b = {"organ": "x", "stagger_s": 900, "interval_s": 300,
         "mitigated": False, "kind": "periodic"}
    mod.STAGGER_OK["x"] = "declared for a measured reason"
    try:
        assert mod.assess([b], [60.0] * 30)[0]["verdict"] == "report"
    finally:
        mod.STAGGER_OK.pop("x", None)
    assert all(isinstance(v, str) and v.strip() for v in mod.STAGGER_OK.values()), \
        "every exemption must name why — the BORN_DARK_OK idiom"
