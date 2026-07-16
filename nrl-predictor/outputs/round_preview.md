# 🏉 Round 20 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Penrith Panthers v Brisbane Broncos | Thu 16 Jul 19:50 | 80.7% | 77.0% | +6.4 | 47 | Penrith Panthers (81%, strong) |
| Cronulla-Sutherland Sharks v Newcastle Knights | Fri 17 Jul 18:00 | 70.8% | 68.7% | +4.0 | 49 | Cronulla-Sutherland Sharks (71%, strong) |
| Sydney Roosters v Melbourne Storm | Fri 17 Jul 20:00 | 65.0% | 74.8% | +2.0 | 48 | Sydney Roosters (65%, lean) |
| Canberra Raiders v South Sydney Rabbitohs | Sat 18 Jul 15:00 | 54.0% | 48.9% | -0.3 | 47 | Canberra Raiders (54%, coin flip) |
| New Zealand Warriors v St George Illawarra Dragons | Sat 18 Jul 17:30 | 83.2% | 81.5% | +7.2 | 47 | New Zealand Warriors (83%, strong) |
| Canterbury-Bankstown Bulldogs v Wests Tigers | Sat 18 Jul 19:35 | 63.3% | 64.2% | +2.3 | 47 | Canterbury-Bankstown Bulldogs (63%, lean) |
| Gold Coast Titans v Manly-Warringah Sea Eagles | Sun 19 Jul 14:00 | 30.3% | 39.6% | -2.7 | 47 | Manly-Warringah Sea Eagles (70%, lean) |
| Dolphins v North Queensland Cowboys | Sun 19 Jul 16:05 | 66.6% | 58.8% | +4.1 | 50 | Dolphins (67%, lean) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in Sydney Roosters v Melbourne Storm: model edge +9.8% vs consensus, EV +34.7% at best price (4 books)
- Manly-Warringah Sea Eagles in Gold Coast Titans v Manly-Warringah Sea Eagles: model edge +9.2% vs consensus, EV +9.4% at best price (4 books)
- Dolphins in Dolphins v North Queensland Cowboys: model edge +7.8% vs consensus, EV +7.9% at best price (4 books)
- Canberra Raiders in Canberra Raiders v South Sydney Rabbitohs: model edge +5.0% vs consensus, EV +5.3% at best price (4 books)
- Penrith Panthers in Penrith Panthers v Brisbane Broncos: model edge +3.7% vs consensus, EV +0.1% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.