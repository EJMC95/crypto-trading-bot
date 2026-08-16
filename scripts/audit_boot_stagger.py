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
KEY_ALIASES = {"implementation_shortfall": "impl-shortfall",
               "lighter_market_scout": "lighter-market",
               "lighter_scout_tuner": "scout-tuner",
               "bot_learn": "learning-brain",
               "lighter_ticket_taker": "lighter-ticket-taker-lshadow",
               "experiment_judge": "xp-judge",
               "golive_readiness": "golive-readiness"}

#: Organs deliberately exempt, with the reason. An exemption is a DECISION and
#: must name why — the `BORN_DARK_OK` idiom.
STAGGER_OK: dict[str, str] = {}


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
        head = body[:org.start()]
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
        gated = "--publish-if-stale" in body
        # The loop interval: the last `sleep` inside the loop body.
        loop = body.split("while true", 1)[1] if "while true" in body else ""
        iv_m = re.findall(r"sleep\s+\"?\$?\{?[A-Z_]*:?-?(\d+)\}?\"?", loop)
        interval = int(iv_m[-1]) if iv_m else None
        kind = ("supervisor" if interval is not None
                and interval <= SUPERVISOR_MAX_BACKOFF_S else "periodic")
        out.append({"organ": name, "stagger_s": stagger, "interval_s": interval,
                    "early": early, "gated": gated, "mitigated": early or gated,
                    "kind": kind})
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
    try:
        raw = subprocess.run(
            ["git", "log", "-n", str(limit), "--format=%cI", "origin/main"],
            capture_output=True, text=True, timeout=60, cwd=ROOT).stdout
        ts = sorted(dt.datetime.fromisoformat(l.strip())
                    for l in raw.splitlines() if l.strip())
        if len(ts) >= 3:
            return ts, "git:origin/main commit times (PROXY — commits batch into pushes)"
    except Exception:      # noqa: BLE001
        pass
    return [], "unavailable"


def gaps_of(times: list[dt.datetime]) -> list[float]:
    return [(b - a).total_seconds() for a, b in zip(times, times[1:])]


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
            for key in (KEY_ALIASES.get(o), o.replace("_", "-"), o):
                if key is None:
                    continue
                try:
                    st_ = store.load_state(key)
                except Exception:              # noqa: BLE001
                    st_ = None
                if isinstance(st_, dict) and isinstance(st_.get("ttl_sec"), (int, float)):
                    out[o] = (float(st_["ttl_sec"]), "published ttl_sec")
                    break
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
        if b["organ"] in tol:
            r["tolerance_s"], r["tolerance_src"] = tol[b["organ"]]
        elif b["interval_s"]:
            r["tolerance_s"], r["tolerance_src"] = 3 * b["interval_s"], "3x interval (proxy)"
        else:
            r["tolerance_s"], r["tolerance_src"] = None, "unknown"
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--limit", type=int, default=60,
                    help="how many recent deploys to sample (default 60)")
    a = ap.parse_args()

    blocks = parse_blocks(RUN_ALL.read_text())
    times, source = deploy_times(a.limit)
    gaps = gaps_of(times)
    rows = assess(blocks, gaps, tolerances([b['organ'] for b in blocks]))

    print(f"deploy cadence source: {source}")
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
