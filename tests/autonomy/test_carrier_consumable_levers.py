"""[(zj)] 🙏 AVO'S JUDGE LANE WAS STRUCTURALLY INERT, AND THE ROW ADVERTISED
FOUR LEVERS TO FIX IT — THREE OF WHICH HER CARRIER CANNOT HOLD.

The carried row `avo-judge-lane-declared-but-not-lever-capable` named this on
6-Sep and it was still true today, on the fleet's second real-money book:

  * `apply_book_levers` guarded `RSI_MAX and MAX_HOLD_MIN` and returned at the
    first miss. `SwingDip` has `RSI_MAX = 42.0` and **no** `MAX_HOLD_MIN`, so
    her arm consumed NOTHING however many levers were registered — the
    registered-but-inert shape I18 exists to prevent, one namespace over from
    `(ye)`;
  * `lever_surface` derived its names from `MUM_LEVER_ATTRS` with no reference
    to the carrier at all, so her row published `unregistered: [rsi_max,
    max_hold_min, vel_lo, vel_hi]` — an instruction to register four names,
    three of which `SwingDip` can never hold and none of which the applier
    would have set. A detector must name an object the operator can act on
    (I8), and this named three that do not exist.

The two were independent readings of mum's attribute list, which is why they
could disagree with the carrier in the same direction and never with each
other. `consumable_lever_attrs` is now the ONE owner both read.

WHAT THE OLD GUARD WAS ACTUALLY PROTECTING, preserved deliberately:
`mum_env_defaults` falls back to mum's own numbers for an attribute a carrier
lacks, so writing a missing attr would INVENT a knob — a 1440-minute hold on a
book with no time stop. Skipping the attribute is the correct half of that
guard; refusing the whole carrier was not.

MEASURED before shipping, on every living carrier: **zero value changes.** mum
keeps all four, avo resolves `xp.avo.rsi_max` to its own unregistered default
(42.0 — the value she already ran), and no book gains a knob.
"""
import ast
import pathlib

import pytest

pytestmark = pytest.mark.autonomy

import fleet_bus as fb                 # noqa: E402
import lighter_family_bot as fam       # noqa: E402

MUM = next(x for x in fam.STRATEGIES if x.bot == "freqtrade-mum")
AVO = next(x for x in fam.STRATEGIES if x.bot == "freqtrade-avo-maria")


# ------------------------------------------------------------- ONE OWNER

def test_the_applier_and_the_surface_read_the_same_owner():
    """THE CLASS-CLOSER. Two independent derivations are how the row could
    advertise a lever the applier would not consume; asserted on the AST so a
    later edit cannot quietly reintroduce a second reading."""
    src = pathlib.Path(fam.__file__).read_text()
    mod = ast.parse(src)
    for fn_name in ("apply_book_levers", "lever_surface"):
        fn = next(n for n in ast.walk(mod)
                  if isinstance(n, ast.FunctionDef) and n.name == fn_name)
        calls = {n.func.id for n in ast.walk(fn)
                 if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)}
        assert "consumable_lever_attrs" in calls, (
            f"{fn_name} no longer reads the shared owner — it is deriving the "
            f"carrier's lever set for itself again")


def test_the_owner_reads_the_class_never_the_mutated_instance():
    """`apply_book_levers` setattr's the INSTANCE, so an instance-keyed read
    would report a knob as consumable only after something had written it."""
    class Bare:
        RSI_MAX = 42.0

    b = Bare()
    assert [x[0] for x in fam.consumable_lever_attrs(b)] == ["rsi_max"]
    b.MAX_HOLD_MIN = 999          # written onto the instance only
    assert [x[0] for x in fam.consumable_lever_attrs(b)] == ["rsi_max"], (
        "the owner is reading the instance — a knob the carrier does not "
        "define would become consumable the moment anything set it")


# ------------------------------------------------- THE CARRIER IS THE TRUTH

def test_a_partial_carrier_consumes_what_it_has_instead_of_nothing():
    """The defect itself: RSI_MAX present, MAX_HOLD_MIN absent."""
    assert [x[0] for x in fam.consumable_lever_attrs(AVO)] == ["rsi_max"]
    assert hasattr(type(AVO), "RSI_MAX")
    assert not hasattr(type(AVO), "MAX_HOLD_MIN")
    assert fam.consumable_lever_attrs(MUM) == fam.MUM_LEVER_ATTRS


def test_a_missing_attribute_is_never_invented():
    """What the old all-or-nothing guard was really for. `mum_env_defaults`
    falls back to mum's numbers, so touching a missing attr would give a book
    with no time stop a 1440-minute one."""
    class Bare:
        RSI_MAX = 42.0

    b = Bare()
    fam.apply_book_levers(b, "xp.avo.")
    assert not hasattr(b, "MAX_HOLD_MIN"), (
        "a knob the carrier does not define was written onto it")
    assert not hasattr(b, "VEL_LO") and not hasattr(b, "VEL_HI")
    assert b.RSI_MAX == 42.0


def test_a_carrier_with_no_consumable_attrs_is_still_a_no_op():
    class Nothing:
        pass

    n = Nothing()
    assert fam.consumable_lever_attrs(n) == ()
    assert fam.apply_book_levers(n, "xp.avo.") == {}


# --------------------------------------------- NO REAL-MONEY VALUE MOVES

@pytest.mark.parametrize("strategy,prefix", [(MUM, "xp.mum."), (AVO, "xp.avo.")])
def test_no_living_carrier_changes_value_under_the_shipped_registry(strategy,
                                                                    prefix):
    """The expectancy price is ZERO and this is what says so: against the
    registry as shipped, every carrier ends the call running exactly the
    value it started with. A lever that is registered LATER moves it — that
    is the point — but merely becoming capable must move nothing."""
    attrs = fam.consumable_lever_attrs(strategy)
    before = {a: getattr(strategy, a) for _b, a, _c in attrs}
    fam.apply_book_levers(strategy, prefix)
    after = {a: getattr(strategy, a) for _b, a, _c in attrs}
    assert before == after, f"{strategy.bot} changed: {before} -> {after}"


# ----------------------------------------------------- THE HONEST SURFACE

def test_the_surface_advertises_only_what_the_carrier_can_hold():
    out = fam.lever_surface(AVO, "xp.avo.")
    assert out["consumable"] == ["rsi_max"]
    assert out["unregistered"] == ["xp.avo.rsi_max"], (
        "the row is still advertising names SwingDip cannot hold")
    assert out["registered_n"] == 0


def test_mums_surface_is_unchanged_and_clean():
    out = fam.lever_surface(MUM, "xp.mum.")
    assert out["registered_n"] == len(fam.MUM_LEVER_ATTRS)
    assert "unregistered" not in out
    assert out["consumable"] == [b for b, _a, _c in fam.MUM_LEVER_ATTRS]


def test_the_declared_lane_is_now_mechanically_capable():
    """The carried row's actual subject: avo's pair DECLARES `xp.avo.` and her
    arm could not consume it. The prefix still resolves and the applier now
    reaches her one real knob — so registering it is a one-line act whenever a
    cage has a measured basis, rather than a rewrite."""
    assert fb.JUDGED_PAIRS["avo"]["xp_prefix"] == "xp.avo."
    arm = fb.JUDGED_PAIRS["avo"]["shadow_bot"]
    assert fam.xp_prefix_for_arm(arm) == "xp.avo."
    assert [x[0] for x in fam.consumable_lever_attrs(AVO)] == ["rsi_max"]


def test_a_book_outside_the_judge_stays_a_no_op_whatever_it_holds():
    """🔮 georgia v3's carrier holds MAX_HOLD_MIN but is nobody's judged arm,
    so it must not pick up a neighbour's namespace."""
    v3 = next((x for x in fam.STRATEGIES if x.bot == "freqtrade-georgia-v3"),
              None)
    if v3 is None:
        pytest.skip("georgia v3 not in the roster")
    assert fam.xp_prefix_for_arm("freqtrade-georgia-v3-lshadow") == ""
    assert fam.lever_surface(v3, "") == {"prefix": ""}
