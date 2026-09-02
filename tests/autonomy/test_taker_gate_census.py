"""[2026-09-03 (xr)] 🎫 THE TAKER'S GATE CENSUS — the half `(uo)` could not see.

`(uo)` built `slot_census` on exactly the right argument: `open 6/6` is
BYTE-IDENTICAL between "six tickets existed" and "twenty existed and fourteen
were refused for want of a slot". It then counted the three SLOT throttles —
and every one of them is reached only AFTER a run of upstream gates that
`continue` silently.

MEASURED on the live payload the day this shipped, and it is the same
ambiguity one loop upstream:

    scout tickets      dip 4 · breakout 12 · momentum 3 · divergence 5  = 24
    slot_census        {"offered": 1, "slots_full": 0, "held_sym": 1}

So the row said *slots are not binding* — true, and useless. **23 of 24
tickets died before the counter and nothing published which gate took them**,
on the book holding the fleet's only CONFIRMED pre-registered winner
(`exit:hold`, fresh n=23 t=2.67) while sitting at 4 of 8 slots. That is the
(lv)/(tx)/(om) shape and I18's corollary: an arm that opens nothing must
publish its OWN census at its OWN bar.

WHAT THESE TESTS PIN:

1. **EVERY refusal is counted — the class, not today's twelve counters.** The
   AST arm walks the real entry loop and requires each `continue`-guard to
   increment a census key inside its own block. This is what fails the day
   someone adds gate fourteen and the hole silently re-opens; a substring or
   key-count test would not (memory: *a substring test is NOT a wiring test*).
   Writing it is what found three gates reading the code had missed — the
   spread gate, the fleet long-budget veto and the notional cap.
2. **The counter sits AT its gate**, so it cannot drift from the rule it
   describes ((hj): a second copy of a rule is a second rule).
3. **It is REPORTED, never a gate.** No entry decision may read the census —
   publish-only, so admission with it is byte-identical to admission without.
4. **It reaches the payload.** A counter nothing publishes is a counter nobody
   can read (the (iz) shape: a declared enforcement that exists and is inert).
"""
import ast
import pathlib

import pytest

import lighter_ticket_taker as taker

SRC = pathlib.Path(taker.__file__).read_text()
TREE = ast.parse(SRC)

CENSUS_NAMES = ("gate_census", "slot_census")


def _entry_loop():
    """The REAL entry loop — located by its own iterator, never by line number."""
    for node in ast.walk(TREE):
        if (isinstance(node, ast.For) and isinstance(node.iter, ast.Call)
                and isinstance(node.iter.func, ast.Name)
                and node.iter.func.id == "incredible"):
            return node
    raise AssertionError(
        "the ticket loop `for lens, t in incredible(...)` is gone — if it was "
        "renamed, re-aim this test at the new iterator; do not delete it")


def _census_writes(stmts):
    """Every `*_census[...] += 1` anywhere inside these statements.

    RECURSES on purpose: `held_sym` and `lens_once` live in a nested `if`, so
    a shallow scan reports them UNCOUNTED and the test would fail on correct
    code — the false-alarm half of a guard nobody then trusts.
    """
    out = []
    for s in stmts:
        for sub in ast.walk(s):
            if (isinstance(sub, ast.AugAssign)
                    and isinstance(sub.target, ast.Subscript)
                    and isinstance(sub.target.value, ast.Name)
                    and sub.target.value.id in CENSUS_NAMES):
                out.append(f"{sub.target.value.id}"
                           f"[{ast.unparse(sub.target.slice)}]")
    return out


def _guards():
    """(line, counters, condition) for every `continue`-guard in the loop."""
    rows = []
    for node in ast.walk(_entry_loop()):
        if isinstance(node, ast.If):
            for blk in (node.body, node.orelse):
                if any(isinstance(s, ast.Continue) for s in blk):
                    rows.append((node.lineno, _census_writes(blk),
                                 ast.unparse(node.test)))
    return rows


# ---------------------------------------------------------------------------
# 1 · THE CLASS CLOSER — a new gate cannot arrive uncounted
# ---------------------------------------------------------------------------
def test_every_refusal_in_the_entry_loop_increments_a_census():
    guards = _guards()
    assert len(guards) >= 13, (
        f"only {len(guards)} continue-guards found in the entry loop — this "
        "test located the wrong loop, and a census test that inspects nothing "
        "reports clean (the `audit_boot_stagger` lesson)")
    uncounted = [(ln, cond[:80]) for ln, c, cond in guards if not c]
    assert not uncounted, (
        "these entry-loop refusals increment NO census counter, so the supply "
        "they turn away is invisible exactly as the 23 tickets were:\n  "
        + "\n  ".join(f"L{ln}: if {cond}" for ln, cond in uncounted)
        + "\n\nAdd a `gate_census[...] += 1` INSIDE the guard's own block "
          "(at the gate, never in a copy of it) and a key in the initialiser.")


def test_the_guard_would_notice_an_uncounted_gate():
    """The positive control (I3): the detector must be able to say NO.

    `test_...increments_a_census` passing is only evidence if an uncounted
    guard would actually redden it — an empty result is not a negative result
    until the check has been seen to produce a positive one.
    """
    fake = ast.parse("for lens, t in incredible(x):\n"
                     "    if lens not in allowed:\n"
                     "        continue\n")
    loop = fake.body[0]
    rows = [(n.lineno, _census_writes(n.body))
            for n in ast.walk(loop)
            if isinstance(n, ast.If) and any(isinstance(s, ast.Continue)
                                             for s in n.body)]
    assert rows and not rows[0][1], (
        "the detector credited a guard that increments nothing — it cannot "
        "distinguish counted from uncounted, so its green run means nothing")


# ---------------------------------------------------------------------------
# 2 · THE COUNTER SITS AT ITS GATE, AND EVERY KEY IS DECLARED
# ---------------------------------------------------------------------------
def test_every_counter_written_is_declared_in_the_initialiser():
    """A `+=` on a key the dict never declared raises KeyError inside the
    trading loop — the (gu) `_ENV_DEFAULTS` trap, where the lookup that fails
    is swallowed by the loop's own except and the lever looks consumed."""
    declared = set()
    for node in ast.walk(TREE):
        if (isinstance(node, ast.Assign) and len(node.targets) == 1
                and isinstance(node.targets[0], ast.Name)
                and node.targets[0].id == "gate_census"
                and isinstance(node.value, ast.Dict)):
            declared = {k.value for k in node.value.keys}
    assert declared, "gate_census is not initialised as a literal dict"
    # EVERY write in the loop, not only the ones inside a continue-guard.
    # `tickets_in` is incremented at the TOP of the loop body — outside any
    # guard — and a guards-only scan silently omitted it, so the first version
    # of this test stayed GREEN while a mutation deleted that key from the
    # initialiser. Caught by mutation round 2; the narrow scan was the defect.
    written = set(_census_writes(_entry_loop().body))
    written = {c[len("gate_census["):-1].strip("'\"")
               for c in written if c.startswith("gate_census[")}
    assert "tickets_in" in written, (
        "the loop no longer counts `tickets_in` — every other counter is read "
        "against it as the denominator, so losing it makes the census "
        "uninterpretable")
    missing = written - declared
    assert not missing, (
        f"written but never declared, so the first hit is a KeyError: {missing}")


# ---------------------------------------------------------------------------
# 3 · REPORTED, NEVER A GATE
# ---------------------------------------------------------------------------
def test_no_entry_decision_reads_the_census():
    """Publish-only. If a condition ever READS `gate_census`, the census has
    become an actuator and this change stopped being free."""
    offenders = []
    for node in ast.walk(_entry_loop()):
        if isinstance(node, (ast.If, ast.While)):
            for sub in ast.walk(node.test):
                if (isinstance(sub, ast.Name) and sub.id == "gate_census"):
                    offenders.append(node.lineno)
    assert not offenders, (
        f"gate_census is read by an entry condition at line(s) {offenders} — "
        "it is REPORTED, never a gate (I15's demote-don't-delete rule)")


# ---------------------------------------------------------------------------
# 4 · IT REACHES THE PAYLOAD
# ---------------------------------------------------------------------------
def test_the_census_is_published_beside_the_slot_census():
    """A counter nothing publishes is inert — the (iz) shape, where a declared
    enforcement existed and graded nothing for days."""
    published = set()
    for node in ast.walk(TREE):
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if (isinstance(k, ast.Constant) and isinstance(v, ast.Name)
                        and v.id in CENSUS_NAMES):
                    published.add(k.value)
    assert "gate_census" in published, (
        "gate_census is counted and never published — nobody can read it")
    assert "slot_census" in published, (
        "slot_census stopped being published; (uo)'s half must survive this one")


@pytest.mark.parametrize("key", [
    "tickets_in", "lens_vetoed", "long_budget", "spread_blocked",
    "notional_cap", "bull_blocked",
])
def test_the_gates_that_actually_bind_are_named(key):
    """`tickets_in` is the denominator every other counter is read against;
    the rest are the gates measured refusing real supply on this book. Losing
    one of these silently returns the row to `{offered: 1}` — informative
    about slots, silent about the 23."""
    assert f'"{key}"' in SRC or f"'{key}'" in SRC, (
        f"gate_census lost its `{key}` counter")
