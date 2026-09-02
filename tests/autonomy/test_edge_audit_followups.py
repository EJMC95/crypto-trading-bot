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

[2-Sep, later -- Eamon: "Calibrate accordingly", then "Calibrate optimally
with findings"] the two numbers the entry flagged as judgements are DERIVED
from the measurements, not set: the shape monitor pages at the exact-binomial
minimum-total-error boundary between the book's own era hit rate and its
break-even (`page_wins_max`, with the false-page and miss rates published
beside it), and the live lane's margins are each comparison's own standard
error at the fleet's critical value, judged against the twin and the book's
mean EXCLUDING the motivating window -- the reversion study's `--margin` arm
runs the shipped book gate on the no-change control and grades its false rates.

Consumers are driven on payloads the PUBLISHER built ((hj)), never on
hand-written fixtures that merely look like them.
"""
import importlib.util
import itertools
import json
import math
import os
import statistics
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
    # [2-Sep, calibrated optimally] the page boundary is the argmin of the total
    # error (false page + missed decay), exact binomial, brute-forced here; both
    # rates ride the payload beside the integer boundary and the integer count
    n_tr, p_era = raw["n_trailing"], raw["hit"]
    tot = [gr.binom_cdf(k, n_tr, p_era) + 1 - gr.binom_cdf(k, n_tr, be) for k in range(n_tr + 1)]
    assert raw["page_wins_max"] == min(range(n_tr + 1), key=lambda k: tot[k]) == sh["page_wins_max"] == 22
    assert raw["wins_trailing"] == sum(1 for r in _ledger(60, 0.83, 3.65, 7.39)[-30:] if r[0] > 0) \
        == sh["wins_trailing"] == 25
    assert sh["page_false_rate_pct"] == round(100 * gr.binom_cdf(22, n_tr, p_era), 1)
    assert sh["page_miss_rate_pct"] == round(100 * (1 - gr.binom_cdf(22, n_tr, be)), 1)
    assert "hit_margin_crit" not in sh
    assert "shape" not in gr.book_payload(gr.stats(_ledger(60, 0.83, 3.65, 7.39)[:1]))


def _two_segment_ledger(older_wins, trailing_wins, n_each=30, win_usd=3.65, loss_usd=7.39):
    """oldest-first rows: an older segment with `older_wins` of `n_each` wins,
    then a trailing segment with `trailing_wins`; losses spread evenly through
    each segment so no fixture carries a streak beyond chance."""
    t0 = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for seg, wins in enumerate((older_wins, trailing_wins)):
        losses = n_each - wins
        lose_at = {int((j + 0.5) * n_each / losses) for j in range(losses)} if losses else set()
        for i in range(n_each):
            lose = i in lose_at
            rows.append(((-0.02 if lose else 0.01), (-loss_usd if lose else win_usd),
                         t0 + timedelta(hours=6 * (seg * n_each + i))))
    return rows


def test_immune_pages_a_live_book_at_or_below_its_page_boundary_and_only_that():
    near = gr.book_payload(gr.stats(_two_segment_ledger(28, 20), book_usd=1000.0))   # era 80%, trailing 20/30
    edge = gr.book_payload(gr.stats(_two_segment_ledger(28, 23), book_usd=1000.0))   # era 85%, trailing 23/30
    ok = gr.book_payload(gr.stats(_two_segment_ledger(28, 26), book_usd=1000.0))     # era 90%, trailing 26/30
    # [2-Sep, calibrated optimally] `edge` is ON its boundary: 23 of 30 sits
    # 9.8pp above break-even -- a "within 5pp" rule stayed QUIET -- yet the
    # window is already likelier under a break-even hit rate than under 85%
    assert edge["shape"]["hit_margin_pp"] > 5.0, edge["shape"]
    assert edge["shape"]["wins_trailing"] == edge["shape"]["page_wins_max"] == 23, edge["shape"]
    assert near["shape"]["wins_trailing"] == 20 <= near["shape"]["page_wins_max"] == 22, near["shape"]
    assert ok["shape"]["wins_trailing"] == 26 > ok["shape"]["page_wins_max"] == 24, ok["shape"]
    nobound = dict(near, shape=dict(near["shape"], page_wins_max=None))
    inv = fi.organ_invariants(_gate_payload({
        "fixture-near-lighter": {"n": 60, **near},
        "fixture-edge-lighter": {"n": 60, **edge},
        "fixture-ok-lighter": {"n": 60, **ok},
        "fixture-near-lshadow": {"n": 60, **near},        # shadow: never paged
        "fixture-nobound-lighter": {"n": 60, **nobound},  # no boundary published: quiet, never re-derived
    }), time.time())
    det = sorted(i["detail"] for i in inv if i["organ"] == "golive-readiness")
    assert len(det) == 2, det
    assert det[0].startswith("fixture-edge-lighter:") and "23 of the last 30" in det[0] \
        and "page boundary 23/30" in det[0], det
    assert det[1].startswith("fixture-near-lighter:") and "20 of the last 30" in det[1] \
        and "page boundary 22/30" in det[1], det
    for d in det:      # what a page costs is IN the page
        assert "of healthy windows" in d and "of break-even ones" in d and "break-even" in d, d


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


def _alt(mean, n, amp=0.4):
    """`n` pct-point returns alternating +-amp around `mean` (mean exact for even n)"""
    return [mean + (amp if i % 2 == 0 else -amp) for i in range(n)]


def test_i25_margins_are_the_books_own_noise_at_the_fleets_critical_value_and_the_twin_is_required():
    assert fp.LIVE_BASE_MIN_N == fa.MIN_N == 10
    assert not hasattr(fp, "LIVE_PRE_MARGIN_PP"), "the fixed reversion margin is gone; margins are derived"
    assert fp.crit_for(10) == fa.t_crit(10) and fp.crit_for(6) == fa.t_crit(6), "the one owner, by value"
    hist, twin_hist = _alt(1.5, 24), _alt(1.2, 12)       # a steady +1.5% book; its +1.2% twin
    before_pre = hist[:12]
    # I25, THE CASE THAT MATTERS: the motivating window was HOT (+2.5) and the
    # episode simply returned to the book's own mean (+1.5) beside a twin at
    # +1.5. Against the motivating window that is "1.0pp worse"; against the
    # book's mean EXCLUDING that window and the twin, it is nothing -> flat
    hot_hist = _alt(1.5, 12) + _alt(2.5, 12)
    tide = fp.judge_windows(_alt(1.5, 6), hot_hist, hot_hist[:12], _alt(1.5, 12), _alt(1.5, 12))
    assert tide["status"] == "graded" and tide["signal"] == "flat", tide
    assert tide["baselines"]["book"]["mean_pct"] == 1.5 and tide["baselines"]["book"]["n"] == 12 \
        and tide["baselines"]["book"]["excludes_motivating_window"] is True, tide
    # a real harm (1.3pp below both, ~4 SE) -> bad; a real gain -> good
    bad = fp.judge_windows(_alt(0.2, 6), hist, before_pre, _alt(1.2, 12), twin_hist)
    assert bad["signal"] == "bad", bad
    assert fp.judge_windows(_alt(3.0, 6), hist, before_pre, _alt(1.2, 12), twin_hist)["signal"] == "good"
    # THE MARGINS ARE crit x SE FROM THE ARMS' OWN DISPERSION, floored -- by
    # identity with fleet_allocation.t_crit, recomputed here
    sd = statistics.stdev(hist)
    se_book = math.sqrt(sd ** 2 / 6 + sd ** 2 / 12)
    assert abs(bad["baselines"]["book"]["margin_pp"] - max(fp.LIVE_MARGIN_PP, fa.t_crit(6) * se_book)) < 2e-3, bad
    se_tw = math.sqrt(sd ** 2 / 6 + statistics.stdev(twin_hist) ** 2 / 12)
    assert abs(bad["baselines"]["twin"]["margin_pp"] - max(fp.LIVE_MARGIN_PP, fa.t_crit(6) * se_tw)) < 2e-3, bad
    assert bad["baselines"]["twin"]["margin_pp"] > fp.LIVE_MARGIN_PP, "the derived margin, not the floor, binds"
    assert bad["baselines"]["twin"]["crit"] == round(fa.t_crit(6), 3) and bad["baselines"]["twin"]["se_pp"] > 0
    # worse than the TWIN beyond its margin but AT the book's own mean -> flat:
    # `bad` needs every baseline, and the mirror (worse than the book, better
    # than the twin) is flat too -- real money is not blamed on one comparison
    assert fp.judge_windows(_alt(1.5, 6), hist, before_pre, _alt(2.5, 12), _alt(2.5, 12))["signal"] == "flat"
    assert fp.judge_windows(_alt(0.2, 6), hist, before_pre, _alt(-2.0, 12), _alt(-2.0, 12))["signal"] == "flat"
    # INSIDE THE NOISE: 0.28pp below both clears a 0.25pp floor but not the
    # derived ~0.30pp margin -> flat; with no critical value (the floor alone)
    # the same episode reads bad -- the difference between a floor and a margin
    nz = fp.judge_windows(_alt(1.22, 6), hist, before_pre, _alt(1.5, 12), _alt(1.5, 12))
    assert nz["signal"] == "flat", nz
    gate0 = fp.book_gate(_alt(1.22, 6), before_pre, hist, crit=0.0)
    assert gate0["margin_pp"] == fp.LIVE_MARGIN_PP and 1.22 < gate0["mean_pct"] - gate0["margin_pp"], gate0
    # no control arm -> recorded, however bad the book comparison looks; a thin
    # twin window (6 < the floor) is not a control arm either
    assert fp.judge_windows(_alt(0.2, 6), hist, before_pre, [], []) == \
        {"status": "recorded", "reason": "no-control-arm"}
    assert fp.judge_windows(_alt(0.2, 6), hist, before_pre, _alt(1.2, 6), twin_hist)["status"] == "recorded"
    # a young book (history below the floor) drops the book baseline; the twin decides alone
    young = fp.judge_windows(_alt(0.2, 6), _alt(1.5, 6), [], _alt(1.2, 12), twin_hist)
    assert young["status"] == "graded" and set(young["baselines"]) == {"twin"}, young
    # END TO END through grade_live on ledger rows: the same hot-window case
    LIVE, TWIN = "fixture-funding-lighter", "fixture-funding-lshadow"
    fp.LIVE_ROWS.add(LIVE)
    try:
        t0 = 1_800_000_000.0
        ep = {"group": "live-funding", "start": t0, "end": t0 + 6 * 3600,
              "stance": {"live.funding.enter_apr": 0.0375}}

        def lt(bot, off_h, pct):
            return {"bot": bot, "profit_ratio": pct / 100.0, "close_ts": _iso(t0 + off_h * 3600)}

        rows = ([lt(LIVE, -20 + i * 0.5, v) for i, v in enumerate(_alt(1.5, 12))]       # before the motivating window
                + [lt(LIVE, -5.9 + i * 0.45, v) for i, v in enumerate(_alt(2.5, 12))]   # the HOT motivating window
                + [lt(LIVE, 1 + i * 0.5, v) for i, v in enumerate(_alt(1.5, 6))]         # the episode: back at the mean
                + [lt(TWIN, 0.25 + i * 0.45, v) for i, v in enumerate(_alt(1.5, 12))]
                + [lt(TWIN, -20 + i * 0.5, v) for i, v in enumerate(_alt(1.5, 12))])
        g = fp.grade_live(ep, rows, group="live-funding")
        assert g["status"] == "graded" and g["signal"] == "flat", g
        assert g["mean_pct_before"] == 2.5 and g["n_book"] == 24, g       # the motivating window is RECORDED, not a baseline
        assert g["baselines"]["book"]["mean_pct"] == 1.5 and g["baselines"]["book"]["n"] == 12, g
        assert set(g["baselines"]) == {"twin", "book"}
    finally:
        fp.LIVE_ROWS.discard(LIVE)


# --------------------------------------------- I25 the instrument that re-measures

def test_the_no_change_control_instrument_reads_a_ledger_file_and_grades_the_shipped_gate(tmp_path):
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
    # the reversion itself (the I25 finding) keeps its owner: brute-force it
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
    # the grade runs the SHIPPED book gate on every (motivating, next) pair: on
    # iid noise the false rates sit near the nominal one-sided rate -> INSIDE
    res = study.margin_arm(books, ks=[k])
    k10 = res["k"][k]
    assert k10["n"] == 78 and res["nominal"] == 1 - fa.CONF, (k10["n"], res["nominal"])
    assert k10["false_bad"] <= 0.2 and k10["false_good"] <= 0.2 and res["verdict"] == "INSIDE", k10
    # the power column moves the right way
    assert k10["power"][-4.0]["bad"] > k10["power"][-2.0]["bad"] > k10["false_bad"], k10["power"]
    # positive control: no critical value = the floor alone -> the false rates
    # explode -> DRIFT. A fixed sub-noise margin is exactly what this replaces.
    drift = study.margin_arm(books, ks=[k], crit=0.0)
    assert drift["verdict"] == "DRIFT" and drift["k"][k]["inside"] is False
    assert drift["k"][k]["false_bad"] + drift["k"][k]["false_good"] > 0.5, drift["k"][k]
    # too few pairs grade nothing -- THIN, never a vacuous INSIDE
    thin = study.margin_arm({"book-a-lshadow": books["book-a-lshadow"][:60]}, ks=[k])
    assert thin["verdict"] == "THIN" and thin["k"][k]["inside"] is None
    # the default window set is anchored on the grader's own baseline floor
    assert fp.LIVE_BASE_MIN_N in study.margin_arm(books)["k"]
