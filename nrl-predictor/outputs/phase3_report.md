# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-07-20. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2287 / 0.6513 | 0.2286 / 0.6513 |
| gbm | 0.2287 / 0.6509 | 0.2285 / 0.6505 |
| blend | 0.2180 / 0.6274 | 0.2180 / 0.6273 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2407 |            0.6743 |      0.2494 |        0.6924 |        0.236  |          0.665  |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2275 |            0.6524 |      0.2331 |        0.6641 |        0.2215 |          0.6381 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2338 |            0.6602 |      0.2398 |        0.6721 |        0.2202 |          0.6303 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2408 |            0.6746 |      0.2347 |        0.662  |        0.2358 |          0.6654 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2333 |            0.6618 |      0.2322 |        0.6595 |        0.2258 |          0.645  |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2172 |            0.629  |      0.2212 |        0.6365 |        0.2    |          0.5895 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2065 |            0.6037 |      0.2156 |        0.6223 |        0.1818 |          0.5448 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2204 |            0.6326 |      0.2187 |        0.6291 |        0.2044 |          0.5944 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6521 |      0.2181 |        0.6294 |        0.218  |          0.63   |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2294 |            0.6538 |      0.221  |        0.6354 |        0.2232 |          0.6408 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2352 |            0.6654 |      0.2313 |        0.6569 |        0.2277 |          0.6493 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   7 |       0.164 |      0     |
| (0.2, 0.3] |  75 |       0.262 |      0.16  |
| (0.3, 0.4] | 211 |       0.356 |      0.344 |
| (0.4, 0.5] | 408 |       0.454 |      0.402 |
| (0.5, 0.6] | 517 |       0.551 |      0.549 |
| (0.6, 0.7] | 522 |       0.649 |      0.669 |
| (0.7, 0.8] | 356 |       0.743 |      0.742 |
| (0.8, 0.9] | 114 |       0.835 |      0.833 |
| (0.9, 1.0] |   5 |       0.91  |      1     |

## Upcoming round — all models

| round    | date                | venue                            | home                          | away                       |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:---------------------------------|:------------------------------|:---------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 21 | 2026-07-23 19:50:00 | CommBank Stadium                 | Parramatta Eels               | Penrith Panthers           |       0.3251 |           0.3731 |       0.4223 |         0.2412 |              -5.2 |               47.5 |
| Round 21 | 2026-07-24 18:00:00 | McDonald Jones Stadium           | Newcastle Knights             | Sydney Roosters            |       0.4336 |           0.4588 |       0.6215 |         0.4075 |              -1.6 |               48.6 |
| Round 21 | 2026-07-24 20:00:00 | Accor Stadium                    | South Sydney Rabbitohs        | Melbourne Storm            |       0.5177 |           0.5192 |       0.5492 |         0.51   |               0.9 |               48.2 |
| Round 21 | 2026-07-25 15:00:00 | GIO Stadium                      | Canberra Raiders              | Wests Tigers               |       0.6987 |           0.5607 |       0.7563 |         0.6986 |               2.7 |               48.1 |
| Round 21 | 2026-07-25 17:30:00 | Accor Stadium                    | Canterbury-Bankstown Bulldogs | New Zealand Warriors       |       0.4517 |           0.4511 |       0.4614 |         0.4177 |              -1.9 |               44.4 |
| Round 21 | 2026-07-25 19:35:00 | Queensland Country Bank Stadium  | North Queensland Cowboys      | Brisbane Broncos           |       0.6205 |           0.5325 |       0.5466 |         0.6304 |               1.4 |               48.2 |
| Round 21 | 2026-07-26 14:00:00 | St George Venues Jubilee Stadium | St George Illawarra Dragons   | Gold Coast Titans          |       0.5508 |           0.4744 |       0.5489 |         0.5233 |              -0.8 |               47.4 |
| Round 21 | 2026-07-26 16:05:00 | 4 Pines Park                     | Manly-Warringah Sea Eagles    | Cronulla-Sutherland Sharks |       0.5078 |           0.5302 |       0.542  |         0.5164 |               1.3 |               47.2 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._