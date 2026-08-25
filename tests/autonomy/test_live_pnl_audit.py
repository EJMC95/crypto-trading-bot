"""The live P&L audit must fail closed, key on the feed's own fields, and
stay WIRED — pins for scripts/live_pnl_audit.py + live-pnl-audit.yml (th).

INCIDENT CLASS. Eamon, 25-Aug: "instances where a month has passed without
something being implemented." The audit exists to end that class, so these
tests pin the ways IT could itself become the class:

  * a dark feed reading as green (the (jc) vacuous-green shape — exit 2 is
    the contract);
  * live-row membership drifting to a curated name list (the audit-scope
    rule has named a retired bot THREE times; `extra.venue` is the rule);
  * the frozen-row detector going quiet (🧭 nav-cook sat "online" for 4.5
    days — the exact row, captured from the real 25-Aug feed, is the
    fixture);
  * the attestation-gap detector firing on the wrong signature or not
    firing (the (td) value-never-landed incident, captured verbatim);
  * the build-spread check re-widening to the whole fleet, which is the
    (fd) per-image-file-set trap this script's own first draft walked into;
  * the workflow un-wiring silently (the (gk)/"rule nobody runs" shape) —
    schedules, dispatch, the --gha invocation, and an unmasked exit code.

FIXTURE PROVENANCE: the payload rows below are trimmed VERBATIM from the
real /pnl.json and /trades.json?source=paper of 2026-08-25 10:56Z — the
publisher built them, per the payload-contract rule ((hj)); the fields the
assertions read are byte-copies, not hand-written lookalikes.
"""
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

import live_pnl_audit as lpa  # noqa: E402

WF = ROOT / ".github" / "workflows" / "live-pnl-audit.yml"

import datetime as dt  # noqa: E402

NOW = dt.datetime(2026, 8, 25, 11, 0, tzinfo=dt.timezone.utc)

# --- trimmed VERBATIM from /pnl.json, 2026-08-25 10:56Z --------------------
PNL = {"bots": [
    {"bot": "freqtrade-avo-maria-lighter", "status": "online",
     "age_sec": 251, "equity": 319.7, "pnl_abs": -60.86, "open_trades": 2,
     "extra": {"venue": "lighter_live", "build": "feb27e5d0318",
               "manual_pnl_usd": 0.0, "clip_usd": 239.77,
               "capital_adjust": 317.76, "initial_equity": 62.795571,
               "entry_vetoes": {"live_clip_scale": 0.75}}},
    {"bot": "freqtrade-georgia-lighter", "status": "online",
     "age_sec": 196, "equity": 273.82, "pnl_abs": -39.6, "open_trades": 5,
     "extra": {"venue": "lighter_live", "build": "feb27e5d0318",
               "manual_pnl_usd": 0.0, "clip_usd": 205.37,
               "entry_vetoes": {"live_clip_scale": 0.75}}},
    {"bot": "freqtrade-mum-lighter", "status": "online",
     "age_sec": 177, "equity": 300.0, "pnl_abs": 0.0, "open_trades": 0,
     "extra": {"venue": "lighter_live", "build": "feb27e5d0318",
               "manual_pnl_usd": 0.0, "clip_usd": 712.5,
               "entry_vetoes": {"live_clip_scale": 1.0}}},
    {"bot": "nav-cook-lshadow", "status": "online", "age_sec": 390899,
     "equity": 1000.0, "pnl_abs": 0.0, "open_trades": 0,
     "extra": {"build": "f45a3a15c11f"}},
    {"bot": "lighter-ticket-taker-lshadow", "status": "online",
     "age_sec": 47, "equity": 1058.1, "pnl_abs": 58.1, "open_trades": 6,
     "extra": {"build": "921b8c40a41f"}},
]}

TRADES = [
    # avo-live: one of the nine 23/24-Aug zero-basis daily-loss flattens
    {"bot": "freqtrade-avo-maria-lighter", "pair": "ZRO", "pnl_abs": 0.0,
     "pnl_pct": 0.0, "reason": "long_daily_loss", "entry_price": None,
     "exit_price": None, "closed_at": "2026-08-23T04:57:36.277149+00:00"},
    # georgia-live: one of the four 22-Aug zero-basis flattens + a real close
    {"bot": "freqtrade-georgia-lighter", "pair": "ETH", "pnl_abs": 0.0,
     "pnl_pct": 0.0, "reason": "long_daily_loss", "entry_price": None,
     "exit_price": 2416.07, "closed_at": "2026-08-22T22:39:16.922520+00:00"},
    {"bot": "freqtrade-georgia-lighter", "pair": "SOL",
     "pnl_abs": 7.5003, "pnl_pct": 0.03486,
     "reason": "long-trend-breakout_roi", "entry_price": 99.031,
     "exit_price": 102.492, "closed_at": "2026-08-25T00:14:17.498414+00:00"},
    # a REAL daily-loss close WITH basis — must never count as unattributed
    {"bot": "freqtrade-georgia-lighter", "pair": "TRX", "pnl_abs": -3.872,
     "pnl_pct": -0.019, "reason": "long-trend-breakout_daily_loss",
     "entry_price": 0.3509, "exit_price": 0.34427,
     "closed_at": "2026-08-22T09:09:16.887500+00:00"},
    # CONSTRUCTED (not verbatim, and the one such row here): a bot trade
    # that closed EXACTLY flat, basis known. pnl 0.0 alone must not read as
    # unattributed — the basis is the discriminator, and the first mutation
    # round proved the fixture needed this case to see it.
    {"bot": "freqtrade-georgia-lighter", "pair": "BTC", "pnl_abs": 0.0,
     "pnl_pct": 0.0, "reason": "long-range-on_daily_loss",
     "entry_price": 78750.0, "exit_price": 78750.0,
     "closed_at": "2026-08-22T09:19:16.887775+00:00"},
]

BUS = {"fleet_risk": {"clip_scale": 0.5, "clip_scale_raw": 0.5,
                      "fleet_dd_7d": None},
       "fleet_tuning": {"levers": {
           "live.avo.clip_scale": {
               "lane": "lighter-live", "value": 0.75,
               "reason": "backstop", "expires": "2026-08-25T11:22:16+00:00"},
           "taker.tp": {"lane": "lighter-taker", "value": 0.06,
                        "reason": "replay-gated"}}},
       "golive_readiness": {"decision_docket": [
           {"book": "lighter-perp-sniper-lshadow", "reason": "unreachable",
            "days_held": 18.9,
            "asks": "keep-or-retire (I17)"}]}}


# ------------------------------------------------------------ pure functions

def test_selftest_is_green():
    assert lpa.selftest() == 0


def test_live_rows_key_on_venue_not_names():
    assert [b["bot"] for b in lpa.live_rows(PNL)] == [
        "freqtrade-avo-maria-lighter", "freqtrade-georgia-lighter",
        "freqtrade-mum-lighter"]
    # a renamed live row is still found; a name list would miss it
    p2 = json.loads(json.dumps(PNL))
    p2["bots"][0]["bot"] = "freqtrade-someone-new-lighter"
    assert "freqtrade-someone-new-lighter" in [
        b["bot"] for b in lpa.live_rows(p2)]


def test_frozen_nav_cook_row_is_stale_and_fresh_rows_are_not():
    st = lpa.stale_rows(PNL)
    assert [r[0]["bot"] for r in st] == ["nav-cook-lshadow"]
    age = st[0][1]
    assert age == 390899 and age / 3600 > 100  # the real 4.5-day freeze


def test_missing_age_is_unknown_never_fresh():
    p2 = json.loads(json.dumps(PNL))
    del p2["bots"][4]["age_sec"]
    assert any(r[0]["bot"] == "lighter-ticket-taker-lshadow" and r[1] is None
               for r in lpa.stale_rows(p2))


def test_attestation_gap_fires_on_the_real_signature_only():
    avo = PNL["bots"][0]
    att = lpa.attribution(avo, lpa.ledger_for(TRADES, avo["bot"]))
    assert att["attestation_gap"] and att["unattributed_flattens"] == 1

    geo = PNL["bots"][1]
    attg = lpa.attribution(geo, lpa.ledger_for(TRADES, geo["bot"]))
    # TRX carried a basis and a real pnl — only ETH counts
    assert attg["unattributed_flattens"] == 1
    assert attg["flatten_pairs"] == ["ETH"]

    # a landed attestation clears the gap without touching the ledger
    avo2 = json.loads(json.dumps(avo))
    avo2["extra"]["manual_pnl_usd"] = -66.4
    att2 = lpa.attribution(avo2, lpa.ledger_for(TRADES, avo["bot"]))
    assert not att2["attestation_gap"]
    assert att2["manual_attested"] == -66.4

    # no unattributed flattens -> no gap even with manual 0.0 (mum's state)
    mum = PNL["bots"][2]
    attm = lpa.attribution(mum, lpa.ledger_for(TRADES, mum["bot"]))
    assert not attm["attestation_gap"]


def test_build_spread_is_live_trio_only():
    # the taker's shadow-image stamp differs from the trio's — that is the
    # (fd) per-image reality and must NOT read as a spread
    assert set(lpa.build_spread(PNL)) == {"feb27e5d0318"}
    p2 = json.loads(json.dumps(PNL))
    p2["bots"][2]["extra"]["build"] = "0000laggard0"
    assert set(lpa.build_spread(p2)) == {"feb27e5d0318", "0000laggard0"}


def test_governor_state_reads_the_live_lane_and_the_carried_abstain():
    gov = lpa.governor_state(BUS)
    assert gov["fleet_clip_scale"] == 0.5
    assert gov["carried_while_abstaining"] is True
    assert [lv["name"] for lv in gov["live_levers"]] == [
        "live.avo.clip_scale"]  # the taker lane must not leak in


def test_sync_findings_red_and_amber_split():
    reds, ambers = lpa.sync_findings(PNL, TRADES, BUS, NOW,
                                     trades_limit=5000)
    assert sum("FROZEN" in r for r in reds) == 1
    assert sum("attestation" in r.lower() for r in reds) == 2  # avo + georgia
    assert any("18.9d" in a for a in ambers)  # the docket age surfaces
    # trades were NOT at the limit -> no truncation amber
    assert not any("truncation" in a for a in ambers)
    reds2, ambers2 = lpa.sync_findings(PNL, TRADES, BUS, NOW,
                                       trades_limit=len(TRADES))
    assert any("truncation" in a for a in ambers2)


def test_render_carries_the_findings_and_the_attribution():
    reds, ambers = lpa.sync_findings(PNL, TRADES, BUS, NOW,
                                     trades_limit=5000)
    rep = lpa.render(PNL, TRADES, BUS, "weekly", NOW, reds, ambers)
    assert "FROZEN" in rep and "nav-cook-lshadow" in rep
    assert "ATTESTATION NOT LANDED" in rep
    assert "-100.46" in rep  # the live trio's combined pnl_abs


def test_fail_closed_on_dark_feed_exit_2(tmp_path):
    dark = tmp_path / "dark.json"
    dark.write_text("{}")
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "live_pnl_audit.py"),
         "--pnl-json", str(dark)],
        capture_output=True, text=True, timeout=120)
    assert r.returncode == 2, (r.stdout, r.stderr)
    assert "fail-closed" in r.stdout


# ------------------------------------------------------------------- wiring

def _wf_text():
    return WF.read_text()


def test_workflow_exists_with_three_schedules_and_dispatch():
    t = _wf_text()
    crons = re.findall(r'cron:\s*"([^"]+)"', t)
    assert len(crons) == 3, "daily + weekly + monthly schedules"
    # one daily (5-field, every day), one weekly (day-of-week set), one
    # monthly (day-of-month set) — the CADENCE claim, not exact times
    assert any(c.split()[4] != "*" for c in crons), "a weekly cron"
    assert any(c.split()[2] != "*" for c in crons), "a monthly cron"
    assert "workflow_dispatch" in t


def test_workflow_runs_the_script_with_gha_and_repo_root():
    t = _wf_text()
    assert "scripts/live_pnl_audit.py" in t
    assert "--gha" in t
    assert "--repo-root" in t, "queue-sweep proxy needs the checkout"
    m = re.search(r"fetch-depth:\s*0", t)
    assert m, "queue-sweep proxy dates OPERATOR_QUEUE.md from git history"


def test_workflow_does_not_mask_the_exit_code():
    t = _wf_text()
    assert "continue-on-error" not in t
    # the run step captures rc deliberately (rc=$?); the FAIL step must then
    # exist and re-raise on any non-zero rc — a guard whose only output is a
    # warning on a passing run is not a guard ((gl)/(hj))
    assert re.search(r"if:\s*\$\{\{\s*steps\.audit\.outputs\.rc\s*!=\s*'0'",
                     t), "the re-raise step is the guard"
    assert "issues: write" in t, "the rolling issue needs the scope ((pn))"
