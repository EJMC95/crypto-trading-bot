# Crypto Research Log

Automated, READ-ONLY/ADVISORY market scan + bot research review (~every 2h). Dry-run/paper bots. Not financial advice. All tweaks below are PROPOSALS for the user to action — nothing here is executed.

---

## 2026-06-27 11:42 UTC

### ** ACTIONABLE **
1. **V5 `intraday-daytrader-5m` still bleeding — reaffirms 22-Jun retirement call.** 69 closed trades, **W=8 / L=61 (11.6% win rate)**, cum −$10.80 (the *only* contributor to the −$22.83 weekly/monthly total alongside v8). Recent exits are death-by-a-thousand-cuts trailing-stops on illiquid alts (ALLO, AKT, VVV, LUNC, ZEC). PROPOSAL: pause V5, or restrict its pairlist to liquid majors + widen the entry gate — it is churning, not trading. *(Evidence: trades.json, periods.json; matches REVALIDATION_2026-06-22 "retire V5".)*
2. **v8 `momo-breakout-alt` is the worst weekly performer (−$11.33, 0/2 wins) and still holds 2 open trades into a risk-off tape.** Breakouts are failing on entry. PROPOSAL: gate v8 off in risk-off the way V7 is (BTC<200d / breadth filter), or treat as unvalidated and shrink stake. *(Evidence: pnl.json equity 979.3; periods.json 2026-06-24 −11.33.)*
3. **Regime at an extreme, not a shift.** F&G **15 (Extreme Fear)**, BTC ~$58–60k (lowest since 2024), breadth **1/15 above 200d**. No action needed for the trend bots — they are correctly defensive (see below) — but worth noting the tape is stretched and a short-squeeze bounce is a live risk for any shorts/over-tight stops.

### Quant snapshot
- **Regime:** RISK-OFF / downtrend. F&G 15 (Extreme Fear). BTC dominance 55.8%, total mcap $2.16T (+1.4% 24h).
- **Breadth:** 1/15 of basket above 200d SMA; 2/15 in a 50>200 golden cross. Only **TRX** is in an uptrend (↑ vs 200d, golden cross); XLM also shows a golden cross but is −18.3% 7d.
- **Majors 30d:** BTC −18.2%, ETH −21.4%, SOL −12.7%, XRP −19.7%, BNB −11.8%. Vol elevated (BTC +42% annualised, XLM +141%).

### News (last few hours, qualitative)
- **Macro/Fed is the driver.** The 18-Jun FOMC held at 3.50–3.75% but *removed easing language* → firmer DXY + Treasury yields, a headwind for non-yielding BTC. Selloff framed as macro risk-aversion, not a crypto-specific shock. ([crypto.news](https://crypto.news/crypto-market-selloff-deepens-as-warsh-fed-and-iran-uncertainty-hit-bitcoin-wintermute/), [tradersunion](https://tradersunion.com/news/cryptocurrency-news/show/2495913-bitcoin-selloff-etf-outflows-fed-inflation/))
- **ETF outflows persist** — ~6 straight weeks; −$692M single-day on 25-Jun (largest since 27-May), ≈ −$5.96B over 30d; ETF holdings growth "basically zero" so funds now add to sell-side supply. ([investing.com](https://www.investing.com/analysis/bitcoin-falls-as-record-etf-outflows-and-strategy-sale-hit-sentiment-200681446), [bitcoinfoundation](https://bitcoinfoundation.org/news/crypto-etfs-news/crypto-etfs-june/))
- **Leverage flush / liquidations** ongoing (24h longs dominant; 7d BTC liqs ~$482M). Some dip-buying (Strive +759 BTC ~$50M @ $65,850). Iran + "Warsh Fed" political uncertainty cited as added pressure. ([ambcrypto](https://ambcrypto.com/bitcoin-falls-below-60k-as-etf-outflows-and-1-48b-liquidations-fuel-crypto-selloff/), [coindesk](https://www.coindesk.com/markets/2026/06/25/bitcoin-plunges-to-new-multi-year-low-of-usd58-000-but-a-short-squeeze-setup-emerges))

### Per-bot read (vs validated expectations)
| Bot | Equity | Open | Closed | W/L | Read |
|-----|--------|------|--------|-----|------|
| trend-golden-cross (V4) | 994.07 | 1 | 0 | 0/0 | ✅ As designed — mostly cash in downtrend; single open is consistent with TRX being the lone major uptrend. |
| swing-dip-buyer (V6) | 1000.00 | 0 | 0 | 0/0 | ✅ As designed — fully in cash, not catching a falling knife. |
| momo-breakout-4h (V7) | 999.30 | 0 | 1 | 0/1 | ✅ As designed — one failed breakout (−0.70), now flat. Correctly suppressed in risk-off. |
| momo-breakout-alt (v8) | 979.30 | 2 | 2 | 0/2 | ⚠️ Diverges — taking failing breakouts (−11.33), still holding 2 into weakness. See ACTIONABLE #2. |
| intraday-daytrader-5m (V5) | 989.23 | 1 | 69 | 8/61 | ⚠️ Over-trading/churning (−10.80, 11.6% WR). See ACTIONABLE #1. |
| listing-sniper | — | 1 | 1 | 0/1 | Research/scanner; stale 198s, −50 placeholder. No action. |
| scanners (triangular-arb, cross-exchange-arb) | n/a | — | — | — | Scanning only; best cross-exch top 4.7%. No fills. No action. |

**Verdict:** The validated "keep" trend bots (V4 / V6 / V7) are behaving exactly as their design expects for this risk-off regime — defensive and mostly in cash. The two flagged bleeders (V5, v8) match prior concerns; both proposals above are consistent with REVALIDATION_2026-06-22 rather than new findings. No regime shift, no stale/halted *trading* bots (only scanners/stock bots show expected staleness). **No change is strictly warranted on the keepers; the two PROPOSALS target the known underperformers.**

---

## 2026-06-28 04:38 UTC

### ** ACTIONABLE **
1. **V5 `intraday-daytrader-5m` keeps bleeding — re-confirms 22-Jun retirement call.** Now **79 closed, W=9 / L=70 (11% win rate)**, cum **−$12.99** — still the dominant contributor to the −$25.03 weekly/monthly total. Exit-reason mix is the tell: **63 trailing-stop / 10 stop-loss / 4 exit-signal / 2 ROI** — death-by-a-thousand-cuts churn, not edge. PROPOSAL (unchanged): pause V5, or restrict pairlist to liquid majors + widen the entry gate. *(Evidence: trades.json exit_reason counts, periods.json.)*
2. **v8 `momo-breakout-alt` still −$11.33 (0/2), still holding 2 open trades into a risk-off tape.** No new fills since 24-Jun (last close 2026-06-24 20:01) so it's now just carrying losers, not adding — but it remains un-gated for regime. PROPOSAL (unchanged): apply V7's risk-off breakout suppression (BTC<200d / breadth) to v8, or treat as unvalidated and shrink stake. *(Evidence: pnl.json equity 977.54; periods.json 2026-06-24 −11.33.)*
3. **EU MiCA licensing deadline is 1 Jul 2026 (3 days out).** Unlicensed firms lose EU-customer access → possible thin-liquidity / delisting air-pockets in smaller alts over the next few sessions. Watch-item only for the 15-coin baskets (V6/V7/v8) — favours sticking to the most liquid names. *(Source: tradingkey / general MiCA coverage.)*

### Quant snapshot
- **Regime:** RISK-OFF / downtrend (unchanged). **F&G 18 (Extreme Fear)** — up from 15 at 11:42 but still extreme. BTC dominance **55.9%**, total mcap **$2.16T (−0.2% 24h)**.
- **Breadth:** **1/15** of basket above 200d SMA; **2/15** in a 50>200 golden cross. Only **TRX** is in a genuine uptrend (↑ vs 200d + golden cross, −1.6% 7d / −6.3% 30d — the most resilient name). XLM shows a golden cross but is −17.6% 7d (rolling over).
- **Majors 30d:** BTC −18.2%, ETH −21.9%, SOL −13.8%, XRP −21.2%, BNB −13.4%. Vol still elevated (BTC +42% ann., XLM +101%, BCH +89%).

### News (last few hours, qualitative)
- **Record ETF outflows — the structural overhang.** US spot BTC ETFs shed **~$3.4B in a single week** (largest since 2024 launch); a **13-day outflow streak ≈ −$4.3B / −59k BTC**, 20-day trailing −$5.42B / −73k BTC (Galaxy). Funds are now net sell-side supply. Some analysts frame it as "more cyclical than structural." ([beincrypto](https://beincrypto.com/bitcoin-etf-outflows-record-streak-june-2026/), [coinfomania](https://coinfomania.com/bitcoin-etf-outflows-june-2026-record-selloff/), [investing.com](https://www.investing.com/analysis/bitcoins-34-billion-etf-bleed-looks-more-cyclical-than-structural-200681474))
- **Macro is the driver.** May **PCE came in hot at 4.1% YoY** (vs 3.8% prior) → cut near-term Fed cut odds, firmer DXY/yields, broad risk-off. Open interest contracted ~18.7%. ([tradingkey](https://www.tradingkey.com/analysis/cryptocurrencies/btc/261945885-crypto-bitcoin-btc-price-crashing-usd-strategy-fed-tradingkey), [stealthex](https://stealthex.io/blog/why-is-bitcoin-dropping/))
- **Liquidations / forced selling** persist: ~**$1.48B** 24h liq in the latest leg below $60k; earlier $1.26B across 209k traders on the 26-Jun dip to ~$58k. BTC now ~$60–63k, fragile consolidation; support $62–63k, resistance $65k. ([ambcrypto](https://ambcrypto.com/bitcoin-falls-below-60k-as-etf-outflows-and-1-48b-liquidations-fuel-crypto-selloff/), [ccn](https://www.ccn.com/news/crypto/bitcoin-price-crash-58k-1-26b-liquidations-55k/))
- **Regulation:** EU MiCA licensing cutoff **1 Jul 2026** (see ACTIONABLE #3); March SEC/CFTC digital-asset classification framework remains the structural US backdrop.

### Per-bot read (vs validated expectations)
| Bot | Equity | Open | Closed | W/L | Read |
|-----|--------|------|--------|-----|------|
| trend-golden-cross (V4) | 994.89 | 1 | 0 | 0/0 | ✅ As designed — mostly cash in downtrend; lone open consistent with TRX being the only major uptrend. |
| swing-dip-buyer (V6) | 1000.00 | 0 | 0 | 0/0 | ✅ As designed — fully in cash, not catching the falling knife. |
| momo-breakout-4h (V7) | 999.30 | 0 | 1 | 0/1 | ✅ As designed — one failed breakout (−0.70), now flat; correctly suppressed in risk-off. |
| momo-breakout-alt (v8) | 977.54 | 2 | 2 | 0/2 | ⚠️ Diverges — un-gated; carrying 2 losers into weakness (−11.33). See ACTIONABLE #2. |
| intraday-daytrader-5m (V5) | 986.87 | 1 | 79 | 9/70 | ⚠️ Churning (−12.99, 11% WR, 63 trailing-stops). See ACTIONABLE #1. |
| hl-perps-rsi / hl-momo-breakout | 1000.65 / 993.61 | 1 / 7 | — | — | Perps dry-run; hl-momo holding 7 into risk-off, −6.39 — monitor (no validated baseline). |
| listing-sniper | — | 1 | 1 | 0/1 | Research/scanner; stale, −50 placeholder. No action. |
| scanners (triangular-arb, cross-exchange-arb) | n/a | — | — | — | Scanning only; best cross-exch top 3.5%. No fills. No action. |

**Verdict:** No regime shift (F&G 15→18, still Extreme Fear; breadth still 1/15). The validated "keep" trend bots **V4 / V6 / V7 are behaving exactly to design** — defensive, mostly in cash. The only bleeders remain the known underperformers **V5 and v8**, matching REVALIDATION_2026-06-22; proposals are reaffirmations, not new findings. New watch-item: **EU MiCA 1-Jul deadline** could thin alt liquidity for the baskets. **No change strictly warranted on keepers.**

---

### Footnote — V6/V7 health verification (live API, ~05:00 UTC follow-up)
Confirmed the two cash-sitting keepers are **eligible-but-idle, NOT stale/broken.** Pulled live freqtrade analysis from the local Docker bots (v6swing :8086, v7momo :8087):
- **Containers healthy:** dry-run active, whitelist 15/15 loading hourly, candles fresh (V6 daily last 27-Jun, V7 4h last 28-Jun), no strategy/indicator exceptions. (Only error = cosmetic CoinMarketCap 429 on V7 fiat-display — no trading impact.)
- **V6 swing (BTC 1d):** `ema50 67,507 < ema200 76,825` → uptrend gate vetoes entry despite RSI 31.8 (oversold). `enter_long=None`. `ema200` is a real value (not NaN) → 200-daily-candle history loaded fine; silent-data-failure mode ruled out. This is the falling-knife protection working as designed.
- **V7 momo (BTC 4h):** `close 60,123 < ema_trend(200) 65,648` → both breakout & pullback entries blocked at the 200-EMA gate; Donchian `dc_high 64,200` unbroken. `enter_long=None`.
- **Concrete re-eval triggers (live):** V6 fires when BTC ema50 reclaims ema200 (~28% apart now — weeks off barring a strong rally); V7 fires when price reclaims 4h ema200 ≈ **65.6k** (~9% above spot) + breaks the Donchian high — V7 will likely re-engage first on any bounce.
- **Decision:** LEAVE V6/V7 untouched (no entry-gate loosening — it would re-introduce the validated falling-knife failure mode). Review on the regime triggers above, not a calendar. Tuning effort stays on the over-trading V5/v8.

---

## 2026-06-29 00:40 UTC

### ** ACTIONABLE **
1. **Sentiment hits a new local low — F&G 12 (Extreme Fear), down 18→12 since yesterday.** Deeper fear, not a regime *shift*: breadth still 1/15 above 200d, BTC still contained ~$60k (7d −7.5%, was −5.5%). Trend keepers stay correctly defensive. Flag: tape is more stretched → short-squeeze bounce risk is rising for anything over-leveraged short / over-tight. *(Evidence: market_snapshot_latest.md F&G 12; periods.json.)*
2. **V5 `intraday-daytrader-5m` is bleeding LESS — the longer-cooldown change (commit 2c971bb) appears to be working.** Still ugly cumulatively (87 closed, W9/L78 = 10.3% WR, −$14.16) BUT daily loss is shrinking fast: −3.05 (24th) → −1.67 → −3.03 → −1.04 → **−0.12 today on just 1 trade**. Fewer trades, smaller cuts. PROPOSAL: **keep the cooldown change and re-measure in ~1 week** before any pause/retire decision — the fix may be salvaging it. (Prior call was retire; this is the first evidence the gate+cooldown is curbing the churn.) *(Evidence: periods.json daily series; trades.json exit_reason = mostly trailing_stop.)*
3. **NEW divergence — `hl-momo-breakout` is holding 16 open longs into Extreme Fear (was 7 yesterday).** Unvalidated HL perps dry-run, equity 995.67 (−$4.33), now loading up as the tape deepens risk-off. No validated baseline to gate against, but 16 concurrent breakout longs at F&G 12 is the opposite of what the validated trend bots are doing. PROPOSAL: add a regime/breadth filter (BTC<200d ⇒ suppress) like V7, or cap concurrent positions — monitor next run for whether these 16 turn into a bigger drawdown. *(Evidence: pnl.json hl-momo-breakout open_trades=16.)*

### Quant snapshot
- **Regime:** RISK-OFF / downtrend (unchanged, deepening). **F&G 12 (Extreme Fear)** — new local low (15→18→12). BTC dominance **55.7%**, total mcap **$2.13T (−1.2% 24h)**.
- **Breadth:** **1/15** above 200d SMA; **2/15** in a 50>200 golden cross. **TRX** remains the only genuine uptrend (↑ vs 200d + golden cross, −3.6% 7d / −7.5% 30d — most resilient). XLM golden-cross but −15.9% 7d (rolling over).
- **Majors 30d:** BTC −19.9%, ETH −22.9%, SOL −14.4%, XRP −22.7%, BNB −23.7% (BNB notably worse this run). Vol elevated (BTC +42% ann., XLM +94%, BCH +89%). AVAX the only green 7d name (+2.7%).

### News (last few hours, qualitative)
- **Macro still the driver, turning more hawkish.** Hot May PCE (4.1% YoY) + **Minneapolis Fed's Kashkari now projecting a rate HIKE before end-2026** → firmer DXY/yields, broad risk-off; not a crypto-specific shock. ([stealthex](https://stealthex.io/blog/why-is-bitcoin-dropping/), [bitcoinnewsdigest](https://bitcoinnewsdigest.substack.com/p/bitcoin-news-digest-june-28-2026))
- **ETF outflows = the structural overhang.** ~13-day outflow streak ≈ −$4.3B; assets across funds down to ~$82.8B from $107.8B (mid-May). Funds are net sell-side supply; some frame it "more cyclical than structural." ([beincrypto](https://beincrypto.com/bitcoin-etf-outflows-record-streak-june-2026/), [investing.com](https://www.investing.com/analysis/bitcoins-34-billion-etf-bleed-looks-more-cyclical-than-structural-200681474))
- **Liquidations** persist: 26-Jun dip to ~$58k flushed ~$1.26B / 209k traders; BTC now consolidating near $60k. ([ccn](https://www.ccn.com/news/crypto/bitcoin-price-crash-58k-1-26b-liquidations-55k/), [news.bitcoin.com](https://news.bitcoin.com/bitcoin-hits-59018-after-a-5-drop-forcing-237m-in-long-liquidations/))
- **Regulation/structural (28-Jun):** House passed a **CBDC moratorium** (no Fed CBDC until end-2030); Fed VC **Bowman wound down the dedicated crypto-supervision program**; **Circle faces a class-action** over a $280M DeFi exploit (USDC/stablecoin-rails risk — watch-item, not basket-direct). EU MiCA licensing cutoff was **1 Jul 2026** (now imminent → possible thin-liquidity air-pockets in smaller alts). ([bitcoinnewsdigest](https://bitcoinnewsdigest.substack.com/p/bitcoin-news-digest-june-28-2026))

### Per-bot read (vs validated expectations)
| Bot | Equity | Open | Closed | W/L | Read |
|-----|--------|------|--------|-----|------|
| trend-golden-cross (V4) | 994.45 | 1 | 0 | 0/0 | ✅ As designed — mostly cash; lone open consistent with TRX being the only major uptrend. |
| swing-dip-buyer (V6) | 1000.00 | 0 | 0 | 0/0 | ✅ As designed — fully in cash, not catching the falling knife. |
| momo-breakout-4h (V7) | 999.30 | 0 | 1 | 0/1 | ✅ As designed — one failed breakout (−0.70), now flat; correctly suppressed in risk-off. |
| momo-breakout-alt (v8) | 977.04 | 2 | 2 | 0/2 | ⚠️ Un-gated; still carrying 2 losers into weakness (−11.33). No new fills since 24-Jun. See ACTIONABLE #... (v8 proposal unchanged: apply V7 regime suppression). |
| intraday-daytrader-5m (V5) | 985.83 | 1 | 87 | 9/78 | ⚠️→🔁 Churn (−14.16, 10% WR) BUT daily bleed shrinking sharply post-cooldown change. See ACTIONABLE #2. |
| hl-momo-breakout | 995.67 | 16 | — | — | ⚠️ NEW — 16 open longs into F&G 12 (was 7). Unvalidated perps; monitor. See ACTIONABLE #3. |
| hl-perps-rsi | 1001.30 | 1 | — | — | OK — +1.30, single position. No action. |
| listing-sniper | — | 3 | 2 | 1/1 | Research/scanner; stale 29min. No action. |
| scanners (triangular-arb, cross-exchange-arb) | n/a | — | — | — | Scanning only; best cross-exch top 4.1%, triangular best depth −0.9%. No fills. No action. |
| stock bots (ikbr, alpaca) | — | — | — | — | Stale (expected, weekend/off-hours); out of crypto scope. |

**Verdict:** No regime shift — F&G deepened (18→12) but structure is unchanged (breadth 1/15, BTC ~$60k). Validated keepers **V4 / V6 / V7 behaving exactly to design** (defensive, mostly cash). Two genuinely new reads this run: (a) **V5's loss rate is shrinking** — first evidence the cooldown fix is curbing churn, so *defer* the retire decision and re-measure; (b) **hl-momo-breakout loaded to 16 longs into extreme fear** — an unvalidated bot diverging from the defensive keepers, worth a regime gate + monitoring. Everything else is a reaffirmation of REVALIDATION_2026-06-22. PROPOSALS only — no actions taken; dry-run/paper, not financial advice.

---

## 2026-06-29 03:32 UTC — Market scan + bot research review

### ** ACTIONABLE **
1. **F&G hits 12 (cycle low) BUT price held the 26-Jun lows for 3 sessions → sentiment-vs-price divergence.** BTC ~$60k, total mcap $2.14T, both ~flat 24h while fear deepened (18→12). This is a *watch-item, possible basing* setup, not a confirmed regime change. PROPOSAL: no action yet — let the validated keepers (V4/V6/V7) stay defensive; if breadth flips (any majors reclaim 200d / first 50>200 crosses beyond TRX+XLM), that's the signal to expect V6/V7 re-entries. Re-measure next run.
2. **hl-momo-breakout drawdown deepening on its 16 open longs.** Equity $985.26 (was ~$995.67 last run, −$14.74 abs) while holding 16 longs into F&G 12. Confirms last run's divergence flag: this unvalidated perps bot is the one keeper-cohort outlier still adding/holding directional longs in deep risk-off. PROPOSAL (unchanged): add a regime gate mirroring V7's breakout-suppression; continue monitoring. No action taken.
3. **V5 (intraday-daytrader-5m) bleed continues to shrink — defer retire decision again.** Daily P&L: −3.05 (25th) → −1.67 (26th) → −3.03 (27th) → −1.04 (28th) → −0.22 (29th, 2 trades). WR still poor (9W/79L ≈ 10%, all exits trailing_stop_loss), but the post-cooldown downtrend in daily loss is holding for a 3rd reading. PROPOSAL: keep deferring the REVALIDATION retire call; re-measure WR over next ~50 trades before deciding.

### Snapshot
- **Fear & Greed 12 (Extreme Fear)** — cycle low. **BTC dominance 55.6%**, **total mcap $2.14T (−0.7% 24h)**.
- **Breadth 1/15 above 200d** (TRX only); 2/15 golden cross (TRX, XLM). Regime = **RISK-OFF / downtrend**, unchanged.
- **Majors 30d:** BTC −18.7%, ETH −21.6%, SOL −11.7%, BNB −22.7%, XRP −21.4%. Only greens 7d: SOL +1.5%, AVAX +6.4%. Vol still elevated (XLM +94%, BCH +90% ann.).

### News (last few hours, qualitative)
- **F&G 18 → "lowest of the cycle"; price held 26-Jun lows 3 sessions** — sentiment/price divergence that historically precedes recoveries (not a guarantee). BTC ~$60,251, ETH ~$1,579. ([MEXC](https://www.mexc.com/news/1179533), [cryptoticker](https://cryptoticker.io/en/why-is-crypto-price-down-today-june-2026/))
- **Macro still the driver, hawkish.** Fed held 3.50–3.75% on 18-Jun but **removed easing language** → firmer DXY/yields, headwind for non-yielding BTC. ([WEEX](https://www.weex.com/questions/article/did-the-june-2026-fed-rate-decision-trigger-liquidations-in-highly-leveraged-crypto-options-market-volatility-realities-c07nrowiv1l0vcynxbmf1v0g))
- **ETF outflows = structural overhang.** Record ~$3.4B single-week early June; 3-week total >$4.21B. Framed by some as "more cyclical than structural." ([investing.com](https://www.investing.com/analysis/bitcoins-34-billion-etf-bleed-looks-more-cyclical-than-structural-200681474), [The Block](https://www.theblock.co/amp/post/406340/bitcoins-fragile-floor-cracks-as-fed-hawks-circle-and-etf-investors-keep-pulling-out-analysts))
- **Liquidations** ongoing (~$1.1B/24h in the recent flush); **SpaceX IPO demand** cited as pulling liquidity from crypto. Big legislative week ahead (CLARITY Act, American Reserve Modernization Act). ([bitrue](https://www.bitrue.com/blog/bitcoin-june-2026-crash-liquidations))

### Per-bot read (vs validated expectations)
| Bot | Equity | Open | Closed | W/L | Read |
|-----|--------|------|--------|-----|------|
| trend-golden-cross (V4) | 994.48 | 1 | 0 | 0/0 | ✅ As designed — mostly cash; lone open consistent w/ TRX being only major in uptrend. |
| swing-dip-buyer (V6) | 1000.00 | 0 | 0 | 0/0 | ✅ As designed — fully in cash, not catching the falling knife at F&G 12. |
| momo-breakout-4h (V7) | 999.30 | 0 | 1 | 0/1 | ✅ As designed — one failed breakout (−0.70), now flat; correctly suppressed in risk-off. |
| momo-breakout-alt (v8) | 981.75 | 2 | 2 | 0/2 | ⚠️ Un-gated; still carrying 2 losers (−11.33) but no new fills since 24-Jun; equity ticked up slightly. Proposal unchanged: apply V7 regime suppression. |
| intraday-daytrader-5m (V5) | 985.75 | 0 | 88 | 9/79 | 🔁 Churn (10% WR) but daily bleed still shrinking (−0.22 today). See ACTIONABLE #3. |
| hl-momo-breakout | 985.26 | 16 | — | — | ⚠️ 16 open longs into F&G 12; drawdown deepening (−14.74). See ACTIONABLE #2. |
| hl-perps-rsi | 1001.28 | 1 | — | — | OK — +1.28, single position. No action. |
| listing-sniper | — | 2 | 4 | 3/1 | Research/scanner; stale ~32min. No action. |
| scanners (triangular-arb, cross-exchange-arb) | n/a | — | — | — | Scanning only; triangular best depth −0.9%, no fills. cross-exch $2188 figure is a scanner notional artifact, not realised P&L. No action. |
| stock bots (ikbr, alpaca) | — | — | — | — | Stale (expected, weekend/off-hours); out of crypto scope. |

**Verdict:** No regime shift — F&G deepened to a cycle low (12) but market structure is unchanged (breadth 1/15, BTC ~$60k). Validated keepers **V4 / V6 / V7 behaving exactly to design** (defensive, mostly cash). Genuinely new this run: (a) a **sentiment-vs-price divergence** worth watching for a possible base — but no action until breadth confirms; (b) **hl-momo-breakout's 16-long book keeps drawing down** in extreme fear — reaffirms the regime-gate proposal; (c) **V5's daily bleed shrank for a 3rd reading** — keep deferring retire. Reaffirms REVALIDATION_2026-06-22 otherwise. PROPOSALS only — no actions taken; dry-run/paper, not financial advice.

---

## 2026-06-29 04:17 UTC — Market scan + bot research review

### ** ACTIONABLE **
*No new actionable since the 03:32 run (~45 min ago) — this is a reaffirmation. Two small deltas worth noting:*
1. **hl-momo-breakout trimmed its book 16 → 14 open longs** (equity $985.26 → $984.23, −$15.77 abs vs −$14.74). Mild de-risking into F&G 12, but still the lone keeper-cohort outlier carrying directional longs in deep risk-off. PROPOSAL unchanged: add a V7-style regime gate; keep monitoring.
2. **V5 (intraday-daytrader-5m) took another trailing-stop loss** (ZEC/USD −1.04%, 10-min hold). Today's daily bleed now −0.42 over 3 trades (was −0.22/2). WR 9W/80L ≈ 10%, exits still 73/89 trailing_stop_loss. Bleed remains small/contained — PROPOSAL unchanged: keep deferring the REVALIDATION retire call, re-measure WR over next ~50 trades.

### Snapshot
- **Fear & Greed 12 (Extreme Fear)** — unchanged, cycle low. **BTC dominance 55.6%**, **total mcap $2.14T (−0.7% 24h)**.
- **Breadth 1/15 above 200d** (TRX only); **2/15 golden cross** (TRX, XLM). Regime = **RISK-OFF / downtrend**, unchanged.
- **Majors 30d:** BTC −18.9%, ETH −21.8%, SOL −12.4%, BNB −23.1%, XRP −21.9%. Only greens 7d: SOL +0.7%, AVAX +5.8%. Vol still elevated (XLM +94%, BCH +90% ann.).

### News (last few hours, qualitative — little new)
- **F&G stuck at extreme fear; low-volume weekend consolidation.** BTC ~$60,251 (flat), ETH ~$1,579; volumes down sharply (BTC −52%, ETH −45%, SOL −51%). Price holding the 26-Jun lows for a 3rd+ session → sentiment-vs-price divergence persists (watch, not confirmed reversal). ([MEXC](https://www.mexc.com/news/1179533), [blockchainreporter](https://blockchainreporter.net/crypto-market-today-june-28-bitcoin-flat-60251-fear-greed-hits-18/))
- **Macro driver unchanged & hawkish.** Fed held 3.50–3.75% on 18-Jun, removed easing language → firmer DXY/yields pressuring non-yielding BTC. ([tradingkey](https://www.tradingkey.com/analysis/cryptocurrencies/btc/261945885-crypto-bitcoin-btc-price-crashing-usd-strategy-fed-tradingkey))
- **ETF outflows = structural overhang** (~$3.4B single-week early June; some frame it "more cyclical than structural"); leverage flush ~$1.1–1.8B/24h in recent sessions. Big legislative week ahead (CLARITY Act, American Reserve Modernization Act). ([investing.com](https://www.investing.com/analysis/bitcoins-34-billion-etf-bleed-looks-more-cyclical-than-structural-200681474), [bitrue](https://www.bitrue.com/blog/bitcoin-june-2026-crash-liquidations))

### Per-bot read (vs validated expectations)
| Bot | Equity | Open | Closed | W/L | Read |
|-----|--------|------|--------|-----|------|
| trend-golden-cross (V4) | 994.72 | 1 | 0 | 0/0 | ✅ As designed — mostly cash; lone open consistent w/ TRX being only major in uptrend. |
| swing-dip-buyer (V6) | 1000.00 | 0 | 0 | 0/0 | ✅ As designed — fully in cash, not catching the knife at F&G 12. |
| momo-breakout-4h (V7) | 999.30 | 0 | 1 | 0/1 | ✅ As designed — one failed breakout (−0.70), now flat; correctly suppressed in risk-off. |
| momo-breakout-alt (v8) | 981.25 | 2 | 2 | 0/2 | ⚠️ Un-gated; still carrying 2 losers (−11.33), no new fills since 24-Jun. Proposal unchanged: apply V7 regime suppression. |
| intraday-daytrader-5m (V5) | 985.48 | 3 | 89 | 9/80 | 🔁 Churn (~10% WR, all trailing-stop) but bleed small/contained. See ACTIONABLE #2. |
| hl-momo-breakout | 984.23 | 14 | — | — | ⚠️ Trimmed 16→14 longs into F&G 12; still drawing down (−15.77). See ACTIONABLE #1. |
| hl-perps-rsi | 1001.28 | 1 | — | — | OK — +1.28, single position. No action. |
| listing-sniper | — | 2 | 4 | 3/1 | Research/scanner; stale ~3min. No action. |
| scanners (triangular-arb, cross-exchange-arb) | n/a | — | — | — | Scanning only; triangular best depth −0.90%, cross-exch best top 4.61% (notional scan artifact, not realised P&L). No action. |
| stock bots (ikbr, alpaca) | — | — | — | — | Stale (expected, off-hours); out of crypto scope. |

**Verdict:** No regime shift, no anomaly — full reaffirmation of REVALIDATION_2026-06-22 and the 03:32 run. F&G pinned at cycle-low 12, breadth 1/15, BTC ~$60k, low-volume weekend chop. Validated keepers **V4/V6/V7 behaving exactly to design** (defensive/cash). Only micro-moves: hl-momo-breakout shaved 2 longs (mild de-risk), V5 took one more small trailing-stop loss. **No change warranted.** PROPOSALS only — no actions taken; dry-run/paper, not financial advice.

---

## 2026-07-03 04:30 UTC — Market scan + bot research review

** ACTIONABLE **
- **V5 (crypto-intraday-15m) is the only bot actively trading in this risk-off tape, and it keeps bleeding — confirms the 22-Jun revalidation "retire V5" verdict.** Live sample (last 155 closed trades): net **-$20.96, 14% win rate** (21W/134L). Exit mix: 121 trailing_stop_loss, 14 hard stop_loss, 12 ROI, 8 exit_signal — classic death-by-a-thousand-cuts chop. Daily P&L has been red every single day 22-Jun→02-Jul (-$0.57 to -$3.25/day). **PROPOSAL:** pause/retire V5 (dry-run) or gate it to only trade when BTC is above its 200-day SMA — right now BTC is below 200d and V5 has no regime filter. Rationale: it is the sole net-negative crypto contributor and its live behaviour matches the retire recommendation.
- **All trend/swing/breakout bots (V4/V6/V7/v8) are correctly in near-cash** — combined ~5 open trades, no new losses since 24-Jun. This is exactly the designed risk-off behaviour; no change warranted, flagged only to confirm they are NOT over-trading.

**Snapshot (2026-07-03 04:25 UTC)**
- Fear & Greed **21 (Extreme Fear)**; BTC dominance **55.6%**; total mcap **$2.21T (+1.3% 24h)**.
- Regime: **RISK-OFF / downtrend.** Breadth **2/15** above 200d SMA and **2/15** in a golden cross — only **XLM** and **TRX** are in uptrends. BTC/ETH/SOL/BNB/XRP all below 200d.
- Notable 7d strength despite the downtrend: SOL +12.1%, BCH +12.0%, XLM +11.4%, ADA +10.8%, ETH +8.0% — a low-quality bounce off oversold; 30d still deeply negative for most (DOT -23%, DOGE/ADA -18%).

**News / catalysts (last few hrs)**
- BTC ~$59–61k, chopping around $60k after reclaiming it on 02-Jul on softer Fed-easing expectations; **June was BTC's worst month of 2026 (-20%)**. SOL led the 02-Jul bounce. (investing.com, cryptotimes.io)
- **Institutional outflows are the dominant driver:** US spot BTC ETFs bled **$4.5B in June** (IBIT ~77% of redemptions), another **-$296M on 01-Jul**. Watch IBIT for a flow reversal as the risk-on tell. (coinglass, investing.com)
- **MiCA transition period ended 01-Jul** — EU CASPs without MiCA authorisation can no longer serve EU clients; a structural, not price, catalyst. (coinspeaker)
- Next **FOMC 28–29 Jul** — the month's main macro event. Citi cut its 12m BTC target to $82k (from $112k); StanChart still $100k YE, Bernstein $150k. (cryptotimes.io)

**Per-bot read (dry-run/paper)**
- crypto-intraday-15m (V5): see ACTIONABLE — bleeding, sole net-negative crypto bot.
- crypto-trend-daily (V4): equity ~$1000.1, 1 open, flat. Correct (mostly cash in downtrend).
- crypto-swing-daily (V6): equity ~$999.9, 1 open, flat. Correct.
- crypto-breakout-4h (V7): equity $1000, 0 open. Correct — no breakouts to chase in risk-off.
- crypto-trendmomo-4h (v8): equity ~$999.8, 2 open, flat since the -$11.33 SOL/APT exit on 24-Jun (old, not recent). Correct now.
- perps-funding-carry (new, dry-run): equity $997.26, -$1.72, 0/3 closed wins, 4 open shorts harvesting funding (VVV/GRAM/NEAR/FARTCOIN @ +39–52% APR). Small negative on carry entry drag; monitor — too new to judge.
- perps-rsi-meanrev / perps-donchian-breakout / perps-regime-switch: all ~flat ($1000 ±0.2), 0–3 open. No concern.
- scanner-cross-exchange-arb: +$80.44 on real (fee+slippage+latency) basis, best top 4.03% across 342 pairs — healthy signal generation (observational only).
- event-listing-sniper: +$251 realized but -$70 unrealized, 4W/47L — low hit-rate is by design (fat-tail listings); watch the unrealized drawdown.

**Divergences / anomalies:** none beyond the known V5 issue. No stale/halted bots (feed fresh, 14 live, 0 stale). Trend bots are NOT over-trading in risk-off — as designed.

*Dry-run/paper; observational only; not financial advice. All items above are PROPOSALS for user review — no config/trade/key changes made.*

## 2026-07-03 07:15 UTC — FLEET REWORK: adaptive dual-mode bots (interactive session, user-directed)

**User goal:** ALL bots — more trades, market adaptability, more opens/closes, more green than red.

**Root cause found:** the 2026-07-01 commit "Switch all bots to 20-candle range" (41b66e8) replaced every bot's validated edge with the same ungated buy-the-range-low logic — no trend filter, live in a bear. V7's Donchian breakout (validated PF ~1.9) and V6's gated dip-buy were silently destroyed; v8 had earlier been sped from its validated 1d to 4h and widened from BTC+ETH to 20 alts without revalidation.

**Design shipped:** each bot = validated edge as its UP-regime mode + a half-stake "stabilized capitulation bounce" as its DOWN-regime mode (RSI oversold + range-low held N candles + up-tick; fast exits, timeouts). Bots now adapt to the regime instead of churning against it or sitting dead. All entries tagged (dip_in_uptrend / breakout / sma_fast_above_slow / range_on / bear_bounce) for per-mode P&L attribution.

**Backtest evidence (docker freqtrade, binance data, 0.1% fee; V5 at 0.26% Kraken fee). OLD = deployed HEAD, NEW = this rework:**

| Bot | Window | OLD | NEW |
|---|---|---|---|
| V6 SwingDip (1d, 15 pairs, mo=8) | 2024-01→2026-06 | 412 tr, 54% win, **-71.3%**, DD 74% | 122 tr, **53.3% win, +6.0%**, DD ~52% |
| V7 MomoBreakout (4h, 15 pairs, mo=10) | 2024-01→2026-06 | 1439 tr, 58% win, **-79.5%**, DD 83% | 547 tr, 34% win, **+56.8%**, DD 33% |
| v8 TrendMomo (1d, BTC+ETH, mo=2) | 2024-01→2026-06 | 532 tr @4h/15 pairs, **-49.9%** | 20 tr, 45% win, **+43.7%** |
| V5 DayTrader (1h, 5 majors, mo=5) | 2025-08→2026-06 | 253 tr @15m, 24.5% win, **-24.6%** | 46 tr, 30% win, **-5.6%** |

Key sub-findings (all tested, not guessed):
- v8 on 1d but 15-pair basket: -68% → the SMA-cross edge does NOT generalize past BTC+ETH (whitelist cut to BTC/ETH; +43.7%). 5-majors variant also failed (-35%).
- V5 at 15m is structurally fee-dead on Kraken: a 3.5h 15m range (~0.3-0.8%) can't clear the 0.52% round-trip fee. Moved to 1h. Five variants tested; best is -5.6% over a bear-heavy window. A 1h breakout sleeve was tried and rejected (-33%, 16% win).
- V5 regime switch: BTC 4h EMA50/200 (was 1d 50/200 — never warmed up; also fixed a silent column-suffix bug that forced permanent bounce-only mode).

**Config changes:** v4 max_open 2→3 (strategy untouched — remains the control); v5 max_open→5, tradable_balance_ratio 0.1→0.5, now 1h; v8 max_open→2, whitelist→BTC+ETH.

**Honest caveats:** V5 remains the only bot without a green backtest — recommend a 2-week live watch with a retire trigger if it can't hold ~breakeven. V6/V7 backtests are on the 15-pair binance proxy of the 24-pair Kraken basket at 0.1% fee (Kraken 0.26% will trim V7's edge; its avg win is large enough to survive it). All dry-run; deploy = commit → push (auto-redeploys freqtrade-bots via GH Actions; persist volume keeps open paper trades).

*Dry-run/paper. No dry_run/key/live-money settings touched.*

## 2026-07-03 08:05 UTC — EQUITY PERSISTENCE: stop resetting to $1000 (user-directed)

**User goal:** equity curves must survive restarts/redeploys and show cumulative growth.

**Freqtrade bots (V4-v8):** already durable as of today — all 5 db_urls point at the /freqtrade/persist Railway volume and the root-ownership shim (2794f40) made it writable. Freqtrade rebuilds the dry-run wallet from the trades DB on start, so equity now carries across deploys. The ~1000 baselines seen on 02-03 Jul were the one-time reset when persistence first engaged. RULE: never change dry_run_wallet (1000) again — it's the fixed baseline the DB accumulates on.

**Custom bots — added durable state (new Postgres table bot_state, save/load in bot_pnl_store; PaperBroker gained to_state()/restore_state()):**
- perps-rsi-meanrev: restores paper account + entry prices/stops + re-entry cooldowns; saves every loop.
- perps-donchian-breakout: restores paper account + open-trade timestamps; saves every loop.
- perps-funding-carry: restores open carries (accrued funding, entry APR); realized was already ledger-backed.
- event-listing-sniper: baseline/open book/pending watchlist now mirrored to Postgres each cycle and restored when sniper_data/ is wiped by a deploy (realized was already ledger-reconciled). Also prevents post-deploy re-seeding blindness.

**Not covered (noted, low priority):** cross-exchange & triangular arb scanners still reset their hypothetical counters on deploy (advisory-only); equities bots persist server-side at Alpaca/IBKR. PaperBroker bots trade fixed $ notionals, so their growth is linear, not compounded (freqtrade bots DO compound via balance-scaled stakes).

*All dry-run. Verified: py_compile on 6 files, paper_broker self-test, JSON round-trip test.*

## 2026-07-03 07:35 UTC — LEARNING PASS 1: tune to the winning points + build the brain (user-directed)

**V5 all-time dissection (157 closed):** ROI exits 13/13 winners; ATR-stop exits 122 at 6% win = -$17.68 of -$20.96 total; only net-positive hold bucket = 90-240min (50% win); <30m holds 2% win. LESSON: winners need room+time. SHIPPED: atr_stop_mult 2.0 -> 2.5 (backtest confirm: win rate 30.4 -> 41.3%, P&L and DD both improved). Session skew noted (18-23 UTC wr 23-36% vs 5-14% elsewhere) — logged as a brain hypothesis, NOT shipped (old universe/timeframe; must re-confirm).

**V7 loosening tested and REJECTED:** 20/10 and 24/12 lookbacks add trades (547->732) but cut profit (+56.8% -> +28/+20%). Its quietness is the regime (2/15 above 200-EMA), not the params. No change.

**v8 loosening tested and SHIPPED:** SMA 20/50 -> 10/40 (inside the validated sweep). Split-window: bull +94.5% vs +71.2% (22 vs 15 trades), bear -9.8% vs -16.0%. More trades, more profit, less bear bleed; DD 26% vs 18% accepted.

**THE BRAIN (bot_learn.py, v1):** reads the durable trade ledger, dissects per bot by tag/exit/pair/duration/session, keeps cumulative hypothesis state (Postgres bot_state 'learning-brain' + local fallback), requires persistence across >=3 runs before promoting a pattern to ACTIONABLE, writes reports/lessons_latest.md. First run: 9 candidates, incl. independently rediscovering the stop lesson and flagging TRX/NEAR as live whitelist bleeders. Wired into the 2-hourly research scan. Limitation (v2 candidate): all-time ledger view — no era-weighting yet, so already-fixed patterns re-flag until history dilutes.

*All dry-run; proposals-only brain; no live-money settings touched.*

## 2026-07-03 09:20 UTC — REGIME BOT ASSESSMENT + MARKET PULSE FEED (user-directed)

**perps-regime-switch assessed:** healthy, zero errors — it was correctly coiled (regime = DOWN+TREND on BTC/ETH, armed to short, waiting for a fresh 1h EMA cross that never came because it deployed INTO the relief bounce). Deeper finding: walk-forward on Aug-2024→Jun-2026 BTC+ETH futures shows the whole design is red: cross-entries 199 trades -32%/DD37; persistent-state entries 716 trades -31%/DD55 (docstring churn warning confirmed); regime-aligned 20-bar Donchian entries 484 trades -20%/DD36 = strictly best. SHIPPED the Donchian entries with an explicit "EXPERIMENT, not a funded edge" label. PROPOSAL: keep it as the designated experiment sleeve; retire if still red at the next monthly review.

**MARKET PULSE (new):** market_pulse.py — keyless collector: Fear&Greed + CoinDesk/CoinTelegraph RSS + Reddit hot (best-effort; 403s from some IPs) + Binance perp funding. Scores mood [-1,+1], flags PANIC on >=3 shock headlines, counts basket-coin mentions. Runs every 10 min inside the freqtrade-bots container -> Postgres bot_state 'market-pulse' (rolling ~7d history) + served at /pulse.json on the dashboard + local reports/market_pulse_latest.md.
- CONSUMPTION POLICY: sizing + learning only. V5 halves new stakes during a panic cluster (entries untouched). bot_learn now correlates every trade with the mood it was opened in (neg/mid/pos buckets) and will propose mood-based gates ONLY if a persistent edge shows (>=10 trades per bucket, >=3 runs). No unvalidated signal gets entry-gate power — that is the promotion path.
- First live pulse: mood -0.19 (F&G 21), no panic, funding +11% APR BTC/ETH; caught "US spot BTC ETFs top $200M daily inflows, first since May" — the flow-reversal tell.

*All dry-run; pulse is advisory sizing + brain food; no keys, no paid APIs, no live-money settings touched.*

## 2026-07-03 09:40 UTC — KNOWN-KNOWLEDGE PASS: tested worldwide/social wisdom against the data (user-directed)

Tested famous edges from quant literature + crypto socials against OUR data before wiring anything:

| Idea (source) | Verdict | Evidence |
|---|---|---|
| Inverse-vol position sizing (AQR/Carver) | **SHIPPED to V7 only** | V7 basket: +56.8% -> +75.9%, DD 32.8 -> 28.3%, identical 547 trades. REJECTED for v8 (BTC+ETH: no dispersion, just under-deploys: +75.4 -> +61.8) and V6 (its best trades ARE high-vol capitulation days; profit halved). |
| Maker-not-taker entries (practitioner staple) | **SHIPPED to V5** | entry_pricing side -> "other" (join the bid). Fee sweep on the 1h window: taker -5.6% / blended -4.7% / full maker -4.1%. Modest at current frequency, structural at higher frequency; costs nothing for a dip-buyer. |
| "Buy extreme fear" F&G contrarian (crypto socials) | **REJECTED** | 1,643 days of F&G x BTC: F&G<15 -> fwd30 -2.1% (coin-flip win rate); mid/greed -> +1-3%. Extreme fear = downtrend continuation, NOT reversal. Validates our regime-following gates; contrarian sizing would have hurt. |
| Turtle pyramiding (add to winners) | DEFERRED | Needs position_adjustment code in V7; candidate for next pass. |
| Funding-rate squeeze setups | ACCUMULATING | Pulse collects funding every 10 min; brain will correlate before any gate. |
| Session filters ("US hours drive continuation") | BRAIN-TRACKED | Matches our live 18-23 UTC finding (23-36% wr vs 5-14%); needs to re-confirm on the new 1h universe (>=20 trades). |
| ICT kill zones / social TA lore | SKIPPED | No reproducible evidence to test against. |

*All dry-run; every accepted idea carries a backtest receipt; every rejection is logged so we don't re-litigate it.*

## 2026-07-04 01:15 UTC — V6 DEEP DIVE: zero trades investigated (user-directed)

**Verdict: NO FAULT — correctly idle.** Logs clean, online, +$0.29, managing its 1 carried position. Daily timeframe = exactly ONE decision point since the rework. Live condition scan across all 24 pairs: bounce mode 0/24 ready (RSIs 39-66, all >30; prices 21-98% up their 20d ranges, all >10%), dip mode blocked on all 4 golden-cross pairs (3-27% above lower Bollinger after the rally). The relief rally lifted the basket out of capitulation before V6 deployed; nothing has pulled back into dip territory yet. Backtest agrees: May-Jun window = 2 trades in 7 weeks.

**Loosening tested and REJECTED (again):** dip RSI 35->40 + bounce zone 10%->15% => 122->196 trades but +6.0% -> -9.0%, DD 20.6% -> 37.2%. V6's patience IS its edge. Do not loosen.

**Breadth improving:** golden crosses 2 -> 4 basket coins overnight (NEAR + INJ joined XLM/TRX) — early regime-repair signal; V6/V7 hunting ground expanding. Nearest V6 trigger: TRX (+3.0% above its lower band, RSI 48 — two red days arm a dip_in_uptrend buy).

## 2026-07-04 05:15 UTC — REGIME BOT: stale deployment found and fixed (user-directed)

**Root cause of continued inactivity: the 2026-07-03 Donchian-entry improvement NEVER DEPLOYED.** perps-regime-switch has no Railway-native auto-deploy and wasn't in the GitHub Action's service map — its last deploy (03 Jul 02:39 UTC) predated the strategy change by ~8h. The bot ran the old EMA-cross code for 19 further hours. (No harm done by luck: zero Donchian short-triggers occurred in that window — the 3 breakouts that DID occur were correctly un-tradeable longs in a down regime.)

Fixes shipped:
1. Redeployed via railway up — new container live 04 Jul 05:06 UTC running the Donchian entries.
2. Workflow (6cf25f3, via web editor): perps-regime-switch now auto-deploys on changes to its own files (surgical filter); run_regime.sh/Dockerfile.regime added to trigger paths; market_pulse.py/freqtrade_pnl_poller.py added to the freqtrade-bots filter.
3. Verified its persist volume is mounted (/freqtrade/persist) and db_url points into it — future trades survive deploys.

Expectation now: shorts on any 1h close below the prior 20-bar low while BTC/ETH daily regime = down+trend (currently armed); longs mirrored in up regimes. Backtest cadence ~0.7 trades/day average. EXPERIMENT status unchanged — monthly retire-review stands.

## 2026-07-04 07:50 UTC — SNIPER INTEL: external listing databases wired in (user-directed)

User asked whether the sniper is missing databases (coinsniper.com, X.com). Assessment + build:
- SHIPPED listing_intel.py (keyless, free): announcement feeds from Binance/Bybit/KuCoin/Upbit (50 symbols captured on first live pull) + CoinGecko footprint check. Validation: ANSEM (the +$325 jackpot) scores full-stake (rank 204); ALABON turns out to be a tokenized stock (rank 7146) — passes footprint but the 1e154dc equity exclusion catches it; true no-page junk gets HALF stake.
- Policy: stake modulation only (junk 0.5x, everything else 1.0x, intel failure = neutral 1.0x). Entries untouched. Every position tagged (announced/footprint/junk/unknown) in state + CSV so the ledger accumulates evidence for harder gating later.
- REJECTED sources: coinsniper.com-class directories (pay-to-list shill boards = adverse selection), X.com for now (paid API, ToS; the high-value subset — exchange announcements — captured directly from the exchanges for free).
- Context from trade-ledger dissection (same session): 46 of 47 "losses" were delist scratches at ~-0.4% avg; entire +$255 profit = one pre-footprinted listing (ANSEM: 2x scale-out + 5x runner). Target-lowering REJECTED: it would cost ~$150 of the ANSEM runner and rescue zero duds (all 24 open positions peaked <+10%). Targets stay 2x/5x/trail.

## 2026-07-04 09:30 UTC — KNOWLEDGE ROLLOUT POLICY: selective, evidence-gated (user-directed)

User asked whether the external-knowledge layer should extend to other/all bots. Policy applied — knowledge must match the bot's mechanism (today's evidence: vol-sizing helped only V7; F&G contrarian and looser gates hurt everywhere tested):
- SHIPPED: panic-cluster half-stake sizing extended to V6 + V7 (their bear_bounce sleeves buy capitulation days — a live news-shock cluster is the knife their stabilized-low gate can't see). Sizing-only, fail-safe neutral.
- SHIPPED: pulse history now records per-coin funding APRs — accumulates the evidence needed to later gate perps shorts against crowded-short squeezes (known edge, but an ENTRY change, so it waits for brain proof).
- NOT wired: V4 (validated control stays clean), v8 (20 trades/2.5yr — cadence too slow for signals), perps entry-gating (evidence first).
- The promotion pipeline is the real mechanism: pulse tags + era-aware brain accumulate per-bot mood/session/funding correlations; persistent findings become ACTIONABLE proposals; tested; shipped.

## 2026-07-05 02:30 UTC — DASHBOARD INSIGHT LAYER (user-directed)

Per-bot additions to the P&L dashboard (verified by live render before ship):
- Quality (ledger): win rate, profit factor, $/trade expectancy + last-close age — from the durable bot_trades table.
- "Since 3 Jul rework": era-split trades/W-L/P&L per reworked bot so the NEW code is judged on its own trades (same era map as the brain).
- 7d equity sparkline + drawdown-from-peak per bot (bot_equity_history).
- Live open-position detail for freqtrade bots (pair, current %, entry tag, hours held) — poller now passes /status through.
- Market pulse strip in the header (mood, F&G, panic flag, funding APRs).
- Status badges: V5 PROBATION, regime-switch EXPERIMENT, V4 CONTROL, v8 SLOW BY DESIGN — the cards now say how to READ each bot.

## 2026-07-04 23:31 UTC — CRYPTO SCAN + BOT REVIEW (scheduled ~2h)

**Read:** structural RISK-OFF with a macro-driven relief bounce in progress — bots behaving to design. No panic, no anomalies, no actionable items. Normal entry.

**Snapshot:** F&G **22 (Extreme Fear)**; BTC dominance 55.7%; total mcap $2.27T (+0.6% 24h). Breadth **2/15 above 200d** (only XLM, TRX; both also the only 50>200 golden crosses). All majors still below their 200d = downtrend intact. 7d returns broadly green though (BTC +5.1%, ETH +13.0%, SOL +15.9%, XRP +10.5%, ADA +32.2%) — a bounce inside a down structure.

**Pulse:** mood **-0.224** (flat all day), **panic=false**, btc_regime=null (source down), funding=null (Binance funding feed still empty). 1 panic-flagged headline (the "$70B flaw") but it's a *patched* white-hat find, not a live hack — correctly sub-cluster, no half-sizing triggered.

**News (last few hrs):**
- BTC retook **$63k**, a 2-week high, +3.6%/wk, reversing end-June losses — driven by softer US macro + Fed's Warsh signalling eased inflation risk; thin July-4 holiday liquidity amplifying. ([CoinDesk](https://www.coindesk.com/markets/2026/07/04/bitcoin-jumps-above-usd63-000-reversing-end-june-losses))
- **ETF flows turned positive:** spot BTC ETFs now 5 straight days of inflows (IBIT-led); BlackRock staked-ETH fund took $100M day one — the demand engine re-firing (the flow-reversal tell first caught 03 Jul). ([Investing.com](https://www.investing.com/analysis/bitcoin-etf-inflows-and-falling-exchange-supply-strengthen-price-floor-200676398))
- **Short squeeze** liquidated ~$281M of bearish bets (≈2× the longs) — mechanical fuel for the up-move, not a long-liquidation cascade. ([CoinMarketCap](https://coinmarketcap.com/top-stories/6a226761f98ad067b44d4ac2/))
- **XRP** +~10%/wk, overtook USDC to #5 by mcap (~$73B). ([CoinDesk](https://www.coindesk.com/markets/2026/07/04/bitcoin-jumps-above-usd63-000-reversing-end-june-losses))

**Per-bot (dashboard live, feed_stale=false, 0 stale / 14 live):**
- **V4** crypto-trend-daily $1004.99 — holding TRX (+1.97), a golden-cross major; else cash. Correct for risk-off. ✓
- **V5** crypto-intraday-15m $1000.25 — only active closer; +$0.25 today (3W/1L), bounce-only. Daily P&L recovering (07-01 −2.39 → 07-02 −0.57 → 07-03 +0.25). Era-net ≈ flat. Correct (PROBATION). ✓
- **V6** crypto-swing-daily $1000.27 — 1 open ATOM (+1.34, range20_buy_low). Patient; its edge. ✓
- **V7** crypto-breakout-4h $1001.10 — 6 breakout opens (ETH/NEAR/ADA/FIL/LINK/SUI), net green (ADA +9.72). Re-entering as breadth repairs = expected on a bounce. ✓
- **v8** crypto-trendmomo-4h $1005.54 — 2 opens (ETH/SOL, sma_fast_above_slow). Slow-by-design. ✓
- **perps-regime-switch** $1000.00 exactly — 0 open / 0 closed. NOT a snapback (never traded this era; redeployed 04 Jul 05:06 w/ Donchian entries, ~0.7 trades/day cadence, armed to short but no 1h close < 20-bar low yet). EXPERIMENT. Watch.
- Other sleeves nominal: perps-rsi-meanrev +17.60, perps-funding-carry −2.15 (0/4), sniper +194.07 realized (ANSEM jackpot intact), cross-exch-arb +4.98, tri-arb −1.13% (unfunded, as retired). Equities-alpaca last update ~25h (July-4 US holiday close — expected, near stale threshold).

**Brain:** run #6 — 162 closed trades, **0 actionable, 0 candidates** (current-era). Persisted postgres+local. No new hypotheses promoted.

**PROPOSALS:** none this cycle. WATCH (not actionable): ETF-inflow reversal + dovish-Fed + short-squeeze = a credible relief catalyst, but breadth is still 2/15>200d and F&G stuck at 22 — **bounce, not a confirmed regime flip**. If golden-cross breadth expands and holds (≥4–5/15) with F&G climbing out of extreme-fear, V6/V7 re-entry space widens; re-assess regime label then. No config touched.

*All dry-run/paper; advisory only; not financial advice. No trades, configs, keys, or dry_run flags altered; nothing committed or emailed.*
