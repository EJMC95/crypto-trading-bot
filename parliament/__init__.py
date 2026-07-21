#!/usr/bin/env python3
"""
parliament/ — 🏛️ The Parliament: a six-layer, self-evolving Lighter-only
shadow fleet, named for the last eight Prime Ministers of Australia
(operator request, 2026-07-21).

THE ROSTER (who is what)
  Layer 4 — six trading bots, each a $1,000 SHADOW book on Lighter mainnet
  data (rows `pm-<name>-lshadow`; fills modelled, orders NEVER sent):
    pm-albanese  🏗️  Trend Rider        — multi-TF trend alignment + momentum
    pm-morrison  📣  Breakout Chaser    — Donchian breakout + volume surge
    pm-turnbull  💼  Mean Reverter      — fades RSI stretch in quiet regimes
    pm-abbott    🥊  Momentum Scalper   — short-hold burst scalps, tight stops
    pm-rudd      🌏  Funding Diplomat   — positions PAID by funding extremes
    pm-gillard   🤝  Dislocation Fader  — fades mark-vs-index premium stretch
  Layer 2+3 — KEATING 🔭, the intelligence engine: 10 Lighter-native scanners
  (parliament/scanners.py) + the 5-model ML ensemble (parliament/ml.py).
  Layer 6 — HOWARD 🧠, the ecosystem brain (parliament/brain.py): shared
  memory, cross-bot intelligence, health monitoring — the longest-serving PM
  of the eight watches everything.
  Layer 5 — six TUNERS (parliament/tuners.py), one per bot, named
  `<bot>-tuner`: bounded, TTL'd, auto-reverting parameter walks — the same
  restrict-first growth-rail doctrine as lighter_scout_tuner.

WHY IT LOOKS THE WAY IT LOOKS (fleet doctrine, not this package's whims)
  * LIGHTER-ONLY: every byte of market data comes from Lighter's own REST/WS
    (mainnet.zklighter.elliot.ai). No foreign venue, no foreign reference —
    audit_venue_purity.py enforces this on shipped code.
  * SHADOW-FIRST: $1,000 books, no top-ups, paper until the go-live gate
    (30d WR > 55% AND maxDD < 15%) — same bar every fleet bot faces.
  * FAIL-SAFE: no DATABASE_URL -> publishes skip; no network -> bots idle;
    cold ML -> neutral 0.5; stale bus payload -> neutral. Nothing here can
    turn a data failure into a position.
  * CONSUMES the fleet bus like every other citizen: brain stake-mults at
    entry (fleet_bus.stake_multiplier), the L2 long-budget veto
    (fleet_bus.long_entries_blocked), and the Lighter Scout's venue-stress
    premium (bot_state `lighter-market`) as an entry pause — the same
    |prem| med >= 15bps bar the Ticket Taker uses.
  * PUBLISHES like every other citizen: bot_pnl_store.publish per book,
    publish_paper_trade per close (tagged `<side>-<lens>_<exit>` so
    bot_learn grades each lens), save_state for restart-proof equity
    curves, and bot_state keys `parliament` (Howard's vitals) +
    `parliament-tuning` (active tuner levers) with updated+ttl_sec.

TRANSPORT
  All six layers run as asyncio tasks in ONE process (parliament_main.py).
  The pub/sub bus is in-process by default; if REDIS_URL is set and the
  `redis` wheel is importable the same topics are ALSO mirrored to Redis
  pub/sub so out-of-process consumers can listen. The ecosystem database is
  SQLite (stdlib sqlite3) on the persist volume when present — and Howard
  ingests the WIDER fleet's paper_trades ledger from Postgres into it, so
  the ML ensemble learns from every bot already publishing, not just the six
  books here.
"""

# Bot roster: bot base-id -> (display, strategy key). The -lshadow suffix is
# appended at publish time (the fleet's venue-variant convention).
PM_BOTS = {
    "pm-albanese": ("🏗️ Albanese — Trend Rider", "trend"),
    "pm-morrison": ("📣 Morrison — Breakout Chaser", "breakout"),
    "pm-turnbull": ("💼 Turnbull — Mean Reverter", "meanrev"),
    "pm-abbott":   ("🥊 Abbott — Momentum Scalper", "scalp"),
    "pm-rudd":     ("🌏 Rudd — Funding Diplomat", "funding"),
    "pm-gillard":  ("🤝 Gillard — Dislocation Fader", "disloc"),
}

SHADOW_SUFFIX = "-lshadow"
START_EQUITY = 1000.0          # fleet rule: $1,000 per book, no top-ups

# bot_state keys Howard publishes (freshness contract: updated + ttl_sec).
STATE_KEY = "parliament"
TUNING_STATE_KEY = "parliament-tuning"
