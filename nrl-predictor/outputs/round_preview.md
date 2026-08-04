# 🏉 Round 23 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Gold Coast Titans v North Queensland Cowboys | Thu 06 Aug 19:50 | 41.7% | 41.9% | -0.3 | 49 | North Queensland Cowboys (58%, lean) |
| New Zealand Warriors v Penrith Panthers | Fri 07 Aug 18:00 | 42.1% | 39.9% | -1.5 | 46 | Penrith Panthers (58%, coin flip) |
| Sydney Roosters v Canterbury-Bankstown Bulldogs | Fri 07 Aug 20:00 | 72.2% | 69.5% | +4.0 | 46 | Sydney Roosters (72%, strong) |
| Melbourne Storm v Manly-Warringah Sea Eagles | Sat 08 Aug 15:00 | 54.7% | 45.2% | +0.4 | 47 | Melbourne Storm (55%, coin flip) |
| Dolphins v Brisbane Broncos | Sat 08 Aug 17:30 | 75.8% | 66.2% | +4.2 | 49 | Dolphins (76%, strong) |
| South Sydney Rabbitohs v Parramatta Eels | Sat 08 Aug 19:35 | 68.0% | 69.8% | +3.7 | 49 | South Sydney Rabbitohs (68%, lean) |
| Canberra Raiders v Newcastle Knights | Sun 09 Aug 14:00 | 57.1% | 53.0% | +1.3 | 48 | Canberra Raiders (57%, coin flip) |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Sun 09 Aug 16:05 | 21.4% | 20.6% | -4.5 | 48 | Cronulla-Sutherland Sharks (79%, strong) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in Melbourne Storm v Manly-Warringah Sea Eagles: model edge +9.6% vs consensus, EV +15.0% at best price (4 books)
- Dolphins in Dolphins v Brisbane Broncos: model edge +9.6% vs consensus, EV +9.1% at best price (4 books)
- St George Illawarra Dragons in St George Illawarra Dragons v Cronulla-Sutherland Sharks: model edge +0.8% vs consensus, EV +7.0% at best price (4 books)
- New Zealand Warriors in New Zealand Warriors v Penrith Panthers: model edge +2.3% vs consensus, EV +5.3% at best price (4 books)
- Canberra Raiders in Canberra Raiders v Newcastle Knights: model edge +4.1% vs consensus, EV +3.9% at best price (4 books)
- Parramatta Eels in South Sydney Rabbitohs v Parramatta Eels: model edge +1.7% vs consensus, EV +2.2% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.