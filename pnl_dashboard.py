#!/usr/bin/env python3
"""
pnl_dashboard.py — ONE live page showing every bot's P&L, read from Postgres.

This is the new unified dashboard. Each bot publishes its snapshot to the
shared `bot_pnl` table (see bot_pnl_store.py); this service reads that table and
renders a mobile-friendly, auto-refreshing page on $PORT. Deploy it as its own
Railway service with DATABASE_URL pointed at the Postgres plugin.

  Local:   DATABASE_URL=postgres://...  python3 pnl_dashboard.py
  Railway: set DATABASE_URL (reference the Postgres service) + expose $PORT.

Deps: psycopg2-binary (see requirements.txt). Falls back to a clear message if
the DB is unreachable so the page never hard-crashes.
"""
import os
import json
import time
import base64
import html
import threading
import datetime as dt
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))

# Tiled "$ EJMC $" watermark painted behind the whole page — styled like a
# spraycan tag (grainy fill via feTurbulence, jittered per-glyph rotation,
# overspray speckle, paint drips). Kept faint — purely decorative, must never
# compete with card text for legibility.
_WATERMARK_TILE_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 900 360' "
    "preserveAspectRatio='xMidYMid meet'>"
    "<defs>"
    "<filter id='spray' x='-30%' y='-30%' width='160%' height='160%'>"
    "<feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' seed='7' result='n'/>"
    "<feColorMatrix in='n' type='matrix' "
    "values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.3 0' result='an'/>"
    "<feComposite in='SourceGraphic' in2='an' operator='in'/>"
    "</filter>"
    "<filter id='soft' x='-80%' y='-80%' width='260%' height='260%'>"
    "<feGaussianBlur stdDeviation='2.4'/>"
    "</filter>"
    "<linearGradient id='dripfade' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#f4f1e6' stop-opacity='0.95'/>"
    "<stop offset='55%' stop-color='#e8e4d5' stop-opacity='0.7'/>"
    "<stop offset='100%' stop-color='#d8d3c2' stop-opacity='0.1'/>"
    "</linearGradient>"
    # off-white paint fill — soft top-lit cream down to a shaded cream
    "<linearGradient id='paintgrad' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#fdfcf6'/>"
    "<stop offset='55%' stop-color='#f2efe4'/>"
    "<stop offset='100%' stop-color='#e4dfd0'/>"
    "</linearGradient>"
    "<linearGradient id='hlgrad' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#ffffff' stop-opacity='0.95'/>"
    "<stop offset='40%' stop-color='#ffffff' stop-opacity='0.2'/>"
    "<stop offset='70%' stop-color='#ffffff' stop-opacity='0'/>"
    "</linearGradient>"
    "</defs>"
    "<g opacity='0.9'>"
    # Graffiti marker handstyle — 'Permanent Marker' web font (loaded on the page;
    # this SVG is inline so it inherits it), skewed for the aggressive tag slant.
    # Falls back to other marker/handwritten faces, then cursive.
    f"<g transform='rotate(-5 450 200) skewX(-11)' "
    f"font-family=\"'Permanent Marker','Rock Salt','Bradley Hand',cursive\" "
    f"font-size='150' font-weight='400' text-anchor='middle'>"
    # soft cast shadow, offset down-right for depth against the light page
    "<text x='456' y='236' fill='#3b4652' opacity='0.28' filter='url(#soft)'>$ EJMC $</text>"
    # dark outline + spray-grained off-white fill (outline carries the contrast
    # on the light background, like a white tag reads against dark)
    "<text x='450' y='228' fill='url(#paintgrad)' stroke='#2c343d' stroke-width='4.5' "
    "stroke-linejoin='round' paint-order='stroke fill' filter='url(#spray)'>$ EJMC $</text>"
    # subtle sheen across the top of the strokes
    "<text x='450' y='228' fill='url(#hlgrad)' style='mix-blend-mode:screen'>$ EJMC $</text>"
    "</g>"
    # paint drips — thin near-straight runs with a small drop at the tip, the way
    # a marker/spray tag bleeds down. Scattered along the baseline.
    "<g opacity='0.9'>"
    "<rect x='178' y='232' width='3.4' height='96' rx='1.7' fill='url(#dripfade)'/>"
    "<circle cx='179.7' cy='330' r='4' fill='#d8d3c2' opacity='0.75'/>"
    "<rect x='262' y='236' width='2.8' height='60' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='263.4' cy='298' r='3.2' fill='#cfc9b8' opacity='0.62'/>"
    "<rect x='330' y='234' width='3.2' height='82' rx='1.6' fill='url(#dripfade)'/>"
    "<circle cx='331.6' cy='318' r='3.8' fill='#cfc9b8' opacity='0.66'/>"
    "<rect x='404' y='238' width='2.6' height='46' rx='1.3' fill='url(#dripfade)'/>"
    "<circle cx='405.3' cy='286' r='3' fill='#cfc9b8' opacity='0.58'/>"
    "<rect x='474' y='234' width='3.4' height='92' rx='1.7' fill='url(#dripfade)'/>"
    "<circle cx='475.7' cy='328' r='4' fill='#d8d3c2' opacity='0.75'/>"
    "<rect x='560' y='236' width='2.8' height='56' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='561.4' cy='294' r='3.2' fill='#cfc9b8' opacity='0.6'/>"
    "<rect x='648' y='234' width='3' height='72' rx='1.5' fill='url(#dripfade)'/>"
    "<circle cx='649.5' cy='308' r='3.6' fill='#cfc9b8' opacity='0.64'/>"
    "<rect x='736' y='236' width='2.8' height='50' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='737.4' cy='288' r='3.2' fill='#cfc9b8' opacity='0.6'/>"
    "</g>"
    # overspray speckle + faint spray-ring flourish, like a tag finished with the can
    "<circle cx='150' cy='150' r='4' fill='#cfc9b8' opacity='0.4' filter='url(#soft)'/>"
    "<circle cx='176' cy='128' r='2.2' fill='#cfc9b8' opacity='0.55'/>"
    "<circle cx='690' cy='150' r='3.6' fill='#cfc9b8' opacity='0.35' filter='url(#soft)'/>"
    "<circle cx='664' cy='170' r='2' fill='#cfc9b8' opacity='0.5'/>"
    "<circle cx='450' cy='92' r='3' fill='#cfc9b8' opacity='0.35' filter='url(#soft)'/>"
    "<circle cx='800' cy='196' r='13' fill='none' stroke='#cfc9b8' stroke-width='1.6' "
    "opacity='0.3' filter='url(#soft)'/>"
    "</g>"
    "</svg>"
)
# Rendered as an INLINE svg (fixed, behind the cards) rather than a CSS
# background-image, so it can use the 'Permanent Marker' web font — background
# SVGs are sandboxed and can't load page fonts, which is why a font swap needs
# this. The <link> for the font is added in the page <head>.
WATERMARK_HTML = f'<div class="wm" aria-hidden="true">{_WATERMARK_TILE_SVG}</div>'
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Login for THIS dashboard page (override via env on Railway).
DASH_USER = os.environ.get("DASH_USER", "eamon")
DASH_PASS = os.environ.get("DASH_PASS", "freqbot2026")

# [2026-07-11 SWAP] Decommissioned venue rows — hidden from the grid and every
# feed so a retired bot can't sit next to its replacement and confuse the LIVE
# section. History stays in bot_equity_history / paper_trades / venue_orders.
# Trail Blazer live retired 11 Jul; its sub-account + Railway service now run
# the Funding Farmer (publishes as perps-funding-lighter-lighter).
# [2026-07-12 DECOMMISSION] Bounce Catcher (perps-rsi-meanrev) + Loop Scout
# (scanner-triangular-arb) stopped on user sign-off: the 12-Jul audit found
# Bounce Catcher running the IDENTICAL entry to Trail Blazer's paper bot
# (REJECTED for edge 12 Jul), and Loop Scout carried a retire verdict since
# the 22-Jun revalidation. Railway services perps-bot + triangular-arb are
# down (empty shells left in the UI); momo-bot stays as the cluster's
# representative. The stale rsi-meanrev lshadow row from Gate-0 goes too.
# [2026-07-12 LOSER CUT] TrendMomoV1 (crypto-trendmomo-4h) retired on user
# sign-off: core leg -29%/4.5y on the tagged Binance replay (26.5% win), live
# bleeder (-$11.33). Removed from run_all.sh in the same commit.
# [2026-07-12 SAME-PAGE SWEEP] perps-donchian-breakout-lshadow was a Gate-0
# local run that stopped 10 Jul (stale ever since); its signal is the
# twice-retired range-buy, so the shadow is NOT restarted — row hidden.
# [2026-07-12 DASHBOARD SWEEP] Trail Blazer's PAPER row (perps-donchian-breakout)
# hidden on user request to clear the bots we're not going ahead with: the live
# half retired 11 Jul and the entry was REJECTED for edge in the 12-Jul audit
# (identical to Bounce Catcher's). NOTE the momo-bot Railway service still runs
# and re-publishes this row — hiding is dashboard-side only; stopping/keeping
# the service is a separate call. History stays in bot_equity_history /
# paper_trades. Also dropped from EXPECTED so no placeholder card returns.
RETIRED_ROWS = {"perps-donchian-breakout",
                "perps-donchian-breakout-lighter",
                "perps-donchian-breakout-lshadow",
                "perps-rsi-meanrev", "perps-rsi-meanrev-lshadow",
                "scanner-triangular-arb", "crypto-trendmomo-4h"}

# Expected bots — so the grid shows a bot even before its first publish.
EXPECTED = ["perps-regime-switch",
            "perps-funding-carry", "perps-funding-lighter", "lighter-perp-sniper",
            "lighter-dislocation", "perps-funding-spread",
            "event-listing-sniper",
            "crypto-trend-daily", "crypto-intraday-15m", "crypto-swing-daily",
            "crypto-breakout-4h",
            "freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia"]

# Scanners book OPTIMISTIC paper-arb fills (observed spreads, no slippage/latency).
# Their pnl_abs is real paper P&L but on a rosier basis than the freqtrade bots'
# simulated fills — so it is reported as a SEPARATE subtotal and never folded
# into the trading-bot P&L headline.
SCANNERS = {"scanner-cross-exchange-arb"}

# Stock/brokerage bots (IBKR + Alpaca). Shown as their own cards with a SEPARATE
# subtotal so their large $ equity never swamps the crypto headline.
STOCKS = {"equities-regime-ibkr", "equities-momentum-alpaca", "equities-momentum"}

# The only bots that should appear. Anything else in the table (e.g. legacy
# pre-rename rows perps-bot/momo-bot/v4core/v5gated/v6swing/v7momo/v8momo) is a
# stale duplicate and is filtered out here so it can never skew totals or the
# grid — independent of whether the Postgres table has been pruned yet.
# Freqtrade fleet bots (July 2026)
FREQTRADE = {"freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia"}
CURRENT_BOTS = set(EXPECTED) | SCANNERS | STOCKS | FREQTRADE

# [2026-07-09 LIGHTER GO-LIVE] Venue-variant rows. When a bot trades on Lighter
# its publisher suffixes the bot id by mode (venues/__init__._SUFFIX):
#   -lighter  = REAL MONEY live   (each on its own Lighter sub-account)
#   -ltest    = Lighter testnet   (real order lifecycle, faucet funds)
#   -lshadow  = shadow            (modelled fills on live books, NEVER sends)
# These are SEPARATE dashboard rows from the paper (hl_paper) bot so the paper
# equity curve is never contaminated. They are detected dynamically (not a fixed
# list) so whichever bots the user brings live just appear, each badged with its
# mode, and the LIVE fleet is reported as its own P&L subtotal.
VENUE_SUFFIXES = {
    "-lighter": ("LIVE", "#f85149", "lighter_live"),
    "-ltest":   ("TESTNET", "#d29922", "lighter_testnet"),
    "-lshadow": ("SHADOW", "#58a6ff", "lighter_shadow"),
}


def venue_variant(bot):
    """(base_bot, suffix_key) if `bot` is a venue-variant row, else (bot, None)."""
    for suf in VENUE_SUFFIXES:
        if bot.endswith(suf):
            return bot[:-len(suf)], suf
    return bot, None


def is_live_bot(bot):
    """True only for REAL-money Lighter rows (not shadow/testnet)."""
    return bot.endswith("-lighter")

# [2026-07-01] Professional display names. Keys stay machine-safe; the dashboard
# shows the descriptive label. label_for() falls back to the raw key if unmapped.
# [2026-07-05] Trendy names + a plain "what it does" tail so a glance tells you
# both the personality and the mechanism. Leading emoji = fast visual scanning.
LABELS = {
    "crypto-trend-daily":          "🌊 Tide Rider · daily 50/200 trend (long)",
    "crypto-intraday-15m":         "⚡ Range Raider · 1h adaptive range + bounce",
    "crypto-swing-daily":          "🩸 Dip Buyer · daily oversold dip (BB/RSI)",
    "crypto-breakout-4h":          "🚀 Breakout Hunter · 4h Donchian breakout",
    "crypto-trendmomo-4h":         "🏄 Momentum Surfer · daily SMA trend",
    "perps-rsi-meanrev":           "🪃 Bounce Catcher · perps range reversion",
    "perps-donchian-breakout":     "🧭 Trail Blazer · perps 4h breakout",
    "perps-regime-switch":         "⚖️ Two-Way Tide · long/short trend engine (perps)",
    "perps-funding-carry":         "🌾 Yield Harvester · perps funding carry",
    "perps-funding-lighter":       "💸 Funding Farmer · Lighter directional funding (stop-guarded)",
    "lighter-perp-sniper":         "🎯 Perp Sniper · new Lighter-listing snipe",
    "lighter-dislocation":         "🧲 Snap Back · Lighter dislocation harvester",
    "perps-funding-spread":        "⚖️ Counterweight · x-sect funding-spread book (L/S)",
    "scanner-triangular-arb":      "🔺 Loop Scout · triangular arb (scanner)",
    "scanner-cross-exchange-arb":  "🔀 Gap Scout · cross-exchange arb (scanner)",
    "event-listing-sniper":        "🎯 Launch Sniper · new-listing buyer",
    "equities-regime-ibkr":        "📊 Index Pilot · SPY/QQQ regime (IBKR)",
    "equities-momentum-alpaca":    "🏆 Stock Leaders · momentum rank (Alpaca)",
    "equities-momentum":           "🏆 Stock Leaders · momentum rank",
    # Freqtrade fleet — new bots July 2026
    "freqtrade-mum":               "👩 Mum · NFI X7 · 5m trend (Binance)",
    "freqtrade-dad":               "👨 Dad · E0V1E · 5m breakout (Binance/Kraken)",
    "freqtrade-avo-maria":         "🙏 Avo Maria · BinH+Cluc · 5m mean reversion",
    "freqtrade-georgia":           "🔮 Georgia · FreqAI LightGBM · 1H ML adaptive",
}
def label_for(bot):
    base, suf = venue_variant(bot)
    if suf:
        tag = VENUE_SUFFIXES[suf][0]
        return f"{LABELS.get(base, base)} — {tag} · Lighter"
    return LABELS.get(bot, bot)

# Paper bots (freqtrade + perps) all start with a $1,000 simulated balance, so
# total P&L = equity - this. Stocks/scanners report on their own basis.
PAPER_START_EQUITY = 1000.0

STALE_SECONDS = 180  # crypto bots loop fast; older than this = "stale"
# Stock bots publish far less often (IKBR every 2h, Alpaca daily), so they need a
# much longer window before they should be considered stale.
STOCK_STALE_SECONDS = 26 * 3600
# Some perps bots run on slow candle loops and publish far less often than the
# fast crypto bots: perps-donchian-breakout loops every 5 min (4h candles), so a
# 180s threshold flags it STALE every cycle even when it is perfectly healthy.
# Give slow-loop bots a wider window (~15 min = 3 missed publishes) so a real
# outage still shows, but a normal 5-min cadence does not read as "down".
SLOW_LOOP = {"perps-donchian-breakout",
             "perps-funding-carry",  # 5-min loop: funding only changes hourly
             "freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria"}  # freqtrade 5m bots
SLOW_LOOP_STALE_SECONDS = 15 * 60
# The listing sniper publishes once per scan cycle, and every ~5th cycle is a
# full exchange-list reload that can run 8-9 minutes when slow exchanges hit
# their HTTP timeouts — a healthy sniper regularly goes >180s between writes.
# Give it its own window so those reload cycles stop tripping a false stale
# flag (the sniper also heartbeats mid-cycle now, but keep this as the backstop).
SNIPER_STALE_SECONDS = 900
# [2026-07-12] Venue-variant rows do NOT always share their base's cadence —
# the Lighter Tide Rider loops HOURLY (its base row is fed by the fast
# freqtrade poller) and the Funding Farmer loops 300s (its base was never in
# SLOW_LOOP after it took over the live slot). Both healthy LIVE bots were
# flapping "stale" on the dashboard most of every cycle. Explicit per-ROW
# windows sized ~2 missed publishes, so a real outage still shows fast.
VARIANT_STALE_SECONDS = {
    "crypto-trend-daily-lighter":    2 * 3600 + 600,   # hourly loop + debounce slack
    "crypto-trend-daily-lshadow":    2 * 3600 + 600,
    "perps-funding-lighter-lighter": 15 * 60,          # 300s loop
    "perps-funding-lighter-lshadow": 15 * 60,
    "perps-funding-spread-lshadow":  15 * 60,          # 300s loop (Counterweight)
}


def stale_secs_for(bot):
    """Per-bot stale threshold: each bot family has its own publish cadence."""
    if bot in VARIANT_STALE_SECONDS:   # variant cadence differs from its base
        return VARIANT_STALE_SECONDS[bot]
    bot, _ = venue_variant(bot)   # other -lighter/-lshadow rows keep base cadence
    if bot in STOCKS:
        return STOCK_STALE_SECONDS
    if bot in SLOW_LOOP:
        return SLOW_LOOP_STALE_SECONDS
    if bot == "event-listing-sniper":
        return SNIPER_STALE_SECONDS
    return STALE_SECONDS


def fetch_rows():
    """Return {bot: row_dict}. Raises on DB error (caller handles)."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_pnl') AS t")
            if cur.fetchone()["t"] is None:
                return {}  # table not created yet (no bot has published)
            cur.execute("SELECT * FROM bot_pnl")
            # Drop legacy pre-rename rows so stale duplicates never reach the
            # grid, totals, or the /pnl.json feed. Venue-variant rows
            # (<base>-lighter/-ltest/-lshadow) pass when their base is a current
            # bot, so a live/shadow Lighter bot shows up automatically.
            return {r["bot"]: r for r in cur.fetchall()
                    if r["bot"] not in RETIRED_ROWS
                    and (r["bot"] in CURRENT_BOTS
                         or venue_variant(r["bot"])[0] in CURRENT_BOTS)}
    finally:
        conn.close()


def fetch_fleet_alerts(hours=48):
    """Recent evidence alerts written by market_context.evaluate_evidence into
    bot_state('fleet-alerts'). Guarded — no alerts is an answer, not an error."""
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_state') AS t")
                if cur.fetchone()[0] is None:
                    return []
                cur.execute("SELECT state FROM bot_state WHERE bot = 'fleet-alerts'")
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return []
        st = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        cut = time.time() - hours * 3600
        return [a for a in (st.get("alerts") or []) if (a.get("ts") or 0) >= cut]
    except Exception:
        return []


def fetch_analysis():
    """Return {strategy: {updated_at, analysis}} from bot_trade_analysis."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trade_analysis') AS t")
            if cur.fetchone()["t"] is None:
                return {}
            cur.execute("SELECT strategy, updated_at, analysis FROM bot_trade_analysis "
                        "ORDER BY strategy")
            return {r["strategy"]: r for r in cur.fetchall()}
    finally:
        conn.close()


def fetch_trades(bot=None, limit=500, include_open=False):
    """Return per-trade history rows from bot_trades (newest close first).

    Read-only; used by the no-auth /trades.json endpoint for the scheduled
    breakdowns and the win/loss deep dive. Dry-run paper trades only."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()["t"] is None:
                return []  # no bot has published trades yet
            clauses, params = [], []
            if not include_open:
                clauses.append("is_open = FALSE")
            if bot:
                clauses.append("bot = %s")
                params.append(bot)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(int(limit))
            cur.execute(
                "SELECT bot, open_ts, close_ts, pair, is_open, profit_ratio, "
                "profit_abs, open_rate, close_rate, amount, stake_amount, "
                "duration_min, enter_tag, exit_reason, leverage "
                f"FROM bot_trades {where} "
                "ORDER BY close_ts DESC NULLS LAST, open_ts DESC LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


# [2026-07-05 INSIGHT] Bots whose strategies were reworked 2026-07-03 — their
# cards split "since rework" stats from lifetime so the NEW code is judged on
# its own trades (same era map as bot_learn.py).
ERA_START = {
    "crypto-intraday-15m": "2026-07-03T06:00Z",
    "crypto-swing-daily": "2026-07-03T06:00Z",
    "crypto-breakout-4h": "2026-07-03T06:00Z",
    "crypto-trendmomo-4h": "2026-07-03T06:00Z",
    "perps-regime-switch": "2026-07-03T10:00Z",
}
# Standing status labels so the dashboard tells you how to READ each bot.
BADGES = {
    "crypto-intraday-15m": ("PROBATION", "#d29922"),
    "perps-regime-switch": ("EXPERIMENT", "#d29922"),
    "crypto-trend-daily": ("CONTROL", "#58a6ff"),
    "crypto-trendmomo-4h": ("SLOW BY DESIGN", "#8b949e"),
}


def fetch_bot_quality():
    """{bot: quality dict} from closed bot_trades — win rate, profit factor,
    expectancy and last-close age (the numbers raw W/L counts hide), plus
    'since rework' era stats for the 2026-07-03 strategy changes."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()[0] is None:
                return {}
            cur.execute("""
                SELECT bot, COUNT(*) AS n,
                       COUNT(*) FILTER (WHERE profit_abs > 0) AS w,
                       COALESCE(SUM(profit_abs) FILTER (WHERE profit_abs > 0), 0) AS gw,
                       COALESCE(SUM(profit_abs) FILTER (WHERE profit_abs < 0), 0) AS gl,
                       COALESCE(SUM(profit_abs), 0) AS pnl,
                       MAX(close_ts) AS last_close
                FROM bot_trades WHERE is_open = FALSE GROUP BY bot""")
            life = {r[0]: r[1:] for r in cur.fetchall()}
            era = {}
            for bot, start in ERA_START.items():
                cur.execute(
                    "SELECT COUNT(*), COUNT(*) FILTER (WHERE profit_abs > 0), "
                    "COALESCE(SUM(profit_abs), 0) FROM bot_trades "
                    "WHERE bot=%s AND is_open=FALSE AND open_ts >= %s",
                    (bot, start))
                era[bot] = cur.fetchone()
            # closed-in-last-24h per bot (over-trading health check)
            cur.execute("SELECT bot, COUNT(*) FROM bot_trades WHERE is_open=FALSE "
                        "AND close_ts > now() - interval '24 hours' GROUP BY bot")
            n24 = dict(cur.fetchall())
            # per-mode (enter_tag) breakdown — era-scoped for reworked bots so
            # the dual-mode design is judged on current-code trades only
            tags = {}
            cur.execute("SELECT bot, COALESCE(enter_tag,'?') , COUNT(*), "
                        "COUNT(*) FILTER (WHERE profit_abs > 0), "
                        "COALESCE(SUM(profit_abs),0) FROM bot_trades "
                        "WHERE is_open=FALSE GROUP BY bot, enter_tag")
            for bot, tag, tn, tw, tpnl in cur.fetchall():
                if bot not in ERA_START:
                    tags.setdefault(bot, []).append(
                        {"tag": tag, "n": tn, "w": tw, "pnl": float(tpnl)})
            for bot, start in ERA_START.items():
                cur.execute("SELECT COALESCE(enter_tag,'?'), COUNT(*), "
                            "COUNT(*) FILTER (WHERE profit_abs > 0), "
                            "COALESCE(SUM(profit_abs),0) FROM bot_trades "
                            "WHERE bot=%s AND is_open=FALSE AND open_ts >= %s "
                            "GROUP BY enter_tag", (bot, start))
                for tag, tn, tw, tpnl in cur.fetchall():
                    tags.setdefault(bot, []).append(
                        {"tag": tag, "n": tn, "w": tw, "pnl": float(tpnl)})
        out = {}
        for bot, (n, w, gw, gl, pnl, last_close) in life.items():
            q = {"n": n, "w": w, "wr": (100.0 * w / n if n else None),
                 "pf": (float(gw) / abs(float(gl)) if float(gl) else None),
                 # [2026-07-07 RESET-PROOF] lifetime ledger P&L — the durable sum
                 # that survives any live-counter wipe (the July-6 reset made the
                 # dashboard show $1000/0 while the ledger held 8 real trades).
                 "pnl": float(pnl),
                 "exp": (float(pnl) / n if n else None), "last_close": last_close,
                 "n24": int(n24.get(bot) or 0),
                 "tags": sorted(tags.get(bot, []), key=lambda t: -t["n"])}
            if bot in era and era[bot]:
                en, ew, epnl = era[bot]
                q["era"] = {"n": en, "w": ew, "pnl": float(epnl)}
            out[bot] = q
        return out
    finally:
        conn.close()


def _sparkline(series):
    """Tiny inline SVG equity sparkline (green if up over the window)."""
    if len(series) < 2:
        return ""
    lo, hi = min(series), max(series)
    span = (hi - lo) or 1.0
    W, H = 130, 26
    pts = " ".join(f"{i * W / (len(series) - 1):.1f},{H - 2 - ((v - lo) / span) * (H - 4):.1f}"
                   for i, v in enumerate(series))
    color = "#3fb950" if series[-1] >= series[0] else "#f85149"
    return (f'<svg width="{W}" height="{H}" style="display:block">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>')


def build_sparks(hours=168):
    """{bot: (sparkline_svg, drawdown_pct_from_window_peak)} from equity history."""
    out = {}
    try:
        series = {}
        for ts_, bot, eq, _pnl in fetch_history(hours):
            if eq is not None:
                series.setdefault(bot, []).append(float(eq))
        for bot, vals in series.items():
            if len(vals) < 2:
                continue
            peak = max(vals)
            dd = (vals[-1] / peak - 1.0) * 100 if peak else 0.0
            out[bot] = (_sparkline(vals), dd)
    except Exception:
        pass
    return out


def _fetch_state(key):
    """One bot_state blob (market-pulse, learning-brain, ...) or None."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_state') AS t")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (key,))
            row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    finally:
        conn.close()


def fetch_pulse_strip():
    """(header_html, latest_dict) from the market_pulse collector."""
    try:
        st = _fetch_state("market-pulse")
        latest = (st or {}).get("latest") or {}
        mood = latest.get("mood")
        if mood is None:
            return "", {}
        col = "#3fb950" if mood > 0.1 else ("#f85149" if mood < -0.1 else "#d29922")
        ptxt = '<b style="color:#f85149">PANIC</b>' if latest.get("panic") else "calm"
        fund = latest.get("funding") or {}
        ftxt = " ".join(f"{k} {v['apr']:+.0f}%" for k, v in fund.items() if v)
        reg = latest.get("btc_regime") or {}
        rtxt = ""
        if reg:
            on = reg.get("risk_on")
            rc = "#3fb950" if on else "#f85149"
            rtxt = f' · BTC 4h <b style="color:{rc}">{"RISK-ON" if on else "RISK-OFF"}</b>'
        return (f'<span>Pulse <b style="color:{col}">{mood:+.2f}</b> · '
                f'F&amp;G <b>{latest.get("fear_greed")}</b> · {ptxt}{rtxt}'
                f'{" · funding " + html.escape(ftxt) if ftxt else ""}</span>', latest)
    except Exception:
        return "", {}


def brain_card_html():
    """Compact card for the learning loop's current state (bot_state 'learning-brain')."""
    try:
        st = _fetch_state("learning-brain")
        if not st:
            return ""
        runs = st.get("runs")
        hyp = st.get("hypotheses") or {}
        act = [e for e in hyp.values()
               if e.get("status") == "ACTIONABLE" and e.get("last_run") == runs]
        cand = [e for e in hyp.values()
                if e.get("status") == "candidate" and e.get("last_run") == runs]
        items = "".join(
            f'<div class="row"><span style="max-width:78%">'
            f'{html.escape((e.get("proposal") or "")[:95])}</span>'
            f'<b>{e.get("seen")}✓</b></div>' for e in (act + cand)[:4])
        if not items:
            items = ('<div class="muted">no current-era hypotheses yet — '
                     'evidence accumulating from the new code\'s trades</div>')
        return (f'<div class="card"><h2>🧠 Brain (bot_learn) <span class="dot on"></span></h2>'
                f'<div class="muted">run {runs} · {len(act)} actionable · '
                f'{len(cand)} candidates (proposals only — humans ship)</div>{items}</div>')
    except Exception:
        return ""


def money(x):
    try:
        return f"{float(x):+,.2f}"
    except (TypeError, ValueError):
        return "—"


def pct(x):
    try:
        return f"{float(x) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "—"


def cls(x):
    try:
        return "pos" if float(x) >= 0 else "neg"
    except (TypeError, ValueError):
        return ""


def _ensure_history_table(conn):
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS bot_equity_history (
            bot TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            equity DOUBLE PRECISION, pnl_abs DOUBLE PRECISION,
            PRIMARY KEY (bot, ts))""")


def snapshot_history_once():
    """Append the current bot_pnl equity/P&L for every bot into the history table.
    Run on a timer so EVERY bot gets an equity time-series with no bot changes."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    conn.autocommit = True
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO bot_equity_history (bot, ts, equity, pnl_abs) "
                        "SELECT bot, now(), equity, pnl_abs FROM bot_pnl "
                        "ON CONFLICT DO NOTHING")
    finally:
        conn.close()


def history_loop(interval=300):
    while True:
        try:
            snapshot_history_once()
        except Exception as e:  # noqa: BLE001
            print(f"[history] snapshot failed: {e}", flush=True)
        time.sleep(interval)


def fetch_history(hours=168):
    """(ts, bot, equity, pnl_abs) rows for the last N hours, oldest first."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_equity_history') AS t")
            if cur.fetchone()[0] is None:
                return []
            cur.execute("SELECT ts, bot, equity, pnl_abs FROM bot_equity_history "
                        f"WHERE ts > now() - interval '{int(hours)} hours' ORDER BY ts")
            return cur.fetchall()
    finally:
        conn.close()


def fetch_open_trades():
    """{bot: [trade dicts]} for currently-open trades (crypto holdings)."""
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()["t"] is None:
                return {}
            cur.execute("SELECT bot, pair, profit_abs, profit_ratio, open_rate "
                        "FROM bot_trades WHERE is_open = TRUE ORDER BY bot, pair")
            out = {}
            for r in cur.fetchall():
                out.setdefault(r["bot"], []).append(dict(r))
            return out
    finally:
        conn.close()


_ENRICH_CACHE = {"ts": 0.0, "data": {}}


def fetch_ledger_enrich():
    """[2026-07-07 UNIFORM CARDS] One cached ledger pass so EVERY bot's card
    carries the same fields regardless of what its publisher sends:
      * lifetime record + total P&L from the union ledger
        (bot_trades + paper_trades — the perps bots publish NULL wins/losses
        to bot_pnl even though the ledger knows their whole history),
      * TODAY's P&L: equity-curve delta since UTC midnight where the bot has
        an equity history (captures unrealized), else trades closed today,
      * last-close detail (pair, P&L, reason, when),
      * open positions for bots whose live book sits in bot_state (perps
        broker positions, funding carries) rather than bot_pnl.extra.
    Guarded: any failure degrades to {} and cards render as before."""
    import time as _time
    if _time.time() - _ENRICH_CACHE["ts"] < 20:
        return _ENRICH_CACHE["data"]
    import psycopg2
    import psycopg2.extras
    out = {}
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') t1, "
                        "to_regclass('public.paper_trades') t2, "
                        "to_regclass('public.bot_equity_history') t3, "
                        "to_regclass('public.bot_state') t4")
            g = cur.fetchone()
            parts = []
            if g["t1"]:
                parts.append("SELECT bot, pair, profit_abs AS pnl, "
                             "exit_reason AS reason, close_ts "
                             "FROM bot_trades WHERE close_ts IS NOT NULL")
            if g["t2"]:
                parts.append("SELECT bot, pair, pnl_abs, reason, "
                             "COALESCE(NULLIF(closed_at,'')::timestamptz, seen_at) "
                             "FROM paper_trades")
            if parts:
                union = " UNION ALL ".join(parts)
                cur.execute(
                    f"WITH t AS ({union}) "
                    "SELECT bot, COUNT(*) n, SUM((pnl>0)::int) w, SUM(pnl) total, "
                    "COALESCE(SUM(pnl) FILTER (WHERE close_ts >= date_trunc('day', now())),0) today_closed, "
                    "COUNT(*) FILTER (WHERE close_ts >= date_trunc('day', now())) today_n "
                    "FROM t GROUP BY bot")
                for r in cur.fetchall():
                    b = out.setdefault(r["bot"], {})
                    n, w = int(r["n"]), int(r["w"] or 0)
                    b["record"] = {"n": n, "w": w, "l": n - w,
                                   "total": round(float(r["total"] or 0), 2)}
                    b["today_closed"] = round(float(r["today_closed"] or 0), 2)
                    b["today_n"] = int(r["today_n"] or 0)
                cur.execute(
                    f"WITH t AS ({union}) "
                    "SELECT DISTINCT ON (bot) bot, pair, pnl, reason, close_ts "
                    "FROM t ORDER BY bot, close_ts DESC")
                for r in cur.fetchall():
                    out.setdefault(r["bot"], {})["last_close"] = {
                        "pair": r["pair"],
                        "pnl": (round(float(r["pnl"]), 2) if r["pnl"] is not None else None),
                        "reason": r["reason"],
                        "ts": r["close_ts"].isoformat() if r["close_ts"] else None}
            if g["t3"]:
                cur.execute(
                    "SELECT bot, (array_agg(equity ORDER BY ts DESC))[1] "
                    "- (array_agg(equity ORDER BY ts))[1] AS delta "
                    "FROM bot_equity_history "
                    "WHERE ts >= date_trunc('day', now()) GROUP BY bot")
                for r in cur.fetchall():
                    if r["delta"] is not None:
                        out.setdefault(r["bot"], {})["today_equity_delta"] = \
                            round(float(r["delta"]), 2)
            if g["t4"]:
                cur.execute("SELECT bot, state FROM bot_state WHERE bot IN "
                            "('perps-rsi-meanrev','perps-donchian-breakout',"
                            "'perps-funding-carry')")
                for r in cur.fetchall():
                    st = r["state"] if isinstance(r["state"], dict) else \
                        json.loads(r["state"] or "{}")
                    poss = []
                    br = st.get("broker") or {}
                    marks = br.get("marks") or {}
                    for coin, v in (br.get("pos") or {}).items():
                        try:
                            qty, entry = float(v[0]), float(v[1])
                            mark = marks.get(coin)
                            upnl = (round((float(mark) - entry) * qty, 2)
                                    if mark is not None else None)
                            poss.append({"pair": str(coin),
                                         "side": "long" if qty > 0 else "short",
                                         "qty": qty, "entry": entry, "upnl": upnl})
                        except Exception:
                            poss.append({"pair": str(coin), "side": "?",
                                         "qty": None, "entry": None, "upnl": None})
                    for coin, p in (st.get("positions") or {}).items():
                        if isinstance(p, dict) and "side" in p:
                            try:
                                net = round(float(p.get("accrued", 0))
                                            - float(p.get("fees", 0)), 2)
                            except Exception:
                                net = None
                            poss.append({"pair": str(coin),
                                         "side": ("short" if "short" in str(p.get("side"))
                                                  else "long"),
                                         "qty": p.get("notional"), "entry": None,
                                         "upnl": net})
                    if poss:
                        out.setdefault(r["bot"], {})["positions"] = poss
    finally:
        conn.close()
    _ENRICH_CACHE["ts"] = _time.time()
    _ENRICH_CACHE["data"] = out
    return out


def age_str(updated_at, threshold=STALE_SECONDS):
    if updated_at is None:
        return "never", True
    now = dt.datetime.now(dt.timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=dt.timezone.utc)
    secs = (now - updated_at).total_seconds()
    stale = secs > threshold
    if secs < 90:
        return f"{int(secs)}s ago", stale
    if secs < 5400:
        return f"{int(secs // 60)}m ago", stale
    return f"{int(secs // 3600)}h ago", stale


def _holdings_html(bot, extra, open_trades):
    """Current holdings: stock bots from extra['positions']; crypto from open bot_trades."""
    items = []
    if isinstance(extra, dict):
        for p in (extra.get("positions") or []):
            # Stock bots publish a LIST of dicts here. Guard against any other
            # shape (a bot publishing {coin: "desc"} took the whole page down on
            # 2026-07-03 — a str has no .get). Non-dict entries render as text.
            if not isinstance(p, dict):
                items.append(f'<div class="row"><span>{html.escape(str(p))}</span></div>')
                continue
            up = p.get("upnl")
            up_html = f' <span class="{cls(up)}">{money(up)}</span>' if up is not None else ""
            items.append(f'<div class="row"><span>{html.escape(str(p.get("symbol")))} ×{p.get("qty")}</span>'
                         f'<b>{money(p.get("value"))}{up_html}</b></div>')
    for t in (open_trades.get(bot) or []):
        pr = t.get("profit_ratio")
        pr_html = f' <span class="{cls(pr)}">{pct(pr)}</span>' if pr is not None else ""
        items.append(f'<div class="row"><span>{html.escape(str(t.get("pair")))}</span>'
                     f'<b>{money(t.get("profit_abs"))}{pr_html}</b></div>')
    return f'<div class="sub">Holdings ({len(items)})</div>{"".join(items)}' if items else ""


def _orders_html(extra):
    if not (isinstance(extra, dict) and extra.get("open_orders")):
        return ""
    items = [f'<div class="row"><span>{html.escape(str(o.get("action")))} '
             f'{html.escape(str(o.get("symbol")))} ×{o.get("qty")}</span>'
             f'<b class="muted">{html.escape(str(o.get("status")))}</b></div>'
             for o in extra["open_orders"]]
    return f'<div class="sub">Open orders ({len(items)})</div>{"".join(items)}'


def card(bot, row, open_trades=None, quality=None, spark=None, mode_note=None,
         enrich=None):
    open_trades = open_trades or {}
    en = enrich or {}
    badge = ""
    _base_bot, _suf = venue_variant(bot)
    if _base_bot in BADGES:
        _t, _c = BADGES[_base_bot]
        badge = (f' <span style="font-size:10px;border:1px solid {_c};color:{_c};'
                 f'border-radius:6px;padding:1px 5px;vertical-align:middle">{_t}</span>')
    # [2026-07-09 LIGHTER GO-LIVE] mode badge — LIVE (real money) stands out in
    # red-filled, TESTNET amber, SHADOW blue, so a live bot is unmistakable.
    if _suf:
        _vt, _vc, _ = VENUE_SUFFIXES[_suf]
        badge += (f' <span style="font-size:10px;border:1px solid {_vc};color:#fff;'
                  f'background:{_vc};border-radius:6px;padding:1px 6px;'
                  f'vertical-align:middle;font-weight:700;letter-spacing:.3px">{_vt}</span>')
    if row is None:
        return (f'<div class="card"><h2>{html.escape(label_for(bot))}{badge} '
                f'<span class="dot off"></span></h2>'
                f'<div class="muted">no data yet — bot has not published</div></div>')
    thr = stale_secs_for(bot)
    age, stale = age_str(row.get("updated_at"), thr)
    status = (row.get("status") or "?")
    dot = "warn" if stale else ("off" if status in ("halted", "error") else "on")
    extra = row.get("extra") or {}
    if isinstance(extra, dict):
        _HIDE = {"positions", "open_orders", "open_pos", "err", "src", "port"}
        _bits = {k: v for k, v in extra.items() if k not in _HIDE}
        extra_bits = " · ".join(f"{k}: {html.escape(str(v))}" for k, v in _bits.items())
    else:
        extra_bits = html.escape(str(extra))
    holdings_html = _holdings_html(bot, extra, open_trades)
    orders_html = _orders_html(extra)
    rows = []
    if row.get("equity") is not None:
        rows.append(f'<div class="row"><span>Equity</span><b>{money(row.get("equity"))}</b></div>')
    # [2026-07-05] Total P&L on EVERY bot card. The freqtrade bots publish
    # pnl_abs=None (their gain is equity - $1000 paper start), so they used to
    # show no P&L line at all — only Equity. Compute a total from whichever
    # source the bot exposes so every card states its number explicitly.
    _pnl_abs = row.get("pnl_abs")
    _eq = row.get("equity")
    # [2026-07-10] Live Lighter bots fund from real collateral (e.g. $65), NOT
    # the $1000 paper start — so NEVER apply the paper baseline to them, or an
    # untraded live account reads a phantom -$935. Their publisher sends real
    # pnl_abs (equity - starting collateral); if it's ever None, show nothing.
    _is_live = is_live_bot(bot)
    if (_pnl_abs is None and _eq is not None and bot not in STOCKS
            and bot not in SCANNERS and not _is_live):
        _pnl_abs = _eq - PAPER_START_EQUITY          # paper bots start at $1,000
    if _pnl_abs is not None:
        pnl_label = "Paper (arb)" if bot in SCANNERS else "Total P&amp;L"
        _pct = row.get("pnl_pct")
        if (_pct is None and _eq not in (None, 0) and bot not in STOCKS
                and bot not in SCANNERS and not _is_live):
            _pct = _pnl_abs / PAPER_START_EQUITY
        rows.append(f'<div class="row"><span>{pnl_label}</span>'
                    f'<b class="{cls(_pnl_abs)}">{money(_pnl_abs)}'
                    f'{" (" + pct(_pct) + ")" if _pct is not None else ""}</b></div>')
    # [2026-07-07 UNIFORM CARDS] Perps bots publish NULL closed/wins/losses to
    # bot_pnl even though the paper ledger has every close — fall back to the
    # ledger so every card shows a real record.
    _closed = row.get("closed_trades")
    if _closed is None and (en.get("record") or {}).get("n"):
        _closed = en["record"]["n"]
    if _closed is not None or row.get("open_trades") is not None:
        rows.append(f'<div class="row"><span>Trades</span>'
                    f'<b>{_closed or 0} closed · {row.get("open_trades") or 0} open</b></div>')
    if row.get("wins") is not None:
        rows.append(f'<div class="row"><span>Win / Loss</span>'
                    f'<b>{row.get("wins") or 0} / {row.get("losses") or 0}</b></div>')
    elif (en.get("record") or {}).get("n"):
        _r = en["record"]
        rows.append(f'<div class="row"><span>Win / Loss (ledger)</span>'
                    f'<b>{_r["w"]} / {_r["l"]} · {money(_r["total"])} lifetime</b></div>')
    # Daily / Weekly / Monthly P&L. [2026-07-07 UNIFORM CARDS] Today's figure
    # is computed server-side for EVERY bot: equity-curve delta since UTC
    # midnight where an equity history exists (captures unrealized moves),
    # else the sum of trades closed today from the ledger. A publisher-sent
    # pnl_daily still wins if a bot ever supplies one.
    pnl_daily   = row.get("pnl_daily")
    # [2026-07-08] a publisher-sent daily figure only counts as "today" while
    # its row was written today (UTC) — a once-a-day publisher (alpaca 22:00
    # cron) must not show yesterday's number all through the next day.
    _upd = row.get("updated_at")
    if pnl_daily is not None and _upd is not None:
        try:
            if _upd.astimezone(dt.timezone.utc).date() != dt.datetime.now(dt.timezone.utc).date():
                pnl_daily = None
        except Exception:
            pass
    if pnl_daily is None:
        pnl_daily = en.get("today_equity_delta")
        if pnl_daily is None and en.get("today_n"):
            pnl_daily = en.get("today_closed")
    pnl_weekly  = row.get("pnl_weekly")
    pnl_monthly = row.get("pnl_monthly")
    if pnl_daily is not None:
        rows.append(f'<div class="row"><span>Today P&amp;L (UTC)</span>'
                    f'<b class="{cls(pnl_daily)}">{money(pnl_daily)}</b></div>')
    if pnl_weekly is not None:
        rows.append(f'<div class="row"><span>7d P&L</span>'
                    f'<b class="{cls(pnl_weekly)}">{money(pnl_weekly)}</b></div>')
    if pnl_monthly is not None:
        rows.append(f'<div class="row"><span>30d P&L</span>'
                    f'<b class="{cls(pnl_monthly)}">{money(pnl_monthly)}</b></div>')
    max_dd = row.get("max_drawdown")
    if max_dd is not None:
        rows.append(f'<div class="row"><span>Max Drawdown</span>'
                    f'<b style="color:#f85149">{pct(max_dd)}</b></div>')
    best_trade  = row.get("best_trade")
    worst_trade = row.get("worst_trade")
    if best_trade is not None or worst_trade is not None:
        rows.append(f'<div class="row"><span>Best / Worst trade</span>'
                    f'<b>{money(best_trade)} / {money(worst_trade)}</b></div>')
    # [2026-07-05 INSIGHT] quality metrics from the durable trade ledger
    q = quality or {}
    if q.get("n"):
        pf = q.get("pf")
        pf_txt = f"{pf:.2f}" if pf is not None else ("∞" if q.get("w") else "—")
        rows.append(f'<div class="row"><span>Quality (ledger)</span>'
                    f'<b>{q["wr"]:.0f}% win · PF {pf_txt} · {money(q["exp"])}/trade</b></div>')
        pass  # last-close now rendered for EVERY bot below (2026-07-07)
        # [2026-07-07 RESET-PROOF] All-time P&L from the durable trade ledger —
        # cannot be zeroed by a live-DB wipe, so a reset can never again hide a
        # bot's true history (July-6: card showed $1000/0 while the ledger held
        # 8 real trades). If this row and 'Total P&L' disagree, a reset happened.
        if q.get("pnl") is not None:
            rows.append(f'<div class="row"><span>All-time Σ (ledger, {q["n"]} closed)</span>'
                        f'<b class="{cls(q["pnl"])}">{money(q["pnl"])}</b></div>')
    e = q.get("era") if q else None
    if e is not None:
        _en, _ew = e.get("n") or 0, e.get("w") or 0
        rows.append(f'<div class="row"><span>Since 3 Jul rework</span>'
                    f'<b class="{cls(e.get("pnl"))}">{_en} trades · {_ew}W/{_en - _ew}L · '
                    f'{money(e.get("pnl"))}</b></div>')
    for _t in (q.get("tags") or [])[:3]:
        rows.append(f'<div class="row"><span>&nbsp;&nbsp;↳ {html.escape(str(_t["tag"]))}</span>'
                    f'<b class="{cls(_t["pnl"])}">{_t["n"]} · {_t["w"]}W/{_t["n"] - _t["w"]}L · '
                    f'{money(_t["pnl"])}</b></div>')
    # [2026-07-07 UNIFORM CARDS] Last close with detail for EVERY bot, from
    # the union ledger (bot_trades + paper_trades).
    _lc = en.get("last_close")
    if _lc and _lc.get("ts"):
        try:
            _la, _ = age_str(dt.datetime.fromisoformat(_lc["ts"]), 10 ** 12)
        except Exception:
            _la = ""
        _lp = _lc.get("pnl")
        rows.append(f'<div class="row"><span>Last close</span>'
                    f'<b>{html.escape(str(_lc.get("pair")))} '
                    f'<span class="{cls(_lp)}">{money(_lp)}</span>'
                    f'{" · " + html.escape(str(_lc.get("reason"))) if _lc.get("reason") else ""}'
                    f'{" · " + html.escape(_la) if _la else ""}</b></div>')
    if spark:
        _svg, _dd = spark
        rows.append(f'<div class="row"><span>7d equity · DD {_dd:+.1f}%</span><b>{_svg}</b></div>')
    # live open positions passed through by the freqtrade poller
    open_pos_html = ""
    _op = extra.get("open_pos") if isinstance(extra, dict) else None
    if _op:
        _lines = "".join(
            f'<div class="row"><span>{html.escape(str(p.get("pair")))}'
            f'{" · " + html.escape(str(p.get("tag"))) if p.get("tag") else ""}'
            f'{" · " + str(p.get("h")) + "h" if p.get("h") is not None else ""}</span>'
            f'<b class="{cls(p.get("pnl"))}">'
            f'{p.get("pnl"):+.2f}%</b></div>'
            for p in _op[:6] if isinstance(p, dict) and p.get("pnl") is not None)
        if _lines:
            open_pos_html = f'<div class="sub">open positions</div>{_lines}'
    # [2026-07-07 UNIFORM CARDS] Perps + funding books live in bot_state, not
    # in bot_pnl.extra — render them the same way the freqtrade bots render.
    if not open_pos_html and en.get("positions"):
        _lines = "".join(
            f'<div class="row"><span>{html.escape(str(p.get("pair")))}'
            f' · {html.escape(str(p.get("side")))}'
            f'{" · $" + format(p["qty"], ".0f") if p.get("side") and isinstance(p.get("qty"), (int, float)) and p.get("entry") is None else ""}'
            f'{" @ " + format(p["entry"], ".4g") if isinstance(p.get("entry"), (int, float)) else ""}</span>'
            f'<b class="{cls(p.get("upnl"))}">'
            f'{money(p.get("upnl")) if p.get("upnl") is not None else "—"}</b></div>'
            for p in en["positions"][:8])
        open_pos_html = (f'<div class="sub">open positions '
                         f'({len(en["positions"])})</div>{_lines}')
    return f'''<div class="card">
      <h2>{html.escape(label_for(bot))}{badge} <span class="dot {dot}"></span></h2>
      <div class="muted">{html.escape(str(status))} · updated {html.escape(age)}{" · STALE" if stale else ""}</div>
      {f'<div class="muted" style="color:#d29922">{html.escape(mode_note)}</div>' if mode_note else ''}
      {"".join(rows)}
      {open_pos_html}
      {holdings_html}
      {orders_html}
      {f'<div class="sub">{extra_bits}</div>' if extra_bits else ''}
    </div>'''


def render():
    try:
        rows = fetch_rows()
        db_err = None
    except Exception as e:
        rows, db_err = {}, f"{type(e).__name__}: {e}"

    try:
        open_trades = fetch_open_trades()
    except Exception:  # noqa: BLE001
        open_trades = {}
    try:
        quality = fetch_bot_quality()
    except Exception:  # noqa: BLE001
        quality = {}
    try:
        enrich = fetch_ledger_enrich()
    except Exception:  # noqa: BLE001
        enrich = {}
    sparks = build_sparks()
    pulse_strip, pulse_latest = fetch_pulse_strip()
    brain_html = brain_card_html()

    # V5's regime-driven mode, so its card explains its own quietness/activity
    mode_notes = {}
    _reg = (pulse_latest or {}).get("btc_regime") or {}
    if _reg:
        mode_notes["crypto-intraday-15m"] = (
            "mode: range_on pullback buys (BTC 4h RISK-ON)" if _reg.get("risk_on")
            else "mode: bear_bounce only — sweep-reclaim setups (BTC 4h RISK-OFF)")

    # union of expected + whatever actually published
    names = list(EXPECTED) + [b for b in rows if b not in EXPECTED]
    # [2026-07-10] Real-money Lighter bots get their OWN section at the top of the
    # page, not interspersed with the paper fleet. is_live_bot = <bot>-lighter rows.
    _mk = lambda b: card(b, rows.get(b), open_trades, quality.get(b), sparks.get(b),
                         mode_notes.get(b), enrich.get(b))
    live_cards = [_mk(b) for b in names if is_live_bot(b)]
    cards = [_mk(b) for b in names if not is_live_bot(b)]
    if brain_html:
        cards.append(brain_html)

    # [2026-07-05] Ambient health checks — the silent-failure classes we have
    # actually hit (persistence resets, over-trading) surfaced on every load.
    checks = []
    for b, r in rows.items():
        if b in SCANNERS or b in STOCKS:
            continue
        q = quality.get(b) or {}
        eq = r.get("equity")
        if (isinstance(eq, (int, float)) and abs(eq - 1000.0) < 1e-9
                and (q.get("n") or 0) > 0 and (r.get("closed_trades") or 0) == 0):
            checks.append(f"{label_for(b)}: equity exactly $1000 with ledger history — possible persistence reset")
        if (q.get("n24") or 0) > 15:
            checks.append(f"{label_for(b)}: {q['n24']} closed trades in 24h — over-trading vs design")
    _era5 = (quality.get("crypto-intraday-15m") or {}).get("era") or {}
    if (_era5.get("pnl") or 0) < -5:
        checks.append(f"V5 probation breach: since-rework P&L {money(_era5.get('pnl'))}")
    health_html = ('<div class="banner">HEALTH: ' + " · ".join(html.escape(c) for c in checks) + "</div>"
                   if checks else
                   '<div class="okline">Health ✓ persistence intact · no over-trading · probation within bounds</div>')

    # [2026-07-11 EVIDENCE ALERTS] recent alerts from market_context's evidence
    # evaluator (dislocation census hits, factor-sample milestones, coin-veto
    # changes, live-vs-shadow divergence). Signal layer only — the sole
    # automated ACTION in the fleet is the restrict-only coin-veto list.
    _fa = fetch_fleet_alerts()
    if _fa:
        health_html += ('<div class="banner">🔔 EVIDENCE: '
                        + " · ".join(html.escape(a.get("msg") or "")
                                     for a in _fa[-6:]) + "</div>")

    live = [r for r in rows.values() if r]
    # [2026-07-09 LIGHTER GO-LIVE] Venue-variant rows (live/testnet/shadow on
    # Lighter) are their OWN groups — never folded into the paper headline, so
    # the paper curve stays clean and the LIVE fleet gets its own P&L line.
    def _variant_kind(r):
        return venue_variant(r.get("bot") or "")[1]
    live_rows = [r for r in live if is_live_bot(r.get("bot") or "")]
    shadow_rows = [r for r in live if _variant_kind(r) in ("-lshadow", "-ltest")]
    _crypto = [r for r in live if r.get("bot") not in STOCKS and not _variant_kind(r)]
    # Crypto trading-bot P&L (the real headline) excludes scanners AND stocks AND
    # venue variants; each of those is shown as its own subtotal so it can't
    # distort the paper total.
    tot_pnl = sum((r.get("pnl_abs") or 0) for r in _crypto
                  if r.get("bot") not in SCANNERS)
    scan_pnl = sum((r.get("pnl_abs") or 0) for r in live
                   if r.get("bot") in SCANNERS)
    stock_pnl = sum((r.get("pnl_abs") or 0) for r in live if r.get("bot") in STOCKS)
    # LIVE (real money on Lighter) — the number that actually matters once funded.
    live_pnl = sum((r.get("pnl_abs") or 0) for r in live_rows)
    live_equity = sum((r.get("equity") or 0) for r in live_rows if r.get("equity") is not None)
    n_live_bots = len(live_rows)
    shadow_pnl = sum((r.get("pnl_abs") or 0) for r in shadow_rows)
    n_shadow_bots = len(shadow_rows)
    tot_equity = sum((r.get("equity") or 0) for r in _crypto if r.get("equity") is not None)
    stock_equity = sum((r.get("equity") or 0) for r in live
                       if r.get("bot") in STOCKS and r.get("equity") is not None)
    n_open = sum((r.get("open_trades") or 0) for r in _crypto)
    n_closed = sum((r.get("closed_trades") or 0) for r in _crypto)
    online = sum(1 for r in live
                 if not age_str(r.get("updated_at"), stale_secs_for(r.get("bot")))[1]
                 and r.get("status") not in ("halted", "error"))

    # Grand total across EVERYTHING (the full picture). Equity is a clean sum of
    # all account balances; P&L sums all bots' pnl_abs (mixed bases — see subtotals).
    grand_equity = sum((r.get("equity") or 0) for r in live if r.get("equity") is not None)
    # Real-money live P&L IS part of the grand total; shadow is modelled (not real)
    # so it stays out of the headline and only shows on its own muted line.
    grand_pnl = tot_pnl + scan_pnl + stock_pnl + live_pnl

    # Whole-feed staleness. The DB can be reachable and rows can exist, yet every
    # row is old because the bots lost their write path (the exact failure mode on
    # 2026-06-22: bots alive, hardcoded DATABASE_URL went stale, no fresh writes).
    # A frozen feed must NOT look like "all bots flat", so flag it loudly here and
    # in /pnl.json.
    def _age_secs(r):
        ua = r.get("updated_at")
        if ua is None:
            return None
        if ua.tzinfo is None:
            ua = ua.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - ua).total_seconds()

    _ages = [s for s in (_age_secs(r) for r in live) if s is not None]
    freshest = min(_ages) if _ages else None
    n_stale_live = sum(1 for r in live
                       if age_str(r.get("updated_at"), stale_secs_for(r.get("bot")))[1])
    feed_stale = bool(live) and freshest is not None and n_stale_live == len(live)

    banner = ""
    if db_err:
        banner = (f'<div class="banner">Database unreachable: {html.escape(db_err)}. '
                  f'Check DATABASE_URL on this service.</div>')
    elif not live:
        banner = ('<div class="banner">Connected to Postgres, but no bot has published yet. '
                  'Make sure each bot has DATABASE_URL set and has run at least one loop.</div>')
    elif feed_stale:
        _m = int(freshest // 60)
        _age = f"{_m} min" if _m < 120 else f"{_m // 60}h {_m % 60}m"
        banner = (f'<div class="banner crit">FEED STALE — no bot has published in {_age}. '
                  f'Showing last-known values, not live P&amp;L. The bots may be running '
                  f'but unable to write to Postgres — check the DATABASE_URL reference on '
                  f'each bot service and redeploy.</div>')

    # [2026-07-09 LIGHTER GO-LIVE] The LIVE fleet gets its own prominent P&L line
    # (real money on Lighter, separate from every paper number). Shadow/testnet
    # get a muted line so the compressed gate ladder is visible at a glance.
    live_total_line = ""
    if n_live_bots:
        live_total_line += (
            f'<span style="border:1px solid #f85149;border-radius:6px;padding:2px 9px;'
            f'background:#f8514918;font-weight:600">🔴 LIVE · Lighter '
            f'<b>{money(live_equity)}</b> eq · '
            f'<b class="{cls(live_pnl)}">{money(live_pnl)}</b> P&amp;L · '
            f'{n_live_bots} bot{"s" if n_live_bots != 1 else ""}</span>')
    if n_shadow_bots:
        live_total_line += (
            f'<span class="muted" style="border:1px solid #30363d;border-radius:6px;'
            f'padding:2px 9px">shadow/testnet <b class="{cls(shadow_pnl)}">'
            f'{money(shadow_pnl)}</b> · {n_shadow_bots} bot'
            f'{"s" if n_shadow_bots != 1 else ""} (modelled)</span>')

    # [2026-07-10] Dedicated "Lighter Live" section — real-money bots grouped at
    # the top in their own bordered block so live money is never lost in the grid.
    live_section = ""
    if live_cards:
        live_section = (
            f'<section class="livewrap">'
            f'<div class="livehdr">⚡ Lighter Live <span class="livetag">REAL MONEY</span>'
            f'<span class="livesum">{money(live_equity)} eq · '
            f'<b class="{cls(live_pnl)}">{money(live_pnl)}</b> P&amp;L · '
            f'{n_live_bots} bot{"s" if n_live_bots != 1 else ""}</span></div>'
            f'<div class="grid">{"".join(live_cards)}</div></section>')

    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>All Bots — Live P&amp;L</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Permanent+Marker&amp;display=swap" rel="stylesheet">
<style>
 @keyframes gradientshift{{0%{{background-position:0% 50%}}50%{{background-position:100% 50%}}100%{{background-position:0% 50%}}}}
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;color:#16232c;
   background-color:#eef7fd;
   background-image:repeating-linear-gradient(180deg,#ffffff 0 70px,#aed8f6 70px 140px);
   background-attachment:fixed}}
 /* the "$ EJMC $" graffiti piece — fixed behind the cards (z-index:-1 so the
    striped body shows behind it and the cards sit on top). */
 .wm{{position:fixed;inset:0;z-index:-1;display:flex;align-items:center;
   justify-content:center;pointer-events:none;overflow:hidden}}
 .wm svg{{width:min(97vw,2000px);height:auto}}
 header{{padding:16px 18px;background:#ffffffd9;backdrop-filter:blur(2px);
   border-bottom:3px solid #caa227;position:relative}}
 header::after{{content:"";position:absolute;left:0;right:0;bottom:-6px;height:2px;
   background:linear-gradient(90deg,#f4d879,#caa227,#8a6d1a,#caa227,#f4d879);
   background-size:300% 100%;animation:gradientshift 6s ease infinite}}
 h1{{margin:0 0 6px;font-size:19px;font-weight:800;letter-spacing:.2px;
   background:linear-gradient(90deg,#8a6d1a,#caa227 35%,#2f7fd6 65%,#8a6d1a);
   background-size:300% 100%;-webkit-background-clip:text;background-clip:text;
   color:transparent;animation:gradientshift 8s ease infinite;display:inline-block}}
 h1 a{{-webkit-text-fill-color:#1462c9;color:#1462c9}}
 .totals{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;color:#16232c}}
 .totals b{{font-size:16px}}
 .banner{{margin:12px 14px 0;padding:10px 12px;background:#fff6dd;border:1px solid #caa227;border-radius:8px;color:#7a5b12;font-size:13px}}
 .banner.crit{{background:#ffe3e3;border-color:#d1242f;color:#a3121b;font-weight:600}}
 .okline{{margin:12px 14px 0;padding:8px 12px;background:#e6f7ec;border:1px solid #caa227;border-radius:8px;color:#1a7f37;font-size:12px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;padding:14px}}
 /* [2026-07-10] Lighter Live section — real money, visually set apart */
 .livewrap{{margin:14px 14px 4px;border:2px solid #d1242f;border-radius:12px;
   box-shadow:0 0 0 1px #caa227 inset,0 0 22px -6px #d1242f66;
   background:linear-gradient(180deg,#ffececcc,#fff6f6cc);overflow:hidden}}
 .livewrap .grid{{padding:12px}}
 .livehdr{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
   padding:11px 14px;background:#d1242f14;border-bottom:1px solid #d1242f33;
   font-size:15px;font-weight:700;color:#a3121b}}
 .livetag{{font-size:10px;font-weight:800;letter-spacing:.5px;color:#fff;
   background:#d1242f;border-radius:6px;padding:2px 7px;box-shadow:0 0 10px #d1242f66}}
 .livesum{{margin-left:auto;font-size:13px;font-weight:500;color:#16232c}}
 .card{{background:#ffffffcc;border:2.5px solid #d4af37;border-radius:10px;padding:14px;
   box-shadow:0 0 0 1px #b8860b55,0 1px 0 #ffffffaa inset;
   transition:border-color .2s,box-shadow .2s}}
 .card:hover{{border-color:#b8860b;box-shadow:0 0 0 1px #b8860b,0 0 16px -6px #d4af37cc}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:10px 0 4px;font-size:12px;color:#5b7184}}
 .muted{{color:#5b7184;font-size:12px}}
 .pos{{color:#1a7f37}} .neg{{color:#d1242f}}
 .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:4px}}
 .dot.on{{background:#1a7f37;box-shadow:0 0 6px #1a7f37}} .dot.off{{background:#d1242f;box-shadow:0 0 6px #d1242f}} .dot.warn{{background:#b8860b;box-shadow:0 0 6px #b8860b}}
 footer{{padding:10px 18px;color:#5b7184;font-size:11px}}
</style></head><body>
{WATERMARK_HTML}
<header>
 <h1>All Bots — live P&amp;L &nbsp;·&nbsp; <a href="/history" style="color:#58a6ff;font-size:14px">history →</a> &nbsp;·&nbsp; <a href="/periods" style="color:#58a6ff;font-size:14px">P&amp;L by day/week/month →</a> &nbsp;·&nbsp; <a href="/market" style="color:#58a6ff;font-size:14px">market regime →</a> &nbsp;·&nbsp; <a href="/learning" style="color:#58a6ff;font-size:14px">learning →</a></h1>
 <div class="totals">
   <span>Bots live <b>{online}</b></span>
   <span style="border-right:1px solid #30363d;padding-right:18px">GRAND TOTAL <b>{money(grand_equity)}</b> eq · <b class="{cls(grand_pnl)}">{money(grand_pnl)}</b> P&amp;L</span>
   {live_total_line}
   <span>Crypto (paper) <b class="{cls(tot_pnl)}">{money(tot_pnl)}</b> · eq {money(tot_equity)}</span>
   <span>Scanner paper <b class="{cls(scan_pnl)}">{money(scan_pnl)}</b></span>
   <span>Stocks (paper) <b class="{cls(stock_pnl)}">{money(stock_pnl)}</b> · eq {money(stock_equity)}</span>
   <span>Trades <b>{n_closed} closed · {n_open} open</b></span>
   {pulse_strip}
 </div>
</header>
{banner}
{health_html}
{live_section}
<div class="grid">{"".join(cards)}</div>
<footer>Reads the shared bot_pnl Postgres table. Auto-refreshes every 30s. Times UTC.
Snapshots older than {STALE_SECONDS}s are flagged stale.</footer>
</body></html>'''


def _svg_chart(series, color, label, height=170, width=760):
    """series: list of (datetime, value) oldest-first. Returns an SVG line chart."""
    series = [(t, v) for t, v in series if v is not None]
    if len(series) < 2:
        return (f'<div class="sub">{label}</div>'
                '<div class="muted">Not enough history yet — the chart fills in as '
                'snapshots accrue (one every 5 min).</div>')
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    n = len(series)
    pts = " ".join(
        f"{(i/(n-1))*width:.1f},{height - (v-lo)/(hi-lo)*height:.1f}"
        for i, (_, v) in enumerate(series))
    last = vals[-1]
    return (f'<div class="sub">{label} · now <b>{money(last)}</b> '
            f'<span class="muted">(min {money(lo)} / max {money(hi)})</span></div>'
            f'<svg viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'preserveAspectRatio="none" style="background:#0d1117;border:1px solid #222;'
            f'border-radius:8px;margin-bottom:8px">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>')


def render_history():
    try:
        rows = fetch_history(hours=168)  # last 7 days
        db_err = None
    except Exception as e:  # noqa: BLE001
        rows, db_err = [], f"{type(e).__name__}: {e}"

    # Each snapshot batch shares one ts (INSERT ... SELECT now()). Aggregate per
    # group (Total / Crypto / Stocks / Scanner) at each point in time. Each chart
    # is auto-scaled so small crypto balances aren't flattened by big stock ones.
    ts_axis = sorted({ts for ts, _, _, _ in rows})
    GROUPS = ["Total", "Crypto", "Stocks", "Scanner"]
    agg = {g: {ts: {"eq": 0.0, "pnl": 0.0} for ts in ts_axis} for g in GROUPS}
    for ts, bot, eq, pnl in rows:
        g = "Stocks" if bot in STOCKS else ("Scanner" if bot in SCANNERS else "Crypto")
        for gg in (g, "Total"):
            if eq is not None:
                agg[gg][ts]["eq"] += eq
            if pnl is not None:
                agg[gg][ts]["pnl"] += pnl

    def series(group, key):
        return [(ts, agg[group][ts][key]) for ts in ts_axis]

    banner = ""
    if db_err:
        banner = f'<div class="banner">Database unreachable: {html.escape(db_err)}.</div>'
    elif not ts_axis:
        banner = ('<div class="banner">No history captured yet. The dashboard snapshots '
                  'every bot\'s equity every 5 minutes — check back shortly.</div>')

    # Whole operation, then per group. Scanners book no equity, so equity charts
    # cover Total/Crypto/Stocks; P&L charts cover all four.
    charts = (
        '<h2 style="font-size:15px;margin:18px 4px 2px">Whole operation</h2>'
        + _svg_chart(series("Total", "eq"), "#e6e6e6", "Total equity")
        + _svg_chart(series("Total", "pnl"), "#3fb950", "Total P&amp;L")
        + '<h2 style="font-size:15px;margin:18px 4px 2px">Crypto bots</h2>'
        + _svg_chart(series("Crypto", "eq"), "#58a6ff", "Crypto equity")
        + _svg_chart(series("Crypto", "pnl"), "#58a6ff", "Crypto P&amp;L")
        + '<h2 style="font-size:15px;margin:18px 4px 2px">Stock bots (IKBR + Alpaca)</h2>'
        + _svg_chart(series("Stocks", "eq"), "#d29922", "Stocks equity")
        + _svg_chart(series("Stocks", "pnl"), "#d29922", "Stocks P&amp;L")
        + '<h2 style="font-size:15px;margin:18px 4px 2px">Scanners</h2>'
        + _svg_chart(series("Scanner", "pnl"), "#a371f7", "Scanner paper P&amp;L")
    )
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>All Bots — History</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}} a{{color:#58a6ff;text-decoration:none;font-size:14px}}
 .wrap{{padding:14px}}
 .sub{{margin:14px 4px 6px;font-size:14px;color:#c9d1d9;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px}}
 .banner{{margin:12px 4px;padding:10px 12px;background:#3d2b12;border:1px solid #6b4a16;border-radius:8px;color:#f0c674;font-size:13px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>All Bots — history &nbsp;·&nbsp; <a href="/">← live</a> &nbsp; <a href="/periods">P&amp;L by period →</a></h1></header>
<div class="wrap">{banner}{charts}</div>
<footer>Equity/P&amp;L sampled every 5 min from the shared bot_pnl table (last 7 days).
Auto-refreshes every 60s. Times UTC.</footer>
</body></html>'''


def _slice_table(title, sl):
    if not sl:
        return ""
    # show the few best and worst rows by total_ratio
    items = list(sl.items())
    rowshtml = []
    for k, v in items:
        rowshtml.append(
            f'<tr><td>{html.escape(str(k))}</td><td>{v.get("n")}</td>'
            f'<td>{float(v.get("win_rate",0))*100:.0f}%</td>'
            f'<td class="{cls(v.get("total_ratio"))}">{float(v.get("total_ratio",0))*100:+.2f}%</td></tr>')
    return (f'<div class="sub">{html.escape(title)}</div>'
            f'<table class="tbl"><tr><th>bucket</th><th>n</th><th>win</th><th>total</th></tr>'
            f'{"".join(rowshtml)}</table>')


def learning_card(strategy, rec):
    a = rec.get("analysis") or {}
    age, stale = age_str(rec.get("updated_at"))
    bots = ", ".join(a.get("bots", []))
    if not a or a.get("n", 0) == 0:
        return (f'<div class="card"><h2>{html.escape(strategy)}</h2>'
                f'<div class="muted">{html.escape(bots)} · updated {html.escape(age)}</div>'
                f'<div class="muted" style="margin-top:8px">No closed trades analysed yet — '
                f'history accrues as the bots trade (4h strategies are slow).</div></div>')
    pf = a.get("profit_factor")
    pf_s = "∞" if pf in (None, float("inf")) else f'{pf}'
    headline = (
        f'<div class="row"><span>Trades</span><b>{a.get("n")}</b></div>'
        f'<div class="row"><span>Win rate</span><b>{float(a.get("win_rate",0))*100:.0f}%</b></div>'
        f'<div class="row"><span>Expectancy / trade</span>'
        f'<b class="{cls(a.get("expectancy"))}">{float(a.get("expectancy",0))*100:+.2f}%</b></div>'
        f'<div class="row"><span>Profit factor</span><b>{pf_s}</b></div>'
        f'<div class="row"><span>Total return</span>'
        f'<b class="{cls(a.get("total_return_ratio"))}">{float(a.get("total_return_ratio",0))*100:+.2f}%</b></div>'
        f'<div class="row"><span>Best / worst</span>'
        f'<b>{float(a.get("best",0))*100:+.1f}% / {float(a.get("worst",0))*100:+.1f}%</b></div>'
    )
    recs = "".join(f'<li>{html.escape(r)}</li>' for r in a.get("recommendations", []))
    recs_html = f'<div class="sub">What it learned</div><ul class="recs">{recs}</ul>' if recs else ""
    return f'''<div class="card">
      <h2>{html.escape(strategy)}</h2>
      <div class="muted">{html.escape(bots)} · updated {html.escape(age)}{" · STALE" if stale else ""}</div>
      {headline}
      {recs_html}
      {_slice_table("By exit reason", a.get("by_exit_reason"))}
      {_slice_table("By pair", a.get("by_pair"))}
    </div>'''


def render_learning():
    try:
        data = fetch_analysis()
        db_err = None
    except Exception as e:
        data, db_err = {}, f"{type(e).__name__}: {e}"
    banner = ""
    if db_err:
        banner = f'<div class="banner">Database unreachable: {html.escape(db_err)}.</div>'
    elif not data:
        banner = ('<div class="banner">No analysis yet. The trainer writes this once a day '
                  'after the bots have closed some trades.</div>')
    cards = "".join(learning_card(s, r) for s, r in data.items())
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Crypto Bots — Learning</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0 0 6px;font-size:18px}}
 a{{color:#58a6ff;text-decoration:none;font-size:13px}}
 .banner{{margin:12px 14px 0;padding:10px 12px;background:#3d2b12;border:1px solid #6b4a16;border-radius:8px;color:#f0c674;font-size:13px}}
 .banner.crit{{background:#3d1218;border-color:#6b1620;color:#f85149;font-weight:600}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;padding:14px}}
 .card{{background:#161b22;border:1px solid #222;border-radius:10px;padding:14px}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:12px 0 4px;font-size:12px;color:#8b949e;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 ul.recs{{margin:4px 0 0;padding-left:18px}} ul.recs li{{font-size:12px;margin:4px 0;color:#cdd9e5}}
 table.tbl{{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 2px}}
 table.tbl th,table.tbl td{{text-align:left;padding:3px 6px;border-bottom:1px solid #21262d}}
 table.tbl th{{color:#8b949e;font-weight:600}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header>
 <h1>Crypto Bots — what they're learning</h1>
 <a href="/">← back to live P&amp;L</a>
</header>
{banner}
<div class="grid">{cards}</div>
<footer>Win/loss post-mortem written daily by the auto-retrainer. Returns are paper
(dry-run). Recommendations marked for review are NOT auto-applied; only out-of-sample-
validated parameter changes are. Auto-refreshes every 2 min. Times UTC.</footer>
</body></html>'''


TRADING_BOTS_ORDER = ["crypto-trend-daily", "crypto-intraday-15m",
                      "crypto-swing-daily", "crypto-breakout-4h", "crypto-trendmomo-4h"]


def fetch_period_pnl(period, limit_periods):
    """Realized P&L per calendar {period} from the durable bot_trades table
    (closed paper trades; survives redeploys). period is 'day'|'week'|'month'.
    Returns (periods_newest_first, ordered_bots, grid[(period,bot)] -> {pnl,n}).
    Scanners are excluded (they book no per-trade rows). Raises on DB error."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()[0] is None:
                return [], [], {}
            cur.execute(
                """
                SELECT date_trunc(%s, close_ts) AS p, bot,
                       COALESCE(SUM(profit_abs), 0), COUNT(*)
                FROM bot_trades
                WHERE is_open = FALSE AND close_ts IS NOT NULL
                GROUP BY 1, 2
                ORDER BY 1 DESC
                """,
                (period,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    grid, periods, bots = {}, [], set()
    for p, bot, pnl, n in rows:
        if bot not in CURRENT_BOTS or bot in SCANNERS:
            continue
        key = p.date().isoformat()
        if key not in periods:
            periods.append(key)
        grid[(key, bot)] = {"pnl": float(pnl), "n": int(n)}
        bots.add(bot)
    periods = periods[:limit_periods]
    ordered = ([b for b in TRADING_BOTS_ORDER if b in bots]
               + sorted(b for b in bots if b not in TRADING_BOTS_ORDER))
    return periods, ordered, grid


def periods_payload():
    """Structured daily/weekly/monthly realized P&L for /periods.json."""
    out = {}
    for label, period, n in (("daily", "day", 31), ("weekly", "week", 13),
                             ("monthly", "month", 13)):
        periods, bots, grid = fetch_period_pnl(period, n)
        out[label] = [
            {"period": key,
             "total": round(sum(grid[(key, b)]["pnl"] for b in bots
                                if (key, b) in grid), 2),
             "trades": sum(grid[(key, b)]["n"] for b in bots if (key, b) in grid),
             "by_bot": {b: round(grid[(key, b)]["pnl"], 2) for b in bots
                        if (key, b) in grid}}
            for key in periods]
    return out


def _period_table(title, period, n):
    try:
        periods, bots, grid = fetch_period_pnl(period, n)
    except Exception as e:
        return (f'<div class="sub">{html.escape(title)}</div>'
                f'<div class="muted">unavailable: {html.escape(str(e))}</div>')
    if not periods:
        return (f'<div class="sub">{html.escape(title)}</div>'
                f'<div class="muted">no closed paper trades yet — check back as the bots trade</div>')
    head = "".join(f"<th>{html.escape(b.replace('-', ' '))}</th>" for b in bots)
    body = []
    for key in periods:
        cells, row_total = [], 0.0
        for b in bots:
            c = grid.get((key, b))
            if c:
                row_total += c["pnl"]
                cells.append(f'<td class="{cls(c["pnl"])}">{money(c["pnl"])}'
                             f'<span class="n"> ({c["n"]})</span></td>')
            else:
                cells.append('<td class="muted">—</td>')
        body.append(f'<tr><td class="pk">{html.escape(key)}</td>{"".join(cells)}'
                    f'<td class="{cls(row_total)}"><b>{money(row_total)}</b></td></tr>')
    return (f'<div class="sub">{html.escape(title)}</div>'
            f'<table class="pt"><tr><th>Period</th>{head}<th>Total</th></tr>'
            f'{"".join(body)}</table>')


def render_periods():
    daily = _period_table("Daily — last 14 days", "day", 14)
    weekly = _period_table("Weekly — last 8 weeks (week starts Mon)", "week", 8)
    monthly = _period_table("Monthly — last 6 months", "month", 6)
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Crypto Bots — P&amp;L by period</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}}
 a{{color:#58a6ff;text-decoration:none}}
 .wrap{{padding:14px}}
 .sub{{margin:18px 4px 6px;font-size:14px;color:#c9d1d9;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px;margin:0 4px}}
 table.pt{{width:100%;border-collapse:collapse;font-size:12px;background:#161b22;
   border:1px solid #222;border-radius:8px;overflow:hidden}}
 table.pt th,table.pt td{{padding:7px 9px;text-align:right;border-bottom:1px solid #21262d;white-space:nowrap}}
 table.pt th{{background:#1b2230;color:#8b949e;font-weight:600;text-align:right}}
 table.pt td.pk,table.pt th:first-child{{text-align:left;color:#c9d1d9}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 .n{{color:#6e7681;font-size:11px}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>Crypto Bots — P&amp;L by period &nbsp;·&nbsp;
 <a href="/">← live</a> &nbsp; <a href="/learning">learning →</a></h1></header>
<div class="wrap">{daily}{weekly}{monthly}</div>
<footer>Realized P&amp;L from closed paper trades (durable bot_trades table; survives redeploys).
Cells show P&amp;L and (trade count). Dry-run only. Times UTC. Auto-refreshes every 120s.</footer>
</body></html>'''


_MKT_CACHE = {"md": None, "ts": 0.0}


def market_md_cached(ttl=1800):
    """Live market-regime snapshot (Fear&Greed, dominance, breadth, per-coin trend),
    cached ~30 min so page loads don't hammer the source APIs."""
    import time as _t
    now = _t.time()
    if _MKT_CACHE["md"] is None or now - _MKT_CACHE["ts"] > ttl:
        try:
            import compile_market_data as _cmd
            _MKT_CACHE["md"] = _cmd.snapshot_markdown()
            _MKT_CACHE["ts"] = now
        except Exception as e:
            if _MKT_CACHE["md"] is None:
                return f"Market snapshot unavailable: {type(e).__name__}: {e}"
    return _MKT_CACHE["md"]


def render_market():
    md = market_md_cached()
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="600">
<title>Crypto Bots — market regime</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}} a{{color:#58a6ff;text-decoration:none}}
 pre{{margin:14px;padding:14px;background:#161b22;border:1px solid #222;border-radius:10px;
   font-size:12.5px;line-height:1.5;white-space:pre-wrap;overflow-x:auto}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>Crypto Bots — market regime &nbsp;·&nbsp;
 <a href="/">← live</a> &nbsp; <a href="/periods">P&amp;L by period</a> &nbsp; <a href="/learning">learning</a></h1></header>
<pre>{html.escape(md)}</pre>
<footer>Sources: Binance (trend/vol/breadth), alternative.me (Fear&amp;Greed), CoinGecko (dominance/mcap).
Cached ~30 min. The trend bots (V4/V6/V7) are designed to sit out risk-off regimes. Not financial advice.</footer>
</body></html>'''


class H(BaseHTTPRequestHandler):
    def _auth_ok(self):
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Basic "):
            return False
        try:
            u, p = base64.b64decode(hdr[6:]).decode().split(":", 1)
        except Exception:
            return False
        return u == DASH_USER and p == DASH_PASS

    def _no_cache(self):
        """Forbid any browser/proxy caching. The snapshot is regenerated on every
        request (generated_at = now()), so a cached copy reads as a FROZEN feed:
        a stale JSON gets served with a day-old generated_at and every delta is
        $0.00, which is indistinguishable from genuine zero activity. Railway's
        edge and browsers may cache a 200 with no cache directives, so be explicit
        on every response."""
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200); self._no_cache(); self.end_headers(); self.wfile.write(b"ok"); return
        if self.path.startswith("/pulse.json"):
            # Market pulse (news/social/funding mood) written by market_pulse.py
            # into bot_state. Read-only, no auth — no secrets inside. Serves the
            # laptop brain/scans and anything else that wants the mood feed.
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT to_regclass('public.bot_state') AS t")
                        if cur.fetchone()[0] is None:
                            raise LookupError("bot_state table not created yet")
                        cur.execute("SELECT state, updated_at FROM bot_state WHERE bot = 'market-pulse'")
                        row = cur.fetchone()
                finally:
                    conn.close()
                if not row:
                    payload = {"error": "no pulse published yet"}
                else:
                    st = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    payload = {"updated_at": row[1].isoformat() if row[1] else None}
                    payload.update(st)
                body = json.dumps(payload, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/alerts.json"):
            # [2026-07-11] Evidence alerts + the restrict-only coin-veto list
            # (market_context.py). Read-only, no secrets, no auth — so the
            # scheduled report sessions and any external watchdog can consume.
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT bot, state, updated_at FROM bot_state "
                                    "WHERE bot IN ('fleet-alerts', 'coin-vetoes')")
                        rows_ = {b: (s if isinstance(s, dict) else json.loads(s), u)
                                 for b, s, u in cur.fetchall()}
                finally:
                    conn.close()
                fa = rows_.get("fleet-alerts", ({}, None))
                cv = rows_.get("coin-vetoes", ({}, None))
                body = json.dumps({
                    "alerts": (fa[0].get("alerts") or [])[-25:],
                    "alerts_updated_at": fa[1].isoformat() if fa[1] else None,
                    "coin_vetoes": cv[0].get("coins") or {},
                    "vetoes_updated_at": cv[1].isoformat() if cv[1] else None,
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/pnl.json"):
            # Read-only JSON snapshot of every bot, for the scheduled
            # daily/weekly breakdowns. Dry-run paper P&L only — no secrets.
            # No auth on this path so the scheduled fetcher can read it.
            try:
                rows = fetch_rows()
                try:
                    _enr = fetch_ledger_enrich()
                except Exception:  # noqa: BLE001
                    _enr = {}
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = []
                _now = dt.datetime.now(dt.timezone.utc)
                _age_secs = []   # raw ages, for the freshest-update figure
                _stale_flags = []  # per-bot stale booleans, threshold-aware
                for r in rows.values():
                    d = {k: _ser(v) for k, v in r.items()}
                    # Tag so downstream reports never blend scanner paper-arb
                    # P&L with the trading bots' realized P&L.
                    d["kind"] = "scanner" if r.get("bot") in SCANNERS else "trading"
                    # [2026-07-09 LIGHTER GO-LIVE] venue provenance for the feed:
                    # which bots are real-money live vs shadow/testnet vs paper.
                    _vbase, _vsuf = venue_variant(r.get("bot") or "")
                    d["venue_mode"] = (VENUE_SUFFIXES[_vsuf][2] if _vsuf
                                       else (r.get("extra") or {}).get("venue"))
                    d["live"] = bool(_vsuf == "-lighter")
                    d["base_bot"] = _vbase
                    # [2026-07-07 UNIFORM CARDS] same server-side enrichment the
                    # cards use, for feed consumers (artifact, reports).
                    _en = _enr.get(r.get("bot")) or {}
                    if _en:
                        _td = _en.get("today_equity_delta")
                        if _td is None and _en.get("today_n"):
                            _td = _en.get("today_closed")
                        d["enrich"] = {"today_pnl": _td,
                                       "record": _en.get("record"),
                                       "last_close": _en.get("last_close"),
                                       "positions": _en.get("positions")}
                    # Per-bot heartbeat (2026-06-25): expose each bot's age and a
                    # threshold-aware stale flag so the scheduled report can flag a
                    # single laggard (e.g. equities-regime-ibkr running ~85m behind the
                    # fleet) without recomputing thresholds itself.
                    thr = stale_secs_for(r.get("bot"))
                    ua = r.get("updated_at")
                    if ua is not None:
                        if ua.tzinfo is None:
                            ua = ua.replace(tzinfo=dt.timezone.utc)
                        secs = (_now - ua).total_seconds()
                        d["age_sec"] = int(secs)
                        d["stale"] = bool(secs > thr)
                        _age_secs.append(secs)
                        _stale_flags.append(d["stale"])
                    else:
                        d["age_sec"] = None
                        d["stale"] = None
                    data.append(d)
                # Top-level meta so the scheduled report can detect a frozen feed
                # directly instead of inferring it. feed_stale = EVERY published bot
                # is past ITS OWN threshold (stock bots get the longer window), so a
                # single lagging stock bot no longer trips a false whole-feed alarm
                # — while a truly frozen feed (the 2026-06-22 failure) still does.
                freshest = min(_age_secs) if _age_secs else None
                # [2026-07-09 LIGHTER GO-LIVE] real-money live-fleet subtotal so
                # the scheduled daily/weekly reports can headline it separately.
                _live_rows = [d for d in data if d.get("live")]
                live_meta = {
                    "n_live_bots": len(_live_rows),
                    "live_pnl": round(sum((d.get("pnl_abs") or 0) for d in _live_rows), 2),
                    "live_equity": round(sum((d.get("equity") or 0) for d in _live_rows
                                             if d.get("equity") is not None), 2),
                    "live_bots": [d.get("bot") for d in _live_rows],
                }
                meta = {
                    "generated_at": _now.isoformat(),
                    "stale_threshold_sec": STALE_SECONDS,
                    "stock_stale_threshold_sec": STOCK_STALE_SECONDS,
                    "sniper_stale_threshold_sec": SNIPER_STALE_SECONDS,
                    "freshest_update_age_sec": (int(freshest) if freshest is not None else None),
                    "feed_stale": bool(_stale_flags) and all(_stale_flags),
                    "n_stale": sum(1 for s in _stale_flags if s),
                    "n_live": len(_stale_flags),
                    "live_fleet": live_meta,
                }
                payload = json.dumps({"meta": meta, "bots": data}).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/periods.json"):
            # Realized daily/weekly/monthly P&L (no auth, like /pnl.json) so a
            # scheduled fetcher can read it. Dry-run paper P&L only.
            try:
                payload = json.dumps(periods_payload()).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/trades.json"):
            # Read-only per-trade history for the scheduled daily/weekly
            # breakdowns and the win/loss deep dive. Dry-run paper trades only —
            # no secrets. No auth on this path (like /pnl.json) so the scheduled
            # fetcher can read it. Query params: ?bot=<name>&limit=<n>&include_open=1
            q = parse_qs(urlparse(self.path).query)
            bot = q.get("bot", [None])[0]
            include_open = q.get("include_open", ["0"])[0] in ("1", "true", "yes")
            try:
                limit = min(max(int(q.get("limit", ["500"])[0]), 1), 5000)
            except (ValueError, TypeError):
                limit = 500
            try:
                rows = fetch_trades(bot=bot, limit=limit, include_open=include_open)
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = [{k: _ser(v) for k, v in r.items()} for r in rows]
                payload = json.dumps({"trades": data}).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Crypto Bots"')
            self.end_headers()
            self.wfile.write(b"Auth required")
            return
        try:
            if self.path.startswith("/market"):
                body = render_market().encode()
            elif self.path.startswith("/periods"):
                body = render_periods().encode()
            elif self.path.startswith("/learning"):
                body = render_learning().encode()
            elif self.path.startswith("/history"):
                body = render_history().encode()
            else:
                body = render().encode()
        except Exception as e:
            body = f"<pre>dashboard error: {html.escape(str(e))}</pre>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self._no_cache()
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"[pnl_dashboard] serving live P&L on :{PORT} "
          f"({'DB set' if DATABASE_URL else 'NO DATABASE_URL'})", flush=True)
    # Background: snapshot every bot's equity into history every 5 min so the
    # /history charts build up over time (no changes needed in any bot).
    if DATABASE_URL:
        threading.Thread(target=history_loop, args=(300,), daemon=True).start()
    # Background: cloud-side scheduled P&L emails (dormant until SMTP_* env vars set).
    try:
        import report_emailer, sys as _sys
        threading.Thread(target=report_emailer.run_loop, args=(_sys.modules[__name__],),
                         daemon=True).start()
    except Exception as _e:
        print(f"[pnl_dashboard] emailer not started: {_e}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
