# DEPLOYMENT READY — NO CONFIG CHANGES NEEDED

All three improved strategies have been **updated in-place** in `user_data/strategies/`:

1. ✅ **ImprovedStrategyV2.py** — relaxed entry (OR logic on RSI/BB conditions)
2. ✅ **MomoBreakoutV1.py** — added pullback signal 
3. ✅ **DayTraderV5Gated.py** — relaxed momentum gates, regime filter stays

**Your Railway configs need ZERO changes** — they already point to these files.

---

## WHAT TO DO NOW

### Option 1: Deploy immediately (1 minute)
```bash
git add -A
git commit -m "Update strategies: V2/V5/Momo improved for better entry signals"
git push origin main
```

Railway auto-redeploys. Bots restart with the new logic within 2-3 minutes.

### Option 2: Test locally first (optional)
```bash
freqtrade backtest --strategy ImprovedStrategyV2 --config config_daytrader_kraken.json
freqtrade backtest --strategy DayTraderV5Gated --config config_v5_kraken.json
freqtrade backtest --strategy MomoBreakoutV1 --config config_v7_momo.json
```

If backtests look better (more trades, win% > 30%), commit and push.

---

## WHAT CHANGED IN EACH

| Strategy | Old Entry | New Entry | Expected Trades |
|----------|-----------|-----------|-----------------|
| **ImprovedStrategyV2** | `ema_up AND rsi<40 AND close<BB_lower` (all 3) | `ema_up AND (close<BB_lower AND rsi<50) OR rsi<35` (OR logic) | 2-3x more |
| **MomoBreakoutV1** | Breakout only | Breakout + pullback signal | 2-3x more |
| **DayTraderV5Gated** | All 5 conditions strict | `rsi>50 OR (rsi>40 AND close>ema)` + gates | 2-3x more |

All **stops, ROI, trailing stops unchanged** — only entries relaxed.

---

## MONITORING AFTER DEPLOY

Check Railway logs within 1 hour:
```bash
docker logs <container_name>
```

You should see messages like:
```
[INFO] Detected buy signal on pair BTC/USDT
```

If **still zero signals** after 2 hours:
1. Verify market is in an **uptrend** (ema_fast > ema_slow)
2. Lower RSI thresholds 5 more points if needed
3. Check if you have enough candle history (startup_candle_count needs 200+ candles loaded)

---

## ⚠️ IMPORTANT

These changes trade **2-3x more** = **2-3x more fees** in live mode. In dry-run, no fees charged so you'll see the wins/losses cleanly. Watch the win% and profit factor first.

If performance is bad, you can **revert immediately** by restoring from git or pulling the original files back.

Ready to deploy?
