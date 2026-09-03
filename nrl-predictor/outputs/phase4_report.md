# Phase 4 report — player props + SGM simulator

_Generated 2026-09-03. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  |       0.5176 |         0.5213 | -0.0037 |
| Gold Coast Titans v Dolphins                      |       0.4269 |         0.4288 | -0.0019 |
| South Sydney Rabbitohs v Sydney Roosters          |       0.5037 |         0.5003 |  0.0034 |
| New Zealand Warriors v Manly-Warringah Sea Eagles |       0.5362 |         0.5334 |  0.0028 |
| North Queensland Cowboys v Canberra Raiders       |       0.5381 |         0.5389 | -0.0008 |
| Cronulla-Sutherland Sharks v Melbourne Storm      |       0.5456 |         0.5467 | -0.0011 |
| St George Illawarra Dragons v Parramatta Eels     |       0.4723 |         0.4752 | -0.0028 |
| Penrith Panthers v Wests Tigers                   |       0.6974 |         0.6951 |  0.0023 |

Max |diff| = 0.0037 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 27 — top ATS props (model fair prices)

| match                                             | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:--------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Connor Tracey           | FB         |        0.7  |   0.502 |         1.99 |     0.155 |          6.4 | 7t/7g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Enari Tuala             | W          |        0.49 |   0.385 |         2.6  |     0.086 |         11.6 | 2t/4g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.47 |   0.372 |         2.69 |     0.08  |         12.5 | 1t/4g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Deine Mariner           | C          |        0.59 |   0.447 |         2.24 |     0.12  |          8.4 | 4t/5g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Josiah Karapani         | W          |        0.59 |   0.444 |         2.25 |     0.118 |          8.5 | 2t/2g    |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos              | Kotoni Staggs           | C          |        0.45 |   0.363 |         2.76 |     0.076 |         13.2 | 5t/10g   |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | Phillip Sami            | W          |        0.81 |   0.554 |         1.81 |     0.194 |          5.2 | 4t/6g    |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | Jaylan De Groot         | C          |        0.59 |   0.448 |         2.23 |     0.12  |          8.3 | 1t/2g    |
| Gold Coast Titans v Dolphins                      | Gold Coast Titans             | AJ Brimson              | C          |        0.47 |   0.376 |         2.66 |     0.082 |         12.2 | 2t/5g    |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Tevita Naufahu          | W          |        0.8  |   0.55  |         1.82 |     0.19  |          5.3 | 2t/1g    |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Hamiso Tabuai-Fidow     | FB         |        0.71 |   0.51  |         1.96 |     0.16  |          6.2 | 7t/9g    |
| Gold Coast Titans v Dolphins                      | Dolphins                      | Jack Bostock            | C          |        0.54 |   0.415 |         2.41 |     0.101 |          9.9 | 2t/3g    |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.85 |   0.573 |         1.74 |     0.21  |          4.8 | 20t/25g  |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Jye Gray                | FB         |        0.51 |   0.398 |         2.51 |     0.093 |         10.8 | 3t/4g    |
| South Sydney Rabbitohs v Sydney Roosters          | South Sydney Rabbitohs        | Latrell Mitchell        | C          |        0.48 |   0.382 |         2.62 |     0.085 |         11.8 | 4t/10g   |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.64 |   0.472 |         2.12 |     0.135 |          7.4 | —        |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Cody Ramsey             | FB         |        0.61 |   0.457 |         2.19 |     0.125 |          8   | 1t/1g    |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters               | Daniel Tupou            | W          |        0.6  |   0.453 |         2.21 |     0.123 |          8.1 | 13t/26g  |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        1.43 |   0.76  |         1.31 |     0.418 |          2.4 | 7t/4g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Ali Leiataua            | C          |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | 1t/1g    |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors          | Charnze Nicoll-Klokstad | FB         |        0.52 |   0.404 |         2.48 |     0.095 |         10.5 | 5t/11g   |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.76 |   0.532 |         1.88 |     0.177 |          5.7 | 10t/7g   |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Tom Trbojevic           | FB         |        0.58 |   0.438 |         2.28 |     0.114 |          8.8 | 11t/12g  |
| New Zealand Warriors v Manly-Warringah Sea Eagles | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.55 |   0.422 |         2.37 |     0.105 |          9.5 | 3t/3g    |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Robert Derby            | W          |        0.62 |   0.463 |         2.16 |     0.129 |          7.7 | 1t/1g    |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Braidon Burns           | W          |        0.58 |   0.439 |         2.28 |     0.115 |          8.7 | 0t/1g    |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys      | Heilum Luki             | 2R         |        0.48 |   0.382 |         2.62 |     0.084 |         11.8 | 3t/5g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Xavier Savage           | W          |        0.74 |   0.522 |         1.92 |     0.169 |          5.9 | 3t/5g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Kaeo Weekes             | FB         |        0.51 |   0.397 |         2.52 |     0.092 |         10.9 | 1t/4g    |
| North Queensland Cowboys v Canberra Raiders       | Canberra Raiders              | Jed Stuart              | W          |        0.46 |   0.369 |         2.71 |     0.078 |         12.8 | 0t/1g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.88 |   0.584 |         1.71 |     0.219 |          4.6 | 7t/9g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.79 |   0.548 |         1.83 |     0.189 |          5.3 | 5t/9g    |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks    | William Kennedy         | FB         |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | —        |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Moses Leo               | W          |        0.61 |   0.456 |         2.19 |     0.125 |          8   | —        |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Harry Grant             | HK         |        0.53 |   0.413 |         2.42 |     0.101 |          9.9 | 7t/10g   |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.48 |   0.38  |         2.63 |     0.083 |         12   | 1t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Mathew Feagai           | W          |        0.81 |   0.554 |         1.81 |     0.194 |          5.2 | 3t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Tyrell Sloan            | W          |        0.74 |   0.524 |         1.91 |     0.171 |          5.9 | 2t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.35 |   0.295 |         3.39 |     0.049 |         20.6 | 3t/14g   |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Josh Addo-Carr          | W          |        1.07 |   0.657 |         1.52 |     0.29  |          3.4 | 11t/9g   |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Tallyn Da Silva         | HK         |        0.39 |   0.323 |         3.1  |     0.059 |         17   | 2t/3g    |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels               | Will Penisini           | C          |        0.38 |   0.313 |         3.19 |     0.055 |         18.1 | 1t/4g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Thomas Jenkins          | W          |        1.36 |   0.742 |         1.35 |     0.393 |          2.5 | 6t/3g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Brian To'o              | W          |        0.6  |   0.452 |         2.21 |     0.122 |          8.2 | 4t/8g    |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers              | Casey McLean            | C          |        0.47 |   0.372 |         2.69 |     0.08  |         12.5 | 1t/3g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Jeral Skelton           | W          |        0.75 |   0.53  |         1.89 |     0.175 |          5.7 | 2t/4g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Junior Tupou            | W          |        0.74 |   0.521 |         1.92 |     0.168 |          5.9 | 2t/3g    |
| Penrith Panthers v Wests Tigers                   | Wests Tigers                  | Patrick Herbert         | C          |        0.48 |   0.38  |         2.63 |     0.084 |         12   | 2t/5g    |

## Round 27 — SGM candidates (fair vs independence pricing)

| match                                             | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:--------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani × ATS Kotoni Staggs × total over 40.5 × match tries over 9.5                    |    0.0288 |        34.75 |          0.0053 |              5.433 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey × ATS Daniel Tupou × total over 44.5 × match tries over 9.5                   |    0.0447 |        22.39 |          0.0086 |              5.182 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × ATS Braidon Burns × ATS Scott Drinkwater × total over 42.5 × match tries over 9.5            |    0.0325 |        30.81 |          0.0064 |              5.069 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Will Penisini × ATS Jordan Samrani × total over 42.5 × match tries over 9.5                     |    0.0265 |        37.76 |          0.0055 |              4.786 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Hamiso Tabuai-Fidow × ATS Jack Bostock × total over 44.5 × match tries over 9.5                        |    0.0588 |        17    |          0.0132 |              4.459 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Ali Leiataua × ATS Charnze Nicoll-Klokstad × total over 41.5 × match tries over 9.5 |    0.0495 |        20.21 |          0.0113 |              4.388 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × ATS William Kennedy × total over 43.5 × match tries over 9.5         |    0.0563 |        17.76 |          0.013  |              4.347 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Casey McLean × total over 44.5 × match tries over 9.5                         |    0.0663 |        15.08 |          0.0161 |              4.12  |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × Deine Mariner 2+ tries × ATS Josiah Karapani × total over 48.5                                                          |    0.0284 |        35.21 |          0.0095 |              2.982 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × Rex Bassingthwaighte 2+ tries × ATS Cody Ramsey × total over 52.5                                                        |    0.0299 |        33.47 |          0.0106 |              2.815 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × Robert Derby 2+ tries × ATS Braidon Burns × total over 50.5                                                     |    0.0311 |        32.15 |          0.0116 |              2.686 |
| Gold Coast Titans v Dolphins                      | Dolphins win × Tevita Naufahu 2+ tries × ATS Hamiso Tabuai-Fidow × total over 52.5                                                             |    0.0538 |        18.6  |          0.0208 |              2.591 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × Josh Addo-Carr 2+ tries × ATS Will Penisini × total over 50.5                                                            |    0.0484 |        20.67 |          0.0187 |              2.584 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos by 13+ × ATS Deine Mariner × ATS Josiah Karapani × total over 40.5                                                            |    0.0564 |        17.74 |          0.0221 |              2.548 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries × ATS Ronaldo Mulitalo × total over 51.5                                                 |    0.0621 |        16.1  |          0.0249 |              2.498 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Ali Leiataua × total over 49.5                                                 |    0.0863 |        11.59 |          0.0361 |              2.389 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte × ATS Cody Ramsey × total over 44.5                                                          |    0.061  |        16.39 |          0.0255 |              2.388 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys by 13+ × ATS Robert Derby × ATS Braidon Burns × total over 42.5                                                       |    0.0674 |        14.83 |          0.0289 |              2.336 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels by 13+ × ATS Josh Addo-Carr × ATS Will Penisini × total over 42.5                                                              |    0.0641 |        15.59 |          0.0287 |              2.235 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 52.5                                                              |    0.0959 |        10.42 |          0.0446 |              2.153 |
| Gold Coast Titans v Dolphins                      | Dolphins by 13+ × ATS Tevita Naufahu × ATS Hamiso Tabuai-Fidow × total over 44.5                                                               |    0.0952 |        10.51 |          0.0443 |              2.149 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 43.5                                                   |    0.0966 |        10.35 |          0.0464 |              2.082 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Ali Leiataua × total over 41.5                                                   |    0.0911 |        10.98 |          0.044  |              2.072 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 44.5                                                                |    0.1374 |         7.28 |          0.0716 |              1.919 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani × total over 40.5                                                               |    0.1009 |         9.91 |          0.0529 |              1.906 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey × total over 44.5                                                             |    0.1054 |         9.49 |          0.0576 |              1.828 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × ATS Braidon Burns × total over 42.5                                                          |    0.1112 |         8.99 |          0.0621 |              1.791 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Will Penisini × total over 42.5                                                                 |    0.108  |         9.26 |          0.0623 |              1.733 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Hamiso Tabuai-Fidow × total over 44.5                                                                  |    0.1514 |         6.61 |          0.0894 |              1.694 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo × total over 43.5                                                      |    0.1648 |         6.07 |          0.0983 |              1.677 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Ali Leiataua × total over 41.5                                                      |    0.1603 |         6.24 |          0.0979 |              1.637 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 44.5                                                                   |    0.1988 |         5.03 |          0.1278 |              1.556 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × Deine Mariner 2+ tries                                                                                                  |    0.083  |        12.05 |          0.0549 |              1.512 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × total over 48.5                                                                                     |    0.1197 |         8.35 |          0.0805 |              1.487 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × ATS Josiah Karapani                                                                                 |    0.1326 |         7.54 |          0.0901 |              1.471 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × total over 50.5                                                                              |    0.1402 |         7.13 |          0.0955 |              1.469 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                                                                            |    0.0934 |        10.71 |          0.0637 |              1.466 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 52.5                                                                               |    0.1192 |         8.39 |          0.0825 |              1.445 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × Robert Derby 2+ tries                                                                                           |    0.0936 |        10.68 |          0.0655 |              1.429 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × match tries over 7.5                                                                                |    0.1546 |         6.47 |          0.1091 |              1.418 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos by 13+ × ATS Deine Mariner                                                                                                    |    0.1206 |         8.29 |          0.0855 |              1.411 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Cody Ramsey                                                                               |    0.1464 |         6.83 |          0.1039 |              1.409 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × total over 40.5                                                                                     |    0.1682 |         5.95 |          0.1201 |              1.401 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × total over 52.5                                                                                            |    0.1643 |         6.09 |          0.1174 |              1.399 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × ATS Braidon Burns                                                                            |    0.146  |         6.85 |          0.1043 |              1.399 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Will Penisini                                                                                   |    0.1442 |         6.93 |          0.1044 |              1.382 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × match tries over 7.5                                                                         |    0.1945 |         5.14 |          0.1408 |              1.381 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × Josh Addo-Carr 2+ tries                                                                                                  |    0.2026 |         4.94 |          0.1468 |              1.38  |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × total over 42.5                                                                              |    0.1944 |         5.14 |          0.1412 |              1.376 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 44.5                                                                               |    0.1727 |         5.79 |          0.1258 |              1.373 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × Sione Katoa 2+ tries                                                                                          |    0.1557 |         6.42 |          0.1136 |              1.371 |
| Gold Coast Titans v Dolphins                      | Dolphins win × Tevita Naufahu 2+ tries                                                                                                         |    0.1434 |         6.97 |          0.1055 |              1.359 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5                                                                          |    0.1846 |         5.42 |          0.1361 |              1.357 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 51.5                                                                             |    0.1661 |         6.02 |          0.1226 |              1.355 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Alex Johnston × total over 44.5                                                           |    0.0971 |        10.3  |          0.072  |              1.349 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Phillip Sami × total over 44.5                                                                         |    0.13   |         7.69 |          0.0967 |              1.345 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys by 13+ × ATS Robert Derby                                                                                             |    0.1484 |         6.74 |          0.1103 |              1.345 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Ronaldo Mulitalo                                                                        |    0.2232 |         4.48 |          0.1662 |              1.343 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos win × ATS Deine Mariner × ATS Connor Tracey × total over 40.5                                                                 |    0.0799 |        12.52 |          0.0597 |              1.337 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys win × ATS Robert Derby × ATS Xavier Savage × total over 42.5                                                          |    0.0983 |        10.18 |          0.0736 |              1.336 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte                                                                                              |    0.1342 |         7.45 |          0.1005 |              1.335 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × total over 50.5                                                                                     |    0.1778 |         5.62 |          0.1337 |              1.33  |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Ali Leiataua                                                                        |    0.2169 |         4.61 |          0.1634 |              1.328 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × ATS Hamiso Tabuai-Fidow                                                                                    |    0.2057 |         4.86 |          0.1553 |              1.325 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.2842 |         3.52 |          0.2146 |              1.324 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × total over 44.5                                                                                            |    0.2314 |         4.32 |          0.1752 |              1.321 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × total over 43.5                                                                             |    0.2359 |         4.24 |          0.1804 |              1.308 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × match tries over 7.5                                                                        |    0.2379 |         4.2  |          0.1818 |              1.308 |
| Gold Coast Titans v Dolphins                      | Dolphins win × ATS Tevita Naufahu × match tries over 7.5                                                                                       |    0.2454 |         4.08 |          0.1884 |              1.303 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Jeral Skelton × total over 44.5                                                                |    0.1934 |         5.17 |          0.1508 |              1.283 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks by 13+ × ATS Sione Katoa                                                                                            |    0.1844 |         5.42 |          0.1442 |              1.279 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × match tries over 7.5                                                                                |    0.2513 |         3.98 |          0.1967 |              1.278 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × total over 42.5                                                                                     |    0.2518 |         3.97 |          0.1974 |              1.275 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks win × ATS Sione Katoa × ATS Moses Leo × total over 43.5                                                             |    0.1059 |         9.45 |          0.083  |              1.275 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × total over 52.5                                                                                    |    0.2377 |         4.21 |          0.187  |              1.271 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels by 13+ × ATS Josh Addo-Carr                                                                                                    |    0.193  |         5.18 |          0.1523 |              1.267 |
| Gold Coast Titans v Dolphins                      | Dolphins by 13+ × ATS Tevita Naufahu                                                                                                           |    0.1911 |         5.23 |          0.1509 |              1.267 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels win × ATS Josh Addo-Carr × ATS Mathew Feagai × total over 42.5                                                                 |    0.1371 |         7.3  |          0.1093 |              1.254 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 49.5                                                                         |    0.1938 |         5.16 |          0.1566 |              1.238 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | Brisbane Broncos -0.5 × ATS Deine Mariner                                                                                                      |    0.2529 |         3.95 |          0.2045 |              1.237 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × total over 44.5                                                                                    |    0.3474 |         2.88 |          0.2833 |              1.226 |
| North Queensland Cowboys v Canberra Raiders       | North Queensland Cowboys -2.5 × ATS Robert Derby                                                                                               |    0.2635 |         3.79 |          0.2157 |              1.222 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.2608 |         3.83 |          0.2143 |              1.217 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 41.5                                                                         |    0.2839 |         3.52 |          0.2338 |              1.214 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.3225 |         3.1  |          0.2659 |              1.213 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.2747 |         3.64 |          0.2268 |              1.211 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.3698 |         2.7  |          0.3061 |              1.208 |
| South Sydney Rabbitohs v Sydney Roosters          | Sydney Roosters -0.5 × ATS Rex Bassingthwaighte                                                                                                |    0.2731 |         3.66 |          0.2268 |              1.204 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.209  |         4.78 |          0.1751 |              1.194 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Jason Saab × total over 41.5                                                        |    0.1485 |         6.74 |          0.1247 |              1.19  |
| Cronulla-Sutherland Sharks v Melbourne Storm      | Cronulla-Sutherland Sharks -2.5 × ATS Sione Katoa                                                                                              |    0.3281 |         3.05 |          0.2776 |              1.182 |
| Gold Coast Titans v Dolphins                      | Dolphins -3.5 × ATS Tevita Naufahu                                                                                                             |    0.3254 |         3.07 |          0.2765 |              1.177 |
| St George Illawarra Dragons v Parramatta Eels     | Parramatta Eels -1.5 × ATS Josh Addo-Carr                                                                                                      |    0.3808 |         2.63 |          0.3279 |              1.161 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.3269 |         3.06 |          0.2818 |              1.16  |
| New Zealand Warriors v Manly-Warringah Sea Eagles | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.4023 |         2.49 |          0.3537 |              1.137 |
| Penrith Panthers v Wests Tigers                   | Penrith Panthers -8.5 × ATS Thomas Jenkins                                                                                                     |    0.4061 |         2.46 |          0.3583 |              1.134 |
| St George Illawarra Dragons v Parramatta Eels     | ATS Josh Addo-Carr × ATS Mathew Feagai                                                                                                         |    0.3661 |         2.73 |          0.3643 |              1.005 |
| Gold Coast Titans v Dolphins                      | ATS Tevita Naufahu × ATS Phillip Sami                                                                                                          |    0.3066 |         3.26 |          0.3054 |              1.004 |
| South Sydney Rabbitohs v Sydney Roosters          | ATS Rex Bassingthwaighte × ATS Alex Johnston                                                                                                   |    0.2757 |         3.63 |          0.2747 |              1.004 |
| Canterbury-Bankstown Bulldogs v Brisbane Broncos  | ATS Deine Mariner × ATS Connor Tracey                                                                                                          |    0.2229 |         4.49 |          0.2224 |              1.002 |
| Cronulla-Sutherland Sharks v Melbourne Storm      | ATS Sione Katoa × ATS Moses Leo                                                                                                                |    0.2697 |         3.71 |          0.2695 |              1.001 |
| New Zealand Warriors v Manly-Warringah Sea Eagles | ATS Alofiana Khan-Pereira × ATS Jason Saab                                                                                                     |    0.407  |         2.46 |          0.4066 |              1.001 |
| Penrith Panthers v Wests Tigers                   | ATS Thomas Jenkins × ATS Jeral Skelton                                                                                                         |    0.3958 |         2.53 |          0.3961 |              0.999 |
| North Queensland Cowboys v Canberra Raiders       | ATS Robert Derby × ATS Xavier Savage                                                                                                           |    0.2403 |         4.16 |          0.2408 |              0.998 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round27.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._