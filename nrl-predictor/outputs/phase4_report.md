# Phase 4 report — player props + SGM simulator

_Generated 2026-07-13. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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

| match                                              |   p_home_sim |   p_home_tier2 |    diff |
|:---------------------------------------------------|-------------:|---------------:|--------:|
| Penrith Panthers v Brisbane Broncos                |       0.652  |         0.6549 | -0.0029 |
| Cronulla-Sutherland Sharks v Newcastle Knights     |       0.5945 |         0.5918 |  0.0027 |
| Sydney Roosters v Melbourne Storm                  |       0.5478 |         0.5482 | -0.0004 |
| Canberra Raiders v South Sydney Rabbitohs          |       0.4928 |         0.4906 |  0.0022 |
| New Zealand Warriors v St George Illawarra Dragons |       0.6674 |         0.6665 |  0.0009 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       |       0.5608 |         0.565  | -0.0042 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     |       0.4333 |         0.4356 | -0.0023 |
| Dolphins v North Queensland Cowboys                |       0.5934 |         0.5956 | -0.0022 |

Max |diff| = 0.0042 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 20 — top ATS props (model fair prices)

| match                                              | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:---------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Thomas Jenkins          | W          |        1.06 |   0.653 |         1.53 |     0.286 |          3.5 | 4t/2g    |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Brian To'o              | W          |        0.52 |   0.405 |         2.47 |     0.096 |         10.4 | 6t/11g   |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers              | Casey McLean            | C          |        0.44 |   0.357 |         2.8  |     0.073 |         13.7 | 1t/2g    |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Grant Anderson          | C          |        0.51 |   0.399 |         2.51 |     0.093 |         10.7 | 2t/3g    |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Antonio Verhoeven       | C          |        0.39 |   0.323 |         3.1  |     0.059 |         17   | —        |
| Penrith Panthers v Brisbane Broncos                | Brisbane Broncos              | Ezra Mam                | B          |        0.38 |   0.318 |         3.15 |     0.057 |         17.6 | 3t/7g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.9  |   0.595 |         1.68 |     0.229 |          4.4 | 8t/9g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.53 |   0.409 |         2.45 |     0.098 |         10.2 | 0t/1g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks    | Jesse Ramien            | C          |        0.52 |   0.406 |         2.46 |     0.097 |         10.4 | 6t/11g   |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Dominic Young           | W          |        0.79 |   0.547 |         1.83 |     0.188 |          5.3 | 6t/7g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Greg Marzhew            | W          |        0.79 |   0.544 |         1.84 |     0.186 |          5.4 | 5t/6g    |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.48 |   0.381 |         2.62 |     0.084 |         11.9 | 1t/2g    |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Tommy Talau             | W          |        0.79 |   0.544 |         1.84 |     0.186 |          5.4 | 3t/2g    |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.62 |   0.46  |         2.17 |     0.127 |          7.9 | —        |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters               | Cody Ramsey             | FB         |        0.45 |   0.359 |         2.78 |     0.074 |         13.5 | 1t/3g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Moses Leo               | W          |        0.72 |   0.511 |         1.96 |     0.161 |          6.2 | 1t/1g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.59 |   0.444 |         2.25 |     0.117 |          8.5 | 1t/2g    |
| Sydney Roosters v Melbourne Storm                  | Melbourne Storm               | Jahrome Hughes          | HB         |        0.51 |   0.401 |         2.5  |     0.094 |         10.7 | 10t/18g  |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Xavier Savage           | W          |        0.68 |   0.492 |         2.03 |     0.148 |          6.8 | 2t/3g    |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Kaeo Weekes             | FB         |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | 2t/4g    |
| Canberra Raiders v South Sydney Rabbitohs          | Canberra Raiders              | Sebastian Kris          | C          |        0.48 |   0.379 |         2.64 |     0.083 |         12   | 3t/7g    |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Alex Johnston           | W          |        0.86 |   0.577 |         1.73 |     0.213 |          4.7 | 11t/14g  |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.49 |   0.39  |         2.57 |     0.088 |         11.3 | —        |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs        | Cody Walker             | FE         |        0.46 |   0.37  |         2.7  |     0.079 |         12.7 | 7t/13g   |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.89 |   0.59  |         1.69 |     0.225 |          4.4 | 4t/5g    |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.72 |   0.516 |         1.94 |     0.164 |          6.1 | 9t/15g   |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors          | Charnze Nicoll-Klokstad | B          |        0.5  |   0.394 |         2.54 |     0.09  |         11.1 | 5t/10g   |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Setu Tu                 | W          |        0.6  |   0.453 |         2.21 |     0.123 |          8.1 | 1t/1g    |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Mathew Feagai           | W          |        0.5  |   0.395 |         2.53 |     0.091 |         11   | 2t/3g    |
| New Zealand Warriors v St George Illawarra Dragons | St George Illawarra Dragons   | Clinton Gutherson       | FB         |        0.41 |   0.338 |         2.96 |     0.065 |         15.4 | 6t/12g   |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.77 |   0.538 |         1.86 |     0.181 |          5.5 | 4t/6g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Enari Tuala             | W          |        0.63 |   0.466 |         2.15 |     0.131 |          7.6 | 6t/11g   |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs | Stephen Crichton        | C          |        0.44 |   0.354 |         2.82 |     0.072 |         13.9 | 3t/8g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Jahream Bula            | FB         |        0.63 |   0.468 |         2.14 |     0.132 |          7.6 | 2t/3g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Taylan May              | C          |        0.6  |   0.454 |         2.2  |     0.123 |          8.1 | 2t/4g    |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Wests Tigers                  | Patrick Herbert         | W          |        0.48 |   0.379 |         2.64 |     0.083 |         12   | 1t/1g    |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | AJ Brimson              | C          |        0.6  |   0.449 |         2.23 |     0.121 |          8.3 | 8t/11g   |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | Phillip Sami            | W          |        0.54 |   0.416 |         2.41 |     0.102 |          9.8 | 5t/10g   |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Gold Coast Titans             | Jaylan De Groot         | C          |        0.37 |   0.312 |         3.21 |     0.055 |         18.3 | 0t/1g    |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Reuben Garrick          | C          |        0.71 |   0.507 |         1.97 |     0.158 |          6.3 | 12t/11g  |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.56 |   0.431 |         2.32 |     0.11  |          9.1 | 1t/1g    |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.54 |   0.419 |         2.39 |     0.103 |          9.7 | 7t/10g   |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Jamayne Isaako          | W          |        0.78 |   0.54  |         1.85 |     0.183 |          5.5 | 13t/16g  |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Jack Bostock            | C          |        0.73 |   0.518 |         1.93 |     0.166 |          6   | 5t/5g    |
| Dolphins v North Queensland Cowboys                | Dolphins                      | Tevita Naufahu          | W          |        0.53 |   0.41  |         2.44 |     0.099 |         10.1 | 0t/1g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Murray Taulagi          | W          |        0.9  |   0.592 |         1.69 |     0.227 |          4.4 | 6t/5g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Zac Laybutt             | W          |        0.54 |   0.419 |         2.39 |     0.103 |          9.7 | 4t/5g    |
| Dolphins v North Queensland Cowboys                | North Queensland Cowboys      | Tom Chester             | C          |        0.53 |   0.413 |         2.42 |     0.1   |         10   | 2t/2g    |

## Round 20 — SGM candidates (fair vs independence pricing)

| match                                              | combo                                                                                                                                         |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:---------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × ATS Latrell Siegwalt × total over 42.5 × match tries over 9.5              |    0.0256 |        39.12 |          0.0048 |              5.304 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × ATS Lehi Hopoate × ATS Jason Saab × total over 41.5 × match tries over 9.5              |    0.0409 |        24.46 |          0.0082 |              4.963 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala × ATS Stephen Crichton × total over 42.5 × match tries over 9.5         |    0.0405 |        24.67 |          0.0082 |              4.936 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × ATS Casey McLean × total over 40.5 × match tries over 9.5                        |    0.0438 |        22.85 |          0.0091 |              4.827 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × ATS Rex Bassingthwaighte × ATS Cody Ramsey × total over 42.5 × match tries over 9.5                   |    0.0429 |        23.29 |          0.0091 |              4.698 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × ATS Jack Bostock × ATS Tevita Naufahu × total over 45.5 × match tries over 10.5                           |    0.048  |        20.82 |          0.0104 |              4.639 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × ATS Adam Pompey × total over 42.5 × match tries over 9.5 |    0.0505 |        19.81 |          0.011  |              4.609 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × ATS Jesse Ramien × total over 42.5 × match tries over 9.5                |    0.0476 |        21.03 |          0.0105 |              4.549 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Edward Kosi × total over 50.5                                                       |    0.0434 |        23.02 |          0.0154 |              2.823 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × Reuben Garrick 2+ tries × ATS Lehi Hopoate × total over 49.5                                                 |    0.0398 |        25.13 |          0.0147 |              2.705 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × Tommy Talau 2+ tries × ATS Rex Bassingthwaighte × total over 50.5                                                       |    0.0475 |        21.07 |          0.018  |              2.636 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × Jacob Kiraz 2+ tries × ATS Enari Tuala × total over 50.5                                                  |    0.0454 |        22.05 |          0.0172 |              2.63  |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS KL Iro × total over 50.5                                                     |    0.0524 |        19.09 |          0.0209 |              2.509 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Brian To'o × total over 48.5                                                             |    0.0688 |        14.53 |          0.0279 |              2.469 |
| Dolphins v North Queensland Cowboys                | Dolphins win × Jamayne Isaako 2+ tries × ATS Jack Bostock × total over 53.5                                                                   |    0.0547 |        18.28 |          0.0222 |              2.465 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Edward Kosi × total over 42.5                                                         |    0.0671 |        14.9  |          0.0283 |              2.374 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Dallin Watene-Zelezniak × total over 50.5                                     |    0.0664 |        15.07 |          0.0281 |              2.366 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles by 13+ × ATS Reuben Garrick × ATS Lehi Hopoate × total over 41.5                                                   |    0.0774 |        12.92 |          0.0329 |              2.352 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs by 13+ × ATS Jacob Kiraz × ATS Enari Tuala × total over 42.5                                                    |    0.0811 |        12.33 |          0.0359 |              2.262 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters by 13+ × ATS Tommy Talau × ATS Rex Bassingthwaighte × total over 42.5                                                         |    0.0808 |        12.38 |          0.0367 |              2.202 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                       |    0.0875 |        11.43 |          0.0407 |              2.149 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Brian To'o × total over 40.5                                                               |    0.1045 |         9.57 |          0.05   |              2.088 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                       |    0.1229 |         8.14 |          0.06   |              2.049 |
| Dolphins v North Queensland Cowboys                | Dolphins by 13+ × ATS Jamayne Isaako × ATS Jack Bostock × total over 45.5                                                                     |    0.0995 |        10.05 |          0.0486 |              2.048 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × total over 42.5                                                            |    0.1123 |         8.9  |          0.0623 |              1.803 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × ATS Lehi Hopoate × total over 41.5                                                      |    0.1256 |         7.96 |          0.0702 |              1.789 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × ATS Rex Bassingthwaighte × total over 42.5                                                            |    0.1352 |         7.4  |          0.0778 |              1.738 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala × total over 42.5                                                       |    0.1327 |         7.54 |          0.0767 |              1.73  |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro × total over 42.5                                                          |    0.1373 |         7.28 |          0.0815 |              1.684 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × ATS Jack Bostock × total over 45.5                                                                        |    0.1571 |         6.36 |          0.0948 |              1.657 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o × total over 40.5                                                                  |    0.1571 |         6.37 |          0.0954 |              1.646 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak × total over 42.5                                          |    0.1801 |         5.55 |          0.1102 |              1.635 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × total over 49.5                                                                         |    0.1567 |         6.38 |          0.1085 |              1.444 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                           |    0.1481 |         6.75 |          0.1033 |              1.434 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × total over 50.5                                                                         |    0.1544 |         6.48 |          0.1088 |              1.42  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × total over 50.5                                                                                       |    0.1631 |         6.13 |          0.1159 |              1.407 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × total over 53.5                                                                                           |    0.1733 |         5.77 |          0.124  |              1.398 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi                                                                              |    0.1509 |         6.63 |          0.1079 |              1.398 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × Tommy Talau 2+ tries                                                                                                    |    0.1347 |         7.43 |          0.0969 |              1.39  |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × total over 50.5                                                                              |    0.148  |         6.76 |          0.1071 |              1.382 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × ATS Lehi Hopoate                                                                        |    0.1632 |         6.13 |          0.1184 |              1.379 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × Reuben Garrick 2+ tries                                                                                      |    0.1182 |         8.46 |          0.0858 |              1.378 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × match tries over 7.5                                                                    |    0.2053 |         4.87 |          0.1492 |              1.377 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × Jacob Kiraz 2+ tries                                                                                      |    0.1342 |         7.45 |          0.0976 |              1.375 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 50.5                                                                       |    0.1829 |         5.47 |          0.1335 |              1.369 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                        |    0.1977 |         5.06 |          0.1448 |              1.366 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × total over 41.5                                                                         |    0.2209 |         4.53 |          0.1623 |              1.362 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × ATS Rex Bassingthwaighte                                                                              |    0.1775 |         5.63 |          0.1306 |              1.359 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × match tries over 8.5                                                                                      |    0.2116 |         4.73 |          0.1557 |              1.358 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × match tries over 7.5                                                                    |    0.2198 |         4.55 |          0.1633 |              1.346 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × total over 42.5                                                                         |    0.2205 |         4.54 |          0.1641 |              1.343 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Enari Tuala                                                                         |    0.1804 |         5.54 |          0.1344 |              1.342 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × ATS Murray Taulagi × total over 45.5                                                                      |    0.1446 |         6.91 |          0.1079 |              1.34  |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × total over 48.5                                                                                   |    0.2116 |         4.73 |          0.158  |              1.34  |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × match tries over 7.5                                                                                  |    0.227  |         4.4  |          0.1697 |              1.338 |
| Dolphins v North Queensland Cowboys                | Dolphins win × Jamayne Isaako 2+ tries                                                                                                        |    0.141  |         7.09 |          0.1055 |              1.337 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Setu Tu × total over 42.5                                                          |    0.1306 |         7.66 |          0.0977 |              1.336 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × total over 42.5                                                                                       |    0.2269 |         4.41 |          0.17   |              1.335 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                                    |    0.1718 |         5.82 |          0.1288 |              1.334 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters win × ATS Tommy Talau × ATS Moses Leo × total over 42.5                                                                       |    0.1161 |         8.61 |          0.0871 |              1.332 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles win × ATS Reuben Garrick × ATS AJ Brimson × total over 41.5                                                        |    0.0968 |        10.33 |          0.0728 |              1.33  |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs win × ATS Jacob Kiraz × ATS Jahream Bula × total over 42.5                                                      |    0.1022 |         9.79 |          0.0771 |              1.325 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                         |    0.212  |         4.72 |          0.1603 |              1.322 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × total over 45.5                                                                                           |    0.2409 |         4.15 |          0.1824 |              1.321 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × total over 42.5                                                                              |    0.2121 |         4.72 |          0.1608 |              1.319 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles by 13+ × ATS Reuben Garrick                                                                                        |    0.1691 |         5.91 |          0.1282 |              1.319 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS KL Iro                                                                            |    0.1831 |         5.46 |          0.1389 |              1.318 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                   |    0.2804 |         3.57 |          0.2142 |              1.309 |
| Dolphins v North Queensland Cowboys                | Dolphins win × ATS Jamayne Isaako × ATS Jack Bostock                                                                                          |    0.2082 |         4.8  |          0.1593 |              1.307 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                        |    0.2803 |         3.57 |          0.2147 |              1.305 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                             |    0.1646 |         6.07 |          0.1264 |              1.303 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                                  |    0.2581 |         3.87 |          0.1982 |              1.302 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Dominic Young × total over 42.5                                                   |    0.1409 |         7.1  |          0.1085 |              1.299 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 42.5                                                                       |    0.2573 |         3.89 |          0.1986 |              1.296 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Grant Anderson × total over 40.5                                                              |    0.1224 |         8.17 |          0.0946 |              1.294 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs by 13+ × ATS Jacob Kiraz                                                                                        |    0.1738 |         5.75 |          0.1344 |              1.293 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Xavier Savage × total over 42.5                                                          |    0.1021 |         9.79 |          0.079  |              1.292 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                              |    0.279  |         3.58 |          0.2161 |              1.291 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters by 13+ × ATS Tommy Talau                                                                                                      |    0.1737 |         5.76 |          0.1347 |              1.29  |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                |    0.2308 |         4.33 |          0.1798 |              1.283 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × total over 40.5                                                                                   |    0.3029 |         3.3  |          0.2373 |              1.276 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                                      |    0.2146 |         4.66 |          0.169  |              1.27  |
| Dolphins v North Queensland Cowboys                | Dolphins by 13+ × ATS Jamayne Isaako                                                                                                          |    0.199  |         5.03 |          0.1569 |              1.268 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                     |    0.1815 |         5.51 |          0.1433 |              1.267 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers win × ATS Thomas Jenkins × ATS Brian To'o                                                                                    |    0.2085 |         4.8  |          0.1647 |              1.266 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Dallin Watene-Zelezniak                                                            |    0.2431 |         4.11 |          0.1947 |              1.249 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                       |    0.2547 |         3.93 |          0.2066 |              1.233 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                  |    0.2632 |         3.8  |          0.2149 |              1.225 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | Manly-Warringah Sea Eagles -2.5 × ATS Reuben Garrick                                                                                          |    0.2995 |         3.34 |          0.2484 |              1.206 |
| Sydney Roosters v Melbourne Storm                  | Sydney Roosters -2.5 × ATS Tommy Talau                                                                                                        |    0.3099 |         3.23 |          0.2597 |              1.193 |
| Dolphins v North Queensland Cowboys                | Dolphins -4.5 × ATS Jamayne Isaako                                                                                                            |    0.3063 |         3.26 |          0.2572 |              1.191 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | Canterbury-Bankstown Bulldogs -2.5 × ATS Jacob Kiraz                                                                                          |    0.3104 |         3.22 |          0.2613 |              1.188 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | Cronulla-Sutherland Sharks -4.5 × ATS Ronaldo Mulitalo                                                                                        |    0.3317 |         3.01 |          0.2804 |              1.183 |
| Canberra Raiders v South Sydney Rabbitohs          | South Sydney Rabbitohs -0.5 × ATS Alex Johnston                                                                                               |    0.3289 |         3.04 |          0.2785 |              1.181 |
| New Zealand Warriors v St George Illawarra Dragons | New Zealand Warriors -6.5 × ATS Alofiana Khan-Pereira                                                                                         |    0.3459 |         2.89 |          0.2939 |              1.177 |
| Penrith Panthers v Brisbane Broncos                | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                    |    0.3664 |         2.73 |          0.3112 |              1.177 |
| Penrith Panthers v Brisbane Broncos                | ATS Thomas Jenkins × ATS Grant Anderson                                                                                                       |    0.2612 |         3.83 |          0.2598 |              1.006 |
| Sydney Roosters v Melbourne Storm                  | ATS Tommy Talau × ATS Moses Leo                                                                                                               |    0.2805 |         3.57 |          0.2795 |              1.003 |
| Dolphins v North Queensland Cowboys                | ATS Jamayne Isaako × ATS Murray Taulagi                                                                                                       |    0.3192 |         3.13 |          0.3182 |              1.003 |
| Gold Coast Titans v Manly-Warringah Sea Eagles     | ATS Reuben Garrick × ATS AJ Brimson                                                                                                           |    0.2267 |         4.41 |          0.2264 |              1.001 |
| New Zealand Warriors v St George Illawarra Dragons | ATS Alofiana Khan-Pereira × ATS Setu Tu                                                                                                       |    0.2684 |         3.73 |          0.2681 |              1.001 |
| Cronulla-Sutherland Sharks v Newcastle Knights     | ATS Ronaldo Mulitalo × ATS Dominic Young                                                                                                      |    0.3235 |         3.09 |          0.3238 |              0.999 |
| Canterbury-Bankstown Bulldogs v Wests Tigers       | ATS Jacob Kiraz × ATS Jahream Bula                                                                                                            |    0.2505 |         3.99 |          0.2516 |              0.996 |
| Canberra Raiders v South Sydney Rabbitohs          | ATS Alex Johnston × ATS Xavier Savage                                                                                                         |    0.2827 |         3.54 |          0.2841 |              0.995 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round20.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._