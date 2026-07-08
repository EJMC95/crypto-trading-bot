# Phase 4 report — player props + SGM simulator

_Generated 2026-07-08. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| Wests Tigers v New Zealand Warriors                   |       0.4242 |         0.4235 |  0.0007 |
| Dolphins v Cronulla-Sutherland Sharks                 |       0.5378 |         0.5389 | -0.0012 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      |       0.5258 |         0.522  |  0.0039 |
| Sydney Roosters v Parramatta Eels                     |       0.6154 |         0.6194 | -0.004  |
| South Sydney Rabbitohs v Newcastle Knights            |       0.5752 |         0.5777 | -0.0025 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys |       0.5882 |         0.5825 |  0.0057 |
| Melbourne Storm v Gold Coast Titans                   |       0.6065 |         0.6    |  0.0065 |

Max |diff| = 0.0065 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 19 — top ATS props (model fair prices)

| match                                                 | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus |
|:------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|
| Wests Tigers v New Zealand Warriors                   | Wests Tigers                  | Taylan May              | C          |        0.61 |   0.458 |         2.18 |     0.126 |          7.9 |
| Wests Tigers v New Zealand Warriors                   | Wests Tigers                  | Jahream Bula            | FB         |        0.55 |   0.423 |         2.36 |     0.106 |          9.5 |
| Wests Tigers v New Zealand Warriors                   | Wests Tigers                  | Sunia Turuva            | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.8  |   0.55  |         1.82 |     0.191 |          5.2 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.75 |   0.529 |         1.89 |     0.174 |          5.7 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors          | Ali Leiataua            | C          |        0.35 |   0.294 |         3.4  |     0.048 |         20.7 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins                      | Jamayne Isaako          | W          |        0.66 |   0.483 |         2.07 |     0.142 |          7   |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins                      | Tevita Naufahu          | W          |        0.64 |   0.47  |         2.13 |     0.134 |          7.5 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins                      | Jack Bostock            | C          |        0.51 |   0.398 |         2.51 |     0.093 |         10.8 |
| Dolphins v Cronulla-Sutherland Sharks                 | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.65 |   0.479 |         2.09 |     0.139 |          7.2 |
| Dolphins v Cronulla-Sutherland Sharks                 | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.53 |   0.411 |         2.43 |     0.099 |         10.1 |
| Dolphins v Cronulla-Sutherland Sharks                 | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.46 |   0.369 |         2.71 |     0.078 |         12.8 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.71 |   0.507 |         1.97 |     0.159 |          6.3 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canterbury-Bankstown Bulldogs | Enari Tuala             | W          |        0.53 |   0.409 |         2.45 |     0.098 |         10.2 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canterbury-Bankstown Bulldogs | Stephen Crichton        | C          |        0.39 |   0.325 |         3.07 |     0.06  |         16.7 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders              | Xavier Savage           | W          |        0.6  |   0.451 |         2.22 |     0.122 |          8.2 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders              | Kaeo Weekes             | FB         |        0.55 |   0.425 |         2.35 |     0.107 |          9.3 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders              | Jed Stuart              | W          |        0.45 |   0.363 |         2.75 |     0.076 |         13.2 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.61 |   0.458 |         2.18 |     0.126 |          7.9 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters               | Junior Tupou            | B          |        0.5  |   0.395 |         2.53 |     0.091 |         11   |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters               | Tommy Talau             | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   |
| Sydney Roosters v Parramatta Eels                     | Parramatta Eels               | Josh Addo-Carr          | W          |        0.59 |   0.448 |         2.23 |     0.12  |          8.3 |
| Sydney Roosters v Parramatta Eels                     | Parramatta Eels               | Isaiah Iongi            | FB         |        0.4  |   0.331 |         3.02 |     0.062 |         16.1 |
| Sydney Roosters v Parramatta Eels                     | Parramatta Eels               | Jordan Samrani          | C          |        0.4  |   0.326 |         3.06 |     0.06  |         16.6 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs        | Alex Johnston           | W          |        1.11 |   0.671 |         1.49 |     0.306 |          3.3 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.55 |   0.421 |         2.37 |     0.105 |          9.5 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs        | Jye Gray                | FB         |        0.36 |   0.299 |         3.34 |     0.05  |         20   |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights             | Greg Marzhew            | W          |        0.77 |   0.538 |         1.86 |     0.181 |          5.5 |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights             | Dominic Young           | W          |        0.75 |   0.526 |         1.9  |     0.172 |          5.8 |
| South Sydney Rabbitohs v Newcastle Knights            | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.5  |   0.393 |         2.55 |     0.09  |         11.1 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.65 |   0.478 |         2.09 |     0.139 |          7.2 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.59 |   0.447 |         2.24 |     0.119 |          8.4 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles    | Clayton Faulalo         | FB         |        0.53 |   0.409 |         2.44 |     0.098 |         10.2 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys      | Murray Taulagi          | W          |        0.7  |   0.501 |         2    |     0.154 |          6.5 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys      | Scott Drinkwater        | FB         |        0.42 |   0.342 |         2.92 |     0.067 |         15   |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | North Queensland Cowboys      | Tom Chester             | C          |        0.39 |   0.325 |         3.07 |     0.06  |         16.7 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm               | Will Warbrick           | W          |        0.76 |   0.534 |         1.87 |     0.178 |          5.6 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm               | Moses Leo               | W          |        0.73 |   0.518 |         1.93 |     0.166 |          6   |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.67 |   0.489 |         2.04 |     0.146 |          6.8 |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans             | Phillip Sami            | W          |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans             | Jaylan De Groot         | C          |        0.44 |   0.357 |         2.8  |     0.073 |         13.7 |
| Melbourne Storm v Gold Coast Titans                   | Gold Coast Titans             | Jensen Taumoepeau       | W          |        0.41 |   0.337 |         2.97 |     0.064 |         15.5 |

## Round 19 — SGM candidates (fair vs independence pricing)

| match                                                 | combo                                                                              |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:------------------------------------------------------|:-----------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders win × Xavier Savage 2+ tries                                      |    0.081  |        12.34 |          0.0533 |              1.52  |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders win × ATS Xavier Savage × ATS Kaeo Weekes                         |    0.1263 |         7.92 |          0.0849 |              1.489 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders win × ATS Xavier Savage × match tries over 7.5                    |    0.1512 |         6.62 |          0.1046 |              1.446 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders win × ATS Xavier Savage × total over 40.5                         |    0.166  |         6.02 |          0.1157 |              1.435 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins win × Jamayne Isaako 2+ tries                                             |    0.1027 |         9.74 |          0.0726 |              1.415 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins win × ATS Jamayne Isaako × ATS Tevita Naufahu                             |    0.1604 |         6.24 |          0.1167 |              1.375 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 44.5                   |    0.2096 |         4.77 |          0.1527 |              1.373 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 44.5                |    0.2044 |         4.89 |          0.1494 |              1.368 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins win × ATS Jamayne Isaako × total over 44.5                                |    0.195  |         5.13 |          0.1427 |              1.366 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                          |    0.1436 |         6.96 |          0.1054 |              1.362 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5              |    0.2236 |         4.47 |          0.165  |              1.355 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × match tries over 7.5           |    0.218  |         4.59 |          0.1615 |              1.35  |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins win × ATS Jamayne Isaako × match tries over 7.5                           |    0.2073 |         4.82 |          0.1536 |              1.349 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries                             |    0.1048 |         9.54 |          0.0778 |              1.347 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                |    0.1002 |         9.98 |          0.0747 |              1.342 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Will Warbrick × total over 44.5                          |    0.2289 |         4.37 |          0.1709 |              1.339 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak |    0.215  |         4.65 |          0.161  |              1.336 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × Will Warbrick 2+ tries                                       |    0.1364 |         7.33 |          0.1022 |              1.335 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau                   |    0.1433 |         6.98 |          0.1078 |              1.33  |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Jason Saab                 |    0.1588 |         6.3  |          0.1195 |              1.33  |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5        |    0.2358 |         4.24 |          0.178  |              1.325 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Will Warbrick × match tries over 7.5                     |    0.2445 |         4.09 |          0.1846 |              1.324 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5             |    0.2361 |         4.23 |          0.1785 |              1.323 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi                   |    0.2072 |         4.83 |          0.1572 |              1.318 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                |    0.2198 |         4.55 |          0.1674 |              1.313 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm win × ATS Will Warbrick × ATS Moses Leo                            |    0.2062 |         4.85 |          0.1596 |              1.292 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × total over 44.5                   |    0.2721 |         3.67 |          0.2133 |              1.276 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5              |    0.2908 |         3.44 |          0.2305 |              1.262 |
| Canterbury-Bankstown Bulldogs v Canberra Raiders      | Canberra Raiders -0.5 × ATS Xavier Savage                                          |    0.2516 |         3.97 |          0.201  |              1.252 |
| Dolphins v Cronulla-Sutherland Sharks                 | Dolphins -2.5 × ATS Jamayne Isaako                                                 |    0.2725 |         3.67 |          0.2256 |              1.208 |
| Manly-Warringah Sea Eagles v North Queensland Cowboys | Manly-Warringah Sea Eagles -4.5 × ATS Lehi Hopoate                                 |    0.268  |         3.73 |          0.2224 |              1.205 |
| Sydney Roosters v Parramatta Eels                     | Sydney Roosters -4.5 × ATS Rex Bassingthwaighte                                    |    0.2757 |         3.63 |          0.2293 |              1.203 |
| Melbourne Storm v Gold Coast Titans                   | Melbourne Storm -4.5 × ATS Will Warbrick                                           |    0.3084 |         3.24 |          0.2577 |              1.197 |
| Wests Tigers v New Zealand Warriors                   | New Zealand Warriors -3.5 × ATS Alofiana Khan-Pereira                              |    0.3248 |         3.08 |          0.274  |              1.185 |
| South Sydney Rabbitohs v Newcastle Knights            | South Sydney Rabbitohs -4.5 × ATS Alex Johnston                                    |    0.3594 |         2.78 |          0.3073 |              1.169 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round19.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._