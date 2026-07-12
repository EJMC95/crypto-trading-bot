# Phase 4 report — player props + SGM simulator

_Generated 2026-07-12. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

## Gate 1 — walk-forward ATS backtest 2022–2025 (Brier / log loss)

| model | Brier | log loss |
|---|---|---|
| positional base rates | 0.1408 | 0.4436 |
| **ATS model** | **0.1401** | **0.4421** |

**GATE PASSED** on 28,508 player-games.

### Per-season

|   year |    n |   brier_model |   brier_base |
|-------:|-----:|--------------:|-------------:|
|   2022 | 6833 |        0.1374 |       0.1378 |
|   2023 | 7206 |        0.1381 |       0.1392 |
|   2024 | 7244 |        0.1437 |       0.1436 |
|   2025 | 7225 |        0.1412 |       0.1424 |

### Reliability (ATS probabilities)

| bin           |    n |   mean_pred |   mean_obs |
|:--------------|-----:|------------:|-----------:|
| (-0.001, 0.1] | 9466 |       0.066 |      0.075 |
| (0.1, 0.2]    | 7599 |       0.145 |      0.14  |
| (0.2, 0.3]    | 4851 |       0.249 |      0.24  |
| (0.3, 0.4]    | 3994 |       0.347 |      0.35  |
| (0.4, 0.5]    | 2132 |       0.442 |      0.439 |
| (0.5, 0.6]    |  456 |       0.53  |      0.52  |
| (0.6, 0.7]    |   10 |       0.615 |      0.5   |

## Gate 3 — joint-sim consistency (player-level sim vs tier-2 MC)

| match                                                 |   p_home_sim |   p_home_tier2 |   diff |
|:------------------------------------------------------|-------------:|---------------:|-------:|
| Manly-Warringah Sea Eagles v North Queensland Cowboys |       0.586  |         0.5854 | 0.0006 |
| Melbourne Storm v Gold Coast Titans                   |       0.6041 |         0.6033 | 0.0008 |

Max |diff| = 0.0008 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 19 — top ATS props (model fair prices)

| match                                                 | team                       | player            | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:------------------------------------------------------|:---------------------------|:------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Jason Saab        | W          |        0.78 |   0.542 |         1.84 |     0.184 |          5.4 | 7t/8g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Lehi Hopoate      | W          |        0.71 |   0.507 |         1.97 |     0.159 |          6.3 | 3t/4g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Tom Trbojevic     | FB         |        0.57 |   0.435 |         2.3  |     0.113 |          8.9 | 5t/9g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Braidon Burns     | W          |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 | 3t/6g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Murray Taulagi    | W          |        0.41 |   0.334 |         3    |     0.063 |         15.8 | 1t/8g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Tom Chester       | C          |        0.37 |   0.313 |         3.2  |     0.055 |         18.2 | 0t/1g    |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Sualauvi Fa'alogo | FB         |        0.81 |   0.555 |         1.8  |     0.195 |          5.1 | 3t/2g    |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Cameron Munster   | FE         |        0.7  |   0.505 |         1.98 |     0.157 |          6.4 | 12t/13g  |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Will Warbrick     | W          |        0.66 |   0.484 |         2.07 |     0.142 |          7   | 2t/3g    |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Jayden Campbell   | FE         |        0.49 |   0.388 |         2.57 |     0.088 |         11.4 | 3t/5g    |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Jaylan De Groot   | C          |        0.44 |   0.355 |         2.81 |     0.072 |         13.8 | —        |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Phillip Sami      | W          |        0.41 |   0.339 |         2.95 |     0.065 |         15.3 | 3t/10g   |

## Round 19 — SGM candidates (fair vs independence pricing)

| match                                                 | combo                                                                                                                           |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick × ATS Moses Leo × total over 40.5 × match tries over 9.5        |    0.0543 |        18.4  |          0.0115 |              4.726 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate × ATS Tom Trbojevic × total over 44.5 × match tries over 9.5 |    0.0588 |        17    |          0.0125 |              4.688 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries × ATS Lehi Hopoate × total over 52.5                                       |    0.0498 |        20.08 |          0.0193 |              2.587 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Sualauvi Fa'alogo 2+ tries × ATS Will Warbrick × total over 48.5                                          |    0.0545 |        18.35 |          0.0216 |              2.526 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab × ATS Lehi Hopoate × total over 44.5                                         |    0.0932 |        10.73 |          0.043  |              2.169 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 13+ × ATS Sualauvi Fa'alogo × ATS Will Warbrick × total over 40.5                                            |    0.0982 |        10.18 |          0.0454 |              2.162 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate × total over 44.5                                            |    0.1477 |         6.77 |          0.0861 |              1.714 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick × total over 40.5                                               |    0.1563 |         6.4  |          0.092  |              1.699 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 52.5                                                               |    0.1587 |         6.3  |          0.1122 |              1.415 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × total over 48.5                                                                   |    0.1763 |         5.67 |          0.1252 |              1.408 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Braidon Burns × total over 44.5                                           |    0.1035 |         9.66 |          0.0763 |              1.357 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × match tries over 7.5                                                              |    0.2311 |         4.33 |          0.1711 |              1.351 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Sualauvi Fa'alogo 2+ tries                                                                                |    0.1531 |         6.53 |          0.1139 |              1.344 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries                                                                            |    0.1383 |         7.23 |          0.1029 |              1.344 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 44.5                                                               |    0.2275 |         4.4  |          0.1695 |              1.342 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × total over 40.5                                                                   |    0.2516 |         3.98 |          0.1888 |              1.333 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × match tries over 7.5                                                          |    0.2431 |         4.11 |          0.1833 |              1.326 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate                                                              |    0.2041 |         4.9  |          0.1548 |              1.318 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick                                                                 |    0.2071 |         4.83 |          0.1571 |              1.318 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Jaylan De Groot × total over 40.5                                             |    0.0878 |        11.39 |          0.0672 |              1.307 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab                                                                              |    0.1948 |         5.13 |          0.152  |              1.281 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 13+ × ATS Sualauvi Fa'alogo                                                                                  |    0.2032 |         4.92 |          0.1591 |              1.277 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles -4.5 × ATS Jason Saab                                                                                |    0.3039 |         3.29 |          0.2538 |              1.197 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm -4.5 × ATS Sualauvi Fa'alogo                                                                                    |    0.3199 |         3.13 |          0.268  |              1.193 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | ATS Jason Saab × ATS Braidon Burns                                                                                              |    0.2455 |         4.07 |          0.2438 |              1.007 |
| Melbourne Storm v Gold Coast Titans                   | ATS Sualauvi Fa'alogo × ATS Jaylan De Groot                                                                                     |    0.1989 |         5.03 |          0.1981 |              1.004 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round19.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._