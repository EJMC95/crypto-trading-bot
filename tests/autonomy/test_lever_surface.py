"""[(yg) 2026-09-06] THE LEVER SURFACE — the observability half of the (ye) fix.

(ye) made 👩 mum's shadow arm ask for the judge's levers under the REGISTERED
namespace (`fleet_bus.xp_prefix_for` / `xp_prefix_for_arm`) instead of a
string rebuilt from the suffixed row id. That closes the instance and pins
the class on the AST (its own tests). What it does not do is make the NEXT
unregistered name visible: `apply_book_levers` is fail-OPEN and `get_lever`
returns the caller's default for a name nothing holds, so an arm asking for
the wrong name looks exactly like an arm the judge never touched — which is
how the defect ran 36h on 4-Sep and 38h again on 6-Sep.

`lever_surface` publishes the resolution on the row (`extra.levers`), so a
namespace the registry does not hold is a row-visible defect. These pins are
for that half only; the prefix itself is pinned by
tests/autonomy/test_judge_lever_prefix_reaches_the_arm.py.
"""
import inspect
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)

import fleet_bus                      # noqa: E402
import lighter_family_bot as fam      # noqa: E402


def test_surface_reports_registered_names_and_flags_unregistered():
    clean = fam.lever_surface("xp.mum.")
    assert clean["prefix"] == "xp.mum." and clean["registry"] is True
    assert clean["registered_n"] == len(fam.MUM_LEVER_ATTRS)
    assert "unregistered" not in clean, clean
    # the exact string the bug produced — must read as a DEFECT, not as clean
    bad = fam.lever_surface("xp.mum-lshadow.")
    assert bad["registry"] is True and bad["registered_n"] == 0
    assert set(bad["unregistered"]) == {
        "xp.mum-lshadow." + bar for bar, _a, _c in fam.MUM_LEVER_ATTRS}


def test_unregistered_key_is_absent_when_clean_never_an_empty_list():
    """An empty list is something a reader learns to skim past; absence is
    the only clean value, so the key's presence alone means 'bug'."""
    assert "unregistered" not in fam.lever_surface("xp.mum.")
    assert fam.lever_surface("xp.mum-lshadow.")["unregistered"]


def test_no_prefix_is_a_first_class_answer():
    """`xp_prefix_for_arm` returns "" for a row that is nobody's shadow arm
    or an image without fleet_bus; the surface must publish that as-is."""
    assert fam.lever_surface("") == {"prefix": ""}
    assert fam.lever_surface(None) == {"prefix": None}


def test_the_surface_is_fed_by_the_owner_not_a_second_resolution():
    """(hj): one owner of the prefix. The publish site must hand
    `lever_surface` the result of `xp_prefix_for_arm(b.bot_id)` — the same
    call the lever apply uses — never its own string."""
    src = inspect.getsource(fam.family_publish_extra)
    assert '"levers": lever_surface(xp_prefix_for_arm(b.bot_id))' in src, src


def test_the_surface_reads_true_for_mums_shadow_arm():
    """End to end through the owners: mum's shadow row resolves the declared
    prefix and every one of her registered knobs is found under it."""
    shadow = fleet_bus.JUDGED_PAIRS["mum"]["shadow_bot"]
    out = fam.lever_surface(fam.xp_prefix_for_arm(shadow))
    assert out["prefix"] == "xp.mum."
    assert out["registry"] is True
    assert out["registered_n"] == len(fam.MUM_LEVER_ATTRS)
    assert "unregistered" not in out


def test_apply_book_levers_runs_env_defaults_on_no_prefix():
    """"" and None both mean 'operator defaults' — never a KeyError, never a
    guessed namespace — the fail-open the whole surface rests on."""
    class S:
        RSI_MAX = 38.0
        MAX_HOLD_MIN = 1440.0
        VEL_LO = -999.0
        VEL_HI = 999.0
    for pfx in ("", None):
        s = S()
        assert fam.apply_book_levers(s, pfx) == {}
        assert s.RSI_MAX == float(fam.mum_env_defaults(S())["rsi_max"])
