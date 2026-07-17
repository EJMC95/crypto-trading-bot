import psycopg2
DSN="postgresql://postgres:FzAXSnwGeyKeXeykUQTNHixyhZoWJRHo@thomas.proxy.rlwy.net:22526/railway"
c=psycopg2.connect(DSN).cursor()

print("===== DAYTRADER-5m: exit_reason breakdown =====")
c.execute("""SELECT exit_reason, count(*), 
  sum(CASE WHEN profit_abs>0 THEN 1 ELSE 0 END) wins,
  round(avg(profit_ratio)::numeric*100,3) avg_pct,
  round(sum(profit_abs)::numeric,3) tot_abs,
  round(avg(duration_min)::numeric,1) avg_dur
  FROM bot_trades WHERE bot='intraday-daytrader-5m' GROUP BY exit_reason ORDER BY count(*) DESC""")
for r in c.fetchall(): print(r)

print("\n===== DAYTRADER-5m: enter_tag breakdown =====")
c.execute("""SELECT enter_tag, count(*), sum(CASE WHEN profit_abs>0 THEN 1 ELSE 0 END) wins,
  round(sum(profit_abs)::numeric,3) tot FROM bot_trades WHERE bot='intraday-daytrader-5m' GROUP BY enter_tag ORDER BY count(*) DESC""")
for r in c.fetchall(): print(r)

print("\n===== DAYTRADER-5m: by pair =====")
c.execute("""SELECT pair, count(*), sum(CASE WHEN profit_abs>0 THEN 1 ELSE 0 END) wins,
  round(sum(profit_abs)::numeric,3) tot FROM bot_trades WHERE bot='intraday-daytrader-5m' GROUP BY pair ORDER BY tot""")
for r in c.fetchall(): print(r)

print("\n===== DAYTRADER-5m: profit distribution & duration =====")
c.execute("""SELECT round(min(profit_ratio)::numeric*100,2), round(max(profit_ratio)::numeric*100,2),
 round(avg(profit_ratio)::numeric*100,3), round(avg(duration_min)::numeric,1),
 round(sum(profit_abs)::numeric,3), count(*) FROM bot_trades WHERE bot='intraday-daytrader-5m'""")
print("min% max% avg% avgDur totAbs n:", c.fetchone())

print("\n===== DAYTRADER-5m: wins vs losses avg size =====")
c.execute("""SELECT CASE WHEN profit_abs>0 THEN 'win' ELSE 'loss' END, count(*),
 round(avg(profit_abs)::numeric,3), round(avg(duration_min)::numeric,1)
 FROM bot_trades WHERE bot='intraday-daytrader-5m' GROUP BY 1""")
for r in c.fetchall(): print(r)

print("\n===== MOMO bots trades =====")
c.execute("""SELECT bot,pair,round(profit_ratio::numeric*100,2),round(profit_abs::numeric,3),exit_reason,duration_min,enter_tag FROM bot_trades WHERE bot LIKE 'momo%' ORDER BY bot""")
for r in c.fetchall(): print(r)

print("\n===== paper_trades (listing-sniper etc) =====")
c.execute("SELECT bot,pair,round(pnl_abs::numeric,3),pnl_pct,reason,opened_at,closed_at FROM paper_trades ORDER BY bot,opened_at")
for r in c.fetchall(): print(r)

print("\n===== bot_trade_analysis (stored) =====")
c.execute("SELECT strategy,updated_at,left(analysis,400) FROM bot_trade_analysis")
for r in c.fetchall(): print(r[0],r[1],"\n",r[2],"\n---")
