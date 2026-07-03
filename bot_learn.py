#!/usr/bin/env python3
"""
bot_learn.py — the fleet's learning loop ("brain"), v1.  READ-ONLY / ADVISORY.

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

WHAT IT NEVER DOES
  Change configs, strategies or trades. Humans (or, later, the cloud trainer's
  promotion path) act on its proposals. This is the "brain grows" half; the
  "hands" stay under human control by design — see NO_REAL_MONEY policy.

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
    with urllib.request.urlopen(TRADES_URL, timeout=30) as r:
        d = json.loads(r.read().decode())
    trades = d if isinstance(d, list) else d.get("trades", d.get("data", []))
    return [t for t in trades if isinstance(t, dict) and not t.get("is_open")]


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
    # Entry-mode expectancy.
    for tag, b in card["by_tag"].items():
        if b["n"] >= MIN_N_FLAG + 2 and b["pnl"] < 0 and b["w"] / b["n"] < max(0.25, wr * 0.6):
            hyp(f"tag:{tag}", "mode_negative",
                f"mode '{tag}': {b['n']} trades, {b['w']/b['n']*100:.0f}% win, ${b['pnl']:+.2f}",
                f"tighten the '{tag}' entry gates on {bot} (quality over quantity)")
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
    cards, all_hyps = {}, []
    for bot, trs in sorted(by_bot.items()):
        cards[bot], hyps = analyse_bot(bot, trs, pulse_hist)
        all_hyps.extend(hyps)

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

    # ---- write lessons_latest.md ------------------------------------------
    os.makedirs(REPORTS_DIR, exist_ok=True)
    L = [f"# Fleet lessons — run {run_no} @ {now} (state: {src})", ""]
    L.append("Generated by bot_learn.py from the durable trade ledger. PROPOSALS ONLY — "
             "nothing here changes a bot until a human (or the trainer's promotion "
             "path) ships it.\n")
    if actionable:
        L.append("## ** ACTIONABLE ** (persisted across ≥%d runs)" % PROMOTE_RUNS)
        for k, e in sorted(actionable.items()):
            L.append(f"- **{e['proposal']}**  \n  evidence: {e['evidence']} "
                     f"(seen {e['seen']} runs since run {e['first_run']})")
        L.append("")
    if candidates:
        L.append("## Candidate hypotheses (watching — not yet actionable)")
        for k, e in sorted(candidates.items()):
            L.append(f"- {e['proposal']}  \n  evidence: {e['evidence']} (seen {e['seen']}/{PROMOTE_RUNS})")
        L.append("")
    L.append("## Per-bot scorecards (closed trades, all time in ledger)")
    for bot, c in sorted(cards.items()):
        if c["n"] == 0:
            continue
        L.append(f"\n### {bot} — n={c['n']}, win {c['wr']}%, pnl ${c['pnl']:+.2f}")
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
    print(f"[bot_learn] run {run_no}: {len(trades)} closed trades, "
          f"{len(actionable)} actionable, {len(candidates)} candidates "
          f"-> {LESSONS_MD} (state: {'+'.join(saved) or 'NOT SAVED'})")
    for k, e in sorted(actionable.items()):
        print(f"  ACTIONABLE: {e['proposal']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
