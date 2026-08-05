#!/usr/bin/env python3
"""
market_pulse.py — keyless live NEWS / SOCIAL / POSITIONING collector ("pulse").

Feeds the fleet's brain with information beyond candles:
  - Fear & Greed index          (alternative.me, free)
  - Reddit r/CryptoCurrency + r/Bitcoin hot posts (public JSON, no auth)
  - CoinDesk + CoinTelegraph RSS headlines        (public, no auth)
  - BTC 4h regime + perp funding BTC/ETH/SOL      (LIGHTER public REST)

Scores a market "mood" in [-1, +1], flags PANIC events (hack/exploit/SEC/
depeg/liquidation-cascade headlines), and counts basket-coin mentions.

-----------------------------------------------------------------------------
[2026-07-17] LIGHTER-FIRST VENUE SWAP — price + funding left Binance.
  audit_venue_purity.py flagged this file's two PRICE/FUNDING feeds as
  violations of the standing "all services must run off lighter" decision.
  The exception this file had been handed ("news/sentiment feeds, not price
  data") was TRUE of the news hosts and FALSE of these two:
    fetch_btc_regime()  api.binance.com  klines       -> Lighter /api/v1/candles
    fetch_funding()     fapi.binance.com premiumIndex -> Lighter /funding-rates
  The NEWS/SENTIMENT feeds STAY on their own hosts and are a PRINCIPLED,
  permanent exception — Lighter does not publish news. Do not "fix" them.

VERDICT (MEASURED 2026-07-17 against both live APIs, same window — a source
swap must be behaviour-neutral or measured, so it was measured):
  * REGIME: **NO BEHAVIOUR CHANGE**. Replaying this exact rule (4h EMA50 vs
    EMA200 over a 250-bar trailing window) at every step across 500 aligned
    4h bars, 2026-04-25 -> 2026-07-17: verdict AGREEMENT 251/251 = 100.0%,
    ZERO flips. Lighter was missing 0 of Binance's 500 bars (no coverage
    gap on BTC). Close divergence median 0.054%, max 0.094% (perp vs spot
    basis). Spot verdict at swap time identical on both: risk_on=True,
    ema50/ema200 spread +1.65% either way.
  * FUNDING: numerically DIFFERENT by construction — it is a different
    venue's funding, which is the entire point of the swap. At swap time
    Lighter BTC/ETH/SOL all sat at the venue's RESTING DEFAULT (9.6e-05 per
    8h == 10.512% true APR) while Binance showed dispersion (+8.56% /
    +4.60% / +0.25% apr). fund_lean therefore moved +0.0816 -> +0.1920,
    i.e. mood +0.0166 on a [-1,+1] scale (funding is 15% of mood). Mood is
    ADVISORY (see CONSUMPTION POLICY); `panic` — the one consumed field —
    is news-derived and untouched.

LIMITATIONS (read before trusting the verdict above)
  * The 100% regime agreement is measured over ~83 days of ONE coin (BTC).
    It is evidence the two series agree on this rule in this window, not a
    proof they always will. The generic claim it rhymes with is the wider
    one already on the record: regime_oracle's real classify() agrees on
    99.4% of coin-days when fed Lighter instead of HL candles
    (scripts/study_lighter_vs_hl_equivalence.py).
  * Lighter's funding is ASYMMETRIC on BTC and this is NOT a defect to
    tune around: over the settled series (751 hourly rows, /api/v1/fundings)
    BTC tops out at exactly the resting default on the long side (max
    +0.0012 %/hr) while ranging to -0.0045 %/hr on the short side, and sits
    at the resting magnitude 43.5% of the time (23 distinct values — it
    moves, it is not pinned). So fund_lean now has a ceiling near +0.19 but
    can still reach ~-0.7. The mood weights and the 0.0005 lean divisor are
    DELIBERATELY UNCHANGED: this commit swaps a source, it does not re-tune
    a signal. Re-denominating fund_lean to Lighter's own distribution is a
    separate, evidence-gated decision.
  * Both venues quote funding per 8h (funding_basis: binance=3/day,
    lighter=3/day), so `rate_8h` keeps its exact meaning and the 0.0005
    divisor stays dimensionally honest across the swap. The conversion goes
    through funding_basis regardless — never hardcode a venue's basis.
  * Lighter's /funding-rates rate is SIGNED (measured: 17 of 201 lighter
    rows negative), like Binance's lastFundingRate. fund_lean's sign
    semantics ("positive = crowded longs") survive the swap. Note this is
    the OPPOSITE convention to /api/v1/fundings, whose rate is unsigned
    with a separate `direction` field — do not cross the two.

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
import time
import urllib.request
from datetime import datetime, timezone

# BARE import, deliberately (born-dark guard, CLAUDE.md): funding_basis is the
# fleet's only authority on a venue's funding period, and Dockerfile.freqtrade
# — the one image that ships market_pulse.py (run_all.sh) — already COPYs it.
# A try/except here would turn a missing COPY into a SILENT wrong-by-8x APR,
# which is the exact failure class that guard exists for. Let it crash loudly.
import funding_basis

PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
REPORTS_DIR = os.path.join(PROJECT_DIR, "reports")
UA = {"User-Agent": "Mozilla/5.0 (crypto-fleet-pulse; dry-run research)"}

# --- Lighter: the fleet's venue (CLAUDE.md, user decision 2026-07-14) -------
LIGHTER_API = os.environ.get("LIGHTER_API_BASE",
                             "https://mainnet.zklighter.elliot.ai")
LIGHTER_VENUE = "lighter"          # the funding_basis key — never a bare 3*365
FUNDING_COINS = ("BTC", "ETH", "SOL")
REGIME_COIN = "BTC"
REGIME_BARS = 250                  # unchanged: the Binance klines limit it replaces
# EMA200 on fewer than this many bars is arithmetic, not a regime. The Lighter
# equivalence study found a COVERAGE TRAP riding along with the venue swap
# (ZEC produced no verdict on 115 of 200 replayed days while HL published), so
# a short series must go NEUTRAL, never assert. 210 mirrors the same rule's
# floor in lighter_family_bot.btc_regime_up(). MEASURED for BTC 4h at the
# swap: Lighter returned all 500/500 bars Binance did — this floor is a guard
# against a future dark book, not a live gap.
REGIME_MIN_BARS = 210

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


_MARKET_IDS = {}          # symbol -> market_id, resolved once per process


def _lighter_market_id(symbol):
    """Lighter's market_id for a fleet symbol, from the venue's own book list.

    Resolved by SYMBOL rather than hardcoded (BTC is market_id 1 today) — a
    hardcoded id silently points at a DIFFERENT COIN if Lighter ever renumbers,
    which is the kind of wrong-but-quiet that no test catches. Raises if the
    book is absent, so the caller's existing guard degrades the field to None.
    """
    if not _MARKET_IDS:
        d = json.loads(_get(f"{LIGHTER_API}/api/v1/orderBookDetails", timeout=20))
        for b in d.get("order_book_details") or []:
            if b.get("symbol") is not None and b.get("market_id") is not None:
                _MARKET_IDS[str(b["symbol"])] = int(b["market_id"])
    if symbol not in _MARKET_IDS:
        raise KeyError(f"lighter has no book for {symbol!r}")
    return _MARKET_IDS[symbol]


def fetch_btc_regime():
    """BTC 4h EMA50 vs EMA200 — the fleet's risk switch (same rule V5 trades).

    [2026-07-17] Source swapped Binance klines -> Lighter /api/v1/candles.
    The RULE and the thresholds are untouched; measured 100.0% verdict
    agreement (251/251 windows) across the swap — see the module header.
    """
    mid = _lighter_market_id(REGIME_COIN)
    now = int(time.time())
    d = json.loads(_get(
        f"{LIGHTER_API}/api/v1/candles?market_id={mid}&resolution=4h"
        f"&start_timestamp={now - REGIME_BARS * 4 * 3600}&end_timestamp={now}"
        f"&count_back={REGIME_BARS}", timeout=20))
    # Lighter candle rows are dicts {t(ms), o,h,l,c,v}; t ASC. Sort defensively —
    # an EMA is order-dependent, and a silently reversed series would invert the
    # regime instead of failing.
    rows = sorted(d.get("c") or [], key=lambda c: int(c["t"]))
    closes = [float(c["c"]) for c in rows]
    if len(closes) < REGIME_MIN_BARS:
        raise ValueError(
            f"lighter {REGIME_COIN} 4h returned {len(closes)} bars < "
            f"{REGIME_MIN_BARS} — too short for EMA200; regime goes NEUTRAL "
            f"rather than assert a number computed from a stub series")

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
    """Perp funding for the majors, from LIGHTER's own book.

    [2026-07-17] Source swapped Binance premiumIndex -> Lighter
    /funding-rates. Output keys ('rate_8h'/'apr') are UNCHANGED and still mean
    exactly what they meant: both venues quote per 8h (funding_basis:
    binance=3/day, lighter=3/day), so the mood lean's 0.0005 divisor stays
    dimensionally honest. The conversion goes through funding_basis anyway —
    hardcoding `3 * 365` against a venue is how this fleet got an 8x-overstated
    APR everywhere for months.

    One endpoint carries every book, so unlike the old per-symbol loop a single
    fetch failure darkens all three — each still degrades to None, never to a
    fabricated 0.0 (a 0.0 rate is a real, meaningful value: flat funding).
    """
    out = {c: None for c in FUNDING_COINS}
    try:
        d = json.loads(_get(f"{LIGHTER_API}/api/v1/funding-rates", timeout=20))
        rows = d.get("funding_rates") or []
    except Exception:
        return out                     # dark feed -> every field None
    # This endpoint republishes binance/bybit/hyperliquid benchmark rows beside
    # Lighter's own. Filter to exchange == 'lighter' or the swap is cosmetic —
    # we'd be reading Binance's rate through a Lighter URL.
    lit = {}
    for row in rows:
        if row.get("exchange") != LIGHTER_VENUE:
            continue
        sym, rate = row.get("symbol"), row.get("rate")
        if sym is None or rate is None:
            continue
        lit[str(sym)] = float(rate)
    for coin in FUNDING_COINS:
        r = lit.get(coin)
        if r is None:
            continue                   # no Lighter book / absent row -> None
        apr_pct = funding_basis.to_apr_pct(r, LIGHTER_VENUE)
        out[coin] = {"rate_8h": r, "apr": round(apr_pct, 1)}
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
        # [2026-08-05 SEED GUARD] checked read — `history` is the rolling
        # hourly series the brain reads; a failed read that fell through as {}
        # RESET it to a single sample and the save made the wipe durable.
        # Degrade: skip the postgres sink this cycle (the other sinks still
        # save); the series resumes on the next clean read.
        _ok, prev = store.load_state_checked("market-pulse")
        if not _ok:
            raise RuntimeError("market-pulse state read failed — "
                               "not overwriting the hourly history")
        prev = prev or {}
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


def _selftest():
    """Offline proof of the 17-Jul venue swap's contract + fail-safes.

    Every fixture here is a NEGATIVE one where it can be: a detective control
    that only ever sees the happy path proves nothing (the lesson from
    audit_venue_purity's own missing negative fixture).
    """
    global _get, _MARKET_IDS
    real_get = _get

    def stub(fn):
        global _get
        _get = fn

    # --- 1. APR conversion is funding_basis's, on the LIGHTER basis ----------
    # The verified anchor: 9.6e-05 per 8h == 10.512% TRUE apr (NOT 84.1%, the
    # 8x-overstated number the fleet published for months).
    stub(lambda u, timeout=15, headers=None: json.dumps({"funding_rates": [
        {"market_id": 1, "exchange": "lighter", "symbol": "BTC", "rate": 9.6e-05},
        {"market_id": 0, "exchange": "lighter", "symbol": "ETH", "rate": -2.88e-04},
        {"market_id": 2, "exchange": "lighter", "symbol": "SOL", "rate": 0.0},
    ]}))
    f = fetch_funding()
    assert set(f) == {"BTC", "ETH", "SOL"}, f
    assert f["BTC"]["rate_8h"] == 9.6e-05 and abs(f["BTC"]["apr"] - 10.5) < 0.05, f["BTC"]
    assert abs(f["BTC"]["apr"] - funding_basis.to_apr_pct(9.6e-05, "lighter")) < 0.05
    # a NEGATIVE rate must survive as negative — fund_lean's whole meaning is
    # its sign, and /funding-rates is signed (unlike /api/v1/fundings)
    assert f["ETH"]["rate_8h"] < 0 and f["ETH"]["apr"] < 0, f["ETH"]
    # 0.0 is a REAL value (flat funding), not a missing one
    assert f["SOL"] is not None and f["SOL"]["rate_8h"] == 0.0, f["SOL"]

    # --- 2. NEGATIVE: benchmark rows must NOT be read as Lighter's own -------
    # /funding-rates republishes binance/bybit/hyperliquid beside lighter. If
    # the exchange filter ever breaks, the swap is cosmetic — we'd read
    # Binance's rate through a Lighter URL and the audit would call it clean.
    stub(lambda u, timeout=15, headers=None: json.dumps({"funding_rates": [
        {"exchange": "binance", "symbol": "BTC", "rate": 0.00099},
        {"exchange": "hyperliquid", "symbol": "BTC", "rate": 0.00077},
        {"exchange": "bybit", "symbol": "ETH", "rate": 0.00055},
    ]}))
    f = fetch_funding()
    assert all(v is None for v in f.values()), \
        f"foreign benchmark rows leaked in as Lighter funding: {f}"

    # --- 3. NEGATIVE: a dark feed yields None, never a fabricated value ------
    def boom(u, timeout=15, headers=None):
        raise OSError("simulated dark Lighter feed")
    stub(boom)
    f = fetch_funding()
    assert f == {"BTC": None, "ETH": None, "SOL": None}, f
    assert not any(v for v in f.values()), "sources_ok would falsely read OK"

    # --- 4. NEGATIVE: a SHORT candle series must NOT produce a regime --------
    # The coverage trap: Lighter can publish a book with far fewer bars than
    # the rule needs. ema(vals, 200) over 12 bars returns a number, happily.
    _MARKET_IDS = {"BTC": 1}
    stub(lambda u, timeout=15, headers=None: json.dumps({"c": [
        {"t": (1_700_000_000 + i * 14400) * 1000, "c": 100.0 + i} for i in range(12)]}))
    try:
        fetch_btc_regime()
        raise AssertionError("a 12-bar series must NOT yield a regime verdict")
    except ValueError as e:
        assert "too short" in str(e), e

    # --- 5. the regime contract + rule are unchanged by the swap -------------
    # A rising series -> EMA50 above EMA200 -> risk_on. Also proves the caller
    # gets the exact 4 keys the dashboard reads (risk_on/ema50/ema200/last).
    stub(lambda u, timeout=15, headers=None: json.dumps({"c": [
        {"t": (1_700_000_000 + i * 14400) * 1000, "c": 100.0 + i}
        for i in range(REGIME_BARS)]}))
    r = fetch_btc_regime()
    assert set(r) == {"risk_on", "ema50", "ema200", "last"}, r
    assert r["risk_on"] is True and r["ema50"] > r["ema200"], r
    assert r["last"] == round(100.0 + REGIME_BARS - 1), r
    # ...and a falling series flips it (the rule still discriminates)
    stub(lambda u, timeout=15, headers=None: json.dumps({"c": [
        {"t": (1_700_000_000 + i * 14400) * 1000, "c": 400.0 - i}
        for i in range(REGIME_BARS)]}))
    assert fetch_btc_regime()["risk_on"] is False

    # --- 6. NEGATIVE: an out-of-order series must not invert the regime ------
    # An EMA is order-dependent; a reversed feed would silently flip the switch.
    rising = [{"t": (1_700_000_000 + i * 14400) * 1000, "c": 100.0 + i}
              for i in range(REGIME_BARS)]
    stub(lambda u, timeout=15, headers=None: json.dumps({"c": list(reversed(rising))}))
    assert fetch_btc_regime()["risk_on"] is True, \
        "a DESC-ordered candle feed inverted the regime — sort is load-bearing"

    # --- 7. an unknown book raises (caller degrades to None) ----------------
    _MARKET_IDS = {"ETH": 0}
    try:
        _lighter_market_id("BTC")
        raise AssertionError("a missing book must raise, not guess an id")
    except KeyError:
        pass

    _get = real_get
    _MARKET_IDS = {}
    print("market_pulse selftest OK (lighter APR via funding_basis @ verified "
          "9.6e-05->10.5%, bench rows rejected, dark feed -> None, short "
          "series -> no verdict, DESC feed does not invert, regime contract "
          "held)")


def main():
    if "--selftest" in sys.argv:
        _selftest()
        return 0
    pulse = build_pulse()
    saved = save(pulse)
    print(f"[pulse] mood {pulse['mood']:+.2f} | F&G {pulse['fear_greed']} | "
          f"panic={pulse['panic']} | sources {pulse['sources_ok']} | saved: {'+'.join(saved) or 'NONE'}")
    return 0


if __name__ == "__main__":
    # [(hw)] imported HERE: this module imports bot_pnl_store lazily inside
    # its publish path, so there is no module-level `store` to reach.
    import bot_pnl_store as _store
    sys.exit(_store.organ_main('market-pulse', main))
