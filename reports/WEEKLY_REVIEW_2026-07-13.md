# Weekly Assessment & Health Check — 13 Jul 2026

Fleet-wide review (paper + live + shadow + stocks + scanners), run 13 Jul ~04:30 UTC.
Sources: `bot_pnl` (state/staleness), `bot_trades` + `paper_trades` (realized, 7d),
`bot_equity_history` (7d equity deltas). Retired/hidden rows excluded.

---

## 🚨 Health check — what the check itself found

### 1. FIXED: per-trade ledger frozen since 6 Jul (silent, fleet-wide)
`bot_trades` had **zero writes since 2026-07-06 07:31 UTC**. Root cause: the 6-Jul
PK-migration commit in `bot_pnl_store.py` landed with backslash-escaped dollar
quotes (`DO \$\$`), so `_ensure_trades_table` raised on every call and
`publish_trades` swallowed the error forever (warn-once). The `bot_pnl` summary
rows kept updating, so nothing *looked* wrong — a textbook silent failure.
**Fixed on both branches today; verified flowing again** (fresh rows from all 7
freqtrade bots within minutes of redeploy). The table self-healed with the
corrected per-pair PK because freqtrade re-publishes each bot's full history
every poll. Knock-on: the learning brain / trainer analyzer were starved of
trade data all week — their conclusions from this week should be discounted.

### 2. FIXED: dashboard was serving from two diverged sources
The `pnl-dashboard` Railway service turned out to be **git-connected to main**
(the 12-Jul watchdog session's setup) while the visual work + new features lived
on `claude/lighter-gate0` and deployed via `railway up`. Today's push to main
auto-regressed prod to the old fork (no manage panel, stale labels, missing
shadow rows). **Resolution: merged the two variants** (gate0 dashboard +
fleet-watchdog daemon + `/watchdog.json`) and synced the merged file to BOTH
branches — either deploy path now serves the same superset. Verified live:
26 rows incl. all 10 shadow rows, watchdog running.

### 3. ACTION NEEDED (you): two decommissioned bots came back to life
Today's pushes to main **resurrected `perps-bot` (Bounce Catcher) and
`triangular-arb` (Loop Scout)** — both decommissioned on your 12-Jul sign-off.
Railway auto-deploys rebuild stopped services on every push (known hazard).
I'm permission-blocked from `railway down` on shared services, so please stop
them in the Railway UI (or ask me to run `railway down --service perps-bot` /
`--service triangular-arb` with your approval). Their dashboard rows stay
hidden either way; the cost is compute + ledger noise.

### 4. Expected/benign
- **equities-momentum-alpaca stale 48h** — weekday-22:00-UTC cron; weekend
  staleness is normal. If still stale after Monday's run, investigate.
- **Tide Rider paper (crypto-trend-daily)** freqtrade DB appears to have reset
  ~6 Jul (lifetime == last-7d trades). Paper-era stat only.
- All other feeds fresh; no error/halted statuses anywhere.

---

## 💰 Live money (Lighter) — both green, both tiny

| Bot | Equity | P&L | Notes |
|---|---|---|---|
| 🌾 Funding Farmer (`perps-funding-lighter-lighter`) | $61.89 | **+$0.76** | 4 open, 1/1 wins, clip $10/cap $40 |
| 🌊 Tide Rider (`crypto-trend-daily-lighter`) | $35.08 | **+$0.08** | 1 open, 1x long trend |

## 📈 Paper crypto — 7d realized (healed ledger + equity deltas)

| Bot | 7d P&L | 7d W/L | Verdict |
|---|---|---|---|
| 🎯 Launch Sniper (event-listing-sniper) | **+$64.13** | 11/184 | Best performer. 6% win rate is the design (many tiny losses, rare big wins); +$207 lifetime |
| 🌾 Yield Harvester (perps-funding-carry) | **+$13.22** | 21 closes | Structural-edge thesis intact; shadow twin +$10 eq/7d too |
| 🌊 Tide Rider paper (crypto-trend-daily) | +$2.56 | 1/13 | One ROI winner paid for 12 small exit losses — trend-bot profile |
| 🩸 Dip Buyer (crypto-swing-daily) | $0 | 0 closes | 1 open; daily dip buyer, quiet by design |
| ⚖️ Two-Way Tide (perps-regime-switch) | −$5.36 | 1/7 | **Bunk candidate** — Index Pilot review already closed this concept (12 Jul) |
| 🚀 Breakout Hunter (crypto-breakout-4h) | −$8.69 | 2/11 | All 11 exits were exit-signal losses; weak spot confirmed |
| ⚡ Range Raider (crypto-intraday-15m) | −$13.23 | 6/27 | ATR stops −$15.57 of it; **worst bleeder**, same code as Georgia |

## 👨‍👩‍👧‍👦 Family (Kraken paper) — all four now ALSO shadowing on Lighter

| Bot | 7d P&L | 7d W/L | Notes |
|---|---|---|---|
| 🙏 Avo Maria (SwingDip 4h) | ~$0 | 0 closes | 1 open, −$0.96 unrealized |
| 🔮 Georgia (DayTrader 15m) | −$4.34 | 14/38 | ATR stops −$5.92, exit signals +$1.59 — same root cause as Range Raider |
| 👩 Mum (TrendMomo 4h) | −$5.83 | 0/4 | Unvalidated 4h speed-up of a strategy whose 1d original was retired for bleeding — **watch closely** |
| 👨 Dad (MomoBreakout 1h) | −$7.44 | 2/11 | All exit-signal losses; validated variant is 4h, this is the 1h speed-up |

Family total ≈ **−$18/wk**. Their Lighter shadow books (`freqtrade-*-lshadow`,
service `family-lighter-shadow`) went live yesterday — day-1 records, no verdicts yet.
The Kraken rows are the control arm for that comparison.

## 🕶 Shadow fleet (modelled, no real orders)
All healthy and publishing: family ×4 (day 1), Counterweight (10 open, day 2),
Snap Back (censusing, no tradeable dislocation ≥150bps yet), Funding-carry shadow
(+$10 eq/7d, 8 open), Perp Sniper shadow (idle, waits for new listings). Too young
to judge — per doctrine, no P&L citations until the records mature.

## 📊 Stocks & scanner
- **IBKR regime** (250k paper): +$64 lifetime, fresh, 2 open — fine.
- **Alpaca momentum** (98.6k paper): −$1,366 lifetime; the +$13.8k 7d equity jump
  looks like a **basis/deposit artifact, not profit** — worth checking its
  publisher's basis next weekday run.
- **Gap Scout** (cross-exchange arb): +$210 lifetime on the new basis; no
  per-trade feed; treat the level (not the trend) with caution after the recent
  basis change.

---

## ADDENDUM (later same day) — issues actioned on "fix all and proceed"

1. **Resurrected services stopped** — `perps-bot` + `triangular-arb` downed
   again (twice — every main push revives them). The durable fix
   (disconnecting their repo source via the Railway API) is permission-gated;
   until you approve it or disconnect them in the Railway UI, any main push
   revives them and I have to re-down them.
2. **Alpaca "jump" explained, no bug** — pre-7-Jul the publisher reported
   cash-only equity (~$84.8k); ~9-10 Jul it switched to full portfolio value
   with a $100k baseline. Since 10 Jul `pnl = equity − 100k` exactly.
   Pre-10-Jul history is mixed-basis; ignore it.
3. **ATR-stop bleed → investigated and FIXED (shipped to both branches):**
   - Post-exit replay of all 40 stop-outs: 77–89% reclaimed entry within 24h,
     positive post-exit drift — the 2.0x counter-trend stop fired on noise.
   - Stop-variant counterfactual on the same trades: wider stops cut the
     bleed ~40% but NO variant made the entries profitable.
   - Band analysis: `range_meanrev` losses in EVERY band bucket (fattest
     bands lost most) → the leg, not the gate, was the problem.
   - **Shipped:** `range_meanrev` sleeve retired (both carriers + Georgia's
     Lighter shadow twin, same evidence shape as the 07-12 bear_bounce
     retirement); counter-trend ATR stop 2.0x → 3.5x for the surviving
     `bounce_pullback` leg. Estimated effect: removes the ~−$14/wk leg and
     roughly a third of the remaining stop bleed.
4. **Found: five zombie Docker containers on this Mac** (`v4core v5gated
   v6swing v7momo v8momo`, up 6 days, ~/freqtrade June-era code, NO
   DATABASE_URL → publish nothing). The real fleet is Railway; these burn CPU
   trading into a local SQLite nobody reads — and v8momo is the retired
   TrendMomo. Recommend `cd ~/freqtrade && docker compose down` when
   convenient (left untouched — your call).

## Verdicts & suggested actions

1. **Stop the resurrected pair** (perps-bot, triangular-arb) in Railway — only
   item needing your hands.
2. **Bunk/hide candidates** for the new dashboard *Manage bots* panel:
   `perps-regime-switch`, `crypto-intraday-15m`, `crypto-breakout-4h` (and watch
   `freqtrade-mum`). Hiding is cosmetic + reversible; actual retirement should
   go through the usual backtest-first doctrine.
3. **One shared root cause** is costing the most paper money: the DayTraderV5Gated
   ATR-stop bleed (Range Raider −$15.6/wk + Georgia −$5.9/wk from stops alone).
   If you want one strategy investigation this week, that's the one.
4. **Winners to leave alone**: Launch Sniper, Yield Harvester, both live Lighter
   bots, IBKR.
5. Ledger-dependent analytics (learning brain, trainer, win/loss deep-dives)
   were blind 6→13 Jul; treat their outputs from this week as void.
