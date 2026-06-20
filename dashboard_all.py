#!/usr/bin/env python3
"""
Build ONE self-contained dashboard.html covering every bot in this folder.

Unlike dashboard.py (which only covered the triangular-arb engine), this scans:
  * every Freqtrade config_*.json  -> a bot row (strategy, exchange, pairs,
    stake, dry-run) enriched with timeframe / stoploss / ROI read straight
    from the matching strategies/<Strategy>.py file.
  * triangular_arb.py              -> the paper arbitrage engine (+ its charts
    built from arb_opportunities.csv).
  * listing_sniper.py              -> the new-listing paper sniper.

Stdlib only. The page embeds its data as JSON and opens straight from disk,
no web server. Charts use Chart.js from a CDN.

    python3 dashboard_all.py      # writes dashboard.html next to this script
    open dashboard.html           # (macOS) view it

Re-run any time to refresh. The scheduled daily digest runs this for you.
"""

import csv
import glob
import json
import os
import re
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "arb_opportunities.csv")
OUT_PATH = os.path.join(HERE, "dashboard.html")
STRAT_DIR = os.path.join(HERE, "strategies")


# ----------------------------- strategy parsing -----------------------------

def _find_strategy_file(strategy_name):
    """Return the path to strategies/<Strategy>.py if it exists."""
    if not strategy_name:
        return None
    cand = os.path.join(STRAT_DIR, f"{strategy_name}.py")
    if os.path.exists(cand):
        return cand
    # Fall back: scan for a `class <Strategy>(IStrategy)` definition.
    for p in glob.glob(os.path.join(STRAT_DIR, "*.py")):
        try:
            with open(p) as f:
                if re.search(rf"class\s+{re.escape(strategy_name)}\b", f.read()):
                    return p
        except OSError:
            continue
    return None


def _scalar(pattern, text, cast=str, default=None):
    m = re.search(pattern, text)
    if not m:
        return default
    try:
        return cast(m.group(1))
    except (ValueError, TypeError):
        return default


def parse_strategy(strategy_name):
    """Pull timeframe / stoploss / roi-cap / trailing from the strategy file."""
    path = _find_strategy_file(strategy_name)
    info = {"timeframe": None, "stoploss": None, "roi_cap": None,
            "trailing": None, "file": os.path.basename(path) if path else None}
    if not path:
        return info
    try:
        with open(path) as f:
            text = f.read()
    except OSError:
        return info
    info["timeframe"] = _scalar(r"^\s*timeframe\s*=\s*['\"]([^'\"]+)['\"]",
                                text, str, None) or \
        _scalar(r"\btimeframe\s*=\s*['\"]([^'\"]+)['\"]", text, str, None)
    info["stoploss"] = _scalar(r"\bstoploss\s*=\s*(-?\d+\.?\d*)", text, float, None)
    info["trailing"] = bool(re.search(r"\btrailing_stop\s*=\s*True", text))
    # ROI cap: the "0": X entry in minimal_roi, if present on one line.
    roi = re.search(r"minimal_roi\s*=\s*\{[^}]*?['\"]0['\"]\s*:\s*([\d.]+)", text,
                    re.DOTALL)
    if roi:
        try:
            info["roi_cap"] = float(roi.group(1))
        except ValueError:
            pass
    return info


def load_freqtrade_bots():
    bots = []
    for cfg_path in sorted(glob.glob(os.path.join(HERE, "config_*.json"))):
        try:
            with open(cfg_path) as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        strat = d.get("strategy")
        ex = (d.get("exchange") or {}).get("name")
        pairs = (d.get("exchange") or {}).get("pair_whitelist", []) or []
        si = parse_strategy(strat)
        bots.append({
            "kind": "freqtrade",
            "name": strat or os.path.basename(cfg_path),
            "config": os.path.basename(cfg_path),
            "exchange": ex,
            "stake_currency": d.get("stake_currency"),
            "stake_amount": d.get("stake_amount"),
            "max_open_trades": d.get("max_open_trades"),
            "dry_run": d.get("dry_run", True),
            "timeframe": si["timeframe"],
            "stoploss": si["stoploss"],
            "roi_cap": si["roi_cap"],
            "trailing": si["trailing"],
            "strategy_file": si["file"],
        })
    return bots


def engine_bots():
    """The two standalone python engines, described from their headers."""
    engines = []
    if os.path.exists(os.path.join(HERE, "triangular_arb.py")):
        engines.append({
            "kind": "engine", "name": "Triangular Arbitrage",
            "config": "triangular_arb.py", "exchange": "kraken",
            "style": "3-leg depth-aware arb scan", "pairs_desc": "full liquid spot universe",
            "dry_run": True, "data": "arb_opportunities.csv",
            "desc": "Scans Kraken for 3-leg loops profitable after fees + real "
                    "order-book slippage. Public data only, no API keys, paper P&L.",
        })
    if os.path.exists(os.path.join(HERE, "listing_sniper.py")):
        engines.append({
            "kind": "engine", "name": "Listing Sniper",
            "config": "listing_sniper.py", "exchange": "top ~100 (CCXT)",
            "style": "new-listing paper sniper", "pairs_desc": "new USD/USDT/USDC/EUR pairs",
            "dry_run": True, "data": "sniper trades CSV",
            "desc": "Detects brand-new spot pairs across the top ~100 exchanges "
                    "(via CCXT, polled concurrently, best-effort skip) and opens "
                    "paper positions with TP 5x / SL / max-hold. 100% dry-run, "
                    "public endpoints only.",
        })
    if os.path.exists(os.path.join(HERE, "hyperliquid_momo_bot.py")):
        engines.append({
            "kind": "engine", "name": "Hyperliquid Perps (MomoBreakout)",
            "config": "hyperliquid_momo_bot.py", "exchange": "hyperliquid (testnet)",
            "style": "4h Donchian 30/15 breakout + EMA200, 12% stop",
            "pairs_desc": "BTC / ETH / SOL perps",
            "dry_run": True, "data": "momo_bot.log",
            "desc": "Perpetuals momentum bot ported from MomoBreakoutV1. Backtest: "
                    "+90% (BTC) / +127% (ETH) at 1x, beats buy & hold on ETH with "
                    "~20-25% drawdown. Testnet only; paper/dry-run by default. "
                    "Posts trade events to Slack via Zapier webhook.",
        })
    return engines


# ------------------------------- arb data -----------------------------------

def load_arb_rows():
    if not os.path.exists(CSV_PATH):
        return []
    rows = []
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            try:
                rows.append({
                    "t": r["timestamp"], "cycle": r["cycle"],
                    "top": float(r["top_of_book_net_pct"]),
                    "depth": float(r["depth_net_pct"]),
                    "pnl": float(r["paper_pnl"]),
                    "filled": str(r["filled"]).strip().lower() == "true",
                    "bal": float(r["virtual_balance"]),
                })
            except (KeyError, ValueError):
                continue
    return rows


def summarize_arb(rows):
    if not rows:
        return {"count": 0}
    fills = [r for r in rows if r["filled"] and r["depth"] >= 0]
    slip = [r["top"] - r["depth"] for r in rows]
    return {
        "count": len(rows), "fills": len(fills), "balance": rows[-1]["bal"],
        "best_depth": max(r["depth"] for r in rows),
        "avg_slip": sum(slip) / len(slip),
        "first": rows[0]["t"], "last": rows[-1]["t"],
    }


# ------------------------------- rendering ----------------------------------

def _fmt(v, suffix="", dash="—"):
    return f"{v}{suffix}" if v not in (None, "") else dash


def render(bots, engines, arb_rows, arb):
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    total = len(bots) + len(engines)
    n_dry = sum(1 for b in bots if b.get("dry_run")) + \
        sum(1 for e in engines if e.get("dry_run"))
    n_live = total - n_dry
    exchanges = sorted({b.get("exchange") for b in bots if b.get("exchange")} |
                       {e.get("exchange") for e in engines if e.get("exchange")})

    def card(label, value, sub=""):
        return (f'<div class="card"><div class="lbl">{label}</div>'
                f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')

    overview = "".join([
        card("Bots configured", str(total), f"{len(bots)} strategies · {len(engines)} engines"),
        card("Mode", f"{n_dry} paper" + (f" · {n_live} live" if n_live else ""),
             "all dry-run = no real orders" if not n_live else "⚠ live bot present"),
        card("Exchanges", ", ".join(exchanges) or "—", "venues in use"),
        card("Arb loops logged", f"{arb.get('count', 0):,}",
             "paper balance " + (f"{arb['balance']:+.2f}" if arb.get("count") else "no data yet")),
    ])

    # Strategy bot table
    strat_rows = "".join(
        f'<tr>'
        f'<td class="b">{b["name"]}</td>'
        f'<td>{_fmt(b.get("exchange"))}</td>'
        f'<td>{_fmt(b.get("timeframe"))}</td>'
        f'<td>{", ".join((b.get("pairs") or [])) if b.get("pairs") else ", ".join(b.get("pair_list", [])) or "—"}</td>'
        f'<td>{_fmt(b.get("stoploss"), "")}</td>'
        f'<td>{_fmt(b.get("max_open_trades"))}</td>'
        f'<td>{_fmt(b.get("stake_currency"))}</td>'
        f'<td><span class="pill {"dry" if b.get("dry_run") else "live"}">'
        f'{"paper" if b.get("dry_run") else "LIVE"}</span></td>'
        f'<td class="mut">{_fmt(b.get("config"))}</td>'
        f'</tr>'
        for b in bots
    ) or '<tr><td colspan="9" class="muted">No Freqtrade configs found.</td></tr>'

    # Engine cards
    eng_html = "".join(
        f'<div class="ecard"><div class="etop"><span class="ename">{e["name"]}</span>'
        f'<span class="pill {"dry" if e.get("dry_run") else "live"}">'
        f'{"paper" if e.get("dry_run") else "LIVE"}</span></div>'
        f'<div class="emeta">{e.get("exchange","—")} · {e.get("style","")} · '
        f'{e.get("pairs_desc","")}</div>'
        f'<div class="edesc">{e.get("desc","")}</div>'
        f'<div class="efile">{e.get("config","")} → {e.get("data","")}</div></div>'
        for e in engines
    ) or '<div class="muted">No standalone engines found.</div>'

    # arb charts
    bal_series = [{"x": r["t"], "y": round(r["bal"], 4)} for r in arb_rows]
    scatter = [{"x": round(r["top"], 4), "y": round(r["depth"], 4)} for r in arb_rows]
    if arb_rows:
        arb_cards = "".join([
            card("Loops logged", f"{arb['count']:,}", f"{arb['first']} → {arb['last']}"),
            card("Paper fills", f"{arb['fills']:,}", "profitable & fully filled"),
            card("Virtual balance", f"{arb['balance']:+.2f}", "cumulative paper P&L"),
            card("Best depth edge", f"{arb['best_depth']:+.3f}%", "after fees + slippage"),
        ])
        arb_note = ""
    else:
        arb_cards = card("Status", "No data yet",
                         "Start triangular_arb.py — loops will appear here.")
        arb_note = ('<p class="note">arb_opportunities.csv is empty so far, so the '
                    'charts below stay blank until the arb engine logs its first scans.</p>')

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Crypto Bots — Unified Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family:-apple-system,system-ui,sans-serif; margin:0;
         background:#0e1116; color:#e6e9ef; }}
  header {{ padding:20px 28px; border-bottom:1px solid #222834; }}
  h1 {{ font-size:18px; margin:0; }}
  .gen {{ color:#7c8698; font-size:12px; margin-top:4px; }}
  .wrap {{ padding:22px 28px; max-width:1180px; margin:0 auto; }}
  h2.sec {{ font-size:13px; text-transform:uppercase; letter-spacing:.05em;
            color:#9aa4b5; margin:30px 0 12px; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr));
            gap:14px; margin-bottom:8px; }}
  .card {{ background:#161b24; border:1px solid #222834; border-radius:12px; padding:16px; }}
  .lbl {{ color:#7c8698; font-size:12px; text-transform:uppercase; letter-spacing:.04em; }}
  .val {{ font-size:23px; font-weight:650; margin-top:6px; }}
  .sub {{ color:#7c8698; font-size:11px; margin-top:4px; }}
  .panel {{ background:#161b24; border:1px solid #222834; border-radius:12px;
            padding:18px; margin-bottom:22px; overflow-x:auto; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:8px 10px; border-bottom:1px solid #1c222d;
            white-space:nowrap; }}
  th {{ color:#7c8698; font-weight:550; }}
  td.b {{ font-weight:600; }}
  td.mut {{ color:#7c8698; }}
  .pill {{ font-size:11px; padding:2px 8px; border-radius:20px; font-weight:600; }}
  .pill.dry {{ background:rgba(70,211,154,.14); color:#46d39a; }}
  .pill.live {{ background:rgba(239,111,123,.16); color:#ef6f7b; }}
  .egrid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(330px,1fr)); gap:14px; }}
  .ecard {{ background:#161b24; border:1px solid #222834; border-radius:12px; padding:16px; }}
  .etop {{ display:flex; justify-content:space-between; align-items:center; }}
  .ename {{ font-weight:650; font-size:15px; }}
  .emeta {{ color:#9aa4b5; font-size:12px; margin:6px 0 8px; }}
  .edesc {{ font-size:13px; line-height:1.5; color:#cdd4e0; }}
  .efile {{ color:#7c8698; font-size:11px; margin-top:10px; font-family:ui-monospace,monospace; }}
  .panel h3 {{ font-size:14px; margin:0 0 14px; color:#c7cedb; }}
  .pos {{ color:#46d39a; }} .neg {{ color:#ef6f7b; }}
  .muted {{ color:#7c8698; text-align:center; padding:18px; }}
  .note {{ color:#7c8698; font-size:12px; line-height:1.5; }}
  canvas {{ max-height:300px; }}
</style></head>
<body>
<header>
  <h1>Crypto Bots — Unified Dashboard</h1>
  <div class="gen">Generated {generated} · {total} bots · paper/dry-run unless flagged LIVE</div>
</header>
<div class="wrap">
  <div class="cards">{overview}</div>

  <h2 class="sec">Strategy bots (Freqtrade)</h2>
  <div class="panel">
    <table><thead><tr>
      <th>Strategy</th><th>Exchange</th><th>TF</th><th>Pairs</th>
      <th>Stoploss</th><th>Max trades</th><th>Stake</th><th>Mode</th><th>Config</th>
    </tr></thead><tbody>{strat_rows}</tbody></table>
  </div>

  <h2 class="sec">Standalone engines</h2>
  <div class="egrid">{eng_html}</div>

  <h2 class="sec">Triangular arbitrage — paper performance</h2>
  <div class="cards">{arb_cards}</div>
  {arb_note}
  <div class="panel"><h3>Virtual balance over time (cumulative paper P&amp;L)</h3>
    <canvas id="bal"></canvas></div>
  <div class="panel"><h3>Top-of-book edge vs depth-confirmed edge (%)</h3>
    <p class="note">Points far below the diagonal = slippage eating the edge.</p>
    <canvas id="scatter"></canvas></div>

  <p class="note">Reminder: every bot here is dry-run / paper. A profitable
     backtest or paper run is not proof of live profit — fees, slippage and
     overfitting quietly eat returns. This is not financial advice.</p>
</div>
<script>
const BAL = {json.dumps(bal_series)};
const SCAT = {json.dumps(scatter)};
const grid = {{ color:'#1c222d' }}, ticks = {{ color:'#7c8698' }};
if (BAL.length) new Chart(document.getElementById('bal'), {{
  type:'line',
  data:{{ datasets:[{{ label:'Virtual balance', data:BAL, parsing:false,
    borderColor:'#46d39a', backgroundColor:'rgba(70,211,154,.12)',
    fill:true, tension:.15, pointRadius:0, borderWidth:2 }}] }},
  options:{{ scales:{{ x:{{ type:'category', grid, ticks:{{...ticks, maxTicksLimit:8}} }},
    y:{{ grid, ticks }} }}, plugins:{{ legend:{{ display:false }} }} }}
}});
if (SCAT.length) {{
  const lo = Math.min(...SCAT.map(p=>Math.min(p.x,p.y)));
  const hi = Math.max(...SCAT.map(p=>Math.max(p.x,p.y)));
  new Chart(document.getElementById('scatter'), {{
    data:{{ datasets:[
      {{ type:'scatter', label:'loops', data:SCAT, pointRadius:3,
         backgroundColor:'rgba(120,170,255,.6)' }},
      {{ type:'line', label:'y = x', data:[{{x:lo,y:lo}},{{x:hi,y:hi}}],
         parsing:false, borderColor:'#7c8698', borderDash:[5,5],
         pointRadius:0, borderWidth:1 }} ]}},
    options:{{ scales:{{ x:{{ title:{{display:true,text:'top-of-book %',color:'#7c8698'}},
      grid, ticks }}, y:{{ title:{{display:true,text:'depth-confirmed %',color:'#7c8698'}},
      grid, ticks }} }}, plugins:{{ legend:{{ display:false }} }} }}
  }});
}}
</script>
</body></html>"""


def collect():
    bots = load_freqtrade_bots()
    # attach pair lists for display
    for cfg_path in sorted(glob.glob(os.path.join(HERE, "config_*.json"))):
        try:
            with open(cfg_path) as f:
                d = json.load(f)
        except (OSError, json.JSONDecodeError):
            continue
        for b in bots:
            if b["config"] == os.path.basename(cfg_path):
                b["pair_list"] = (d.get("exchange") or {}).get("pair_whitelist", []) or []
    return bots


def main():
    bots = collect()
    engines = engine_bots()
    arb_rows = load_arb_rows()
    arb = summarize_arb(arb_rows)
    html = render(bots, engines, arb_rows, arb)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote {OUT_PATH} — {len(bots)} strategy bots + {len(engines)} engines, "
          f"arb loops: {arb.get('count', 0)}.")
    return bots, engines, arb


if __name__ == "__main__":
    main()
