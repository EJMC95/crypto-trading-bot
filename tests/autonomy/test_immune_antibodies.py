"""An antibody that matches nothing is a fix that did nothing.

[2026-09-11] 🧲 Snap Back was retired 4-Aug (jh) and its frozen census kept
being re-alerted: `market_context.fire_alerts` reads
`lighter-dislocation-lshadow` with no age check (I1 — content before liveness)
and `_alert`'s dedup refreshes `last_seen` on every hit, so `alert_fossils`'
age arm could never reach those rows. MEASURED on the 10-Sep evidence review:
**19 of 23 verdict rows** were that one dead book repeating one sentence, and
it had read that way every day for five weeks.

`fleet_immune.ANTIBODIES` is the table built for exactly this. But an antibody
is a SUBSTRING, and a substring is a guess until something checks it against
the text it is supposed to match — the "a check that inspects nothing reports
clean" class ((po)) applied to a cure rather than a detector. So this file
pins two things:

  1. the MECHANISM — a known-toxic alert is pruned at any age, and a live
     alert beside it is not;
  2. the AIM — every antibody substring must actually occur in the source of
     a module that publishes alerts. A retired pattern whose wording drifted,
     or one typed with the wrong emoji, fails here instead of silently
     neutralising nothing.

Rule 2 is what makes this more than a snapshot of today's table: it survives
new antibodies and deletes itself cleanly when one is removed.
"""
import os
import re
import sys
import time

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

import fleet_immune as fi  # noqa: E402

#: Modules that build the `msg` strings `alert_fossils` matches against.
#: An antibody must be aimed at one of them.
ALERT_PUBLISHERS = ("market_context.py", "fleet_immune.py", "evidence_board.py")


def _publisher_text():
    out = []
    for name in ALERT_PUBLISHERS:
        p = os.path.join(ROOT, name)
        if os.path.exists(p):
            with open(p, encoding="utf-8") as fh:
                out.append(fh.read())
    return "\n".join(out)


def test_every_antibody_aims_at_a_string_a_publisher_can_actually_emit():
    """The aim check. A cure for a message nobody sends is not a cure.

    Tolerant of f-string interpolation: the substring is checked against the
    source with `{...}` placeholders collapsed, because an antibody
    legitimately matches the literal PREFIX of an f-string.
    """
    src = _publisher_text()
    assert src, f"no alert publisher found among {ALERT_PUBLISHERS}"
    flat = re.sub(r"\{[^{}]*\}", "", src)
    missing = [sub for sub, _ in fi.ANTIBODIES
               if sub not in src and sub not in flat]
    assert not missing, (
        f"these antibodies match no publisher text and therefore neutralise "
        f"nothing: {missing} — check the wording against the format string "
        f"that emits it, or delete the entry")


def test_every_antibody_carries_a_reason():
    """I8: the output is read by an operator, so it must say WHY."""
    for sub, reason in fi.ANTIBODIES:
        assert isinstance(reason, str) and len(reason) > 15, (sub, reason)


def test_a_toxic_alert_is_pruned_at_any_age_and_a_live_one_is_not():
    """The mechanism, driven with the publisher's own message shape.

    The fossils are FRESH by `last_seen` — that is the whole reason the age arm
    could not reach them — so this fixture stamps them seconds old on purpose.
    """
    now = time.time()
    toxic = [
        {"key": "disloc:AVAX", "ts": now - 60, "last_seen": now - 60,
         "msg": "🧲 tradeable dislocation on AVAX: 210bps (census 4 events) "
                "— Snap Back thesis evidence"},
        {"key": "census:50", "ts": now - 60, "last_seen": now - 60,
         "msg": "🧲 dislocation census reached 62 events — worth a review"},
    ]
    live = {"key": "veto:AI", "ts": now - 60, "last_seen": now - 60,
            "msg": "measured slip 33.93bps > 15 (n=5)"}

    keep, pruned = fi.alert_fossils(toxic + [live], now, 24)

    assert [a["key"] for a in keep] == ["veto:AI"], (
        "a live alert must survive beside a pruned fossil — a filter that "
        "takes the whole feed is the disease, not the cure")
    assert len(pruned) == 2
    assert all("antibody" in p["why"] for p in pruned), pruned
    assert all("retired" in p["why"] for p in pruned), (
        "the prune reason must name the object the operator can act on (I8)")


def test_the_age_arm_still_works_independently():
    """A guard that only ever fires on the new entries would hide a regression
    in the arm that was already there."""
    now = time.time()
    old = {"key": "whatever", "ts": now - 200 * 3600,
           "last_seen": now - 200 * 3600, "msg": "some ordinary condition"}
    keep, pruned = fi.alert_fossils([old], now, 24)
    assert keep == [] and "age-stale" in pruned[0]["why"], pruned


@pytest.mark.parametrize("sub", [s for s, _ in fi.ANTIBODIES])
def test_no_antibody_is_broad_enough_to_swallow_an_unrelated_alert(sub):
    """A one- or two-character antibody would prune the whole bloodstream.

    Not a style rule: `alert_fossils` matches by naive substring at ANY age,
    so breadth here is unbounded blast radius.
    """
    assert len(sub) >= 12, (
        f"antibody {sub!r} is short enough to match unrelated alerts — "
        f"aim it at a distinctive part of the publisher's format string")
