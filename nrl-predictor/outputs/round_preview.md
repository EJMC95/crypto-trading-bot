# 🏉 Round 27 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos | Thu 03 Sep 19:50 | 64.3% | 71.5% | +1.0 | 46 | Canterbury-Bankstown Bulldogs (64%, lean) |
| Gold Coast Titans v Dolphins | Fri 04 Sep 18:00 | 22.8% | 23.8% | -3.1 | 49 | Dolphins (77%, strong) |
| South Sydney Rabbitohs v Sydney Roosters | Fri 04 Sep 20:00 | 45.0% | 86.8% | +0.2 | 48 | Sydney Roosters (55%, coin flip) |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Sat 05 Sep 15:00 | 66.0% | 72.6% | +1.4 | 46 | New Zealand Warriors (66%, lean) |
| North Queensland Cowboys v Canberra Raiders | Sat 05 Sep 17:30 | 60.3% | 61.3% | +1.4 | 48 | North Queensland Cowboys (60%, lean) |
| Cronulla-Sutherland Sharks v Melbourne Storm | Sat 05 Sep 19:35 | 62.3% | 30.5% | +2.1 | 48 | Cronulla-Sutherland Sharks (62%, lean) |
| St George Illawarra Dragons v Parramatta Eels | Sun 06 Sep 14:00 | 44.2% | 43.3% | -1.0 | 48 | Parramatta Eels (56%, coin flip) |
| Penrith Panthers v Wests Tigers | Sun 06 Sep 16:05 | 87.6% | 87.2% | +8.3 | 48 | Penrith Panthers (88%, strong) |

**Value flags (model vs best available price, paper only):**
- Sydney Roosters in South Sydney Rabbitohs v Sydney Roosters: model edge +41.9% vs consensus, EV +312.9% at best price (4 books)
- Cronulla-Sutherland Sharks in Cronulla-Sutherland Sharks v Melbourne Storm: model edge +31.8% vs consensus, EV +96.1% at best price (4 books)
- Brisbane Broncos in Canterbury-Bankstown Bulldogs v Brisbane Broncos: model edge +7.2% vs consensus, EV +19.7% at best price (4 books)
- Manly-Warringah Sea Eagles in New Zealand Warriors v Manly-Warringah Sea Eagles: model edge +6.7% vs consensus, EV +19.2% at best price (4 books)
- St George Illawarra Dragons in St George Illawarra Dragons v Parramatta Eels: model edge +0.9% vs consensus, EV +1.6% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Gold Coast Titans v Dolphins: Elo 26% vs GBM 38%