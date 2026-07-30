# 🏉 Round 22 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| North Queensland Cowboys v Sydney Roosters | Thu 30 Jul 19:50 | 43.7% | 37.9% | -1.2 | 49 | Sydney Roosters (56%, coin flip) |
| St George Illawarra Dragons v Dolphins | Fri 31 Jul 18:00 | 23.6% | 23.4% | -4.8 | 49 | Dolphins (76%, strong) |
| Melbourne Storm v Canterbury-Bankstown Bulldogs | Fri 31 Jul 20:00 | 65.5% | 36.6% | +3.2 | 46 | Melbourne Storm (65%, lean) |
| Gold Coast Titans v New Zealand Warriors | Sat 01 Aug 15:00 | 33.1% | 38.3% | -3.0 | 47 | New Zealand Warriors (67%, lean) |
| Penrith Panthers v Canberra Raiders | Sat 01 Aug 17:30 | 78.8% | 70.3% | +6.6 | 46 | Penrith Panthers (79%, strong) |
| Brisbane Broncos v Newcastle Knights | Sat 01 Aug 19:35 | 53.9% | 63.3% | +1.6 | 48 | Brisbane Broncos (54%, coin flip) |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Sun 02 Aug 14:00 | 69.0% | 74.4% | +2.1 | 48 | Cronulla-Sutherland Sharks (69%, lean) |
| Wests Tigers v Parramatta Eels | Sun 02 Aug 16:05 | 53.3% | 32.9% | +0.4 | 49 | Wests Tigers (53%, coin flip) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in Melbourne Storm v Canterbury-Bankstown Bulldogs: model edge +28.9% vs consensus, EV +73.5% at best price (4 books)
- Wests Tigers in Wests Tigers v Parramatta Eels: model edge +20.5% vs consensus, EV +54.7% at best price (4 books)
- Newcastle Knights in Brisbane Broncos v Newcastle Knights: model edge +9.4% vs consensus, EV +19.8% at best price (4 books)
- South Sydney Rabbitohs in Cronulla-Sutherland Sharks v South Sydney Rabbitohs: model edge +5.3% vs consensus, EV +16.2% at best price (4 books)
- North Queensland Cowboys in North Queensland Cowboys v Sydney Roosters: model edge +5.8% vs consensus, EV +11.4% at best price (4 books)
- Penrith Panthers in Penrith Panthers v Canberra Raiders: model edge +8.4% vs consensus, EV +7.9% at best price (4 books)
- New Zealand Warriors in Gold Coast Titans v New Zealand Warriors: model edge +5.2% vs consensus, EV +3.8% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Cronulla-Sutherland Sharks v South Sydney Rabbitohs: Elo 72% vs GBM 82%