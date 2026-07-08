# 🏉 Round 19 preview — model probabilities

_Blend = Elo+Poisson logistic stack (validated 2015–2025: Brier 0.2188 vs market 0.2075). Margins/totals from the tier-2 Monte Carlo. Market = de-vigged median across keyless book feeds (see src/ingest/odds_live.py). Paper only._

| fixture | kickoff | blend P(home) | market P(home) | margin | total | call |
|---|---|---|---|---|---|---|
| Wests Tigers v New Zealand Warriors | Fri 10 Jul 20:00 | 38.1% | 29.5% | -3.3 | 48 | New Zealand Warriors (62%, lean) |
| Dolphins v Cronulla-Sutherland Sharks | Sat 11 Jul 15:00 | 58.6% | 61.2% | +1.7 | 49 | Dolphins (59%, lean) |
| Canterbury-Bankstown Bulldogs v Canberra Raiders | Sat 11 Jul 17:30 | 58.4% | 61.3% | +1.1 | 45 | Canterbury-Bankstown Bulldogs (58%, lean) |
| Sydney Roosters v Parramatta Eels | Sat 11 Jul 19:35 | 74.8% | 78.9% | +4.9 | 48 | Sydney Roosters (75%, strong) |
| South Sydney Rabbitohs v Newcastle Knights | Sun 12 Jul 14:00 | 59.0% | 48.2% | +3.3 | 49 | South Sydney Rabbitohs (59%, lean) |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Sun 12 Jul 16:05 | 63.1% | 61.3% | +3.7 | 48 | Manly-Warringah Sea Eagles (63%, lean) |
| Melbourne Storm v Gold Coast Titans | Sun 12 Jul 18:15 | 75.7% | 70.3% | +4.5 | 48 | Melbourne Storm (76%, strong) |

**Value flags (model vs best available price, paper only):**
- Wests Tigers in Wests Tigers v New Zealand Warriors: model edge +8.7% vs consensus, EV +27.7% at best price (4 books)
- South Sydney Rabbitohs in South Sydney Rabbitohs v Newcastle Knights: model edge +10.8% vs consensus, EV +17.9% at best price (4 books)
- Parramatta Eels in Sydney Roosters v Parramatta Eels: model edge +4.2% vs consensus, EV +16.0% at best price (4 books)
- Cronulla-Sutherland Sharks in Dolphins v Cronulla-Sutherland Sharks: model edge +2.6% vs consensus, EV +3.5% at best price (4 books)
- Canberra Raiders in Canterbury-Bankstown Bulldogs v Canberra Raiders: model edge +2.9% vs consensus, EV +3.2% at best price (4 books)
- Melbourne Storm in Melbourne Storm v Gold Coast Titans: model edge +5.3% vs consensus, EV +2.9% at best price (4 books)
- _Caveat: on a fresh model most 'edges' are model error, not market error — the paper ledger exists to measure which. No real money._

**Model spread this round:** games where the tiers disagree by >10% are the ones to watch for team-list news — that disagreement is usually roster signal one model has and the other hasn't.
- Wests Tigers v New Zealand Warriors: Elo 41% vs GBM 29%
- Melbourne Storm v Gold Coast Titans: Elo 77% vs GBM 64%

**Top tryscorer per match (model fair price):**
- Wests Tigers v New Zealand Warriors: Alofiana Khan-Pereira (W, New Zealand Warriors) — 55% ATS, fair 1.82
- Dolphins v Cronulla-Sutherland Sharks: Jamayne Isaako (W, Dolphins) — 48% ATS, fair 2.07
- Canterbury-Bankstown Bulldogs v Canberra Raiders: Jacob Kiraz (W, Canterbury-Bankstown Bulldogs) — 51% ATS, fair 1.97
- Sydney Roosters v Parramatta Eels: Rex Bassingthwaighte (W, Sydney Roosters) — 46% ATS, fair 2.18
- South Sydney Rabbitohs v Newcastle Knights: Alex Johnston (W, South Sydney Rabbitohs) — 67% ATS, fair 1.49
- Manly-Warringah Sea Eagles v North Queensland Cowboys: Murray Taulagi (W, North Queensland Cowboys) — 50% ATS, fair 2.00
- Melbourne Storm v Gold Coast Titans: Will Warbrick (W, Melbourne Storm) — 53% ATS, fair 1.87

**Top-3 SGM candidates by correlation lift** (fair price vs independence price — the gap is the mispriced correlation):
- Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes: joint 12.6% → fair 7.92 (independent 11.78, lift ×1.49)
- Canberra Raiders win × ATS Xavier Savage × total over 40.5: joint 16.6% → fair 6.02 (independent 8.64, lift ×1.44)
- Dolphins win × ATS Jamayne Isaako × ATS Tevita Naufahu: joint 16.0% → fair 6.24 (independent 8.57, lift ×1.38)
- _Paste bookie SGM quotes into data/manual_odds/roundNN.csv and re-run scripts/run_phase4.py for EV vs quoted._