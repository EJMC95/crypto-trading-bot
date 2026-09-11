# Crypto Bots — Weekly P&L Digest

**Report date:** 2026-07-13 (Mon cycle; generated 2026-07-15) · **Completed week covered:** Mon 2026-07-06 → Sun 2026-07-12
*Paper fleet = dry-run bots on live market data with simulated fills. Lighter fleet = REAL money (small live sizing). Not financial advice.*

---

## 💸 LIVE (real money) — Lighter fleet

Real-money books since inception ~2026-07-09/11. A per-week slice isn't published for these (they don't feed `periods.json`), so figures are **cumulative** with today's move noted.

| Bot | Mode | Equity | Cum. P&L | Closed record | Today | Holds |
|-----|------|-------:|---------:|:-------------:|------:|-------|
| 💸 Funding Farmer (`perps-funding-lighter-lighter`) | live 2x | $61.82 | **+$0.69** | 12 · W11/L1 (+$2.67) | −$3.38 | ETH·SOL·HYPE short, WTI long |
| 🌊 Tide Rider (`crypto-trend-daily-lighter`) | live 1x | $34.80 | **−$0.20** | 0 closed (holding) | +$0.06 | TRX |
| **Live fleet total** | | **$96.62** | **+$0.49** | | | |

**Live vs shadow gap (⚠️ flagged 2026-07-13):**

| | Live | Shadow control | Read |
|---|-----:|---------------:|------|
| Funding Farmer record total | +$2.67 (W11/L1) | +$4.51 (W18/L7) | Live **under**performing shadow; alert measured **+5.4% execution divergence** — worth investigating. Live acct is ~$62 vs shadow's $1,000 notional, so compare the % gap, not the $. |
| Tide Rider cum. P&L | −$0.20 | −$0.22 | Tracking shadow tightly — no divergence. |

Funding Farmer's worst live print this week: **LIT −$2.01** (short stopped out, 2026-07-14). Otherwise 11 of 12 closes green — the structural funding edge is showing, but the −$3.38 day + the shadow gap say execution slippage is eating into it.

---

## 📄 PAPER — completed week realized P&L (Jul 6 – Jul 12)

Source: dashboard `periods.json` (week key `2026-07-06`). W/L from `trades.json`.

| Bot | Strategy | Realized P&L | Trades | W / L | Win % |
|-----|----------|-------------:|-------:|:-----:|:-----:|
| crypto-trend-daily (V4) | daily trend, majors | **+$2.56** | 13 | 1 / 12 | 7.7% |
| freqtrade-dad (MomoBreakout) | 4h breakout | −$3.47 | 8 | 2 / 6 | 25.0% |
| freqtrade-georgia (DayTrader) | 15m gated | −$4.44 | 36 | 13 / 23 | 36.1% |
| freqtrade-mum (TrendMomo) | 1d trend-momo | −$5.83 | 4 | 0 / 4 | 0.0% |
| crypto-breakout-4h (V7) | Donchian 4h | −$7.88 | 9 | 1 / 8 | 11.1% |
| crypto-intraday-15m (V5) | intraday range | −$11.97 | 26 | 6 / 20 | 23.1% |
| **TOTAL (trading bots)** | | **−$31.03** | **96** | **23 / 73** | **24.0%** |

*Arb scanners (cross-exchange-arb, event-listing-sniper) excluded — optimistic/research paper.*
*Note: `perps-regime-switch` also closed 7 trades (W1/L6, **−$5.36**) in this window but has since stopped publishing to the live feed (not in `pnl.json`) — consistent with RegimeSwitchV1 being unfunded/retired. Not in the total above.*

- **Best:** 🌱 **V4 trend-daily +$2.56** — the only green bot, on just 1 winning trade of 13 (one big major-trend rider carried it).
- **Worst:** 🔻 **V5 intraday-15m −$11.97** — 26 trades, 23% win, still the fleet's biggest bleeder.

### Week-over-week (paper, `periods.json` basis)

| Metric | Prior wk (Jun 29–Jul 5) | Completed wk (Jul 6–12) | Δ |
|--------|-----------------------:|------------------------:|:--:|
| Total realized | −$2.00 | −$31.03 | **−$29.03** |
| Trades | 10 | 96 | +86 |
| Bots trading | 1 | 6 | +5 |

⚠️ Not apples-to-apples: the freqtrade family bots (mum/dad/georgia) came fully online this week, so the fleet went from 1 active bot to 6. The −$31 is a wider, noisier fleet finding its feet, not a single strategy blowing up.

**Current week to date (Jul 13–14):** freqtrade-dad −$3.97, intraday-15m −$1.27, breakout-4h −$0.81, georgia +$0.20 → running ≈ −$5.85 over 11 trades. Early.

---

## 🔔 Evidence alerts (past week)

| When (UTC) | Sev | Alert |
|-----------|-----|-------|
| 07-11 13:57 | action | 🚫 Coin veto: **added ADA, kBONK** |
| 07-11 20:38 | action | 🚫 Coin veto: **removed ADA** (kBONK remains) |
| 07-13 14:58 | info | 🧲 Dislocation on **KAITO 350bps** (census 21) — Snap Back evidence |
| 07-13 14:58 | info | 🧲 Dislocation **census reached 92 events** — worth a review |
| **07-13 21:03** | **warn** | **⚠️ Funding Farmer live vs shadow gap +5.4% — execution divergence** |
| 07-14 15:13 | info | 🧲 Dislocation on **EIGEN 156bps** (census 42) |
| 07-14 15:13 | info | 🧲 Dislocation on **KAITO 350bps** (census 57) |
| 07-14 21:18 | action | 🚫 Coin veto: **re-added ADA** |

**Current coin-veto list:**
- **ADA** — stop rate 5/9 ≥ 50% (30d)
- **kBONK** — measured slippage 18.72bps > 15 (n=6)

**Snap Back 🧲 (`lighter-dislocation-lshadow`, shadow/census-gated):** dislocation census now **384 events** (max 350.5bps). 1 shadow trade closed: KAITO short_converged **+$0.18**. Census milestone hit (92→ review) — but still evidence-gathering only; **do not cite its P&L as edge** until the census validates the thesis.

---

## 🩺 Health

- **All 21 live-feed bots online, 0 stale** (`n_stale: 0`, feed fresh at generation). No halts this week.
- `perps-regime-switch` — dropped off the live feed after trading −$5.36 in the completed week (unfunded/retired, expected).
- `freqtrade-mum` — idle: 0 closes in the current week, holding 4 majors (1d trend-momo signals sparse by design).
- Tide Rider live row last update ~25 min at snapshot (within its own threshold — not stale).

---

## 📌 Read — is the validated edge showing yet?

Too early / too few trades on most bots to call. The one structural edge with live evidence — **Funding Farmer's directional-funding carry** — *is* printing (11/12 live closes green, cumulative +$0.69 real), but the **+5.4% live-vs-shadow gap is the story of the week**: execution slippage is skimming the edge, and one −$2 stop (LIT) offset most of the small winners. The paper family bots (mum/dad/georgia) are in their first full week — 24% aggregate win rate is noisy shakedown data, not a verdict. V4 trend (+$2.56 on majors) and Georgia's 36% win rate are the least-bad signals; V5 intraday remains the confirmed loser kept on paper. Snap Back's census keeps building but hasn't earned a P&L claim. Net: watch the funding-carry execution gap; give the paper family ≥2 more weeks before judging.

*Dry-run/paper for the paper fleet; real money on the Lighter fleet. Not financial advice.*
