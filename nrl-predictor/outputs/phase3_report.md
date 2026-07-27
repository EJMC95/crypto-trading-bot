# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-07-27. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2286 / 0.6512 | 0.2286 / 0.6512 |
| gbm | 0.2299 / 0.6535 | 0.2298 / 0.6532 |
| blend | 0.2179 / 0.6271 | 0.2178 / 0.6270 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2405 |            0.6738 |      0.2487 |        0.6908 |        0.2361 |          0.6652 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2275 |            0.6523 |      0.2342 |        0.6662 |        0.2214 |          0.6379 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2334 |            0.6596 |      0.24   |        0.6724 |        0.2198 |          0.6294 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2408 |            0.6747 |      0.2385 |        0.6697 |        0.2362 |          0.666  |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2331 |            0.6613 |      0.2351 |        0.6652 |        0.2253 |          0.6439 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2171 |            0.629  |      0.2218 |        0.6377 |        0.1991 |          0.5874 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2066 |            0.6038 |      0.2218 |        0.6351 |        0.1814 |          0.5437 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2205 |            0.6328 |      0.2199 |        0.6312 |        0.2048 |          0.5957 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6522 |      0.2163 |        0.6262 |        0.2179 |          0.63   |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2297 |            0.6543 |      0.2213 |        0.6358 |        0.223  |          0.6404 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.235  |            0.6651 |      0.2317 |        0.6579 |        0.2277 |          0.6493 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   8 |       0.165 |      0     |
| (0.2, 0.3] |  80 |       0.262 |      0.138 |
| (0.3, 0.4] | 214 |       0.355 |      0.362 |
| (0.4, 0.5] | 426 |       0.454 |      0.41  |
| (0.5, 0.6] | 510 |       0.55  |      0.547 |
| (0.6, 0.7] | 525 |       0.648 |      0.679 |
| (0.7, 0.8] | 345 |       0.743 |      0.745 |
| (0.8, 0.9] | 102 |       0.835 |      0.833 |
| (0.9, 1.0] |   5 |       0.908 |      1     |

## Upcoming round — all models

| round    | date                | venue                           | home                        | away                          |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:--------------------------------|:----------------------------|:------------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 22 | 2026-07-30 19:50:00 | Queensland Country Bank Stadium | North Queensland Cowboys    | Sydney Roosters               |       0.4638 |           0.4722 |       0.5533 |         0.4371 |              -1.2 |               48.7 |
| Round 22 | 2026-07-31 18:00:00 | WIN Stadium                     | St George Illawarra Dragons | Dolphins                      |       0.302  |           0.3891 |       0.2851 |         0.2375 |              -4.8 |               48.8 |
| Round 22 | 2026-07-31 20:00:00 | AAMI Park                       | Melbourne Storm             | Canterbury-Bankstown Bulldogs |       0.638  |           0.5811 |       0.5435 |         0.6556 |               3.2 |               46   |
| Round 22 | 2026-08-01 15:00:00 | Cbus Super Stadium              | Gold Coast Titans           | New Zealand Warriors          |       0.3769 |           0.4344 |       0.4001 |         0.3348 |              -3   |               46.6 |
| Round 22 | 2026-08-01 17:30:00 | Glen Willow Oval                | Penrith Panthers            | Canberra Raiders              |       0.7402 |           0.6611 |       0.7369 |         0.7883 |               6.6 |               46   |
| Round 22 | 2026-08-01 19:35:00 | Suncorp Stadium                 | Brisbane Broncos            | Newcastle Knights             |       0.5664 |           0.5427 |       0.49   |         0.5415 |               1.6 |               48.4 |
| Round 22 | 2026-08-02 14:00:00 | Ocean Protect Stadium           | Cronulla-Sutherland Sharks  | South Sydney Rabbitohs        |       0.7164 |           0.5481 |       0.8298 |         0.6897 |               2.1 |               47.8 |
| Round 22 | 2026-08-02 16:05:00 | CommBank Stadium                | Wests Tigers                | Parramatta Eels               |       0.5467 |           0.5067 |       0.451  |         0.5319 |               0.4 |               49.2 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._