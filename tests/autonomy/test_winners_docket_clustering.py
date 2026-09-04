"""[2026-09-04 (xy)] THE PRE-REGISTERED FOLLOW-THROUGH IS A CLUSTER-ROBUST TEST.

THE INCIDENT. 👩 mum's LIVE row — real money — carried a pre-registered
follow-through registered 2026-09-02. On 4-Sep the docket read her fresh sample
as **n=18, t=-3.05, -$66.46** and printed NOT_CONFIRMED. **Eight of those
eighteen closes are ONE `daily_loss` halt instant at 2026-09-02T17:19:45,
carrying 67% of the loss.** A flatten writes n rows at one timestamp; they share
that instant's move and are ONE observation, not eight. Clustered by the gate's
own estimator she reads t=-2.72 over **8 close-batches** — below the I16 floor
once the floor is counted on batches rather than rows, i.e. UNDECIDED.

`(xv)` had engraved this the previous day ("one flatten instant is ONE
observation") and the docket could not consume it. Its only independence caveat
counted distinct UTC *dates* and reported "2 close-day(s)" — true, and the wrong
granularity for the question. A finding no gate consumes is a note ((gn)).

THE FIX IS SYMMETRIC, and the positive control is the point: 🎫 the taker's
`exit:hold` follow-through is 24 closes over 23 batches and stays CONFIRMED at
cluster-robust t=+2.67. A guard that only ever refuses is trivially safe and
useless — this one refuses a false condemnation on a halt and a false crown on
an inflated winning batch, and leaves the real confirmation standing.

ONE-OWNER: the arithmetic AND the cluster definition are
`golive_readiness.cluster_stats`/`cluster_se`. `winners_docket.cluster_view`
shapes rows and nothing else — a second copy would let the docket and the gate
disagree about the same ledger ((hj)).
"""
import os
import sys
from datetime import datetime, timedelta, timezone

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))))
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__)))), "scripts"))

import golive_readiness as gr          # noqa: E402
import winners_docket as wd            # noqa: E402

T0 = datetime(2026, 9, 2, 0, 0, 0, tzinfo=timezone.utc)


def _row(pct, minutes, tag="long-x"):
    """A docket bucket row. `pct` is a RATIO, as fetch_paper_trades gives it."""
    return {"pct": pct, "abs": pct * 100.0, "closed": T0 + timedelta(minutes=minutes),
            "tag": tag}


def _spread(pcts, tag="long-x", start=60, step=180):
    """One close per row, each its own batch (steps far exceed CLUSTER_WINDOW_S)."""
    return [_row(p, start + i * step, tag) for i, p in enumerate(pcts)]


def _batch(pcts, minutes, tag="long-x"):
    """Every close at ONE instant — a flatten. One observation, n rows."""
    return [_row(p, minutes, tag) for p in pcts]


# ---------------------------------------------------------------- the owner

def test_cluster_view_defers_to_the_gates_owner_and_does_not_reimplement_it():
    """(hj): the docket must not carry a second copy of the estimator."""
    src = open(wd.__file__).read()
    body = src[src.index("def cluster_view"):src.index("def followthrough")]
    assert "gr.cluster_stats(" in body, "cluster_view must call the gate's owner"
    # The sandwich meat is the thing that gets re-implemented; it must not be here.
    for tell in ("G/(G-1", "g / (g - 1", "n_eff\" :", "sqrt((g /"):
        assert tell not in body, f"docket re-implements the estimator: {tell!r}"


def test_cluster_view_matches_the_owner_called_directly():
    rows = _spread([0.01, -0.02, 0.03, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02, -0.01])
    got = wd.cluster_view(rows)
    pct = [r["pct"] * 100 for r in rows]
    n = len(pct)
    mean = sum(pct) / n
    sd = (sum((x - mean) ** 2 for x in pct) / n) ** 0.5
    want = gr.cluster_stats([(r["pct"] * 100, r["abs"], r["closed"]) for r in rows],
                            mean, sd, n)
    assert got == want


def test_cluster_view_sorts_defensively():
    """`cluster_stats` windows a SEQUENCE; unsorted rows would invent batches."""
    rows = _spread([0.01, -0.02, 0.03, -0.01, 0.02, 0.04, -0.03, 0.01, 0.02, -0.01])
    assert wd.cluster_view(list(reversed(rows))) == wd.cluster_view(rows)


def test_cluster_view_is_none_on_a_shape_the_estimator_cannot_judge():
    """A single batch has no between-cluster variation — absent, never 'fine'."""
    assert wd.cluster_view(_batch([0.01, -0.02, 0.03, 0.04], 60)) is None
    assert wd.cluster_view([]) is None
    assert wd.cluster_view(_spread([0.01])) is None


def test_a_flatten_is_one_batch_not_n():
    clus = wd.cluster_view(_spread([0.01, -0.01, 0.02, -0.02])
                           + _batch([-0.05] * 8, 5000))
    assert clus["n_clusters"] == 5, "8 simultaneous closes are ONE batch"
    assert clus["max_batch"] == 8


# ------------------------------------------------- the verdict is clustered

def _ft(rows, since="2026-09-01T00:00:00+00:00", key=("bot", "book", "*")):
    wd.PRE_REGISTERED[key] = {"since": since, "n": 50, "t": 2.7, "mean_pct": 0.7}
    try:
        return wd.followthrough(key, rows)
    finally:
        wd.PRE_REGISTERED.pop(key, None)


def test_the_incident_a_halt_no_longer_condemns_a_real_money_book():
    """mum's shape: 10 ordinary closes + ONE 8-row flatten carrying the loss.

    iid this is a large negative t on n=18. Clustered it is 11 batches, and the
    verdict must not be driven by the halt."""
    rows = _spread([0.004, -0.003, 0.005, -0.002, 0.003,
                    -0.004, 0.002, 0.001, -0.001, 0.003]) + _batch([-0.055] * 8, 9000)
    ft = _ft(rows)
    assert ft["n"] == 18
    assert ft["t"] < -2.0, "the iid statistic really is this negative"
    assert ft["clus"]["n_clusters"] == 11 and ft["clus"]["max_batch"] == 8
    assert abs(ft["clus"]["t_cluster"]) < abs(ft["t"]), "clustering must deflate |t|"
    assert ft["verdict"] == "not_confirmed"
    assert "cluster-robust" in ft["why"]


def test_the_i16_floor_counts_batches_not_rows():
    """9 ordinary closes + an 8-row flatten is n=17 but only 10 observations...

    ...and one fewer batch is below the floor. Rows must not buy the floor."""
    ordinary = [0.004, -0.003, 0.005, -0.002, 0.003, -0.004, 0.002, 0.001, 0.003]
    over = _ft(_spread(ordinary) + _batch([-0.05] * 8, 9000))
    assert over["clus"]["n_clusters"] == 10 and over["verdict"] != "undecided"
    under = _ft(_spread(ordinary[:-1]) + _batch([-0.05] * 8, 9000))
    assert under["n"] == 16, "still well above MIN_N counted on ROWS"
    assert under["clus"]["n_clusters"] == 9
    assert under["verdict"] == "undecided"
    assert "close-batch" in under["why"]


def test_a_winning_flatten_cannot_crown_a_bucket_either():
    """SYMMETRY. The same inflation with the sign flipped must not CONFIRM."""
    rows = _spread([0.0005, -0.0005] * 5) + _batch([0.06] * 8, 9000)
    ft = _ft(rows)
    assert ft["t"] >= 2.0, "iid, this batch would have crowned it"
    assert ft["verdict"] != "confirmed"


def test_a_genuine_spread_out_winner_is_still_confirmed():
    """THE POSITIVE CONTROL — the taker's shape. A guard that only refuses is
    trivially safe and useless (I3 applied to a gate)."""
    ft = _ft(_spread([0.03, 0.02, 0.04, 0.01, 0.035, 0.025, 0.045, 0.015,
                      0.03, 0.02, 0.04, 0.028]))
    assert ft["clus"]["n_clusters"] == 12 and ft["clus"]["max_batch"] == 1
    assert ft["verdict"] == "confirmed"
    assert "cluster-robust" in ft["why"]


def test_it_is_never_crowned_when_the_cluster_read_is_not_computable():
    """FAIL-CLOSED, and the closed direction is 'never crown'."""
    ft = _ft(_batch([0.05, 0.06, 0.04, 0.05, 0.06, 0.05, 0.04, 0.06,
                     0.05, 0.05, 0.06, 0.04], 9000))
    assert ft["clus"] is None
    assert ft["verdict"] == "undecided"
    assert "not computable" in ft["why"]


def test_an_unregistered_bucket_is_still_none():
    assert wd.followthrough(("nobody", "book", "*"), _spread([0.01] * 12)) is None


def test_no_closes_since_registration_is_undecided():
    ft = _ft(_spread([0.01] * 12), since="2027-01-01T00:00:00+00:00")
    assert ft["verdict"] == "undecided" and ft["n"] == 0


# ------------------------------------------------------- reported everywhere

def test_every_graded_bucket_publishes_its_cluster_read():
    """So the BH referee's own inflation is VISIBLE. The referee still runs on
    the iid p — changing that re-verdicts 42 buckets and needs its own evidence
    pass — but an unpublished number is one nobody can grade next."""
    bk = {("b", "book", "*"): _spread([0.01, -0.02, 0.03, -0.01, 0.02,
                                       0.04, -0.03, 0.01, 0.02, -0.01])}
    g = wd.grade_buckets(bk)[("b", "book", "*")]
    assert "clus" in g and g["clus"]["n_clusters"] == 10


def test_the_report_renders_the_clustered_line_for_a_pre_registered_bucket():
    key = ("b", "book", "*")
    wd.PRE_REGISTERED[key] = {"since": "2026-09-01T00:00:00+00:00",
                              "n": 50, "t": 2.7, "mean_pct": 0.7}
    try:
        txt, _ = wd.report(wd.grade_buckets(
            {key: _spread([0.03, 0.02, 0.04, 0.01, 0.035, 0.025, 0.045,
                           0.015, 0.03, 0.02, 0.04, 0.028])}))
    finally:
        wd.PRE_REGISTERED.pop(key, None)
    assert "CLUSTERED" in txt and "close-batch" in txt


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-q"]))
