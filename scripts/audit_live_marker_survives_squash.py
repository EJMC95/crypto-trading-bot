#!/usr/bin/env python3
"""[2026-09-02 (xh)] A LIVE-DEPLOY MARKER IN A BRANCH COMMIT DOES NOT SURVIVE A
SQUASH MERGE — THE PR TITLE IS WHAT LANDS ON MAIN.

`(hj)` settled WHERE the marker is read from: `git log --format='%s'`, subjects
only, pinned by `audit_deploy_coverage.marker_source_ok()`. What it could not
know is which subject reaches main. Under a MERGE commit every branch subject
does. Under a SQUASH the branch subjects are folded into the body and the
squash SUBJECT is generated from the **pull request title** — so a marker
written in a commit subject is silently dropped, and the deploy gate, reading
main correctly, sees no marker and ships nothing.

MEASURED, on a REAL-MONEY book, the day this shipped. `(xe)` fixed a margin
mis-read on the two live rows and its commit subject opened with
`[deploy-live]`. It merged as #275, squashed:

    9a667f7 (xe) One position, two spellings: ... (#275)

No marker. 🙏 avo's live arm therefore never took the fix — `audit_code_currency`
read it `DEFERRED, 14 commits behind, none marked for this marker-gated
service`, which is that guard being exactly right about a deploy that was
supposed to have happened. 👩 mum only got the fix incidentally, carried by an
unrelated PR merged an hour later whose author had put `[deploy-live-mum]` in
the TITLE. The difference between the two rows was which field the marker was
typed into.

THE RULE THIS ENFORCES, and it is deliberately the weak form: if any commit on
the branch carries a live marker, the PR TITLE must carry it too. It does not
require a marker (most changes are correctly main-only under `(mm)`), it does
not guess the merge method, and it is always satisfiable by editing the title.
Writing it in both places costs nothing and makes the deploy independent of
which merge button is pressed.

    audit_live_marker_survives_squash.py --title "<pr title>" --subjects-from -
    audit_live_marker_survives_squash.py --selftest

Exit 0 = no branch marker, or every branch marker is also in the title.
Exit 1 = a marker would be dropped by a squash merge.
"""
import argparse
import re
import sys

#: The live markers the deploy gate reads. Kept in ONE place and checked
#: against the workflow below, so a new live service cannot be added there and
#: silently escape this guard.
MARKERS = ("[deploy-live]", "[deploy-live-taker]", "[deploy-live-georgia]",
           "[deploy-live-mum]", "[deploy-live-farmer]")

WORKFLOW = ".github/workflows/railway-redeploy.yml"


def markers_in(text):
    """The live markers present in `text`, as a set. Substring, exactly as the
    deploy gate's own `grep -qF` is — never a regex that could disagree."""
    return {m for m in MARKERS if m in (text or "")}


def check(title, subjects):
    """[] when nothing would be dropped, else the markers a squash would eat."""
    on_branch = set()
    for s in subjects or ():
        on_branch |= markers_in(s)
    return sorted(on_branch - markers_in(title))


def workflow_markers(path=WORKFLOW):
    """Every `[deploy-live...]` literal the deploy workflow greps for.

    Read from the workflow rather than retyped: a marker this file does not
    know about is a marker it cannot protect, and that gap would be silent.
    """
    try:
        with open(path, encoding="utf-8") as fh:
            body = fh.read()
    except OSError:
        return None                      # not in a checkout — no claim
    return set(re.findall(r"\[deploy-live[a-z-]*\]", body))


def _selftest():
    ok = True

    def expect(got, want, what):
        nonlocal ok
        if got != want:
            ok = False
            print(f"FAIL {what}: {got!r} != {want!r}")

    # the incident: marker on the branch, absent from the title
    expect(check("(xe) One position, two spellings",
                 ["[deploy-live] one position, two spellings", "fixup"]),
           ["[deploy-live]"], "the (xe) drop is caught")
    # the fix: same marker in the title
    expect(check("[deploy-live] (xe) One position, two spellings",
                 ["[deploy-live] one position, two spellings"]),
           [], "a marker in the title is not a drop")
    # main-only work must never be forced to carry a marker
    expect(check("(xh) a session-start hook", ["(xh) a session-start hook"]),
           [], "no marker anywhere is fine")
    # a marker in the BODY is not a subject and is not read by the gate ((hj)),
    # so it is not this guard's business either
    expect(check("(xh) hook", ["(xh) hook"]), [], "bodies are out of scope")
    # per-service markers are tracked independently
    expect(check("[deploy-live-mum] x", ["[deploy-live-mum] x", "[deploy-live-taker] y"]),
           ["[deploy-live-taker]"], "a second service's marker is caught")

    # the marker list must cover what the workflow actually greps for
    wf = workflow_markers()
    if wf is not None:
        missing = sorted(wf - set(MARKERS))
        if missing:
            ok = False
            print(f"FAIL MARKERS is missing {missing} — the workflow greps for "
                  f"them, so a PR carrying one would escape this guard")

    print("audit_live_marker_survives_squash --selftest:", "OK" if ok else "FAILED")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--title", help="the pull request title")
    ap.add_argument("--subjects-from", help="file of commit subjects, or - for stdin")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    if a.title is None or a.subjects_from is None:
        ap.error("--title and --subjects-from are both required")
    if a.subjects_from == "-":
        subjects = sys.stdin.read().splitlines()
    else:
        with open(a.subjects_from, encoding="utf-8") as fh:
            subjects = fh.read().splitlines()
    dropped = check(a.title, subjects)
    if not dropped:
        print("audit_live_marker_survives_squash: OK — no live marker would be "
              "dropped by a squash merge")
        return 0
    print("audit_live_marker_survives_squash: a SQUASH MERGE WOULD DROP "
          f"{', '.join(dropped)}\n")
    print("  A squash subject is generated from the PULL REQUEST TITLE, not\n"
          "  from your commit subjects, so this marker would never reach main\n"
          "  and the live service would NOT be deployed — silently.\n")
    print(f"  Fix: put {' '.join(dropped)} at the front of the PR TITLE as well.\n"
          "  Keep it in the commit subject too; both is correct, and then the\n"
          "  deploy does not depend on which merge button is pressed.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
