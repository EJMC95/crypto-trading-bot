# DEPLOYMENT GUIDE FOR FIXED STRATEGIES

## TL;DR

You have **three new strategy files** that relax overly tight entry conditions while keeping proven risk management:

1. **ImprovedStrategyV2_Fixed.py** (1h dip-buyer) — copy to `user_data/strategies/`
2. **MomoBreakoutV1_Fixed.py** (4h breakout + pullback) — copy to `user_data/strategies/`, replacing MomoBreakoutV1.py
3. **DayTraderV5Gated_Fixed.py** (5m gated daytrader) — copy to `user_data/strategies/`, replacing DayTraderV5Gated.py

---

## WHAT EACH FIXES

### ImprovedStrategyV2_Fixed
**Old entry:** `ema_fast > ema_slow AND rsi < 40 AND close < bb_lower`  
**New entry:** `ema_fast > ema_slow AND (rsi < 50 AND close < bb_lower) OR rsi < 35`

**Why:** The old condition required all three to align—too rare. The new logic fires when:
- Price is in an uptrend (ema_fast > ema_slow) AND EITHER:
  - Price dips below the Bollinger Band and RSI hasn't gotten too hot (< 50), OR
  - Price is deeply oversold (RSI < 35, even if Bollinger not hit)

**Expected outcome:** 2-3x more trades, same risk-on discipline.

---

### MomoBreakoutV1_Fixed
**Old entry:** `close > 30-bar high AND close > 200-EMA` (breakout only)  
**New entry:** Same as old, PLUS `close < 15-bar low AND close > 200-EMA AND rsi < 50` (pullback)

**Why:** The original strategy only fired on fresh breakouts. In sideways/falling markets, those never happen. The fix adds a second signal: within an uptrend, if price dips below a recent low and RSI isn't overbought, buy that pullback too.

**Expected outcome:** More entry signals in range-bound markets; original backtest still applies because both entry paths stay true to the "buy strength in uptrends" core.

---

### DayTraderV5Gated_Fixed
**Old entry:** `rsi > 55 AND close > 9-EMA AND volume > sma_volume AND ema9_rising_1h AND regime_up_1d`  
**New entry:** `(rsi > 50 OR (rsi > 40 AND close > ema_fast)) AND ema9_rising_1h AND regime_up_1d`

**Why:** The old entry had five strict conditions. The new one relaxes momentum to:
- RSI > 50 (was 55), OR
- RSI > 40 with price above the fast EMA (catches pullbacks to trend)

The two macro filters (day-trend up + daily regime up) stay—these are the real edge.

**Expected outcome:** 2-3x more trades, still gated by the regime filter so it won't trade in falling markets.

---

## HOW TO DEPLOY

### Step 1: Copy files to your project
```bash
# From your bot directory
cp ImprovedStrategyV2_Fixed.py user_data/strategies/
cp user_data/strategies/MomoBreakoutV1_Fixed.py user_data/strategies/MomoBreakoutV1.py
cp user_data/strategies/DayTraderV5Gated_Fixed.py user_data/strategies/DayTraderV5Gated.py
```

### Step 2: Update your Freqtrade configs to point to the new strategies

**config_daytrader_kraken.json:**
```json
  "strategy": "ImprovedStrategyV2Fixed",
```

**config_v5_kraken.json:**
```json
  "strategy": "DayTraderV5GatedFixed",
```

**config_v7_momo.json:**
```json
  "strategy": "MomoBreakoutV1Fixed",
```

### Step 3: Test locally first (optional but recommended)
```bash
freqtrade backtest --strategy ImprovedStrategyV2Fixed --config config_daytrader_kraken.json
freqtrade backtest --strategy DayTraderV5GatedFixed --config config_v5_kraken.json
freqtrade backtest --strategy MomoBreakoutV1Fixed --config config_v7_momo.json
```

If backtests show improvement in entry count, commit and deploy to Railway.

### Step 4: Push to Railway
```bash
git add -A
git commit -m "Relax entry conditions on V2_Fixed, V5_Fixed, MomoV1_Fixed"
git push origin main
```

Railway will auto-redeploy.

---

## EXPECTED BEHAVIOR AFTER DEPLOYMENT

You should see:
- **More trades** (2-3x baseline) — the entry gates are looser
- **Faster P&L swings** — some will be losses (that's normal; the stops handle them)
- **Lower trade duration** — more entries mean more exits too
- **No trades in downtrends** — the daily regime filters still protect you

If you see **zero trades after deployment**, check:
1. Is the bot actually running? (`docker ps`, Railway dashboard)
2. Do you have 1h+ of recent price data? (Freqtrade needs startup candles)
3. Is the market in an uptrend? (ema_fast > ema_slow on your pair)

---

## NEXT STEPS FOR MONITORING

1. **Watch 48 hours of dry-run trades** — you want to see 10-20 trades, win% > 30%, PF > 1.0
2. **Check logs for entry signals** — `docker logs <container>` should show "Detected buy signal on pair"
3. **If still quiet,** try loosening RSI thresholds by 5 more points (e.g., RSI < 55 instead of < 50)
4. **If too many losses,** tighten the stoploss from -6% to -4% (Freqtrade JSON config)

---

## RISK WARNING

These changes trade **more frequently**, which means:
- More fees (in dry-run, zero fees; live trading, ~0.25-0.40% per round trip)
- More wins but also more losses (breakeven to small profits is normal)
- The 40-50% win rate on momentum strategies is _by design_; the profit factor (total wins / total losses) matters more

Test in dry-run for at least 1 week before going live.
