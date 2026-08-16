#!/usr/bin/env python3
"""
[2026-08-16 (oy)] 💰 THE ALLOCATION PAYLOAD PUBLISHED WHAT THE RANKING WANTED
AND NOT WHAT ANY CONSUMER WOULD DO.

`target_usd` is a PRE-GATE number. The gate that decides whether it is honoured
— `(lx)`'s era rule — lives in `fleet_bus`, so a reader of the allocation
payload alone could not tell that 🌾 carry's **$10,072 target yields a scale of
1.00**. On 16-Aug a reader did exactly that: filed it as a growth item and
reported that the fleet's largest capital move was riding a contaminated
sample, when the era gate had been capping it at flat since 13-Aug. The number
was always derivable and never published. That is the defect.

This is the `(lv)`/I18 rule applied to an ADVISORY organ: a payload must not be
byte-identical between "this book will be scaled up 4x" and "this book will be
left at flat". `{open: 0}` was the trading version; `target_usd: 10072` with no
outcome beside it is the allocation version.

WHAT IS PINNED HERE:
  * the gated outcome is published (`scale_effective`) and the bit is named
    (`expansion_gated`);
  * the arithmetic has ONE owner — `fleet_bus.allocation_scale_for` — so the
    organ cannot drift from the consumer ((hj));
  * the published field does NOT overstate its reach: it is what the ROW
    yields, never what every consumer uses, because `FLEET_ALLOCATION_MODE`
    is per-service and no payload can know it.
"""
from __future__ import annotations

import ast
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import fleet_allocation as fa            # noqa: E402
import fleet_bus as fb                   # noqa: E402


def _row(target, base=1000.0):
    return {"target_usd": float(target), "current_usd": float(base)}


# ------------------------------------------------------- the published outcome
def test_the_live_carry_shape_publishes_flat_not_the_target():
    """THE INCIDENT. target $10,072 on a null era claim must publish 1.00.

    MUTATION: drop the era gate from allocation_scale_for -> RED (4.0).
    """
    r = _row(10072)
    fa.set_era_twin(r, 10, None)          # exactly what the organ published
    assert r["claim_era"] is None
    assert r["scale_effective"] == 1.0, (
        f"a $10,072 target with no era claim published "
        f"{r['scale_effective']!r}; the era gate caps it at flat")
    assert r["expansion_gated"] is True


def test_a_positive_era_claim_releases_the_expansion():
    r = _row(10072)
    fa.set_era_twin(r, 40, 0.5)
    assert r["scale_effective"] == 4.0, "clamped ceiling, gate satisfied"
    assert r["expansion_gated"] is False


def test_a_reduction_is_never_reported_as_gated():
    """`expansion_gated` must mean 'the era declined an expansion', never
    'there was no expansion to decline'. ⚖️ Counterweight sits at the probe
    floor with claim_era 0.0 — a reduction, not a refusal."""
    r = _row(250)
    fa.set_era_twin(r, 40, 0.0)
    assert r["scale_effective"] == 0.25
    assert r["expansion_gated"] is False, (
        "a book being scaled DOWN was reported as having an expansion "
        "declined; that conflates 'refused' with 'never asked'")


def test_flat_is_not_gated():
    r = _row(1000)
    fa.set_era_twin(r, 40, None)
    assert r["scale_effective"] == 1.0
    assert r["expansion_gated"] is False


def test_an_unusable_row_publishes_None_not_a_number():
    """Fail-safe: a junk target must not become a confident scale."""
    for bad in ("x", None, float("nan"), -5.0):
        r = {"target_usd": bad, "current_usd": 1000.0}
        fa.set_era_twin(r, 40, 0.5)
        assert r["scale_effective"] is None, f"target {bad!r} -> a number"
        assert r["expansion_gated"] is False


# ------------------------------------------------------------- one owner only
def test_the_organ_imports_the_rule_and_does_not_recompute_it():
    """A second copy of the rule is a second rule ((hj)). The organ must call
    `fleet_bus.allocation_scale_for`, and must not carry its own clamp
    literals — a drifted ceiling would publish a number the consumer never
    honours, which is this defect wearing new clothes.

    MUTATION: inline the arithmetic in fleet_allocation -> RED.
    """
    src = (ROOT / "fleet_allocation.py").read_text()
    tree = ast.parse(src)
    imported = set()
    for n in ast.walk(tree):
        if isinstance(n, ast.ImportFrom) and n.module == "fleet_bus":
            imported |= {a.name for a in n.names}
    assert "allocation_scale_for" in imported, (
        "fleet_allocation must import the consumer's own scale rule")
    called = {n.func.id for n in ast.walk(tree)
              if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
    assert "allocation_scale_for" in called, "imported but never called"
    # the clamp bounds belong to fleet_bus alone
    for lit in ("0.25", "4.0"):
        assert f"min({lit}" not in src and f"max({lit}" not in src, (
            f"fleet_allocation appears to re-clamp with {lit}; the bounds "
            f"have one owner (fleet_bus.ALLOC_SCALE_{'FLOOR' if lit=='0.25' else 'CEIL'})")


def test_the_consumer_and_the_publisher_agree_by_construction():
    """The published number must BE the consumer's number, for every row the
    organ can emit — checked against `allocation_scale_for` itself rather than
    a hand-written expectation ((hj): test against the publisher's own code).
    """
    for target in (250, 700, 1000, 2015, 10072):
        for era in (None, 0.0, 0.5):
            r = _row(target)
            fa.set_era_twin(r, 40, era)
            assert r["scale_effective"] == (
                round(fb.allocation_scale_for(r, 1000.0), 4)), (
                f"publisher disagrees with consumer at target={target} "
                f"era={era}")


def test_the_field_does_not_overstate_its_reach():
    """`FLEET_ALLOCATION_MODE` is per-service, so no payload can promise what
    a consumer will use. The limit must stay written where the field is."""
    tree = ast.parse((ROOT / "fleet_bus.py").read_text())
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef)
              and n.name == "allocation_scale_for")
    doc = ast.get_docstring(fn) or ""
    # Scoped to THIS function's own docstring on purpose: the phrase appears
    # elsewhere in the module, so a page-wide substring scan passed with the
    # declaration deleted (mutation M6 survived exactly that first draft).
    assert "FLEET_ALLOCATION_MODE" in doc, (
        "allocation_scale_for no longer declares that it is env-blind; a "
        "published scale that silently claims consumer-wide reach is the "
        "overstating-field defect this change exists to remove")
    assert "never" in doc.lower(), (
        "the 'what this row yields, never what every consumer uses' limit "
        "has gone from the docstring that owns it")


if __name__ == "__main__":
    for _n, _f in sorted(globals().items()):
        if _n.startswith("test_") and callable(_f):
            _f()
            print(f"  ok {_n}")
    print("test_allocation_scale_published: all passed")
