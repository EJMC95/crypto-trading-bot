# 🏉 Round 26 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Brisbane Broncos v Melbourne Storm | Thu 27 Aug 19:50 | 44.4% | 51.0% | -0.4 | 48 | Melbourne Storm (56%, coin flip) |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Fri 28 Aug 18:00 | 80.6% | 66.7% | +7.3 | 47 | Manly-Warringah Sea Eagles (81%, strong) |
| Penrith Panthers v Canterbury-Bankstown Bulldogs | Fri 28 Aug 20:00 | 78.7% | 69.5% | +6.5 | 45 | Penrith Panthers (79%, strong) |
| Gold Coast Titans v South Sydney Rabbitohs | Sat 29 Aug 15:00 | 37.5% | 32.2% | -1.8 | 48 | South Sydney Rabbitohs (62%, lean) |
| Sydney Roosters v Dolphins | Sat 29 Aug 17:30 | 57.5% | 61.3% | +0.9 | 49 | Sydney Roosters (58%, coin flip) |
| North Queensland Cowboys v Wests Tigers | Sat 29 Aug 19:35 | 72.4% | 72.9% | +3.1 | 50 | North Queensland Cowboys (72%, strong) |
| New Zealand Warriors v Newcastle Knights | Sun 30 Aug 14:00 | 71.8% | 67.1% | +4.1 | 48 | New Zealand Warriors (72%, strong) |
| Parramatta Eels v Cronulla-Sutherland Sharks | Sun 30 Aug 16:05 | 32.7% | 34.7% | -2.3 | 48 | Cronulla-Sutherland Sharks (67%, lean) |

**Value flags (model vs best available price, paper only):**
- Manly-Warringah Sea Eagles in Manly-Warringah Sea Eagles v St George Illawarra Dragons: model edge +13.8% vs consensus, EV +14.4% at best price (3 books)
- Gold Coast Titans in Gold Coast Titans v South Sydney Rabbitohs: model edge +5.3% vs consensus, EV +10.7% at best price (3 books)
- Melbourne Storm in Brisbane Broncos v Melbourne Storm: model edge +6.6% vs consensus, EV +8.4% at best price (3 books)
- Penrith Panthers in Penrith Panthers v Canterbury-Bankstown Bulldogs: model edge +9.2% vs consensus, EV +7.8% at best price (3 books)
- Wests Tigers in North Queensland Cowboys v Wests Tigers: model edge +0.6% vs consensus, EV +5.1% at best price (3 books)
- Dolphins in Sydney Roosters v Dolphins: model edge +3.7% vs consensus, EV +4.1% at best price (3 books)
- New Zealand Warriors in New Zealand Warriors v Newcastle Knights: model edge +4.6% vs consensus, EV +1.9% at best price (3 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Parramatta Eels v Cronulla-Sutherland Sharks: Elo 38% vs GBM 50%