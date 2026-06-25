# Freqtrade Weekly Deep-Dive — Mon 22 Jun 2026

Dry-run / paper money ($1000 each), Kraken, BTC/USD + ETH/USD. Not financial advice.

## Headline: all 4 bots were DOWN — now restarted

The big finding this week is operational, not strategic. **All four bots stopped on Wed 18 Jun at ~17:54 local and had been offline for ~4 days.** No containers were running and nothing was listening on ports 8084–8087. I restarted them per the runbook (`docker compose up -d`); all four are back up with fresh `RUNNING` heartbeats as of ~09:08 local today.

Because they were offline, there is **no new trade activity this week**, and the trade databases are empty across all four (zero closed trades on record). So win rates, P/L and drawdown are all N/A — there's simply nothing to read into the strategies yet.

## Status table

| Bot | Running now | Trades (7d) | Realized P/L total | Win % | Open |
|-----|-------------|-------------|--------------------|-------|------|
| v4core (ImprovedStrategyV4, daily trend) | ✅ restarted | 0 | $0.00 | N/A | 0 |
| v5gated (DayTraderV5Gated, 5m regime-gated) | ✅ restarted | 0 | $0.00 | N/A | 0 |
| v6swing (SwingDipV1, daily dip-buyer) | ✅ restarted | 0 | $0.00 | N/A | 0 |
| v7momo (MomoBreakoutV1, 4h breakout) | ✅ restarted | 0 | $0.00 | N/A | 0 |

## How they stopped

The logs are clean — each bot logged normal `RUNNING` heartbeats right up to the last entry on 18 Jun, then simply stopped. **No tracebacks, no crash, no out-of-memory.** This looks like a host/Docker shutdown or a manual stop on the 18th that was never brought back up, rather than a strategy or code fault.

The only ERROR lines in the logs are a Telegram misconfiguration — the token is still the placeholder `PASTE_YOUR_FULL_TOKEN_HERE`, so Telegram notifications never connect. This is harmless to trading (it doesn't stop the bot or affect orders) but it does mean you get no phone alerts when something like this 4-day outage happens. Worth fixing if you want to be notified.

## Plain-English read

With four days of downtime and empty databases, there's nothing to judge the strategies on this week. For context on what "normal" looks like once they're running: v4core mostly holds/sits and rarely trades; v5gated only trades when the daily trend is up; v6swing only buys dips inside an uptrend; v7momo catches 4h breakouts and ~40% win rate is normal for it. None of these are high-frequency, so even a healthy week can show few or zero trades — but four still-empty databases after weeks of running means **v5gated and v7momo have yet to fire a single trade in a confirmed UP regime**, which remains the unproven case worth watching once uptime is restored.

## Action items

1. **Done — bots restarted.** All four (plus v8momo) are running again. Verify they stay up over the next day; the real question is why they stopped on the 18th and whether they'll auto-restart after the next reboot.
2. **Consider `restart: unless-stopped`** in `docker-compose.yml` so a host reboot brings the bots back automatically instead of leaving them down for days. This outage cost a full week of paper data.
3. **Optional — fix the Telegram token** (replace `PASTE_YOUR_FULL_TOKEN_HERE`) so you actually get alerted to outages and fills.
4. **Next week** should be the first clean read on whether v5gated/v7momo trade in an up regime — assuming uptime holds.

---
*Generated automatically. Dry-run paper trading only; not financial advice.*
