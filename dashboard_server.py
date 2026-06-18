#!/usr/bin/env python3
"""
Combined P&L + trades dashboard for the 5 Freqtrade bots that run in this
container. Serves ONE password-protected web page on $PORT (Railway exposes it).

It talks to each bot's local REST API (127.0.0.1:<port>), aggregates profit,
open trades and recent closed trades, and renders a mobile-friendly page that
auto-refreshes. Stdlib only — no extra deps (runs on the freqtrade image).
"""
import os, json, base64, urllib.request, html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

# Bot REST creds (match the api_server section of every config)
BOT_USER = "freqtrader"
BOT_PASS = "freqbot2026"
# Login for THIS dashboard page
DASH_USER = "eamon"
DASH_PASS = "freqbot2026"

BOTS = [
    ("v4core",  8085, "ImprovedStrategyV4 / 1d trend core", "1d"),
    ("v5gated", 8084, "DayTraderV5Gated / 5m gated",        "5m"),
    ("v6swing", 8086, "SwingDipV1 / daily dip-buy",         "1d"),
    ("v7momo",  8087, "MomoBreakoutV1 / 4h breakout",       "4h"),
    ("v8momo",  8088, "TrendMomoV1 / daily SMA cross",      "1d"),
]
import urllib.parse
PORT = int(os.environ.get("PORT", "8080"))


def _req(url, headers=None, method="GET", timeout=6):
    req = urllib.request.Request(url, headers=headers or {}, method=method)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _token(port):
    auth = base64.b64encode(f"{BOT_USER}:{BOT_PASS}".encode()).decode()
    return _req(f"http://127.0.0.1:{port}/api/v1/token/login",
                headers={"Authorization": f"Basic {auth}"}, method="POST")["access_token"]


def fetch(name, port, desc, tf=None):
    d = {"name": name, "port": port, "desc": desc, "online": False,
         "open": [], "closed": []}
    try:
        h = {"Authorization": f"Bearer {_token(port)}"}
        d["profit"] = _req(f"http://127.0.0.1:{port}/api/v1/profit", headers=h)
        d["open"] = _req(f"http://127.0.0.1:{port}/api/v1/status", headers=h) or []
        tr = _req(f"http://127.0.0.1:{port}/api/v1/trades?limit=8", headers=h)
        d["closed"] = (tr.get("trades", []) if isinstance(tr, dict) else tr) or []
        d["online"] = True
    except Exception as e:
        d["error"] = type(e).__name__
    return d


def money(x):
    try:
        return f"{float(x):+,.2f}"
    except (TypeError, ValueError):
        return "—"


def pct(x):
    try:
        return f"{float(x)*100:+.2f}%"
    except (TypeError, ValueError):
        return "—"


def cls(x):
    try:
        return "pos" if float(x) >= 0 else "neg"
    except (TypeError, ValueError):
        return ""


def trade_rows(trades, closed=False):
    if not trades:
        return '<tr><td colspan="4" class="muted">none</td></tr>'
    out = []
    for t in trades:
        pair = html.escape(str(t.get("pair", "?")))
        pr = t.get("profit_abs") if "profit_abs" in t else t.get("profit_ratio")
        prr = t.get("profit_ratio")
        when = (t.get("close_date") or t.get("open_date") or "")[:16].replace("T", " ")
        extra = html.escape(str(t.get("exit_reason", ""))) if closed else \
            f'{float(t.get("current_rate",0)):,.2f}' if t.get("current_rate") else ""
        out.append(
            f'<tr><td>{pair}</td><td class="{cls(prr)}">{money(t.get("profit_abs"))}</td>'
            f'<td class="{cls(prr)}">{pct(prr)}</td><td class="muted">{html.escape(str(extra))} {when}</td></tr>')
    return "".join(out)


def render():
    bots = [fetch(*b) for b in BOTS]
    tot_closed = sum((b.get("profit", {}).get("profit_closed_coin") or 0) for b in bots if b["online"])
    tot_open = sum((float(t.get("profit_abs") or 0) for b in bots for t in b["open"]))
    n_open = sum(len(b["open"]) for b in bots)
    n_closed = sum((b.get("profit", {}).get("closed_trade_count") or 0) for b in bots if b["online"])
    online = sum(1 for b in bots if b["online"])

    cards = []
    for b in bots:
        if not b["online"]:
            cards.append(f'<div class="card"><h2>{b["name"]} <span class="dot off"></span></h2>'
                         f'<div class="muted">{html.escape(b["desc"])}</div>'
                         f'<div class="muted">offline / starting ({b.get("error","")})</div></div>')
            continue
        p = b.get("profit", {})
        cards.append(f'''<div class="card">
          <h2>{b["name"]} <span class="dot on"></span></h2>
          <div class="muted">{html.escape(b["desc"])}</div>
          <div class="row"><span>Closed P&amp;L</span><b class="{cls(p.get("profit_closed_coin"))}">{money(p.get("profit_closed_coin"))} USD ({pct(p.get("profit_closed_percent"))})</b></div>
          <div class="row"><span>Trades</span><b>{p.get("closed_trade_count",0)} closed · {len(b["open"])} open</b></div>
          <div class="row"><span>Win / Loss</span><b>{p.get("winning_trades",0)} / {p.get("losing_trades",0)}</b></div>
          <div class="sub">Open trades</div>
          <table><tr><th>Pair</th><th>P&amp;L</th><th>%</th><th>now / age</th></tr>{trade_rows(b["open"])}</table>
          <div class="sub">Recent closed</div>
          <table><tr><th>Pair</th><th>P&amp;L</th><th>%</th><th>reason / date</th></tr>{trade_rows(b["closed"], closed=True)}</table>
        </div>''')

    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="30">
<title>Crypto Bots — P&amp;L</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0 0 6px;font-size:18px}}
 .totals{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px}}
 .totals b{{font-size:16px}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;padding:14px}}
 .card{{background:#161b22;border:1px solid #222;border-radius:10px;padding:14px}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:10px 0 4px;font-size:12px;color:#8b949e;text-transform:uppercase;letter-spacing:.04em}}
 table{{width:100%;border-collapse:collapse;font-size:12px}}
 th,td{{text-align:left;padding:3px 4px;border-bottom:1px solid #21262d}}
 th{{color:#8b949e;font-weight:600}}
 .muted{{color:#8b949e}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:4px}}
 .dot.on{{background:#3fb950}} .dot.off{{background:#f85149}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header>
 <h1>Crypto Bots — combined P&amp;L &amp; trades</h1>
 <div class="totals">
   <span>Bots online <b>{online}/5</b></span>
   <span>Total closed P&amp;L <b class="{cls(tot_closed)}">{money(tot_closed)} USD</b></span>
   <span>Open P&amp;L <b class="{cls(tot_open)}">{money(tot_open)} USD</b></span>
   <span>Trades <b>{n_closed} closed · {n_open} open</b></span>
 </div>
</header>
<div class="grid">{"".join(cards)}</div>
<footer>Dry-run paper trading. Auto-refreshes every 30s. Times UTC.</footer>
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
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Crypto Bots"')
            self.end_headers()
            self.wfile.write(b"Auth required")
            return
        if self.path.startswith("/health"):
            self.send_response(200); self.end_headers(); self.wfile.write(b"ok"); return
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
    print(f"[dashboard] serving combined P&L on :{PORT}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
