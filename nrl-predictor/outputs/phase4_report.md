# Phase 4 report — player props + SGM simulator

_Generated 2026-07-20. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                                   |   p_home_sim |   p_home_tier2 |    diff |
|:--------------------------------------------------------|-------------:|---------------:|--------:|
| Parramatta Eels v Penrith Panthers                      |       0.3769 |         0.3791 | -0.0022 |
| Newcastle Knights v Sydney Roosters                     |       0.4608 |         0.4593 |  0.0015 |
| South Sydney Rabbitohs v Melbourne Storm                |       0.523  |         0.5319 | -0.0089 |
| Canberra Raiders v Wests Tigers                         |       0.5656 |         0.5645 |  0.0011 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    |       0.456  |         0.4625 | -0.0065 |
| North Queensland Cowboys v Brisbane Broncos             |       0.5355 |         0.529  |  0.0065 |
| St George Illawarra Dragons v Gold Coast Titans         |       0.4855 |         0.4818 |  0.0037 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks |       0.5354 |         0.5347 |  0.0008 |

Max |diff| = 0.0089 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 21 — top ATS props (model fair prices)

| match                                                   | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:--------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Parramatta Eels v Penrith Panthers                      | Parramatta Eels               | Josh Addo-Carr          | W          |        0.6  |   0.452 |         2.21 |     0.123 |          8.2 | 8t/14g   |
| Parramatta Eels v Penrith Panthers                      | Parramatta Eels               | Sean Russell            | C          |        0.4  |   0.329 |         3.04 |     0.061 |         16.3 | 3t/7g    |
| Parramatta Eels v Penrith Panthers                      | Parramatta Eels               | Brian Kelly             | W          |        0.37 |   0.306 |         3.27 |     0.053 |         19   | 5t/14g   |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers              | Thomas Jenkins          | W          |        0.89 |   0.588 |         1.7  |     0.222 |          4.5 | 5t/4g    |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers              | Brian To'o              | W          |        0.6  |   0.452 |         2.21 |     0.123 |          8.2 | 11t/15g  |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers              | Paul Alamoti            | C          |        0.49 |   0.39  |         2.56 |     0.089 |         11.3 | 3t/4g    |
| Newcastle Knights v Sydney Roosters                     | Newcastle Knights             | Dominic Young           | W          |        0.9  |   0.595 |         1.68 |     0.229 |          4.4 | 3t/4g    |
| Newcastle Knights v Sydney Roosters                     | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.5  |   0.394 |         2.54 |     0.09  |         11.1 | 0t/1g    |
| Newcastle Knights v Sydney Roosters                     | Newcastle Knights             | Bradman Best            | C          |        0.5  |   0.393 |         2.54 |     0.09  |         11.1 | 2t/4g    |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.55 |   0.424 |         2.36 |     0.106 |          9.4 | —        |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters               | Hugo Savala             | FE         |        0.54 |   0.414 |         2.41 |     0.101 |          9.9 | 2t/2g    |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters               | Tommy Talau             | W          |        0.51 |   0.398 |         2.51 |     0.093 |         10.8 | 4t/7g    |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Alex Johnston           | W          |        1.17 |   0.691 |         1.45 |     0.328 |          3.1 | 19t/16g  |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.61 |   0.459 |         2.18 |     0.127 |          7.9 | 3t/4g    |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Tallis Duncan           | C          |        0.5  |   0.392 |         2.55 |     0.09  |         11.2 | 3t/4g    |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Will Warbrick           | W          |        0.81 |   0.555 |         1.8  |     0.195 |          5.1 | 4t/5g    |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Moses Leo               | W          |        0.7  |   0.505 |         1.98 |     0.157 |          6.4 | —        |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.56 |   0.426 |         2.35 |     0.107 |          9.3 | 1t/3g    |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Xavier Savage           | W          |        0.63 |   0.468 |         2.14 |     0.132 |          7.6 | 2t/4g    |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Kaeo Weekes             | FB         |        0.6  |   0.451 |         2.22 |     0.122 |          8.2 | 2t/4g    |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Jed Stuart              | W          |        0.6  |   0.451 |         2.22 |     0.122 |          8.2 | 2t/3g    |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Taylan May              | C          |        0.69 |   0.5   |         2    |     0.154 |          6.5 | 2t/4g    |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Jahream Bula            | FB         |        0.61 |   0.455 |         2.2  |     0.124 |          8   | 3t/7g    |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Sunia Turuva            | W          |        0.57 |   0.433 |         2.31 |     0.111 |          9   | 2t/5g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.48 |   0.38  |         2.63 |     0.084 |         11.9 | 2t/6g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Bronson Xerri           | C          |        0.47 |   0.376 |         2.66 |     0.082 |         12.3 | 3t/5g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Connor Tracey           | FB         |        0.45 |   0.365 |         2.74 |     0.077 |         13.1 | 4t/7g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.99 |   0.627 |         1.59 |     0.259 |          3.9 | 4t/4g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.75 |   0.526 |         1.9  |     0.172 |          5.8 | 8t/13g   |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Ali Leiataua            | C          |        0.39 |   0.321 |         3.11 |     0.058 |         17.2 | —        |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Tom Chester             | C          |        0.51 |   0.401 |         2.5  |     0.094 |         10.7 | 1t/1g    |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Jaxon Purdue            | C          |        0.46 |   0.369 |         2.71 |     0.079 |         12.7 | 2t/4g    |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Murray Taulagi          | W          |        0.45 |   0.36  |         2.78 |     0.074 |         13.5 | 3t/11g   |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Ezra Mam                | B          |        0.58 |   0.438 |         2.29 |     0.114 |          8.8 | 5t/5g    |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Josiah Karapani         | W          |        0.54 |   0.419 |         2.39 |     0.103 |          9.7 | 2t/3g    |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Jesse Arthars           | W          |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 6t/11g   |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Tyrell Sloan            | C          |        0.76 |   0.532 |         1.88 |     0.177 |          5.7 | 7t/7g    |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Setu Tu                 | W          |        0.54 |   0.418 |         2.4  |     0.103 |          9.7 | —        |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.52 |   0.408 |         2.45 |     0.098 |         10.2 | 10t/17g  |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Phillip Sami            | W          |        0.66 |   0.483 |         2.07 |     0.142 |          7   | 7t/13g   |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Arama Hau               | 2R         |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | 2t/2g    |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Jensen Taumoepeau       | W          |        0.48 |   0.383 |         2.61 |     0.085 |         11.7 | —        |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Clayton Faulalo         | FB         |        0.73 |   0.519 |         1.93 |     0.167 |          6   | 3t/3g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Toluta'u Koula          | C          |        0.66 |   0.482 |         2.08 |     0.141 |          7.1 | 5t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.54 |   0.417 |         2.4  |     0.102 |          9.8 | 3t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | 7t/9g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.48 |   0.38  |         2.63 |     0.084 |         11.9 | 5t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.42 |   0.344 |         2.91 |     0.067 |         14.9 | 1t/2g    |

## Round 21 — SGM candidates (fair vs independence pricing)

| match                                                   | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:--------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × ATS Jaxon Purdue × ATS Murray Taulagi × total over 44.5 × match tries over 9.5                |    0.0269 |        37.2  |          0.0052 |              5.176 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × ATS Jensen Taumoepeau × ATS Jaylan De Groot × total over 42.5 × match tries over 9.5                |    0.0318 |        31.49 |          0.0062 |              5.159 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × ATS Cody Ramsey × total over 44.5 × match tries over 9.5                    |    0.0246 |        40.65 |          0.0048 |              5.15  |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × ATS Moses Leo × ATS Sualauvi Fa'alogo × total over 44.5 × match tries over 9.5                       |    0.0516 |        19.39 |          0.0102 |              5.079 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Ali Leiataua × total over 40.5 × match tries over 9.5 |    0.0405 |        24.67 |          0.008  |              5.073 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × ATS Toluta'u Koula × ATS Jason Saab × total over 42.5 × match tries over 9.5            |    0.0457 |        21.87 |          0.0095 |              4.79  |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes × ATS Jed Stuart × total over 43.5 × match tries over 9.5                           |    0.0457 |        21.86 |          0.01   |              4.589 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Paul Alamoti × total over 42.5 × match tries over 9.5                         |    0.0503 |        19.87 |          0.0114 |              4.397 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × Tom Chester 2+ tries × ATS Jaxon Purdue × total over 52.5                                                       |    0.0198 |        50.61 |          0.0065 |              3.035 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × Rex Bassingthwaighte 2+ tries × ATS Tommy Talau × total over 52.5                                                        |    0.0237 |        42.16 |          0.0082 |              2.881 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × Will Warbrick 2+ tries × ATS Moses Leo × total over 52.5                                                                 |    0.0467 |        21.43 |          0.0164 |              2.837 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × Phillip Sami 2+ tries × ATS Jensen Taumoepeau × total over 50.5                                                        |    0.03   |        33.29 |          0.0106 |              2.828 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × Clayton Faulalo 2+ tries × ATS Toluta'u Koula × total over 50.5                                               |    0.043  |        23.27 |          0.016  |              2.683 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 48.5                                      |    0.0697 |        14.34 |          0.0266 |              2.626 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × Xavier Savage 2+ tries × ATS Kaeo Weekes × total over 51.5                                                              |    0.034  |        29.45 |          0.013  |              2.607 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys by 13+ × ATS Tom Chester × ATS Jaxon Purdue × total over 44.5                                                         |    0.0478 |        20.9  |          0.0195 |              2.455 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 50.5                                                              |    0.0586 |        17.05 |          0.0239 |              2.455 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                          |    0.0561 |        17.81 |          0.0234 |              2.402 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans by 13+ × ATS Phillip Sami × ATS Jensen Taumoepeau × total over 42.5                                                          |    0.0585 |        17.09 |          0.0245 |              2.385 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm by 13+ × ATS Will Warbrick × ATS Moses Leo × total over 44.5                                                                   |    0.0705 |        14.18 |          0.0305 |              2.313 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles by 13+ × ATS Clayton Faulalo × ATS Toluta'u Koula × total over 42.5                                                 |    0.0773 |        12.93 |          0.0338 |              2.289 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders by 13+ × ATS Xavier Savage × ATS Kaeo Weekes × total over 43.5                                                                |    0.0737 |        13.58 |          0.0328 |              2.248 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 40.5                                        |    0.0972 |        10.28 |          0.0444 |              2.189 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                |    0.0992 |        10.08 |          0.048  |              2.066 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × ATS Jaxon Purdue × total over 44.5                                                            |    0.0794 |        12.6  |          0.0425 |              1.868 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                             |    0.0902 |        11.09 |          0.0493 |              1.828 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × ATS Moses Leo × total over 44.5                                                                      |    0.1299 |         7.7  |          0.0714 |              1.819 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × ATS Jensen Taumoepeau × total over 42.5                                                             |    0.0981 |        10.19 |          0.0542 |              1.811 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × ATS Toluta'u Koula × total over 42.5                                                    |    0.1311 |         7.63 |          0.0741 |              1.769 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes × total over 43.5                                                                   |    0.1181 |         8.47 |          0.0677 |              1.743 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 40.5                                           |    0.168  |         5.95 |          0.0983 |              1.71  |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                   |    0.1536 |         6.51 |          0.093  |              1.651 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × total over 52.5                                                                               |    0.1145 |         8.74 |          0.0763 |              1.5   |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 52.5                                                                               |    0.1215 |         8.23 |          0.0818 |              1.485 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × Will Warbrick 2+ tries                                                                                                   |    0.1291 |         7.74 |          0.0889 |              1.453 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × total over 51.5                                                                                     |    0.1469 |         6.81 |          0.1017 |              1.445 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × total over 50.5                                                                                     |    0.1359 |         7.36 |          0.0943 |              1.441 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × Tom Chester 2+ tries                                                                                            |    0.0679 |        14.72 |          0.0473 |              1.437 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × Phillip Sami 2+ tries                                                                                                  |    0.0998 |        10.02 |          0.0698 |              1.43  |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × total over 50.5                                                                         |    0.1466 |         6.82 |          0.1029 |              1.424 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × total over 44.5                                                                               |    0.1631 |         6.13 |          0.1148 |              1.421 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × ATS Moses Leo                                                                                        |    0.1821 |         5.49 |          0.1283 |              1.419 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × Clayton Faulalo 2+ tries                                                                                      |    0.1196 |         8.36 |          0.0847 |              1.412 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                                                                            |    0.0771 |        12.96 |          0.0549 |              1.406 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × ATS Jensen Taumoepeau                                                                               |    0.1297 |         7.71 |          0.0925 |              1.403 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × total over 52.5                                                                                      |    0.1295 |         7.72 |          0.0927 |              1.397 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × ATS Jaxon Purdue                                                                              |    0.106  |         9.44 |          0.0759 |              1.396 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau                                                                               |    0.122  |         8.2  |          0.0874 |              1.395 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × match tries over 7.5                                                                          |    0.1729 |         5.78 |          0.1241 |              1.394 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 44.5                                                                               |    0.1715 |         5.83 |          0.1232 |              1.392 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Tom Chester × ATS Josiah Karapani × total over 44.5                                                         |    0.067  |        14.93 |          0.0483 |              1.388 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × Xavier Savage 2+ tries                                                                                                  |    0.0987 |        10.13 |          0.0712 |              1.386 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5                                                                          |    0.1835 |         5.45 |          0.1329 |              1.381 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.1866 |         5.36 |          0.1354 |              1.378 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × ATS Toluta'u Koula                                                                      |    0.1759 |         5.68 |          0.1281 |              1.374 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 48.5                                                                         |    0.1653 |         6.05 |          0.1205 |              1.372 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys by 13+ × ATS Tom Chester                                                                                              |    0.1286 |         7.78 |          0.0941 |              1.366 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × match tries over 7.5                                                                                |    0.1908 |         5.24 |          0.14   |              1.364 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Dominic Young × total over 44.5                                                           |    0.1002 |         9.98 |          0.0735 |              1.363 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                    |    0.1899 |         5.27 |          0.1398 |              1.359 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes                                                                                     |    0.1551 |         6.45 |          0.1143 |              1.357 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × total over 42.5                                                                                     |    0.1902 |         5.26 |          0.1402 |              1.356 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × match tries over 7.5                                                                                |    0.2035 |         4.91 |          0.1501 |              1.355 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × match tries over 7.5                                                                    |    0.2068 |         4.84 |          0.1528 |              1.353 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × total over 43.5                                                                                     |    0.202  |         4.95 |          0.1494 |              1.352 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans by 13+ × ATS Phillip Sami                                                                                                    |    0.1463 |         6.83 |          0.1083 |              1.351 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × total over 44.5                                                                                      |    0.1903 |         5.26 |          0.141  |              1.349 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × total over 42.5                                                                         |    0.2061 |         4.85 |          0.1528 |              1.349 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte                                                                                              |    0.139  |         7.19 |          0.1034 |              1.344 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                             |    0.2318 |         4.31 |          0.1726 |              1.343 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × match tries over 7.5                                                                                 |    0.2028 |         4.93 |          0.1521 |              1.333 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Phillip Sami × ATS Tyrell Sloan × total over 42.5                                                                  |    0.0994 |        10.06 |          0.0747 |              1.332 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles by 13+ × ATS Clayton Faulalo                                                                                        |    0.1599 |         6.26 |          0.1203 |              1.329 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm win × ATS Will Warbrick × ATS Alex Johnston × total over 44.5                                                                  |    0.1292 |         7.74 |          0.0973 |              1.328 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Taylan May × total over 43.5                                                                    |    0.1    |        10    |          0.0755 |              1.325 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders by 13+ × ATS Xavier Savage                                                                                                    |    0.1612 |         6.2  |          0.1219 |              1.323 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.2213 |         4.52 |          0.1675 |              1.321 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm by 13+ × ATS Will Warbrick                                                                                                     |    0.1428 |         7    |          0.1082 |              1.32  |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 40.5                                                                         |    0.2431 |         4.11 |          0.1854 |              1.312 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.1735 |         5.76 |          0.1333 |              1.302 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Josh Addo-Carr × total over 42.5                                                               |    0.1203 |         8.31 |          0.0926 |              1.299 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                    |    0.2667 |         3.75 |          0.2056 |              1.298 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.266  |         3.76 |          0.2052 |              1.296 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Clayton Faulalo × ATS Ronaldo Mulitalo × total over 42.5                                                  |    0.0874 |        11.44 |          0.0677 |              1.291 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.2056 |         4.86 |          0.1596 |              1.288 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.1888 |         5.3  |          0.1472 |              1.283 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Jacob Kiraz × total over 40.5                                                       |    0.0897 |        11.15 |          0.071  |              1.263 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.2271 |         4.4  |          0.1822 |              1.246 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys -2.5 × ATS Tom Chester                                                                                                |    0.2292 |         4.36 |          0.1862 |              1.231 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters -2.5 × ATS Rex Bassingthwaighte                                                                                                |    0.2413 |         4.14 |          0.1981 |              1.218 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles -2.5 × ATS Clayton Faulalo                                                                                          |    0.2886 |         3.46 |          0.239  |              1.208 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders -2.5 × ATS Xavier Savage                                                                                                      |    0.2764 |         3.62 |          0.2292 |              1.206 |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm -0.5 × ATS Will Warbrick                                                                                                       |    0.3044 |         3.28 |          0.2534 |              1.201 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans -0.5 × ATS Phillip Sami                                                                                                      |    0.2872 |         3.48 |          0.2394 |              1.2   |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                     |    0.3175 |         3.15 |          0.2658 |              1.195 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.3491 |         2.86 |          0.2949 |              1.184 |
| St George Illawarra Dragons v Gold Coast Titans         | ATS Phillip Sami × ATS Tyrell Sloan                                                                                                            |    0.2606 |         3.84 |          0.2598 |              1.003 |
| Canberra Raiders v Wests Tigers                         | ATS Xavier Savage × ATS Taylan May                                                                                                             |    0.2354 |         4.25 |          0.2352 |              1.001 |
| Newcastle Knights v Sydney Roosters                     | ATS Rex Bassingthwaighte × ATS Dominic Young                                                                                                   |    0.253  |         3.95 |          0.2532 |              0.999 |
| South Sydney Rabbitohs v Melbourne Storm                | ATS Will Warbrick × ATS Alex Johnston                                                                                                          |    0.3865 |         2.59 |          0.3869 |              0.999 |
| North Queensland Cowboys v Brisbane Broncos             | ATS Tom Chester × ATS Josiah Karapani                                                                                                          |    0.1685 |         5.94 |          0.1687 |              0.999 |
| Parramatta Eels v Penrith Panthers                      | ATS Thomas Jenkins × ATS Josh Addo-Carr                                                                                                        |    0.2644 |         3.78 |          0.2651 |              0.997 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | ATS Alofiana Khan-Pereira × ATS Jacob Kiraz                                                                                                    |    0.24   |         4.17 |          0.2408 |              0.997 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | ATS Clayton Faulalo × ATS Ronaldo Mulitalo                                                                                                     |    0.2279 |         4.39 |          0.2291 |              0.994 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round21.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._