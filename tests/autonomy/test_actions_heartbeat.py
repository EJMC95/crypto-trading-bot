"""The CI-liveness dead-man's switch must page a billing lockout, off-Actions.

INCIDENT (2026-07-28, memory: github-billing-kills-all-ci-and-deploys). A
GitHub billing lockout killed EVERY workflow silently — CI, deploys AND the
Actions-hosted fleet-watchdog — and the only detection was a human noticing
3-16s not-started "failures". No Actions-side check can detect a lockout,
because a lockout stops Actions itself: I13, a dead loop runs no handler.

THE MECHANISM (2026-08-05). fleet-watchdog.yml's HOURLY cron (fires regardless
of pushes — so a quiet no-push day cannot false-page) upserts bot_state
'actions-heartbeat' {updated, ttl_sec, run_id} using db-backup.yml's existing
secret pattern (project token -> DATABASE_PUBLIC_URL; no new secrets, no
unauthenticated write endpoint). The IN-SERVICE watchdog on Railway —
unaffected by a lockout — pages the existing ntfy topic via
`actions_heartbeat_problem` reading the DB directly, PLUS the generic ORGAN
DARK path (the key is critical in ORGAN_SPECS, joining the pageable set
deliberately per I13).

THE BARS ARE MEASURED, NOT NOMINAL (2026-09-02). GitHub starves free-tier
`schedule` delivery — 198 gaps measured 18-Aug -> 2-Sep: median 0.99h,
p95 5.77h, max 21.52h, with 10.1% of ordinary intervals over the old 3.25h
bar while push CI ran fine through every one. Since 2-Sep the beat is ALSO
written by every main-push CI run (changelog-check.yml piggyback), so its
age measures "any Actions delivery": merged-stream control over the same
tape, max gap 8.39h, 0 of 999 over 12h. Hence TWO RUNGS — LATE (4h, a
warning: visible, never paged) and DARK (12h, the page).

These tests pin: the pager's behavior at every input shape, the key's
criticality + ttl coherence across all three homes (svc constant, ORGAN_SPECS,
workflow payload), the run_loop call site (a pager not called is not a pager),
and the workflow step's existence + cadence.
"""
import ast
import re
from pathlib import Path

import fleet_watchdog_svc as wd

ROOT = Path(__file__).resolve().parent.parent.parent
DASH = ROOT / "pnl_dashboard.py"
WORKFLOW = ROOT / ".github" / "workflows" / "fleet-watchdog.yml"
PIGGYBACK = ROOT / ".github" / "workflows" / "changelog-check.yml"

NOW = 1_800_000_000.0


def _beat(age_s, now=NOW):
    """A payload shaped exactly like the workflow's jsonb_build_object."""
    import datetime as dt
    u = dt.datetime.fromtimestamp(now - age_s, dt.timezone.utc)
    return {"updated": u.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "ttl_sec": 14400, "run_id": "12345", "src": "fleet-watchdog.yml"}


# ---------------------------------------------------------------- behavior --

def test_fresh_heartbeat_is_silent():
    assert wd.actions_heartbeat_problem(_beat(600), True, 999999, NOW) is None


def test_one_missed_beat_is_still_silent():
    """One missed hourly beat (~2h old) is LATE, not a page — cron jitter and
    a single queued run must not train the operator to ignore the pager."""
    assert wd.actions_heartbeat_problem(_beat(7200), True, 999999, NOW) is None


def test_beyond_the_dark_bar_pages():
    p = wd.actions_heartbeat_problem(_beat(wd.ACTIONS_HB_MAX_S + 60), True,
                                     999999, NOW)
    assert p and "GITHUB ACTIONS DARK" in p, p
    # I8: the page must name what the operator opens — Actions runs + billing.
    assert "Billing" in p and "Actions" in p, p


def test_db_read_failure_is_not_an_actions_page():
    """A Postgres blip must not send the operator to GitHub (I8) — DB darkness
    is the FEED STALE layer's diagnosis, from the same DB."""
    assert wd.actions_heartbeat_problem(None, False, 999999, NOW) is None
    assert wd.actions_heartbeat_problem(
        _beat(wd.ACTIONS_HB_MAX_S + 60), False, 999999, NOW) is None


def test_absent_key_is_quiet_during_bootstrap_then_pages():
    """Before the workflow's first run the key does not exist: quiet. But a
    heartbeat that NEVER arrives must still page once this service has been up
    past the stale bar — a dead-man's switch that never arms is the I13 trap."""
    assert wd.actions_heartbeat_problem(None, True, 600, NOW) is None
    p = wd.actions_heartbeat_problem(None, True, wd.ACTIONS_HB_MAX_S + 60, NOW)
    assert p and "NEVER SEEN" in p, p


def test_unreadable_stamp_fails_toward_the_page():
    """A row that EXISTS with a junk 'updated' is a broken writer, not
    bootstrap — the (hc) unreadable-stamp direction."""
    p = wd.actions_heartbeat_problem({"updated": "garbage"}, True, 600, NOW)
    assert p and "UNREADABLE" in p, p


# ------------------------------------------------- pageable-set coherence --

def _organ_row():
    src = DASH.read_text()
    blk = src[src.index("ORGAN_SPECS = ["):]
    blk = blk[:blk.index("\n]") + 2]
    m = re.search(r'\(\s*"actions-heartbeat",\s*"[^"]*",\s*(True|False),\s*'
                  r'(None|\d+)\)', blk)
    assert m, "actions-heartbeat left ORGAN_SPECS — the vitals/pageable half is gone"
    return m.group(1) == "True", None if m.group(2) == "None" else int(m.group(2))


def test_the_heartbeat_key_is_watchdog_critical():
    crit, ttl = _organ_row()
    assert crit, ("actions-heartbeat demoted out of paging — the whole point "
                  "is that its staleness reaches the phone (I13)")
    assert ttl is not None, "must be TTL'd, not EVENT-typed — silence here IS failure"
    assert ttl >= 3600, (f"ttl {ttl}s < the 3600s cron period — every ordinary "
                         "hour would read LATE, which is how an alarm becomes noise")
    # [2026-09-02 (wl-follow)] RE-AIMED with the measurement — the old pin
    # (DARK within 4h) asserted the nominal-cron design, and the measured
    # delivery distribution refuted it: 10.1% of ordinary scheduled intervals
    # exceeded it (a pin is not a reason, I26). The bar must clear the
    # merged-stream (cron + push-CI piggyback) maximum of 8.39h and still
    # page inside half a day.
    assert 3 * ttl > int(8.39 * 3600), (
        f"DARK at {3 * ttl / 3600:.1f}h sits inside the MEASURED ordinary "
        "delivery tail (merged-stream max 8.39h) — the pager would cry wolf, "
        "which is how the operator learns to ignore the one lockout detector")
    assert 3 * ttl <= 12 * 3600, (
        f"DARK at {3 * ttl / 3600:.1f}h — a lockout is permanent until a "
        "human acts and must page within half a day")


def test_the_three_stale_bars_agree():
    """svc constant, ORGAN_SPECS ttl and the workflow payload's ttl_sec must
    tell one story — a retyped constant is a constant that drifts."""
    _, ttl = _organ_row()
    assert wd.ACTIONS_HB_MAX_S == 3 * ttl, (
        f"svc pages at {wd.ACTIONS_HB_MAX_S}s but the organ goes DARK at "
        f"{3 * ttl}s — two thresholds, two stories on one fault")
    # EVERY write site must stamp the same ttl — the cron writer AND the
    # (wl-follow) push-CI piggyback writer. findall, not search: the first
    # match agreeing says nothing about a second writer that drifted.
    sites = 0
    for wf_path in (WORKFLOW, PIGGYBACK):
        for m in re.finditer(r"'ttl_sec',\s*(\d+)", wf_path.read_text()):
            sites += 1
            assert int(m.group(1)) == ttl, (
                f"{wf_path.name} stamps ttl_sec={m.group(1)} but ORGAN_SPECS "
                f"says {ttl} — two writers, two stories on one key")
    assert sites >= 2, (
        f"expected the cron writer AND the piggyback writer to stamp ttl_sec, "
        f"found {sites} site(s) — a beat writer lost its ttl")
    # and the LATE rung is the vitals ttl itself: warning onset = the card
    # turning LATE, one story on both surfaces.
    assert wd.ACTIONS_HB_LATE_S == ttl, (
        f"LATE at {wd.ACTIONS_HB_LATE_S}s but the vitals card turns LATE at "
        f"{ttl}s — two onsets, two stories")


# ------------------------------------------------------------- call sites --

def test_run_loop_actually_calls_the_heartbeat_check():
    """A pager not called is not a pager (the registered-but-inert failure).
    AST, not substring — a comment mentioning the name must not pass this."""
    tree = ast.parse((ROOT / "fleet_watchdog_svc.py").read_text())
    run_loop = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "run_loop")
    calls = [n for n in ast.walk(run_loop)
             if isinstance(n, ast.Call)
             and ((isinstance(n.func, ast.Name)
                   and n.func.id == "actions_heartbeat_problem")
                  or (isinstance(n.func, ast.Attribute)
                      and n.func.attr == "actions_heartbeat_problem"))]
    assert calls, "run_loop no longer calls actions_heartbeat_problem"
    # and its verdict must be able to reach `problems` (the paged list)
    seg = ast.get_source_segment((ROOT / "fleet_watchdog_svc.py").read_text(),
                                 run_loop)
    assert re.search(r"problems\.append\(_hb_p\)", seg), (
        "the heartbeat verdict is computed but never appended to problems")


# ---------------------------------------------------------------- workflow --

def test_workflow_writes_the_beat_on_an_hourly_cron():
    wf = WORKFLOW.read_text()
    assert re.search(r"cron:\s*'7 \* \* \* \*'", wf), (
        "fleet-watchdog.yml is no longer hourly — the 3-missed-beats math and "
        "the 3900s ttl both assume a 3600s cadence; retune BOTH if this moves")
    # Anchored in the SQL itself, NOT a page-wide substring — the key also
    # appears in comments, and mutation-testing this file proved a bare
    # substring check stays green when the upsert key is renamed.
    assert re.search(r"VALUES\s*\('actions-heartbeat',\s*now\(\)", wf), (
        "the heartbeat upsert no longer writes the 'actions-heartbeat' key — "
        "the dead-man's switch is disarmed and the svc pager will "
        "(correctly) fire in ~3h")
    assert "ON CONFLICT (bot) DO UPDATE" in wf, (
        "the heartbeat write lost its upsert — a second run would fail on the "
        "primary key and the beat would freeze at the first row")
    assert "'run_id', '${RUN_ID}'" in wf, (
        "the beat lost run_id — the page names the last run the operator can open")
    # the write must come from the SAME secret pattern db-backup.yml proved,
    # never an unauthenticated dashboard endpoint
    assert "RAILWAY_TOKEN" in wf and "DATABASE_PUBLIC_URL" in wf, (
        "heartbeat no longer resolves the DB via the Railway project token")


# ------------------------------------------------ the (wl-follow) LATE rung --

def test_the_late_band_is_a_warning_and_never_a_page():
    """LATE < age <= MAX: the pager stays quiet (10.1% of ordinary scheduled
    intervals live here — paging on them is how the operator learns to ignore
    the lockout detector), while the warning is visible."""
    age = (wd.ACTIONS_HB_LATE_S + wd.ACTIONS_HB_MAX_S) // 2
    assert wd.actions_heartbeat_problem(_beat(age), True, 999999, NOW) is None
    w = wd.actions_heartbeat_late(_beat(age), True, NOW)
    assert w and "slow" in w.lower(), w


def test_fresh_and_dark_are_not_late():
    """Below LATE: silence. Beyond MAX: the PAGE owns the story — a warning
    beside a problem would be two lines about one fault."""
    assert wd.actions_heartbeat_late(_beat(600), True, NOW) is None
    assert wd.actions_heartbeat_late(_beat(wd.ACTIONS_HB_MAX_S + 60),
                                     True, NOW) is None


def test_late_inherits_the_problem_functions_fail_directions():
    """Failed read / absent key / junk stamp all have owners in
    actions_heartbeat_problem — the late rung must not double-report them."""
    assert wd.actions_heartbeat_late(None, False, NOW) is None
    assert wd.actions_heartbeat_late(None, True, NOW) is None
    assert wd.actions_heartbeat_late({"updated": "garbage"}, True, NOW) is None


def test_run_loop_wires_the_late_rung_into_warnings():
    """Same shape as the problems pin above: a rung not called is not a rung."""
    src = (ROOT / "fleet_watchdog_svc.py").read_text()
    tree = ast.parse(src)
    run_loop = next(n for n in tree.body
                    if isinstance(n, ast.FunctionDef) and n.name == "run_loop")
    calls = [n for n in ast.walk(run_loop)
             if isinstance(n, ast.Call)
             and ((isinstance(n.func, ast.Name)
                   and n.func.id == "actions_heartbeat_late")
                  or (isinstance(n.func, ast.Attribute)
                      and n.func.attr == "actions_heartbeat_late"))]
    assert calls, "run_loop no longer calls actions_heartbeat_late"
    seg = ast.get_source_segment(src, run_loop)
    assert re.search(r"warnings\.append\(_hb_w\)", seg), (
        "the late verdict is computed but never appended to warnings")


def test_the_piggyback_beat_writes_on_push_ci():
    """[2026-09-02] The dead-man's switch's second writer: every main-push CI
    run beats the key, so its age measures 'any Actions delivery' — the
    quantity the DARK page's diagnosis actually claims. Anchored in the SQL
    (the (hj) rule: a comment naming the key must not pass)."""
    wf = PIGGYBACK.read_text()
    assert re.search(r"VALUES\s*\('actions-heartbeat',\s*now\(\)", wf), (
        "changelog-check.yml lost the piggyback heartbeat upsert — the beat "
        "rides the starved schedule queue alone again (measured: 10.1% of "
        "scheduled intervals exceed 3.25h; five 7-21.5h gaps in one week)")
    assert "ON CONFLICT (bot) DO UPDATE" in wf
    assert "'src', 'changelog-check.yml'" in wf, (
        "the piggyback beat must stamp its own src — two writers of one key "
        "must be tellable apart on the payload (I8)")
    assert re.search(r"github\.event_name\s*==\s*'push'", wf), (
        "the piggyback step must be gated to push events")
