# Phase 3 report — Poisson + GBM vs Elo and the closing line

_Generated 2026-09-03. Walk-forward 2015–2025; Poisson refits before every round (Dixon–Coles decay ξ=1.0, 5y window); GBM retrains before every season on strictly-prior matches; stacked probability features are themselves walk-forward outputs. Draws score 0.5._

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | common subset (n=2171) |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6862 |
| elo_cal | 0.2194 / 0.6304 | 0.2192 / 0.6302 |
| poisson | 0.2287 / 0.6513 | 0.2286 / 0.6513 |
| gbm | 0.2283 / 0.6501 | 0.2281 / 0.6498 |
| blend | 0.2180 / 0.6272 | 0.2179 / 0.6272 |
| market | 0.2075 / 0.6036 | 0.2072 / 0.6029 |

## Per-season

|   year |   games |   brier_naive |   logloss_naive |   brier_elo_cal |   logloss_elo_cal |   brier_poisson |   logloss_poisson |   brier_gbm |   logloss_gbm |   brier_blend |   logloss_blend |   brier_market |   logloss_market |
|-------:|--------:|--------------:|----------------:|----------------:|------------------:|----------------:|------------------:|------------:|--------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |        0.2505 |          0.6941 |          0.237  |            0.6667 |          0.2409 |            0.6746 |      0.249  |        0.6912 |        0.2362 |          0.6653 |         0.2304 |           0.6507 |
|   2016 |     201 |        0.2393 |          0.6767 |          0.2202 |            0.6357 |          0.2275 |            0.6524 |      0.2314 |        0.6609 |        0.2215 |          0.6381 |         0.1872 |           0.5608 |
|   2017 |     201 |        0.2503 |          0.6937 |          0.2242 |            0.6389 |          0.2333 |            0.6594 |      0.2381 |        0.6686 |        0.2199 |          0.6297 |         0.2101 |           0.6081 |
|   2018 |     201 |        0.2441 |          0.6814 |          0.2355 |            0.6647 |          0.2411 |            0.6752 |      0.2393 |        0.6714 |        0.236  |          0.6658 |         0.2405 |           0.6746 |
|   2019 |     201 |        0.2455 |          0.6866 |          0.2278 |            0.6495 |          0.233  |            0.6613 |      0.2335 |        0.662  |        0.2256 |          0.6444 |         0.2227 |           0.6377 |
|   2020 |     169 |        0.2488 |          0.6938 |          0.2052 |            0.6012 |          0.2171 |            0.6288 |      0.2211 |        0.6363 |        0.1996 |          0.5885 |         0.1829 |           0.5489 |
|   2021 |     201 |        0.2485 |          0.6901 |          0.1872 |            0.5582 |          0.2066 |            0.6039 |      0.2148 |        0.6202 |        0.1816 |          0.5443 |         0.1677 |           0.5113 |
|   2022 |     201 |        0.2434 |          0.68   |          0.2025 |            0.591  |          0.2204 |            0.6325 |      0.218  |        0.627  |        0.2046 |          0.595  |         0.1903 |           0.5647 |
|   2023 |     213 |        0.2446 |          0.6847 |          0.2175 |            0.6292 |          0.2285 |            0.6521 |      0.2174 |        0.629  |        0.218  |          0.63   |         0.1976 |           0.5844 |
|   2024 |     213 |        0.2419 |          0.6792 |          0.2234 |            0.6408 |          0.2296 |            0.6542 |      0.2193 |        0.6319 |        0.2231 |          0.6407 |         0.221  |           0.6364 |
|   2025 |     213 |        0.2453 |          0.686  |          0.2293 |            0.6526 |          0.235  |            0.6651 |      0.2293 |        0.6525 |        0.2277 |          0.6493 |         0.2313 |           0.6606 |

## Reliability (blend, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   8 |       0.167 |      0     |
| (0.2, 0.3] |  76 |       0.262 |      0.171 |
| (0.3, 0.4] | 214 |       0.355 |      0.343 |
| (0.4, 0.5] | 412 |       0.454 |      0.41  |
| (0.5, 0.6] | 517 |       0.55  |      0.544 |
| (0.6, 0.7] | 522 |       0.648 |      0.672 |
| (0.7, 0.8] | 357 |       0.743 |      0.745 |
| (0.8, 0.9] | 104 |       0.836 |      0.837 |
| (0.9, 1.0] |   5 |       0.909 |      1     |

## Upcoming round — all models

| round    | date                | venue                           | home                          | away                       |   p_home_elo |   p_home_poisson |   p_home_gbm |   p_home_blend |   exp_margin_home |   exp_total_points |
|:---------|:--------------------|:--------------------------------|:------------------------------|:---------------------------|-------------:|-----------------:|-------------:|---------------:|------------------:|-------------------:|
| Round 27 | 2026-09-03 19:50:00 | Accor Stadium                   | Canterbury-Bankstown Bulldogs | Brisbane Broncos           |       0.6627 |           0.5244 |       0.6113 |         0.6425 |               1   |               45.8 |
| Round 27 | 2026-09-04 18:00:00 | Cbus Super Stadium              | Gold Coast Titans             | Dolphins                   |       0.2648 |           0.4263 |       0.3804 |         0.2221 |              -3.1 |               49   |
| Round 27 | 2026-09-04 20:00:00 | Allianz Stadium                 | South Sydney Rabbitohs        | Sydney Roosters            |       0.452  |           0.4997 |       0.4585 |         0.4707 |               0.2 |               48.3 |
| Round 27 | 2026-09-05 15:00:00 | Go Media Stadium                | New Zealand Warriors          | Manly-Warringah Sea Eagles |       0.7138 |           0.5309 |       0.7264 |         0.6643 |               1.4 |               46   |
| Round 27 | 2026-09-05 17:30:00 | Queensland Country Bank Stadium | North Queensland Cowboys      | Canberra Raiders           |       0.6136 |           0.5308 |       0.5698 |         0.5871 |               1.4 |               47.9 |
| Round 27 | 2026-09-05 19:35:00 | Ocean Protect Stadium           | Cronulla-Sutherland Sharks    | Melbourne Storm            |       0.6275 |           0.5531 |       0.6399 |         0.5996 |               2.2 |               47.9 |
| Round 27 | 2026-09-06 14:00:00 | WIN Stadium                     | St George Illawarra Dragons   | Parramatta Eels            |       0.454  |           0.4763 |       0.4625 |         0.4169 |              -1   |               48   |
| Round 27 | 2026-09-06 16:05:00 | CommBank Stadium                | Penrith Panthers              | Wests Tigers               |       0.8442 |           0.6946 |       0.7611 |         0.8707 |               8.3 |               48.3 |

_Margin/total expectations come from the tier-2 Monte Carlo; the blend is a logistic stack of Elo+Poisson with weights learned on 2010–2014 only. GBM is reported but not blended (no pre-2015 out-of-sample output to learn a weight from) — revisit when lineup/weather features land in Phase 5._