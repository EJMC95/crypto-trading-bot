# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-08-20. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2286 / 0.6512 | 0.2286 / 0.6512 |
| gbm | 0.2295 / 0.6526 | 0.2294 / 0.6524 |
| blend | 0.2179 / 0.6272 | 0.2179 / 0.6271 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2407 |            0.6743 |      0.2486 |        0.6903 |        0.2361 |          0.6652 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2271 |            0.6515 |      0.231  |        0.6598 |        0.2213 |          0.6377 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2336 |            0.6599 |      0.2402 |        0.6729 |        0.22   |          0.6298 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2408 |            0.6746 |      0.2388 |        0.6705 |        0.236  |          0.6657 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2334 |            0.6621 |      0.2378 |        0.6709 |        0.2257 |          0.6446 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.217  |            0.6287 |      0.2235 |        0.6412 |        0.1995 |          0.5883 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2061 |            0.6028 |      0.2163 |        0.624  |        0.1814 |          0.5439 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2207 |            0.633  |      0.2212 |        0.634  |        0.2047 |          0.5952 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2287 |            0.6525 |      0.2168 |        0.6269 |        0.218  |          0.6301 |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2295 |            0.654  |      0.222  |        0.6377 |        0.223  |          0.6405 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2352 |            0.6654 |      0.2284 |        0.6507 |        0.2277 |          0.6494 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   8 |       0.166 |      0     |
| (0.2, 0.3] |  76 |       0.262 |      0.158 |
| (0.3, 0.4] | 211 |       0.355 |      0.353 |
| (0.4, 0.5] | 417 |       0.453 |      0.405 |
| (0.5, 0.6] | 520 |       0.55  |      0.544 |
| (0.6, 0.7] | 517 |       0.649 |      0.675 |
| (0.7, 0.8] | 357 |       0.743 |      0.745 |
| (0.8, 0.9] | 104 |       0.836 |      0.837 |
| (0.9, 1.0] |   5 |       0.909 |      1     |

## Upcoming round — all models

| round    | date                | venue                  | home                        | away                          |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:-----------------------|:----------------------------|:------------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 25 | 2026-08-20 19:50:00 | AAMI Park              | Melbourne Storm             | Penrith Panthers              |       0.463  |           0.4413 |       0.5378 |         0.4071 |              -2.5 |               46.8 |
| Round 25 | 2026-08-21 18:00:00 | GIO Stadium            | Canberra Raiders            | Brisbane Broncos              |       0.6663 |           0.5214 |       0.7775 |         0.6557 |               0.9 |               46.7 |
| Round 25 | 2026-08-21 20:00:00 | Suncorp Stadium        | Dolphins                    | Parramatta Eels               |       0.7656 |           0.627  |       0.6697 |         0.7884 |               5.3 |               49.6 |
| Round 25 | 2026-08-22 15:00:00 | McDonald Jones Stadium | Newcastle Knights           | Manly-Warringah Sea Eagles    |       0.6222 |           0.4603 |       0.5296 |         0.5295 |              -1.6 |               48   |
| Round 25 | 2026-08-22 17:30:00 | Accor Stadium          | South Sydney Rabbitohs      | New Zealand Warriors          |       0.4638 |           0.4964 |       0.4747 |         0.4562 |              -0.1 |               46.8 |
| Round 25 | 2026-08-22 19:35:00 | Allianz Stadium        | St George Illawarra Dragons | Canterbury-Bankstown Bulldogs |       0.4238 |           0.4587 |       0.4728 |         0.3766 |              -1.6 |               45.3 |
| Round 25 | 2026-08-23 14:00:00 | Cbus Super Stadium     | Gold Coast Titans           | Cronulla-Sutherland Sharks    |       0.3254 |           0.4332 |       0.4344 |         0.2799 |              -2.7 |               47.7 |
| Round 25 | 2026-08-23 16:05:00 | Allianz Stadium        | Sydney Roosters             | Wests Tigers                  |       0.8415 |           0.6299 |       0.7639 |         0.8495 |               5.6 |               49.1 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._