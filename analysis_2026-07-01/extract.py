import psycopg2, csv, json, os
DSN="postgresql://postgres:FzAXSnwGeyKeXeykUQTNHixyhZoWJRHo@thomas.proxy.rlwy.net:22526/railway"
OUT=os.path.dirname(os.path.abspath(__file__))
conn=psycopg2.connect(DSN); cur=conn.cursor()

def dump(table):
    cur.execute(f"SELECT * FROM {table}")
    cols=[d[0] for d in cur.description]
    rows=cur.fetchall()
    p=os.path.join(OUT,f"{table}.csv")
    with open(p,"w",newline="") as f:
        w=csv.writer(f); w.writerow(cols)
        for r in rows: w.writerow(r)
    return cols,len(rows)

for t in ["bot_trades","paper_trades","bot_equity_history","bot_pnl","bot_trade_analysis"]:
    cols,n=dump(t)
    print(f"\n== {t}: {n} rows ==")
    print("cols:", cols)

# bot_trades summary
print("\n===== bot_trades per-bot summary =====")
cur.execute("""SELECT bot, count(*) total,
  sum(CASE WHEN is_open THEN 1 ELSE 0 END) open,
  sum(CASE WHEN NOT is_open THEN 1 ELSE 0 END) closed,
  min(open_ts) mn, max(open_ts) mx
  FROM bot_trades GROUP BY bot ORDER BY bot""")
for r in cur.fetchall(): print(r)

print("\n===== paper_trades per-bot summary =====")
cur.execute("SELECT bot, count(*), min(created_at), max(created_at) FROM paper_trades GROUP BY bot ORDER BY bot")
for r in cur.fetchall(): print(r)

print("\n===== bot_equity_history summary =====")
cur.execute("SELECT bot, count(*), min(ts), max(ts) FROM bot_equity_history GROUP BY bot ORDER BY bot")
for r in cur.fetchall(): print(r)
print("\nDONE. CSVs in", OUT)
