"""[2026-08-02] EVERY CONSUMER OF THE LENS VETO MUST SUPPLY THE LENS'S OWN RECORD.

THE CLASS, which took three entries to close and is why this guard exists:

  * `(ij)` found that `brain-lens-forward` grades the SCOUT's tickets on 4h
    forward marks while the taker holds a BRACKET, so the proxy can INVERT the
    verdict — killing the winner and keeping the loser. It made the lens's own
    realised closes SENIOR, and fixed the TAKER.
  * `(im)` found the SCOUT TUNER asking the same authority the same question
    with half the evidence: it delegated correctly — no second copy — but
    passed neither `sides` nor `realised`. Measured live, the two disagreed:
    tuner `{dip, divergence, momentum}` vs taker `{dip, momentum}`, so the one
    lens the LIVE book trades was the one lens the growth rail would never
    widen.
  * Then the STRATEGY INCUBATOR turned out to be a third consumer doing exactly
    the same thing — the one CLAUDE.md had explicitly predicted when the rule
    was centralised ("a third was about to appear in strategy_incubator").

**Delegation is not enough. A single authority asked with partial evidence is a
second rule wearing the first one's name** — the `(hj)` lesson one layer in.
`audit_recurrence` had by then flagged `lighter-ticket-taker` at 6 entries in
7 days, which is the square-one detector doing its job: the instances were
being fixed and the CLASS was not closing.

WHAT THIS GUARD ASSERTS: every call to `vetoed_lenses` outside the module that
DEFINES it passes a `realised=` keyword. It inspects the CALL NODE, never the
source text — an earlier attempt matched the callee's own `realised=None`
PARAMETER and stayed green with the argument deleted at the call site.

It does NOT assert a verdict. A caller may legitimately pass `{}` (fail-safe
open, the documented degrade), and the taker's own entry loop may pass `sides`
as well. The invariant is only that the evidence is OFFERED, because the
failure mode is silence: nobody notices a consumer that never asked.
"""
import ast
import pathlib

REPO = pathlib.Path(__file__).resolve().parents[2]

#: The module that DEFINES the rule. Its internal calls are the definition
#: site's own business (its selftest calls it dozens of ways on purpose).
OWNER = "lighter_ticket_taker.py"

#: Consumers that must supply the evidence. Adding a consumer without adding it
#: here does not weaken the guard — the scan below finds callers by AST across
#: the whole tree, so a new file is caught whether or not anyone lists it.
KNOWN_CONSUMERS = {"lighter_scout_tuner.py", "strategy_incubator.py"}


def _is_selftest(name):
    return "selftest" in name.lower() or name.startswith("test_")


def _calls(path):
    """Every PRODUCTION `vetoed_lenses(...)` Call node in a file.

    SELFTEST BODIES ARE EXCLUDED, and that exclusion is load-bearing rather
    than convenient: those call sites deliberately exercise the proxy-only
    path. `bot_learn`'s selftest asserts "the taker vetoes on the pooled grade
    WITHOUT `sides`" — a contract test whose whole point is to omit the
    argument — and the tuner's does the same for `realised`. Demanding the
    evidence there would forbid testing the degrade path this guard's own
    fail-safe contract depends on.
    """
    tree = ast.parse(path.read_text())
    skip = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and _is_selftest(node.name):
            for inner in ast.walk(node):
                skip.add(id(inner))
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or id(node) in skip:
            continue
        fn = node.func
        name = getattr(fn, "attr", None) or getattr(fn, "id", None)
        if name == "vetoed_lenses":
            yield node


def _consumer_files():
    for p in sorted(REPO.glob("*.py")):
        if p.name == OWNER:
            continue
        try:
            if any(_calls(p)):
                yield p
        except SyntaxError:                     # pragma: no cover
            continue


def test_the_known_consumers_are_still_the_consumers():
    """If this list drifts, the docstring above stops describing the fleet."""
    found = {p.name for p in _consumer_files()}
    assert found == KNOWN_CONSUMERS, (
        f"lens-veto consumers changed: {found} vs {KNOWN_CONSUMERS}. "
        "Add the new one here and make sure it passes realised=.")


def test_every_consumer_offers_the_lenss_own_record():
    """The class `(ij)`/`(im)` kept re-opening, closed executably.

    Checks the CALL NODE's keywords. A source-text scan is not a structural
    claim — it matches the callee's own parameter name and cannot fail.
    """
    missing = []
    for path in _consumer_files():
        for node in _calls(path):
            if not any(k.arg == "realised" for k in node.keywords):
                missing.append(f"{path.name}:{node.lineno}")
    assert not missing, (
        "these consumers judge a lens on the 4h forward proxy alone, with the "
        "lens's own closes invisible — the exact inversion (ij) measured: "
        + ", ".join(missing))


def test_the_owner_still_accepts_the_evidence():
    """The guard is meaningless if the parameter it demands stops existing."""
    import inspect

    import lighter_ticket_taker as tt
    params = inspect.signature(tt.vetoed_lenses).parameters
    assert "realised" in params, "the authority must accept the record"
    assert params["realised"].default is None, (
        "fail-safe open: the default must reproduce forward-proxy-only "
        "behaviour, never 'veto nothing'")
