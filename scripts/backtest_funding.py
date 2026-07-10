#!/usr/bin/env python3
"""
scripts/backtest_funding.py — does Lighter's ZERO perp fee flip the funding-carry
harvester (funding_carry_bot.py, "Yield Harvester") from its 0W/28L live record
to net-positive?

WHY: the live bot's loss root-cause (see the EXIT REBUILD comment in
funding_carry_bot.py, and memory trail-blazer-no-durable-edge) is FRICTION, not
signal — a 29bps round-trip (HL taker 4.5bps + hedge 10bps, both charged at open
AND close) needs ~64h at 40% APR just to break even, but spiky alt funding
mean-reverts in hours. So the fee is the whole game. Lighter charges ZERO perp
fee. This backtest quantifies exactly how far that moves the needle.

METHOD (honest, favourable-case — same modelling caveats as the live bot):
  * Pulls REAL hourly funding history from Hyperliquid mainnet (public, no keys)
    for a hot-funding universe, paginated to cover the full window.
  * Replays the EXACT live logic on a merged hourly grid: PERSIST_H entry gate,
    ENTER_APR / EXIT_APR, flip-grace close, fee-payback decay close, MAX_HOLD,
    bleed stop, and the MAX_POSITIONS portfolio cap ranked by |funding|.
  * Delta-neutral => price P&L = 0; we capture funding minus fees only (the
    bot's model). Funding accrues at the LIVE hourly rate with position sign, so
    a rate that flips against us costs us, exactly as live.
  * Sweeps the fee model from HL-today down to Lighter zero-fee and reports the
    BREAK-EVEN round-trip friction — the single number that decides this bot.

Fee legs (per side of the round trip, fraction of notional):
  perp_fee  — the perp taker fill. HL=4.5bps. Lighter=0.
  hedge_cost— the delta-neutral hedge leg (spot on another venue, or a second
              perp). Independent of Lighter's perp fee.
"""
import json
import os
import time
import urllib.request

CACHE = os.path.join(os.path.dirname(__file__), ".funding_cache.json")

# ---- exact live-bot params (funding_carry_bot.py) --------------------------
ENTER_APR = 0.40
EXIT_APR = 0.15
MAX_HOLD_H = 14 * 24
PERSIST_H = 6.0
FLIP_GRACE_H = 1.0
FEE_PAYBACK_MARGIN = 0.10
BLEED_STOP_FRAC = 0.02
NOTIONAL = 300.0
MAX_POSITIONS = 8
HOURS_PER_YEAR = 24 * 365

FETCH_DAYS = 180
HL = "https://api.hyperliquid.xyz/info"

# Hot-funding-prone liquid universe (majors rarely trip 40% APR; the carry lives
# in alts/memes/newer perps whose funding spikes). Same names the live bot scans.
COINS = ["BTC", "ETH", "SOL", "BNB", "XRP", "DOGE", "AVAX", "LINK", "ADA", "LTC",
         "DOT", "NEAR", "SUI", "HYPE", "AAVE", "WIF", "JUP", "OP", "ARB", "TIA",
         "PEPE", "ENA", "ORDI", "TAO", "SEI", "APT", "INJ", "FTM", "RUNE", "kBONK",
         "kSHIB", "MEME", "ME", "MINA", "STX", "GALA", "JTO", "PYTH", "W", "ZRO"]

# Fee scenarios: (label, perp_fee_per_side, hedge_cost_per_side)
SCENARIOS = [
    ("HL live today (current bot)",      0.00045, 0.0010),   # 29.0 bps round trip
    ("Lighter perp + CEX spot hedge",    0.00000, 0.0010),   # 20.0 bps (perp free)
    ("Lighter perp + Lighter-perp hedge",0.00000, 0.00015),  #  3.0 bps (both ~free, spread only)
    ("Lighter idealized (frictionless)", 0.00000, 0.00000),  #  0.0 bps (upper bound)
]


def _post(payload, tries=5):
    """POST with retry+backoff — HL rate-limits fundingHistory with HTTP 500."""
    body = json.dumps(payload).encode()
    for i in range(tries):
        try:
            req = urllib.request.Request(HL, data=body,
                                         headers={"Content-Type": "application/json"})
            return json.loads(urllib.request.urlopen(req, timeout=30).read())
        except Exception:
            if i == tries - 1:
                return None
            time.sleep(0.6 * (i + 1))   # linear backoff on transient 500s
    return None


def funding_history(coin):
    """Paginated hourly funding history over FETCH_DAYS (HL caps 500 rows/call).
    Retries transient errors instead of truncating the coin. Returns [(ts,rate)]."""
    out, seen = [], set()
    cursor = int((time.time() - FETCH_DAYS * 86400) * 1000)
    end = int(time.time() * 1000)
    for _ in range(60):  # 60*500 rows >> 180d hourly
        rows = _post({"type": "fundingHistory", "coin": coin,
                      "startTime": cursor, "endTime": end})
        if not rows:
            break
        new = 0
        for r in rows:
            t = int(r["time"])
            if t in seen:
                continue
            seen.add(t)
            out.append((t, float(r["fundingRate"])))
            new += 1
        last = max(int(r["time"]) for r in rows)
        if new == 0 or last <= cursor:
            break
        cursor = last + 1
        time.sleep(0.3)   # be polite between pages to avoid rate-limit 500s
    out.sort()
    return out


def simulate(series, perp_fee, hedge_cost, enter_apr=ENTER_APR, exit_apr=EXIT_APR):
    """Replay the live bot on a merged hourly grid. `series` is {coin: {ts:rate}}.
    enter_apr/exit_apr are tunable (the entry gate exists to avoid fee bleed, so
    zero-fee venues can afford a lower one). Returns
    (n_closed, n_wins, realized_$, gross_funding_$, total_fees_$)."""
    open_cost = perp_fee + hedge_cost           # charged at open and again at close
    # Merged, sorted hourly timeline across all coins.
    grid = sorted({t for m in series.values() for t in m})
    positions = {}     # coin -> dict(side, opened_ts, accrued, fees)
    hot_since = {}     # coin -> ts first >= ENTER_APR (persistence clock)
    realized = n_closed = n_wins = 0
    gross = fees_paid = 0.0
    prev_t = None
    for t in grid:
        dt_h = 0.0 if prev_t is None else (t - prev_t) / 3.6e6
        prev_t = t
        rates = {c: m[t] for c, m in series.items() if t in m}

        # ---- manage open carries ----
        for coin in list(positions):
            rate = rates.get(coin)
            if rate is None:
                continue
            apr = rate * HOURS_PER_YEAR
            pos = positions[coin]
            sign = -1.0 if pos["side"] == "short_perp" else 1.0
            accr = (-sign) * rate * dt_h * NOTIONAL
            pos["accrued"] += accr
            gross += accr
            held_h = (t - pos["opened_ts"]) / 3.6e6

            flipped_now = (pos["side"] == "short_perp" and apr < 0) or \
                          (pos["side"] == "long_perp" and apr > 0)
            if flipped_now:
                pos.setdefault("flipped_since", t)
            else:
                pos.pop("flipped_since", None)
            close_fee = open_cost * NOTIONAL
            net_if_closed = pos["accrued"] - (pos["fees"] + close_fee)
            flipped = flipped_now and (t - pos["flipped_since"]) / 3.6e6 >= FLIP_GRACE_H
            decayed = abs(apr) < exit_apr and net_if_closed >= FEE_PAYBACK_MARGIN
            expired = held_h >= MAX_HOLD_H
            bleeding = net_if_closed <= -BLEED_STOP_FRAC * NOTIONAL
            if not (flipped or decayed or expired or bleeding):
                continue
            pos["fees"] += close_fee
            fees_paid += close_fee
            pnl = pos["accrued"] - pos["fees"]
            realized += pnl
            n_closed += 1
            n_wins += 1 if pnl > 0 else 0
            del positions[coin]

        # ---- persistence clock ----
        for c, rate in rates.items():
            if abs(rate * HOURS_PER_YEAR) >= enter_apr:
                hot_since.setdefault(c, t)
            else:
                hot_since.pop(c, None)

        # ---- scan for new carries (ranked by |funding|, respect cap) ----
        if len(positions) < MAX_POSITIONS:
            cand = sorted(
                ((c, rate) for c, rate in rates.items()
                 if c not in positions
                 and abs(rate * HOURS_PER_YEAR) >= enter_apr
                 and (t - hot_since.get(c, t)) / 3.6e6 >= PERSIST_H),
                key=lambda cr: -abs(cr[1]))
            for coin, rate in cand[:MAX_POSITIONS - len(positions)]:
                oc = open_cost * NOTIONAL
                positions[coin] = {"side": "short_perp" if rate > 0 else "long_perp",
                                   "opened_ts": t, "accrued": 0.0, "fees": oc}
                fees_paid += oc

    return n_closed, n_wins, realized, gross, fees_paid


def breakeven_rt_bps(series):
    """Binary-search the round-trip friction (bps) at which net realized = 0,
    holding the hedge/perp split irrelevant (we vary total per-side symmetrically)."""
    def net(rt_bps):
        per_side = (rt_bps / 1e4) / 2.0
        _, _, realized, _, _ = simulate(series, 0.0, per_side)  # all friction in hedge leg
        return realized
    lo, hi = 0.0, 60.0
    if net(lo) < 0:
        return 0.0  # loses even frictionless -> no fee level saves it
    if net(hi) > 0:
        return None  # profitable even at 60bps
    for _ in range(28):
        mid = (lo + hi) / 2
        if net(mid) > 0:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2


def main():
    print(f"Funding-carry backtest — real HL hourly funding, {FETCH_DAYS}d, "
          f"{len(COINS)} coins, ${NOTIONAL:.0f} x max {MAX_POSITIONS}\n"
          f"entry>={ENTER_APR:.0%} APR persist {PERSIST_H:.0f}h, exit<{EXIT_APR:.0%} "
          f"(fee-payback), max-hold {MAX_HOLD_H//24}d\n")
    # Cache the fetched funding so threshold/fee iteration doesn't re-hit the API.
    # Delete scripts/.funding_cache.json (or pass --refresh) to re-pull.
    import sys
    cache = {}
    if os.path.exists(CACHE) and "--refresh" not in sys.argv:
        try:
            raw = json.load(open(CACHE))
            cache = {c: {int(t): r for t, r in m.items()} for c, m in raw.items()}
            print(f"(loaded {len(cache)} coins from cache; --refresh to re-pull)\n")
        except Exception:
            cache = {}
    series = {}
    hot_coins = 0
    for coin in COINS:
        if coin in cache and cache[coin]:
            series[coin] = cache[coin]
        else:
            h = funding_history(coin)
            if not h:
                continue
            series[coin] = {t: r for t, r in h}
        hotp = sum(1 for r in series[coin].values() if abs(r * HOURS_PER_YEAR) >= ENTER_APR)
        if hotp:
            hot_coins += 1
        print(f"  {coin:>6}: {len(series[coin]):>4} hrs  {hotp:>3} hot (>={ENTER_APR:.0%})")
    try:
        json.dump({c: {str(t): r for t, r in m.items()} for c, m in series.items()},
                  open(CACHE, "w"))
    except Exception:
        pass
    print(f"\n{hot_coins}/{len(series)} coins had funding >= {ENTER_APR:.0%} APR at "
          f"some point.\n")

    print(f"{'fee scenario':<34} {'RTbps':>6} {'trades':>7} {'W':>4} {'L':>4} "
          f"{'win%':>5} {'gross$':>9} {'fees$':>9} {'net$':>9} {'net%cap':>8}")
    # Capital honestly tied up: each 1x delta-neutral carry uses ~2*NOTIONAL
    # (perp margin + hedge). Report net vs that, and vs the $1000 account.
    cap = 2 * NOTIONAL * MAX_POSITIONS
    for label, perp, hedge in SCENARIOS:
        n, w, realized, gross, fees = simulate(series, perp, hedge)
        rt = (perp + hedge) * 2 * 1e4
        win = 100 * w / n if n else 0
        print(f"{label:<34} {rt:>6.1f} {n:>7} {w:>4} {n-w:>4} {win:>5.0f} "
              f"{gross:>9.2f} {fees:>9.2f} {realized:>9.2f} {realized/cap*100:>7.1f}%")

    # ---- robustness: is the edge broad, or one hot coin? ----
    print("\nRobustness (Lighter perp + CEX spot hedge, 20bps) — drop biggest contributor:")
    contrib = []
    for coin in series:
        one = {coin: series[coin]}
        _, _, r_one, _, _ = simulate(one, 0.0, 0.0010)
        contrib.append((r_one, coin))
    contrib.sort(reverse=True)
    top_coin = contrib[0][1] if contrib else None
    if top_coin:
        _, _, r_all, _, _ = simulate(series, 0.0, 0.0010)
        rest = {c: series[c] for c in series if c != top_coin}
        n2, w2, r_rest, _, _ = simulate(rest, 0.0, 0.0010)
        print(f"  top contributor: {top_coin} (+${contrib[0][0]:.2f} standalone)")
        print(f"  full universe net = +${r_all:.2f}  |  without {top_coin} = "
              f"+${r_rest:.2f} ({n2} trades, {100*w2/n2 if n2 else 0:.0f}% win)")
        print(f"  top 3 contributors: " +
              ", ".join(f"{c}(+${v:.0f})" for v, c in contrib[:3]))

    # ---- Lighter-specific optimization: lower the entry gate ----
    # The 40% gate exists ONLY to avoid fee bleed (fees need ~64h@40% to pay back).
    # With Lighter's near-zero fee that rationale weakens — can we harvest more by
    # entering moderate funding too? Test on the both-perp (3bps) model.
    print("\nEntry-threshold sweep — does zero-fee unlock a lower gate? (the 40% gate "
          "only exists to survive HL fee bleed)")
    print("  Tested under BOTH hedge structures so the recommendation is robust:")
    print(f"{'ENTER_APR':>10} {'EXIT_APR':>9} | {'both-perp 3bps':>22} | {'CEX-hedge 20bps':>22}")
    print(f"{'':>10} {'':>9} | {'trades':>7} {'win%':>5} {'net$':>7} | {'trades':>7} {'win%':>5} {'net$':>7}")
    for ea in (0.15, 0.20, 0.30, 0.40):
        xa = ea * (EXIT_APR / ENTER_APR)   # keep the exit/enter ratio (0.375)
        n3, w3, r3, _, _ = simulate(series, 0.0, 0.00015, enter_apr=ea, exit_apr=xa)
        n2, w2, r2, _, _ = simulate(series, 0.0, 0.0010, enter_apr=ea, exit_apr=xa)
        print(f"{ea:>9.0%} {xa:>9.1%} | {n3:>7} {100*w3/n3 if n3 else 0:>5.0f} {r3:>7.1f} | "
              f"{n2:>7} {100*w2/n2 if n2 else 0:>5.0f} {r2:>7.1f}")

    be = breakeven_rt_bps(series)
    print()
    if be is None:
        print("Break-even friction: profitable even at 60bps round-trip (signal is strong).")
    elif be <= 0:
        print("Break-even friction: NEGATIVE even frictionless — the funding signal "
              "itself loses money here; zero fees cannot save it.")
    else:
        print(f"Break-even round-trip friction: ~{be:.1f} bps.")
        print(f"  HL today = 29.0 bps ({'ABOVE' if be < 29 else 'below'} break-even -> "
              f"{'LOSS' if be < 29 else 'profit'}).")
        print(f"  Lighter perp + CEX spot hedge = 20.0 bps "
              f"({'ABOVE' if be < 20 else 'below'} -> {'LOSS' if be < 20 else 'PROFIT'}).")
        print(f"  Lighter both-perp = ~3.0 bps "
              f"({'ABOVE' if be < 3 else 'below'} -> {'LOSS' if be < 3 else 'PROFIT'}).")


if __name__ == "__main__":
    main()
