# 🏉 Round 23 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Gold Coast Titans v North Queensland Cowboys | Thu 06 Aug 19:50 | 41.6% | 42.4% | -0.3 | 49 | North Queensland Cowboys (58%, lean) |
| New Zealand Warriors v Penrith Panthers | Fri 07 Aug 18:00 | 43.7% | 41.7% | -1.5 | 46 | Penrith Panthers (56%, coin flip) |
| Sydney Roosters v Canterbury-Bankstown Bulldogs | Fri 07 Aug 20:00 | 72.8% | 70.2% | +4.0 | 46 | Sydney Roosters (73%, strong) |
| Melbourne Storm v Manly-Warringah Sea Eagles | Sat 08 Aug 15:00 | 56.6% | 45.2% | +0.4 | 47 | Melbourne Storm (57%, coin flip) |
| Dolphins v Brisbane Broncos | Sat 08 Aug 17:30 | 74.2% | 66.2% | +4.2 | 49 | Dolphins (74%, strong) |
| South Sydney Rabbitohs v Parramatta Eels | Sat 08 Aug 19:35 | 67.9% | 70.7% | +3.7 | 49 | South Sydney Rabbitohs (68%, lean) |
| Canberra Raiders v Newcastle Knights | Sun 09 Aug 14:00 | 58.0% | 51.7% | +1.3 | 48 | Canberra Raiders (58%, coin flip) |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Sun 09 Aug 16:05 | 21.3% | 20.7% | -4.5 | 48 | Cronulla-Sutherland Sharks (79%, strong) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in Melbourne Storm v Manly-Warringah Sea Eagles: model edge +11.4% vs consensus, EV +18.8% at best price (4 books)
- Canberra Raiders in Canberra Raiders v Newcastle Knights: model edge +6.3% vs consensus, EV +9.0% at best price (4 books)
- Dolphins in Dolphins v Brisbane Broncos: model edge +8.0% vs consensus, EV +6.8% at best price (4 books)
- St George Illawarra Dragons in St George Illawarra Dragons v Cronulla-Sutherland Sharks: model edge +0.6% vs consensus, EV +6.5% at best price (4 books)
- New Zealand Warriors in New Zealand Warriors v Penrith Panthers: model edge +2.1% vs consensus, EV +6.2% at best price (4 books)
- Parramatta Eels in South Sydney Rabbitohs v Parramatta Eels: model edge +2.8% vs consensus, EV +6.0% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.