#!/usr/bin/env python3
"""
market_pulse.py — keyless live NEWS / SOCIAL / POSITIONING collector ("pulse").

Feeds the fleet's brain with information beyond candles:
  - Fear & Greed index          (alternative.me, free)
  - Reddit r/CryptoCurrency + r/Bitcoin hot posts (public JSON, no auth)
  - CoinDesk + CoinTelegraph RSS headlines        (public, no auth)
  - Perp funding rates BTC/ETH/SOL                (Binance fapi public)

Scores a market "mood" in [-1, +1], flags PANIC events (hack/exploit/SEC/
depeg/liquidation-cascade headlines), and counts basket-coin mentions.

STORAGE
  - Postgres bot_state key 'market-pulse' (via bot_pnl_store) when
    DATABASE_URL is set — this is what the live bots + dashboard read.
    Keeps a rolling ~7-day hourly history INSIDE the blob so the brain
    (bot_learn.py) can correlate trades with the mood they were opened in.
  - Always ALSO writes reports/market_pulse_latest.md + market_pulse_state.json
    locally so laptop runs (the 2-hourly scan) see it without a DB.

CONSUMPTION POLICY (deliberate): pulse only modulates SIZING (see
DayTraderV5Gated.custom_stake_amount) and informs the brain/scans. It never
creates entries by itself — a signal earns entry-gate power only after the
brain shows a persistent edge correlation. Guarded everywhere: any source
failing, or no DB, degrades to neutral — never blocks trading.
"""
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
UA = {"User-Agent": "Mozilla/5.0 (crypto-fleet-pulse; dry-run research)"}

BASKET = ["BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "LINK",
          "DOT", "LTC", "BCH", "ATOM", "XLM", "TRX"]
COIN_WORDS = {  # common-name aliases -> ticker
    "bitcoin": "BTC", "ethereum": "ETH", "ether": "ETH", "solana": "SOL",
    "ripple": "XRP", "cardano": "ADA", "dogecoin": "DOGE", "avalanche": "AVAX",
    "chainlink": "LINK", "polkadot": "DOT", "litecoin": "LTC", "tron": "TRX",
    "stellar": "XLM", "cosmos": "ATOM",
}
PANIC_WORDS = ["hack", "hacked", "exploit", "stolen", "drained", "breach",
               "lawsuit", "sues", "sec charges", "bans", "banned", "bankrupt",
               "insolven", "liquidation cascade", "flash crash", "plunge",
               "depeg", "halted", "rug pull", "collapse", "crackdown", "seiz"]
POSITIVE_WORDS = ["etf inflow", "inflows", "approval", "approved", "adoption",
                  "partnership", "integration", "upgrade", "rally", "surge",
                  "all-time high", "institutional", "accumulat", "buyback",
                  "breakout", "reserve", "treasury adds", "halving"]


def _get(url, timeout=15, headers=None):
    req = urllib.request.Request(url, headers=headers or UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", "replace")


def _kw_hits(text_lower, words):
    """Word-boundary keyword count — 'ban' must not match 'bank'."""
    n = 0
    for w in words:
        if re.search(rf"(?<![a-z]){re.escape(w)}", text_lower):
            n += 1
    return n


def _score_text(text):
    """(-1..+1) keyword sentiment for one headline/title."""
    t = text.lower()
    neg = _kw_hits(t, PANIC_WORDS)
    pos = _kw_hits(t, POSITIVE_WORDS)
    if neg == pos == 0:
        return 0.0, False
    return max(-1.0, min(1.0, (pos - neg) / max(1, pos + neg))), neg > 0


def fetch_fear_greed():
    d = json.loads(_get("https://api.alternative.me/fng/?limit=1"))
    v = int(d["data"][0]["value"])
    return {"value": v, "label": d["data"][0].get("value_classification"),
            "norm": (v - 50) / 50.0}          # 0 fear..100 greed -> -1..+1


def fetch_reddit():
    titles = []
    for sub in ("CryptoCurrency", "Bitcoin"):
        try:
            d = json.loads(_get(f"https://www.reddit.com/r/{sub}/hot.json?limit=25"))
            for c in d.get("data", {}).get("children", []):
                p = c.get("data", {})
                if p.get("stickied"):
                    continue
                titles.append({"title": p.get("title", ""), "score": int(p.get("score") or 0),
                               "src": f"r/{sub}"})
        except Exception as e:
            titles.append({"title": f"[source error r/{sub}: {type(e).__name__}]",
                           "score": 0, "src": f"r/{sub}", "err": True})
    return titles


def fetch_rss():
    heads = []
    feeds = [("coindesk", "https://www.coindesk.com/arc/outboundfeeds/rss/"),
             ("cointelegraph", "https://cointelegraph.com/rss")]
    for name, url in feeds:
        try:
            raw = _get(url, timeout=20)
            # tolerant parse: pull <title> inside <item>
            items = re.findall(r"<item>(.*?)</item>", raw, re.S)[:20]
            for it in items:
                m = re.search(r"<title>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</title>", it, re.S)
                if m:
                    t = re.sub(r"\s+", " ", m.group(1)).strip()
                    if t:
                        heads.append({"title": t, "src": name})
        except Exception as e:
            heads.append({"title": f"[source error {name}: {type(e).__name__}]",
                          "src": name, "err": True})
    return heads


def fetch_btc_regime():
    """BTC 4h EMA50 vs EMA200 — the fleet's risk switch (same rule V5 trades)."""
    d = json.loads(_get("https://api.binance.com/api/v3/klines?symbol=BTCUSDT&interval=4h&limit=250"))
    closes = [float(c[4]) for c in d]
    def ema(vals, n):
        k = 2 / (n + 1)
        e = vals[0]
        for v in vals[1:]:
            e = v * k + e * (1 - k)
        return e
    e50, e200 = ema(closes, 50), ema(closes, 200)
    return {"risk_on": e50 > e200, "ema50": round(e50), "ema200": round(e200),
            "last": round(closes[-1])}


def fetch_funding():
    out = {}
    for sym in ("BTCUSDT", "ETHUSDT", "SOLUSDT"):
        try:
            d = json.loads(_get(f"https://fapi.binance.com/fapi/v1/premiumIndex?symbol={sym}"))
            r = float(d.get("lastFundingRate") or 0.0)
            out[sym[:-4]] = {"rate_8h": r, "apr": round(r * 3 * 365 * 100, 1)}
        except Exception:
            out[sym[:-4]] = None
    return out


def build_pulse():
    now = datetime.now(timezone.utc)
    sources_ok = {}
    try:
        fng = fetch_fear_greed(); sources_ok["fear_greed"] = True
    except Exception:
        fng = None; sources_ok["fear_greed"] = False
    reddit = fetch_reddit()
    sources_ok["reddit"] = not all(t.get("err") for t in reddit) if reddit else False
    rss = fetch_rss()
    sources_ok["rss"] = not all(h.get("err") for h in rss) if rss else False
    funding = fetch_funding()
    sources_ok["funding"] = any(v for v in funding.values())
    try:
        btc_regime = fetch_btc_regime()
        sources_ok["btc_regime"] = True
    except Exception:
        btc_regime = None
        sources_ok["btc_regime"] = False

    texts = [(t["title"], max(1, t.get("score", 1))) for t in reddit if not t.get("err")]
    texts += [(h["title"], 5) for h in rss if not h.get("err")]  # editorial weight

    sent_num = sent_den = 0.0
    panic_heads, mentions = [], {c: 0 for c in BASKET}
    for text, w in texts:
        s, is_panic = _score_text(text)
        sent_num += s * w
        sent_den += w
        if is_panic:
            panic_heads.append(text[:140])
        tl = text.lower()
        for c in BASKET:
            if re.search(rf"\b{c.lower()}\b", tl):
                mentions[c] += 1
        for word, tick in COIN_WORDS.items():
            if word in tl:
                mentions[tick] += 1
    text_sent = (sent_num / sent_den) if sent_den else 0.0

    # Composite mood: F&G 40%, text sentiment 45%, funding lean 15%.
    fund_vals = [v["rate_8h"] for v in funding.values() if v]
    fund_lean = 0.0
    if fund_vals:
        # very positive funding = crowded longs/euphoria; very negative = fear
        fund_lean = max(-1.0, min(1.0, (sum(fund_vals) / len(fund_vals)) / 0.0005))
    mood = round(0.40 * (fng["norm"] if fng else 0.0)
                 + 0.45 * text_sent + 0.15 * fund_lean, 3)
    panic = len(panic_heads) >= 3      # one scary headline is noise; a cluster is a signal

    top_mentions = {k: v for k, v in sorted(mentions.items(), key=lambda x: -x[1]) if v > 0}
    return {
        "ts": now.isoformat(timespec="seconds"),
        "mood": mood, "panic": panic,
        "fear_greed": (fng or {}).get("value"),
        "text_sentiment": round(text_sent, 3),
        "funding": funding,
        "btc_regime": btc_regime,
        "panic_headlines": panic_heads[:6],
        "coin_mentions": top_mentions,
        "headlines": [h["title"][:120] for h in rss if not h.get("err")][:10],
        "sources_ok": sources_ok,
    }


# [2026-07-14 HISTORY-WINDOW FIX] The 200-entry cap assumed hourly appends
# ("~7d at 1/h") but the pulse loops every ~10 min, so the rolling window had
# silently shrunk to ~33 HOURS — the brain's mood-conditioned analysis and the
# Jul-14 review's panic study were reading a fraction of the intended history.
# [2026-07-15] Operator: append every 30 MIN not hourly — "more data to better
# inform" the brain/board. Cap bumped to 400 so the ~8-day window holds at the
# doubled resolution (latest still refreshes every ~10-min run).
HIST_MIN_GAP_SEC = int(os.environ.get("PULSE_HIST_GAP_SEC", "1740"))   # ~29 min
HIST_CAP = int(os.environ.get("PULSE_HIST_CAP", "400"))                # ~8d at 2/h


def append_hourly(hist, pulse):
    """Append a compact history entry unless the newest is <55 min old."""
    try:
        if hist:
            last = datetime.fromisoformat(str(hist[-1].get("ts", "")).replace("Z", "+00:00"))
            now = datetime.fromisoformat(str(pulse["ts"]).replace("Z", "+00:00"))
            if (now - last).total_seconds() < HIST_MIN_GAP_SEC:
                return hist
    except (ValueError, TypeError):
        pass  # unparsable ts -> append rather than silently stall the history
    hist.append({"ts": pulse["ts"], "mood": pulse["mood"],
                 "fng": pulse["fear_greed"], "panic": pulse["panic"],
                 # funding APRs per coin: lets the brain correlate perps
                 # trades with crowd positioning at open (squeeze evidence)
                 "funding": {k: v["apr"] for k, v in pulse["funding"].items() if v}})
    return hist


def save(pulse):
    saved = []
    # Durable copy + rolling history for the brain.
    try:
        import bot_pnl_store as store
        prev = store.load_state("market-pulse") or {}
        hist = append_hourly(prev.get("history", []), pulse)
        # [2026-07-15] carry the fleet freshness contract (updated+ttl_sec) so
        # respiration / immune / fleet_bus can read pulse's age — it had none,
        # which made the respiration organ false-flag it as a dead feed.
        state = {"latest": pulse, "history": hist[-HIST_CAP:],
                 "updated": pulse["ts"], "ttl_sec": 3600}
        if store.save_state("market-pulse", state):
            saved.append("postgres")
    except Exception:
        pass
    # Local copies (laptop scans / no-DB mode).
    try:
        os.makedirs(REPORTS_DIR, exist_ok=True)
        loc = os.path.join(REPORTS_DIR, "market_pulse_state.json")
        prev = {}
        if os.path.exists(loc):
            try:
                prev = json.load(open(loc))
            except Exception:
                prev = {}
        hist = append_hourly(prev.get("history", []), pulse)
        json.dump({"latest": pulse, "history": hist[-HIST_CAP:],
                   "updated": pulse["ts"], "ttl_sec": 3600}, open(loc, "w"), indent=1)
        md = [f"# Market pulse — {pulse['ts']}",
              f"- **Mood: {pulse['mood']:+.2f}**  (F&G {pulse['fear_greed']}, "
              f"text {pulse['text_sentiment']:+.2f})",
              f"- **Panic flag: {'YES' if pulse['panic'] else 'no'}**",
              f"- Funding APR: " + ", ".join(f"{k} {v['apr']:+.0f}%" for k, v in
                                             pulse["funding"].items() if v),
              f"- Hot coins: " + ", ".join(f"{k}({v})" for k, v in
                                           list(pulse["coin_mentions"].items())[:8])]
        if pulse["panic_headlines"]:
            md.append("\n## Panic headlines\n" +
                      "\n".join(f"- {h}" for h in pulse["panic_headlines"]))
        md.append("\n## Latest headlines\n" +
                  "\n".join(f"- {h}" for h in pulse["headlines"]))
        open(os.path.join(REPORTS_DIR, "market_pulse_latest.md"), "w").write("\n".join(md) + "\n")
        saved.append("local")
    except Exception:
        pass
    return saved


def main():
    pulse = build_pulse()
    saved = save(pulse)
    print(f"[pulse] mood {pulse['mood']:+.2f} | F&G {pulse['fear_greed']} | "
          f"panic={pulse['panic']} | sources {pulse['sources_ok']} | saved: {'+'.join(saved) or 'NONE'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
