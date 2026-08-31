# Phase 4 report — player props + SGM simulator

_Generated 2026-08-31. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                             |   p_home_sim |   p_home_tier2 |    diff |
|:--------------------------------------------------|-------------:|---------------:|--------:|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  |       0.5199 |         0.5213 | -0.0014 |
| Gold Coast Titans v Dolphins                      |       0.4302 |         0.4288 |  0.0014 |
| South Sydney Rabbitohs v Sydney Roosters          |       0.5063 |         0.5003 |  0.006  |
| New Zealand Warriors v Manly-Warringah Sea Eagles |       0.5338 |         0.5334 |  0.0004 |
| North Queensland Cowboys v Canberra Raiders       |       0.5373 |         0.5389 | -0.0016 |
| Cronulla-Sutherland Sharks v Melbourne Storm      |       0.5453 |         0.5467 | -0.0014 |
| St George Illawarra Dragons v Parramatta Eels     |       0.4767 |         0.4752 |  0.0016 |
| Penrith Panthers v Wests Tigers                   |       0.6916 |         0.6951 | -0.0034 |

Max |diff| = 0.0060 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 27 — top ATS props (model fair prices)

| match                                             | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:--------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Connor Tracey           | FB         |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 7t/7g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Enari Tuala             | W          |        0.51 |   0.397 |         2.52 |     0.092 |         10.9 | 2t/4g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.48 |   0.383 |         2.61 |     0.085 |         11.7 | 1t/4g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Josiah Karapani         | W          |        0.58 |   0.439 |         2.28 |     0.115 |          8.7 | 2t/2g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Jesse Arthars           | W          |        0.38 |   0.316 |         3.17 |     0.056 |         17.8 | 1t/4g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Xavier Willison         | FR         |        0.33 |   0.284 |         3.52 |     0.045 |         22.3 | 3t/5g    |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | Phillip Sami            | W          |        0.7  |   0.505 |         1.98 |     0.157 |          6.4 | 4t/6g    |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | Jaylan De Groot         | C          |        0.52 |   0.404 |         2.47 |     0.096 |         10.5 | 1t/2g    |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | Jensen Taumoepeau       | W          |        0.47 |   0.378 |         2.64 |     0.083 |         12.1 | —        |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Tevita Naufahu          | W          |        0.85 |   0.574 |         1.74 |     0.211 |          4.7 | 2t/1g    |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Jack Bostock            | C          |        0.57 |   0.436 |         2.29 |     0.113 |          8.8 | 2t/3g    |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Trai Fuller             | FB         |        0.5  |   0.394 |         2.54 |     0.09  |         11.1 | 1t/1g    |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.88 |   0.587 |         1.7  |     0.222 |          4.5 | 20t/25g  |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.53 |   0.41  |         2.44 |     0.099 |         10.1 | 2t/4g    |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Jye Gray                | FB         |        0.53 |   0.41  |         2.44 |     0.099 |         10.1 | 3t/4g    |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.55 |   0.421 |         2.37 |     0.105 |          9.5 | —        |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Cody Ramsey             | FB         |        0.52 |   0.407 |         2.46 |     0.097 |         10.3 | 1t/1g    |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Billy Smith             | C          |        0.46 |   0.369 |         2.71 |     0.079 |         12.7 | 3t/5g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        1.07 |   0.656 |         1.53 |     0.289 |          3.5 | 7t/4g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.7  |   0.502 |         1.99 |     0.155 |          6.5 | 13t/17g  |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Ali Leiataua            | C          |        0.4  |   0.332 |         3.01 |     0.063 |         16   | 1t/1g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.81 |   0.556 |         1.8  |     0.195 |          5.1 | 10t/7g   |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.59 |   0.443 |         2.26 |     0.117 |          8.5 | 3t/3g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Reuben Garrick          | C          |        0.51 |   0.4   |         2.5  |     0.094 |         10.7 | 8t/10g   |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Murray Taulagi          | W          |        0.57 |   0.435 |         2.3  |     0.112 |          8.9 | 3t/9g    |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Heilum Luki             | 2R         |        0.52 |   0.408 |         2.45 |     0.097 |         10.3 | 3t/5g    |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Liam Sutton             | FE         |        0.47 |   0.373 |         2.68 |     0.08  |         12.5 | 1t/1g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Xavier Savage           | W          |        0.73 |   0.516 |         1.94 |     0.165 |          6.1 | 3t/5g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Sebastian Kris          | C          |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 3t/7g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Kaeo Weekes             | FB         |        0.5  |   0.392 |         2.55 |     0.09  |         11.2 | 1t/4g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.74 |   0.521 |         1.92 |     0.168 |          5.9 | 7t/9g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.67 |   0.486 |         2.06 |     0.144 |          6.9 | 5t/9g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.58 |   0.438 |         2.28 |     0.114 |          8.7 | 2t/4g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Will Warbrick           | W          |        0.74 |   0.524 |         1.91 |     0.171 |          5.9 | 4t/4g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Moses Leo               | W          |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | —        |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Harry Grant             | HK         |        0.51 |   0.399 |         2.51 |     0.093 |         10.7 | 7t/10g   |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Mathew Feagai           | W          |        0.67 |   0.488 |         2.05 |     0.145 |          6.9 | 3t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Tyrell Sloan            | C          |        0.62 |   0.46  |         2.17 |     0.127 |          7.9 | 2t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Setu Tu                 | W          |        0.5  |   0.396 |         2.52 |     0.092 |         10.9 | 0t/1g    |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Josh Addo-Carr          | W          |        0.97 |   0.62  |         1.61 |     0.253 |          4   | 11t/9g   |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Isaiah Iongi            | FB         |        0.37 |   0.312 |         3.2  |     0.055 |         18.3 | 1t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Tallyn Da Silva         | B          |        0.35 |   0.297 |         3.36 |     0.049 |         20.2 | 2t/3g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Thomas Jenkins          | W          |        1.14 |   0.681 |         1.47 |     0.317 |          3.2 | 6t/3g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Brian To'o              | W          |        0.51 |   0.398 |         2.52 |     0.092 |         10.8 | 4t/8g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Paul Alamoti            | C          |        0.48 |   0.383 |         2.61 |     0.085 |         11.7 | 2t/3g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Taylan May              | C          |        0.55 |   0.421 |         2.38 |     0.105 |          9.6 | 0t/1g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Starford To'a           | C          |        0.54 |   0.419 |         2.38 |     0.104 |          9.6 | 3t/6g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Sunia Turuva            | W          |        0.51 |   0.401 |         2.49 |     0.094 |         10.6 | 1t/3g    |

## Round 27 — SGM candidates (fair vs independence pricing)

| match                                             | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:--------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × ATS Jesse Arthars × ATS Antonio Verhoeven × total over 40.5 × match tries over 9.5                |    0.0164 |        60.98 |          0.0028 |              5.935 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey × ATS Billy Smith × total over 42.5 × match tries over 9.5                    |    0.0297 |        33.72 |          0.0059 |              5.017 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × ATS Scott Drinkwater × ATS Tom Chester × total over 42.5 × match tries over 9.5            |    0.0249 |        40.1  |          0.005  |              4.966 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × ATS Sean Russell × total over 43.5 × match tries over 9.5                        |    0.0235 |        42.55 |          0.0049 |              4.817 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Ali Leiataua × total over 41.5 × match tries over 9.5 |    0.0444 |        22.52 |          0.0094 |              4.746 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5 × match tries over 9.5                  |    0.0513 |        19.5  |          0.0111 |              4.639 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Jack Bostock × ATS Trai Fuller × total over 44.5 × match tries over 9.5                                |    0.05   |        20    |          0.0109 |              4.572 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Paul Alamoti × total over 44.5 × match tries over 9.5                         |    0.0561 |        17.83 |          0.0133 |              4.204 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × Josiah Karapani 2+ tries × ATS Jesse Arthars × total over 48.5                                                          |    0.02   |        49.95 |          0.0064 |              3.106 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × Rex Bassingthwaighte 2+ tries × ATS Cody Ramsey × total over 50.5                                                        |    0.0238 |        42.05 |          0.0081 |              2.953 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × Murray Taulagi 2+ tries × ATS Scott Drinkwater × total over 50.5                                                |    0.0221 |        45.21 |          0.0079 |              2.809 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × Josh Addo-Carr 2+ tries × ATS Isaiah Iongi × total over 51.5                                                             |    0.0431 |        23.2  |          0.0158 |              2.726 |
| Gold Coast Titans v Dolphins                      | Dolphins win × Tevita Naufahu 2+ tries × ATS Jack Bostock × total over 52.5                                                                    |    0.0509 |        19.65 |          0.0195 |              2.615 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos by 13+ × ATS Josiah Karapani × ATS Jesse Arthars × total over 40.5                                                            |    0.0402 |        24.89 |          0.0155 |              2.587 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries × ATS Ronaldo Mulitalo × total over 50.5                                                 |    0.0436 |        22.96 |          0.0169 |              2.572 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 49.5                                      |    0.0752 |        13.29 |          0.0296 |              2.539 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte × ATS Cody Ramsey × total over 42.5                                                          |    0.0516 |        19.38 |          0.0211 |              2.443 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys by 13+ × ATS Murray Taulagi × ATS Scott Drinkwater × total over 42.5                                                  |    0.05   |        20    |          0.0212 |              2.358 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels by 13+ × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 43.5                                                               |    0.0613 |        16.31 |          0.0265 |              2.314 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 52.5                                                              |    0.0732 |        13.66 |          0.0316 |              2.313 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                   |    0.0827 |        12.1  |          0.0368 |              2.244 |
| Gold Coast Titans v Dolphins                      | Dolphins by 13+ × ATS Tevita Naufahu × ATS Jack Bostock × total over 44.5                                                                      |    0.0855 |        11.7  |          0.0385 |              2.218 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 41.5                                        |    0.0956 |        10.46 |          0.0449 |              2.129 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 44.5                                                                |    0.1159 |         8.63 |          0.0588 |              1.97  |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × ATS Jesse Arthars × total over 40.5                                                               |    0.0711 |        14.06 |          0.037  |              1.922 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey × total over 42.5                                                             |    0.0904 |        11.06 |          0.0481 |              1.878 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × ATS Scott Drinkwater × total over 42.5                                                     |    0.082  |        12.19 |          0.0455 |              1.803 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi × total over 43.5                                                                  |    0.1021 |         9.8  |          0.0574 |              1.777 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Jack Bostock × total over 44.5                                                                         |    0.1355 |         7.38 |          0.078  |              1.737 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 42.5                                                      |    0.1355 |         7.38 |          0.078  |              1.736 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 41.5                                           |    0.166  |         6.02 |          0.0991 |              1.675 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 44.5                                                                   |    0.1639 |         6.1  |          0.1026 |              1.597 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                                                                            |    0.0729 |        13.72 |          0.0488 |              1.495 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × Josiah Karapani 2+ tries                                                                                                |    0.0782 |        12.78 |          0.0524 |              1.494 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × total over 48.5                                                                                   |    0.116  |         8.62 |          0.078  |              1.488 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × ATS Jesse Arthars                                                                                 |    0.0924 |        10.82 |          0.063  |              1.466 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 50.5                                                                               |    0.1183 |         8.45 |          0.0808 |              1.465 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey                                                                               |    0.1179 |         8.48 |          0.0807 |              1.46  |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × total over 50.5                                                                            |    0.131  |         7.63 |          0.0908 |              1.443 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × match tries over 7.5                                                                              |    0.1519 |         6.58 |          0.1067 |              1.424 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × Murray Taulagi 2+ tries                                                                                         |    0.0812 |        12.31 |          0.0572 |              1.421 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 50.5                                                                             |    0.1548 |         6.46 |          0.1094 |              1.415 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × total over 40.5                                                                                   |    0.1652 |         6.05 |          0.1173 |              1.408 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries                                                                                          |    0.1216 |         8.22 |          0.0864 |              1.407 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × ATS Scott Drinkwater                                                                       |    0.1074 |         9.31 |          0.0764 |              1.406 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5                                                                          |    0.1644 |         6.08 |          0.118  |              1.393 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × total over 52.5                                                                                            |    0.168  |         5.95 |          0.1206 |              1.393 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos by 13+ × ATS Josiah Karapani                                                                                                  |    0.1168 |         8.56 |          0.0839 |              1.392 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 42.5                                                                               |    0.1644 |         6.08 |          0.1184 |              1.388 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × Josh Addo-Carr 2+ tries                                                                                                  |    0.1736 |         5.76 |          0.1252 |              1.387 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.204  |         4.9  |          0.1475 |              1.383 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Isaiah Iongi                                                                                    |    0.1339 |         7.47 |          0.0969 |              1.382 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte                                                                                              |    0.1199 |         8.34 |          0.0872 |              1.375 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × total over 51.5                                                                                     |    0.1703 |         5.87 |          0.124  |              1.374 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Josiah Karapani × ATS Connor Tracey × total over 40.5                                                               |    0.0828 |        12.08 |          0.0604 |              1.371 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo                                                                        |    0.1791 |         5.58 |          0.1313 |              1.364 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × match tries over 7.5                                                                       |    0.1819 |         5.5  |          0.1334 |              1.364 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × total over 42.5                                                                            |    0.182  |         5.49 |          0.1337 |              1.362 |
| Gold Coast Titans v Dolphins                      | Dolphins win × Tevita Naufahu 2+ tries                                                                                                         |    0.1575 |         6.35 |          0.1163 |              1.354 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                             |    0.2247 |         4.45 |          0.1667 |              1.348 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 49.5                                                                         |    0.1777 |         5.63 |          0.132  |              1.346 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys by 13+ × ATS Murray Taulagi                                                                                           |    0.1404 |         7.12 |          0.1045 |              1.344 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × match tries over 7.5                                                                        |    0.2156 |         4.64 |          0.1607 |              1.342 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 42.5                                                                             |    0.2158 |         4.63 |          0.1609 |              1.341 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Alex Johnston × total over 42.5                                                           |    0.0921 |        10.85 |          0.0691 |              1.334 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa                                                                                            |    0.1705 |         5.87 |          0.1278 |              1.334 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Jack Bostock                                                                                           |    0.1804 |         5.54 |          0.1354 |              1.333 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × total over 44.5                                                                                            |    0.24   |         4.17 |          0.1801 |              1.333 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Murray Taulagi × ATS Xavier Savage × total over 42.5                                                        |    0.0919 |        10.88 |          0.0692 |              1.328 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Phillip Sami × total over 44.5                                                                         |    0.1202 |         8.32 |          0.0907 |              1.326 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × match tries over 7.5                                                                                       |    0.2547 |         3.93 |          0.1938 |              1.314 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × match tries over 7.5                                                                                |    0.2405 |         4.16 |          0.184  |              1.307 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × total over 52.5                                                                                    |    0.2221 |         4.5  |          0.1702 |              1.305 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.2364 |         4.23 |          0.1813 |              1.304 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × total over 43.5                                                                                     |    0.2382 |         4.2  |          0.1828 |              1.303 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Will Warbrick × total over 42.5                                                         |    0.1098 |         9.11 |          0.0844 |              1.301 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Taylan May × total over 44.5                                                                   |    0.1408 |         7.1  |          0.1086 |              1.297 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 41.5                                                                         |    0.2537 |         3.94 |          0.1969 |              1.288 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Jason Saab × total over 41.5                                                        |    0.1402 |         7.13 |          0.1098 |              1.276 |
| Gold Coast Titans v Dolphins                      | Dolphins by 13+ × ATS Tevita Naufahu                                                                                                           |    0.1964 |         5.09 |          0.1544 |              1.272 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels by 13+ × ATS Josh Addo-Carr                                                                                                    |    0.1805 |         5.54 |          0.1423 |              1.269 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Mathew Feagai × total over 43.5                                                                 |    0.1139 |         8.78 |          0.0898 |              1.269 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.1896 |         5.27 |          0.1499 |              1.265 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × total over 44.5                                                                                    |    0.322  |         3.11 |          0.2573 |              1.251 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.3445 |         2.9  |          0.2776 |              1.241 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos -0.5 × ATS Josiah Karapani                                                                                                    |    0.2467 |         4.05 |          0.1998 |              1.235 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.2633 |         3.8  |          0.2137 |              1.232 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.2242 |         4.46 |          0.1826 |              1.228 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters -0.5 × ATS Rex Bassingthwaighte                                                                                                |    0.2424 |         4.13 |          0.1987 |              1.22  |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys -2.5 × ATS Murray Taulagi                                                                                             |    0.2476 |         4.04 |          0.2033 |              1.218 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks -2.5 × ATS Sione Katoa                                                                                              |    0.2971 |         3.37 |          0.2458 |              1.209 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.3095 |         3.23 |          0.2628 |              1.178 |
| Gold Coast Titans v Dolphins                      | Dolphins -3.5 × ATS Tevita Naufahu                                                                                                             |    0.3344 |         2.99 |          0.2843 |              1.176 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.3522 |         2.84 |          0.3001 |              1.173 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels -0.5 × ATS Josh Addo-Carr                                                                                                      |    0.3593 |         2.78 |          0.3084 |              1.165 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers -8.5 × ATS Thomas Jenkins                                                                                                     |    0.3781 |         2.65 |          0.3289 |              1.149 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | ATS Alofiana Khan-Pereira × ATS Jason Saab                                                                                                     |    0.365  |         2.74 |          0.3633 |              1.004 |
| Gold Coast Titans v Dolphins                      | ATS Tevita Naufahu × ATS Phillip Sami                                                                                                          |    0.2888 |         3.46 |          0.2882 |              1.002 |
| North Queensland Cowboys v Canberra Raiders       | ATS Murray Taulagi × ATS Xavier Savage                                                                                                         |    0.2262 |         4.42 |          0.226  |              1.001 |
| St George Illawarra Dragons v Parramatta Eels     | ATS Josh Addo-Carr × ATS Mathew Feagai                                                                                                         |    0.3039 |         3.29 |          0.3037 |              1     |
| Penrith Panthers v Wests Tigers                   | ATS Thomas Jenkins × ATS Taylan May                                                                                                            |    0.2888 |         3.46 |          0.2889 |              1     |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | ATS Josiah Karapani × ATS Connor Tracey                                                                                                        |    0.2262 |         4.42 |          0.2264 |              0.999 |
| South Sydney Rabbitohs v Sydney Roosters          | ATS Rex Bassingthwaighte × ATS Alex Johnston                                                                                                   |    0.245  |         4.08 |          0.2465 |              0.994 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | ATS Sione Katoa × ATS Will Warbrick                                                                                                            |    0.2713 |         3.69 |          0.2729 |              0.994 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round27.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._