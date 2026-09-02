"""[2026-09-02, edge-audit follow-up] Eamon: "Proceed on all."

EDGE_AUDIT_2026-09-02.md left four items as prose after its three approved
sizing advisements shipped ((wu)). These pins make each one executable:

  * section 6.1 -- kelly's pre-registered keep-or-retire read is a docket
    deferral that EXPIRES, and a carried row that closes only when the entry
    is removed;
  * section 6.4 / section 9 -- the SHAPE block (hit rate vs the book's own
    break-even, payoff, streak vs chance) flows from the grader's `stats` to
    its payload to the immune organ, which flags LIVE books only;
  * section 9 -- the chance-streak owner is the grader (exact, no simulation)
    and the audit imports it by identity;
  * section 9 / I25 -- the live lane's pre-window margin is the measured
    reversion, the twin is required, and the baseline floor is the fleet's
    computability floor.

[2-Sep, later -- Eamon: "Calibrate accordingly"] the two numbers the entry
flagged as uncalibrated are now measurements: the shape monitor tests
`hit_margin_z` against the fleet's own claim bar (`hit_margin_crit`) instead
of a round 5pp, and the I25 margin is re-measured by the reversion study's
own `--margin` arm, which grades the constant against the band it measures.

Consumers are driven on payloads the PUBLISHER built ((hj)), never on
hand-written fixtures that merely look like them.
"""
import importlib.util
import itertools
import json
import math
import os
import sys
import time
from datetime import datetime, timedelta, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
for _p in (ROOT, os.path.join(ROOT, "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import golive_readiness as gr          # noqa: E402
import fleet_immune as fi              # noqa: E402
import fleet_proprioception as fp      # noqa: E402
import fleet_allocation as fa          # noqa: E402
import edge_audit as ea                # noqa: E402
import session_state as ss             # noqa: E402

_spec = importlib.util.spec_from_file_location(
    "study_changes_hurt",
    os.path.join(ROOT, "scripts", "study_do_our_changes_hurt_2026-08-27.py"))
study = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(study)


# ------------------------------------------------------------ 6.1 kelly's read

def test_kellys_read_is_a_docket_deferral_that_expires():
    d, until, why = gr.decided_until("band-kelly-lshadow", "2026-09-15T00:00:00+00:00")
    assert d is True and until == "2026-10-01", (d, until)
    for needle in ("n>=60", "RETIRE", "fresh upper bound", "1-Sep", "CLAUDE.md"):
        assert needle in why, (needle, why)
    # past the date the deferral EXPIRES and the docket prints decision_overdue
    d2, until2, _ = gr.decided_until("band-kelly-lshadow", "2026-10-02T00:00:00+00:00")
    assert d2 is False and until2 == "2026-10-01"
    # keyed on the bare book, one suffix strip, like every other entry
    assert gr.decided_until("band-kelly", "2026-09-15T00:00:00+00:00")[0] is True


def test_kellys_read_is_carried_until_the_entry_is_removed():
    row = next(it for it in ss.CARRIED if it["id"] == "kelly-fresh-read-pre-registered")
    assert row["closes_when"]() is False, "the deferral entry exists, so the row stays open"
    assert "band-kelly" in row["why_open"] and "DECIDED_UNTIL" in row["why_open"]


# ------------------------------------------------------- 9 the chance streak

def test_expected_streak_is_exact_and_owned_by_the_grader():
    assert ea.expected_streak is gr.expected_streak, "the audit must import the owner by identity"
    # exact against brute force over every outcome string
    for n, p in ((5, 0.5), (7, 0.35), (6, 0.8)):
        for k in range(1, n + 2):
            brute = 0.0
            for outcome in itertools.product((0, 1), repeat=n):
                run = mx = 0
                for o in outcome:
                    run = run + 1 if o else 0
                    mx = max(mx, run)
                if mx < k:
                    brute += (p ** sum(outcome)) * ((1 - p) ** (n - sum(outcome)))
            assert abs(gr.loss_run_cdf(n, p, k) - brute) < 1e-12, (n, p, k)
    es = gr.expected_streak(383, 0.55)           # kelly-shaped: n=383, hit 45%
    assert isinstance(es["p50"], int) and isinstance(es["p95"], int)
    assert 6 <= es["p50"] <= es["p95"] <= 20, es
    assert gr.expected_streak(100, 0.2)["p95"] < gr.expected_streak(100, 0.6)["p95"]
    assert gr.expected_streak(1, 0.5) is None and gr.expected_streak(30, 1.0) is None
    # the old simulated signature still resolves (call sites pass draws/seed)
    assert gr.expected_streak(40, 0.5, draws=5, seed=1) == gr.expected_streak(40, 0.5)


# ------------------------------------------- 6.4 / 9 the shape block, end to end

def _ledger(n, hit, win_usd, loss_usd):
    """oldest-first (pct, abs, closed_at) rows; losers fall every `period`-th
    row so the trailing-30 hit rate equals the overall one (a fixture whose
    tail differs from its body would test the fixture, not the monitor)."""
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    period = max(2, round(1.0 / (1.0 - hit)))
    rows = []
    for i in range(n):
        lose = (i % period == period - 1)
        rows.append(((-0.02 if lose else 0.01), (-loss_usd if lose else win_usd),
                     t0 + timedelta(hours=6 * i)))
    return rows


def _gate_payload(books):
    return {"golive-readiness": {"updated": datetime.now(timezone.utc).isoformat(),
                                 "ttl_sec": 86400, "books": books}}


def test_shape_block_is_published_from_the_graders_own_stats():
    st = gr.stats(_ledger(60, 0.83, 3.65, 7.39), book_usd=1000.0)
    sh = gr.book_payload(st)["shape"]
    for k in ("hit_pct", "hit_trailing_pct", "n_trailing", "avg_win_usd", "avg_loss_usd",
              "payoff", "breakeven_hit_pct", "hit_margin_pp", "streak_now", "streak_max",
              "streak_p50_chance", "streak_p95_chance"):
        assert k in sh, (k, sh)
    assert sh["avg_win_usd"] == 3.65 and sh["avg_loss_usd"] == 7.39
    assert sh["breakeven_hit_pct"] == round(100 / (1 + 3.65 / 7.39), 1)      # 66.9
    assert sh["n_trailing"] == gr.SHAPE_TRAIL_N == 30
    # [2-Sep, calibrated] the margin in sampling-noise units -- SEs above
    # break-even with the SE taken at break-even -- and the fleet's own claim
    # bar for the trailing n, each from its owner, never a retyped constant
    raw = st["shape"]
    be = raw["breakeven_hit"]
    z = (raw["hit_trailing"] - be) / math.sqrt(be * (1 - be) / raw["n_trailing"])
    assert abs(raw["hit_margin_z"] - z) < 1e-9 and sh["hit_margin_z"] == round(z, 2), (raw, sh)
    assert raw["hit_margin_crit"] == fa.t_crit(30, floor=gr.HORIZON_Z) >= 1.28, raw
    assert sh["hit_margin_crit"] == round(raw["hit_margin_crit"], 3)
    assert "shape" not in gr.book_payload(gr.stats(_ledger(60, 0.83, 3.65, 7.39)[:1]))


def test_immune_flags_a_live_book_below_the_claim_bar_and_only_that():
    near = gr.book_payload(gr.stats(_ledger(60, 0.66, 3.65, 7.39), book_usd=1000.0))
    noise = gr.book_payload(gr.stats(_ledger(60, 0.77, 3.65, 7.39), book_usd=1000.0))
    ok = gr.book_payload(gr.stats(_ledger(60, 0.85, 3.65, 7.39), book_usd=1000.0))
    # [2-Sep, calibrated] `noise` is the case a POINTS threshold got wrong: 22 of
    # 30 sits 6.4pp above break-even -- QUIET under "within 5pp" -- and 0.74 SE,
    # below the fleet's claim bar for n=30, so the window does not show PF > 1
    assert noise["shape"]["hit_margin_pp"] > 5.0, noise["shape"]
    for p in (near, noise):
        assert p["shape"]["hit_margin_z"] <= p["shape"]["hit_margin_crit"], p["shape"]
    assert ok["shape"]["hit_margin_z"] > ok["shape"]["hit_margin_crit"], ok["shape"]
    nocrit = dict(near, shape=dict(near["shape"], hit_margin_crit=None))
    inv = fi.organ_invariants(_gate_payload({
        "fixture-near-lighter": {"n": 60, **near},
        "fixture-noise-lighter": {"n": 60, **noise},
        "fixture-ok-lighter": {"n": 60, **ok},
        "fixture-near-lshadow": {"n": 60, **near},      # shadow: never paged
        "fixture-nocrit-lighter": {"n": 60, **nocrit},  # no bar published: quiet, never re-derived
    }), time.time())
    det = sorted(i["detail"] for i in inv if i["organ"] == "golive-readiness")
    assert len(det) == 2, det
    assert det[0].startswith("fixture-near-lighter:") and "claim bar" in det[0], det
    assert det[1].startswith("fixture-noise-lighter:") and "claim bar" in det[1], det


def test_immune_flags_a_live_streak_beyond_chance_and_is_quiet_inside_it():
    calm = gr.book_payload(gr.stats(_ledger(60, 0.85, 3.65, 7.39), book_usd=1000.0))
    assert calm["shape"]["streak_now"] <= calm["shape"]["streak_p95_chance"]
    hot = dict(calm, shape=dict(calm["shape"], streak_now=calm["shape"]["streak_p95_chance"] + 1))
    inv = fi.organ_invariants(_gate_payload({
        "fixture-calm-lighter": {"n": 60, **calm},
        "fixture-hot-lighter": {"n": 60, **hot},
        "fixture-hot-lshadow": {"n": 60, **hot},
    }), time.time())
    det = [i["detail"] for i in inv if i["organ"] == "golive-readiness"]
    assert len(det) == 1 and det[0].startswith("fixture-hot-lighter:") and "p95 chance" in det[0], det


def test_immune_stays_quiet_on_a_thin_trailing_window_and_a_stale_gate():
    near = gr.book_payload(gr.stats(_ledger(60, 0.66, 3.65, 7.39), book_usd=1000.0))
    thin = dict(near, shape=dict(near["shape"], n_trailing=fi.SHAPE_MIN_N - 1))
    assert fi.organ_invariants(_gate_payload({"x-lighter": {"n": 60, **thin}}), time.time()) == []
    stale = _gate_payload({"x-lighter": {"n": 60, **near}})
    stale["golive-readiness"]["updated"] = "2020-01-01T00:00:00+00:00"
    assert fi.organ_invariants(stale, time.time()) == []


# ----------------------------------------------------------- 9 / I25 the margin

def _iso(ts):
    return datetime.fromtimestamp(ts, timezone.utc).isoformat()


#: [2-Sep re-measurement, `study_do_our_changes_hurt_2026-08-27.py --margin`]
#: hot-window collapse (pp) and its SE per window size, 3,801 closes / 26 books.
#: RECORDED here with its date so an edit of the constant to 0.25 or 5.0
#: reddens; the instrument, not this pin, is what re-measures it.
MEASURED_COLLAPSE_2SEP = {10: (1.741, 0.497), 15: (1.518, 0.469),
                          20: (1.601, 0.458), 30: (1.672, 0.579)}


def test_i25_pre_window_margin_is_the_measured_reversion_and_twin_is_required():
    assert fp.LIVE_BASE_MIN_N == fa.MIN_N == 10
    for k, (m, se) in MEASURED_COLLAPSE_2SEP.items():
        assert abs(fp.LIVE_PRE_MARGIN_PP - m) <= 2 * se, (k, fp.LIVE_PRE_MARGIN_PP, m, se)
    assert fp.LIVE_PRE_MARGIN_PP > fp.LIVE_MARGIN_PP
    LIVE, TWIN = "fixture-funding-lighter", "fixture-funding-lshadow"
    fp.LIVE_ROWS.add(LIVE)
    try:
        t0 = 1_800_000_000.0
        ep = {"group": "live-funding", "start": t0, "end": t0 + 6 * 3600,
              "stance": {"live.funding.enter_apr": 0.0375}}

        def lt(bot, off_h, pct):
            return {"bot": bot, "profit_ratio": pct, "close_ts": _iso(t0 + off_h * 3600)}

        during = [lt(LIVE, 1 + i * 0.5, 0.002) for i in range(6)]
        pre = lambda pct, n=12: [lt(LIVE, -5.9 + i * 0.45, pct) for i in range(n)]   # noqa: E731
        twin = lambda pct, n=12: [lt(TWIN, 0.25 + i * 0.45, pct) for i in range(n)]  # noqa: E731
        gl = lambda tr: fp.grade_live(ep, tr, group="live-funding")                 # noqa: E731
        # inside the tide: 1.3pp below the pre-window, 1.0pp below the twin -> flat
        tide = gl(during + pre(0.015) + twin(0.012))
        assert tide["status"] == "graded" and tide["signal"] == "flat", tide
        assert tide["baselines"]["pre"]["margin_pp"] == fp.LIVE_PRE_MARGIN_PP
        # beyond the tide on both -> bad, still reachable on real evidence
        bad = gl(during + pre(0.025) + twin(0.012))
        assert bad["signal"] == "bad", bad
        # no control arm -> recorded, however bad the pre-window looks
        alone = gl(during + pre(0.05))
        assert alone["status"] == "recorded" and alone["reason"] == "no-control-arm", alone
        # a twin below the computability floor is not a control arm
        thin = gl(during + pre(0.025) + twin(0.012, n=6))
        assert thin["status"] == "recorded", thin
    finally:
        fp.LIVE_ROWS.discard(LIVE)


# --------------------------------------------- I25 the instrument that re-measures

def test_the_reversion_instrument_reads_a_ledger_file_and_grades_the_margin(tmp_path):
    import random
    rng = random.Random(7)
    t0 = datetime(2026, 6, 1, tzinfo=timezone.utc)
    trades = []
    for bot in ("book-a-lshadow", "book-b-lshadow"):
        for i in range(400):
            pct = rng.gauss(0.0, 0.02)
            trades.append({"bot": bot, "closed_at": (t0 + timedelta(hours=i)).isoformat(),
                           "pnl_pct": pct, "pnl_abs": pct * 100})
    trades.append({"bot": "junk", "closed_at": "not a time", "pnl_pct": 0.1})
    trades.append({"bot": "junk", "closed_at": None, "pnl_pct": 0.1})
    trades.append({"bot": "junk", "closed_at": t0.isoformat(), "pnl_pct": None})
    path = tmp_path / "trades.json"
    path.write_text(json.dumps({"trades": trades}))
    rows = study.load_ledger_file(str(path))
    assert len(rows) == 800 and rows == sorted(rows, key=lambda r: r[1])
    books = study.by_book(rows)
    assert set(books) == {"book-a-lshadow", "book-b-lshadow"}
    # `hot_collapse` is the peak arm's own windows, as one number: brute-force it
    k = 10
    brute = []
    for v in books.values():
        ys = [p for _t, p in v]
        bm = sum(ys) / len(ys)
        for i in range(0, len(ys) - 2 * k, k):
            w, nxt = ys[i:i + k], ys[i + k:i + 2 * k]
            if len(nxt) == k and sum(w) / k > bm:
                brute.append((sum(w) / k - sum(nxt) / k) * 100)
    m, se, n = study.hot_collapse(books, k)
    assert n == len(brute) >= study.MIN_WINDOWS and abs(m - sum(brute) / n) < 1e-9, (m, n)
    assert m > 0 and se > 0, "iid noise still reverts: a window selected for being hot is followed by the mean"
    # the grade: the measured collapse is INSIDE its own band; 10pp is DRIFT
    assert study.margin_arm(books, margin=m, ks=[k])["verdict"] == "INSIDE"
    drift = study.margin_arm(books, margin=10.0, ks=[k])
    assert drift["verdict"] == "DRIFT" and drift["k"][k]["inside"] is False
    # too few hot windows grade nothing -- THIN, never a vacuous INSIDE
    thin = study.margin_arm({"book-a-lshadow": books["book-a-lshadow"][:60]}, margin=m, ks=[k])
    assert thin["verdict"] == "THIN" and thin["k"][k]["inside"] is None
    # the default window set is anchored on the grader's own baseline floor
    assert fp.LIVE_BASE_MIN_N in study.margin_arm(books)["k"]
