"""Tier 3 — the brain's stake-mult PIPELINE: streak gate, fast-path, and the
kill-switch honesty rules.

Finding 10 (TEST_COVERAGE_ANALYSIS_2026-07-29.md): brain_stats (the math) is
98% covered; `compute_stake_mults` — the pipeline that turns ledgers into the
multipliers sizing the family's seven running shadow books — was validated
only by `brain_replay`. Its docstring calls the `engine` param a replay
seam; these tests drive it directly. The consumer clamp [0.5, 1.5] lives in
fleet_bus (already pinned); THIS file pins the generator's authority gates,
each carrying its own audit-fix history:

  * the frozen v2 rule table (loss + low win-rate at the raw-count floors);
  * the 3-run STREAK gate — a qualification publishes on run 3, never run 1,
    and a tag that stops qualifying drops immediately (forgive & forget);
  * the DIRECTION-SCOPED streak (21-Jul audit fix): reduce-streak credit
    must never let an expand publish on its first qualifying run;
  * the EMER fast-path (16-Jul "no-brainer window"): urgent publishes on
    run 1, latency-only, and `urgent` is re-earned EVERY run so a sticky
    True can never ride through the BRAIN_MULT_ENGINE=v2 kill switch;
  * sticky-within-qualification (28-Jul fix): a published entry keeps
    publishing while it keeps qualifying in the same direction — no one-run
    flap back to 1.0x on a bucket the engine still condemns;
  * engine-downgrade field honesty (28-Jul fix): a v2 run strips the prior
    v3 run's evidence keys instead of dressing them on a v2-stamped entry.

The v2 rule-table tests run against the REAL brain_stats. The streak/urgent
choreography stubs the qualifier at the module seam so each run's verdict is
scripted — the pipeline under test is compute_stake_mults itself.
"""
import pytest

import bot_learn as bl

pytestmark = pytest.mark.autonomy


def _cards(n, w, pnl, bot="freqtrade-mum", tag="long-momo"):
    return {bot: {"by_tag": {tag: {"n": n, "w": w, "pnl": pnl}}}}


# ── the frozen v2 rule table (real brain_stats) ──────────────────────────────
def test_v2_rule_table_at_the_floors():
    state = {}
    # n>=30, losing, wr<25% -> 0.5x ... but NOT published until the streak
    pub, _ = bl.compute_stake_mults(_cards(30, 7, -50.0), state, run_no=1,
                                    engine="v2")
    assert pub == {}                       # gate, not the grid, decides
    e = state["mult_streaks"]["freqtrade-mum|long-momo"]
    assert e["mult"] == 0.5 and e["streak"] == 1

    # wr just under 40% -> 0.75x tier; positive pnl -> no qualification
    s2 = {}
    bl.compute_stake_mults(_cards(30, 11, -10.0), s2, 1, engine="v2")
    assert s2["mult_streaks"]["freqtrade-mum|long-momo"]["mult"] == 0.75
    s3 = {}
    bl.compute_stake_mults(_cards(30, 7, +10.0), s3, 1, engine="v2")
    assert s3.get("mult_streaks", {}) == {}    # winning tags are never throttled

    # soft floor: 15 <= n < 30 needs the harsher wr bar and caps at 0.75x
    s4 = {}
    bl.compute_stake_mults(_cards(15, 3, -20.0), s4, 1, engine="v2")
    assert s4["mult_streaks"]["freqtrade-mum|long-momo"]["mult"] == 0.75
    s5 = {}
    bl.compute_stake_mults(_cards(14, 0, -20.0), s5, 1, engine="v2")
    assert s5.get("mult_streaks", {}) == {}    # under every floor -> nothing


def test_untagged_buckets_never_get_a_mult():
    state = {}
    cards = {"b": {"by_tag": {"(untagged)": {"n": 99, "w": 0, "pnl": -999.0}}}}
    pub, _ = bl.compute_stake_mults(cards, state, 1, engine="v2")
    assert pub == {} and state.get("mult_streaks", {}) == {}


# ── the 3-run streak gate + forgiveness ──────────────────────────────────────
def test_streak_publishes_on_run_three_and_forgives_immediately():
    state, cards = {}, _cards(30, 7, -50.0)
    assert bl.compute_stake_mults(cards, state, 1, engine="v2")[0] == {}
    assert bl.compute_stake_mults(cards, state, 2, engine="v2")[0] == {}
    pub, _ = bl.compute_stake_mults(cards, state, 3, engine="v2")
    assert pub["freqtrade-mum"]["long-momo"]["mult"] == 0.5   # PROMOTE_RUNS=3

    # the tag heals (stops qualifying): entry drops the SAME run — the brain
    # forgives as gracefully as it forgets
    pub, _ = bl.compute_stake_mults(_cards(35, 20, +5.0), state, 4, engine="v2")
    assert pub == {} and state["mult_streaks"] == {}


# ── scripted-qualifier choreography (module-seam stubs) ──────────────────────
@pytest.fixture
def scripted(monkeypatch):
    """Route the verdict layer to a script; the pipeline stays real."""
    script = {"verdicts": [], "i": 0}

    def fake_v2(n, w, pnl, min_n, soft_n):
        v = script["verdicts"][min(script["i"], len(script["verdicts"]) - 1)]
        script["i"] += 1
        return v

    monkeypatch.setattr(bl.bstats, "qualify_v2", fake_v2)
    return script


def _ev(**over):
    return {"prior_mu": 0.5, "prior_kappa": 8.0, "prior_src": "fleet",
            "pnl_w": -20.0, "post_wr": 0.15, **over}


@pytest.fixture
def scripted_v3(monkeypatch):
    """v3 path with a scripted qualify_v3 — exercises the urgent fast-path."""
    script = {"verdicts": [], "i": 0}
    monkeypatch.setattr(bl.bstats, "weighted_bucket_episodes",
                        lambda *a, **kw: {"stub": True})
    monkeypatch.setattr(bl.bstats, "eb_prior", lambda *a, **kw: {"stub": True})

    def fake_v3(st, prior, min_n, soft_n, expand):
        v = script["verdicts"][min(script["i"], len(script["verdicts"]) - 1)]
        script["i"] += 1
        return v

    monkeypatch.setattr(bl.bstats, "qualify_v3", fake_v3)
    return script


ERA = {"freqtrade-mum": [{"enter_tag": "long-momo", "pnl_abs": -1.0}] }


def test_direction_flip_restarts_the_streak(scripted):
    # [2026-07-21 AUDIT FIX] two reduce-qualifying runs of credit must not
    # let an expand publish early: a direction flip is a NEW claim.
    scripted["verdicts"] = [0.5, 0.5, 1.25, 1.25, 1.25]
    state, cards = {}, _cards(30, 7, -50.0)
    bl.compute_stake_mults(cards, state, 1, engine="v2")
    bl.compute_stake_mults(cards, state, 2, engine="v2")
    pub, _ = bl.compute_stake_mults(cards, state, 3, engine="v2")   # flips here
    assert pub == {}, "run 3 flipped direction — streak restarted, no publish"
    e = state["mult_streaks"]["freqtrade-mum|long-momo"]
    assert e["dirn"] == "expand" and e["streak"] == 1
    bl.compute_stake_mults(cards, state, 4, engine="v2")
    pub, _ = bl.compute_stake_mults(cards, state, 5, engine="v2")
    assert pub["freqtrade-mum"]["long-momo"]["mult"] == 1.25   # 3 in the NEW dirn


def test_urgent_fast_path_publishes_on_run_one(scripted_v3):
    # [2026-07-16b] EMER bars skip the streak gate on the FIRST qualifying
    # run — latency only. The key lands in vitals.urgent so brain-vitals
    # surfaces it.
    scripted_v3["verdicts"] = [(0.5, _ev(urgent=True))]
    state = {}
    pub, vit = bl.compute_stake_mults(_cards(45, 5, -80.0), state, 1,
                                      era_trades=ERA, now_ts=1_700_000_000.0,
                                      engine="v3")
    assert pub["freqtrade-mum"]["long-momo"]["mult"] == 0.5
    assert vit["urgent"] == ["freqtrade-mum|long-momo"]
    assert vit["engine"] == "v3"


def test_sticky_within_qualification_no_one_run_flap(scripted_v3, scripted):
    # [2026-07-28 AUDIT FIX] an urgent-published entry that softens past the
    # EMER bar on run 2 (still qualifying, streak 2 < 3) must KEEP publishing
    # — the fast-path is latency-only, not a flap generator.
    scripted_v3["verdicts"] = [(0.5, _ev(urgent=True)), (0.5, _ev())]
    state = {}
    bl.compute_stake_mults(_cards(45, 5, -80.0), state, 1,
                           era_trades=ERA, now_ts=1_700_000_000.0, engine="v3")
    pub, vit = bl.compute_stake_mults(_cards(45, 5, -80.0), state, 2,
                                      era_trades=ERA, now_ts=1_700_000_000.0,
                                      engine="v3")
    assert pub["freqtrade-mum"]["long-momo"]["mult"] == 0.5, "no one-run flap"
    assert vit["urgent"] == [], "run 2 was not urgent — it published as sticky"


def test_kill_switch_honesty_urgent_and_v3_fields_do_not_survive_v2(scripted_v3, scripted):
    # A v3 urgent run, then the operator throws BRAIN_MULT_ENGINE=v2: the
    # entry may keep qualifying via v2, but `urgent` must be RE-EARNED (False
    # under v2) and the v3 evidence keys must be STRIPPED, not dressed on a
    # v2-stamped entry. [2026-07-21 + 2026-07-28 fixes]
    scripted_v3["verdicts"] = [(0.5, _ev(urgent=True))]
    scripted["verdicts"] = [0.5]
    state = {}
    bl.compute_stake_mults(_cards(45, 5, -80.0), state, 1,
                           era_trades=ERA, now_ts=1_700_000_000.0, engine="v3")
    pub, vit = bl.compute_stake_mults(_cards(45, 5, -80.0), state, 2,
                                      engine="v2")
    e = pub["freqtrade-mum"]["long-momo"]
    assert e["engine"] == "v2" and e["urgent"] is False
    assert "post_wr" not in e and "prior_mu" not in e, \
        "v3 evidence keys must not dress a v2-stamped entry"
    assert vit["urgent"] == []
