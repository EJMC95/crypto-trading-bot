"""A CARD MAY NOT ASSERT A NUMBER NOTHING PUBLISHED (2026-08-03).

MEASURED the day this shipped: the 💸 Funding Farmer's dashboard card read

    "…when |APR|≥40%, vol-vetoed, stop-guarded · clip $20 × cap $80"

while the live real-money process was running **clip $37.50, cap $150, gate 5%
TRUE apr**. All three numbers were hand-typed prose in `pnl_dashboard
.DESCRIPTIONS`, read from nothing, and every one of them was a RUNTIME value:

  * the clip rides the growth rail's `live.clip_scale` lever,
  * the cap is the operator's `*_MAX_NOTIONAL` env,
  * `enter_apr` is a judge-promotable `live.funding.*` lever.

The APR half had been **8x overstated since the 17-Jul basis fix** — the card
was quoting a Hyperliquid-era per-hour annualisation of a per-8h rate. Nobody
caught it for a fortnight because a hardcoded number and a live one RENDER
IDENTICALLY; the operator read the card, believed the config had not landed,
and only the container's own boot line settled it.

So the rule this file enforces: **the mechanism may be prose; the numbers come
from the publisher.** Same family as [[self-describing-labels-lie]] and the
(df) rule that enablement is verified by published output, never by "the var is
set on the service".

The first test is the load-bearing one, and it is the (hj) class — a consumer
reading a key its publisher does not emit, with a green selftest, because the
fixture was written by whoever wrote the consumer. It reads the publisher's
OWN `store.publish(extra=...)` dict by AST and requires the consumer's keys to
be a subset. Rename a key on either side and this goes red.
"""
import ast
import os
import sys

import pytest

_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import pnl_dashboard  # noqa: E402

FARMER = "perps-funding-lighter"
UNIT_KEYS = ("clip_usd", "cap_usd", "max_open", "enter_apr")


def _published_extra_keys(module_filename):
    """Literal string keys of every `extra=` dict passed to a `.publish(...)`
    call in the module. AST, not a substring scan: the (gn) lesson is that a
    page-wide grep is not a structural claim — `"clip_usd"` appears in this
    file's own docstring, and would satisfy a naive search of the bot."""
    src = open(os.path.join(_ROOT, module_filename), encoding="utf-8").read()
    keys = set()
    for node in ast.walk(ast.parse(src)):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        if not (isinstance(fn, ast.Attribute) and fn.attr == "publish"):
            continue
        for kw in node.keywords:
            if kw.arg != "extra" or not isinstance(kw.value, ast.Dict):
                continue
            for k in kw.value.keys:
                if isinstance(k, ast.Constant) and isinstance(k.value, str):
                    keys.add(k.value)
    return keys


def test_farmer_publishes_every_unit_the_card_renders():
    """The publisher emits every key the card reads. This is the contract; if
    it breaks, the card silently renders NOTHING and the old prose bug is back
    in a new costume."""
    published = _published_extra_keys("lighter_funding_bot.py")
    assert published, "no publish(extra={...}) dict found — did the call move?"
    missing = [k for k in UNIT_KEYS if k not in published]
    assert not missing, (
        f"lighter_funding_bot publishes {sorted(published)} but the dashboard's "
        f"live_units reads {missing} — consumer/publisher key drift, the (hj) class")


def test_card_renders_the_published_numbers_not_a_default():
    """Non-degenerate: the (hj) lesson is that every one of those four dead
    consumers returned an empty/None that a value-free test calls 'fine'."""
    row = {"extra": {"clip_usd": 37.5, "cap_usd": 150.0,
                     "max_open": 5, "enter_apr": 0.05}}
    out = pnl_dashboard.desc_for(f"{FARMER}-lighter", row)
    for want in ("clip $37.50", "cap $150", "5 slots", "5.00%"):
        assert want in out, f"card lost {want!r} — rendered: {out!r}"
    # the mechanism survives alongside the units
    assert "RECEIVES funding" in out


def test_absent_units_render_nothing_rather_than_a_plausible_default():
    """A bot that has not shipped the publisher yet must show NO units. A
    confident wrong number is worse than a blank — that is the entire defect
    being closed here, so a default would reintroduce it."""
    assert pnl_dashboard.live_units({"extra": {}}) == ""
    assert pnl_dashboard.live_units({}) == ""
    assert pnl_dashboard.live_units(None) == ""
    # a non-dict extra must not raise on a dashboard render path
    assert pnl_dashboard.live_units({"extra": "junk"}) == ""
    out = pnl_dashboard.desc_for(f"{FARMER}-lighter", {"extra": {}})
    assert "clip" not in out and "$" not in out


def test_a_bool_is_not_a_number():
    """isinstance(True, int) is True, so an unguarded check renders a stray
    flag as 'clip $1.00' — a confident wrong number, the exact failure mode."""
    assert pnl_dashboard.live_units({"extra": {"clip_usd": True}}) == ""


@pytest.mark.parametrize("needle", ["clip $", "cap $", "≥40", "APR≥", "|APR|"])
def test_description_carries_no_hardcoded_units(needle):
    """The prose may describe the MECHANISM and never the numbers. Checked on
    the raw DESCRIPTIONS entry, not the rendered card — the rendered card is
    SUPPOSED to contain 'clip $…' once the payload supplies it, so asserting
    against the render would be a test that fails on the fix working."""
    assert needle not in pnl_dashboard.DESCRIPTIONS[FARMER], (
        f"DESCRIPTIONS[{FARMER!r}] hardcodes {needle!r}; publish it and let "
        "live_units render it")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-q"]))
