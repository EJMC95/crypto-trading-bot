"""The sentinel's bias must price its own graded record — measured EDGE, not hit rate.

THE MEASUREMENT (2026-08-05, live payload + STUDY_CONSENSUS_GATE (ji)): the
sentinel's three highest-n playbooks graded ANTI-predictive — regulation
crackdown 0.19 hit over n=85, geopolitical shock 0.24/n=83, exchange incident
0.34/n=87 — yet each kept `hit_rate` worth of its full fear forever, because
`blended_bias` used the EB posterior of HIT RATE as the anticipation's
weight. The informative zero of a DIRECTIONAL call is a coin flip (0.5), not
0 — I15's win-rate/expectancy non-sequitur, sitting inside an organ.
Measured consequence ((ji)): market bias ≤ −0.5 for 91.3% of 2,399 samples
and ≥ +0.5 for 0.0% — a constant, and a constant gates nothing (I7). The
organ's risk-on proposal path (bias ≥ +0.3 AND a graded-accurate playbook)
was unreachable by construction while its risk-off crouch re-proposed
forever: the panic was structural, not observed.

THE RULE under test ((jv)):
    weight = (prior_conf·PE + max(0, 2·hit − n)) / (PE + n)
— at n=0 the playbook prior applies UNCHANGED (priors are deliberately
modest soft weights, not probability claims); as n grows the weight
converges to max(0, 2·hit/n − 1), so an at-or-below-coin-flip record
SILENCES its playbook while an accurate one keeps its measured edge; the
weight never crosses zero, so direction never auto-flips (operator review
owns that). `conf` (second return) stays the EB posterior hit estimate.

Fixture honesty ((hj)): the `observed` structure is built by the REAL grader
(`grade_events`) wherever the shape matters — a consumer is tested against a
payload its publisher built, never a hand-written lookalike.
"""
import event_sentinel as es


PE = es.PRIOR_EPISODES
SEV = 0.9
DAY = 24 * 3600


# ------------------------------------------------------------ real grader --
def _graded_observed(etype, n, hits, bias=-0.4):
    """Build `observed` for {etype}|all|24 through grade_events itself:
    one event per episode, sector index rising (a MISS for a bearish bias)
    or falling (a HIT), spaced so only the 24h horizon can grade."""
    events, cache, observed = {}, [], {}
    for i in range(n):
        t0 = i * 200_000                      # >> tol + 24h: no cross-match
        hit = i < hits
        events[f"e{i}"] = {"type": etype, "first_seen_ts": t0,
                           "pred": {"all": {"bias": bias, "conf": 0.6}}}
        cache.append({"ts": t0, "idx": {"all": 100.0}})
        end = 97.0 if (hit == (bias < 0)) else 103.0
        cache.append({"ts": t0 + DAY, "idx": {"all": end}})
    graded = es.grade_events(events, cache, observed, now_ts=n * 200_000 + DAY)
    key = f"{etype}|all|24"
    assert graded == n and observed[key]["n"] == n, (graded, observed)
    assert observed[key]["hit"] == hits, observed
    return observed


def _prior_row(etype, sector="all"):
    d, c, _hl = es.EVENT_TYPES[etype]["playbook"][sector]
    return d, c


# ----------------------------------------------------------------- silence --
def test_record_refuted_fear_is_silenced():
    """hit 6/30 (0.20 — crackdown's live grade to the decimal): the weight
    must collapse to the washing-out prior, NOT to the 0.2 hit rate.
    Mutation this kills: reverting the weight to `conf`."""
    obs = _graded_observed("regulation_crackdown", 30, 6)
    b_ref, _ = es.blended_bias("regulation_crackdown", "all", SEV, obs)
    b_pri, _ = es.blended_bias("regulation_crackdown", "all", SEV, {})
    assert b_pri < 0                          # the prior fear itself stands
    assert abs(b_ref) <= abs(b_pri) * 0.2, (b_ref, b_pri)


def test_coin_flip_record_earns_nothing():
    """hit = n/2 must not retain half the fear the way hit-rate weighting
    did — a coin flip is the zero of a directional record."""
    obs = _graded_observed("regulation_crackdown", 60, 30)
    b_coin, _ = es.blended_bias("regulation_crackdown", "all", SEV, obs)
    b_pri, _ = es.blended_bias("regulation_crackdown", "all", SEV, {})
    assert abs(b_coin) <= abs(b_pri) * 0.15, (b_coin, b_pri)


def test_direction_never_flips_whatever_the_record_says():
    """A playbook measured BACKWARDS (2/40) reads ~zero, never positive:
    the record's reversal is surfaced by its grade, not traded in reverse.
    Mutation this kills: dropping the max(0, ·) floor."""
    obs = _graded_observed("regulation_crackdown", 40, 2)
    b, _ = es.blended_bias("regulation_crackdown", "all", SEV, obs)
    assert b <= 0.0, b                        # bearish playbook: never > 0
    assert abs(b) <= 0.05, b                  # and effectively silent


# ------------------------------------------------------------------- voice --
def test_accurate_playbook_keeps_and_grows_its_voice():
    """easing 19/20 (its live grade is 0.95/n=21): the earned weight must
    EXCEED the prior-only weight — accuracy buys reach, per I16's shape."""
    obs = _graded_observed("monetary_easing", 20, 19, bias=+0.4)
    b_earn, c_earn = es.blended_bias("monetary_easing", "all", 0.8, obs)
    b_pri, _ = es.blended_bias("monetary_easing", "all", 0.8, {})
    assert b_earn > b_pri > 0, (b_earn, b_pri)
    assert c_earn > 0.8, c_earn


def test_priors_apply_unchanged_at_n0():
    """Every playbook row at n=0 must return exactly (dir·sev·prior, prior):
    the taxonomy's modest soft weights are deliberately NOT re-scored
    against the coin flip. Mutation this kills: applying the edge map to
    the prior term (which would mute most of the taxonomy at birth)."""
    for etype, spec in es.EVENT_TYPES.items():
        for sector, (d, c, _hl) in spec["playbook"].items():
            b, conf = es.blended_bias(etype, sector, 1.0, {})
            assert b == round(d * c, 3), (etype, sector, b)
            assert conf == round(c, 3), (etype, sector, conf)


def test_conf_stays_the_posterior_hit_estimate():
    """The second return is the honest hit-rate posterior, untouched by the
    edge map — the grades card keeps reporting how often the playbook is
    RIGHT, while bias reports how much that is WORTH."""
    obs = _graded_observed("regulation_crackdown", 30, 6)
    d, prior = _prior_row("regulation_crackdown")
    _, conf = es.blended_bias("regulation_crackdown", "all", SEV, obs)
    assert conf == round((prior * PE + 6) / (PE + 30), 3), conf


# ------------------------------------------------------------ reachability --
def test_risk_on_bar_is_reachable_when_records_diverge():
    """The (ji) constant escapes: with the fleet's ACTUAL grade shape — one
    accurate positive playbook active beside THREE record-refuted fear
    playbooks — the summed 'all' bias must clear the +0.3 risk-on bar.
    Under hit-rate weighting the refuted trio held the door shut (their
    residual ~0.2–0.35 weights summed past the easing signal); enactment
    stays with the scout tuner's replay gate either way."""
    biases = [
        es.blended_bias("monetary_easing", "all", 0.8,
                        _graded_observed("monetary_easing", 20, 19,
                                         bias=+0.4))[0],
        es.blended_bias("regulation_crackdown", "all", SEV,
                        _graded_observed("regulation_crackdown", 30, 6))[0],
        es.blended_bias("geopolitical_shock", "all", SEV,
                        _graded_observed("geopolitical_shock", 30, 7))[0],
        es.blended_bias("exchange_incident", "all", SEV,
                        _graded_observed("exchange_incident", 30, 10))[0],
    ]
    total = max(-1.0, min(1.0, sum(biases)))      # the publish-loop clamp
    assert total >= 0.3, (total, biases)
