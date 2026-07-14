#!/usr/bin/env python3
"""
bot_learn.py — the fleet's learning loop ("brain"), v2.

WHAT IT DOES
  1. Pulls the durable trade ledger (the pnl-dashboard's /trades.json, which is
     backed by the Postgres bot_trades table and survives redeploys).
  2. Dissects every bot's closed trades along five axes: entry tag, exit
     reason, pair, hold-duration bucket, and UTC session.
  3. Keeps CUMULATIVE state across runs (Postgres bot_state key
     'learning-brain' when DATABASE_URL is set, else reports/brain_state.json):
     a candidate pattern ("hypothesis") must persist across >= PROMOTE_RUNS
     runs AND keep its sample growing before it is promoted to ACTIONABLE —
     one lucky/unlucky day never changes anything.
  4. Writes reports/lessons_latest.md: per-bot scorecards + PROPOSALS.
  5. [2026-07-14 L4 META-LABELING] Publishes NUMERIC, REDUCE-ONLY per-
     (bot, enter_tag) stake multipliers to bot_state 'brain-stake-mults'.
     Strategies read them at entry via fleet_bus.stake_multiplier() — the
     first brain output any bot actually trades on. Hard guardrails:
       - trade-count floor: n >= MULT_MIN_N (30) era trades on that tag
         for a 0.5x; a softer 0.75x needs n >= MULT_SOFT_N (15)
       - persistence: the reduction must recur on PROMOTE_RUNS (3)
         consecutive brain runs before it is PUBLISHED (streak-gated,
         same philosophy as hypothesis promotion)
       - reduce-only: v1 never publishes > 1.0x; boosting must earn its
         own evidence bar later
       - fail-safe: payload carries updated+ttl_sec; consumers go neutral
         when it is stale (see fleet_bus.py)
  6. [2026-07-14 VENUE A/B] Compares every paper book with its Lighter
     shadow twin (<bot> vs <bot>-lshadow, live -lighter rows too) from
     bot_pnl — the shadow-book data collected since 13 Jul — and reports
     the venue gap per strategy in lessons + state (key 'venue_ab').
  7. [2026-07-14b DIAGNOSIS] For every negative (bot, tag) bucket at sample
     size, classifies WHICH LEVER the loss lives in — exit_too_tight /
     venue_execution / fee_bleed / regime_timing / entry_quality — using
     exit-path splits, post-exit drift from public 1h candles (the
     mechanized form of the manual replay behind the 13-Jul stop widening),
     fee-scale tests, a regime-oracle-history join, and the venue A/B
     table. Publishes bot_state 'brain-diagnosis'; proposals now name the
     lever instead of defaulting to "tighten the entry gates" (the 92-run
     'flip' artifact this replaces).

WHAT IT NEVER DOES
  Change entry/exit logic, configs, or trades — and it never SIZES UP.
  The multipliers only throttle stakes on tags the ledger has repeatedly
  scored negative at sample size. Humans still ship logic changes; see
  NO_REAL_MONEY policy.

Run it anywhere: laptop (called by the 2-hourly research scan) or cloud.
"""
import json
import os
import sys
import urllib.request
from collections import defaultdict
from datetime import datetime, timezone

TRADES_URL = os.environ.get(
    "LEARN_TRADES_URL",
    "https://pnl-dashboard-production-858c.up.railway.app/trades.json?limit=2000")
PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
LOCAL_STATE = os.path.join(REPORTS_DIR, "brain_state.json")
LESSONS_MD = os.path.join(REPORTS_DIR, "lessons_latest.md")

MIN_N_FLAG = 8        # min closed trades before a pair/tag pattern counts
MIN_N_SESSION = 20    # sessions are noisier -> bigger sample required
PROMOTE_RUNS = 3      # a hypothesis must survive this many runs to be ACTIONABLE

# [2026-07-14 L4] Stake-multiplier floors. The design doc's non-negotiable:
# tiny samples must never masquerade as edge. 30 era-trades for the hard
# throttle mirrors the meta-labeling literature's minimum;
# 15 for the soft one because it only shaves a quarter of the stake.
MULT_MIN_N = 30       # era trades on a tag before a 0.5x may publish
MULT_SOFT_N = 15      # era trades before a 0.75x may publish
MULT_KEY = "brain-stake-mults"
MULT_TTL_SEC = 26000  # ~3.6 brain intervals (7200s) -> 3 missed runs = stale

# [2026-07-14b DIAGNOSIS LAYER] Discriminate WHERE a negative sleeve loses:
# entry quality / exit path / fee bleed / regime timing / venue execution.
# Born from the 92-run "tighten the 'flip' entry gates" artifact — the brain
# could find patterns but not tell an entry problem from an exit problem from
# a venue problem, so its prose pointed at the wrong lever.
DIAG_KEY = "brain-diagnosis"
DIAG_MIN_N = 10           # closed era trades before diagnosing a bucket
DIAG_DRIFT_MAX_PAIRS = 30  # cap Kraken fetches per run (once per pair, cached)
STOPPISH = ("stop_loss", "trailing_stop_loss", "bleed_stop", "stoploss",
            "liquidation", "force_exit")
# Round-trip friction estimate per bot (fraction of stake). Kraken spot taker
# 0.26%/side is the freqtrade default; the perps ledger documented ~29bps.
FEE_RT_DEFAULT = 0.0052
FEE_RT = {"perps-funding-carry": 0.0029, "perps-rsi-meanrev": 0.0029,
          "perps-donchian-breakout": 0.0029, "event-listing-sniper": 0.0060}

# [ERA AWARENESS] Hypotheses must come from trades taken by the CURRENT code.
# Without this the brain prosecutes today's strategy for yesterday's crimes
# (e.g. flagging pairs the dead 15m scalper bled on). Trades opened before a
# bot's era-start still show in lifetime tallies but generate no hypotheses.
ERA_START = {
    "crypto-intraday-15m": "2026-07-13T00:00",   # 13-Jul: range_meanrev retired + counter-trend stop 2.0->3.5x
    "crypto-swing-daily":  "2026-07-03T06:00",   # ungated range -> validated dip + bounce
    "crypto-breakout-4h":  "2026-07-14T00:00",   # 14-Jul: BTC-tide gate on breakout entries (backtest-validated)
    "crypto-trendmomo-4h": "2026-07-03T06:00",   # 4h/20-alt -> 1d BTC+ETH 10/40 (retired 12-Jul)
    "perps-regime-switch": "2026-07-03T10:00",   # EMA-cross -> Donchian entries (retired 12-Jul)
    "freqtrade-georgia":   "2026-07-13T00:00",   # 13-Jul: same DayTraderV5Gated sleeve/stop changes
    "freqtrade-mum":       "2026-07-14T00:00",   # 14-Jul: whitelist curated to the 10 backtest-positive pairs
    "freqtrade-dad":       "2026-07-14T00:00",   # 14-Jul: BTC-tide gate (same MomoBreakoutV1 carrier)
}

# ---------------------------------------------------------------------------


def _load_state():
    # Prefer the durable Postgres copy (cloud + survives laptop wipes).
    try:
        import bot_pnl_store as store
        s = store.load_state("learning-brain")
        if s:
            return s, "postgres"
    except Exception:
        pass
    try:
        with open(LOCAL_STATE) as f:
            return json.load(f), "local"
    except Exception:
        return {"runs": 0, "hypotheses": {}}, "fresh"


def _save_state(state):
    saved = []
    try:
        import bot_pnl_store as store
        if store.save_state("learning-brain", state):
            saved.append("postgres")
    except Exception:
        pass
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        with open(LOCAL_STATE, "w") as f:
            json.dump(state, f, indent=1)
        saved.append("local")
    except Exception:
        pass
    return saved


def _fetch_trades():
    # Freqtrade bots: the durable bot_trades ledger via the dashboard's HTTP feed.
    with urllib.request.urlopen(TRADES_URL, timeout=30) as r:
        d = json.loads(r.read().decode())
    trades = d if isinstance(d, list) else d.get("trades", d.get("data", []))
    trades = [t for t in trades if isinstance(t, dict) and not t.get("is_open")]
    # [2026-07-05 ALL-BOTS] Perps + sniper close to the paper_trades table, NOT
    # bot_trades, so they were invisible to the brain. Pull them directly (works
    # when DATABASE_URL is set — always true in the cloud container the brain now
    # runs in) and merge, so the fleet's learning covers EVERY bot, not just
    # freqtrade. Guarded: no DB / import error -> just the freqtrade set.
    try:
        import bot_pnl_store as store
        paper = store.fetch_paper_trades(limit=5000)
        if paper:
            trades.extend(t for t in paper if not t.get("is_open"))
    except Exception:
        pass
    return trades


def _bucketize(trades, key):
    out = defaultdict(lambda: {"n": 0, "w": 0, "pnl": 0.0})
    for t in trades:
        k = key(t)
        if k is None:
            continue
        b = out[str(k)]
        b["n"] += 1
        p = t.get("profit_abs") or 0.0
        b["pnl"] += p
        if p > 0:
            b["w"] += 1
    return out


def _dur_bucket(t):
    m = t.get("duration_min") or 0
    return "<30m" if m < 30 else "30-90m" if m < 90 else "90-240m" if m < 240 else ">240m"


def _session(t):
    ts = str(t.get("open_ts") or "")
    if len(ts) < 13:
        return None
    h = int(ts[11:13])
    return f"UTC{h - h % 3:02d}-{h - h % 3 + 2:02d}"


def _load_pulse_history():
    """Rolling mood snapshots from market_pulse.py — local file first, then the
    dashboard's /pulse.json. Returns [] when unavailable (correlation skipped)."""
    try:
        with open(os.path.join(REPORTS_DIR, "market_pulse_state.json")) as f:
            h = json.load(f).get("history", [])
            if h:
                return h
    except Exception:
        pass
    try:
        url = os.environ.get(
            "LEARN_PULSE_URL",
            "https://pnl-dashboard-production-858c.up.railway.app/pulse.json")
        with urllib.request.urlopen(url, timeout=15) as r:
            return json.loads(r.read().decode()).get("history", [])
    except Exception:
        return []


def _mood_at(history, open_ts):
    """Nearest mood snapshot within 2h of a trade's open, else None."""
    if not history or not open_ts:
        return None
    try:
        t = datetime.fromisoformat(str(open_ts).replace("Z", "+00:00"))
    except Exception:
        return None
    best, best_dt = None, 7200.0
    for h in history:
        try:
            ht = datetime.fromisoformat(h["ts"])
        except Exception:
            continue
        d = abs((ht - t).total_seconds())
        if d < best_dt:
            best, best_dt = h, d
    return best


def analyse_bot(bot, trades, pulse_hist=None):
    """Return (scorecard dict, list of candidate hypotheses)."""
    n = len(trades)
    wins = sum(1 for t in trades if (t.get("profit_abs") or 0) > 0)
    pnl = sum(t.get("profit_abs") or 0 for t in trades)
    wr = wins / n if n else 0.0
    card = {"n": n, "wins": wins, "wr": round(wr * 100, 1), "pnl": round(pnl, 2),
            "by_tag": _bucketize(trades, lambda t: t.get("enter_tag") or "(untagged)"),
            "by_exit": _bucketize(trades, lambda t: t.get("exit_reason")),
            "by_dur": _bucketize(trades, _dur_bucket),
            "by_pair": _bucketize(trades, lambda t: t.get("pair")),
            "by_session": _bucketize(trades, _session)}
    hyps = []

    def hyp(key, kind, evidence, proposal):
        hyps.append({"key": f"{bot}|{key}", "kind": kind,
                     "evidence": evidence, "proposal": proposal})

    # Pair-level bleeders / earners.
    for pair, b in card["by_pair"].items():
        if b["n"] >= MIN_N_FLAG and b["w"] / b["n"] < 0.20 and b["pnl"] < 0:
            hyp(f"pair:{pair}:bleeder", "pair_bleeder",
                f"{pair}: {b['n']} trades, {b['w']/b['n']*100:.0f}% win, ${b['pnl']:+.2f}",
                f"consider dropping {pair} from {bot}'s whitelist")
        if b["n"] >= MIN_N_FLAG and b["w"] / b["n"] >= 0.55 and b["pnl"] > 0:
            hyp(f"pair:{pair}:earner", "pair_earner",
                f"{pair}: {b['n']} trades, {b['w']/b['n']*100:.0f}% win, ${b['pnl']:+.2f}",
                f"{pair} is a consistent earner for {bot} — protect it in any universe change")
    # [2026-07-14b] Entry-mode expectancy moved to the DIAGNOSIS layer in
    # main(): the old blanket "tighten the '{tag}' entry gates" prose fired on
    # any negative bucket regardless of whether the loss lived in the entry,
    # the exit path, fees, regime timing, or the venue — the 92-run 'flip'
    # artifact. diagnose() now names the lever, with drift/fee/regime evidence.
    # Stop-too-tight signature: fast deaths dominate losses AND ROI exits win.
    fast = card["by_dur"].get("<30m", {"n": 0, "w": 0, "pnl": 0})
    roi = card["by_exit"].get("roi", {"n": 0, "w": 0, "pnl": 0})
    if fast["n"] >= MIN_N_FLAG and fast["w"] / max(1, fast["n"]) < 0.10 and \
       roi["n"] >= 3 and roi["w"] == roi["n"]:
        hyp("stop_too_tight", "stop_too_tight",
            f"<30m holds: {fast['n']} trades at {fast['w']/fast['n']*100:.0f}% win "
            f"(${fast['pnl']:+.2f}) while ROI exits are {roi['w']}/{roi['n']} winners",
            f"widen {bot}'s stop / give entries room — winners need time to reach the ladder")
    # Session skew (needs the bigger sample).
    if n >= 60:
        for sess, b in card["by_session"].items():
            if b["n"] >= MIN_N_SESSION and wr > 0 and b["w"] / b["n"] <= wr * 0.4:
                hyp(f"session:{sess}", "session_dead_zone",
                    f"{sess}: {b['n']} trades at {b['w']/b['n']*100:.0f}% win vs {wr*100:.0f}% overall",
                    f"consider blocking new {bot} entries during {sess}")
            if b["n"] >= MIN_N_SESSION and b["w"] / b["n"] >= min(0.95, wr * 1.8) and b["pnl"] > 0:
                hyp(f"session:{sess}:hot", "session_hot_zone",
                    f"{sess}: {b['n']} trades at {b['w']/b['n']*100:.0f}% win vs {wr*100:.0f}% overall",
                    f"{sess} is {bot}'s best session — a future tweak could size up there")
    # Mood correlation (news/social pulse) — only meaningful once market_pulse
    # history overlaps enough trades; accumulates value from 2026-07-03 onward.
    if pulse_hist and n >= 30:
        buckets = {"neg": [0, 0], "mid": [0, 0], "pos": [0, 0]}
        matched = 0
        for t in trades:
            m = _mood_at(pulse_hist, t.get("open_ts"))
            if not m:
                continue
            matched += 1
            mood = m.get("mood") or 0.0
            k = "neg" if mood <= -0.15 else ("pos" if mood >= 0.15 else "mid")
            buckets[k][0] += 1
            if (t.get("profit_abs") or 0) > 0:
                buckets[k][1] += 1
        card["mood_matched"] = matched
        card["by_mood"] = {k: {"n": v[0], "w": v[1]} for k, v in buckets.items()}
        for k, v in buckets.items():
            if v[0] >= 10 and wr > 0:
                bwr = v[1] / v[0]
                if bwr <= wr * 0.5:
                    hyp(f"mood:{k}", "mood_dead_zone",
                        f"'{k}' mood: {v[0]} trades at {bwr*100:.0f}% win vs {wr*100:.0f}% overall",
                        f"consider halving/blocking {bot} entries when market mood is '{k}'")
                elif bwr >= min(0.95, wr * 1.7) and v[1] > 0:
                    hyp(f"mood:{k}:hot", "mood_hot_zone",
                        f"'{k}' mood: {v[0]} trades at {bwr*100:.0f}% win vs {wr*100:.0f}% overall",
                        f"{bot} performs best in '{k}' mood — candidate for informed size-up")
    return card, hyps


# --------------------------------------------------------------------------
# [2026-07-14b] Diagnosis evidence collectors
# --------------------------------------------------------------------------

_KRAKEN_ALT = {"BTC": "XBT"}
_kraken_cache = {}   # pair -> list[(epoch, o, h, l, c)] | None (per-process run)


def _kraken_hourly(pair):
    """720 recent 1h candles from Kraken's public OHLC (covers ~30 days — the
    whole current ledger). Cached per pair per run; None (also cached) when the
    pair isn't on Kraken (perps alts, sniper venues) — drift evidence is then
    simply unavailable for that pair, never an error."""
    if pair in _kraken_cache:
        return _kraken_cache[pair]
    result = None
    try:
        base, _, quote = str(pair).partition("/")
        base = _KRAKEN_ALT.get(base.upper(), base.upper())
        quote = (quote or "USD").upper()
        if quote in ("USDT", "USDC"):
            quote = "USD"
        url = f"https://api.kraken.com/0/public/OHLC?pair={base}{quote}&interval=60"
        with urllib.request.urlopen(url, timeout=20) as r:
            d = json.loads(r.read().decode())
        if not d.get("error"):
            k = [k for k in d["result"] if k != "last"][0]
            result = [(int(row[0]), float(row[1]), float(row[2]),
                       float(row[3]), float(row[4])) for row in d["result"][k]]
    except Exception:
        result = None
    _kraken_cache[pair] = result
    return result


def _epoch(ts):
    try:
        return datetime.fromisoformat(str(ts).replace("Z", "+00:00")).timestamp()
    except Exception:
        return None


def _post_exit_drift(trade):
    """(reclaimed_entry_within_24h, fwd_return_24h) for one closed trade, from
    public 1h candles after its close — the mechanized version of the manual
    replay that justified the 13-Jul stop widening. None when rates/candles are
    missing or fewer than 6 post-close hours exist yet."""
    close_ts = _epoch(trade.get("close_ts"))
    close_rate = trade.get("close_rate")
    open_rate = trade.get("open_rate")
    if not (close_ts and close_rate and open_rate):
        return None
    candles = _kraken_hourly(trade.get("pair"))
    if not candles:
        return None
    window = [c for c in candles if c[0] > close_ts][:24]
    if len(window) < 6:
        return None
    reclaimed = any(h >= float(open_rate) for _, _, h, _, _ in window)
    fwd = window[-1][4] / float(close_rate) - 1.0
    return reclaimed, fwd


def _load_regime_history():
    """regime-oracle snapshots (every 30 min since 7-Jul) -> [{'ts': epoch,
    'risk_off': bool}], newest first. [] when the DB isn't reachable."""
    try:
        import bot_pnl_store as store
        hist = store.fetch_state_history("regime-oracle", limit=800)
    except Exception:
        return []
    out = []
    for h in hist or []:
        ts = _epoch(h.get("ts"))
        read = str(((h.get("payload") or {}).get("fleet") or {}).get("read") or "")
        if ts:
            out.append({"ts": ts, "risk_off": read.startswith("risk-off")})
    return out


def _regime_at(regime_hist, open_ts):
    """Nearest oracle snapshot within 1h of a trade's open, else None."""
    t = _epoch(open_ts)
    if not (t and regime_hist):
        return None
    best, best_d = None, 3600.0
    for h in regime_hist:
        d = abs(h["ts"] - t)
        if d < best_d:
            best, best_d = h, d
    return best


def _median(xs):
    xs = sorted(xs)
    return xs[len(xs) // 2] if xs else None


def diagnose(bot, tag, trades, regime_hist, venue_ab, drift_budget):
    """Classify WHY a negative (bot, tag) bucket loses. Returns a dict with
    'primary', 'proposal', and the evidence, or None below the sample floor.
    Rules are ordered by decisiveness; every piece of evidence is optional and
    its absence just removes that rule from contention (fail-soft)."""
    n = len(trades)
    pnl = sum(t.get("profit_abs") or 0 for t in trades)
    if n < DIAG_MIN_N or pnl >= 0:
        return None
    losers = [t for t in trades if (t.get("profit_abs") or 0) < 0]
    by_exit = _bucketize(trades, lambda t: t.get("exit_reason") or "?")
    gross_loss = sum(-(t.get("profit_abs") or 0) for t in losers) or 1e-9

    worst_exit, worst = max(by_exit.items(), key=lambda kv: -kv[1]["pnl"])
    worst_share = max(0.0, -worst["pnl"]) / gross_loss
    worst_wr = worst["w"] / worst["n"] if worst["n"] else 0.0
    working_exits = [k for k, v in by_exit.items()
                     if v["n"] >= 3 and v["w"] / v["n"] >= 0.6 and v["pnl"] > 0]

    drifts = []
    for t in losers:
        if len(_kraken_cache) >= DIAG_DRIFT_MAX_PAIRS and t.get("pair") not in _kraken_cache:
            continue
        if drift_budget.get("left", 0) <= 0:
            break
        d = _post_exit_drift(t)
        drift_budget["left"] -= 1
        if d is not None:
            drifts.append(d)
    reclaim = (sum(1 for r, _ in drifts if r) / len(drifts)) if drifts else None
    avg_fwd = (sum(f for _, f in drifts) / len(drifts)) if drifts else None

    med_loser = _median([abs(t.get("profit_ratio") or 0) for t in losers
                         if t.get("profit_ratio") is not None])
    fee_rt = FEE_RT.get(bot, FEE_RT_DEFAULT)
    fee_share = (fee_rt / med_loser) if med_loser else None

    matched = counter = 0
    for t in losers:
        r = _regime_at(regime_hist, t.get("open_ts"))
        if r is not None:
            matched += 1
            counter += 1 if r["risk_off"] else 0
    counter_share = (counter / matched) if matched >= 8 else None

    ab = venue_ab.get(bot) or {}
    twin = ab.get("shadow") or ab.get("live") or {}
    twin_pnl = twin.get("pnl_abs")
    twin_n = (twin.get("wins") or 0) + (twin.get("losses") or 0)

    ev = {"n": n, "pnl": round(pnl, 2), "worst_exit": worst_exit,
          "worst_share": round(worst_share, 2), "worst_wr": round(worst_wr, 2),
          "working_exits": working_exits, "drift_n": len(drifts),
          "reclaim": None if reclaim is None else round(reclaim, 2),
          "avg_fwd": None if avg_fwd is None else round(avg_fwd, 4),
          "med_loser_ratio": None if med_loser is None else round(med_loser, 4),
          "fee_share": None if fee_share is None else round(fee_share, 2),
          "regime_matched": matched,
          "counter_regime": None if counter_share is None else round(counter_share, 2),
          "twin_pnl": twin_pnl, "twin_n": twin_n}

    def out(primary, proposal):
        return {"primary": primary, "proposal": proposal, "evidence": ev}

    where = f"{bot}/{tag}" if tag != "(untagged)" else bot
    # 1. EXIT TOO TIGHT: a stop-family path eats the losses, almost never wins,
    #    and price reclaims entry after it fires — the exit cuts noise as danger.
    if (worst_exit in STOPPISH and worst_share >= 0.5 and worst_wr <= 0.15
            and reclaim is not None and len(drifts) >= 5
            and reclaim >= 0.6 and (avg_fwd or 0) > -0.005):
        return out("exit_too_tight",
                   f"widen/slow the '{worst_exit}' path on {where} — {reclaim:.0%} of "
                   f"losing exits reclaimed entry within 24h (fwd {avg_fwd:+.1%}); "
                   f"do NOT tighten entries")
    # 2. VENUE/EXECUTION: same signal is profitable on the Lighter twin.
    if twin_pnl is not None and pnl < 0 < twin_pnl and twin_n >= 5:
        return out("venue_execution",
                   f"{where}: signal survives on the Lighter twin (${twin_pnl:+.2f} "
                   f"vs paper ${pnl:+.2f}) — fix venue/fees, not the strategy")
    # 3. FEE BLEED: median loss is fee-scale — costs, not direction.
    if fee_share is not None and fee_share >= 0.5 and med_loser <= 0.012:
        return out("fee_bleed",
                   f"{where} losses are fee-scale (median loser {med_loser:.2%} vs "
                   f"~{fee_rt:.2%} round-trip) — raise band/edge floors or move venue; "
                   f"signals are not the lever")
    # 4. REGIME TIMING: losses cluster in oracle risk-off windows.
    if counter_share is not None and counter_share >= 0.7:
        return out("regime_timing",
                   f"gate {where} entries on the shared regime — {counter_share:.0%} "
                   f"of matched losses opened during oracle risk-off")
    # 5. ENTRY QUALITY: price kept falling after losing exits — the exits were
    #    right, the entries were wrong. The ONLY case that earns the old
    #    "tighten the entry gates" prose.
    if reclaim is not None and len(drifts) >= 5 and reclaim <= 0.35 and (avg_fwd or 0) < 0:
        return out("entry_quality",
                   f"tighten the '{tag}' entry gates on {bot} — post-exit drift "
                   f"confirms the entries were wrong (only {reclaim:.0%} reclaimed, "
                   f"fwd {avg_fwd:+.1%})")
    return out("mixed_unclear",
               f"{where} is negative but no single lever dominates yet "
               f"(worst path '{worst_exit}' {worst_share:.0%} of losses) — keep sampling")


def compute_stake_mults(cards, state, run_no):
    """[2026-07-14 L4] Reduce-only per-(bot, tag) stake multipliers.

    Rule table (era trades only — ERA_START already applied to the cards):
        n >= MULT_MIN_N,  pnl < 0, wr < 25%          -> 0.50x
        n >= MULT_MIN_N,  pnl < 0, wr < 40%          -> 0.75x
        MULT_SOFT_N <= n < MULT_MIN_N, pnl < 0, wr < 25% -> 0.75x
    A computed reduction must recur on PROMOTE_RUNS consecutive runs before
    it publishes (streak-gated); one bad day never throttles anything. A tag
    that stops qualifying resets its streak and drops from the published set
    immediately — the brain forgives as gracefully as it forgets.
    Returns {bot: {tag: {mult, n, wr, pnl, streak}}} of PUBLISHED entries.
    """
    streaks = state.setdefault("mult_streaks", {})
    seen = set()
    for bot, c in cards.items():
        for tag, b in c.get("by_tag", {}).items():
            if tag == "(untagged)":
                continue   # no strategy passes this tag — a mult here is pure noise
            n, w, pnl = b["n"], b["w"], b["pnl"]
            wr = w / n if n else 0.0
            mult = None
            if n >= MULT_MIN_N and pnl < 0 and wr < 0.25:
                mult = 0.5
            elif n >= MULT_MIN_N and pnl < 0 and wr < 0.40:
                mult = 0.75
            elif MULT_SOFT_N <= n < MULT_MIN_N and pnl < 0 and wr < 0.25:
                mult = 0.75
            if mult is None:
                continue
            key = f"{bot}|{tag}"
            seen.add(key)
            e = streaks.setdefault(key, {"streak": 0, "first_run": run_no})
            e["streak"] += 1
            e["last_run"] = run_no
            e.update({"mult": mult, "n": n, "wr": round(wr * 100, 1), "pnl": round(pnl, 2)})
    # Streak resets: qualification must be CONSECUTIVE runs.
    for key in list(streaks):
        if key not in seen:
            del streaks[key]
    published = defaultdict(dict)
    for key, e in streaks.items():
        if e["streak"] >= PROMOTE_RUNS:
            bot, tag = key.split("|", 1)
            published[bot][tag] = {"mult": e["mult"], "n": e["n"], "wr": e["wr"],
                                   "pnl": e["pnl"], "streak": e["streak"]}
    return dict(published)


def _publish_stake_mults(published):
    """Write the multiplier payload to bot_state (+history) — guarded."""
    try:
        import bot_pnl_store as store
        payload = {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   "ttl_sec": MULT_TTL_SEC, "mode": "reduce-only",
                   "min_n": MULT_MIN_N, "promote_runs": PROMOTE_RUNS,
                   "mults": published}
        ok = store.save_state(MULT_KEY, payload)
        try:
            store.save_history(MULT_KEY, payload)
        except Exception:
            pass
        return bool(ok)
    except Exception:
        return False


def venue_ab_report():
    """[2026-07-14 REACH] Paper book vs Lighter shadow twin, from bot_pnl.

    The shadow books (rows '<bot>-lshadow', live '<bot>-lighter') have been
    collecting since 13 Jul — the first venue A/B data the fleet has. Same
    strategy, different venue: a persistent gap is execution/funding, not
    signal. Returns {base_bot: {"paper": {...}, "shadow": {...}, "gap_pnl"}}.
    """
    try:
        import bot_pnl_store as store
        rows = store.fetch_bot_pnl()
        if not rows:
            return {}
        by_bot = {r["bot"]: r for r in rows}
        out = {}
        for name, r in by_bot.items():
            for suffix in ("-lshadow", "-lighter"):
                if not name.endswith(suffix):
                    continue
                base = name[: -len(suffix)]
                twin = by_bot.get(base)
                if not twin:
                    continue

                def _pick(row):
                    return {"equity": row.get("equity"), "pnl_abs": row.get("pnl_abs"),
                            "wins": row.get("wins"), "losses": row.get("losses"),
                            "open": row.get("open_trades")}
                e = out.setdefault(base, {"paper": _pick(twin)})
                e["shadow" if suffix == "-lshadow" else "live"] = _pick(r)
                try:
                    e["gap_pnl"] = round((r.get("pnl_abs") or 0) - (twin.get("pnl_abs") or 0), 2)
                except Exception:
                    pass
        return out
    except Exception:
        return {}


def main():
    trades = _fetch_trades()
    state, src = _load_state()
    state["runs"] = int(state.get("runs", 0)) + 1
    run_no = state["runs"]
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")

    by_bot = defaultdict(list)
    for t in trades:
        by_bot[t.get("bot", "?")].append(t)

    pulse_hist = _load_pulse_history()
    cards, all_hyps, era_trades = {}, [], {}
    for bot, trs in sorted(by_bot.items()):
        era = ERA_START.get(bot)
        trs_era = [t for t in trs if str(t.get("open_ts") or "") >= era] if era else trs
        era_trades[bot] = trs_era
        cards[bot], hyps = analyse_bot(bot, trs_era, pulse_hist)
        cards[bot]["n_lifetime"] = len(trs)
        cards[bot]["era"] = era or "all-time"
        all_hyps.extend(hyps)

    # [2026-07-14b DIAGNOSIS] For every negative (bot, tag) bucket at sample
    # size, name the LEVER (entry / exit / fee / regime / venue) instead of the
    # old blanket entry-gate prose. Reuses the same hypothesis keys
    # ('{bot}|tag:{tag}') so existing streaks carry over — the prose upgrades,
    # the persistence memory survives.
    venue_ab = venue_ab_report()
    regime_hist = _load_regime_history()
    drift_budget = {"left": 120}   # bounds Kraken candle work per run
    diagnoses = {}
    for bot, trs in sorted(era_trades.items()):
        buckets = defaultdict(list)
        for t in trs:
            buckets[str(t.get("enter_tag") or "(untagged)")].append(t)
        for tag, bucket in sorted(buckets.items()):
            d = diagnose(bot, tag, bucket, regime_hist, venue_ab, drift_budget)
            if d is None:
                continue
            diagnoses[f"{bot}|{tag}"] = d
            b = d["evidence"]
            all_hyps.append({
                "key": f"{bot}|tag:{tag}", "kind": f"diag_{d['primary']}",
                "evidence": (f"'{tag}': n={b['n']}, ${b['pnl']:+.2f}; worst path "
                             f"'{b['worst_exit']}' ({b['worst_share']:.0%} of losses, "
                             f"wr {b['worst_wr']:.0%}); drift n={b['drift_n']} "
                             f"reclaim={b['reclaim']} fwd={b['avg_fwd']}; "
                             f"fee_share={b['fee_share']}; "
                             f"counter_regime={b['counter_regime']}"),
                "proposal": d["proposal"],
            })

    # Reconcile hypotheses with cumulative state: persistence -> promotion.
    seen_now = {h["key"] for h in all_hyps}
    hstate = state.setdefault("hypotheses", {})
    for h in all_hyps:
        e = hstate.setdefault(h["key"], {"first_run": run_no, "seen": 0, "status": "candidate"})
        e["seen"] += 1
        e["last_run"] = run_no
        e["evidence"] = h["evidence"]
        e["proposal"] = h["proposal"]
        e["kind"] = h["kind"]
        if e["seen"] >= PROMOTE_RUNS and e["status"] == "candidate":
            e["status"] = "ACTIONABLE"
    for k, e in hstate.items():
        if k not in seen_now and e.get("status") != "retired" and \
           run_no - e.get("last_run", run_no) >= PROMOTE_RUNS:
            e["status"] = "retired"   # pattern faded — the brain forgets gracefully

    actionable = {k: e for k, e in hstate.items() if e["status"] == "ACTIONABLE"}
    candidates = {k: e for k, e in hstate.items() if e["status"] == "candidate"}

    # [2026-07-14 L4] Numeric stake multipliers — computed every run, streak-
    # gated, published reduce-only. Strategies consume via fleet_bus.
    published_mults = compute_stake_mults(cards, state, run_no)
    mults_saved = _publish_stake_mults(published_mults)

    # [2026-07-14 REACH] Venue A/B computed above (feeds diagnosis too).
    state["venue_ab"] = venue_ab

    # [2026-07-14b] Publish the diagnoses — same freshness contract as the
    # multipliers. Advisory: consumers are humans + the dashboard; nothing
    # trades on this directly.
    try:
        import bot_pnl_store as store
        diag_payload = {"updated": now, "ttl_sec": MULT_TTL_SEC,
                        "diagnoses": diagnoses}
        store.save_state(DIAG_KEY, diag_payload)
        try:
            store.save_history(DIAG_KEY, diag_payload)
        except Exception:
            pass
    except Exception:
        pass
    state["diagnoses"] = diagnoses

    # ---- write lessons_latest.md ------------------------------------------
    os.makedirs(REPORTS_DIR, exist_ok=True)
    L = [f"# Fleet lessons — run {run_no} @ {now} (state: {src})", ""]
    L.append("Generated by bot_learn.py from the durable trade ledger. PROPOSALS ONLY — "
             "nothing here changes a bot until a human (or the trainer's promotion "
             "path) ships it.\n")
    # Only show entries the CURRENT era's data still supports this run —
    # stale ones decay to retired quietly instead of nagging.
    live_act = {k: e for k, e in actionable.items() if e.get("last_run") == run_no}
    live_cand = {k: e for k, e in candidates.items() if e.get("last_run") == run_no}
    if live_act:
        L.append("## ** ACTIONABLE ** (persisted across ≥%d runs of current-era data)" % PROMOTE_RUNS)
        for k, e in sorted(live_act.items()):
            L.append(f"- **{e['proposal']}**  \n  evidence: {e['evidence']} "
                     f"(seen {e['seen']} runs since run {e['first_run']})")
        L.append("")
    if live_cand:
        L.append("## Candidate hypotheses (watching — not yet actionable)")
        for k, e in sorted(live_cand.items()):
            L.append(f"- {e['proposal']}  \n  evidence: {e['evidence']} (seen {e['seen']}/{PROMOTE_RUNS})")
        L.append("")
    # [2026-07-14 L4] Published stake multipliers — the brain's live handle
    # on sizing. Empty section = every tag is trading at full stake.
    L.append("## Stake multipliers in force (bot_state '%s', reduce-only)" % MULT_KEY)
    if published_mults:
        for bot, tags in sorted(published_mults.items()):
            for tag, m in sorted(tags.items()):
                L.append(f"- **{bot} / {tag} -> {m['mult']}x**  "
                         f"(n={m['n']}, wr={m['wr']}%, pnl ${m['pnl']:+.2f}, "
                         f"streak {m['streak']} runs)")
    else:
        L.append("- none — no tag currently clears the floor "
                 f"(n>={MULT_SOFT_N}, negative pnl, {PROMOTE_RUNS} consecutive runs)")
    L.append("")
    # [2026-07-14b] Diagnoses — WHY each negative sleeve loses (the lever).
    if diagnoses:
        L.append("## Diagnoses (which lever each negative sleeve needs)")
        for key, d in sorted(diagnoses.items()):
            L.append(f"- **[{d['primary']}]** {d['proposal']}")
        L.append("")
    # [2026-07-14 REACH] Venue A/B — same strategy, Kraken paper vs Lighter.
    ab_lines = []
    for base, e in sorted(venue_ab.items()):
        for arm in ("shadow", "live"):
            if arm not in e:
                continue
            p, s = e["paper"], e[arm]
            ab_lines.append(
                f"- {base}: paper ${p.get('pnl_abs') or 0:+.2f} "
                f"({p.get('wins') or 0}W/{p.get('losses') or 0}L) vs {arm} "
                f"${s.get('pnl_abs') or 0:+.2f} ({s.get('wins') or 0}W/{s.get('losses') or 0}L)")
    if ab_lines:
        L.append("## Venue A/B (paper vs Lighter twins — execution/funding gap, not signal)")
        L.extend(ab_lines)
        L.append("")
    L.append("## Per-bot scorecards (closed trades, all time in ledger)")
    for bot, c in sorted(cards.items()):
        if c["n"] == 0:
            continue
        era_note = "" if c.get("era") == "all-time" else \
            f" (current era since {str(c.get('era'))[:10]}; lifetime n={c.get('n_lifetime', c['n'])})"
        L.append(f"\n### {bot} — n={c['n']}, win {c['wr']}%, pnl ${c['pnl']:+.2f}{era_note}")
        top_exit = sorted(c["by_exit"].items(), key=lambda x: -x[1]["n"])[:4]
        L.append("  exits: " + "; ".join(
            f"{k} n={v['n']} wr={v['w']/v['n']*100:.0f}% ${v['pnl']:+.2f}" for k, v in top_exit))
        durs = sorted(c["by_dur"].items())
        L.append("  holds: " + "; ".join(
            f"{k} n={v['n']} wr={v['w']/v['n']*100:.0f}%" for k, v in durs))
        if c.get("by_mood"):
            L.append("  mood: " + "; ".join(
                f"{k} n={v['n']} wr={(v['w']/v['n']*100 if v['n'] else 0):.0f}%"
                for k, v in c["by_mood"].items()) +
                f" (matched {c.get('mood_matched', 0)}/{c['n']})")
    with open(LESSONS_MD, "w") as f:
        f.write("\n".join(L) + "\n")

    saved = _save_state(state)
    n_mults = sum(len(t) for t in published_mults.values())
    print(f"[bot_learn] run {run_no}: {len(trades)} closed trades, "
          f"{len(live_act)} actionable, {len(live_cand)} candidates (current-era), "
          f"{n_mults} stake-mults published ({'ok' if mults_saved else 'no-db'}), "
          f"{len(diagnoses)} diagnoses, venue A/B pairs: {len(venue_ab)} "
          f"-> {LESSONS_MD} (state: {'+'.join(saved) or 'NOT SAVED'})")
    for key, d in sorted(diagnoses.items()):
        print(f"  DIAGNOSIS [{d['primary']}]: {d['proposal']}")
    for k, e in sorted(live_act.items()):
        print(f"  ACTIONABLE: {e['proposal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
