# Phase 4 report — player props + SGM simulator

_Generated 2026-08-04. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                                    |   p_home_sim |   p_home_tier2 |    diff |
|:---------------------------------------------------------|-------------:|---------------:|--------:|
| Gold Coast Titans v North Queensland Cowboys             |       0.4911 |         0.4851 |  0.006  |
| New Zealand Warriors v Penrith Panthers                  |       0.4639 |         0.4652 | -0.0013 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          |       0.598  |         0.602  | -0.004  |
| Melbourne Storm v Manly-Warringah Sea Eagles             |       0.5106 |         0.512  | -0.0014 |
| Dolphins v Brisbane Broncos                              |       0.5957 |         0.5905 |  0.0052 |
| South Sydney Rabbitohs v Parramatta Eels                 |       0.5927 |         0.5936 | -0.0009 |
| Canberra Raiders v Newcastle Knights                     |       0.5339 |         0.533  |  0.001  |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks |       0.3952 |         0.3962 | -0.0011 |

Max |diff| = 0.0060 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 23 — top ATS props (model fair prices)

| match                                                    | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:---------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Gold Coast Titans v North Queensland Cowboys             | Gold Coast Titans             | AJ Brimson              | C          |        0.65 |   0.476 |         2.1  |     0.138 |          7.3 | 10t/15g  |
| Gold Coast Titans v North Queensland Cowboys             | Gold Coast Titans             | Jayden Campbell         | FE         |        0.64 |   0.475 |         2.11 |     0.136 |          7.3 | 4t/5g    |
| Gold Coast Titans v North Queensland Cowboys             | Gold Coast Titans             | Phillip Sami            | W          |        0.47 |   0.375 |         2.67 |     0.081 |         12.3 | 4t/12g   |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys      | Murray Taulagi          | W          |        0.72 |   0.513 |         1.95 |     0.163 |          6.1 | 8t/10g   |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys      | Braidon Burns           | W          |        0.53 |   0.41  |         2.44 |     0.098 |         10.2 | 3t/6g    |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys      | Zac Laybutt             | C          |        0.5  |   0.396 |         2.52 |     0.092 |         10.9 | 2t/2g    |
| New Zealand Warriors v Penrith Panthers                  | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        1    |   0.63  |         1.59 |     0.262 |          3.8 | 3t/3g    |
| New Zealand Warriors v Penrith Panthers                  | New Zealand Warriors          | Charnze Nicoll-Klokstad | FB         |        0.56 |   0.429 |         2.33 |     0.109 |          9.2 | 6t/11g   |
| New Zealand Warriors v Penrith Panthers                  | New Zealand Warriors          | Ali Leiataua            | C          |        0.45 |   0.362 |         2.76 |     0.075 |         13.3 | 1t/2g    |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers              | Brian To'o              | W          |        0.72 |   0.514 |         1.95 |     0.163 |          6.1 | 8t/10g   |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers              | Thomas Jenkins          | W          |        0.69 |   0.496 |         2.02 |     0.151 |          6.6 | 1t/3g    |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers              | Paul Alamoti            | C          |        0.47 |   0.376 |         2.66 |     0.082 |         12.2 | 3t/6g    |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters               | Mark Nawaqanitawase     | W          |        0.79 |   0.548 |         1.83 |     0.189 |          5.3 | 2t/2g    |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters               | James Tedesco           | FB         |        0.72 |   0.512 |         1.95 |     0.162 |          6.2 | 13t/14g  |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters               | Billy Smith             | W          |        0.49 |   0.388 |         2.58 |     0.088 |         11.4 | —        |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Canterbury-Bankstown Bulldogs | Matt Burton             | C          |        0.68 |   0.492 |         2.03 |     0.148 |          6.8 | 7t/8g    |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Canterbury-Bankstown Bulldogs | Stephen Crichton        | FE         |        0.45 |   0.364 |         2.75 |     0.076 |         13.1 | 5t/11g   |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Canterbury-Bankstown Bulldogs | Viliame Kikau           | 2R         |        0.44 |   0.359 |         2.79 |     0.074 |         13.5 | 6t/12g   |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Melbourne Storm               | Moses Leo               | W          |        0.71 |   0.506 |         1.98 |     0.158 |          6.3 | 0t/1g    |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.65 |   0.475 |         2.1  |     0.137 |          7.3 | 0t/1g    |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Melbourne Storm               | Siulagi Tuimalatu-Brown | W          |        0.61 |   0.456 |         2.19 |     0.125 |          8   | —        |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.82 |   0.559 |         1.79 |     0.198 |          5.1 | 7t/7g    |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles    | Toluta'u Koula          | C          |        0.72 |   0.515 |         1.94 |     0.164 |          6.1 | 5t/5g    |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles    | Blake Wilson            | W          |        0.53 |   0.41  |         2.44 |     0.098 |         10.2 | —        |
| Dolphins v Brisbane Broncos                              | Dolphins                      | Hamiso Tabuai-Fidow     | FB         |        0.66 |   0.485 |         2.06 |     0.143 |          7   | 5t/10g   |
| Dolphins v Brisbane Broncos                              | Dolphins                      | Herbie Farnworth        | C          |        0.64 |   0.471 |         2.12 |     0.134 |          7.5 | 2t/3g    |
| Dolphins v Brisbane Broncos                              | Dolphins                      | Selwyn Cobbo            | W          |        0.61 |   0.458 |         2.18 |     0.126 |          7.9 | 0t/1g    |
| Dolphins v Brisbane Broncos                              | Brisbane Broncos              | Kotoni Staggs           | C          |        0.62 |   0.463 |         2.16 |     0.129 |          7.7 | 6t/7g    |
| Dolphins v Brisbane Broncos                              | Brisbane Broncos              | Gehamat Shibasaki       | B          |        0.56 |   0.428 |         2.34 |     0.108 |          9.2 | 3t/3g    |
| Dolphins v Brisbane Broncos                              | Brisbane Broncos              | Reece Walsh             | FB         |        0.49 |   0.389 |         2.57 |     0.088 |         11.4 | 3t/5g    |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs        | Alex Johnston           | W          |        1.14 |   0.681 |         1.47 |     0.316 |          3.2 | 18t/16g  |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs        | Campbell Graham         | W          |        0.6  |   0.454 |         2.2  |     0.123 |          8.1 | 5t/8g    |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs        | Tallis Duncan           | C          |        0.44 |   0.358 |         2.79 |     0.074 |         13.6 | 2t/3g    |
| South Sydney Rabbitohs v Parramatta Eels                 | Parramatta Eels               | Josh Addo-Carr          | W          |        0.83 |   0.564 |         1.77 |     0.202 |          5   | 14t/15g  |
| South Sydney Rabbitohs v Parramatta Eels                 | Parramatta Eels               | Isaiah Iongi            | FB         |        0.48 |   0.38  |         2.63 |     0.084 |         12   | 1t/1g    |
| South Sydney Rabbitohs v Parramatta Eels                 | Parramatta Eels               | Jordan Samrani          | C          |        0.38 |   0.318 |         3.14 |     0.057 |         17.5 | —        |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders              | Kaeo Weekes             | FB         |        0.65 |   0.478 |         2.09 |     0.138 |          7.2 | 4t/6g    |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders              | Simi Sasagi             | C          |        0.61 |   0.455 |         2.2  |     0.124 |          8   | 3t/4g    |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders              | Xavier Savage           | W          |        0.53 |   0.414 |         2.42 |     0.101 |          9.9 | 3t/7g    |
| Canberra Raiders v Newcastle Knights                     | Newcastle Knights             | Greg Marzhew            | W          |        0.8  |   0.551 |         1.82 |     0.191 |          5.2 | 8t/8g    |
| Canberra Raiders v Newcastle Knights                     | Newcastle Knights             | Dominic Young           | W          |        0.68 |   0.492 |         2.03 |     0.148 |          6.7 | 7t/9g    |
| Canberra Raiders v Newcastle Knights                     | Newcastle Knights             | Fletcher Sharpe         | FE         |        0.43 |   0.347 |         2.88 |     0.069 |         14.5 | 1t/2g    |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | St George Illawarra Dragons   | Setu Tu                 | W          |        0.64 |   0.474 |         2.11 |     0.136 |          7.4 | 0t/1g    |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.63 |   0.467 |         2.14 |     0.131 |          7.6 | 5t/10g   |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | St George Illawarra Dragons   | Tyrell Sloan            | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 2t/8g    |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.7  |   0.503 |         1.99 |     0.155 |          6.4 | 7t/9g    |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.56 |   0.431 |         2.32 |     0.11  |          9.1 | 6t/9g    |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks    | Braydon Trindall        | FE         |        0.45 |   0.363 |         2.76 |     0.076 |         13.2 | 4t/7g    |

## Round 23 — SGM candidates (fair vs independence pricing)

| match                                                    | combo                                                                                                                                  |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:---------------------------------------------------------|:---------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × ATS Thomas Jenkins × ATS Paul Alamoti × total over 40.5 × match tries over 9.5                 |    0.04   |        25    |          0.0078 |              5.107 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × ATS Braidon Burns × ATS Zac Laybutt × total over 44.5 × match tries over 9.5       |    0.0393 |        25.43 |          0.0079 |              4.946 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Toluta'u Koula × ATS Blake Wilson × total over 42.5 × match tries over 9.5       |    0.049  |        20.39 |          0.01   |              4.885 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × ATS Simi Sasagi × ATS Xavier Savage × total over 42.5 × match tries over 9.5                  |    0.0424 |        23.57 |          0.0087 |              4.858 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa × ATS William Kennedy × total over 42.5 × match tries over 9.5 |    0.0347 |        28.79 |          0.0072 |              4.806 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS James Tedesco × ATS Billy Smith × total over 40.5 × match tries over 9.5           |    0.0485 |        20.62 |          0.0104 |              4.657 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Herbie Farnworth × ATS Selwyn Cobbo × total over 44.5 × match tries over 9.5              |    0.0533 |        18.75 |          0.0118 |              4.527 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × ATS Tallis Duncan × total over 44.5 × match tries over 9.5      |    0.0533 |        18.76 |          0.0124 |              4.284 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × Murray Taulagi 2+ tries × ATS Braidon Burns × total over 52.5                                           |    0.0354 |        28.26 |          0.0125 |              2.838 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × Brian To'o 2+ tries × ATS Thomas Jenkins × total over 48.5                                                      |    0.0445 |        22.46 |          0.016  |              2.781 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries × ATS Toluta'u Koula × total over 50.5                                            |    0.0511 |        19.56 |          0.0186 |              2.753 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × Kaeo Weekes 2+ tries × ATS Simi Sasagi × total over 50.5                                                        |    0.0348 |        28.77 |          0.0128 |              2.708 |
| Dolphins v Brisbane Broncos                              | Dolphins win × Hamiso Tabuai-Fidow 2+ tries × ATS Herbie Farnworth × total over 52.5                                                   |    0.0379 |        26.36 |          0.0144 |              2.631 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × Mark Nawaqanitawase 2+ tries × ATS James Tedesco × total over 48.5                                               |    0.0571 |        17.52 |          0.0219 |              2.611 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS Sione Katoa × total over 50.5                                         |    0.0392 |        25.52 |          0.0153 |              2.565 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Campbell Graham × total over 52.5                                            |    0.072  |        13.88 |          0.0305 |              2.358 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Murray Taulagi × ATS Braidon Burns × total over 44.5                                             |    0.061  |        16.4  |          0.0262 |              2.33  |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders by 13+ × ATS Kaeo Weekes × ATS Simi Sasagi × total over 42.5                                                          |    0.0692 |        14.45 |          0.0301 |              2.302 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers by 13+ × ATS Brian To'o × ATS Thomas Jenkins × total over 40.5                                                        |    0.0779 |        12.83 |          0.0341 |              2.284 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab × ATS Toluta'u Koula × total over 42.5                                              |    0.0765 |        13.07 |          0.0339 |              2.258 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS Sione Katoa × total over 42.5                                           |    0.0824 |        12.13 |          0.0368 |              2.237 |
| Dolphins v Brisbane Broncos                              | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow × ATS Herbie Farnworth × total over 44.5                                                     |    0.0821 |        12.18 |          0.0373 |              2.202 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters by 13+ × ATS Mark Nawaqanitawase × ATS James Tedesco × total over 40.5                                                 |    0.1042 |         9.6  |          0.0479 |              2.174 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Campbell Graham × total over 44.5                                              |    0.1027 |         9.73 |          0.0503 |              2.042 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × ATS Braidon Burns × total over 44.5                                                |    0.1058 |         9.45 |          0.0581 |              1.823 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Toluta'u Koula × total over 42.5                                                 |    0.1388 |         7.2  |          0.0779 |              1.782 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × ATS Simi Sasagi × total over 42.5                                                             |    0.1149 |         8.7  |          0.065  |              1.767 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × ATS Thomas Jenkins × total over 40.5                                                           |    0.1351 |         7.4  |          0.0766 |              1.764 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa × total over 42.5                                              |    0.1275 |         7.84 |          0.0729 |              1.749 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Herbie Farnworth × total over 44.5                                                        |    0.1274 |         7.85 |          0.074  |              1.721 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS James Tedesco × total over 40.5                                                    |    0.1642 |         6.09 |          0.0963 |              1.705 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham × total over 44.5                                                 |    0.1626 |         6.15 |          0.0998 |              1.629 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × Jason Saab 2+ tries                                                                                   |    0.1339 |         7.47 |          0.0922 |              1.452 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × total over 52.5                                                                    |    0.1353 |         7.39 |          0.094  |              1.439 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × total over 50.5                                                                               |    0.1397 |         7.16 |          0.0974 |              1.434 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 52.5                                                                               |    0.1493 |         6.7  |          0.1045 |              1.429 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × Murray Taulagi 2+ tries                                                                                 |    0.1141 |         8.77 |          0.0799 |              1.428 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 50.5                                                                |    0.1634 |         6.12 |          0.1146 |              1.426 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × total over 48.5                                                                                |    0.1464 |         6.83 |          0.1027 |              1.425 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × total over 48.5                                                                        |    0.1789 |         5.59 |          0.1256 |              1.424 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 50.5                                                                      |    0.1444 |         6.93 |          0.1018 |              1.418 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × ATS Braidon Burns                                                                  |    0.1443 |         6.93 |          0.1018 |              1.416 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × Brian To'o 2+ tries                                                                                             |    0.1178 |         8.49 |          0.0833 |              1.415 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Toluta'u Koula                                                                   |    0.1887 |         5.3  |          0.134  |              1.409 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × Kaeo Weekes 2+ tries                                                                                            |    0.0983 |        10.17 |          0.0698 |              1.408 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × ATS Thomas Jenkins                                                                             |    0.1805 |         5.54 |          0.1305 |              1.383 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × ATS Simi Sasagi                                                                               |    0.1516 |         6.6  |          0.1097 |              1.382 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × total over 44.5                                                                    |    0.1934 |         5.17 |          0.1412 |              1.37  |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × match tries over 7.5                                                                           |    0.1923 |         5.2  |          0.1405 |              1.368 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × match tries over 7.5                                                                 |    0.2056 |         4.86 |          0.151  |              1.361 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × match tries over 7.5                                                                   |    0.2341 |         4.27 |          0.1721 |              1.36  |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × match tries over 7.5                                                                          |    0.1935 |         5.17 |          0.1423 |              1.36  |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × total over 42.5                                                                               |    0.1937 |         5.16 |          0.1428 |              1.356 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × total over 44.5                                                                               |    0.2133 |         4.69 |          0.1574 |              1.356 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × total over 40.5                                                                                |    0.2099 |         4.76 |          0.1549 |              1.355 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × match tries over 7.5                                                               |    0.206  |         4.85 |          0.1522 |              1.354 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × Mark Nawaqanitawase 2+ tries                                                                                     |    0.1461 |         6.84 |          0.108  |              1.353 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Kotoni Staggs × total over 44.5                                                           |    0.0984 |        10.16 |          0.0728 |              1.352 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × total over 42.5                                                                      |    0.2046 |         4.89 |          0.1514 |              1.352 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers win × ATS Brian To'o × ATS Alofiana Khan-Pereira × total over 40.5                                                    |    0.1319 |         7.58 |          0.0977 |              1.35  |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                           |    0.2279 |         4.39 |          0.1694 |              1.345 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS Matt Burton × total over 40.5                                                      |    0.1241 |         8.06 |          0.0925 |              1.342 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Setu Tu × total over 42.5                                                  |    0.1074 |         9.31 |          0.08   |              1.342 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                             |    0.1206 |         8.29 |          0.0899 |              1.342 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 42.5                                                                |    0.2275 |         4.39 |          0.1697 |              1.341 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders win × ATS Kaeo Weekes × ATS Greg Marzhew × total over 42.5                                                            |    0.1053 |         9.49 |          0.0785 |              1.341 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys win × ATS Murray Taulagi × ATS AJ Brimson × total over 44.5                                                   |    0.0899 |        11.12 |          0.0671 |              1.34  |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × total over 40.5                                                                        |    0.2534 |         3.95 |          0.1894 |              1.338 |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders by 13+ × ATS Kaeo Weekes                                                                                              |    0.1491 |         6.71 |          0.1114 |              1.338 |
| Dolphins v Brisbane Broncos                              | Dolphins win × Hamiso Tabuai-Fidow 2+ tries                                                                                            |    0.1085 |         9.22 |          0.0811 |              1.337 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × match tries over 7.5                                                                          |    0.227  |         4.41 |          0.1699 |              1.336 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers by 13+ × ATS Brian To'o                                                                                               |    0.1572 |         6.36 |          0.1176 |              1.336 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa                                                                |    0.1661 |         6.02 |          0.1245 |              1.334 |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Murray Taulagi                                                                                   |    0.1485 |         6.73 |          0.1116 |              1.33  |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters win × ATS Mark Nawaqanitawase × ATS James Tedesco                                                                      |    0.2126 |         4.7  |          0.1604 |              1.325 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles win × ATS Jason Saab × ATS Moses Leo × total over 42.5                                                      |    0.1008 |         9.92 |          0.0763 |              1.322 |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles by 13+ × ATS Jason Saab                                                                                     |    0.1496 |         6.69 |          0.1133 |              1.321 |
| Dolphins v Brisbane Broncos                              | Dolphins win × ATS Hamiso Tabuai-Fidow × ATS Herbie Farnworth                                                                          |    0.1712 |         5.84 |          0.1301 |              1.317 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                    |    0.2328 |         4.3  |          0.1782 |              1.307 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × total over 52.5                                                                       |    0.1902 |         5.26 |          0.1456 |              1.306 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                               |    0.1899 |         5.27 |          0.1465 |              1.296 |
| Dolphins v Brisbane Broncos                              | Dolphins by 13+ × ATS Hamiso Tabuai-Fidow                                                                                              |    0.1793 |         5.58 |          0.1392 |              1.288 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters by 13+ × ATS Mark Nawaqanitawase                                                                                       |    0.2021 |         4.95 |          0.157  |              1.288 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Campbell Graham                                                                   |    0.2251 |         4.44 |          0.1752 |              1.285 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Josh Addo-Carr × total over 44.5                                                  |    0.1591 |         6.28 |          0.1246 |              1.277 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × total over 44.5                                                                       |    0.2782 |         3.59 |          0.2197 |              1.266 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                  |    0.296  |         3.38 |          0.2367 |              1.251 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                      |    0.2373 |         4.21 |          0.1945 |              1.22  |
| Canberra Raiders v Newcastle Knights                     | Canberra Raiders -2.5 × ATS Kaeo Weekes                                                                                                |    0.2649 |         3.78 |          0.2182 |              1.214 |
| New Zealand Warriors v Penrith Panthers                  | Penrith Panthers -2.5 × ATS Brian To'o                                                                                                 |    0.2901 |         3.45 |          0.239  |              1.213 |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | Cronulla-Sutherland Sharks -4.5 × ATS Ronaldo Mulitalo                                                                                 |    0.2907 |         3.44 |          0.2423 |              1.2   |
| Melbourne Storm v Manly-Warringah Sea Eagles             | Manly-Warringah Sea Eagles -0.5 × ATS Jason Saab                                                                                       |    0.3124 |         3.2  |          0.2603 |              1.2   |
| Gold Coast Titans v North Queensland Cowboys             | North Queensland Cowboys -0.5 × ATS Murray Taulagi                                                                                     |    0.2974 |         3.36 |          0.2477 |              1.2   |
| Dolphins v Brisbane Broncos                              | Dolphins -4.5 × ATS Hamiso Tabuai-Fidow                                                                                                |    0.2769 |         3.61 |          0.2308 |              1.2   |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | Sydney Roosters -4.5 × ATS Mark Nawaqanitawase                                                                                         |    0.3131 |         3.19 |          0.2616 |              1.197 |
| South Sydney Rabbitohs v Parramatta Eels                 | South Sydney Rabbitohs -4.5 × ATS Alex Johnston                                                                                        |    0.3717 |         2.69 |          0.3216 |              1.155 |
| New Zealand Warriors v Penrith Panthers                  | ATS Brian To'o × ATS Alofiana Khan-Pereira                                                                                             |    0.3275 |         3.05 |          0.3262 |              1.004 |
| Gold Coast Titans v North Queensland Cowboys             | ATS Murray Taulagi × ATS AJ Brimson                                                                                                    |    0.2433 |         4.11 |          0.2426 |              1.003 |
| Sydney Roosters v Canterbury-Bankstown Bulldogs          | ATS Mark Nawaqanitawase × ATS Matt Burton                                                                                              |    0.2697 |         3.71 |          0.269  |              1.002 |
| South Sydney Rabbitohs v Parramatta Eels                 | ATS Alex Johnston × ATS Josh Addo-Carr                                                                                                 |    0.385  |         2.6  |          0.3846 |              1.001 |
| Canberra Raiders v Newcastle Knights                     | ATS Kaeo Weekes × ATS Greg Marzhew                                                                                                     |    0.2601 |         3.84 |          0.2602 |              1     |
| Melbourne Storm v Manly-Warringah Sea Eagles             | ATS Jason Saab × ATS Moses Leo                                                                                                         |    0.282  |         3.55 |          0.2821 |              1     |
| St George Illawarra Dragons v Cronulla-Sutherland Sharks | ATS Ronaldo Mulitalo × ATS Setu Tu                                                                                                     |    0.2352 |         4.25 |          0.2353 |              0.999 |
| Dolphins v Brisbane Broncos                              | ATS Hamiso Tabuai-Fidow × ATS Kotoni Staggs                                                                                            |    0.2231 |         4.48 |          0.2236 |              0.997 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round23.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._