# Phase 4 report — player props + SGM simulator

_Generated 2026-07-23. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| South Sydney Rabbitohs v Melbourne Storm                |       0.5261 |         0.5319 | -0.0058 |
| Canberra Raiders v Wests Tigers                         |       0.5675 |         0.5645 |  0.0029 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    |       0.4584 |         0.4625 | -0.0042 |
| North Queensland Cowboys v Brisbane Broncos             |       0.5332 |         0.529  |  0.0042 |
| St George Illawarra Dragons v Gold Coast Titans         |       0.4841 |         0.4818 |  0.0023 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks |       0.5343 |         0.5347 | -0.0004 |

Max |diff| = 0.0058 vs 3σ MC bound 0.0173 → **PASSED**.

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
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Alex Johnston           | W          |        1.31 |   0.73  |         1.37 |     0.377 |          2.7 | 19t/16g  |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Campbell Graham         | W          |        0.71 |   0.508 |         1.97 |     0.159 |          6.3 | 8t/12g   |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs        | Euan Aitken             | 2R         |        0.34 |   0.285 |         3.51 |     0.045 |         22.2 | 5t/16g   |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Moses Leo               | W          |        0.8  |   0.551 |         1.81 |     0.192 |          5.2 | —        |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.63 |   0.469 |         2.13 |     0.133 |          7.5 | 1t/3g    |
| South Sydney Rabbitohs v Melbourne Storm                | Melbourne Storm               | Siulagi Tuimalatu-Brown | W          |        0.59 |   0.443 |         2.26 |     0.117 |          8.5 | —        |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Xavier Savage           | W          |        0.52 |   0.406 |         2.46 |     0.097 |         10.3 | 2t/4g    |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Kaeo Weekes             | FB         |        0.5  |   0.391 |         2.56 |     0.089 |         11.2 | 2t/4g    |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders              | Jed Stuart              | W          |        0.5  |   0.391 |         2.56 |     0.089 |         11.3 | 2t/3g    |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Faaletino Tavana        | W          |        0.73 |   0.518 |         1.93 |     0.166 |          6   | —        |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Jahream Bula            | FB         |        0.6  |   0.448 |         2.23 |     0.12  |          8.3 | 3t/7g    |
| Canberra Raiders v Wests Tigers                         | Wests Tigers                  | Sunia Turuva            | C          |        0.56 |   0.427 |         2.34 |     0.108 |          9.3 | 2t/5g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.51 |   0.398 |         2.51 |     0.092 |         10.8 | 2t/6g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Connor Tracey           | FB         |        0.48 |   0.382 |         2.62 |     0.084 |         11.8 | 4t/7g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | Canterbury-Bankstown Bulldogs | Viliame Kikau           | 2R         |        0.46 |   0.367 |         2.72 |     0.078 |         12.9 | 7t/14g   |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.99 |   0.63  |         1.59 |     0.262 |          3.8 | 4t/4g    |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.75 |   0.528 |         1.89 |     0.174 |          5.8 | 8t/13g   |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors          | Kurt Capewell           | 2R         |        0.4  |   0.329 |         3.04 |     0.061 |         16.3 | 5t/12g   |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Jeremiah Nanai          | 2R         |        0.53 |   0.413 |         2.42 |     0.1   |         10   | 6t/7g    |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Braidon Burns           | W          |        0.48 |   0.384 |         2.61 |     0.085 |         11.7 | 2t/5g    |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys      | Tom Chester             | C          |        0.46 |   0.368 |         2.72 |     0.078 |         12.9 | 1t/1g    |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Kotoni Staggs           | C          |        0.55 |   0.424 |         2.36 |     0.106 |          9.4 | 9t/13g   |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Ezra Mam                | FE         |        0.53 |   0.41  |         2.44 |     0.099 |         10.1 | 5t/5g    |
| North Queensland Cowboys v Brisbane Broncos             | Brisbane Broncos              | Josiah Karapani         | W          |        0.5  |   0.392 |         2.55 |     0.09  |         11.2 | 2t/3g    |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Tyrell Sloan            | W          |        0.76 |   0.533 |         1.88 |     0.177 |          5.6 | 7t/7g    |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Setu Tu                 | W          |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | —        |
| St George Illawarra Dragons v Gold Coast Titans         | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.53 |   0.409 |         2.45 |     0.098 |         10.2 | 10t/17g  |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Dean Ieremia            | W          |        0.74 |   0.525 |         1.91 |     0.171 |          5.8 | 1t/1g    |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Phillip Sami            | W          |        0.68 |   0.492 |         2.03 |     0.148 |          6.7 | 7t/13g   |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans             | Arama Hau               | 2R         |        0.56 |   0.426 |         2.35 |     0.108 |          9.3 | 2t/2g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Toluta'u Koula          | W          |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 5t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.59 |   0.447 |         2.24 |     0.12  |          8.4 | 3t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles    | Lehi Hopoate            | FB         |        0.45 |   0.362 |         2.77 |     0.075 |         13.3 | 0t/4g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.57 |   0.436 |         2.29 |     0.113 |          8.8 | 7t/9g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.47 |   0.376 |         2.66 |     0.082 |         12.2 | 5t/7g    |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.41 |   0.34  |         2.95 |     0.066 |         15.3 | 1t/2g    |

## Round 21 — SGM candidates (fair vs independence pricing)

| match                                                   | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:--------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × ATS Tom Chester × ATS Jaxon Purdue × total over 44.5 × match tries over 9.5                 |    0.0237 |        42.19 |          0.0045 |              5.239 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × ATS Cody Ramsey × total over 44.5 × match tries over 9.5                    |    0.0246 |        40.65 |          0.0048 |              5.15  |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Ali Leiataua × total over 40.5 × match tries over 9.5 |    0.0406 |        24.64 |          0.0079 |              5.141 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × ATS Jason Saab × ATS Lehi Hopoate × total over 42.5 × match tries over 9.5               |    0.0374 |        26.74 |          0.0075 |              4.999 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × ATS Phillip Sami × ATS Jaylan De Groot × total over 42.5 × match tries over 9.5                     |    0.0434 |        23.05 |          0.0087 |              4.988 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes × ATS Jed Stuart × total over 43.5 × match tries over 9.5                           |    0.0324 |        30.9  |          0.0068 |              4.791 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × ATS Latrell Siegwalt × total over 44.5 × match tries over 9.5           |    0.0466 |        21.47 |          0.0097 |              4.787 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Paul Alamoti × total over 42.5 × match tries over 9.5                         |    0.0503 |        19.87 |          0.0114 |              4.397 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × Braidon Burns 2+ tries × ATS Tom Chester × total over 52.5                                                      |    0.0169 |        59.31 |          0.0057 |              2.949 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × Rex Bassingthwaighte 2+ tries × ATS Tommy Talau × total over 52.5                                                        |    0.0237 |        42.16 |          0.0082 |              2.881 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × Dean Ieremia 2+ tries × ATS Phillip Sami × total over 50.5                                                             |    0.0451 |        22.15 |          0.0165 |              2.728 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × Xavier Savage 2+ tries × ATS Kaeo Weekes × total over 51.5                                                              |    0.0222 |        45.05 |          0.0082 |              2.718 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × Toluta'u Koula 2+ tries × ATS Jason Saab × total over 50.5                                                    |    0.0386 |        25.93 |          0.0142 |              2.712 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 48.5                                      |    0.0682 |        14.66 |          0.0261 |              2.61  |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys by 13+ × ATS Braidon Burns × ATS Tom Chester × total over 44.5                                                        |    0.0466 |        21.44 |          0.0187 |              2.498 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Campbell Graham × total over 52.5                                                    |    0.0855 |        11.69 |          0.0347 |              2.463 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 50.5                                                              |    0.0586 |        17.05 |          0.0239 |              2.455 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                          |    0.0561 |        17.81 |          0.0234 |              2.402 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles by 13+ × ATS Toluta'u Koula × ATS Jason Saab × total over 42.5                                                      |    0.0713 |        14.03 |          0.0308 |              2.316 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders by 13+ × ATS Xavier Savage × ATS Kaeo Weekes × total over 43.5                                                                |    0.0575 |        17.4  |          0.0249 |              2.309 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans by 13+ × ATS Dean Ieremia × ATS Phillip Sami × total over 42.5                                                               |    0.0737 |        13.58 |          0.0334 |              2.203 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 40.5                                        |    0.0949 |        10.54 |          0.0434 |              2.185 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                |    0.0992 |        10.08 |          0.048  |              2.066 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Campbell Graham × total over 44.5                                                      |    0.0957 |        10.45 |          0.0471 |              2.032 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × ATS Tom Chester × total over 44.5                                                           |    0.0755 |        13.25 |          0.0397 |              1.901 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                             |    0.0902 |        11.09 |          0.0493 |              1.828 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes × total over 43.5                                                                   |    0.0923 |        10.83 |          0.0516 |              1.79  |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × ATS Jason Saab × total over 42.5                                                         |    0.1202 |         8.32 |          0.0676 |              1.777 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × ATS Phillip Sami × total over 42.5                                                                  |    0.1293 |         7.73 |          0.0747 |              1.732 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 40.5                                           |    0.1671 |         5.98 |          0.097  |              1.723 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                   |    0.1536 |         6.51 |          0.093  |              1.651 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × total over 44.5                                                         |    0.1691 |         5.91 |          0.1025 |              1.649 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × total over 52.5                                                                             |    0.1079 |         9.27 |          0.0713 |              1.513 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 52.5                                                                               |    0.1215 |         8.23 |          0.0818 |              1.485 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × total over 51.5                                                                                     |    0.131  |         7.63 |          0.0895 |              1.464 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × Braidon Burns 2+ tries                                                                                          |    0.0607 |        16.47 |          0.0422 |              1.439 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × Dean Ieremia 2+ tries                                                                                                  |    0.1202 |         8.32 |          0.0839 |              1.433 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × total over 50.5                                                                          |    0.1445 |         6.92 |          0.1012 |              1.428 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × ATS Tom Chester                                                                             |    0.1008 |         9.92 |          0.0709 |              1.422 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × total over 44.5                                                                             |    0.1538 |         6.5  |          0.1083 |              1.42  |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × total over 50.5                                                                                     |    0.1424 |         7.02 |          0.101  |              1.409 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × Xavier Savage 2+ tries                                                                                                  |    0.0724 |        13.81 |          0.0515 |              1.406 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                                                                            |    0.0771 |        12.96 |          0.0549 |              1.406 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × match tries over 7.5                                                                        |    0.1636 |         6.11 |          0.1166 |              1.403 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × Toluta'u Koula 2+ tries                                                                                       |    0.1153 |         8.68 |          0.0823 |              1.4   |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau                                                                               |    0.122  |         8.2  |          0.0874 |              1.395 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 44.5                                                                               |    0.1715 |         5.83 |          0.1232 |              1.392 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes                                                                                     |    0.1203 |         8.31 |          0.0866 |              1.388 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.1869 |         5.35 |          0.1349 |              1.385 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys win × ATS Braidon Burns × ATS Kotoni Staggs × total over 44.5                                                         |    0.0637 |        15.69 |          0.0461 |              1.384 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5                                                                          |    0.1835 |         5.45 |          0.1329 |              1.381 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × match tries over 7.5                                                                                |    0.1825 |         5.48 |          0.1324 |              1.379 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 48.5                                                                         |    0.1645 |         6.08 |          0.1194 |              1.378 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × ATS Jason Saab                                                                           |    0.1611 |         6.21 |          0.117  |              1.377 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × ATS Phillip Sami                                                                                    |    0.1762 |         5.68 |          0.1282 |              1.375 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × ATS Faaletino Tavana × total over 43.5                                                              |    0.0937 |        10.67 |          0.0681 |              1.375 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders win × ATS Xavier Savage × total over 43.5                                                                                     |    0.1809 |         5.53 |          0.1317 |              1.374 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys by 13+ × ATS Braidon Burns                                                                                            |    0.124  |         8.07 |          0.0908 |              1.366 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Dominic Young × total over 44.5                                                           |    0.1002 |         9.98 |          0.0735 |              1.363 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                    |    0.1899 |         5.27 |          0.1398 |              1.359 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × match tries over 7.5                                                                     |    0.2054 |         4.87 |          0.1513 |              1.357 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                             |    0.2318 |         4.31 |          0.171  |              1.355 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × total over 42.5                                                                          |    0.2045 |         4.89 |          0.1514 |              1.351 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                            |    0.2523 |         3.96 |          0.1874 |              1.347 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte                                                                                              |    0.139  |         7.19 |          0.1034 |              1.344 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders by 13+ × ATS Xavier Savage                                                                                                    |    0.1428 |         7    |          0.1067 |              1.338 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham                                                                           |    0.2471 |         4.05 |          0.185  |              1.336 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × total over 42.5                                                                                     |    0.1992 |         5.02 |          0.1492 |              1.335 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.2215 |         4.51 |          0.1662 |              1.332 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × match tries over 7.5                                                                                |    0.1986 |         5.03 |          0.1492 |              1.331 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans by 13+ × ATS Dean Ieremia                                                                                                    |    0.1516 |         6.6  |          0.1147 |              1.322 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles win × ATS Toluta'u Koula × ATS Ronaldo Mulitalo × total over 42.5                                                   |    0.0877 |        11.4  |          0.0665 |              1.32  |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 40.5                                                                         |    0.2428 |         4.12 |          0.1842 |              1.318 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles by 13+ × ATS Toluta'u Koula                                                                                         |    0.1567 |         6.38 |          0.1191 |              1.316 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans win × ATS Dean Ieremia × ATS Tyrell Sloan × total over 42.5                                                                  |    0.1031 |         9.7  |          0.079  |              1.305 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.1735 |         5.76 |          0.1333 |              1.302 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Josh Addo-Carr × total over 42.5                                                               |    0.1203 |         8.31 |          0.0926 |              1.299 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                    |    0.2667 |         3.75 |          0.2056 |              1.298 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.266  |         3.76 |          0.2052 |              1.296 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.1876 |         5.33 |          0.1454 |              1.29  |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.2056 |         4.86 |          0.1596 |              1.288 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × total over 52.5                                                                               |    0.1719 |         5.82 |          0.1337 |              1.285 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Jacob Kiraz × total over 40.5                                                       |    0.0937 |        10.67 |          0.074  |              1.266 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Moses Leo × total over 44.5                                                               |    0.1392 |         7.18 |          0.1113 |              1.251 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.2271 |         4.4  |          0.1822 |              1.246 |
| North Queensland Cowboys v Brisbane Broncos             | North Queensland Cowboys -2.5 × ATS Braidon Burns                                                                                              |    0.218  |         4.59 |          0.1753 |              1.244 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × total over 44.5                                                                               |    0.2516 |         3.98 |          0.2025 |              1.242 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                          |    0.2693 |         3.71 |          0.2186 |              1.232 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                              |    0.2045 |         4.89 |          0.1679 |              1.218 |
| Newcastle Knights v Sydney Roosters                     | Sydney Roosters -2.5 × ATS Rex Bassingthwaighte                                                                                                |    0.2413 |         4.14 |          0.1981 |              1.218 |
| Canberra Raiders v Wests Tigers                         | Canberra Raiders -2.5 × ATS Xavier Savage                                                                                                      |    0.2458 |         4.07 |          0.2018 |              1.218 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | Manly-Warringah Sea Eagles -2.5 × ATS Toluta'u Koula                                                                                           |    0.2847 |         3.51 |          0.2365 |              1.204 |
| Parramatta Eels v Penrith Panthers                      | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                     |    0.3175 |         3.15 |          0.2658 |              1.195 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.3493 |         2.86 |          0.2938 |              1.189 |
| St George Illawarra Dragons v Gold Coast Titans         | Gold Coast Titans -0.5 × ATS Dean Ieremia                                                                                                      |    0.3041 |         3.29 |          0.2561 |              1.187 |
| South Sydney Rabbitohs v Melbourne Storm                | South Sydney Rabbitohs -1.5 × ATS Alex Johnston                                                                                                |    0.413  |         2.42 |          0.3622 |              1.14  |
| Canberra Raiders v Wests Tigers                         | ATS Xavier Savage × ATS Faaletino Tavana                                                                                                       |    0.2125 |         4.71 |          0.2107 |              1.008 |
| St George Illawarra Dragons v Gold Coast Titans         | ATS Dean Ieremia × ATS Tyrell Sloan                                                                                                            |    0.2765 |         3.62 |          0.276  |              1.002 |
| South Sydney Rabbitohs v Melbourne Storm                | ATS Alex Johnston × ATS Moses Leo                                                                                                              |    0.4013 |         2.49 |          0.4004 |              1.002 |
| Newcastle Knights v Sydney Roosters                     | ATS Rex Bassingthwaighte × ATS Dominic Young                                                                                                   |    0.253  |         3.95 |          0.2532 |              0.999 |
| Canterbury-Bankstown Bulldogs v New Zealand Warriors    | ATS Alofiana Khan-Pereira × ATS Jacob Kiraz                                                                                                    |    0.2526 |         3.96 |          0.253  |              0.999 |
| North Queensland Cowboys v Brisbane Broncos             | ATS Braidon Burns × ATS Kotoni Staggs                                                                                                          |    0.1612 |         6.21 |          0.1615 |              0.998 |
| Parramatta Eels v Penrith Panthers                      | ATS Thomas Jenkins × ATS Josh Addo-Carr                                                                                                        |    0.2644 |         3.78 |          0.2651 |              0.997 |
| Manly-Warringah Sea Eagles v Cronulla-Sutherland Sharks | ATS Toluta'u Koula × ATS Ronaldo Mulitalo                                                                                                      |    0.2241 |         4.46 |          0.2257 |              0.993 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round21.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._