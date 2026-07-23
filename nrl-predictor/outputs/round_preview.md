# 🏉 Round 21 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Parramatta Eels v Penrith Panthers | Thu 23 Jul 19:50 | 24.1% | 19.4% | -5.2 | 48 | Penrith Panthers (76%, strong) |
| Newcastle Knights v Sydney Roosters | Fri 24 Jul 18:00 | 40.8% | 34.7% | -1.6 | 49 | Sydney Roosters (59%, lean) |
| South Sydney Rabbitohs v Melbourne Storm | Fri 24 Jul 20:00 | 51.0% | 47.2% | +0.9 | 48 | South Sydney Rabbitohs (51%, coin flip) |
| Canberra Raiders v Wests Tigers | Sat 25 Jul 15:00 | 70.0% | 77.7% | +2.7 | 48 | Canberra Raiders (70%, lean) |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors | Sat 25 Jul 17:30 | 41.8% | 37.9% | -1.9 | 44 | New Zealand Warriors (58%, lean) |
| North Queensland Cowboys v Brisbane Broncos | Sat 25 Jul 19:35 | 63.0% | 43.0% | +1.4 | 48 | North Queensland Cowboys (63%, lean) |
| St George Illawarra Dragons v Gold Coast Titans | Sun 26 Jul 14:00 | 52.4% | 51.6% | -0.8 | 47 | St George Illawarra Dragons (52%, coin flip) |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Sun 26 Jul 16:05 | 51.7% | 41.5% | +1.3 | 47 | Manly-Warringah Sea Eagles (52%, coin flip) |

**Value flags (model vs best available price, paper only):**
- North Queensland Cowboys in North Queensland Cowboys v Brisbane Broncos: model edge +20.0% vs consensus, EV +43.6% at best price (4 books)
- Wests Tigers in Canberra Raiders v Wests Tigers: model edge +7.8% vs consensus, EV +32.1% at best price (4 books)
- Parramatta Eels in Parramatta Eels v Penrith Panthers: model edge +4.8% vs consensus, EV +20.6% at best price (4 books)
- Manly-Warringah Sea Eagles in Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks: model edge +10.2% vs consensus, EV +18.8% at best price (4 books)
- Newcastle Knights in Newcastle Knights v Sydney Roosters: model edge +6.1% vs consensus, EV +12.1% at best price (4 books)
- Canterbury-Bankstown Bulldogs in Canterbury-Bankstown Bulldogs v New Zealand Warriors: model edge +3.9% vs consensus, EV +6.6% at best price (4 books)
- South Sydney Rabbitohs in South Sydney Rabbitohs v Melbourne Storm: model edge +3.8% vs consensus, EV +3.0% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Newcastle Knights v Sydney Roosters: Elo 43% vs GBM 62%