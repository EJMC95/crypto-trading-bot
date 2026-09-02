#!/usr/bin/env python3
"""organ_board.py — the weekly ORGAN BOARD: grade what each organ SAYS, not just its pulse.

WHY. The 2-Sep (wp) organ review read every organ on the bus BY HAND — twenty
payloads, each judged against what its docstring promises ("is the judge
judging anything?", "is the incubator's champion real?", "is GDELT up?"). It
took a session, was correct for one morning, and nothing keeps it correct: the
watchdog pages on DEATH, `fleet_immune` on invariant violations, the weekly
scoreboard reads P&L — no scheduled thing asks "is this organ producing the
OUTPUT it was built for?", so an organ can be fresh, in-TTL and USELESS for
weeks (a judge at `0 of 4` lanes, an ensemble at coin-flip accuracy). This
makes the next review a DIFF: the same twenty questions asked weekly from the
PUBLIC feeds, with the 2-Sep by-hand reading pinned as `REVIEW_2SEP`.

STATES, in I1 order — liveness FIRST, then semantics:
  dark    key absent, `age > ttl_sec`, or an unreadable stamp; content is never
          graded (a frozen payload is byte-identical to a healthy one, I1).
  watch   alive and the output says the organ is not doing its job — OR a field
          this board needs is ABSENT: a check that inspects nothing must not
          report clean (house rule), so a dropped field degrades to
          `watch: field absent`, never a silent ok, never a crash.
  fixed?  the baseline read `watch` and the payload reads clean now — a claim
          for a human to confirm, never promoted to `ok` by the board.
  idle    alive, clean, structurally nothing to do (empty queue, no live lane).
  ok      alive and the output is what the organ promises.

`grade(bus, pnl, now)` is PURE (no I/O, no clock); `--selftest` drives it against
a fixture and mutations offline. `main()` is FAIL-CLOSED on the FEED (exit 2 on
a dark/unparseable feed, the `audit_code_currency --pnl-json` contract), exit 0
otherwise: `watch` is a reading, not a red. The default bus URL is `?hours=0` —
the same live keys without the 8 MB history array.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

BUS_URL = "https://pnl-dashboard-production-858c.up.railway.app/bus.json?hours=0"
PNL_URL = "https://pnl-dashboard-production-858c.up.railway.app/pnl.json"
STATES = ("ok", "watch", "fixed?", "idle", "dark")
ICON = {"ok": "🟢 ok", "watch": "🟡 watch", "fixed?": "🔵 fixed?", "idle": "⚪ idle", "dark": "🔴 dark"}
NUM = (int, float)


class Absent(Exception):
    """A field the check needs is not in the payload (or is the wrong shape) — graded `watch`."""


def need(p, path, typ=None):
    cur = p
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            raise Absent(path)
        cur = cur[part]
    if typ is not None and not isinstance(cur, typ):
        raise Absent(f"{path} (not a {typ.__name__})")
    return cur


def age_sec(payload, now):
    """Seconds since `updated`; None when the stamp is missing/unreadable."""
    try:
        t = datetime.fromisoformat(str(payload.get("updated")).replace("Z", "+00:00"))
    except (TypeError, ValueError, AttributeError):
        return None
    return (now - (t if t.tzinfo else t.replace(tzinfo=timezone.utc))).total_seconds()


def liveness(bus, organ, now):
    """(payload, why_dark) — why_dark is None only when something still writes the key (I1)."""
    p = bus.get(organ) if isinstance(bus, dict) else None
    if not isinstance(p, dict):
        return None, "key absent from bus"
    age = age_sec(p, now)
    if age is None:
        return p, "`updated` missing/unparseable — liveness unknowable"
    ttl = p.get("ttl_sec")
    if not isinstance(ttl, NUM) or ttl <= 0:
        return p, f"ttl_sec absent — liveness unknowable (age {age / 3600:.1f}h)"
    if age > ttl:
        return p, f"age {age / 3600:.1f}h > ttl {ttl / 3600:.1f}h"
    return p, None


# ---- per-organ output checks: (payload, ctx) -> (state, why) ----------------
def c_fleet_risk(p, ctx):
    lp, lb = need(p, "long_positions"), need(p, "long_budget")
    why, co = f"light {p.get('light')} · pooled long {lp}/{lb}", p.get("cohorts")
    if isinstance(co, dict):   # [(wp)] the live/shadow split
        # [(wy)] graded PER COHORT: the pooled count mixes paper into real
        # money and back, so "at budget" is asked of each population against
        # its own budget, and the row names WHICH one binds.
        at = []
        for k, v in co.items():
            if not isinstance(v, dict):
                continue
            n, b = v.get("long_positions"), v.get("long_budget")
            lt = v.get("light")
            why += f" · {k} {n}/{b}" + (f" {lt}" if lt else "")
            if isinstance(n, NUM) and isinstance(b, NUM) and n >= b:
                at.append(k)
        return ("watch" if at else "ok"), why + (f" · AT BUDGET: {','.join(at)}" if at else "")
    why += " · cohorts absent (pre-(wp) payload)"
    return ("watch" if lp >= lb else "ok"), why


def c_brain_stake_mults(p, ctx):
    mults, living = need(p, "mults", dict), ctx["living"]
    n = sum(1 for bot, tags in mults.items() if bot in living and isinstance(tags, dict)
            for o in tags.values() if isinstance(o, dict) and o.get("published"))
    why = f"{n} published opinion(s) across {len(living)} living bots · mode {p.get('mode')}"
    if not living:
        return "watch", "no living bots on the feed — " + why
    return ("watch" if n < 3 else "ok"), why


def c_strategy_incubator(p, ctx):
    ch = need(p, "funnel.champion_is")
    why = (f"champion_is {ch} · streak {need(p, 'champion.streak')} · both_halves_pos "
           f"{need(p, 'funnel.both_halves_pos')} · enactable {need(p, 'funnel.enactable')}")
    return ("ok" if ch else "watch"), why + ("" if ch else f" · {p['funnel'].get('champion_why')}")


def c_xp_judge(p, ctx):
    j = need(p, "lanes.judging")
    why = (f"judging {j} · live {need(p, 'lanes.live')} · unjudgeable "
           f"{need(p, 'lanes.unjudgeable')} · stood_down {need(p, 'lanes.stood_down')}")
    return ("watch" if str(j).startswith("0 of") else "ok"), why


def c_xp_queue(p, ctx):
    c = need(p, "candidates", list)
    try:
        live = need(ctx["bus"].get("xp_judge") or {}, "lanes.live")
    except Absent:
        return "watch", f"{len(c)} candidate(s) · judge lanes.live absent — cannot tell idle from starved"
    if c:
        return "ok", f"{len(c)} candidate(s) queued"
    return ("watch" if live else "idle"), f"0 candidates · judge live lanes {live or 'none'}"


def c_scout_tuner(p, ctx):
    return "ok", f"{len(need(p, 'enacted', dict))} enacted lever(s) · baseline_net {need(p, 'baseline_net')}"


def c_proprioception(p, ctx):
    h, hu = need(p, "counts.helping"), need(p, "counts.hurting")
    return ("watch" if hu > 0 else "ok"), f"helping {h} · hurting {hu} · graded {p['counts'].get('graded')}"


def c_evidence_board(p, ctx):
    items = need(p, "items", list)
    n = sum(1 for i in items if isinstance(i, dict) and i.get("verdict") == "active")
    return "ok", f"{n} active of {len(items)} item(s)"


def c_fleet_immune(p, ctx):
    sick = need(p, "sick", list)
    if not sick:
        return "ok", "sick: none"
    organs = sorted({str(s.get("organ") if isinstance(s, dict) else s) for s in sick})
    return "watch", f"{len(sick)} sick finding(s): {', '.join(organs)}"


def c_impl_shortfall(p, ctx):
    v, sd = need(p, "verdict"), p.get("stood_down")
    why = f"verdict {v}" + (f" ({sd['why']})" if isinstance(sd, dict) and sd.get("why") else "")
    return ("watch" if v in ("stood_down", "insufficient") else "ok"), why


def c_event_sentinel(p, ctx):
    gdelt, bias, pg = need(p, "sources_ok.gdelt"), need(p, "market_bias"), p.get("playbook_grades")
    state, why = ("ok" if gdelt else "watch"), f"market_bias {bias} · gdelt {gdelt}"
    rates = [g.get("hit_rate") for g in pg.values()
             if isinstance(g, dict) and isinstance(g.get("hit_rate"), NUM)] if isinstance(pg, dict) else []
    if rates:
        why += f" · best playbook hit_rate {max(rates):.2f} of {len(rates)}"
        state = "watch" if max(rates) < 0.5 else state
    else:
        why += " · playbook_grades absent"
    return state, why


def c_parliament(p, ctx):
    acc, r = need(p, "ml.oos_acc", dict), need(p, "restarts")
    vals = {k: v for k, v in acc.items() if isinstance(v, NUM)}
    if not vals:
        raise Absent("ml.oos_acc (no numeric models)")
    bk = max(vals, key=vals.get)
    return ("watch" if vals[bk] <= 0.52 else "ok"), f"oos_acc max {vals[bk]:.4f} ({bk}) of {len(vals)} · restarts {r}"


def c_fleet_respiration(p, ctx):
    s = need(p, "spo2")
    return ("watch" if s < 1.0 else "ok"), f"spo2 {s} · state {p.get('state')}"


def c_golive_readiness(p, ctx):
    books, docket = need(p, "books", dict), need(p, "decision_docket", list)
    n = sum(1 for b in books.values() if isinstance(b, dict)
            and (b.get("horizon") or {}).get("verdict") in ("on_track", "ready"))
    names = ", ".join(str(d.get("book") if isinstance(d, dict) else d) for d in docket)
    why = f"{n} of {len(books)} books on_track/ready · docket {len(docket)}" + (f": {names}" if docket else "")
    return ("watch" if docket else "ok"), why


def c_fleet_allocation(p, ctx):
    bc = need(p, "by_class", dict)
    if not bc:
        raise Absent("by_class (empty)")
    return "ok", " · ".join(f"{c} era-claim {need(bc, f'{c}.n_with_era_claim')}/{bc[c].get('books', '?')}" for c in bc)


def c_lighter_market(p, ctx):
    return "ok", f"stress.med {need(p, 'stress.med')}bps · n_books {need(p, 'n_books')}"


def c_brain_vitals(p, ctx):
    h, u = need(p, "healthy"), need(p, "urgent", list)
    return ("ok" if h and not u else "watch"), f"healthy {h} · urgent {len(u)} · run {p.get('run')}"


def c_fleet_regen(p, ctx):
    r, no = need(p, "repaired", list), need(p, "needs_operator", list)
    if no:
        return "watch", f"needs_operator {no}"
    return ("ok" if r else "idle"), f"repaired {len(r)} · needs_operator 0"


def _open_map(p, field, noun):
    m = need(p, field, dict)
    return ("ok" if m else "idle"), f"{len(m)} open {noun}(s)" + (": " + ", ".join(sorted(m)[:6]) if m else "")


def c_tuning_proposals(p, ctx):
    return _open_map(p, "proposals", "proposal")


def c_fleet_tuning(p, ctx):
    return _open_map(p, "levers", "lever")


CHECKS = [(n[2:], f) for n, f in list(globals().items()) if n.startswith("c_")]

#: The 2-Sep (wp) by-hand review, as this board grades its feed. `fixed?` is a
#: row that read `watch` here and reads clean now. Pinned by --selftest to the
#: fixture, so moving a baseline means re-deriving it from a real feed.
REVIEW_2SEP = {
    "fleet_risk": "watch", "brain_stake_mults": "ok", "strategy_incubator": "watch",
    "xp_judge": "watch", "xp_queue": "idle", "scout_tuner": "ok", "proprioception": "ok",
    "evidence_board": "ok", "fleet_immune": "watch", "impl_shortfall": "watch",
    "event_sentinel": "watch", "parliament": "watch", "fleet_respiration": "ok",
    "golive_readiness": "watch", "fleet_allocation": "ok", "lighter_market": "ok",
    "brain_vitals": "ok", "fleet_regen": "idle", "tuning_proposals": "ok", "fleet_tuning": "ok",
}


def grade(bus, pnl, now):
    """PURE: rows [{organ, state, why}] in CHECKS order. Liveness first (I1), then output."""
    rows_in = pnl.get("bots") if isinstance(pnl, dict) else pnl
    living = {r.get("bot") for r in (rows_in or []) if isinstance(r, dict) and r.get("bot") and not r.get("stale")}
    ctx, out = {"living": living, "bus": bus if isinstance(bus, dict) else {}}, []
    for organ, fn in CHECKS:
        p, dark = liveness(ctx["bus"], organ, now)
        if dark:
            out.append({"organ": organ, "state": "dark", "why": dark})
            continue
        try:
            state, why = fn(p, ctx)
        except Absent as e:
            state, why = "watch", f"field absent: {e}"
        except Exception as e:                    # never a crash, never a silent ok
            state, why = "watch", f"check error: {e!r}"
        if state == "ok" and REVIEW_2SEP.get(organ) == "watch":
            state, why = "fixed?", f"read watch on 2-Sep (wp), clean now — confirm: {why}"
        out.append({"organ": organ, "state": state, "why": why})
    return out


def render(rows):
    L = ["### 🫀 Organ board — output, not pulse (baseline: 2-Sep (wp) by-hand review)", "",
         "| Organ | State | What the payload says |", "|---|---|---|"]
    L += [f"| `{r['organ']}` | {ICON[r['state']]} | {r['why'].replace('|', '/')} |" for r in rows]
    tally = " · ".join(f"{s} {sum(1 for r in rows if r['state'] == s)}" for s in STATES)
    L += ["", f"{len(rows)} organs: {tally}. `watch` is a reading, not a red; `dark` is I1 — "
          "nothing writes the key, so its content was not graded.", ""]
    return "\n".join(L)


def load_feed(src):
    if str(src).startswith(("http://", "https://")):
        import urllib.request
        with urllib.request.urlopen(str(src), timeout=30) as resp:
            return json.load(resp)
    return json.loads(Path(src).read_text())


def feed_dark(bus, pnl):
    """Reason string when a FEED (not an organ) is unusable — exit 2 territory."""
    if not isinstance(bus, dict) or not any(isinstance(v, dict) for v in bus.values()):
        return "bus.json carries no organ payloads"
    rows = pnl.get("bots") if isinstance(pnl, dict) else pnl
    if not isinstance(rows, list) or not any(isinstance(r, dict) and r.get("bot") for r in rows):
        return "pnl.json carries no bot rows"
    return None


# ---- fixture: the 2-Sep 04:20Z public feeds, trimmed to the fields graded ----
FIXTURE_NOW = datetime(2026, 9, 2, 4, 20, tzinfo=timezone.utc)
FIXTURE_BUS = json.loads(r'''{"fleet_risk":{"updated":"2026-09-02T04:15:31+00:00","ttl_sec":900,"light":"red","long_positions":20,"long_budget":20},"brain_stake_mults":{"updated":"2026-09-02T04:14:07+00:00","ttl_sec":26000,"mode":"two-way","mults":{"book-douglas-lshadow":{"short-impulse":{"mult":0.75,"published":true}},"freqtrade-mum-lighter":{"long-oversold-rebound":{"mult":1.25,"published":true}},"lighter-ticket-taker-lshadow":{"short-divergence":{"mult":0.75,"published":true}}}},"strategy_incubator":{"updated":"2026-09-02T04:09:19+00:00","ttl_sec":10800,"funnel":{"champion_is":false,"champion_why":"weak half $-7.60 < $3.5 (one-half win = noise)","both_halves_pos":5,"enactable":0},"champion":{"streak":0,"net":11.54}},"xp_judge":{"updated":"2026-09-02T04:17:16+00:00","ttl_sec":10800,"phase":"stood_down","lanes":{"live":[],"judging":"0 of 4","unknown":[],"stood_down":["farmer","georgia"],"serial_lane":"farmer","unjudgeable":["avo","mum"]}},"xp_queue":{"updated":"2026-09-02T04:09:19+00:00","ttl_sec":10800,"candidates":[]},"scout_tuner":{"updated":"2026-09-02T04:17:12+00:00","ttl_sec":10800,"baseline_net":-31.18,"enacted":{"taker.momo_chg":6.0,"scout.div_gap_pp":30.0}},"proprioception":{"updated":"2026-09-02T04:18:09+00:00","ttl_sec":2700,"counts":{"open":4,"graded":66,"helping":2,"hurting":0,"episodes":120}},"evidence_board":{"updated":"2026-09-02T04:14:24+00:00","ttl_sec":1800,"items":[{"key":"board:immune","verdict":"active"},{"key":"board:budget-crowding","verdict":"active"},{"key":"board:lens-floor:breakout","verdict":"active"},{"key":"board:lens-floor:dip","verdict":"active"},{"key":"board:lens-floor:divergence","verdict":"active"},{"key":"board:lens-floor:momentum","verdict":"active"},{"key":"board:lens-positive:dip","verdict":"active"},{"key":"board:tuner-enacted","verdict":"active"},{"key":"board:promotion-watch:lighter-ticket-taker-lshadow","verdict":"active"},{"key":"board:promotion-watch:perps-funding-carry-lshadow","verdict":"active"},{"key":"board:stress-headroom","verdict":"active"},{"key":"board:prop-helping:scout.brk_range_min","verdict":"active"},{"key":"board:prop-helping:scout.momo_chg_min","verdict":"active"},{"key":"board:book-carry.max_positions-held","verdict":"active"},{"key":"board:book-fundspread.k-held","verdict":"active"},{"key":"veto:CXMT","verdict":"resolved"},{"key":"disloc:CHIP","verdict":"stale"},{"key":"disloc:SNDK","verdict":"stale"},{"key":"disloc:SKHYNIXUSD","verdict":"stale"},{"key":"disloc:0G","verdict":"stale"}]},"fleet_immune":{"updated":"2026-09-02T04:18:16+00:00","ttl_sec":2400,"sick":[{"organ":"freqtrade-avo-maria-lighter","detail":"headroom refused: liq_unpriced (gap 7.98"},{"organ":"freqtrade-avo-maria-lighter","detail":"protective stop is DEAD at gross 5.3 (ce"},{"organ":"freqtrade-mum-lighter","detail":"headroom refused: liq_unpriced (gap None"},{"organ":"freqtrade-mum-lighter","detail":"protective stop is DEAD at gross 9.5 (ce"}]},"impl_shortfall":{"updated":"2026-09-02T04:09:24+00:00","ttl_sec":3600,"verdict":"stood_down","stood_down":{"why":"live arm retired"}},"event_sentinel":{"updated":"2026-09-02T04:12:54+00:00","ttl_sec":2400,"sources_ok":{"rss":true,"gdelt":false},"market_bias":-0.613,"playbook_grades":{"ai_boom":{"hit_rate":0.54},"etf_adoption":{"hit_rate":0.75},"inflation_cool":{"hit_rate":0.69},"monetary_easing":{"hit_rate":0.72},"exchange_incident":{"hit_rate":0.27},"geopolitical_shock":{"hit_rate":0.31},"monetary_tightening":{"hit_rate":0.4},"regulation_crackdown":{"hit_rate":0.2}}},"parliament":{"updated":"2026-09-02T04:15:01+00:00","ttl_sec":900,"ml":{"oos_acc":{"nb":0.4995,"knn":0.5009,"logit":0.5004,"ridge":0.4907,"stumps":0.4876}},"restarts":75},"fleet_respiration":{"updated":"2026-09-02T04:12:54+00:00","ttl_sec":1200,"spo2":1.0,"state":"healthy"},"golive_readiness":{"updated":"2026-09-02T02:06:30+00:00","ttl_sec":43200,"decision_docket":[{"book":"perps-funding-spread-lshadow"},{"book":"book-grimes-lshadow"},{"book":"band-garrett-lshadow"},{"book":"book-douglas-lshadow"},{"book":"perps-funding-lighter-lshadow"},{"book":"nav-cook-lshadow"},{"book":"freqtrade-georgia-lshadow"}],"books":{"nav-cook-lshadow":{"horizon":{"verdict":"unreachable"}},"band-kelly-lshadow":{"horizon":{"verdict":"unreachable"}},"pm-albanese-lshadow":{"horizon":{"verdict":"underpowered"}},"pm-turnbull-lshadow":{"horizon":{"verdict":"on_track"}},"band-garrett-lshadow":{"horizon":{"verdict":"unreachable"}},"book-douglas-lshadow":{"horizon":{"verdict":"unreachable"}},"freqtrade-mum-lighter":{"horizon":{"verdict":"on_track"}},"freqtrade-mum-lshadow":{"horizon":{"verdict":"on_track"}},"freqtrade-georgia-lighter":{"horizon":{"verdict":"unreachable"}},"freqtrade-georgia-lshadow":{"horizon":{"verdict":"undecidable"}},"freqtrade-avo-maria-lighter":{"horizon":{"verdict":"undecidable"}},"freqtrade-avo-maria-lshadow":{"horizon":{"verdict":"on_track"}},"lighter-perp-sniper-lshadow":{"horizon":{"verdict":"undecidable"}},"perps-funding-carry-lshadow":{"horizon":{"verdict":"underpowered"}},"freqtrade-georgia-v3-lshadow":{"horizon":{"verdict":"unreachable"}},"lighter-ticket-taker-lshadow":{"horizon":{"verdict":"on_track"}},"perps-funding-spread-lshadow":{"horizon":{"verdict":"unreachable"}},"perps-funding-lighter-lshadow":{"horizon":{"verdict":"unreachable"}}}},"fleet_allocation":{"updated":"2026-09-02T04:09:40+00:00","ttl_sec":5400,"by_class":{"funding":{"n_with_era_claim":0,"books":6},"directional":{"n_with_era_claim":5,"books":15}}},"lighter_market":{"updated":"2026-09-02T04:16:32+00:00","ttl_sec":900,"stress":{"med":5.8},"n_books":214},"brain_vitals":{"updated":"2026-09-02T04:14:02+00:00","ttl_sec":9600,"healthy":true,"urgent":[],"run":817},"fleet_regen":{"updated":"2026-09-02T04:09:14+00:00","ttl_sec":2400,"repaired":[],"needs_operator":[]},"tuning_proposals":{"updated":"2026-09-02T04:12:54+00:00","ttl_sec":7200,"proposals":{"event-sentinel:taker.momo_chg":{"lever":"taker.momo_chg"},"event-sentinel:taker.brk_range":{"lever":"taker.brk_range"},"event-sentinel:taker.max_hold_h":{"lever":"taker.max_hold_h"}}},"fleet_tuning":{"updated":"2026-09-02T04:17:11+00:00","ttl_sec":7800,"levers":{"taker.momo_chg":null,"scout.div_gap_pp":null,"evsent.min_sources":null,"evsent.severity_bar":null,"live.georgia.clip_scale":null}}}''')
FIXTURE_PNL = json.loads(r'''{"bots":[{"bot":"perps-funding-carry-lshadow","status":"online","age_sec":143,"stale":false,"closed_trades":107,"open_trades":15,"equity":1093.9064210590818,"pnl_abs":66.70288471944777},{"bot":"book-grimes-lshadow","status":"online","age_sec":225,"stale":false,"closed_trades":0,"open_trades":0,"equity":1000.0,"pnl_abs":0.0},{"bot":"perps-funding-lighter-lshadow","status":"online","age_sec":55,"stale":false,"closed_trades":239,"open_trades":5,"equity":986.09770756417,"pnl_abs":-13.902292435829963},{"bot":"freqtrade-avo-maria-lshadow","status":"online","age_sec":206,"stale":false,"closed_trades":22,"open_trades":4,"equity":1012.0121247753408,"pnl_abs":12.012124775340794},{"bot":"freqtrade-mum-lshadow","status":"online","age_sec":738,"stale":false,"closed_trades":9,"open_trades":2,"equity":1017.0719087413751,"pnl_abs":17.07190874137507},{"bot":"book-bezos-lshadow","status":"online","age_sec":241,"stale":false,"closed_trades":1,"open_trades":0,"equity":1003.8277488180386,"pnl_abs":3.8277488180385566},{"bot":"band-garrett-lshadow","status":"online","age_sec":33,"stale":false,"closed_trades":85,"open_trades":2,"equity":974.5025607915477,"pnl_abs":-25.497439208452306},{"bot":"book-hull-lshadow","status":"online","age_sec":166,"stale":false,"closed_trades":1,"open_trades":10,"equity":1002.0286003139489,"pnl_abs":2.028600313948915},{"bot":"freqtrade-georgia-lshadow","status":"online","age_sec":78,"stale":false,"closed_trades":224,"open_trades":0,"equity":1007.7676328556018,"pnl_abs":7.767632855601846},{"bot":"pm-turnbull-lshadow","status":"online","age_sec":19,"stale":false,"closed_trades":35,"open_trades":0,"equity":1003.52,"pnl_abs":3.52},{"bot":"perps-funding-spread-lshadow","status":"online","age_sec":93,"stale":false,"closed_trades":161,"open_trades":10,"equity":965.5317271023548,"pnl_abs":-34.46827289764519},{"bot":"book-kiyosaki-lshadow","status":"online","age_sec":276,"stale":false,"closed_trades":2,"open_trades":6,"equity":1017.2137812542883,"pnl_abs":17.213781254288335},{"bot":"nav-cook-lshadow","status":"online","age_sec":111,"stale":false,"closed_trades":38,"open_trades":0,"equity":990.01,"pnl_abs":-9.99},{"bot":"lighter-perp-sniper-lshadow","status":"online","age_sec":58,"stale":false,"closed_trades":42,"open_trades":0,"equity":1001.534340221403,"pnl_abs":1.5343402214029993},{"bot":"freqtrade-avo-maria-lighter","status":"online","age_sec":44,"stale":false,"closed_trades":11,"open_trades":3,"equity":307.96,"pnl_abs":-6.19},{"bot":"lighter-ticket-taker-lshadow","status":"online","age_sec":100,"stale":false,"closed_trades":291,"open_trades":6,"equity":1068.81,"pnl_abs":68.81},{"bot":"pm-albanese-lshadow","status":"online","age_sec":20,"stale":false,"closed_trades":51,"open_trades":3,"equity":997.66,"pnl_abs":-2.34},{"bot":"book-douglas-lshadow","status":"online","age_sec":251,"stale":false,"closed_trades":81,"open_trades":0,"equity":950.7664000980652,"pnl_abs":-49.23359990193481},{"bot":"band-kelly-lshadow","status":"online","age_sec":51,"stale":false,"closed_trades":387,"open_trades":2,"equity":869.6175269868213,"pnl_abs":-130.38247301317872},{"bot":"freqtrade-mum-lighter","status":"online","age_sec":23,"stale":false,"closed_trades":53,"open_trades":11,"equity":563.11,"pnl_abs":42.69}]}''')


def _mut(**edits):
    """Deep copy of the fixture bus with `organ={...field: value}` overlays; returns rows by organ."""
    m = copy.deepcopy(FIXTURE_BUS)
    for organ, fields in edits.items():
        m[organ].update(fields)
    return m, {r["organ"]: r for r in grade(m, FIXTURE_PNL, FIXTURE_NOW)}


def selftest():
    rows = grade(FIXTURE_BUS, FIXTURE_PNL, FIXTURE_NOW)
    got = {r["organ"]: r["state"] for r in rows}
    assert [r["organ"] for r in rows] == [o for o, _ in CHECKS] and set(got.values()) <= set(STATES)
    bad = {k: (got.get(k), REVIEW_2SEP.get(k)) for k in set(got) | set(REVIEW_2SEP) if got.get(k) != REVIEW_2SEP.get(k)}
    assert not bad, f"baseline drifted from fixture: {bad}"
    assert "dark" not in got.values() and "fixed?" not in got.values()
    # (a) aged past ttl -> DARK, content not consulted (I1); an absent key is dark too
    _, r = _mut(lighter_market={"updated": "2026-09-01T00:00:00+00:00", "n_books": "junk"})
    assert r["lighter_market"]["state"] == "dark" and "ttl" in r["lighter_market"]["why"], r["lighter_market"]
    m = copy.deepcopy(FIXTURE_BUS); del m["fleet_risk"]
    assert grade(m, FIXTURE_PNL, FIXTURE_NOW)[0]["state"] == "dark"
    # (b) fleet_immune.sick non-empty -> WATCH naming the organ; emptied -> fixed? (baseline was watch)
    _, r = _mut(fleet_immune={"sick": [{"organ": "organ-x", "detail": "d"}]})
    assert r["fleet_immune"]["state"] == "watch" and "organ-x" in r["fleet_immune"]["why"], r["fleet_immune"]
    assert _mut(fleet_immune={"sick": []})[1]["fleet_immune"]["state"] == "fixed?"
    # (c) a missing field -> watch/absent: one organ, then EVERY organ stripped to its stamps
    m = copy.deepcopy(FIXTURE_BUS); del m["fleet_respiration"]["spo2"]
    r = grade(m, FIXTURE_PNL, FIXTURE_NOW)[[o for o, _ in CHECKS].index("fleet_respiration")]
    assert r["state"] == "watch" and "absent" in r["why"], r
    bare = {o: {"updated": FIXTURE_NOW.isoformat(), "ttl_sec": 60} for o, _ in CHECKS}
    for r in grade(bare, FIXTURE_PNL, FIXTURE_NOW):
        assert r["state"] == "watch" and "absent" in r["why"], r
    # one semantics arm + the baseline claim: a cleared watch reads fixed?, never ok
    _, r = _mut(fleet_risk={"long_positions": 3, "cohorts": {"live": {"long_positions": 1, "long_budget": 6}}})
    assert r["fleet_risk"]["state"] == "fixed?" and "live 1/6" in r["fleet_risk"]["why"], r["fleet_risk"]
    assert grade(FIXTURE_BUS, {"bots": []}, FIXTURE_NOW)[1]["state"] == "watch"   # no living bots -> no opinions
    # (d) an empty/unparseable bus is a dark FEED -> exit 2 (never a table of twenty darks read as a result)
    assert feed_dark({}, FIXTURE_PNL) and feed_dark(FIXTURE_BUS, {"bots": []}) and not feed_dark(FIXTURE_BUS, FIXTURE_PNL)
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        eb, ep = Path(d, "bus.json"), Path(d, "pnl.json")
        ep.write_text(json.dumps(FIXTURE_PNL))
        for junk in ("{}", "not json"):
            eb.write_text(junk)
            assert main(["--bus-json", str(eb), "--pnl-json", str(ep)]) == 2
    assert "| `fleet_immune` | 🟡 watch |" in render(rows)
    print(f"organ_board selftest OK — {len(CHECKS)} organs graded, baseline pinned, "
          f"4 mutations (dark/sick/absent/empty-feed) red as expected; semantic arms in tests/autonomy/test_organ_board.py")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description="Weekly organ board — grades each organ's OUTPUT off the public feeds.")
    ap.add_argument("--bus-json", default=BUS_URL, metavar="PATH_OR_URL")
    ap.add_argument("--pnl-json", default=PNL_URL, metavar="PATH_OR_URL")
    ap.add_argument("--selftest", action="store_true", help="offline, fixture-driven")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    try:
        bus, pnl = load_feed(a.bus_json), load_feed(a.pnl_json)
        dark = feed_dark(bus, pnl)
    except Exception as e:                       # unreadable feed: fail closed
        dark = repr(e)
    if dark:
        print(f"organ_board: FEED DARK — {dark}", file=sys.stderr)
        return 2
    md = render(grade(bus, pnl, datetime.now(timezone.utc)))
    print(md)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a") as f:
            f.write(md + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
