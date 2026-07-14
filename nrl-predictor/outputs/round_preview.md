# 🏉 Round 20 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Penrith Panthers v Brisbane Broncos | Thu 16 Jul 19:50 | 82.7% | 79.3% | +6.4 | 47 | Penrith Panthers (83%, strong) |
| Cronulla-Sutherland Sharks v Newcastle Knights | Fri 17 Jul 18:00 | 71.4% | 61.3% | +4.0 | 49 | Cronulla-Sutherland Sharks (71%, strong) |
| Sydney Roosters v Melbourne Storm | Fri 17 Jul 20:00 | 63.2% | 74.6% | +2.0 | 48 | Sydney Roosters (63%, lean) |
| Canberra Raiders v South Sydney Rabbitohs | Sat 18 Jul 15:00 | 53.8% | 52.4% | -0.3 | 47 | Canberra Raiders (54%, coin flip) |
| New Zealand Warriors v St George Illawarra Dragons | Sat 18 Jul 17:35 | 82.9% | 81.5% | +7.2 | 47 | New Zealand Warriors (83%, strong) |
| Canterbury-Bankstown Bulldogs v Wests Tigers | Sat 18 Jul 19:35 | 64.7% | 62.3% | +2.3 | 47 | Canterbury-Bankstown Bulldogs (65%, lean) |
| Gold Coast Titans v Manly-Warringah Sea Eagles | Sun 19 Jul 14:00 | 31.0% | 39.6% | -2.7 | 47 | Manly-Warringah Sea Eagles (69%, lean) |
| Dolphins v North Queensland Cowboys | Sun 19 Jul 16:05 | 66.7% | 58.8% | +4.1 | 50 | Dolphins (67%, lean) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in Sydney Roosters v Melbourne Storm: model edge +11.4% vs consensus, EV +41.7% at best price (4 books)
- Cronulla-Sutherland Sharks in Cronulla-Sutherland Sharks v Newcastle Knights: model edge +10.2% vs consensus, EV +12.1% at best price (4 books)
- Manly-Warringah Sea Eagles in Gold Coast Titans v Manly-Warringah Sea Eagles: model edge +8.5% vs consensus, EV +8.3% at best price (4 books)
- Dolphins in Dolphins v North Queensland Cowboys: model edge +7.8% vs consensus, EV +8.0% at best price (4 books)
- Canterbury-Bankstown Bulldogs in Canterbury-Bankstown Bulldogs v Wests Tigers: model edge +2.3% vs consensus, EV +1.5% at best price (4 books)
- Penrith Panthers in Penrith Panthers v Brisbane Broncos: model edge +3.4% vs consensus, EV +0.1% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.