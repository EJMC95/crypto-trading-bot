# 🏉 Round 25 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Melbourne Storm v Penrith Panthers | Thu 20 Aug 19:50 | 39.7% | 31.8% | -2.5 | 47 | Penrith Panthers (60%, lean) |
| Canberra Raiders v Brisbane Broncos | Fri 21 Aug 18:00 | 65.1% | 71.9% | +0.9 | 47 | Canberra Raiders (65%, lean) |
| Dolphins v Parramatta Eels | Fri 21 Aug 20:00 | 79.8% | 76.2% | +5.3 | 50 | Dolphins (80%, strong) |
| Newcastle Knights v Manly-Warringah Sea Eagles | Sat 22 Aug 15:00 | 54.1% | 66.0% | -1.6 | 48 | Newcastle Knights (54%, coin flip) |
| South Sydney Rabbitohs v New Zealand Warriors | Sat 22 Aug 17:30 | 46.2% | 38.3% | -0.1 | 47 | New Zealand Warriors (54%, coin flip) |
| St George Illawarra Dragons v Canterbury-Bankstown Bulldogs | Sat 22 Aug 19:35 | 39.5% | 36.0% | -1.6 | 45 | Canterbury-Bankstown Bulldogs (61%, lean) |
| Gold Coast Titans v Cronulla-Sutherland Sharks | Sun 23 Aug 14:00 | 28.5% | 35.8% | -2.7 | 48 | Cronulla-Sutherland Sharks (72%, strong) |
| Sydney Roosters v Wests Tigers | Sun 23 Aug 16:05 | 84.2% | 89.7% | +5.6 | 49 | Sydney Roosters (84%, strong) |

**Value flags (model vs best available price, paper only):**
- Wests Tigers in Sydney Roosters v Wests Tigers: model edge +5.5% vs consensus, EV +66.2% at best price (4 books)
- Manly-Warringah Sea Eagles in Newcastle Knights v Manly-Warringah Sea Eagles: model edge +11.9% vs consensus, EV +32.1% at best price (4 books)
- Brisbane Broncos in Canberra Raiders v Brisbane Broncos: model edge +6.8% vs consensus, EV +27.4% at best price (4 books)
- Melbourne Storm in Melbourne Storm v Penrith Panthers: model edge +7.8% vs consensus, EV +21.0% at best price (4 books)
- South Sydney Rabbitohs in South Sydney Rabbitohs v New Zealand Warriors: model edge +7.9% vs consensus, EV +15.5% at best price (4 books)
- St George Illawarra Dragons in St George Illawarra Dragons v Canterbury-Bankstown Bulldogs: model edge +3.4% vs consensus, EV +8.6% at best price (4 books)
- Cronulla-Sutherland Sharks in Gold Coast Titans v Cronulla-Sutherland Sharks: model edge +7.4% vs consensus, EV +7.3% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Canberra Raiders v Brisbane Broncos: Elo 67% vs GBM 78%
- Gold Coast Titans v Cronulla-Sutherland Sharks: Elo 33% vs GBM 43%