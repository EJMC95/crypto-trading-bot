#!/usr/bin/env python3
"""
scripts/audit_deploy_coverage.py — does a change to this file ever REACH the fleet?

╔══════════════════════════════════════════════════════════════════════════╗
║ WHY THIS EXISTS (measured 2026-07-17, and it is the whole story)          ║
║                                                                          ║
║ CLAUDE.md says: "Deploy trigger: push to main branch → Railway auto-      ║
║ deploys". **That is FALSE for 16 of the 20 organs in run_all.sh and for   ║
║ BOTH real-money bots.** Measured, not inferred:                           ║
║                                                                          ║
║  * NOT ONE of the 12 Railway services is git-connected — `railway         ║
║    variables` returns zero RAILWAY_GIT_* keys on every one. Railway-side  ║
║    Auto Deploy is OFF fleet-wide.                                         ║
║  * The ONLY automated path is `.github/workflows/railway-redeploy.yml`,   ║
║    which runs `railway up` — but only for a HARDCODED path list, and only ║
║    for freqtrade-bots / pnl-dashboard / funding-carry.                    ║
║  * That list was last extended 2026-07-07. Everything built since — the   ║
║    ENTIRE intelligence layer (bot_learn, experiment_judge, evidence_board,║
║    fleet_immune, fleet_proprioception, fleet_regen, fleet_respiration,    ║
║    implementation_shortfall, lighter_market_scout, lighter_scout_tuner,   ║
║    strategy_incubator, event_sentinel, fleet_clock) plus lighter_ticket_  ║
║    taker — ships ONLY when a human remembers `railway up`.                ║
║  * The retired HL `funding-carry` arm auto-deploys. The LIVE Funding      ║
║    Farmer does not.                                                       ║
║                                                                          ║
║ WHAT IT COST: six commits of fill telemetry landed 2026-07-17 between     ║
║ 04:27 and 10:52 UTC. The funding container booted 04:34 and never picked  ║
║ any of them up. `venue_orders` has never carried a `measured` or          ║
║ `fill_src` key — 58 real orders, 0 measured fills — and the Funding       ║
║ Farmer's entire gate/stop verdict turns on the friction number that       ║
║ telemetry exists to measure. The code was right. It was never running.    ║
║ This is the mechanism behind every "frozen service" incident in           ║
║ [[railway-cli-frozen-services]]: not mystery, a stale list.               ║
║                                                                          ║
║ THE 7-JUL COMMENT IN THAT WORKFLOW SAYS IT ALREADY HAPPENED ONCE:         ║
║   "cross-bot layer (runs inside freqtrade-bots via run_all.sh) — added    ║
║    2026-07-07 after 9cedf08 (SUI + historize) silently didn't deploy"     ║
║ They added the two organs that had bitten them and left the list to rot   ║
║ again. **A list that must be remembered is the control that already       ║
║ failed.** Hence a guard, not a longer list.                               ║
╚══════════════════════════════════════════════════════════════════════════╝

WHAT IT CHECKS. For each image, the Dockerfile declares what is IN it (COPY)
and what it RUNS (CMD / run_all.sh). The workflow declares which paths trigger
a deploy of which service. A file that ships in an auto-deployed image but is
NOT on that image's path filter is ORPHANED: editing it is a silent no-op.

WHAT IT DELIBERATELY DOES NOT CHECK. Whether a service is git-connected, and
whether the running container matches git — both need the network, and this
guard must stay a static, offline, CI-safe check like its siblings
(audit_image_imports / audit_venue_purity / audit_sdk_pin). Marker-grepping
the RUNNING container remains the only proof a deploy landed
([[railway-cli-frozen-services]]); this catches the class one level earlier —
the change that could never have deployed in the first place.

Read-only. Touches no bot, no DB, no network.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "railway-redeploy.yml")

# ---------------------------------------------------------------------------
# DECLARED: a file here is KNOWN not to auto-deploy, WITH A REASON. Silence is
# not an option — the same rule as BORN_DARK_OK. A reason must say why the
# omission is correct, not merely restate it.
# ---------------------------------------------------------------------------
DEPLOY_COVERAGE_OK = {
    "lighter_funding_bot.py": (
        "LIVE REAL MONEY (trail-blazer-live). Auto-deploy on EVERY push stays "
        "marker-gated for two CURRENT reasons: (1) a push may carry unfinished "
        "WIP and a redeploy RESTARTS a real-money book; (2) the slope gate 'fails "
        "open ~1h after restart' (in-process history), so each restart relaxes a "
        "validated ENTRY refinement. The earlier memory-only-halt hazard "
        "(lighter-flatten-silent-halt-redeploy-incident: a halt wiped, HYPE "
        "re-bought 37s after boot) is NO LONGER the reason — it was FIXED: the "
        "daily-loss halt (07-11), day-start baseline (07-21 D3), and post-stop "
        "quarantine (07-22) all survive restarts now ('a restart no longer "
        "re-arms a stopped coin'). Ship DELIBERATELY via workflow_dispatch OR the "
        "[deploy-live-farmer]/[deploy-live] commit marker (both check out clean "
        "main; added 2026-07-25) — never on EVERY push, never from a local "
        "`railway up` which uploads your desk (deploy-live-from-a-clean-worktree)."
    ),
    "lighter_trend_bot.py": (
        "Same restart hazard as lighter_funding_bot.py, and its service "
        "(tide-rider-lighter-live) now runs the Ticket Taker's image. Its live "
        "row is RETIRED and REAL_MONEY_KILL is the only thing holding it — an "
        "automatic redeploy of this file is exactly the loaded gun in "
        "golive-name-the-image-before-the-env. Operator-dispatched only."
    ),
    "lighter_ticket_taker.py": (
        "LIVE REAL MONEY since 17-Jul (tide-rider-lighter-live, "
        "Dockerfile.tickettaker). Same deliberate-dispatch rule as the Farmer. "
        "NOTE it also runs as a SHADOW arm inside freqtrade-bots via run_all.sh, "
        "so a freqtrade-bots deploy DOES move the shadow twin — the two arms can "
        "drift, and that is a real hazard worth a review item, not a reason to "
        "auto-ship the live one."
    ),
    "venues/": (
        "The shared real-money surface (SafetyRails, notional caps, the signer, "
        "the fill read). Imported by BOTH live bots; auto-deploying it would "
        "auto-restart them. Same operator-dispatch rule."
    ),
}


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def workflow_filters():
    """(service -> compiled path regex) from the `grep -qE` lines in the decide
    step — the list that chooses WHICH SERVICE gets deployed."""
    src = _read(WORKFLOW)
    out = {}
    # grep -qE '<regex>'; then svcs="<name>"  /  svcs="${svcs:+$svcs,}<name>"
    for m in re.finditer(
        r"grep\s+-qE\s+'([^']+)'.*?\n\s*svcs=\"(?:\$\{svcs:\+\$svcs,\})?([a-z0-9-]+)\"",
        src, re.S,
    ):
        rx, svc = m.group(1), m.group(2)
        out.setdefault(svc, []).append(re.compile(rx))
    return out


def workflow_paths():
    """The `on: push: paths:` globs — the list that decides whether the job RUNS
    AT ALL.

    [2026-07-17 CORRECTION — this guard shipped with a FALSE-OK.] It read only
    the greps above and argued in its own docstring that "the greps are what
    bind". Wrong, and backwards: `paths:` is evaluated by GitHub BEFORE the job
    starts. A file present in a grep but absent from `paths:` never reaches the
    grep, because the workflow never runs. So the binding list is the INTERSECTION
    — a file needs BOTH — and a guard that checked only one half would hand out a
    green OK for a file that can never deploy. That is the exact failure class
    this file exists to catch, committed inside the file catching it.
    Found by reconciling with scripts/audit_deploy_filter.py, which a concurrent
    session wrote against the SAME bug from the other side: it checks `paths:`
    and not the greps. Neither guard was right alone."""
    src = _read(WORKFLOW)
    m = re.search(r"^\s*paths:\s*\n((?:\s*(?:#.*)?\n|\s*-\s*'[^']+'\s*\n)+)",
                  src, re.M)
    if not m:
        return None                     # unparseable -> caller fails closed
    return [g.group(1) for g in re.finditer(r"-\s*'([^']+)'", m.group(1))]


def _path_listed(rel, globs):
    """Does `rel` match any `paths:` glob? Supports the two forms the workflow
    actually uses: an exact filename and a `dir/**` prefix."""
    for g in globs:
        if g.endswith("/**"):
            if rel.startswith(g[:-2]):
                return True
        elif g == rel:
            return True
    return False


def image_files(dockerfile):
    """Repo-relative paths COPY'd into an image. Mirrors audit_image_imports's
    reconstruction closely enough for coverage: multi-source COPY, `COPY dir/`,
    and the `COPY . .` catch-all."""
    files, catch_all = set(), False
    for line in _read(dockerfile).splitlines():
        line = line.strip()
        if not line.upper().startswith("COPY "):
            continue
        parts = line[5:].split()
        parts = [p for p in parts if not p.startswith("--")]
        if len(parts) < 2:
            continue
        for src in parts[:-1]:            # last token is the destination
            if src == ".":
                catch_all = True
            else:
                files.add(src.rstrip("/") + ("/" if src.endswith("/") else ""))
    return files, catch_all


def run_all_organs():
    p = os.path.join(ROOT, "run_all.sh")
    if not os.path.exists(p):
        return set()
    return set(re.findall(r"([a-z_]+\.py)", _read(p)))


def declared(path):
    """Longest-prefix match, so `venues/` covers `venues/lighter_client.py`."""
    if path in DEPLOY_COVERAGE_OK:
        return DEPLOY_COVERAGE_OK[path]
    for k, v in DEPLOY_COVERAGE_OK.items():
        if k.endswith("/") and path.startswith(k):
            return v
    return None


# Dockerfile -> the service the workflow can deploy. Only images the workflow
# knows about can be covered at all; the rest are manual by construction.
AUTO_IMAGES = {"Dockerfile.freqtrade": "freqtrade-bots",
               "Dockerfile.dashboard": "pnl-dashboard",
               "Dockerfile.funding": "funding-carry"}


_UNSET = object()   # "not supplied" — distinct from None, which means UNPARSEABLE


def covered(svc, rel, filters=_UNSET, globs=_UNSET):
    """Can a push to `rel` deploy `svc`? BOTH lists must contain it.

    Module-level ON PURPOSE. This was a lambda inside main(), and the selftest
    that "proved" the both-lists rule mutation-SURVIVED reverting it to grep-only
    — because the test drove _path_listed() in isolation and never touched the
    integration. A test that cannot fail when the rule is removed is decoration.
    Same closure-untestable shape as lighter_funding_bot's fill helpers, made by
    the same author, one hour later."""
    # [2026-07-17] _UNSET, not None. `globs=None` used to mean BOTH "caller did
    # not supply it, go read the workflow" AND "the paths: block did not parse".
    # One value, two meanings — the load_state_seeds_on_a_failed_read shape — and
    # it made the fail-closed branch UNREACHABLE from a test: passing None just
    # re-fetched the real workflow. My mutation test caught it by surviving.
    filters = workflow_filters() if filters is _UNSET else filters
    globs = workflow_paths() if globs is _UNSET else globs
    if globs is None:
        return False                      # unparseable paths: -> fail CLOSED
    return (any(rx.match(rel) for rx in filters.get(svc, []))
            and _path_listed(rel, globs))


def main():
    filters = workflow_filters()
    globs = workflow_paths()
    if not filters or globs is None:
        print("audit_deploy_coverage: FAILED — could not parse the workflow's "
              f"{'service greps' if not filters else 'paths: block'} from "
              f"{WORKFLOW}. The guard cannot vouch for a file it cannot read; "
              "failing closed.")
        return 1
    # A file must be in BOTH lists to deploy: `paths:` gates whether the job
    # runs, the greps choose the service. Fold `paths:` into the service test so
    # a file listed in one and not the other is reported, not passed.
    _cov = lambda svc, p: covered(svc, p, filters, globs)

    orphans, ok_declared = [], []
    for df, svc in sorted(AUTO_IMAGES.items()):
        dfp = os.path.join(ROOT, df)
        if not os.path.exists(dfp):
            continue
        files, catch_all = image_files(dfp)
        if catch_all:
            continue                       # `COPY . .` — everything ships
        for f in sorted(files):
            # only python we actually run is interesting; assets/configs churn
            if not (f.endswith(".py") or f.endswith(".sh")):
                continue
            if _cov(svc, f):
                continue
            why = declared(f)
            (ok_declared if why else orphans).append((f, svc, df))

    organs = run_all_organs()
    organ_orphans = sorted(
        o for o in organs
        if not _cov("freqtrade-bots", o) and not declared(o)
        and os.path.exists(os.path.join(ROOT, o))
    )

    if orphans or organ_orphans:
        print("DEPLOY-ORPHANED — these ship in an auto-deployed image but no "
              "push can move them.\nEditing one is a SILENT NO-OP: green CI, "
              "green tests, old code still running.\n")
        seen = set()
        for f, svc, df in orphans:
            if f in seen:
                continue
            seen.add(f)
            print(f"  {f:<32} in {df} -> service {svc}")
        for o in organ_orphans:
            if o in seen:
                continue
            seen.add(o)
            print(f"  {o:<32} launched by run_all.sh -> service freqtrade-bots")
        print("\n  Fix: add the path to BOTH the `paths:` block AND the service's "
              "`grep -qE` in\n  .github/workflows/railway-redeploy.yml — or DECLARE "
              "it in DEPLOY_COVERAGE_OK\n  with a reason. Both lists bind: `paths:` "
              "gates whether the job RUNS,\n  the grep picks the service. A file in "
              "one and not the other cannot deploy.\n  (You CAN `git push` a "
              "workflow file — the PAT has the scope. TESTED 17-Jul,\n  ce446c7. "
              "The 'web editor only' caveat is FALSE and was steering sessions\n"
              "  away from CI fixes for weeks — see push-straight-to-main.)")
        print(f"\naudit_deploy_coverage: {len(seen)} ORPHANED file(s); "
              f"{len(ok_declared)} declared exception(s).")
        return 1

    print(f"audit_deploy_coverage: OK — every runnable file in an auto-deployed "
          f"image is covered by a push path or declared ({len(ok_declared)} "
          f"declared).")
    return 0


def _extract_live_marker_block():
    """The decide step's OPT-IN live-bot marker logic, lifted verbatim from the
    workflow: the lines from `msgs="$(git log ...` through the fi that closes the
    trail-blazer-live (Farmer) block. Returns the raw lines (list). Raises if the
    gate is missing/unclosed — a real-money deploy gate that vanished must not
    read as 'nothing to test'."""
    lines = _read(WORKFLOW).splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if 'msgs="$(git log' in l)
    except StopIteration:
        raise AssertionError("live-bot marker block not found (no `msgs=$(git log` "
                             "line) — the opt-in real-money deploy gate may be gone")
    block, seen_farmer = [], False
    for l in lines[start:]:
        block.append(l)
        if "trail-blazer-live" in l:
            seen_farmer = True
        if seen_farmer and l.strip() == "fi":
            return block
    raise AssertionError("live-bot marker block never closed (no Farmer `fi`)")


def _marker_logic_selftest():
    """Behavioral test of the OPT-IN live-bot deploy markers, BOUND to the real
    decide-step bash (extracted above, run under bash) so a future edit that lets
    an UNMARKED push deploy real money turns this RED. Synthetic INPUTS, real
    LOGIC, safety-INVARIANT assertions — the covered() pattern applied to the
    marker gate. 'No marker -> no real-money deploy' is a CONTRACT, not today's
    tree state, so asserting it is not the good-news-fails trap _selftest() avoids
    elsewhere. Skips only if bash is genuinely absent (never on a real assertion)."""
    import shutil
    import subprocess
    if not shutil.which("bash"):
        print("  (marker-logic test SKIPPED — no bash on this host)")
        return
    block = _extract_live_marker_block()
    joined = "\n".join(block)
    # sanity: we grabbed the REAL gate, not a gutted stub (else a mutation that
    # deletes the block would make the behavioral cases vacuously pass)
    for needle in ("[deploy-live-taker]", "[deploy-live-farmer]", "[deploy-live]",
                   "tide-rider-lighter-live", "trail-blazer-live", "live_all"):
        assert needle in joined, f"marker gate missing {needle!r} — refusing to vouch"
    indent = min(len(l) - len(l.lstrip()) for l in block if l.strip())
    body = [l[indent:] if len(l) >= indent else l for l in block]
    body[0] = 'msgs="$2"'            # swap the git-log fetch for the fixture
    script = ("set -uo pipefail\n"
              'changed="$1"; svcs=""; live_all=0\n'
              "{\n" + "\n".join(body) + "\n} >/dev/null\n"   # drop the '-> marker' echoes
              'printf "%s" "$svcs"\n')

    def decide(changed, msgs):
        r = subprocess.run(["bash", "-c", script, "b", changed, msgs],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"decide bash failed ({r.returncode}): {r.stderr}"
        return r.stdout.strip()

    T, F = "tide-rider-lighter-live", "trail-blazer-live"
    cases = [
        # HAZARD — an unmarked push must NEVER deploy a real-money book
        ("lighter_funding_bot.py", "fix funding slope", ""),
        ("lighter_ticket_taker.py", "tweak taker", ""),
        ("venues/safety.py", "rails tweak", ""),
        (f"lighter_funding_bot.py\nvenues/safety.py", "Farmer WIP (dark)", ""),
        # intended deploys
        ("lighter_funding_bot.py", "ship [deploy-live-farmer]", F),
        ("lighter_funding_bot.py", "both [deploy-live]", F),
        ("lighter_ticket_taker.py", "ship [deploy-live-taker]", T),
        ("lighter_ticket_taker.py", "ship [deploy-live]", T),
        ("venues/safety.py", "shared [deploy-live]", f"{T},{F}"),
        # isolation: a bot-only [deploy-live] must NOT restart the other bot
        ("lighter_funding_bot.py", "farmer-only [deploy-live]", F),
        ("lighter_ticket_taker.py", "taker-only [deploy-live]", T),
        # wrong marker for the changed file does nothing
        ("lighter_funding_bot.py", "wrong [deploy-live-taker]", ""),
    ]
    for changed, msgs, exp in cases:
        got = decide(changed, msgs)
        assert got == exp, (f"marker gate BROKEN: changed={changed!r} msgs={msgs!r} "
                            f"-> {got!r}, want {exp!r}")


def _selftest():
    """Drives the parser against SYNTHETIC fixtures, never against today's real
    violations — a test that asserts the current breakage still exists demands
    the defect remain (tests-must-not-fail-on-good-news)."""
    fs = workflow_filters()
    assert "freqtrade-bots" in fs, fs.keys()
    assert "pnl-dashboard" in fs, fs.keys()
    m = lambda svc, p: any(rx.match(p) for rx in fs[svc])
    # POSITIVE: these four predate the 07-07 filter and must always be covered.
    for p in ("fleet_risk.py", "regime_oracle.py", "market_pulse.py",
              "freqtrade_pnl_poller.py"):
        assert m("freqtrade-bots", p), f"{p} should be covered"
    assert m("freqtrade-bots", "user_data/strategies/X.py"), "user_data/ prefix"
    # NEGATIVE — on a SYNTHETIC regex, never on the real tree.
    # [2026-07-17] This line used to be `assert not m("freqtrade-bots",
    # "bot_learn.py"), "brain must read as orphaned"` — and it went RED the hour
    # someone ADDED the brain to the filter. A test that fails on GOOD NEWS is a
    # test that demands the defect remain, and this file's own selftest docstring
    # says so three lines up. I wrote the warning and the violation in the same
    # commit. The detector's ability to SEE a gap is a property of the regex, so
    # prove it on a fixture whose gap cannot be fixed out from under it.
    import re as _re
    fake = [_re.compile(r"^(only_this\.py$)")]
    _m = lambda p: any(rx.match(p) for rx in fake)
    assert _m("only_this.py"), "fixture sanity"
    assert not _m("bot_learn.py"), "detector must be able to report a gap"
    assert not _m("x_only_this.py"), "must be anchored"
    assert not _m("only_this.pyc"), "must be exact, not a prefix"

    # COPY reconstruction, incl. the multi-source form
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "Dockerfile.t")
        open(p, "w").write("FROM x\nCOPY a.py b.py /app/\nCOPY venues/ /app/venues/\n")
        f, ca = image_files(p)
        assert f == {"a.py", "b.py", "venues/"}, f
        assert ca is False
        open(p, "w").write("FROM x\nCOPY . .\n")
        _, ca = image_files(p)
        assert ca is True, "COPY . . must set catch_all (everything ships)"

    # BOTH lists bind: `paths:` gates the job, the greps pick the service.
    # Today the real workflow's two lists agree, so this is a LATENT false-OK —
    # it fires the moment someone edits one list and not the other, which is
    # precisely what extending this workflow requires. Fixtures, so the test
    # proves the RULE rather than today's accident.
    globs = ["'x'"] and ["bot_learn.py", "user_data/**"]
    assert _path_listed("bot_learn.py", globs)
    assert _path_listed("user_data/strategies/S.py", globs), "dir/** prefix"
    assert not _path_listed("fleet_risk.py", globs), "must not match by accident"
    assert not _path_listed("bot_learn.pyc", globs), "exact filename, not prefix"
    # the false-OK itself: in a grep, absent from paths: -> CANNOT deploy
    grep_ok = True
    assert not (grep_ok and _path_listed("fleet_risk.py", globs)), \
        "a file in the grep but not paths: must NOT read as covered"
    assert workflow_paths() is not None, "real paths: block must parse"
    assert len(workflow_paths()) > 5, "paths: parse looks truncated"

    # DRIVE covered() ITSELF — with injected fixtures, not around it.
    # My first two attempts at this test both mutation-SURVIVED: the assertions
    # exercised _path_listed() and a local lambda, so reverting the real rule to
    # grep-only changed nothing and the suite stayed green. Testing AROUND a
    # function is not testing it. covered() takes filters/globs as parameters
    # precisely so this can reach it.
    F = {"svc": [re.compile(r"^(a\.py$|b\.py$)")]}
    assert covered("svc", "a.py", F, ["a.py"]) is True, "in BOTH lists -> deploys"
    assert covered("svc", "b.py", F, ["a.py"]) is False, \
        "in the GREP but not paths: -> the job never runs -> must NOT read covered"
    assert covered("svc", "a.py", F, []) is False, "paths: empty -> nothing runs"
    assert covered("svc", "z.py", F, ["z.py"]) is False, \
        "in paths: but no grep -> job runs, deploys nothing -> not covered"
    assert covered("svc", "a.py", F, None) is False, \
        "unparseable paths: must fail CLOSED, never open"
    assert covered("nope", "a.py", F, ["a.py"]) is False, "unknown service"

    # declared(): longest-prefix, so venues/ covers its children
    assert declared("venues/lighter_client.py"), "venues/ prefix must cover children"
    assert declared("lighter_funding_bot.py")
    assert declared("bot_learn.py") is None, "brain is NOT declared — it's a real gap"
    for k, v in DEPLOY_COVERAGE_OK.items():
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"
    # the OPT-IN live-bot marker gate — bound to the real workflow bash
    _marker_logic_selftest()
    print("audit_deploy_coverage _selftest OK "
          "(parser + COPY reconstruction + declared-prefix + live-bot marker gate, "
          "on fixtures)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(main())
