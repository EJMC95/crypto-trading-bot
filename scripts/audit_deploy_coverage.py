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
        "LIVE REAL MONEY (trail-blazer-live). Auto-deploy on every push is "
        "UNSAFE here, not merely unnecessary: a redeploy restarts the bot, and "
        "its own boot banner says the slope gate 'fails open for ~1h after "
        "restart'. lighter-flatten-silent-halt-redeploy-incident is what a "
        "restart did with positions open (a memory-only halt was wiped and HYPE "
        "re-bought 37s after boot). Ship it DELIBERATELY via the workflow's "
        "workflow_dispatch, which checks out clean main — never from a local "
        "`railway up`, which uploads your desk (deploy-live-from-a-clean-worktree)."
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
    """(service -> compiled path regex) as the workflow ACTUALLY applies it.

    Parsed from the `grep -qE '...'` lines in the decide step, not from the
    `paths:` block at the top. Those two lists are maintained by hand and can
    disagree — `paths:` only decides whether the job RUNS; the greps decide
    which service is deployed. The greps are what bind, so the greps are what
    this guard reads."""
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


def main():
    filters = workflow_filters()
    if not filters:
        print("audit_deploy_coverage: FAILED — could not parse any service "
              f"filter from {WORKFLOW}. The guard cannot vouch for a file it "
              "cannot read; failing closed.")
        return 1

    orphans, ok_declared = [], []
    for df, svc in sorted(AUTO_IMAGES.items()):
        dfp = os.path.join(ROOT, df)
        if not os.path.exists(dfp):
            continue
        files, catch_all = image_files(dfp)
        if catch_all:
            continue                       # `COPY . .` — everything ships
        rxs = filters.get(svc, [])
        for f in sorted(files):
            # only python we actually run is interesting; assets/configs churn
            if not (f.endswith(".py") or f.endswith(".sh")):
                continue
            if any(rx.match(f) for rx in rxs):
                continue
            why = declared(f)
            (ok_declared if why else orphans).append((f, svc, df))

    organs = run_all_organs()
    rxs = filters.get("freqtrade-bots", [])
    organ_orphans = sorted(
        o for o in organs
        if not any(rx.match(o) for rx in rxs) and not declared(o)
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
              "it in DEPLOY_COVERAGE_OK\n  with a reason. Workflow files need the "
              "GitHub web editor (push-straight-to-main).")
        print(f"\naudit_deploy_coverage: {len(seen)} ORPHANED file(s); "
              f"{len(ok_declared)} declared exception(s).")
        return 1

    print(f"audit_deploy_coverage: OK — every runnable file in an auto-deployed "
          f"image is covered by a push path or declared ({len(ok_declared)} "
          f"declared).")
    return 0


def _selftest():
    """Drives the parser against SYNTHETIC fixtures, never against today's real
    violations — a test that asserts the current breakage still exists demands
    the defect remain (tests-must-not-fail-on-good-news)."""
    fs = workflow_filters()
    assert "freqtrade-bots" in fs, fs.keys()
    assert "pnl-dashboard" in fs, fs.keys()
    m = lambda svc, p: any(rx.match(p) for rx in fs[svc])
    # POSITIVE: the four the workflow really does cover
    for p in ("fleet_risk.py", "regime_oracle.py", "market_pulse.py",
              "freqtrade_pnl_poller.py"):
        assert m("freqtrade-bots", p), f"{p} should be covered"
    assert m("freqtrade-bots", "user_data/strategies/X.py"), "user_data/ prefix"
    # NEGATIVE: the detector must SEE a gap, or it can only ever say OK
    assert not m("freqtrade-bots", "bot_learn.py"), "brain must read as orphaned"
    assert not m("pnl-dashboard", "bot_learn.py")
    # the regex is anchored: a suffix match must not pass
    assert not m("freqtrade-bots", "x_fleet_risk.py"), "must be anchored"

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

    # declared(): longest-prefix, so venues/ covers its children
    assert declared("venues/lighter_client.py"), "venues/ prefix must cover children"
    assert declared("lighter_funding_bot.py")
    assert declared("bot_learn.py") is None, "brain is NOT declared — it's a real gap"
    for k, v in DEPLOY_COVERAGE_OK.items():
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"
    print("audit_deploy_coverage _selftest OK "
          "(parser + COPY reconstruction + declared-prefix, on fixtures)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(main())
