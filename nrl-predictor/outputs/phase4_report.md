# Phase 4 report — player props + SGM simulator

_Generated 2026-07-27. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                               |   p_home_sim |   p_home_tier2 |    diff |
|:----------------------------------------------------|-------------:|---------------:|--------:|
| North Queensland Cowboys v Sydney Roosters          |       0.4738 |         0.4749 | -0.0012 |
| St George Illawarra Dragons v Dolphins              |       0.3858 |         0.3832 |  0.0026 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     |       0.5788 |         0.582  | -0.0032 |
| Gold Coast Titans v New Zealand Warriors            |       0.4291 |         0.4325 | -0.0034 |
| Penrith Panthers v Canberra Raiders                 |       0.6557 |         0.6521 |  0.0037 |
| Brisbane Broncos v Newcastle Knights                |       0.541  |         0.5455 | -0.0046 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs |       0.5492 |         0.5525 | -0.0033 |
| Wests Tigers v Parramatta Eels                      |       0.5162 |         0.5135 |  0.0027 |

Max |diff| = 0.0046 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 22 — top ATS props (model fair prices)

| match                                               | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:----------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Murray Taulagi          | W          |        0.7  |   0.502 |         1.99 |     0.155 |          6.5 | 3t/6g    |
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Scott Drinkwater        | FB         |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 4t/9g    |
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Tom Chester             | C          |        0.4  |   0.332 |         3.01 |     0.062 |         16   | 0t/1g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Junior Tupou            | B          |        0.59 |   0.444 |         2.25 |     0.117 |          8.5 | 3t/3g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Billy Smith             | C          |        0.53 |   0.41  |         2.44 |     0.098 |         10.2 | 3t/3g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.51 |   0.402 |         2.49 |     0.095 |         10.6 | —        |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Setu Tu                 | W          |        0.59 |   0.443 |         2.26 |     0.117 |          8.5 | —        |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Tyrell Sloan            | C          |        0.55 |   0.423 |         2.36 |     0.106 |          9.5 | 2t/4g    |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.47 |   0.377 |         2.65 |     0.082 |         12.2 | 2t/4g    |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Jamayne Isaako          | W          |        0.79 |   0.547 |         1.83 |     0.188 |          5.3 | 7t/10g   |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Tevita Naufahu          | W          |        0.71 |   0.508 |         1.97 |     0.159 |          6.3 | —        |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Jack Bostock            | C          |        0.51 |   0.398 |         2.52 |     0.092 |         10.8 | 1t/3g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Moses Leo               | W          |        0.95 |   0.613 |         1.63 |     0.245 |          4.1 | 2t/1g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Will Warbrick           | W          |        0.57 |   0.434 |         2.31 |     0.112 |          9   | 1t/4g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.57 |   0.432 |         2.31 |     0.111 |          9   | 0t/1g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.92 |   0.6   |         1.67 |     0.233 |          4.3 | 5t/5g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Stephen Crichton        | C          |        0.5  |   0.392 |         2.55 |     0.089 |         11.2 | 6t/13g   |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Enari Tuala             | W          |        0.49 |   0.388 |         2.57 |     0.088 |         11.4 | 4t/10g   |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | Phillip Sami            | W          |        0.47 |   0.375 |         2.67 |     0.081 |         12.3 | 5t/10g   |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | Jayden Campbell         | FE         |        0.46 |   0.369 |         2.71 |     0.079 |         12.7 | 5t/8g    |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | AJ Brimson              | C          |        0.41 |   0.339 |         2.95 |     0.065 |         15.3 | 5t/9g    |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.97 |   0.622 |         1.61 |     0.255 |          3.9 | 2t/1g    |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.49 |   0.385 |         2.6  |     0.086 |         11.6 | 6t/16g   |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Adam Pompey             | C          |        0.46 |   0.369 |         2.71 |     0.078 |         12.8 | 3t/5g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Thomas Jenkins          | W          |        0.68 |   0.494 |         2.03 |     0.149 |          6.7 | 0t/2g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Casey McLean            | C          |        0.67 |   0.49  |         2.04 |     0.146 |          6.8 | 3t/3g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Blaize Talagi           | FE         |        0.44 |   0.357 |         2.8  |     0.073 |         13.7 | 2t/3g    |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Kaeo Weekes             | FB         |        0.66 |   0.481 |         2.08 |     0.141 |          7.1 | 3t/4g    |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Xavier Savage           | W          |        0.64 |   0.47  |         2.13 |     0.134 |          7.5 | 2t/3g    |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Daine Laurie            | FE         |        0.35 |   0.294 |         3.41 |     0.048 |         20.8 | 1t/3g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Josiah Karapani         | W          |        0.64 |   0.473 |         2.11 |     0.136 |          7.4 | 1t/1g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Brendan Piakura         | 2R         |        0.41 |   0.335 |         2.99 |     0.064 |         15.7 | 2t/2g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Antonio Verhoeven       | C          |        0.4  |   0.327 |         3.06 |     0.06  |         16.6 | —        |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Dominic Young           | W          |        0.76 |   0.53  |         1.89 |     0.175 |          5.7 | 5t/7g    |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Greg Marzhew            | W          |        0.71 |   0.51  |         1.96 |     0.16  |          6.2 | 1t/2g    |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.49 |   0.39  |         2.57 |     0.088 |         11.3 | —        |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.78 |   0.542 |         1.84 |     0.185 |          5.4 | 7t/7g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.74 |   0.521 |         1.92 |     0.168 |          5.9 | 6t/8g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.64 |   0.474 |         2.11 |     0.136 |          7.3 | 3t/4g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.67 |   0.488 |         2.05 |     0.145 |          6.9 | 7t/13g   |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.49 |   0.385 |         2.6  |     0.086 |         11.6 | 1t/2g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Brandon Smith           | HK         |        0.35 |   0.293 |         3.42 |     0.048 |         20.9 | 5t/10g   |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Sunia Turuva            | W          |        1    |   0.631 |         1.59 |     0.263 |          3.8 | 7t/6g    |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Jahream Bula            | FB         |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 3t/4g    |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Taylan May              | C          |        0.63 |   0.47  |         2.13 |     0.133 |          7.5 | 2t/4g    |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Josh Addo-Carr          | W          |        0.71 |   0.507 |         1.97 |     0.158 |          6.3 | 7t/11g   |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Isaiah Iongi            | FB         |        0.62 |   0.464 |         2.15 |     0.13  |          7.7 | 2t/2g    |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Brian Kelly             | W          |        0.38 |   0.316 |         3.16 |     0.056 |         17.7 | 4t/12g   |

## Round 22 — SGM candidates (fair vs independence pricing)

| match                                               | combo                                                                                                                                         |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:----------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × ATS Antonio Verhoeven × ATS Jesse Arthars × total over 44.5 × match tries over 9.5               |    0.0222 |        45.13 |          0.0044 |              5.068 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean × ATS Brian To'o × total over 42.5 × match tries over 9.5                        |    0.039  |        25.64 |          0.0078 |              5.027 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5 × match tries over 9.5                   |    0.0284 |        35.16 |          0.0057 |              4.985 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Adam Pompey × total over 42.5 × match tries over 9.5 |    0.0396 |        25.28 |          0.0082 |              4.85  |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × ATS Brian Kelly × total over 44.5 × match tries over 9.5                        |    0.0344 |        29.04 |          0.0074 |              4.675 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Will Warbrick × ATS Sualauvi Fa'alogo × total over 41.5 × match tries over 9.5                      |    0.0503 |        19.9  |          0.0109 |              4.631 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5 × match tries over 9.5                 |    0.0607 |        16.49 |          0.0136 |              4.464 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × ATS Tevita Naufahu × ATS Jack Bostock × total over 44.5 × match tries over 9.5                            |    0.0575 |        17.4  |          0.0131 |              4.403 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × Josiah Karapani 2+ tries × ATS Antonio Verhoeven × total over 52.5                                                     |    0.0242 |        41.29 |          0.0085 |              2.834 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × Billy Smith 2+ tries × ATS Rex Bassingthwaighte × total over 52.5                                                       |    0.0206 |        48.5  |          0.0074 |              2.769 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × Josh Addo-Carr 2+ tries × ATS Isaiah Iongi × total over 52.5                                                            |    0.0371 |        26.95 |          0.0135 |              2.75  |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Casey McLean × total over 50.5                                                           |    0.0439 |        22.8  |          0.0166 |              2.638 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                     |    0.0524 |        19.09 |          0.0202 |              2.587 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × Moses Leo 2+ tries × ATS Will Warbrick × total over 49.5                                                                |    0.0599 |        16.69 |          0.0236 |              2.542 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × Jamayne Isaako 2+ tries × ATS Tevita Naufahu × total over 52.5                                                                 |    0.0556 |        17.99 |          0.0219 |              2.532 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries × ATS Ronaldo Mulitalo × total over 50.5                                                |    0.0509 |        19.64 |          0.0202 |              2.518 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos by 13+ × ATS Josiah Karapani × ATS Antonio Verhoeven × total over 44.5                                                       |    0.0501 |        19.98 |          0.0208 |              2.407 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters by 13+ × ATS Billy Smith × ATS Rex Bassingthwaighte × total over 44.5                                                         |    0.0509 |        19.65 |          0.0216 |              2.35  |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels by 13+ × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 44.5                                                              |    0.0651 |        15.36 |          0.0287 |              2.265 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                       |    0.0786 |        12.72 |          0.0354 |              2.222 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Casey McLean × total over 42.5                                                             |    0.0995 |        10.05 |          0.0457 |              2.176 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm by 13+ × ATS Moses Leo × ATS Will Warbrick × total over 41.5                                                                  |    0.092  |        10.87 |          0.0424 |              2.168 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                  |    0.0908 |        11.02 |          0.042  |              2.163 |
| St George Illawarra Dragons v Dolphins              | Dolphins by 13+ × ATS Jamayne Isaako × ATS Tevita Naufahu × total over 44.5                                                                   |    0.1039 |         9.63 |          0.0492 |              2.111 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × ATS Antonio Verhoeven × total over 44.5                                                          |    0.0814 |        12.29 |          0.0444 |              1.833 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte × total over 44.5                                                            |    0.0849 |        11.78 |          0.0468 |              1.814 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 44.5                                                                 |    0.113  |         8.85 |          0.0646 |              1.75  |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                          |    0.1293 |         7.73 |          0.0742 |              1.743 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean × total over 42.5                                                                |    0.1471 |         6.8  |          0.0853 |              1.725 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                     |    0.1506 |         6.64 |          0.0882 |              1.707 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Will Warbrick × total over 41.5                                                                     |    0.1486 |         6.73 |          0.088  |              1.689 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × ATS Tevita Naufahu × total over 44.5                                                                      |    0.1577 |         6.34 |          0.094  |              1.678 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × total over 52.5                                                                                       |    0.1156 |         8.65 |          0.078  |              1.483 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × total over 52.5                                                                                  |    0.1307 |         7.65 |          0.0894 |              1.461 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × Josh Addo-Carr 2+ tries                                                                                                 |    0.1062 |         9.42 |          0.0729 |              1.457 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                   |    0.1659 |         6.03 |          0.1144 |              1.451 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × Billy Smith 2+ tries                                                                                                    |    0.0708 |        14.13 |          0.0493 |              1.436 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × Josiah Karapani 2+ tries                                                                                               |    0.1003 |         9.97 |          0.0709 |              1.414 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 50.5                                                                            |    0.1613 |         6.2  |          0.1147 |              1.407 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × total over 52.5                                                                                           |    0.1734 |         5.77 |          0.1235 |              1.404 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi                                                                                   |    0.1549 |         6.45 |          0.1105 |              1.403 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × total over 52.5                                                                                    |    0.1292 |         7.74 |          0.0923 |              1.4   |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Kaeo Weekes × total over 42.5                                                                 |    0.1179 |         8.48 |          0.0842 |              1.4   |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × total over 44.5                                                                                       |    0.1635 |         6.12 |          0.1172 |              1.396 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte                                                                              |    0.1147 |         8.72 |          0.0824 |              1.391 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × total over 44.5                                                                                  |    0.189  |         5.29 |          0.136  |              1.39  |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × total over 49.5                                                                                         |    0.1874 |         5.34 |          0.1356 |              1.382 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × ATS Antonio Verhoeven                                                                            |    0.1092 |         9.16 |          0.0792 |              1.379 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries                                                                                         |    0.133  |         7.52 |          0.0966 |              1.377 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × match tries over 7.5                                                                             |    0.202  |         4.95 |          0.1468 |              1.376 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Josiah Karapani × ATS Dominic Young × total over 44.5                                                              |    0.0989 |        10.11 |          0.0719 |              1.376 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × match tries over 7.5                                                                                  |    0.1742 |         5.74 |          0.1267 |              1.375 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                              |    0.2353 |         4.25 |          0.1729 |              1.361 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                        |    0.1736 |         5.76 |          0.1277 |              1.36  |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                   |    0.2361 |         4.24 |          0.1739 |              1.358 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Murray Taulagi × total over 44.5                                                                  |    0.0798 |        12.53 |          0.0591 |              1.351 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × match tries over 7.5                                                                       |    0.2279 |         4.39 |          0.1691 |              1.348 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × total over 44.5                                                                                    |    0.1848 |         5.41 |          0.1372 |              1.347 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × Moses Leo 2+ tries                                                                                                      |    0.1831 |         5.46 |          0.136  |              1.347 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo                                                                       |    0.1987 |         5.03 |          0.1476 |              1.346 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                            |    0.1765 |         5.67 |          0.1312 |              1.346 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters by 13+ × ATS Billy Smith                                                                                                      |    0.1284 |         7.79 |          0.0954 |              1.345 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                     |    0.1873 |         5.34 |          0.1395 |              1.342 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 42.5                                                                            |    0.2279 |         4.39 |          0.17   |              1.341 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos by 13+ × ATS Josiah Karapani                                                                                                 |    0.1522 |         6.57 |          0.1136 |              1.341 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Will Warbrick                                                                                       |    0.1961 |         5.1  |          0.1468 |              1.336 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × match tries over 7.5                                                                               |    0.1972 |         5.07 |          0.1476 |              1.336 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels by 13+ × ATS Josh Addo-Carr                                                                                                   |    0.1392 |         7.18 |          0.1045 |              1.332 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × match tries over 7.5                                                                                    |    0.2469 |         4.05 |          0.1857 |              1.33  |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × total over 44.5                                                                                           |    0.2455 |         4.07 |          0.1847 |              1.329 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Sunia Turuva × total over 44.5                                                                 |    0.1147 |         8.72 |          0.0864 |              1.328 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × ATS Setu Tu × total over 44.5                                                                             |    0.1082 |         9.24 |          0.0816 |              1.326 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Jacob Kiraz × total over 41.5                                                                       |    0.1611 |         6.21 |          0.1223 |              1.317 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × Jamayne Isaako 2+ tries                                                                                                        |    0.1487 |         6.72 |          0.1129 |              1.317 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × total over 41.5                                                                                         |    0.2672 |         3.74 |          0.2032 |              1.315 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × match tries over 7.5                                                                                      |    0.2615 |         3.82 |          0.199  |              1.314 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                   |    0.2508 |         3.99 |          0.1909 |              1.314 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                        |    0.2514 |         3.98 |          0.1922 |              1.308 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Alex Johnston × total over 42.5                                                        |    0.1087 |         9.2  |          0.0832 |              1.307 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                |    0.1201 |         8.33 |          0.092  |              1.305 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Jamayne Isaako × ATS Tevita Naufahu                                                                                        |    0.2148 |         4.66 |          0.1646 |              1.305 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa                                                                                           |    0.1762 |         5.67 |          0.1352 |              1.303 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean                                                                                  |    0.1962 |         5.1  |          0.1523 |              1.288 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Phillip Sami × total over 42.5                                                     |    0.0924 |        10.83 |          0.0719 |              1.284 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                  |    0.2119 |         4.72 |          0.1665 |              1.273 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm by 13+ × ATS Moses Leo                                                                                                        |    0.2068 |         4.84 |          0.1635 |              1.265 |
| St George Illawarra Dragons v Dolphins              | Dolphins by 13+ × ATS Jamayne Isaako                                                                                                          |    0.2129 |         4.7  |          0.1693 |              1.258 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                       |    0.2037 |         4.91 |          0.162  |              1.258 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos -2.5 × ATS Josiah Karapani                                                                                                   |    0.2685 |         3.72 |          0.2199 |              1.221 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                    |    0.2879 |         3.47 |          0.2382 |              1.209 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters -1.5 × ATS Billy Smith                                                                                                        |    0.2471 |         4.05 |          0.2045 |              1.208 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels -0.5 × ATS Josh Addo-Carr                                                                                                     |    0.2824 |         3.54 |          0.2347 |              1.203 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks -2.5 × ATS Sione Katoa                                                                                             |    0.3092 |         3.23 |          0.258  |              1.199 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm -4.5 × ATS Moses Leo                                                                                                          |    0.3322 |         3.01 |          0.2795 |              1.189 |
| St George Illawarra Dragons v Dolphins              | Dolphins -4.5 × ATS Jamayne Isaako                                                                                                            |    0.3221 |         3.1  |          0.2724 |              1.183 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                         |    0.3638 |         2.75 |          0.3103 |              1.173 |
| Penrith Panthers v Canberra Raiders                 | ATS Thomas Jenkins × ATS Kaeo Weekes                                                                                                          |    0.2383 |         4.2  |          0.2378 |              1.002 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | ATS Sione Katoa × ATS Alex Johnston                                                                                                           |    0.265  |         3.77 |          0.2649 |              1     |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | ATS Moses Leo × ATS Jacob Kiraz                                                                                                               |    0.3677 |         2.72 |          0.368  |              0.999 |
| Gold Coast Titans v New Zealand Warriors            | ATS Alofiana Khan-Pereira × ATS Phillip Sami                                                                                                  |    0.2325 |         4.3  |          0.2328 |              0.999 |
| Wests Tigers v Parramatta Eels                      | ATS Josh Addo-Carr × ATS Sunia Turuva                                                                                                         |    0.3216 |         3.11 |          0.3218 |              0.999 |
| North Queensland Cowboys v Sydney Roosters          | ATS Billy Smith × ATS Murray Taulagi                                                                                                          |    0.2062 |         4.85 |          0.2072 |              0.995 |
| St George Illawarra Dragons v Dolphins              | ATS Jamayne Isaako × ATS Setu Tu                                                                                                              |    0.2396 |         4.17 |          0.2416 |              0.992 |
| Brisbane Broncos v Newcastle Knights                | ATS Josiah Karapani × ATS Dominic Young                                                                                                       |    0.246  |         4.07 |          0.2483 |              0.991 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round22.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._