# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-08-24. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2286 / 0.6513 | 0.2286 / 0.6512 |
| gbm | 0.2281 / 0.6496 | 0.2279 / 0.6494 |
| blend | 0.2179 / 0.6272 | 0.2179 / 0.6271 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.241  |            0.6748 |      0.2476 |        0.6882 |        0.2362 |          0.6654 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2275 |            0.6523 |      0.2311 |        0.66   |        0.2215 |          0.638  |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2337 |            0.66   |      0.2404 |        0.6734 |        0.22   |          0.6299 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2405 |            0.674  |      0.2364 |        0.6649 |        0.2359 |          0.6654 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2335 |            0.6621 |      0.2327 |        0.6605 |        0.2257 |          0.6447 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2174 |            0.6294 |      0.2186 |        0.631  |        0.1997 |          0.5887 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2061 |            0.6028 |      0.2145 |        0.62   |        0.1814 |          0.5439 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2202 |            0.6322 |      0.2187 |        0.6288 |        0.2045 |          0.5948 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6522 |      0.2179 |        0.6297 |        0.2179 |          0.63   |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2297 |            0.6544 |      0.2208 |        0.6355 |        0.2231 |          0.6407 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2349 |            0.6649 |      0.2295 |        0.6526 |        0.2276 |          0.6492 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   8 |       0.167 |      0     |
| (0.2, 0.3] |  75 |       0.262 |      0.173 |
| (0.3, 0.4] | 215 |       0.355 |      0.347 |
| (0.4, 0.5] | 413 |       0.454 |      0.404 |
| (0.5, 0.6] | 518 |       0.55  |      0.55  |
| (0.6, 0.7] | 518 |       0.648 |      0.67  |
| (0.7, 0.8] | 357 |       0.742 |      0.742 |
| (0.8, 0.9] | 106 |       0.836 |      0.84  |
| (0.9, 1.0] |   5 |       0.909 |      1     |

## Upcoming round — all models

| round    | date                | venue                           | home                       | away                          |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:--------------------------------|:---------------------------|:------------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 26 | 2026-08-27 19:50:00 | Suncorp Stadium                 | Brisbane Broncos           | Melbourne Storm               |       0.4919 |           0.4889 |       0.4078 |         0.4442 |              -0.4 |               47.7 |
| Round 26 | 2026-08-28 18:00:00 | 4 Pines Park                    | Manly-Warringah Sea Eagles | St George Illawarra Dragons   |       0.7593 |           0.6747 |       0.7192 |         0.8056 |               7.3 |               47.3 |
| Round 26 | 2026-08-28 20:00:00 | CommBank Stadium                | Penrith Panthers           | Canterbury-Bankstown Bulldogs |       0.7366 |           0.6534 |       0.76   |         0.7868 |               6.5 |               45.2 |
| Round 26 | 2026-08-29 15:00:00 | Cbus Super Stadium              | Gold Coast Titans          | South Sydney Rabbitohs        |       0.4209 |           0.4551 |       0.4754 |         0.3753 |              -1.8 |               48.2 |
| Round 26 | 2026-08-29 17:30:00 | Allianz Stadium                 | Sydney Roosters            | Dolphins                      |       0.6194 |           0.5197 |       0.5513 |         0.5751 |               0.9 |               49   |
| Round 26 | 2026-08-29 19:35:00 | Queensland Country Bank Stadium | North Queensland Cowboys   | Wests Tigers                  |       0.7236 |           0.5702 |       0.6951 |         0.7235 |               3.1 |               49.8 |
| Round 26 | 2026-08-30 14:00:00 | Go Media Stadium                | New Zealand Warriors       | Newcastle Knights             |       0.7222 |           0.5971 |       0.6229 |         0.7176 |               4.1 |               47.6 |
| Round 26 | 2026-08-30 16:05:00 | CommBank Stadium                | Parramatta Eels            | Cronulla-Sutherland Sharks    |       0.3821 |           0.4469 |       0.4971 |         0.327  |              -2.3 |               48.1 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._