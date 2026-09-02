"""🔮 georgia's two arms ran different ENTRY policies, so the judge refused.

[2026-08-28 (vd)] Eamon: *"the oracle, like the judge needs to be loosened
otherwise we will never get lift off"* / *"please fix permanently"*.

THE BLOCKER, from the judge's own published state — not inferred:

    georgia  phase=unjudgeable
      reason: policy_mismatch
      detail: arms diverge on ['max_entries_per_hour']:
              live={'max_entries_per_hour': None} shadow={'max_entries_per_hour': 5}

The judge was RIGHT to refuse: a paired bar across two different entry policies
is not a comparison. Nothing needed loosening — the arms needed aligning. This
is the fix, and it is deliberately NOT a bar change: no evidence requirement
moved, so `EVIDENCE IS SENIOR TO PERMISSION` is untouched.

MEASURED, on the two arms' own ledgers — entries per ACTIVE hour:
    shadow {1: 108h, 2: 44h, 3: 4h}          at-or-over cap in  2.6% of hours
    live   {1: 16h, 2: 5h, 3: 3h, 4: 1h, 9: 1h}                19.2%
The live arm reached NINE entries in one hour. Her ledger prices the marginal
entry: rank 1 −0.443%/trade (n=24), rank 2 +0.828% (n=9), rank 3 −7.752% (n=3).

RESTRICT-ONLY, which is why it ships without a forward test: the live arm can
only ever take FEWER entries, converging onto the cap the shadow was MEASURED
at ((ve) 3 -> 5). Aligning to the measured policy is not a widening and costs no
expectancy the shadow has not already paid.

PERMANENT BY CONSTRUCTION — the point of the whole change. Both arms read
`lighter_family_bot.throttle_cap`, so they cannot drift apart again without
somebody editing one owner. A host-local copy of the cap would be a second
policy ((hj)), and that is exactly how this divergence was born.
"""
import ast
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import lighter_family_bot as fam                             # noqa: E402

LIVE = ROOT / "lighter_avo_live_bot.py"


def _live_src():
    return LIVE.read_text()


def test_the_live_host_imports_the_shadows_throttle_owner():
    """ONE OWNER. A host-local cap is a second policy and is how the arms
    diverged in the first place."""
    tree = ast.parse(_live_src())
    imported = {a.name for n in ast.walk(tree)
                if isinstance(n, ast.ImportFrom) and n.module == "lighter_family_bot"
                for a in n.names}
    assert "throttle_cap" in imported, (
        "the live host must import throttle_cap, not re-derive the cap")


def test_the_live_host_ENFORCES_the_cap_not_just_stamps_it():
    """The defect was a host that stamped honestly and enforced nothing. A
    stamp without enforcement is a declaration; the judge needs the policy."""
    src = _live_src()
    tree = ast.parse(src)
    calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call)
             and getattr(n.func, "id", "") == "throttle_cap"]
    assert len(calls) >= 2, (
        "throttle_cap must be called at least twice — once to ENFORCE in the "
        f"entry loop and once to STAMP; found {len(calls)}")
    assert '_verdict(sym, "throttled")' in src, (
        "the entry loop must refuse an over-cap entry and SAY SO in the census "
        "— a silent refusal is unattributable (I18)")


def test_the_stamp_reports_what_is_enforced():
    """A stamp that disagrees with the loop re-creates the divergence in the
    other direction — the judge would then compare a policy nobody runs."""
    src = _live_src()
    assert 'policy_stamp(S, "lighter_live", "diversified",\n' in src or \
           'policy_stamp(S, "lighter_live", "diversified", throttle_cap(S))' in src, \
        "the live stamp must pass throttle_cap(S)"
    assert 'policy_stamp(S, "lighter_live", "diversified", None)' not in src, (
        "the live host still stamps a hard-coded None — that is the exact "
        "value that made georgia's pair unjudgeable")


def test_both_arms_stamp_the_SAME_cap_for_georgia():
    """THE PARITY THE JUDGE ACTUALLY CHECKS, driven through the real builder
    rather than asserted about it."""
    # [2026-09-02 (wt)] georgia is retired on both arms; the PARITY property is
    # about the stamp BUILDER, not the roster, so drive it off the registered
    # DayTraderGated carrier (still the one class that throttles).
    geo = next(s for s in fam.STRATEGIES if s.bot == "freqtrade-georgia")
    cap = fam.throttle_cap(geo)
    # [2026-08-28 (vd)] STAYS 5. A cut to 2 was measured (permutation P=0.0244)
    # and REVERTED: one NEAR close at -19.506% on a -5% stop is 87% of the
    # signal. See the constant's own note.
    assert cap == 5, f"georgia's cap stays 5 — re-read (vd)"
    shadow = fam.policy_stamp(geo, "lighter_shadow", "list", cap)
    live = fam.policy_stamp(geo, "lighter_live", "diversified", cap)
    assert shadow["max_entries_per_hour"] == live["max_entries_per_hour"] == 5, (
        "the arms still disagree on the throttle — the pair stays unjudgeable")


def test_a_non_daytrader_book_is_left_byte_identical():
    """🙏 avo must not acquire a throttle she never had. `None` means no cap,
    and the live host's behaviour for her is unchanged."""
    avo = next(s for s in fam.live_strategies() if s.bot == "freqtrade-avo-maria")
    assert fam.throttle_cap(avo) is None, (
        "avo has no hourly throttle and this change must not give her one")
    mum = next(s for s in fam.live_strategies() if s.bot == "freqtrade-mum")
    assert fam.throttle_cap(mum) is None


def test_the_gate_is_restrict_only():
    """The cap can only REFUSE an entry, never manufacture one — so the worst
    case of a wrong cap is fewer trades, never an unwanted position."""
    src = _live_src()
    i = src.index('_cap = throttle_cap(S)')
    window = src[i:i + 600]
    assert "continue" in window, "the throttle branch must refuse, not open"
    assert "market_open" not in window, (
        "the throttle branch must not sit on an opening path")


@pytest.mark.parametrize("stale", [
    "enforces NO hourly throttle",
    "live rank is the\n                # UNCENSORED within-hour ordinal",
])
def test_no_stale_claim_that_this_host_has_no_throttle(stale):
    """I12: a comment that no longer describes the system is a defect. Three of
    these existed and each would send the next reader to the wrong conclusion
    about a real-money entry path."""
    assert stale not in _live_src(), (
        f"stale claim still in the live host: {stale!r}")


# ------------------------------------------- the venue's refusal must be named
def test_a_venue_refusal_is_named_on_the_row():
    """[2026-08-28 (vd)] 👩 mum published `venue_reject: 1` and nothing else
    while Lighter refused EVERY order she placed:

        code=20558 "You are accessing Lighter from a restricted jurisdiction"

    A live book that COULD NOT TRADE AT ALL was byte-identical to a quiet book
    with no signal, and the only record was a log line inside a container —
    [[a-venue-403-kills-a-live-book-silently]], measured there at 8.2h dark
    with nothing paged.

    I8: a detector must name the object the operator can act on. A jurisdiction
    block is an OPERATOR action WITH THE VENUE — no code may route around it —
    so the row carries the venue's own code and message verbatim.
    """
    import lighter_avo_live_bot as live
    c = live.scan_census({"BTC": "venue_reject"}, {"BTC": 30.0}, 36.0,
                         ["BTC"], {}, None, None, None, None, 0,
                         last_reject={"sym": "JTO", "why": "code=20558 x",
                                      "at": "2026-08-28T06:36:19Z"})
    assert c["venue_reject_why"]["sym"] == "JTO"
    assert "20558" in c["venue_reject_why"]["why"]


def test_no_refusal_publishes_NO_key_rather_than_an_empty_one():
    """An empty dict would read as 'refused, reason unknown'. Absent means
    nothing was refused — unknown degrades to the honest absence (I8)."""
    import lighter_avo_live_bot as live
    c = live.scan_census({"BTC": "no_signal"}, {"BTC": 50.0}, 36.0,
                         ["BTC"], {}, None, None, None, None, 0)
    assert "venue_reject_why" not in c


def test_the_reject_holder_is_reachable_from_the_publisher():
    """THE DEFECT THIS ALMOST SHIPPED WITH. The reject happens in `main`'s
    entry loop; the census is built in `_publish_row`. The first cut made the
    holder a `main` local, so it was populated and structurally unable to reach
    the payload — the same computed-and-dropped shape as this morning's
    `n_phantom`. Module scope is what makes it publishable."""
    import ast
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    tree = ast.parse(src)
    module_level = {t.id for n in tree.body if isinstance(n, ast.Assign)
                    for t in n.targets if isinstance(t, ast.Name)}
    assert "_LAST_REJECT" in module_level, (
        "_LAST_REJECT must be module-level or _publish_row cannot see it")


def test_the_reject_reason_is_durable_like_the_verdict_it_explains():
    """[2026-08-28 (vd)] THE DESYNC THIS SHIPPED WITH, caught on the live row.

    `scan_verdict` is durable BY DESIGN — kept across loops and restored across
    restarts, because this book decides on a slow candle and publishes every
    90s ("a per-CYCLE census would read 'nothing evaluated' on ~159 of every
    160 loops"). The first cut added `_LAST_REJECT.clear()` to the per-loop
    counter block — three lines above the comment saying exactly which things
    must NOT be reset there.

    Result on the live row: `venue_reject: 1` beside `venue_reject_why: null`.
    The verdict outlived its reason, which is the precise ambiguity the field
    was added to remove. The `at` stamp is what makes a stale reason readable
    as stale; clearing is not.
    """
    src = (ROOT / "lighter_avo_live_bot.py").read_text()
    # AST, not a substring: my first cut asserted `"_LAST_REJECT.clear()" not
    # in src` and failed on its OWN comment explaining the bug. A page-wide
    # substring scan is not a structural claim
    # ([[a-substring-test-is-not-a-wiring-test]]).
    tree = ast.parse(src)
    clears = [n for n in ast.walk(tree)
              if isinstance(n, ast.Call)
              and isinstance(n.func, ast.Attribute) and n.func.attr == "clear"
              and getattr(n.func.value, "id", "") == "_LAST_REJECT"]
    assert not clears, (
        f"_LAST_REJECT.clear() is called at line(s) "
        f"{[c.lineno for c in clears]} — the reason is reset per loop while "
        f"its verdict is durable, so the row publishes venue_reject with a "
        f"null reason again")
    # and the reason must be self-dating, or a durable one is unreadable
    updates = [n for n in ast.walk(tree)
               if isinstance(n, ast.Call)
               and isinstance(n.func, ast.Attribute) and n.func.attr == "update"
               and getattr(n.func.value, "id", "") == "_LAST_REJECT"]
    assert updates, "_LAST_REJECT is never populated"
    assert any(k.arg == "at" for u in updates for k in u.keywords), (
        "the reason must carry an `at` stamp, or a stale one reads as fresh")
