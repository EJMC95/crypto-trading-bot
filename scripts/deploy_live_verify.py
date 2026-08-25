#!/usr/bin/env python3
"""deploy_live_verify.py — a live deploy as ONE VERIFIED ACT: print, watch, read back.

WHAT THIS REPLACES, measured: on 3-Aug the operator's live-deploy attempt was
**8 workflow dispatches with 5 cancelled inside 4 minutes** — fire, doubt,
cancel, re-fire — because nothing closed the loop between "I dispatched" and
"the container is running the new bytes". The loop-closer already exists in
pieces (the workflow run's conclusion; the `extra.build`+`extra.build_n` stamp
readback that CLAUDE.md names as the ONLY proof a deploy landed); this tool is
those pieces in one foreground command:

  1. PRINT — for a REAL-MONEY service it REFUSES to dispatch anything and
     prints the exact operator command (live dispatch is operator-only,
     doctrine + harness rule). For auto services it likewise dispatches
     NOTHING — this tool contains no dispatch path at all, pinned by AST in
     its own selftest — it only tells the operator what to run.
  2. WATCH — polls `gh run list` for the triggered run to conclusion.
     BOUNDED foreground polling by a human at a terminal, not a wakeup chain
     (P1–P3: finite attempts, hard deadlines, then it stops and says so).
  3. VERIFY — computes the EXPECTED (build, build_n) at the deployed ref
     against each IMAGE'S OWN COPY set (the (fd) rule: a repo-tree hash reads
     a converged 14-file image as "never landed"), then polls /pnl.json until
     every fresh row stamped `extra.svc == <service>` matches, and prints
     CONFIRMED or NOT-LANDED with the diff. A stale row never confirms (I1).

SECOND-COPY DOCTRINE ((hj)): the stamp rule has ONE owner. This file imports
`audit_code_currency`'s machinery (`image_shared_sets`, `stamps_at`,
`ROW_ENTRY`, `rows_from_pnl_json`, `_row_age`) and re-implements none of it —
its selftest asserts by AST that no build/hash machinery is defined here.

EXIT CODES: 0 CONFIRMED · 1 NOT-LANDED (run may be green; the container is
not on the expected stamp — [[railway-cli-frozen-services]]) · 2 cannot
resolve/verify (unknown service, dark feed, uncomputable expected stamp —
fail-closed, never a guess) · 3 the watched run failed / never appeared.

USAGE
  scripts/deploy_live_verify.py trail-blazer-live          # print + watch + verify
  scripts/deploy_live_verify.py tide-rider-lighter-live --verify-only
  scripts/deploy_live_verify.py snap-back-shadow --run-id 31234567890
"""
import argparse
import ast
import datetime as dt
import subprocess
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "scripts"))

import audit_code_currency as acc  # noqa: E402  — the ONE owner of stamp resolution

#: railway-redeploy.yml, addressed by ID — the filename form does not resolve
#: in this repo (measured, recorded in CLAUDE.md's Railway Setup section).
WORKFLOW_ID = "305025607"
PNL_URL = "https://pnl-dashboard-production-858c.up.railway.app/pnl.json"

#: The REAL-MONEY services this tool must never dispatch for, with the row the
#: readback proves and the commit-subject marker of the alternative route.
#: Cross-checked against audit_code_currency.MARKER_GATED/ROW_ENTRY in the
#: selftest so this map cannot drift from the fleet's own model of what is
#: marker-gated. (`funding-farmer-shadow` is marker-gated too but holds zero
#: real money — (hi) joined the arms' deploy clock — so it takes the ordinary
#: path here: the refusal is about real money, not about markers.)
LIVE_SERVICES = {
    # [2026-08-25] 🔮 georgia runs `trail-blazer-live` since the (ta)/(tb) slot
    # conversion — this map still described the Farmer three days later (the
    # thirteenth "who is live" registry, found by the mum go-live gap audit).
    # Her own marker; `[deploy-live-farmer]` is a no-op alias that moves only
    # the shadow arm now (see railway-redeploy.yml).
    "trail-blazer-live": ("freqtrade-georgia-lighter", "[deploy-live-georgia]"),
    # [2026-08-13 (ma)] the slot's THIRD occupant: 🙏 Avo Maria's row, same
    # service, same marker gate.
    "tide-rider-lighter-live": ("freqtrade-avo-maria-lighter", "[deploy-live-taker]"),
}

# Bounded foreground polling — a CLI a human sits in front of, never a wakeup
# chain (P1–P3). The selftest pins the total below an hour so nobody quietly
# turns this into a poller.
RUN_APPEAR_MAX_S = 600     # operator has to type the command
RUN_POLL_S = 20
RUN_DONE_MAX_S = 1500      # railway up + image build
VERIFY_MAX_S = 900         # container boot + first publish cycle
VERIFY_POLL_S = 30
FRESH_S = 900              # a row older than this proves nothing (I1)


def dispatch_command(service):
    return f'gh workflow run {WORKFLOW_ID} -f services="{service}"'


def announce(service):
    """The step-1 text. This tool has NO dispatch path (AST-pinned below) —
    for a live service that is a refusal with the exact operator command."""
    cmd = dispatch_command(service)
    if service in LIVE_SERVICES:
        row, marker = LIVE_SERVICES[service]
        return (
            f"{service} is a REAL-MONEY service — this tool NEVER dispatches a "
            f"deploy for it: live dispatch is operator-only.\n"
            f"Operator, run ONE of:\n"
            f"  {cmd}\n"
            f"  (or push a commit whose SUBJECT carries {marker} and touches "
            f"the live image's own files — never write that marker in a body)\n"
            f"This tool now WATCHES for the run, then VERIFIES the stamp "
            f"readback on row {row}."
        )
    return (
        f"{service} is an auto service (push-triggered via "
        f"railway-redeploy.yml). This tool dispatches nothing for it either — "
        f"it watches and verifies. To force a deploy the operator can run: {cmd}"
    )


# ── WATCH ───────────────────────────────────────────────────────────────────

def _parse_iso(s):
    return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00"))


def list_runs():
    r = subprocess.run(
        ["gh", "run", "list", "--workflow", WORKFLOW_ID, "--limit", "15",
         "--json", "databaseId,status,conclusion,createdAt,displayTitle"],
        cwd=str(ROOT), capture_output=True, text=True, check=False)
    if r.returncode != 0:
        return None
    try:
        import json
        return json.loads(r.stdout)
    except Exception:  # noqa: BLE001
        return None


def pick_run(runs, since_epoch):
    """Newest run created at/after since_epoch (30s clock slack). Pure."""
    best = None
    for r in runs or []:
        try:
            ts = _parse_iso(r.get("createdAt")).timestamp()
        except Exception:  # noqa: BLE001
            continue
        if ts + 30 >= since_epoch and (best is None or ts > best[0]):
            best = (ts, r)
    return best[1] if best else None


def watch(since_epoch, run_id=None, appear_max_s=RUN_APPEAR_MAX_S,
          done_max_s=RUN_DONE_MAX_S, poll_s=RUN_POLL_S, fetch=None,
          sleep=time.sleep):
    """(run, verdict): verdict is the run's conclusion, or 'no-run' /
    'watch-timeout'. Bounded in both phases — this returns, always."""
    fetch = fetch or list_runs
    deadline = time.time() + appear_max_s
    run = None
    while run is None:
        runs = fetch()
        if run_id is not None:
            run = next((r for r in runs or []
                        if str(r.get("databaseId")) == str(run_id)), None)
        else:
            run = pick_run(runs, since_epoch)
        if run is not None:
            break
        if time.time() >= deadline:
            return None, "no-run"
        sleep(poll_s)
    deadline = time.time() + done_max_s
    while True:
        if run.get("status") == "completed":
            return run, (run.get("conclusion") or "unknown")
        if time.time() >= deadline:
            return run, "watch-timeout"
        sleep(poll_s)
        runs = fetch()
        nxt = next((r for r in runs or []
                    if r.get("databaseId") == run.get("databaseId")), None)
        run = nxt or run


# ── VERIFY ──────────────────────────────────────────────────────────────────

def expected_stamps(entries, ref):
    """{entry: (id, n)} at REF, computed by that checkout's OWN bot_pnl_store
    against each image's own COPY set — audit_code_currency's machinery by
    IMPORT, never a re-hash ((hj)/(fd)). A clean throwaway worktree, never the
    local tree: `railway up` from CI ships clean main, and the local desk may
    carry WIP ([[deploy-live-from-a-clean-worktree]])."""
    hide = acc.image_shared_sets()
    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "wt"
        r = subprocess.run(["git", "worktree", "add", "-q", "--detach",
                            str(wt), ref],
                           cwd=str(ROOT), capture_output=True, text=True,
                           check=False)
        if r.returncode != 0:
            raise RuntimeError(f"git worktree add {ref}: {r.stderr.strip()}")
        try:
            return acc.stamps_at(wt, sorted(set(entries)), hide)
        finally:
            subprocess.run(["git", "worktree", "remove", "--force", str(wt)],
                           cwd=str(ROOT), capture_output=True, check=False)


def verify_rows(rows, service, expected, fresh_s=FRESH_S):
    """(verdict, lines) — the stamp-readback classifier. Pure over its inputs.

    verdict: CONFIRMED (every counted row is FRESH and matches), PENDING
    (something does not match yet, or matches only on a stale row — I1: a
    stale row describes its LAST publish, not a running container), NO-ROWS
    (nothing verifiable stamps this service). Unmapped rows are reported and
    deliberately NOT counted either way — a row this tool cannot resolve must
    not confirm a deploy, and must not block one forever either; mapping it
    in audit_code_currency.ROW_ENTRY is the fix ((jb))."""
    lines, matched, pending = [], 0, 0
    for r in rows or []:
        ex = (r.get("extra") or {})
        if ex.get("svc") != service:
            continue
        bot = r.get("bot")
        entry = acc.ROW_ENTRY.get(bot)
        if entry is None:
            lines.append(f"  {bot}: unmapped in audit_code_currency.ROW_ENTRY "
                         f"— cannot verify, not counted")
            continue
        exp = expected.get(entry)
        age, stale = acc._row_age(r)
        agetxt = "?" if age is None else f"{age / 60.0:.1f}m"
        if not exp or not exp[0]:
            pending += 1
            lines.append(f"  {bot}: no expected stamp computable for {entry} — "
                         f"FAIL-CLOSED, cannot confirm against a guess")
            continue
        got_id, got_n = ex.get("build"), ex.get("build_n")
        fresh = (stale is False) if stale is not None \
            else (age is not None and age <= fresh_s)
        if got_id == exp[0] and (got_n is None or int(got_n) == int(exp[1])):
            if fresh:
                matched += 1
                lines.append(f"  {bot}: MATCH {got_id}/{got_n} (age {agetxt})")
            else:
                pending += 1
                lines.append(f"  {bot}: stamp matches but the row is STALE "
                             f"(age {agetxt}) — a stale row describes its LAST "
                             f"publish, not a running container (I1); "
                             f"not confirmed")
        else:
            pending += 1
            if got_n is not None and exp[1] and int(got_n) != int(exp[1]):
                lines.append(f"  {bot}: build_n {got_n} != expected {exp[1]} — "
                             f"a different COUNT means a different FILE SET, "
                             f"not drifted code ((fd)); check the image's COPY "
                             f"set before reading this as stale. observed "
                             f"{got_id}/{got_n} vs expected {exp[0]}/{exp[1]}")
            else:
                lines.append(f"  {bot}: observed {got_id}/{got_n} vs expected "
                             f"{exp[0]}/{exp[1]} (age {agetxt})")
    if matched == 0 and pending == 0:
        return "NO-ROWS", lines
    return ("CONFIRMED" if pending == 0 else "PENDING"), lines


def _default_ref():
    """origin/main after a best-effort fetch (a stale local ref once called a
    shipped fix 'missing' — [[fetch-before-comparing-branches]]); HEAD when
    there is no origin."""
    try:
        subprocess.run(["git", "fetch", "-q", "origin", "main"],
                       cwd=str(ROOT), capture_output=True, timeout=60,
                       check=False)
    except Exception:  # noqa: BLE001
        pass
    r = subprocess.run(["git", "rev-parse", "--verify", "-q", "origin/main"],
                       cwd=str(ROOT), capture_output=True, text=True,
                       check=False)
    return "origin/main" if r.returncode == 0 else "HEAD"


# ── MAIN FLOW ───────────────────────────────────────────────────────────────

def run_flow(a):
    svc = a.service
    print(announce(svc))
    print()
    since = time.time()

    # Baseline readback FIRST — so "already current" is visible before anyone
    # dispatches, and so the service resolves to real rows at all.
    try:
        rows = acc.rows_from_pnl_json(a.pnl_json)
    except Exception as e:  # noqa: BLE001
        print(f"deploy_live_verify: cannot read the feed — {e}")
        return 2
    svc_rows = [r for r in rows if (r.get("extra") or {}).get("svc") == svc]
    if not svc_rows:
        seen = sorted({(r.get("extra") or {}).get("svc") for r in rows
                       if (r.get("extra") or {}).get("svc")})
        print(f"deploy_live_verify: no bot_pnl row stamps extra.svc={svc!r} — "
              f"nothing to read back. Stamped services on the feed: "
              f"{', '.join(seen)}")
        return 2
    entries = sorted({acc.ROW_ENTRY[r["bot"]] for r in svc_rows
                      if r.get("bot") in acc.ROW_ENTRY})
    if not entries:
        print("deploy_live_verify: rows found but none is mapped in "
              "audit_code_currency.ROW_ENTRY — map them there first ((jb)); "
              "verifying against a guessed entry is worse than refusing (I8).")
        return 2

    ref = a.ref or _default_ref()
    try:
        expected = expected_stamps(entries, ref)
    except Exception as e:  # noqa: BLE001
        print(f"deploy_live_verify: cannot compute expected stamps — {e}")
        return 2
    print(f"expected stamps at {ref}, per image COPY set:")
    for e_ in entries:
        got = expected.get(e_) or (None, 0)
        print(f"  {e_}: {got[0]}/{got[1]}")
        if not got[0]:
            print("deploy_live_verify: FAIL-CLOSED — an expected stamp could "
                  "not be computed; refusing to verify against a guess.")
            return 2

    verdict, lines = verify_rows(svc_rows, svc, expected, a.fresh)
    print("baseline readback (pre-deploy):")
    for ln in lines:
        print(ln)
    if verdict == "CONFIRMED":
        print("NOTE: the running container ALREADY matches the expected stamp. "
              "A redeploy that changes no hashed byte is invisible to stamp "
              "readback — this tool can confirm the service is CURRENT, not "
              "that a fresh deploy happened.")
        if a.verify_only:
            print("CONFIRMED (already current)")
            return 0
    print()

    if not a.verify_only:
        print(f"watching for the workflow run (bounded: {RUN_APPEAR_MAX_S}s "
              f"to appear, {RUN_DONE_MAX_S}s to conclude)...")
        run, concl = watch(since, run_id=a.run_id)
        if run is None:
            print("deploy_live_verify: no run appeared — did the operator "
                  "dispatch? Stopping (this tool never dispatches; re-run "
                  "with --run-id or --verify-only).")
            return 3
        print(f"run {run.get('databaseId')} "
              f"({run.get('displayTitle')!r}) concluded: {concl}")
        if concl != "success":
            print("deploy_live_verify: the run did not succeed — a stamp "
                  "readback now would grade the OLD container. Stopping.")
            return 3

    deadline = time.time() + a.verify_timeout
    while True:
        try:
            rows = acc.rows_from_pnl_json(a.pnl_json)
        except Exception as e:  # noqa: BLE001
            print(f"  feed read failed ({e}) — retrying")
            rows = []
        verdict, lines = verify_rows(rows, svc, expected, a.fresh)
        if verdict == "CONFIRMED":
            print("CONFIRMED — every fresh row for this service publishes the "
                  "expected extra.build+extra.build_n:")
            for ln in lines:
                print(ln)
            return 0
        if time.time() >= deadline:
            print(f"NOT-LANDED — timeout after {a.verify_timeout}s. Last "
                  f"readback:")
            for ln in lines:
                print(ln)
            print("A green run has never implied a container took it "
                  "([[railway-cli-frozen-services]]). Check the service's "
                  "deploy logs in Railway, then re-run with --verify-only.")
            return 1
        time.sleep(min(VERIFY_POLL_S, max(0.1, deadline - time.time())))


# ── SELFTEST ────────────────────────────────────────────────────────────────

def _selftest():
    # LIVE_SERVICES cannot drift from the fleet's own marker/row model.
    for svc, (row, marker) in LIVE_SERVICES.items():
        assert row in acc.ROW_ENTRY, f"{svc}: row {row} unmapped in ROW_ENTRY"
        assert row in acc.MARKER_GATED and marker in acc.MARKER_GATED[row], \
            f"{svc}: {marker} not the marker acc knows for {row}"

    # The refusal names the exact operator command and never claims to act.
    txt = announce("trail-blazer-live")
    assert WORKFLOW_ID in txt and 'services="trail-blazer-live"' in txt, txt
    assert "NEVER dispatches" in txt and "operator-only" in txt, txt
    txt2 = announce("snap-back-shadow")
    assert WORKFLOW_ID in txt2 and "dispatches nothing" in txt2, txt2

    # NO-DISPATCH is STRUCTURAL: no subprocess invocation in this module may
    # begin `gh workflow ...` — the dispatch form is `gh workflow run`.
    src = Path(__file__).read_text()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and node.args \
                and isinstance(node.args[0], (ast.List, ast.Tuple)):
            consts = [e.value for e in node.args[0].elts
                      if isinstance(e, ast.Constant)
                      and isinstance(e.value, str)]
            assert consts[:2] != ["gh", "workflow"], \
                "this tool must never dispatch (`gh workflow ...`) — it " \
                "prints the command for the operator"
    # SECOND-COPY pin ((hj)): the stamp rule lives in bot_pnl_store /
    # audit_code_currency; this file must not re-implement it. AST, not a
    # substring scan — a substring scan fails on its own assertion sentence
    # (the doctrine's exact "page-wide scan" trap, hit while writing this).
    imported = {getattr(n, "module", None) or a2.name
                for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom))
                for a2 in n.names}
    assert "hashlib" not in imported, "no local hashing — import the owner"
    defs = {n.name for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef)}
    banned = {"build_compute", "_build_files", "image_shared_sets",
              "stamps_at", "classify", "rows_from_pnl_json"}
    assert not (banned & defs), f"second copy of the rule: {banned & defs}"

    # pick_run: only runs created at/after `since` count; junk never crashes.
    runs = [{"databaseId": 1, "createdAt": "2026-08-04T00:00:00Z",
             "status": "completed", "conclusion": "success"},
            {"databaseId": 2, "createdAt": "2026-08-04T02:00:00Z",
             "status": "in_progress", "conclusion": None}]
    since = _parse_iso("2026-08-04T01:00:00Z").timestamp()
    assert pick_run(runs, since)["databaseId"] == 2
    assert pick_run(runs, _parse_iso("2026-08-04T03:00:00Z").timestamp()) is None
    assert pick_run([], since) is None
    assert pick_run([{"createdAt": "junk"}], since) is None

    # watch(): bounded in BOTH phases, with injected fetch/sleep (offline).
    done = dict(runs[1], status="completed", conclusion="success")
    seq = [[], [runs[1]], [done]]
    calls = {"n": 0}

    def fake_fetch():
        i = min(calls["n"], len(seq) - 1)
        calls["n"] += 1
        return seq[i]

    run, concl = watch(since, fetch=fake_fetch, sleep=lambda s: None)
    assert concl == "success" and run["databaseId"] == 2, (run, concl)
    run, concl = watch(since, fetch=lambda: [], sleep=lambda s: None,
                       appear_max_s=0)
    assert (run, concl) == (None, "no-run"), (run, concl)
    run, concl = watch(since, fetch=lambda: [runs[1]], sleep=lambda s: None,
                       done_max_s=0)
    assert concl == "watch-timeout", concl
    # --run-id pins the run even when a newer one exists
    run, concl = watch(since, run_id=1,
                       fetch=lambda: runs, sleep=lambda s: None)
    assert run["databaseId"] == 1 and concl == "success", (run, concl)

    # verify_rows — fixtures mirror the LIVE feed envelope acc's own selftest
    # measured off the endpoint (bot/extra{build,build_n,svc}/age_sec/stale):
    # the (hj) rule wants the publisher's payload, and acc.rows_from_pnl_json
    # (tested there against that envelope) is the adapter this consumes.
    expected = {"lighter_funding_bot.py": ("f27e50d805af", 15)}
    ok = {"bot": "perps-funding-lighter-lighter", "age_sec": 60,
          "stale": False, "extra": {"svc": "trail-blazer-live",
                                    "build": "f27e50d805af", "build_n": 15}}
    v, _ = verify_rows([ok], "trail-blazer-live", expected)
    assert v == "CONFIRMED", v
    # wrong id -> PENDING, and the diff names BOTH stamps
    bad = dict(ok, extra=dict(ok["extra"], build="deadbeef0000"))
    v, L = verify_rows([bad], "trail-blazer-live", expected)
    assert v == "PENDING" and any("deadbeef0000" in ln and "f27e50d805af" in ln
                                  for ln in L), (v, L)
    # wrong COUNT -> the (fd) FILE-SET wording, never a bare mismatch
    badn = dict(ok, extra=dict(ok["extra"], build="deadbeef0000", build_n=14))
    v, L = verify_rows([badn], "trail-blazer-live", expected)
    assert v == "PENDING" and any("FILE SET" in ln and "(fd)" in ln
                                  for ln in L), (v, L)
    # the SAME id with a different COUNT must not confirm — the count is
    # load-bearing on its own ((fd)); this is the fixture that reddens when
    # the n comparison is dropped (the first mutation pass survived without it
    # because every n-mismatch fixture also mismatched the id).
    oddn = dict(ok, extra=dict(ok["extra"], build_n=14))
    v, L = verify_rows([oddn], "trail-blazer-live", expected)
    assert v == "PENDING" and any("FILE SET" in ln for ln in L), (v, L)
    # a STALE match must never confirm (I1)
    stale = dict(ok, age_sec=7200, stale=True)
    v, L = verify_rows([stale], "trail-blazer-live", expected)
    assert v == "PENDING" and any("STALE" in ln for ln in L), (v, L)
    # DB-shaped row (stale=None): age governs
    v, _ = verify_rows([dict(ok, stale=None)], "trail-blazer-live", expected)
    assert v == "CONFIRMED", v
    v, _ = verify_rows([dict(ok, stale=None, age_sec=7200)],
                       "trail-blazer-live", expected)
    assert v == "PENDING", v
    # another service's rows are invisible
    v, _ = verify_rows([ok], "tide-rider-lighter-live", expected)
    assert v == "NO-ROWS", v
    # an unmapped row is reported and counted NEITHER way
    unmapped = {"bot": "mystery-row", "age_sec": 5, "stale": False,
                "extra": {"svc": "trail-blazer-live",
                          "build": "f27e50d805af", "build_n": 15}}
    v, L = verify_rows([unmapped], "trail-blazer-live", expected)
    assert v == "NO-ROWS" and any("unmapped" in ln for ln in L), (v, L)
    # missing expected stamp -> FAIL-CLOSED pending, never CONFIRMED
    v, L = verify_rows([ok], "trail-blazer-live",
                       {"lighter_funding_bot.py": (None, 0)})
    assert v == "PENDING" and any("FAIL-CLOSED" in ln for ln in L), (v, L)
    # one matching row does not carry a mismatching one
    v, _ = verify_rows([ok, bad], "trail-blazer-live", expected)
    assert v == "PENDING", v

    # Bounded polls: a foreground CLI, never a wakeup chain (P1–P3).
    total = RUN_APPEAR_MAX_S + RUN_DONE_MAX_S + VERIFY_MAX_S
    assert 0 < total <= 3600, total
    assert RUN_POLL_S >= 5 and VERIFY_POLL_S >= 10

    print("deploy_live_verify --selftest OK (live refusal + operator command, "
          "no-dispatch AST pin, second-copy pin, run picker, bounded watch, "
          "stamp-readback classifier incl. (fd) file-set + I1 staleness, "
          "fail-closed expected stamps, bounded polls)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("service", nargs="?",
                    help="Railway service name (trail-blazer-live, "
                         "tide-rider-lighter-live, or any auto service)")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--ref", default=None,
                    help="commit the deploy ships (default: origin/main "
                         "after a fetch, else HEAD)")
    ap.add_argument("--pnl-json", default=PNL_URL,
                    help="dashboard feed (file or URL) for the stamp readback")
    ap.add_argument("--verify-only", action="store_true",
                    help="skip the gh run watch; just read the stamp back")
    ap.add_argument("--run-id", default=None,
                    help="watch this exact run instead of the newest one")
    ap.add_argument("--verify-timeout", type=int, default=VERIFY_MAX_S)
    ap.add_argument("--fresh", type=int, default=FRESH_S,
                    help="max row age (s) for a stamp to count as a live "
                         "container's word (I1)")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        raise SystemExit(0)
    if not a.service:
        ap.error("service is required (or --selftest)")
    raise SystemExit(run_flow(a))
