import json, time, urllib.request, os, sys
SP = os.path.dirname(os.path.abspath(__file__)) + "/ohlc"
PAIRS = ["XBTUSD","ETHUSD","SOLUSD","ADAUSD","XRPUSD","LTCUSD","BCHUSD","LINKUSD","AVAXUSD","DOTUSD",
         "NEARUSD","ALGOUSD","XLMUSD","FILUSD","UNIUSD","AAVEUSD","INJUSD","SUIUSD","TIAUSD","OPUSD",
         "ARBUSD","ETCUSD","DOGEUSD","TRXUSD","ATOMUSD","MATICUSD","PEPEUSD","WIFUSD","BONKUSD"]
def fetch(pair, interval):
    url=f"https://api.kraken.com/0/public/OHLC?pair={pair}&interval={interval}"
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            d=json.loads(r.read())
        if d.get("error"): return None, d["error"]
        k=[k for k in d["result"] if k!="last"][0]
        return d["result"][k], None
    except Exception as e:
        return None, str(e)
ok=0
for iv,name in [(240,"4h"),(1440,"1d")]:
    for p in PAIRS:
        rows,err=fetch(p,iv)
        if rows:
            json.dump(rows, open(f"{SP}/{p}_{name}.json","w"))
            ok+=1
        else:
            print(f"SKIP {p} {name}: {err}", file=sys.stderr)
        time.sleep(1.1)
print(f"saved {ok} series to {SP}")
