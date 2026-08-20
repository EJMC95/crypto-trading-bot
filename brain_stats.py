#!/usr/bin/env python3
"""
brain_stats.py — the brain's statistics engine (v3, 2026-07-16).

Pure functions, stdlib only, no I/O — imported by bot_learn.py (the live
brain) AND brain_replay.py (the validation harness), so a rule change is
always judged on the SAME code that will run it (the lighter_ticket_replay
pattern).

WHAT v3 ADDS OVER THE v2 RAW-COUNT RULES
  1. DECAY WEIGHTING (principled forgetting): every closed trade carries
     weight 2^(-age_days / half_life). A tag that bled three weeks ago but
     trades clean today stops qualifying for a throttle on its own — the
     hard ERA_START cutoff stays (code-era hygiene), decay handles drift
     WITHIN an era. Effective sample size is Kish n_eff = (Σw)²/Σw², which
     is ≤ raw n, so every floor applied to n_eff is stricter than v2.
  2. EMPIRICAL-BAYES POOLING (hierarchical priors): a (bot, tag) win rate
     is shrunk toward its evidence pool — same tag on sibling bots first
     (range_meanrev on georgia informs range_meanrev on intraday-15m),
     else the bot's other tags, else the whole living fleet. Small samples
     get pulled hard toward the pool; big samples barely move. Prior
     strength kappa is bounded so no pool can ever dominate real data.
  3. UNCERTAINTY, NOT POINT ESTIMATES: qualification requires the Wilson
     upper bound of the win rate below a bar AND a weighted t-statistic on
     per-trade PnL below zero — "this tag is bad" must survive its own
     sampling noise, not just print a low percentage once.
  4. RICHER BUCKET METRICS: expectancy in %, profit factor, weighted
     stdev, max consecutive losses — published for the dashboard/board.

WHAT v3 KEEPS UNTOUCHED (the authority contract)
  Reduce-only, never > 1.0x, the raw-count floors (MULT_MIN_N/MULT_SOFT_N
  era trades — the design doc's non-negotiable), the PROMOTE_RUNS
  consecutive-run streak gate, instant forgiveness on disqualification,
  and fleet_bus's [0.5, 1.0] clamp on the consumer side. The upgrade is
  WHICH buckets qualify and the quality of the evidence — not what the
  brain is allowed to do about them.

VALIDATION: brain_replay.py replays the real ledger (3->15 Jul, both
halves) through qualify_v2 and qualify_v3 and compares counterfactual
throttled PnL. Selftest: `python3 brain_stats.py` (synthetic invariants).
"""
import math

# Decay half-life for trade weights (days). Overridable via env in
# bot_learn (BRAIN_HALF_LIFE_DAYS); replay sweeps it.
HALF_LIFE_DAYS = 14.0

# v3 qualification bars. Calibrated on the 3->15 Jul ledger replay so the
# genuine bleeders v2 caught still throttle (rsi-meanrev/donchian era tags)
# while noise-driven qualifications need real evidence. post_wr is the
# EB-shrunk win rate, w_hi the Wilson 80% upper bound on the decayed win
# rate, t the weighted t-stat of per-trade PnL.
Z80 = 1.2816                 # one-sided 90% / two-sided 80% normal quantile
HARD_POST_WR = 0.28          # 0.5x: shrunk wr must sit below this
HARD_W_HI = 0.45             # ...and even the optimistic bound below this
HARD_T = -1.0                # ...and PnL negative at >= 1 sigma
SOFT_POST_WR = 0.42          # 0.75x: the v2 wr<0.40 rule, shrinkage-adjusted
SOFT_W_HI = 0.60
SOFT_T = -0.7
# [2026-07-21 EXPAND — operator: "brain needs to be able to widen too"]
# The MIRROR bars for growing a PROVEN tag above 1.0x. Stricter by design
# than their reduce twins: the condemnation side uses the OPTIMISTIC Wilson
# bound (benefit of the doubt before shrinking someone), the expand side
# uses the PESSIMISTIC one (a raise must survive the worst plausible read).
# No soft-n path (pooling may condemn a thin tag via its family, but praise
# does not inherit — a sibling's win rate is not this tag's), and no EMER
# fast-path (urgency exists to stop bleeding; there is no urgent reason to
# size UP — expand always waits out the full streak gate).
EXP_SOFT_POST_WR = 0.55      # 1.25x: shrunk wr above this...
EXP_SOFT_W_LO = 0.50         # ...with even the pessimistic bound past coin-flip
EXP_SOFT_T = 2.0             # ...and PnL positive at >= 2 sigma
EXP_HARD_POST_WR = 0.60      # 1.5x
EXP_HARD_W_LO = 0.55
EXP_HARD_T = 2.5
# [2026-08-20 (sh)] 2.0x — THE CEILING STEP, and the reason it exists.
#
# **Operator: "training wheels need to go off and they need to start growing
# and learning with the brain that has every loss we've had or win and can let
# the bots adjust themselves accordingly."** Until now the ladder stopped at
# 1.5x, so the brain — which holds every close this fleet has ever made — could
# never express more than "half again" about a book however overwhelming its
# own evidence. 👩 mum measures +4.658%/trade and the most the brain could ever
# say about her was 1.5x. That is a training wheel, not a bar.
#
# THE BAR IS SET WHERE THIS FLEET'S OWN HISTORY PUTS IT. `t >= 3.5` is not a
# round number: it sits ABOVE every headline this fleet has re-measured and
# lost (🧙 Schwager t=1.88 -> "not established"; 📐 Grimes' keltner t=0.49;
# 🧘 Douglas t=0.50) and at-or-below the two that SURVIVED re-measurement
# (🧮 Hull t=+3.92 on n=50, 🌾 carry t=3.10 on n=101). A tier that doubles a
# stake should clear the level where this fleet's claims have historically
# stopped dissolving, and 2.5 is demonstrably not that level.
#
# It is deliberately HARDER than the tier below on every axis — win rate,
# Wilson lower bound, t AND the decayed-evidence floor — so the ladder is
# monotone in strictness, which the selftest pins. SHADOW BOOKS ONLY: no live
# bot reads a brain multiplier, and `fleet_bus.allowed()` clamps every consumer.
EXP_MAX_POST_WR = 0.65       # 2.0x
EXP_MAX_W_LO = 0.60
EXP_MAX_T = 3.5

# [2026-08-20 (si)] **THE RANGE REACHES 6.7x, BOTH WAYS. Eamon, explicitly:
# "The brain needs to be able to go to 6.7x specifically either way now."**
#
# The rungs above 2.0x and below 0.5x are DATA rather than another six
# if-blocks, for one reason: the ladder must be checked STRONGEST-BAR FIRST or
# a tag that clears 6.7x is silently handed 1.25x, and an ordering bug in a
# hand-written chain is invisible. As a table, "monotone in strictness" and
# "checked strongest-first" are both one assertion each — and they are pinned.
#
# Each tuple is (mult, post_wr bar, wilson bar, t bar, n_eff floor). The
# expand side reads `>` on post/wilson and `>=` on t; the reduce side reads
# `<` and `<=`. The two are mirrors: the condemnation side uses the
# OPTIMISTIC Wilson bound (benefit of the doubt before shrinking someone),
# the expand side the PESSIMISTIC one (a raise must survive the worst
# plausible read) — the (bh) asymmetry, unchanged and now extended.
#
# WHAT REACHING THE TOP WOULD COST, said out loud rather than discovered
# later. Only the FAMILY books and the Parliament consume a brain multiplier
# (🌾 carry, 🎫 the taker and ⚖️ Counterweight do not, and no live bot does).
# For a family book that is $50 x 5 slots = $250 gross at 1.0x and **$1,675 on
# a $1,000 book at 6.7x — about 1.7x equity**. The Parliament re-checks its own
# MAX_NOTIONAL against the real multiplied clip, so it is already guarded.
# And the go-live drawdown bar interacts directly: %-drawdown scales with the
# stake, so a book above **15/6.7 = 2.24%** measured maxDD would breach the
# 15% bar at full size. Neither is a reason not to have the range — they are
# what the range means, and they belong beside it.
#
# IT SHIPS INERT. The top rung needs t >= 8.0 on n_eff >= 80; the best book in
# this fleet's history is 🧮 Hull at t=+3.92 on n=50, and 🌾 carry at t=3.10.
# Nothing is close. That is the point of a ceiling: it is where evidence COULD
# take a book, not a value anybody set.
EXPAND_LADDER = (
    #  mult   post   w_lo    t    n_eff
    (   6.7,  0.75,  0.70,  8.0,  80.0),
    (   4.5,  0.72,  0.66,  6.0,  60.0),
    (   3.0,  0.68,  0.63,  4.5,  45.0),
    (   2.0,  EXP_MAX_POST_WR,  EXP_MAX_W_LO,  EXP_MAX_T,  30.0),
)
#: The mirror, below the existing 0.5x rung. Reaching a deep CUT is allowed on
#: slightly thinner evidence than the matching raise (n_eff 30/45/60 against
#: 45/60/80): protecting a book earlier is the asymmetry this fleet already
#: keeps everywhere else, and 1/6.7 is 6.7x "the other way" exactly.
REDUCE_LADDER = (
    #      mult   post   w_hi     t    n_eff
    (1.0 / 6.7,  0.19,  0.34,  -4.0,  60.0),
    (1.0 / 4.5,  0.22,  0.37,  -3.0,  45.0),
    (1.0 / 3.0,  0.25,  0.40,  -2.0,  30.0),
)
MIN_N_EFF_HARD = 18.0        # decayed evidence floor under the raw n>=30 floor
# [(sh)] the 2.0x step needs MORE decayed evidence than 1.5x, not the same
# amount: a book can hold a high `t` on a thin decayed sample, and doubling a
# stake off forgotten trades is the shape this floor exists to refuse.
MIN_N_EFF_MAX = 30.0         # the 2.0x rung's floor; the table below owns
                             # every rung above it
MIN_N_EFF_SOFT = 9.0         # under the raw n>=15 floor
KAPPA_MIN, KAPPA_MAX = 5.0, 15.0
# Family condemnation (soft tier only): when the tag's OWN family is big
# and bad, the bucket's dollar-significance bar relaxes from HARD_T to
# FAM_T — lowered, never removed: the bucket still needs its own negative
# EV. "Big" = pool n_eff >= 30 (hard-tier sample scale carried by the
# family), which under kappa = 5 + 0.2*n_eff means kappa >= 11. (v2 fired
# on the wr level with no significance test at all; this path remains
# stricter.)
FAMILY_BAD_WR = 0.30
FAM_T = -0.5
KAPPA_FAM = 11.0

# [2026-07-16b FAST-PATH] Emergency tier: evidence so overwhelming that the
# PROMOTE_RUNS streak gate protects against nothing (one bad day cannot
# print these numbers), so the throttle publishes on the FIRST qualifying
# run. This reduces LATENCY only — the multiplier grid, reduce-only clamp
# and floors are untouched; authority did not move. Born from the operator's
# 16-Jul "genuine no-brainer window" ask.
EMER_N = 40                  # raw era trades
EMER_N_EFF = 28.0            # decayed evidence floor
EMER_POST_WR = 0.20          # EB-shrunk win rate below even the hard bar
EMER_W_HI = 0.35             # optimistic bound still terrible
EMER_T = -2.5                # dollars negative at >= 2.5 sigma

# Episode grouping for the lens-forward grader: the scout re-emits a live
# ticket every cycle, so raw counts are massively serially correlated
# (~200 emissions of one BTC breakout != 200 samples). A new EPISODE starts
# when the same (lens, sym) has been absent longer than this gap.
EPISODE_GAP_SEC = 1800

# [2026-07-22] Close-burst episode gap for the STAKE-MULT evidence layer
# (the (bb) deferred item, built): a family bot closing five alts on one
# candle — or a strategy twin closing the identical pairs 4 minutes apart
# (dad+breakout-4h, "10 losses ≈ 1 correlated episode") — is ONE market
# event, not five/ten units of evidence. Distinct from EPISODE_GAP_SEC
# (scout re-emissions, 30 min): close bursts are candle-synchronized, so
# 10 min separates distinct 15m bars while collapsing same-event fills.
# bot_learn overrides via BRAIN_EP_GAP_SEC; 0 disables (trade basis).
EPISODE_GAP_CLOSE_SEC = 600.0


# ---------------------------------------------------------------------------
# weighted bucket statistics
# ---------------------------------------------------------------------------

def decay_weight(age_days, half_life=HALF_LIFE_DAYS):
    if age_days is None or age_days < 0:
        age_days = 0.0
    return 2.0 ** (-float(age_days) / float(half_life))


def kish_n_eff(weights):
    """Kish effective sample size: (Σw)² / Σw². Equals n for equal weights."""
    s = sum(weights)
    s2 = sum(w * w for w in weights)
    return (s * s / s2) if s2 > 0 else 0.0


def weighted_bucket(trades, now_ts, half_life=HALF_LIFE_DAYS):
    """Full bucket statistics for a list of closed-trade dicts.

    Returns the v2-compatible raw trio (n, w, pnl) plus the v3 layer:
    n_eff, wr_w, pnl_w (decayed dollars), mean_w/sd_w/t (per-trade $),
    exp_pct (mean profit_ratio, raw), pf (profit factor, raw),
    max_consec_loss. Trades missing close_ts decay as age 0 (no free pass:
    full weight = maximal evidence against themselves too).
    """
    n = len(trades)
    out = {"n": n, "w": 0, "pnl": 0.0, "n_eff": 0.0, "wr_w": 0.0,
           "pnl_w": 0.0, "mean_w": 0.0, "sd_w": 0.0, "t": 0.0,
           "exp_pct": None, "pf": None, "max_consec_loss": 0}
    if not n:
        return out
    ws, pnls, ratios = [], [], []
    gross_win = gross_loss = 0.0
    consec = max_consec = 0
    w_wins = 0.0
    for t in trades:
        p = t.get("profit_abs") or 0.0
        age_days = None
        ct = t.get("_close_epoch")
        if ct is not None and now_ts is not None:
            age_days = max(0.0, (now_ts - ct) / 86400.0)
        w = decay_weight(age_days, half_life)
        ws.append(w)
        pnls.append(p)
        if t.get("profit_ratio") is not None:
            ratios.append(float(t["profit_ratio"]))
        out["pnl"] += p
        if p > 0:
            out["w"] += 1
            w_wins += w
            gross_win += p
            consec = 0
        else:
            gross_loss += -p
            consec += 1
            max_consec = max(max_consec, consec)
    sw = sum(ws)
    out["n_eff"] = round(kish_n_eff(ws), 2)
    out["wr_w"] = (w_wins / sw) if sw > 0 else 0.0
    out["pnl_w"] = sum(w * p for w, p in zip(ws, pnls))
    mean_w = out["pnl_w"] / sw if sw > 0 else 0.0
    var_w = (sum(w * (p - mean_w) ** 2 for w, p in zip(ws, pnls)) / sw) if sw > 0 else 0.0
    sd_w = math.sqrt(var_w)
    out["mean_w"] = mean_w
    out["sd_w"] = sd_w
    ne = out["n_eff"]
    out["t"] = (mean_w / (sd_w / math.sqrt(ne))) if (sd_w > 1e-12 and ne >= 2) else 0.0
    out["exp_pct"] = (sum(ratios) / len(ratios) * 100.0) if ratios else None
    out["pf"] = (gross_win / gross_loss) if gross_loss > 1e-9 else None
    out["max_consec_loss"] = max_consec
    return out


def wilson(p_hat, n_eff, z=Z80):
    """Wilson score interval (lo, hi) on a proportion at effective n."""
    if n_eff <= 0:
        return 0.0, 1.0
    z2 = z * z
    denom = 1.0 + z2 / n_eff
    centre = p_hat + z2 / (2.0 * n_eff)
    spread = z * math.sqrt(p_hat * (1.0 - p_hat) / n_eff + z2 / (4.0 * n_eff * n_eff))
    return max(0.0, (centre - spread) / denom), min(1.0, (centre + spread) / denom)


# ---------------------------------------------------------------------------
# empirical-Bayes hierarchical prior
# ---------------------------------------------------------------------------

def _pool_wr(buckets):
    """(n_eff-weighted win rate, total n_eff) over a list of bucket stats."""
    tot = sum(b["n_eff"] for b in buckets)
    if tot <= 0:
        return None, 0.0
    return sum(b["wr_w"] * b["n_eff"] for b in buckets) / tot, tot


def eb_prior(sibling_buckets, bot_buckets, global_buckets):
    """(mu, kappa, source) — the prior a (bot, tag) bucket shrinks toward.

    Levels, most specific wins: same tag on OTHER bots (n_eff >= 10 pooled),
    else the bot's OTHER tags (n_eff >= 20), else the living fleet
    (n_eff >= 30), else an uninformative 0.45 at minimum strength. Self is
    always excluded from its own prior — pooled evidence must be
    independent of the bucket it judges. kappa grows with pool size but is
    clamped to [KAPPA_MIN, KAPPA_MAX] pseudo-trades so a giant pool can
    never drown a real sample.
    """
    for buckets, floor, src in ((sibling_buckets, 10.0, "tag-family"),
                                (bot_buckets, 20.0, "bot"),
                                (global_buckets, 30.0, "fleet")):
        mu, tot = _pool_wr(buckets or [])
        if mu is not None and tot >= floor:
            kappa = max(KAPPA_MIN, min(KAPPA_MAX, 5.0 + 0.2 * tot))
            return mu, kappa, src
    return 0.45, KAPPA_MIN, "default"


def posterior_wr(wr_w, n_eff, mu, kappa):
    """Beta-binomial posterior mean on decayed counts."""
    if n_eff + kappa <= 0:
        return mu
    return (wr_w * n_eff + mu * kappa) / (n_eff + kappa)


# ---------------------------------------------------------------------------
# qualification policies (the replay compares these head-to-head)
# ---------------------------------------------------------------------------

def qualify_v2(n, w, pnl, min_n=30, soft_n=15):
    """FROZEN 2026-07-14 v2 rule — kept verbatim for replay + kill switch.
        n >= 30, pnl < 0, wr < 25%              -> 0.50x
        n >= 30, pnl < 0, wr < 40%              -> 0.75x
        15 <= n < 30, pnl < 0, wr < 25%         -> 0.75x
    """
    wr = w / n if n else 0.0
    if n >= min_n and pnl < 0 and wr < 0.25:
        return 0.5
    if n >= min_n and pnl < 0 and wr < 0.40:
        return 0.75
    if soft_n <= n < min_n and pnl < 0 and wr < 0.25:
        return 0.75
    return None


def qualify_v3(stats, prior, min_n=30, soft_n=15, expand=False):
    """(mult|None, evidence dict). stats from weighted_bucket, prior from
    eb_prior. Raw-count floors are unchanged from v2 (necessary, never
    sufficient); on top of them the decayed EV must be negative at
    t-stat strength AND the shrunk win rate AND its Wilson upper bound
    must clear the bars. Every number that decided the call is returned
    so the published payload carries its own audit trail.

    [2026-07-21 EXPAND] With expand=True a POSITIVE bucket can qualify for
    1.25x/1.5x on the mirror bars (EXP_*): Wilson LOWER bound, positive t,
    full n floor only, no family inheritance, no urgent path. The caller
    owns the switch (bot_learn: v3 engine AND BRAIN_MULT_EXPAND on) so the
    replay harness and the v2 kill switch both zero the expand side.
    """
    n, n_eff = stats["n"], stats["n_eff"]
    mu, kappa, src = prior
    post = posterior_wr(stats["wr_w"], n_eff, mu, kappa)
    w_lo, w_hi = wilson(stats["wr_w"], n_eff)
    t = stats["t"]
    ev = {"n_eff": round(n_eff, 1), "wr_w": round(stats["wr_w"], 3),
          "post_wr": round(post, 3), "w_hi": round(w_hi, 3),
          "w_lo": round(w_lo, 3),
          "t": round(t, 2), "pnl_w": round(stats["pnl_w"], 2),
          "prior_mu": round(mu, 3), "prior_kappa": round(kappa, 1),
          "prior_src": src, "urgent": False,
          # [2026-07-22] episode basis: how many market EVENTS the evidence
          # fields were computed on (None for plain weighted_bucket callers)
          "n_ep": stats.get("n_episodes")}
    if stats["pnl_w"] >= 0:
        if not expand:
            return None, ev
        # [(sh)/(si)] the ceiling steps FIRST — the ladder is walked
        # strongest-bar down, so a tag that clears 6.7x is never silently
        # handed 1.25x. Table-driven so that ordering is a property of the
        # data and not of a hand-written chain.
        for _m, _pw, _wl, _t, _ne in EXPAND_LADDER:
            if (n >= min_n and n_eff >= _ne and stats["pnl_w"] > 0
                    and post > _pw and w_lo > _wl and t >= _t):
                return _m, ev
        if (n >= min_n and n_eff >= MIN_N_EFF_HARD and stats["pnl_w"] > 0
                and post > EXP_HARD_POST_WR and w_lo > EXP_HARD_W_LO
                and t >= EXP_HARD_T):
            return 1.5, ev
        if (n >= min_n and n_eff >= MIN_N_EFF_HARD and stats["pnl_w"] > 0
                and post > EXP_SOFT_POST_WR and w_lo > EXP_SOFT_W_LO
                and t >= EXP_SOFT_T):
            return 1.25, ev
        return None, ev
    # [(si)] the DEEP cuts first, same strongest-bar-down rule as the expand
    # side. Above the existing 0.5x block so the ordering is total; the 0.5x
    # rung and its EMER fast-path below are untouched.
    for _m, _pw, _wh, _t, _ne in REDUCE_LADDER:
        if (n >= min_n and n_eff >= _ne
                and post < _pw and w_hi < _wh and t <= _t):
            ev["urgent"] = bool(n >= EMER_N and n_eff >= EMER_N_EFF
                                and post < EMER_POST_WR and w_hi < EMER_W_HI
                                and t <= EMER_T)
            return _m, ev
    if (n >= min_n and n_eff >= MIN_N_EFF_HARD
            and post < HARD_POST_WR and w_hi < HARD_W_HI and t <= HARD_T):
        # Emergency fast-path: overwhelming evidence skips the streak gate.
        ev["urgent"] = bool(n >= EMER_N and n_eff >= EMER_N_EFF
                            and post < EMER_POST_WR and w_hi < EMER_W_HI
                            and t <= EMER_T)
        return 0.5, ev
    if (n >= min_n and n_eff >= MIN_N_EFF_HARD
            and post < SOFT_POST_WR and w_hi < SOFT_W_HI and t <= SOFT_T):
        return 0.75, ev
    fam_condemns = (src == "tag-family" and mu < FAMILY_BAD_WR
                    and kappa >= KAPPA_FAM)
    if (soft_n <= n < min_n and n_eff >= MIN_N_EFF_SOFT
            and post < HARD_POST_WR
            and (t <= HARD_T or (fam_condemns and t <= FAM_T))):
        if fam_condemns and t > HARD_T:
            ev["via"] = "family-condemn"
        return 0.75, ev
    return None, ev


# ---------------------------------------------------------------------------
# episode grouping (lens-forward de-correlation)
# ---------------------------------------------------------------------------

def episode_firsts(timestamps, gap_sec=EPISODE_GAP_SEC):
    """Given one (lens, sym)'s emission timestamps (any order), return the
    set of timestamps that START an episode — the moment a taker could
    first have acted on the ticket. Consecutive emissions closer than
    gap_sec are the same market episode, not fresh evidence."""
    firsts, prev = set(), None
    for ts in sorted(timestamps):
        if prev is None or ts - prev > gap_sec:
            firsts.add(ts)
        prev = ts
    return firsts


def cluster_episodes(trades, gap_sec=EPISODE_GAP_CLOSE_SEC):
    """[2026-07-22, the (bb) deferred item] Collapse a bucket's closed
    trades into market-event EPISODES by chain-linked close time: a trade
    whose close falls within gap_sec of the episode's latest close joins
    it, ANY pair — the recorded evidence is time-correlation, not pair
    identity (a multi-pair dump closes on one candle; twins close the
    identical pairs minutes apart). An episode's pseudo-trade: profit_abs
    = Σ members, profit_ratio = Σ members' ratios (the event's total book
    move; None when no member carries one), _close_epoch = the LAST
    member's close (the evidence resolves when the event ends). A
    single-member episode returns the ORIGINAL trade dict, so a bucket
    with no bursts is BIT-IDENTICAL to its trade list. Trades without
    _close_epoch cannot be time-clustered and stay single-trade episodes
    (no free correlation assumption in either direction). gap_sec <= 0 or
    None disables. Pure; order-independent; mutates nothing."""
    if not gap_sec or gap_sec <= 0:
        return list(trades)
    timed = [t for t in trades if t.get("_close_epoch") is not None]
    untimed = [t for t in trades if t.get("_close_epoch") is None]
    groups, cur = [], []
    for t in sorted(timed, key=lambda x: x["_close_epoch"]):
        if cur and t["_close_epoch"] - cur[-1]["_close_epoch"] > gap_sec:
            groups.append(cur)
            cur = []
        cur.append(t)
    if cur:
        groups.append(cur)
    out = []
    for grp in groups:
        if len(grp) == 1:
            out.append(grp[0])
            continue
        ratios = [t["profit_ratio"] for t in grp
                  if t.get("profit_ratio") is not None]
        out.append({"profit_abs": sum((t.get("profit_abs") or 0.0)
                                      for t in grp),
                    "profit_ratio": sum(ratios) if ratios else None,
                    "_close_epoch": grp[-1]["_close_epoch"],
                    "_n_trades": len(grp)})
    return out + untimed


def weighted_bucket_episodes(trades, now_ts, half_life=HALF_LIFE_DAYS,
                             gap_sec=EPISODE_GAP_CLOSE_SEC):
    """weighted_bucket with the v3 STATISTICAL layer computed on EPISODES.

    The raw-count fields keep their TRADE meaning — n/w/pnl (qualify_v3's
    raw floors read stats['n']: the design doc's non-negotiable, unmoved),
    exp_pct, pf, max_consec_loss. The evidence fields — n_eff, wr_w,
    pnl_w, mean_w, sd_w, t — come from the episode bucket: ten fills of
    one market event are ONE unit of evidence, for a condemnation AND for
    a raise (the (bh) expand bars inherit the same protection — a
    correlated win-burst cannot inflate its own t-stat). Episode decay
    weighs at the event's last close; members span minutes, so the skew
    vs per-trade decay is negligible and documented rather than modeled.
    Adds n_episodes. gap_sec=0 (or a burst-free bucket) is BIT-IDENTICAL
    to weighted_bucket — the knob is its own kill switch."""
    base = weighted_bucket(trades, now_ts, half_life)
    eps = cluster_episodes(trades, gap_sec)
    base["n_episodes"] = len(eps)
    if len(eps) == len(trades):
        return base
    ep = weighted_bucket(eps, now_ts, half_life)
    for k in ("n_eff", "wr_w", "pnl_w", "mean_w", "sd_w", "t"):
        base[k] = ep[k]
    return base


# ---------------------------------------------------------------------------
# selftest
# ---------------------------------------------------------------------------

def _selftest():
    now = 1_800_000_000.0
    mk = lambda pnl, days_ago, ratio=None: {
        "profit_abs": pnl, "profit_ratio": ratio,
        "_close_epoch": now - days_ago * 86400}

    # Kish: equal weights -> n_eff == n; skewed weights -> n_eff < n.
    assert abs(kish_n_eff([1, 1, 1, 1]) - 4.0) < 1e-9
    assert kish_n_eff([1, 0.05, 0.05, 0.05]) < 2.0

    # Decay: a fresh loss outweighs an old one; n_eff <= n always.
    fresh = weighted_bucket([mk(-5, 0)] * 10 + [mk(5, 40)] * 10, now)
    assert fresh["pnl"] == 0.0 and fresh["pnl_w"] < 0      # raw flat, decayed negative
    assert fresh["n_eff"] <= fresh["n"]

    # Forgiveness: an old bleed + clean present flips decayed EV positive.
    # Raw: n=19, wr=3/19=16% < 25%, pnl -$47.5 -> v2 soft-throttles 0.75x.
    healed = weighted_bucket([mk(-4, 35)] * 16 + [mk(5.5, 1)] * 3, now)
    assert healed["pnl"] < 0 < healed["pnl_w"]
    assert qualify_v3(healed, (0.4, 8.0, "test"))[0] is None   # v3 forgives
    assert qualify_v2(healed["n"], healed["w"], healed["pnl"]) == 0.75  # v2 wouldn't

    # Wilson: bounds tighten with n, contain p_hat.
    lo1, hi1 = wilson(0.2, 10)
    lo2, hi2 = wilson(0.2, 100)
    assert lo1 <= 0.2 <= hi1 and (hi2 - lo2) < (hi1 - lo1)

    # EB shrinkage: small sample pulled toward pool, big sample barely moves.
    assert abs(posterior_wr(0.1, 5, 0.5, 10) - 0.1) > abs(posterior_wr(0.1, 200, 0.5, 10) - 0.1)
    # Prior level selection + kappa clamp.
    big = [{"wr_w": 0.6, "n_eff": 500.0}]
    mu, kappa, src = eb_prior(big, [], [])
    assert src == "tag-family" and kappa == KAPPA_MAX
    assert eb_prior([], [], [])[2] == "default"

    # v3 throttles a genuine persistent bleeder at sample size...
    bad = weighted_bucket([mk(-3, d % 10, -0.02) for d in range(34)]
                          + [mk(2, d % 10, 0.01) for d in range(4)], now)
    m, ev = qualify_v3(bad, eb_prior([], [], []))
    # [2026-08-20 (si)] WAS 0.5 — this case now reaches the 1/3 rung, and the
    # change is the instruction working rather than a regression. Its own
    # evidence is overwhelming (t=-9.16, post_wr 0.157, Wilson UPPER 0.202 on
    # n_eff 37.3): before the range reached 6.7x either way, the deepest the
    # brain could cut a bleeder like this was HALF, whatever it knew. It clears
    # 1/3 (post<0.25, w_hi<0.40, t<=-2.0, n_eff>=30) and stops there because
    # n_eff 37.3 is short of the 45 and 60 the deeper rungs require — the
    # evidence floor doing exactly its job.
    assert m == round(1.0 / 3.0, 10) or abs(m - 1.0 / 3.0) < 1e-9, (m, ev)
    assert ev["t"] < -4 and ev["n_eff"] < 45, ev
    # ...never emits anything above 0.75 (reduce-only grid), and never
    # fires on a small noisy sample even when the point estimate looks bad.
    noisy = weighted_bucket([mk(-1, 1)] * 7 + [mk(1.5, 1)] * 3, now)
    assert qualify_v3(noisy, (0.45, 8.0, "test"))[0] is None
    for f in (qualify_v2, ):
        assert f(40, 5, -10.0) == 0.5 and f(40, 14, -10.0) == 0.75
    assert all(x in (None, 0.5, 0.75) for x in
               [qualify_v2(n, w, p) for n in (5, 20, 40) for w in (0, 10) for p in (-5, 5)])

    # [2026-07-21 EXPAND] two-way mults: the mirror bars.
    # A strong fresh winner clears the 1.5x hard bar — but ONLY when the
    # caller arms expand; the default path preserves the reduce-only grid.
    strong = weighted_bucket([mk(2.0, d % 3, 0.02) for d in range(26)]
                             + [mk(-1.0, d % 3, -0.01) for d in range(4)], now)
    assert qualify_v3(strong, eb_prior([], [], []))[0] is None  # default: no expand
    m_s, ev_s = qualify_v3(strong, eb_prior([], [], []), expand=True)
    assert m_s == 1.5, (m_s, ev_s)
    assert ev_s["urgent"] is False        # expand never fast-paths
    # A decent-but-not-overwhelming winner lands the 1.25x soft step (its
    # pessimistic Wilson bound clears coin-flip but not the 0.55 hard bar).
    decent = weighted_bucket([mk(1.0, d % 3, 0.01) for d in range(19)]
                             + [mk(-0.6, d % 3, -0.006) for d in range(11)], now)
    m_dc, ev_dc = qualify_v3(decent, eb_prior([], [], []), expand=True)
    assert m_dc == 1.25, (m_dc, ev_dc)
    # Small positive samples never expand (full n floor, no soft-n path)...
    small_win = weighted_bucket([mk(1.5, 1)] * 12 + [mk(-0.5, 1)] * 3, now)
    assert qualify_v3(small_win, eb_prior([], [], []), expand=True)[0] is None
    # ...and family praise does NOT inherit: a mediocre own sample under a
    # glowing tag-family prior stays at 1.0 (w_lo + t are own-sample bars).
    mediocre = weighted_bucket([mk(0.8, 1) if i % 2 == 0 else mk(-0.8, 1)
                                for i in range(30)], now)
    assert qualify_v3(mediocre, (0.85, KAPPA_MAX, "tag-family"),
                      expand=True)[0] is None
    # Reduce side is untouched by the EXPAND SWITCH — that is the property
    # here, not the value: throwing the expand kill switch must not change
    # what a bleeder gets. [(si)] the value is now 1/3, and it is the SAME
    # either way, which is what this line has always been about.
    assert qualify_v3(bad, eb_prior([], [], []), expand=True)[0] == m

    # Family condemnation: weak own dollars (t between FAM_T and HARD_T)
    # fire ONLY when the tag family is big and bad — and never on the
    # hard tier, never with positive own EV.
    # 3 wins / 12 losses -> t ~= -0.83: between FAM_T and HARD_T by design.
    weak = weighted_bucket([mk(1.0, 1) if i % 5 == 0 else mk(-0.4, 1)
                            for i in range(15)], now)
    assert HARD_T < weak["t"] <= FAM_T, weak["t"]
    m_no, _ = qualify_v3(weak, (0.20, KAPPA_MAX, "bot"))       # wrong level
    m_yes, ev_yes = qualify_v3(weak, (0.20, KAPPA_MAX, "tag-family"))
    m_small, _ = qualify_v3(weak, (0.20, KAPPA_MIN, "tag-family"))  # small pool
    assert m_no is None and m_small is None and m_yes == 0.75, (m_no, m_yes, m_small)
    assert ev_yes.get("via") == "family-condemn"

    # Fast-path: a catastrophic fresh bleeder is URGENT; the ordinary
    # bleeder from above is NOT (streak gate still applies to it).
    disaster = weighted_bucket([mk(-2.0, 0.2)] * 42 + [mk(1.0, 0.2)] * 4, now)
    m_d, ev_d = qualify_v3(disaster, eb_prior([], [], []))
    # [(si)] 1/4.5 now, not 0.5 — and the pair below is the property worth
    # having: `disaster` (t=-13.95, n_eff 46.0) is cut DEEPER than `bad`
    # (t=-9.16, n_eff 37.3). Before the range reached 6.7x either way both got
    # exactly HALF, so the brain could see the difference between them and had
    # no way to say it.
    assert abs(m_d - 1.0 / 4.5) < 1e-9 and ev_d["urgent"] is True, (m_d, ev_d)
    m_b, ev_b = qualify_v3(bad, eb_prior([], [], []))
    # [(si)] the ordinary bleeder is 1/3 now, and still NOT urgent — the
    # streak gate applies to it. The deep rungs inherit the same EMER test as
    # the 0.5x rung, so "how deep" and "how fast" stay independent.
    assert abs(m_b - 1.0 / 3.0) < 1e-9 and ev_b["urgent"] is False, ev_b
    assert m_d < m_b, (
        "the worse bleeder must be cut deeper — if these collapse to one "
        "value the ladder has stopped discriminating and the range is decoration")

    # Episodes: 3 tight emissions + one after a gap = 2 episodes.
    f = episode_firsts([0, 60, 120, 9000])
    assert f == {0, 9000}

    # [2026-07-22] CLOSE-BURST EPISODE BASIS (the (bb) deferred item).
    # Identity: a burst-free bucket is BIT-IDENTICAL to the trade basis.
    spread = [mk(-2.0, d) for d in range(20)] + [mk(1.0, d + 0.5) for d in range(8)]
    wb, wbe = weighted_bucket(spread, now), weighted_bucket_episodes(spread, now)
    assert wbe.pop("n_episodes") == len(spread) and wbe == wb, "identity broken"
    # gap 0 disables even on a burst
    burst_day = 3.0
    burst = ([mk(-2.0, burst_day + i * 1e-4) for i in range(10)]
             + [mk(1.5, 10 + d) for d in range(4)])
    z = weighted_bucket_episodes(burst, now, gap_sec=0)
    assert z["n_episodes"] == len(burst)
    # a 10-fill burst is ONE event: raw n keeps the trade count (floors
    # unmoved), the evidence layer collapses
    be = weighted_bucket_episodes(burst, now)
    assert be["n"] == 14 and be["n_episodes"] == 5, be["n_episodes"]
    assert be["n_eff"] < weighted_bucket(burst, now)["n_eff"] / 2
    assert be["pnl"] == weighted_bucket(burst, now)["pnl"], "raw $ untouched"
    # cluster mechanics: ratios sum, last close stamps, member count kept,
    # untimed trades stay singles, pair-blind chaining
    grp = cluster_episodes([
        {"profit_abs": -1.0, "profit_ratio": -0.01, "_close_epoch": 1000},
        {"profit_abs": -2.0, "profit_ratio": None, "_close_epoch": 1200},
        {"profit_abs": 3.0, "profit_ratio": 0.03, "_close_epoch": 1500},
        {"profit_abs": 9.0, "profit_ratio": 0.09, "_close_epoch": 99999},
        {"profit_abs": 5.0, "profit_ratio": 0.05}])
    assert len(grp) == 3, grp
    e0 = [g for g in grp if g.get("_n_trades")][0]
    assert e0["profit_abs"] == 0.0 and abs(e0["profit_ratio"] - 0.02) < 1e-9
    assert e0["_close_epoch"] == 1500 and e0["_n_trades"] == 3
    assert {g["profit_abs"] for g in grp} == {0.0, 9.0, 5.0}
    # THE RECORDED CASE, both directions. dad+breakout-4h's "10 losses in
    # 4 minutes": on the trade basis this bucket condemns; on the episode
    # basis 5 events cannot clear the bars — the burst may not condemn...
    burst_bad = ([mk(-2.0, 2.0 + i * 1e-4) for i in range(14)]
                 + [mk(-2.0, 5.0 + i * 1e-4) for i in range(14)]
                 + [mk(1.0, 8 + d * 0.5) for d in range(5)])
    tb = weighted_bucket(burst_bad, now)
    assert qualify_v3(tb, eb_prior([], [], []), min_n=30, soft_n=15)[0] is not None, \
        "fixture must condemn on the trade basis or it proves nothing"
    eb = weighted_bucket_episodes(burst_bad, now)
    m_eb, ev_eb = qualify_v3(eb, eb_prior([], [], []), min_n=30, soft_n=15)
    assert m_eb is None and ev_eb["n_ep"] == 7, (m_eb, ev_eb)
    # ...and the MIRROR: a correlated WIN-burst may not buy a raise (the
    # (bh) expand bars inherit the same de-correlation), while the same
    # totals spread out still can.
    # (0.35d spacing — genuinely spread in CLOSE time; the (bh) fixture's
    # `d % 3` ages put 30 trades on 3 epochs, which IS a burst here)
    win_spread = ([mk(2.0, d * 0.35, 0.02) for d in range(26)]
                  + [mk(-1.0, 9 + d * 0.35, -0.01) for d in range(4)])
    assert qualify_v3(weighted_bucket_episodes(win_spread, now),
                      eb_prior([], [], []), expand=True)[0] == 1.5, \
        "spread winners must still expand on the episode basis"
    win_burst = ([mk(2.0, 1.0 + i * 1e-4, 0.02) for i in range(26)]
                 + [mk(-1.0, 5 + d, -0.01) for d in range(4)])
    assert qualify_v3(weighted_bucket(win_burst, now),
                      eb_prior([], [], []), expand=True)[0] is not None, \
        "fixture must expand on the trade basis or it proves nothing"
    assert qualify_v3(weighted_bucket_episodes(win_burst, now),
                      eb_prior([], [], []), expand=True)[0] is None, \
        "one lucky market event bought a 1.5x raise"

    print("brain_stats selftest OK (incl. close-burst episode basis: "
          "identity, gap-0 kill, raw-floor preservation, recorded "
          "dad+breakout case, expand mirror)")


if __name__ == "__main__":
    _selftest()
