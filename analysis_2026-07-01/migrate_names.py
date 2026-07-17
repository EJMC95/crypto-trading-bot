#!/usr/bin/env python3
"""Migrate P&L history from old bot keys -> new keys (conflict-safe)."""
import os, sys, psycopg2
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rename_map import RENAME

DSN = "postgresql://postgres:FzAXSnwGeyKeXeykUQTNHixyhZoWJRHo@thomas.proxy.rlwy.net:22526/railway"
# table -> unique key columns (besides bot) used to avoid collisions
TABLES = {
    "bot_pnl":            [],            # unique on bot alone
    "bot_trades":         ["open_ts"],
    "paper_trades":       ["trade_id"],
    "bot_equity_history": ["ts"],
}
conn = psycopg2.connect(DSN); conn.autocommit = False; cur = conn.cursor()

def counts():
    out = {}
    for t in TABLES:
        cur.execute(f"SELECT count(*) FROM {t}"); out[t] = cur.fetchone()[0]
    return out

print("Before:", counts())
for old, (new, _label) in RENAME.items():
    for t, keys in TABLES.items():
        if keys:
            cond = " AND ".join([f"t2.{k}=t1.{k}" for k in keys])
            # move rows that won't collide with an existing new-key row
            cur.execute(f"""UPDATE {t} t1 SET bot=%s
                            WHERE t1.bot=%s AND NOT EXISTS
                            (SELECT 1 FROM {t} t2 WHERE t2.bot=%s AND {cond})""",
                        (new, old, new))
        else:
            cur.execute(f"UPDATE {t} SET bot=%s WHERE bot=%s AND NOT EXISTS "
                        f"(SELECT 1 FROM {t} x WHERE x.bot=%s)", (new, old, new))
        # drop any leftover old-key rows that collided (new-key version already exists)
        cur.execute(f"DELETE FROM {t} WHERE bot=%s", (old,))
conn.commit()
print("After :", counts())
# show any residual OLD keys anywhere (should be none)
resid = {}
for t in TABLES:
    cur.execute(f"SELECT DISTINCT bot FROM {t}")
    for (b,) in cur.fetchall():
        if b in RENAME: resid.setdefault(t, []).append(b)
print("Residual OLD keys:", resid or "NONE")
print("Distinct bots now in bot_equity_history:")
cur.execute("SELECT bot, count(*) FROM bot_equity_history GROUP BY bot ORDER BY bot")
for r in cur.fetchall(): print("  ", r[0], r[1])
