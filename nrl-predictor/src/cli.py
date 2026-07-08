"""Weekly-rhythm CLI (Build Spec §9 Phase 5). One command per step:

  python -m src.cli refresh              # data pulls (results history, NRL.com, odds snapshot)
  python -m src.cli predict              # phase-3 pipeline -> ratings + round predictions
  python -m src.cli preview              # round_preview.md (+ market columns if odds captured)
  python -m src.cli feed                 # write outputs/nrl.json
  python -m src.cli odds                 # live 4-book snapshot -> consensus, value flags, ledger log
  python -m src.cli grade --round 19     # Monday: settle the round, print Notion-ready summary

Scheduling stays with Cowork — these are the commands its weekly task runs.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def cmd_refresh(_: argparse.Namespace) -> None:
    from src.ingest import nrl_stats, results_history
    results_history.build()
    res = nrl_stats.build()
    m = res["matches"]
    print(f"matches: {len(m)} through {m['date'].max().date()}")
    if not res["fixtures_next"].empty:
        print(f"next round: {res['fixtures_next']['round'].iloc[0]}")


def cmd_predict(_: argparse.Namespace) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "run_phase3.py")], check=True)


def cmd_preview(_: argparse.Namespace) -> None:
    from src.publish import notion_preview
    print(f"-> {notion_preview.build()}")


def cmd_feed(_: argparse.Namespace) -> None:
    from src.publish import dashboard_feed, dashboard_html
    print(f"-> {dashboard_feed.build()}")
    print(f"-> {dashboard_html.build()}")


def cmd_odds(_: argparse.Namespace) -> None:
    subprocess.run([sys.executable, str(ROOT / "scripts" / "capture_odds.py")], check=True)


def cmd_grade(args: argparse.Namespace) -> None:
    import re

    import pandas as pd
    from src.eval import backtest as bt
    from src.eval import ledger
    from src.ingest import nrl_stats, teams

    season = args.season or date.today().year
    if args.auto:
        led = ledger.load()
        open_rounds = sorted(
            int(m.group(1)) for m in
            (re.match(r"Round (\d+)", r) for r in
             led.loc[led["settled_at"].isna(), "round"].unique())
            if m)
        if not open_rounds:
            print("grade --auto: no unsettled rounds in the ledger")
            return
        for rnd in open_rounds:
            args.round = rnd
            args.auto = False
            cmd_grade(args)
        return
    label = f"Round {args.round}"
    draw = nrl_stats._parse_draw_fixtures(
        nrl_stats.fetch_nrl_draw(season, args.round, refresh=True), season)
    played = draw[draw["match_state"].eq("FullTime")]
    if played.empty:
        print(f"{label}: no completed games yet — nothing to settle")
        return
    settled = ledger.settle_h2h(label, played)

    names = teams.id_to_name()
    print(f"# {label} graded — {date.today():%d %b %Y}\n")
    for g in played.itertuples(index=False):
        row = settled[(settled["home_id"] == g.home_id) & (settled["away_id"] == g.away_id)]
        note = ""
        if len(row):
            r = row.iloc[0]
            note = (f" | pick {names.get(r['selection'], r['selection'])} "
                    f"@ {r['market_price_at_log']:.2f} -> {r['result']} ({r['pnl_units']:+.2f}u)")
        print(f"- {names[g.home_id]} {g.home_score:.0f}–{g.away_score:.0f} "
              f"{names[g.away_id]}{note}")

    # Round Brier for the blend picks logged in the ledger.
    merged = settled.merge(
        played[["home_id", "away_id", "home_score", "away_score"]],
        on=["home_id", "away_id"], how="inner")
    if len(merged):
        # model_prob is the pick-side prob; convert to home-side for scoring
        p_home = pd.Series(
            [r.model_prob if r.selection == r.home_id else 1 - r.model_prob
             for r in merged.itertuples(index=False)])
        y = bt.outcome(merged)
        print(f"\nBlend Brier this round: {bt.brier(p_home.to_numpy(), y):.4f} "
              f"({len(merged)} games)")
    print()
    print(ledger.summary(label))
    print()
    print(ledger.summary())


def main() -> None:
    ap = argparse.ArgumentParser(prog="nrl", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("refresh").set_defaults(fn=cmd_refresh)
    sub.add_parser("predict").set_defaults(fn=cmd_predict)
    sub.add_parser("preview").set_defaults(fn=cmd_preview)
    sub.add_parser("feed").set_defaults(fn=cmd_feed)
    sub.add_parser("odds").set_defaults(fn=cmd_odds)
    g = sub.add_parser("grade")
    g.add_argument("--round", type=int)
    g.add_argument("--season", type=int, default=None)
    g.add_argument("--auto", action="store_true",
                   help="settle every round with unsettled ledger bets")
    g.set_defaults(fn=cmd_grade)
    args = ap.parse_args()
    if args.cmd == "grade" and not args.auto and args.round is None:
        ap.error("grade requires --round N or --auto")
    args.fn(args)


if __name__ == "__main__":
    main()
