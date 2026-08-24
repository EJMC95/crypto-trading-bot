# Phase 4 report — player props + SGM simulator

_Generated 2026-08-24. ATS model: hierarchical Poisson-gamma try rates (positional pooling, ξ=1.4 decay) × tier-2 team try expectation via Poisson thinning. Squads in backtest = the 17 who played (Tuesday-list proxy — applies equally to model and baseline)._

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
| Brisbane Broncos v Melbourne Storm                       |       0.4871 |         0.4854 |  0.0017 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons |       0.6624 |         0.6617 |  0.0008 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         |       0.6583 |         0.6556 |  0.0027 |
| Gold Coast Titans v South Sydney Rabbitohs               |       0.4551 |         0.4563 | -0.0012 |
| Sydney Roosters v Dolphins                               |       0.5266 |         0.5232 |  0.0034 |
| North Queensland Cowboys v Wests Tigers                  |       0.5766 |         0.5746 |  0.002  |
| New Zealand Warriors v Newcastle Knights                 |       0.6    |         0.6032 | -0.0032 |
| Parramatta Eels v Cronulla-Sutherland Sharks             |       0.446  |         0.4542 | -0.0082 |

Max |diff| = 0.0082 vs 3σ MC bound 0.0173 → **PASSED**.

## Round 26 — top ATS props (model fair prices)

| match                                                    | team                          | player                  | position   |   exp_tries |   p_ats |   fair_price |   p_2plus |   fair_2plus | vs_opp   |
|:---------------------------------------------------------|:------------------------------|:------------------------|:-----------|------------:|--------:|-------------:|----------:|-------------:|:---------|
| Brisbane Broncos v Melbourne Storm                       | Brisbane Broncos              | Jesse Arthars           | W          |        0.62 |   0.46  |         2.17 |     0.128 |          7.8 | 5t/9g    |
| Brisbane Broncos v Melbourne Storm                       | Brisbane Broncos              | Josiah Karapani         | W          |        0.51 |   0.402 |         2.49 |     0.094 |         10.6 | 1t/3g    |
| Brisbane Broncos v Melbourne Storm                       | Brisbane Broncos              | Antonio Verhoeven       | C          |        0.41 |   0.334 |         2.99 |     0.063 |         15.8 | —        |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm               | Will Warbrick           | W          |        0.85 |   0.572 |         1.75 |     0.209 |          4.8 | 8t/7g    |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm               | Sualauvi Fa'alogo       | FB         |        0.66 |   0.482 |         2.08 |     0.141 |          7.1 | 3t/3g    |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm               | Jahrome Hughes          | HB         |        0.65 |   0.477 |         2.1  |     0.138 |          7.3 | 13t/15g  |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles    | Lehi Hopoate            | W          |        0.61 |   0.454 |         2.2  |     0.124 |          8.1 | 2t/4g    |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles    | Toluta'u Koula          | C          |        0.55 |   0.425 |         2.35 |     0.107 |          9.4 | 4t/7g    |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles    | Jason Saab              | W          |        0.49 |   0.384 |         2.6  |     0.086 |         11.7 | 3t/8g    |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | St George Illawarra Dragons   | Tyrell Sloan            | C          |        0.62 |   0.464 |         2.15 |     0.13  |          7.7 | 6t/7g    |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | St George Illawarra Dragons   | Setu Tu                 | W          |        0.55 |   0.42  |         2.38 |     0.104 |          9.6 | 1t/1g    |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | St George Illawarra Dragons   | Clinton Gutherson       | FB         |        0.35 |   0.298 |         3.35 |     0.05  |         20.1 | 8t/18g   |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers              | Thomas Jenkins          | W          |        0.8  |   0.552 |         1.81 |     0.192 |          5.2 | 2t/3g    |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers              | Paul Alamoti            | C          |        0.68 |   0.492 |         2.03 |     0.148 |          6.8 | 4t/4g    |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers              | Brian To'o              | W          |        0.65 |   0.478 |         2.09 |     0.139 |          7.2 | 6t/9g    |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Canterbury-Bankstown Bulldogs | Jacob Kiraz             | W          |        0.58 |   0.442 |         2.26 |     0.116 |          8.6 | 3t/7g    |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Canterbury-Bankstown Bulldogs | Lachlan Galvin          | HB         |        0.39 |   0.321 |         3.11 |     0.058 |         17.2 | 2t/5g    |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Canterbury-Bankstown Bulldogs | Matt Burton             | FE         |        0.38 |   0.317 |         3.15 |     0.057 |         17.7 | 3t/8g    |
| Gold Coast Titans v South Sydney Rabbitohs               | Gold Coast Titans             | Jaylan De Groot         | C          |        0.66 |   0.481 |         2.08 |     0.141 |          7.1 | 1t/1g    |
| Gold Coast Titans v South Sydney Rabbitohs               | Gold Coast Titans             | Phillip Sami            | W          |        0.57 |   0.436 |         2.29 |     0.113 |          8.9 | 2t/6g    |
| Gold Coast Titans v South Sydney Rabbitohs               | Gold Coast Titans             | Jensen Taumoepeau       | W          |        0.52 |   0.408 |         2.45 |     0.098 |         10.2 | —        |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs        | Alex Johnston           | W          |        1.19 |   0.695 |         1.44 |     0.333 |          3   | 16t/13g  |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs        | Cody Walker             | FE         |        0.56 |   0.428 |         2.34 |     0.109 |          9.2 | 7t/10g   |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs        | Edward Kosi             | W          |        0.38 |   0.317 |         3.15 |     0.057 |         17.6 | 0t/2g    |
| Sydney Roosters v Dolphins                               | Sydney Roosters               | Rex Bassingthwaighte    | W          |        0.68 |   0.495 |         2.02 |     0.15  |          6.7 | 1t/1g    |
| Sydney Roosters v Dolphins                               | Sydney Roosters               | Tommy Talau             | W          |        0.47 |   0.373 |         2.68 |     0.08  |         12.4 | 1t/3g    |
| Sydney Roosters v Dolphins                               | Sydney Roosters               | Billy Smith             | C          |        0.46 |   0.37  |         2.7  |     0.079 |         12.7 | 2t/4g    |
| Sydney Roosters v Dolphins                               | Dolphins                      | Tevita Naufahu          | W          |        0.8  |   0.55  |         1.82 |     0.191 |          5.2 | 3t/2g    |
| Sydney Roosters v Dolphins                               | Dolphins                      | Jamayne Isaako          | W          |        0.58 |   0.44  |         2.27 |     0.115 |          8.7 | 7t/12g   |
| Sydney Roosters v Dolphins                               | Dolphins                      | Trai Fuller             | FB         |        0.45 |   0.365 |         2.74 |     0.077 |         13.1 | 1t/1g    |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys      | Murray Taulagi          | W          |        0.91 |   0.599 |         1.67 |     0.232 |          4.3 | 10t/9g   |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys      | Jaxon Purdue            | C          |        0.58 |   0.441 |         2.27 |     0.116 |          8.6 | 3t/3g    |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys      | Scott Drinkwater        | FB         |        0.54 |   0.415 |         2.41 |     0.101 |          9.9 | 8t/13g   |
| North Queensland Cowboys v Wests Tigers                  | Wests Tigers                  | Jahream Bula            | FB         |        0.66 |   0.481 |         2.08 |     0.141 |          7.1 | 6t/7g    |
| North Queensland Cowboys v Wests Tigers                  | Wests Tigers                  | Starford To'a           | C          |        0.61 |   0.456 |         2.19 |     0.125 |          8   | 6t/7g    |
| North Queensland Cowboys v Wests Tigers                  | Wests Tigers                  | Taylan May              | C          |        0.59 |   0.444 |         2.25 |     0.117 |          8.5 | 3t/4g    |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors          | Alofiana Khan-Pereira   | W          |        0.76 |   0.531 |         1.88 |     0.176 |          5.7 | 3t/4g    |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors          | Adam Pompey             | C          |        0.65 |   0.476 |         2.1  |     0.138 |          7.3 | 9t/11g   |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors          | Dallin Watene-Zelezniak | W          |        0.61 |   0.456 |         2.19 |     0.125 |          8   | 9t/16g   |
| New Zealand Warriors v Newcastle Knights                 | Newcastle Knights             | Greg Marzhew            | W          |        0.95 |   0.613 |         1.63 |     0.246 |          4.1 | 7t/8g    |
| New Zealand Warriors v Newcastle Knights                 | Newcastle Knights             | Dominic Young           | W          |        0.56 |   0.43  |         2.33 |     0.109 |          9.1 | 3t/9g    |
| New Zealand Warriors v Newcastle Knights                 | Newcastle Knights             | Fletcher Sharpe         | FB         |        0.46 |   0.366 |         2.73 |     0.077 |         13   | 0t/1g    |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Parramatta Eels               | Josh Addo-Carr          | W          |        0.5  |   0.391 |         2.55 |     0.089 |         11.2 | 4t/12g   |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Parramatta Eels               | Isaiah Iongi            | FB         |        0.4  |   0.332 |         3.02 |     0.062 |         16   | 0t/1g    |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Parramatta Eels               | Joash Papalii           | FE         |        0.4  |   0.331 |         3.02 |     0.062 |         16.1 | —        |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks    | Ronaldo Mulitalo        | W          |        0.73 |   0.519 |         1.93 |     0.167 |          6   | 4t/6g    |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks    | Sione Katoa             | W          |        0.63 |   0.468 |         2.13 |     0.133 |          7.5 | 4t/6g    |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks    | KL Iro                  | C          |        0.58 |   0.438 |         2.28 |     0.114 |          8.8 | 1t/2g    |

## Round 26 — SGM candidates (fair vs independence pricing)

| match                                                    | combo                                                                                                                                         |   p_joint |   fair_price |   p_independent |   correlation_lift |
|:---------------------------------------------------------|:----------------------------------------------------------------------------------------------------------------------------------------------|----------:|-------------:|----------------:|-------------------:|
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × ATS Billy Smith × total over 44.5 × match tries over 9.5                   |    0.0342 |        29.27 |          0.0068 |              4.991 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa × ATS KL Iro × total over 44.5 × match tries over 9.5                 |    0.0516 |        19.39 |          0.0105 |              4.898 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × ATS Sualauvi Fa'alogo × ATS Moses Leo × total over 42.5 × match tries over 9.5                      |    0.0474 |        21.09 |          0.0099 |              4.781 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × ATS Jaxon Purdue × ATS Scott Drinkwater × total over 44.5 × match tries over 10.5         |    0.0443 |        22.57 |          0.0093 |              4.747 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × ATS Latrell Siegwalt × total over 42.5 × match tries over 9.5              |    0.0278 |        35.95 |          0.0059 |              4.721 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × ATS Paul Alamoti × ATS Brian To'o × total over 40.5 × match tries over 9.5                        |    0.0594 |        16.82 |          0.0126 |              4.72  |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × ATS Jason Saab × total over 42.5 × match tries over 9.5              |    0.04   |        24.98 |          0.0087 |              4.617 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Adam Pompey × ATS Dallin Watene-Zelezniak × total over 42.5 × match tries over 9.5 |    0.0556 |        17.98 |          0.0124 |              4.497 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × Rex Bassingthwaighte 2+ tries × ATS Tommy Talau × total over 52.5                                                       |    0.0305 |        32.79 |          0.0106 |              2.872 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries × ATS Sione Katoa × total over 52.5                                                |    0.0412 |        24.27 |          0.0151 |              2.733 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × Will Warbrick 2+ tries × ATS Sualauvi Fa'alogo × total over 50.5                                                        |    0.0527 |        18.98 |          0.0193 |              2.731 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × Alex Johnston 2+ tries × ATS Edward Kosi × total over 50.5                                                       |    0.0568 |        17.61 |          0.022  |              2.577 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries × ATS Toluta'u Koula × total over 50.5                                                 |    0.0333 |        30.05 |          0.0131 |              2.533 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries × ATS Adam Pompey × total over 50.5                                                 |    0.0481 |        20.78 |          0.0191 |              2.519 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × Murray Taulagi 2+ tries × ATS Jaxon Purdue × total over 52.5                                                   |    0.0567 |        17.64 |          0.0226 |              2.509 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × Thomas Jenkins 2+ tries × ATS Paul Alamoti × total over 48.5                                                           |    0.0567 |        17.64 |          0.0228 |              2.486 |
| Sydney Roosters v Dolphins                               | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                         |    0.0598 |        16.72 |          0.0248 |              2.409 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo × ATS Sione Katoa × total over 44.5                                                  |    0.0773 |        12.94 |          0.0341 |              2.265 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm by 13+ × ATS Will Warbrick × ATS Sualauvi Fa'alogo × total over 42.5                                                          |    0.0785 |        12.75 |          0.0351 |              2.234 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs by 13+ × ATS Alex Johnston × ATS Edward Kosi × total over 42.5                                                         |    0.0686 |        14.59 |          0.0316 |              2.168 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 42.5                                                   |    0.0845 |        11.84 |          0.0393 |              2.148 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers by 13+ × ATS Thomas Jenkins × ATS Paul Alamoti × total over 40.5                                                             |    0.1129 |         8.85 |          0.0531 |              2.126 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira × ATS Adam Pompey × total over 42.5                                                   |    0.0906 |        11.04 |          0.0432 |              2.096 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys by 13+ × ATS Murray Taulagi × ATS Jaxon Purdue × total over 44.5                                                     |    0.0904 |        11.06 |          0.0432 |              2.092 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau × total over 44.5                                                            |    0.0979 |        10.21 |          0.053  |              1.846 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa × total over 44.5                                                     |    0.126  |         7.93 |          0.0716 |              1.759 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × ATS Sualauvi Fa'alogo × total over 42.5                                                             |    0.1384 |         7.22 |          0.0793 |              1.746 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi × total over 42.5                                                            |    0.1154 |         8.67 |          0.0678 |              1.703 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula × total over 42.5                                                      |    0.1217 |         8.22 |          0.0718 |              1.694 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × ATS Jaxon Purdue × total over 44.5                                                        |    0.1449 |         6.9  |          0.0866 |              1.673 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Adam Pompey × total over 42.5                                                      |    0.1429 |         7    |          0.0856 |              1.67  |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × ATS Paul Alamoti × total over 40.5                                                                |    0.1667 |         6    |          0.0998 |              1.669 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 50.5                                                                           |    0.1644 |         6.08 |          0.1138 |              1.444 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 52.5                                                                              |    0.136  |         7.35 |          0.0945 |              1.439 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × Will Warbrick 2+ tries                                                                                                  |    0.1443 |         6.93 |          0.1004 |              1.437 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 52.5                                                                       |    0.1427 |         7.01 |          0.1003 |              1.423 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × Rex Bassingthwaighte 2+ tries                                                                                           |    0.1069 |         9.35 |          0.0752 |              1.422 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tommy Talau                                                                              |    0.131  |         7.63 |          0.0929 |              1.411 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × total over 48.5                                                                                   |    0.1883 |         5.31 |          0.1334 |              1.411 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × Ronaldo Mulitalo 2+ tries                                                                                    |    0.1218 |         8.21 |          0.0871 |              1.399 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 50.5                                                                        |    0.1691 |         5.92 |          0.1212 |              1.395 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × total over 50.5                                                                                     |    0.1553 |         6.44 |          0.1117 |              1.391 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Tyrell Sloan × total over 42.5                                                        |    0.1097 |         9.11 |          0.0792 |              1.386 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × ATS Sualauvi Fa'alogo                                                                               |    0.1861 |         5.37 |          0.1344 |              1.385 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × total over 44.5                                                                              |    0.1951 |         5.13 |          0.1424 |              1.371 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × total over 44.5                                                                       |    0.2063 |         4.85 |          0.1518 |              1.359 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × total over 52.5                                                                           |    0.1825 |         5.48 |          0.1346 |              1.357 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × match tries over 7.5                                                                      |    0.229  |         4.37 |          0.169  |              1.355 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Sione Katoa                                                                       |    0.1748 |         5.72 |          0.1291 |              1.355 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × match tries over 7.5                                                                              |    0.2479 |         4.03 |          0.1834 |              1.352 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × match tries over 7.5                                                                         |    0.2073 |         4.82 |          0.1534 |              1.351 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × ATS Jacob Kiraz × total over 40.5                                                                 |    0.1213 |         8.24 |          0.0899 |              1.35  |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × total over 42.5                                                                           |    0.2289 |         4.37 |          0.1696 |              1.349 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × Alex Johnston 2+ tries                                                                                           |    0.2329 |         4.29 |          0.1726 |              1.349 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × Alofiana Khan-Pereira 2+ tries                                                                                     |    0.1355 |         7.38 |          0.1006 |              1.347 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Greg Marzhew × total over 42.5                                                     |    0.1476 |         6.78 |          0.1098 |              1.344 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × Murray Taulagi 2+ tries                                                                                        |    0.171  |         5.85 |          0.1275 |              1.342 |
| Sydney Roosters v Dolphins                               | Sydney Roosters win × ATS Rex Bassingthwaighte × ATS Tevita Naufahu × total over 44.5                                                         |    0.1042 |         9.6  |          0.0776 |              1.342 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Edward Kosi                                                                              |    0.1524 |         6.56 |          0.1137 |              1.341 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × match tries over 7.5                                                                  |    0.2201 |         4.54 |          0.1644 |              1.339 |
| Sydney Roosters v Dolphins                               | Sydney Roosters by 13+ × ATS Rex Bassingthwaighte                                                                                             |    0.1556 |         6.43 |          0.1167 |              1.334 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × total over 40.5                                                                                   |    0.2701 |         3.7  |          0.2028 |              1.332 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × match tries over 8.5                                                                      |    0.223  |         4.48 |          0.1674 |              1.332 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × match tries over 7.5                                                                                |    0.2188 |         4.57 |          0.1648 |              1.328 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × total over 42.5                                                                                     |    0.2184 |         4.58 |          0.1649 |              1.325 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × match tries over 7.5                                                                   |    0.2365 |         4.23 |          0.179  |              1.321 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × total over 42.5                                                                        |    0.236  |         4.24 |          0.1791 |              1.318 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks win × ATS Ronaldo Mulitalo × ATS Josh Addo-Carr × total over 44.5                                                  |    0.0788 |        12.69 |          0.0599 |              1.316 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × ATS Jaxon Purdue                                                                          |    0.1919 |         5.21 |          0.1459 |              1.315 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × total over 50.5                                                                              |    0.1913 |         5.23 |          0.1458 |              1.312 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors win × ATS Alofiana Khan-Pereira × ATS Adam Pompey                                                                        |    0.1911 |         5.23 |          0.1457 |              1.311 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × Lehi Hopoate 2+ tries                                                                                        |    0.1036 |         9.66 |          0.0792 |              1.308 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks by 13+ × ATS Ronaldo Mulitalo                                                                                      |    0.1702 |         5.88 |          0.1302 |              1.308 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm by 13+ × ATS Will Warbrick                                                                                                    |    0.1615 |         6.19 |          0.1237 |              1.305 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × total over 44.5                                                                           |    0.2566 |         3.9  |          0.1975 |              1.299 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys win × ATS Murray Taulagi × ATS Jahream Bula × total over 44.5                                                        |    0.1229 |         8.14 |          0.0954 |              1.287 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × Thomas Jenkins 2+ tries                                                                                                |    0.1557 |         6.42 |          0.1213 |              1.284 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles win × ATS Lehi Hopoate × ATS Toluta'u Koula                                                                        |    0.1575 |         6.35 |          0.123  |              1.281 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles by 13+ × ATS Lehi Hopoate                                                                                          |    0.2034 |         4.92 |          0.159  |              1.28  |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm win × ATS Will Warbrick × ATS Jesse Arthars × total over 42.5                                                                 |    0.0961 |        10.41 |          0.0752 |              1.279 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers win × ATS Thomas Jenkins × ATS Paul Alamoti                                                                                  |    0.2195 |         4.56 |          0.172  |              1.276 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors by 13+ × ATS Alofiana Khan-Pereira                                                                                       |    0.1962 |         5.1  |          0.154  |              1.274 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × match tries over 7.5                                                                         |    0.2713 |         3.69 |          0.2144 |              1.265 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × total over 42.5                                                                              |    0.2709 |         3.69 |          0.2148 |              1.261 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers by 13+ × ATS Thomas Jenkins                                                                                                  |    0.234  |         4.27 |          0.1859 |              1.259 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys by 13+ × ATS Murray Taulagi                                                                                          |    0.2077 |         4.82 |          0.1661 |              1.25  |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs win × ATS Alex Johnston × ATS Jaylan De Groot × total over 42.5                                                        |    0.1284 |         7.79 |          0.1032 |              1.245 |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs by 13+ × ATS Alex Johnston                                                                                             |    0.2074 |         4.82 |          0.1681 |              1.234 |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | Manly-Warringah Sea Eagles -6.5 × ATS Lehi Hopoate                                                                                            |    0.2713 |         3.69 |          0.2236 |              1.214 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | Cronulla-Sutherland Sharks -2.5 × ATS Ronaldo Mulitalo                                                                                        |    0.2975 |         3.36 |          0.249  |              1.195 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | Penrith Panthers -6.5 × ATS Thomas Jenkins                                                                                                    |    0.3192 |         3.13 |          0.2673 |              1.194 |
| Sydney Roosters v Dolphins                               | Sydney Roosters -1.5 × ATS Rex Bassingthwaighte                                                                                               |    0.2948 |         3.39 |          0.2471 |              1.193 |
| New Zealand Warriors v Newcastle Knights                 | New Zealand Warriors -4.5 × ATS Alofiana Khan-Pereira                                                                                         |    0.3029 |         3.3  |          0.2544 |              1.191 |
| Brisbane Broncos v Melbourne Storm                       | Melbourne Storm -0.5 × ATS Will Warbrick                                                                                                      |    0.331  |         3.02 |          0.2794 |              1.185 |
| North Queensland Cowboys v Wests Tigers                  | North Queensland Cowboys -4.5 × ATS Murray Taulagi                                                                                            |    0.3255 |         3.07 |          0.2759 |              1.18  |
| Gold Coast Titans v South Sydney Rabbitohs               | South Sydney Rabbitohs -2.5 × ATS Alex Johnston                                                                                               |    0.3788 |         2.64 |          0.3274 |              1.157 |
| Penrith Panthers v Canterbury-Bankstown Bulldogs         | ATS Thomas Jenkins × ATS Jacob Kiraz                                                                                                          |    0.2453 |         4.08 |          0.2442 |              1.004 |
| Gold Coast Titans v South Sydney Rabbitohs               | ATS Alex Johnston × ATS Jaylan De Groot                                                                                                       |    0.3329 |         3    |          0.3322 |              1.002 |
| New Zealand Warriors v Newcastle Knights                 | ATS Alofiana Khan-Pereira × ATS Greg Marzhew                                                                                                  |    0.3257 |         3.07 |          0.325  |              1.002 |
| Brisbane Broncos v Melbourne Storm                       | ATS Will Warbrick × ATS Jesse Arthars                                                                                                         |    0.261  |         3.83 |          0.2609 |              1     |
| Manly-Warringah Sea Eagles v St George Illawarra Dragons | ATS Lehi Hopoate × ATS Tyrell Sloan                                                                                                           |    0.2117 |         4.72 |          0.212  |              0.999 |
| Parramatta Eels v Cronulla-Sutherland Sharks             | ATS Ronaldo Mulitalo × ATS Josh Addo-Carr                                                                                                     |    0.2031 |         4.92 |          0.2037 |              0.997 |
| Sydney Roosters v Dolphins                               | ATS Rex Bassingthwaighte × ATS Tevita Naufahu                                                                                                 |    0.2696 |         3.71 |          0.2707 |              0.996 |
| North Queensland Cowboys v Wests Tigers                  | ATS Murray Taulagi × ATS Jahream Bula                                                                                                         |    0.2895 |         3.45 |          0.2906 |              0.996 |

_correlation_lift = joint probability ÷ product of leg marginals. Lift > 1 means the legs help each other — a bookmaker pricing them independently (then stacking 20–40% margin) undervalues the combo. No quoted SGM prices yet: paste bookie quotes into data/manual_odds/round26.csv and re-run to get EV columns._

_Paper only. Fair prices are model outputs with uncertainty, not betting advice._