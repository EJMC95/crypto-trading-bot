import psycopg2
DSN="postgresql://postgres:FzAXSnwGeyKeXeykUQTNHixyhZoWJRHo@thomas.proxy.rlwy.net:22526/railway"
c=psycopg2.connect(DSN).cursor()
print("===== bot_pnl full (all 12) =====")
c.execute("SELECT bot,status,equity,round(pnl_abs::numeric,2),open_trades,closed_trades,wins,losses,extra FROM bot_pnl ORDER BY bot")
for r in c.fetchall():
    ex=str(r[8])[:120] if r[8] else ""
    print(r[0],"| eq",r[2],"| pnl",r[3],"| o/c",r[4],r[5],"| W/L",r[6],r[7],"|",ex)
print("\n===== equity history: drawdown per bot =====")
c.execute("""SELECT bot, count(*), round(min(equity)::numeric,2), round(max(equity)::numeric,2),
  round((SELECT equity FROM bot_equity_history e2 WHERE e2.bot=e.bot ORDER BY ts DESC LIMIT 1)::numeric,2) last,
  min(ts), max(ts) FROM bot_equity_history e GROUP BY bot ORDER BY bot""")
for r in c.fetchall(): print(r)
print("\n===== stored analysis =====")
c.execute("SELECT strategy,updated_at FROM bot_trade_analysis")
for r in c.fetchall(): print(r)
