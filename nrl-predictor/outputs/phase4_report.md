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
| South Sydney Rabbitohs v Newcastle Knights            |       0.5746 |         0.5774 | -0.0028 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys |       0.5869 |         0.5829 |  0.004  |
| Melbourne Storm v Gold Coast Titans                   |       0.6082 |         0.6045 |  0.0037 |

Max |diff| = 0.0040 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 19 — top ATS props (model fair prices)

| match                                                 | team                       | player            | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:------------------------------------------------------|:---------------------------|:------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | David Fifita      | 2R         |        0.87 |   0.579 |         1.73 |     0.215 |          4.6 | 8t/9g    |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | Tallis Duncan     | C          |        0.53 |   0.41  |         2.44 |     0.098 |         10.2 | 2t/4g    |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs     | Jack Wighton      | C          |        0.51 |   0.402 |         2.49 |     0.094 |         10.6 | 8t/21g   |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Greg Marzhew      | W          |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 7t/6g    |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Fletcher Sharpe   | FE         |        0.58 |   0.439 |         2.28 |     0.115 |          8.7 | 4t/3g    |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights          | Dominic Young     | W          |        0.52 |   0.407 |         2.46 |     0.097 |         10.3 | 4t/6g    |
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

| match                                                 | combo                                                                                |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:------------------------------------------------------|:-------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Tallis Duncan × ATS Jack Wighton × total over 44.5  |    0.0946 |        10.57 |          0.0529 |              1.787 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate × total over 44.5 |    0.1485 |         6.73 |          0.0866 |              1.715 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick × total over 44.5    |    0.1612 |         6.2  |          0.0954 |              1.69  |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Tallis Duncan × total over 44.5                     |    0.182  |         5.5  |          0.1311 |              1.388 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × Tallis Duncan 2+ tries                                  |    0.0762 |        13.12 |          0.0553 |              1.378 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Tallis Duncan × match tries over 7.5                |    0.1924 |         5.2  |          0.141  |              1.365 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Tallis Duncan × ATS Jack Wighton                    |    0.1246 |         8.03 |          0.0917 |              1.358 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries                                 |    0.1386 |         7.21 |          0.1032 |              1.344 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 44.5                    |    0.2286 |         4.38 |          0.1705 |              1.341 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs by 13-+ × ATS Tallis Duncan                                   |    0.1492 |         6.7  |          0.1114 |              1.34  |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Sualauvi Fa'alogo 2+ tries                                     |    0.1674 |         5.97 |          0.1254 |              1.335 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × total over 44.5                        |    0.2492 |         4.01 |          0.1878 |              1.327 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × match tries over 7.5               |    0.2435 |         4.11 |          0.1837 |              1.325 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Lehi Hopoate                   |    0.2048 |         4.88 |          0.1552 |              1.32  |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × match tries over 7.5                   |    0.2666 |         3.75 |          0.2034 |              1.311 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Sualauvi Fa'alogo × ATS Will Warbrick                      |    0.223  |         4.49 |          0.1711 |              1.303 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 13-+ × ATS Jason Saab                                  |    0.1943 |         5.15 |          0.1519 |              1.279 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 13-+ × ATS Sualauvi Fa'alogo                                      |    0.2185 |         4.58 |          0.1729 |              1.264 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs -3.5 × ATS Tallis Duncan                                      |    0.2498 |         4    |          0.2059 |              1.213 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles -4.5 × ATS Jason Saab                                     |    0.304  |         3.29 |          0.2537 |              1.198 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm -4.5 × ATS Sualauvi Fa'alogo                                         |    0.3356 |         2.98 |          0.2834 |              1.184 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles by 1-12 × ATS Jason Saab                                  |    0.1599 |         6.25 |          0.1532 |              1.044 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs by 1-12 × ATS Tallis Duncan                                   |    0.1207 |         8.29 |          0.1158 |              1.042 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm by 1-12 × ATS Sualauvi Fa'alogo                                      |    0.1691 |         5.91 |          0.1637 |              1.033 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round19.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._