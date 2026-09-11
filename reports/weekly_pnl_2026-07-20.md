# Crypto bots — weekly P&L

**Week reported:** Mon 13 Jul → Sun 19 Jul 2026 (UTC buckets, the most recent *completed* week in `/periods.json`)
**Generated:** Wed 22 Jul 2026, 09:10 AEST (Sydney) — a day late; the Mon-20 run did not fire.
**Sources:** `/periods.json`, `/pnl.json`, `/trades.json?limit=2000` (+ `?source=paper`), `/alerts.json` — all four fetched clean, no errors.

Real money on the Lighter live rows; everything else is dry-run/paper with simulated fills. Not financial advice.

---

## 💰 LIVE (real money) — first

| Row | Bot | Realized wk | Closes | W/L | Mean %/trade |
|---|---|---:|---:|---:|---:|
| perps-funding-lighter-lighter | 💸 Funding Farmer (2x) | **+$4.24** | 27 | 21/6 | +0.76% |
| lighter-ticket-taker-lighter | 🎫 Ticket Taker (live 17-Jul) | **+$0.39** | 3 | 2/1 | +0.53% |
| | **LIVE total** | **+$4.63** | **30** | **23/7** | |

**Live vs shadow (per-trade, never equity):**

| Pair | Live | Shadow | Gap |
|---|---:|---:|---:|
| Funding Farmer | +0.76%/trade (n=27) | +0.61%/trade (n=39) | **live +0.15pp ahead** |
| Ticket Taker | +0.53%/trade (n=3) | +0.46%/trade (n=39) | live +0.07pp (n=3 — noise) |

Live is *not* slipping this week — the real book beat its own shadow twin on both rows. Caveat: the Farmer's live arm closed 27 trades vs the shadow's 39, so the two arms are not trading an identical set; and the Taker's n=3 is meaningless on its own.

⚠️ **Live book is tiny:** total live equity **$163.54** (Farmer $96.40, Taker $67.14). Lifetime live P&L is **+$2.99**, i.e. *below* this week's +$4.63 realized — the live rows were net-negative going in and carry open marks. Read the % column, not the dollars.

🌊 **Tide Rider's live row is gone** — `crypto-trend-daily-lighter` was retired 17-Jul when the Ticket Taker took the same service/keys/sub-account. Leaving both rows up would have double-counted the same real money. Tide Rider continues as a shadow row only.

---

## 📄 Paper / shadow fleet — week of 13–19 Jul

Living Lighter rows only. Retired rows (Gap Scout, Launch Sniper, Bounce Catcher, Donchian, equities-momentum, the HL funding-carry arm) are excluded — several still logged closes into the ledger before their 17-Jul guards bit.

| Bot | Realized | Closes | W/L |
|---|---:|---:|---:|
| 🌾 perps-funding-carry-lshadow | **+$35.69** | 31 | 14/17 |
| 🎫 lighter-ticket-taker-lshadow | +$9.02 | 39 | 20/19 |
| 💸 perps-funding-lighter-lshadow | +$7.18 | 39 | 21/18 |
| 🙏 freqtrade-avo-maria-lshadow | +$0.88 | 2 | 2/0 |
| ⚖️ perps-funding-spread-lshadow | +$0.20 | 19 | 9/10 |
| 🧲 lighter-dislocation-lshadow | +$0.18 | 1 | 1/0 |
| 🔮 freqtrade-georgia-lshadow | −$0.16 | 20 | 9/11 |
| 👨 freqtrade-dad-lshadow | −$2.84 | 4 | 0/4 |
| crypto-breakout-4h-lshadow | −$4.87 | 6 | 0/6 |
| crypto-intraday-15m-lshadow | **−$5.54** | 10 | 1/9 |
| **Fleet total (incl. the 2 live rows)** | **+$44.37** | **201** | |

**Best:** 🌾 Yield Harvester (funding-carry shadow) at +$35.69 — 80% of the fleet's week, on a *losing* win rate (14W/17L). That is a fat-tail carry profile, not a hit-rate edge.
**Worst:** crypto-intraday-15m-lshadow at −$5.54 on 1W/9L, with crypto-breakout-4h (0W/6L) and 👨 dad (0W/4L) right behind — three books that went 1-for-19 between them.

*Note on the bot map:* the V4/V5/V6/V7/V8 Kraken paper fleet in this task's brief no longer exists — it was cut 14-Jul. Those strategies are now re-expressed as Lighter shadow rows (`crypto-*-lshadow`, the family bots). The `bot_trades` ledger still holds a few legacy `freqtrade-*` / `crypto-*` rows through 14-Jul; they are the same books pre-rename and are not double-counted above.

---

## 🔔 Evidence alerts

**In the reported week (13–19 Jul):** 2 alerts, both `info` — no divergence alert, no "significant evidence" alert.

| When (UTC) | Key | Alert |
|---|---|---|
| 16-Jul 15:43 | `census:50` | 🧲 dislocation census reached **2,900 events** — worth a review |
| 18-Jul 13:31 | `factor-sample:2` | 🛰️ joined decision+context dataset at **87 closed trades** — factor validation becoming possible |

**Since the week closed (20–21 Jul), for context:** 11 more `info` alerts — `factor-sample:3` (97 closed trades, 21-Jul) plus 10 tradeable-dislocation hits feeding the 🧲 Snap Back thesis: KAITO 350bps (census 386), APEX 313bps (1093), BIO 272bps (28), 0G 258bps (190), ZORA 202bps (127), RESOLV 188bps (319), EIGEN 156bps (112), NEAR 150bps (14).

**Current coin-veto list** (as of 21-Jul 23:07 UTC):

| Coin | Reason |
|---|---|
| ADA | stop rate 9/16 ≥ 50% (30d) |
| BOT | measured slip **216.71bps** > 15 (n=5) |
| SOXL | measured slip 17.91bps > 15 (n=14) |

No veto changes were alerted during the week; BOT's 216bps slip is the standout — a book that big a slip should not be sized into.

---

## 📈 Vs prior week

| Week | Total | Trades |
|---|---:|---:|
| 06–12 Jul | +$3.00 | 15 |
| **13–19 Jul** | **+$44.37** | **201** |
| 20–21 Jul (week-to-date, 2 days) | +$0.48 | 88 |

The prior week is not a fair comparison — only three Lighter rows were publishing then (the fleet-wide Lighter cut landed mid-July), so 15 trades vs 201 is a fleet coming online, not a performance jump. The more useful signal is the **week-to-date**: 88 trades in two days for +$0.48, i.e. the carry engine that carried last week has stopped paying, and 🎫 Ticket Taker's shadow is −$3.64 over those two days.

---

## 🔬 Is the validated edge showing up?

Honestly: **one edge is showing, the rest is too early or actively disconfirming.** The funding complex is the only thing working — carry (+$35.69) and the Farmer shadow/live (+$7.18/+$4.24) are 100%+ of the fleet's week, and the Farmer's live arm at +0.76%/trade over 27 closes is the first stretch where real fills beat their own shadow, which is exactly the thing that had never been measurable. But carry's 14W/17L means the P&L lives in a handful of trades — one week is not a distribution, and the week-to-date collapse (+$0.48 on 88 trades) is what a fat-tail book looks like when the tail doesn't show. The directional books are the opposite story: intraday-15m, breakout-4h and dad went a combined **1W/19L for −$13.25**, and 🔮 Georgia ground out −$0.16 on 20 trades — consistent with the standing verdict that the long lenses have no forward edge and that Lighter's single falling-regime tape flatters nothing directional. 🎫 Ticket Taker's shadow (+$9.02, 20W/19L) is doing its job at a coin-flip win rate, but its **live** arm has 3 closes total — the ~30-divergence-close bar for a real verdict is still weeks away. Nothing here changes a go-live decision.

---

## 🩺 Health

- **No stale rows.** At snapshot (21-Jul 23:08 UTC) all **23** trading rows report `online`, `n_stale: 0`, freshest update 5s old, `feed_stale: false`.
- **Idle-but-online** (0 closes all week, some with open positions): `crypto-swing-daily-lshadow`, `crypto-trend-daily-lshadow` (🌊 Tide Rider — trades rarely by design), `equities-regime-lshadow`, `lighter-perp-sniper-lshadow`, `freqtrade-mum-lshadow`, and 4 of the 6 🏛️ Parliament rows (albanese/morrison/turnbull idle; abbott/gillard/rudd have opened books since 20-Jul). Expected for a fleet that stood up on 21-Jul, not a fault.
- **Caveat:** `/pnl.json` is a *point-in-time* snapshot. It cannot tell me whether a row went stale mid-week and recovered — a bot that died Thursday and came back Sunday looks healthy here. No halt/offline was flagged in `/alerts.json` either way.
