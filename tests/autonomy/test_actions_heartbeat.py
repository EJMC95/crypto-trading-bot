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
unaffected by a lockout — pages the existing ntfy topic when the beat exceeds
3 missed beats (3.25h), via `actions_heartbeat_problem` reading the DB
directly, PLUS the generic ORGAN DARK path (the key is critical in
ORGAN_SPECS, joining the pageable set deliberately per I13).

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

NOW = 1_800_000_000.0


def _beat(age_s, now=NOW):
    """A payload shaped exactly like the workflow's jsonb_build_object."""
    import datetime as dt
    u = dt.datetime.fromtimestamp(now - age_s, dt.timezone.utc)
    return {"updated": u.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
            "ttl_sec": 3900, "run_id": "12345", "src": "fleet-watchdog.yml"}


# ---------------------------------------------------------------- behavior --

def test_fresh_heartbeat_is_silent():
    assert wd.actions_heartbeat_problem(_beat(600), True, 999999, NOW) is None


def test_one_missed_beat_is_still_silent():
    """One missed hourly beat (~2h old) is LATE, not a page — cron jitter and
    a single queued run must not train the operator to ignore the pager."""
    assert wd.actions_heartbeat_problem(_beat(7200), True, 999999, NOW) is None


def test_three_missed_beats_page():
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
    assert 3 * ttl <= 4 * 3600, (f"DARK at {3 * ttl / 3600:.1f}h — a lockout must "
                                 "page within hours, not a working day")


def test_the_three_stale_bars_agree():
    """svc constant, ORGAN_SPECS ttl and the workflow payload's ttl_sec must
    tell one story — a retyped constant is a constant that drifts."""
    _, ttl = _organ_row()
    assert wd.ACTIONS_HB_MAX_S == 3 * ttl, (
        f"svc pages at {wd.ACTIONS_HB_MAX_S}s but the organ goes DARK at "
        f"{3 * ttl}s — two thresholds, two stories on one fault")
    wf = WORKFLOW.read_text()
    m = re.search(r"'ttl_sec',\s*(\d+)", wf)
    assert m, "workflow payload lost its ttl_sec — every bus payload carries one"
    assert int(m.group(1)) == ttl, (
        f"workflow stamps ttl_sec={m.group(1)} but ORGAN_SPECS says {ttl}")


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
