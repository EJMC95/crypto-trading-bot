#!/usr/bin/env python3
"""Apply the fleet rename to code (exact key-string replacement) — crypto repo."""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from rename_map import RENAME

REPO = "/Users/eamonjuaomartins-carrick/Claude/Projects/Crypto Trading Bot"
FILES = [
    "freqtrade_pnl_poller.py", "hyperliquid_perps_bot.py", "hyperliquid_momo_bot.py",
    "triangular_arb.py", "cross_exchange_arb.py", "listing_sniper.py",
    "pnl_dashboard.py", "dashboard_all.py", "trade_analyzer.py",
]
# longest keys first so no old key is a prefix of another during replace
ORDER = sorted(RENAME.keys(), key=len, reverse=True)
total = {}
for fn in FILES:
    p = os.path.join(REPO, fn)
    if not os.path.exists(p):
        print("MISSING", fn); continue
    s = open(p).read(); orig = s; cnt = 0
    for old in ORDER:
        new = RENAME[old][0]
        c = s.count(old)
        if c:
            s = s.replace(old, new); cnt += c; total[old] = total.get(old, 0) + c
    if s != orig:
        open(p, "w").write(s)
    print(f"{fn}: {cnt} replacements")
print("\nPer-key totals:", total)
