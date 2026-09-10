#!/usr/bin/env python3
"""CHANGELOG entry-letter UNIQUENESS — the sync channel's own integrity guard.

WHY THIS EXISTS (2026-07-29 (fd)). CHANGELOG.md is how parallel Claude sessions
stay in sync, and entries cross-reference each other BY LETTER ("the (co) paths
fix", "see (az)"). A duplicated letter silently makes every such reference
ambiguous — including from TRACKED CODE (`.github/workflows/railway-redeploy.yml`
cites "(ff)"; `tests/test_selftests.py` cites "(ex)").

It has happened at least SEVEN times: 21-Jul (av)->(aw)->(ax), (bn) twice,
21-Jul (br) twice, 22-Jul (ca)/(cb), the 23-Jul (co)-(cr) QUADRUPLE — whose own
merge note promised a de-duplication follow-up that then sat unrepaired for six
days — and on 2026-07-29 alone, twice in one afternoon: one session's (ev)
collided, moved to (ex), collided AGAIN, and finally landed on (fi) only after
the other session had taken (fb) AND (fc) mid-edit — NINE recorded collisions.

Every one of those was found by a human reading the file. The rule itself was
written NOWHERE a session reads before writing — so the control that kept
failing was "remember to check", the same shape the born-dark guard exists to
replace. This is the detector; CLAUDE.md carries the rule.

THE ERA BOUNDARY IS MEASURED, NOT ASSUMED. The letter sequence is CONTINUOUS
(not per-day) and it RESTARTED at (a) on 2026-07-17: that day legitimately
carries both the tail of the old run (aa..au) and the head of the new one, so
17-Jul contains real, deliberate duplicates. From 2026-07-18 forward the only
duplicates were ever the (co)-(cr) block. Scoping to >= 2026-07-18 therefore
fails ONLY on genuine collisions and never on history. Headers with no letter
at all (all 2026-07-15 and older, pre-convention) are ignored everywhere.

    python3 scripts/audit_changelog_letters.py            # scan (CI-gating)
    python3 scripts/audit_changelog_letters.py --selftest # negative fixture
"""
import collections
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Directories the citation scan must never descend into.
#: [2026-08-27 (um)] `.claude/worktrees` is where `new_session_worktree.sh` puts
#: every concurrent session's private branch, and that script ASSERTS the path
#: is git-ignored. So this walk was reading files git itself excludes from the
#: current branch — code on OTHER branches, mid-write, citing letters those
#: branches have and this one does not.
#: THE COST: any session could be turned RED by another session's uncommitted
#: work, on a failure it had no way to fix because the file was not its own.
#: Measured the day this shipped: 4 sibling worktrees, 3 dangling hits from
#: a branch whose own CHANGELOG carries the entry they cite. That is exactly the
#: cry-wolf trap this repo has already paid for ((gl): "a guard whose only
#: output is a warning on a passing run is not a guard"; (mz): a guard that
#: reddens on a pre-existing backlog gets exempted within a day and then guards
#: nothing). Scoped to the worktree root ONLY, not all of `.claude` — hooks and
#: settings there are this branch's own files and must still be scanned.
SKIP_DIRS = {".git", ".venv", "node_modules", "__pycache__"}
SKIP_RELPATHS = {os.path.join(".claude", "worktrees")}


def walk_py(root):
    """Every .py in `root` that belongs to THIS branch's tree."""
    for _root, _dirs, _files in os.walk(root):
        _dirs[:] = [d for d in _dirs if d not in SKIP_DIRS]
        rel = os.path.relpath(_root, root)
        if any(rel == s or rel.startswith(s + os.sep) for s in SKIP_RELPATHS):
            _dirs[:] = []
            continue
        for f in _files:
            if f.endswith(".py"):
                yield os.path.join(_root, f)


CHANGELOG = os.path.join(ROOT, "CHANGELOG.md")

# Measured 2026-07-29: >=07-18 isolates the current sequence from the 17-Jul
# restart day. Moving this EARLIER will fail the build on deliberate history.
ERA_START = "2026-07-18"

HEADER = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \(([a-z]+)\)(.*)$", re.M)

# Deliberate, DECLARED duplicates. A letter belongs here only with a reason that
# says why it must stay ambiguous — which is almost never the right answer,
# because the whole point of a letter is to be citable. Prefer renumbering.
LETTERS_OK = {}


def scan(text):
    """-> (entries, duplicates). Pure, so the selftest can drive it."""
    entries = [(d, l, t.strip()) for d, l, t in HEADER.findall(text)
               if d >= ERA_START]
    by_letter = collections.defaultdict(list)
    for d, l, t in entries:
        by_letter[l].append((d, t))
    dups = {l: v for l, v in by_letter.items()
            if len(v) > 1 and l not in LETTERS_OK}
    return entries, dups


# A header that is not at line start. `HEADER` is anchored with re.M, and so
# is every human `grep '^## '` — so an entry glued to the end of the previous
# entry's prose is invisible to the index, to this guard, and to Markdown
# itself, while its letter still gets cited.
GLUED = re.compile(r"(?<!\A)(?<!\n)## (\d{4}-\d{2}-\d{2}) \(([a-z]+)\)")

# THE TWO FORMS THAT ARE UNAMBIGUOUSLY CITATIONS: the dated bracket the fleet
# stamps in code comments, and a backticked letter in prose. MEASURED before
# choosing: matching any parenthesised short word instead finds 278 "dangling"
# hits across the tree — ordinary English and identifiers, every one noise, and
# a guard that cries wolf trains the operator to ignore it. These two forms
# find 496 real citations with ZERO noise. LIMIT, declared rather than silent:
# a bare prose citation is not checked; it is also not how code cites.
#
# [2026-08-19 (qn)] THE SHORT DATE FORM WAS A BLIND SPOT, AND IT WAS FOUND THE
# ONLY WAY A BLIND SPOT EVER IS — by walking into it. A session cited `(qn)`
# in three files with NO `(qn)` entry in the changelog, and this guard reported
# **"OK — 994 citations all resolve"**. Cause: `\d{4}-\d{2}-\d{2}` demands a
# full ISO date, and the tree also stamps `[19-Aug (qn)]`. MEASURED at the fix:
# **22 short-form citations across the tree were unverified** (vs 624 ISO), 7
# of them predating that session — so this was live, not self-inflicted.
# The widening stays inside the noise argument above: it requires the SAME
# unambiguous `[<date> (xx)]` bracket, only with a `D-Mon`/`DD-Mon` date. It
# does NOT reach for bare parens (the 278-hit noise case that argument
# rejected). Re-measured after: still ZERO false hits.
_DATE = r"(?:\d{4}-\d{2}-\d{2}|\d{1,2}-(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec))"
CITE_DATED = re.compile(r"\[" + _DATE + r" \(([a-z]{1,3})\)\]")
CITE_TICKED = re.compile(r"`\(([a-z]{1,3})\)`")


def glued_headers(text):
    """-> [(date, letter)] for headers not at line start. See entry lc.

    MEASURED: entry kp's header was appended directly to the previous entry's
    last sentence. One missing newline, the only occurrence in 369 headers —
    and it took the entry out of the index entirely while 10 citations, 6 of
    them in tracked code, kept pointing at it."""
    return GLUED.findall(text or "")


def succ(letter):
    """The next letter in the sequence: a..z, then aa, ab, ... zz, aaa, ...

    [2026-08-16 (pd)] BIJECTIVE BASE-26, not a hand-rolled alphabet walk, and
    the difference is the bug this retires. Sessions each wrote their own
    enumerator inline; on 16-Aug one of mine enumerated `o` + `a..z` only, so
    when the sequence exhausted `oz` it raised StopIteration mid-script, the
    calling shell interpolated the empty result into a commit subject, and a
    letterless commit went to main with no entry. A generator with no rollover
    is a countdown.

    The rule is DERIVED FROM THIS FILE'S HISTORY, not invented: it rolls
    z -> aa, az -> ba, bz -> ca, ... nz -> oa, oz -> pa. That is bijective
    base-26 (a=1 ... z=26, no zero digit), so zz -> aaa falls out instead of
    being a second special case waiting to fail the same way one level up.
    """
    n = 0
    for ch in str(letter):
        if not ("a" <= ch <= "z"):
            raise ValueError(f"not a changelog letter: {letter!r}")
        n = n * 26 + (ord(ch) - 96)
    if n < 1:
        raise ValueError(f"not a changelog letter: {letter!r}")
    n += 1
    out = ""
    while n:
        n, r = divmod(n - 1, 26)
        out = chr(97 + r) + out
    return out


def rank(letter):
    """Position in the sequence, as an integer (a=1, z=26, aa=27, ...)."""
    n = 0
    for ch in str(letter):
        if not ("a" <= ch <= "z"):
            raise ValueError(f"not a changelog letter: {letter!r}")
        n = n * 26 + (ord(ch) - 96)
    if n < 1:
        raise ValueError(f"not a changelog letter: {letter!r}")
    return n


def latest(letters):
    """The furthest-along letter in `letters`, by SEQUENCE not by string.

    String order is wrong here and quietly so: `"z" > "aa"` lexicographically
    while `aa` comes after `z` in this sequence.
    """
    best = None
    for l in letters:
        try:
            r = rank(l)
        except ValueError:
            continue
        if best is None or r > best[0]:
            best = (r, l)
    return None if best is None else best[1]


def next_free(taken, start="a"):
    """The first letter at or after `start` that nothing has claimed.

    `taken` must include letters claimed by CITATIONS, not only by headers: a
    session writes a citation into code before its entry lands, and taking that
    letter is how a citation ends up resolving to somebody else's entry — green
    to this audit, wrong to a reader. Measured twice on 16-Aug.
    """
    taken = {str(x) for x in taken}
    cur = str(start)
    while cur in taken:
        cur = succ(cur)
    return cur


def claimed_letters(text, paths=(), window=50):
    """Letters that are spoken for: every HEADER, plus near-ahead RESERVATIONS.

    [2026-08-16 (pd)] THE TWO KINDS ARE NOT THE SAME KIND, and conflating them
    is how the first cut of this function answered `woo`.

    * HEADERS are authoritative and unambiguous.
    * A CITATION is only interesting when it is a RESERVATION: a session writes
      its letter into code before its entry lands, and taking that letter is
      how a citation ends up resolving to somebody else's entry — green to this
      audit, wrong to a reader (measured twice on 16-Aug). But a citation is
      also just a bracketed pair in text, and this tree is full of prose and
      code that matches — bracketed "the", "usd", "vol", "row". Counting those
      put the tip near `won` and produced a next-letter three thousand entries
      into the future.

    So a citation counts only inside a WINDOW just past the newest header. A
    reservation is always a step or two ahead of the tip; an English word in
    brackets is not. `window` bounds how far ahead a session may reserve.
    """
    hdrs = {l for _d, l, _t in scan(text)[0]}
    # A CITATION is never a CALL. `(?<![\w)])` drops `_tail(px)`, `pct(bh)`,
    # `len(sh)` — call syntax whose argument happens to be two letters — while
    # keeping `see (pd)` and `[2026-08-16 (pd)]`. Without it the window filled
    # with variable names (`px`, `py`, `pp`) and the next letter skipped them.
    pat = re.compile(r"(?<![\w)])\(([a-z]{1,3})\)")
    tip = latest(hdrs)
    if tip is None:
        return set(hdrs)
    lo, hi = rank(tip), rank(tip) + int(window)
    out = set(hdrs)
    for src in [text] + [_read(x) for x in paths]:
        for cand in pat.findall(src or ""):
            try:
                r = rank(cand)
            except ValueError:
                continue
            if lo < r <= hi:
                out.add(cand)
    return out


def _read(path):
    try:
        return open(path, encoding="utf-8").read()
    except OSError:
        return ""


def next_letter(text, paths=(), extra_claimed=()):
    """The letter a new entry should take: the first free one AFTER the tip.

    [2026-09-10 (zw)] `extra_claimed` exists so the OPEN-BRANCH letters can be
    folded in WITHOUT the CLI re-implementing this function. The `--next` block
    had grown its own `claimed_letters -> latest -> next_free` chain to do
    exactly that, which left this function dead at its only real call site and
    put two copies of the picking rule one file apart — "A SECOND COPY OF A
    RULE IS A SECOND RULE", and the copy that drifts is the one nobody runs.
    A letter an abandoned branch burns costs nothing: the sequence is bijective
    base-26 and unbounded."""
    claimed = claimed_letters(text, paths) | set(extra_claimed)
    tip = latest({l for _d, l, _t in scan(text)[0]})
    return next_free(claimed, start=succ(tip) if tip else "a")


def code_citations(paths):
    """-> [(path, lineno, letter)] for EVERY changelog citation in tracked
    python comments/strings, resolving or not.

    [2026-08-19 (rz)] Split out of `dangling_code_citations` so the extraction
    rule has ONE owner and two consumers: that function (does the letter
    resolve to anything?) and `scripts/audit_citation_drift.py` (does it still
    resolve to the SAME ENTRY it was written against?). A second copy of this
    tokenizer would be a second rule, and the two would drift — the class this
    repo names in "A SECOND COPY OF A RULE IS A SECOND RULE".

    Tokenized rather than regexed over raw source: only comments and string
    literals can carry a citation, and source is full of same-shaped
    identifiers."""
    import io
    import tokenize
    out = []
    for p in paths:
        try:
            src = open(p, encoding="utf-8").read()
            toks = list(tokenize.generate_tokens(io.StringIO(src).readline))
        except Exception:      # noqa: BLE001 — unreadable/unparseable: skip
            continue
        for tok in toks:
            if tok.type not in (tokenize.COMMENT, tokenize.STRING):
                continue
            for letter in (CITE_DATED.findall(tok.string)
                           + CITE_TICKED.findall(tok.string)):
                out.append((p, tok.start[0], letter))
    return out


def dangling_code_citations(paths, known):
    """-> [(path, lineno, letter)] for changelog citations in tracked python
    COMMENTS/STRINGS that resolve to no header. See 2026-08-06 entry lc.

    Tokenized rather than regexed over raw source: only comments and string
    literals can carry a citation, and source is full of same-shaped
    identifiers. A citation that resolves to nothing is a reader sent nowhere.

    NOTE ON THIS DOCSTRING: it deliberately writes letters in prose form and
    never in either citation form, so text ABOUT the class cannot be flagged
    AS the class — the self-reference trap this fleet has paid for before.
    That is why this file needs no exemption from its own guard."""
    return [(p, n, l) for p, n, l in code_citations(paths) if l not in known]


#: [2026-08-16 (nq)] An entry that declares itself CORRECTED IN PLACE. The
#: phrase must appear inside that entry's OWN body — see `corrected_letters`.
CORRECTED = re.compile(r"CORRECTED IN PLACE", re.I)

#: [2026-08-16 (ns)] How alike two titles must be before a declared correction
#: is believed. MEASURED, not picked: the real in-place correction this escape
#: was built for scores **0.978**, while the two known false cases score
#: **0.259** (two different correction entries colliding on a letter) and
#: **0.267** (the original `(fz)` two-session race). 0.6 sits with ~4x margin
#: on both sides of that gap.
SAME_ENTRY_RATIO = 0.6


def same_entry(a, b):
    """True when two titles are the SAME entry, one of them edited.

    [2026-08-16 (ns)] THE HOLE THIS CLOSES, found within the hour by the very
    collision it would have hidden. `(nq)` let a declared `CORRECTED IN PLACE`
    suppress a cross-branch letter clash — but it asked only *"does this
    letter's entry declare a correction?"*, so it also suppressed a letter
    shared by two ENTIRELY DIFFERENT entries that both happened to be
    corrections. That is not hypothetical: a concurrent session was mid-write
    on its own `(nq)` (a corrected 🧘 Douglas row) while this session's `(nq)`
    was already on origin/main — a genuine race the escape would have
    swallowed, in the guard whose entire job is to catch it.

    A real in-place correction edits a few words of one title; a race puts two
    unrelated subjects on one letter. `difflib` separates those cleanly (see
    `SAME_ENTRY_RATIO` for the measured numbers), and requiring BOTH signals —
    an explicit declaration AND textual continuity — means neither alone can
    wave the guard off.
    """
    import difflib
    return difflib.SequenceMatcher(
        None, str(a or ""), str(b or "")).ratio() >= SAME_ENTRY_RATIO


#: [2026-08-26] An entry that declares its own RENUMBER, naming BOTH letters.
#: The convention's rule 4 already requires the move to be recorded inline in
#: the moved entry — this is that record, made machine-readable so a guard can
#: tell a declared move from a silent sweep. Accepts `->`, an arrow, or the
#: word "to", because three past entries used three of those spellings.
RENUMBERED = re.compile(
    r"RENUMBER(?:ED)?\s*\(?([a-z]{1,3})\)?\s*(?:->|→|to)\s*\(?([a-z]{1,3})\)?",
    re.I)


def renumbered_pairs(text):
    """-> {(from_letter, to_letter)} declared in `text`.

    [2026-08-26] WHY THIS IS NOT AN EXACT-TITLE MATCH, which is the obvious
    implementation and is UNSAFE. A renumber moves a header from one letter to
    another with the TITLE UNCHANGED — and so does the `(nx)` incident, where a
    `perl -pi -e 's/(nv)/(nx)/g'` rewrote ANOTHER session's `(nv)` entry to
    `(nx)` and destroyed 90 lines. Both look identical to a title comparison.

    The one thing that separates them is that a legitimate renumber is
    DECLARED, in the moved entry, by a human decision about which entry is
    cited; the sweep is silent by construction. So the declaration is the
    discriminator, exactly as `CORRECTED` is for an in-place correction — and
    like that one it is required TOGETHER with a structural match, never alone.
    """
    return {(m.group(1).lower(), m.group(2).lower())
            for m in RENUMBERED.finditer(str(text or ""))}


def corrected_letters(text):
    """-> {letter} whose OWN entry body declares an in-place correction.

    [2026-08-16 (nq)] WHY THIS EXISTS — the guard forbade what I12 REQUIRES.
    `cross_branch` treats *same letter + different title* as a collision. That
    is right for two sessions racing for a letter, and wrong for the one other
    thing that produces the same signature: an entry whose title was CORRECTED
    IN PLACE. I12 is explicit — *"a doctrine that no longer describes the
    system is a defect, not history — correct it in place and say so"* — and
    `(nn)` needed exactly that (its title claimed four days of red CI; the
    workflow's own run history says 24 hours). With no notion of a correction,
    the guard made every title permanently immutable, so the repo's own
    correction rule and its own guard contradicted each other and the guard won.

    THE ESCAPE IS DELIBERATELY NARROW, because a collision guard that can be
    waved off is worse than none:
      * the declaration must sit in the body of **that letter's own entry** — a
        `CORRECTED IN PLACE` anywhere else in the file excuses nothing, so one
        correction cannot silence the guard for a genuine collision elsewhere;
      * it only ever suppresses a letter BOTH sides already share, which is the
        one case where the title is the sole distinguishing signal;
      * it is a positive declaration a human wrote, not an inference.
    A real collision — two different entries, neither declaring a correction —
    fires exactly as before, which the selftest pins with the original `(fz)`
    incident.
    """
    out, marks = set(), list(HEADER.finditer(text or ""))
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        if CORRECTED.search(text[m.end():end]):
            out.add(m.group(2))
    return out


def lost_entries(mine, theirs, my_text=None):
    """-> [(date, letter, title)] for era entries origin/main carries that this
    tree has LOST. Pure, so the selftest can drive it.

    [2026-09-01 (vw)] WHY THIS EXISTS. PR #237 squash-merged a branch whose
    CHANGELOG.md was a 2-line stub, replacing 655 entries; PR #212 then
    overwrote the stub with a stale 566-entry copy. Eleven days of the fleet's
    record left main and EVERY guard stayed quiet, because every arm here asks
    about entries that exist — collisions, citations, glued headers — and none
    asks whether entries VANISHED. The (po) class: a check that inspects
    nothing reports clean.

    KEYED ON LETTERS, deliberately: a title corrected in place (I12) keeps its
    letter and must not trip this. A renumber DECLARES itself
    (`renumbered_pairs`, the machine-readable rule-4 record) — but the
    declaration alone excuses NOTHING, because this file's own prose carries
    ~48 historical renumber records and loose English that the pattern also
    matches (measured: a bare `moved_from` set held ('sf','sk') and even
    ('ed','get'), so the arm's first cut was vacuous for any letter ever
    named near the word "renumber" — caught by the I3 mutation, not by the
    green selftest). So the excuse is TWO-signal, the `cross_branch` shape: a
    declared `(X) -> (Y)` counts only when my tree's (Y) entry carries the
    SAME TITLE as the (X) entry origin/main lost. DECLARED LIMIT: pre-era and
    letterless headers are outside the key space, so a wipe of ONLY
    pre-18-Jul history would pass this arm; every real wipe removes era
    entries too, and 646 of them stand guard.
    """
    mine_letters = {l for _d, l, _t in mine}
    mine_by_letter = {l: t for _d, l, t in mine}
    moved = renumbered_pairs(my_text)
    out = []
    for d, l, t in theirs:
        if l in mine_letters:
            continue
        if any(frm == l and same_entry(mine_by_letter.get(to), t)
               for frm, to in moved):
            continue                     # a declared move, carried in my tree
        out.append((d, l, t))
    return out


def cross_branch(mine, theirs, my_text=None):
    """-> {letter: (my_title, their_title)} for letters BOTH sides used with
    DIFFERENT titles. Pure, so the selftest can drive it.

    `my_text` (optional) is my full CHANGELOG. When given, two narrow escapes
    apply — each needs TWO signals, so neither can be waved off with prose:
    * a letter whose own entry declares `CORRECTED IN PLACE` AND whose titles
      are the same entry edited — see `corrected_letters`;
    * [2026-09-01 (vw)] a DECLARED RENUMBER: my text records `(X) -> (Y)` AND
      my tree carries origin/main's displaced (X) entry at (Y) with the same
      title. This is exactly the repair this guard's own FIX text prescribes
      ("the other moves to the next free one and records the move inline") —
      and before this escape existed, the branch PERFORMING that repair was
      refused by the guard that prescribed it. The (nx) silent-sweep shape
      still fires: a sweep rewrites letters without a declaration, and a
      declaration without the matching moved entry excuses nothing.
    Omitting `my_text` keeps the original strict behaviour, so every existing
    caller and test is unchanged.

    WHY (2026-07-30 (hj)). The in-file check above cannot see the collision
    that actually keeps happening: two sessions on two BRANCHES each pick "the
    next free letter" from their own snapshot, and each file is internally
    unique right up until the merge. That is the documented failure mode —
    CLAUDE.md's rule 2 says pick the letter at PUSH time — and on 2026-07-30 it
    bit again: main's entry and a branch's entry both landed as (fz), and the
    loser had already been renumbered once before ((fx) -> (fz) -> (gi)).

    SAME letter + SAME title is a merge/rebase of the same entry, not a
    collision — comparing titles rather than letters alone is what keeps this
    quiet on every ordinary branch.
    """
    theirs_by_letter = {l: t for _d, l, t in theirs}
    fixed = corrected_letters(my_text) if my_text else set()
    moved = renumbered_pairs(my_text) if my_text else set()
    mine_by_letter = {l: t for _d, l, t in mine}
    out = {}
    for _d, letter, title in mine:
        other = theirs_by_letter.get(letter)
        if other is None or other == title:
            continue
        if letter in fixed and same_entry(title, other):
            continue                           # a corrected title, not a race
        # [(vw)] a DECLARED renumber whose moved entry my tree actually holds:
        # their displaced (letter) entry lives here at (to) under the same
        # title. Both signals or it still fires — see the docstring.
        if any(frm == letter and same_entry(mine_by_letter.get(to), other)
               for frm, to in moved):
            continue
        out[letter] = (title, other)
    return out


def _git(*a, timeout=20):
    """Every git call this guard makes, through ONE owner. Fail-safe: None.

    [2026-09-10] Hoisted out of `_baseline_changelog`, where it was nested, so
    the open-branch arm below cannot grow a second copy of the same rule with
    its own timeout and its own idea of what a failure looks like — the
    "A SECOND COPY OF A RULE IS A SECOND RULE" class this repo already paid
    for in the go-live gate. A non-zero exit, a missing git, a timeout and a
    ref that does not resolve all collapse to None, which every caller reads
    as "no arm", never as "clean".
    """
    import subprocess
    try:
        r = subprocess.run(("git",) + a, cwd=ROOT, capture_output=True,
                           text=True, timeout=timeout)
    except Exception:                          # noqa: BLE001 — no git, no arm
        return None
    return r.stdout if r.returncode == 0 else None


#: [2026-09-10] Wall-clock ceiling on the open-branch arm's git reads, and a
#: cap on how many refs it will even try. MEASURED on this repo the day the
#: arm shipped: 98 remote-tracking refs, 96 once main/HEAD/self are excluded,
#: 82 carrying a readable CHANGELOG.md. CORRECTED IN PLACE (I12) the day it
#: shipped: the design note said 2.7s, and the END-TO-END run measures
#: **5.3s** wall (`time audit_changelog_letters.py`, warm) — the 2.7s figure
#: counted the sweep's three stages and not the citation walk they run beside.
#: ~25% of this budget, not 10%. The number is quoted here because it is the
#: argument for the budget existing, so an optimistic one is worse than none. The budget exists for
#: the repo this becomes, not the one it is: a clone that has fetched 500 dead
#: branches must degrade to a PARTIAL answer that SAYS SO, never to a hung
#: push. Over budget is reported, never silently truncated — a cap that
#: reaches your reasoning without declaring itself is the (qz) trap.
OPEN_BRANCH_BUDGET_S = 20.0
OPEN_BRANCH_REF_CAP = 400


def _open_refs(for_each_ref_out, head="", upstream=""):
    """-> [refname] from `for-each-ref` output. Pure, so the selftest drives it.

    SELF IS EXCLUDED, and it has to be: my own upstream, and any ref parked on
    my own HEAD, carry MY entries — so a title I am editing in place would
    otherwise collide with the copy I pushed an hour ago, i.e. the guard
    reddening on its own author with nothing to fix. That is the (um) shape,
    which this file has already paid for once.
    """
    skip = {"refs/remotes/origin/main", "refs/remotes/origin/HEAD"}
    if upstream:
        skip.add("refs/remotes/" + upstream.strip())
    refs = []
    for line in (for_each_ref_out or "").splitlines():
        name, _tab, oid = line.partition("\t")
        name, oid = name.strip(), oid.strip()
        if not name or name in skip:
            continue
        if head and oid == head:
            continue                           # a ref parked on my own commit
        refs.append(name)
    # [2026-09-10 (zw)] The cap RETURNS ITS OWN TRUNCATION rather than
    # swallowing it. `return refs[:CAP]` is the (qz) trap in one line: a cap
    # that reaches a caller's reasoning without declaring itself is an
    # undeclared sampling step, and this one would have read as "I compared
    # every open branch" while silently ignoring the 401st. The caller prints
    # the dropped count, so a truncated sweep is never byte-identical to a
    # complete one.
    return refs[:OPEN_BRANCH_REF_CAP], max(0, len(refs) - OPEN_BRANCH_REF_CAP)


def origin_branch_refs():
    """-> [refname] for every OPEN branch on origin, newest tip first.

    [2026-09-10] LOCAL REFS, NOT `git ls-remote`, and the choice is measured
    rather than assumed. `ls-remote` is the obvious candidate — it is the only
    thing that sees a branch this clone has never fetched — and it cannot do
    this job: it returns SHAs, and a SHA whose objects are absent cannot be
    read (`git show <sha>:CHANGELOG.md` fails), so the only finding it could
    ever produce is *"a branch exists that I cannot inspect"*. That is a
    WARNING on a passing run, which `(gl)` measured as not a guard at all.
    It is also a 0.83s NETWORK call on every push and would take this arm's
    fail-safe-open promise offline with it. MEASURED here: all 97 heads
    `ls-remote` reports were already present locally, so the network buys
    nothing today either.
    THE DECLARED BLIND SPOT, therefore: a branch pushed since this clone last
    fetched is invisible to this arm. `git fetch` closes it; the arm prints
    how many branches it compared so a stale clone is never byte-identical to
    a clean one.

    Self-exclusion and the cap live in `_open_refs`, which is pure.

    Returns `(refs, dropped)` — `dropped` is how many refs the cap discarded,
    so a truncated sweep can SAY SO instead of reading as a complete one.
    """
    return _open_refs(
        _git("for-each-ref", "--sort=-committerdate",
             "--format=%(refname)\t%(objectname)", "refs/remotes/origin"),
        head=(_git("rev-parse", "HEAD") or "").strip(),
        upstream=(_git("rev-parse", "--abbrev-ref", "--symbolic-full-name",
                       "@{u}") or "").strip())


def origin_branch_changelogs(refs, budget_s=None, _read_ref=None):
    """-> ([(ref, entries)], truncated). One `git show` per ref, budgeted.

    A ref whose CHANGELOG.md is absent or unreadable is SKIPPED and the sweep
    CONTINUES — 14 of this repo's 98 refs predate the file and they are
    scattered through the list, so stopping at the first one would silently
    truncate the answer. Deliberately NOT one multi-revision `git grep`, which
    is the fast-looking option and is unsafe: MEASURED while designing this, a
    single ref without CHANGELOG.md aborts the whole invocation with `fatal:
    unable to resolve revision`, and piped through `wc -l` that failure reads
    as **zero matches** — a clean scan. One subprocess per ref keeps every
    failure local to the ref that caused it.

    `_read_ref` exists so the selftest can drive the loop offline; production
    never passes it.
    """
    import time
    read = _read_ref or (lambda r: _git("show", r + ":CHANGELOG.md",
                                        timeout=10))
    budget = OPEN_BRANCH_BUDGET_S if budget_s is None else budget_s
    out, t0, truncated = [], time.time(), False
    for r in refs:
        if time.time() - t0 > budget:
            truncated = True
            break
        txt = read(r)
        if not txt:
            continue
        out.append((r, scan(txt)[0]))
    return out, truncated


def origin_claimed_letters(branches):
    """-> {letter} that ANY open origin branch's CHANGELOG already carries."""
    out = set()
    for _ref, entries in branches:
        out |= {l for _d, l, _t in entries}
    return out


def open_branch_clashes(mine, base, branches, my_text=None):
    """-> {letter: (my_title, their_title, [refs])} for a letter THIS tree is
    adding that an OPEN origin branch is also adding, for a different entry.

    [2026-09-10] WHY, and it is the last blind spot in the letter guard.
    `cross_branch` compares against `origin/main` ONLY, so it can only ever
    report a collision AFTER the rival letter has landed — while the rival is
    still an open branch or an open PR, both sides are internally unique and
    both are green. MEASURED on 10-Sep, the day this shipped: ONE entry was
    renumbered FIVE times in a single session — (zn) -> (zq) -> (zr) -> (zs)
    -> (zu) — a sixth letter was taken for a separate fix, and a seventh
    collision followed; `origin/main` itself gained two of those letters
    DURING the session. Seven collisions in one day, every one of them a
    grep-and-repoint across 565 python files' citations, because `git log`
    subjects keep the old letter. While this very fix was being measured an
    EIGHTH arrived: `origin/claude/audit-9sep` and this tree both held (zt),
    the guard reported OK, and then origin/main took (zt) for a THIRD entry.

    THE ARM IS SCOPED BY SUBTRACTION, and that is the whole of why it can be
    left switched on. Comparing my tree against all 98 refs raw produces
    **592 findings** on this repo today, and up to **10,997** for one branch
    carrying a rewritten CHANGELOG — a guard that reddens on a pre-existing
    backlog is exempted within a day and then guards nothing ((mz)). So both
    sides are first reduced to what they ADD relative to origin/main: an entry
    already on main is not a claim by anyone, which retires every merged,
    squash-merged and stale-but-identical branch at once, with no age cutoff
    to tune and no `git merge-base` walk to pay for. MEASURED after: **592 ->
    1**, and the 1 is the real live (zt) clash. Re-measured adversarially by
    treating each of the 82 branches in turn as "mine": the worst case is
    **2 findings**, against 10,997 for the raw comparison.

    THE BOUND IS STRUCTURAL, not tuned: a finding must be a letter this tree
    adds, so the arm can never report more letters than the entries in this
    session's own diff — typically one or two.

    Escapes are NOT re-implemented here: the comparison itself is
    `cross_branch`, so a declared CORRECTED IN PLACE and a declared renumber
    are honoured on an open branch exactly as they are against main.
    """
    base_by = {l: t for _d, l, t in base}
    my_claim = {l for _d, l, t in mine if base_by.get(l) != t}
    if not my_claim:
        return {}
    out = {}
    for ref, entries in branches:
        theirs_new = [(d, l, t) for d, l, t in entries if base_by.get(l) != t]
        # TWO PASSES, cheap one first. `my_text` costs a regex sweep of the
        # whole 3.6MB changelog PER BRANCH (measured: 4.0s across 82 branches,
        # ~60% of this arm's cost) and can only ever REMOVE findings, both
        # escapes being suppressions. So ask the cheap question first and pay
        # for the escapes only on a branch that actually collides — about 1 in
        # 82. Measured after: 4.0s -> 0.9s.
        if not cross_branch(mine, theirs_new):
            continue
        for letter, (mine_t, their_t) in cross_branch(
                mine, theirs_new, my_text=my_text).items():
            if letter not in my_claim:
                continue                       # their clash with main, not mine
            out.setdefault(letter, (mine_t, their_t, []))[2].append(ref)
    return out


def _baseline_changelog(skip_if_same=True):
    """origin/main's CHANGELOG, or None when it is unavailable/irrelevant.

    Fail-SAFE OPEN and deliberately so: no git, a shallow clone with no
    origin/main, or a HEAD that already EQUALS origin/main all return None and
    the guard keeps its pre-existing in-file behaviour. This arm can only ADD a
    finding.

    [2026-08-16 (ns)] CORRECTED IN PLACE: this docstring used to say *"or
    running ON main itself"*, contradicting the NOTE fifteen lines below it and
    the code between them. The arm keys on whether HEAD has DIVERGED from
    origin/main, never on the local ref's name — being skipped on a branch
    called `main` is the exact bug that NOTE records fixing. The stale sentence
    had also been copied into CLAUDE.md's letter rule, where a session would
    actually read it and conclude the arm cannot fire on the workflow this repo
    uses. Both corrected together.

    [2026-09-10] `skip_if_same=False` is for the OPEN-BRANCH arm only. This
    arm asks whether HEAD has DIVERGED, which is right for it; the open-branch
    arm asks about the WORKING TREE, and a session that has just pushed (HEAD
    == origin/main) and is writing its next entry is precisely the window in
    which a letter is chosen. The default is unchanged, so every existing
    caller and test behaves exactly as before.
    """
    base = (_git("rev-parse", "origin/main") or "").strip()
    mine = (_git("rev-parse", "HEAD") or "").strip()
    if not base or (skip_if_same and base == mine):
        return None                            # nothing to compare against
    # NOTE: deliberately NOT skipped when the local branch is called "main".
    # My first cut excluded it, and that disabled this arm in the exact
    # workflow this repo actually uses — sessions commit straight to local
    # `main` and push. It was disabled on the very run that would have caught
    # (gm) being taken by a concurrent session. What matters is whether HEAD
    # has diverged from origin/main, not what the local ref is called.
    return _git("show", "origin/main:CHANGELOG.md")


def main():
    if not os.path.isfile(CHANGELOG):
        print("audit_changelog_letters: CHANGELOG.md not found", file=sys.stderr)
        return 1
    _raw = open(CHANGELOG, encoding="utf-8").read()
    entries, dups = scan(_raw)
    _open_n, _open_trunc = 0, False
    # [2026-08-06 (lc)] A HEADER THAT IS NOT A HEADER. Checked FIRST: every other arm
    # here reasons over the index, and an entry missing from the index cannot
    # be found duplicated, cited or clashing. Fixing it is one newline.
    glued = glued_headers(_raw)
    if glued:
        print("\nCHANGELOG HEADER NOT AT LINE START — invisible to the letter "
              "index, to `grep '^## '`\nand to Markdown, while its letter is "
              "still cited:\n")
        for d, letter in glued:
            print(f"  ({letter})  {d}")
        print("\nFIX: put a blank line before the header. Measured in lc: one "
              "glued header took an\nentry out of the index while 10 "
              "citations, 6 in tracked code, pointed at it.\n")
        return 1
    base_text = _baseline_changelog()
    if base_text:
        # [(nq)] `_raw` rides along so a letter whose own entry declares
        # CORRECTED IN PLACE is not reported as a collision — the signature is
        # identical and I12 mandates the correction. See `corrected_letters`.
        clashes = cross_branch(entries, scan(base_text)[0], my_text=_raw)
        if clashes:
            print("\nCROSS-BRANCH CHANGELOG LETTER COLLISION — this branch and "
                  "origin/main both used\nthese letters for DIFFERENT entries. "
                  "Every citation to them is ambiguous after the merge:\n")
            for letter, (mine_t, theirs_t) in sorted(clashes.items()):
                print(f"  ({letter})")
                print(f"      this branch : {mine_t[:84]}")
                print(f"      origin/main : {theirs_t[:84]}")
            print("\nFIX: the entry that is CITED FROM TRACKED CODE keeps the "
                  "letter; the other moves\nto the next free one and records "
                  "the move inline. Decide by grepping the tree:\n"
                  "  grep -rn '(<letter>)' --include='*.md' --include='*.py' "
                  "--include='*.yml' .\n")
            return 1
        # [2026-09-01 (vw)] THE LOST-ENTRIES ARM. PR #237 replaced this file's
        # 655 entries with a 2-line stub and every guard stayed green; PR #212
        # then overwrote the stub with an 11-day-stale copy. The changelog may
        # only GROW: an era entry origin/main carries and this tree does not is
        # a deletion, and a deletion is the defect — restore it, or declare the
        # renumber that moved it.
        lost = lost_entries(entries, scan(base_text)[0], my_text=_raw)
        if lost:
            print(f"\nCHANGELOG ENTRIES LOST vs origin/main — {len(lost)} "
                  f"entr{'y' if len(lost) == 1 else 'ies'} present there and "
                  f"missing from this tree. The changelog is the fleet's "
                  f"record and its sync channel; it only ever grows:\n")
            for d, letter, title in lost[:12]:
                print(f"  ({letter})  {d}  {title[:80]}")
            if len(lost) > 12:
                print(f"  ... and {len(lost) - 12} more")
            print("\nFIX: your branch's CHANGELOG.md is stale or was "
                  "overwritten — rebase it onto origin/main's copy and re-add "
                  "your own entries on top (see (vw) for the #237/#212 wipe "
                  "this arm exists for). A deliberate renumber is declared "
                  "inline: 'RENUMBERED (x) -> (y)'.\n")
            return 1
    # [2026-09-10] THE OPEN-BRANCH ARM — the collision `cross_branch` above
    # structurally CANNOT see. It compares against origin/main, so a rival
    # letter is only visible once it has already landed; while the rival is an
    # unmerged branch or an open PR both files are internally unique and both
    # runs are green. See `open_branch_clashes` for the 10-Sep measurement
    # (seven renumbers in one day) and for why both sides are first reduced to
    # what they ADD relative to main (592 raw findings on this repo -> 1).
    _open_base = base_text or _baseline_changelog(skip_if_same=False)
    if _open_base:
        _ob_refs, _ob_dropped = origin_branch_refs()
        _branches, _open_trunc = origin_branch_changelogs(_ob_refs)
        _open_n = len(_branches)
        open_clashes = open_branch_clashes(entries, scan(_open_base)[0],
                                           _branches, my_text=_raw)
        if open_clashes:
            print("\nOPEN-BRANCH CHANGELOG LETTER COLLISION — a letter this "
                  "tree is ADDING is already\nspoken for by an UNMERGED "
                  "branch on origin. Both sides are internally unique and "
                  "both\nare green today; every citation goes ambiguous at "
                  "the merge:\n")
            for letter, (mine_t, their_t, refs) in sorted(open_clashes.items()):
                print(f"  ({letter})")
                print(f"      this tree   : {mine_t[:84]}")
                print(f"      their entry : {their_t[:84]}")
                for r in refs:
                    print("      on branch   : "
                          + r.replace("refs/remotes/", ""))
            print("\nFIX: take a letter free EVERYWHERE — `python3 "
                  "scripts/audit_changelog_letters.py --next`\ncounts open "
                  "origin branches now, so moving YOUR entry is always "
                  "available and is one\ncommand. If yours is the entry CITED "
                  "FROM TRACKED CODE it keeps the letter and the\nother "
                  "branch moves instead (rule 3); either way record the move "
                  "inline, because\n`git log` subjects keep the old letter. "
                  "Run `git fetch` first — this arm reads only\nbranches this "
                  "clone has already fetched.\n")
            return 1
    if dups:
        print(f"\nDUPLICATE CHANGELOG LETTERS (era >= {ERA_START}) — every "
              f"cross-reference to these is ambiguous:\n")
        for letter, uses in sorted(dups.items()):
            print(f"  ({letter}) used {len(uses)}x:")
            for d, t in uses:
                print(f"      {d}  {t[:88]}")
        print("\nFIX: the entry that is CITED keeps the letter; the other moves "
              "to the next free one\nand records the move inline (see the "
              "convention in CLAUDE.md). Check citations with:\n"
              "  grep -rn '(<letter>)' --include='*.md' --include='*.py' "
              "--include='*.yml' .\n")
        return 1
    # [2026-08-06 (lc)] A CITATION THAT RESOLVES TO NOTHING. Uniqueness says two entries
    # do not share a letter; it says nothing about a letter cited from code
    # that no entry carries — which is how a real-money finding
    # (`fleet_bus.is_crypto`, 19 non-crypto live positions) reached tracked
    # code and never reached this file. Known letters come from the WHOLE
    # changelog, not the >=ERA_START window: citing an older entry is normal.
    _known = {l for _, l, _ in HEADER.findall(_raw)}
    _py = [p for p in walk_py(ROOT)]
    dangling = dangling_code_citations(sorted(_py), _known)
    if dangling:
        print("\nCHANGELOG CITATION IN CODE RESOLVES TO NO ENTRY — a reader "
              "following it lands nowhere:\n")
        for p, ln, letter in dangling[:20]:
            print(f"  ({letter})  {os.path.relpath(p, ROOT)}:{ln}")
        if len(dangling) > 20:
            print(f"  ... and {len(dangling) - 20} more")
        print("\nFIX: either the entry is missing (write it — an undocumented "
              "change is the defect,\nnot the citation) or the letter moved "
              "(repoint the comment). Measured (lc): a\nreal-money finding "
              "lived only in a commit body because its entry was never "
              "written.\n")
        return 1
    # [2026-09-10] The branch count is PUBLISHED, never assumed. A run that
    # compared zero open branches (a shallow CI checkout has no
    # remote-tracking refs but its own) is byte-identical to a clean sweep
    # unless it says so — the (po)/(lv) rule this repo keeps paying for.
    print(f"audit_changelog_letters: OK — {len(entries)} lettered entries since "
          f"{ERA_START}, every letter unique, no glued header, "
          f"{len(_py)} python files' citations all resolve"
          + (f", {_open_n} open origin branch(es) compared"
             if _open_n else ", NO open origin branches compared")
          + (" [BUDGET TRUNCATED]" if _open_trunc else "")
          + (f" ({len(LETTERS_OK)} declared)" if LETTERS_OK else ""))
    return 0


def _selftest():
    """The detector must FIRE on a duplicate, not merely stay quiet on a clean
    file — a guard that can only pass is not a guard."""
    clean = ("## 2026-07-29 (fa) — one\n\nbody\n\n"
             "## 2026-07-29 (fb) — two\n\nbody\n")
    _e, d = scan(clean)
    assert not d, d
    assert len(_e) == 2, _e

    dirty = clean + "\n## 2026-07-29 (fa) — a colliding third\n\nbody\n"
    _e2, d2 = scan(dirty)
    assert set(d2) == {"fa"}, d2
    assert len(d2["fa"]) == 2, d2
    assert any("colliding third" in t for _dt, t in d2["fa"]), d2

    # PRE-ERA duplicates must be tolerated: 17-Jul is the restart day and
    # legitimately carries two sequences.
    old = ("## 2026-07-17 (a) — restart head\n\nb\n\n"
           "## 2026-07-17 (a) — old-sequence tail\n\nb\n")
    _e3, d3 = scan(old)
    assert not d3 and not _e3, "pre-era headers must be ignored entirely"

    # letterless headers (pre-convention) must never crash or count
    assert scan("## 2026-07-14\n\nbody\n") == ([], {})

    # ---- CROSS-BRANCH arm (hj): the collision the in-file check CANNOT see --
    # Reproduces 2026-07-30 exactly: both sides internally unique, both used
    # (fz) for a different entry.
    _mine = scan("## 2026-07-30 (fz) — THE OFFENSE PASS\n\nb\n")[0]
    _main = scan("## 2026-07-30 (fz) — a THIRD era-pooling error\n\nb\n")[0]
    assert set(cross_branch(_mine, _main)) == {"fz"}, cross_branch(_mine, _main)
    assert cross_branch(_mine, _main)["fz"] == (
        "— THE OFFENSE PASS", "— a THIRD era-pooling error")
    # SAME letter + SAME title is a rebase/merge of the same entry, NOT a
    # collision. Without this the guard would fire on every ordinary branch
    # that merged main in — i.e. it would be turned off within a day.
    assert cross_branch(_mine, _mine) == {}
    # a letter only one side has is not a collision either
    _other = scan("## 2026-07-30 (hj) — something else\n\nb\n")[0]
    assert cross_branch(_mine, _other) == {}
    assert cross_branch([], _main) == {} and cross_branch(_mine, []) == {}

    # [(nq)] AN ENTRY CORRECTED IN PLACE IS NOT A COLLISION — I12 requires the
    # correction, and a corrected TITLE is byte-indistinguishable from a race.
    # The fixture is a REAL in-place correction: one clause of one title edited,
    # which is what (nn) actually was. [(ns)] An earlier version of this arm
    # used two unrelated titles and still expected suppression — it passed only
    # because the escape was too loose, and the (ns) similarity requirement
    # correctly refuses it. A fixture that does not look like the real thing
    # cannot pin the real thing.
    _orig_text = ("## 2026-07-30 (fz) — THE OFFENSE PASS: the growth rail "
                  "reaches six books, FOUR DAYS of tape\n\nb\n")
    _orig = scan(_orig_text)[0]
    _fixed_text = ("## 2026-07-30 (fz) — THE OFFENSE PASS: the growth rail "
                   "reaches six books, 24 HOURS of tape\n\n"
                   "> **[CORRECTED IN PLACE per I12.]** was 'four days'\n")
    _fixed = scan(_fixed_text)[0]
    assert cross_branch(_fixed, _orig, my_text=_fixed_text) == {}, \
        "a declared in-place correction must not read as a letter collision"
    # ...but WITHOUT the declaration the very same edit still fires, so the
    # (fz) incident this guard was built for is untouched.
    assert set(cross_branch(_fixed, _orig)) == {"fz"}
    _undeclared = ("## 2026-07-30 (fz) — THE OFFENSE PASS: the growth rail "
                   "reaches six books, 24 HOURS of tape\n\nb\n")
    assert set(cross_branch(scan(_undeclared)[0], _orig,
                            my_text=_undeclared)) == {"fz"}, \
        "no declaration ⇒ still a collision"
    # THE ESCAPE IS PER-ENTRY: a correction declared in a DIFFERENT entry must
    # not excuse this one, or one correction would silence the whole guard.
    _elsewhere = ("## 2026-07-31 (ga) — unrelated\n\n"
                  "> **[CORRECTED IN PLACE per I12.]**\n\n"
                  + _undeclared)
    assert set(cross_branch(scan(_elsewhere)[0], _orig,
                            my_text=_elsewhere)) == {"fz"}, \
        "a correction in another entry must not excuse this letter"
    assert corrected_letters(_elsewhere) == {"ga"}
    assert corrected_letters("") == set() and corrected_letters(None) == set()

    # [(ns)] A DECLARATION IS NOT ENOUGH — the titles must be the SAME ENTRY.
    # The hole (nq) opened: two DIFFERENT entries that both happen to be
    # corrections would share a letter and be waved through. Measured ratios:
    # a real in-place correction 0.978, this case 0.259, the (fz) race 0.267.
    _race_text = ("## 2026-08-16 (fz) — the Douglas row overstated its numbers\n\n"
                  "> **[CORRECTED IN PLACE per I12.]** pre-(ml) figures\n")
    assert set(cross_branch(scan(_race_text)[0], _main,
                            my_text=_race_text)) == {"fz"}, \
        "a DIFFERENT entry that merely declares a correction is still a race"
    assert same_entry("— CI WAS RED FOR FOUR DAYS OVER 0.1pp, AND THE REASON "
                      "WAS 13 UNTESTED STATEMENTS INLINED INTO main()",
                      "— CI WAS RED FOR 24 HOURS OVER 0.1pp, AND THE REASON "
                      "WAS 13 UNTESTED STATEMENTS INLINED INTO main()"), \
        "an edited title is the same entry"
    assert not same_entry("— THE OFFENSE PASS", "— a THIRD era-pooling error")
    assert not same_entry("— the Douglas row overstated its numbers",
                          "— `(nn)` SAID FOUR DAYS AND THE RECEIPTS SAY 24 HOURS")
    assert same_entry("x", "x") and not same_entry("", "a totally other title")
    assert not same_entry(None, "anything")
    # the pre-era scope applies here too — 17-Jul's restart must not clash
    _pre = scan("## 2026-07-17 (a) — restart head\n\nb\n")[0]
    assert cross_branch(_pre, scan("## 2026-07-17 (a) — tail\n\nb\n")[0]) == {}

    # ---- [(vw)] THE LOST-ENTRIES ARM: the changelog only grows -------------
    # Reproduces the #237/#212 shape: entries on origin/main, gone from mine.
    _full = ("## 2026-07-30 (fz) — one\n\nb\n\n"
             "## 2026-07-30 (ga) — two\n\nb\n")
    _wiped = "## 2026-07-30 (fz) — one\n\nb\n"
    _lost = lost_entries(scan(_wiped)[0], scan(_full)[0])
    assert [l for _d, l, _t in _lost] == ["ga"], _lost
    # identical sets and my-side ADDITIONS are quiet — growth is the point
    assert lost_entries(scan(_full)[0], scan(_full)[0]) == []
    assert lost_entries(scan(_full + "\n## 2026-07-31 (gb) — three\n\nb\n")[0],
                        scan(_full)[0]) == []
    # a DECLARED renumber is not a loss...
    _moved = ("## 2026-07-30 (fz) — one\n\nb\n\n"
              "## 2026-07-30 (gb) — two\n\n"
              "> RENUMBERED (ga) -> (gb) on a collision\n\nb\n")
    assert lost_entries(scan(_moved)[0], scan(_full)[0], my_text=_moved) == []
    # ...a declaration whose moved-to entry does NOT carry the displaced title
    # excuses nothing — the two-signal rule. The first cut of this arm took
    # the declaration alone, and the real file's ~48 historical renumber
    # records in prose made it vacuous for any letter near the word
    # "renumber" (found by the I3 mutation on the real file, not by these
    # fixtures — which is why this fixture now exists)...
    _moved_lie = ("## 2026-07-30 (fz) — one\n\nb\n\n"
                  "## 2026-07-30 (gb) — entirely different\n\n"
                  "> RENUMBERED (ga) -> (gb)\n\nb\n")
    assert lost_entries(scan(_moved_lie)[0], scan(_full)[0],
                        my_text=_moved_lie), \
        "a renumber declaration without the displaced title is not an excuse"
    # ...an UNDECLARED disappearance still fires (the silent-sweep shape)...
    _swept = ("## 2026-07-30 (fz) — one\n\nb\n\n"
              "## 2026-07-30 (gb) — two\n\nb\n")
    assert lost_entries(scan(_swept)[0], scan(_full)[0], my_text=_swept), \
        "an undeclared disappearance must fire"
    # ...and the WIPE ITSELF: a stub loses everything
    assert len(lost_entries(scan("")[0], scan(_full)[0])) == 2

    # ---- [(vw)] cross_branch honours a DECLARED renumber, two signals ------
    _theirs_fz = scan("## 2026-07-30 (fz) — THE DISPLACED ENTRY\n\nb\n")[0]
    _mine_rn = ("## 2026-07-30 (fz) — MY OWN DIFFERENT ENTRY\n\nb\n\n"
                "## 2026-07-30 (gb) — THE DISPLACED ENTRY\n\n"
                "> RENUMBERED (fz) -> (gb) at the merge\n\nb\n")
    assert cross_branch(scan(_mine_rn)[0], _theirs_fz,
                        my_text=_mine_rn) == {}, \
        "a declared renumber carrying the displaced entry must not clash"
    # a declaration WITHOUT the matching moved entry excuses nothing
    _mine_lie = ("## 2026-07-30 (fz) — MY OWN DIFFERENT ENTRY\n\nb\n\n"
                 "## 2026-07-30 (gb) — SOMETHING ELSE ENTIRELY\n\n"
                 "> RENUMBERED (fz) -> (gb)\n\nb\n")
    assert set(cross_branch(scan(_mine_lie)[0], _theirs_fz,
                            my_text=_mine_lie)) == {"fz"}, \
        "a renumber declaration without the moved entry is a sweep"
    # and no declaration at all keeps the original strictness
    _mine_nd = "## 2026-07-30 (fz) — MY OWN DIFFERENT ENTRY\n\nb\n"
    assert set(cross_branch(scan(_mine_nd)[0], _theirs_fz,
                            my_text=_mine_nd)) == {"fz"}
    # fail-SAFE: the baseline arm must never raise, whatever git says here
    _b = _baseline_changelog()
    assert _b is None or isinstance(_b, str), type(_b)

    # and the REAL file must parse to something (a regex that matches nothing
    # would make this guard vacuously green forever)
    real, _rd = scan(open(CHANGELOG, encoding="utf-8").read())
    assert len(real) > 50, f"parsed only {len(real)} headers — regex rot?"

    # [2026-08-16 (pd)] THE SEQUENCE. Every rollover asserted below is one this
    # file's own history actually took; `zz -> aaa` is the one it has not
    # reached, included because the bug retired here was a helper that worked
    # right up until the sequence outgrew it.
    assert succ("a") == "b" and succ("y") == "z"
    assert succ("z") == "aa", "single letters must GROW, not wrap to 'a'"
    assert succ("az") == "ba" and succ("bz") == "ca" and succ("nz") == "oa"
    assert succ("oz") == "pa", "the boundary that pushed a letterless commit"
    assert succ("zz") == "aaa", "and it must not be a countdown one level up"
    for _bad in ("", "A", "a1", "(a)", None, "a b"):
        try:
            succ(_bad)
        except (ValueError, TypeError):
            pass
        else:
            raise AssertionError(f"succ accepted junk: {_bad!r}")
    assert next_free({"pa", "pb"}, start="pa") == "pc"
    assert next_free(set(), start="a") == "a"
    assert next_free({"z"}, start="z") == "aa", "next_free must cross a boundary"
    # [(pd)] `latest` must order by SEQUENCE, not by string: "z" > "aa" as
    # text, while aa comes AFTER z here. Getting this wrong sends the next
    # entry backwards into a gap.
    assert latest(["z", "aa"]) == "aa" and latest(["aa", "z"]) == "aa"
    assert latest(["b", "oz", "pa"]) == "pa"
    assert latest([]) is None and latest(["ZZ", "9"]) is None
    assert rank("a") == 1 and rank("z") == 26 and rank("aa") == 27
    # the real file HAS holes, so first-free != next: pin that the CLI's rule
    # (start after the tip) never reuses one
    # [(pd)] WHAT COUNTS AS A RESERVATION — each of these three was a wrong
    # answer this function actually gave before it was pinned. NOTE THE
    # `_cite()` HELPER: writing a literal bracketed letter in THIS file would
    # reserve it for real, because this file is scanned too — the same trap
    # the module docstring already records for its own prose. Caught by
    # running `--next` after adding these arms and getting a letter two past
    # the one I had reserved.
    def _cite(x):
        return "(" + x + ")"

    _base = f"## 2026-08-16 {_cite('pa')} — tip\n\nbody\n"
    assert next_letter(_base) == "pb", next_letter(_base)
    #   1. a genuine reservation just ahead IS honoured (the stolen-letter hole)
    assert next_letter(_base + f"\nsee {_cite('pb')} for why\n") == "pc"
    #   2. an English word in brackets is NOT a letter (this answered `woo`)
    assert next_letter(_base + "\n" + " ".join(
        _cite(w) for w in ("the", "usd", "vol", "row")) + "\n") == "pb"
    #   3. CALL SYNTAX is not a citation (the window filled with `px`, `py`)
    assert next_letter(_base + f"\nx = _tail{_cite('pb')} + pct{_cite('pc')}\n") == "pb"
    #   4. and the sequence never goes BACKWARDS into a historical gap: this
    #      file has 381 entries and no `er` header, which is what made the
    #      first version of the CLI answer with it.
    _gapped = _base + f"## 2026-08-16 {_cite('pc')} — later\n\nb\n"
    assert rank(next_letter(_gapped)) > rank("pc"), next_letter(_gapped)

    _real = claimed_letters(open(CHANGELOG, encoding="utf-8").read())
    _tip = latest(_real)
    assert rank(next_free(_real, start=succ(_tip))) > rank(_tip), \
        "the next letter must move the sequence FORWARD, never into a gap"
    # built, never spelled: a literal bracketed letter in THIS file would
    # reserve it for real (see the _cite note below — the same trap twice)
    _br = lambda x: "(" + x + ")"                                # noqa: E731
    _hdr = f"## 2026-08-16 {_br('pa')} — x\n\nbody\n"
    assert "pa" in claimed_letters(_hdr), "a header claims its letter"
    assert "pb" in claimed_letters(_hdr + f"\nsee {_br('pb')}\n"), \
        "a CITATION just ahead of the tip claims a letter too — the hole "\
        "that let one session's citation resolve to another's entry"
    # and against the real file: the answer must not already be taken
    _real_txt = open(CHANGELOG, encoding="utf-8").read()
    _n = next_free(claimed_letters(_real_txt))
    assert _n not in claimed_letters(_real_txt), _n

    # ---- [(um)] THE WALK MUST NOT READ OTHER SESSIONS' WORKTREES ----------
    # CONSTRUCTED, not observed. The first version of this check ran against
    # the live tree and passed with the skip REMOVED — because the sibling
    # worktree's dangling citation had transiently cleared, so "green" said
    # nothing about the fix. (po): empty output is not a negative result until
    # the check has been seen to produce a positive one. So build the
    # condition: a repo-shaped tmp dir with one ordinary file and one file
    # inside `.claude/worktrees`, and assert the walk sees exactly the first.
    import shutil
    import tempfile
    _tmp = tempfile.mkdtemp(prefix="acl_walk_")
    try:
        os.makedirs(os.path.join(_tmp, "scripts"))
        _wt = os.path.join(_tmp, ".claude", "worktrees", "other-session",
                           "scripts")
        os.makedirs(_wt)
        _mine = os.path.join(_tmp, "scripts", "mine.py")
        _theirs = os.path.join(_wt, "theirs.py")
        # a hook living directly under `.claude` — THIS branch's own file, and
        # the reason the skip is scoped to the worktree root rather than to
        # `.claude` wholesale. Without this case a too-broad skip passes.
        os.makedirs(os.path.join(_tmp, ".claude", "hooks"))
        _hook = os.path.join(_tmp, ".claude", "hooks", "hook.py")
        for _p in (_mine, _theirs, _hook):
            with open(_p, "w", encoding="utf-8") as _fh:
                # ASSEMBLED, never written literally: a whole-file scan
                # matches the guard's own source, so a literal fixture makes
                # this file flag ITSELF — the (po) trap, inside the guard
                # written to avoid it. Caught by running the guard after the
                # test passed.
                _fh.write("# [2026-08-27 " + "(zz)" + "] a citation\n")
        _seen = sorted(walk_py(_tmp))
        assert _seen == sorted([_mine, _hook]), _seen
        # POSITIVE CONTROL: without the skip the walk MUST find the worktree
        # file — otherwise this test would pass on a walk that finds nothing.
        _saved = set(SKIP_RELPATHS)
        SKIP_RELPATHS.clear()
        try:
            _both = sorted(walk_py(_tmp))
            assert _both == sorted([_mine, _hook, _theirs]), _both
        finally:
            SKIP_RELPATHS.update(_saved)
        # and the dangling-citation arm genuinely fires on that file, so the
        # skip is suppressing a REAL finding rather than a hypothetical one
        assert dangling_code_citations([_theirs], {"f" + "a"}), \
            "the citation arm must flag the worktree file when it is scanned"
        assert not dangling_code_citations([_mine], {"zz"}), \
            "a known letter must not be reported as dangling"
    finally:
        shutil.rmtree(_tmp, ignore_errors=True)

    # ---- [2026-09-10] THE OPEN-BRANCH ARM ---------------------------------
    # THE INCIDENT: one entry was renumbered FIVE times in a single session —
    # (zn) -> (zq) -> (zr) -> (zs) -> (zu) — a sixth letter went to a separate
    # fix and a seventh collision followed, and while this fix was being
    # measured an EIGHTH arrived: this tree and origin/claude/audit-9sep both
    # held (zt) and the guard printed OK, because the rival was an unmerged
    # branch and origin/main is the only thing `cross_branch` can see.
    # FIXTURES ARE ASSEMBLED, never spelled: a literal bracketed letter in
    # this file RESERVES it for real, the trap this module's own docstrings
    # already record twice.
    _obr = lambda x: "(" + x + ")"                               # noqa: E731
    _ob_main = f"## 2026-09-10 {_obr('zk')} — an entry already on main\n\nb\n"
    _ob_base = scan(_ob_main)[0]
    _ob_my_txt = _ob_main + f"\n## 2026-09-10 {_obr('zl')} — MY NEW ENTRY\n\nb\n"
    _ob_my = scan(_ob_my_txt)[0]
    _ob_their = scan(_ob_main + f"\n## 2026-09-10 {_obr('zl')} — THEIR "
                     "DIFFERENT ENTRY\n\nb\n")[0]
    _ob_hit = open_branch_clashes(_ob_my, _ob_base,
                                  [("refs/remotes/origin/claude/x", _ob_their)],
                                  my_text=_ob_my_txt)
    assert set(_ob_hit) == {"zl"}, _ob_hit
    assert _ob_hit["zl"][2] == ["refs/remotes/origin/claude/x"], _ob_hit
    # THE NOISE CONTROL, and it is the whole reason this arm can stay switched
    # on. A branch whose colliding letter is ALREADY ON MAIN is adding
    # nothing, so it is quiet — which retires every merged, squash-merged and
    # stale-identical branch at once. MEASURED on this repo without the
    # subtraction: 592 findings across 98 refs, and 10,997 for a single branch
    # carrying a rewritten changelog. A guard that reddens on a pre-existing
    # backlog is exempted within a day and then guards nothing ((mz)).
    assert open_branch_clashes(_ob_my, _ob_base, [("r", scan(_ob_main)[0])],
                               my_text=_ob_my_txt) == {}, \
        "a letter already on main is nobody's claim"
    # THE SUBTRACTION ON MY SIDE, pinned: a letter I merely CARRY from main,
    # which a branch is rewriting under me, is that branch's race with main —
    # not mine, and not something I could fix by editing my own file. Without
    # this filter the arm reports other people's collisions on every run.
    _ob_carry = scan(f"## 2026-09-10 {_obr('zk')} — THEIR REWRITE OF A MAIN "
                     "ENTRY\n\nb\n")[0]
    assert open_branch_clashes(_ob_my, _ob_base, [("r", _ob_carry)],
                               my_text=_ob_my_txt) == {}, \
        "a letter I merely carry from main is not my claim"
    # THE SUBTRACTION ON THEIR SIDE, pinned: a branch merely CARRYING main's
    # copy of a letter I am changing is not a SECOND collision — that finding
    # belongs to the cross_branch arm, and repeating it once per branch is
    # exactly how the unsubtracted comparison reached 592.
    _ob_edit_txt = f"## 2026-09-10 {_obr('zk')} — I CHANGED THIS ENTRY\n\nb\n"
    assert open_branch_clashes(scan(_ob_edit_txt)[0], _ob_base,
                               [("r", scan(_ob_main)[0])],
                               my_text=_ob_edit_txt) == {}, \
        "a branch carrying main's copy is not a second collision"
    # THE PURE REF FILTER: main, HEAD, my own upstream and any ref parked on
    # my own commit are excluded — comparing me against myself would redden
    # the guard on its own author, with nothing to fix ((um)).
    _ob_out = ("refs/remotes/origin/main\tAAA\n"
               "refs/remotes/origin/HEAD\tAAA\n"
               "refs/remotes/origin/claude/mine\tHHH\n"
               "refs/remotes/origin/claude/self\tMYHEAD\n"
               "refs/remotes/origin/claude/other\tBBB\n")
    assert _open_refs(_ob_out, head="MYHEAD",
                      upstream="origin/claude/mine") == (
        ["refs/remotes/origin/claude/other"], 0), _open_refs(
            _ob_out, "MYHEAD", "origin/claude/mine")
    # POSITIVE CONTROL: with no HEAD and no upstream the same input yields the
    # three non-main refs, so the assertion above is testing the filter and
    # not an empty walk.
    assert len(_open_refs(_ob_out)[0]) == 3, _open_refs(_ob_out)
    assert _open_refs("") == ([], 0) and _open_refs(None) == ([], 0)
    # a letter only THEY add is THEIR race with main, not a finding I can fix
    _ob_theirs_only = scan(_ob_main + f"\n## 2026-09-10 {_obr('zm')} — only "
                           "theirs\n\nb\n")[0]
    assert open_branch_clashes(_ob_my, _ob_base, [("r", _ob_theirs_only)],
                               my_text=_ob_my_txt) == {}
    # SAME letter + SAME title is a shared entry, never a race
    assert open_branch_clashes(_ob_my, _ob_base, [("r", _ob_my)],
                               my_text=_ob_my_txt) == {}
    # FAIL-SAFE OPEN: no branches, or nothing of my own to claim, finds nothing
    assert open_branch_clashes(_ob_my, _ob_base, [], my_text=_ob_my_txt) == {}
    assert open_branch_clashes(_ob_base, _ob_base, [("r", _ob_their)],
                               my_text=_ob_main) == {}
    # THE ESCAPES ARE INHERITED, not re-implemented — the comparison IS
    # `cross_branch`, so a declared in-place correction (I12) is honoured on
    # an open branch exactly as it is against main...
    _ob_corr_txt = (_ob_main + f"\n## 2026-09-10 {_obr('zl')} — MY NEW ENTRY, "
                    "24 HOURS\n\n> **[CORRECTED IN PLACE per I12.]** was "
                    "'four days'\n")
    _ob_corr_their = scan(_ob_main + f"\n## 2026-09-10 {_obr('zl')} — MY NEW "
                          "ENTRY, FOUR DAYS\n\nb\n")[0]
    assert open_branch_clashes(scan(_ob_corr_txt)[0], _ob_base,
                               [("r", _ob_corr_their)],
                               my_text=_ob_corr_txt) == {}, \
        "a declared in-place correction must not read as an open-branch race"
    # ...and the SAME edit without the declaration still fires.
    _ob_undecl = (_ob_main + f"\n## 2026-09-10 {_obr('zl')} — MY NEW ENTRY, "
                  "24 HOURS\n\nb\n")
    assert set(open_branch_clashes(scan(_ob_undecl)[0], _ob_base,
                                   [("r", _ob_corr_their)],
                                   my_text=_ob_undecl)) == {"zl"}, \
        "no declaration ⇒ still a race"
    # ...and so is a DECLARED renumber that actually carries the displaced
    # entry, which is the repair this guard's own FIX text prescribes.
    _ob_rn_txt = (_ob_main + f"\n## 2026-09-10 {_obr('zl')} — MY OWN ENTRY"
                  f"\n\nb\n\n## 2026-09-10 {_obr('zm')} — THEIR DISPLACED "
                  "ENTRY\n\n> RENUMBERED " + _obr('zl') + " -> " + _obr('zm')
                  + " at the merge\n\nb\n")
    _ob_rn_their = scan(_ob_main + f"\n## 2026-09-10 {_obr('zl')} — THEIR "
                        "DISPLACED ENTRY\n\nb\n")[0]
    assert open_branch_clashes(scan(_ob_rn_txt)[0], _ob_base,
                               [("r", _ob_rn_their)],
                               my_text=_ob_rn_txt) == {}, \
        "a declared renumber carrying the displaced entry must not clash"
    # `origin_claimed_letters` is what makes `--next` PREVENTIVE rather than
    # merely diagnostic: measured at the incident, from a tip of `zs` the old
    # rule handed out the very letter audit-9sep was already using.
    assert origin_claimed_letters([("r", _ob_their)]) == {"zk", "zl"}
    assert origin_claimed_letters([]) == set()
    # THE LIVE GIT ARMS must never raise, whatever this checkout is, and must
    # never compare me against myself.
    _ob_refs, _ob_dropped = origin_branch_refs()
    assert isinstance(_ob_refs, list), type(_ob_refs)
    assert isinstance(_ob_dropped, int) and _ob_dropped >= 0, _ob_dropped
    # the cap must REPORT its truncation, never swallow it ((qz))
    _capped, _drop = _open_refs("\n".join(
        f"refs/remotes/origin/b{i}\tdead{i}" for i in range(OPEN_BRANCH_REF_CAP + 7)))
    assert len(_capped) == OPEN_BRANCH_REF_CAP and _drop == 7, (len(_capped), _drop)
    assert "refs/remotes/origin/main" not in _ob_refs
    assert "refs/remotes/origin/HEAD" not in _ob_refs
    _ob_bl, _ob_tr = origin_branch_changelogs(_ob_refs[:2])
    assert isinstance(_ob_bl, list) and _ob_tr is False
    # AN EXHAUSTED BUDGET MUST SAY SO. A partial sweep that reports itself as
    # complete is the (qz) silent-cap trap, in the guard whose whole job is to
    # not miss a letter.
    _ob_bl0, _ob_tr0 = origin_branch_changelogs(["refs/remotes/origin/main"],
                                                budget_s=-1.0)
    assert _ob_bl0 == [] and _ob_tr0 is True, (_ob_bl0, _ob_tr0)
    # AN UNRESOLVABLE REF IS SKIPPED AND THE SWEEP CONTINUES. 14 of this
    # repo's 98 refs predate CHANGELOG.md and they are scattered through the
    # list, so ending the sweep at the first one would silently drop every
    # branch after it — a partial answer wearing a complete one's output.
    # Driven offline, so this pins the LOOP and not the checkout.
    _ob_seen = []

    def _ob_read(r):
        _ob_seen.append(r)
        return _ob_main if r.endswith("/good") else None

    _ob_mix, _ = origin_branch_changelogs(
        ["refs/remotes/origin/no-such-ref", "refs/remotes/origin/good"],
        _read_ref=_ob_read)
    assert [r for r, _e in _ob_mix] == ["refs/remotes/origin/good"], _ob_mix
    assert _ob_seen == ["refs/remotes/origin/no-such-ref",
                        "refs/remotes/origin/good"], \
        "an unresolvable ref must be skipped, never end the sweep"

    # ---- THE ARM MUST FIRE FROM `main()`, NOT ONLY FROM ITS PURE HELPER ----
    # [2026-09-10 (zw)] A 24-mutation round killed 16 and left EIGHT alive, and
    # every survivor was in `main()`'s wiring rather than in the comparison:
    # `if open_clashes:` -> `if False and open_clashes:` disabled the whole
    # detection and nothing went red. That is the same shape this session found
    # in 🏦 Rich Dad an hour earlier, and it is the shape this file's own
    # doctrine names — a helper can be perfect while the arm that calls it is
    # dead. So `main()` is driven end-to-end here against stubbed git seams: a
    # planted CHANGELOG this tree ADDS a letter to, and a stub branch that
    # holds the same letter for a different title.
    import contextlib
    import io
    import tempfile

    _g = globals()
    _saved = {k: _g[k] for k in ("CHANGELOG", "origin_branch_refs",
                                 "origin_branch_changelogs",
                                 "_baseline_changelog",
                                 "dangling_code_citations")}
    try:
        _base_txt = ("## 2026-08-01 (aa) — base one\n\nbody\n")
        _mine_txt = ("## 2026-08-02 (ab) — MY entry\n\nbody\n\n"
                     + _base_txt)
        _their = [("refs/remotes/origin/claude/rival",
                   scan("## 2026-08-02 (ab) — THEIR different entry\n\nbody\n\n"
                        + _base_txt)[0])]
        _fd, _tmp = tempfile.mkstemp(suffix=".md")
        os.close(_fd)
        open(_tmp, "w", encoding="utf-8").write(_mine_txt)
        _g["CHANGELOG"] = _tmp
        _g["origin_branch_refs"] = lambda: (["refs/remotes/origin/claude/rival"], 0)
        _g["origin_branch_changelogs"] = lambda refs, **k: (_their, False)
        _g["_baseline_changelog"] = lambda **k: _base_txt
        # the fixture CHANGELOG holds two letters; the real tree's citations
        # resolve against the REAL file, so that arm is stubbed OUT rather
        # than allowed to fail this fixture for an unrelated reason.
        _g["dangling_code_citations"] = lambda *a, **k: []

        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _rc = main()
        _out = _buf.getvalue()
        assert _rc == 1, (
            "main() did not FAIL on a letter an open branch already holds — "
            "the open-branch arm is wired but inert")
        assert "OPEN-BRANCH CHANGELOG LETTER COLLISION" in _out, _out[:400]
        assert "(ab)" in _out and "claude/rival" in _out, _out[:400]

        # POSITIVE CONTROL, so the assertion above is testing the ARM and not a
        # main() that fails on everything: the same tree with a branch holding
        # the SAME title is a rebase, not a race, and must pass — and the OK
        # line must PUBLISH how many branches it compared, or a swept-nothing
        # run is byte-identical to a swept-clean one.
        _g["origin_branch_changelogs"] = lambda refs, **k: (
            [("refs/remotes/origin/claude/rival", scan(_mine_txt)[0])], False)
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _rc2 = main()
        _out2 = _buf.getvalue()
        assert _rc2 == 0, _out2[:400]
        assert "1 open origin branch(es) compared" in _out2, _out2[:400]
        # THE `skip_if_same` HALF, and it is the reason the arm asks for a
        # baseline of its own. `_baseline_changelog()` returns None when HEAD
        # already EQUALS origin/main — correct for the cross-branch arm, which
        # has nothing to compare — but the OPEN-BRANCH question is about the
        # WORKING TREE, so a session that has just pushed still has to be told
        # its next letter is spoken for. Driven by making the default call
        # return None and only the explicit one return the base: if main()
        # ever drops `skip_if_same=False` this goes green-to-red.
        _g["_baseline_changelog"] = (
            lambda skip_if_same=True, **k: None if skip_if_same else _base_txt)
        _g["origin_branch_changelogs"] = lambda refs, **k: (_their, False)
        _buf = io.StringIO()
        with contextlib.redirect_stdout(_buf):
            _rc3 = main()
        assert _rc3 == 1, (
            "the open-branch arm went quiet when HEAD == origin/main — a "
            "session that just pushed is exactly when the next letter matters")
        assert "OPEN-BRANCH CHANGELOG LETTER COLLISION" in _buf.getvalue()
    finally:
        _g.update(_saved)
        with contextlib.suppress(Exception):
            os.unlink(_tmp)

    # ---- `_baseline_changelog` ITSELF honours the flag (mut19's target) ----
    _saved_git = globals()["_git"]
    try:
        globals()["_git"] = lambda *a, **k: (
            "SAME" if a[:1] == ("show",) else "SAME")
        # base == mine: skipped by default, RETURNED when asked explicitly
        assert _baseline_changelog() is None
        assert _baseline_changelog(skip_if_same=False) == "SAME"
    finally:
        globals()["_git"] = _saved_git

    # ---- THE PREVENTIVE HALF: `next_letter` must honour extra_claimed ----
    # This is what `--next` uses to step past a letter an OPEN BRANCH holds,
    # and it is the half that stops the renumber rather than reporting it.
    _nl_txt = "## 2026-08-01 (aa) — one\n\nbody\n"
    assert next_letter(_nl_txt) == "ab", next_letter(_nl_txt)
    assert next_letter(_nl_txt, extra_claimed={"ab"}) == "ac"
    assert next_letter(_nl_txt, extra_claimed={"ab", "ac"}) == "ad"

    print(f"audit_changelog_letters selftest OK (fires on a duplicate; ignores "
          f"the pre-{ERA_START} restart era and letterless headers; skips "
          f"sibling worktrees; sees open origin branches; sees {len(real)} "
          f"real entries)")
    return 0


if __name__ == "__main__":
    if "--next" in sys.argv:
        # [(pd)] THE ONE PLACE THAT PICKS A LETTER, so no session has to write
        # an enumerator again. Counts headers AND citations across tracked
        # files; degrades to headers-only if git is unavailable.
        # [2026-09-10 (zw)] It now also counts every letter held by origin/main
        # and by an OPEN origin branch, and it does so by handing them to
        # `next_letter` rather than re-deriving the pick here — see that
        # function for why the inline copy was removed.
        import subprocess
        _txt = open(CHANGELOG, encoding="utf-8").read()
        try:
            _files = subprocess.run(
                ["git", "ls-files", "*.py", "*.md", "*.yml"],
                capture_output=True, text=True, timeout=30).stdout.split()
        except Exception:                    # noqa: BLE001 — degrade, never block
            _files = []
        # [2026-09-10] THE PREVENTIVE HALF, and it is the half that stops
        # the renumber rather than reporting it. MEASURED against the 10-Sep
        # incident: from a tip of `zs` this printed a letter
        # `origin/claude/audit-9sep` was already using, and with open branches
        # counted it steps past it instead — the eighth collision of that day
        # does not happen. Letters an abandoned branch burns cost nothing: the
        # sequence is bijective base-26 and unbounded, and 9 were held this
        # way on the day this shipped.
        _branches, _ = origin_branch_changelogs(origin_branch_refs()[0])
        _extra = set(origin_claimed_letters(_branches))
        _base = _baseline_changelog(skip_if_same=False)
        if _base:
            _extra |= {l for _d, l, _t in scan(_base)[0]}
        print(next_letter(_txt, _files, extra_claimed=_extra))
        sys.exit(0)
    sys.exit(_selftest() if "--selftest" in sys.argv else main())
