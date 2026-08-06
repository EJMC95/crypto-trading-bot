# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-08-06. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2286 / 0.6511 | 0.2285 / 0.6511 |
| gbm | 0.2289 / 0.6513 | 0.2288 / 0.6511 |
| blend | 0.2179 / 0.6271 | 0.2179 / 0.6271 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2406 |            0.674  |      0.2472 |        0.6875 |        0.2361 |          0.6651 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2274 |            0.6521 |      0.2331 |        0.6641 |        0.2214 |          0.6379 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2337 |            0.6602 |      0.2393 |        0.6713 |        0.22   |          0.6299 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.241  |            0.675  |      0.2367 |        0.6659 |        0.236  |          0.6658 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2331 |            0.6614 |      0.2343 |        0.6636 |        0.2256 |          0.6444 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.217  |            0.6287 |      0.2241 |        0.6425 |        0.1995 |          0.5884 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.206  |            0.6027 |      0.2176 |        0.6267 |        0.1814 |          0.5439 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2205 |            0.6328 |      0.22   |        0.6315 |        0.2046 |          0.595  |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2283 |            0.6518 |      0.2165 |        0.6268 |        0.2179 |          0.6298 |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2293 |            0.6535 |      0.2211 |        0.6361 |        0.223  |          0.6403 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2351 |            0.6653 |      0.228  |        0.6496 |        0.2277 |          0.6494 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   8 |       0.167 |      0     |
| (0.2, 0.3] |  76 |       0.262 |      0.158 |
| (0.3, 0.4] | 213 |       0.355 |      0.35  |
| (0.4, 0.5] | 414 |       0.453 |      0.408 |
| (0.5, 0.6] | 517 |       0.55  |      0.545 |
| (0.6, 0.7] | 522 |       0.648 |      0.672 |
| (0.7, 0.8] | 355 |       0.743 |      0.744 |
| (0.8, 0.9] | 105 |       0.836 |      0.838 |
| (0.9, 1.0] |   5 |       0.909 |      1     |

## Upcoming round — all models

| round    | date                | venue                            | home                        | away                          |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:---------------------------------|:----------------------------|:------------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 23 | 2026-08-06 19:50:00 | Cbus Super Stadium               | Gold Coast Titans           | North Queensland Cowboys      |       0.4477 |           0.492  |       0.5314 |         0.4165 |              -0.3 |               48.6 |
| Round 23 | 2026-08-07 18:00:00 | Go Media Stadium                 | New Zealand Warriors        | Penrith Panthers              |       0.4903 |           0.4642 |       0.5557 |         0.4372 |              -1.5 |               45.5 |
| Round 23 | 2026-08-07 20:00:00 | Allianz Stadium                  | Sydney Roosters             | Canterbury-Bankstown Bulldogs |       0.7144 |           0.5946 |       0.6261 |         0.7284 |               4   |               46   |
| Round 23 | 2026-08-08 15:00:00 | HBF Park                         | Melbourne Storm             | Manly-Warringah Sea Eagles    |       0.5878 |           0.5115 |       0.5433 |         0.5656 |               0.4 |               47.4 |
| Round 23 | 2026-08-08 17:30:00 | Suncorp Stadium                  | Dolphins                    | Brisbane Broncos              |       0.7291 |           0.5976 |       0.6858 |         0.7417 |               4.2 |               48.9 |
| Round 23 | 2026-08-08 19:35:00 | Allianz Stadium                  | South Sydney Rabbitohs      | Parramatta Eels               |       0.6497 |           0.5868 |       0.5872 |         0.6789 |               3.7 |               48.8 |
| Round 23 | 2026-08-09 14:00:00 | GIO Stadium                      | Canberra Raiders            | Newcastle Knights             |       0.5859 |           0.5314 |       0.5498 |         0.58   |               1.3 |               47.9 |
| Round 23 | 2026-08-09 16:05:00 | St George Venues Jubilee Stadium | St George Illawarra Dragons | Cronulla-Sutherland Sharks    |       0.2539 |           0.3948 |       0.302  |         0.2131 |              -4.5 |               47.5 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._