# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-08-11. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2286 / 0.6512 | 0.2286 / 0.6512 |
| gbm | 0.2294 / 0.6523 | 0.2293 / 0.6522 |
| blend | 0.2179 / 0.6272 | 0.2179 / 0.6271 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2407 |            0.6743 |      0.2461 |        0.6852 |        0.2362 |          0.6653 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2273 |            0.652  |      0.2343 |        0.6666 |        0.2214 |          0.6378 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2335 |            0.6596 |      0.2404 |        0.6735 |        0.2199 |          0.6297 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2407 |            0.6744 |      0.2391 |        0.6708 |        0.2359 |          0.6656 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2335 |            0.6622 |      0.2346 |        0.6643 |        0.2257 |          0.6447 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2175 |            0.6297 |      0.223  |        0.6403 |        0.1997 |          0.5888 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2064 |            0.6034 |      0.2196 |        0.6307 |        0.1815 |          0.5441 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2203 |            0.6323 |      0.221  |        0.6334 |        0.2045 |          0.5949 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6521 |      0.2159 |        0.625  |        0.2179 |          0.63   |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2294 |            0.6537 |      0.2199 |        0.6329 |        0.223  |          0.6404 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2352 |            0.6655 |      0.2299 |        0.6534 |        0.2277 |          0.6494 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   7 |       0.162 |      0     |
| (0.2, 0.3] |  75 |       0.26  |      0.16  |
| (0.3, 0.4] | 216 |       0.355 |      0.35  |
| (0.4, 0.5] | 415 |       0.454 |      0.402 |
| (0.5, 0.6] | 514 |       0.55  |      0.547 |
| (0.6, 0.7] | 522 |       0.648 |      0.674 |
| (0.7, 0.8] | 357 |       0.743 |      0.745 |
| (0.8, 0.9] | 104 |       0.836 |      0.837 |
| (0.9, 1.0] |   5 |       0.909 |      1     |

## Upcoming round — all models

| round    | date                | venue                  | home                          | away                        |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:-----------------------|:------------------------------|:----------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 24 | 2026-08-13 19:50:00 | CommBank Stadium       | Penrith Panthers              | Sydney Roosters             |       0.6011 |           0.5999 |       0.6384 |         0.6488 |               4.2 |               46.6 |
| Round 24 | 2026-08-14 18:00:00 | 4 Pines Park           | Manly-Warringah Sea Eagles    | Dolphins                    |       0.4837 |           0.5265 |       0.6015 |         0.4843 |               1.2 |               48.3 |
| Round 24 | 2026-08-14 20:00:00 | Accor Stadium          | Canterbury-Bankstown Bulldogs | South Sydney Rabbitohs      |       0.6061 |           0.4821 |       0.6401 |         0.5479 |              -0.7 |               45.9 |
| Round 24 | 2026-08-15 15:00:00 | Ocean Protect Stadium  | Cronulla-Sutherland Sharks    | Canberra Raiders            |       0.7078 |           0.5895 |       0.7694 |         0.7168 |               3.7 |               47   |
| Round 24 | 2026-08-15 17:30:00 | CommBank Stadium       | Parramatta Eels               | North Queensland Cowboys    |       0.4767 |           0.5016 |       0.4931 |         0.4385 |               0.1 |               49.3 |
| Round 24 | 2026-08-15 19:35:00 | Suncorp Stadium        | Brisbane Broncos              | New Zealand Warriors        |       0.3988 |           0.4684 |       0.3852 |         0.3676 |              -1.2 |               46.2 |
| Round 24 | 2026-08-16 14:00:00 | McDonald Jones Stadium | Newcastle Knights             | Gold Coast Titans           |       0.7378 |           0.5578 |       0.7696 |         0.7261 |               2.4 |               48.7 |
| Round 24 | 2026-08-16 16:05:00 | CommBank Stadium       | Wests Tigers                  | St George Illawarra Dragons |       0.6232 |           0.5723 |       0.5522 |         0.624  |               3   |               48.5 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._