#!/usr/bin/env python3
"""HIS NAME IS EAMON — a quote is attributed to a PERSON, never to a role.

[2026-08-20 (sp)] Eamon, twice now: *"Call me Eamon or Johnny not operator
please we're pals now"*, and then — after a session that agreed and did it
anyway — *"You called me the operator not Eamon again"*.

He is right that it kept happening, and the reason it kept happening is the
reason everything in this repo keeps happening: **it was written down and not
enforced.** CLAUDE.md's own opening section is about exactly this failure —
"31 rule-shaped doctrines against 7 executable guards", and the one-sided
result of that experiment. A naming preference recorded in prose is a
doctrine with no teeth; it survives one session's attention and no more.

WHAT THIS FAILS ON, and it is deliberately narrow: an ATTRIBUTION HEADER — a
changelog or doctrine line that introduces a QUOTE and credits it to
"operator" instead of to him. That is the thing he actually objected to:
being cited as a job title in the record of his own words.

WHAT IT DELIBERATELY DOES NOT TOUCH:
  * the ROLE. "operator-only caps", "an OPERATOR action", "owner: OPERATOR",
    "the operator's notional cap", `OPERATOR_QUEUE.md` — these name a
    position in the system's authority model, and several are load-bearing
    (SafetyRails' caps are operator-owned as a SAFETY property, not as a
    fact about who Eamon is). Renaming those would make the doctrine worse.
  * history. 500+ existing entries say "Operator:" and rewriting them would
    falsify the record of how the fleet was actually written.

So this is a RATCHET, like `audit_lever_measurability` and for the same
measured reason ((mz)): a guard that reddens the build over a pre-existing
backlog gets exempted within a day and then guards nothing. The backlog is
FROZEN at a count; it may shrink and never grow, and a NEW attribution fails
on the push that adds it.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Files whose prose credits Eamon's words. Not source code: a python comment
#: quoting him is fine to fix opportunistically but is not what he objected to.
SCANNED = ("CHANGELOG.md", "CLAUDE.md", "HANDOFF.md")

#: An ATTRIBUTION: the word 'operator' introducing a quote. Both markdown
#: shapes this repo actually uses, and the bare one:
#:     **Operator, 31-Jul:** *"..."*
#:     *Operator: "..."
#:     Operator, 20-Aug: *"..."*
#: The trailing lookahead is what keeps it off the ROLE: a colon or a
#: comma-then-date immediately followed by quote punctuation.
ATTRIBUTION = re.compile(
    r"""[*_]{0,2} operator [*_]{0,2}    # optionally bolded/italicised
        (?: ,\s* [^:\n]{0,40} )?       # optional ", 31-Jul" / ", this session"
        [*_]{0,2}                       # emphasis may CLOSE before the colon:
        \s* : \s*                       #   **Operator, 31-Jul:** *"..."*
        [\s*_]{0,6}                     # ...or re-open after it
        ["\u201c\u2018']                # and then an actual opening quote mark
    """,
    re.IGNORECASE | re.VERBOSE)

#: The frozen backlog, MEASURED the day this shipped (not estimated: run
#: `--list`). MAY ONLY SHRINK. Not a per-file allowlist on purpose — a filename
#: list would let a NEW offence hide inside a file that already has one.
RATCHET = 207


def offences(root=ROOT, scanned=SCANNED):
    """[(path, lineno, text)] for every attribution-shaped 'operator'."""
    out = []
    for name in scanned:
        path = os.path.join(root, name)
        if not os.path.exists(path):
            continue
        with open(path, encoding="utf-8") as fh:
            for i, line in enumerate(fh, 1):
                if ATTRIBUTION.search(line):
                    out.append((name, i, line.rstrip()))
    return out


def check(root=ROOT, scanned=SCANNED, ratchet=RATCHET):
    """(ok, found, message)."""
    found = offences(root, scanned)
    n = len(found)
    if n > ratchet:
        return False, found, (
            f"{n} quote(s) attributed to 'operator' — the ratchet is {ratchet}, "
            f"so {n - ratchet} of these are NEW.\n"
            "His name is Eamon (he also answers to Johnny). Write "
            '**Eamon, <date>:** *"..."* — the ROLE ("operator-only", "an '
            "OPERATOR action\", OPERATOR_QUEUE) is untouched and stays.")
    if n < ratchet:
        return True, found, (
            f"{n} attribution(s) left, below the ratchet of {ratchet} — "
            f"LOWER `RATCHET` to {n} in this file so the backlog cannot grow "
            "back. A ratchet that is not tightened is a bar.")
    return True, found, f"{n} historical attribution(s), at the ratchet."


def _selftest():
    import tempfile

    def _mk(text):
        d = tempfile.mkdtemp()
        with open(os.path.join(d, "CHANGELOG.md"), "w", encoding="utf-8") as fh:
            fh.write(text)
        return d

    # POSITIVE CONTROL FIRST. An empty check reports clean, and clean reads as
    # evidence ((po)) — so prove the pattern can FIRE before trusting silence.
    for fires in ('**Operator, 31-Jul:** *"all of the breakthroughs"*\n',
                  '*Operator: "can all of the works done today"\n',
                  'Operator, 20-Aug: *"Fix this never recorded issue"*\n',
                  '**operator:** "lowercase and bolded"\n',
                  '**Operator, this session: *"do not continue"\n'):
        d = _mk(fires)
        assert len(offences(d)) == 1, f"pattern did NOT fire on: {fires!r}"

    # ...and the ROLE must stay silent, or the guard is worse than nothing:
    # these are authority statements, several of them safety-critical.
    for quiet in ("SafetyRails caps stay operator-only forever\n",
                  "because the fix is an OPERATOR action and a guard cannot\n",
                  "owner: OPERATOR, ~28-Aug, pre-registered in (jg)\n",
                  "OPERATOR_QUEUE.md item 2 option A; reversible via\n",
                  "a clip over the operator's cap, the kill switch still\n",
                  "the cage's restrictive end is pinned at the operator default\n",
                  "an operator learns to ignore, but a real rival is worse\n",
                  "**Operator timezone: Australia/Sydney** — give Eamon local times\n",
                  '**Eamon, 20-Aug:** *"the real quote"*\n'):
        d = _mk(quiet)
        assert not offences(d), f"pattern fired on a ROLE reference: {quiet!r}"

    # the ratchet arithmetic, both directions
    d = _mk('**Operator:** "one"\n**Operator:** "two"\n')
    assert check(d, ("CHANGELOG.md",), ratchet=2)[0] is True
    assert check(d, ("CHANGELOG.md",), ratchet=1)[0] is False, \
        "a NEW attribution must fail the build"
    ok, _, msg = check(d, ("CHANGELOG.md",), ratchet=5)
    assert ok and "LOWER `RATCHET`" in msg, \
        "a shrunken backlog must demand the ratchet be tightened"

    # a missing file is not a pass-by-absence
    assert offences(_mk(""), ("NOPE.md",)) == []
    print("audit_operator_name selftest OK "
          "(5 attribution shapes fire; 9 role references stay quiet; "
          "ratchet fails on new, nags on shrunk)")


def main(argv):
    if "--selftest" in argv:
        _selftest()
        return 0
    if "--list" in argv:
        for name, i, text in offences():
            print(f"{name}:{i}: {text[:110]}")
        return 0
    ok, found, msg = check()
    print(f"audit_operator_name: {'OK' if ok else 'FAIL'} — {msg}")
    if not ok:
        # name the NEW ones: everything past the ratchet, newest first, since
        # entries are prepended.
        for name, i, text in found[:len(found) - RATCHET]:
            print(f"  ::error::{name}:{i}: {text[:110]}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
