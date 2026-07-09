# H100 Opportunity Scout — 2026-07-09

**Ask:** have the bots scout "H100" as an opportunity today.
**Verdict: NO TRADE — no tradable H100 instrument exists on any venue the fleet
operates on, and the only real H100 instrument (a Swedish micro-cap equity)
fails every liquidity and scope gate we have.** No config, whitelist, or bot
change is warranted. If an H100 *token* ever lists, the event-listing-sniper
catches it automatically — that is exactly the event class it was built for.

---

## 1. What "H100" actually is

There is **no cryptocurrency with ticker H100**. The name resolves to two
real-world things:

1. **H100 Group AB** — a Stockholm-listed (Nasdaq First North, ticker `H100`)
   health-tech company that pivoted into a MicroStrategy-style **Bitcoin
   treasury** play. Holds ~1,046 BTC per recent reporting, proposed
   acquisitions in March 2026 targeting a 3,500 BTC treasury ("Europe's
   largest"), and plans a Bitcoin financial platform in 2026.
   Secondary lines: `HOGPF` (US OTC), `GS9` (Frankfurt/Munich/Stuttgart).
2. **Nvidia's H100 GPU** — a chip, not an instrument. (There is also an
   unrelated Australian ETF that reuses the H100 ticker on the ASX.)

## 2. Venue scan — run live 2026-07-09

| Venue (who trades there) | Method | Result |
|---|---|---|
| Kraken (dad, avo-maria) | full `AssetPairs` scan | **no H100 pair** |
| Binance (mum, dad, georgia) | direct API geo-blocked; cross-checked via CoinGecko + announcement feed | **no H100 pair** |
| Crypto.com (spot bots' data feed) | `H100_USD` ticker lookup | **not found** |
| Hyperliquid (perps bots, momo) | full perps `universe` scan | **no H100 perp** |
| CoinGecko (sniper's footprint check) | `search?query=h100` | **zero coins** — no such token exists anywhere |
| Binance/Bybit/KuCoin/Upbit new-listing feeds | ran `listing_intel.refresh_announced()` live (18 current announcements) | **H100 not announced** |

The CoinGecko zero-footprint result is the decisive one: it is not that H100 is
merely unlisted on our venues — **no H100 token exists at all**, on any
tracked exchange or chain.

## 3. The equity, for completeness

| Line | Last | 1-mo | 52-wk range | Liquidity |
|---|---|---|---|---|
| HOGPF (US OTC) | $0.082 | **−45%** | $0.0001 – $1.40 | ~5k sh/day ≈ **$400/day** |
| GS9 (Frankfurt) | €0.10 | −1% (pinned) | €0.093 – €1.10 | near-zero, most days 0 volume |

Context: the July 2025 capital raise (~$54M of a ~$96M total) was priced at
SEK 6.38/share; the stock now trades roughly **88% below that raise price**
and ~94% off its 52-week high, while the company continues issuing
shares/convertibles to buy BTC.

## 4. Why this is a NO for the fleet

1. **Crypto bots (17 of 19):** nothing to whitelist — the instrument does not
   exist. Any "H100 coin" that appears in a search result is noise or a
   yet-unlaunched contract; exactly the ALABON/TERON junk class the sniper's
   intel gate now quarter-stakes or skips.
2. **Equity bots:** `equities-momentum-alpaca` cannot reach OTC or Stockholm;
   `equities-regime-ibkr` trades SPY/QQQ only. Even ignoring scope, a $1,000
   account cannot trade an instrument doing $400/day of dollar volume — one
   ticket would be >2x the daily tape, with no exit.
3. **The thesis is redundant:** H100 Group is a leveraged-BTC proxy. The fleet
   already holds direct, liquid BTC exposure across five-plus bots with real
   fills and real exits. Taking the same beta through an illiquid, serially
   diluting foreign micro-cap adds only basis risk and a liquidity trap.
4. **Fundamental profile:** treasury-company mNAV premium stories are
   discretionary lottery tickets, not systematic-bot instruments. Down 45% in
   a month into ongoing dilution is not a dip signal our strategies are built
   to judge.

## 5. What would change the verdict

- **An actual H100 token lists on a tracked exchange** → `listing_sniper.py`
  enters automatically and `listing_intel.py` sizes it by announcement +
  footprint quality. No pre-work needed or possible; a pre-listing whitelist
  entry would do nothing.
- **The equity migrates to a liquid US listing** (real NASDAQ, not OTC) with
  meaningful volume → re-scout as an equities-bot candidate; would still need
  a strategy that trades single names, which neither equity bot currently is.

## Sources

- [H100 Group](https://www.h100.group/) · [bitcointreasuries.net profile](https://bitcointreasuries.net/public-companies/h100-group)
- [CoinDesk 2026-03-23 — H100 eyes Europe's largest bitcoin treasury (3,500 BTC via acquisitions)](https://www.coindesk.com/markets/2026/03/23/h100-eyes-europe-s-largest-bitcoin-treasury-with-3-500-btc-in-proposed-acquistions)
- [Phemex — H100 to build Bitcoin financial platform in 2026, holds 1,046 BTC](https://phemex.com/news/article/h100-to-launch-bitcoin-financial-platform-in-2026-holds-1046-btc-50942)
- [crypto.news — H100 Group raises $54M for Bitcoin treasury strategy](https://crypto.news/h100-group-raises-54-million-for-its-bitcoin-treasury-strategy/) · [ChainCatcher — total raised ~$96M](https://www.chaincatcher.com/en/article/2190405)
- Market data: Yahoo Finance public chart API (HOGPF, GS9.F), Kraken `AssetPairs`, Hyperliquid `info/meta`, CoinGecko `search`, Crypto.com ticker lookup — all queried live 2026-07-09.
