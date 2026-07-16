# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-07-16. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2287 / 0.6514 | 0.2286 / 0.6513 |
| gbm | 0.2292 / 0.6522 | 0.2291 / 0.6520 |
| blend | 0.2180 / 0.6273 | 0.2180 / 0.6273 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2408 |            0.6744 |      0.2505 |        0.6948 |        0.2361 |          0.6651 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2275 |            0.6524 |      0.2329 |        0.6638 |        0.2215 |          0.6381 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2333 |            0.6593 |      0.2397 |        0.6718 |        0.2201 |          0.63   |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2412 |            0.6754 |      0.2374 |        0.6673 |        0.2359 |          0.6657 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.2334 |            0.662  |      0.2333 |        0.6617 |        0.2258 |          0.6449 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2173 |            0.6292 |      0.2228 |        0.6398 |        0.2    |          0.5894 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2061 |            0.6029 |      0.2168 |        0.6249 |        0.1817 |          0.5445 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2203 |            0.6323 |      0.2216 |        0.6351 |        0.2044 |          0.5945 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2286 |            0.6523 |      0.2179 |        0.63   |        0.218  |          0.6301 |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2297 |            0.6543 |      0.2207 |        0.6347 |        0.2232 |          0.6408 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2353 |            0.6657 |      0.2282 |        0.6501 |        0.2278 |          0.6495 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   7 |       0.163 |      0     |
| (0.2, 0.3] |  76 |       0.262 |      0.158 |
| (0.3, 0.4] | 210 |       0.356 |      0.34  |
| (0.4, 0.5] | 409 |       0.454 |      0.406 |
| (0.5, 0.6] | 523 |       0.551 |      0.547 |
| (0.6, 0.7] | 515 |       0.649 |      0.672 |
| (0.7, 0.8] | 364 |       0.743 |      0.742 |
| (0.8, 0.9] | 106 |       0.837 |      0.84  |
| (0.9, 1.0] |   5 |       0.91  |      1     |

## Upcoming round — all models

| round    | date                | venue                 | home                          | away                        |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:----------------------|:------------------------------|:----------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 20 | 2026-07-16 19:50:00 | CommBank Stadium      | Penrith Panthers              | Brisbane Broncos            |       0.7835 |           0.6539 |       0.8289 |         0.8073 |               6.4 |               46.7 |
| Round 20 | 2026-07-17 18:00:00 | Ocean Protect Stadium | Cronulla-Sutherland Sharks    | Newcastle Knights           |       0.701  |           0.5962 |       0.7201 |         0.708  |               4   |               48.9 |
| Round 20 | 2026-07-17 20:00:00 | Allianz Stadium       | Sydney Roosters               | Melbourne Storm             |       0.646  |           0.551  |       0.7229 |         0.6501 |               2   |               48.1 |
| Round 20 | 2026-07-18 15:00:00 | GIO Stadium           | Canberra Raiders              | South Sydney Rabbitohs      |       0.5753 |           0.4919 |       0.609  |         0.5399 |              -0.3 |               47.1 |
| Round 20 | 2026-07-18 17:35:00 | Go Media Stadium      | New Zealand Warriors          | St George Illawarra Dragons |       0.8115 |           0.6721 |       0.7123 |         0.832  |               7.2 |               46.6 |
| Round 20 | 2026-07-18 19:35:00 | Accor Stadium         | Canterbury-Bankstown Bulldogs | Wests Tigers                |       0.6499 |           0.5549 |       0.7378 |         0.6334 |               2.3 |               46.8 |
| Round 20 | 2026-07-19 14:00:00 | Cbus Super Stadium    | Gold Coast Titans             | Manly-Warringah Sea Eagles  |       0.369  |           0.4328 |       0.38   |         0.3035 |              -2.7 |               47.3 |
| Round 20 | 2026-07-19 16:05:00 | Suncorp Stadium       | Dolphins                      | North Queensland Cowboys    |       0.6414 |           0.5923 |       0.6297 |         0.666  |               4.1 |               50.2 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._