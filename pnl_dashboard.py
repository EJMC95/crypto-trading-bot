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
            return {r["bot"]: r for r in cur.fetchall()}
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
        rows.append(f'<div class="row"><span>P&amp;L</span>'
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
    tot_pnl = sum((r.get("pnl_abs") or 0) for r in live)
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
 <h1>Crypto Bots — live P&amp;L</h1>
 <div class="totals">
   <span>Bots live <b>{online}</b></span>
   <span>Total P&amp;L <b class="{cls(tot_pnl)}">{money(tot_pnl)}</b></span>
   <span>Total equity <b>{money(tot_equity)}</b></span>
   <span>Trades <b>{n_closed} closed · {n_open} open</b></span>
 </div>
</header>
{banner}
<div class="grid">{"".join(cards)}</div>
<footer>Reads the shared bot_pnl Postgres table. Auto-refreshes every 30s. Times UTC.
Snapshots older than {STALE_SECONDS}s are flagged stale.</footer>
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
            # Read-only JSON of every bot's latest snapshot, for the scheduled
            # daily/weekly breakdowns. Dry-run paper P&L only — no secrets.
            try:
                rows = fetch_rows()
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = [{k: _ser(v) for k, v in r.items()} for r in rows.values()]
                payload = json.dumps({"bots": data}).encode()
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode()
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
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
