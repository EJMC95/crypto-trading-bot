# Phase 1 report — Elo walk-forward backtest

_Generated 2026-07-07. Matches replayed: 4712 (2003-03-14 → 2026-07-05). Draws score 0.5; log loss uses half-credit form._

## Fitted parameters (grid-searched on 2006–2014 predictions only)

- K = 10.0, home advantage = 60.0 Elo (≈ 2.4 points), pre-season regression = 33%, logistic scale = 400.0, MOV cap = 3.0

## Overall 2015–2025 (Brier / log loss)

| model | all eval games | odds-matched subset |
|---|---|---|
| naive | 0.2456 / 0.6859 | 0.2457 / 0.6861 |
| elo | 0.2186 / 0.6287 | 0.2185 / 0.6285 |
| elo_cal | 0.2194 / 0.6304 | 0.2193 / 0.6303 |
| market | 0.2075 / 0.6036 | 0.2075 / 0.6036 |

_Market coverage: 98.1% of eval games have a de-vigged closing/avg price (aussportsbetting file ends 2025-08 in the current capture)._

## Per-season

|   year |   games |   brier_elo |   logloss_elo |   brier_elo_cal |   logloss_elo_cal |   brier_naive |   logloss_naive |   brier_market |   logloss_market |
|-------:|--------:|------------:|--------------:|----------------:|------------------:|--------------:|----------------:|---------------:|-----------------:|
|   2015 |     201 |      0.2368 |        0.6666 |          0.237  |            0.6667 |        0.2505 |          0.6941 |         0.2304 |           0.6507 |
|   2016 |     201 |      0.2198 |        0.6347 |          0.2202 |            0.6357 |        0.2393 |          0.6767 |         0.1872 |           0.5608 |
|   2017 |     201 |      0.2232 |        0.6366 |          0.2242 |            0.6389 |        0.2503 |          0.6937 |         0.2101 |           0.6081 |
|   2018 |     201 |      0.2359 |        0.6658 |          0.2355 |            0.6647 |        0.2441 |          0.6814 |         0.2405 |           0.6746 |
|   2019 |     201 |      0.2274 |        0.6487 |          0.2278 |            0.6495 |        0.2455 |          0.6866 |         0.2227 |           0.6377 |
|   2020 |     169 |      0.2028 |        0.5956 |          0.2052 |            0.6012 |        0.2488 |          0.6938 |         0.1829 |           0.5489 |
|   2021 |     201 |      0.1841 |        0.5505 |          0.1872 |            0.5582 |        0.2485 |          0.6901 |         0.1677 |           0.5113 |
|   2022 |     201 |      0.2014 |        0.5878 |          0.2025 |            0.591  |        0.2434 |          0.68   |         0.1903 |           0.5647 |
|   2023 |     213 |      0.2169 |        0.6281 |          0.2175 |            0.6292 |        0.2446 |          0.6847 |         0.1976 |           0.5844 |
|   2024 |     213 |      0.2234 |        0.6412 |          0.2234 |            0.6408 |        0.2419 |          0.6792 |         0.221  |           0.6364 |
|   2025 |     213 |      0.2291 |        0.6522 |          0.2293 |            0.6526 |        0.2453 |          0.686  |         0.2313 |           0.6606 |

## Reliability (calibrated Elo, 2015–2025)

| bin        |   n |   mean_pred |   mean_obs |
|:-----------|----:|------------:|-----------:|
| (0.1, 0.2] |   3 |       0.179 |      0     |
| (0.2, 0.3] |  38 |       0.272 |      0.158 |
| (0.3, 0.4] | 162 |       0.36  |      0.29  |
| (0.4, 0.5] | 381 |       0.455 |      0.377 |
| (0.5, 0.6] | 597 |       0.551 |      0.534 |
| (0.6, 0.7] | 605 |       0.649 |      0.653 |
| (0.7, 0.8] | 350 |       0.742 |      0.763 |
| (0.8, 0.9] |  78 |       0.833 |      0.859 |
| (0.9, 1.0] |   1 |       0.918 |      1     |

## Current ratings

|    | team_id   |    elo | team                          |
|---:|:----------|-------:|:------------------------------|
|  1 | PEN       | 1642.7 | Penrith Panthers              |
|  2 | SYD       | 1586   | Sydney Roosters               |
|  3 | DOL       | 1573.5 | Dolphins                      |
|  4 | CRO       | 1563.9 | Cronulla-Sutherland Sharks    |
|  5 | NZW       | 1560.9 | New Zealand Warriors          |
|  6 | MAN       | 1542.5 | Manly-Warringah Sea Eagles    |
|  7 | MEL       | 1539.3 | Melbourne Storm               |
|  8 | NQL       | 1505.4 | North Queensland Cowboys      |
|  9 | NEW       | 1488.8 | Newcastle Knights             |
| 10 | SOU       | 1488   | South Sydney Rabbitohs        |
| 11 | CBY       | 1480.2 | Canterbury-Bankstown Bulldogs |
| 12 | CAN       | 1466.4 | Canberra Raiders              |
| 13 | BRI       | 1461.7 | Brisbane Broncos              |
| 14 | PAR       | 1431.9 | Parramatta Eels               |
| 15 | WST       | 1420.9 | Wests Tigers                  |
| 16 | GLD       | 1371.6 | Gold Coast Titans             |
| 17 | SGI       | 1358.1 | St George Illawarra Dragons   |

## Upcoming round

| round    | date                | venue                       | home                          | away                       |   elo_home |   elo_away |   p_home_raw |   p_home_cal |
|:---------|:--------------------|:----------------------------|:------------------------------|:---------------------------|-----------:|-----------:|-------------:|-------------:|
| Round 19 | 2026-07-10 20:00:00 | Campbelltown Sports Stadium | Wests Tigers                  | New Zealand Warriors       |     1420.9 |     1560.9 |       0.3869 |       0.4053 |
| Round 19 | 2026-07-11 15:00:00 | Kayo Stadium                | Dolphins                      | Cronulla-Sutherland Sharks |     1573.5 |     1563.9 |       0.5989 |       0.5974 |
| Round 19 | 2026-07-11 17:30:00 | Accor Stadium               | Canterbury-Bankstown Bulldogs | Canberra Raiders           |     1480.2 |     1466.4 |       0.6046 |       0.6026 |
| Round 19 | 2026-07-11 19:35:00 | Allianz Stadium             | Sydney Roosters               | Parramatta Eels            |     1586   |     1431.9 |       0.7742 |       0.7587 |
| Round 19 | 2026-07-12 14:00:00 | Accor Stadium               | South Sydney Rabbitohs        | Newcastle Knights          |     1488   |     1488.8 |       0.5844 |       0.5844 |
| Round 19 | 2026-07-12 16:05:00 | 4 Pines Park                | Manly-Warringah Sea Eagles    | North Queensland Cowboys   |     1542.5 |     1505.4 |       0.6362 |       0.6312 |
| Round 19 | 2026-07-12 18:15:00 | AAMI Park                   | Melbourne Storm               | Gold Coast Titans          |     1539.3 |     1371.6 |       0.7877 |       0.7716 |