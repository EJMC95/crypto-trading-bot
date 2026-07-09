#!/usr/bin/env python3
"""
venues/symbol_map.py — fleet (HL-style) symbol ↔ Lighter symbol + size math.

Verified against the LIVE Lighter mainnet market list 2026-07-09 (215 markets,
scripts/lighter_day1.py; full dump in docs/lighter.md). Two remap classes:

  * HL k-prefixed coins are 1000-unit denominations; Lighter spells the same
    thing with a 1000 prefix: kBONK ↔ 1000BONK, kSHIB ↔ 1000SHIB. Size is 1:1
    (both sides already count thousands).
  * HL PEPE is a RAW-unit market but Lighter only lists 1000PEPE, so 1 Lighter
    unit = 1000 HL units: lighter_size = hl_size * 0.001 (and mult back on
    the way out).

NOT listed on Lighter (2026-07-09): INJ, ATOM, ORDI, TON (from the pilots'
33-coin universe) — bots simply skip them in lighter modes and log it once.
NOTE the Cowork day-1 excerpt had ADA/HYPE/BLUR unlisted: WRONG for ADA and
HYPE (both live, their API fetch truncated); right for BLUR and ATOM.
"""
from __future__ import annotations

# fleet symbol -> (lighter symbol, size multiplier fleet->lighter)
_EXPLICIT = {
    "kBONK": ("1000BONK", 1.0),
    "kSHIB": ("1000SHIB", 1.0),
    "kPEPE": ("1000PEPE", 1.0),
    "kFLOKI": ("1000FLOKI", 1.0),
    "PEPE": ("1000PEPE", 0.001),
    "SHIB": ("1000SHIB", 0.001),
    "BONK": ("1000BONK", 0.001),
    "FLOKI": ("1000FLOKI", 0.001),
}


def to_lighter(coin: str) -> tuple[str, float]:
    """fleet symbol -> (lighter_symbol, size_mult). Unknown coins map to
    themselves 1:1 — listing is checked against the live market list, not here."""
    return _EXPLICIT.get(coin, (coin, 1.0))


def from_lighter(symbol: str) -> tuple[str, float]:
    """lighter symbol -> (fleet_symbol, size_mult lighter->fleet). The k-form
    wins for 1000-markets because that is what the fleet universes use."""
    if symbol.startswith("1000"):
        return "k" + symbol[4:], 1.0
    return symbol, 1.0
