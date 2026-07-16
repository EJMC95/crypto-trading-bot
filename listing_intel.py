#!/usr/bin/env python3
"""
listing_intel.py — external intelligence for the listing sniper. Keyless, free.

WHAT IT KNOWS (two axes):
  1. ANNOUNCED — is this symbol in a major exchange's official new-listing
     announcement feed (Binance / Bybit / KuCoin / Upbit)? A listing that a
     major pre-announced is a categorically better ticket than an unannounced
     micro-cap appearing on exchange #74.
  2. FOOTPRINT — does the coin exist on CoinGecko at all (page / market-cap
     rank)? Separates real projects from the ALABON/TERON-class junk that made
     up 46 of the sniper's first 52 closed trades (the ANSEM jackpot, by
     contrast, had a CoinGecko rank of ~206 at snipe time).

HOW IT'S USED (deliberately conservative, mirrors the pulse policy):
  Stake modulation ONLY — never entry creation, never stake increases.
    announced or has-footprint  -> 1.0x stake (normal)
    provably unknown everywhere -> 0.25x stake (quarter-ticket lottery junk) [2026-07-07, was 0.5]
    intel unavailable / errors  -> 1.0x (never punish for our own API failures)
  Every position is tagged so the ledger accumulates evidence; harder gating
  (or skip-entirely) gets promoted only if the tags prove out.

All fetchers are guarded and cached; a dead source degrades to neutral.
"""
import json
import re
import time
import urllib.request

UA = {"User-Agent": "Mozilla/5.0 (listing-intel; dry-run research)"}
_PAREN = re.compile(r"\(([A-Z0-9]{2,12})\)")

# module caches
_announced = {}          # SYMBOL -> {"src": str, "seen": epoch}
_announced_at = 0.0
_footprint_cache = {}    # SYMBOL -> dict|None (None = confirmed absent)
ANNOUNCE_TTL = 300       # refresh announcement feeds every 5 min
ANNOUNCE_WINDOW = 96 * 3600   # a listing counts as "announced" for 4 days


def _get(url, timeout=12):
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8", "replace"))


def _titles_binance():
    d = _get("https://www.binance.com/bapi/composite/v1/public/cms/article/list/query"
             "?type=1&pageNo=1&pageSize=20&catalogId=48")
    arts = (d.get("data", {}).get("catalogs") or [{}])[0].get("articles") or []
    return [(a.get("title", ""), "binance") for a in arts]


def _titles_bybit():
    d = _get("https://api.bybit.com/v5/announcements/index?locale=en-US&type=new_crypto&limit=20")
    return [(x.get("title", ""), "bybit") for x in d.get("result", {}).get("list") or []]


def _titles_kucoin():
    d = _get("https://api.kucoin.com/api/v3/announcements?annType=new-listings&pageSize=20")
    return [(x.get("annTitle", ""), "kucoin") for x in d.get("data", {}).get("items") or []]


def _titles_upbit():
    d = _get("https://api-manager.upbit.com/api/v1/announcements?os=web&page=1&per_page=20&category=trade")
    return [(x.get("title", ""), "upbit") for x in d.get("data", {}).get("notices") or []]


def refresh_announced(now=None):
    """Refresh the announced-symbol set from all feeds (throttled). Never raises."""
    global _announced_at
    now = now or time.time()
    if now - _announced_at < ANNOUNCE_TTL:
        return _announced
    _announced_at = now
    titles = []
    for fn in (_titles_binance, _titles_bybit, _titles_kucoin, _titles_upbit):
        try:
            titles.extend(fn())
        except Exception:
            continue                       # dead feed -> just skip this cycle
    for title, src in titles:
        # tickers in parens: "World Premiere: Cap (CAP) Listed", "(MPLX, NEX ...)"
        for grp in _PAREN.findall(title or ""):
            for sym in re.split(r"[,\s/]+", grp):
                if 2 <= len(sym) <= 12 and sym.isalnum() and not sym.isdigit():
                    _announced.setdefault(sym.upper(), {"src": src, "seen": now})
        # Bybit derivative style: "New listing: HIMSUSDT Perpetual"
        m = re.search(r"[Nn]ew listing:?\s+([A-Z0-9]{2,12})(?:USDT|USDC|USD)\b", title or "")
        if m:
            _announced.setdefault(m.group(1).upper(), {"src": src, "seen": now})
    # age out stale entries
    for sym in [s for s, v in _announced.items() if now - v["seen"] > ANNOUNCE_WINDOW]:
        _announced.pop(sym, None)
    return _announced


def footprint(symbol):
    """CoinGecko existence check. Returns dict (may be empty) if the coin has a
    page, None if confirmed absent, or raises-never/'?' on API failure."""
    sym = symbol.upper()
    if sym in _footprint_cache:
        return _footprint_cache[sym]
    try:
        d = _get(f"https://api.coingecko.com/api/v3/search?query={sym}", timeout=10)
        hit = next((c for c in d.get("coins", [])
                    if str(c.get("symbol", "")).upper() == sym), None)
        _footprint_cache[sym] = ({"id": hit.get("id"), "rank": hit.get("market_cap_rank")}
                                 if hit else None)
    except Exception:
        return "?"                          # API failure — do NOT cache, stay neutral
    return _footprint_cache[sym]


def classify(pair_symbol, now=None):
    """('announced'|'footprint'|'junk'|'unknown', stake_mult, detail) for a
    market symbol like 'ANSEM/USDT'. Fail-safe neutral."""
    try:
        base = str(pair_symbol).split("/")[0].upper()
        # [2026-07-16 AUDIT FIX] the unconditional K-strip mangled REAL
        # K-symbols (KAVA→AVA, KAITO→AITO, KERNEL→ERNEL): wrong intel class,
        # wrong stake, ghost-skips of genuine listings. Look the RAW symbol
        # up first; the stripped variant (kSHIB-style 1000x prefixes) is only
        # a fallback when the raw one draws a complete blank.
        candidates = [base]
        stripped = re.sub(r"^K(?=[A-Z]{3,})", "", base)
        if stripped != base:
            candidates.append(stripped)
        for b in candidates:
            ann = refresh_announced(now).get(b)
            if ann:
                return "announced", 1.0, f"pre-announced on {ann['src']}"
            fp = footprint(b)
            if fp == "?":
                return "unknown", 1.0, "intel unavailable (neutral)"
            if fp:
                rank = fp.get("rank")
                return "footprint", 1.0, f"coingecko:{fp.get('id')}" + (f" rank {rank}" if rank else "")
        return "junk", 0.25, "no announcement, no coingecko page"  # [2026-07-07] was 0.5 — the junk class is 80% of tickets and dies by delisting
    except Exception:
        return "unknown", 1.0, "intel error (neutral)"


if __name__ == "__main__":
    ann = refresh_announced()
    print(f"announced symbols ({len(ann)}): {sorted(ann)[:20]}")
    for s in ("ANSEM/USDT", "ALABON/USDT", "BTC/USDT"):
        print(s, "->", classify(s))
