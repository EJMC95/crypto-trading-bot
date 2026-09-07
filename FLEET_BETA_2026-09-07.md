# FLEET MARKET EXPOSURE — 2026-09-07 07:33

_Advisory. Moves no lever, no capital, no promotion. Beta is each book's per-trade return regressed on an equal-weight BTC/ETH/SOL index over **that trade's own holding window**._

## The headline, and the weighting is the finding

| weighting | fleet beta | what it asks |
|---|---|---|
| trade-weighted | **+0.043** | what does the average TRADE look like |
| **exposure-weighted** | **+0.324** | **what is the MONEY doing** |
| live cohort only | **+0.658** | what is the REAL money doing |

The gap is an averaging artifact with a name: **band-kelly-lshadow contributes 590 of 1730 labelled trades at a beta of -0.76** and a small clip, so it dominates the COUNT and almost none of the RISK. Only the exposure-weighted row is a risk statement.

## Composition — who supplies the exposure, and who pays for the hedge

| cohort | mean beta | net $ |
|---|---|---|
| books that MAKE money | **+0.40** | $+317.59 |
| books that LOSE money | **-0.12** | $-201.60 |

**A fleet that nets to zero beta by holding winners long and losers short is not hedged — it is paying for its neutrality, and the bill is the losers' P&L.**

## Per book

| book | beta | t | avg $ at risk | net $ | n | coverage |
|---|---|---|---|---|---|---|
| `perps-funding-carry-lshadow` | +0.12 | +3.26 | $1733 | $+12.92 | 30 | 100% |
| `freqtrade-mum-lighter` | +0.66 | +4.01 | $1123 | $+81.12 | 91 | 99% |
| `lighter-ticket-taker-lshadow` | +0.80 | +4.83 | $355 | $+157.92 | 186 | 100% |
| `freqtrade-avo-maria-lighter` | — | — | $222 | $+85.71 | 14 | 100% |
| `perps-funding-spread-lshadow` | -0.25 | -1.85 | $185 | $-34.99 | 155 | 100% |
| `freqtrade-mum-lshadow` | +0.58 | +4.12 | $182 | $+24.61 | 91 | 100% |
| `freqtrade-avo-maria-lshadow` | -0.08 | -0.85 | $139 | $+24.55 | 29 | 100% |
| `band-kelly-lshadow` | -0.76 | -4.86 | $83 | $-132.53 | 590 | 100% |
| `freqtrade-georgia-v3-lshadow` | +0.75 | +6.37 | $78 | $-3.18 | 95 | 100% |
| `book-bezos-lshadow` | +0.10 | +0.13 | $69 | $-24.00 | 33 | 100% |
| `freqtrade-georgia-lshadow` | +0.99 | +7.92 | $25 | $+12.85 | 266 | 99% |
| `pm-albanese-lshadow` | +0.01 | +0.04 | $21 | $-0.21 | 68 | 100% |
| `pm-turnbull-lshadow` | -0.29 | -1.46 | $7 | $+3.62 | 49 | 100% |
| `lighter-perp-sniper-lshadow` | -0.58 | -0.92 | $5 | $-6.69 | 47 | 100% |

`avg $ at risk` is time-weighted deployed capital — the weight that makes the exposure-weighted beta a risk number rather than a trade average. A book with no beta had fewer than 20 labelled closes or under 80% index coverage; it is not a claim of neutrality.

## Effective bets — what `1/HHI` over symbols cannot express

| measure | value | what it counts |
|---|---|---|
| distinct symbols held | 29 | the raw count |
| `fleet_risk.long_effective_n` (`1/HHI`) | 11.8 | concentration ACROSS symbols, blind to whether they move together |
| **correlation-aware N_eff** | **2.8** | independence — collapses toward 1 as the held names correlate |

**The incumbent overstates independence by 4.2x on the currently held set** (29 of 29 held names priced). `fleet_risk`'s own docstring already warns that *"23 open longs that are all crypto beta is ~one trade, and nothing said so"* — the warning is correct and `1/HHI` over symbols cannot express it.

**NOTHING HERE MODIFIES `fleet_risk`.** That field feeds live consumers and the audit's safety constraints forbid touching filters that affect existing bots. This publishes the alternative BESIDE the incumbent so the two can be compared before anyone decides to move one.
