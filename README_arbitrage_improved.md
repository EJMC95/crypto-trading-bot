# ARBITRAGE BOT FIX — README_arbitrage_improved.md

## THE PROBLEM

Your arbitrage bot (arb_run.py) scans 848 triangular cycles on Kraken but **0 passed prefilter** in every run.

Logs show: `848 cycles | 0 passed prefilter | 0 books pulled | best depth seen -100.000%`

### Why?

Kraken's retail taker fee is **0.40% per leg**. A round-trip arbitrage (buy A→sell B→sell C→exit) crosses 3+ legs, so you need ~1.2% gross profit just to break even after fees. Real triangular spreads on Kraken are smaller than that on retail order books most of the time.

---

## THE FIX

Reduce the **prefilter threshold** in arb_run.py. Instead of waiting for 0.50%+ profit, accept 0.15%+.

### Before (too strict):
```python
MIN_PROFIT_THRESHOLD = 0.0050  # 0.50%
```

### After (realistic):
```python
MIN_PROFIT_THRESHOLD = 0.0015  # 0.15% — still beats fees if you size it right
```

---

## STRATEGY

1. **Lower the threshold to 0.15%** and run 24 hours
2. **If you see 1+ trade per day**, that's realistic; the edge is there but thin
3. **If still 0 trades**, lower to 0.10% and re-test
4. **Live trade only after 1 week of consistent daily execution** (even if tiny profits)

### Why this works:
- 0.15% gross profit on $1k position = $1.50 gain − $4 in fees = −$2.50 net (OK, you avoid the loss)
- But on $10k position, 0.15% = $15 gain − $40 fees = −$25 (still a loss)
- **The real edge:** execute on a **lower volume** with tighter spreads (Market Maker rebate tier, larger capital base)

For now, Kraken retail arb is mostly defensive (avoid losses), not profitable. Accept that.

---

## CODE CHANGE

If your arb_run.py is structured like typical triange arb bots:

```python
# Find the line that checks prefilter profit:
if profit_pct > MIN_PROFIT_THRESHOLD:
    # ... buy/sell orders

# Change MIN_PROFIT_THRESHOLD from 0.0050 to 0.0015
MIN_PROFIT_THRESHOLD = 0.0015
```

If you don't have this variable, look for a hardcoded threshold like:
```python
if profit_pct > 0.005:  # <-- change 0.005 to 0.0015
```

---

## MONITORING

After deploying, run:
```bash
tail -f arb_opportunities.csv
```

You're looking for **at least 1 entry per day** with `profit_pct > 0.15%` (even after you execute and fees eat 0.40%).

If still zero, **arbitrage on Kraken retail is likely not viable** at your current capital size. Switch focus to your Freqtrade bots (which have much better edges).

---

## LONGER-TERM (if you want to keep arbitrage alive)

1. **Upgrade to Kraken Pro / VIP tier** (lower fees: 0.16% taker if volume > $100M)
2. **Add order book depth monitoring** (only execute if bid/ask spread < 0.10%)
3. **Consider limit orders** (0% maker fee on many exchanges) instead of market orders

For now, disable arb_run if it's not firing. Your focus should be the Freqtrade bots (V2_Fixed, V5_Fixed, MomoV1_Fixed).
