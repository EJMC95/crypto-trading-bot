"""[(yb)] THE LEVER NAMESPACE, THE VELOCITY GAUGE, AND THE VIRTUAL FLIP.

Eamon, 4-Sep: *"Mum should seize the opportunity to flip her 'virtual' -
trade... her evolving to be able to change a long to a short if the
percentage"* — asked while 👩 mum sat long VIRTUAL at -2.08% and her other
three holdings were green.

Three things came out of answering it, and this file pins all three.

1 · THE JUDGE'S MUM LANE HAD NEVER APPLIED AN EXPERIMENT. The family host
    built its lever prefix by stripping the FIRST id segment —
    `freqtrade-mum-lshadow` -> `xp.mum-lshadow.` — while the judge writes
    `xp.mum.`, the name `JUDGED_PAIRS` has declared all along.
    `fleet_tuning.get_lever` returns the CALLER'S DEFAULT for an unregistered
    name, so the arm ran the env default, correctly and silently. Measured on
    the live bus: `xp.mum.rsi_max = 32.0` open for 36h while every close
    stamped `bars.rsi_max = 38.0`, judge holding on `arm_skew`. The fleet's
    only shadow->real-money path was inert. Same family as the
    `era_epoch_for` double-rsplit ((hd)/(hg)): an id is not a namespace.

    The instance fix is one line; the CLASS closes here — every declared
    pair's prefix must resolve to REGISTERED levers, so a new book cannot
    ship with a namespace nothing holds.

2 · THE REAL-MONEY ARM COULD NOT SEE THE DIP VELOCITY IT TRADES ON. `(xl)`
    measured that mum's information is in the SHAPE of the fall (12-20 rsi
    points over 4 bars: +0.309%/trade, t +2.82; a violent 20+ collapse:
    -0.091%, t -0.66). `signals()` returns `vel` on EVERY scan. The $1,000
    shadow published it; the row holding real money threw it away — I23 at
    the arm that steers, and the same shape (ya) had just found in avo's BB
    term one wave earlier.

3 · THE NAIVE FLIP LOSES, SO THE FLEET MEASURES IT INSTEAD OF TRADING IT. On
    her own 152 closes the 12 stop-outs are followed by the coin rising
    +0.881% within a median 2.32h — the stop fires at maximum oversold, which
    is the bottom. So the book records the short it did NOT take and marks it
    forward against a matched-window random-coin short ((hm) in mirror form),
    at zero capital. `sides` stays ["long"], so `POLICY_SIG_FIELDS` is
    untouched and her go-live era does not reset — which matters, because she
    is 72 closes in at `days_to_gate_obs 19.8` and a real short side would
    restart that clock at zero.
"""
import ast
import inspect

import fleet_bus
import fleet_tuning
import lighter_family_bot as fam
import lighter_avo_live_bot as live
import experiment_judge as judge


# --------------------------------------------------------------------------
# 1 · the lever namespace
# --------------------------------------------------------------------------
def test_every_judged_pair_resolves_to_registered_levers():
    """THE CLASS-CLOSER. For every declared pair, the prefix a host resolves
    must name levers the registry actually holds. This is what makes the
    36h stall unrepeatable: a namespace nothing holds fails the build."""
    checked = 0
    for pid, spec in fleet_bus.JUDGED_PAIRS.items():
        for arm in ("live_bot", "shadow_bot"):
            bot = spec.get(arm)
            if not bot:
                continue
            prefix = fleet_bus.xp_prefix_for(bot)
            assert prefix, f"{pid}/{arm} ({bot}) resolves NO xp prefix"
            assert prefix == spec.get("xp_prefix"), \
                f"{pid}/{arm} resolved {prefix!r} != declared {spec['xp_prefix']!r}"
            checked += 1
    assert checked >= 4, f"only {checked} arms checked — the sweep went blind"


def test_mums_arm_asks_for_the_name_the_judge_writes():
    """The live instance, stated as the two halves that must MEET: whatever
    the judge writes for this lane, the arm must be able to read."""
    shadow = fleet_bus.JUDGED_PAIRS["mum"]["shadow_bot"]
    prefix = fleet_bus.xp_prefix_for(shadow)
    for cand in judge.MUM_CANDIDATES:
        for name in cand["levers"]:
            assert name.startswith(prefix), \
                f"judge writes {name!r}; the arm reads under {prefix!r}"
            assert name in fleet_tuning.LEVERS, f"{name} is not registered"


def test_the_prefix_is_never_built_from_the_bot_id_again():
    """The DEFECT's own shape, on the AST.

    THE FIRST VERSION OF THIS TEST SURVIVED THE MUTATION THAT RESTORES THE
    BUG, and it is worth recording why, because it is this repo's own rule
    walked into by the guard written to enforce it: it inspected the
    ARGUMENT at the `apply_book_levers` call site, and the mutation simply
    moved the f-string one line up into the `b.lever_prefix = ...`
    assignment. The check looked structural and asked the wrong node.

    The claim that actually holds: `lever_prefix` is assigned ONLY from a
    call to `xp_prefix_for`. Any other producer — an f-string, a split, a
    concatenation — is the bug returning, wherever it is written."""
    tree = ast.parse(inspect.getsource(fam))
    producers = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign):
            continue
        for tgt in node.targets:
            if isinstance(tgt, ast.Attribute) and tgt.attr == "lever_prefix":
                producers.append(node.value)
    assert producers, "nothing assigns lever_prefix — the wiring is gone"
    from_owner = 0
    for v in producers:
        if isinstance(v, ast.Constant):
            assert v.value is None, \
                f"lever_prefix seeded with a literal {v.value!r}"
            continue                       # the Book.__init__ default
        assert isinstance(v, ast.Call), \
            f"lever_prefix built from a {type(v).__name__}, not a call"
        nm = getattr(v.func, "id", None) or getattr(v.func, "attr", None)
        assert nm == "xp_prefix_for", \
            f"lever_prefix built by {nm!r} instead of the registry owner"
        from_owner += 1
    assert from_owner == 1, \
        f"expected exactly one registry-owned producer, found {from_owner}"


def test_the_host_resolves_mums_prefix_to_the_registry_value():
    """And the VALUE, driven rather than reasoned about: whatever the host
    computes for mum's shadow arm must be the declared namespace."""
    tree = ast.parse(inspect.getsource(fam))
    keyed = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and (getattr(n.func, "id", None)
                  or getattr(n.func, "attr", None)) == "xp_prefix_for"
             and n.args
             and getattr(n.args[0], "attr", None) == "bot_id"]
    assert keyed, "the resolution no longer keys on the book's own bot id"
    assert fam.xp_prefix_for("freqtrade-mum-lshadow") == "xp.mum."
    assert fam.xp_prefix_for("freqtrade-mum-lighter") == "xp.mum."
    # the defect's own output must never be reachable from the owner
    assert "lshadow" not in (fam.xp_prefix_for("freqtrade-mum-lshadow") or "")


def test_lever_surface_names_an_unregistered_namespace():
    """The OBSERVABILITY half. Two correct fail-opens composed into something
    invisible; this is what makes the composition visible."""
    good = fam.lever_surface("xp.mum.")
    assert good["prefix"] == "xp.mum." and good["registry"] is True
    assert "unregistered" not in good, \
        "a clean surface must not publish an empty defect list to skim past"
    assert good["registered_n"] == len(fam.MUM_LEVER_ATTRS)

    bad = fam.lever_surface("xp.mum-lshadow.")     # the defect, verbatim
    assert bad["registered_n"] == 0
    assert bad["unregistered"] and all(
        n.startswith("xp.mum-lshadow.") for n in bad["unregistered"])

    # a book outside the judge is a first-class answer, NOT a defect
    assert fam.lever_surface(None) == {"prefix": None}
    assert fleet_bus.xp_prefix_for("book-hull-lshadow") is None


# --------------------------------------------------------------------------
# 2 · the velocity gauge
# --------------------------------------------------------------------------
def test_the_velocity_gauge_is_one_owner_on_both_arms():
    """(hj): a second copy of a rule is a second rule — and this one is read
    to price a real-money entry cell.

    Importing the owner is not using it: the first version of this test
    asserted identity only, and a mutation that kept the import while
    re-implementing the gauge inline in `scan_census` sailed through. Both
    halves are checked now — the name IS the owner, and the census CALLS
    it."""
    assert live.vel_census is fam.vel_census
    tree = ast.parse(inspect.getsource(live.scan_census))
    calls = [n for n in ast.walk(tree)
             if isinstance(n, ast.Call)
             and (getattr(n.func, "id", None)
                  or getattr(n.func, "attr", None)) == "vel_census"]
    assert calls, "the live census imports the gauge owner and never calls it"


def test_the_live_arm_captures_the_velocity_it_trades_on():
    """AST, not a substring scan: `last_vel[sym] = ...` must be a real WRITE
    (a Subscript in Store context). (ya)'s mutation survived a page-wide
    scan for exactly this shape."""
    tree = ast.parse(inspect.getsource(live))
    writes = [n for n in ast.walk(tree)
              if isinstance(n, ast.Subscript)
              and isinstance(n.ctx, ast.Store)
              and getattr(n.value, "id", None) == "last_vel"]
    assert writes, "the live arm never WRITES last_vel — the gauge is dead"


def test_the_gauge_never_fabricates_a_reading():
    """ABSENT, never zero: a fabricated `vel_med: 0.0` reads as 'every dip is
    a flat drift', which is a claim, not a silence (the (st) rsi_min trap)."""
    class S:
        VEL_LO, VEL_HI = -999.0, 999.0
    assert fam.vel_census({}, S()) == {}
    assert fam.vel_census(None, S()) == {}
    assert fam.vel_census({"A": None, "B": "junk"}, S()) == {}
    out = fam.vel_census({"A": 5.0, "B": 14.0, "C": 22.0}, S())
    assert out["vel_read"] == 3 and out["vel_band"] == [-999.0, 999.0]
    assert out["vel_in_band"] == 3


def test_the_band_is_read_off_the_carrier_not_retyped():
    class S:
        VEL_LO, VEL_HI = 12.0, 20.0
    out = fam.vel_census({"A": 5.0, "B": 14.0, "C": 22.0}, S())
    assert out["vel_band"] == [12.0, 20.0]
    assert out["vel_in_band"] == 1, "only the 14.0 reading sits in [12, 20)"


def test_both_arms_stamp_the_velocity_on_the_trade():
    """I23: the quantity the knob cuts, recorded ON the trade — so the band
    can be graded from the LEDGER (I14) and not only by a replay whose own
    author declared a 50x gap to it."""
    for mod in (fam, live):
        src = inspect.getsource(mod)
        assert '"vel_entry"' in src, f"{mod.__name__} never stamps vel_entry"


# --------------------------------------------------------------------------
# 3 · the virtual flip ledger
# --------------------------------------------------------------------------
class _Flip:
    flip_ledger = True


class _Plain:
    pass


def _marks(d):
    return d.get


def test_only_loss_class_exits_open_a_virtual_short():
    s, flips = _Flip(), []
    m = {"A": 100.0, "N": 10.0}
    for reason, want in (("long-oversold-rebound_stop_loss", True),
                         ("long-oversold-rebound_max_hold", True),
                         ("long-oversold-rebound_daily_loss", True),
                         ("long-oversold-rebound_roi", False),
                         ("long_roi", False),
                         ("long-oversold-rebound_delisted", False)):
        got = fam.flip_open(s, flips, "A", 100.0, reason, 0.0, ["N"], _marks(m))
        assert got is want, f"{reason}: opened={got}, expected {want}"


def test_a_short_return_has_the_right_sign():
    """The whole point: a coin that keeps FALLING pays the flip; one that
    bounces costs it. Her stops measured +0.881% of bounce, so this sign is
    the difference between the instrument saying yes and saying no."""
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "N": 10.0}
    fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    m["A"] = 90.0                                   # fell 10% -> short +10%
    fam.flip_settle(s, flips, acc, 7 * 3600, _marks(m))
    assert fam.flip_block(s, acc, flips)["6h"]["mean_pct"] == 10.0

    s2, flips2, acc2 = _Flip(), [], {}
    m2 = {"A": 100.0, "N": 10.0}
    fam.flip_open(s2, flips2, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m2))
    m2["A"] = 110.0                                 # bounced -> short -10%
    fam.flip_settle(s2, flips2, acc2, 7 * 3600, _marks(m2))
    assert fam.flip_block(s2, acc2, flips2)["6h"]["mean_pct"] == -10.0


def test_nothing_settles_before_its_horizon():
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "N": 10.0}
    fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    fam.flip_settle(s, flips, acc, 5.9 * 3600, _marks(m))
    b = fam.flip_block(s, acc, flips)
    assert b["6h"]["n"] == 0 and b["24h"]["n"] == 0 and b["pending"] == 1


def test_both_horizons_are_published_so_a_sign_cannot_be_chosen():
    """Picking one horizon and reporting it is how an (oe)-style artifact
    ships. Both are always present."""
    b = fam.flip_block(_Flip(), {}, [])
    for h in fam.FLIP_HORIZONS_H:
        assert fam.flip_key(h) in b, f"{h} missing from the payload"


def test_a_dark_mark_books_nothing_rather_than_a_flat_return():
    """I8: a 0.0% observation from no data is the loudest possible claim.

    BOTH legs dark AND the traded leg alone. The single-leg case is the one
    that matters and the one the first version of this test missed: with
    everything dark, the ATOMIC pair rule blocks the write and the test
    passed for a reason unrelated to what it claims. A mutation defaulting a
    missing mark to the entry price — booking an exactly-flat flip — survived
    it. Here the null leg is readable, so only the dark-coin rule can save
    it."""
    s, flips, acc = _Flip(), [], {}
    fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"],
                  _marks({"A": 100.0, "N": 10.0}))
    fam.flip_settle(s, flips, acc, 7 * 3600, lambda c: None)
    assert fam.flip_block(s, acc, flips)["6h"]["n"] == 0, "both legs dark"

    s2, flips2, acc2 = _Flip(), [], {}
    fam.flip_open(s2, flips2, "A", 100.0, "x_stop_loss", 0.0, ["N"],
                  _marks({"A": 100.0, "N": 10.0}))
    # the NULL leg prices fine; only the traded coin is dark
    fam.flip_settle(s2, flips2, acc2, 7 * 3600,
                    lambda c: 11.0 if c == "N" else None)
    b = fam.flip_block(s2, acc2, flips2)
    assert b["6h"]["n"] == 0, (
        "a dark coin mark booked an observation — most likely as an exactly "
        "flat 0.0% flip, which is a claim rather than a silence")
    assert b["pending"] == 1, "the record must survive to settle later"


def test_the_pair_settles_atomically():
    """(rp)'s rule: both legs or neither — an unpaired observation cannot be
    differenced against anything."""
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "N": 10.0}
    fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    m.pop("N")                                       # the NULL leg goes dark
    m["A"] = 90.0
    fam.flip_settle(s, flips, acc, 7 * 3600, _marks(m))
    b = fam.flip_block(s, acc, flips)
    assert b["6h"]["n"] == 0, "the real leg settled without its control"


def test_n_equals_null_n_by_construction():
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "B": 50.0, "N": 10.0}
    for c in ("A", "B"):
        fam.flip_open(s, flips, c, m[c], "x_stop_loss", 0.0, ["N"], _marks(m))
    m.update({"A": 90.0, "B": 55.0, "N": 11.0})
    fam.flip_settle(s, flips, acc, 7 * 3600, _marks(m))
    for h in fam.FLIP_HORIZONS_H:
        k = fam.flip_key(h)
        assert acc.get(k, {}).get("n", 0) == acc.get(k, {}).get("null_n", 0)


def test_the_ledger_is_published_at_zero_and_absent_off_carrier():
    """(lv)/I18: an omitted key is byte-identical between 'no loss-class exit
    yet' and 'the instrument is not running'."""
    b = fam.flip_block(_Flip(), {}, [])
    assert b["6h"]["n"] == 0 and b["6h"]["mean_pct"] is None
    assert b["pending"] == 0 and "basis" in b
    assert fam.flip_block(_Plain(), {}, []) == {}, \
        "a non-flip carrier's payload shape moved"


def test_a_non_flip_carrier_records_nothing():
    flips = []
    assert fam.flip_open(_Plain(), flips, "A", 1.0, "x_stop_loss", 0.0,
                         ["N"], _marks({"A": 1.0, "N": 1.0})) is False
    assert flips == []


def test_only_mum_declares_the_flip_ledger():
    carriers = [v for v in vars(fam).values()
                if isinstance(v, type) and getattr(v, "flip_ledger", False)]
    assert [c.__name__ for c in carriers] == ["OversoldRebound"], carriers


def test_the_deferral_cap_counts_rather_than_drops():
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "N": 10.0}
    for _ in range(5):
        fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    m["A"] = 90.0
    fam.flip_settle(s, flips, acc, 7 * 3600, _marks(m), max_settle=2)
    b = fam.flip_block(s, acc, flips)
    assert b["6h"]["n"] == 2 and b["deferred"] == 3 and b["pending"] == 5


def test_the_settled_age_is_published_not_the_nominal_horizon():
    """I1's shape: the age is the fact, the horizon is only the intent."""
    s, flips, acc = _Flip(), [], {}
    m = {"A": 100.0, "N": 10.0}
    fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    m["A"] = 90.0
    fam.flip_settle(s, flips, acc, 9.5 * 3600, _marks(m))
    assert fam.flip_block(s, acc, flips)["6h"]["settled_at_h"] == 9.5


def test_the_pending_list_is_bounded():
    s, flips = _Flip(), []
    m = {"A": 100.0, "N": 10.0}
    for _ in range(fam.FLIP_MAX_PENDING + 50):
        fam.flip_open(s, flips, "A", 100.0, "x_stop_loss", 0.0, ["N"], _marks(m))
    assert len(flips) == fam.FLIP_MAX_PENDING


def test_the_instrument_tolerates_a_book_that_has_never_run_it():
    """[(vr)] THE CONTAINER IS TOLERATED, NEVER ASSUMED — and this was a live
    regression, not a hypothetical: the first cut read `self.flips` straight
    off the Book inside the CLOSE PATH, and a stub Book without the attribute
    raised there. That is the class that killed four family books' publishes
    for five days, and this one sits in a real-money close.

    A telemetry arm that can break a trading loop is worse than no telemetry
    arm — the control arm's own rule, applied to its sibling."""
    s = _Flip()
    assert fam.flip_open(s, None, "A", 100.0, "x_stop_loss", 0.0, ["N"],
                         _marks({"A": 1.0})) is False
    assert fam.flip_open(s, "not-a-list", "A", 100.0, "x_stop_loss", 0.0,
                         ["N"], _marks({"A": 1.0})) is False
    fam.flip_settle(s, None, None, 0.0, _marks({}))          # must not raise
    fam.flip_settle(s, [], "not-a-dict", 0.0, _marks({}))     # must not raise
    assert fam.flip_block(s, None, None)["pending"] == 0


def test_the_flip_ledger_can_never_place_an_order():
    """The safety claim, ASSERTED rather than described: these functions are
    telemetry and must contain no order path. `control_draw` is shared, so
    it is checked with them."""
    banned = {"market_open", "market_close", "place_order", "send_order",
              "create_order", "flatten"}
    for fn in (fam.flip_open, fam.flip_settle, fam.flip_block,
               fam.control_draw):
        tree = ast.parse(inspect.getsource(fn))
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                nm = getattr(node.func, "id", None) or \
                    getattr(node.func, "attr", None)
                assert nm not in banned, f"{fn.__name__} calls {nm}"


def test_the_flip_adds_no_side_so_the_era_does_not_reset():
    """The reason this is an instrument and not a trade. `POLICY_SIG_FIELDS`
    carries `sides`, so a real short would restart her go-live clock; she is
    72 closes in with ~20 days to the gate."""
    import scripts.golive_readiness as gr
    assert "sides" in gr.POLICY_SIG_FIELDS
    inst = fam.OversoldRebound("freqtrade-mum", "1h", -0.04, 4,
                               "oversold-1h")
    assert getattr(inst, "flip_ledger", False) is True, \
        "the carrier under test does not run the instrument"
    stamp = fam.policy_stamp(inst, "lighter_live", "diversified", None)
    assert stamp["sides"] == ["long"], stamp


def test_both_arms_run_the_flip_ledger():
    """(vh)/(pt): a control arm running a different instrument is not a
    control. Both hosts import the SAME owners."""
    assert live.flip_open is fam.flip_open
    assert live.flip_settle is fam.flip_settle
    assert live.flip_block is fam.flip_block
    for mod in (fam, live):
        src = inspect.getsource(mod)
        assert "flip_open(" in src and "flip_settle(" in src \
            and "flip_block(" in src, f"{mod.__name__} is missing a call site"


# --------------------------------------------------------------------------
# 4 · the judge stops holding a lane it never ran
# --------------------------------------------------------------------------
def test_a_never_applied_experiment_is_voided_and_requeued_untried():
    assert judge.VOID_SKEW_H > 0
    src = inspect.getsource(judge.run_once) if hasattr(judge, "run_once") \
        else inspect.getsource(judge)
    assert "VOIDED-NEVER-APPLIED" in src
    # the candidate must NOT be retired: a skew verdict is about the
    # plumbing, never about the idea
    i = src.index("VOIDED-NEVER-APPLIED")
    window = src[i:i + 1600]
    assert "done=done + [cand" not in window, (
        "a voided candidate was added to `done` — that retires it on a "
        "verdict about the plumbing")
    assert "phase=\"idle\"" in window and "current=None" in window


def test_the_void_never_fires_before_its_window():
    """A void inside the window would abandon a recoverable arm mid-fix."""
    src = inspect.getsource(judge)
    i = src.index("_skew_h = ")
    window = src[i:i + 400]
    assert ">= VOID_SKEW_H" in window, \
        "the void must be gated on elapsed hours, not fire on sight"
