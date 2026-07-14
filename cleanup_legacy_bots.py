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
    "perps-regime-switch", "perps-regime-switch-lshadow",
    "scanner-triangular-arb", "crypto-trendmomo-4h",
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


if __name__ == "__main__":
    raise SystemExit(main())
