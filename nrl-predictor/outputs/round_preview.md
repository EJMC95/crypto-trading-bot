# 🏉 Round 27 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos | Thu 03 Sep 19:50 | 64.2% | 71.5% | +1.0 | 46 | Canterbury-Bankstown Bulldogs (64%, lean) |
| Gold Coast Titans v Dolphins | Fri 04 Sep 18:00 | 22.2% | 23.8% | -3.1 | 49 | Dolphins (78%, strong) |
| South Sydney Rabbitohs v Sydney Roosters | Fri 04 Sep 20:00 | 47.1% | 86.8% | +0.2 | 48 | Sydney Roosters (53%, coin flip) |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Sat 05 Sep 15:00 | 66.4% | 72.2% | +1.4 | 46 | New Zealand Warriors (66%, lean) |
| North Queensland Cowboys v Canberra Raiders | Sat 05 Sep 17:30 | 58.7% | 61.7% | +1.4 | 48 | North Queensland Cowboys (59%, lean) |
| Cronulla-Sutherland Sharks v Melbourne Storm | Sat 05 Sep 19:35 | 60.0% | 31.0% | +2.2 | 48 | Cronulla-Sutherland Sharks (60%, lean) |
| St George Illawarra Dragons v Parramatta Eels | Sun 06 Sep 14:00 | 41.7% | 41.6% | -1.0 | 48 | Parramatta Eels (58%, lean) |
| Penrith Panthers v Wests Tigers | Sun 06 Sep 16:05 | 87.1% | 87.2% | +8.3 | 48 | Penrith Panthers (87%, strong) |

**Value flags (model vs best available price, paper only):**
- Sydney Roosters in South Sydney Rabbitohs v Sydney Roosters: model edge +39.8% vs consensus, EV +297.0% at best price (4 books)
- Cronulla-Sutherland Sharks in Cronulla-Sutherland Sharks v Melbourne Storm: model edge +29.0% vs consensus, EV +85.9% at best price (4 books)
- Brisbane Broncos in Canterbury-Bankstown Bulldogs v Brisbane Broncos: model edge +7.2% vs consensus, EV +19.8% at best price (4 books)
- Manly-Warringah Sea Eagles in New Zealand Warriors v Manly-Warringah Sea Eagles: model edge +5.7% vs consensus, EV +17.5% at best price (4 books)
- Canberra Raiders in North Queensland Cowboys v Canberra Raiders: model edge +3.0% vs consensus, EV +7.4% at best price (4 books)
- Wests Tigers in Penrith Panthers v Wests Tigers: model edge +0.1% vs consensus, EV +0.2% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Gold Coast Titans v Dolphins: Elo 26% vs GBM 38%