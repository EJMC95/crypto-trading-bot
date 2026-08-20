# 🏉 Round 25 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Melbourne Storm v Penrith Panthers | Thu 20 Aug 19:50 | 40.7% | 31.8% | -2.5 | 47 | Penrith Panthers (59%, lean) |
| Canberra Raiders v Brisbane Broncos | Fri 21 Aug 18:00 | 65.6% | 72.9% | +0.9 | 47 | Canberra Raiders (66%, lean) |
| Dolphins v Parramatta Eels | Fri 21 Aug 20:00 | 78.8% | 76.2% | +5.3 | 50 | Dolphins (79%, strong) |
| Newcastle Knights v Manly-Warringah Sea Eagles | Sat 22 Aug 15:00 | 52.9% | 65.8% | -1.6 | 48 | Newcastle Knights (53%, coin flip) |
| South Sydney Rabbitohs v New Zealand Warriors | Sat 22 Aug 17:30 | 45.6% | 38.5% | -0.1 | 47 | New Zealand Warriors (54%, coin flip) |
| St George Illawarra Dragons v Canterbury-Bankstown Bulldogs | Sat 22 Aug 19:35 | 37.7% | 35.8% | -1.6 | 45 | Canterbury-Bankstown Bulldogs (62%, lean) |
| Gold Coast Titans v Cronulla-Sutherland Sharks | Sun 23 Aug 14:00 | 28.0% | 36.0% | -2.7 | 48 | Cronulla-Sutherland Sharks (72%, strong) |
| Sydney Roosters v Wests Tigers | Sun 23 Aug 16:05 | 85.0% | 88.9% | +5.6 | 49 | Sydney Roosters (85%, strong) |

**Value flags (model vs best available price, paper only):**
- Wests Tigers in Sydney Roosters v Wests Tigers: model edge +3.9% vs consensus, EV +65.5% at best price (4 books)
- Manly-Warringah Sea Eagles in Newcastle Knights v Manly-Warringah Sea Eagles: model edge +12.8% vs consensus, EV +34.1% at best price (4 books)
- Brisbane Broncos in Canberra Raiders v Brisbane Broncos: model edge +7.3% vs consensus, EV +22.2% at best price (4 books)
- Melbourne Storm in Melbourne Storm v Penrith Panthers: model edge +8.9% vs consensus, EV +22.1% at best price (4 books)
- South Sydney Rabbitohs in South Sydney Rabbitohs v New Zealand Warriors: model edge +7.1% vs consensus, EV +14.1% at best price (4 books)
- Cronulla-Sutherland Sharks in Gold Coast Titans v Cronulla-Sutherland Sharks: model edge +8.1% vs consensus, EV +8.0% at best price (4 books)
- St George Illawarra Dragons in St George Illawarra Dragons v Canterbury-Bankstown Bulldogs: model edge +1.8% vs consensus, EV +3.6% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Canberra Raiders v Brisbane Broncos: Elo 67% vs GBM 78%
- Gold Coast Titans v Cronulla-Sutherland Sharks: Elo 33% vs GBM 43%