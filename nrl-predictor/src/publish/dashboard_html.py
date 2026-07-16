"""Build the season dashboard HTML (Build Spec §8).

Round selector over every remaining round → game tabs → per-game view (win
probability model vs market, expected margin/total/tries, SGM multis, tryscorers)
plus a Match Intel panel (team lists, weather, flags) and a Track Record tab.

Data source: outputs/season_predictions.json (all remaining rounds; current round
carries market/SGM/signals merged in). Self-contained page (inline CSS/JS, data
baked at build) served at "/" by service/main.py — redeploy = refresh.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs"

VALIDATION = ("Match model: walk-forward 2015–2025 Brier 0.2179 (naive 0.2456, "
              "closing line 0.2075). Tryscorer model: 2022–25 Brier 0.1401 vs "
              "positional base 0.1408 — gates passed.")


def _payload() -> dict:
    season = json.loads((OUT / "season_predictions.json").read_text())
    sig = json.loads((OUT / "round_signals_applied.json").read_text()) if (OUT / "round_signals_applied.json").exists() else {"games": []}
    sig_by = {(g["home"], g["away"]): g for g in sig.get("games", [])}
    track = json.loads((OUT / "track_record.json").read_text()) if (OUT / "track_record.json").exists() else None

    for rnd in season["rounds"]:
        for g in rnd["games"]:
            s = sig_by.get((g["home"], g["away"]))
            if s:  # merge the richer signal overlay (flags, confidence) for the current round
                g["flags"] = s.get("flags", [])
                g["info_confidence"] = s.get("info_confidence")
                g["adjusted_total"] = s.get("adjusted_total")
                g["baseline_total"] = s.get("baseline_total")
    season["track"] = track
    season["validation"] = VALIDATION
    season["generated"] = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    return season


BODY_TEMPLATE = r"""
<title>__TITLE__</title>
<style>
  :root {
    --surface:#fcfcfb; --plane:#f9f9f7; --ink:#0b0b0b; --ink-2:#52514e;
    --muted:#898781; --grid:#e1e0d9; --border:rgba(11,11,11,0.10);
    --model:#2a78d6; --market:#1baf7a; --track:#eceae4; --chip-bg:#e8f0fb; --good:#006300;
  }
  @media (prefers-color-scheme: dark){:root{
    --surface:#1a1a19; --plane:#0d0d0d; --ink:#fff; --ink-2:#c3c2b7; --muted:#898781;
    --grid:#2c2c2a; --border:rgba(255,255,255,0.10); --model:#3987e5; --market:#199e70;
    --track:#262624; --chip-bg:#14273f; --good:#0ca30c; }}
  :root[data-theme="dark"]{--surface:#1a1a19;--plane:#0d0d0d;--ink:#fff;--ink-2:#c3c2b7;
    --muted:#898781;--grid:#2c2c2a;--border:rgba(255,255,255,0.10);--model:#3987e5;
    --market:#199e70;--track:#262624;--chip-bg:#14273f;--good:#0ca30c;}
  :root[data-theme="light"]{--surface:#fcfcfb;--plane:#f9f9f7;--ink:#0b0b0b;--ink-2:#52514e;
    --muted:#898781;--grid:#e1e0d9;--border:rgba(11,11,11,0.10);--model:#2a78d6;
    --market:#1baf7a;--track:#eceae4;--chip-bg:#e8f0fb;--good:#006300;}
  *{box-sizing:border-box;margin:0;}
  body{background:var(--plane);color:var(--ink);
       font:15px/1.45 system-ui,-apple-system,"Segoe UI",sans-serif;padding:20px 16px 40px;}
  .wrap{max-width:880px;margin:0 auto;}
  header h1{font-size:22px;font-weight:700;}
  header .sub{color:var(--ink-2);font-size:13px;margin-top:2px;}
  .nav{display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin:16px 0 10px;}
  select{background:var(--surface);color:var(--ink);border:1px solid var(--border);
         border-radius:9px;padding:8px 12px;font:600 14px system-ui,sans-serif;cursor:pointer;}
  .trackbtn{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);
       border-radius:9px;padding:8px 12px;font:600 13px system-ui;cursor:pointer;}
  .trackbtn.on{color:var(--ink);border-color:var(--model);box-shadow:inset 0 -2px 0 var(--model);}
  .tabs{display:flex;gap:6px;overflow-x:auto;margin:6px 0 12px;padding-bottom:4px;}
  .tab{border:1px solid var(--border);background:var(--surface);color:var(--ink-2);
       border-radius:9px;padding:8px 12px;font:600 13px/1 system-ui;cursor:pointer;white-space:nowrap;}
  .tab[aria-selected="true"]{color:var(--ink);border-color:var(--model);box-shadow:inset 0 -2px 0 var(--model);}
  .card{background:var(--surface);border:1px solid var(--border);border-radius:12px;padding:18px;}
  .banner{background:var(--chip-bg);border-radius:9px;padding:9px 12px;font-size:12.5px;
          color:var(--ink-2);margin-bottom:12px;}
  .matchhead{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;align-items:baseline;}
  .matchhead h2{font-size:17px;} .matchhead .when{color:var(--muted);font-size:12.5px;}
  .tiles{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 4px;}
  .tile{flex:1 1 130px;border:1px solid var(--border);border-radius:10px;padding:10px 12px;}
  .tile .k{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;}
  .tile .v{font-size:19px;font-weight:700;margin-top:2px;}
  .tile .v small{font-size:12px;font-weight:500;color:var(--ink-2);}
  .valuechip{display:inline-block;background:var(--chip-bg);color:var(--ink);border-radius:999px;
             padding:3px 10px;font-size:12px;font-weight:600;margin-top:6px;}
  h3{font-size:13px;text-transform:uppercase;letter-spacing:.05em;color:var(--ink-2);margin:18px 0 8px;}
  .bar-row{margin:10px 0 14px;}
  .bar-row .lbl{display:flex;justify-content:space-between;font-size:12.5px;color:var(--ink-2);margin-bottom:4px;}
  .bar-row .lbl b{color:var(--ink);}
  .trk{height:22px;background:var(--track);border-radius:4px;position:relative;overflow:hidden;}
  .fill{height:100%;border-radius:4px 0 0 4px;} .fill.model{background:var(--model);} .fill.market{background:var(--market);}
  .trk .pct{position:absolute;top:0;line-height:22px;font-size:12px;font-weight:700;font-variant-numeric:tabular-nums;}
  .pct.in{color:#fff;left:8px;} .pct.out{color:var(--ink);left:8px;} .pct.right{right:8px;left:auto;color:var(--ink-2);font-weight:600;}
  table{border-collapse:collapse;width:100%;font-size:13px;}
  th{text-align:left;color:var(--muted);font-weight:600;font-size:11.5px;text-transform:uppercase;
     letter-spacing:.04em;padding:6px 8px;border-bottom:1px solid var(--grid);}
  td{padding:6px 8px;border-bottom:1px solid var(--grid);font-variant-numeric:tabular-nums;}
  tr:last-child td{border-bottom:none;}
  tr.teamsplit td{padding:0;height:6px;border-bottom:2px solid var(--border);background:var(--chip-bg);}
  .multi{border:1px solid var(--border);border-radius:10px;padding:12px;margin-bottom:8px;}
  .multi .legs{font-weight:600;font-size:14px;}
  .multi .nums{display:flex;gap:14px;flex-wrap:wrap;margin-top:6px;color:var(--ink-2);font-size:12.5px;font-variant-numeric:tabular-nums;}
  .multi .nums b{color:var(--ink);} .lift{background:var(--chip-bg);border-radius:999px;padding:2px 9px;font-weight:700;color:var(--ink);}
  .tierchip{display:inline-block;color:#fff;border-radius:999px;padding:2px 9px;font-size:11.5px;
            font-weight:700;margin-right:8px;text-transform:capitalize;vertical-align:middle;}
  .parlay{border:1px solid var(--model);border-radius:12px;padding:14px;margin:6px 0 14px;background:var(--chip-bg);}
  .parlay .h{display:flex;justify-content:space-between;align-items:baseline;flex-wrap:wrap;gap:8px;}
  .parlay .h b{font-size:15px;} .parlay .price{font-size:20px;font-weight:700;}
  .parlay ul{margin:8px 0 0 18px;padding:0;font-size:13px;} .parlay li{padding:1px 0;}
  .conf{display:inline-block;border-radius:999px;padding:2px 9px;font-size:11.5px;font-weight:700;}
  .conf.high{background:rgba(12,163,12,.15);color:var(--good);}
  .conf.provisional{background:rgba(250,178,25,.18);color:#9a6a00;}
  .conf.low{background:var(--track);color:var(--ink-2);}
  @media (prefers-color-scheme:dark){.conf.provisional{color:#fab219;}}
  .flag{display:flex;gap:8px;align-items:baseline;margin:5px 0;font-size:12.5px;}
  .flag .dot{flex:none;width:7px;height:7px;border-radius:50%;margin-top:5px;}
  .flag.warn .dot{background:#ec835a;} .flag.info .dot{background:var(--model);}
  .wx{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;color:var(--ink-2);margin:6px 0;font-variant-numeric:tabular-nums;}
  .wx b{color:var(--ink);}
  .statgrid{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0;}
  .statgrid .s{flex:1 1 150px;border:1px solid var(--border);border-radius:10px;padding:12px;}
  .statgrid .s .n{font-size:22px;font-weight:700;} .statgrid .s .l{color:var(--muted);font-size:11.5px;text-transform:uppercase;letter-spacing:.04em;}
  footer{color:var(--muted);font-size:12px;margin-top:20px;} footer .warn{margin-top:4px;}
</style>
<div class="wrap">
  <header>
    <h1>🏉 NRL Predictor — <span id="season-round"></span></h1>
    <div class="sub">Paper-track model output — not betting advice. Generated <span id="gen"></span>.</div>
  </header>
  <div class="nav">
    <button class="trackbtn" id="valuebtn">💹 Value board</button>
    <button class="trackbtn" id="trackbtn">📊 Track record</button>
    <button class="trackbtn" id="formbtn">📈 Form guide</button>
    <label style="color:var(--ink-2);font-size:13px">Round</label>
    <select id="roundsel"></select>
    <span id="roundtag" style="color:var(--muted);font-size:12.5px"></span>
  </div>
  <div class="tabs" id="tabs"></div>
  <div class="card" id="panel"></div>
  <footer>
    <div id="validation"></div>
    <div class="warn">Fair prices are model outputs with uncertainty. Bookmaker SGM engines stack 20–40% margin — a fair price below the quote is not an instruction to bet. Paper only.</div>
  </footer>
</div>
<script>
const DATA = __DATA__;
const nick = n => n.split(" ").pop();
const pc = x => (x==null||isNaN(x)) ? "—" : (100*x).toFixed(1)+"%";
const sel = document.getElementById("roundsel");
const tabs = document.getElementById("tabs");
const panel = document.getElementById("panel");
const roundtag = document.getElementById("roundtag");
document.getElementById("season-round").textContent = DATA.current_round_label;
document.getElementById("gen").textContent = DATA.generated;
document.getElementById("validation").textContent = DATA.validation;
let curRound = DATA.rounds.findIndex(r => r.round_no === DATA.current_round);
if (curRound < 0) curRound = 0;

DATA.rounds.forEach((r,i)=>{
  const o=document.createElement("option"); o.value=i;
  o.textContent = r.round + (r.actionable?"  • live":"");
  sel.appendChild(o);
});
sel.value = curRound;
sel.onchange = ()=>{ selectRound(+sel.value); };
document.getElementById("trackbtn").onclick = renderTrack;
document.getElementById("formbtn").onclick = renderForm;
document.getElementById("valuebtn").onclick = renderValue;

function bar(label,p,cls,h,a){
  if(p==null||isNaN(p)) return "";
  const w=Math.max(2,Math.min(98,100*p)), inFill=w>18;
  return `<div class="bar-row"><div class="lbl"><span><b>${label}</b> — ${h} ${pc(p)}</span>
    <span>${a} ${pc(1-p)}</span></div><div class="trk"><div class="fill ${cls}" style="width:${w}%"></div>
    <span class="pct ${inFill?"in":"out"}">${pc(p)}</span><span class="pct right">${pc(1-p)}</span></div></div>`;
}

function intel(g){
  if(g.info_confidence===undefined && !g.weather && !g.xstats && !g.avail) return "";
  const conf=g.info_confidence||"low";
  const lbl={high:"Team lists confirmed",provisional:"Lists provisional",low:"Lists not out — last-game squad"}[conf];
  let h=`<h3>Match intel — on-the-day signals</h3><span class="conf ${conf}">${lbl}</span>`;
  const w=g.weather;
  if(w){ h+=`<div class="wx"><span>rain <b>${w.precip_prob??"?"}%</b></span>
    <span><b>${(w.precip_mm??0).toFixed(1)}</b> mm</span><span>wind <b>${Math.round(w.wind_kmh??0)}</b> km/h</span>
    <span>temp <b>${Math.round(w.temp_c??0)}</b>°C</span>`;
    if(g.weather_try_mult&&g.weather_try_mult<0.999)
      h+=`<span>tries <b>×${g.weather_try_mult}</b></span>`;
    h+=`</div>`; }
  if(g.avail && Math.abs(g.avail.win_shift)>=0.005){
    const s=g.avail.win_shift, who=s>=0?nick(g.home):nick(g.away);
    h+=`<div class="flag info"><span class="dot"></span><span>Lineup strength (named 17, ridge-APM):
      favours <b>${who}</b> — win prob adjusted ${s>=0?"+":""}${(100*s).toFixed(1)}% vs a neutral lineup.</span></div>`;
  }
  if(g.xstats){
    const fmt=(m)=>`${m>=1?"+":""}${(100*(m-1)).toFixed(0)}%`;
    h+=`<div class="flag info"><span class="dot"></span><span>Tryscorer prices sharpened by opponent edge-defence (xStats):
      <b>${nick(g.home)}</b> tries ${fmt(g.xstats.home)}, <b>${nick(g.away)}</b> tries ${fmt(g.xstats.away)} — flows into every ATS &amp; SGM leg.</span></div>`;
  }
  if(!(g.flags||[]).length && conf==="high")
    h+=`<div class="flag info"><span class="dot"></span><span>No late changes or weather concerns flagged.</span></div>`;
  for(const f of (g.flags||[]))
    h+=`<div class="flag ${f.severity}"><span class="dot"></span><span>${f.text}</span></div>`;
  return h;
}

function parlaysHTML(){
  if(!(DATA.parlays||[]).length) return "";
  let h=`<h3>🎟 Parlay of the round (across games)</h3>`;
  for(const p of DATA.parlays){
    h+=`<div class="parlay"><div class="h"><b>${p.name}</b>
      <span class="price">$${(+p.fair_price).toFixed(2)}</span></div>
      <div style="color:var(--ink-2);font-size:12.5px">model joint ${pc(p.p_joint)} · legs are separate games (independent)</div>
      <ul>${p.legs.map(l=>`<li>${l}</li>`).join("")}</ul></div>`;
  }
  return h;
}

function renderGame(ri,gi){
  const r=DATA.rounds[ri], g=r.games[gi];
  [...tabs.children].forEach((t,j)=>t.setAttribute("aria-selected",j===gi));
  document.getElementById("trackbtn").classList.remove("on");
  document.getElementById("formbtn").classList.remove("on");
  document.getElementById("valuebtn").classList.remove("on");
  const p=g.p, marginSide=g.margin>=0?nick(g.home):nick(g.away);
  let h=`<div class="matchhead"><h2>${g.home} v ${g.away}</h2>
    <span class="when">${g.kickoff} · ${g.venue}</span></div>`;
  if(!r.actionable) h+=`<div class="banner">Projection for ${r.round} — win/margin/total
    from current model ratings, refreshed every run as results land. Team lists,
    live odds and same-game multis appear here in the days before kickoff.</div>`;
  if(r.actionable && gi===0) h+=parlaysHTML();
  h+=`<div class="tiles">
    <div class="tile"><div class="k">Model call</div><div class="v">${p.blend>=0.5?nick(g.home):nick(g.away)}
      <small>${pc(Math.max(p.blend,1-p.blend))} blend</small></div></div>
    <div class="tile"><div class="k">Expected margin</div><div class="v">${marginSide} <small>by</small> ${Math.abs(g.margin).toFixed(1)}</div>
      ${g.margin_ci?`<div class="k" style="margin-top:4px">80%: ${g.margin_ci[0]} to ${g.margin_ci[1]}</div>`:""}</div>
    <div class="tile"><div class="k">Expected total</div><div class="v">${g.total.toFixed(0)} <small>pts</small></div>
      ${g.total_ci?`<div class="k" style="margin-top:4px">80%: ${g.total_ci[0]}–${g.total_ci[1]}</div>`:""}</div>
    ${g.tries?`<div class="tile"><div class="k">Expected tries</div>
      <div class="v">${g.tries.home.toFixed(1)}<small> ${nick(g.home)}</small> ${g.tries.away.toFixed(1)}<small> ${nick(g.away)}</small></div></div>`:""}
  </div>`;
  if(g.value) h+=`<span class="valuechip">Model value (paper): ${g.value.side} ${g.value.ev>0?"+":""}${g.value.ev.toFixed(1)}% EV at best price</span>`;
  h+=intel(g);
  h+=`<h3>Win probability — home side</h3>`;
  h+=bar("Model (blend)",p.blend,"model",nick(g.home),nick(g.away));
  if(p.market!=null) h+=bar("Market (4-book de-vig)",p.market,"market",nick(g.home),nick(g.away));
  h+=`<table><thead><tr><th>Elo</th><th>Poisson</th><th>Blend</th>${p.market!=null?"<th>Market</th>":""}</tr></thead>
    <tbody><tr><td>${pc(p.elo)}</td><td>${pc(p.poisson)}</td><td>${pc(p.blend)}</td>${p.market!=null?`<td>${pc(p.market)}</td>`:""}</tr></tbody></table>`;
  if(g.bands){
    const b=g.bands;
    h+=`<h3>Winning margin — probability bands</h3>
      <table><thead><tr><th>Outcome</th><th>Model prob</th><th>Fair</th></tr></thead><tbody>
      ${[[nick(g.home)+" by 1–12",b.home_1_12],[nick(g.home)+" by 13+",b.home_13],
         [nick(g.away)+" by 1–12",b.away_1_12],[nick(g.away)+" by 13+",b.away_13]]
        .map(r=>`<tr><td>${r[0]}</td><td>${pc(r[1])}</td><td>${r[1]>0.01?"$"+(1/r[1]).toFixed(2):"—"}</td></tr>`).join("")}
      </tbody></table>`;
  }
  if((g.multis||[]).length){
    h+=`<h3>Same-game multis — value to longshot (model fair prices)</h3>`;
    for(const m of g.multis){
      const tier=m.tier||(m.fair_price<6?"value":(m.fair_price<15?"big":"longshot"));
      const tc={value:"var(--market)",big:"var(--model)",longshot:"#eb6834"}[tier];
      h+=`<div class="multi"><div class="legs">
        <span class="tierchip" style="background:${tc}">${tier} · $${(+m.fair_price).toFixed(2)}</span>
        ${m.combo.replaceAll(" × "," &nbsp;×&nbsp; ")}</div>
        <div class="nums"><span>joint <b>${pc(m.p_joint)}</b></span>
        <span>${m.n_legs||m.combo.split(" × ").length} legs</span>
        <span>priced independently <b>$${(1/(+m.p_independent)).toFixed(2)}</b></span>
        <span class="lift">×${(+m.correlation_lift).toFixed(2)} correlation</span></div></div>`;
    }
  }
  if((g.scorers||[]).length){
    h+=`<h3>Tryscorers — both teams — ${r.actionable?"model top picks":"provisional (team list not out)"}</h3>
      <table><thead><tr><th>Player</th><th>Pos</th><th>Team</th><th>E(tries)</th><th>P(1+)</th><th>Fair 1+</th><th>P(2+)</th><th>Fair 2+</th><th>vs opp</th></tr></thead><tbody>`;
    let prevTeam=null;
    for(const t of g.scorers){
      // a thin divider row between the two teams' blocks
      if(prevTeam!==null && t.team!==prevTeam)
        h+=`<tr class="teamsplit"><td colspan="9"></td></tr>`;
      prevTeam=t.team;
      const edge=["W","C","FB"].includes(t.position)?` title="edge attacker"`:"";
      h+=`<tr><td${edge}>${t.player}</td><td>${t.position}</td><td>${nick(t.team)}</td>
      <td>${(t.exp_tries??0).toFixed(2)}</td><td>${pc(t.p_ats)}</td><td>$${(t.fair??0).toFixed(2)}</td>
      <td>${pc(t.p_2plus)}</td><td>${t.fair_2plus?"$"+t.fair_2plus.toFixed(1):"—"}</td><td>${t.vs_opp||"—"}</td></tr>`;
    }
    h+=`</tbody></table>
      <p style="color:var(--muted);font-size:11.5px;margin-top:4px">Top 5 per side — both teams. vs opp = this player's try record against this specific opponent (career, before today) — shrunk into the rate above.</p>`;
  }
  panel.innerHTML=h;
}

function selectRound(ri){
  sel.value=ri;
  const r=DATA.rounds[ri];
  roundtag.textContent = r.actionable ? "live — full intel & odds" : "projection";
  tabs.innerHTML="";
  r.games.forEach((g,gi)=>{
    const b=document.createElement("button"); b.className="tab"; b.textContent=`${nick(g.home)} v ${nick(g.away)}`;
    b.onclick=()=>renderGame(ri,gi); tabs.appendChild(b);
  });
  renderGame(ri,0);
}

function renderTrack(){
  document.getElementById("trackbtn").classList.add("on");
  document.getElementById("formbtn").classList.remove("on");
  document.getElementById("valuebtn").classList.remove("on");
  [...tabs.children].forEach(t=>t.setAttribute("aria-selected",false));
  const t=DATA.track;
  if(!t||(!t.win.n&&!t.tryscorer.n)){
    panel.innerHTML=`<h2>Track record</h2><p style="color:var(--ink-2)">No graded rounds yet.
      After each round is played the pipeline settles every call — win, margin, total and top
      tryscorer — and the running accuracy shows here.</p>`; return;
  }
  const p1=x=>x==null?"—":(100*x).toFixed(1)+"%";
  let h=`<h2>Prediction track record</h2><p style="color:var(--ink-2);font-size:13px">Every model
    call graded against the result — separate from the paper betting ledger. Updated ${(t.updated||"").slice(0,16).replace("T"," ")} UTC.</p>
    <div class="statgrid">
      <div class="s"><div class="l">Win pick</div><div class="n">${p1(t.win.hit_rate)}</div><div class="l">${t.win.hits??0}/${t.win.n} · Brier ${t.win.brier??"—"}</div></div>
      <div class="s"><div class="l">Top tryscorer</div><div class="n">${p1(t.tryscorer.hit_rate)}</div><div class="l">${t.tryscorer.hits??0}/${t.tryscorer.n} · Brier ${t.tryscorer.brier??"—"}</div></div>
      <div class="s"><div class="l">Margin error</div><div class="n">${t.margin.mae??"—"}<small style="font-size:13px"> pts</small></div><div class="l">bias ${t.margin.bias>=0?"+":""}${t.margin.bias??"—"}</div></div>
      <div class="s"><div class="l">Total error</div><div class="n">${t.total.mae??"—"}<small style="font-size:13px"> pts</small></div><div class="l">bias ${t.total.bias>=0?"+":""}${t.total.bias??"—"}</div></div>
    </div>`;
  if((t.per_round||[]).length){
    h+=`<h3>By round</h3><table><thead><tr><th>Round</th><th>Win</th><th>Win Brier</th><th>Tryscorer</th><th>Total MAE</th></tr></thead><tbody>`;
    for(const r of t.per_round) h+=`<tr><td>${r.round}</td><td>${r.win_hits}</td><td>${r.win_brier??"—"}</td><td>${r.tryscorer_hits}</td><td>${r.total_mae??"—"}</td></tr>`;
    h+=`</tbody></table>`;
  }
  h+=`<p style="color:var(--muted);font-size:12px;margin-top:12px">Bias > 0 = model over-predicts.
    Brier lower = better calibrated (0 perfect, 0.25 a coin flip).</p>`;
  // paper betting scorecard: ROI / yield / CLV / bankroll — the professional read
  const pf=DATA.performance||{};
  if(pf.n_settled){
    const clv=pf.clv_avg_pct;
    h+=`<h3>Paper betting scorecard (flat + quarter-Kelly ledger)</h3>
      <div class="statgrid">
        <div class="s"><div class="l">Record</div><div class="n" style="font-size:20px">${pf.record||"—"}</div><div class="l">${pf.n_settled} settled</div></div>
        <div class="s"><div class="l">P&amp;L</div><div class="n">${pf.pnl_units>=0?"+":""}${pf.pnl_units??"—"}<small style="font-size:13px">u</small></div><div class="l">on ${pf.staked_units??"—"}u</div></div>
        <div class="s"><div class="l">ROI / yield</div><div class="n" style="color:${(pf.roi_pct||0)>=0?'var(--good)':'#c0392b'}">${pf.roi_pct>=0?"+":""}${pf.roi_pct??"—"}%</div><div class="l">per unit staked</div></div>
        <div class="s"><div class="l">CLV (beat close)</div><div class="n" style="color:${(clv||0)>=0?'var(--good)':'#c0392b'}">${clv==null?"—":(clv>=0?"+":"")+clv+"%"}</div><div class="l">${pf.clv_n?`${Math.round(100*pf.clv_beat_rate)}% of ${pf.clv_n}`:"awaiting closes"}</div></div>
      </div>
      <p style="color:var(--muted);font-size:12px;margin-top:6px">CLV = did we take a better price than the market's close?
      Positive CLV over time is the surest sign of a real edge — it survives short-run variance. Paper only.</p>`;
  }
  panel.innerHTML=h;
}

function renderValue(){
  document.getElementById("valuebtn").classList.add("on");
  document.getElementById("trackbtn").classList.remove("on");
  document.getElementById("formbtn").classList.remove("on");
  [...tabs.children].forEach(t=>t.setAttribute("aria-selected",false));
  const v=DATA.value_board||[];
  if(!v.length){
    panel.innerHTML=`<h2>Value board</h2><p style="color:var(--ink-2)">No positive-EV edges
      in the current market snapshot — the model agrees with the books, or odds aren't live yet.
      Edges appear here when the model's price beats the best of the four books.</p>`; return;
  }
  let h=`<h2>Value board — model vs market edge</h2>
    <p style="color:var(--ink-2);font-size:13px">Every side of every game where the model's probability
    implies value at the <b>best available price across the four books</b> (line-shopped). Ranked by
    expected value. <b>Kelly</b> = suggested stake as % of bankroll (quarter-Kelly, capped 5%).</p>
    <table><thead><tr><th>Selection</th><th>Match</th><th>Model</th><th>Market</th><th>Edge</th>
      <th>Best price</th><th>Fair</th><th>EV</th><th>Kelly</th></tr></thead><tbody>`;
  for(const r of v){
    const evc=r.ev_pct>=8?"var(--good)":r.ev_pct>=3?"var(--model)":"var(--ink)";
    h+=`<tr><td><b>${nick(r.selection)}</b></td><td style="color:var(--ink-2);font-size:12px">${nick(r.match.split(" v ")[0])} v ${nick(r.match.split(" v ")[1])}</td>
      <td>${pc(r.model_p)}</td><td>${r.market_p==null?"—":pc(r.market_p)}</td>
      <td>${r.edge_pp==null?"—":(r.edge_pp>=0?"+":"")+r.edge_pp+"pp"}</td>
      <td><b>$${r.best_price.toFixed(2)}</b></td><td style="color:var(--muted)">$${r.fair_price?r.fair_price.toFixed(2):"—"}</td>
      <td style="color:${evc};font-weight:700">+${r.ev_pct}%</td>
      <td>${r.kelly_pct>0?r.kelly_pct+"%":"—"}</td></tr>`;
  }
  h+=`</tbody></table>
    <p style="color:var(--muted);font-size:12px;margin-top:10px">Model and market both de-vigged. Edge = model − market
    (percentage points). A fair price below the quoted price is the value. <b>Paper only — model opinions, not betting advice;
    bookmaker margins and limits are real.</b></p>`;
  panel.innerHTML=h;
}

function renderForm(){
  document.getElementById("formbtn").classList.add("on");
  document.getElementById("trackbtn").classList.remove("on");
  document.getElementById("valuebtn").classList.remove("on");
  [...tabs.children].forEach(t=>t.setAttribute("aria-selected",false));
  const f=DATA.form||[];
  if(!f.length){
    panel.innerHTML=`<h2>Form guide</h2><p style="color:var(--ink-2)">Advanced-stats form
      table appears once the season's match stats have been scraped.</p>`; return;
  }
  // colour a rank 1..N from strong (green) to weak (amber)
  const n=f.length, tint=(rk)=>{if(rk==null)return "";const q=(rk-1)/(n-1||1);
    const g=`rgba(27,175,122,${(0.16*(1-q)).toFixed(3)})`, a=`rgba(235,104,52,${(0.16*q).toFixed(3)})`;
    return `background:${q<0.5?g:a}`;};
  const arrow=t=>t>0.15?`<span style="color:var(--good)">▲ ${t.toFixed(2)}</span>`
    :t<-0.15?`<span style="color:#c0392b">▼ ${Math.abs(t).toFixed(2)}</span>`
    :`<span style="color:var(--muted)">→</span>`;
  let h=`<h2>Form guide — expected-stats league table</h2>
    <p style="color:var(--ink-2);font-size:13px">Built from the scraped advanced match stats
    (line breaks, tackle breaks, run &amp; post-contact metres, offloads). <b>xAtt</b> = tries a team
    deserves to score per game, <b>xDef</b> = tries it deserves to concede, <b>Edge leak</b> = line +
    tackle breaks conceded (edge softness). Leak-free rolling form as of ${DATA.form_as_of||""}.
    This is what feeds the tryscorer xStats sharpening.</p>
    <table><thead><tr><th>#</th><th>Team</th><th>xAtt</th><th>xDef</th><th>Net</th>
      <th>Edge leak</th><th>Trend (net, last 5)</th></tr></thead><tbody>`;
  for(const r of f){
    h+=`<tr><td>${r.rank}</td><td><b>${nick(r.team)}</b></td>
      <td style="${tint(r.xatt_rank)}">${r.xatt.toFixed(2)} <small style="color:var(--muted)">#${r.xatt_rank}</small></td>
      <td style="${tint(r.xdef_rank)}">${r.xdef.toFixed(2)} <small style="color:var(--muted)">#${r.xdef_rank}</small></td>
      <td><b>${r.xdiff>=0?"+":""}${r.xdiff.toFixed(2)}</b></td>
      <td style="${tint(r.xedge_rank)}">${r.xedge==null?"—":r.xedge.toFixed(1)}${r.xedge_rank?` <small style="color:var(--muted)">#${r.xedge_rank}</small>`:""}</td>
      <td>${arrow(r.trend)}</td></tr>`;
  }
  h+=`</tbody></table>
    <p style="color:var(--muted);font-size:12px;margin-top:10px">Net = xAtt − xDef (attacking minus
    defensive expected tries). Green = league-best, amber = league-worst on that column. Edge leak lower
    is stauncher. A team facing a high edge-leak opponent gets its tryscorer prices lifted (xStats).</p>`;
  panel.innerHTML=h;
}

selectRound(curRound);
</script>
"""


def build() -> Path:
    data = _payload()
    title = f"NRL Predictor — {data.get('current_round_label', 'Season')}"
    body = BODY_TEMPLATE.replace("__DATA__", json.dumps(data)).replace("__TITLE__", title)
    page = ("<!doctype html><html lang=\"en\"><head><meta charset=\"utf-8\">"
            "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
            f"</head><body>{body}</body></html>")
    OUT.mkdir(exist_ok=True)
    full = OUT / "dashboard.html"
    full.write_text(page)
    (OUT / "dashboard_body.html").write_text(body)
    return full


if __name__ == "__main__":
    print(f"-> {build()}")
