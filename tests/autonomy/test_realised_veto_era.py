"""[2026-08-13 (lj)] THE REALISED LENS VETO GRADES THE POLICY THE ARM RUNS.

THE INCIDENT. The LIVE Ticket Taker — real money, divergence-short only —
read n=44, mean −0.468%, t=−0.83 on its short-divergence realised record, so
`realised_loses` stayed silent (bar: mean<0 AND t≤−1.0). The rows taken under
the policy it ACTUALLY RUNS read n=31, mean −1.128%, t=−1.75, and the
trailing 8 days −2.456%/t=−3.68 with nine of ten closes `_sl`. The 13
diluting rows predate the 30-Jul policy boundary that `golive_readiness`
already refuses to pool across — era discipline existed in the GRADER and
never reached the ACTUATOR, the exact I15 shape ("when a bad idea is removed
from a report, grep for it in the things that ACT").

WHAT IS GUARDED HERE, in priority order:

  1. Scoping: with `policy=` supplied, rows stamped with another signature do
     not dilute the current policy's grade (the incident, as a fixture).
  2. The pooled FALLBACK below `min_n`: a lens with a standing cross-era veto
     and ~no current-era closes (the `dip` shape — the veto itself blocks its
     entries) must be judged on its FULL record, never handed to the 4h
     proxy. Falling to the proxy would have RELEASED the fleet's only
     significant realised loser (n=13, t=−2.66) the day this shipped.
  3. (kk)/I6 absence semantics: an arm with NO stamps anywhere keeps pooled
     behaviour; once ANY row is stamped, unstamped rows are pre-adoption and
     leave the era sample.
  4. Cross-module drift arms: the signature FIELD SET and the signature
     FUNCTION are pinned to `scripts/golive_readiness` behaviourally — a
     direct import is blocked (this module ships in the live-taker image;
     dragging the grader in is the born-dark class), so the test is what
     makes the two copies unable to disagree silently.
  5. The stamp and the filter share ONE builder (`current_policy`), and the
     production call site actually passes `policy=` — a scoping fix that no
     call site uses is the registered-but-inert failure.
"""
import ast
import pathlib
import sys

import pytest

import lighter_ticket_taker as tt

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
import golive_readiness as golive  # noqa: E402

pytestmark = pytest.mark.autonomy

BOT = "lighter-ticket-taker-lighter"

#: The live arm's signature fields as stamped on every in-era close.
CUR = {"bull": True, "lenses": ["divergence"],
       "sides": {"divergence": ["short"]}, "venue": "lighter_live"}
#: The pre-30-Jul policy (bull off, both sides) the diluting rows ran under.
OLD = {"bull": False, "lenses": ["divergence"],
       "sides": {"divergence": ["long", "short"]}, "venue": "lighter_live"}


def _row(pct, policy=..., extra=None, lens="divergence", side="short",
         bot=BOT, is_open=False):
    e = dict(extra or {})
    if policy is not ...:
        e["policy"] = policy
    return {"bot": bot, "profit_ratio": pct, "is_open": is_open,
            "enter_tag": f"{side}-{lens}", "extra": e}


def _incident():
    """13 profitable old-policy rows over 31 consistently losing current ones —
    the live ledger's load-bearing shape. The old rows are BIG winners on
    purpose: what kept the real pooled t at −0.83 was their variance, so the
    fixture reproduces mean<0 with t above the bar (here −0.55), silent for
    the same reason the live payload was."""
    old = [_row(+0.02, policy=OLD) for _ in range(13)]
    # small alternation so sd > 0 and t is finite and decisively negative
    cur = [_row(-0.011 if i % 2 else -0.009, policy=CUR) for i in range(31)]
    return old + cur


def test_the_incident_pooled_is_silent_and_scoped_fires():
    rows = _incident()
    pooled = tt.realised_lens_evidence(rows, BOT, sides={"divergence": "short"})
    n, mean, t = pooled["divergence"]
    assert n == 44
    assert not tt.realised_loses(mean, t), (
        "fixture must reproduce the dilution: pooled stays under the bar")
    scoped = tt.realised_lens_evidence(rows, BOT, sides={"divergence": "short"},
                                       policy=CUR)
    n, mean, t = scoped["divergence"]
    assert n == 31, "the 13 other-era rows must leave the sample"
    assert tt.realised_loses(mean, t), (
        "the current policy's own record must be allowed to fire the veto")


def test_below_min_n_the_full_record_decides_never_the_proxy():
    """The `dip` shape: a standing cross-era veto whose own firing keeps the
    era sample empty. The lens must come back GRADED (on the full record, at
    its full n) rather than absent — absent is what hands it to the proxy."""
    rows = [_row(-0.02, policy=OLD, lens="dip", side="long")
            for _ in range(12)] + [_row(-0.018, policy=OLD, lens="dip",
                                        side="long")]
    # one in-era close of noise — far below the floor
    rows.append(_row(+0.001, policy=CUR, lens="dip", side="long"))
    out = tt.realised_lens_evidence(rows, BOT, policy=CUR)
    n, mean, t = out["dip"]
    assert n == 14, "era sample (1) is under the floor -> the FULL record grades"
    assert tt.realised_loses(mean, t), "the standing veto must not release"


def test_min_n_boundary_prefers_the_era_sample_exactly_at_the_floor():
    rows = ([_row(+0.01, policy=OLD) for _ in range(20)]
            + [_row(-0.011 if i % 2 else -0.009, policy=CUR)
               for i in range(10)])
    out = tt.realised_lens_evidence(rows, BOT, policy=CUR, min_n=10)
    n, mean, t = out["divergence"]
    assert n == 10 and mean < 0, "at exactly min_n the era sample decides"


def test_an_arm_with_no_stamps_anywhere_keeps_pooled_behaviour():
    """(kk)/I6: 'the stamp mechanism is not deployed' is not 'every trade is
    another era's'. All-unstamped + policy= must grade the full record."""
    rows = [_row(-0.011 if i % 2 else -0.009, policy=...) for i in range(12)]
    out = tt.realised_lens_evidence(rows, BOT, policy=CUR)
    assert out["divergence"][0] == 12


def test_once_any_stamp_exists_unstamped_rows_are_pre_adoption():
    rows = ([_row(+0.02, policy=...) for _ in range(5)]
            + [_row(-0.011 if i % 2 else -0.009, policy=CUR)
               for i in range(11)])
    out = tt.realised_lens_evidence(rows, BOT, policy=CUR)
    assert out["divergence"][0] == 11, "unstamped rows must leave the era sample"


def test_an_unreadable_stamp_is_fail_closed_out_of_the_era():
    """Present-but-broken differs from absent: a trade whose policy cannot be
    read cannot confirm the current one. With the era sample still over the
    floor, the broken rows must not be in it."""
    rows = ([_row(+0.05, policy="not-a-dict")]        # unreadable
            + [_row(+0.05, policy={"bull": True, "lenses": [],
                                   "sides": {}, "venue": "lighter_live"})]
            + [_row(-0.011 if i % 2 else -0.009, policy=CUR)
               for i in range(11)])
    out = tt.realised_lens_evidence(rows, BOT, policy=CUR)
    n, mean, t = out["divergence"]
    assert n == 11 and mean < 0


def test_policy_none_is_byte_identical_legacy():
    rows = _incident()
    legacy = tt.realised_lens_evidence(rows, BOT, sides={"divergence": "short"})
    assert legacy["divergence"][0] == 44


def test_a_malformed_policy_degrades_to_pooled_not_a_raise():
    rows = _incident()
    out = tt.realised_lens_evidence(rows, BOT, policy=[("not", "a-dict")])
    assert out["divergence"][0] == 44


# ---------------------------------------------------------------------------
# Cross-module drift arms — the mirrored rule cannot quietly diverge.
# ---------------------------------------------------------------------------

def test_signature_field_set_is_pinned_to_the_grader():
    assert tuple(tt._POLICY_SIG_FIELDS) == tuple(golive.POLICY_SIG_FIELDS)


def test_stamp_state_agrees_with_the_grader_on_policy_rows():
    """Behavioural pin across a spread of shapes, malformed included. Scope:
    extras that CARRY a `policy` key — the only rows this book writes; the
    grader's bracket branch (Farmer-shaped rows) is deliberately out of scope."""
    fixtures = [
        {"policy": dict(CUR, max_open=6, ticket_top_n=12)},
        {"policy": dict(OLD, max_open=4)},
        {"policy": {"bull": True, "lenses": [], "sides": {},
                    "venue": "lighter_live"}},          # unreadable: no lenses
        {"policy": "junk"},                             # unreadable: not a dict
        {"policy": {"venue": "lighter_shadow", "bull": False,
                    "lenses": ["dip"], "sides": {"dip": ["long"]}}},
    ]
    for ex in fixtures:
        ours, theirs = tt._policy_stamp_state(ex), golive.stamp_state(ex)
        assert ours == theirs, (ex, ours, theirs)


def test_the_stamp_and_the_filter_share_one_builder():
    """A close stamped by `_close_extra` must match `current_policy()`'s
    signature — the round trip that makes stamp/filter drift impossible."""
    stamped = tt._close_extra({"bars": {"tp": 0.04, "sl": -0.03,
                                        "max_hold_h": 48.0}})
    row_sig = tt._policy_stamp_state(stamped)
    cur_sig = tt._policy_stamp_state({"policy": dict(tt.current_policy())})
    assert row_sig == cur_sig and cur_sig is not None
    # and the AST proves _close_extra literally calls the builder
    tree = ast.parse(pathlib.Path(tt.__file__).read_text(encoding="utf-8"))
    fn = next(n for n in ast.walk(tree)
              if isinstance(n, ast.FunctionDef) and n.name == "_close_extra")
    calls = {c.func.id for c in ast.walk(fn)
             if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)}
    assert "current_policy" in calls


def test_the_production_call_site_passes_policy():
    """A scoping fix no call site uses is registered-but-inert. AST, not a
    substring scan (the (hm) lesson): the PRODUCTION call — the one fed by
    `store.fetch_paper_trades(...)` — must carry a `policy` keyword. The
    module's own selftest keeps deliberate legacy (policy-less) calls, which
    is why this keys on the ingest rather than on every call."""
    tree = ast.parse(pathlib.Path(tt.__file__).read_text(encoding="utf-8"))
    prod = []
    for c in ast.walk(tree):
        if not (isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                and c.func.id == "realised_lens_evidence" and c.args):
            continue
        feeds_ledger = any(
            isinstance(s, ast.Attribute) and s.attr == "fetch_paper_trades"
            for s in ast.walk(c.args[0]))
        if feeds_ledger:
            prod.append(c)
    assert prod, "no fetch_paper_trades-fed call site found"
    for c in prod:
        assert any(k.arg == "policy" for k in c.keywords), (
            "realised_lens_evidence(fetch_paper_trades(...)) called without "
            "policy= — the era scoping is inert at the production call site")
