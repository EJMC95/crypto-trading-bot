#!/usr/bin/env python3
"""
cleanup_legacy_bots.py — one-shot prune of stale pre-rename rows from `bot_pnl`.

Background: bots were renamed on 2026-06-20 to describe their function. The
`bot_pnl` table is keyed by bot name and nothing deletes old keys, so the old
rows (perps-bot, momo-bot, v4core, v5gated, v6swing, v7momo, v8momo) linger as
stale duplicates. The dashboard already filters them out at read time, but this
script removes them at the source so the table is clean.

Safe by construction:
  * Deletes ONLY names in LEGACY_BOTS (an explicit allow-list of dead names).
  * Dry-run by default — prints what it WOULD delete. Pass --apply to commit.
  * No-ops cleanly if DATABASE_URL is unset or Postgres is unreachable.

Usage:
    DATABASE_URL=postgres://...  python3 cleanup_legacy_bots.py          # preview
    DATABASE_URL=postgres://...  python3 cleanup_legacy_bots.py --apply  # delete
On Railway: run as a one-off command on any service that has DATABASE_URL set.
"""
import os
import sys

# Dead pre-rename names. Edit here if more legacy keys ever need pruning.
LEGACY_BOTS = [
    "perps-bot", "momo-bot",
    "v4core", "v5gated", "v6swing", "v7momo", "v8momo",
    # [2026-07-14 GHOST-EXPOSURE CLEANUP] Officially-retired bots (the
    # dashboard's RETIRED_ROWS set). Their services are stopped but their
    # frozen bot_pnl rows lingered — Bounce Catcher's held 6 phantom longs
    # and Trail Blazer's 16, pinning the fleet-risk light RED for hours
    # (see CROSS_BOT_ADVISORY_REVIEW_2026-07-14.md). Deletes the bot_pnl
    # snapshot row ONLY — trade ledgers (bot_trades / paper_trades /
    # venue_orders) and bot_state history are kept, same semantics as the
    # dashboard Manage panel's delete. A row reappears automatically if
    # its bot is ever revived (publish() upserts).
    "perps-rsi-meanrev", "perps-rsi-meanrev-lshadow",
    "perps-donchian-breakout", "perps-donchian-breakout-lighter",
    "perps-donchian-breakout-lshadow",
    # [2026-08-15 (nf)] the red-stop slate's prune half — see RETIRED_ROWS
    # in pnl_dashboard.py for the seven verdicts and overrides
    "pm-gillard-lshadow", "pm-abbott-lshadow",
    "pm-rudd-lshadow", "pm-morrison-lshadow",
    "crypto-intraday-15m-lshadow", "crypto-swing-daily-lshadow",
    "freqtrade-dad-lshadow",
    # [2026-08-13 (ma)] 🎫 Ticket Taker's LIVE row — pruned once
    # freqtrade-avo-maria-lighter publishes from the same sub-account
    # (verified at cutover: stamp e49ba8fa7ed2, baseline $62.80). Ledger
    # (56 closes) kept, as always. NOTE the old container can keep
    # publishing for a few minutes during Railway's rollout overlap and
    # re-upsert this row after a prune — harmless: RETIRED_ROWS hides it
    # from the grid, the totals AND /pnl.json either way, and the next
    # boot prunes again. The Taker SHADOW row is untouched.
    "lighter-ticket-taker-lighter",
    # [2026-07-17] 🌊 Tide Rider's LIVE row — 🎫 Ticket Taker took the slot on
    # the SAME service/keys/sub-account (the 11-Jul Trail Blazer -> Funding
    # Farmer shape). Both halves of a retirement, per the 16-Jul lesson that
    # hiding a row is not retiring it: RETIRED_ROWS hides the card, this PRUNES
    # the frozen row. It must be pruned, not just hidden — the row still holds a
    # stale $34.67 for a sub-account the TAKER now reports, so leaving it makes
    # the fleet double-count real money (and a frozen row with phantom holdings
    # is what pinned the fleet-risk light RED for hours on 14-Jul).
    # Safe to prune permanently: tide-rider-lighter-live now builds
    # Dockerfile.tickettaker, so nothing can ever re-upsert this id.
    # [2026-08-01 (ie)] THE -lshadow TWIN IS NOW LISTED, and the precondition
    # this note set has been met FIRST: `lighter_trend_bot.main` idles at boot
    # behind `TIDE_RIDER_RETIRED_OVERRIDE`, so it no longer publishes and
    # cannot re-upsert after a prune. Guard first, then prune — the order is
    # the whole lesson of the equities note below.
    # WHY: 22 days, 9 buys, ZERO sells, 0 closed trades, holding 6 of 6 and
    # 33% of the fleet-wide long budget against no measured claim. Pruning
    # the frozen row is what actually RETURNS those 6 long slots to the fleet
    # — `fleet_risk` counts a book's open longs from its bot_pnl row, so a
    # hidden-but-present row would keep consuming the budget invisibly, the
    # exact 14-Jul phantom-holdings failure that pinned the light RED.
    "crypto-trend-daily-lighter",
    "crypto-trend-daily-lshadow",
    # [2026-08-04] 🧲 SNAP BACK RETIRED (operator decision, OPERATOR_QUEUE.md
    # item 2 option A). The guard came FIRST, per the order this file teaches:
    # `lighter_dislocation_bot.main` idles at boot behind
    # `SNAPBACK_RETIRED_OVERRIDE`, so this prune is terminal rather than a
    # race with a live publisher. WHY: t=-2.97 on n=175 closes, mean
    # -0.281%/trade, both halves negative, ~-$1/day, 100% `converged` exits
    # since the widening, and the growth rail structurally cannot restrict it
    # (its binding entry floor ENTER_FLOOR_MULT is an unregistered literal;
    # every reachable lever motion loosens). Pruning frees the book's held
    # slots from every reader of bot_pnl — a hidden-but-present row keeps
    # consuming budget invisibly (the 14-Jul phantom-holdings failure).
    # Ledgers (paper_trades / venue_orders) and census history are KEPT.
    # Only the -lshadow row ever published (v1 refuses lighter_live).
    "lighter-dislocation-lshadow",
    # [2026-08-13 (lo)] 📊 Index Rider — I17 retirement, operator decision
    # ("get rid of what's not working"): 0 closes/44d, ~17.2 closes/yr
    # structural rate. Both halves per doctrine: RETIRED_ROWS hides, this
    # prunes. Ledgers kept; INDEX_RIDER_RETIRED_OVERRIDE=run resurrects.
    "equities-regime-lshadow",
    # [2026-08-14 (mr)] 🚀 crypto-breakout-4h — I17 retirement, operator
    # decision. The one book of NINE on the decision docket that survives
    # Benjamini-Hochberg at FDR 0.05 (p=0.0036 vs 0.0056): in-era n=15,
    # mean -1.745%/trade, t=-3.50, BOTH halves negative; all-time n=21,
    # t=-5.48. Both halves per doctrine: RETIRED_ROWS hides, this prunes —
    # and pruning is what actually frees its TWO held slots (TRX, LINK) from
    # every reader of bot_pnl, including the ENFORCED 20-long budget. A
    # hidden-but-present row keeps consuming budget invisibly (the 14-Jul
    # phantom-holdings failure). The guard came FIRST: the book is dropped
    # from `lighter_family_bot.live_strategies()`, so this prune is terminal
    # rather than a race with a live publisher — and it is ROW-scoped because
    # that module runs six other books. Ledgers kept;
    # BREAKOUT4H_RETIRED_OVERRIDE=run resurrects.
    "crypto-breakout-4h-lshadow",
    "perps-regime-switch", "perps-regime-switch-lshadow",
    "scanner-triangular-arb", "crypto-trendmomo-4h",
    # [2026-07-17 LIGHTER-ONLY CUT] operator: "i only want things running on
    # lighter". Both rows traded NON-Lighter venues; both bots now idle at boot
    # behind a code guard, so this prune is durable rather than a race with a
    # live writer. `perps-funding-carry` is the Yield Harvester's HL-DATA arm
    # only — its Lighter twin `perps-funding-carry-lshadow` keeps running and is
    # deliberately absent from this list. Ledgers kept (see the note above).
    "event-listing-sniper", "perps-funding-carry",
    "scanner-cross-exchange-arb",
    # [2026-07-14 LIGHTER-FIRST CUT] laptop stock bots retired on user
    # instruction — the Lighter ports (equities-*-lshadow) are the bots now.
    # NOTE their processes run on the operator's machine OUTSIDE this repo;
    # while they keep running, their rows re-upsert after each prune (hidden
    # by RETIRED_ROWS either way). Stop the laptop cron/processes to finish.
    "equities-momentum-alpaca", "equities-regime-ibkr",
    # [2026-07-17] 🏆 Stock Leaders RETIRED — the retirement was HALF DONE and
    # the dashboard hid the evidence. It was added to pnl_dashboard's
    # RETIRED_ROWS (so the row vanished from the grid) but NOT here, so the
    # bot_pnl snapshot lingered and went stale forever: invisible on the
    # dashboard, still sat in the table, still counted by anything that reads
    # bot_pnl directly rather than through RETIRED_ROWS. That is the exact
    # shape of the 14-Jul ghost-exposure incident above (frozen rows pinning
    # the risk light RED). Hiding a row is not retiring it — the two lists
    # must move together.
    # The bot itself refuses to start (MOMO_RETIRED guard), so this prune is
    # terminal rather than a race with a live publisher.
    "equities-momentum", "equities-momentum-lshadow",
    # [2026-07-14 KRAKEN RETIREMENT] the 8 Kraken paper rows — the -lshadow
    # twins are the fleet now (their rows are NOT in this list, nor is Tide
    # Rider's live row). Family ONLY_BOT services re-upsert until the
    # operator stops them in Railway; prunes stay idempotent.
    "crypto-trend-daily", "crypto-intraday-15m",
    "crypto-swing-daily", "crypto-breakout-4h",
    "freqtrade-mum", "freqtrade-dad",
    "freqtrade-avo-maria", "freqtrade-georgia",
]


def main():
    apply = "--apply" in sys.argv
    db = os.environ.get("DATABASE_URL", "").strip()
    if not db:
        print("DATABASE_URL not set — nothing to do.")
        return 0
    try:
        import psycopg2
    except Exception as e:  # noqa: BLE001
        print(f"psycopg2 not importable ({e}); install psycopg2-binary.")
        return 1

    try:
        conn = psycopg2.connect(db, connect_timeout=6)
    except Exception as e:  # noqa: BLE001
        print(f"connect failed ({e}); check DATABASE_URL.")
        return 1

    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_pnl') AS t")
            if cur.fetchone()[0] is None:
                print("bot_pnl table does not exist yet — nothing to prune.")
                return 0
            # Show which legacy rows are actually present.
            cur.execute(
                "SELECT bot, updated_at FROM bot_pnl WHERE bot = ANY(%s) ORDER BY bot",
                (LEGACY_BOTS,),
            )
            present = cur.fetchall()
            if not present:
                print("No legacy rows present — table already clean.")
                return 0
            print("Legacy rows found:")
            for bot, updated_at in present:
                print(f"  - {bot:<12} last updated {updated_at}")

            if not apply:
                print(f"\nDRY RUN — would delete {len(present)} row(s). "
                      f"Re-run with --apply to commit.")
                return 0

            cur.execute("DELETE FROM bot_pnl WHERE bot = ANY(%s)", (LEGACY_BOTS,))
            deleted = cur.rowcount
            conn.commit()
            print(f"\nDeleted {deleted} legacy row(s). Done.")
        return 0
    except Exception as e:  # noqa: BLE001
        conn.rollback()
        print(f"prune failed, rolled back ({e}).")
        return 1
    finally:
        conn.close()


def _prune_history():
    """[2026-07-16] boot-time bot_state_history retention sweep — the inline
    every-~200-writes prune in bot_pnl_store covers long-running containers;
    this covers each deploy deterministically."""
    try:
        import bot_pnl_store as store
        n = store.prune_history()
        if n is not None:
            print(f"bot_state_history: pruned {n} rows past retention.")
    except Exception as e:  # noqa: BLE001
        print(f"history prune skipped ({e}).")


if __name__ == "__main__":
    _prune_history()
    raise SystemExit(main())
