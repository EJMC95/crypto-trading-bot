#!/usr/bin/env python3
"""
Build a self-contained dashboard.html from arb_opportunities.csv.

No dependencies (stdlib only). The CSV data is embedded directly into the HTML
as JSON, so the page opens straight from disk with no local web server and no
file-access errors. Charts use Chart.js from a CDN.

    python3 dashboard.py          # writes dashboard.html next to the CSV
    open dashboard.html           # (macOS) view it

Re-run any time to refresh. The scheduled morning digest runs this for you.
"""

import csv
import json
import os
from datetime import datetime, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
CSV_PATH = os.path.join(HERE, "arb_opportunities.csv")
OUT_PATH = os.path.join(HERE, "dashboard.html")


def load_rows():
    if not os.path.exists(CSV_PATH):
        return []
    rows = []
    with open(CSV_PATH, newline="") as f:
        for r in csv.DictReader(f):
            try:
                # HEARTBEAT rows record the best top-of-book edge on a scan that
                # booked nothing. They have an empty depth field and are kept
                # separate so they never count as fills or pollute slippage.
                is_hb = str(r.get("cycle", "")).strip().upper() == "HEARTBEAT"
                rows.append({
                    "t": r["timestamp"],
                    "cycle": r["cycle"],
                    "top": float(r["top_of_book_net_pct"]),
                    "depth": None if is_hb else float(r["depth_net_pct"]),
                    "pnl": 0.0 if is_hb else float(r["paper_pnl"]),
                    "filled": False if is_hb else
                              (str(r["filled"]).strip().lower() == "true"),
                    "bal": float(r["virtual_balance"]),
                    "hb": is_hb,
                })
            except (KeyError, ValueError):
                continue
    return rows


def summarize(rows):
    if not rows:
        return {"count": 0}
    # Real depth-confirmed opportunity rows vs. heartbeat trend rows.
    opps = [r for r in rows if not r["hb"]]
    hbs = [r for r in rows if r["hb"]]
    fills = [r for r in opps if r["filled"] and r["depth"] >= 0]
    slip = [r["top"] - r["depth"] for r in opps]
    # frequency + avg depth edge per cycle (opportunities only)
    by_cycle = {}
    for r in opps:
        c = by_cycle.setdefault(r["cycle"], {"n": 0, "depth_sum": 0.0, "best": -1e9})
        c["n"] += 1
        c["depth_sum"] += r["depth"]
        c["best"] = max(c["best"], r["depth"])
    top_cycles = sorted(
        ({"cycle": k, "n": v["n"], "avg_depth": v["depth_sum"] / v["n"], "best": v["best"]}
         for k, v in by_cycle.items()),
        key=lambda x: x["n"], reverse=True,
    )[:12]
    # Best top-of-book edge ever seen (across opportunities + heartbeats).
    best_top = max((r["top"] for r in rows), default=None)
    return {
        "count": len(opps),
        "heartbeats": len(hbs),
        "fills": len(fills),
        "balance": rows[-1]["bal"],
        "best_depth": max((r["depth"] for r in opps), default=None),
        "best_top": best_top,
        "avg_slip": (sum(slip) / len(slip)) if slip else None,
        "first": rows[0]["t"],
        "last": rows[-1]["t"],
        "top_cycles": top_cycles,
    }


def render(rows, s):
    generated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    opps = [r for r in rows if not r["hb"]]
    bal_series = [{"x": r["t"], "y": round(r["bal"], 4)} for r in rows]
    top_series = [{"x": r["t"], "y": round(r["top"], 4)} for r in rows]
    scatter = [{"x": round(r["top"], 4), "y": round(r["depth"], 4)} for r in opps]
    recent = opps[-25:][::-1]

    def card(label, value, sub=""):
        return (f'<div class="card"><div class="lbl">{label}</div>'
                f'<div class="val">{value}</div><div class="sub">{sub}</div></div>')

    def pct(v, suffix="%"):
        return "—" if v is None else f"{v:+.3f}{suffix}"

    if not rows:
        cards = card("Status", "No data yet",
                     "Start the bot — opportunities will appear here.")
        rows_html = ('<tr><td colspan="6" class="muted">'
                     'arb_opportunities.csv is empty so far.</td></tr>')
        top_html = '<tr><td colspan="4" class="muted">—</td></tr>'
    else:
        cards = "".join([
            card("Opportunities logged", f"{s['count']:,}",
                 f"{s['first']} → {s['last']}"),
            card("Paper fills", f"{s['fills']:,}", "profitable & fully filled"),
            card("Virtual balance", f"{s['balance']:+.2f}", "cumulative paper P&L"),
            card("Best depth edge", pct(s['best_depth']), "after fees + slippage"),
            card("Best top-of-book", pct(s['best_top']),
                 "best apparent edge (pre-slippage)"),
            card("Avg slippage", pct(s['avg_slip']), "top-of-book minus depth"),
            card("Heartbeats", f"{s['heartbeats']:,}", "trend samples, no fill"),
        ])
        rows_html = "".join(
            f'<tr><td>{r["t"]}</td><td>{r["cycle"]}</td>'
            f'<td>{r["top"]:+.3f}</td><td>{r["depth"]:+.3f}</td>'
            f'<td class="{"pos" if r["pnl"]>=0 else "neg"}">{r["pnl"]:+.2f}</td>'
            f'<td>{"✓" if r["filled"] else "✗"}</td></tr>'
            for r in recent
        ) or ('<tr><td colspan="6" class="muted">No depth-confirmed loops yet — '
              'heartbeats only. Best apparent edge is shown above.</td></tr>')
        top_html = "".join(
            f'<tr><td>{c["cycle"]}</td><td>{c["n"]}</td>'
            f'<td>{c["avg_depth"]:+.3f}</td><td>{c["best"]:+.3f}</td></tr>'
            for c in s["top_cycles"]
        ) or '<tr><td colspan="4" class="muted">—</td></tr>'

    return f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Triangular Arb — Paper Trading Dashboard</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.1/chart.umd.min.js"></script>
<style>
  :root {{ color-scheme: dark; }}
  body {{ font-family: -apple-system, system-ui, sans-serif; margin: 0;
         background:#0e1116; color:#e6e9ef; }}
  header {{ padding:20px 28px; border-bottom:1px solid #222834; }}
  h1 {{ font-size:18px; margin:0; }}
  .gen {{ color:#7c8698; font-size:12px; margin-top:4px; }}
  .wrap {{ padding:22px 28px; max-width:1100px; margin:0 auto; }}
  .cards {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(170px,1fr));
            gap:14px; margin-bottom:26px; }}
  .card {{ background:#161b24; border:1px solid #222834; border-radius:12px;
           padding:16px; }}
  .lbl {{ color:#7c8698; font-size:12px; text-transform:uppercase;
          letter-spacing:.04em; }}
  .val {{ font-size:24px; font-weight:650; margin-top:6px; }}
  .sub {{ color:#7c8698; font-size:11px; margin-top:4px; }}
  .panel {{ background:#161b24; border:1px solid #222834; border-radius:12px;
            padding:18px; margin-bottom:22px; }}
  .panel h2 {{ font-size:14px; margin:0 0 14px; color:#c7cedb; }}
  table {{ width:100%; border-collapse:collapse; font-size:13px; }}
  th, td {{ text-align:left; padding:7px 10px; border-bottom:1px solid #1c222d; }}
  th {{ color:#7c8698; font-weight:550; }}
  .pos {{ color:#46d39a; }} .neg {{ color:#ef6f7b; }}
  .muted {{ color:#7c8698; text-align:center; padding:18px; }}
  .note {{ color:#7c8698; font-size:12px; line-height:1.5; }}
  canvas {{ max-height:300px; }}
</style></head>
<body>
<header>
  <h1>Triangular Arbitrage — Paper Trading Dashboard</h1>
  <div class="gen">Generated {generated} · source: arb_opportunities.csv · paper only, no real orders</div>
</header>
<div class="wrap">
  <div class="cards">{cards}</div>

  <div class="panel"><h2>Virtual balance over time (cumulative paper P&L)</h2>
    <canvas id="bal"></canvas></div>

  <div class="panel"><h2>Best top-of-book edge over time (%)</h2>
    <p class="note">How close the best loop got each sample, before slippage.
       At Kraken's ~1.2% fee floor this normally sits well below zero — that is
       the honest picture of why nothing books.</p>
    <canvas id="tops"></canvas></div>

  <div class="panel"><h2>Top-of-book edge vs depth-confirmed edge (%)</h2>
    <p class="note">Points far below the diagonal = slippage eating the edge.
       The further a dot sits under the line y = x, the more the mirage shrank
       once real size hit the book.</p>
    <canvas id="scatter"></canvas></div>

  <div class="panel"><h2>Most frequent loops</h2>
    <table><thead><tr><th>Cycle</th><th>Times seen</th>
      <th>Avg depth edge %</th><th>Best %</th></tr></thead>
      <tbody>{top_html}</tbody></table></div>

  <div class="panel"><h2>Recent opportunities (latest 25)</h2>
    <table><thead><tr><th>Time (UTC)</th><th>Cycle</th><th>Top %</th>
      <th>Depth %</th><th>Paper P&L</th><th>Filled</th></tr></thead>
      <tbody>{rows_html}</tbody></table></div>

  <p class="note">Reminder: at Kraken's 0.40%/leg taker fee a loop must clear
     ~1.2% in fees plus spread plus slippage before it books a positive paper
     trade. A flat-or-empty balance is a real, useful result.</p>
</div>
<script>
const BAL = {json.dumps(bal_series)};
const TOPS = {json.dumps(top_series)};
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
if (TOPS.length) new Chart(document.getElementById('tops'), {{
  type:'line',
  data:{{ datasets:[{{ label:'Best top-of-book edge %', data:TOPS, parsing:false,
    borderColor:'#78aaff', backgroundColor:'rgba(120,170,255,.12)',
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


def main():
    rows = load_rows()
    s = summarize(rows)
    html = render(rows, s)
    with open(OUT_PATH, "w") as f:
        f.write(html)
    if rows:
        bd = "—" if s["best_depth"] is None else f"{s['best_depth']:+.3f}%"
        bt = "—" if s["best_top"] is None else f"{s['best_top']:+.3f}%"
        print(f"Wrote {OUT_PATH} — {s['count']} opportunities, "
              f"{s['heartbeats']} heartbeats, {s['fills']} paper fills, "
              f"balance {s['balance']:+.2f}, best depth {bd}, best top {bt}.")
    else:
        print(f"Wrote {OUT_PATH} — no data yet (start the bot to populate it).")


if __name__ == "__main__":
    main()
