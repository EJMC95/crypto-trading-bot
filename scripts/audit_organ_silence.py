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
        return None, None, None, "run_all.sh not readable"
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
    return silent, ok, declared, None


def main():
    silent, ok, declared, err = scan()
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
    print(f"audit_organ_silence: OK — {len(ok)} organ(s) report their own "
          f"death, {len(declared)} declared silent with a reason")
    return 0


def _selftest():
    """The detector must FIRE, not merely stay quiet on a clean tree."""
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
