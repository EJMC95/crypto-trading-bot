# Phase 4 report — player props + SGM simulator

_Generated 2026-07-16. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                              |   p_home_sim |   p_home_tier2 |    diff |
|:---------------------------------------------------|-------------:|---------------:|--------:|
| Penrith Panthers v Brisbane Broncos                |       0.6477 |         0.6517 | -0.0041 |
| Cronulla-Sutherland Sharks v Newcastle Knights     |       0.594  |         0.5909 |  0.0031 |
| Sydney Roosters v Melbourne Storm                  |       0.5495 |         0.5511 | -0.0016 |
| Canberra Raiders v South Sydney Rabbitohs          |       0.4869 |         0.4898 | -0.0029 |
| New Zealand Warriors v St George Illawarra Dragons |       0.6628 |         0.6672 | -0.0044 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       |       0.5582 |         0.5638 | -0.0056 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     |       0.4357 |         0.4337 |  0.0019 |
| Dolphins v North Queensland Cowboys                |       0.5888 |         0.5897 | -0.0009 |

Max |diff| = 0.0056 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 20 — top ATS props (model fair prices)

| match                                              | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:---------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Thomas Jenkins          | W          |        1.14 |   0.679 |         1.47 |     0.314 |          3.2 | 4t/2g    |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Brian To'o              | W          |        0.56 |   0.427 |         2.34 |     0.108 |          9.3 | 6t/11g   |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Casey McLean            | C          |        0.47 |   0.377 |         2.65 |     0.082 |         12.1 | 1t/2g    |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Grant Anderson          | B          |        0.44 |   0.358 |         2.79 |     0.074 |         13.6 | 2t/3g    |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Deine Mariner           | W          |        0.43 |   0.352 |         2.84 |     0.071 |         14.1 | 2t/5g    |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Reece Walsh             | FB         |        0.37 |   0.313 |         3.2  |     0.055 |         18.2 | 3t/9g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.81 |   0.556 |         1.8  |     0.195 |          5.1 | 8t/9g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.47 |   0.376 |         2.66 |     0.082 |         12.2 | 0t/1g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | Jesse Ramien            | C          |        0.47 |   0.373 |         2.68 |     0.08  |         12.4 | 6t/11g   |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Dominic Young           | W          |        0.64 |   0.473 |         2.11 |     0.136 |          7.4 | 6t/7g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Greg Marzhew            | W          |        0.64 |   0.471 |         2.12 |     0.134 |          7.5 | 5t/6g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Kalyn Ponga             | FB         |        0.39 |   0.325 |         3.08 |     0.06  |         16.7 | 7t/12g   |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Mark Nawaqanitawase     | W          |        1.25 |   0.714 |         1.4  |     0.356 |          2.8 | 4t/2g    |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Daniel Tupou            | W          |        0.63 |   0.467 |         2.14 |     0.132 |          7.6 | 14t/26g  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Cody Ramsey             | FB         |        0.46 |   0.367 |         2.73 |     0.077 |         12.9 | 1t/3g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Moses Leo               | W          |        0.73 |   0.517 |         1.93 |     0.166 |          6   | 1t/1g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 | 1t/2g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Jack Howarth            | C          |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 3t/4g    |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Ethan Strange           | FE         |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 3t/3g    |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Xavier Savage           | W          |        0.49 |   0.39  |         2.57 |     0.088 |         11.3 | 2t/3g    |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Kaeo Weekes             | FB         |        0.42 |   0.345 |         2.9  |     0.068 |         14.7 | 2t/4g    |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.9  |   0.592 |         1.69 |     0.226 |          4.4 | 11t/14g  |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Cody Walker             | FE         |        0.48 |   0.382 |         2.62 |     0.084 |         11.8 | 7t/13g   |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Campbell Graham         | W          |        0.41 |   0.335 |         2.99 |     0.064 |         15.7 | 2t/7g    |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        1.03 |   0.644 |         1.55 |     0.277 |          3.6 | 4t/5g    |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.84 |   0.568 |         1.76 |     0.205 |          4.9 | 9t/15g   |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Adam Pompey             | C          |        0.46 |   0.369 |         2.71 |     0.078 |         12.8 | 3t/8g    |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Setu Tu                 | W          |        0.6  |   0.45  |         2.22 |     0.121 |          8.2 | 1t/1g    |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Mathew Feagai           | C          |        0.5  |   0.392 |         2.55 |     0.09  |         11.2 | 2t/3g    |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Clinton Gutherson       | FB         |        0.41 |   0.335 |         2.98 |     0.064 |         15.7 | 6t/12g   |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.85 |   0.571 |         1.75 |     0.208 |          4.8 | 4t/6g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Enari Tuala             | C          |        0.69 |   0.497 |         2.01 |     0.151 |          6.6 | 6t/11g   |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Jacob Preston           | 2R         |        0.49 |   0.387 |         2.58 |     0.087 |         11.5 | 1t/2g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Jeral Skelton           | W          |        0.97 |   0.622 |         1.61 |     0.255 |          3.9 | 4t/2g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Jahream Bula            | FB         |        0.55 |   0.422 |         2.37 |     0.105 |          9.5 | 2t/3g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Starford To'a           | C          |        0.39 |   0.32  |         3.13 |     0.058 |         17.3 | 2t/5g    |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | AJ Brimson              | C          |        0.66 |   0.482 |         2.07 |     0.142 |          7.1 | 8t/11g   |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | Phillip Sami            | W          |        0.59 |   0.448 |         2.23 |     0.12  |          8.4 | 5t/10g   |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | Dean Ieremia            | W          |        0.4  |   0.331 |         3.02 |     0.062 |         16.1 | 0t/3g    |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Tom Trbojevic           | FB         |        0.78 |   0.543 |         1.84 |     0.185 |          5.4 | 13t/10g  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Reuben Garrick          | C          |        0.66 |   0.482 |         2.08 |     0.141 |          7.1 | 12t/11g  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.52 |   0.408 |         2.45 |     0.098 |         10.2 | 1t/1g    |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Hamiso Tabuai-Fidow     | FB         |        0.81 |   0.553 |         1.81 |     0.193 |          5.2 | 5t/5g    |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Jamayne Isaako          | W          |        0.77 |   0.535 |         1.87 |     0.179 |          5.6 | 13t/16g  |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Jack Bostock            | C          |        0.72 |   0.514 |         1.95 |     0.163 |          6.1 | 5t/5g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Murray Taulagi          | W          |        0.79 |   0.547 |         1.83 |     0.189 |          5.3 | 6t/5g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Zac Laybutt             | C          |        0.48 |   0.381 |         2.62 |     0.084 |         11.9 | 4t/5g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Tom Chester             | C          |        0.47 |   0.376 |         2.66 |     0.082 |         12.3 | 2t/2g    |

## Round 20 — SGM candidates (fair vs independence pricing)

| match                                              | combo                                                                                                                                         |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:---------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × ATS Jack Wighton × total over 42.5 × match tries over 9.5              |    0.0263 |        37.99 |          0.0052 |              5.071 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala × ATS Matt Burton × total over 42.5 × match tries over 9.5              |    0.0455 |        21.98 |          0.0094 |              4.85  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × ATS Reuben Garrick × ATS Lehi Hopoate × total over 42.5 × match tries over 9.5           |    0.0495 |        20.21 |          0.0105 |              4.699 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Casey McLean × total over 40.5 × match tries over 9.5                        |    0.0464 |        21.57 |          0.01   |              4.617 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × ATS Jesse Ramien × total over 42.5 × match tries over 9.5                |    0.038  |        26.34 |          0.0082 |              4.603 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × ATS Jack Bostock × total over 44.5 × match tries over 10.5                      |    0.0592 |        16.9  |          0.0131 |              4.508 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS Daniel Tupou × ATS Cody Ramsey × total over 42.5 × match tries over 9.5                   |    0.0552 |        18.11 |          0.0125 |              4.421 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Adam Pompey × total over 42.5 × match tries over 9.5 |    0.0639 |        15.65 |          0.0147 |              4.352 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Campbell Graham × total over 50.5                                                   |    0.0411 |        24.35 |          0.0144 |              2.853 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × Jacob Kiraz 2+ tries × ATS Enari Tuala × total over 50.5                                                  |    0.056  |        17.86 |          0.021  |              2.668 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS KL Iro × total over 50.5                                                     |    0.0433 |        23.12 |          0.0164 |              2.637 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × Tom Trbojevic 2+ tries × ATS Reuben Garrick × total over 50.5                                                |    0.0488 |        20.5  |          0.0191 |              2.551 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × Mark Nawaqanitawase 2+ tries × ATS Daniel Tupou × total over 50.5                                                       |    0.0857 |        11.67 |          0.035  |              2.449 |
| Dolphins v North Queensland Cowboys                | Dolphins win × Hamiso Tabuai-Fidow 2+ tries × ATS Jamayne Isaako × total over 52.5                                                            |    0.0575 |        17.39 |          0.0235 |              2.443 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Campbell Graham × total over 42.5                                                     |    0.0598 |        16.72 |          0.025  |              2.391 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                     |    0.0897 |        11.15 |          0.038  |              2.358 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 48.5                                                             |    0.0727 |        13.76 |          0.031  |              2.343 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles by 13+ × ATS Tom Trbojevic × ATS Reuben Garrick × total over 42.5                                                  |    0.0876 |        11.42 |          0.0393 |              2.228 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                       |    0.0771 |        12.97 |          0.0349 |              2.211 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs by 13+ × ATS Jacob Kiraz × ATS Enari Tuala × total over 42.5                                                    |    0.0911 |        10.97 |          0.0413 |              2.207 |
| Dolphins v North Queensland Cowboys                | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × total over 44.5                                                              |    0.105  |         9.53 |          0.0505 |              2.08  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters by 13+ × ATS Mark Nawaqanitawase × ATS Daniel Tupou × total over 42.5                                                         |    0.0999 |        10.01 |          0.0486 |              2.053 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 40.5                                                               |    0.1101 |         9.09 |          0.0538 |              2.047 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                       |    0.1432 |         6.99 |          0.0726 |              1.972 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × total over 42.5                                                        |    0.1022 |         9.79 |          0.0562 |              1.818 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × ATS Reuben Garrick × total over 42.5                                                     |    0.1424 |         7.02 |          0.0821 |              1.734 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala × total over 42.5                                                       |    0.1495 |         6.69 |          0.0867 |              1.724 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                          |    0.1203 |         8.31 |          0.0701 |              1.716 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS Daniel Tupou × total over 42.5                                                            |    0.1707 |         5.86 |          0.1031 |              1.656 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × total over 44.5                                                                 |    0.1637 |         6.11 |          0.099  |              1.653 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 40.5                                                                  |    0.1655 |         6.04 |          0.1027 |              1.612 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                          |    0.2095 |         4.77 |          0.1323 |              1.584 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                           |    0.1585 |         6.31 |          0.1113 |              1.424 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham                                                                          |    0.137  |         7.3  |          0.0972 |              1.41  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × total over 50.5                                                                          |    0.1621 |         6.17 |          0.1151 |              1.409 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × total over 50.5                                                                         |    0.1623 |         6.16 |          0.1156 |              1.404 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 50.5                                                                       |    0.1765 |         5.67 |          0.1259 |              1.402 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 52.5                                                                                      |    0.1768 |         5.66 |          0.1276 |              1.385 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × Jacob Kiraz 2+ tries                                                                                      |    0.1528 |         6.54 |          0.1107 |              1.38  |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × total over 50.5                                                                              |    0.1534 |         6.52 |          0.1115 |              1.376 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × Tom Trbojevic 2+ tries                                                                                       |    0.1392 |         7.18 |          0.1015 |              1.372 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × match tries over 8.5                                                                                 |    0.2145 |         4.66 |          0.1583 |              1.355 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                                    |    0.1492 |         6.7  |          0.1103 |              1.353 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                        |    0.2086 |         4.79 |          0.1551 |              1.345 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Jeral Skelton × total over 42.5                                                     |    0.1453 |         6.88 |          0.1081 |              1.343 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × ATS Reuben Garrick                                                                       |    0.1901 |         5.26 |          0.1416 |              1.342 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × match tries over 7.5                                                                     |    0.2288 |         4.37 |          0.1706 |              1.341 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala                                                                         |    0.2037 |         4.91 |          0.1519 |              1.34  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × total over 42.5                                                                          |    0.2286 |         4.37 |          0.1705 |              1.34  |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Dominic Young × total over 42.5                                                   |    0.1196 |         8.36 |          0.0893 |              1.34  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × Mark Nawaqanitawase 2+ tries                                                                                            |    0.2493 |         4.01 |          0.1867 |              1.335 |
| Dolphins v North Queensland Cowboys                | Dolphins win × Hamiso Tabuai-Fidow 2+ tries                                                                                                   |    0.1441 |         6.94 |          0.1081 |              1.333 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × total over 42.5                                                                         |    0.2311 |         4.33 |          0.1737 |              1.331 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × match tries over 7.5                                                                    |    0.2298 |         4.35 |          0.1729 |              1.329 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS Daniel Tupou                                                                              |    0.2305 |         4.34 |          0.1734 |              1.329 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro                                                                            |    0.1581 |         6.32 |          0.1191 |              1.328 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × total over 48.5                                                                                   |    0.2107 |         4.75 |          0.1587 |              1.328 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                         |    0.2211 |         4.52 |          0.1668 |              1.325 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                                  |    0.247  |         4.05 |          0.1866 |              1.323 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × total over 42.5                                                                              |    0.2215 |         4.52 |          0.1675 |              1.323 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 42.5                                                                       |    0.2466 |         4.06 |          0.187  |              1.319 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 44.5                                                                                      |    0.2453 |         4.08 |          0.1864 |              1.316 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Setu Tu × total over 42.5                                                          |    0.1387 |         7.21 |          0.1055 |              1.316 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Tom Trbojevic × ATS AJ Brimson × total over 42.5                                                         |    0.1084 |         9.23 |          0.0825 |              1.313 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako                                                                                   |    0.2162 |         4.62 |          0.1654 |              1.307 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles by 13+ × ATS Tom Trbojevic                                                                                         |    0.1829 |         5.47 |          0.1408 |              1.3   |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                             |    0.1673 |         5.98 |          0.1289 |              1.298 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × total over 50.5                                                                               |    0.1963 |         5.09 |          0.1514 |              1.296 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Murray Taulagi × total over 44.5                                                                 |    0.1331 |         7.51 |          0.1027 |              1.296 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Deine Mariner × total over 40.5                                                               |    0.1087 |         9.2  |          0.0841 |              1.291 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs by 13+ × ATS Jacob Kiraz                                                                                        |    0.1872 |         5.34 |          0.145  |              1.291 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                              |    0.2801 |         3.57 |          0.2183 |              1.283 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                        |    0.2979 |         3.36 |          0.2324 |              1.282 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                   |    0.2969 |         3.37 |          0.2318 |              1.281 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                |    0.2467 |         4.05 |          0.1931 |              1.277 |
| Dolphins v North Queensland Cowboys                | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow                                                                                                     |    0.2023 |         4.94 |          0.1587 |              1.275 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × total over 40.5                                                                                   |    0.3061 |         3.27 |          0.2411 |              1.269 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                                      |    0.2003 |         4.99 |          0.1579 |              1.269 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                     |    0.2235 |         4.48 |          0.1763 |              1.268 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Xavier Savage × total over 42.5                                                          |    0.0818 |        12.22 |          0.0648 |              1.263 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                    |    0.2256 |         4.43 |          0.1791 |              1.26  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × match tries over 7.5                                                                          |    0.2773 |         3.61 |          0.2218 |              1.25  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × total over 42.5                                                                               |    0.2777 |         3.6  |          0.2226 |              1.247 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                            |    0.289  |         3.46 |          0.2329 |              1.241 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS Moses Leo × total over 42.5                                                               |    0.1419 |         7.05 |          0.1152 |              1.232 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters by 13+ × ATS Mark Nawaqanitawase                                                                                              |    0.216  |         4.63 |          0.1766 |              1.223 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                  |    0.2682 |         3.73 |          0.2202 |              1.218 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                       |    0.2734 |         3.66 |          0.2246 |              1.217 |
| Dolphins v North Queensland Cowboys                | Dolphins -4.5 × ATS Hamiso Tabuai-Fidow                                                                                                       |    0.3106 |         3.22 |          0.2602 |              1.193 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles -2.5 × ATS Tom Trbojevic                                                                                           |    0.3192 |         3.13 |          0.2686 |              1.189 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs -0.5 × ATS Alex Johnston                                                                                               |    0.3434 |         2.91 |          0.2896 |              1.186 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs -2.5 × ATS Jacob Kiraz                                                                                          |    0.328  |         3.05 |          0.2768 |              1.185 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks -4.5 × ATS Ronaldo Mulitalo                                                                                        |    0.3144 |         3.18 |          0.2655 |              1.184 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                    |    0.372  |         2.69 |          0.3175 |              1.172 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors -6.5 × ATS Alofiana Khan-Pereira                                                                                         |    0.3694 |         2.71 |          0.3161 |              1.169 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters -2.5 × ATS Mark Nawaqanitawase                                                                                                |    0.3912 |         2.56 |          0.3403 |              1.15  |
| Cronulla-Sutherland Sharks v Newcastle Knights     | ATS Ronaldo Mulitalo × ATS Dominic Young                                                                                                      |    0.2691 |         3.72 |          0.2658 |              1.012 |
| Sydney Roosters v Melbourne Storm                  | ATS Mark Nawaqanitawase × ATS Moses Leo                                                                                                       |    0.3706 |         2.7  |          0.3686 |              1.006 |
| Penrith Panthers v Brisbane Broncos                | ATS Thomas Jenkins × ATS Deine Mariner                                                                                                        |    0.236  |         4.24 |          0.2355 |              1.002 |
| New Zealand Warriors v St George Illawarra Dragons | ATS Alofiana Khan-Pereira × ATS Setu Tu                                                                                                       |    0.291  |         3.44 |          0.2906 |              1.002 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | ATS Jacob Kiraz × ATS Jeral Skelton                                                                                                           |    0.356  |         2.81 |          0.3555 |              1.002 |
| Canberra Raiders v South Sydney Rabbitohs          | ATS Alex Johnston × ATS Xavier Savage                                                                                                         |    0.2294 |         4.36 |          0.2296 |              0.999 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | ATS Tom Trbojevic × ATS AJ Brimson                                                                                                            |    0.2629 |         3.8  |          0.2637 |              0.997 |
| Dolphins v North Queensland Cowboys                | ATS Hamiso Tabuai-Fidow × ATS Murray Taulagi                                                                                                  |    0.3012 |         3.32 |          0.3035 |              0.992 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round20.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._