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
import base64
import html
import datetime as dt
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Login for THIS dashboard page (override via env on Railway).
DASH_USER = os.environ.get("DASH_USER", "eamon")
DASH_PASS = os.environ.get("DASH_PASS", "freqbot2026")

# Expected bots — so the grid shows a bot even before its first publish.
EXPECTED = ["hl-perps-rsi", "hl-momo-breakout", "triangular-arb", "listing-sniper",
            "trend-golden-cross", "intraday-daytrader-5m", "swing-dip-buyer",
            "momo-breakout-4h", "momo-breakout-alt"]

# Scanners book OPTIMISTIC paper-arb fills (observed spreads, no slippage/latency).
# Their pnl_abs is real paper P&L but on a rosier basis than the freqtrade bots'
# simulated fills — so it is reported as a SEPARATE subtotal and never folded
# into the trading-bot P&L headline.
SCANNERS = {"triangular-arb", "cross-exchange-arb"}

# The only bots that should appear. Anything else in the table (e.g. legacy
# pre-rename rows perps-bot/momo-bot/v4core/v5gated/v6swing/v7momo/v8momo) is a
# stale duplicate and is filtered out here so it can never skew totals or the
# grid — independent of whether the Postgres table has been pruned yet.
CURRENT_BOTS = set(EXPECTED) | SCANNERS

STALE_SECONDS = 180  # snapshots older than this are flagged "stale"


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
            # grid, totals, or the /pnl.json feed.
            return {r["bot"]: r for r in cur.fetchall()
                    if r["bot"] in CURRENT_BOTS}
    finally:
        conn.close()


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


def age_str(updated_at):
    if updated_at is None:
        return "never", True
    now = dt.datetime.now(dt.timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=dt.timezone.utc)
    secs = (now - updated_at).total_seconds()
    stale = secs > STALE_SECONDS
    if secs < 90:
        return f"{int(secs)}s ago", stale
    if secs < 5400:
        return f"{int(secs // 60)}m ago", stale
    return f"{int(secs // 3600)}h ago", stale


def card(bot, row):
    if row is None:
        return (f'<div class="card"><h2>{html.escape(bot)} '
                f'<span class="dot off"></span></h2>'
                f'<div class="muted">no data yet — bot has not published</div></div>')
    age, stale = age_str(row.get("updated_at"))
    status = (row.get("status") or "?")
    dot = "warn" if stale else ("off" if status in ("halted", "error") else "on")
    extra = row.get("extra") or {}
    if isinstance(extra, dict):
        extra_bits = " · ".join(f"{k}: {html.escape(str(v))}" for k, v in extra.items())
    else:
        extra_bits = html.escape(str(extra))
    rows = []
    if row.get("equity") is not None:
        rows.append(f'<div class="row"><span>Equity</span><b>{money(row.get("equity"))}</b></div>')
    if row.get("pnl_abs") is not None:
        pnl_label = "Paper (arb)" if bot in SCANNERS else "P&amp;L"
        rows.append(f'<div class="row"><span>{pnl_label}</span>'
                    f'<b class="{cls(row.get("pnl_abs"))}">{money(row.get("pnl_abs"))}'
                    f'{" (" + pct(row.get("pnl_pct")) + ")" if row.get("pnl_pct") is not None else ""}</b></div>')
    if row.get("closed_trades") is not None or row.get("open_trades") is not None:
        rows.append(f'<div class="row"><span>Trades</span>'
                    f'<b>{row.get("closed_trades") or 0} closed · {row.get("open_trades") or 0} open</b></div>')
    if row.get("wins") is not None:
        rows.append(f'<div class="row"><span>Win / Loss</span>'
                    f'<b>{row.get("wins") or 0} / {row.get("losses") or 0}</b></div>')
    return f'''<div class="card">
      <h2>{html.escape(bot)} <span class="dot {dot}"></span></h2>
      <div class="muted">{html.escape(str(status))} · updated {html.escape(age)}{" · STALE" if stale else ""}</div>
      {"".join(rows)}
      {f'<div class="sub">{extra_bits}</div>' if extra_bits else ''}
    </div>'''


def render():
    try:
        rows = fetch_rows()
        db_err = None
    except Exception as e:
        rows, db_err = {}, f"{type(e).__name__}: {e}"

    # union of expected + whatever actually published
    names = list(EXPECTED) + [b for b in rows if b not in EXPECTED]
    cards = [card(b, rows.get(b)) for b in names]

    live = [r for r in rows.values() if r]
    # Trading-bot P&L (the real headline) excludes scanners; scanners' optimistic
    # paper-arb booking is shown as its own subtotal so it can't flatter the total.
    tot_pnl = sum((r.get("pnl_abs") or 0) for r in live
                  if r.get("bot") not in SCANNERS)
    scan_pnl = sum((r.get("pnl_abs") or 0) for r in live
                   if r.get("bot") in SCANNERS)
    tot_equity = sum((r.get("equity") or 0) for r in live if r.get("equity") is not None)
    n_open = sum((r.get("open_trades") or 0) for r in live)
    n_closed = sum((r.get("closed_trades") or 0) for r in live)
    online = sum(1 for r in live
                 if not age_str(r.get("updated_at"))[1] and r.get("status") not in ("halted", "error"))

    banner = ""
    if db_err:
        banner = (f'<div class="banner">Database unreachable: {html.escape(db_err)}. '
                  f'Check DATABASE_URL on this service.</div>')
    elif not live:
        banner = ('<div class="banner">Connected to Postgres, but no bot has published yet. '
                  'Make sure each bot has DATABASE_URL set and has run at least one loop.</div>')

    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Crypto Bots — Live P&amp;L</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0 0 6px;font-size:18px}}
 .totals{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}}
 .totals b{{font-size:16px}}
 .banner{{margin:12px 14px 0;padding:10px 12px;background:#3d2b12;border:1px solid #6b4a16;border-radius:8px;color:#f0c674;font-size:13px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;padding:14px}}
 .card{{background:#161b22;border:1px solid #222;border-radius:10px;padding:14px}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:10px 0 4px;font-size:12px;color:#8b949e}}
 .muted{{color:#8b949e;font-size:12px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:4px}}
 .dot.on{{background:#3fb950}} .dot.off{{background:#f85149}} .dot.warn{{background:#d29922}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header>
 <h1>Crypto Bots — live P&amp;L &nbsp;·&nbsp; <a href="/periods" style="color:#58a6ff;font-size:14px">P&amp;L by day/week/month →</a> &nbsp;·&nbsp; <a href="/learning" style="color:#58a6ff;font-size:14px">what they're learning →</a></h1>
 <div class="totals">
   <span>Bots live <b>{online}</b></span>
   <span>Trading P&amp;L <b class="{cls(tot_pnl)}">{money(tot_pnl)}</b></span>
   <span>Scanner paper <b class="{cls(scan_pnl)}">{money(scan_pnl)}</b></span>
   <span>Total equity <b>{money(tot_equity)}</b></span>
   <span>Trades <b>{n_closed} closed · {n_open} open</b></span>
 </div>
</header>
{banner}
<div class="grid">{"".join(cards)}</div>
<footer>Reads the shared bot_pnl Postgres table. Auto-refreshes every 30s. Times UTC.
Snapshots older than {STALE_SECONDS}s are flagged stale.</footer>
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


TRADING_BOTS_ORDER = ["trend-golden-cross", "intraday-daytrader-5m",
                      "swing-dip-buyer", "momo-breakout-4h", "momo-breakout-alt"]


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

    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
        if self.path.startswith("/pnl.json"):
            # Read-only JSON snapshot of every bot, for the scheduled
            # daily/weekly breakdowns. Dry-run paper P&L only — no secrets.
            # No auth on this path so the scheduled fetcher can read it.
            try:
                rows = fetch_rows()
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = []
                for r in rows.values():
                    d = {k: _ser(v) for k, v in r.items()}
                    # Tag so downstream reports never blend scanner paper-arb
                    # P&L with the trading bots' realized P&L.
                    d["kind"] = "scanner" if r.get("bot") in SCANNERS else "trading"
                    data.append(d)
                payload = json.dumps({"bots": data}).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
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
            if self.path.startswith("/periods"):
                body = render_periods().encode()
            elif self.path.startswith("/learning"):
                body = render_learning().encode()
            else:
                body = render().encode()
        except Exception as e:
            body = f"<pre>dashboard error: {html.escape(str(e))}</pre>".encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"[pnl_dashboard] serving live P&L on :{PORT} "
          f"({'DB set' if DATABASE_URL else 'NO DATABASE_URL'})", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
