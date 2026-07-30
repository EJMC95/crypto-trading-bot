# Phase 4 report — player props + SGM simulator

_Generated 2026-07-30. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| St George Illawarra Dragons v Dolphins              |       0.3863 |         0.3832 |  0.0031 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     |       0.5804 |         0.582  | -0.0016 |
| Gold Coast Titans v New Zealand Warriors            |       0.4284 |         0.4325 | -0.0042 |
| Penrith Panthers v Canberra Raiders                 |       0.6594 |         0.6521 |  0.0074 |
| Brisbane Broncos v Newcastle Knights                |       0.5382 |         0.5455 | -0.0074 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs |       0.5504 |         0.5525 | -0.0021 |
| Wests Tigers v Parramatta Eels                      |       0.5165 |         0.5135 |  0.003  |

Max |diff| = 0.0074 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 22 — top ATS props (model fair prices)

| match                                               | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:----------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Murray Taulagi          | W          |        0.7  |   0.502 |         1.99 |     0.155 |          6.5 | 3t/6g    |
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Scott Drinkwater        | FB         |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 4t/9g    |
| North Queensland Cowboys v Sydney Roosters          | North Queensland Cowboys      | Tom Chester             | C          |        0.4  |   0.332 |         3.01 |     0.062 |         16   | 0t/1g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Junior Tupou            | B          |        0.59 |   0.444 |         2.25 |     0.117 |          8.5 | 3t/3g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Billy Smith             | C          |        0.53 |   0.41  |         2.44 |     0.098 |         10.2 | 3t/3g    |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.51 |   0.402 |         2.49 |     0.095 |         10.6 | —        |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Setu Tu                 | W          |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 | —        |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Tyrell Sloan            | W          |        0.56 |   0.429 |         2.33 |     0.109 |          9.2 | 2t/4g    |
| St George Illawarra Dragons v Dolphins              | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.48 |   0.383 |         2.61 |     0.085 |         11.8 | 2t/4g    |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Hamiso Tabuai-Fidow     | FB         |        0.85 |   0.571 |         1.75 |     0.208 |          4.8 | 7t/8g    |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Jamayne Isaako          | W          |        0.74 |   0.523 |         1.91 |     0.17  |          5.9 | 7t/10g   |
| St George Illawarra Dragons v Dolphins              | Dolphins                      | Selwyn Cobbo            | W          |        0.5  |   0.393 |         2.54 |     0.09  |         11.1 | 1t/4g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Moses Leo               | W          |        0.98 |   0.626 |         1.6  |     0.259 |          3.9 | 2t/1g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.59 |   0.444 |         2.25 |     0.118 |          8.5 | 0t/1g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm               | Siulagi Tuimalatu-Brown | W          |        0.55 |   0.423 |         2.36 |     0.106 |          9.5 | —        |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.85 |   0.574 |         1.74 |     0.21  |          4.8 | 5t/5g    |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Stephen Crichton        | FE         |        0.46 |   0.371 |         2.7  |     0.079 |         12.6 | 6t/13g   |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Canterbury-Bankstown Bulldogs | Enari Tuala             | C          |        0.46 |   0.367 |         2.72 |     0.078 |         12.9 | 4t/10g   |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | Dean Ieremia            | W          |        0.52 |   0.403 |         2.48 |     0.095 |         10.5 | 2t/3g    |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | Phillip Sami            | W          |        0.47 |   0.375 |         2.67 |     0.081 |         12.3 | 5t/10g   |
| Gold Coast Titans v New Zealand Warriors            | Gold Coast Titans             | Jayden Campbell         | FE         |        0.46 |   0.369 |         2.71 |     0.079 |         12.7 | 5t/8g    |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        1.04 |   0.647 |         1.54 |     0.28  |          3.6 | 2t/1g    |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.52 |   0.406 |         2.46 |     0.097 |         10.4 | 6t/16g   |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors          | Adam Pompey             | C          |        0.49 |   0.389 |         2.57 |     0.088 |         11.4 | 3t/5g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Thomas Jenkins          | W          |        0.8  |   0.55  |         1.82 |     0.19  |          5.3 | 0t/2g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Casey McLean            | C          |        0.79 |   0.546 |         1.83 |     0.187 |          5.3 | 3t/3g    |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers              | Nathan Cleary           | HB         |        0.5  |   0.392 |         2.55 |     0.09  |         11.1 | 6t/13g   |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Kaeo Weekes             | FB         |        0.53 |   0.412 |         2.43 |     0.1   |         10   | 3t/4g    |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Xavier Savage           | W          |        0.51 |   0.402 |         2.49 |     0.095 |         10.6 | 2t/3g    |
| Penrith Panthers v Canberra Raiders                 | Canberra Raiders              | Ethan Strange           | FE         |        0.36 |   0.302 |         3.31 |     0.051 |         19.6 | 1t/2g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Deine Mariner           | C          |        0.89 |   0.589 |         1.7  |     0.224 |          4.5 | 4t/2g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Josiah Karapani         | W          |        0.59 |   0.444 |         2.25 |     0.118 |          8.5 | 1t/1g    |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos              | Reece Walsh             | FB         |        0.45 |   0.364 |         2.75 |     0.076 |         13.1 | 2t/5g    |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Dominic Young           | W          |        0.73 |   0.519 |         1.93 |     0.167 |          6   | 5t/7g    |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Greg Marzhew            | W          |        0.69 |   0.499 |         2    |     0.153 |          6.6 | 1t/2g    |
| Brisbane Broncos v Newcastle Knights                | Newcastle Knights             | Fletcher Sharpe         | FE         |        0.48 |   0.38  |         2.63 |     0.084 |         11.9 | —        |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.71 |   0.51  |         1.96 |     0.16  |          6.2 | 7t/7g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.67 |   0.489 |         2.04 |     0.146 |          6.8 | 6t/8g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.59 |   0.444 |         2.25 |     0.118 |          8.5 | 3t/4g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.62 |   0.46  |         2.17 |     0.127 |          7.9 | 7t/13g   |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Campbell Graham         | W          |        0.59 |   0.445 |         2.25 |     0.118 |          8.5 | 6t/8g    |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | South Sydney Rabbitohs        | Jack Wighton            | C          |        0.43 |   0.347 |         2.89 |     0.069 |         14.6 | 11t/22g  |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Sunia Turuva            | W          |        0.96 |   0.618 |         1.62 |     0.25  |          4   | 7t/6g    |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Jahream Bula            | FB         |        0.7  |   0.502 |         1.99 |     0.155 |          6.4 | 3t/4g    |
| Wests Tigers v Parramatta Eels                      | Wests Tigers                  | Junior Tupou            | W          |        0.53 |   0.411 |         2.43 |     0.099 |         10.1 | 2t/5g    |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Josh Addo-Carr          | W          |        0.65 |   0.478 |         2.09 |     0.138 |          7.2 | 7t/11g   |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Isaiah Iongi            | FB         |        0.57 |   0.437 |         2.29 |     0.113 |          8.8 | 2t/2g    |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels               | Will Penisini           | C          |        0.44 |   0.355 |         2.82 |     0.072 |         13.9 | 3t/7g    |

## Round 22 — SGM candidates (fair vs independence pricing)

| match                                               | combo                                                                                                                                         |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:----------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × ATS Will Penisini × total over 44.5 × match tries over 9.5                      |    0.0372 |        26.91 |          0.0071 |              5.204 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5 × match tries over 9.5                   |    0.0284 |        35.16 |          0.0057 |              4.985 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Adam Pompey × total over 42.5 × match tries over 9.5 |    0.0472 |        21.18 |          0.0095 |              4.975 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani × ATS Reece Walsh × total over 44.5 × match tries over 9.5                     |    0.046  |        21.73 |          0.0094 |              4.893 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Sualauvi Fa'alogo × ATS Siulagi Tuimalatu-Brown × total over 41.5 × match tries over 9.5            |    0.0519 |        19.27 |          0.0111 |              4.685 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean × ATS Brian To'o × total over 42.5 × match tries over 9.5                        |    0.0505 |        19.79 |          0.0108 |              4.665 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5 × match tries over 9.5                 |    0.0521 |        19.18 |          0.0113 |              4.63  |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × ATS Selwyn Cobbo × total over 44.5 × match tries over 9.5                       |    0.0598 |        16.72 |          0.0135 |              4.424 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × Josh Addo-Carr 2+ tries × ATS Isaiah Iongi × total over 52.5                                                            |    0.0308 |        32.45 |          0.0108 |              2.845 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × Billy Smith 2+ tries × ATS Rex Bassingthwaighte × total over 52.5                                                       |    0.0206 |        48.5  |          0.0074 |              2.769 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries × ATS Ronaldo Mulitalo × total over 50.5                                                |    0.0436 |        22.94 |          0.0164 |              2.659 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × Deine Mariner 2+ tries × ATS Josiah Karapani × total over 52.5                                                         |    0.0496 |        20.15 |          0.019  |              2.612 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                     |    0.0598 |        16.73 |          0.0232 |              2.572 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × Moses Leo 2+ tries × ATS Sualauvi Fa'alogo × total over 49.5                                                            |    0.0651 |        15.36 |          0.0258 |              2.521 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Casey McLean × total over 50.5                                                           |    0.0592 |        16.9  |          0.024  |              2.466 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × Hamiso Tabuai-Fidow 2+ tries × ATS Jamayne Isaako × total over 52.5                                                            |    0.0597 |        16.75 |          0.0245 |              2.434 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels by 13+ × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 44.5                                                              |    0.0586 |        17.05 |          0.0245 |              2.393 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters by 13+ × ATS Billy Smith × ATS Rex Bassingthwaighte × total over 44.5                                                         |    0.0509 |        19.65 |          0.0216 |              2.35  |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                  |    0.0825 |        12.12 |          0.037  |              2.227 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos by 13+ × ATS Deine Mariner × ATS Josiah Karapani × total over 44.5                                                           |    0.0793 |        12.6  |          0.0356 |              2.226 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm by 13+ × ATS Moses Leo × ATS Sualauvi Fa'alogo × total over 41.5                                                              |    0.0977 |        10.23 |          0.0449 |              2.175 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                       |    0.0859 |        11.64 |          0.0397 |              2.164 |
| St George Illawarra Dragons v Dolphins              | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × total over 44.5                                                              |    0.1064 |         9.4  |          0.0517 |              2.058 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Casey McLean × total over 42.5                                                             |    0.1161 |         8.61 |          0.0564 |              2.058 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 44.5                                                                 |    0.1032 |         9.69 |          0.0557 |              1.851 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte × total over 44.5                                                            |    0.0849 |        11.78 |          0.0468 |              1.814 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani × total over 44.5                                                              |    0.1333 |         7.5  |          0.0757 |              1.76  |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                     |    0.1351 |         7.4  |          0.078  |              1.733 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Sualauvi Fa'alogo × total over 41.5                                                                 |    0.158  |         6.33 |          0.0929 |              1.7   |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                          |    0.1395 |         7.17 |          0.0823 |              1.695 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean × total over 42.5                                                                |    0.1729 |         5.79 |          0.1052 |              1.643 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako × total over 44.5                                                                 |    0.1624 |         6.16 |          0.0995 |              1.633 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × total over 52.5                                                                                       |    0.1156 |         8.65 |          0.078  |              1.483 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × Josh Addo-Carr 2+ tries                                                                                                 |    0.0929 |        10.76 |          0.0632 |              1.471 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × total over 52.5                                                                                    |    0.1245 |         8.03 |          0.0861 |              1.446 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi                                                                                   |    0.1381 |         7.24 |          0.096  |              1.437 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × Billy Smith 2+ tries                                                                                                    |    0.0708 |        14.13 |          0.0493 |              1.436 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 50.5                                                                            |    0.1545 |         6.47 |          0.1079 |              1.432 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                   |    0.1785 |         5.6  |          0.1269 |              1.406 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries                                                                                         |    0.1165 |         8.59 |          0.0829 |              1.404 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × total over 44.5                                                                                       |    0.1635 |         6.12 |          0.1172 |              1.396 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Rex Bassingthwaighte                                                                              |    0.1147 |         8.72 |          0.0824 |              1.391 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × Deine Mariner 2+ tries                                                                                                 |    0.1593 |         6.28 |          0.1152 |              1.384 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 52.5                                                                                      |    0.1772 |         5.64 |          0.1281 |              1.383 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × total over 44.5                                                                                    |    0.1758 |         5.69 |          0.1274 |              1.38  |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × total over 52.5                                                                                    |    0.1559 |         6.41 |          0.1132 |              1.377 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × match tries over 7.5                                                                                  |    0.1742 |         5.74 |          0.1267 |              1.375 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × total over 49.5                                                                                         |    0.1905 |         5.25 |          0.1395 |              1.366 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × match tries over 7.5                                                                               |    0.1871 |         5.35 |          0.1372 |              1.364 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani                                                                                |    0.1837 |         5.44 |          0.135  |              1.361 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Kaeo Weekes × total over 42.5                                                                 |    0.1084 |         9.22 |          0.0798 |              1.36  |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels by 13+ × ATS Josh Addo-Carr                                                                                                   |    0.1312 |         7.62 |          0.0965 |              1.359 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo                                                                       |    0.1774 |         5.64 |          0.1307 |              1.357 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × match tries over 7.5                                                                       |    0.2146 |         4.66 |          0.1586 |              1.354 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters win × ATS Billy Smith × ATS Murray Taulagi × total over 44.5                                                                  |    0.0798 |        12.53 |          0.0591 |              1.351 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 42.5                                                                            |    0.2152 |         4.65 |          0.1593 |              1.351 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                        |    0.1798 |         5.56 |          0.1333 |              1.348 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels win × ATS Josh Addo-Carr × ATS Sunia Turuva × total over 44.5                                                                 |    0.1056 |         9.47 |          0.0784 |              1.347 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                     |    0.2053 |         4.87 |          0.1527 |              1.345 |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters by 13+ × ATS Billy Smith                                                                                                      |    0.1284 |         7.79 |          0.0954 |              1.345 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × Moses Leo 2+ tries                                                                                                      |    0.193  |         5.18 |          0.144  |              1.341 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Sualauvi Fa'alogo                                                                                   |    0.208  |         4.81 |          0.1553 |              1.339 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Setu Tu × total over 44.5                                                                        |    0.1159 |         8.63 |          0.0868 |              1.335 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × total over 44.5                                                                                    |    0.2265 |         4.41 |          0.1708 |              1.326 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                            |    0.1926 |         5.19 |          0.1455 |              1.323 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Alex Johnston × total over 42.5                                                        |    0.0973 |        10.28 |          0.0737 |              1.321 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                              |    0.2543 |         3.93 |          0.1926 |              1.321 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                   |    0.2552 |         3.92 |          0.1933 |              1.321 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa                                                                                           |    0.1672 |         5.98 |          0.1269 |              1.318 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × match tries over 7.5                                                                                    |    0.251  |         3.98 |          0.1907 |              1.316 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 44.5                                                                                      |    0.252  |         3.97 |          0.1916 |              1.315 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × ATS Dominic Young × total over 44.5                                                                |    0.1175 |         8.51 |          0.0894 |              1.314 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos win × ATS Deine Mariner × match tries over 7.5                                                                               |    0.2415 |         4.14 |          0.184  |              1.312 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × Hamiso Tabuai-Fidow 2+ tries                                                                                                   |    0.1634 |         6.12 |          0.1245 |              1.312 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × ATS Jacob Kiraz × total over 41.5                                                                       |    0.1551 |         6.45 |          0.1186 |              1.308 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm win × ATS Moses Leo × total over 41.5                                                                                         |    0.2713 |         3.69 |          0.2079 |              1.305 |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × match tries over 7.5                                                                                 |    0.2678 |         3.73 |          0.2063 |              1.298 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dean Ieremia × total over 42.5                                                     |    0.1041 |         9.6  |          0.0806 |              1.293 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                   |    0.2593 |         3.86 |          0.2013 |              1.288 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos by 13+ × ATS Deine Mariner                                                                                                   |    0.184  |         5.43 |          0.1432 |              1.285 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                        |    0.2591 |         3.86 |          0.2018 |              1.284 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                |    0.1539 |         6.5  |          0.1202 |              1.28  |
| St George Illawarra Dragons v Dolphins              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Jamayne Isaako                                                                                   |    0.2235 |         4.47 |          0.1751 |              1.276 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm by 13+ × ATS Moses Leo                                                                                                        |    0.2128 |         4.7  |          0.168  |              1.267 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers win × ATS Thomas Jenkins × ATS Casey McLean                                                                                  |    0.2366 |         4.23 |          0.1886 |              1.255 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                  |    0.2324 |         4.3  |          0.1857 |              1.252 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                       |    0.2146 |         4.66 |          0.1723 |              1.246 |
| St George Illawarra Dragons v Dolphins              | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow                                                                                                     |    0.2183 |         4.58 |          0.1754 |              1.244 |
| Wests Tigers v Parramatta Eels                      | Parramatta Eels -0.5 × ATS Josh Addo-Carr                                                                                                     |    0.2658 |         3.76 |          0.2196 |              1.21  |
| North Queensland Cowboys v Sydney Roosters          | Sydney Roosters -1.5 × ATS Billy Smith                                                                                                        |    0.2471 |         4.05 |          0.2045 |              1.208 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | Cronulla-Sutherland Sharks -2.5 × ATS Sione Katoa                                                                                             |    0.2935 |         3.41 |          0.2437 |              1.204 |
| Penrith Panthers v Canberra Raiders                 | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                    |    0.3153 |         3.17 |          0.2644 |              1.193 |
| Brisbane Broncos v Newcastle Knights                | Brisbane Broncos -2.5 × ATS Deine Mariner                                                                                                     |    0.329  |         3.04 |          0.2762 |              1.191 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | Melbourne Storm -4.5 × ATS Moses Leo                                                                                                          |    0.3411 |         2.93 |          0.2867 |              1.19  |
| St George Illawarra Dragons v Dolphins              | Dolphins -4.5 × ATS Hamiso Tabuai-Fidow                                                                                                       |    0.3324 |         3.01 |          0.2835 |              1.173 |
| Gold Coast Titans v New Zealand Warriors            | New Zealand Warriors -3.5 × ATS Alofiana Khan-Pereira                                                                                         |    0.377  |         2.65 |          0.3245 |              1.162 |
| St George Illawarra Dragons v Dolphins              | ATS Hamiso Tabuai-Fidow × ATS Setu Tu                                                                                                         |    0.2596 |         3.85 |          0.2588 |              1.003 |
| Gold Coast Titans v New Zealand Warriors            | ATS Alofiana Khan-Pereira × ATS Dean Ieremia                                                                                                  |    0.2608 |         3.83 |          0.2604 |              1.002 |
| Cronulla-Sutherland Sharks v South Sydney Rabbitohs | ATS Sione Katoa × ATS Alex Johnston                                                                                                           |    0.2348 |         4.26 |          0.2345 |              1.002 |
| Wests Tigers v Parramatta Eels                      | ATS Josh Addo-Carr × ATS Sunia Turuva                                                                                                         |    0.2945 |         3.4  |          0.2941 |              1.001 |
| Melbourne Storm v Canterbury-Bankstown Bulldogs     | ATS Moses Leo × ATS Jacob Kiraz                                                                                                               |    0.3567 |         2.8  |          0.3567 |              1     |
| Brisbane Broncos v Newcastle Knights                | ATS Deine Mariner × ATS Dominic Young                                                                                                         |    0.3093 |         3.23 |          0.3097 |              0.999 |
| Penrith Panthers v Canberra Raiders                 | ATS Thomas Jenkins × ATS Kaeo Weekes                                                                                                          |    0.2238 |         4.47 |          0.2244 |              0.998 |
| North Queensland Cowboys v Sydney Roosters          | ATS Billy Smith × ATS Murray Taulagi                                                                                                          |    0.2062 |         4.85 |          0.2072 |              0.995 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round22.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._