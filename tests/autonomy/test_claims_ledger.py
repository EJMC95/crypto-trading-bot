"""THE LEDGER OF CLAIMS — the structural pins. [2026-08-27 (vm)]

The `--selftest` blocks in `scripts/claims_ledger.py` and
`scripts/audit_claim_freshness.py` drive every verdict branch on fixtures. What
lives HERE is the half a fixture cannot reach:

  * the ledger's dotted OWNER PATHS are resolved against a payload built by
    `golive_readiness`'s OWN publisher functions, not by a hand-written dict —
    this repo's single most repeated defect is a fixture with invented key
    names (`closed_at` vs `close_ts`), and a claim pointed at a key the organ
    does not publish would sit UNRESOLVED forever while reading like diligence;
  * that the leak this artifact was built for actually FIRES on the real table;
  * that the ratchet, the declaration gate and the CI regime are the shapes
    they claim to be, asserted through the real `audit` rather than by reading.
"""
import datetime as dt
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
SCRIPTS = os.path.join(ROOT, "scripts")
for _p in (ROOT, SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import claims_ledger as cl                    # noqa: E402
import audit_claim_freshness as acf           # noqa: E402
import golive_readiness as gr                 # noqa: E402


# --------------------------------------------------------------- publisher-built
def _publisher_payload(bot, pcts, start=None):
    """A `golive-readiness` payload assembled by the GRADER'S OWN functions.

    `stats` -> `book_payload` -> `gate_horizon` is the exact composition the
    publish site runs (golive_readiness.py, the `payload_books[bot] = {...}`
    block); nothing here types a key name by hand, which is the whole point —
    if the organ renames `t`, this fixture renames it too and the claims that
    point at the old name go UNRESOLVED loudly instead of silently.
    """
    start = start or dt.datetime(2026, 7, 1, tzinfo=dt.timezone.utc)
    rows = [(p, p * 8.0, start + dt.timedelta(hours=6 * i))
            for i, p in enumerate(pcts)]
    s = gr.stats(rows)
    hz = gr.gate_horizon(s, first_close=rows[0][2],
                         now=start + dt.timedelta(days=40))
    return {"books": {bot: {**gr.book_payload(s), "horizon": hz}}}


def _allocation_payload(bot, pcts):
    """A `fleet-allocation` payload from the ORGAN'S OWN run_once — the same
    no-hand-typed-keys rule as the grader fixture above. Added for the
    mum-golive-justification claim, whose argued number (the positive edge
    lower bound that moved georgia's $220) is owned by this organ."""
    import datetime as _dt
    import fleet_allocation as fa
    start = _dt.datetime(2026, 8, 20, tzinfo=_dt.timezone.utc)
    rows = [{"bot": bot, "profit_ratio": p, "profit_abs": p * 80,
             "open_rate": 1.0, "close_rate": 1.0 + p,
             "opened_at": (start + _dt.timedelta(hours=6 * i)).isoformat(),
             "closed_at": (start + _dt.timedelta(hours=6 * i + 3)).isoformat()}
            for i, p in enumerate(pcts)]

    class _S:
        def fetch_paper_trades(self, limit=None):
            return [dict(r) for r in rows]

        def fetch_bot_pnl(self, *a, **k):
            return []

    old = fa.store
    fa.store = _S()
    try:
        return fa.run_once(publish=False)
    finally:
        fa.store = old


def test_every_claims_owner_path_resolves_in_a_publisher_built_payload():
    # a book with a real spread of closes, so `t`/`mean_pct`/`horizon` are all
    # genuinely computed rather than short-circuited by the n<2 early return
    pcts = [0.004, -0.002, 0.011, -0.006, 0.008, 0.001, -0.003, 0.009,
            0.002, -0.001, 0.006, 0.003]
    for row in cl.CLAIMS:
        key, path = row["owner"]
        bot = path.split(".")[1]
        payload = (_allocation_payload(bot, pcts)
                   if key == "fleet-allocation"
                   else _publisher_payload(bot, pcts))
        got = cl.resolve(payload, path)
        assert got is not None, (
            f"{row['id']}: `{path}` is not a key {key}'s own publisher emits — "
            f"a claim pointed at a phantom field can never go STALE")
        assert cl._num(got) is not None, (row["id"], path, got)


def test_a_renamed_organ_field_is_UNRESOLVED_not_silently_matching():
    pcts = [0.004, -0.002, 0.011, -0.006, 0.008, 0.001, -0.003, 0.009]
    row = cl.CLAIMS[0]
    bot = row["owner"][1].split(".")[1]
    payload = _publisher_payload(bot, pcts)
    payload["books"][bot].pop("t")                      # the organ renames it
    g = cl.grade(row, {row["owner"][0]: payload}, dt.date(2026, 8, 27))
    assert g["status"] == "UNRESOLVED", g
    assert g["live"] is None


# ------------------------------------------------------------------ declaration
def test_a_row_without_a_resolvable_owner_is_REFUSED():
    ok = cl._fixture()[0]
    for mutant in (dict(ok, owner="golive-readiness"),
                   dict(ok, owner=("golive-readiness",)),
                   dict(ok, owner=("", "books.b.t")),
                   dict(ok, owner=("golive-readiness", "   "))):
        bad = cl.validate([mutant])
        assert bad and any("CANNOT BE ADDED" in b for b in bad), mutant["owner"]
    # ...and a row naming an organ FILE that no longer exists is refused too,
    # through audit_doctrine_enforcement.check_ref — the invariants' own
    # mechanism, imported rather than re-expressed
    gone = cl.validate([dict(ok, owner_ref="scripts/deleted_organ.py")])
    assert gone and "no longer resolves" in gone[0], gone


def test_the_owner_check_is_the_doctrine_guards_own_and_not_a_copy():
    import audit_doctrine_enforcement as ade
    src = open(os.path.join(SCRIPTS, "claims_ledger.py"), encoding="utf-8").read()
    assert "from audit_doctrine_enforcement import check_ref" in src
    # by IDENTITY, never by asserting a name is absent (a name check stays
    # green against a hand-rolled copy — the (hj) rule)
    assert ade.check_ref(cl.CLAIMS[0]["owner_ref"], ROOT) is None
    assert ade.check_ref("scripts/no_such_file.py", ROOT)


def test_the_real_table_is_declarable_and_every_kind_is_legal():
    assert cl.validate() == []
    assert {c["kind"] for c in cl.CLAIMS} <= set(cl.KINDS)
    assert len({c["id"] for c in cl.CLAIMS}) == len(cl.CLAIMS)
    # the brief's three shapes are all present, so the ledger is not a
    # one-sided instrument wearing a two-sided name
    assert {c["kind"] for c in cl.CLAIMS} == {"win", "refusal", "doctrine"}


# ----------------------------------------------------------------------- drift
def test_a_drifted_number_reddens():
    ok = dict(cl._fixture()[0], covers=("row-a",), kind="doctrine",
              cites=("CLAUDE.md",))
    base = dict(today=dt.date(2026, 8, 27),
                sh_text="", docker_text="", rows=("row-a",),
                ratchet={"live_rows_without_a_justification_claim": 0})
    inside = {"k": {"books": {"b": {"t": 2.4}}}}      # number 2.0, tol 0.5
    outside = {"k": {"books": {"b": {"t": 3.1}}}}
    assert acf.audit(claims=[ok], states=inside, **base)[0] == 0
    rc, lines = acf.audit(claims=[ok], states=outside, **base)
    assert rc == 1 and any("STALE" in x for x in lines), lines
    # I8 — the finding names the file the operator has to open
    assert any("CLAUDE.md" in x for x in lines), lines


def test_the_georgia_golive_number_is_the_leak_this_exists_for():
    """The seeded doctrine row FIRES against the organ's own number.

    Measured 27-Aug: CLAUDE.md/(ta) argues georgia onto a real sub-account at
    `t = 1.48`; `golive-readiness` publishes 0.62. The payload here is built by
    the grader's own functions, so this asserts the MECHANISM (a doctrine
    number graded against its organ) rather than replaying today's live value.
    """
    row = next(c for c in cl.CLAIMS
               if c["id"] == "georgia-golive-justification")
    key, path = row["owner"]
    bot = path.split(".")[1]
    assert bot == "freqtrade-georgia-lshadow", row["owner"]
    # a flat, noisy book grades well below the claimed 1.48
    flat = _publisher_payload(bot, [0.004, -0.004, 0.005, -0.005, 0.006,
                                    -0.006, 0.004, -0.003, 0.002, -0.002])
    g = cl.grade(row, {key: flat}, dt.date(2026, 8, 27))
    assert g["status"] == "STALE", g
    assert g["drift"] > row["tol"]
    assert "CLAUDE.md" in g["cites"]


def test_a_dark_organ_is_never_graded_and_never_clean():
    rc, lines = acf.audit(claims=cl.CLAIMS, states={}, rows=(),
                          sh_text="", docker_text="",
                          ratchet={"live_rows_without_a_justification_claim": 0},
                          today=dt.date(2026, 8, 27))
    assert rc == 2, (rc, lines)
    assert all(g["status"] == "DARK"
               for g in cl.grade_all({}, cl.CLAIMS, dt.date(2026, 8, 27)))


# --------------------------------------------------------------------- ratchet
def test_the_ratchet_may_only_shrink():
    ok = dict(cl._fixture()[0], covers=("row-a",), kind="doctrine")
    st = {"k": {"books": {"b": {"t": 2.0}}}}
    base = dict(today=dt.date(2026, 8, 27), sh_text="", docker_text="",
                states=st, claims=[ok])
    three = ("row-a", "row-b", "row-c")             # one covered, two not
    at, _ = acf.audit(rows=three, ratchet={
        "live_rows_without_a_justification_claim": 2}, **base)
    grew, lines = acf.audit(rows=three, ratchet={
        "live_rows_without_a_justification_claim": 1}, **base)
    shrank, tighten = acf.audit(rows=three, ratchet={
        "live_rows_without_a_justification_claim": 5}, **base)
    assert at == 0, "equality must pass — a ratchet is not a bar"
    assert grew == 1 and any("> ratchet 1" in x for x in lines), lines
    assert shrank == 0 and any("RATCHET CAN TIGHTEN" in x for x in tighten)


def test_a_new_live_book_with_no_justification_fails_the_push_that_adds_it():
    """The ratchet's forward half: today's backlog is tolerated, a NEW one is
    not — which is what stops the pile growing while it drains."""
    # [2026-09-02 (wl)] georgia's retirement took the fleet's only justified
    # live row off the roster; [same day, the drain] both remaining live rows
    # gained claims and the ratchet tightened to its measured floor of ZERO.
    # The fixture mirrors that production state: one claim covering the whole
    # roster, backlog 0 == ratchet 0 — and the forward half must catch the
    # very first unjustified newcomer.
    roster = acf.live_rows()
    assert roster and "freqtrade-georgia-lighter" not in roster, roster
    ok = dict(cl._fixture()[0], covers=tuple(roster), kind="doctrine")
    st = {"k": {"books": {"b": {"t": 2.0}}}}
    base = dict(today=dt.date(2026, 8, 27), sh_text="", docker_text="",
                states=st, claims=[ok], ratchet=dict(acf.RATCHET))
    assert acf.audit(rows=roster, **base)[0] == 0
    rc, lines = acf.audit(rows=tuple(roster) + ("lus-pessoa-lighter",), **base)
    assert rc == 1 and any("lus-pessoa-lighter" in x for x in lines), lines


def test_the_ratchet_is_fail_closed_on_an_unreadable_roster():
    rc, lines = acf.audit(claims=cl.CLAIMS, rows=None, sh_text="",
                          docker_text="", states={"golive-readiness": {}},
                          today=dt.date(2026, 8, 27))
    assert rc == 1 and any("live roster is unreadable" in x for x in lines)


def test_the_ratchet_is_at_its_measured_value_and_the_roster_is_the_declared_one():
    """A ratchet recorded above its own measurement guards nothing."""
    roster = acf.live_rows()
    gap = acf.uncovered_live_rows(roster)
    assert len(gap) <= acf.RATCHET["live_rows_without_a_justification_claim"], gap


# ------------------------------------------------------------------- born-dark
def test_a_run_all_loop_without_a_COPY_is_reported_as_born_dark():
    sh = "python3 /freqtrade/scripts/claims_ledger.py --publish || true"
    assert acf.dark_loops(sh, "COPY bot_pnl_store.py /x") == ["claims_ledger"]
    assert acf.dark_loops(
        sh, "COPY scripts/claims_ledger.py /freqtrade/scripts/x.py") == []
    # this is a class audit_image_imports structurally cannot see: it filters
    # run-path modules through `repo_modules()`, which enumerates ROOT-level
    # .py only, so nothing under scripts/ ever reaches its check
    import audit_image_imports as aii
    assert "claims_ledger" not in aii.repo_modules()


def test_run_all_actually_runs_both_instruments():
    """(c) of the brief, pinned: the WIN instrument now has a schedule.

    `winners_docket.py` carried no `--publish` flag (its __main__ tests
    `"--selftest" in sys.argv`), so the loop runs it bare and run_all.sh
    records what publishing would need. Asserted here so a future edit cannot
    quietly drop the docket back to never running.
    """
    sh = open(os.path.join(ROOT, "run_all.sh"), encoding="utf-8").read()
    assert acf.script_loops(sh) >= {"claims_ledger", "winners_docket"}
    assert "claims_ledger.py --publish" in sh
    src = open(os.path.join(SCRIPTS, "winners_docket.py"), encoding="utf-8").read()
    assert "--publish" not in src, (
        "winners_docket gained a --publish flag — move the loop onto it and "
        "delete the note in run_all.sh that says what it would need")


# ----------------------------------------------------------------- CI regime
def test_the_no_database_url_regime_does_not_pass_vacuously():
    """CI has no DATABASE_URL. A run that recomputed nothing must not exit 0."""
    had = os.environ.pop("DATABASE_URL", None)
    try:
        rc, lines = acf.audit(claims=cl.CLAIMS, rows=acf.live_rows(),
                              sh_text="", docker_text="",
                              today=dt.date(2026, 8, 27))
    finally:
        if had is not None:
            os.environ["DATABASE_URL"] = had
    assert rc != 0, (rc, lines)
    assert rc == 2, (rc, lines)
    assert any("LIVE ARM SKIPPED" in x for x in lines), lines
    assert any("NOT recomputed" in x for x in lines), lines


def test_an_offline_finding_outranks_the_inconclusive_skip():
    """rc 1 beats rc 2: a real defect must not be masked by "I couldn't read
    the organ", which is the softer verdict."""
    had = os.environ.pop("DATABASE_URL", None)
    try:
        rc, _ = acf.audit(claims=[dict(cl._fixture()[0],
                                       owner_ref="scripts/gone.py")],
                          rows=(), sh_text="", docker_text="",
                          ratchet={"live_rows_without_a_justification_claim": 0},
                          today=dt.date(2026, 8, 27))
    finally:
        if had is not None:
            os.environ["DATABASE_URL"] = had
    assert rc == 1


# ----------------------------------------------------------------- publish-only
def test_the_ledger_is_publish_only():
    """No entry rule, exit rule, threshold, cap or sizing may move because of
    this artifact. Asserted by AST over CALLS, never by a page-wide substring
    scan — three tests in one 30-Jul session failed on the very sentence
    promising the property they checked."""
    import ast
    called = set()
    for mod in ("claims_ledger.py", "audit_claim_freshness.py"):
        for node in ast.walk(ast.parse(open(os.path.join(SCRIPTS, mod),
                                            encoding="utf-8").read())):
            if isinstance(node, ast.Call):
                f = node.func
                called.add(f.attr if isinstance(f, ast.Attribute)
                           else getattr(f, "id", ""))
    assert not ({"write_levers", "get_lever", "market_open", "publish",
                 "publish_paper_trade", "apply_tuning"} & called), sorted(called)
    pay = cl.build(cl.grade_all({}, cl.CLAIMS, dt.date(2026, 8, 27)))
    assert pay["advisory"] is True and pay["moves_capital"] is False
    # the bus contract: a cross-read payload carries BOTH fields or no
    # consumer obeying `fleet_bus.is_fresh` can ever be written for it
    assert pay["updated"] and pay["ttl_sec"] > 0


# -------------------------------------------------------------------- selftests
@pytest.mark.parametrize("mod", ["scripts.claims_ledger",
                                 "scripts.audit_claim_freshness"])
def test_selftest_is_offline_and_green(mod):
    env = dict(os.environ)
    env.pop("DATABASE_URL", None)
    r = subprocess.run([sys.executable, "-m", mod, "--selftest"], cwd=ROOT,
                       capture_output=True, text=True, timeout=120, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
