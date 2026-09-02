#!/usr/bin/env python3
"""A NUMBER QUOTED IN DOCTRINE MUST STILL MATCH THE ORGAN THAT OWNS IT.

[2026-08-27 (vm)] `audit_doctrine_enforcement` asks whether an invariant names
an executable guard, and `check_ref` fails the build when that guard is deleted
out from under it. This is the same mechanism pointed at NUMBERS instead of
RULES — `check_ref` is IMPORTED by `claims_ledger.validate`, never re-expressed,
because a second copy of a rule is a second rule.

WHY. The fleet has 29 `scripts/audit_*.py` and not one of them asks whether a
figure quoted in doctrine is still true. Measured the day this shipped:
CLAUDE.md justifies putting REAL MONEY on 🔮 georgia with *"5 of 6 bars, both
halves positive, failing only `t` (1.48 < 2.0)"*, while `golive-readiness` — the
organ that owns that number — publishes **t = 0.62, `undecidable`**. The figure
that moved a live sub-account was 2.4x stale and had stood five days. It fires
on this guard's first run, which is the point: an instrument that cannot show
its own mechanism working on day one is a document.

FOUR ARMS, three of them offline:

  1. DECLARATION (offline, always). `claims_ledger.validate` — a row that does
     not name an owner who can recompute it CANNOT BE ADDED. Refused before any
     network, so an unfalsifiable number never enters the ledger.
  2. RATCHET (offline, always). Every REAL-MONEY row in
     `fleet_books.DECLARED_LIVE` should carry a `doctrine` claim naming the
     number that justified the money. Measured today: **1 of 3** (georgia).
     A RATCHET and not a bar, for `audit_lever_measurability`'s own reason —
     a guard that reddens the build on a pre-existing backlog gets exempted
     within a day and then guards nothing — so the backlog may only SHRINK
     and a NEW live row with no justification FAILS the push that adds it.
  3. BORN-DARK (offline, always). A `run_all.sh` loop that invokes
     `scripts/<x>.py` needs a matching `COPY` in `Dockerfile.freqtrade` or the
     loop is a no-op behind `|| true` — the exact 16-Jul `event_sentinel`
     incident. `audit_image_imports` cannot see this class: its `repo_modules()`
     enumerates ROOT-level `.py` only, so anything under `scripts/` is filtered
     out of its run-path check before it is looked at. Declared, not assumed.
  4. LIVE (needs a source). Recompute every claim against its organ.

TWO REGIMES, and the second is the whole reason the third arm is worth having.
CI has no `DATABASE_URL`, so the live arm has no bot_state to read. It is then
**SKIPPED LOUDLY and the run exits 2** — never 0. A guard that reports clean
because it inspected nothing is the failure this repo has already paid for, and
`(po)` says it plainly: empty output is not a negative result. Pass
`--bus-json` to grade off the PUBLIC feed, which is how the georgia measurement
above was taken from a seat with no Railway login.

EXIT CODES, matching `audit_code_currency`'s: 0 clean · 1 a positive finding
(stale number, dead owner, ratchet growth, dark loop) · 2 could not conclude.

    python3 scripts/audit_claim_freshness.py                # offline arms + skip
    python3 scripts/audit_claim_freshness.py --bus-json     # + the live arm
    python3 scripts/audit_claim_freshness.py --selftest
"""
import argparse
import datetime as _dt
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import claims_ledger as cl                                       # noqa: E402

RUN_ALL = os.path.join(ROOT, "run_all.sh")
DOCKERFILE = os.path.join(ROOT, "Dockerfile.freqtrade")

#: THE RATCHET. Measured 2026-08-27 from this guard's own first run: three
#: real-money rows (🙏 avo, 🔮 georgia, 👩 mum), one of which — georgia — has a
#: claim row naming the number the swap was argued on. MAY ONLY SHRINK.
#: Draining it is the job: each entry is a live book whose justification is
#: prose nobody can recompute.
#: [2026-09-02 (wl)] re-measured at the georgia retirement: she left the
#: roster AND took the fleet's only justification claim with her, so the
#: backlog is STILL 2 — now avo and mum, both unjustified. The value holds;
#: the basis above is history.
#: [2026-09-02, same day] DRAINED TO ZERO — mum-golive-justification and
#: avo-live-keep-criterion cover both live rows, so the ratchet tightens to
#: its measured floor. From here ANY live row without a claim fails the push
#: that adds it, which is the guard working at full strength for the first
#: time since it shipped.
RATCHET = {"live_rows_without_a_justification_claim": 0}

#: Distinguishes "read the real thing" from "the read FAILED". `None` is the
#: fail-closed value an unreadable roster returns, so it cannot double as the
#: parameter default — a sentinel that means both is how a fail-closed branch
#: goes untested.
_UNSET = object()

#: `scripts/<name>.py` invoked from run_all.sh that is DELIBERATELY absent from
#: the image, with the reason. Empty today: both loops this guard covers must
#: ship or they are decoration.
DARK_LOOP_OK = {}


# ------------------------------------------------------------------- arm 2
def live_rows():
    """The declared real-money roster. Fail-CLOSED on an unreadable import:
    an empty roster would make this arm pass vacuously, which is the one
    outcome a ratchet must never produce."""
    try:
        import fleet_books
        return tuple(fleet_books.DECLARED_LIVE)
    except Exception:                                            # noqa: BLE001
        return None


def uncovered_live_rows(rows, claims=None):
    """-> sorted live rows with no `doctrine` claim covering them."""
    claims = cl.CLAIMS if claims is None else claims
    covered = {r for c in claims if c.get("kind") == "doctrine"
               for r in c.get("covers", ())}
    return sorted(set(rows) - covered)


# ------------------------------------------------------------------- arm 3
def script_loops(sh_text):
    """-> {script basename} that run_all.sh invokes from `scripts/`.

    A separate parse from `audit_image_imports._sh_modules` on purpose, and the
    reason is the finding above: that helper returns bare module NAMES and its
    caller intersects them with ROOT-level `.py` files, so a `scripts/` path is
    discarded before it can be judged. This asks the question that one cannot.
    """
    return set(re.findall(r"python3?\s+\S*?scripts/([A-Za-z_0-9]+)\.py",
                          sh_text or ""))


def copied_scripts(docker_text):
    return set(re.findall(r"^COPY\s+scripts/([A-Za-z_0-9]+)\.py",
                          docker_text or "", re.M))


def dark_loops(sh_text, docker_text, declared=None):
    declared = DARK_LOOP_OK if declared is None else declared
    return sorted(script_loops(sh_text) - copied_scripts(docker_text)
                  - set(declared))


# --------------------------------------------------------------------- audit
def audit(bus_json=None, claims=None, today=None, sh_text=None,
          docker_text=None, rows=_UNSET, ratchet=None, states=_UNSET):
    """-> (rc, lines). Pure enough for the selftest to drive every branch."""
    claims = cl.CLAIMS if claims is None else claims
    ratchet = RATCHET if ratchet is None else ratchet
    today = today or _dt.date.today()
    L, rc = [], 0

    # 1 — DECLARATION
    bad = cl.validate(claims)
    if bad:
        rc = 1
        L.append("DECLARATION — the ledger refuses its own table:")
        L += [f"    {b}" for b in bad]
    else:
        L.append(f"  declaration    {len(claims):>3} claim(s), every one names "
                 f"an owner that resolves")

    # 2 — RATCHET over the real-money roster
    rows = live_rows() if rows is _UNSET else rows
    if rows is None:
        rc = 1
        L.append("FAIL: the live roster is unreadable — this arm would report "
                 "every real-money row as justified. Fail-closed.")
    else:
        gap = uncovered_live_rows(rows, claims)
        cap = ratchet.get("live_rows_without_a_justification_claim")
        if len(gap) > cap:
            rc = 1
            L.append(f"FAIL: {len(gap)} real-money row(s) with no doctrine "
                     f"claim > ratchet {cap} — a book holding real money must "
                     f"name the number that justified it, in a row this guard "
                     f"can recompute. New since the ratchet: {gap}")
        elif len(gap) < cap:
            L.append(f"RATCHET CAN TIGHTEN: {len(gap)} unjustified live row(s), "
                     f"ratchet says {cap} — lower RATCHET"
                     f"['live_rows_without_a_justification_claim'] to "
                     f"{len(gap)}")
        else:
            L.append(f"  ratchet        {len(gap):>3} live row(s) still "
                     f"unjustified (at ratchet; draining is the job): {gap}")

    # 3 — BORN-DARK
    if sh_text is None:
        sh_text = _read(RUN_ALL)
    if docker_text is None:
        docker_text = _read(DOCKERFILE)
    dark = dark_loops(sh_text, docker_text)
    if dark:
        rc = 1
        for name in dark:
            L.append(f"FAIL: run_all.sh runs scripts/{name}.py and "
                     f"Dockerfile.freqtrade does not COPY it — the loop is a "
                     f"no-op behind `|| true`. Add "
                     f"`COPY scripts/{name}.py /freqtrade/scripts/{name}.py`.")
    else:
        L.append(f"  born-dark      {len(script_loops(sh_text)):>3} scripts/ "
                 f"loop(s) in run_all.sh, all present in the image")

    # 4 — LIVE
    keys = sorted({c["owner"][0] for c in claims})
    if states is _UNSET:
        if not bus_json and not os.environ.get("DATABASE_URL"):
            L.append("")
            L.append(f"LIVE ARM SKIPPED — no DATABASE_URL and no --bus-json, "
                     f"so {len(claims)} claim(s) were NOT recomputed. This run "
                     f"is INCONCLUSIVE, not clean (exit 2).")
            return (rc or 2), L
        states, source = cl.read_states(keys, bus_json)
    else:
        source = "injected"
    graded = cl.grade_all(states, claims, today)
    c = cl.counts(graded)
    L.append("")
    L.append(f"LIVE ({source}) — HOLDS {c['HOLDS']}  STALE {c['STALE']}  "
             f"PENDING {c['PENDING']}  UNRESOLVED {c['UNRESOLVED']}  "
             f"DARK {c['DARK']}")
    for g in graded:
        if g["status"] in ("STALE", "UNRESOLVED"):
            rc = 1
            L.append(f"  {g['status']}: {g['id']} — {g['why']}")
            L.append(f"      fix the SENTENCE (I12, in place), in: "
                     f"{', '.join(g['cites']) or '<uncited>'}; then move "
                     f"`number`/`as_of` in scripts/claims_ledger.py")
        elif g["status"] == "PENDING":
            L.append(f"  PENDING: {g['id']} — graded from {g['grade_after']}")
    if c["DARK"]:
        L.append(f"  {c['DARK']} claim(s) DARK — the organ did not answer, so "
                 f"they are NOT graded. Inconclusive, never clean.")
        rc = rc or 2
    return rc, L


def _read(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as fh:
            return fh.read()
    except OSError:
        return ""


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--bus-json", nargs="?", const=cl.BUS_JSON, default=None)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    rc, lines = audit(bus_json=a.bus_json)
    for ln in lines:
        print(ln)
    print("audit_claim_freshness: " + {0: "OK — every claim still matches the "
                                          "organ that owns it.",
                                       1: "FAIL",
                                       2: "INCONCLUSIVE (see above)"}[rc])
    return rc


# ---------------------------------------------------------------------- tests
def selftest():
    today = _dt.date(2026, 8, 27)
    rows_fix = cl._fixture()
    ok_claim = [dict(rows_fix[0], covers=("row-a",), kind="doctrine")]
    st = {"k": {"books": {"b": {"t": 2.05}}}}
    SH = "python3 /freqtrade/scripts/claims_ledger.py --publish || true\n"
    DK = "COPY scripts/claims_ledger.py /freqtrade/scripts/claims_ledger.py\n"
    base = dict(today=today, sh_text=SH, docker_text=DK, states=st,
                rows=("row-a",), ratchet={"live_rows_without_a_justification"
                                          "_claim": 0})

    rc, L = audit(claims=ok_claim, **base)
    assert rc == 0, (rc, L)

    # A STALE number FAILS, and names the file to fix rather than only the row.
    stale = [dict(ok_claim[0], number=9.0, tol=0.1, cites=("CLAUDE.md",))]
    rc, L = audit(claims=stale, **base)
    assert rc == 1 and any("STALE" in x for x in L), L
    assert any("CLAUDE.md" in x for x in L), L

    # A DEAD OWNER fails at DECLARATION — before any live read, so a deleted
    # organ can never be mistaken for a book that merely went quiet.
    dead = [dict(ok_claim[0], owner_ref="scripts/no_such_organ.py")]
    rc, L = audit(claims=dead, **base)
    assert rc == 1 and any("no longer resolves" in x for x in L), L

    # THE RATCHET may only shrink: equality passes, growth fails, and a smaller
    # backlog INVITES tightening rather than silently banking it.
    two = dict(base, rows=("row-a", "row-b", "row-c"))
    rc, L = audit(claims=ok_claim, **dict(two, ratchet={
        "live_rows_without_a_justification_claim": 2}))
    assert rc == 0 and any("at ratchet" in x for x in L), L
    rc, L = audit(claims=ok_claim, **dict(two, ratchet={
        "live_rows_without_a_justification_claim": 1}))
    assert rc == 1 and any("> ratchet 1" in x for x in L), L
    rc, L = audit(claims=ok_claim, **dict(two, ratchet={
        "live_rows_without_a_justification_claim": 3}))
    assert rc == 0 and any("RATCHET CAN TIGHTEN" in x for x in L), L

    # FAIL-CLOSED on an unreadable roster — reporting every live row as
    # justified is the one direction that is wrong dangerously.
    rc, L = audit(claims=ok_claim, **dict(base, rows=None))
    assert rc == 1 and any("live roster is unreadable" in x for x in L), L

    # BORN-DARK: a loop with no COPY fails and prints the exact line to add.
    rc, L = audit(claims=ok_claim, **dict(base, docker_text="COPY x.py /x.py"))
    assert rc == 1 and any("does not COPY it" in x for x in L), L
    assert any("COPY scripts/claims_ledger.py" in x for x in L), L

    # ...and the parse sees a run_all.sh path form, not just a bare name
    assert script_loops("  python3 /freqtrade/scripts/foo.py --publish") == {"foo"}
    assert script_loops("python3 scripts/foo.py") == {"foo"}
    assert script_loops("python3 /freqtrade/fleet_radar.py") == set()
    assert copied_scripts("COPY scripts/foo.py /freqtrade/scripts/foo.py") \
        == {"foo"}

    # THE CI REGIME MUST NOT PASS VACUOUSLY. No DATABASE_URL and no feed means
    # the live arm did not run, and a run that graded nothing exits 2.
    had = os.environ.pop("DATABASE_URL", None)
    try:
        rc, L = audit(claims=ok_claim, **dict(base, states=_UNSET))
        assert rc == 2, (rc, L)
        assert any("LIVE ARM SKIPPED" in x for x in L), L
        assert any("INCONCLUSIVE" in x for x in L), L
        # ...and an offline FINDING still outranks the skip: rc 1 beats rc 2.
        rc, L = audit(claims=dead, **dict(base, states=_UNSET))
        assert rc == 1, (rc, L)
    finally:
        if had is not None:
            os.environ["DATABASE_URL"] = had

    # A DARK organ is inconclusive, never clean — and never STALE either.
    rc, L = audit(claims=ok_claim, **dict(base, states={}))
    assert rc == 2 and any("DARK" in x for x in L), L

    # a PENDING prediction is reported and passes — a claim registered for a
    # future grading date must not redden the build before it is decidable
    pend = [dict(ok_claim[0], grade_after="2999-01-01")]
    rc, L = audit(claims=pend, **base)
    assert rc == 0 and any("PENDING" in x for x in L), L

    print("audit_claim_freshness selftest OK (declaration, stale, dead owner, "
          "ratchet x3, roster fail-closed, born-dark, CI skip, dark organ, "
          "pending)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
