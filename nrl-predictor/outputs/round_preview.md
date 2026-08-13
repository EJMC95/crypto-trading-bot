# 🏉 Round 24 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Penrith Panthers v Sydney Roosters | Thu 13 Aug 19:50 | 61.2% | 61.9% | +4.2 | 47 | Penrith Panthers (61%, lean) |
| Manly-Warringah Sea Eagles v Dolphins | Fri 14 Aug 18:00 | 47.1% | 29.1% | +1.2 | 48 | Dolphins (53%, coin flip) |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Fri 14 Aug 20:00 | 55.8% | 58.8% | -0.7 | 46 | Canterbury-Bankstown Bulldogs (56%, coin flip) |
| Cronulla-Sutherland Sharks v Canberra Raiders | Sat 15 Aug 15:00 | 70.5% | 72.5% | +3.6 | 47 | Cronulla-Sutherland Sharks (70%, strong) |
| Parramatta Eels v North Queensland Cowboys | Sat 15 Aug 17:30 | 46.1% | 38.3% | +0.1 | 49 | North Queensland Cowboys (54%, coin flip) |
| Brisbane Broncos v New Zealand Warriors | Sat 15 Aug 19:35 | 36.6% | 34.2% | -1.2 | 46 | New Zealand Warriors (63%, lean) |
| Newcastle Knights v Gold Coast Titans | Sun 16 Aug 14:00 | 73.1% | 77.6% | +2.4 | 49 | Newcastle Knights (73%, strong) |
| Wests Tigers v St George Illawarra Dragons | Sun 16 Aug 16:05 | 62.8% | 50.5% | +3.0 | 48 | Wests Tigers (63%, lean) |

**Value flags (model vs best available price, paper only):**
- Manly-Warringah Sea Eagles in Manly-Warringah Sea Eagles v Dolphins: model edge +18.0% vs consensus, EV +60.2% at best price (4 books)
- Parramatta Eels in Parramatta Eels v North Queensland Cowboys: model edge +7.8% vs consensus, EV +19.7% at best price (4 books)
- Wests Tigers in Wests Tigers v St George Illawarra Dragons: model edge +12.3% vs consensus, EV +19.4% at best price (4 books)
- Gold Coast Titans in Newcastle Knights v Gold Coast Titans: model edge +4.5% vs consensus, EV +14.2% at best price (4 books)
- South Sydney Rabbitohs in Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs: model edge +3.0% vs consensus, EV +5.2% at best price (4 books)
- Canberra Raiders in Cronulla-Sutherland Sharks v Canberra Raiders: model edge +2.1% vs consensus, EV +3.3% at best price (4 books)
- Brisbane Broncos in Brisbane Broncos v New Zealand Warriors: model edge +2.5% vs consensus, EV +2.5% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Manly-Warringah Sea Eagles v Dolphins: Elo 48% vs GBM 60%