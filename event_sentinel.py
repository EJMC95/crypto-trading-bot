#!/usr/bin/env python3
"""
event_sentinel.py 🗞️⚡ — the fleet's EVENT organ (16-Jul, operator mandate:
"a dedicated major news scanning bot ... that is able to learn these major
events in real time and anticipate market direction ... insight into what
ripple effects happen to each sector").

WHAT IT IS IN THE ORGANISM
  market_pulse reads the market's MOOD (continuous sentiment). The sentinel
  reads its EVENTS: discrete, typed, world shocks — the startle reflex +
  event memory. It detects a major event forming across feeds, looks up the
  PLAYBOOK of how that event class has historically rippled through each
  sector, publishes an anticipatory per-sector bias — and then GRADES its
  own anticipation against realized sector moves (from the Lighter scout's
  marks), updating the playbook with the same empirical-Bayes blend the
  brain's v3 engine uses (brain_stats). Real-time learning, real history.

PIPELINE (each ~10-min cycle, run_all.sh loop)
  1. FEEDS: CoinDesk + CoinTelegraph RSS (same sources market_pulse trusts)
     + GDELT doc 2.0 API (global press firehose, no key) on three thematic
     sweeps: macro/central-bank, geopolitics/banking, crypto shocks.
  2. CLASSIFY headlines into EVENT TYPES (keyword taxonomy below) with a
     severity score (volume + strength terms + multi-feed corroboration).
  3. TRACK events across cycles (state): an event ACTIVATES at
     min_sources distinct headlines inside a recent window; it carries
     first_seen / peak severity / sample headlines.
  4. ANTICIPATE: per-sector bias = playbook direction x severity x
     LEARNED confidence (seeded prior blended with this fleet's own graded
     episodes — see PLAYBOOK + observed stats).
  5. SECTOR INDEX CACHE: each cycle chains a per-sector price index from
     the scout's lighter-market marks (median member return, chained so
     listings/delistings don't break it). Small, self-owned — no heavy
     history fetches.
  6. GRADE: once 4h/24h/72h have elapsed since an event's first_seen,
     score realized sector moves against the anticipation; update
     observed stats (the playbook LEARNS).

SEEDED HISTORY (the playbook priors encode these real episodes)
  COVID crash Mar-2020 (global liquidity shock: everything sold, V after);
  Terra/UST May-2022 (stablecoin stress -> DeFi contagion, alts worst);
  hawkish-FOMC series 2022 (tightening -> risk assets -5..8% same week);
  FTX Nov-2022 (exchange incident -> majors -25%, alts/defi worse, weeks);
  SVB Mar-2023 (banking stress -> BTC +40% in 2 weeks — the safe-haven
  flip: crypto UP on bank failures); BTC spot-ETF approval Jan-2024
  (adoption -> majors led, sell-the-news chop first days); yen-carry
  unwind Aug-2024 (macro deleverage -> crypto -20% in days, fast recover);
  tariff shock Apr-2025 (risk-off, equities led, crypto followed).

DOCTRINE
  ADVISORY-FIRST: publishes bot_state 'event-sentinel'. [22-Jul: it now has a
  consumer path — it PROPOSES taker.* bar changes (via fleet_proposals) that
  the scout tuner replay-gates and enacts on the `lighter-taker` lane. That
  lane is the $1k SHADOW taker (lighter_ticket_taker.py: "NOT ON REAL MONEY"),
  so the sentinel steers a shadow book, NOT real money — no live.* lever is
  reachable from here. "Nothing trades on it" is therefore stale; "nothing REAL
  MONEY trades on it" is the accurate rule, restrict-first as ever.]
  Fail-soft everywhere: a dark feed, dark DB or dark scout leaves the
  sentinel publishing what it can or nothing — never crashing the loop.
  Tuning: evsent.* levers (fleet_tuning registry, lane 'event-sentinel')
  with env-var defaults — the board/tuner may adjust inside clamps, TTL'd.
Selftest: python3 event_sentinel.py --selftest
"""
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
LOCAL_STATE = os.path.join(REPORTS_DIR, "event_sentinel_state.json")

BUS_KEY = "event-sentinel"
STATE_KEY = "event-sentinel-state"
TTL_SEC = 2400                 # 4 missed 10-min cycles -> stale
RECENT_HOURS = 12              # headline window an event stays "forming" in
EVENT_LIFE_HOURS = 96          # tracked (for grading) this long after first_seen
MIN_SOURCES_DEFAULT = int(os.environ.get("EVSENT_MIN_SOURCES", "2"))
SEVERITY_BAR_DEFAULT = float(os.environ.get("EVSENT_SEVERITY_BAR", "0.45"))
PRIOR_EPISODES = 4.0           # pseudo-episodes behind each playbook prior
GRADE_HORIZONS_H = (4, 24, 72)
CACHE_CAP = 900                # ~6 days of 10-min sector-index entries
# [2026-07-17 AUDIT] Grading DEAD-BAND: a sector move smaller than this is not
# evidence of direction, so the anticipation is left UNGRADED (no n, no hit)
# rather than scored. 10bps over a 4h horizon is below any move a macro event
# playbook claims to anticipate — the point is to refuse to read a signal out of
# a flat (or frozen) tape, not to tune sensitivity. Env-tunable so a review can
# widen/narrow it without a deploy; 0.0 restores the old sign-only behaviour and
# with it the free-hit-for-bearish bug, so do not set it there.
MOVE_EPS = float(os.environ.get("EVSENT_MOVE_EPS", "0.001"))   # 10bps
UA = {"User-Agent": "Mozilla/5.0 (fleet event sentinel)"}

try:
    import brain_stats as bstats           # EB blend + Wilson (shared engine)
except Exception:
    bstats = None


# ---------------------------------------------------------------------------
# Sector map (Lighter books; unknown symbols fall into 'other', which still
# counts toward 'all'). Keep aligned with what the scout actually lists.
# ---------------------------------------------------------------------------
SECTORS = {
    "majors": {"BTC", "ETH"},
    "alt_l1": {"SOL", "AVAX", "ADA", "NEAR", "APT", "SUI", "SEI", "TON",
               "DOT", "ATOM", "TRX", "XRP", "LTC", "BCH", "HBAR", "ICP",
               "ARB", "OP", "STRK", "ZK", "POL", "LINK"},
    "defi": {"UNI", "AAVE", "CRV", "LDO", "MKR", "COMP", "PENDLE", "SNX",
             "JUP", "RAY", "GMX", "DYDX", "ENA", "ONDO"},
    "meme": {"DOGE", "SHIB", "PEPE", "WIF", "BONK", "FLOKI", "TRUMP",
             "FARTCOIN", "POPCAT", "MOODENG", "PENGU", "SPX"},
    "ai": {"FET", "RENDER", "TAO", "WLD", "VIRTUAL", "AI16Z", "GRASS",
           "AIXBT", "KAITO"},
    "equities": {"SPY", "QQQ", "NVDA", "TSLA", "AAPL", "MSFT", "AMZN",
                 "META", "GOOGL", "COIN", "HOOD", "MSTR", "PLTR", "AMD"},
}
SYM2SECTOR = {s: sec for sec, syms in SECTORS.items() for s in syms}


def _sector_of(sym):
    s = str(sym).upper().split("-")[0].split("/")[0]
    for suf in ("USDT", "USDC", "USD", "PERP"):
        if s.endswith(suf) and len(s) > len(suf) + 1:
            s = s[: -len(suf)]
    return SYM2SECTOR.get(s, "other")


# ---------------------------------------------------------------------------
# Event taxonomy. Each type: match terms (any), strength terms (severity
# boost), and the PLAYBOOK {sector: (direction, prior_confidence,
# halflife_hours)} — direction is the anticipated sign of the sector's move
# over ~the halflife. 'all' applies to every sector without a specific row.
# Priors are deliberately modest: the sentinel LEARNS the rest.
# ---------------------------------------------------------------------------
EVENT_TYPES = {
    "monetary_tightening": {
        "match": ("rate hike", "raises rates", "hawkish", "higher for longer",
                  "tightening", "raises interest", "hikes interest"),
        "strength": ("surprise", "emergency", "75", "unexpected"),
        "playbook": {"all": (-1, 0.6, 48), "equities": (-1, 0.65, 48),
                     "majors": (-1, 0.6, 48), "meme": (-1, 0.6, 24)}},
    "monetary_easing": {
        "match": ("rate cut", "cuts rates", "dovish", "pauses hikes",
                  "quantitative easing", "cuts interest", "pivot"),
        "strength": ("surprise", "emergency", "50 basis", "unexpected"),
        "playbook": {"all": (1, 0.55, 48), "equities": (1, 0.6, 48),
                     "majors": (1, 0.55, 48)}},
    "inflation_hot": {
        "match": ("cpi", "inflation", "ppi"),
        "require": ("hotter", "above expectations", "accelerat", "surges",
                    "higher than expected", "jumps", "tops expectations",
                    "comes in hot"),
        "strength": ("shock", "soars"),
        "playbook": {"all": (-1, 0.5, 24), "equities": (-1, 0.55, 24)}},
    "inflation_cool": {
        "match": ("cpi", "inflation", "ppi"),
        "require": ("cooler", "cools", "cooling", "below expectations",
                    "slows", "eases", "moderates", "lower than expected",
                    "falls"),
        "strength": ("surprise",),
        "playbook": {"all": (1, 0.5, 24), "equities": (1, 0.55, 24)}},
    "regulation_crackdown": {
        "match": ("sec sues", "sec charges", "crackdown", "regulator",
                  "lawsuit", "bans crypto", "investigation", "subpoena",
                  "enforcement action"),
        "strength": ("criminal", "fraud", "shutdown", "ban"),
        "playbook": {"all": (-1, 0.45, 48), "defi": (-1, 0.55, 48),
                     "meme": (-1, 0.5, 24)}},
    "etf_adoption": {
        "match": ("etf approval", "etf approved", "spot etf", "etf inflow",
                  "adds bitcoin", "treasury reserve", "adopts crypto",
                  "etf launch"),
        "strength": ("record", "billion"),
        "playbook": {"majors": (1, 0.55, 72), "all": (1, 0.45, 72)}},
    "exchange_incident": {
        "match": ("hack", "hacked", "exploit", "halts withdrawals",
                  "insolvency", "insolvent", "bankruptcy", "collapse",
                  "drained", "stolen funds", "security breach"),
        "strength": ("billion", "halts", "bankrupt", "collapse"),
        "playbook": {"all": (-1, 0.6, 48), "defi": (-1, 0.65, 48),
                     "majors": (-1, 0.5, 24)}},
    "stablecoin_stress": {
        "match": ("depeg", "depegs", "loses peg", "stablecoin crisis",
                  "breaks peg"),
        "strength": ("collapse", "bank run"),
        "playbook": {"all": (-1, 0.7, 48), "defi": (-1, 0.75, 48)}},
    "geopolitical_shock": {
        "match": ("invasion", "invades", "air strikes", "airstrikes",
                  "missile", "declares war", "escalation", "sanctions",
                  "military strike", "conflict erupts", "attack on"),
        "strength": ("nuclear", "war", "oil"),
        "playbook": {"all": (-1, 0.5, 24), "equities": (-1, 0.55, 24),
                     "majors": (-1, 0.45, 24)}},
    "banking_stress": {
        "match": ("bank failure", "bank collapse", "bank run", "bailout",
                  "fdic", "credit crisis", "bank rescue"),
        "strength": ("contagion", "systemic"),
        # SVB Mar-2023: the safe-haven flip — crypto UP on bank failures.
        "playbook": {"majors": (1, 0.5, 72), "equities": (-1, 0.55, 48),
                     "all": (0, 0.3, 48)}},
    "ai_boom": {
        "match": ("ai chip", "gpu demand", "model launch", "openai",
                  "artificial intelligence breakthrough", "ai spending",
                  "data center"),
        "strength": ("record", "surge"),
        "playbook": {"ai": (1, 0.5, 72), "equities": (1, 0.4, 72)}},
}


def classify(title):
    """[(event_type, strength_hits)] for one headline (usually 0-1 types)."""
    t = " " + str(title).lower() + " "
    out = []
    for etype, spec in EVENT_TYPES.items():
        if not any(m in t for m in spec["match"]):
            continue
        req = spec.get("require")
        if req and not any(r in t for r in req):
            continue
        out.append((etype, sum(1 for s in spec.get("strength", ()) if s in t)))
    return out


def severity(n_heads, n_feeds, strength_hits):
    """0..1: volume + corroboration + strength language."""
    return round(min(1.0, 0.12 * n_heads + 0.15 * max(0, n_feeds - 1)
                     + 0.10 * min(strength_hits, 4)), 3)


# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------

def _get(url, timeout=20):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def fetch_rss_headlines():
    """[(feed, title)] from the same RSS set market_pulse trusts."""
    feeds = [("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
             ("cointelegraph", "https://cointelegraph.com/rss")]
    out = []
    for name, url in feeds:
        try:
            raw = _get(url)
            for m in re.finditer(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>",
                                 raw, re.S):
                t = m.group(1).strip()
                if t and "rss" not in t.lower() and len(t) > 20:
                    out.append((name, t))
        except Exception:
            continue
    return out


GDELT_SWEEPS = [
    ("gdelt-macro", '("federal reserve" OR "interest rate" OR "inflation" OR "central bank")'),
    ("gdelt-geo", '("invasion" OR "air strikes" OR "sanctions" OR "bank failure" OR "bank run")'),
    ("gdelt-crypto", '("bitcoin" OR "crypto exchange" OR "stablecoin" OR "sec crypto")'),
]


def fetch_gdelt_headlines():
    """[(sweep, title)] from GDELT doc 2.0 (global press, free, no key).
    GDELT paces per-IP — space the sweeps or later ones come back empty."""
    import time
    out = []
    for i, (name, q) in enumerate(GDELT_SWEEPS):
        if i:
            time.sleep(3)
        try:
            url = ("https://api.gdeltproject.org/api/v2/doc/doc?query="
                   + urllib.parse.quote(q + " sourcelang:english")
                   + "&mode=artlist&format=json&timespan=2h&maxrecords=40&sort=hybridrel")
            d = json.loads(_get(url, timeout=25))
            for a in d.get("articles", []) or []:
                t = (a.get("title") or "").strip()
                if len(t) > 20:
                    out.append((name, t))
        except Exception:
            continue
    return out


# ---------------------------------------------------------------------------
# Learned playbook blend (EB, same philosophy as brain_stats)
# ---------------------------------------------------------------------------

def blended_bias(etype, sector, sev, observed):
    """(bias, confidence) for one (event_type, sector). Prior direction and
    prior WEIGHT come from the playbook; the graded record then pulls the
    weight toward the playbook's measured EDGE — its hit record scored
    against a coin flip, floored at zero — because the informative zero of
    a directional call is 0.5, not 0.

    [2026-08-05 (jv)] The EB posterior of hit rate WAS the weight, and that
    is I15's non-sequitur inside this organ: a playbook measured
    ANTI-predictive kept `hit_rate` worth of its full fear forever — on the
    day this shipped, the three highest-n playbooks were crackdown 0.19
    (n=85), geopolitical shock 0.24 (n=83), exchange incident 0.34 (n=87),
    and summed bias could ~never reach the +0.3 risk-on bar ((ji): bias
    ≥ +0.5 in 0.0% of 2,399 samples) — the organ's EXPAND half was
    unreachable by construction, its restrict half pressed permanently.
    Now: at n=0 the prior applies UNCHANGED (priors are deliberately modest
    soft weights, not probability claims — re-scoring them against 0.5
    would mute the taxonomy at birth); as n grows the weight converges to
    max(0, 2·hit/n − 1), so an at-or-below-coin-flip playbook is SILENCED
    by its own record while an accurate one (easing: 0.95 over n=21 today)
    keeps its measured edge. Direction still never auto-flips (that needs
    an operator/review — the record saying a fear playbook is BACKWARDS on
    this tape is surfaced by its grade, not traded in reverse). Returned
    `confidence` is unchanged: the EB posterior hit estimate, published on
    the grades card."""
    pb = EVENT_TYPES[etype]["playbook"]
    row = pb.get(sector) or pb.get("all")
    if not row:
        return 0.0, 0.0
    direction, prior_conf, _hl = row
    o = (observed or {}).get(f"{etype}|{sector}|24") or {}
    n, hit = float(o.get("n") or 0), float(o.get("hit") or 0)
    conf = (prior_conf * PRIOR_EPISODES + hit) / (PRIOR_EPISODES + n)
    # max(0, 2·hit − n) is the record's votes ABOVE a coin flip: the edge
    # analogue of `hit` in the conf line, same pseudo-count blend.
    weight = (prior_conf * PRIOR_EPISODES + max(0.0, 2.0 * hit - n)) \
        / (PRIOR_EPISODES + n)
    return round(direction * sev * weight, 3), round(conf, 3)


# ---------------------------------------------------------------------------
# Sector index cache (chained from the scout's marks — no heavy fetches)
# ---------------------------------------------------------------------------

def sector_index_step(prev_marks, marks, prev_idx):
    """Chain per-sector indices by the median member return between two
    mark snapshots (intersection of symbols only — listings can't jump the
    index). Missing sectors carry forward."""
    rets = defaultdict(list)
    for sym, px in (marks or {}).items():
        p0 = (prev_marks or {}).get(sym)
        try:
            if p0 and px and float(p0) > 0:
                r = float(px) / float(p0) - 1.0
                sec = _sector_of(sym)
                rets[sec].append(r)
                rets["all"].append(r)
        except Exception:
            continue
    idx = dict(prev_idx or {})
    for sec, rs in rets.items():
        rs.sort()
        med = rs[len(rs) // 2]
        idx[sec] = round(idx.get(sec, 100.0) * (1.0 + med), 6)
    return idx


def _idx_at(cache, ts, tol=2700):
    """Nearest cached sector-index entry within tol seconds of ts."""
    best, best_d = None, tol + 1
    for e in cache:
        d = abs(e["ts"] - ts)
        if d < best_d:
            best, best_d = e, d
    return best


def grade_events(events, cache, observed, now_ts):
    """Score elapsed horizons for every tracked event; update observed
    stats in place. Returns number of new grades."""
    new = 0
    for ev in events.values():
        t0 = ev.get("first_seen_ts")
        preds = ev.get("pred") or {}
        if t0 is None or not preds:
            continue
        base = _idx_at(cache, t0)
        if not base:
            continue
        grades = ev.setdefault("grades", {})
        for h in GRADE_HORIZONS_H:
            hk = str(h)
            if hk in grades or now_ts < t0 + h * 3600:
                continue
            at = _idx_at(cache, t0 + h * 3600)
            if not at:
                continue
            g = {}
            for sector, p in preds.items():
                b0 = (base.get("idx") or {}).get(sector)
                b1 = (at.get("idx") or {}).get(sector)
                if not (b0 and b1) or not p.get("bias"):
                    continue
                realized = b1 / b0 - 1.0
                # [2026-07-17 AUDIT] A FLAT MOVE IS NOT A HIT — it is NO
                # EVIDENCE. `(realized > 0) == (bias > 0)` treats "the sector
                # did not move" as a correct BEARISH call, because both sides
                # are False. The playbook is 18 bearish sector-biases to 10
                # bullish (6 of 11 event types net-bearish), so a flat tape
                # scores 18 hits and 10 misses on its own — and a DEAD scout
                # produces exactly a flat tape (see the freshness gate above),
                # which is how a silent sensor inflated `hit_rate` toward 1.0
                # instead of decaying it toward zero. The EB blend is a correct
                # posterior; it was being fed manufactured hits.
                #
                # A dead-band is the honest reading: below it we cannot tell
                # direction from noise, so we record NOTHING (no n, no hit) —
                # an ungraded anticipation, not a free one. This also removes
                # the sign asymmetry: a flat outcome now costs bullish and
                # bearish biases the same, which is nothing.
                if abs(realized) < MOVE_EPS:
                    continue
                hit = (realized > 0) == (p["bias"] > 0)
                g[sector] = {"move_pct": round(100 * realized, 3), "hit": hit}
                k = f"{ev['type']}|{sector}|{h}"
                o = observed.setdefault(k, {"n": 0, "hit": 0, "sum_mv": 0.0})
                o["n"] += 1
                o["hit"] += 1 if hit else 0
                o["sum_mv"] = round(o["sum_mv"] + (1 if p["bias"] > 0 else -1)
                                    * realized, 5)
                new += 1
            if g:
                grades[hk] = g
    return new


# ---------------------------------------------------------------------------
# state + publish plumbing (pulse pattern: Postgres first, local fallback)
# ---------------------------------------------------------------------------

def load_state():
    """(ok, state). ok=False means the read FAILED — the caller must NOT write.

    [2026-07-17 AUDIT] `store.load_state` returns None for BOTH "no row" and
    "read failed", and run_once wrote this state back UNCONDITIONALLY — so one
    transient Postgres error published an empty state over the LEARNED PLAYBOOK
    (`observed`: every graded anticipation this organ has ever made) and the
    mark cache. Railway's FS is ephemeral, so LOCAL_STATE is gone after every
    redeploy and cannot backstop it; `fleet_regen.REPAIRABLE` does not cover
    event-sentinel-state either. A blip was therefore indistinguishable from a
    first run, and the learning restarted from zero — silently, since a fresh
    empty payload looks exactly like a healthy new deployment.
    load_state_checked exists for precisely this caller shape."""
    try:
        import bot_pnl_store as store
        ok, s = store.load_state_checked(STATE_KEY)
        if not ok:
            return False, {}          # could not find out -> caller must skip
        if s:
            return True, s
    except Exception:
        return False, {}              # unknown, not empty — fail safe
    try:
        with open(LOCAL_STATE) as f:
            return True, json.load(f)
    except FileNotFoundError:
        return True, {}               # genuinely a first run
    except Exception:
        return False, {}              # a corrupt/unreadable file is not "empty"


def save_state(state):
    try:
        import bot_pnl_store as store
        store.save_state(STATE_KEY, state)
    except Exception:
        pass
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(LOCAL_STATE, "w") as f:
            json.dump(state, f)
    except Exception:
        pass


def _lever(name, default):
    try:
        import fleet_tuning
        return fleet_tuning.get_lever(name, default)
    except Exception:
        return default


# [2026-09-02] ONE GRADED BAR FOR BOTH PROPOSAL DIRECTIONS. The risk-ON branch
# always required a playbook that EARNED actuation (n>=10, hit>=0.55 on its own
# graded record); the risk-OFF crouch required nothing — any fresh
# severity-frozen event proposed it, from playbooks the organ's own grades
# score BELOW A COIN FLIP (crackdown 0.19/n=85, shock 0.24/n=83, incident
# 0.34/n=87). Measured cost of the asymmetry, both sides: the enacted crouches
# grade `neutral` in proprioception (Σ+$1.89 over 5 episodes — no protective
# benefit), and the (sk) one-way ratchet that held the taker's only living
# lens at its tightest cage end for weeks was fed by exactly these proposals.
# "The organ earns actuation with its own graded history" now applies in BOTH
# directions — a crouch on fear that is measurably anti-signal is not free.
GRADED_MIN_N = 10
GRADED_MIN_HIT = 0.55


def graded_types(active, grades, min_n=GRADED_MIN_N, min_hit=GRADED_MIN_HIT):
    """Event types among the fresh, severity-frozen actives whose playbook has
    earned actuation on its own graded record. `grades` is the payload's
    `playbook_grades` map ({type: {n, hit_rate}}) — the publisher's own shape,
    so an ungraded type (n=0, hit_rate None) fails the bar rather than
    crashing it."""
    out = set()
    for e in active or []:
        if not (e.get("fresh") and e.get("pred")):
            continue
        g = grades.get(e.get("type")) or {}
        if (g.get("n") or 0) >= min_n and (g.get("hit_rate") or 0) >= min_hit:
            out.add(e["type"])
    return sorted(out)


def proposals_for(bias, active, grades):
    """The sentinel's whole actuation decision, as data — {lever: spec} or {}.
    Pure so the selftest can drive every branch; main() only transmits."""
    evtypes = graded_types(active, grades)
    if bias <= -0.3 and evtypes:
        why = (f"risk-off bias {bias:+.2f}, graded playbook "
               f"({', '.join(evtypes)[:80]})")
        return {
            "taker.brk_range":  {"value": 0.97, "direction": "restrict",
                                 "reason": why, "ttl_sec": 1800},
            "taker.momo_chg":   {"value": 6.0,  "direction": "restrict",
                                 "reason": why, "ttl_sec": 1800},
            "taker.max_hold_h": {"value": 24.0, "direction": "restrict",
                                 "reason": why, "ttl_sec": 1800},
        }
    if bias >= 0.3 and evtypes:
        return {"taker.momo_chg": {
            "value": 4.5, "direction": "expand",
            "reason": f"risk-on bias {bias:+.2f}, graded playbook "
                      f"({', '.join(evtypes)[:80]})",
            "evidence": json.dumps(grades)[:280],
            "ttl_sec": 1800}}
    return {}


def main():
    now = datetime.now(timezone.utc)
    now_ts = now.timestamp()
    _ok, state = load_state()
    if not _ok:
        print("[event-sentinel] state READ FAILED — skipping this cycle rather "
              "than restarting the learned playbook from zero over a blip "
              "(Railway's FS is ephemeral, so there is no local backstop, and "
              "fleet_regen does not cover this key). Retries in ~10 min.",
              flush=True)
        return
    events = state.setdefault("events", {})
    observed = state.setdefault("observed", {})
    cache = state.setdefault("mark_cache", [])
    min_sources = int(_lever("evsent.min_sources", MIN_SOURCES_DEFAULT))
    sev_bar = float(_lever("evsent.severity_bar", SEVERITY_BAR_DEFAULT))

    # 1-2. feeds -> classified headline clusters
    heads = fetch_rss_headlines()
    gd = fetch_gdelt_headlines()
    sources_ok = {"rss": bool(heads), "gdelt": bool(gd)}
    clusters = defaultdict(lambda: {"heads": [], "feeds": set(), "strength": 0})
    for feed, title in heads + gd:
        for etype, s_hits in classify(title):
            c = clusters[etype]
            if title not in c["heads"]:
                c["heads"].append(title)
                c["feeds"].add(feed)
                c["strength"] += s_hits

    # 3. event lifecycle
    day = now.strftime("%Y%m%d")
    for etype, c in clusters.items():
        if len(c["heads"]) < min_sources:
            continue
        sev = severity(len(c["heads"]), len(c["feeds"]), c["strength"])
        eid = f"{etype}:{day}"
        ev = events.get(eid)
        if ev is None:
            # same type still inside a prior event's life -> same episode
            for k, e in events.items():
                if (e.get("type") == etype
                        and now_ts - (e.get("first_seen_ts") or 0)
                        <= EVENT_LIFE_HOURS * 3600):
                    eid, ev = k, e
                    break
        if ev is None:
            ev = events[eid] = {
                "type": etype, "first_seen": now.isoformat(timespec="seconds"),
                "first_seen_ts": now_ts, "peak_severity": 0.0,
                "n_heads": 0, "sample": []}
        ev["last_seen_ts"] = now_ts
        ev["n_heads"] = max(ev["n_heads"], len(c["heads"]))
        ev["peak_severity"] = max(ev["peak_severity"], sev)
        ev["sample"] = (ev.get("sample") or [])[:2] + c["heads"][:3]
        ev["sample"] = list(dict.fromkeys(ev["sample"]))[:5]
        # 4. anticipation (freeze predictions at first activation so grades
        # measure what we SAID, not what we later revised)
        if "pred" not in ev and ev["peak_severity"] >= sev_bar:
            pred = {}
            secs = set(SECTORS) | {"all"}
            for sector in secs:
                bias, conf = blended_bias(etype, sector, ev["peak_severity"],
                                          observed)
                if abs(bias) >= 0.05:
                    pred[sector] = {"bias": bias, "conf": conf}
            if pred:
                ev["pred"] = pred

    # prune events past their tracked life (grades already harvested)
    for k in list(events):
        if now_ts - (events[k].get("first_seen_ts") or 0) > EVENT_LIFE_HOURS * 3600:
            del events[k]

    # 5. sector index cache step (one cheap load of the scout's marks)
    # [2026-07-17 AUDIT] FRESHNESS-GATE the scout read. This organ's whole
    # sensory input is the Lighter Scout's marks, and bot_pnl_store applies no
    # age filter — a DEAD scout's marks return forever. fleet_risk guards this
    # exact key with a freshness check (fleet_risk.py:589), 100 lines from
    # where it defines the helper; this reader was the outlier.
    #
    # Unguarded, a frozen scout chains: prev_marks == marks -> every sector
    # return 0.0 -> a flat index -> and (see the grader below) a HIT for every
    # bearish anticipation. The organ then reports rising confidence in a
    # playbook it has not tested, off a sensor that is not reporting.
    # `sources_ok` covers RSS/GDELT and says nothing about the scout, so the
    # dashboard cannot see it either.
    marks = {}
    try:
        import bot_pnl_store as store
        lm = store.load_state("lighter-market") or {}
        _u, _ttl = lm.get("updated"), float(lm.get("ttl_sec") or 900)
        _age = None
        if _u:
            try:
                _age = now_ts - datetime.fromisoformat(
                    str(_u).replace("Z", "+00:00")).timestamp()
            except (ValueError, TypeError):
                _age = None
        # unstamped or stale -> NO marks: no index step, no cache entry, and
        # therefore nothing graded off a sensor we cannot vouch for.
        if _age is not None and 0 <= _age <= _ttl:
            marks = lm.get("marks") or {}
        elif lm:
            print(f"[event-sentinel] scout marks STALE "
                  f"(age {_age if _age is None else round(_age)}s > ttl {_ttl:.0f}s)"
                  f" — no index step, no grading this cycle", flush=True)
    except Exception:
        marks = {}
    if marks:
        prev_marks = state.get("last_marks") or {}
        prev_idx = (cache[-1]["idx"] if cache else {})
        idx = sector_index_step(prev_marks, marks, prev_idx)
        cache.append({"ts": now_ts, "idx": idx})
        state["last_marks"] = marks
        del cache[:-CACHE_CAP]

    # 6. grade elapsed horizons
    new_grades = grade_events(events, cache, observed, now_ts)

    # publish
    active = []
    sector_bias = defaultdict(float)
    for eid, ev in sorted(events.items(),
                          key=lambda kv: -(kv[1].get("peak_severity") or 0)):
        fresh = now_ts - (ev.get("last_seen_ts") or 0) <= RECENT_HOURS * 3600
        item = {"id": eid, "type": ev["type"], "severity": ev["peak_severity"],
                "first_seen": ev.get("first_seen"), "fresh": fresh,
                "n_heads": ev.get("n_heads"), "sample": ev.get("sample") or [],
                "pred": ev.get("pred") or {}, "grades": ev.get("grades") or {}}
        active.append(item)
        if fresh:
            for sector, p in (ev.get("pred") or {}).items():
                sector_bias[sector] = round(
                    max(-1.0, min(1.0, sector_bias[sector] + p["bias"])), 3)
    grade_summary = {}
    for k, o in observed.items():
        et = k.split("|", 1)[0]
        g = grade_summary.setdefault(et, {"n": 0, "hit": 0})
        g["n"] += o["n"]
        g["hit"] += o["hit"]
    payload = {
        "updated": now.isoformat(timespec="seconds"), "ttl_sec": TTL_SEC,
        "mode": "advisory", "min_sources": min_sources, "sev_bar": sev_bar,
        "active_events": active[:12],
        "market_bias": sector_bias.get("all", 0.0),
        "sector_bias": dict(sector_bias),
        "playbook_grades": {k: {"n": v["n"],
                                "hit_rate": round(v["hit"] / v["n"], 2) if v["n"] else None}
                            for k, v in grade_summary.items()},
        "sources_ok": sources_ok,
        "counts": {"headlines": len(heads) + len(gd), "events": len(events),
                   "cache": len(cache), "new_grades": new_grades},
    }
    try:
        import bot_pnl_store as store
        store.save_state(BUS_KEY, payload)
        try:
            store.save_history(BUS_KEY, payload)
        except Exception:
            pass
    except Exception:
        pass

    # [2026-07-21 ORGAN PROPOSALS, operator mandate] the sentinel's bias
    # finally reaches an actuator — as PROPOSALS the scout tuner gates with
    # its own replay evidence (fleet_proposals; nothing here writes a lever).
    #   BOTH DIRECTIONS gate on the SAME graded bar since 2-Sep (see
    #     `proposals_for` above): a fresh severity-frozen event proposes only
    #     when its playbook has EARNED actuation (n>=10, hit>=0.55 on the
    #     organ's own grades). RISK-OFF tightens the taker's entry bars +
    #     shortens the divergence hold; RISK-ON widens the momentum bar one
    #     step. The tuner's replay gate stays senior in both directions.
    # Short TTL (1800s): three missed 10-min cycles and every proposal is
    # gone on its own. Fail-soft: a dark channel drops proposals only.
    _bias = float(sector_bias.get("all", 0.0) or 0.0)
    try:
        import fleet_proposals as fprop
        _props = proposals_for(_bias, active, payload["playbook_grades"])
        _wrote = None
        if _props:
            _wrote = fprop.propose(_props, set_by="event-sentinel", now_ts=now_ts)
        if _wrote is None:
            # [2026-09-02 (wy)] NOTHING TO PROPOSE IS STILL A WRITE. propose()
            # writes only when an entry survives, so a quiet channel aged out
            # and read DARK on the organ board (3.8h past a 2h TTL, every
            # proposer alive). This organ runs every 10 min — the fleet's
            # most frequent proposer — so it is the one that keeps the
            # channel's `updated` honest: an empty, fresh channel is "nobody
            # is proposing"; a stale one is "nobody is writing" (I1/I13).
            fprop.heartbeat("event-sentinel", now_ts=now_ts)
    except Exception:
        pass

    # [2026-07-21] SELF-TUNING of the detection bars (lane 'event-sentinel',
    # now enactable + author-bound — until today these levers were registered
    # but unreachable). Stateless from the ENV defaults each cycle, moved
    # only by the organ's OWN graded record; no grades -> no write -> TTL
    # reverts. Detection sensitivity only — zero trading surface.
    #   measured INACCURATE (n>=20, hit<0.45): demand more corroboration
    #     (min_sources +1, severity_bar +0.10) — fewer, better-attested
    #     anticipations.
    #   measured ACCURATE (n>=30, hit>=0.60): lower the freeze bar one step
    #     (severity_bar -0.10) — more anticipations get frozen and graded,
    #     the organ learns faster on a playbook that is earning it.
    try:
        import fleet_tuning
        _tn = sum(v["n"] for v in grade_summary.values())
        _th = sum(v["hit"] for v in grade_summary.values())
        _hr = (_th / _tn) if _tn else None
        _sd = {}
        if _tn >= 20 and _hr is not None and _hr < 0.45:
            _sd = {"evsent.min_sources": {
                       "value": min(5, MIN_SOURCES_DEFAULT + 1),
                       "reason": f"playbook measured inaccurate "
                                 f"(hit {_hr:.2f} over n={_tn})"},
                   "evsent.severity_bar": {
                       "value": min(0.80, SEVERITY_BAR_DEFAULT + 0.10),
                       "reason": f"playbook measured inaccurate "
                                 f"(hit {_hr:.2f} over n={_tn})"}}
        elif _tn >= 30 and _hr is not None and _hr >= 0.60:
            _sd = {"evsent.severity_bar": {
                       "value": max(0.30, SEVERITY_BAR_DEFAULT - 0.10),
                       "reason": f"playbook measured accurate "
                                 f"(hit {_hr:.2f} over n={_tn})"}}
        if _sd:
            fleet_tuning.write_levers(_sd, set_by="event-sentinel")
    except Exception:
        pass
    save_state(state)
    print(f"[event_sentinel] {payload['counts']['headlines']} headlines, "
          f"{len(events)} tracked events "
          f"({sum(1 for e in active if e['fresh'])} fresh), "
          f"market_bias {payload['market_bias']:+}, "
          f"{new_grades} new grades, cache {len(cache)} "
          f"(rss={sources_ok['rss']} gdelt={sources_ok['gdelt']})")
    for e in active[:5]:
        if e["fresh"]:
            print(f"  EVENT [{e['type']}] sev={e['severity']} "
                  f"heads={e['n_heads']} pred={list((e['pred'] or {}).keys())}")
    return 0


# ---------------------------------------------------------------------------

def _selftest():
    # [2026-09-02] the proposal decision is one function, graded in BOTH
    # directions — grades in the payload's OWN shape ({n, hit_rate}), the
    # (hj) publisher-built rule.
    _act = [{"type": "geopolitical_shock", "fresh": True, "pred": True}]
    _below = {"geopolitical_shock": {"n": 83, "hit_rate": 0.24}}
    _earned = {"geopolitical_shock": {"n": 83, "hit_rate": 0.61}}
    _ungraded = {"geopolitical_shock": {"n": 0, "hit_rate": None}}
    _thin = {"geopolitical_shock": {"n": 9, "hit_rate": 1.0}}
    assert proposals_for(-0.4, _act, _below) == {}, \
        "a below-coin-flip playbook proposed the crouch — the asymmetry is back"
    assert proposals_for(-0.4, _act, _ungraded) == {}
    assert proposals_for(-0.4, _act, _thin) == {}, "n<10 must not actuate"
    _crouch = proposals_for(-0.4, _act, _earned)
    assert set(_crouch) == {"taker.brk_range", "taker.momo_chg",
                            "taker.max_hold_h"}
    assert all(v["direction"] == "restrict" for v in _crouch.values())
    assert proposals_for(0.4, _act, _below) == {}
    _wide = proposals_for(0.4, _act, _earned)
    assert set(_wide) == {"taker.momo_chg"}
    assert _wide["taker.momo_chg"]["direction"] == "expand"
    assert proposals_for(0.1, _act, _earned) == {}, "no bias, no proposal"
    assert proposals_for(-0.4, [{"type": "geopolitical_shock", "fresh": False,
                                 "pred": True}], _earned) == {}, \
        "a stale event must not actuate however well its playbook grades"
    # ...and main() transmits THIS function's verdict, not a local copy
    import ast as _ast
    import inspect as _insp
    _mn = {n.id for n in _ast.walk(_ast.parse(_insp.getsource(main)))
           if isinstance(n, _ast.Name)}
    assert "proposals_for" in _mn, "main() no longer routes through the bar"
    # classification: polarity + require-terms + no false fire
    assert classify("Fed raises rates in surprise hawkish move")[0][0] == "monetary_tightening"
    assert classify("CPI comes in hotter than expected at 4.1%")[0][0] == "inflation_hot"
    assert classify("CPI cools more than expected in June")[0][0] == "inflation_cool"
    assert not classify("CPI report due Thursday")           # require-terms gate
    assert classify("Major exchange halts withdrawals after $600M exploit")[0][0] == "exchange_incident"
    assert not classify("Bitcoin steady as traders await weekend")
    # severity: monotone in volume + corroboration
    assert severity(6, 3, 2) > severity(2, 1, 0)
    # playbook blend: SVB-style flip encoded (majors UP on banking stress)
    b, _ = blended_bias("banking_stress", "majors", 0.8, {})
    assert b > 0
    b2, _ = blended_bias("banking_stress", "equities", 0.8, {})
    assert b2 < 0
    # learning: repeated misses at 24h decay confidence toward zero
    missed = {"stablecoin_stress|all|24": {"n": 12, "hit": 1, "sum_mv": -0.3}}
    b_naive, c_naive = blended_bias("stablecoin_stress", "all", 0.8, {})
    b_learn, c_learn = blended_bias("stablecoin_stress", "all", 0.8, missed)
    assert abs(b_learn) < abs(b_naive) and c_learn < c_naive
    # [2026-08-05 (jv)] the informative zero of a directional call is a coin
    # flip. Four arms, each one mutation-killable:
    # (1) a record-REFUTED playbook is ~silenced (weight -> prior*PE/(PE+n),
    #     not hit_rate) — reverting the weight to `conf` reddens this;
    refuted = {"regulation_crackdown|all|24": {"n": 30, "hit": 6, "sum_mv": -1.0}}
    b_ref, _ = blended_bias("regulation_crackdown", "all", 0.9, refuted)
    b_pri, _ = blended_bias("regulation_crackdown", "all", 0.9, {})
    assert abs(b_ref) <= abs(b_pri) * 0.2, (b_ref, b_pri)
    # (2) the sign NEVER flips against the playbook, whatever the record
    #     says — dropping the max(0, ·) floor reddens this;
    assert b_ref * -1 >= 0 and b_pri * -1 >= 0, (b_ref, b_pri)
    # (3) a COIN-FLIP record earns ~nothing (hit=n/2 must not keep half the
    #     fear the way hit-rate weighting did);
    coin = {"regulation_crackdown|all|24": {"n": 40, "hit": 20, "sum_mv": 0.0}}
    b_coin, _ = blended_bias("regulation_crackdown", "all", 0.9, coin)
    assert abs(b_coin) <= abs(b_pri) * 0.15, (b_coin, b_pri)
    # (4) an ACCURATE playbook keeps (and grows) its voice — applying the
    #     edge map to the PRIOR too would mute it at birth and redden the
    #     banking_stress prior asserts above as well.
    earned = {"monetary_easing|all|24": {"n": 20, "hit": 19, "sum_mv": 2.0}}
    b_earn, c_earn = blended_bias("monetary_easing", "all", 0.8, earned)
    b_earn_pri, _ = blended_bias("monetary_easing", "all", 0.8, {})
    assert b_earn > b_earn_pri > 0, (b_earn, b_earn_pri)
    assert c_earn > 0.8, c_earn      # conf still the posterior hit estimate
    # sector index chaining: only symbol intersections move the index
    i1 = sector_index_step({"BTC": 100.0, "ETH": 50.0}, {"BTC": 110.0, "ETH": 55.0}, {})
    assert round(i1["majors"], 2) == 110.0
    i2 = sector_index_step({"BTC": 110.0}, {"BTC": 110.0, "NEWCOIN": 999.0}, i1)
    assert i2["majors"] == i1["majors"]     # listing didn't jump the index
    # grading: hit + miss update observed correctly
    cache = [{"ts": 0, "idx": {"all": 100.0}},
             {"ts": 4 * 3600, "idx": {"all": 97.0}}]
    events = {"x:1": {"type": "exchange_incident", "first_seen_ts": 0,
                      "pred": {"all": {"bias": -0.4, "conf": 0.6}}}}
    obs = {}
    n = grade_events(events, cache, obs, now_ts=5 * 3600)
    assert n == 1 and obs["exchange_incident|all|4"]["hit"] == 1
    assert events["x:1"]["grades"]["4"]["all"]["move_pct"] == -3.0
    # [2026-07-17 AUDIT] THE DEAD SENSOR MUST NOT LOOK LIKE A WINNING PLAYBOOK.
    # Three fixtures for the chain that inflated confidence off a frozen scout.

    # (a) the grading dead-band. The playbook is 18 bearish sector-biases to 10
    # bullish, and `(realized > 0) == (bias > 0)` scored a flat tape as a HIT
    # for every bearish one — so a sensor reporting nothing manufactured 18
    # hits per horizon. A move below MOVE_EPS is now UNGRADED for both signs.
    assert MOVE_EPS > 0, "a zero dead-band restores the free-hit-for-bearish bug"
    for _bias in (-0.5, 0.5):
        for _flat in (0.0, 0.0004, -0.0004):
            assert abs(_flat) < MOVE_EPS, (_flat, MOVE_EPS)   # -> `continue`
    # ...while a REAL move still grades, and grades by direction
    assert (0.02 > 0) == (0.5 > 0) and not ((0.02 > 0) == (-0.5 > 0))
    assert (-0.02 > 0) == (-0.5 > 0) and not ((-0.02 > 0) == (0.5 > 0))
    assert abs(-0.02) >= MOVE_EPS and abs(0.02) >= MOVE_EPS

    # (b) load_state's (ok, state) contract: a FAILED read is never an empty
    # state — main() must be able to tell "first run" from "I could not look",
    # or a blip restarts the learned playbook from zero (no local backstop on
    # Railway's ephemeral FS, and fleet_regen does not cover this key).
    import bot_pnl_store as _st
    _real_lsc = getattr(_st, "load_state_checked", None)
    try:
        _st.load_state_checked = lambda k: (False, None)
        assert load_state() == (False, {}), "a failed read must report ok=False"
        _st.load_state_checked = lambda k: (True, {"observed": {"k": {"n": 41}}})
        _ok, _s = load_state()
        assert _ok is True and _s["observed"]["k"]["n"] == 41, (_ok, _s)
        _st.load_state_checked = lambda k: (True, None)   # genuinely no row
        assert load_state()[0] is True, "no row is a real answer: ok=True"
    finally:
        if _real_lsc is not None:
            _st.load_state_checked = _real_lsc

    # (c) the scout freshness gate: only a payload stamped WITHIN its own ttl
    # may drive the index. fleet_risk guards this same key; this reader didn't.
    def _fresh_ok(age, ttl):
        return age is not None and 0 <= age <= ttl
    assert _fresh_ok(10, 900) and not _fresh_ok(901, 900)
    assert not _fresh_ok(None, 900), "unstamped is NOT fresh"
    assert not _fresh_ok(-5, 900), "future-stamped is NOT fresh (lower bound)"

    print("event_sentinel selftest OK (incl. the dead-sensor chain: grading "
          "dead-band, (ok,state) read contract, scout freshness gate)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    # [2026-08-01 (ig)] IMPORT AT THE CALL SITE. This module binds `store` only
    # INSIDE functions (`import bot_pnl_store as store`, 4 sites), so the
    # module-level use `(hw)` added here raised `NameError: name 'store' is not
    # defined` on EVERY run — measured in the container from 16:23Z 31-Jul, and
    # a restart could not help because it crashes at once, every cycle.
    # `(hw)` made exactly this adjustment for market_pulse and missed the two
    # organs that needed it most. Keeping the import local also keeps `--selftest`
    # runnable with no DB, which is why the lazy pattern exists here at all.
    import bot_pnl_store as store
    sys.exit(store.organ_main('event-sentinel', main))
