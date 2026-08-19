#!/usr/bin/env python3
"""audit_boot_stagger.py — CAN EVERY ORGAN ACTUALLY REACH ITS FIRST RUN?

WHY (2026-08-16). `run_all.sh` starts each organ behind a boot stagger —
`( sleep N; while true; do <organ>; sleep INTERVAL; done ) &` — to spread load
across a container start. **A push is a deploy, and a deploy restarts every one
of those timers from zero.** So an organ whose stagger exceeds the interval
between deploys never reaches its first run at all.

MEASURED the day this shipped, 03:02–04:40 UTC: 25 successful redeploy runs,
median gap **3.0 min**, minimum 6 seconds. Against 🚦 `golive_readiness`'s
**900s** stagger, **24 of 24** inter-deploy gaps were shorter, so its first
post-deploy publish kept being pushed back.

**STATED HONESTLY, BECAUSE MY FIRST READING OF THIS WAS WRONG:** the grader was
never actually OVERDUE. It published six times that day — 01:26, 01:42, 02:30,
03:44, 04:47, 04:56 — a largest gap of **73.9 min against a 360 min interval**.
I read a 47-minute wait after a deploy as an outage and said "the rule that
governs real money could not publish"; the organ's own contract was met
comfortably throughout. **A delayed first run is not a missed run**, and a
guard built on my impatience would fire constantly on healthy organs.

So the failing condition here is CONTRACT-BASED, not rate-based: an organ fails
only when deploys arrived closer together than its TIME-TO-FIRST-RUN for longer
than its consumers tolerate. **Measured on the live fleet after this guard's own
parser was corrected: NOTHING fails.** Every organ runs within 6 minutes of
boot, and 8 of 20 within 35 seconds, because the common block shape is
`( sleep <small>; run; sleep <long>; while true; ... )` — an early run already.

The one organ that genuinely had a 900s time-to-first-run was 🚦 the go-live
grader, and it now has a staleness-gated early run. **So this guard's standing
job is not to report a problem — it is to notice when a NEW organ, or an edit
to an old one, reintroduces one.** The risk is real but latent: a burst
outlasting an organ's TTL would silence it, and nothing else in the fleet would
report that, because an organ that never reaches its first run is not sick — no
exception, no stale-key alarm from the organ itself, every liveness contract
green.

WHAT THIS CLOSES. Not the instance — that was fixed by giving the grader a
staleness-gated early run. This closes the CLASS: any organ, including ones not
yet written, whose stagger drifts past the fleet's real deploy cadence.

WHAT IT FAILS ON, deliberately narrow (a guard that fires on everything trains
the operator to ignore it — `(gl)`):

  FAIL   a PERIODIC organ, with NO early-run mitigation, for which deploys
         arrived closer together than its stagger CONTINUOUSLY FOR LONGER THAN
         ITS CONSUMERS TOLERATE — its published `ttl_sec` where that is
         readable, else a declared 3x-interval proxy. Past the TTL a reader
         goes neutral (`fleet_bus.is_fresh`), so that is the point at which
         silence stops being a delay and starts being an outage.

         AN EARLIER DRAFT FAILED ON `burst > interval` AND WAS WRONG: it
         flagged 🕐 `fleet_clock` for missing ONE five-minute advisory cycle,
         which is exactly the cry-wolf output this guard must not produce.
         Missing a cycle is normal and self-healing; outlasting the TTL is not.
  REPORT everything else — worst bursts, supervisors, mitigated organs. These
         are informational rows on a passing run and are not warnings anyone
         must act on.

WHY NOT FAIL ON A STARVE RATE: measured the same day, `evidence_board` (330s)
lost 75% of its races and still published at a median gap of 10.0 min — EXACTLY
its 600s interval. `bot_learn` lost 71% and still ran at boot+300s to the
second. Both were healthy; a rate-based rule would have failed both. The rate
says how often an organ loses a race, which is not the question. **The question
is whether it ever missed a cycle**, and only the burst DURATION answers it.

READ-ONLY. Parses a shell script and reads workflow history; changes nothing.
"""
from __future__ import annotations

import argparse
import ast
import datetime as dt
import json
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUN_ALL = ROOT / "run_all.sh"

#: A trailing loop sleep at or below this is a RESTART BACKOFF, not a publish
#: interval — the block supervises a long-running process (🏛️ parliament_main
#: runs an asyncio supervisor and publishes from inside it). Such a block has
#: no repeated invocation to gate on staleness, so the mitigation this guard
#: looks for does not apply and it is never failed.
SUPERVISOR_MAX_BACKOFF_S = 60

#: A first invocation at or under this is EARLY — the organ runs before its own
#: long stagger, so no deploy cadence can starve it. Not a number invented here:
#: it is the bar `tests/autonomy/test_immune_boot_execution.py` already asserts
#: on every starved organ, and the (ou) boot ladder tops out at 35s.
EARLY_RUN_MAX_S = 60

#: bot_state keys whose name is not the module name. Without these the TTL
#: lookup silently falls back to the 3x-interval PROXY, and the proxy was
#: measurably wrong in both directions (impl-shortfall real ttl 60 min vs a 90
#: min proxy; fleet-regen 40 vs 45). A guard should read the published contract.
#: ORGAN -> KEY IS NOT 1:1, and the strictest contract binds first. 🧠 bot_learn
#: alone publishes five keys with different TTLs, so the tolerance that matters
#: is the MINIMUM across the keys consumers actually gate on.
#: [CORRECTED 16-Aug, peer-caught] this mapped `bot_learn -> learning-brain`,
#: which is the brain's MEMORY BLOB and carries no `ttl_sec` at all — so the
#: lookup found nothing and fell straight back to the proxy the alias existed to
#: avoid, 360 min against a real 160. An alias doing the opposite of its job.
#: The brain's real consumer contracts are `brain-vitals` (9600s) and
#: `brain-stake-mults` (26000s); min = 9600.
KEY_ALIASES = {"implementation_shortfall": ("impl-shortfall",),
               "lighter_market_scout": ("lighter-market",),
               "lighter_scout_tuner": ("scout-tuner",),
               "bot_learn": ("brain-vitals", "brain-stake-mults"),
               "experiment_judge": ("xp-judge",),
               "golive_readiness": ("golive-readiness",)}

#: Organs deliberately exempt, with the reason. An exemption is a DECISION and
#: must name why — the `BORN_DARK_OK` idiom.
STAGGER_OK: dict[str, str] = {
    "lighter_ticket_taker": (
        "a trading BOOK, not a bus organ: it publishes no bot_state key with a "
        "ttl_sec, so the 3x-interval proxy (15 min) governs by fallback — but "
        "its only cross-process reader is its bot_pnl row behind fleet_risk's "
        "STALE_ROW_SEC=3900s (65 min) staleness filter, 4.3x the proxy. The "
        "19-Aug merge storm (a 17-min run of sub-210s commit gaps on the "
        "commit-time proxy) sat well inside that real contract, and the proxy "
        "alone turned the whole fleet's suite red ((rg)). This waives the "
        "PROXY, never the contract: a burst outlasting 65 min WOULD silence "
        "the row for real — revisit if the deploy cadence ever sustains that."),
}


def declares_flag(script: str, flag: str) -> bool | None:
    """Does the ORGAN actually implement the flag the SHELL hands it?

    None when the target cannot be read — fail-OPEN, because a guard that
    cannot see must not manufacture a finding.

    WHY THIS IS THE LOAD-BEARING CHECK, not a nicety. `(pe)`: a claim read off
    `run_all.sh` is a claim about the SHELL, not the organ. MEASURED on this
    repo — at `dc803be` the shell passed `--publish-if-stale` TWICE and
    `golive_readiness.py` declared it ZERO times, until `(pa)` supplied the
    missing half. argparse exits 2, `|| true` swallows it, the boot log reads

        error: unrecognized arguments: --publish-if-stale 21600

    and a shell parser calls that block correctly mitigated throughout. Static
    parse rather than `--help`: no imports, no venue calls, no side effects,
    and it works with no DB and no network.
    """
    rel = script.replace("/freqtrade/", "")
    try:
        src = (ROOT / rel).read_text()
    except Exception:      # noqa: BLE001
        return None
    return bool(re.search(r"add_argument\(\s*[\"']" + re.escape(flag), src))


def parse_blocks(text: str) -> list[dict]:
    """Every backgrounded organ block in run_all.sh, with its timings.

    Shape parsed:  ( [early run]  sleep <stagger>
                     while true; do <organ>.py ; sleep <interval> ; done ) &
    """
    out: list[dict] = []
    # The closing token is `... done ) &` on ONE line — `)` is NOT at the start
    # of its line. An anchor of `^\s*\)` matches nothing and the audit reports a
    # serene "0 organs", which is the reaper-that-reaps-nothing failure `(of)`
    # recorded. Anchor on `) &` at END of line instead, lazily.
    for m in re.finditer(r"^\((.*?)\)\s*&\s*$", text, re.S | re.M):
        body = m.group(1)
        org = re.search(r"python3\s+/freqtrade/(?:scripts/)?([A-Za-z_0-9]+)\.py", body)
        if not org:
            continue
        name = org.group(1)
        # THE NUMBER THAT MATTERS IS TIME-TO-FIRST-RUN — the sleeps before the
        # FIRST invocation, not every sleep before the loop.
        #
        # [CORRECTED 2026-08-16, and this bug had me about to "fix" four organs
        # that were already fixed.] Summing all pre-loop sleeps reads
        # `( sleep 20; run; sleep 660; while true; ... )` as a 680s stagger when
        # the organ actually runs at boot+20. Four organs use exactly that shape
        # — fleet_radar 35s, fleet_regen 20s, fleet_proprioception 10s,
        # implementation_shortfall 30s — and all four were reported FAIL. A
        # guard that invents work is worse than no guard; it was caught only by
        # reading the blocks it had accused.
        # AN INVOCATION THE ORGAN WILL REJECT IS NOT A FIRST RUN. `early` is a
        # POSITIONAL property, so a block whose first line is an early run
        # scores stagger 0 even when that run dies on `unrecognized arguments`
        # and `|| true` hides it — which is exactly what shipped here between
        # `dc803be` and `(pa)`. So walk the invocations in order and take the
        # first EFFECTIVE one: the first whose flags the target actually
        # declares. Unreadable target ⇒ fail-OPEN, counted as effective.
        inert: list[str] = []
        first_ok = org                      # fallback: the first invocation
        for inv in re.finditer(
                r"python3\s+(/freqtrade/(?:scripts/)?[A-Za-z_0-9]+\.py)([^\n]*)", body):
            flags = re.findall(r"(--[a-z][a-z0-9-]*)", inv.group(2))
            bad = [f for f in flags if declares_flag(inv.group(1), f) is False]
            if not bad:
                first_ok = inv
                break
            inert.extend(bad)
        head = body[:first_ok.start()]
        st_m = re.findall(r"sleep\s+\"?\$?\{?[A-Z_]*:?-?(\d+)\}?\"?", head)
        stagger = sum(int(x) for x in st_m) if st_m else 0
        # EARLY = "no sleep longer than EARLY_RUN_MAX_S precedes the first
        # invocation" — the fleet's OWN property and bar, not one invented here:
        # `tests/autonomy/test_immune_boot_execution.py::
        # test_every_starved_organ_runs_once_before_its_long_stagger` asserts
        # `before[0] <= 60` on every starved organ, and the (ou) ladder tops out
        # at 35s, so there is deliberate headroom.
        # [CORRECTED 16-Aug, peer-caught] this was `"--publish-if-stale" in body`
        # under a comment claiming it meant "runs before its own long sleep". It
        # did not: 🛡️ fleet_immune — the canonical early-run organ this whole fix
        # began with — parsed as NOT early, 1 of 20 fleet-wide. The verdict was
        # unaffected (`stagger_s` already carried reachability) but a field whose
        # name and comment disagree with its value is a defect waiting to be read.
        early = stagger <= EARLY_RUN_MAX_S
        # The CHEAP early run — reachable AND free when the key is already
        # fresh. Named separately because it is the pattern worth spreading.
        gated = ("--publish-if-stale" in body
                 and declares_flag("scripts/golive_readiness.py",
                                   "--publish-if-stale") is not False)
        # The loop interval: the last `sleep` inside the loop body.
        loop = body.split("while true", 1)[1] if "while true" in body else ""
        iv_m = re.findall(r"sleep\s+\"?\$?\{?[A-Z_]*:?-?(\d+)\}?\"?", loop)
        interval = int(iv_m[-1]) if iv_m else None
        kind = ("supervisor" if interval is not None
                and interval <= SUPERVISOR_MAX_BACKOFF_S else "periodic")
        out.append({"organ": name, "stagger_s": stagger, "interval_s": interval,
                    "early": early, "gated": gated, "mitigated": early or gated,
                    "inert_flags": sorted(set(inert)), "kind": kind})
    return out


def deploy_times(limit: int = 60) -> tuple[list[dt.datetime], str]:
    """Deploy instants, newest-first source preferred. Returns (times, source).

    The honest signal is the deploy workflow's own successful runs. Falls back
    to commit timestamps on `origin/main` — a PROXY, declared as one, because
    several commits can ride a single push and so a single deploy.
    """
    try:
        raw = subprocess.run(
            ["gh", "run", "list", "--workflow", "Railway Redeploy",
             "--limit", str(limit), "--json", "createdAt,conclusion"],
            capture_output=True, text=True, timeout=90, cwd=ROOT).stdout
        rows = [r for r in json.loads(raw) if r.get("conclusion") == "success"]
        ts = sorted(dt.datetime.fromisoformat(r["createdAt"].replace("Z", "+00:00"))
                    for r in rows)
        if len(ts) >= 3:
            return ts, "gh:Railway Redeploy (successful runs)"
    except Exception:      # noqa: BLE001 — any failure falls through to git
        pass
    # [2026-08-17 (pi)] TRY `HEAD` TOO, not just `origin/main`. CI checks out a
    # DETACHED HEAD, so `origin/main` may not be a ref there at all — and this
    # is the only tier CI can ever reach, because `gh run list` above needs
    # `actions: read` and CI's GITHUB_TOKEN does not have it. With both tiers
    # dark the audit returned `[]` and asserted NOTHING, so an ENFORCED_AUDITS
    # member was structurally incapable of failing the build it gates.
    for ref in ("origin/main", "HEAD"):
        try:
            raw = subprocess.run(
                ["git", "log", "-n", str(limit), "--format=%cI", ref],
                capture_output=True, text=True, timeout=60, cwd=ROOT).stdout
            ts = sorted(dt.datetime.fromisoformat(l.strip())
                        for l in raw.splitlines() if l.strip())
            if len(ts) >= 3:
                return ts, (f"git:{ref} commit times "
                            "(PROXY — commits batch into pushes)")
        except Exception:      # noqa: BLE001
            continue
    return [], "unavailable"


def gaps_of(times: list[dt.datetime]) -> list[float]:
    return [(b - a).total_seconds() for a, b in zip(times, times[1:])]


def _const_ints(tree: ast.Module) -> dict[str, float]:
    """Module-level names bound to an integer, for the forms organs actually use.

    MODULE LEVEL ONLY (`tree.body`, never `ast.walk`). A whole-tree walk picks
    up `--selftest` FIXTURES — that mistake produced a table claiming the proxy
    was wrong by 18x when the true worst case is 1.50x.
    """
    out: dict[str, float] = {}

    def val(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return float(n.value)
        if isinstance(n, ast.Name):
            return out.get(n.id)
        # int(os.environ.get("NAME", "2400")) — the declared default is the
        # value every container runs unless someone overrides it.
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
                and n.func.id in ("int", "float") and n.args):
            inner = n.args[0]
            if (isinstance(inner, ast.Call) and isinstance(inner.func, ast.Attribute)
                    and inner.func.attr == "get" and len(inner.args) >= 2
                    and isinstance(inner.args[1], ast.Constant)):
                try:
                    return float(inner.args[1].value)
                except (TypeError, ValueError):
                    return None
            return val(inner)
        if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
            a, b = val(n.left), val(n.right)
            return a * b if a is not None and b is not None else None
        return None

    for node in tree.body:
        if isinstance(node, ast.Assign):
            v = val(node.value)
            if v is None:
                continue
            for t in node.targets:
                if isinstance(t, ast.Name):
                    out[t.id] = v
    return out


def static_ttls(organs: list[str]) -> dict[str, tuple[float, str]]:
    """{organ: (seconds, source)} read from each organ's SOURCE — no database.

    WHY THIS TIER EXISTS (2026-08-16, peer-found). The live read below is
    unavailable in the one place this guard gates a build: neither `tests.yml`
    nor `changelog-check.yml` sets `DATABASE_URL`, so `tolerances()` resolves
    NOTHING in CI and all 20 organs fall to the 3x proxy. Every improvement
    built on the DB read — including the min-across-keys fix — is therefore
    inert at the gate.

    Every organ declares its payload TTL as a module-level `*TTL_SEC` constant,
    so the real contract is readable with no database at all. The `*TTL_SEC`
    suffix is the discriminator and it is exact: it captures all 17 payload
    constants and excludes every LEVER ttl (`LEVER_TTL`, `LIVE_LEVER_TTL_S`,
    `RELEASE_REQ_TTL`, `QUALITY_VETO_TTL_S`), which are unrelated quantities
    that would corrupt the number.

    THE MINIMUM across an organ's TTL constants, for the same reason
    `tolerances()` takes it across keys: an organ is silent on all of them at
    once, so the strictest consumer contract binds.
    """
    out: dict[str, tuple[float, str]] = {}
    for o in organs:
        path = ROOT / f"{o}.py"
        if not path.exists():
            path = ROOT / "scripts" / f"{o}.py"
        if not path.exists():
            continue
        try:
            consts = _const_ints(ast.parse(path.read_text()))
        except Exception:                        # noqa: BLE001 — unreadable ⇒ no claim
            continue
        found = [v for k, v in consts.items() if k.endswith("TTL_SEC") and v > 0]
        if found:
            out[o] = (min(found), "ttl_sec from source" if len(found) == 1
                      else f"min of {len(found)} ttl_sec from source")
    return out


def tolerances(organs: list[str]) -> dict[str, tuple[float, str]]:
    """{organ: (seconds, source)} — how long a consumer tolerates silence.

    THE CONTRACT IS `ttl_sec`, not the interval. Every payload carries one and
    `fleet_bus.is_fresh` is what consumers actually gate on, so a burst only
    HURTS once it exceeds the TTL — past that, readers go neutral. Missing one
    cycle of a 5-minute advisory clock is not a defect and must not fail a
    build (that is the cry-wolf failure `(gl)` names).

    Read from the live keys when a DB is reachable; otherwise fall back to a
    declared 3x-interval proxy, so the guard still works offline and says which
    basis it used rather than implying a precision it does not have.
    """
    out: dict[str, tuple[float, str]] = {}
    try:
        sys.path.insert(0, str(ROOT))
        import bot_pnl_store as store          # noqa: E402
        for o in organs:
            keys = KEY_ALIASES.get(o) or (o.replace("_", "-"), o)
            found: list[float] = []
            for key in keys:
                try:
                    st_ = store.load_state(key)
                except Exception:              # noqa: BLE001
                    st_ = None
                if isinstance(st_, dict) and isinstance(st_.get("ttl_sec"), (int, float)):
                    found.append(float(st_["ttl_sec"]))
            # THE MINIMUM, not the first hit: an organ publishing several keys
            # is silent on ALL of them at once, so the strictest consumer
            # contract is the one that binds. Taking the first would let a
            # generous key (brain-stake-mults, 26000s) mask a strict sibling
            # (brain-vitals, 9600s) that has already gone neutral.
            if found:
                out[o] = (min(found),
                          "published ttl_sec" if len(found) == 1
                          else f"min of {len(found)} published ttl_sec")
    except Exception:                          # noqa: BLE001
        pass
    return out


def assess(blocks: list[dict], gaps: list[float],
           tol: dict[str, tuple[float, str]] | None = None) -> list[dict]:
    """Per-organ verdict. FAIL only on the structural case (see module docs)."""
    tol = tol or {}
    out = []
    for b in blocks:
        r = dict(b, starve_rate=None, verdict="report", why="")
        # [2026-08-17 (pg)] TOLERANCE IS SET BEFORE THE CADENCE CHECK, and the
        # order is the whole fix. It used to sit below the `if not gaps` early
        # return, so a run with NO deploy cadence produced rows with no
        # `tolerance_s`/`tolerance_src` at all — and `main()` indexes
        # `r["tolerance_src"]` directly to print the basis line. Result:
        # `KeyError: 'tolerance_src'`, a hard crash, in the block whose own
        # comment is about declaring which regime you are in.
        # WHY IT WAS INVISIBLE LOCALLY AND FATAL IN CI: the tolerance does not
        # depend on `gaps`; the CADENCE does. A developer's `gh` has full scope
        # and returns ~58 deploys, so this branch never fires. CI's
        # GITHUB_TOKEN is `contents/metadata/packages: read` with NO
        # `actions: read`, so the workflow-run listing yields nothing, gaps is
        # empty, and every row takes the early return. Measured: red on main
        # from `fb4d1c6` (16-Aug 07:31Z) through HEAD, blocking the Tests
        # signal for every session pushing on top of it, while the same commit
        # ran green on a laptop. The (a guard has TWO REGIMES) class, landing
        # inside the guard that documents it.
        if b["organ"] in tol:
            r["tolerance_s"], r["tolerance_src"] = tol[b["organ"]]
        elif b["interval_s"]:
            r["tolerance_s"], r["tolerance_src"] = 3 * b["interval_s"], "3x interval (proxy)"
        else:
            r["tolerance_s"], r["tolerance_src"] = None, "unknown"
        if not gaps:
            r["why"] = "no deploy cadence available — cannot assess"
            out.append(r)
            continue
        starved = sum(1 for g in gaps if g < b["stagger_s"])
        r["starve_rate"] = starved / len(gaps)
        # THE BURST is what actually starves an organ: a RUN of consecutive
        # deploys each closer together than the stagger, so the timer is reset
        # before it can elapse, over and over. Its duration — not the starve
        # RATE — is the quantity that can breach a contract.
        worst, cur = 0.0, 0.0
        for g in gaps:
            cur = cur + g if g < b["stagger_s"] else 0.0
            worst = max(worst, cur)
        r["worst_burst_s"] = worst
        # (tolerance was set above, before the cadence check — see (pg))
        # A ONE-SHOT organ has no loop and so no interval — it must simply get
        # ONE uninterrupted window as long as its own stagger, ever. If every
        # observed gap is shorter, it never ran at all, and for the one-shot
        # that matters most the miss is PERMANENT: 🧹 `cleanup_legacy_bots`
        # prunes retired rows at boot, so a skipped run leaves a dead book's row
        # standing until the next lucky boot. Peer-caught 16-Aug: with
        # `interval_s = None` the tolerance was None and this organ — the single
        # one whose missed first run cannot be made up — was structurally
        # UNFAILABLE, sailing through a modelled 200-minute burst.
        if (b["interval_s"] is None and not r["mitigated"]
                and b["stagger_s"] > 0 and max(gaps) < b["stagger_s"]
                and b["organ"] not in STAGGER_OK):
            r["verdict"] = "FAIL"
            r["why"] = (f"ONE-SHOT organ: no observed deploy gap reached its "
                        f"{b['stagger_s']}s stagger (longest {max(gaps)/60:.1f} "
                        f"min), so it never ran — and a one-shot's missed run is "
                        f"not made up on the next cycle, because there is none.")
            out.append(r)
            continue
        if b["organ"] in STAGGER_OK:
            r["why"] = f"declared exempt: {STAGGER_OK[b['organ']]}"
        elif b["kind"] == "supervisor":
            r["why"] = ("supervises a long-running process — the trailing sleep "
                        "is a restart backoff, not a publish interval, so there "
                        "is no repeated invocation to gate")
        elif b["mitigated"]:
            r["why"] = "has an early run before the stagger — reachable regardless"
        elif r["tolerance_s"] and worst > r["tolerance_s"]:
            r["verdict"] = "FAIL"
            r["why"] = (f"deploys arrived closer together than its {b['stagger_s']}s "
                        f"stagger for {worst/60:.0f} min without a break — beyond "
                        f"the {r['tolerance_s']/60:.0f} min its consumers tolerate "
                        f"({r['tolerance_src']}), so readers saw STALE data. Give it "
                        f"an early run, or declare it in STAGGER_OK with a reason.")
        else:
            # NOT `tol` — that is the parameter, and rebinding it here made the
            # dict a STRING for every later organ. Peer-caught 16-Aug: from
            # iteration two `b["organ"] in tol` became a substring test, so
            # organs silently lost their published ttl_sec and fell back to the
            # proxy, verdicts became ORDER-DEPENDENT, and when an organ's name
            # happened to occur in the string ("b" in "...published ttl_sec")
            # the next `tol[b["organ"]]` raised TypeError outright. The live run
            # survived on ordering luck alone.
            shown = (f"{r['tolerance_s']/60:.0f} min ({r['tolerance_src']})"
                     if r["tolerance_s"] else "n/a")
            r["why"] = (f"worst uninterrupted burst {worst/60:.0f} min vs tolerance "
                        f"{shown} — delayed, never stale to a consumer")
        out.append(r)
    return out


def _selftest() -> int:
    """NEGATIVE FIXTURE — the detector must still fire on a planted defect.

    `pytest tests/autonomy/test_boot_stagger.py` is the thorough suite; this is
    the CI-gating proof that the guard has not been quietly defanged, which is
    the one thing a green full scan can never show (it is green precisely when
    the fleet is healthy, and would be equally green if the rule were deleted).
    """
    # 1. an organ that CANNOT reach its first run must FAIL
    starved = {"organ": "planted", "stagger_s": 300, "interval_s": 300,
               "early": False, "gated": False, "mitigated": False,
               "inert_flags": [], "kind": "periodic"}
    r = assess([starved], [60.0] * 20)[0]
    assert r["verdict"] == "FAIL", f"detector did not fire: {r}"
    # 2. ...and a healthy one must NOT (the cry-wolf direction)
    healthy = dict(starved, stagger_s=20, early=True, mitigated=True)
    assert assess([healthy], [60.0] * 20)[0]["verdict"] == "report"
    # 3. no cadence asserts NOTHING — a guard that cannot see must not invent
    assert assess([starved], [])[0]["verdict"] == "report"
    # 4. the real file still parses (the reaper-that-reaps-nothing case)
    blocks = parse_blocks(RUN_ALL.read_text())
    assert len(blocks) >= 15, f"parsed only {len(blocks)} organs"
    by = {b["organ"]: b for b in blocks}
    assert by["fleet_immune"]["mitigated"] is True, "run-first shape regressed"
    # 5. a flag the organ does not declare is not a first run (pe)
    inert = parse_blocks(
        '( python3 /freqtrade/scripts/golive_readiness.py --publish '
        '--publish-if-nonexistent 1 || true\n  sleep 900\n  while true; do\n'
        '    python3 /freqtrade/scripts/golive_readiness.py --publish || true\n'
        '    sleep 21600\n  done ) &\n')[0]
    assert inert["stagger_s"] == 900 and inert["inert_flags"], inert
    print("audit_boot_stagger selftest OK (fires on a starved organ, stays "
          "quiet on a healthy one, asserts nothing without cadence, parses the "
          "live file, and discounts an invocation the organ would reject).")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=60,
                    help="how many recent deploys to sample (default 60)")
    ap.add_argument("--selftest", action="store_true",
                    help="negative fixture — prove the detector still detects")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()

    blocks = parse_blocks(RUN_ALL.read_text())
    times, source = deploy_times(a.limit)
    gaps = gaps_of(times)
    # THREE TIERS, most authoritative first: the LIVE payload (what consumers
    # are actually gating on right now) > the organ's own SOURCE constant (the
    # same contract, minus any env override, and available with no database) >
    # the 3x-interval proxy. The middle tier is what makes CI read real
    # contracts instead of proxying all 20 organs.
    _organs = [b["organ"] for b in blocks]
    _tol = {**static_ttls(_organs), **tolerances(_organs)}
    rows = assess(blocks, gaps, _tol)

    # DECLARE WHICH BASIS PRODUCED THESE VERDICTS. This guard has TWO REGIMES
    # and they are easy to confuse: with a DB it reads each organ's published
    # `ttl_sec` (17 of 20 today); with none — which is EVERY CI run, since no
    # workflow sets DATABASE_URL — `tolerances()` returns nothing and the
    # 3x-interval proxy governs ALL of them. Two sessions each measured a
    # different regime, stated it unconditionally, and spent four exchanges
    # disagreeing about numbers that were both right. Same "declare your
    # source" property already built into `deploy_times`, one level down.
    def _n(pred):
        return sum(1 for r in rows if r["tolerance_src"] and pred(r["tolerance_src"]))

    # ORDER MATTERS: "ttl_sec from source" also contains "ttl_sec", so the live
    # tier must be matched on "published" and the source tier on "from source".
    n_live = _n(lambda s: "published" in s)
    n_src = _n(lambda s: "from source" in s)
    n_prox = _n(lambda s: "proxy" in s)
    print(f"deploy cadence source: {source}")
    print(f"tolerance basis: published ttl_sec {n_live} organ(s), "
          f"ttl_sec from source {n_src}, 3x-interval proxy {n_prox}, "
          f"unknown {len(rows) - n_live - n_src - n_prox}"
          + ("   [no DATABASE_URL — this is the CI regime]" if not n_live else ""))
    if gaps:
        print(f"  {len(times)} deploys, {times[0]:%d-%b %H:%M} -> "
              f"{times[-1]:%d-%b %H:%M} UTC | median gap "
              f"{st.median(gaps)/60:.1f} min, min {min(gaps)/60:.1f} min")
    print()
    hdr = (f"{'organ':28s} {'stagger':>8s} {'interval':>9s} {'burst':>8s}  verdict")
    print(hdr); print("-" * len(hdr))
    for r in sorted(rows, key=lambda x: -x["stagger_s"]):
        iv = ("supervisor" if r["kind"] == "supervisor"
              else (f"{r['interval_s']}s" if r["interval_s"] else "-"))
        sr = ("-" if r.get("worst_burst_s") is None
              else f"{r['worst_burst_s']/60:.0f}m")
        tag = "FAIL" if r["verdict"] == "FAIL" else ("mitigated" if r["mitigated"]
                                                    else r["kind"])
        print(f"{r['organ']:28s} {r['stagger_s']:>7d}s {iv:>9s} {sr:>7s}  {tag}")
    bad = [r for r in rows if r["verdict"] == "FAIL"]
    print()
    for r in bad:
        print(f"FAIL {r['organ']}: {r['why']}")
    if not gaps:
        print("audit_boot_stagger: no deploy cadence available — nothing asserted.")
        return 0
    if bad:
        print(f"\naudit_boot_stagger: {len(bad)} organ(s) cannot reach a first run.")
        return 1
    print(f"audit_boot_stagger: OK — {len(rows)} organ(s), none unreachable at "
          f"the measured deploy cadence.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
