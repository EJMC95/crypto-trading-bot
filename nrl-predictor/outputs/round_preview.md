# 🏉 Round 20 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Penrith Panthers v Brisbane Broncos | Thu 16 Jul 19:50 | 82.7% | 80.4% | +6.4 | 47 | Penrith Panthers (83%, strong) |
| Cronulla-Sutherland Sharks v Newcastle Knights | Fri 17 Jul 18:00 | 71.4% | 60.5% | +4.0 | 49 | Cronulla-Sutherland Sharks (71%, strong) |
| Sydney Roosters v Melbourne Storm | Fri 17 Jul 20:00 | 63.2% | 65.2% | +2.0 | 48 | Sydney Roosters (63%, lean) |
| Canberra Raiders v South Sydney Rabbitohs | Sat 18 Jul 15:00 | 53.8% | 52.8% | -0.3 | 47 | Canberra Raiders (54%, coin flip) |
| New Zealand Warriors v St George Illawarra Dragons | Sat 18 Jul 17:35 | 82.9% | 80.9% | +7.2 | 47 | New Zealand Warriors (83%, strong) |
| Canterbury-Bankstown Bulldogs v Wests Tigers | Sat 18 Jul 19:35 | 64.7% | 63.8% | +2.3 | 47 | Canterbury-Bankstown Bulldogs (65%, lean) |
| Gold Coast Titans v Manly-Warringah Sea Eagles | Sun 19 Jul 14:00 | 31.0% | 38.6% | -2.7 | 47 | Manly-Warringah Sea Eagles (69%, lean) |
| Dolphins v North Queensland Cowboys | Sun 19 Jul 16:05 | 66.7% | 58.6% | +4.1 | 50 | Dolphins (67%, lean) |

**Value flags (model vs best available price, paper only):**
- Cronulla-Sutherland Sharks in Cronulla-Sutherland Sharks v Newcastle Knights: model edge +10.9% vs consensus, EV +14.2% at best price (4 books)
- Dolphins in Dolphins v North Queensland Cowboys: model edge +8.1% vs consensus, EV +8.7% at best price (4 books)
- Manly-Warringah Sea Eagles in Gold Coast Titans v Manly-Warringah Sea Eagles: model edge +7.6% vs consensus, EV +6.9% at best price (4 books)
- Melbourne Storm in Sydney Roosters v Melbourne Storm: model edge +2.0% vs consensus, EV +1.2% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.