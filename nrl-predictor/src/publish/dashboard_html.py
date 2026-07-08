"""Build the round dashboard HTML (Build Spec §8) — game tabs, win-probability
bars (model vs market), SGM multi suggestions + tryscorer props per game.

Self-contained page (all CSS/JS inline, data baked in at build time) written to
outputs/dashboard.html and served at "/" by service/main.py on Railway — the
pnl-dashboard pattern. Redeploy = refresh.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"

VALIDATION = ("Match model: walk-forward 2015–2025 Brier 0.2188 (naive 0.2456, "
              "closing line 0.2075). Tryscorer model: 2022–25 Brier 0.1401 vs "
              "positional base 0.1408 — gates passed.")


def _payload() -> dict:
    preds = pd.read_csv(OUT / "round_predictions.csv")
    market = pd.read_csv(OUT / "round_market.csv") if (OUT / "round_market.csv").exists() else pd.DataFrame()
    props = pd.read_csv(OUT / "round_props.csv") if (OUT / "round_props.csv").exists() else pd.DataFrame()
    sgm = pd.read_csv(OUT / "round_sgm.csv") if (OUT / "round_sgm.csv").exists() else pd.DataFrame()
    tries = pd.read_csv(OUT / "round_tries.csv") if (OUT / "round_tries.csv").exists() else pd.DataFrame()

    games = []
    for r in preds.itertuples(index=False):
        key = f"{r.home} v {r.away}"
        mk = market[(market["home"] == r.home) & (market["away"] == r.away)] if len(market) else pd.DataFrame()
        mk = mk.iloc[0].to_dict() if len(mk) else {}
        g_props = props[props["match"] == key] if len(props) else pd.DataFrame()
        g_sgm = sgm[sgm["match"] == key] if len(sgm) else pd.DataFrame()
        g_tries = tries[tries["match"] == key] if len(tries) else pd.DataFrame()
        g_tries = g_tries.iloc[0].to_dict() if len(g_tries) else None
        games.append({
            "home": r.home, "away": r.away,
            "kickoff": pd.Timestamp(r.date).strftime("%a %d %b, %H:%M"),
            "venue": r.venue,
            "p": {"elo": r.p_home_elo, "poisson": r.p_home_poisson,
                  "gbm": r.p_home_gbm, "blend": r.p_home_blend,
                  "market": mk.get("market_p_home")},
            "margin": r.exp_margin_home, "total": r.exp_total_points,
            "value": ({"side": mk["value_side"], "ev": mk["value_ev_pct"],
                       "best_home": mk["best_odds_home"], "best_away": mk["best_odds_away"]}
                      if mk and mk.get("value_ev_pct") is not None and mk["value_ev_pct"] > 0 else None),
            "tries": g_tries,
            "props": (g_props.sort_values("p_ats", ascending=False)
                      .head(6)[["player", "position", "team", "exp_tries", "p_ats",
                                "fair_price", "p_2plus", "fair_2plus"]]
                      .to_dict(orient="records")),
            "multis": (g_sgm.sort_values("correlation_lift", ascending=False)
                       [["combo", "p_joint", "fair_price", "p_independent", "correlation_lift"]]
                       .to_dict(orient="records")),
        })
    return {
        "round": preds["round"].iloc[0],
        "generated": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "validation": VALIDATION,
        "games": games,
    }


BODY_TEMPLATE = """
<title>__TITLE__</title>
<style>
  :root {
    --surface: #fcfcfb; --plane: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e;
    --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
    --model: #2a78d6; --market: #1baf7a; --track: #eceae4;
    --chip-bg: #e8f0fb; --good: #006300;
  }
  @media (prefers-color-scheme: dark) { :root {
    --surface: #1a1a19; --plane: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --model: #3987e5; --market: #199e70; --track: #262624;
    --chip-bg: #14273f; --good: #0ca30c;
  } }
  :root[data-theme="dark"] {
    --surface: #1a1a19; --plane: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7;
    --muted: #898781; --grid: #2c2c2a; --border: rgba(255,255,255,0.10);
    --model: #3987e5; --market: #199e70; --track: #262624;
    --chip-bg: #14273f; --good: #0ca30c;
  }
  :root[data-theme="light"] {
    --surface: #fcfcfb; --plane: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e;
    --muted: #898781; --grid: #e1e0d9; --border: rgba(11,11,11,0.10);
    --model: #2a78d6; --market: #1baf7a; --track: #eceae4;
    --chip-bg: #e8f0fb; --good: #006300;
  }
  * { box-sizing: border-box; margin: 0; }
  body { background: var(--plane); color: var(--ink);
         font: 15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif;
         padding: 20px 16px 40px; }
  .wrap { max-width: 880px; margin: 0 auto; }
  header h1 { font-size: 22px; font-weight: 700; }
  header .sub { color: var(--ink-2); font-size: 13px; margin-top: 2px; }
  .tabs { display: flex; gap: 6px; overflow-x: auto; margin: 18px 0 12px;
          padding-bottom: 4px; }
  .tab { border: 1px solid var(--border); background: var(--surface);
         color: var(--ink-2); border-radius: 9px; padding: 8px 12px;
         font: 600 13px/1 system-ui, sans-serif; cursor: pointer;
         white-space: nowrap; }
  .tab[aria-selected="true"] { color: var(--ink); border-color: var(--model);
         box-shadow: inset 0 -2px 0 var(--model); }
  .card { background: var(--surface); border: 1px solid var(--border);
          border-radius: 12px; padding: 18px; }
  .matchhead { display: flex; justify-content: space-between; gap: 12px;
               flex-wrap: wrap; align-items: baseline; }
  .matchhead h2 { font-size: 17px; }
  .matchhead .when { color: var(--muted); font-size: 12.5px; }
  .tiles { display: flex; gap: 10px; flex-wrap: wrap; margin: 14px 0 4px; }
  .tile { flex: 1 1 130px; border: 1px solid var(--border); border-radius: 10px;
          padding: 10px 12px; }
  .tile .k { color: var(--muted); font-size: 11.5px; text-transform: uppercase;
             letter-spacing: .04em; }
  .tile .v { font-size: 19px; font-weight: 700; margin-top: 2px; }
  .tile .v small { font-size: 12px; font-weight: 500; color: var(--ink-2); }
  .valuechip { display: inline-block; background: var(--chip-bg);
               color: var(--ink); border-radius: 999px; padding: 3px 10px;
               font-size: 12px; font-weight: 600; margin-top: 6px; }
  h3 { font-size: 13px; text-transform: uppercase; letter-spacing: .05em;
       color: var(--ink-2); margin: 18px 0 8px; }
  .bar-row { margin: 10px 0 14px; }
  .bar-row .lbl { display: flex; justify-content: space-between;
                  font-size: 12.5px; color: var(--ink-2); margin-bottom: 4px; }
  .bar-row .lbl b { color: var(--ink); }
  .track { height: 22px; background: var(--track); border-radius: 4px;
           position: relative; overflow: hidden; }
  .fill { height: 100%; border-radius: 4px 0 0 4px; }
  .fill.model { background: var(--model); }
  .fill.market { background: var(--market); }
  .track .pct { position: absolute; top: 0; line-height: 22px; font-size: 12px;
                font-weight: 700; font-variant-numeric: tabular-nums; }
  .pct.in { color: #fff; left: 8px; } .pct.out { color: var(--ink); left: 8px; }
  .pct.right { right: 8px; left: auto; color: var(--ink-2); font-weight: 600; }
  table { border-collapse: collapse; width: 100%; font-size: 13px; }
  th { text-align: left; color: var(--muted); font-weight: 600; font-size: 11.5px;
       text-transform: uppercase; letter-spacing: .04em; padding: 6px 8px;
       border-bottom: 1px solid var(--grid); }
  td { padding: 6px 8px; border-bottom: 1px solid var(--grid);
       font-variant-numeric: tabular-nums; }
  tr:last-child td { border-bottom: none; }
  .multi { border: 1px solid var(--border); border-radius: 10px; padding: 12px;
           margin-bottom: 8px; }
  .multi .legs { font-weight: 600; font-size: 14px; }
  .multi .nums { display: flex; gap: 14px; flex-wrap: wrap; margin-top: 6px;
                 color: var(--ink-2); font-size: 12.5px;
                 font-variant-numeric: tabular-nums; }
  .multi .nums b { color: var(--ink); }
  .lift { background: var(--chip-bg); border-radius: 999px; padding: 2px 9px;
          font-weight: 700; color: var(--ink); }
  footer { color: var(--muted); font-size: 12px; margin-top: 20px; }
  footer .warn { margin-top: 4px; }
</style>
<div class="wrap">
  <header>
    <h1>🏉 NRL Predictor — <span id="round"></span></h1>
    <div class="sub">Paper-track model output — not betting advice. Generated <span id="gen"></span>.</div>
  </header>
  <div class="tabs" role="tablist" id="tabs"></div>
  <div class="card" id="panel" role="tabpanel"></div>
  <footer>
    <div id="validation"></div>
    <div class="warn">Fair prices are model outputs with uncertainty. Bookmaker SGM engines stack 20–40% margin — a fair price below the quote is not an instruction to bet. Paper only.</div>
  </footer>
</div>
<script>
const DATA = __DATA__;
const nick = n => n.split(" ").pop();
const pc = x => (100 * x).toFixed(1) + "%";
const tabs = document.getElementById("tabs");
const panel = document.getElementById("panel");
document.getElementById("round").textContent = DATA.round;
document.getElementById("gen").textContent = DATA.generated;
document.getElementById("validation").textContent = DATA.validation;

function bar(label, p, cls, homeName, awayName) {
  if (p == null || isNaN(p)) return "";
  const w = Math.max(2, Math.min(98, 100 * p));
  const inFill = w > 18;
  return `<div class="bar-row">
    <div class="lbl"><span><b>${label}</b> — ${homeName} ${pc(p)}</span>
    <span>${awayName} ${pc(1 - p)}</span></div>
    <div class="track"><div class="fill ${cls}" style="width:${w}%"></div>
      <span class="pct ${inFill ? "in" : "out"}">${pc(p)}</span>
      <span class="pct right">${pc(1 - p)}</span></div></div>`;
}

function render(i) {
  const g = DATA.games[i];
  [...tabs.children].forEach((t, j) => t.setAttribute("aria-selected", j === i));
  const p = g.p;
  const marginSide = g.margin >= 0 ? nick(g.home) : nick(g.away);
  let h = `<div class="matchhead"><h2>${g.home} v ${g.away}</h2>
    <span class="when">${g.kickoff} · ${g.venue}</span></div>
    <div class="tiles">
      <div class="tile"><div class="k">Model call</div>
        <div class="v">${p.blend >= 0.5 ? nick(g.home) : nick(g.away)}
          <small>${pc(Math.max(p.blend, 1 - p.blend))} blend</small></div></div>
      <div class="tile"><div class="k">Expected margin</div>
        <div class="v">${marginSide} <small>by</small> ${Math.abs(g.margin).toFixed(1)}</div></div>
      <div class="tile"><div class="k">Expected total</div>
        <div class="v">${g.total.toFixed(0)} <small>pts</small></div></div>
      ${g.tries ? `<div class="tile"><div class="k">Expected tries</div>
        <div class="v">${g.tries.exp_tries_home.toFixed(1)}<small> ${nick(g.home)}</small>
        &nbsp;${g.tries.exp_tries_away.toFixed(1)}<small> ${nick(g.away)}</small></div>
        <div class="k" style="margin-top:4px">over ${g.tries.tries_line} tries: ${(100*g.tries.p_over_line).toFixed(0)}%</div></div>` : ""}
    </div>`;
  if (g.value) h += `<span class="valuechip">Model value (paper): ${g.value.side} ` +
    `${g.value.ev > 0 ? "+" : ""}${g.value.ev.toFixed(1)}% EV at best price</span>`;
  h += `<h3>Win probability — home side</h3>`;
  h += bar("Model (blend)", p.blend, "model", nick(g.home), nick(g.away));
  h += bar("Market (4-book de-vig)", p.market, "market", nick(g.home), nick(g.away));
  h += `<table><thead><tr><th>Elo</th><th>Poisson</th><th>GBM</th><th>Blend</th><th>Market</th></tr></thead>
    <tbody><tr>${["elo", "poisson", "gbm", "blend", "market"].map(k =>
      `<td>${p[k] == null || isNaN(p[k]) ? "—" : pc(p[k])}</td>`).join("")}</tr></tbody></table>`;
  if (g.multis.length) {
    h += `<h3>Multi suggestions (same-game, model fair prices)</h3>`;
    for (const m of g.multis) {
      h += `<div class="multi"><div class="legs">${m.combo.replaceAll(" × ", " &nbsp;×&nbsp; ")}</div>
        <div class="nums"><span>joint <b>${pc(m.p_joint)}</b></span>
        <span>fair <b>$${m.fair_price.toFixed(2)}</b></span>
        <span>priced independently <b>$${(1 / m.p_independent).toFixed(2)}</b></span>
        <span class="lift">×${m.correlation_lift.toFixed(2)} correlation</span></div></div>`;
    }
  }
  if (g.props.length) {
    h += `<h3>Tryscorers — how many tries the model expects</h3>
      <table><thead><tr><th>Player</th><th>Pos</th><th>Team</th><th>E(tries)</th>
      <th>P(1+)</th><th>Fair 1+</th><th>P(2+)</th><th>Fair 2+</th></tr></thead><tbody>`;
    for (const t of g.props)
      h += `<tr><td>${t.player}</td><td>${t.position}</td><td>${nick(t.team)}</td>
        <td>${t.exp_tries.toFixed(2)}</td><td>${pc(t.p_ats)}</td><td>$${t.fair_price.toFixed(2)}</td>
        <td>${pc(t.p_2plus)}</td><td>${t.fair_2plus ? "$" + t.fair_2plus.toFixed(1) : "—"}</td></tr>`;
    h += `</tbody></table>`;
  }
  panel.innerHTML = h;
}

DATA.games.forEach((g, i) => {
  const b = document.createElement("button");
  b.className = "tab"; b.role = "tab";
  b.textContent = `${nick(g.home)} v ${nick(g.away)}`;
  b.onclick = () => render(i);
  tabs.appendChild(b);
});
render(0);
</script>
"""


def build() -> Path:
    data = _payload()
    title = f"NRL Predictor — {data['round']}"
    body = BODY_TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__TITLE__", title)
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"</head><body>{body}</body></html>")
    OUT.mkdir(exist_ok=True)
    full = OUT / "dashboard.html"
    full.write_text(page)
    (OUT / "dashboard_body.html").write_text(body)  # artifact-friendly variant
    return full


if __name__ == "__main__":
    print(f"-> {build()}")
