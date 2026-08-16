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
import datetime as dt
import importlib.util
import json
import pathlib
import re

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


def test_the_run_declares_WHICH_tolerance_basis_produced_its_verdicts(capsys,
                                                                     monkeypatch):
    """THIS GUARD HAS TWO REGIMES AND THEY ARE EASY TO CONFUSE.

    With a DB it reads each organ's published `ttl_sec` (17 of 20 today). With
    none — which is EVERY CI run, since no workflow sets DATABASE_URL — the
    3x-interval proxy governs ALL of them. Two sessions each measured a
    different regime, each stated it unconditionally, and spent four exchanges
    disagreeing about numbers that were both correct.

    So the run must SAY which basis produced it, the same "declare your source"
    property `deploy_times` already has one level up.
    """
    monkeypatch.setattr(mod, "parse_blocks", lambda _t: [
        {"organ": "x", "stagger_s": 20, "interval_s": 300, "early": True,
         "gated": False, "mitigated": True, "inert_flags": [],
         "kind": "periodic"}])
    monkeypatch.setattr(mod, "deploy_times", lambda _l=60: (
        [dt.datetime(2026, 8, 16, 0, m, tzinfo=dt.timezone.utc)
         for m in (0, 5, 10)], "stub"))
    monkeypatch.setattr(mod, "tolerances", lambda _o: {})       # the CI regime
    monkeypatch.setattr("sys.argv", ["audit_boot_stagger.py"])
    mod.main()
    out = capsys.readouterr().out
    assert "tolerance basis:" in out, "the run must declare its basis"
    assert "proxy 1" in out and "published ttl_sec 0" in out, out
    assert "CI regime" in out, "a proxy-only run must say so unprompted"

    # ...and with real TTLs the line reports them instead
    monkeypatch.setattr(mod, "tolerances",
                        lambda _o: {"x": (1200.0, "published ttl_sec")})
    mod.main()
    out2 = capsys.readouterr().out
    assert "published ttl_sec 1" in out2 and "CI regime" not in out2, out2


def test_tolerance_is_the_MINIMUM_ttl_across_an_organs_keys(monkeypatch):
    """ORGAN -> KEY IS NOT 1:1, and the strictest contract binds first.

    Peer-caught 16-Aug: the alias mapped `bot_learn -> learning-brain`, which is
    the brain's MEMORY BLOB and carries no `ttl_sec` at all — so the lookup
    found nothing and fell back to the very proxy the alias existed to avoid,
    360 min against a real 160. An alias doing the opposite of its job.

    An organ publishing several keys is silent on ALL of them at once, so
    taking the FIRST hit would let a generous key (brain-stake-mults, 26000s)
    mask a strict sibling (brain-vitals, 9600s) that has already gone neutral.
    """
    ttls = {"brain-vitals": 9600, "brain-stake-mults": 26000}

    class _FakeStore:
        @staticmethod
        def load_state(key):
            return {"ttl_sec": ttls[key]} if key in ttls else None

    monkeypatch.setitem(__import__("sys").modules, "bot_pnl_store", _FakeStore)
    # ORDER THE GENEROUS KEY FIRST, deliberately. With the strict key first,
    # `found[0]` and `min(found)` coincide and the test passes against a
    # first-hit implementation — which is exactly what my own mutation run
    # caught: U1 (`min` -> `found[0]`) SURVIVED until this line was reversed.
    # A test that only passes because of tuple ordering is not a test.
    monkeypatch.setitem(mod.KEY_ALIASES, "bot_learn",
                        ("brain-stake-mults", "brain-vitals"))
    tol = mod.tolerances(["bot_learn"])
    secs, src = tol["bot_learn"]
    assert secs == 9600, (
        f"must take the MIN across keys, not the first hit — got {secs}; "
        "with the generous key first, a first-hit implementation returns 26000")
    assert "min of 2" in src, src
    # the discarded alias must be gone — it is what caused the fallback
    assert "learning-brain" not in mod.KEY_ALIASES.get("bot_learn", ()), \
        "a key with no ttl_sec cannot serve as the tolerance source"


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


def test_the_git_tier_falls_back_to_HEAD_when_origin_main_is_not_a_ref(monkeypatch):
    """[(pi)] CI checks out a DETACHED HEAD, and `gh run list` needs
    `actions: read` which CI's GITHUB_TOKEN lacks — so the git proxy is the ONLY
    tier CI can reach, and it asked for a ref that may not exist there. With
    both tiers dark the audit asserted nothing, making an `ENFORCED_AUDITS`
    member structurally unable to fail the build it gates.
    """
    seen = []

    class _R:
        def __init__(self, out): self.stdout = out

    def fake_run(cmd, *a, **k):
        if cmd[:2] == ["gh", "run"]:
            raise RuntimeError("no actions: read")       # the CI regime
        seen.append(cmd[-1])
        if cmd[-1] == "origin/main":
            return _R("")                               # not a ref here
        return _R("2026-08-17T01:00:00+00:00\n"
                  "2026-08-17T01:10:00+00:00\n"
                  "2026-08-17T01:30:00+00:00\n")
    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    times, source = mod.deploy_times(60)
    assert seen == ["origin/main", "HEAD"], f"must try both, in order: {seen}"
    assert len(times) == 3, times
    assert "HEAD" in source and "PROXY" in source, source


def test_a_cadence_less_row_still_carries_its_tolerance():
    """[(pg)] THE INCIDENT: `assess` set the tolerance BELOW the `if not gaps`
    early return, so a run with no deploy cadence emitted rows with no
    `tolerance_s`/`tolerance_src` key at all — and `main()` indexes
    `r["tolerance_src"]` to print the basis line. `KeyError`, hard crash.

    The tolerance does not depend on the cadence; only the verdict does. So a
    row must carry it either way, and that is asserted here rather than in
    `main()` alone — every consumer of `assess`'s rows gets the guarantee.
    """
    r = _row(stagger=900, interval=600, gaps=[])
    assert "tolerance_s" in r and "tolerance_src" in r, sorted(r)
    assert r["tolerance_src"] == "3x interval (proxy)", r["tolerance_src"]


def test_main_survives_the_CI_regime_end_to_end(monkeypatch, capsys):
    """[(pg)] The regression as CI actually met it: no DATABASE_URL *and* no
    deploy cadence. A developer's `gh` has full scope and returns ~58 deploys,
    so this path never fires locally — CI's GITHUB_TOKEN carries
    `contents/metadata/packages: read` with no `actions: read`, the run listing
    comes back empty, and every row takes the early return. Red on main from
    `fb4d1c6` to HEAD while the same commit ran green on a laptop.

    Asserts the whole `main()`, not `assess` alone: the crash was in the
    summary line, which a row-level test would have sailed past.
    """
    monkeypatch.setattr(mod, "deploy_times", lambda _n: ([], "none"))
    monkeypatch.setattr(mod, "tolerances", lambda _o: {})   # no DB
    monkeypatch.setattr("sys.argv", ["audit_boot_stagger.py"])
    assert mod.main() == 0
    out = capsys.readouterr().out
    assert "tolerance basis:" in out, out
    # EVERY organ lands in exactly one bucket. The four counts summing to the
    # organ count is the real invariant — it is what a missing `tolerance_src`
    # broke. `unknown` is NOT zero and must not be asserted to be: 🧹
    # `cleanup_legacy_bots` is a one-shot with no interval, so it has no
    # proxy to fall back on and "unknown" is its honest basis.
    n_organs = len(mod.parse_blocks(mod.RUN_ALL.read_text()))
    got = [int(m) for m in re.findall(
        r"published ttl_sec (\d+) organ\(s\), ttl_sec from source (\d+), "
        r"3x-interval proxy (\d+), unknown (\d+)", out)[0]]
    assert sum(got) == n_organs, \
        f"{sum(got)} attributed vs {n_organs} organs — a row fell through: {out}"


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


# --------------------------------------------------------------------------
# deploy_times() — the input the whole verdict rests on.
#
# Every `assess` test above is handed a `gaps` list directly, so until now the
# function that PRODUCES that list was the one untested thing in the guard. It
# has two sources of very different authority and the caller has to be able to
# tell which one answered: the deploy workflow's own successful runs, and — when
# those are unreachable — commit times on origin/main, which are a PROXY because
# several commits ride one push and so one deploy. A proxy silently presented as
# the record is the (I14) shape; a guard that dies when `gh` is absent is worse
# than one that says it cannot assess, because it has to run offline and in CI.
#
# These never shell out: `subprocess.run` is faked, so the tests are hermetic
# and give the same answer on a laptop, in CI, and with no network at all.
# --------------------------------------------------------------------------

class _Done:
    """Stands in for a CompletedProcess — only `.stdout` is read."""

    def __init__(self, stdout=""):
        self.stdout = stdout


def _fake_run(gh=None, git=None):
    """Dispatch on argv[0]. A callable value is invoked so a source can RAISE."""

    def run(cmd, *a, **kw):
        src = gh if cmd[0] == "gh" else git
        if src is None:
            raise FileNotFoundError(cmd[0])       # the tool is not installed
        if callable(src):
            return src()
        return _Done(src)

    return run


def _gh_rows(n, conclusion="success", start="2026-08-16T10:00:00Z"):
    base = dt.datetime.fromisoformat(start.replace("Z", "+00:00"))
    return json.dumps([
        {"createdAt": (base + dt.timedelta(minutes=3 * i)).isoformat().replace("+00:00", "Z"),
         "conclusion": conclusion}
        for i in range(n)
    ])


def _git_lines(n, start="2026-08-16T10:00:00+10:00"):
    base = dt.datetime.fromisoformat(start)
    return "\n".join((base + dt.timedelta(minutes=7 * i)).isoformat()
                     for i in range(n)) + "\n"


def test_the_deploy_workflows_own_runs_are_preferred_and_the_source_says_so(monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=_gh_rows(5), git=_git_lines(9)))
    times, source = mod.deploy_times()
    assert len(times) == 5, "the gh path answered, so git must not have been consulted"
    assert source.startswith("gh:"), source
    assert "PROXY" not in source, "the workflow's own runs are the record, not a proxy"


def test_only_SUCCESSFUL_runs_count_as_deploys(monkeypatch):
    """A failed run did not deploy anything; counting it invents cadence."""
    monkeypatch.setattr(mod.subprocess, "run",
                        _fake_run(gh=_gh_rows(6, conclusion="failure"), git=_git_lines(4)))
    times, source = mod.deploy_times()
    assert source.startswith("git:"), \
        "six FAILED runs are zero deploys — that must fall through, not answer"
    assert len(times) == 4


def test_a_gh_failure_DEGRADES_to_git_rather_than_raising(monkeypatch):
    """The property the guard is least allowed to lose: it must work offline.

    `gh` missing, unauthenticated, rate-limited or returning junk are all the
    same to a caller — none of them may turn a guard into a crash.
    """
    for broken in (None,                                    # not installed
                   "",                                      # empty stdout
                   "not json at all",                       # unparseable
                   '[{"conclusion": "success"}]',           # no createdAt
                   lambda: (_ for _ in ()).throw(OSError("boom"))):
        monkeypatch.setattr(mod.subprocess, "run",
                            _fake_run(gh=broken, git=_git_lines(5)))
        times, source = mod.deploy_times()
        assert source.startswith("git:"), f"{broken!r} should degrade to git, got {source}"
        assert len(times) == 5


def test_the_git_fallback_DECLARES_itself_a_proxy(monkeypatch):
    """A caller must be able to tell which basis produced the verdict."""
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=None, git=_git_lines(5)))
    times, source = mod.deploy_times()
    assert source.startswith("git:")
    assert "PROXY" in source, \
        "commits batch into pushes, so these gaps are UNDERSTATED — say so in the source"


def test_fewer_than_three_gh_runs_falls_through_instead_of_answering(monkeypatch):
    """Two points make one gap. That is not a cadence, and the guard says so."""
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=_gh_rows(2), git=_git_lines(6)))
    times, source = mod.deploy_times()
    assert source.startswith("git:") and len(times) == 6


def test_fewer_than_three_on_BOTH_paths_asserts_nothing(monkeypatch):
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=_gh_rows(2), git=_git_lines(2)))
    times, source = mod.deploy_times()
    assert times == [] and source == "unavailable"


def test_total_unavailability_is_reported_never_raised(monkeypatch):
    """No gh, no git, no network — the CI and offline case."""
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=None, git=None))
    times, source = mod.deploy_times()
    assert times == [] and source == "unavailable"


def test_an_unavailable_cadence_makes_every_organ_unassessable(monkeypatch):
    """The end-to-end of the two tests above: no basis ⇒ no finding, ever."""
    monkeypatch.setattr(mod.subprocess, "run", _fake_run(gh=None, git=None))
    times, _ = mod.deploy_times()
    b = {"organ": "x", "stagger_s": 900, "interval_s": 300,
         "mitigated": False, "kind": "periodic"}
    verdicts = mod.assess([b], mod.gaps_of(times))
    assert verdicts[0]["verdict"] == "report"
    assert "cannot assess" in verdicts[0]["why"]


def test_times_are_ascending_so_gaps_are_positive(monkeypatch):
    """`gaps_of` zips consecutive pairs, so a newest-first list yields NEGATIVE
    gaps — and every negative gap compares `< stagger_s`, i.e. a reversed sort
    reads as a 100% starve rate on every organ."""
    for src in (_fake_run(gh=_gh_rows(5), git=None),
                _fake_run(gh=None, git=_git_lines(5))):
        monkeypatch.setattr(mod.subprocess, "run", src)
        times, _ = mod.deploy_times()
        assert times == sorted(times), "oldest-first is the contract gaps_of relies on"
        assert all(g > 0 for g in mod.gaps_of(times))


def test_both_sources_return_timezone_aware_instants(monkeypatch):
    """Mixing naive and aware datetimes raises TypeError on subtraction, and
    the two sources are stamped differently (`...Z` vs a `+10:00` offset), so
    this is the seam where that would appear."""
    for src in (_fake_run(gh=_gh_rows(4), git=None),
                _fake_run(gh=None, git=_git_lines(4))):
        monkeypatch.setattr(mod.subprocess, "run", src)
        times, source = mod.deploy_times()
        assert times, source
        assert all(t.tzinfo is not None and t.utcoffset() is not None for t in times), \
            f"{source} returned a naive datetime"


# --------------------------------------------------------------------------
# static_ttls() — the tier that makes CI read real contracts.
#
# The live read is unavailable exactly where this guard gates a build: neither
# tests.yml nor changelog-check.yml sets DATABASE_URL, so `tolerances()`
# resolved nothing and all 20 organs fell to the 3x proxy. Every organ declares
# its payload TTL as a module-level `*TTL_SEC` constant, so the contract is
# readable with no database.
# --------------------------------------------------------------------------

def _ttl_of(tmp_path, name, src):
    p = tmp_path / f"{name}.py"
    p.write_text(src)
    old = mod.ROOT
    mod.ROOT = tmp_path
    try:
        return mod.static_ttls([name]).get(name)
    finally:
        mod.ROOT = old


def test_a_plain_constant_is_read(tmp_path):
    assert _ttl_of(tmp_path, "org_a", "TTL_SEC = 2400\n")[0] == 2400


def test_the_env_default_is_the_value_containers_actually_run(tmp_path):
    got = _ttl_of(tmp_path, "org_b",
                  'import os\nTTL_SEC = int(os.environ.get("X_TTL_SEC", "1200"))\n')
    assert got[0] == 1200


def test_the_three_times_interval_form_resolves(tmp_path):
    """`evidence_board` and `fleet_proprioception` literally define
    TTL_SEC = 3 * INTERVAL — which is also why the proxy is exact on them."""
    got = _ttl_of(tmp_path, "org_c",
                  'import os\nINTERVAL = int(os.environ.get("I", "600"))\n'
                  'TTL_SEC = 3 * INTERVAL\n')
    assert got[0] == 1800


def test_the_MINIMUM_is_taken_across_an_organs_ttl_constants(tmp_path):
    """An organ is silent on every key at once, so the STRICTEST contract binds
    — the same rule `tolerances()` applies across live keys. The generous
    constant is written FIRST so a first-hit implementation returns 26000 and
    this assertion actually discriminates."""
    got = _ttl_of(tmp_path, "org_d", "MULT_TTL_SEC = 26000\nVITALS_TTL_SEC = 9600\n")
    assert got[0] == 9600, "took the first constant, not the minimum"
    assert "min of 2" in got[1]


def test_a_LEVER_ttl_is_not_a_payload_ttl(tmp_path):
    """The `*TTL_SEC` suffix is the discriminator, and it must exclude
    LEVER_TTL / LIVE_LEVER_TTL_S / RELEASE_REQ_TTL / QUALITY_VETO_TTL_S —
    unrelated quantities that would corrupt the tolerance."""
    got = _ttl_of(tmp_path, "org_e",
                  "TTL_SEC = 10800\nLEVER_TTL = 60\nQUALITY_VETO_TTL_S = 30\n")
    assert got[0] == 10800, "a lever TTL leaked into the payload tolerance"


def test_a_SELFTEST_FIXTURE_is_not_mistaken_for_the_contract(tmp_path):
    """THE REGRESSION PIN for my own error. A whole-tree `ast.walk` picks up
    fixtures inside functions and produced a table claiming the proxy was wrong
    by 18x when the true worst case is 1.50x. Module level only."""
    got = _ttl_of(tmp_path, "org_f",
                  "TTL_SEC = 3600\n\n"
                  "def _selftest():\n"
                  "    fake = {'updated': 'x', 'ttl_sec': 600}\n"
                  "    OTHER_TTL_SEC = 60\n"
                  "    return fake, OTHER_TTL_SEC\n")
    assert got[0] == 3600, "a selftest fixture was read as the real contract"


def test_an_organ_with_no_ttl_constant_makes_NO_claim(tmp_path):
    """Fail-open: no constant ⇒ no entry ⇒ the proxy still governs. A guard
    that cannot see must not manufacture a number."""
    assert _ttl_of(tmp_path, "org_g", "INTERVAL = 300\n") is None


def test_an_unparseable_or_missing_module_makes_no_claim(tmp_path):
    assert _ttl_of(tmp_path, "org_h", "def broken( :\n") is None
    assert mod.static_ttls(["no_such_organ_anywhere"]) == {}


def test_the_LIVE_organs_resolve_and_reproduce_the_min_across_keys_result():
    """Against the real tree: the static tier must cover the fleet and must
    reproduce the brain's DB-derived 160m (min of VITALS 9600 / MULT 26000)
    with no database at all — that equivalence is the whole point of the tier."""
    organs = [b["organ"] for b in mod.parse_blocks(mod.RUN_ALL.read_text())]
    st = mod.static_ttls(organs)
    assert len(st) >= 15, f"only {len(st)} organs resolved statically"
    assert st["bot_learn"][0] == 9600, st.get("bot_learn")
    assert "min of 2" in st["bot_learn"][1]
    # the three that cannot resolve are structural, not gaps
    for organ in ("cleanup_legacy_bots", "lighter_ticket_taker", "parliament_main"):
        assert organ not in st, f"{organ} has no payload TTL and must make no claim"


def test_the_live_read_OUTRANKS_the_source_read(capsys, monkeypatch):
    """Precedence: live payload > source constant > proxy. The live value is
    what consumers gate on RIGHT NOW, including any env override the source
    read cannot see.

    THIS DRIVES `main()`, NOT AN INLINE DICT. My first version built the merge
    in the test itself, so reversing the module's real merge order left it
    GREEN — a test that passes for the wrong reason, the same shape as the
    `min(found)`/`found[0]` fixture caught in review. The header counts are
    what discriminate: whichever tier wins is the one that gets counted.
    """
    monkeypatch.setattr(mod, "parse_blocks", lambda _t: [
        {"organ": "x", "stagger_s": 20, "interval_s": 300, "early": True,
         "gated": False, "mitigated": True, "inert_flags": [],
         "kind": "periodic"}])
    monkeypatch.setattr(mod, "deploy_times", lambda _l=60: (
        [dt.datetime(2026, 8, 16, 0, m, tzinfo=dt.timezone.utc)
         for m in (0, 5, 10)], "stub"))
    # both tiers answer, and they DISAGREE
    monkeypatch.setattr(mod, "static_ttls", lambda _o: {"x": (111.0, "ttl_sec from source")})
    monkeypatch.setattr(mod, "tolerances", lambda _o: {"x": (999.0, "published ttl_sec")})
    monkeypatch.setattr("sys.argv", ["audit_boot_stagger.py"])
    mod.main()
    out = capsys.readouterr().out
    assert "published ttl_sec 1 organ(s)" in out, out
    assert "ttl_sec from source 0" in out, \
        "the SOURCE tier won — the live payload must outrank it"


def test_the_three_bases_are_counted_DISTINCTLY():
    """`"ttl_sec from source"` also contains `"ttl_sec"`, so a header that
    matched on that substring would report source reads as live ones and hide
    the CI regime — the exact ambiguity this declaration exists to remove."""
    live, src, prox = "published ttl_sec", "ttl_sec from source", "3x interval (proxy)"
    assert "published" in live and "published" not in src
    assert "from source" in src and "from source" not in live
    assert "proxy" in prox and "proxy" not in live and "proxy" not in src
