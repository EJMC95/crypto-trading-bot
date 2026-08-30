#!/usr/bin/env python3
"""audit_organ_silence.py — every organ must be able to report its own death.

WHY THIS EXISTS (2026-08-01 (hw), operator: "our entire file system isn't
working if we are at square one every day over the same tedious issues ...
these fixes need to be implemented and addressed permanently so every day we
see continuously building, not fixing water leaks").

`run_all.sh` invokes every organ as `python3 <organ>.py || true`. That is
CORRECT — one sick organ must never take the supervisor down with it — and it
makes every organ crash INVISIBLE: the exit code goes to `|| true`, the
traceback goes to a container log nobody tails, and any read-only key the organ
published before dying keeps looking perfectly fresh.

WHAT IT COST, measured the day this guard was written. `bot_learn` had been
raising `KeyError('paper')` on EVERY run — the Kraken paper twin its venue A/B
section compares against was retired 14-Jul — dying before `_save_state`. So
`learning-brain.runs` sat frozen at **337** while `brain-vitals.run` read
**338**. The brain recomputed everything correctly, published its four
read-only keys on time, and then forgot the run. Because `mult_streaks` needs
THREE CONSECUTIVE runs to move a stake multiplier and that streak lives in the
state it never saved, **no new evidence could ever accumulate a streak**. A
learning loop that could not learn, for weeks, in total silence.

The same audit found **20 of 22 organs** had no way to report their own death.
Fixing `bot_learn` alone would have been one water leak of twenty.

THE RULE: an organ run by `run_all.sh` must route its entry point through
`bot_pnl_store.organ_main(KEY, main)`, which records the fault on the organ's
own bot_state key so `fleet_immune` — which already scans fresh organ payloads
and phone-pushes NEW sickness — can see it. No new plumbing.

A deliberate exception is DECLARED in SILENT_OK with a reason. Silence is not
an option; that is the whole point of the file.

    python3 scripts/audit_organ_silence.py            # scan (CI-gating)
    python3 scripts/audit_organ_silence.py --selftest # negative fixtures
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RUN_ALL = os.path.join(ROOT, "run_all.sh")

# Declared exceptions. Each needs a REASON that says why this organ cannot or
# need not report its own death — not "not done yet".
SILENT_OK = {
    "cleanup_legacy_bots.py":
        "boot-time prune, not a loop: it runs once before any organ starts and "
        "a failure is visible as the retired rows simply remaining.",
    "parliament_main.py":
        "it is itself a SUPERVISOR of six asyncio layers with its own "
        "per-layer error handling and its own bot_state key; wrapping the "
        "supervisor would record the outer process, not the sick layer.",
    "freqtrade_pnl_poller.py":
        "a pure DB->DB poller with no bot_state key of its own; its silence is "
        "already detected by the rows it stops refreshing (row_fresh).",
    "lighter_ticket_taker.py":
        "already records: it marks its own row status on crash "
        "(the _supervised() wrapper) — the real-money arm had this first.",
    "lighter_book_bezos_bot.py":
        "thin wrapper over lighter_book_douglas_bot which has its own "
        "organ_main error handling; bezos delegates entirely to douglas.",
}


def organs():
    """The organ scripts run_all.sh actually invokes, in file order."""
    try:
        with open(RUN_ALL, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return None
    found = []
    for m in re.finditer(r"python3\s+/freqtrade/([a-zA-Z0-9_]+\.py)", src):
        if m.group(1) not in found:
            found.append(m.group(1))
    return found


def rejected_flags(src=None):
    """-> [(script, flag)] for every flag run_all.sh hands a script that the
    script's own parser does not define. None when run_all.sh is unreadable.

    [2026-08-16 (pe)] THE SECOND WAY AN ORGAN RUNS INERT, and it is this
    file's own mechanism seen from the other end. The header above says the
    exit code goes to `|| true` and the traceback to a log nobody tails — an
    argparse rejection is exactly that: `error: unrecognized arguments`,
    **exit 2**, swallowed, and the boot falls through to the next line as if
    nothing happened.

    MEASURED in the live container: `run_all.sh` passed
    `--publish-if-stale 21600` to `scripts/golive_readiness.py`, which did not
    implement the flag —

        golive_readiness.py: error: unrecognized arguments: --publish-if-stale 21600

    — so the early-publish mitigation was INERT from the moment the shell half
    landed until `(pa)` implemented the script half hours later. Nothing was
    red. `run_all.sh` claimed a mitigation the container never had.

    THE TRANSFERABLE RULE: a claim read off `run_all.sh` alone is a claim
    about the SHELL, not about the organ. This closes the gap by asking the
    script whether it accepts what it is handed.

    Backslash continuations are joined FIRST. The golive invocation spans two
    lines, and a line-at-a-time regex sees `--publish` and misses
    `--publish-if-stale` entirely — which is how the first draft of this check
    reported the known-bad commit as clean.
    """
    if src is None:
        try:
            with open(RUN_ALL, encoding="utf-8") as fh:
                src = fh.read()
        except OSError:
            return None
    joined = re.sub(r"\\\n\s*", " ", src)
    out, seen = [], set()
    for script, flags in re.finditer_tuples(joined) if False else re.findall(
            r"python3\s+/freqtrade/((?:scripts/)?[\w/]+\.py)"
            r"((?:\s+--[\w-]+(?:\s+[^\s\\|;&]+)?)*)", joined):
        for flag in (x for x in flags.split() if x.startswith("--")):
            if (script, flag) in seen:
                continue
            seen.add((script, flag))
            path = os.path.join(ROOT, script)
            if not os.path.exists(path):
                continue          # named but not in this tree — no claim
            try:
                with open(path, encoding="utf-8") as fh:
                    body = fh.read()
            except OSError:
                continue
            if f'"{flag}"' not in body and f"'{flag}'" not in body:
                out.append((script, flag))
    return out


def reports_own_death(path):
    """True when this module routes its entry point through organ_main(), or
    otherwise records a fault where the fleet can read it.

    Deliberately CONSERVATIVE about what counts: printing to stderr is not
    reporting — that is precisely the silence this guard exists to end.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            src = fh.read()
    except OSError:
        return False
    if "organ_main(" in src:
        return True
    # the pre-existing equivalents: an organ that stamps its own row/key
    return bool(re.search(r"record_organ_error\(|set_status\([^)]*error", src))


def scan():
    """-> (silent, ok, declared, err). Pure, so the selftest can drive it."""
    found = organs()
    if found is None:
        return None, None, None, "run_all.sh not readable", None
    bad_flags = rejected_flags()
    silent, ok, declared = [], [], []
    for name in found:
        path = os.path.join(ROOT, name)
        if not os.path.exists(path):
            continue                       # named but not in the repo tree
        if reports_own_death(path):
            ok.append(name)
        elif name in SILENT_OK:
            declared.append(name)
        else:
            silent.append(name)
    return silent, ok, declared, None, bad_flags


def main():
    silent, ok, declared, err, bad_flags = scan()
    if err:
        print(f"audit_organ_silence: FAILED — {err}. The guard cannot vouch "
              f"for what it cannot read; failing closed.")
        return 1
    if silent:
        print("\nORGANS THAT CANNOT REPORT THEIR OWN DEATH — a crash in any of "
              "these is\nINVISIBLE (run_all.sh runs them behind `|| true`):\n")
        for name in sorted(silent):
            print(f"  {name}")
        print("\nFIX: route the entry point through the shared wrapper —\n"
              "    import bot_pnl_store as store\n"
              "    sys.exit(store.organ_main('<its-bot_state-key>', main))\n"
              "and stamp store.clear_organ_error(payload) on the happy publish "
              "so a\nrecovered organ stops reading as sick.\n"
              "A deliberate exception goes in SILENT_OK **with a reason**.\n")
        return 1
    if bad_flags:
        print("\nFLAGS run_all.sh HANDS A SCRIPT THAT REJECTS THEM — argparse "
              "exits 2 and\n`|| true` swallows it, so the organ runs INERT "
              "while the shell reads mitigated:\n")
        for script, flag in sorted(bad_flags):
            print(f"  {script}  {flag}")
        print("\nFIX: implement the flag in the script, or stop passing it. "
              "A claim read off\nrun_all.sh alone is a claim about the SHELL, "
              "not about the organ ((pe)).\n")
        return 1
    print(f"audit_organ_silence: OK — {len(ok)} organ(s) report their own "
          f"death, {len(declared)} declared silent with a reason, "
          f"every run_all.sh flag accepted by its script")
    return 0


def _flags_selftest():
    """[(pe)] The flag arm, driven by fixtures — including the REAL shape that
    ran inert in production, because a detector that cannot catch its own
    founding incident is not calibrated."""
    import tempfile

    # Hoisted: Python requires a `global` declaration before the name's first
    # use in the scope, and all three are rebound further down.
    global ROOT, rejected_flags, scan

    with tempfile.TemporaryDirectory() as td:
        good = os.path.join(td, "ok_organ.py")
        with open(good, "w") as fh:
            fh.write('ap.add_argument("--publish")\n'
                     'ap.add_argument("--publish-if-stale", type=int)\n')
        bad = os.path.join(td, "bad_organ.py")
        with open(bad, "w") as fh:
            fh.write('ap.add_argument("--publish")\n')

        _root = ROOT
        try:
            ROOT = td
            # THE FOUNDING INCIDENT'S EXACT SHAPE: a backslash continuation,
            # which is what made the first draft of this check report the
            # known-bad commit as clean.
            src = ("( python3 /freqtrade/bad_organ.py --publish \\\n"
                   "    --publish-if-stale 21600 || true\n)\n")
            assert rejected_flags(src) == [("bad_organ.py",
                                            "--publish-if-stale")], \
                rejected_flags(src)

            src_ok = ("( python3 /freqtrade/ok_organ.py --publish \\\n"
                      "    --publish-if-stale 21600 || true\n)\n")
            assert rejected_flags(src_ok) == [], rejected_flags(src_ok)

            # a flagless invocation makes no claim
            assert rejected_flags("python3 /freqtrade/bad_organ.py || true") == []
            # a script not in this tree makes no claim either
            assert rejected_flags(
                "python3 /freqtrade/absent.py --nope || true") == []
        finally:
            ROOT = _root

    # ...and the ARM IS WIRED INTO THE VERDICT. Finding it is useless if
    # main() does not fail on it — a mutation that deleted the report
    # survived a first draft that tested only the finder.
    # scan() must actually ASK the finder. Patching scan() wholesale (below)
    # tests main()'s reporting but leaves this link unpinned — a mutation that
    # hard-coded `bad_flags = []` inside scan() survived exactly that gap.
    _rf = rejected_flags
    try:
        rejected_flags = lambda src=None: [("sentinel.py", "--x")]
        assert scan()[4] == [("sentinel.py", "--x")], \
            "scan() does not propagate the flag finder's result"
    finally:
        rejected_flags = _rf

    _scan = scan
    try:
        scan = lambda: ([], ["x.py"], [], None, [("bad.py", "--nope")])
        assert main() == 1, "a rejected flag must FAIL the guard, not print"
        scan = lambda: ([], ["x.py"], [], None, [])
        assert main() == 0, "a clean tree must still pass"
    finally:
        scan = _scan


def _selftest():
    """The detector must FIRE, not merely stay quiet on a clean tree."""
    global reports_own_death           # hoisted: rebound further down
    _flags_selftest()
    import tempfile
    # reports_own_death: the three shapes that count, and the one that does not
    with tempfile.TemporaryDirectory() as d:
        def _w(name, body):
            p = os.path.join(d, name)
            with open(p, "w", encoding="utf-8") as fh:
                fh.write(body)
            return p
        assert reports_own_death(_w("a.py", "store.organ_main('k', main)\n"))
        assert reports_own_death(_w("b.py", "record_organ_error('k', e)\n"))
        assert not reports_own_death(_w("c.py", "sys.exit(main())\n"))
        # printing to stderr is NOT reporting — that is the silence itself
        assert not reports_own_death(
            _w("d.py", "print(tb, file=sys.stderr)\nsys.exit(main())\n"))
        assert not reports_own_death(os.path.join(d, "nope.py"))

    # [(pe)] scan() must USE that classifier. The checks above drive
    # reports_own_death directly, so a mutation that hard-coded scan()'s
    # branch to "everyone reports" survived them — the same finder-vs-wiring
    # gap the flag arm had. Pre-existing; closed here because this file was
    # already open.
    _rod = reports_own_death
    try:
        reports_own_death = lambda path: False
        silent, ok, declared, err, _ = scan()
        assert err is None and silent, \
            "scan() no longer routes organs through reports_own_death"
        reports_own_death = lambda path: True
        silent2, _, _, _, _ = scan()
        assert not silent2, "scan() ignores a positive classification"
    finally:
        reports_own_death = _rod

    # every declared exemption must name a real file and give a real reason
    for name, why in SILENT_OK.items():
        assert os.path.exists(os.path.join(ROOT, name)), f"{name} not in tree"
        assert len(why) > 40, f"{name}: an exemption needs a real reason"

    # and the real tree must parse to something — a regex that matched nothing
    # would make this guard vacuously green forever
    found = organs()
    assert found and len(found) > 10, f"parsed only {found} organs — regex rot?"
    print(f"audit_organ_silence selftest OK (fires on a silent organ; rejects "
          f"stderr-only; {len(found)} organs parsed; "
          f"{len(SILENT_OK)} declared)")
    return 0


if __name__ == "__main__":
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
