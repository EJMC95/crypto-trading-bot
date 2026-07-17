#!/usr/bin/env python3
"""
scripts/study_fundspread_basis_mixing.py — does the HL/Lighter unit MIXING in
Counterweight's ranking window (`fund_hist`) actually corrupt the L/S picks?

THE REPORTED BUG (2026-07-17, from a read-only equivalence study)
  lighter_funding_spread_bot.py builds one `fund_hist[coin]` list from TWO
  sources with DIFFERENT funding bases:
    * hl_backfill()  -> Hyperliquid `fundingHistory.fundingRate`  = HOURLY
    * live sampling  -> Lighter `funding_map()['rate']`           = 8-HOURLY
  and the rebalance means over the mixed list. The report claimed the mix ratio
  varies PER COIN ("depends on how much live coverage that coin has accumulated
  since backfill"), making it a cross-sectional corruption rather than the
  fleet-wide monotonic 8x rescale.

MEASURED VERDICTS (17 Jul 2026 — read this instead of re-testing)

  (0) IS LIGHTER'S /funding-rates `rate` SIGNED? **YES — the report's bigger
      hypothesis is REFUTED.** Live: 12 of 201 lighter rows are NEGATIVE
      (DATA -3.2e-04, TRX -4.64e-04, SOL -1.6e-05); the row schema is exactly
      ['exchange','market_id','rate','symbol'] — there is NO `direction` field
      to miss, unlike the SETTLED /api/v1/fundings series. The most-negative
      long leg fires correctly. Do not re-open.

  (1) HL IS HOURLY, LIGHTER IS 8H — both CONFIRMED, structurally not
      statistically. HL `fundingHistory` returns exactly 72 rows for a 72h
      window (1/hour). Lighter/HL rate ratio on the STABLE names is ~8
      (BTC 7.73, ETH 7.68, LINK 7.68, LTC 8.21; median 8.21). Divergent names
      (ADA -167) are real cross-venue rate divergence, NOT basis — the trap the
      17-Jul CHANGELOG explicitly warns about. So the 8x mixing is real.

  (2) THE REPORT'S PER-COIN MECHANISM IS **WRONG**. Measured against the live
      persisted state (bot_state, 2026-07-17 03:50Z): all 30 coins get a FULL
      78-row HL backfill (no coin is short-changed), so the mix is UNIFORM
      across the cross-section, not per-coin. A uniform mix is a common
      positive scalar => monotonic => ranking PRESERVED. The report's
      "freshly-backfilled coin scores 8x smaller than one with a full live
      window" needs coins to be backfilled at DIFFERENT times, which only
      happens if per-coin coverage straddles MIN_COVERAGE at a restart.

  (3) THE BUG IS CURRENTLY **INERT**. In the live state every coin's window is
      unit-PURE: the 25 Lighter-tradeable coins are 100% Lighter samples
      (93 each, 0 HL rows — the backfill has aged out of the 72h window), and
      the only 5 HL-contaminated coins (GALA/INJ/RUNE/STX/W) are exactly the
      coins that are NOT tradeable Lighter markets, so `ctx.supports()` filters
      them out of `scores` before ranking. Nothing mixed reaches a pick.

  (4) WHEN IT DOES BITE: only a COLD START (empty state) or an outage long
      enough to drop coverage under MIN_COVERAGE=36h, and only for the ~72h it
      takes the HL rows to age out. `fund_hist` is PERSISTED, and a restart
      with >=36h of coverage skips the backfill entirely — so ordinary
      redeploys do NOT re-contaminate.

  (5) **THE PROPOSED x8 FIX IS REFUTED — IT MAKES THE COLD START WORSE.**
      Cold-start replay, fidelity to the Lighter-only ranking (matched picks
      /10), swept over every viable boot hour:
        +48h : CONTROL 7.88/10  vs  FIX 5.38/10 — control closer in 16/16
               boots, fix closer in 0. Unanimous.
        +72h : 10.00 vs 10.00 — identical (HL has aged out; both == truth).
      WHY (deterministic arithmetic, not luck): a raw HL row (~1e-05) is ~8x
      SMALLER than a Lighter row (~9.6e-05), so under the shipped code the
      contaminating rows act as near-zero filler contributing only ~6% of the
      score — they dilute the score's MAGNITUDE but barely move the ranking.
      Multiplying them by 8 makes them EQUAL-weighted, handing a full 1/3 of
      the score to HYPERLIQUID's cross-section, which genuinely diverges from
      Lighter's coin by coin. UNIT-PURITY IS NOT CORRECTNESS. The honest fix is
      not a scale factor: it is to stop ranking a Lighter book on a foreign
      venue's rates at all (drop HL rows once Lighter coverage >= MIN_COVERAGE,
      or accept a 36h cold-start blackout). That is a STRATEGY change the
      factor lab cannot adjudicate — see (7).
      CAVEAT, stated: the 16 boots are drawn from ONE overlapping ~96h window,
      so they are correlated, not 16 independent samples. The DIRECTION is
      structural (the weight shift above), the magnitude is one window's.

  (6) THE FIX DOES NOT HELP THE FIRST REBALANCE EITHER. At boot the window is
      100% HL, so scaling every row by 8 is monotonic and the picks are
      IDENTICAL (measured: +0h control^fix = 5L/5S). The first rebalance ranks
      a LIGHTER book by HYPERLIQUID funding either way — a data-source
      question, not a units question.

  (7) THE DEEPER PROBLEM THIS UNCOVERS: Counterweight's edge was validated by
      backtest_xsect_factor_lab.py on the `.dirfund_cache.json` tape, which is
      **HYPERLIQUID** funding — it ranks AND accrues on HL hourly rates
      throughout. The live book ranks on LIGHTER rates and earns LIGHTER
      funding. No backtest has ever tested the live signal. This is the same
      class as the 17-Jul Funding Farmer finding ("every funding backtest ran
      on Hyperliquid"); a Lighter funding tape now exists
      (scripts/backtest_funding_lighter.py). Re-running the factor lab on
      Lighter's own tape is the 21-Jul review's call, not a patch.

  (8) **A BIGGER, ACTIVE BUG THIS STUDY FOUND — THE ACCRUAL (not the ranking).**
      lighter_funding_spread_bot.py:329 still models carry as
      `rate * notional * dt_h`, which is right only if the quote is HOURLY. On
      Lighter it is per 8h => **8x OVER-ACCRUAL**, live, right now. Commit
      31ec660 ("Funding BASIS fix") claims in its own message to have fixed
      "five bots" — it touched this file but changed ONLY the logging constant
      `H`, leaving the accrual. `funding_basis.to_hourly` is used by
      lighter_trend_bot / lighter_momentum_bot / lighter_funding_bot /
      lighter_index_bot — four, not five. lighter_family_bot.py:896
      (`- rate * sz * px * dt_h`, Lighter `funding_map` via line 789) is the
      other miss. Measured cost on Counterweight's live state (17-Jul ~04:0xZ;
      the figures drift as the book publishes — the RATIO is the point):
        published equity $1000.858 (+$0.858 "profit")
        broker.equity() 999.831 | fund_realized -0.0651 | fund_open +1.0923
        corrected        999.831 + (-0.0651/8) + (1.0923/8) = **$999.959**
      => the book's ENTIRE reported gain is the 8x artifact; it is really flat
      to slightly NEGATIVE (-$0.04) on exactly the quantity it exists to
      harvest. Ledger cross-check closes to the cent: sum(pnl_abs) -0.8730 =
      price -0.8079 + fund_realized -0.0651. Direction differs per book:
      Counterweight RECEIVES on both legs so the 8x FLATTERS it; the long-only
      family books PAY, so the 8x makes them look WORSE than reality. `accrued`
      reaches `account_value()` -> the DAILY-LOSS RAIL in both, so it is not
      cosmetic. This is the finding that matters here — the ranking bug the
      study was opened for is inert; this one is live and it is the number a
      go-live decision would read.

  (9) INCIDENTAL: lighter_market_scout.py's funding_aprs() docstring claims the
      benchmark "hyperliquid rows are hourly and are now 8x LOW". MEASURED
      FALSE: Lighter normalises ALL FOUR exchange rows to a common 8h basis
      (its HL row 1.0e-04 == 8x HL's native 1.2493e-05/hr — confirmed here and
      independently in backtest_funding_lighter.py's header). The CODE is right
      (3*365 suits every row); the COMMENT lies. Doc-only, no behaviour.

METHOD
  Real data on both sides, no synthesis: HL `fundingHistory` (hourly) + the
  bot's OWN persisted Lighter samples pulled from bot_state. Simulate a cold
  boot at B, then replay the bot's exact scoring (`sum(rs)/len(rs)` over
  t >= t0-72h, MIN_COVERAGE gate, ranked ascending, LONG bottom-K/SHORT top-K)
  at each 24h rebalance under three arms that differ in EXACTLY ONE variable —
  the factor applied to HL rows:
    CONTROL  x1  = shipped code (mixed units)
    FIX      x8  = HL normalised to Lighter's 8h basis
    TRUTH    --  = Lighter samples only (what the book actually earns)

Usage:  DATABASE_URL=... python3 scripts/study_fundspread_basis_mixing.py
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
import funding_basis  # noqa: E402

# the shipped bot's constants — keep in sync with lighter_funding_spread_bot.py
COINS = ("BTC,ETH,SOL,BNB,XRP,DOGE,AVAX,LINK,ADA,LTC,DOT,NEAR,SUI,HYPE,AAVE,WIF,"
         "JUP,OP,ARB,TIA,ENA,SEI,APT,INJ,RUNE,STX,GALA,JTO,PYTH,W").split(",")
K = 5
LOOKBACK_H = 72
MIN_COVERAGE = LOOKBACK_H // 2
REBALANCE_H = 24
HL_INFO = "https://api.hyperliquid.xyz/info"
LIGHTER_FR = "https://mainnet.zklighter.elliot.ai/api/v1/funding-rates"

# The ratio between the two venues' quoted bases. NOT a magic 8: it is exactly
# HL periods/day over Lighter periods/day, asked of the fleet's basis authority.
HL_TO_LIGHTER = (funding_basis.periods_per_day("hyperliquid")
                 / funding_basis.periods_per_day("lighter"))


def hl_hist(coin, hours):
    start = int((time.time() - hours * 3600) * 1000)
    body = json.dumps({"type": "fundingHistory", "coin": coin,
                       "startTime": start}).encode()
    req = urllib.request.Request(HL_INFO, data=body,
                                 headers={"Content-Type": "application/json"})
    rows = json.loads(urllib.request.urlopen(req, timeout=25).read())
    out = {}
    for r in rows or []:
        out[(int(r["time"]) // 3600000) * 3600] = float(r["fundingRate"])
    return sorted(out.items())


def lighter_tradeable():
    """The REAL supports() gate: a tradeable, active Lighter market."""
    r = urllib.request.urlopen(
        "https://mainnet.zklighter.elliot.ai/api/v1/orderBookDetails", timeout=30)
    obs = json.loads(r.read()).get("order_book_details") or []
    return {o.get("symbol") for o in obs
            if str(o.get("status", "active")).lower() == "active"}


def live_fund_hist():
    """The bot's OWN persisted Lighter samples — real data, not a model."""
    import psycopg2
    url = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if not url:
        sys.exit("set DATABASE_URL (public proxy) — this study reads real state")
    c = psycopg2.connect(url)
    cur = c.cursor()
    cur.execute("select state from bot_state where bot=%s",
                ("perps-funding-spread-lshadow",))
    row = cur.fetchone()
    if not row:
        sys.exit("no live state for perps-funding-spread-lshadow")
    st = row[0]
    if isinstance(st, str):
        st = json.loads(st)
    return st


def score_arm(fh_hl, fh_lt, boot, t0, hl_factor, use_hl=True):
    """Replay the bot's EXACT scoring. hl_factor is the ONLY thing that varies."""
    floor = t0 - LOOKBACK_H * 3600
    scores = {}
    for coin in COINS:
        rows = []
        if use_hl:
            # what hl_backfill(coin, 78) left in the window, at boot time
            rows += [(t, r * hl_factor) for t, r in fh_hl.get(coin, [])
                     if floor <= t <= boot]
        # live Lighter samples accumulated since boot
        rows += [(t, r) for t, r in fh_lt.get(coin, []) if boot < t <= t0
                 and t >= floor]
        rs = [r for _, r in rows]
        if len(rs) >= MIN_COVERAGE:
            scores[coin] = sum(rs) / len(rs)
    return scores


def picks(scores, tradeable):
    s = {c: v for c, v in scores.items() if c in tradeable}
    if len(s) < 2 * K:
        return None, None, s
    ranked = sorted(s, key=s.get)
    return set(ranked[:K]), set(ranked[-K:]), s


def main():
    print("=" * 78)
    print("Counterweight fund_hist unit-mixing — REAL data, both venues")
    print("=" * 78)
    print(f"basis authority: HL {funding_basis.periods_per_day('hyperliquid')}/day, "
          f"Lighter {funding_basis.periods_per_day('lighter')}/day "
          f"-> HL_TO_LIGHTER = {HL_TO_LIGHTER:.1f}")

    st = live_fund_hist()
    fh_lt_raw = st.get("fund_hist") or {}
    tradeable = lighter_tradeable()
    now = time.time()

    # Lighter samples ONLY (the bot's live-sampled rows are the non-hour-aligned
    # ones; HL backfill rows are hour-aligned by construction in hl_backfill).
    fh_lt = {c: [(t, r) for t, r in rows if t % 3600 != 0]
             for c, rows in fh_lt_raw.items()}
    span = {c: (max(t for t, _ in v) - min(t for t, _ in v)) / 3600.0
            for c, v in fh_lt.items() if v}
    have = sorted(span, key=lambda c: -span[c])
    print(f"\nlive Lighter samples: {len(have)} coins, "
          f"longest span {max(span.values()):.1f}h")

    # Need HL rows back to (boot - LOOKBACK_H), and boot is as early as the
    # oldest live Lighter sample, so fetch the full span + the lookback + slack.
    hl_hours = int(max(span.values()) + LOOKBACK_H + 12)
    print(f"\nfetching HL hourly history ({hl_hours}h) ...")
    fh_hl = {}
    for c in COINS:
        try:
            fh_hl[c] = hl_hist(c, hl_hours)
        except Exception as e:  # noqa: BLE001
            print(f"  HL {c} failed: {e}")
            fh_hl[c] = []

    # ---- (3) the live steady state: is anything mixed actually ranked? ------
    print("\n" + "-" * 78)
    print("(3) LIVE STEADY STATE — is a mixed window reaching a pick?")
    print("-" * 78)
    mixed_ranked = []
    for coin in COINS:
        rows = fh_lt_raw.get(coin) or []
        w = [(t, r) for t, r in rows if t >= now - LOOKBACK_H * 3600]
        if not w:
            continue
        hl_rows = [1 for t, _ in w if t % 3600 == 0]
        lt_rows = [1 for t, _ in w if t % 3600 != 0]
        if hl_rows and lt_rows:
            mixed_ranked.append(coin)
        elif hl_rows and coin in tradeable and len(hl_rows) >= MIN_COVERAGE:
            mixed_ranked.append(coin + "(pure-HL but RANKABLE)")
    print(f"coins whose CURRENT window is unit-mixed AND rankable: "
          f"{mixed_ranked or 'NONE — bug is inert right now'}")

    # ---- (5) cold-start replay ---------------------------------------------
    print("\n" + "-" * 78)
    print("(5) COLD-START REPLAY — picks under CONTROL(x1) vs FIX(x8) vs TRUTH")
    print("-" * 78)
    # Boot at the oldest live Lighter sample, so the ENTIRE post-boot transient
    # (0h -> HL fully aged out) is replayed against real Lighter data.
    boot = now - max(span.values()) * 3600.0 + 1.0
    print(f"simulated cold boot at now-{(now-boot)/3600:.1f}h "
          f"(so real Lighter samples exist post-boot)\n")
    print("%-6s %-9s %-9s %-9s %-9s" % ("reb", "ctl^fix", "ctl^truth",
                                        "fix^truth", "verdict"))
    print("-" * 52)
    any_diff = False
    k = 0
    while True:
        t0 = boot + k * REBALANCE_H * 3600
        if t0 > now:
            break
        ctl = score_arm(fh_hl, fh_lt, boot, t0, 1.0)
        fix = score_arm(fh_hl, fh_lt, boot, t0, HL_TO_LIGHTER)
        tru = score_arm(fh_hl, fh_lt, boot, t0, 1.0, use_hl=False)
        cl, cs, cS = picks(ctl, tradeable)
        fl, fs, fS = picks(fix, tradeable)
        tl, ts, tS = picks(tru, tradeable)
        if cl is None:
            print("%-6s %s" % (f"+{k*24}h", "not rankable (< 2K coins)"))
            k += 1
            continue

        def ov(a, b):
            if a is None or b is None:
                return "n/a"
            return f"{len(a[0] & b[0])}L/{len(a[1] & b[1])}S"
        cf = ov((cl, cs), (fl, fs))
        ct = ov((cl, cs), (tl, ts)) if tl else "n/a"
        ft = ov((fl, fs), (tl, ts)) if tl else "n/a"
        same = (cl == fl and cs == fs)
        if not same:
            any_diff = True
        verdict = "same" if same else "**DIFFERS**"
        print("%-6s %-9s %-9s %-9s %-9s" % (f"+{k*24}h", cf, ct, ft, verdict))
        k += 1

    print("\n" + "=" * 78)
    if not any_diff:
        print("RESULT: control and fix pick IDENTICALLY at every replayed "
              "rebalance.\n        The x8 normalisation is a NO-OP on picks in "
              "this window.")
    else:
        print("RESULT: the fix CHANGES picks during the cold-start window "
              "(see **DIFFERS**).")
    print("=" * 78)

    # ---- ROBUSTNESS: never conclude from one boot time (n=1 is not a result) -
    print("\n" + "-" * 78)
    print("(5b) ROBUSTNESS SWEEP — every viable boot hour, not one lucky cell")
    print("-" * 78)
    print("Fidelity to TRUTH (Lighter-only ranking) = matched picks out of 10")
    print("A HIGHER score is CLOSER to what the book actually earns.\n")
    oldest = now - max(span.values()) * 3600.0 + 1.0
    rows_out = []
    for off_h in range(0, int((now - oldest) / 3600) - 48 + 1, 3):
        b = oldest + off_h * 3600.0
        for stage in (48, 72):
            t0 = b + stage * 3600.0
            if t0 > now:
                continue
            tru = score_arm(fh_hl, fh_lt, b, t0, 1.0, use_hl=False)
            tl, ts, _ = picks(tru, tradeable)
            if tl is None:
                continue
            ctl = score_arm(fh_hl, fh_lt, b, t0, 1.0)
            fix = score_arm(fh_hl, fh_lt, b, t0, HL_TO_LIGHTER)
            cl, cs, _ = picks(ctl, tradeable)
            fl, fs, _ = picks(fix, tradeable)
            if cl is None or fl is None:
                continue
            rows_out.append((stage,
                             len(cl & tl) + len(cs & ts),
                             len(fl & tl) + len(fs & ts)))
    for stage in (48, 72):
        sub = [r for r in rows_out if r[0] == stage]
        if not sub:
            continue
        nc = sum(r[1] for r in sub) / len(sub)
        nf = sum(r[2] for r in sub) / len(sub)
        cw = sum(1 for r in sub if r[1] > r[2])
        fw = sum(1 for r in sub if r[2] > r[1])
        print(f"  +{stage}h  n={len(sub):3d} boots | CONTROL mean {nc:.2f}/10 | "
              f"FIX mean {nf:.2f}/10 | control closer {cw}, fix closer {fw}, "
              f"tie {len(sub)-cw-fw}")
    print("\nIf CONTROL >= FIX, multiplying the HL rows by 8 does NOT buy")
    print("cold-start fidelity — it re-weights a FOREIGN venue's cross-section")
    print("from ~6% of the score to a full 1/3. Unit-purity != correctness.")


if __name__ == "__main__":
    main()
