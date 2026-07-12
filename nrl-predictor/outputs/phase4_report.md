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

| match                                                 |   p_home_sim |   p_home_tier2 |    diff |
|:------------------------------------------------------|-------------:|---------------:|--------:|
| South Sydney Rabbitohs v Newcastle Knights            |       0.5757 |         0.5774 | -0.0016 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys |       0.5869 |         0.5829 |  0.004  |
| Melbourne Storm v Gold Coast Titans                   |       0.6082 |         0.6045 |  0.0037 |

Max |diff| = 0.0040 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 19 — top ATS props (model fair prices)

| match                                                 | team                       | player            | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:------------------------------------------------------|:---------------------------|:------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | Alex Johnston     | W          |        1.12 |   0.673 |         1.49 |     0.308 |          3.2 | 17t/11g  |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | David Fifita      | 2R         |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 8t/9g    |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | Edward Kosi       | W          |        0.51 |   0.399 |         2.51 |     0.093 |         10.8 | 2t/2g    |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Greg Marzhew      | W          |        0.83 |   0.564 |         1.77 |     0.202 |          5   | 7t/6g    |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Fletcher Sharpe   | FB         |        0.66 |   0.485 |         2.06 |     0.143 |          7   | 4t/3g    |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Dominic Young     | W          |        0.6  |   0.451 |         2.22 |     0.122 |          8.2 | 4t/6g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Jason Saab        | W          |        0.78 |   0.542 |         1.85 |     0.184 |          5.4 | 7t/8g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Lehi Hopoate      | W          |        0.71 |   0.507 |         1.97 |     0.159 |          6.3 | 3t/4g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles | Tom Trbojevic     | FB         |        0.57 |   0.435 |         2.3  |     0.113 |          8.9 | 5t/9g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Braidon Burns     | W          |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 | 3t/6g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Murray Taulagi    | W          |        0.41 |   0.334 |         3    |     0.063 |         15.8 | 1t/8g    |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys   | Tom Chester       | C          |        0.38 |   0.313 |         3.2  |     0.055 |         18.2 | 0t/1g    |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Sualauvi Fa'alogo | FB         |        0.86 |   0.578 |         1.73 |     0.214 |          4.7 | 3t/2g    |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Cameron Munster   | FE         |        0.75 |   0.527 |         1.9  |     0.173 |          5.8 | 12t/13g  |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm            | Will Warbrick     | W          |        0.7  |   0.505 |         1.98 |     0.157 |          6.4 | 2t/3g    |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Jayden Campbell   | FE         |        0.52 |   0.408 |         2.45 |     0.097 |         10.3 | 3t/5g    |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Jaylan De Groot   | C          |        0.47 |   0.373 |         2.68 |     0.08  |         12.4 | —        |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans          | Phillip Sami      | W          |        0.44 |   0.356 |         2.81 |     0.073 |         13.8 | 3t/10g   |

## Round 19 — SGM candidates (fair vs independence pricing)

| match                                                 | combo                                                                                                                           |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:------------------------------------------------------|:--------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate × ATS Tom Trbojevic × total over 44.5 × match tries over 9.5 |    0.059  |        16.95 |          0.0126 |              4.676 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × ATS Tallis Duncan × total over 44.5 × match tries over 9.5   |    0.0374 |        26.75 |          0.0082 |              4.586 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick × ATS Moses Leo × total over 44.5 × match tries over 9.5        |    0.0705 |        14.19 |          0.0154 |              4.568 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries × ATS Lehi Hopoate × total over 52.5                                       |    0.0503 |        19.86 |          0.0193 |              2.602 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Sualauvi Fa'alogo 2+ tries × ATS Will Warbrick × total over 52.5                                          |    0.0597 |        16.74 |          0.0233 |              2.564 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Edward Kosi × total over 52.5                                         |    0.0648 |        15.43 |          0.0259 |              2.499 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab × ATS Lehi Hopoate × total over 44.5                                         |    0.0926 |        10.8  |          0.0431 |              2.151 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 13+ × ATS Sualauvi Fa'alogo × ATS Will Warbrick × total over 44.5                                            |    0.1044 |         9.57 |          0.049  |              2.133 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Edward Kosi × total over 44.5                                           |    0.0894 |        11.18 |          0.0424 |              2.11  |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate × total over 44.5                                            |    0.1485 |         6.73 |          0.0866 |              1.715 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick × total over 44.5                                               |    0.1612 |         6.2  |          0.0954 |              1.69  |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × total over 44.5                                              |    0.1417 |         7.06 |          0.0847 |              1.673 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 52.5                                                               |    0.1593 |         6.28 |          0.1127 |              1.413 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × total over 52.5                                                                   |    0.1727 |         5.79 |          0.1232 |              1.402 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries                                                                            |    0.1386 |         7.21 |          0.1032 |              1.344 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 44.5                                                               |    0.2286 |         4.38 |          0.1705 |              1.341 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Sualauvi Fa'alogo 2+ tries                                                                                |    0.1674 |         5.97 |          0.1254 |              1.335 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × total over 44.5                                                                   |    0.2492 |         4.01 |          0.1878 |              1.327 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × match tries over 7.5                                                          |    0.2435 |         4.11 |          0.1837 |              1.325 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate                                                              |    0.2048 |         4.88 |          0.1552 |              1.32  |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi                                                                |    0.1939 |         5.16 |          0.1474 |              1.316 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × total over 52.5                                                                |    0.188  |         5.32 |          0.1431 |              1.314 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                             |    0.2246 |         4.45 |          0.171  |              1.314 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × match tries over 7.5                                                              |    0.2666 |         3.75 |          0.2034 |              1.311 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick                                                                 |    0.223  |         4.49 |          0.1711 |              1.303 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab                                                                              |    0.1943 |         5.15 |          0.1519 |              1.279 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × total over 44.5                                                                |    0.2711 |         3.69 |          0.2143 |              1.265 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 13+ × ATS Sualauvi Fa'alogo                                                                                  |    0.2185 |         4.58 |          0.1729 |              1.264 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                           |    0.2893 |         3.46 |          0.2312 |              1.251 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                               |    0.2284 |         4.38 |          0.1865 |              1.224 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles -4.5 × ATS Jason Saab                                                                                |    0.304  |         3.29 |          0.2537 |              1.198 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm -4.5 × ATS Sualauvi Fa'alogo                                                                                    |    0.3356 |         2.98 |          0.2834 |              1.184 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs -4.5 × ATS Alex Johnston                                                                                 |    0.3598 |         2.78 |          0.3095 |              1.162 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round19.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._