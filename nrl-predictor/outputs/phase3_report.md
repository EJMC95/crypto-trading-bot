# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-07-07. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2287 / 0.6514 | 0.2286 / 0.6513 |
| gbm | 0.2287 / 0.6510 | 0.2284 / 0.6504 |
| blend | 0.2188 / 0.6293 | 0.2186 / 0.6290 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.241  |            0.6748 |      0.2472 |        0.6874 |        0.237  |          0.6669 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2277 |            0.6526 |      0.2329 |        0.6637 |        0.2201 |          0.6356 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2334 |            0.6596 |      0.2384 |        0.6694 |        0.2228 |          0.636  |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2411 |            0.6753 |      0.2352 |        0.6627 |        0.236  |          0.6654 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.233  |            0.6611 |      0.2337 |        0.6625 |        0.2268 |          0.6475 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2173 |            0.6294 |      0.2238 |        0.6418 |        0.2029 |          0.5964 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2066 |            0.6039 |      0.2171 |        0.6255 |        0.1856 |          0.5546 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2201 |            0.6319 |      0.2182 |        0.628  |        0.203  |          0.5922 |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6522 |      0.2182 |        0.6298 |        0.2172 |          0.6286 |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2294 |            0.6538 |      0.2191 |        0.6317 |        0.2229 |          0.6397 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.2353 |            0.6657 |      0.2321 |        0.6589 |        0.2291 |          0.6522 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   3 |       0.167 |      0     |
| (0.2, 0.3] |  47 |       0.267 |      0.149 |
| (0.3, 0.4] | 184 |       0.359 |      0.299 |
| (0.4, 0.5] | 413 |       0.455 |      0.392 |
| (0.5, 0.6] | 601 |       0.551 |      0.556 |
| (0.6, 0.7] | 575 |       0.648 |      0.663 |
| (0.7, 0.8] | 323 |       0.74  |      0.762 |
| (0.8, 0.9] |  68 |       0.832 |      0.868 |
| (0.9, 1.0] |   1 |       0.911 |      1     |

## Upcoming round — all models

| round    | date                | venue                       | home                          | away                       |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:----------------------------|:------------------------------|:---------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 19 | 2026-07-10 20:00:00 | Campbelltown Sports Stadium | Wests Tigers                  | New Zealand Warriors       |       0.4053 |           0.4202 |       0.2877 |         0.3812 |              -3.3 |               47.5 |
| Round 19 | 2026-07-11 15:00:00 | Kayo Stadium                | Dolphins                      | Cronulla-Sutherland Sharks |       0.5974 |           0.5411 |       0.66   |         0.5859 |               1.7 |               48.7 |
| Round 19 | 2026-07-11 17:30:00 | Accor Stadium               | Canterbury-Bankstown Bulldogs | Canberra Raiders           |       0.6026 |           0.5241 |       0.636  |         0.5839 |               1.1 |               44.7 |
| Round 19 | 2026-07-11 19:35:00 | Allianz Stadium             | Sydney Roosters               | Parramatta Eels            |       0.7587 |           0.6156 |       0.8282 |         0.7478 |               4.9 |               48.4 |
| Round 19 | 2026-07-12 14:00:00 | Accor Stadium               | South Sydney Rabbitohs        | Newcastle Knights          |       0.5844 |           0.5801 |       0.5194 |         0.5897 |               3.3 |               49   |
| Round 19 | 2026-07-12 16:05:00 | 4 Pines Park                | Manly-Warringah Sea Eagles    | North Queensland Cowboys   |       0.6312 |           0.5874 |       0.7146 |         0.6311 |               3.7 |               48.2 |
| Round 19 | 2026-07-12 18:15:00 | AAMI Park                   | Melbourne Storm               | Gold Coast Titans          |       0.7716 |           0.6085 |       0.6384 |         0.7567 |               4.5 |               48.1 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._