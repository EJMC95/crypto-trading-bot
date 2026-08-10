# Phase 4 report — player props + SGM simulator

_Generated 2026-08-10. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                                  |   p_home_sim |   p_home_tier2 |    diff |
|:-------------------------------------------------------|-------------:|---------------:|--------:|
| Penrith Panthers v Sydney Roosters                     |       0.5957 |         0.6035 | -0.0078 |
| Manly-Warringah Sea Eagles v Dolphins                  |       0.5268 |         0.5231 |  0.0037 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs |       0.4831 |         0.4822 |  0.0009 |
| Cronulla-Sutherland Sharks v Canberra Raiders          |       0.5917 |         0.5886 |  0.003  |
| Parramatta Eels v North Queensland Cowboys             |       0.502  |         0.4989 |  0.0031 |
| Brisbane Broncos v New Zealand Warriors                |       0.469  |         0.4663 |  0.0026 |
| Newcastle Knights v Gold Coast Titans                  |       0.5557 |         0.5591 | -0.0034 |
| Wests Tigers v St George Illawarra Dragons             |       0.5685 |         0.5712 | -0.0028 |

Max |diff| = 0.0078 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 24 — top ATS props (model fair prices)

| match                                                  | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:-------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Thomas Jenkins          | W          |        0.94 |   0.609 |         1.64 |     0.242 |          4.1 | 4t/2g    |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Brian To'o              | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 8t/13g   |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Casey McLean            | C          |        0.44 |   0.356 |         2.81 |     0.072 |         13.8 | 2t/3g    |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Tommy Talau             | W          |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | 6t/8g    |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.52 |   0.407 |         2.46 |     0.097 |         10.3 | —        |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Junior Tupou            | B          |        0.5  |   0.391 |         2.56 |     0.089 |         11.2 | 2t/3g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.72 |   0.514 |         1.95 |     0.163 |          6.1 | 4t/2g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Toluta'u Koula          | C          |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | 5t/4g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Reuben Garrick          | C          |        0.53 |   0.412 |         2.43 |     0.1   |         10   | 4t/3g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Jamayne Isaako          | W          |        0.54 |   0.419 |         2.39 |     0.103 |          9.7 | 5t/9g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Jack Bostock            | C          |        0.51 |   0.4   |         2.5  |     0.094 |         10.7 | 1t/1g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Tevita Naufahu          | W          |        0.48 |   0.38  |         2.63 |     0.084 |         12   | 0t/1g    |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Stephen Crichton        | C          |        0.64 |   0.475 |         2.11 |     0.137 |          7.3 | 11t/14g  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Bronson Xerri           | C          |        0.55 |   0.421 |         2.38 |     0.104 |          9.6 | 3t/3g    |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Matt Burton             | FE         |        0.47 |   0.377 |         2.66 |     0.082 |         12.2 | 7t/12g   |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.92 |   0.6   |         1.67 |     0.234 |          4.3 | 18t/20g  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.66 |   0.484 |         2.07 |     0.142 |          7   | 3t/3g    |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Tallis Duncan           | C          |        0.44 |   0.353 |         2.83 |     0.071 |         14   | 3t/5g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 10t/13g  |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.61 |   0.457 |         2.19 |     0.126 |          8   | 3t/4g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.56 |   0.431 |         2.32 |     0.11  |          9.1 | 8t/13g   |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Xavier Savage           | W          |        0.64 |   0.472 |         2.12 |     0.135 |          7.4 | 3t/6g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Kaeo Weekes             | FB         |        0.48 |   0.381 |         2.62 |     0.084 |         11.9 | 1t/4g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Daine Laurie            | FE         |        0.48 |   0.38  |         2.63 |     0.084 |         11.9 | 2t/4g    |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Josh Addo-Carr          | W          |        0.95 |   0.612 |         1.63 |     0.245 |          4.1 | 15t/13g  |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Jordan Samrani          | C          |        0.46 |   0.369 |         2.71 |     0.078 |         12.8 | 1t/1g    |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Brian Kelly             | W          |        0.44 |   0.357 |         2.8  |     0.073 |         13.7 | 8t/16g   |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Jaxon Purdue            | C          |        0.69 |   0.501 |         2    |     0.154 |          6.5 | 3t/2g    |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Tom Chester             | C          |        0.57 |   0.433 |         2.31 |     0.111 |          9   | 2t/2g    |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Murray Taulagi          | W          |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | 1t/4g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Grant Anderson          | C          |        0.5  |   0.391 |         2.56 |     0.089 |         11.3 | 2t/3g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Josiah Karapani         | W          |        0.48 |   0.38  |         2.63 |     0.084 |         11.9 | 1t/3g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Jesse Arthars           | W          |        0.42 |   0.342 |         2.92 |     0.067 |         15   | 2t/7g    |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.93 |   0.606 |         1.65 |     0.239 |          4.2 | 7t/6g    |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.72 |   0.511 |         1.96 |     0.161 |          6.2 | 9t/12g   |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Ali Leiataua            | C          |        0.37 |   0.308 |         3.25 |     0.053 |         18.9 | 1t/2g    |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Dominic Young           | W          |        1.17 |   0.691 |         1.45 |     0.328 |          3   | 11t/6g   |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.81 |   0.556 |         1.8  |     0.195 |          5.1 | 6t/4g    |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Greg Marzhew            | W          |        0.49 |   0.386 |         2.59 |     0.087 |         11.5 | 2t/6g    |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | Phillip Sami            | W          |        0.69 |   0.498 |         2.01 |     0.152 |          6.6 | 8t/10g   |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | AJ Brimson              | C          |        0.6  |   0.451 |         2.22 |     0.122 |          8.2 | 8t/10g   |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | Jaylan De Groot         | C          |        0.43 |   0.353 |         2.84 |     0.071 |         14.1 | 1t/2g    |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Taylan May              | C          |        0.73 |   0.517 |         1.94 |     0.165 |          6.1 | —        |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Sunia Turuva            | W          |        0.66 |   0.482 |         2.08 |     0.141 |          7.1 | 2t/4g    |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Jahream Bula            | FB         |        0.49 |   0.388 |         2.58 |     0.087 |         11.4 | 1t/5g    |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.66 |   0.481 |         2.08 |     0.141 |          7.1 | 13t/14g  |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Setu Tu                 | W          |        0.47 |   0.377 |         2.65 |     0.082 |         12.1 | —        |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Clinton Gutherson       | FB         |        0.41 |   0.338 |         2.96 |     0.065 |         15.4 | 10t/18g  |

## Round 24 — SGM candidates (fair vs independence pricing)

| match                                                  | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:-------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Ali Leiataua × total over 42.5 × match tries over 9.5 |    0.0408 |        24.53 |          0.0076 |              5.348 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × ATS Reuben Garrick × total over 44.5 × match tries over 9.5           |    0.0435 |        22.99 |          0.0088 |              4.968 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × ATS Sione Katoa × total over 42.5 × match tries over 9.5                  |    0.0487 |        20.55 |          0.0099 |              4.915 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × ATS Tallis Duncan × total over 41.5 × match tries over 9.5                  |    0.0413 |        24.19 |          0.0084 |              4.896 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × ATS Sunia Turuva × ATS Jahream Bula × total over 42.5 × match tries over 9.5                               |    0.0435 |        23.01 |          0.0091 |              4.8   |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × ATS Tom Chester × ATS Murray Taulagi × total over 44.5 × match tries over 9.5                |    0.0427 |        23.43 |          0.009  |              4.766 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Casey McLean × total over 42.5 × match tries over 9.5                         |    0.0394 |        25.35 |          0.0084 |              4.688 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Fletcher Sharpe × ATS Greg Marzhew × total over 44.5 × match tries over 9.5                    |    0.0683 |        14.63 |          0.0157 |              4.361 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × Jaxon Purdue 2+ tries × ATS Tom Chester × total over 52.5                                                       |    0.036  |        27.78 |          0.0124 |              2.902 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries × ATS Toluta'u Koula × total over 52.5                                                  |    0.0389 |        25.73 |          0.0134 |              2.895 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                      |    0.0609 |        16.41 |          0.0224 |              2.722 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Edward Kosi × total over 49.5                                                        |    0.06   |        16.66 |          0.0225 |              2.672 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × Taylan May 2+ tries × ATS Sunia Turuva × total over 50.5                                                                    |    0.0432 |        23.13 |          0.0163 |              2.653 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS KL Iro × total over 50.5                                                      |    0.042  |        23.79 |          0.016  |              2.635 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 50.5                                                              |    0.0518 |        19.29 |          0.0207 |              2.502 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × Dominic Young 2+ tries × ATS Fletcher Sharpe × total over 52.5                                                         |    0.0884 |        11.31 |          0.0368 |              2.401 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Jaxon Purdue × ATS Tom Chester × total over 44.5                                                         |    0.064  |        15.62 |          0.0269 |              2.379 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 44.5                                                    |    0.0677 |        14.76 |          0.0295 |              2.3   |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers by 13+ × ATS Taylan May × ATS Sunia Turuva × total over 42.5                                                                      |    0.0838 |        11.93 |          0.037  |              2.268 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                        |    0.0851 |        11.75 |          0.0376 |              2.265 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                        |    0.0881 |        11.35 |          0.0396 |              2.224 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Edward Kosi × total over 41.5                                                          |    0.0829 |        12.07 |          0.0375 |              2.21  |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                |    0.085  |        11.76 |          0.0389 |              2.186 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights by 13+ × ATS Dominic Young × ATS Fletcher Sharpe × total over 44.5                                                           |    0.115  |         8.7  |          0.0568 |              2.024 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × ATS Tom Chester × total over 44.5                                                            |    0.1102 |         9.07 |          0.0602 |              1.832 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 44.5                                                       |    0.1145 |         8.74 |          0.0637 |              1.796 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × ATS Sunia Turuva × total over 42.5                                                                         |    0.1342 |         7.45 |          0.0768 |              1.747 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                           |    0.1515 |         6.6  |          0.0869 |              1.744 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                           |    0.1317 |         7.59 |          0.0756 |              1.742 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × total over 41.5                                                             |    0.1475 |         6.78 |          0.0851 |              1.733 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                   |    0.1339 |         7.47 |          0.0783 |              1.709 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Fletcher Sharpe × total over 44.5                                                              |    0.1908 |         5.24 |          0.117  |              1.631 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 52.5                                                                            |    0.1366 |         7.32 |          0.0942 |              1.45  |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × Jaxon Purdue 2+ tries                                                                                           |    0.1053 |         9.5  |          0.0728 |              1.446 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × total over 50.5                                                                                            |    0.1529 |         6.54 |          0.1066 |              1.435 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × total over 52.5                                                                              |    0.1324 |         7.55 |          0.0929 |              1.425 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × ATS Tom Chester                                                                              |    0.1468 |         6.81 |          0.1032 |              1.423 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries                                                                                         |    0.1172 |         8.53 |          0.0825 |              1.421 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 50.5                                                                        |    0.1575 |         6.35 |          0.1115 |              1.413 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                            |    0.1656 |         6.04 |          0.1173 |              1.412 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.1687 |         5.93 |          0.1206 |              1.398 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × total over 49.5                                                                               |    0.1629 |         6.14 |          0.1174 |              1.387 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi                                                                               |    0.1985 |         5.04 |          0.1433 |              1.386 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula                                                                         |    0.157  |         6.37 |          0.1139 |              1.378 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                             |    0.2147 |         4.66 |          0.1563 |              1.373 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × Taylan May 2+ tries                                                                                                         |    0.122  |         8.19 |          0.089  |              1.372 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                         |    0.1527 |         6.55 |          0.1113 |              1.371 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × total over 42.5                                                                                            |    0.2188 |         4.57 |          0.16   |              1.368 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × total over 44.5                                                                              |    0.1888 |         5.3  |          0.1383 |              1.365 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 44.5                                                                            |    0.1961 |         5.1  |          0.1437 |              1.365 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                    |    0.1791 |         5.58 |          0.1313 |              1.364 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × match tries over 7.5                                                                                       |    0.2181 |         4.59 |          0.16   |              1.363 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Jamayne Isaako × total over 44.5                                                       |    0.0814 |        12.29 |          0.06   |              1.355 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × ATS Valentine Holmes × total over 42.5                                                                     |    0.1033 |         9.68 |          0.0767 |              1.348 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Taylan May × ATS Sunia Turuva                                                                                           |    0.1807 |         5.53 |          0.1341 |              1.348 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × match tries over 7.5                                                                       |    0.2086 |         4.79 |          0.1548 |              1.347 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × ATS Josh Addo-Carr × total over 44.5                                                         |    0.1137 |         8.79 |          0.0846 |              1.345 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Jaxon Purdue                                                                                             |    0.1427 |         7.01 |          0.1061 |              1.345 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Jaxon Purdue × match tries over 7.5                                                                         |    0.1996 |         5.01 |          0.1485 |              1.345 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                                     |    0.1236 |         8.09 |          0.0921 |              1.343 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                                   |    0.2226 |         4.49 |          0.1666 |              1.337 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 42.5                                                                        |    0.223  |         4.48 |          0.167  |              1.336 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Xavier Savage × total over 42.5                                                    |    0.1051 |         9.51 |          0.0787 |              1.336 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                          |    0.2152 |         4.65 |          0.1619 |              1.33  |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × Dominic Young 2+ tries                                                                                                 |    0.2309 |         4.33 |          0.1736 |              1.33  |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro                                                                             |    0.1751 |         5.71 |          0.1318 |              1.329 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.225  |         4.44 |          0.1697 |              1.326 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate                                                                                           |    0.1572 |         6.36 |          0.1187 |              1.325 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.1832 |         5.46 |          0.1383 |              1.324 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers by 13+ × ATS Taylan May                                                                                                           |    0.1776 |         5.63 |          0.1344 |              1.322 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                         |    0.2247 |         4.45 |          0.1702 |              1.32  |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.1819 |         5.5  |          0.1379 |              1.319 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × total over 41.5                                                                               |    0.2321 |         4.31 |          0.1762 |              1.318 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Fletcher Sharpe                                                                                |    0.2675 |         3.74 |          0.2034 |              1.315 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × total over 52.5                                                                                    |    0.1829 |         5.47 |          0.14   |              1.306 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Tommy Talau × total over 42.5                                                                  |    0.1137 |         8.8  |          0.0873 |              1.303 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.2565 |         3.9  |          0.197  |              1.302 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                    |    0.2569 |         3.89 |          0.1975 |              1.301 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                              |    0.1694 |         5.9  |          0.1306 |              1.298 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                                       |    0.1863 |         5.37 |          0.1447 |              1.288 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.1798 |         5.56 |          0.1397 |              1.287 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Grant Anderson × total over 42.5                                                    |    0.0845 |        11.83 |          0.0663 |              1.275 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × total over 44.5                                                                                    |    0.2669 |         3.75 |          0.2107 |              1.267 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Stephen Crichton × total over 41.5                                                        |    0.1061 |         9.43 |          0.0838 |              1.266 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × match tries over 7.5                                                                               |    0.2845 |         3.52 |          0.2268 |              1.254 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.2162 |         4.62 |          0.1725 |              1.253 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Phillip Sami × total over 44.5                                                                 |    0.1315 |         7.6  |          0.1058 |              1.243 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights by 13+ × ATS Dominic Young                                                                                                   |    0.2179 |         4.59 |          0.1781 |              1.224 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers -2.5 × ATS Taylan May                                                                                                             |    0.3067 |         3.26 |          0.255  |              1.203 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys -0.5 × ATS Jaxon Purdue                                                                                               |    0.2851 |         3.51 |          0.2373 |              1.202 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks -4.5 × ATS Ronaldo Mulitalo                                                                                         |    0.2903 |         3.45 |          0.2425 |              1.197 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles -1.5 × ATS Lehi Hopoate                                                                                             |    0.3043 |         3.29 |          0.2547 |              1.195 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.3315 |         3.02 |          0.278  |              1.192 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs -0.5 × ATS Alex Johnston                                                                                                |    0.3504 |         2.85 |          0.2965 |              1.182 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers -4.5 × ATS Thomas Jenkins                                                                                                     |    0.3406 |         2.94 |          0.2892 |              1.178 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights -2.5 × ATS Dominic Young                                                                                                     |    0.3837 |         2.61 |          0.3339 |              1.149 |
| Penrith Panthers v Sydney Roosters                     | ATS Thomas Jenkins × ATS Tommy Talau                                                                                                           |    0.2704 |         3.7  |          0.2689 |              1.005 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | ATS Ronaldo Mulitalo × ATS Xavier Savage                                                                                                       |    0.2426 |         4.12 |          0.2418 |              1.003 |
| Parramatta Eels v North Queensland Cowboys             | ATS Jaxon Purdue × ATS Josh Addo-Carr                                                                                                          |    0.3062 |         3.27 |          0.3057 |              1.002 |
| Brisbane Broncos v New Zealand Warriors                | ATS Alofiana Khan-Pereira × ATS Grant Anderson                                                                                                 |    0.2365 |         4.23 |          0.2359 |              1.002 |
| Manly-Warringah Sea Eagles v Dolphins                  | ATS Lehi Hopoate × ATS Jamayne Isaako                                                                                                          |    0.2139 |         4.67 |          0.2138 |              1.001 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | ATS Alex Johnston × ATS Stephen Crichton                                                                                                       |    0.2863 |         3.49 |          0.2866 |              0.999 |
| Newcastle Knights v Gold Coast Titans                  | ATS Dominic Young × ATS Phillip Sami                                                                                                           |    0.3463 |         2.89 |          0.3465 |              0.999 |
| Wests Tigers v St George Illawarra Dragons             | ATS Taylan May × ATS Valentine Holmes                                                                                                          |    0.2452 |         4.08 |          0.246  |              0.997 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round24.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._