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


def test_BOTH_early_run_shapes_parse_as_mitigated_from_the_LIVE_file():
    """THE REGRESSION PIN. Peer-caught 16-Aug, and it is the reason this test
    reads run_all.sh rather than a fixture.

    Every SHAPE-based predicate tried so far was right about one arrangement
    and wrong about another. `head = body[:first_sleep.start()]` handled the
    run-first `(os)` shape and missed the `(ou)` ladder. Replacing it with a
    flag test handled neither, and REGRESSED 🛡️ fleet_immune — the canonical
    run-first organ whose 50-minute silence started this work — from
    mitigated=True to False.

    The property that survives both, and is the fleet's own (see
    `test_immune_boot_execution.py`): NO SLEEP LONGER THAN 60s PRECEDES THE
    FIRST INVOCATION. Pinned here against the real file so a future predicate
    cannot pass a fixture while breaking a live organ.
    """
    blocks = {b["organ"]: b for b in mod.parse_blocks(mod.RUN_ALL.read_text())}
    # run-first shape: ( run; sleep 540; while true ... )
    immune = blocks["fleet_immune"]
    assert immune["stagger_s"] == 0, immune
    assert immune["early"] is True and immune["mitigated"] is True, \
        "fleet_immune is THE run-first organ — it must never parse unmitigated"
    # ladder shape: ( sleep 10..35; run; sleep 540..720; while true ... )
    for organ in ("fleet_radar", "fleet_regen", "fleet_proprioception",
                  "implementation_shortfall"):
        b = blocks[organ]
        assert b["stagger_s"] <= mod.EARLY_RUN_MAX_S, (organ, b["stagger_s"])
        assert b["mitigated"] is True, f"{organ} runs early and must say so"
    # the bar is the fleet's, not one invented here
    assert mod.EARLY_RUN_MAX_S == 60


def test_an_invocation_the_organ_REJECTS_is_not_a_first_run():
    """`(pe)`: a claim read off run_all.sh is a claim about the SHELL, not the
    organ — and `early` is POSITIONAL, so a block whose first line is an early
    run scores stagger 0 even when that run dies on `unrecognized arguments`
    and `|| true` hides it.

    NOT HYPOTHETICAL, AND I SHIPPED IT: at dc803be the shell passed
    `--publish-if-stale` twice while golive_readiness.py declared it ZERO
    times, until (pa) supplied the missing half. Live boot log:
    `error: unrecognized arguments: --publish-if-stale 21600`. A shell-only
    parser called that block correctly mitigated throughout.
    """
    inert = """
( python3 /freqtrade/scripts/golive_readiness.py --publish --publish-if-nonexistent 21600 || true
  sleep 900
  while true; do
    python3 /freqtrade/scripts/golive_readiness.py --publish || true
    sleep 21600
  done ) &
"""
    b = mod.parse_blocks(inert)[0]
    assert b["stagger_s"] == 900, "the rejected run must not count as the first"
    assert b["early"] is False and b["gated"] is False
    assert b["inert_flags"] == ["--publish-if-nonexistent"], b["inert_flags"]
    # ...and the real block, whose flag IS implemented, is unaffected
    live = {x["organ"]: x for x in mod.parse_blocks(mod.RUN_ALL.read_text())}
    g = live["golive_readiness"]
    assert g["inert_flags"] == [] and g["gated"] is True and g["stagger_s"] == 0


def test_flag_detection_fails_open_on_an_unreadable_target():
    """A guard that cannot see must not manufacture a finding."""
    assert mod.declares_flag("/freqtrade/does_not_exist.py", "--x") is None
    assert mod.declares_flag("/freqtrade/scripts/golive_readiness.py",
                             "--publish-if-stale") is True
    assert mod.declares_flag("/freqtrade/scripts/golive_readiness.py",
                             "--no-such-flag") is False


def test_a_one_shot_organ_can_be_failed_at_all():
    """🧹 cleanup_legacy_bots has no loop, so `interval_s` is None — and with a
    None tolerance it was structurally UNFAILABLE, the single organ whose
    missed first run is PERMANENT (it prunes retired rows at boot; a skipped
    run leaves a dead book's row standing). Peer-caught."""
    one_shot = {"organ": "cleanup_legacy_bots", "stagger_s": 600,
                "interval_s": None, "early": False, "gated": False,
                "mitigated": False, "kind": "periodic"}
    starved = mod.assess([one_shot], [60.0] * 200)[0]
    assert starved["verdict"] == "FAIL", "a one-shot that never ran must fail"
    assert "one-shot" in starved["why"].lower()
    # ...but one long-enough window is all it needs, ever
    ok = mod.assess([one_shot], [60.0] * 50 + [3600.0])[0]
    assert ok["verdict"] == "report"
    # and an early one-shot is never at risk
    early = dict(one_shot, stagger_s=60, early=True, mitigated=True)
    assert mod.assess([early], [60.0] * 200)[0]["verdict"] == "report"


def test_assess_does_not_clobber_its_own_tolerance_map():
    """Peer-caught: a local f-string named `tol` rebound the PARAMETER inside
    the loop, so from iteration two `b["organ"] in tol` was a substring test.
    Organs silently lost their published ttl_sec, verdicts became
    ORDER-DEPENDENT, and when a name occurred in the string ("b" in
    "...published ttl_sec") the next lookup raised TypeError outright."""
    blocks = [{"organ": n, "stagger_s": 300, "interval_s": 300, "early": False,
               "gated": False, "mitigated": False, "kind": "periodic"}
              for n in ("a", "b", "published", "min")]
    tol = {n: (7200.0, "published ttl_sec") for n in ("a", "b", "published", "min")}
    gaps = [60.0] * 20                      # 20-min burst; a 2h TTL tolerates it
    rows = mod.assess(blocks, gaps, tol)
    assert [r["tolerance_src"] for r in rows] == ["published ttl_sec"] * 4, rows
    assert {r["verdict"] for r in rows} == {"report"}
    # ORDER-INDEPENDENCE is the property, so assert it directly
    rev = mod.assess(blocks[::-1], gaps, tol)
    assert {r["organ"]: r["verdict"] for r in rows} == \
           {r["organ"]: r["verdict"] for r in rev}


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
