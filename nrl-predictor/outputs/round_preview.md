# 🏉 Round 19 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Sun 12 Jul 16:05 | 64.8% | 74.2% | +3.7 | 48 | Manly-Warringah Sea Eagles (65%, lean) |
| Melbourne Storm v Gold Coast Titans | Sun 12 Jul 18:15 | 78.0% | 71.8% | +4.5 | 48 | Melbourne Storm (78%, strong) |

**Value flags (model vs best available price, paper only):**
- North Queensland Cowboys in Manly-Warringah Sea Eagles v North Queensland Cowboys: model edge +9.4% vs consensus, EV +32.0% at best price (2 books)
- Melbourne Storm in Melbourne Storm v Gold Coast Titans: model edge +6.2% vs consensus, EV +5.3% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Melbourne Storm v Gold Coast Titans: Elo 77% vs GBM 65%