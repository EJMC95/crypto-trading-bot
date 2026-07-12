# 🏉 Round 19 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| South Sydney Rabbitohs v Newcastle Knights | Sun 12 Jul 14:00 | 58.8% | 47.6% | +3.2 | 49 | South Sydney Rabbitohs (59%, lean) |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Sun 12 Jul 16:05 | 63.2% | 66.4% | +3.7 | 48 | Manly-Warringah Sea Eagles (63%, lean) |
| Melbourne Storm v Gold Coast Titans | Sun 12 Jul 18:15 | 75.6% | 71.8% | +4.5 | 48 | Melbourne Storm (76%, strong) |

**Value flags (model vs best available price, paper only):**
- South Sydney Rabbitohs in South Sydney Rabbitohs v Newcastle Knights: model edge +11.2% vs consensus, EV +17.7% at best price (4 books)
- North Queensland Cowboys in Manly-Warringah Sea Eagles v North Queensland Cowboys: model edge +3.2% vs consensus, EV +4.8% at best price (4 books)
- Melbourne Storm in Melbourne Storm v Gold Coast Titans: model edge +3.8% vs consensus, EV +2.1% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Melbourne Storm v Gold Coast Titans: Elo 77% vs GBM 64%