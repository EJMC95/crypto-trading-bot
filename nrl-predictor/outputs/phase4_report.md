# Phase 4 report — player props + SGM simulator

_Generated 2026-08-11. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| Penrith Panthers v Sydney Roosters                     |       0.5924 |         0.6035 | -0.0111 |
| Manly-Warringah Sea Eagles v Dolphins                  |       0.5254 |         0.5231 |  0.0023 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs |       0.4849 |         0.4822 |  0.0027 |
| Cronulla-Sutherland Sharks v Canberra Raiders          |       0.5925 |         0.5886 |  0.0039 |
| Parramatta Eels v North Queensland Cowboys             |       0.5026 |         0.4989 |  0.0037 |
| Brisbane Broncos v New Zealand Warriors                |       0.466  |         0.4663 | -0.0003 |
| Newcastle Knights v Gold Coast Titans                  |       0.5573 |         0.5548 |  0.0025 |
| Wests Tigers v St George Illawarra Dragons             |       0.572  |         0.5704 |  0.0016 |

Max |diff| = 0.0111 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 24 — top ATS props (model fair prices)

| match                                                  | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:-------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Thomas Jenkins          | W          |        1.22 |   0.705 |         1.42 |     0.345 |          2.9 | 4t/2g    |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Brian To'o              | W          |        0.65 |   0.479 |         2.09 |     0.139 |          7.2 | 8t/13g   |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers              | Paul Alamoti            | C          |        0.55 |   0.424 |         2.36 |     0.106 |          9.4 | 3t/5g    |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Mark Nawaqanitawase     | W          |        0.7  |   0.501 |         2    |     0.154 |          6.5 | 1t/3g    |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Billy Smith             | W          |        0.57 |   0.433 |         2.31 |     0.111 |          9   | —        |
| Penrith Panthers v Sydney Roosters                     | Sydney Roosters               | Robert Toia             | C          |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 2t/3g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.77 |   0.539 |         1.85 |     0.182 |          5.5 | 4t/2g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Toluta'u Koula          | C          |        0.62 |   0.465 |         2.15 |     0.13  |          7.7 | 5t/4g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles    | Reuben Garrick          | C          |        0.57 |   0.435 |         2.3  |     0.112 |          8.9 | 4t/3g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Selwyn Cobbo            | W          |        0.71 |   0.506 |         1.98 |     0.158 |          6.3 | 6t/5g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Hamiso Tabuai-Fidow     | FB         |        0.61 |   0.456 |         2.19 |     0.125 |          8   | 6t/7g    |
| Manly-Warringah Sea Eagles v Dolphins                  | Dolphins                      | Jamayne Isaako          | W          |        0.47 |   0.378 |         2.65 |     0.083 |         12.1 | 5t/9g    |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Stephen Crichton        | FE         |        0.71 |   0.51  |         1.96 |     0.161 |          6.2 | 11t/14g  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Matt Burton             | C          |        0.52 |   0.408 |         2.45 |     0.098 |         10.3 | 7t/12g   |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | Canterbury-Bankstown Bulldogs | Connor Tracey           | FB         |        0.49 |   0.386 |         2.59 |     0.087 |         11.5 | 5t/9g    |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.97 |   0.622 |         1.61 |     0.254 |          3.9 | 18t/20g  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Jack Wighton            | C          |        0.47 |   0.378 |         2.65 |     0.083 |         12.1 | 6t/12g   |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs        | Campbell Graham         | W          |        0.47 |   0.378 |         2.65 |     0.082 |         12.1 | 5t/12g   |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.65 |   0.48  |         2.08 |     0.14  |          7.1 | 10t/13g  |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.55 |   0.424 |         2.36 |     0.106 |          9.4 | 3t/4g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.51 |   0.399 |         2.51 |     0.093 |         10.8 | 8t/13g   |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Savelio Tamale          | C          |        0.59 |   0.446 |         2.24 |     0.119 |          8.4 | 2t/3g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Xavier Savage           | W          |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | 3t/6g    |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Canberra Raiders              | Kaeo Weekes             | FB         |        0.41 |   0.334 |         2.99 |     0.063 |         15.8 | 1t/4g    |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Josh Addo-Carr          | W          |        1.08 |   0.659 |         1.52 |     0.292 |          3.4 | 15t/13g  |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Jordan Samrani          | C          |        0.52 |   0.407 |         2.46 |     0.097 |         10.3 | 1t/1g    |
| Parramatta Eels v North Queensland Cowboys             | Parramatta Eels               | Brian Kelly             | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 8t/16g   |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Jaxon Purdue            | HB         |        0.66 |   0.484 |         2.06 |     0.143 |          7   | 3t/2g    |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Tom Chester             | C          |        0.54 |   0.418 |         2.39 |     0.103 |          9.7 | 2t/2g    |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys      | Murray Taulagi          | W          |        0.52 |   0.403 |         2.48 |     0.095 |         10.5 | 1t/4g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Deine Mariner           | C          |        0.83 |   0.563 |         1.77 |     0.202 |          5   | 4t/2g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Grant Anderson          | W          |        0.44 |   0.357 |         2.8  |     0.073 |         13.7 | 2t/3g    |
| Brisbane Broncos v New Zealand Warriors                | Brisbane Broncos              | Josiah Karapani         | W          |        0.43 |   0.347 |         2.88 |     0.069 |         14.6 | 1t/3g    |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.99 |   0.627 |         1.59 |     0.259 |          3.9 | 7t/6g    |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.76 |   0.532 |         1.88 |     0.176 |          5.7 | 9t/12g   |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors          | Ali Leiataua            | C          |        0.39 |   0.322 |         3.1  |     0.059 |         17.1 | 1t/2g    |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Dominic Young           | W          |        1.09 |   0.663 |         1.51 |     0.297 |          3.4 | 11t/6g   |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Fletcher Sharpe         | FE         |        0.75 |   0.529 |         1.89 |     0.174 |          5.7 | 6t/4g    |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights             | Kalyn Ponga             | FB         |        0.46 |   0.372 |         2.69 |     0.08  |         12.6 | 8t/12g   |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | Phillip Sami            | W          |        0.74 |   0.523 |         1.91 |     0.17  |          5.9 | 8t/10g   |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | AJ Brimson              | C          |        0.65 |   0.476 |         2.1  |     0.137 |          7.3 | 8t/10g   |
| Newcastle Knights v Gold Coast Titans                  | Gold Coast Titans             | Dean Ieremia            | W          |        0.48 |   0.379 |         2.64 |     0.083 |         12   | 0t/1g    |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Junior Tupou            | W          |        0.89 |   0.589 |         1.7  |     0.224 |          4.5 | 3t/3g    |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Sunia Turuva            | W          |        0.63 |   0.468 |         2.14 |     0.132 |          7.6 | 2t/4g    |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers                  | Jahream Bula            | FB         |        0.47 |   0.375 |         2.66 |     0.081 |         12.3 | 1t/5g    |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Valentine Holmes        | C          |        0.76 |   0.532 |         1.88 |     0.177 |          5.7 | 13t/14g  |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Setu Tu                 | W          |        0.55 |   0.422 |         2.37 |     0.105 |          9.5 | —        |
| Wests Tigers v St George Illawarra Dragons             | St George Illawarra Dragons   | Clinton Gutherson       | FB         |        0.48 |   0.379 |         2.64 |     0.083 |         12   | 10t/18g  |

## Round 24 — SGM candidates (fair vs independence pricing)

| match                                                  | combo                                                                                                                                          |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:-------------------------------------------------------|:-----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Ali Leiataua × total over 42.5 × match tries over 9.5 |    0.0447 |        22.36 |          0.0087 |              5.161 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Jack Wighton × ATS Campbell Graham × total over 40.5 × match tries over 9.5               |    0.0365 |        27.43 |          0.0073 |              5.012 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × ATS Murray Taulagi × ATS Braidon Burns × total over 44.5 × match tries over 9.5               |    0.0328 |        30.53 |          0.0066 |              4.936 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × ATS Reuben Garrick × total over 44.5 × match tries over 9.5           |    0.0508 |        19.67 |          0.0104 |              4.904 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × ATS Sione Katoa × total over 42.5 × match tries over 9.5                  |    0.0392 |        25.48 |          0.0081 |              4.872 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Kalyn Ponga × ATS Greg Marzhew × total over 42.5 × match tries over 9.5                        |    0.0403 |        24.8  |          0.0087 |              4.661 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × ATS Sunia Turuva × ATS Jahream Bula × total over 42.5 × match tries over 9.5                             |    0.0468 |        21.37 |          0.0102 |              4.573 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Paul Alamoti × total over 42.5 × match tries over 9.5                         |    0.0629 |        15.89 |          0.0139 |              4.517 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × Tom Chester 2+ tries × ATS Murray Taulagi × total over 52.5                                                     |    0.0229 |        43.67 |          0.0076 |              2.994 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries × ATS Toluta'u Koula × total over 52.5                                                  |    0.044  |        22.72 |          0.0158 |              2.791 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Jack Wighton × total over 48.5                                                       |    0.0512 |        19.55 |          0.0189 |              2.708 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS KL Iro × total over 50.5                                                      |    0.034  |        29.39 |          0.0127 |              2.678 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                      |    0.0671 |        14.91 |          0.0258 |              2.596 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × Dominic Young 2+ tries × ATS Kalyn Ponga × total over 50.5                                                             |    0.0586 |        17.07 |          0.0226 |              2.59  |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × Junior Tupou 2+ tries × ATS Sunia Turuva × total over 50.5                                                                  |    0.0575 |        17.39 |          0.0223 |              2.578 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Tom Chester × ATS Murray Taulagi × total over 44.5                                                       |    0.051  |        19.59 |          0.0206 |              2.483 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 50.5                                                              |    0.0829 |        12.06 |          0.035  |              2.368 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Jack Wighton × total over 40.5                                                         |    0.0697 |        14.35 |          0.0303 |              2.303 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                        |    0.0746 |        13.41 |          0.0326 |              2.287 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 44.5                                                    |    0.0742 |        13.48 |          0.0328 |              2.262 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                        |    0.0947 |        10.56 |          0.0431 |              2.197 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights by 13+ × ATS Dominic Young × ATS Kalyn Ponga × total over 42.5                                                               |    0.0785 |        12.75 |          0.0359 |              2.185 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers by 13+ × ATS Junior Tupou × ATS Sunia Turuva × total over 42.5                                                                    |    0.0901 |        11.09 |          0.0421 |              2.142 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                |    0.1101 |         9.09 |          0.0537 |              2.05  |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × ATS Murray Taulagi × total over 44.5                                                          |    0.0855 |        11.69 |          0.0457 |              1.873 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 44.5                                                       |    0.1267 |         7.9  |          0.0707 |              1.79  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Jack Wighton × total over 40.5                                                            |    0.1218 |         8.21 |          0.0687 |              1.772 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                           |    0.1152 |         8.68 |          0.0659 |              1.748 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Kalyn Ponga × total over 42.5                                                                  |    0.1307 |         7.65 |          0.0758 |              1.724 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                           |    0.1615 |         6.19 |          0.0942 |              1.714 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × ATS Sunia Turuva × total over 42.5                                                                       |    0.148  |         6.76 |          0.0877 |              1.687 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 42.5                                                                   |    0.1752 |         5.71 |          0.108  |              1.622 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × total over 52.5                                                                               |    0.1151 |         8.69 |          0.0768 |              1.498 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × Tom Chester 2+ tries                                                                                            |    0.0729 |        13.72 |          0.0493 |              1.477 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 50.5                                                                        |    0.1496 |         6.68 |          0.1044 |              1.433 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × ATS Murray Taulagi                                                                            |    0.1127 |         8.88 |          0.0789 |              1.429 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 52.5                                                                            |    0.1414 |         7.07 |          0.1001 |              1.411 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                            |    0.177  |         5.65 |          0.1255 |              1.411 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × total over 44.5                                                                               |    0.1614 |         6.19 |          0.1145 |              1.41  |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Jack Wighton                                                                              |    0.1607 |         6.22 |          0.1144 |              1.404 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries                                                                                         |    0.127  |         7.87 |          0.0908 |              1.399 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × ATS Josh Addo-Carr × total over 44.5                                                          |    0.1059 |         9.44 |          0.0758 |              1.397 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys win × ATS Tom Chester × match tries over 7.5                                                                          |    0.1721 |         5.81 |          0.1236 |              1.392 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                      |    0.1848 |         5.41 |          0.1335 |              1.385 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula                                                                         |    0.1741 |         5.75 |          0.1259 |              1.382 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × total over 50.5                                                                                          |    0.1735 |         5.77 |          0.1263 |              1.374 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys by 13+ × ATS Tom Chester                                                                                              |    0.1216 |         8.22 |          0.089  |              1.367 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × total over 48.5                                                                               |    0.1671 |         5.98 |          0.1224 |              1.365 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                         |    0.1591 |         6.29 |          0.1166 |              1.365 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                             |    0.2311 |         4.33 |          0.1697 |              1.362 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Savelio Tamale × total over 42.5                                                   |    0.095  |        10.53 |          0.0697 |              1.362 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                                     |    0.1073 |         9.32 |          0.0789 |              1.36  |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × Junior Tupou 2+ tries                                                                                                       |    0.1661 |         6.02 |          0.1223 |              1.358 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × Dominic Young 2+ tries                                                                                                 |    0.211  |         4.74 |          0.1558 |              1.355 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                                   |    0.2114 |         4.73 |          0.1562 |              1.353 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 42.5                                                                        |    0.2118 |         4.72 |          0.1565 |              1.353 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 44.5                                                                            |    0.2042 |         4.9  |          0.1514 |              1.349 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × total over 50.5                                                                                    |    0.184  |         5.44 |          0.1374 |              1.339 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Kalyn Ponga                                                                                    |    0.1747 |         5.72 |          0.131  |              1.334 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro                                                                             |    0.1534 |         6.52 |          0.115  |              1.334 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Selwyn Cobbo × total over 44.5                                                         |    0.103  |         9.71 |          0.0774 |              1.332 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × match tries over 7.5                                                                       |    0.2181 |         4.59 |          0.1637 |              1.332 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × ATS Sunia Turuva                                                                                         |    0.1995 |         5.01 |          0.1511 |              1.32  |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate                                                                                           |    0.1647 |         6.07 |          0.125  |              1.318 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                          |    0.2194 |         4.56 |          0.1665 |              1.317 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Deine Mariner × total over 42.5                                                     |    0.1307 |         7.65 |          0.0994 |              1.315 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                         |    0.2327 |         4.3  |          0.1775 |              1.311 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                    |    0.232  |         4.31 |          0.1769 |              1.311 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × total over 40.5                                                                               |    0.2393 |         4.18 |          0.1831 |              1.307 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                                       |    0.1765 |         5.66 |          0.1352 |              1.306 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × ATS Valentine Holmes × total over 42.5                                                                   |    0.1296 |         7.72 |          0.0993 |              1.306 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × match tries over 7.5                                                                                     |    0.2446 |         4.09 |          0.1874 |              1.305 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × total over 50.5                                                                                    |    0.1982 |         5.04 |          0.152  |              1.304 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers win × ATS Junior Tupou × total over 42.5                                                                                          |    0.2448 |         4.09 |          0.1877 |              1.304 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                 |    0.2524 |         3.96 |          0.194  |              1.301 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                     |    0.2459 |         4.07 |          0.1904 |              1.292 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                              |    0.1731 |         5.78 |          0.1343 |              1.289 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × total over 42.5                                                                                    |    0.2618 |         3.82 |          0.2038 |              1.285 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × match tries over 7.5                                                                               |    0.2612 |         3.83 |          0.2035 |              1.284 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                        |    0.1869 |         5.35 |          0.1464 |              1.277 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers by 13+ × ATS Junior Tupou                                                                                                         |    0.1973 |         5.07 |          0.1552 |              1.271 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights win × ATS Dominic Young × ATS Phillip Sami × total over 42.5                                                                 |    0.136  |         7.36 |          0.1072 |              1.269 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × ATS Mark Nawaqanitawase × total over 42.5                                                          |    0.143  |         6.99 |          0.1138 |              1.256 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                               |    0.2842 |         3.52 |          0.2267 |              1.254 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers win × ATS Thomas Jenkins × total over 42.5                                                                                    |    0.2842 |         3.52 |          0.2272 |              1.251 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights by 13+ × ATS Dominic Young                                                                                                   |    0.2072 |         4.83 |          0.1667 |              1.243 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Matt Burton × total over 40.5                                                             |    0.0909 |        11.01 |          0.0742 |              1.224 |
| Parramatta Eels v North Queensland Cowboys             | North Queensland Cowboys -0.5 × ATS Tom Chester                                                                                                |    0.2418 |         4.14 |          0.1977 |              1.223 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                   |    0.2417 |         4.14 |          0.1991 |              1.214 |
| Cronulla-Sutherland Sharks v Canberra Raiders          | Cronulla-Sutherland Sharks -4.5 × ATS Ronaldo Mulitalo                                                                                         |    0.2733 |         3.66 |          0.2262 |              1.208 |
| Brisbane Broncos v New Zealand Warriors                | New Zealand Warriors -2.5 × ATS Alofiana Khan-Pereira                                                                                          |    0.344  |         2.91 |          0.2896 |              1.188 |
| Manly-Warringah Sea Eagles v Dolphins                  | Manly-Warringah Sea Eagles -1.5 × ATS Lehi Hopoate                                                                                             |    0.3176 |         3.15 |          0.2675 |              1.187 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | South Sydney Rabbitohs -0.5 × ATS Alex Johnston                                                                                                |    0.3591 |         2.79 |          0.3049 |              1.178 |
| Wests Tigers v St George Illawarra Dragons             | Wests Tigers -2.5 × ATS Junior Tupou                                                                                                           |    0.3462 |         2.89 |          0.2952 |              1.173 |
| Newcastle Knights v Gold Coast Titans                  | Newcastle Knights -2.5 × ATS Dominic Young                                                                                                     |    0.3734 |         2.68 |          0.3208 |              1.164 |
| Penrith Panthers v Sydney Roosters                     | Penrith Panthers -4.5 × ATS Thomas Jenkins                                                                                                     |    0.3847 |         2.6  |          0.334  |              1.152 |
| Brisbane Broncos v New Zealand Warriors                | ATS Alofiana Khan-Pereira × ATS Deine Mariner                                                                                                  |    0.3527 |         2.84 |          0.3517 |              1.003 |
| Manly-Warringah Sea Eagles v Dolphins                  | ATS Lehi Hopoate × ATS Selwyn Cobbo                                                                                                            |    0.2751 |         3.64 |          0.2745 |              1.002 |
| Wests Tigers v St George Illawarra Dragons             | ATS Junior Tupou × ATS Valentine Holmes                                                                                                        |    0.3123 |         3.2  |          0.3124 |              1     |
| Cronulla-Sutherland Sharks v Canberra Raiders          | ATS Ronaldo Mulitalo × ATS Savelio Tamale                                                                                                      |    0.2139 |         4.67 |          0.214  |              1     |
| Newcastle Knights v Gold Coast Titans                  | ATS Dominic Young × ATS Phillip Sami                                                                                                           |    0.3474 |         2.88 |          0.3476 |              0.999 |
| Penrith Panthers v Sydney Roosters                     | ATS Thomas Jenkins × ATS Mark Nawaqanitawase                                                                                                   |    0.352  |         2.84 |          0.3529 |              0.998 |
| Parramatta Eels v North Queensland Cowboys             | ATS Tom Chester × ATS Josh Addo-Carr                                                                                                           |    0.2748 |         3.64 |          0.2762 |              0.995 |
| Canterbury-Bankstown Bulldogs v South Sydney Rabbitohs | ATS Alex Johnston × ATS Matt Burton                                                                                                            |    0.2501 |         4    |          0.2522 |              0.992 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round24.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._