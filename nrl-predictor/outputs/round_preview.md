# 🏉 Round 21 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Parramatta Eels v Penrith Panthers | Thu 23 Jul 19:50 | 24.1% | 20.2% | -5.2 | 48 | Penrith Panthers (76%, strong) |
| Newcastle Knights v Sydney Roosters | Fri 24 Jul 18:00 | 40.8% | 45.4% | -1.6 | 49 | Sydney Roosters (59%, lean) |
| South Sydney Rabbitohs v Melbourne Storm | Fri 24 Jul 20:00 | 51.0% | 62.7% | +0.9 | 48 | South Sydney Rabbitohs (51%, coin flip) |
| Canberra Raiders v Wests Tigers | Sat 25 Jul 15:00 | 69.9% | 76.3% | +2.7 | 48 | Canberra Raiders (70%, lean) |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors | Sat 25 Jul 17:30 | 41.8% | 37.4% | -1.9 | 44 | New Zealand Warriors (58%, lean) |
| North Queensland Cowboys v Brisbane Broncos | Sat 25 Jul 19:35 | 63.0% | 46.5% | +1.4 | 48 | North Queensland Cowboys (63%, lean) |
| St George Illawarra Dragons v Gold Coast Titans | Sun 26 Jul 14:00 | 52.3% | 50.5% | -0.8 | 47 | St George Illawarra Dragons (52%, coin flip) |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Sun 26 Jul 16:05 | 51.6% | 42.3% | +1.3 | 47 | Manly-Warringah Sea Eagles (52%, coin flip) |

**Value flags (model vs best available price, paper only):**
- Melbourne Storm in South Sydney Rabbitohs v Melbourne Storm: model edge +11.7% vs consensus, EV +32.3% at best price (4 books)
- Wests Tigers in Canberra Raiders v Wests Tigers: model edge +6.5% vs consensus, EV +29.6% at best price (4 books)
- North Queensland Cowboys in North Queensland Cowboys v Brisbane Broncos: model edge +16.6% vs consensus, EV +29.2% at best price (4 books)
- Manly-Warringah Sea Eagles in Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks: model edge +9.3% vs consensus, EV +21.4% at best price (4 books)
- Parramatta Eels in Parramatta Eels v Penrith Panthers: model edge +3.9% vs consensus, EV +15.8% at best price (4 books)
- Canterbury-Bankstown Bulldogs in Canterbury-Bankstown Bulldogs v New Zealand Warriors: model edge +4.4% vs consensus, EV +8.6% at best price (4 books)
- Sydney Roosters in Newcastle Knights v Sydney Roosters: model edge +4.7% vs consensus, EV +3.7% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Newcastle Knights v Sydney Roosters: Elo 43% vs GBM 62%