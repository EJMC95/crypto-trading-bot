#!/usr/bin/env python3
"""
pnl_dashboard.py — ONE live page showing every bot's P&L, read from Postgres.

This is the new unified dashboard. Each bot publishes its snapshot to the
shared `bot_pnl` table (see bot_pnl_store.py); this service reads that table and
renders a mobile-friendly, auto-refreshing page on $PORT. Deploy it as its own
Railway service with DATABASE_URL pointed at the Postgres plugin.

  Local:   DATABASE_URL=postgres://...  python3 pnl_dashboard.py
  Railway: set DATABASE_URL (reference the Postgres service) + expose $PORT.

Deps: psycopg2-binary (see requirements.txt). Falls back to a clear message if
the DB is unreachable so the page never hard-crashes.
"""
import os
import json
import time
import base64
import hmac
import html
import threading
import datetime as dt
from urllib.parse import urlparse, parse_qs
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

PORT = int(os.environ.get("PORT", "8080"))

# Tiled "$ EJMC $" watermark painted behind the whole page — styled like a
# spraycan tag (grainy fill via feTurbulence, jittered per-glyph rotation,
# overspray speckle, paint drips). Kept faint — purely decorative, must never
# compete with card text for legibility.
_WATERMARK_TILE_SVG = (
    "<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 900 360' "
    "preserveAspectRatio='xMidYMid meet'>"
    "<defs>"
    "<filter id='spray' x='-30%' y='-30%' width='160%' height='160%'>"
    "<feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' seed='7' result='n'/>"
    "<feColorMatrix in='n' type='matrix' "
    "values='0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1.3 0' result='an'/>"
    "<feComposite in='SourceGraphic' in2='an' operator='in'/>"
    "</filter>"
    "<filter id='soft' x='-80%' y='-80%' width='260%' height='260%'>"
    "<feGaussianBlur stdDeviation='2.4'/>"
    "</filter>"
    "<linearGradient id='dripfade' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#f4f1e6' stop-opacity='0.95'/>"
    "<stop offset='55%' stop-color='#e8e4d5' stop-opacity='0.7'/>"
    "<stop offset='100%' stop-color='#d8d3c2' stop-opacity='0.1'/>"
    "</linearGradient>"
    # off-white paint fill — soft top-lit cream down to a shaded cream
    "<linearGradient id='paintgrad' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#fdfcf6'/>"
    "<stop offset='55%' stop-color='#f2efe4'/>"
    "<stop offset='100%' stop-color='#e4dfd0'/>"
    "</linearGradient>"
    "<linearGradient id='hlgrad' x1='0' y1='0' x2='0' y2='1'>"
    "<stop offset='0%' stop-color='#ffffff' stop-opacity='0.95'/>"
    "<stop offset='40%' stop-color='#ffffff' stop-opacity='0.2'/>"
    "<stop offset='70%' stop-color='#ffffff' stop-opacity='0'/>"
    "</linearGradient>"
    "</defs>"
    "<g opacity='0.9'>"
    # Graffiti marker handstyle — 'Permanent Marker' web font (loaded on the page;
    # this SVG is inline so it inherits it), skewed for the aggressive tag slant.
    # Falls back to other marker/handwritten faces, then cursive.
    f"<g transform='rotate(-5 450 200) skewX(-11)' "
    f"font-family=\"'Permanent Marker','Rock Salt','Bradley Hand',cursive\" "
    f"font-size='150' font-weight='400' text-anchor='middle'>"
    # soft cast shadow, offset down-right for depth against the light page
    "<text x='456' y='236' fill='#3b4652' opacity='0.28' filter='url(#soft)'>$ EJMC $</text>"
    # dark outline + spray-grained off-white fill (outline carries the contrast
    # on the light background, like a white tag reads against dark)
    "<text x='450' y='228' fill='url(#paintgrad)' stroke='#2c343d' stroke-width='4.5' "
    "stroke-linejoin='round' paint-order='stroke fill' filter='url(#spray)'>$ EJMC $</text>"
    # subtle sheen across the top of the strokes
    "<text x='450' y='228' fill='url(#hlgrad)' style='mix-blend-mode:screen'>$ EJMC $</text>"
    "</g>"
    # paint drips — thin near-straight runs with a small drop at the tip, the way
    # a marker/spray tag bleeds down. Scattered along the baseline.
    "<g opacity='0.9'>"
    "<rect x='178' y='232' width='3.4' height='96' rx='1.7' fill='url(#dripfade)'/>"
    "<circle cx='179.7' cy='330' r='4' fill='#d8d3c2' opacity='0.75'/>"
    "<rect x='262' y='236' width='2.8' height='60' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='263.4' cy='298' r='3.2' fill='#cfc9b8' opacity='0.62'/>"
    "<rect x='330' y='234' width='3.2' height='82' rx='1.6' fill='url(#dripfade)'/>"
    "<circle cx='331.6' cy='318' r='3.8' fill='#cfc9b8' opacity='0.66'/>"
    "<rect x='404' y='238' width='2.6' height='46' rx='1.3' fill='url(#dripfade)'/>"
    "<circle cx='405.3' cy='286' r='3' fill='#cfc9b8' opacity='0.58'/>"
    "<rect x='474' y='234' width='3.4' height='92' rx='1.7' fill='url(#dripfade)'/>"
    "<circle cx='475.7' cy='328' r='4' fill='#d8d3c2' opacity='0.75'/>"
    "<rect x='560' y='236' width='2.8' height='56' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='561.4' cy='294' r='3.2' fill='#cfc9b8' opacity='0.6'/>"
    "<rect x='648' y='234' width='3' height='72' rx='1.5' fill='url(#dripfade)'/>"
    "<circle cx='649.5' cy='308' r='3.6' fill='#cfc9b8' opacity='0.64'/>"
    "<rect x='736' y='236' width='2.8' height='50' rx='1.4' fill='url(#dripfade)'/>"
    "<circle cx='737.4' cy='288' r='3.2' fill='#cfc9b8' opacity='0.6'/>"
    "</g>"
    # overspray speckle + faint spray-ring flourish, like a tag finished with the can
    "<circle cx='150' cy='150' r='4' fill='#cfc9b8' opacity='0.4' filter='url(#soft)'/>"
    "<circle cx='176' cy='128' r='2.2' fill='#cfc9b8' opacity='0.55'/>"
    "<circle cx='690' cy='150' r='3.6' fill='#cfc9b8' opacity='0.35' filter='url(#soft)'/>"
    "<circle cx='664' cy='170' r='2' fill='#cfc9b8' opacity='0.5'/>"
    "<circle cx='450' cy='92' r='3' fill='#cfc9b8' opacity='0.35' filter='url(#soft)'/>"
    "<circle cx='800' cy='196' r='13' fill='none' stroke='#cfc9b8' stroke-width='1.6' "
    "opacity='0.3' filter='url(#soft)'/>"
    "</g>"
    "</svg>"
)
# Rendered as an INLINE svg (fixed, behind the cards) rather than a CSS
# background-image, so it can use the 'Permanent Marker' web font — background
# SVGs are sandboxed and can't load page fonts, which is why a font swap needs
# this. The <link> for the font is added in the page <head>.
WATERMARK_HTML = f'<div class="wm" aria-hidden="true">{_WATERMARK_TILE_SVG}</div>'
DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

# Login for THIS dashboard page. Set DASH_PASS via env on the Railway service.
# [2026-07-18] The password is NOT committed, and auth FAILS CLOSED when it is
# unset. A real-money console (live positions + kill-switch surface) must never
# ship a working default: the previous committed default ("freqbot2026") was
# found live on the production service, which set no override, so the password
# effectively sat in git. No secret configured now => no access, never a
# guessable one. DASH_USER stays defaulted (a username is not a secret).
DASH_USER = os.environ.get("DASH_USER", "eamon")
DASH_PASS = os.environ.get("DASH_PASS", "")

# [2026-07-11 SWAP] Decommissioned venue rows — hidden from the grid and every
# feed so a retired bot can't sit next to its replacement and confuse the LIVE
# section. History stays in bot_equity_history / paper_trades / venue_orders.
# Trail Blazer live retired 11 Jul; its sub-account + Railway service now run
# the Funding Farmer (publishes as perps-funding-lighter-lighter).
# [2026-07-12 DECOMMISSION] Bounce Catcher (perps-rsi-meanrev) + Loop Scout
# (scanner-triangular-arb) stopped on user sign-off: the 12-Jul audit found
# Bounce Catcher running the IDENTICAL entry to Trail Blazer's paper bot
# (REJECTED for edge 12 Jul), and Loop Scout carried a retire verdict since
# the 22-Jun revalidation. Railway services perps-bot + triangular-arb are
# down (empty shells left in the UI); momo-bot stays as the cluster's
# representative. The stale rsi-meanrev lshadow row from Gate-0 goes too.
# [2026-07-12 LOSER CUT] TrendMomoV1 (crypto-trendmomo-4h) retired on user
# sign-off: core leg -29%/4.5y on the tagged Binance replay (26.5% win), live
# bleeder (-$11.33). Removed from run_all.sh in the same commit.
# [2026-07-12 SAME-PAGE SWEEP] perps-donchian-breakout-lshadow was a Gate-0
# local run that stopped 10 Jul (stale ever since); its signal is the
# twice-retired range-buy, so the shadow is NOT restarted — row hidden.
# [2026-07-12 DASHBOARD SWEEP] Trail Blazer's PAPER row (perps-donchian-breakout)
# hidden on user request to clear the bots we're not going ahead with: the live
# half retired 11 Jul and the entry was REJECTED for edge in the 12-Jul audit
# (identical to Bounce Catcher's). NOTE the momo-bot Railway service still runs
# and re-publishes this row — hiding is dashboard-side only; stopping/keeping
# the service is a separate call. History stays in bot_equity_history /
# paper_trades. Also dropped from EXPECTED so no placeholder card returns.
# [2026-07-13 DECOMMISSION] Two-Way Tide (perps-regime-switch) removed on user
# instruction: the 12-Jul Index Pilot review closed its long/short-regime
# concept, live record 1/7 wins -$5.36. User deleted the Railway service
# entirely (repo disconnected first, so nothing can resurrect it); row + the
# EXPECTED placeholder retired here. History stays in the ledgers.
# [2026-07-14 LIGHTER-FIRST CUT] The laptop stock bots (Alpaca Stock Leaders
# + IBKR Index Pilot) retired on user instruction — their Lighter ports
# (equities-momentum-lshadow / equities-regime-lshadow) ARE the bots now.
# Their raw broker-scale equity ($100k/$250k paper accounts) also broke every
# cross-bot comparison. NOTE: the laptop processes run OUTSIDE this repo —
# rows are hidden+pruned here, but only the operator can stop the processes
# (until then their rows re-upsert into bot_pnl, harmlessly hidden).
# [2026-07-14 KRAKEN RETIREMENT — user instruction] The 8 Kraken PAPER rows
# retired; their Lighter -lshadow twins are the fleet and keep displaying
# (bases move EXPECTED -> VARIANT_ONLY below), and Tide Rider's LIVE row
# (crypto-trend-daily-lighter) is unaffected — this set matches exact row
# names only. Operator side: stop the 4 family Railway services (ONLY_BOT
# mum/dad/avo-maria/georgia); the main container drops its 4 spot bots on
# this deploy.
RETIRED_ROWS = {
                # [2026-08-22 (ta)/(tb)] 💸 the Funding Farmer's LIVE arm.
                # Horizon `unreachable` on BOTH arms at the fleet's own grader
                # (live n=91 mean -0.160%/trade t=-0.88 halves +2.51/-7.65).
                # 🔮 georgia took the sub-account by converting the SAME
                # service in place, so leaving this row visible would
                # DOUBLE-COUNT the same real money — the identical reason
                # `crypto-trend-daily-lighter` had to be retired when 🎫 the
                # Taker took its slot (17-Jul). Hidden only AFTER the flatten
                # published `extra.retired.open == 0`, because /pnl.json is
                # filtered by this very set and hiding it earlier blinds the
                # feed the flatten is verified on.
                # Its SHADOW twin is NOT retired and keeps trading.
                "perps-funding-lighter-lighter",
                "perps-donchian-breakout",
                "perps-donchian-breakout-lighter",
                "perps-donchian-breakout-lshadow",
                # [2026-08-15 (nf)] THE RED-STOP SLATE — seven I17 calls made
                # in one operator act on the decision docket's own verdicts
                # (every row horizon=unreachable or I17-undecidable, asks
                # open since 6-Aug). Each is reversible via its own override
                # env; ledgers kept; open paper positions freeze (the (mr)
                # precedent). Both halves shipped together per the standing
                # retirement rule (this set hides; LEGACY_BOTS prunes).
                # [2026-08-16 (oj)] 🧙 book-schwager RETIRED — the I17
                # keep-or-retire call, operator decision on the (nu)/(oe)
                # re-measurement. UNDECIDABLE BY TAIL, a new class beside
                # I17's slow-clock one: the founding +$457.21/t=1.88 sits
                # OUTSIDE the whole measurable distribution (90-cell sweep,
                # t>=2.0 in 0 of 90), the top 3 of 298 trades are 112% of the
                # total, the random-entry null reads P=0.183, and at the
                # measured mean/sd it needs ~719 closes (~40 MONTHS) to reach
                # t=2.0. ZERO closes in its own ledger. 4 open paper
                # positions freeze (the (mr) precedent). Reversible via
                # SCHWAGER_RETIRED_OVERRIDE=run. Both halves shipped
                # together; LEGACY_BOTS prunes.
                "book-schwager-lshadow",
                # [2026-08-17 (pm)] 🎸 band-barnes — the I17 call on the carry
                # cell, operator decision. ZERO INDEPENDENT EVIDENCE, measured
                # on its own ledger: 0 of 9 episodes its living carry sleeve
                # ever opened were a coin 🌾 carry was not already holding at
                # that moment (3 coins, all carry's). Minted as a THREE-sleeve
                # super-book; two sleeves already retired ((ly), (nf)), so the
                # survivor is carry's own gate at a smaller cap — one bet held
                # twice. Zero open positions, so nothing freezes. Reversible
                # via BARNES_RETIRED_OVERRIDE=run. Both halves shipped
                # together; LEGACY_BOTS prunes.
                "band-barnes-lshadow",
                "pm-gillard-lshadow", "pm-abbott-lshadow",
                "pm-rudd-lshadow", "pm-morrison-lshadow",
                "crypto-intraday-15m-lshadow", "crypto-swing-daily-lshadow",
                "freqtrade-dad-lshadow",
                # [2026-08-19 (ro)] 👩 mum's (rd) retirement was REVERSED by
                # the operator and she is deliberately NOT hidden: she trades
                # again as v2 (OversoldRebound, 1h, bracketed). The bare
                # Kraken-era `freqtrade-mum` stays retired below — that is a
                # DIFFERENT row, and conflating the two is the bare-name trap
                # this file's own tests pin.
                # [2026-08-13 (ma)] 🎫 Ticket Taker's LIVE row — 🙏 Avo Maria
                # took the slot (same service/keys/sub-account, the slot's
                # THIRD occupant; operator decision, cutover verified by
                # stamp readback e49ba8fa7ed2). Same rule as the Tide Rider
                # entry directly below: both rows would report the SAME
                # ~$62.80 sub-account and the fleet total would double-count
                # it — measured live at cutover: live_equity read $323.30
                # across 3 "live bots" when the real money is $260.50 across
                # 2 accounts. The Taker SHADOW row keeps grading untouched.
                "lighter-ticket-taker-lighter",
                # [2026-07-17] 🌊 Tide Rider RETIRED from the live slot —
                # 🎫 Ticket Taker took it (operator: "taker was meant to replace
                # rider"), the same shape as the 11-Jul Trail Blazer -> Funding
                # Farmer swap: SAME service (tide-rider-lighter-live), same keys,
                # same sub-account, no transfer. The service now builds
                # Dockerfile.tickettaker, so this id can never be published
                # again — the retirement is permanent, not a hidden live bot.
                # RETIRING IT IS REQUIRED, not cosmetic: the taker already
                # publishes the SAME $34.67 sub-account under
                # lighter-ticket-taker-lighter, so both rows reported the same
                # real money and the fleet total DOUBLE-COUNTED it. The money is
                # not hidden by this — it moves to the taker's row.
                # Its record: 0 closed trades ever, died on n=14; the operator
                # flattened its last TRX by hand and armed the kill switch.
                # [2026-08-01 (ie)] THE -lshadow TWIN IS NOW HERE TOO, and the
                # precondition this note demanded has been met FIRST: the
                # trend bot idles at boot behind
                # `TIDE_RIDER_RETIRED_OVERRIDE` (lighter_trend_bot.main), so
                # the row cannot simply return. Order matters — guard, then
                # retire. Measured over its whole 22-day life: 9 buys, ZERO
                # sells, 0 closed trades, holding 6 of 6 and 33% of the fleet
                # long budget with no measured claim. `(hk)`'s universe
                # widening worked on the ENTRY side only — 5 of those 9 buys
                # landed in the two days after it — so it now fills ~12x
                # faster and still cannot exit. Its only price exit is a 35%
                # stop, 2.3x the 15% go-live drawdown bar ((gv)), so it can
                # never clear the gate that governs real money. `(hz)` called
                # this "the genuinely unclosed decision"; it is closed.
                "crypto-trend-daily-lighter",
                "crypto-trend-daily-lshadow",
                # [2026-08-04] 🧲 SNAP BACK RETIRED — operator decision
                # (OPERATOR_QUEUE.md item 2, option A) on the strongest
                # retire case in the fleet: t=-2.97 on n=175, mean
                # -0.281%/trade, BOTH halves negative, ~-$1/day, and 100%
                # `converged` exits since the widening — the book harvests
                # its own entry gate. The growth rail structurally cannot
                # restrict it: its binding entry floor (ENTER_FLOOR_MULT)
                # is an unregistered bare literal, and every lever motion
                # the registry CAN express loosens it. Guard first, then
                # retire (the Tide Rider order, (if)):
                # `lighter_dislocation_bot.main` idles at boot behind
                # `SNAPBACK_RETIRED_OVERRIDE`, so the row cannot simply
                # return. Only the -lshadow row ever published — the v1
                # gate refuses lighter_live, so there is no live row to
                # retire. Ledgers and census history kept.
                "lighter-dislocation-lshadow",
                # [2026-08-14 (mr)] 🚀 crypto-breakout-4h RETIRED — the I17
                # call, operator decision. The ONLY book of the NINE on the
                # decision docket that survives Benjamini-Hochberg at FDR 0.05
                # (p=0.0036 vs a 0.0056 critical value); both samples agree in
                # direction and significance — in-era n=15 mean -1.745%/trade
                # t=-3.50 halves -2.56/-4.94, all-time n=21 mean -2.236%
                # t=-5.48 halves both negative, ~-$0.48/day, horizon
                # `unreachable`. Frees 2 slots of the ENFORCED 20-long budget
                # (TRX + LINK). Costs no thesis coverage: 4h breakout lives on
                # in 🧙 book-schwager (n=277, +$457.21, both halves positive).
                # Guard first, per the order this file teaches: the book is
                # dropped from `lighter_family_bot.live_strategies()`, which is
                # ROW-scoped because that module also runs six OTHER books —
                # the idle-the-process pattern of 🌊/📊 would silence them all.
                # Ledgers kept; BREAKOUT4H_RETIRED_OVERRIDE=run resurrects.
                "crypto-breakout-4h-lshadow",
                # [2026-08-13 (lo)] 📊 Index Rider RETIRED — the I17 call,
                # made by the operator ("get rid of what's not working"):
                # ZERO closes in 44 days, measured rule rate ~17.2/yr vs a
                # 30-close bar — structurally undecidable. Guard idles the
                # bot (INDEX_RIDER_RETIRED_OVERRIDE=run resurrects); only
                # the -lshadow row ever published. Ledgers + :equity kept.
                "equities-regime-lshadow",
                "perps-rsi-meanrev", "perps-rsi-meanrev-lshadow",
                "scanner-triangular-arb", "crypto-trendmomo-4h",
                "perps-regime-switch", "perps-regime-switch-lshadow",
                "equities-momentum-alpaca", "equities-regime-ibkr",
                # [2026-07-17] 🏆 Stock Leaders RETIRED. Not the rule (n=3 fills
                # in a real market-wide crash, inside its own envelope) — it
                # cannot promote at any size worth the slot: maxDD 37-44% with
                # ZERO carry vs the 15% go-live gate, and the only deployment
                # that clears the gate (15%, $30/slot) earns ~$42-67/yr, at or
                # below risk-free. Funding was never the problem (~8% TRUE apr
                # vs a ~52% breakeven). Ledger kept; see lighter_momentum_bot.py.
                "equities-momentum", "equities-momentum-lshadow",
                "crypto-trend-daily", "crypto-intraday-15m",
                "crypto-swing-daily", "crypto-breakout-4h",
                "freqtrade-mum", "freqtrade-dad",
                "freqtrade-avo-maria", "freqtrade-georgia",
                # [2026-07-17] LIGHTER-ONLY (operator: "i only want things
                # running on lighter"). Both traded NON-Lighter venues and both
                # are now code-guarded to idle at boot (the guard is the stop —
                # Railway resurrects stopped services on git push).
                #   event-listing-sniper — spot listings on ~100 CEXes. Its
                #     replacement, the Lighter Perp Sniper, has run since 9-Jul;
                #     both were sniping at once for 8 days.
                #   perps-funding-carry — the HL-data arm of Yield Harvester.
                #     Its Lighter twin perps-funding-carry-lshadow CONTINUES and
                #     is deliberately NOT retired here.
                # Ledgers kept, per retirement policy.
                #   scanner-cross-exchange-arb (🔀 Gap Scout) — paper-traded arb
                #     BETWEEN Kraken/Binance/Coinbase; no Lighter leg exists in
                #     that trade, so it could only be stopped, not moved. Its
                #     Lighter-premium job moved to lighter_market_scout (every
                #     liquid book vs its 6); fleet_risk rewired to that source.
                "event-listing-sniper", "perps-funding-carry",
                "scanner-cross-exchange-arb"}

# Expected bots — so the grid shows a bot even before its first publish.
# [2026-07-13 NO-DATA FIX] Venue-suffixed bots (Funding Farmer, Snap Back,
# Counterweight, Perp Sniper) publish ONLY -lighter/-lshadow rows — their BASE
# ids never publish, so listing them here produced permanent "no data yet"
# placeholder cards (the user's "bots with no data" complaint). They move to
# VARIANT_ONLY: still first-class CURRENT_BOTS (their variant rows pass the
# fetch_rows filter) but no dead placeholder card.
VARIANT_ONLY = {"perps-funding-lighter", "lighter-perp-sniper",
                "lighter-dislocation", "perps-funding-spread",
                # [2026-07-13] Index Rider — the IBKR bot's regime strategy on
                # Lighter STOCK PERPS (SPY/QQQ), shadow-only; base never publishes
                "equities-regime",
                # [2026-07-14 KRAKEN RETIREMENT] the 8 ex-Kraken bases: paper
                # rows retired, the -lshadow twins (+ Tide Rider live) display
                # under these bases
                "crypto-trend-daily", "crypto-intraday-15m",
                "crypto-swing-daily", "crypto-breakout-4h",
                "freqtrade-mum", "freqtrade-dad",
                "freqtrade-avo-maria", "freqtrade-georgia",
                # [2026-07-14] 🎫 Ticket Taker — shadow-only scout trader
                "lighter-ticket-taker",
                # [2026-07-21] 🏛️ the Parliament — six PM shadow books
                # (parliament_main.py in the freqtrade-bots container).
                # Publish ONLY -lshadow rows; bases never publish.
                "pm-albanese", "pm-morrison", "pm-turnbull",
                "pm-abbott", "pm-rudd", "pm-gillard",
                # [2026-08-05] 🎸 Barnesy — the funding super-book
                # (lighter_band_barnes_bot.py, service band-barnes-shadow).
                # First of the Australian-musician cohort. Shadow-only;
                # base never publishes.
                "band-barnes",
                # [2026-08-13 (lp)] 🛢️ Garrett — the thin-tier funding band
                # (lighter_funding_bot.py VARIANT, service
                # band-garrett-shadow). Second of the musician cohort.
                # Shadow-only; base never publishes.
                "band-garrett",
                # [2026-08-13 (ls)] 🏦 Rich Dad — the cash-flow doctrine book
                # (lighter_book_kiyosaki_bot.py, service book-kiyosaki-shadow;
                # operator: "create a bot from rich dad poor dad"). First of
                # the BOOKS cohort (book-<surname>, named for the author).
                # Shadow-only; base never publishes.
                "book-kiyosaki",
                # [2026-08-13 (mb)-(me)] the BOOKS cohort's second wave —
                # operator: "Build me 4 bots for each of these books".
                # 🧘 Douglas (Trading in the Zone), 📐 Grimes (The Art and
                # Science of TA), 🧙 Schwager (Market Wizards), 🧮 Hull
                # (Options, Futures and Other Derivatives). Each its own
                # service (book-<surname>-shadow). Shadow-only; bases never
                # publish.
                "book-douglas", "book-grimes", "book-schwager", "book-hull",
                # [2026-08-18] 🪁 band-kelly — the MIRROR book (operator:
                # "does the exact opposite of all of the major losing
                # sequences"; lighter_band_kelly_bot.py, service
                # band-kelly-shadow). Third of the musician cohort.
                # Shadow-only; base never publishes.
                "band-kelly",
                # [2026-08-19 (ri)] 🧭 nav-cook — the NAVIGATOR (the (re)
                # [45,60)bps band book; lighter_nav_cook_bot.py, service
                # nav-cook-shadow). First of the navigator cohort. Registered
                # at birth-completion: without this the row filter (line
                # ~781) drops nav-cook-lshadow from /pnl.json and the
                # provisioning readback chases a ghost — the (ml) shape.
                # Shadow-only; base never publishes.
                "nav-cook"}
EXPECTED = ["perps-funding-carry",
            "event-listing-sniper"]

# Scanners book OPTIMISTIC paper-arb fills (observed spreads, no slippage/latency).
# Their pnl_abs is real paper P&L but on a rosier basis than the freqtrade bots'
# simulated fills — so it is reported as a SEPARATE subtotal and never folded
# into the trading-bot P&L headline.
SCANNERS = {"scanner-cross-exchange-arb"}

# Stock/brokerage bots (IBKR + Alpaca). Shown as their own cards with a SEPARATE
# subtotal so their large $ equity never swamps the crypto headline.
# [2026-07-14] laptop originals (ibkr/alpaca) retired — the Lighter ports are
# the stock bots now. Bases stay listed so stock-class handling applies.
STOCKS = {"equities-momentum", "equities-regime"}

# [2026-07-16] Over-trading bar per bot CLASS (keyed by BASE name). The flat
# 15/day was written when `quality` only saw the slow freqtrade books; once the
# paper ledger joined it, the high-frequency-BY-DESIGN books would trip the
# health banner on every load. These cadences are the design, not a fault:
# a dislocation fader and a listing sniper are supposed to close often.
OVERTRADE_LIMIT = {
    "lighter-dislocation":   60,   # 🧲 Snap Back — fades every dislocation print
    "lighter-ticket-taker":  40,   # 🎫 Ticket Taker — up to one per lens per cycle
    "event-listing-sniper":  60,   # 🎯 Launch Sniper — every new CEX listing
    "lighter-perp-sniper":   60,   # 🎯 Perp Sniper — same, on Lighter
    "perps-funding-lighter": 40,   # 💸 Funding Farmer — 5-min loop, flips often
    "perps-funding-spread":  40,   # ⚖️ Counterweight — x-sect L/S rebalances
    "pm-abbott":             40,   # 🥊 Parliament scalper — ≤4h holds by design
    "pm-gillard":            40,   # 🤝 Parliament disloc fader — closes often
    "band-barnes":           40,   # 🎸 Barnesy — 10 xsect legs can rebalance
                                   # in one pass + two harvest sleeves
    "band-garrett":          40,   # 🛢️ Garrett — the Farmer's loop cadence
                                   # (same file), thin tier flips often
    "book-kiyosaki":         20,   # 🏦 Rich Dad — 6 slots; a funding whipsaw
                                   # day can flip-and-refill more than 15
    "book-douglas":          30,   # 🧘 The Zone — 1h impulse fades, ~12h max
                                   # hold; a violent day can cycle 4 slots
    "band-kelly":            40,   # 🪁 the Mirror — 90s loop, median hold
                                   # ~5min (the ghost's own cadence); a
                                   # dislocation-storm day cycles 4 slots fast
    "nav-cook":             120,   # 🧭 the Navigator. MEASURED on its first
                                   # 24 closes: 55.9 closes/day, all exiting
                                   # `converged` at a ~5min median hold — the
                                   # 4h bound is never reached. 120 is ~2x its
                                   # observed normal, so the card flags a real
                                   # DOUBLING rather than lighting up every
                                   # hour on healthy behaviour. [Corrected
                                   # 19-Aug: this shipped at 20, reasoned from
                                   # the DESIGN ("4h hold x 4 slots"), which
                                   # would have kept a permanent warning on a
                                   # book that is simply fast. A threshold that
                                   # is always on is not a signal. The separate
                                   # question — whether ~56/day vs the study's
                                   # ~1.5/day means a missing re-entry cooldown
                                   # — belongs in the changelog (rq) and to the
                                   # nav-cook session, not to a lit-up chip.]
}
OVERTRADE_DEFAULT = 15

# The only bots that should appear. Anything else in the table (e.g. legacy
# pre-rename rows perps-bot/momo-bot/v4core/v5gated/v6swing/v7momo/v8momo) is a
# stale duplicate and is filtered out here so it can never skew totals or the
# grid — independent of whether the Postgres table has been pruned yet.
# Freqtrade fleet bots (July 2026)
FREQTRADE = {"freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria", "freqtrade-georgia"}
CURRENT_BOTS = set(EXPECTED) | VARIANT_ONLY | SCANNERS | STOCKS | FREQTRADE

# [2026-07-09 LIGHTER GO-LIVE] Venue-variant rows. When a bot trades on Lighter
# its publisher suffixes the bot id by mode (venues/__init__._SUFFIX):
#   -lighter  = REAL MONEY live   (each on its own Lighter sub-account)
#   -ltest    = Lighter testnet   (real order lifecycle, faucet funds)
#   -lshadow  = shadow            (modelled fills on live books, NEVER sends)
# These are SEPARATE dashboard rows from the paper (hl_paper) bot so the paper
# equity curve is never contaminated. They are detected dynamically (not a fixed
# list) so whichever bots the user brings live just appear, each badged with its
# mode, and the LIVE fleet is reported as its own P&L subtotal.
VENUE_SUFFIXES = {
    # [2026-07-13] LIVE badge red -> green on user request.
    "-lighter": ("LIVE", "#1a7f37", "lighter_live"),
    "-ltest":   ("TESTNET", "#d29922", "lighter_testnet"),
    "-lshadow": ("SHADOW", "#58a6ff", "lighter_shadow"),
}


def venue_variant(bot):
    """(base_bot, suffix_key) if `bot` is a venue-variant row, else (bot, None)."""
    for suf in VENUE_SUFFIXES:
        if bot.endswith(suf):
            return bot[:-len(suf)], suf
    return bot, None


def is_live_bot(bot):
    """True only for REAL-money Lighter rows (not shadow/testnet)."""
    return bot.endswith("-lighter")

# [2026-07-01] Professional display names. Keys stay machine-safe; the dashboard
# shows the descriptive label. label_for() falls back to the raw key if unmapped.
# [2026-07-05] Trendy names + a plain "what it does" tail so a glance tells you
# both the personality and the mechanism. Leading emoji = fast visual scanning.
# [2026-07-13 NAME TIDY-UP on user request] Purpose-first names — no exchange
# tags (the LIVE/SHADOW chips carry venue), the role after the dash, and a
# one-line strategy description (DESCRIPTIONS below) rendered on every card so
# each bot's intent + current units are reviewable at a glance.
LABELS = {
    "crypto-trend-daily":          "🌊 Tide Rider — trend rider",
    "crypto-intraday-15m":         "⚡ Range Raider — day trader",
    "crypto-swing-daily":          "🩸 Dip Buyer — swing dip buyer",
    "crypto-breakout-4h":          "🚀 Breakout Hunter — breakout rider",
    # [2026-07-14] retired-bot labels removed (Momentum Surfer, Bounce
    # Catcher, Trail Blazer, Two-Way Tide, Loop Scout): their rows are
    # deleted from bot_pnl (cleanup_legacy_bots on boot) and RETIRED_ROWS
    # filters any republish, so the labels were dead code.
    "perps-funding-carry":         "🌾 Yield Harvester — funding carry",
    "band-barnes":                 "🎸 Barnesy — funding super-book",
    "band-garrett":                "🛢️ Garrett — thin-tier funding band",
    "book-kiyosaki":               "🏦 Rich Dad — cash-flow doctrine book",
    "book-douglas":                "🧘 The Zone — discipline book",
    "book-grimes":                 "📐 The Technician — quantified-edge book",
    "book-schwager":               "🧙 The Wizard — ride-winners book",
    "book-hull":                   "🧮 The Professor — cost-of-carry book",
    "band-kelly":                  "🪁 the Mirror — rides what the losers fade",
    "nav-cook":                    "🧭 the Navigator — charts the band below the mirror's floor",
    "perps-funding-lighter":       "💸 Funding Farmer — funding harvester",
    "lighter-perp-sniper":         "🎯 Perp Sniper — listing sniper",
    "lighter-dislocation":         "🧲 Snap Back — dislocation harvester",
    "perps-funding-spread":        "⚖️ Counterweight — funding L/S book",
    "lighter-ticket-taker":        "🎫 Ticket Taker — scout-driven trader",
    "scanner-cross-exchange-arb":  "🔀 Gap Scout — arb scanner",
    "event-listing-sniper":        "🎯 Launch Sniper — listing buyer",
    "equities-regime":             "📊 Index Rider — stock-perp regime",
    "equities-momentum":           "🏆 Stock Leaders — stock momentum",
    "freqtrade-mum":               "👩 Mum v2 — oversold rebound",
    "freqtrade-dad":               "👨 Dad — breakout rider",
    "freqtrade-avo-maria":         "🙏 Avo Maria — dip buyer",
    "freqtrade-georgia":           "🔮 Georgia — day trader",
    # [2026-07-21] 🏛️ the Parliament — last 8 Australian PMs: 6 books here,
    # Keating (scanners+ML) and Howard (ecosystem brain) are its organs.
    "pm-albanese":                 "🏗️ Albanese — trend rider",
    "pm-morrison":                 "📣 Morrison — breakout chaser",
    "pm-turnbull":                 "💼 Turnbull — mean reverter",
    "pm-abbott":                   "🥊 Abbott — momentum scalper",
    "pm-rudd":                     "🌏 Rudd — funding diplomat",
    "pm-gillard":                  "🤝 Gillard — dislocation fader",
}

# One-line strategy brief per bot (shared by its venue variants — the chips
# say WHERE it runs, this says WHAT it does + current units).
DESCRIPTIONS = {
    "freqtrade-mum":       "OversoldRebound · 1h — REVIVED 19-Aug (ro): buys RSI(14)<25 OUTSIDE an uptrend (the cell avo cannot take), bracket predefined at entry, 12h carry-bounded cap; carries its OWN random-entry control arm · $50 × 4 slots",
    "freqtrade-dad":       "MomoBreakoutV1 · 4h — buys a fresh 20-bar high above the 200-EMA, trails out on the 15-bar low · $50 × 4 slots",
    "freqtrade-avo-maria": "SwingDipV1 · 4h — buys RSI<42 dips under the lower Bollinger in an uptrend, sells into strength · shadow $50 × 6 slots; LIVE clips = equity × gross_x ÷ 5 slots, levered 1.4× of a 1.5× drawdown budget (funded + levered 21-Aug (sr); slot swap 13-Aug)",
    "freqtrade-georgia":   "DayTraderV5Gated · 15m — BTC-regime-switched pullback + breakout entries, 3.5×ATR trailing stop, ROI ladder · $50 × 5 slots",
    "crypto-trend-daily":  "daily 50/200-EMA golden cross — long through uptrends, cash after the death cross; holds for weeks",
    "crypto-intraday-15m": "DayTraderV5Gated · 1h — Georgia's engine at the validated 1h settings · 29 pairs, 5 slots",
    "crypto-swing-daily":  "SwingDipV1 · 1d — the validated daily dip-buyer · 29 pairs, 8 slots",
    "crypto-breakout-4h":  "MomoBreakoutV1 · 4h — the validated Donchian breakout · 29 pairs, 6 slots",
    # [2026-08-03] UNITS DELIBERATELY ABSENT — this line used to read
    # "…when |APR|≥40% … · clip $20 × cap $80" and every one of those three
    # numbers was wrong: the process was running clip $37.50, cap $150 and a 5%
    # TRUE gate, and the APR had been 8x overstated since the 17-Jul basis fix.
    # They are RUNTIME values (clip rides live.clip_scale, cap is the operator's
    # *_MAX_NOTIONAL env, enter_apr is a judge-promotable lever), so prose can
    # only ever drift. The bot publishes them now and `live_units` renders them.
    # Describe the MECHANISM here; never the numbers.
    "perps-funding-lighter": "holds the side that RECEIVES funding, vol-vetoed, stop-guarded",
    "perps-funding-carry":  "funding-rate carry on HL data — the Funding Farmer's origin strategy",
    "band-barnes":          "three funding sleeves under one $1k roof — carry harvest (≥20% TRUE, decay-paid discipline, $80×4), funding-extreme directional (top |APR|, 10% stop, $40×4), x-sect L/S rank (K=5/side, $33 legs, 24h rebalance) · closes tagged per sleeve · config FROZEN 30d from birth ((hm))",
    "book-kiyosaki":        "Rich Dad Poor Dad as rules — holds only funding-RECEIVING positions (assets), delta-neutral modelled so P&L is pure cash flow; sells a position the moment it persists as a liability; decay-closes only after income repays all costs (pay yourself first); entries must repay their round trip within the payback bar (financial literacy)",
    "book-douglas":         "Trading in the Zone as rules — fades extreme 1h impulses (>2.5×ATR24) with a bracket predefined at entry (stop 1.0×/target 1.5×ATR, 12h expiry, never widened); same size every trade, outcomes cannot alter execution; publishes its rolling 20-trade sample in R-multiples",
    "book-grimes":          "The Art & Science of TA as rules — a structural setup roster (pullback/failtest/keltner; breakout is Schwager's supply) behind a rolling replay gate: a setup may enter only while its trailing 120d record on the venue's own tape clears the bar (n≥20, net>0, t≥0.5); the scorecard is published every loop",
    "book-schwager":        "Market Wizards as rules — 4h Donchian-20 breakouts with EMA20>50 confirm; cut losses at 2×ATR, ride winners on a wide 3.5×ATR chandelier trail, NO profit target and NO pyramid (measured and refuted); one position per coin",
    "book-hull":            "Options, Futures & Other Derivatives as rules — delta-neutral funding receiver in the mid-band cell [7.8%,20%) TRUE × [$2M,$10M) that completes the Garrett|Hull|Farmer volume tiling; payback-velocity floor (the no-arbitrage cost band), 24h flip grace (basis noise ≠ signal, measured), adverse-basis entry veto",
    "band-kelly":           "holds the OPPOSITE side of the fleet's measured losers over exactly the windows the loser would have traded — v1 mirrors retired 🧲 Snap Back: LONG the premium-rich dislocations it shorted, SHORT the discounts it bought, exit when the ghost's own rules (converged/stop/2h) would have exited · refused/waiting mirror families publish in extra.roster · env-only, single-policy clock",
    "nav-cook":             "rides the SAME dislocations 🪁 band-kelly mirrors, in the band it REFUSES — premium [45,60) bps, strictly below the mirror's 60bps floor, so the two TILE the surface and every event this book takes is one band-kelly declines (I20 by BAND, not by row id) · non-crypto by nature (the band's crypto population is n=4) with pre-IPO excluded as the only class measured negative · 4h hold, exits on the venue's own index residual · env-only, single-policy clock",
    "perps-funding-spread": "ranks 72h mean funding across the venue's liquid books: LONG the K most-negative, SHORT the K most-positive, rebalances daily · K=8, $20/leg [30-Jul: K 5→8, universe 30→60]",
    "lighter-dislocation":  "fades Lighter-vs-index dislocations at an ADAPTIVE gate — a percentile of the live residual, floored at EXIT_BPS×1.5 (~60bps today, was a fixed 150) · universe up to 40 [30-Jul]",
    "lighter-perp-sniper":  "snipes debut-regime books: brand-new listings PLUS volume surges and any book under 21 daily candles [30-Jul — the listing diff alone was a one-loop trigger, hence n=1 in weeks]",
    "lighter-ticket-taker": "trades the Lighter Scout's high-conviction tickets · SHADOW arm takes all four lenses (breakout/dip/momentum/divergence) so the brain keeps grading them; the LIVE arm is DIVERGENCE-ONLY — the brain grades the other three negative at n≈1300–2600 · each close tagged by lens",
    "event-listing-sniper": "buys brand-new CEX listings — many tiny losses, occasional big wins by design",
    "scanner-cross-exchange-arb": "scans cross-exchange spreads and paper-fills observed gaps (optimistic basis, own subtotal)",
    "equities-regime":      "the venue's 10 non-crypto books: index-likes long above the 200d SMA (±1% band), single names + commodities on a 20/50 cross · $100 × up to 10 slots [30-Jul: 3→10 books, clip $250→$100]",
    "equities-momentum":    "qualifies close>SMA200 & SMA20>SMA50, ranks by 42d return, holds top-5 of 25 (US stocks + gold/silver/oil + BTC/ETH), weekly rotation · $180 × 5 slots",
    "pm-albanese":  "Parliament 🏛️ · rides 15m+1h EMA(12/48) agreement confirmed by a momentum burst · ML-gated, $25 × 3 slots",
    "pm-morrison":  "Parliament 🏛️ · chases 48-bar Donchian breaks confirmed by a volume spike · ML-gated, $25 × 3 slots",
    "pm-turnbull":  "Parliament 🏛️ · fades RSI<25/>75 stretch, stands down in expanding vol · ML-gated, $25 × 3 slots",
    "pm-abbott":    "Parliament 🏛️ · scalps strong 15m momentum bursts, tight TP/SL, ≤4h hold · ML-gated, $25 × 3 slots",
    "pm-rudd":      "Parliament 🏛️ · holds the side funding PAYS when |TRUE apr| ≥ 20%, trend-sanity-checked · $25 × 3 slots",
    "pm-gillard":   "Parliament 🏛️ · fades ≥25bps mark-vs-index premium (Lighter's OWN index), exits on reconverge · $25 × 3 slots",
}


def _num(v):
    """A real number, never a bool (isinstance(True, int) is True and a
    stray flag rendering as 'clip $1.00' is exactly the kind of confident
    wrong number this whole change exists to remove)."""
    return isinstance(v, (int, float)) and not isinstance(v, bool)


def live_units(row):
    """[2026-08-03] A card's sizing, read from the PROCESS's own payload.

    The units used to be typed into DESCRIPTIONS by hand, so the card asserted
    a clip and a cap that nothing verified — and on 3-Aug the Funding Farmer's
    line was wrong in all three numbers at once (see the note above its entry).
    Anything the growth rail, an env var or a promoted lever can move must be
    rendered from what the bot published, not from prose.

    Absent fields render NOTHING rather than a default: a bot that has not
    shipped the publisher yet must show no units at all, because a plausible
    wrong number is worse than a blank — the failure mode being closed here."""
    e = (row or {}).get("extra") or {}
    if not isinstance(e, dict):
        return ""
    bits = []
    if _num(e.get("clip_usd")):
        bits.append(f"clip ${e['clip_usd']:,.2f}")
    if _num(e.get("cap_usd")):
        bits.append(f"cap ${e['cap_usd']:,.0f}")
    if _num(e.get("max_open")):
        bits.append(f"{int(e['max_open'])} slots")
    if _num(e.get("enter_apr")):
        bits.append(f"enter ≥{e['enter_apr']:.2%} TRUE apr")
    return " · ".join(bits)


def desc_for(bot, row=None):
    base, _ = venue_variant(bot)
    desc = DESCRIPTIONS.get(base, "")
    units = live_units(row)
    return " · ".join(p for p in (desc, units) if p)
def label_for(bot):
    base, suf = venue_variant(bot)
    if suf:
        tag = VENUE_SUFFIXES[suf][0]
        return f"{LABELS.get(base, base)} — {tag} · Lighter"
    return LABELS.get(bot, bot)

# Paper bots (freqtrade + perps) all start with a $1,000 simulated balance, so
# total P&L = equity - this. Stocks/scanners report on their own basis.
PAPER_START_EQUITY = 1000.0

STALE_SECONDS = 180  # crypto bots loop fast; older than this = "stale"
# Stock bots publish far less often (IKBR every 2h, Alpaca daily), so they need a
# much longer window before they should be considered stale.
STOCK_STALE_SECONDS = 26 * 3600
# Some perps bots run on slow candle loops and publish far less often than the
# fast crypto bots: perps-donchian-breakout loops every 5 min (4h candles), so a
# 180s threshold flags it STALE every cycle even when it is perfectly healthy.
# Give slow-loop bots a wider window (~15 min = 3 missed publishes) so a real
# outage still shows, but a normal 5-min cadence does not read as "down".
SLOW_LOOP = {"perps-donchian-breakout",
             "perps-funding-carry",  # 5-min loop: funding only changes hourly
             "freqtrade-mum", "freqtrade-dad", "freqtrade-avo-maria"}  # freqtrade 5m bots
SLOW_LOOP_STALE_SECONDS = 15 * 60
# The listing sniper publishes once per scan cycle, and every ~5th cycle is a
# full exchange-list reload that can run 8-9 minutes when slow exchanges hit
# their HTTP timeouts — a healthy sniper regularly goes >180s between writes.
# Give it its own window so those reload cycles stop tripping a false stale
# flag (the sniper also heartbeats mid-cycle now, but keep this as the backstop).
SNIPER_STALE_SECONDS = 900
# [2026-07-12] Venue-variant rows do NOT always share their base's cadence —
# the Lighter Tide Rider loops HOURLY (its base row is fed by the fast
# freqtrade poller) and the Funding Farmer loops 300s (its base was never in
# SLOW_LOOP after it took over the live slot). Both healthy LIVE bots were
# flapping "stale" on the dashboard most of every cycle. Explicit per-ROW
# windows sized ~2 missed publishes, so a real outage still shows fast.
VARIANT_STALE_SECONDS = {
    "crypto-trend-daily-lighter":    2 * 3600 + 600,   # hourly loop + debounce slack
    "crypto-trend-daily-lshadow":    2 * 3600 + 600,
    "perps-funding-lighter-lighter": 15 * 60,          # 300s loop
    "perps-funding-lighter-lshadow": 15 * 60,
    "perps-funding-spread-lshadow":  15 * 60,          # 300s loop (Counterweight)
    # [2026-07-17] 🎫 Ticket Taker: 300s cadence on BOTH arms — the shadow arm
    # from run_all.sh, the live arm from tickettaker_loop.sh, deliberately the
    # same so the two records stay comparable (the shadow arm is the control the
    # go-live rests on). ~2 missed publishes, matching the Funding Farmer's.
    "lighter-ticket-taker-lighter":  15 * 60,
    "lighter-ticket-taker-lshadow":  15 * 60,
}


def stale_secs_for(bot):
    """Per-bot stale threshold: each bot family has its own publish cadence."""
    if bot in VARIANT_STALE_SECONDS:   # variant cadence differs from its base
        return VARIANT_STALE_SECONDS[bot]
    bot, suf = venue_variant(bot)
    # [2026-07-13] Every -lshadow row gets the slow-loop window by default: the
    # 7-book family-lighter-shadow loop can exceed 180s around candle-refetch
    # bursts (governed REST pacing), which flapped the fresh shadow rows
    # "stale" + spammed the watchdog. 15 min = 3+ missed loops for every
    # shadow bot (90-300s cadences) — a real outage still shows fast.
    if suf == "-lshadow":
        return SLOW_LOOP_STALE_SECONDS
    if bot in STOCKS:
        return STOCK_STALE_SECONDS
    if bot in SLOW_LOOP:
        return SLOW_LOOP_STALE_SECONDS
    if bot == "event-listing-sniper":
        return SNIPER_STALE_SECONDS
    return STALE_SECONDS


# [2026-07-13 INTERACTIVE MANAGE] User-managed hidden set, persisted in
# bot_state so it survives dashboard redeploys. Complements the static
# RETIRED_ROWS above: code marks the officially-retired bots; this lets Eamon
# hide/unhide (and delete rows for) retired or bunk bots from the page itself
# instead of waiting for a code change. Applied inside fetch_rows, so the
# grid, the totals AND /pnl.json all respect it — one choke point.
HIDDEN_STATE_KEY = "dashboard-hidden-bots"


def fetch_hidden_bots():
    """{bot: iso_hidden_at} chosen via the Manage panel. {} on any error —
    a broken state read must never blank the whole dashboard."""
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_state') AS t")
                if cur.fetchone()[0] is None:
                    return {}
                cur.execute("SELECT state FROM bot_state WHERE bot = %s",
                            (HIDDEN_STATE_KEY,))
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return {}
        st = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        return dict(st.get("bots") or {})
    except Exception:  # noqa: BLE001
        return {}


def save_hidden_bots(bots):
    """Upsert the hidden set (same shape bot_pnl_store.save_state writes)."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_state (
                    bot        TEXT PRIMARY KEY,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    state      JSONB
                )
                """)
            cur.execute(
                """
                INSERT INTO bot_state (bot, updated_at, state)
                VALUES (%s, now(), %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at = now(), state = EXCLUDED.state
                """, (HIDDEN_STATE_KEY, json.dumps({"bots": bots})))
        conn.commit()
    finally:
        conn.close()


def delete_bot_row(bot):
    """Remove a bot's bot_pnl row. Dashboard-row only: ledger history
    (bot_trades / paper_trades / venue_orders / bot_equity_history) is kept,
    and an ACTIVE bot's row simply reappears on its next publish — so this
    can only permanently remove bots that no longer run. Returns rows deleted."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM bot_pnl WHERE bot = %s", (bot,))
            n = cur.rowcount
        conn.commit()
        return n
    finally:
        conn.close()


def fetch_all_bot_ids():
    """Every bot id present in bot_pnl (unfiltered) — feeds the Manage panel
    so retired/legacy rows can be deleted even though the grid filters them."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_pnl') AS t")
            if cur.fetchone()[0] is None:
                return []
            cur.execute("SELECT bot FROM bot_pnl ORDER BY bot")
            return [r[0] for r in cur.fetchall()]
    finally:
        conn.close()


def fetch_rows(hidden=None):
    """Return {bot: row_dict}. Raises on DB error (caller handles)."""
    import psycopg2
    import psycopg2.extras
    if hidden is None:
        hidden = fetch_hidden_bots()
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_pnl') AS t")
            if cur.fetchone()["t"] is None:
                return {}  # table not created yet (no bot has published)
            cur.execute("SELECT * FROM bot_pnl")
            # Drop legacy pre-rename rows so stale duplicates never reach the
            # grid, totals, or the /pnl.json feed. Venue-variant rows
            # (<base>-lighter/-ltest/-lshadow) pass when their base is a current
            # bot, so a live/shadow Lighter bot shows up automatically.
            return {r["bot"]: r for r in cur.fetchall()
                    if r["bot"] not in RETIRED_ROWS
                    and r["bot"] not in hidden
                    and (r["bot"] in CURRENT_BOTS
                         or venue_variant(r["bot"])[0] in CURRENT_BOTS)}
    finally:
        conn.close()


def fetch_fleet_alerts(hours=48):
    """Recent evidence alerts written by market_context.evaluate_evidence into
    bot_state('fleet-alerts'). Guarded — no alerts is an answer, not an error."""
    try:
        import psycopg2
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_state') AS t")
                if cur.fetchone()[0] is None:
                    return []
                cur.execute("SELECT state FROM bot_state WHERE bot = 'fleet-alerts'")
                row = cur.fetchone()
        finally:
            conn.close()
        if not row:
            return []
        st = row[0] if isinstance(row[0], dict) else json.loads(row[0])
        cut = time.time() - hours * 3600
        return [a for a in (st.get("alerts") or []) if (a.get("ts") or 0) >= cut]
    except Exception:
        return []


def fetch_analysis():
    """Return {strategy: {updated_at, analysis}} from bot_trade_analysis."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trade_analysis') AS t")
            if cur.fetchone()["t"] is None:
                return {}
            cur.execute("SELECT strategy, updated_at, analysis FROM bot_trade_analysis "
                        "ORDER BY strategy")
            return {r["strategy"]: r for r in cur.fetchall()}
    finally:
        conn.close()


def fetch_trades(bot=None, limit=500, include_open=False):
    """Return per-trade history rows from bot_trades (newest close first).

    Read-only; used by the no-auth /trades.json endpoint for the scheduled
    breakdowns and the win/loss deep dive. Dry-run paper trades only."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()["t"] is None:
                return []  # no bot has published trades yet
            clauses, params = [], []
            if not include_open:
                # [2026-07-28] IS NOT TRUE, not = FALSE: the column is
                # nullable and a feed omitting the key writes NULL — the
                # fetch_bot_quality leg was deliberately fixed to this
                # predicate; the union doctrine needs every reader on it.
                clauses.append("is_open IS NOT TRUE")
            if bot:
                clauses.append("bot = %s")
                params.append(bot)
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(int(limit))
            cur.execute(
                "SELECT bot, open_ts, close_ts, pair, is_open, profit_ratio, "
                "profit_abs, open_rate, close_rate, amount, stake_amount, "
                "duration_min, enter_tag, exit_reason, leverage "
                f"FROM bot_trades {where} "
                "ORDER BY close_ts DESC NULLS LAST, open_ts DESC LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


def fetch_paper_rows(bot=None, limit=500):
    """Per-trade rows from the durable paper_trades ledger (funding bots,
    sniper, live Lighter closes). [2026-07-14] The Jul-14 advisory review was
    blind to these books because only bot_trades had a read endpoint — this
    feeds /trades.json?source=paper so outside analysis sees the whole fleet."""
    import psycopg2
    import psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.paper_trades') AS t")
            if cur.fetchone()["t"] is None:
                return []
            clauses, params = [], []
            if bot:
                clauses.append("bot = %s")
                params.append(bot)
            else:
                # [2026-07-21 AUDIT FIX] the default window excludes the
                # sniper's side='skip' gate-log rows: 278 of the newest 500
                # were skip diagnostics of a RETIRED bot, crowding real
                # fleet history out of the very endpoint reviews read.
                # Still reachable explicitly via ?bot=<name>-skips.
                clauses.append("side IS DISTINCT FROM 'skip'")
            where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
            params.append(int(limit))
            # [2026-07-15 EVIDENCE] widened columns (side/tag/prices/size/extra)
            # serve too, so outside reviews read entry context, not just P&L.
            # side='skip' rows (sniper gate log) publish under the separate
            # 'event-listing-sniper-skips' name — reachable via ?bot=.
            cur.execute(
                "SELECT bot, trade_id, pair, pnl_abs, pnl_pct, opened_at, "
                "closed_at, reason, seen_at, side, tag, entry_price, "
                "exit_price, size, extra "
                f"FROM paper_trades {where} "
                "ORDER BY seen_at DESC LIMIT %s",
                params,
            )
            return list(cur.fetchall())
    finally:
        conn.close()


# [2026-07-05 INSIGHT] Bots whose strategies were reworked 2026-07-03 — their
# cards split "since rework" stats from lifetime so the NEW code is judged on
# its own trades (same era map as bot_learn.py).
ERA_START = {
    "crypto-intraday-15m": "2026-07-03T06:00Z",
    "crypto-swing-daily": "2026-07-03T06:00Z",
    "crypto-breakout-4h": "2026-07-03T06:00Z",
    "crypto-trendmomo-4h": "2026-07-03T06:00Z",
    "perps-regime-switch": "2026-07-03T10:00Z",
}
# Standing status labels so the dashboard tells you how to READ each bot.
BADGES = {
    "crypto-intraday-15m": ("PROBATION", "#d29922"),
    "perps-regime-switch": ("EXPERIMENT", "#d29922"),
    "crypto-trend-daily": ("CONTROL", "#58a6ff"),
    "crypto-trendmomo-4h": ("SLOW BY DESIGN", "#8b949e"),
}


def fetch_bot_quality():
    """{bot: quality dict} from closed trades in BOTH ledgers — win rate,
    profit factor, expectancy, last-close age, 24h count and the per-mode
    breakdown, plus 'since rework' era stats where an era is defined.

    [2026-07-16 UNIFIED] This read bot_trades ONLY, so every Lighter bot —
    including BOTH LIVE real-money rows (lighter-ticket-taker-lighter,
    perps-funding-lighter-lighter), which record to paper_trades — rendered
    blank while retired Kraken paper rows showed full stats. The bots with
    actual money had the least detail. Now every bot, live or shadow, gets
    identical metrics. [2026-07-17] The live trend row shown here used to be
    crypto-trend-daily-lighter (🌊 Tide Rider); it retired that day and 🎫
    Ticket Taker took the same sub-account, so lighter-ticket-taker-lighter is
    now the second live real-money row.

    Merged in SQL (UNION ALL -> GROUP BY bot), never client-side: wr/pf/exp
    are RATIOS, recomputable only from summed gross-win/gross-loss.
    Keys stay FULLY-SUFFIXED row ids — paper_trades.bot already carries the
    venue suffix (venues/__init__.py), so normalizing would merge a live book
    with its shadow twin. Ledger differences handled: pnl_abs vs profit_abs,
    closed_at(TEXT) vs close_ts, and paper_trades' side='skip' rows (the
    sniper's gate-rejection LOGS, not trades) which would poison every metric.
    """
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            parts = []
            cur.execute("SELECT to_regclass('public.bot_trades')")
            if cur.fetchone()[0] is not None:
                # is_open IS NOT TRUE (not = FALSE): the column is nullable, and
                # `= FALSE` silently drops closed-by-omission rows.
                parts.append("""
                    SELECT bot, profit_abs AS pnl_abs, close_ts, open_ts,
                           COALESCE(enter_tag,'?') AS enter_tag,
                           'bot_trades'::text AS src
                    FROM bot_trades
                    WHERE is_open IS NOT TRUE AND profit_abs IS NOT NULL""")
            cur.execute("SELECT to_regclass('public.paper_trades')")
            if cur.fetchone()[0] is not None:
                # enter_tag from `reason` ('<dir>_<exit>' -> '<dir>'), mirroring
                # bot_pnl_store.split_reason. NOT the `tag` column: Gap Scout
                # writes a venue ROUTE there ("kraken->coinbaseexchange").
                parts.append("""
                    SELECT bot, pnl_abs,
                           closed_at::timestamptz AS close_ts,
                           CASE WHEN pg_input_is_valid(opened_at,'timestamptz')
                                THEN opened_at::timestamptz END AS open_ts,
                           COALESCE(NULLIF(CASE WHEN reason ~ '^(long|short)[_-]'
                                                THEN split_part(reason,'_',1) END,''),
                                    '?') AS enter_tag,
                           'paper_trades'::text AS src
                    FROM paper_trades
                    WHERE closed_at IS NOT NULL
                      AND pg_input_is_valid(closed_at,'timestamptz')
                      AND side IS DISTINCT FROM 'skip'
                      AND pnl_abs IS NOT NULL""")
            if not parts:
                return {}
            u = "WITH u AS (" + " UNION ALL ".join(parts) + ") "

            cur.execute(u + """
                SELECT bot, COUNT(*) AS n,
                       COUNT(*) FILTER (WHERE pnl_abs > 0) AS w,
                       COALESCE(SUM(pnl_abs) FILTER (WHERE pnl_abs > 0), 0) AS gw,
                       COALESCE(SUM(pnl_abs) FILTER (WHERE pnl_abs < 0), 0) AS gl,
                       COALESCE(SUM(pnl_abs), 0) AS pnl,
                       MAX(close_ts) AS last_close,
                       COUNT(*) FILTER (WHERE close_ts > now() - interval '24 hours')
                           AS n24,
                       COUNT(DISTINCT src) AS nsrc
                FROM u GROUP BY bot""")
            life = {r[0]: r[1:] for r in cur.fetchall()}
            era = {}
            for bot, start in ERA_START.items():
                cur.execute(u + "SELECT COUNT(*), COUNT(*) FILTER (WHERE pnl_abs > 0), "
                            "COALESCE(SUM(pnl_abs), 0) FROM u "
                            "WHERE bot=%s AND open_ts >= %s", (bot, start))
                era[bot] = cur.fetchone()
            # per-mode (enter_tag) breakdown — era-scoped for reworked bots so
            # the dual-mode design is judged on current-code trades only
            tags = {}
            cur.execute(u + "SELECT bot, enter_tag, COUNT(*), "
                        "COUNT(*) FILTER (WHERE pnl_abs > 0), "
                        "COALESCE(SUM(pnl_abs),0) FROM u GROUP BY bot, enter_tag")
            for bot, tag, tn, tw, tpnl in cur.fetchall():
                if bot not in ERA_START:
                    tags.setdefault(bot, []).append(
                        {"tag": tag, "n": int(tn), "w": int(tw), "pnl": float(tpnl)})
            for bot, start in ERA_START.items():
                cur.execute(u + "SELECT enter_tag, COUNT(*), "
                            "COUNT(*) FILTER (WHERE pnl_abs > 0), "
                            "COALESCE(SUM(pnl_abs),0) FROM u "
                            "WHERE bot=%s AND open_ts >= %s GROUP BY enter_tag",
                            (bot, start))
                for tag, tn, tw, tpnl in cur.fetchall():
                    tags.setdefault(bot, []).append(
                        {"tag": tag, "n": int(tn), "w": int(tw), "pnl": float(tpnl)})
        out = {}
        for bot, (n, w, gw, gl, pnl, last_close, n24, nsrc) in life.items():
            n, w = int(n), int(w)
            if int(nsrc or 1) > 1:
                # A card blending a dead Kraken history with a live Lighter book
                # is the one merge failure that looks plausible and is wrong.
                print(f"[dashboard] {bot}: closes in BOTH ledgers — blended",
                      flush=True)
            q = {"n": n, "w": w, "wr": (100.0 * w / n if n else None),
                 "pf": (float(gw) / abs(float(gl)) if float(gl) else None),
                 # [2026-07-07 RESET-PROOF] lifetime ledger P&L — the durable sum
                 # that survives any live-counter wipe (the July-6 reset made the
                 # dashboard show $1000/0 while the ledger held 8 real trades).
                 "pnl": float(pnl),
                 "exp": (float(pnl) / n if n else None), "last_close": last_close,
                 "n24": int(n24 or 0),
                 "tags": sorted(tags.get(bot, []), key=lambda t: -t["n"])}
            if bot in era and era[bot]:
                en, ew, epnl = era[bot]
                q["era"] = {"n": int(en), "w": int(ew), "pnl": float(epnl)}
            out[bot] = q
        return out
    finally:
        conn.close()


def _sparkline(series):
    """Tiny inline SVG equity sparkline (green if up over the window)."""
    if len(series) < 2:
        return ""
    lo, hi = min(series), max(series)
    span = (hi - lo) or 1.0
    W, H = 130, 26
    pts = " ".join(f"{i * W / (len(series) - 1):.1f},{H - 2 - ((v - lo) / span) * (H - 4):.1f}"
                   for i, v in enumerate(series))
    color = "#3fb950" if series[-1] >= series[0] else "#f85149"
    return (f'<svg width="{W}" height="{H}" style="display:block">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5"/></svg>')


def build_sparks(hours=168):
    """{bot: (sparkline_svg, drawdown_pct_from_window_peak)} from equity history."""
    out = {}
    try:
        series = {}
        for ts_, bot, eq, _pnl in fetch_history(hours):
            if eq is not None:
                series.setdefault(bot, []).append(float(eq))
        for bot, vals in series.items():
            if len(vals) < 2:
                continue
            peak = max(vals)
            dd = (vals[-1] / peak - 1.0) * 100 if peak else 0.0
            out[bot] = (_sparkline(vals), dd)
    except Exception:
        pass
    return out


def _fetch_state(key):
    """One bot_state blob (market-pulse, learning-brain, ...) or None."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_state') AS t")
            if cur.fetchone()[0] is None:
                return None
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (key,))
            row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row[0], dict) else json.loads(row[0])
    finally:
        conn.close()


def fetch_pulse_strip():
    """(header_html, latest_dict) from the market_pulse collector."""
    try:
        st = _fetch_state("market-pulse")
        latest = (st or {}).get("latest") or {}
        mood = latest.get("mood")
        if mood is None:
            return "", {}
        col = "#3fb950" if mood > 0.1 else ("#f85149" if mood < -0.1 else "#d29922")
        ptxt = '<b style="color:#f85149">PANIC</b>' if latest.get("panic") else "calm"
        fund = latest.get("funding") or {}
        ftxt = " ".join(f"{k} {v['apr']:+.0f}%" for k, v in fund.items() if v)
        reg = latest.get("btc_regime") or {}
        rtxt = ""
        if reg:
            on = reg.get("risk_on")
            rc = "#3fb950" if on else "#f85149"
            rtxt = f' · BTC 4h <b style="color:{rc}">{"RISK-ON" if on else "RISK-OFF"}</b>'
        return (f'<span>Pulse <b style="color:{col}">{mood:+.2f}</b> · '
                f'F&amp;G <b>{latest.get("fear_greed")}</b> · {ptxt}{rtxt}'
                f'{" · funding " + html.escape(ftxt) if ftxt else ""}</span>', latest)
    except Exception:
        return "", {}


def evidence_board_card():
    """⚖️ [2026-07-15 EVIDENCE BOARD v2] The evidence organ's live output
    (bot_state 'evidence-board'): scored/corroborated items with trend +
    verdict, and its shadow-mode restrict-only proposals. Read-only render —
    the organ itself lives in evidence_board.py on the freqtrade-bots
    container. Fail-silent like every other card."""
    try:
        b = fetch_states(["evidence-board"]).get("evidence-board") or {}
        items = b.get("items") or []
        if not items:
            return ""
        _tr = {"escalating": "▲", "decaying": "▼", "steady": "•"}
        _sevc = {"warn": "#d29922", "action": "#f85149"}
        rows_html = []
        for i in items[:8]:
            col = _sevc.get(i.get("sev"), "#8b949e")
            dim = ' style="opacity:.45"' if i.get("verdict") in ("resolved", "stale") else ""
            prop = (f'<div class="muted" style="margin-left:14px">↳ would ({html.escape(str(b.get("mode","shadow")))}): '
                    f'{html.escape(str(i.get("proposal")))}</div>') if i.get("proposal") else ""
            rows_html.append(
                f'<div{dim}><span style="color:{col}">{_tr.get(i.get("trend"), "•")} '
                f'{i.get("score", 0):.1f}</span> {html.escape(str(i.get("msg") or i.get("key")))[:110]} '
                f'<span class="muted">[{html.escape(str(i.get("verdict")))}]</span></div>{prop}')
        age = ""
        try:
            _u = _iso_dt(b.get("updated"))
            if _u:
                age = f' · {int((dt.datetime.now(dt.timezone.utc) - _u).total_seconds() // 60)}m ago'
        except Exception:
            pass
        n_prop = len(b.get("proposals") or [])
        return (f'<div class="card"><h2>⚖️ Evidence board <span class="dot on"></span></h2>'
                f'<div class="muted">mode {html.escape(str(b.get("mode", "shadow")))} · '
                f'{len(items)} items · {n_prop} shadow proposals{age} — '
                f'{"restrict + EXPAND" if b.get("books") else "restrict-only"} levers · '
                f'the growth rail authors the shadow books\' lanes</div>'
                f'{"".join(rows_html)}</div>')
    except Exception:  # noqa: BLE001
        return ""


def _mins_until(iso_utc):
    """' in 42m' / ' in 4.5h' from an ISO-UTC stamp; ' now' right at it;
    '' when unparsable or already well past (stale sample). Relative on
    purpose — timezone-neutral wherever the operator reads it."""
    try:
        from datetime import datetime, timezone
        t = datetime.fromisoformat(str(iso_utc))
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        m = (t - datetime.now(timezone.utc)).total_seconds() / 60.0
        if m < -5:
            return ""
        if m <= 2:
            return " now"
        return f" in {m / 60:.1f}h" if m >= 90 else f" in {int(round(m))}m"
    except Exception:  # noqa: BLE001
        return ""


def autonomy_rail_card():
    """🤖 [2026-07-16] Autonomy / Growth Rail — one glance at the self-tuning
    stack that was headless until now (bot_state: fleet-tuning, scout-tuner,
    strategy-incubator, xp-queue, xp-judge, fleet-immune, fleet-regen,
    fleet-respiration, fleet-clock, impl-shortfall, gapscout-census). Read-only
    render; the organs live on the freqtrade-bots container. Fail-silent like
    every other card: a DARK organ omits its row, an all-dark fleet hides the
    card, any error renders nothing. One fetch_states round-trip for all 11."""
    try:
        s = fetch_states([
            "fleet-tuning", "scout-tuner", "fleet-proprioception",
            "strategy-incubator", "xp-queue",
            "xp-judge", "fleet-immune", "fleet-regen", "fleet-respiration",
            "fleet-clock", "impl-shortfall", "gapscout-census",
            "tuning-proposals",
        ])
        G, R, Y, M = "#1a7f37", "#d1242f", "#d29922", "#8b949e"

        def _d(x):   # money or dash — never "$None"
            try:
                return money(x) if isinstance(x, (int, float)) else "—"
            except Exception:  # noqa: BLE001
                return "—"

        def row(key, label, val, color=None):
            st = s.get(key) or {}
            if not st:
                return None                      # dark / never spoke -> omit
            fresh = _state_fresh(st)
            dim = "" if fresh else ' style="opacity:.45"'
            tail = "" if fresh else " · STALE"
            c = f'color:{color}' if color else ''
            return (f'<div{dim}><span class="muted">{html.escape(label)}</span> '
                    f'<b style="{c}">{html.escape(str(val))}{tail}</b></div>')

        def _f(x):   # float or None — payload numbers arrive as anything
            try:
                return float(x)
            except Exception:  # noqa: BLE001
                return None

        def _s(x):   # display string, never the literal "None"
            return "—" if x is None else str(x)

        def b_tuning():
            ft = s.get("fleet-tuning") or {}
            lv = ft.get("levers")
            lv = lv if isinstance(lv, dict) else {}
            lv = {k: x for k, x in lv.items() if _lever_unexpired(x)}
            live = sum(1 for x in lv.values()
                       if isinstance(x, dict) and x.get("lane") == "lighter-live")
            _brk = lever_lane_summary(lv)
            return row("fleet-tuning", "🎚️ Levers active",
                       f'{len(lv)}'
                       + (f' — {_brk}' if _brk else '')
                       + (f' · {live} LIVE' if live else ''),
                       Y if live else None)

        def b_tuner():
            tn = s.get("scout-tuner") or {}
            ntn = len(tn.get("enacted") or {})
            return row("scout-tuner", "🔧 Scout tuner",
                       f'{ntn} enacted · baseline {_d(tn.get("baseline_net"))}',
                       Y if ntn else None)

        def b_incubator():
            ic = s.get("strategy-incubator") or {}
            ch = ic.get("champion") or {}
            conf = ch.get("confidence") or "none"
            icv = ("no champion yet" if conf == "none" or ch.get("net") is None
                   else f'{conf} · net {_d(ch.get("net"))}'
                   + (f' (vs default {_d(ch.get("vs_default"))})'
                      if ch.get("vs_default") is not None else ''))
            npr = len(ic.get("prospects") or [])
            if npr:
                icv += f' · {npr} prospects'
            # the full genotype LEADERBOARD + prospect register live in the
            # dedicated incubator_card() below (operator: "no genotype list
            # on the pnl" → 16-Jul (ad); "no list of the prospective bots"
            # → 22-Jul); this row stays the one-line summary.
            return row("strategy-incubator", "🧬 Incubator", icv,
                       G if conf == "stable" else M)

        def b_queue():
            return row("xp-queue", "📥 XP queue",
                       f'{len((s.get("xp-queue") or {}).get("candidates") or [])} candidates')

        def b_judge():
            xj = s.get("xp-judge") or {}
            ph = xj.get("phase")
            return row("xp-judge", "⚖️ XP judge",
                       f'{_s(ph)} · {xj.get("candidate") or "—"}',
                       G if ph == "promoted" else (Y if ph == "running" else M))

        def b_immune():
            im = s.get("fleet-immune") or {}
            nsick, nq = len(im.get("sick") or []), len(im.get("quarantined_levers") or {})
            return row("fleet-immune", "🛡️ Immune",
                       f'{nsick} sick · {nq} quarantined · {im.get("pruned_alerts") or 0} pruned',
                       R if nsick else (Y if nq else G))

        def b_regen():
            rg = s.get("fleet-regen") or {}
            nrep, nop = len(rg.get("repaired") or []), len(rg.get("needs_operator") or [])
            return row("fleet-regen", "🩹 Regen",
                       f'{nrep} repaired' + (f' · {nop} NEED OPERATOR' if nop else ''),
                       R if nop else (Y if nrep else None))

        def b_resp():
            rp = s.get("fleet-respiration") or {}
            spo2 = _f(rp.get("spo2"))
            # missing SpO2 is UNKNOWN (grey), not a healthy green 0%
            rc = (M if spo2 is None else
                  R if spo2 < 0.7 else (Y if spo2 < 0.9 else G))
            pct = f"{int(round(spo2 * 100))}%" if spo2 is not None else "—"
            return row("fleet-respiration", "🫁 Respiration",
                       f'SpO2 {pct} · {_s(rp.get("state"))}', rc)

        def b_clock():
            ck = s.get("fleet-clock") or {}
            # clock v2 (16-Jul): NYSE open/close + the next market event
            ck_ny = ck.get("markets")
            ck_ny = ck_ny.get("nyse") if isinstance(ck_ny, dict) else None
            ck_ny = ck_ny if isinstance(ck_ny, dict) else {}
            ck_ne = ck.get("next_event")
            ck_ne = ck_ne if isinstance(ck_ne, dict) else {}
            ck_txt = f'{_s(ck.get("primary"))}' \
                + (" · THIN" if ck.get("thin_liquidity") else "")
            if ck_ny:
                ck_txt += ' · NYSE ' + ('open' if ck_ny.get("open") else 'closed')
            if ck_ne.get("at_utc"):
                ck_txt += (f' · {_s(ck_ne.get("market"))} {_s(ck_ne.get("event"))}'
                           f'{_mins_until(ck_ne.get("at_utc"))}')
            return row("fleet-clock", "🕰️ Clock", ck_txt,
                       Y if ck.get("thin_liquidity") else None)

        def b_shortfall():
            sf = s.get("impl-shortfall") or {}
            vd = sf.get("verdict")
            sc = R if vd == "live-slipping" else (G if vd == "live-ahead" else M)
            xs = sf.get("exit_slip_bps")
            gap = sf.get("gap_pp")
            return row("impl-shortfall", "📉 Live vs shadow",
                       f'{_s(vd)} · gap {_s(gap)}pp'
                       + (f' · exit-slip {xs}bps' if xs is not None else ''), sc)

        def b_census():
            # [2026-07-17 AUDIT] Gap Scout retired (6432868): it no longer
            # publishes, so this row could only ever render its own fossil
            # marked "· STALE". Drop it rather than teach the operator that a
            # STALE badge on this card is normal. Its board loop (the widen
            # ladder off `quiet_hours`) is inert for the same reason.
            return ""

        def b_proprio():
            pr = s.get("fleet-proprioception") or {}
            pc = pr.get("counts") or {}
            n_hurt = pc.get("hurting") or 0
            return row("fleet-proprioception", "🦾 Outcomes",
                       f'{pc.get("graded") or 0} graded of {pc.get("episodes") or 0} '
                       f'episodes · {pc.get("helping") or 0} helping · '
                       f'{n_hurt} hurting',
                       Y if n_hurt else (G if (pc.get("graded") or 0) else None))

        def b_proposals():
            # [2026-07-21] the organs' proposal channel: what the wider
            # organism is ASKING the tuners for right now (the tuners' own
            # gates decide). Summarized by author so one glance shows who is
            # proposing; dark/empty channel omits the row.
            tp = s.get("tuning-proposals") or {}
            props = [p for p in (tp.get("proposals") or {}).values()
                     if isinstance(p, dict) and _lever_unexpired(p)]
            if not props:
                return None
            by = {}
            for p in props:
                by.setdefault(str(p.get("set_by") or "?"), []).append(p)
            n_r = sum(1 for p in props if p.get("direction") == "restrict")
            txt = (f'{len(props)} open ({n_r} restrict / '
                   f'{len(props) - n_r} expand) · '
                   + " · ".join(f'{a}×{len(v)}' for a, v in sorted(by.items())))
            return row("tuning-proposals", "🗳️ Organ proposals", txt,
                       Y if n_r else None)

        rows = []
        # [2026-07-16 AUDIT FIX] one organ's odd-shaped payload used to throw
        # inside the single outer try and silently vanish the WHOLE card —
        # indistinguishable from "autonomy stack not running". Each row now
        # degrades alone.
        for build in (b_tuning, b_tuner, b_proposals, b_proprio, b_incubator,
                      b_queue, b_judge, b_immune, b_regen, b_resp, b_clock,
                      b_shortfall, b_census):
            try:
                rows.append(build())
            except Exception:  # noqa: BLE001
                rows.append(None)

        rows = [r for r in rows if r]
        if not rows:
            return ""
        return (f'<div class="card"><h2>🤖 Autonomy / Growth Rail '
                f'<span class="dot on"></span></h2>'
                f'<div class="muted">self-tuning stack · levers auto-revert on TTL · '
                f'nothing ratchets · live money gated</div>{"".join(rows)}</div>')
    except Exception:  # noqa: BLE001
        return ""


def parliament_card():
    """🏛️ [2026-07-21] The Parliament on the MAIN page (operator: "i cant see
    howard, vitals, or the 10 scanners on the pnl dashboard") — the six-layer
    chamber made visible where the operator actually looks, not just on
    /vitals.json. Renders Howard's brain vitals, the full 10-scanner bench
    (quiet members INCLUDED — absent is how gaps hide), the ML bench's
    prequential OOS accuracies, and the tuner bench's active levers.
    Read-only; bot_state 'parliament' + 'parliament-tuning' (Howard publishes
    both every 5 min from the freqtrade-bots container). Fail-silent like
    every card: a chamber that has never spoken hides the card; a STALE
    chamber renders dimmed with the honest tail."""
    try:
        s = fetch_states(["parliament", "parliament-tuning"])
        p = s.get("parliament") or {}
        if not p:
            return ""
        G, R, Y, M = "#1a7f37", "#d1242f", "#d29922", "#8b949e"
        fresh = _state_fresh(p)
        dim = "" if fresh else ' style="opacity:.45"'
        tail = "" if fresh else " · STALE"

        health = p.get("health") or {}
        stalled = health.get("stalled") or []
        stress = p.get("stress") or {}
        data = p.get("data") or {}
        books = p.get("books") or {}
        n_closed = sum(int(b.get("closed") or 0) for b in books.values()
                       if isinstance(b, dict))
        hcolor = R if stalled else (Y if stress.get("pause") else G)
        htxt = (f'{len(books)} books · {n_closed} closed · '
                f'{data.get("books") or 0} Lighter books tracked · '
                f'stress {stress.get("med_bps") if stress.get("med_bps") is not None else "—"}bps'
                + (' · ENTRY PAUSE' if stress.get("pause") else '')
                + (f' · STALLED {", ".join(stalled)}' if stalled else ''))
        rows = [f'<div{dim}><span class="muted">🧠 Howard</span> '
                f'<b style="color:{hcolor}">{html.escape(htxt)}{tail}</b></div>']

        ml = p.get("ml") or {}
        accs = ml.get("oos_acc") or {}
        if ml.get("enabled"):
            acc_txt = " · ".join(f'{k} {float(v):.0%}' for k, v in
                                 sorted(accs.items())) if accs else "—"
            mtxt = (f'{"READY" if ml.get("ready") else "warming"} · '
                    f'n={ml.get("n_seen") or 0} · {acc_txt}')
            rows.append(f'<div{dim}><span class="muted">🤖 Keating ML</span> '
                        f'<b style="color:{G if ml.get("ready") else M}">'
                        f'{html.escape(mtxt)}{tail}</b></div>')

        # [2026-07-21 AUDIT FIX] the tuning row judges freshness on the
        # TUNING payload's own updated+ttl_sec — it used to inherit the
        # `parliament` key's verdict, so a day-old lever list rendered
        # bright/current whenever Howard's other publish was healthy.
        t = s.get("parliament-tuning") or {}
        t_fresh = _state_fresh(t)
        t_dim = "" if t_fresh else ' style="opacity:.45"'
        t_tail = "" if t_fresh else " · STALE"
        act = t.get("active") or {}
        levers = [f'{bot.replace("pm-", "")}:{lv.get("param")}='
                  f'{lv.get("value")}'
                  for bot, lvs in sorted(act.items())
                  for lv in (lvs if isinstance(lvs, list) else [])]
        rows.append(f'<div{t_dim}><span class="muted">🎚️ Tuners</span> '
                    f'<b style="color:{Y if levers else ""}">'
                    f'{html.escape(" · ".join(levers) if levers else "no active levers (auto-reverted)")}'
                    f'{t_tail}</b></div>')

        bench = (p.get("scanners") or {}).get("bench") or {}
        table = ""
        if bench:
            # [2026-07-21 AUDIT FIX] last-fire ages are frozen AT PUBLISH by
            # Howard — rendering them raw on a stale payload said "5m ago"
            # about an hours-old fire. Re-base to now with the payload's own
            # age so the printed age is honest however stale the chamber is.
            _p_age = 0.0
            try:
                _pd = _iso_dt(p.get("updated"))
                if _pd is not None:
                    from datetime import datetime as _dt, timezone as _tz
                    _p_age = max(0.0, (_dt.now(_tz.utc) - _pd).total_seconds())
            except Exception:  # noqa: BLE001
                _p_age = 0.0
            trs = []
            for name, b in sorted(bench.items()):
                n = b.get("n") or 0
                if n:
                    last = (f'{html.escape(str(b.get("last_sym") or "—"))} · '
                            f'{int(((b.get("last_age_sec") or 0) + _p_age) / 60)}m ago')
                    style = ""
                else:
                    last, style = "quiet", ' style="opacity:.45"'
                trs.append(f'<tr{style}><td>{html.escape(name)}</td>'
                           f'<td style="text-align:right">{n}</td>'
                           f'<td style="text-align:right">{b.get("runs") or 0}</td>'
                           f'<td>{last}</td></tr>')
            table = ('<table style="width:100%;font-size:12px;margin-top:6px">'
                     '<tr class="muted"><th style="text-align:left">🔭 scanner</th>'
                     '<th style="text-align:right">signals</th>'
                     '<th style="text-align:right">runs</th>'
                     '<th style="text-align:left">last fire</th></tr>'
                     + "".join(trs) + '</table>')

        dot = "on" if fresh and not stalled else ""
        return (f'<div class="card"><h2>🏛️ Parliament '
                f'<span class="dot {dot}"></span></h2>'
                f'<div class="muted">six PM shadow books · Keating 🔭 10 scanners '
                f'+ 5-model ML · Howard 🧠 brain · $25 clips, shadow-only, '
                f'fleet-governed</div>{"".join(rows)}{table}</div>')
    except Exception:  # noqa: BLE001
        return ""


def incubator_card():
    """🧬 [2026-07-16] Incubator / Reproduction (bot_state 'strategy-incubator').
    The genotype-breeding stack made visible: the elite leaderboard of bred
    Ticket-Taker genotypes scored by replay over the recorded tape, the
    champion + its anti-overfit confidence (tentative / candidate / stable),
    and the funding candidates it proposes to the experiment judge.
    [2026-07-22 PROSPECT REGISTER (operator: "the incubator has no list of
    the prospective bots its created and their stats")]: renders the organ's
    durable `prospects` list (every genotype ever scored — latest + best-ever
    stats, origin, role, cycles seen) and `funding_prospects` (each proposal
    joined to its judge lifecycle: queued/running/promoted/abandoned/faded).
    Read-only render; the organ lives in strategy_incubator.py on the
    freqtrade-bots container. Fail-silent like every other card — empty
    state hides it."""
    try:
        b = fetch_states(["strategy-incubator"]).get("strategy-incubator") or {}
        elite = [e for e in (b.get("elite") or []) if isinstance(e, dict)]
        champ = b.get("champion") or {}
        pros = [p for p in (b.get("prospects") or []) if isinstance(p, dict)]
        fpros = [p for p in (b.get("funding_prospects") or [])
                 if isinstance(p, dict)]
        if not elite and not champ and not pros and not fpros:
            return ""
        G, R, M, Y = "#1a7f37", "#d1242f", "#8b949e", "#d29922"

        def _dm(x):
            return f"${money(x)}" if isinstance(x, (int, float)) else "—"

        def _geno(gt):
            if not isinstance(gt, dict):
                return ""
            # [2026-07-17] div = the divergence lens (taker.div_gap_pp), added
            # to the gene pool that day; without it the card silently omitted
            # the only SHORT lens's allele from every genotype it rendered.
            # [2026-07-22] unknown (future) genes render as k=v instead of
            # silently vanishing — the same omission class, closed for good.
            ab = {"BRK_RANGE": "brk", "DIP_RANGE": "dip", "MOMO_CHG": "momo",
                  "DIV_GAP_PP": "div", "TAKE_PROFIT": "tp", "STOP_LOSS": "sl",
                  "MAX_HOLD_H": "hold"}
            parts = [f"{ab[k]}{gt[k]}" for k in ab if k in gt]
            parts += [f"{k.lower()}={gt[k]}" for k in sorted(gt) if k not in ab]
            return html.escape(" ".join(parts))

        # champion line
        champ_line = ""
        if champ:
            conf = str(champ.get("confidence") or "—")
            cc = {"stable": G, "candidate": Y}.get(conf, M)
            vs = champ.get("vs_default")
            champ_line = (
                f'<div><span class="muted">champion</span> '
                f'<b style="color:{cc}">{html.escape(conf).upper()}</b> · '
                f'net {_dm(champ.get("net"))}'
                + (f' · vs default {_dm(vs)}' if isinstance(vs, (int, float)) else '')
                + f' · streak {champ.get("streak")} · '
                f'h1 {_dm(champ.get("h1"))} h2 {_dm(champ.get("h2"))}</div>')

        # THE PROSPECT REGISTER — the full bred-genotype list (rank order,
        # dormants last). Falls back to the old ≤5-row elite render only for
        # payloads predating the register.
        rows = []
        rolec = {"fittest": Y, "gamete": G, "scored": M,
                 "unmeasured": M, "dormant": M}
        for i, e in enumerate(pros[:12], 1):
            net = e.get("net")
            col = (G if isinstance(net, (int, float)) and net > 0
                   else (M if isinstance(net, (int, float)) and net == 0 else R))
            role = str(e.get("role") or "")
            mark = (' <span style="color:%s">✓both</span>' % G
                    if e.get("both_halves_pos") else "")
            best = (f' · best lcb {_dm(e.get("best_lcb"))}'
                    if isinstance(e.get("best_lcb"), (int, float))
                    and e.get("best_lcb") != e.get("lcb") else "")
            rows.append(
                f'<div><span class="muted">#{i}</span> '
                f'<b style="color:{rolec.get(role, M)}">{html.escape(role.upper())}</b> '
                f'<span style="color:{col}">{_dm(net)}</span>{mark} '
                f'<span class="muted">lcb {_dm(e.get("lcb"))} · '
                f'{e.get("closes") if e.get("closes") is not None else "—"}cl · '
                f'×{e.get("cycles") or 1} {html.escape(str(e.get("origin") or ""))}'
                f'{best}</span> '
                f'<span class="muted" style="font-size:.85em">'
                f'{_geno(e.get("genotype"))}</span></div>')
        if pros and len(pros) > 12:
            rows.append(f'<div class="muted" style="font-size:.85em">… '
                        f'{len(pros) - 12} more tracked</div>')
        if not pros:
            for i, e in enumerate(elite[:5], 1):
                net = e.get("net")
                col = (G if isinstance(net, (int, float)) and net > 0
                       else (M if isinstance(net, (int, float)) and net == 0 else R))
                mark = (' <span style="color:%s">✓both</span>' % G
                        if e.get("both_halves_pos") else "")
                rows.append(
                    f'<div><span style="color:{col}">#{i} {_dm(net)}</span>{mark} '
                    f'<span class="muted">h1 {_dm(e.get("h1"))} h2 {_dm(e.get("h2"))}</span> '
                    f'<span class="muted" style="font-size:.85em">{_geno(e.get("genotype"))}</span></div>')

        # FUNDING PROSPECTS — each proposal's judge lifecycle (newest first)
        frows = []
        statc = {"promoted": G, "running": Y, "queued": M, "proposed": M,
                 "completed": M, "abandoned": R, "faded": R, "invalid": R}
        for e in list(reversed(fpros))[:8]:
            st = str(e.get("status") or "—")
            s = e.get("stats") or {}
            bits = []
            if s.get("n_shadow") is not None:
                bits.append(f'shadow n={s["n_shadow"]}')
            if s.get("n_live") is not None:
                bits.append(f'live n={s["n_live"]}')
            if isinstance(s.get("shadow_mean_pct"), (int, float)):
                bits.append(f'sh {s["shadow_mean_pct"]:+.2f}pp')
            if isinstance(s.get("live_mean_pct"), (int, float)):
                bits.append(f'lv {s["live_mean_pct"]:+.2f}pp')
            why = s.get("why")
            tail = (" · ".join(bits)
                    + (f' · {html.escape(str(why)[:60])}' if why else ""))
            frows.append(
                f'<div><b style="color:{statc.get(st, M)}">'
                f'{html.escape(st.upper())}</b> '
                f'{html.escape(str(e.get("name") or ""))} '
                f'<span class="muted" style="font-size:.85em">{tail}</span></div>')
        if frows:
            frows.insert(0, f'<div class="muted" style="margin-top:4px">'
                            f'funding prospects → judge ({len(fpros)})</div>')

        n_prop = len(b.get("proposed") or [])
        age = ""
        try:
            _u = _iso_dt(b.get("updated"))
            if _u:
                age = f' · {int((dt.datetime.now(dt.timezone.utc) - _u).total_seconds() // 60)}m ago'
        except Exception:
            pass
        n_cur = sum(1 for e in pros if str(e.get("role") or "") != "dormant")
        reg = (f'{len(pros)} prospects tracked ({n_cur} scored this cycle) · '
               if pros else "")
        return (f'<div class="card"><h2>🧬 Incubator / Reproduction '
                f'<span class="dot on"></span></h2>'
                f'<div class="muted">breeding {b.get("tape_snaps")} snaps '
                f'({html.escape(str(b.get("tape_source")))}) · {reg}{n_prop} '
                f'funding candidates → judge{age} — genotypes replay-scored; '
                f'champion only trusted when STABLE (anti-overfit)</div>'
                f'{champ_line}{"".join(rows)}{"".join(frows)}</div>')
    except Exception:  # noqa: BLE001
        return ""


def radar_card():
    """📡 [2026-07-23] Edge radar (bot_state 'fleet-radar'): every LIVING book
    graded on a constellation of sensors — significance (t), both-halves,
    median/jackknife robustness, trade rate — with an ETA to a |t|>=2 verdict.
    Read-only; the organ lives in fleet_radar.py on the freqtrade-bots
    container. Fail-silent — no state hides the card (it first publishes ~11 min
    after that container boots, then every 30 min)."""
    try:
        r = fetch_states(["fleet-radar"]).get("fleet-radar") or {}
        books = [b for b in (r.get("books") or []) if isinstance(b, dict)]
        if not books:
            return ""
        summ = r.get("summary") or {}
        CLS = {"real_edge": ("🟢", "#1a7f37"), "plausible": ("🟡", "#d29922"),
               "artifact": ("🟠", "#e3742f"), "weak": ("⚪", "#8b949e"),
               "noise": ("⚫", "#6e7681"), "losing": ("🔴", "#d1242f"),
               "starved": ("🌫️", "#6a8ba8")}
        order = ["real_edge", "plausible", "artifact", "weak", "noise",
                 "losing", "starved"]
        ARR = {"decaying": ("↓", "#d1242f"), "emerging": ("↑", "#1a7f37"),
               "stable": ("→", "#8b949e"), "insufficient": ("·", "#6e7681")}
        rows = []
        for b in books:
            cls = str(b.get("class") or "")
            ic, col = CLS.get(cls, ("·", "#8b949e"))
            t = b.get("radar_t")
            t = t if isinstance(t, (int, float)) else 0.0
            aic, acol = ARR.get(str(b.get("trajectory")), ("·", "#6e7681"))
            cav = list(b.get("caveats") or [])
            if b.get("twin_role") == "control":
                cav.append("twin")
            flag = (f'<span style="color:#d29922"> ⚠{html.escape(",".join(cav))}</span>'
                    if cav else "")
            rows.append(
                '<div style="display:flex;gap:6px;font-size:.85em;padding:1px 0;'
                'white-space:nowrap">'
                f'<span style="width:70px;color:{col}">{ic} {html.escape(cls)}</span>'
                f'<span style="flex:1;overflow:hidden;text-overflow:ellipsis">'
                f'{html.escape(str(b.get("bot")))}{flag}</span>'
                f'<span class="muted" style="width:30px;text-align:right">'
                f'n{b.get("n")}</span>'
                f'<span style="width:44px;text-align:right;color:{col}">'
                f't{t:+.1f}</span>'
                f'<span style="width:14px;text-align:center;color:{acol}" '
                f'title="trajectory: {html.escape(str(b.get("trajectory")))}">{aic}</span>'
                f'<span class="muted" style="width:224px;overflow:hidden;'
                f'text-overflow:ellipsis">{html.escape(str(b.get("eta") or ""))}'
                '</span></div>')
        cnt = " · ".join(f'{CLS[c][0]}{len(summ.get(c) or [])}'
                         for c in order if summ.get(c))
        age = ""
        try:
            _u = _iso_dt(r.get("updated"))
            if _u:
                _m = int((dt.datetime.now(dt.timezone.utc) - _u).total_seconds() // 60)
                age = f' · {_m}m ago'
        except Exception:
            pass
        return (f'<div class="card"><h2>📡 Edge radar '
                f'<span class="dot on"></span></h2>'
                f'<div class="muted">{r.get("n_books")} living books · {cnt}{age}'
                f' — significance + both-halves + median/jackknife + '
                f'ETA-to-verdict (publish-only, no consumer yet)</div>'
                f'{"".join(rows)}</div>')
    except Exception:  # noqa: BLE001
        return ""


#: The six go-live bars, rendered left-to-right in the order
#: `scripts/golive_readiness.BAR_NAMES` publishes them. Label + tooltip only —
#: the PASS/FAIL decision is the grader's, never re-derived here (the dashboard
#: re-deriving a rule is how the (fk) gate drifted from its own documentation).
GOLIVE_BARS = [
    ("window", "d", "window >= 30 days"),
    ("closes", "n", "closes >= 30 — evidence is denominated in FILLS"),
    ("mean", "μ", "mean per-trade > 0"),
    ("t", "t", "t >= 2.0 — significance, not just a positive mean"),
    ("halves", "½", "both halves positive"),
    ("maxdd", "▽", "max drawdown < 15%"),
]


def golive_card():
    """🚦 [2026-07-30] The go-live gate, made VISIBLE (bot_state
    'golive-readiness', published 6-hourly by scripts/golive_readiness.py).

    Why this card exists. The (fk) bar is the one rule that decides whether a
    $1,000 shadow book may ever hold real money, and until today it had no
    publisher and no schedule — it ran when a human typed the command, so
    between reviews there was no way to see that (for instance) 🌾 Yield
    Harvester was passing five of six bars and failing only the 30-day window.
    A gate nobody can read is not a gate; it is a memory.

    Renders each living book's six bars as chips, worst-first is NOT the sort —
    CLOSEST FIRST is, because the operator's question is "who is next?". The
    win-rate column is shown because the (fk) rewrite made it informative
    rather than a bar, and 🌾 is the book that proves the difference.

    Read-only, fail-silent, and it promotes NOTHING: go-live remains an
    explicit operator act."""
    try:
        r = fetch_states(["golive-readiness"]).get("golive-readiness") or {}
        books = r.get("books") or {}
        if not isinstance(books, dict) or not books:
            return ""
        bar = r.get("bar") or {}
        ready = set(r.get("ready") or [])
        # closest to the bar first; ties broken by significance, then sample
        order = sorted(books.items(),
                       key=lambda kv: (-(kv[1].get("bars_passed") or 0),
                                       -(kv[1].get("t") or 0),
                                       -(kv[1].get("n") or 0)))
        rows = []
        for bot, b in order:
            if not isinstance(b, dict):
                continue
            passed = b.get("bars") or {}
            chips = []
            for key, glyph, tip in GOLIVE_BARS:
                on = bool(passed.get(key))
                col = "#1a7f37" if on else "#6e7681"
                bg = "rgba(26,127,55,.16)" if on else "rgba(110,118,129,.10)"
                chips.append(
                    f'<span title="{html.escape(tip)}: '
                    f'{"PASS" if on else "not yet"}" style="color:{col};'
                    f'background:{bg};border-radius:3px;padding:0 3px;'
                    f'font-size:.8em">{glyph}</span>')
            np_ = b.get("bars_passed") or 0
            is_ready = bot in ready or b.get("ready")
            # The (fk) divergence, shown rather than asserted: a book the NEW
            # bar admits and the retired win-rate rule would have rejected.
            note = ""
            if is_ready and not b.get("legacy_ready"):
                note = ('<span style="color:#1a7f37" title="passes the (fk) '
                        'bar; the retired win-rate rule would have rejected '
                        'it — this is the carry shape">✦</span>')
            elif b.get("legacy_ready") and not is_ready:
                note = ('<span style="color:#d1242f" title="the retired '
                        'win-rate rule would have ADMITTED this book">⚠</span>')
            # [2026-07-30 (hc)] POLICY ERA. When a book is graded on a subset of
            # its ledger the card must say so beside the sample size, or the
            # operator reads `n57` next to a book whose row says 82 closes and
            # has no way to tell which number the bars were computed from. The
            # tooltip carries the era's declared reason verbatim.
            era = b.get("era") if isinstance(b.get("era"), dict) else None
            era_chip = ""
            if era and era.get("since"):
                at = b.get("alltime") or {}
                era_chip = (
                    f'<span title="policy era since {html.escape(str(era.get("since")))}'
                    f' — graded on {era.get("closes_in_era")} of '
                    f'{era.get("closes_all_time")} closes. '
                    f'{html.escape(str(era.get("why") or ""))} All-time would read '
                    f'{at.get("bars_passed", "?")}/6, t{(at.get("t") or 0):+.2f}." '
                    f'style="color:#8250df;background:rgba(130,80,223,.14);'
                    f'border-radius:3px;padding:0 3px;font-size:.75em">'
                    f'era {html.escape(str(era.get("since"))[5:])}</span>')
            # [2026-07-30 (hf)] LEDGER INTEGRITY. A book whose ledger shows a
            # same-pair overlap cannot have come from one process, so its `n` is
            # not one book's trades and none of the six bars means what it says.
            # Rendered as a loud chip rather than folded into `fails`, because
            # this invalidates the row rather than adding a reason to it.
            integ = b.get("integrity") if isinstance(b.get("integrity"), dict) else None
            if integ and integ.get("two_writers"):
                era_chip += (
                    f'<span title="TWO WRITERS: '
                    f'{integ.get("same_pair_overlaps")} same-pair overlap(s), '
                    f'deepest {integ.get("deepest_overlap_h")}h on '
                    f'{html.escape(str(integ.get("deepest_overlap_pair")))}, peak '
                    f'{integ.get("peak_concurrent")} concurrent. One process '
                    f'cannot hold two positions in one symbol, so this ledger is '
                    f'more than one book&#39;s record and n/t do not mean what '
                    f'they say. Operator action: stop the duplicate service." '
                    f'style="color:#d1242f;background:rgba(209,36,47,.14);'
                    f'border-radius:3px;padding:0 3px;font-size:.75em">'
                    f'2 writers</span>')
            # [2026-08-06 (ks)] GATE HORIZON — WHEN the book becomes decidable
            # at its measured trajectory. Published by the grader
            # (`gate_horizon`), never re-derived here; a payload without the
            # field renders exactly as before. Amber "→ date" = projected at
            # the current rate ("~" = low-confidence n); grey "≥ date" = a
            # window FLOOR (opens, not passes); red "∞ @trend" = unreachable
            # at the current trajectory (a trajectory statement, NOT a
            # retirement verdict — the tooltip says why); "undecidable" =
            # beyond the projection horizon, I17's keep-or-retire class.
            hz = b.get("horizon") if isinstance(b.get("horizon"), dict) else None
            if hz and hz.get("verdict") and hz.get("verdict") != "ready":
                _txt, _col, _bg = None, "#8b949e", "rgba(110,118,129,.10)"
                _hv = str(hz.get("verdict"))
                if _hv == "on_track" and hz.get("eta"):
                    _pre = "~" if hz.get("eta_conf") == "low" else ""
                    _txt = f'→ {_pre}{html.escape(str(hz["eta"])[5:])}'
                    _col, _bg = "#d29922", "rgba(210,153,34,.14)"
                elif _hv == "no_rate" and hz.get("eta"):
                    _txt = f'≥ {html.escape(str(hz["eta"])[5:])}'
                elif _hv == "unreachable":
                    _txt, _col, _bg = "∞ @trend", "#d1242f", "rgba(209,36,47,.14)"
                elif _hv == "undecidable":
                    _txt = "undecidable"
                elif _hv == "unprojectable":
                    # [(la)] A 5/6 BOOK MUST NOT BE THE ONE WITH NO CHIP.
                    # `unprojectable` fires when ONLY the halves bar fails —
                    # the book CLOSEST to the gate — and it had no branch
                    # here, so a 2/6 book showed a chip and a 5/6 book showed
                    # nothing. The operator reads that absence as "no data"
                    # rather than "one path-property bar, mends by trading".
                    _txt = "halves only"
                if _txt:
                    era_chip += (
                        f'<span title="{html.escape(str(hz.get("why") or ""))}'
                        f' — a projection at the current measured trajectory, '
                        f'never a promise; re-derived each publish." '
                        f'style="color:{_col};background:{_bg};'
                        f'border-radius:3px;padding:0 3px;font-size:.75em">'
                        f'{_txt}</span>')
            miss = "; ".join(str(x) for x in (b.get("fails") or [])[:2])
            col = ("#1a7f37" if is_ready else
                   "#d29922" if np_ >= 5 else "#8b949e")
            dd = b.get("max_dd_pct")
            rows.append(
                '<div style="display:flex;gap:6px;font-size:.85em;padding:1px 0;'
                'white-space:nowrap">'
                f'<span style="width:38px;color:{col};text-align:right">'
                f'{np_}/6</span>'
                f'<span style="width:62px">{"".join(chips)}</span>'
                f'<span style="flex:1;overflow:hidden;text-overflow:ellipsis">'
                f'{html.escape(str(bot))} {note}{era_chip}</span>'
                f'<span class="muted" style="width:34px;text-align:right">'
                f'n{b.get("n")}</span>'
                f'<span style="width:44px;text-align:right;color:{col}">'
                f't{(b.get("t") or 0):+.1f}</span>'
                f'<span class="muted" style="width:46px;text-align:right" '
                f'title="win rate — REPORTED, not a bar since (fk)">'
                f'{(b.get("win_pct") or 0):.0f}%</span>'
                f'<span class="muted" style="width:52px;text-align:right" '
                f'title="max drawdown">'
                f'{"n/a" if dd is None else f"{dd:.1f}%"}</span>'
                f'<span class="muted" style="width:180px;overflow:hidden;'
                f'text-overflow:ellipsis">{html.escape(miss)}</span></div>')
        age = ""
        try:
            _u = _iso_dt(r.get("updated"))
            if _u:
                _m = int((dt.datetime.now(dt.timezone.utc) - _u).total_seconds() // 60)
                age = f' · {_m}m ago'
        except Exception:
            pass
        head = (f'{len(ready)} at the bar' if ready
                else 'none at the bar yet')
        # [2026-08-06 (kv)] BOOKS BELOW THE PUBLISH FLOOR — one muted footer
        # line. These are the I17 cases the horizon exists to surface (📊
        # equities-regime at 0 closes ever, a newborn 🎸 Barnesy accruing its
        # first closes) and until now they were invisible on the very card
        # built to show gate distance. Absent key = old payload = no line.
        bf = r.get("below_floor") if isinstance(r.get("below_floor"), dict) \
            else None
        bf_line = ""
        # [(la)] The DARK check must sit OUTSIDE the below-floor guard — a
        # dark sweep with no thin books produces an EMPTY map, which is
        # exactly when the warning matters and exactly when an inside-the-
        # guard check cannot fire. (Caught by its own test before ship.)
        rm = r.get("roster") if isinstance(r.get("roster"), dict) else {}
        dark = ""
        if rm and (rm.get("error") or not rm.get("scanned")):
            dark = ('<div style="font-size:.75em;color:#d1242f" '
                    'title="The zero-ledger roster sweep did not run, so '
                    'books with no ledger rows are NOT covered by the line '
                    'above.">roster sweep DARK — zero-ledger books not '
                    'covered (' +
                    html.escape(str(rm.get("error") or "scanned 0")) +
                    ')</div>')
        if bf or dark:
            parts = []
            for b, v in sorted((bf or {}).items()):
                if not isinstance(v, dict):
                    continue
                h = v.get("horizon") if isinstance(v.get("horizon"), dict) \
                    else {}
                p = html.escape(f'{b} n{v.get("n_alltime")}')
                # [(la)] KEY THE GLYPH ON THE VERDICT THE PUBLISHER SENDS, and
                # never drop one. This stamped `≥` — the card's own FLOOR
                # glyph, defined 40 lines up — on ANY eta, so live Barnesy's
                # PROJECTED 05-09 read as a floor; and a below-floor book
                # whose verdict is unreachable/undecidable has eta=None, so it
                # rendered as a bare `bot nN`, byte-identical to a book with
                # no horizon at all. Those are precisely the two verdicts
                # carrying an I17 keep-or-retire call, invisible on the line
                # built to surface I17.
                _bhv, _beta = str(h.get("verdict") or ""), h.get("eta")
                if _beta:
                    p += ((' &rarr;' if _bhv == "on_track" else ' &ge;')
                          + html.escape(str(_beta)[5:]))
                elif _bhv == "unreachable":
                    p += ' &infin;@trend'
                elif _bhv == "undecidable":
                    p += ' undecidable'
                _bwhy = h.get("why")
                parts.append(f'<span title="{html.escape(str(_bwhy))}">{p}</span>'
                             if _bwhy else p)
            # (kw) made the sweep self-reporting and left every CONSUMER
            # blind: on a dark `fetch_bot_pnl` the roster books simply vanish
            # from this line and the footer just gets shorter — silently
            # dropping 📊 equities-regime, the standing I17 case it exists
            # for. `dark` is computed above the guard for that reason.
            if parts or dark:
                bf_line = (
                    '<div class="muted" style="font-size:.75em;padding-top:2px"'
                    ' title="Below the grader&#39;s publish floor — too few '
                    'closes to grade. Undecidable until they close trades '
                    '(I17: keep-or-retire, not another tuning pass).">'
                    + ('below floor: ' + " · ".join(parts) if parts else '')
                    + '</div>' + dark)
        return (f'<div class="card"><h2>🚦 Go-live grader '
                f'<span class="dot on"></span></h2>'
                f'<div class="muted">{len(rows)} graded books · {head}{age} — '
                f'bar: &ge;{bar.get("min_days", 30):g}d, '
                f'&ge;{bar.get("min_closes", 30)} closes, mean&gt;0, '
                f't&ge;{bar.get("min_t", 2.0):g}, both halves +, maxDD&lt;'
                f'{100 * (bar.get("max_dd") or 0.15):.0f}%. '
                f'Win% is reported, NOT a bar. Grades only — go-live is an '
                f'explicit operator act.</div>'
                f'{"".join(rows)}{bf_line}</div>')
    except Exception:  # noqa: BLE001
        return ""


# ---------------------------------------------------------------------------
# [2026-08-26] 🏭 THE PRODUCTION PIPE — "where does a new book actually get
# stuck?", answered at a glance instead of by hand-reading /bus.json.
#
# Eamon's standing complaint is that the inventions have not produced: no new
# bot has appeared on the dashboard as a promoted, real-money book. The fleet
# already publishes every number needed to answer that — across FOUR keys the
# dashboard fetches anyway — and nobody had joined them.
#
# IT LEADS WITH THE PROMOTION PIPE, NOT THE GO-LIVE BARS, and that ordering is
# the whole point of the card. Leading with the bars shows a dozen books
# failing on EVIDENCE — the one blocker nobody can clear this week, because it
# is arithmetic on a sample that does not exist yet. The judge's pairs are
# where a session can actually move something: on the live payload the day this
# shipped, three of four pairs were `unjudgeable` on a POLICY STAMP or a scan
# ORDER, not on performance. That is a wire, and a wire can be closed.
#
# So every blocker is sorted into one of three classes, and the class says who
# owns it:
#   * MEASUREMENT — no owner needed, the clock does it (closes must accrue).
#   * DECISION    — owner: Eamon (a keep-or-retire, an override flip).
#   * WIRE        — a code gap a session can close today.
# An unrecognised state is UNKNOWN and says so; it never falls into a class it
# was not measured into (I8: unknown degrades to honest, never to a guess).
# ---------------------------------------------------------------------------

#: Blocker classes. `done` = not blocked. The tuple is
#: (label, colour, background, tooltip).
PIPE_MEASURE, PIPE_DECIDE = "measure", "decide"
PIPE_WIRE, PIPE_DONE, PIPE_UNKNOWN = "wire", "done", "unknown"

PIPE_CLASS = {
    PIPE_MEASURE: ("⏳ measure", "#d29922", "rgba(210,153,34,.14)",
                   "BLOCKED ON A MEASUREMENT — no owner needed, the clock "
                   "does it: closes have to accrue before anything can be "
                   "judged."),
    PIPE_DECIDE: ("🧑 decide", "#8250df", "rgba(130,80,223,.14)",
                  "BLOCKED ON A DECISION — owner: Eamon. No amount of waiting "
                  "or coding moves this; it needs a call."),
    PIPE_WIRE: ("🔌 wire", "#0969da", "rgba(9,105,218,.14)",
                "BLOCKED ON A WIRE — a code gap someone can close. This is "
                "the class a session can clear this week."),
    PIPE_DONE: ("✓ moving", "#1a7f37", "rgba(26,127,55,.16)",
                "not blocked — this pair is judgeable and running."),
    PIPE_UNKNOWN: ("? unknown", "#d1242f", "rgba(209,36,47,.14)",
                   "the judge published a state this card does not recognise. "
                   "Deliberately NOT filed under a class — an unmapped reason "
                   "must never render as a known blocker or as progress."),
}

#: `xp-judge` pairs[*].unjudgeable.reason -> blocker class. Keyed on the
#: JUDGE'S OWN reason strings (experiment_judge._pair_precheck's `_un(...)`
#: calls), so a new reason arriving from the publisher renders UNKNOWN rather
#: than being silently absorbed into whichever class happens to be nearest.
PIPE_PAIR_REASON = {
    # the stamp ships with the build; it wakes on the first stamped CLOSE each
    # side — i.e. it is waiting for trades, not for code.
    "policy_unstamped": PIPE_MEASURE,
    # every one of these needs a human to change something in the tree/config.
    "live_row_dark": PIPE_WIRE,
    # [(va)] the control arm's publisher is dead — the fix is the stopped or
    # crash-looping shadow SERVICE, not anything in the pair's config.
    "shadow_row_dark": PIPE_WIRE,
    "policy_mismatch": PIPE_WIRE,
    "parity_unreadable": PIPE_WIRE,
    "capacity_mismatch": PIPE_WIRE,
}

#: `xp-judge` pairs[*].phase -> blocker class, for the phases that carry no
#: `unjudgeable` block of their own.
PIPE_PAIR_PHASE = {
    "stood_down": PIPE_DECIDE,   # wake_when is an operator env flip
    "idle": PIPE_WIRE,           # judgeable; nothing in the candidate queue
    "running": PIPE_MEASURE,     # accruing closes toward the paired bar
    "promoted": PIPE_DONE,
}


def _pipe_syd(iso):
    """An ISO TIMESTAMP -> 'DD-Mon HH:MM Syd', or None if it is unparseable.

    Sydney-local because Eamon reads it (CLAUDE.md's timezone rule); the
    payloads themselves stay UTC. Deliberately refuses a BARE DATE — see
    `_pipe_eta`.

    `tzdata` can be absent on a slim image, so this mirrors
    `fleet_watchdog_svc._now_op`'s measured fallback rather than inventing a
    second policy: a fixed +10 stamp, LABELLED `Syd*` so the star says it is
    right in winter and may be an hour out under daylight saving. The one
    thing it never does is hand back the bare UTC clock time."""
    d = _iso_dt(iso)
    if d is None:
        return None
    try:
        from zoneinfo import ZoneInfo
        return d.astimezone(ZoneInfo("Australia/Sydney")).strftime(
            "%d-%b %H:%M Syd")
    except Exception:  # noqa: BLE001
        return (d.astimezone(dt.timezone.utc)
                + dt.timedelta(hours=10)).strftime("%d-%b %H:%M Syd*")


def _pipe_eta(eta):
    """The grader's horizon `eta` -> (text, tooltip-suffix).

    The gate horizon publishes a bare CALENDAR DATE ('2026-11-10'), not an
    instant, so there is no time-of-day to convert and shifting it into Sydney
    would invent a day boundary the grader never computed (a UTC date spans two
    Sydney dates). It is therefore rendered AS PUBLISHED and LABELLED as the
    grader's UTC calendar date, rather than silently relabelled — the Sydney
    rule is about never handing over a bare unlabelled time, and a fabricated
    shift would be worse than an honest label."""
    if not eta:
        return None, ""
    return (str(eta), " The grader publishes this as a UTC calendar date "
                      "(no time of day), so it is shown unconverted; in "
                      "Sydney it lands on that date or the one after.")


def _pipe_stage(value, unknown_why):
    """One funnel stage -> its rendered HTML.

    THE TRAP THIS CLOSES: a dark key must render '?', never '0'. 'No book
    reached the bar' and 'nobody asked' are different findings that look
    identical once a missing payload is coerced to a number, and the second one
    silently reads as a healthy measurement. `None` is UNKNOWN."""
    if value is None:
        return ('<b style="color:#d1242f" title="UNKNOWN — '
                + html.escape(str(unknown_why)) + '">?</b>')
    return f'<b>{int(value)}</b>'


def _pipe_funnel(alloc, gl):
    """-> [(label, value|None, unknown_reason, tooltip)] — the production
    funnel, every stage from a named publisher field.

    `alloc`/`gl` are the FRESH payloads or None. A stage whose source is dark,
    stale or missing its field is None (unknown) and is rendered as such."""
    dark_a = "fleet-allocation is dark or stale — no roster to count"
    dark_g = "golive-readiness is dark or stale — no grades to count"

    rows_n = alloc.get("n_books") if isinstance(alloc, dict) else None
    rows_n = rows_n if isinstance(rows_n, int) else None

    # ever-closed = roster minus the organ's own declared zero-close list. An
    # ABSENT list is unknown; an EMPTY list is a real measurement (no zero-close
    # books), so `is None` is the test, never truthiness.
    zc = alloc.get("zero_close_books") if isinstance(alloc, dict) else None
    closed_n = (rows_n - len(zc)
                if rows_n is not None and isinstance(zc, list) else None)

    # I16 claims: max(0, mean - 1.28*SE) > 0. If NOT ONE book carries a numeric
    # `claim`, the field is absent from this payload version and the answer is
    # unknown — counting zero would assert "no book has evidence".
    claim_n, saw_claim = None, False
    books = alloc.get("books") if isinstance(alloc, dict) else None
    if isinstance(books, dict) and books:
        n = 0
        for v in books.values():
            c = v.get("claim") if isinstance(v, dict) else None
            if isinstance(c, (int, float)):
                saw_claim = True
                if c > 0:
                    n += 1
        claim_n = n if saw_claim else None

    # on-track: the grader's OWN horizon verdict, over graded books AND the
    # below-floor map (a thin book on track is still on track).
    track_n = None
    if isinstance(gl, dict):
        pool = {}
        for k in ("books", "below_floor"):
            m = gl.get(k)
            if isinstance(m, dict):
                pool.update(m)
        if pool:
            track_n = sum(
                1 for v in pool.values()
                if isinstance(v, dict)
                and str((v.get("horizon") or {}).get("verdict")) == "on_track")

    ready = gl.get("ready") if isinstance(gl, dict) else None
    bar_n = len(ready) if isinstance(ready, list) else None

    return [
        ("rows", rows_n, dark_a,
         "living book rows the allocation organ ranks"),
        ("ever closed", closed_n, dark_a,
         "rows with at least one closed trade — the rest are undecidable "
         "until they trade (I17)"),
        ("measured claim", claim_n, dark_a + " (or no book publishes `claim`)",
         "books whose I16 lower bound max(0, mean - 1.28*SE) is positive — "
         "evidence, not a lucky mean"),
        ("on track", track_n, dark_g,
         "books the gate horizon projects will reach the bar at their measured "
         "trajectory"),
        ("AT THE BAR", bar_n, dark_g,
         "books passing all six go-live bars right now. Go-live still needs "
         "Eamon's explicit act."),
    ]


def _pipe_pairs(judge):
    """-> [(class, pair_id, headline, wake_when, detail)] for every judge pair,
    WIRE first — the class a session can actually clear this week."""
    out = []
    pairs = judge.get("pairs") if isinstance(judge, dict) else None
    if not isinstance(pairs, dict):
        return out
    for pid, p in pairs.items():
        if not isinstance(p, dict):
            continue
        phase = str(p.get("phase") or "")
        un = p.get("unjudgeable") if isinstance(p.get("unjudgeable"), dict) else None
        sd = p.get("stood_down") if isinstance(p.get("stood_down"), dict) else None
        if un:
            reason = str(un.get("reason") or "")
            cls = PIPE_PAIR_REASON.get(reason, PIPE_UNKNOWN)
            head, wake, detail = reason or "unjudgeable", un.get("wake_when"), un.get("detail")
        elif sd:
            cls = PIPE_PAIR_PHASE.get(phase, PIPE_UNKNOWN)
            head = phase or "stood_down"
            wake, detail = sd.get("wake_when"), sd.get("why")
            if sd.get("successor"):
                detail = f'{detail or ""} → {sd["successor"]}'.strip()
        else:
            cls = PIPE_PAIR_PHASE.get(phase, PIPE_UNKNOWN)
            head, wake, detail = phase or "?", None, p.get("note")
        # the stamp census IS the measurement, so show it where it exists
        st = p.get("stamps") if isinstance(p.get("stamps"), dict) else None
        if st:
            bits = " · ".join(f'{k} {st[k]}' for k in ("live", "shadow") if st.get(k))
            if bits:
                detail = f'{detail or ""} [{bits}]'.strip()
        out.append((cls, str(pid), head, wake, detail))
    order = {PIPE_WIRE: 0, PIPE_DECIDE: 1, PIPE_MEASURE: 2,
             PIPE_UNKNOWN: 3, PIPE_DONE: 4}
    out.sort(key=lambda r: (order.get(r[0], 9), r[1]))
    return out


def pipeline_card():
    """🏭 The production pipe (bot_state `golive-readiness`, `xp-judge`,
    `fleet-allocation`, `strategy-incubator` — four keys the dashboard already
    fetches; no new source, no new deploy rule).

    Read-only and fail-silent, like every other card: it grades nothing,
    promotes nothing and writes no lever. What it does is JOIN the four organs
    that between them answer "why has no new bot reached real money?", and
    order the answer by who can act.

    HONESTY CONTRACT — the reason this card is worth testing at all. Every key
    may be dark, stale or missing a field, and a missing number here is
    dangerous in one specific direction: `0 at the bar` is a real and common
    measurement, so a dark grader coerced to zero renders as a confident,
    plausible, WRONG reading. So each funnel stage carries its own source and
    a dark source prints `?` with a tooltip naming what is missing, never a
    number and never a green state. A payload past `grace × ttl_sec` is
    treated as dark (I1: liveness before semantics) and said so in the header.
    The card hides entirely only when ALL FOUR keys are missing — a partially
    dark fleet is exactly when the unknowns need to be visible."""
    try:
        st = fetch_states(["golive-readiness", "xp-judge", "fleet-allocation",
                           "strategy-incubator"])
        raw = {k: (st.get(k) if isinstance(st.get(k), dict) else None)
               for k in ("golive-readiness", "xp-judge", "fleet-allocation",
                         "strategy-incubator")}
        if not any(raw.values()):
            return ""                      # nothing published at all — hide
        # I1: a stale payload is DARK for every value it would have supplied.
        stale = [k for k, v in raw.items() if v and not _state_fresh(v)]
        use = {k: (v if v and _state_fresh(v) else None) for k, v in raw.items()}
        gl, judge = use["golive-readiness"], use["xp-judge"]
        alloc, inc = use["fleet-allocation"], use["strategy-incubator"]

        # ---- the funnel -------------------------------------------------
        cells = []
        for label, val, why, tip in _pipe_funnel(alloc, gl):
            cells.append(
                f'<span title="{html.escape(tip)}">'
                f'{_pipe_stage(val, why)} '
                f'<span class="muted">{html.escape(label)}</span></span>')
        funnel = ('<div style="font-size:.95em;padding:2px 0">'
                  + ' <span class="muted">&rarr;</span> '.join(cells)
                  + '</div>')

        # ---- THE PROMOTION PIPE (leads) ---------------------------------
        rows = []
        pair_rows = _pipe_pairs(judge)
        if judge is None:
            rows.append('<div style="font-size:.85em;color:#d1242f" '
                        'title="xp-judge is dark or stale, so the promotion '
                        'pipe cannot be read at all. This is NOT the same as '
                        '&quot;no pairs are blocked&quot;.">'
                        'promotion pipe UNKNOWN — xp-judge dark or stale</div>')
        elif not pair_rows:
            rows.append('<div style="font-size:.85em;color:#d1242f" '
                        'title="xp-judge published no `pairs` map — an older '
                        'payload, or the census did not run. Not a clean '
                        'pipe.">promotion pipe UNKNOWN — no pairs '
                        'published</div>')
        for cls, pid, head, wake, detail in pair_rows:
            lab, col, bg, tip = PIPE_CLASS[cls]
            rows.append(
                '<div style="display:flex;gap:6px;font-size:.85em;padding:1px 0;'
                'white-space:nowrap">'
                f'<span title="{html.escape(tip)}" style="width:78px;'
                f'color:{col};background:{bg};border-radius:3px;padding:0 3px;'
                f'font-size:.9em;text-align:center">{lab}</span>'
                f'<span style="width:64px">{html.escape(pid)}</span>'
                f'<span style="width:130px;color:{col};overflow:hidden;'
                f'text-overflow:ellipsis">{html.escape(str(head))}</span>'
                f'<span class="muted" style="flex:1;overflow:hidden;'
                f'text-overflow:ellipsis"'
                + (f' title="wake_when: {html.escape(str(wake))}"' if wake else '')
                + f'>{html.escape(str(detail or ""))}</span></div>')
            if wake:
                rows.append(
                    '<div class="muted" style="font-size:.75em;padding-left:150px;'
                    'overflow:hidden;text-overflow:ellipsis;white-space:nowrap" '
                    'title="the judge&#39;s own `wake_when` — what has to '
                    'become true for this pair to start being judged">wake: '
                    + html.escape(str(wake)) + '</div>')

        # ---- BLOCKED ON A MEASUREMENT: the ETA'd books ------------------
        meas = []
        if gl is None:
            meas.append('<span style="color:#d1242f" title="golive-readiness '
                        'is dark or stale — no horizon to read">unknown '
                        '(grader dark)</span>')
        else:
            pool = {}
            for k in ("books", "below_floor"):
                m = gl.get(k)
                if isinstance(m, dict):
                    pool.update(m)
            for b, v in sorted(pool.items()):
                hz = (v.get("horizon") or {}) if isinstance(v, dict) else {}
                if str(hz.get("verdict")) != "on_track":
                    continue
                txt, note = _pipe_eta(hz.get("eta"))
                lab = (f'{b} &rarr; {html.escape(txt)}' if txt
                       else f'{b} <span style="color:#d1242f">eta unknown</span>')
                meas.append(f'<span title="{html.escape(str(hz.get("why") or ""))}'
                            f'{html.escape(note)}">{lab}</span>')
            if not meas:
                meas.append('<span class="muted">none — no book is on track '
                            'to the bar at its measured trajectory</span>')
        meas_line = ('<div style="font-size:.8em;padding-top:3px" '
                     'title="BLOCKED ON A MEASUREMENT — nobody owns these; '
                     'they need closes. Dates are the grader&#39;s own '
                     'projection at the measured trajectory, never a promise.">'
                     '<span class="muted">⏳ measurement:</span> '
                     + " · ".join(meas) + '</div>')

        # ---- BLOCKED ON A DECISION: the I17 docket ----------------------
        if gl is None:
            dec = ('<span style="color:#d1242f">unknown — grader dark or '
                   'stale</span>')
        elif not isinstance(gl.get("decision_docket"), list):
            dec = ('<span style="color:#d1242f" title="this payload carries no '
                   '`decision_docket` — an older grader, or the docket read '
                   'failed. Not the same as an empty docket.">unknown — no '
                   'docket published</span>')
        else:
            dk = [d for d in gl["decision_docket"] if isinstance(d, dict)]
            if not dk:
                dec = ('<span class="muted">none open</span>')
            else:
                held = [d.get("days_held") for d in dk
                        if isinstance(d.get("days_held"), (int, float))]
                worst = max(dk, key=lambda d: (d.get("days_held") or 0))
                oldest = (f'longest {max(held):.0f}d — '
                          f'{html.escape(str(worst.get("book")))}'
                          if held else 'age unknown')
                since = _pipe_syd(worst.get("since"))
                dec = (f'<b>{len(dk)}</b> book(s) asking keep-or-retire · '
                       f'{oldest}'
                       + (f' <span class="muted">(since {html.escape(since)})'
                          f'</span>' if since else ''))
                if not gl.get("docket_valid", True):
                    dec += (' <span style="color:#d29922" title="the grader '
                            'could not read its own prior docket-seen map, so '
                            'every clock reads as first-seen today — the ages '
                            'above are FLOORS.">clocks unverified</span>')
        dec_line = ('<div style="font-size:.8em;padding-top:1px" '
                    'title="BLOCKED ON A DECISION — owner: Eamon. I17: a book '
                    'that cannot reach its own bar is a keep-or-retire call, '
                    'never another tuning pass.">'
                    '<span class="muted">🧑 decision (Eamon):</span> '
                    + dec + '</div>')

        # ---- the incubator: is anything even being bred? ----------------
        if inc is None:
            inc_txt = ('<span style="color:#d1242f">unknown — '
                       'strategy-incubator dark or stale</span>')
        else:
            ch = inc.get("champion") if isinstance(inc.get("champion"), dict) else {}
            fr = inc.get("frontier") if isinstance(inc.get("frontier"), dict) else {}
            cap = (inc.get("proposal_capacity")
                   if isinstance(inc.get("proposal_capacity"), dict) else {})
            el = inc.get("elite")
            net = ch.get("net")
            bits = [f'champion {("$" + money(net)) if isinstance(net, (int, float)) else "unknown"}'
                    f' ({html.escape(str(ch.get("confidence") or "—"))})',
                    ('frontier enactable '
                     + ('yes' if fr.get("enactable") is True
                        else 'no' if fr.get("enactable") is False else 'unknown')),
                    f'elite {len(el)}' if isinstance(el, list) else 'elite unknown']
            if cap.get("exhausted") is True:
                bits.append('<span style="color:#d29922">funding lane '
                            'EXHAUSTED</span>')
            elif isinstance(cap.get("untried"), int):
                bits.append(f'{cap["untried"]} untried')
            else:
                bits.append('<span style="color:#d1242f">funding lane '
                            'unknown</span>')
            inc_txt = " · ".join(bits)
        inc_line = ('<div style="font-size:.8em;padding-top:1px" '
                    'title="the reproduction organ. An empty elite list plus a '
                    'non-enactable frontier plus an exhausted funding lane '
                    'means nothing is currently queued to become a new book.">'
                    '<span class="muted">🧬 breeding:</span> '
                    + inc_txt + '</div>')

        # ---- header: liveness FIRST (I1) --------------------------------
        dark = sorted(k for k, v in raw.items() if not v)
        warn = ""
        if dark or stale:
            parts = []
            if dark:
                parts.append("dark: " + ", ".join(dark))
            if stale:
                parts.append("stale: " + ", ".join(sorted(stale)))
            warn = (f' · <span style="color:#d1242f" title="Every number this '
                    f'card would have taken from these keys reads UNKNOWN, not '
                    f'zero.">{html.escape(" · ".join(parts))}</span>')
        age = ""
        _a = _state_age_h(raw.get("xp-judge") or raw.get("golive-readiness"))
        if _a is not None:
            age = f' · judge {int(_a * 60)}m ago'
        return (f'<div class="card"><h2>🏭 Production pipe '
                f'<span class="dot on"></span></h2>'
                f'<div class="muted">shadow &rarr; graded &rarr; real money'
                f'{age}{warn} — read-only; promotes nothing. Blockers are '
                f'sorted by WHO can clear them: a wire is a code gap, a '
                f'measurement needs closes, a decision needs Eamon.</div>'
                f'{funnel}'
                f'<div class="muted" style="padding-top:4px">promotion pipe '
                f'(🧪 judge pairs) — wire-blocked first</div>'
                f'{"".join(rows)}{meas_line}{dec_line}{inc_line}</div>')
    except Exception:  # noqa: BLE001
        return ""


def brain_card_html():
    """Compact card for the learning loop's current state (bot_state 'learning-brain')."""
    try:
        st = _fetch_state("learning-brain")
        if not st:
            return ""
        runs = st.get("runs")
        hyp = st.get("hypotheses") or {}
        act = [e for e in hyp.values()
               if e.get("status") == "ACTIONABLE" and e.get("last_run") == runs]
        cand = [e for e in hyp.values()
                if e.get("status") == "candidate" and e.get("last_run") == runs]
        items = "".join(
            f'<div class="row"><span style="max-width:78%">'
            f'{html.escape((e.get("proposal") or "")[:95])}</span>'
            f'<b>{e.get("seen")}✓</b></div>' for e in (act + cand)[:4])
        if not items:
            items = ('<div class="muted">no current-era hypotheses yet — '
                     'evidence accumulating from the new code\'s trades</div>')
        return (f'<div class="card"><h2>🧠 Brain (bot_learn) <span class="dot on"></span></h2>'
                f'<div class="muted">run {runs} · {len(act)} actionable · '
                f'{len(cand)} candidates (proposals only — humans ship)</div>{items}</div>')
    except Exception:
        return ""


def money(x):
    try:
        return f"{float(x):+,.2f}"
    except (TypeError, ValueError):
        return "—"


def pct(x):
    try:
        return f"{float(x) * 100:+.2f}%"
    except (TypeError, ValueError):
        return "—"


def cls(x):
    try:
        return "pos" if float(x) >= 0 else "neg"
    except (TypeError, ValueError):
        return ""


def _ensure_history_table(conn):
    with conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS bot_equity_history (
            bot TEXT NOT NULL, ts TIMESTAMPTZ NOT NULL DEFAULT now(),
            equity DOUBLE PRECISION, pnl_abs DOUBLE PRECISION,
            PRIMARY KEY (bot, ts))""")


def snapshot_history_once():
    """Append the current bot_pnl equity/P&L for every bot into the history table.
    Run on a timer so EVERY bot gets an equity time-series with no bot changes."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    conn.autocommit = True
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute("INSERT INTO bot_equity_history (bot, ts, equity, pnl_abs) "
                        "SELECT bot, now(), equity, pnl_abs FROM bot_pnl "
                        "ON CONFLICT DO NOTHING")
    finally:
        conn.close()


def history_loop(interval=300):
    while True:
        try:
            snapshot_history_once()
        except Exception as e:  # noqa: BLE001
            print(f"[history] snapshot failed: {e}", flush=True)
        time.sleep(interval)


def fetch_history(hours=168):
    """(ts, bot, equity, pnl_abs) rows for the last N hours, oldest first.
    [2026-07-15 SALVAGE] hours=None -> the whole table (/history?hours=all)."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_equity_history') AS t")
            if cur.fetchone()[0] is None:
                return []
            where = ("" if hours is None
                     else f"WHERE ts > now() - interval '{int(hours)} hours' ")
            cur.execute("SELECT ts, bot, equity, pnl_abs FROM bot_equity_history "
                        f"{where}ORDER BY ts")
            return cur.fetchall()
    finally:
        conn.close()


def fetch_open_trades():
    """{bot: [trade dicts]} for currently-open trades (crypto holdings)."""
    import psycopg2, psycopg2.extras
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS t")
            if cur.fetchone()["t"] is None:
                return {}
            cur.execute("SELECT bot, pair, profit_abs, profit_ratio, open_rate "
                        "FROM bot_trades WHERE is_open = TRUE ORDER BY bot, pair")
            out = {}
            for r in cur.fetchall():
                out.setdefault(r["bot"], []).append(dict(r))
            return out
    finally:
        conn.close()


_ENRICH_CACHE = {"ts": 0.0, "data": {}}


def fetch_golive_dd():
    """{bot: {"pct": float|None, "basis": str|None, "why": str|None}} — the
    go-live drawdown bar, read off the grader's own `golive-readiness` payload.

    [(vg)] THE GRADER IS THE OWNER. `scripts/golive_readiness.py` publishes
    `max_dd_pct` per book as the WORSE of realised and mark-to-market (I9,
    (ia)), already a PERCENT (13.1 means 13.1%) — so it must never be passed
    through `pct()`, which multiplies by 100 and renders +1310.00%. Measured
    on the live payload: 14 graded books all carry it; the 6 `below_floor`
    books carry `why_absent` instead ("no closed trades in the ledger"), and
    the union covers every rendered row.

    A book the grader cannot speak for returns `pct=None` WITH its `why`, so
    the card can say UNKNOWN rather than omit the line. Absent entirely means
    the grader is dark — also unknown, never a plausible zero, because `0.0%`
    drawdown is a real everyday reading on this fleet and would be
    byte-identical to a dead grader.
    """
    st = fetch_states(["golive-readiness"]).get("golive-readiness") or {}
    out = {}
    for section in ("books", "below_floor"):
        for bot, rec in (st.get(section) or {}).items():
            if not isinstance(rec, dict):
                continue
            pct_v = rec.get("max_dd_pct")
            try:
                pct_v = float(pct_v) if pct_v is not None else None
            except (TypeError, ValueError):
                pct_v = None
            out[bot] = {"pct": pct_v,
                        "basis": rec.get("maxdd_basis"),
                        "why": rec.get("why_absent") or rec.get("mtm_why")}
    return out


def fetch_ledger_enrich():
    """[2026-07-07 UNIFORM CARDS] One cached ledger pass so EVERY bot's card
    carries the same fields regardless of what its publisher sends:
      * lifetime record + total P&L from the union ledger
        (bot_trades + paper_trades — the perps bots publish NULL wins/losses
        to bot_pnl even though the ledger knows their whole history),
      * TODAY's P&L: equity-curve delta since UTC midnight where the bot has
        an equity history (captures unrealized), else trades closed today,
      * last-close detail (pair, P&L, reason, when),
      * open positions for bots whose live book sits in bot_state (perps
        broker positions, funding carries) rather than bot_pnl.extra.
    Guarded: any failure degrades to {} and cards render as before."""
    import time as _time
    if _time.time() - _ENRICH_CACHE["ts"] < 20:
        return _ENRICH_CACHE["data"]
    import psycopg2
    import psycopg2.extras
    out = {}
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') t1, "
                        "to_regclass('public.paper_trades') t2, "
                        "to_regclass('public.bot_equity_history') t3, "
                        "to_regclass('public.bot_state') t4")
            g = cur.fetchone()
            parts = []
            if g["t1"]:
                parts.append("SELECT bot, pair, profit_abs AS pnl, "
                             "exit_reason AS reason, close_ts "
                             "FROM bot_trades WHERE close_ts IS NOT NULL")
            if g["t2"]:
                parts.append("SELECT bot, pair, pnl_abs, reason, "
                             "COALESCE(CASE WHEN pg_input_is_valid(closed_at, "
                             "'timestamptz') THEN closed_at::timestamptz END, "
                             "seen_at) FROM paper_trades")
            if parts:
                union = " UNION ALL ".join(parts)
                # [(vg)] 7d/30d P&L and best/worst join this SAME aggregate.
                # `card()` read `row["pnl_weekly"]`, `row["pnl_monthly"]`,
                # `row["best_trade"]` and `row["worst_trade"]` off a bot_pnl row
                # for weeks — four columns `bot_pnl` HAS NEVER HAD (its 12 are
                # bot, closed_trades, equity, extra, losses, open_trades,
                # pnl_abs, pnl_daily, pnl_pct, status, updated_at, wins), each
                # behind an `is not None` guard, so two card sections were
                # unreachable dead code on every bot forever. They are the
                # read-side residue of the 28-Jul doc-truth cleanup, which
                # struck those exact five names from `publish()`'s docs and
                # fixed the publisher and the docs but not the consumer.
                # Derived here from the ledger this pass already scans, so the
                # numbers are REALISED closes — the same basis as `record`.
                cur.execute(
                    f"WITH t AS ({union}) "
                    "SELECT bot, COUNT(*) n, SUM((pnl>0)::int) w, SUM(pnl) total, "
                    "COALESCE(SUM(pnl) FILTER (WHERE close_ts >= date_trunc('day', now())),0) today_closed, "
                    "COUNT(*) FILTER (WHERE close_ts >= date_trunc('day', now())) today_n, "
                    "SUM(pnl) FILTER (WHERE close_ts >= now() - interval '7 days') pnl_7d, "
                    "COUNT(*) FILTER (WHERE close_ts >= now() - interval '7 days') n_7d, "
                    "SUM(pnl) FILTER (WHERE close_ts >= now() - interval '30 days') pnl_30d, "
                    "COUNT(*) FILTER (WHERE close_ts >= now() - interval '30 days') n_30d, "
                    "MAX(pnl) best, MIN(pnl) worst "
                    "FROM t GROUP BY bot")
                for r in cur.fetchall():
                    b = out.setdefault(r["bot"], {})
                    n, w = int(r["n"]), int(r["w"] or 0)
                    b["record"] = {"n": n, "w": w, "l": n - w,
                                   "total": round(float(r["total"] or 0), 2)}
                    b["today_closed"] = round(float(r["today_closed"] or 0), 2)
                    b["today_n"] = int(r["today_n"] or 0)

                    def _num(v):
                        return round(float(v), 2) if v is not None else None
                    # n_* rides along so a window with NO closes stays
                    # distinguishable from one that closed exactly flat — the
                    # (hf)/I1 shape at the reporting layer, and the whole reason
                    # this card is being repaired in the first place.
                    b["pnl_7d"], b["n_7d"] = _num(r["pnl_7d"]), int(r["n_7d"] or 0)
                    b["pnl_30d"], b["n_30d"] = _num(r["pnl_30d"]), int(r["n_30d"] or 0)
                    b["best_trade"], b["worst_trade"] = _num(r["best"]), _num(r["worst"])
                cur.execute(
                    f"WITH t AS ({union}) "
                    "SELECT DISTINCT ON (bot) bot, pair, pnl, reason, close_ts "
                    "FROM t ORDER BY bot, close_ts DESC")
                for r in cur.fetchall():
                    out.setdefault(r["bot"], {})["last_close"] = {
                        "pair": r["pair"],
                        "pnl": (round(float(r["pnl"]), 2) if r["pnl"] is not None else None),
                        "reason": r["reason"],
                        "ts": r["close_ts"].isoformat() if r["close_ts"] else None}
            if g["t3"]:
                cur.execute(
                    "SELECT bot, (array_agg(equity ORDER BY ts DESC))[1] "
                    "- (array_agg(equity ORDER BY ts))[1] AS delta "
                    "FROM bot_equity_history "
                    "WHERE ts >= date_trunc('day', now()) GROUP BY bot")
                for r in cur.fetchall():
                    if r["delta"] is not None:
                        out.setdefault(r["bot"], {})["today_equity_delta"] = \
                            round(float(r["delta"]), 2)
            if g["t4"]:
                cur.execute("SELECT bot, state FROM bot_state WHERE bot IN "
                            "('perps-rsi-meanrev','perps-donchian-breakout',"
                            "'perps-funding-carry')")
                for r in cur.fetchall():
                    st = r["state"] if isinstance(r["state"], dict) else \
                        json.loads(r["state"] or "{}")
                    poss = []
                    br = st.get("broker") or {}
                    marks = br.get("marks") or {}
                    for coin, v in (br.get("pos") or {}).items():
                        try:
                            qty, entry = float(v[0]), float(v[1])
                            mark = marks.get(coin)
                            upnl = (round((float(mark) - entry) * qty, 2)
                                    if mark is not None else None)
                            poss.append({"pair": str(coin),
                                         "side": "long" if qty > 0 else "short",
                                         "qty": qty, "entry": entry, "upnl": upnl})
                        except Exception:
                            poss.append({"pair": str(coin), "side": "?",
                                         "qty": None, "entry": None, "upnl": None})
                    for coin, p in (st.get("positions") or {}).items():
                        if isinstance(p, dict) and "side" in p:
                            try:
                                net = round(float(p.get("accrued", 0))
                                            - float(p.get("fees", 0)), 2)
                            except Exception:
                                net = None
                            poss.append({"pair": str(coin),
                                         "side": ("short" if "short" in str(p.get("side"))
                                                  else "long"),
                                         "qty": p.get("notional"), "entry": None,
                                         "upnl": net})
                    if poss:
                        out.setdefault(r["bot"], {})["positions"] = poss
    finally:
        conn.close()
    _ENRICH_CACHE["ts"] = _time.time()
    _ENRICH_CACHE["data"] = out
    return out


def age_str(updated_at, threshold=STALE_SECONDS):
    if updated_at is None:
        return "never", True
    now = dt.datetime.now(dt.timezone.utc)
    if updated_at.tzinfo is None:
        updated_at = updated_at.replace(tzinfo=dt.timezone.utc)
    secs = (now - updated_at).total_seconds()
    stale = secs > threshold
    if secs < 90:
        return f"{int(secs)}s ago", stale
    if secs < 5400:
        return f"{int(secs // 60)}m ago", stale
    return f"{int(secs // 3600)}h ago", stale


def _holdings_html(bot, extra, open_trades):
    """Current holdings: stock bots from extra['positions']; crypto from open bot_trades."""
    items = []
    if isinstance(extra, dict):
        for p in (extra.get("positions") or []):
            # Stock bots publish a LIST of dicts here. Guard against any other
            # shape (a bot publishing {coin: "desc"} took the whole page down on
            # 2026-07-03 — a str has no .get). Non-dict entries render as text.
            if not isinstance(p, dict):
                items.append(f'<div class="row"><span>{html.escape(str(p))}</span></div>')
                continue
            up = p.get("upnl")
            up_html = f' <span class="{cls(up)}">{money(up)}</span>' if up is not None else ""
            items.append(f'<div class="row"><span>{html.escape(str(p.get("symbol")))} ×{p.get("qty")}</span>'
                         f'<b>{money(p.get("value"))}{up_html}</b></div>')
    for t in (open_trades.get(bot) or []):
        pr = t.get("profit_ratio")
        pr_html = f' <span class="{cls(pr)}">{pct(pr)}</span>' if pr is not None else ""
        items.append(f'<div class="row"><span>{html.escape(str(t.get("pair")))}</span>'
                     f'<b>{money(t.get("profit_abs"))}{pr_html}</b></div>')
    return f'<div class="sub">Holdings ({len(items)})</div>{"".join(items)}' if items else ""


def _orders_html(extra):
    if not (isinstance(extra, dict) and extra.get("open_orders")):
        return ""
    items = [f'<div class="row"><span>{html.escape(str(o.get("action")))} '
             f'{html.escape(str(o.get("symbol")))} ×{o.get("qty")}</span>'
             f'<b class="muted">{html.escape(str(o.get("status")))}</b></div>'
             for o in extra["open_orders"]]
    return f'<div class="sub">Open orders ({len(items)})</div>{"".join(items)}'


def card(bot, row, open_trades=None, quality=None, spark=None, mode_note=None,
         enrich=None, extra_html=""):
    open_trades = open_trades or {}
    en = enrich or {}
    badge = ""
    _base_bot, _suf = venue_variant(bot)
    if _base_bot in BADGES:
        _t, _c = BADGES[_base_bot]
        badge = (f' <span style="font-size:10px;border:1px solid {_c};color:{_c};'
                 f'border-radius:6px;padding:1px 5px;vertical-align:middle">{_t}</span>')
    # [2026-07-09 LIGHTER GO-LIVE] mode badge — LIVE (real money) stands out in
    # red-filled, TESTNET amber, SHADOW blue, so a live bot is unmistakable.
    if _suf:
        _vt, _vc, _ = VENUE_SUFFIXES[_suf]
        badge += (f' <span style="font-size:10px;border:1px solid {_vc};color:#fff;'
                  f'background:{_vc};border-radius:6px;padding:1px 6px;'
                  f'vertical-align:middle;font-weight:700;letter-spacing:.3px">{_vt}</span>')
    _desc = desc_for(bot, row)
    _desc_html = (f'<div class="desc">{html.escape(_desc)}</div>' if _desc else "")
    if row is None:
        return (f'<div class="card"><h2>{html.escape(label_for(bot))}{badge} '
                f'<span class="dot off"></span></h2>{_desc_html}'
                f'<div class="muted">no data yet — bot has not published</div></div>')
    thr = stale_secs_for(bot)
    age, stale = age_str(row.get("updated_at"), thr)
    status = (row.get("status") or "?")
    dot = "warn" if stale else ("off" if status in ("halted", "error") else "on")
    extra = row.get("extra") or {}
    if isinstance(extra, dict):
        _HIDE = {"positions", "open_orders", "open_pos", "err", "src", "port"}
        # [2026-08-04 (iy)] None values are dropped: shadow arms publish
        # cap_usd=null (no cap env by design) and the raw join rendered
        # "cap_usd: None" on two cards. An absent value is not a datum.
        _bits = {k: v for k, v in extra.items()
                 if k not in _HIDE and v is not None}
        extra_bits = " · ".join(f"{k}: {html.escape(str(v))}" for k, v in _bits.items())
    else:
        extra_bits = html.escape(str(extra))
    holdings_html = _holdings_html(bot, extra, open_trades)
    orders_html = _orders_html(extra)
    rows = []
    if row.get("equity") is not None:
        rows.append(f'<div class="row"><span>Equity</span><b>{money(row.get("equity"))}</b></div>')
    # [2026-07-05] Total P&L on EVERY bot card. The freqtrade bots publish
    # pnl_abs=None (their gain is equity - $1000 paper start), so they used to
    # show no P&L line at all — only Equity. Compute a total from whichever
    # source the bot exposes so every card states its number explicitly.
    _pnl_abs = row.get("pnl_abs")
    _eq = row.get("equity")
    # [2026-07-10] Live Lighter bots fund from real collateral (e.g. $65), NOT
    # the $1000 paper start — so NEVER apply the paper baseline to them, or an
    # untraded live account reads a phantom -$935. Their publisher sends real
    # pnl_abs (equity - starting collateral); if it's ever None, show nothing.
    _is_live = is_live_bot(bot)
    if (_pnl_abs is None and _eq is not None and bot not in STOCKS
            and bot not in SCANNERS and not _is_live):
        _pnl_abs = _eq - PAPER_START_EQUITY          # paper bots start at $1,000
    if _pnl_abs is not None:
        pnl_label = "Paper (arb)" if bot in SCANNERS else "Total P&amp;L"
        _pct = row.get("pnl_pct")
        if (_pct is None and _eq not in (None, 0) and bot not in STOCKS
                and bot not in SCANNERS and not _is_live):
            _pct = _pnl_abs / PAPER_START_EQUITY
        rows.append(f'<div class="row"><span>{pnl_label}</span>'
                    f'<b class="{cls(_pnl_abs)}">{money(_pnl_abs)}'
                    f'{" (" + pct(_pct) + ")" if _pct is not None else ""}</b></div>')
    # [2026-07-07 UNIFORM CARDS] Perps bots publish NULL closed/wins/losses to
    # bot_pnl even though the paper ledger has every close — fall back to the
    # ledger so every card shows a real record.
    _closed = row.get("closed_trades")
    if _closed is None and (en.get("record") or {}).get("n"):
        _closed = en["record"]["n"]
    if _closed is not None or row.get("open_trades") is not None:
        rows.append(f'<div class="row"><span>Trades</span>'
                    f'<b>{_closed or 0} closed · {row.get("open_trades") or 0} open</b></div>')
    if row.get("wins") is not None:
        rows.append(f'<div class="row"><span>Win / Loss</span>'
                    f'<b>{row.get("wins") or 0} / {row.get("losses") or 0}</b></div>')
    elif (en.get("record") or {}).get("n"):
        _r = en["record"]
        rows.append(f'<div class="row"><span>Win / Loss (ledger)</span>'
                    f'<b>{_r["w"]} / {_r["l"]} · {money(_r["total"])} lifetime</b></div>')
    # Daily / Weekly / Monthly P&L. [2026-07-07 UNIFORM CARDS] Today's figure
    # is computed server-side for EVERY bot: equity-curve delta since UTC
    # midnight where an equity history exists (captures unrealized moves),
    # else the sum of trades closed today from the ledger. A publisher-sent
    # pnl_daily still wins if a bot ever supplies one.
    pnl_daily   = row.get("pnl_daily")
    # [2026-07-08] a publisher-sent daily figure only counts as "today" while
    # its row was written today (UTC) — a once-a-day publisher (alpaca 22:00
    # cron) must not show yesterday's number all through the next day.
    _upd = row.get("updated_at")
    if pnl_daily is not None and _upd is not None:
        try:
            if _upd.astimezone(dt.timezone.utc).date() != dt.datetime.now(dt.timezone.utc).date():
                pnl_daily = None
        except Exception:
            pass
    if pnl_daily is None:
        pnl_daily = en.get("today_equity_delta")
        if pnl_daily is None and en.get("today_n"):
            pnl_daily = en.get("today_closed")
    # [(vg)] FROM THE LEDGER PASS, NOT FROM `row`. These read
    # `row["pnl_weekly"]`/`row["pnl_monthly"]` — bot_pnl columns that do not
    # exist — so both lines were unreachable on every bot, forever. REALISED
    # closes in the window, the same basis as the record line below.
    pnl_weekly  = en.get("pnl_7d")
    pnl_monthly = en.get("pnl_30d")
    if pnl_daily is not None:
        rows.append(f'<div class="row"><span>Today P&amp;L (UTC)</span>'
                    f'<b class="{cls(pnl_daily)}">{money(pnl_daily)}</b></div>')
    # `P&amp;L`, not `P&L` — a raw ampersand is invalid HTML, and it survived
    # here precisely because these two lines have never rendered: unreachable
    # code is also unexercised code. The neighbouring "Today P&amp;L" line,
    # which does render, had it right all along.
    if pnl_weekly is not None:
        rows.append(f'<div class="row"><span>7d P&amp;L</span>'
                    f'<b class="{cls(pnl_weekly)}">{money(pnl_weekly)}</b></div>')
    if pnl_monthly is not None:
        rows.append(f'<div class="row"><span>30d P&amp;L</span>'
                    f'<b class="{cls(pnl_monthly)}">{money(pnl_monthly)}</b></div>')
    # [(vg)] MAX DRAWDOWN IS A GO-LIVE BAR AND IT ALWAYS RENDERS NOW.
    # It read `row["max_drawdown"]`, a bot_pnl column that has never existed,
    # so the line was silently absent on every book — and absent is
    # byte-identical to "this book has no drawdown", on the one number that
    # governs whether real money is allowed. Sourced from the grader that owns
    # it (`golive_dd`, the WORSE of realised and MTM); UNKNOWN is stated with
    # the grader's own reason rather than dropped, because a missing row is
    # exactly the failure being repaired here.
    # UNITS: `max_dd_pct` is ALREADY a percent — `pct()` would render 13.1 as
    # +1310.00%. Formatted directly, and pinned by a test.
    _dd = en.get("golive_dd")
    if _dd and _dd.get("pct") is not None:
        _basis = _dd.get("basis")
        _bl = f' title="worse of realised and mark-to-market; basis: {_basis}"' \
            if _basis else ""
        rows.append(f'<div class="row"><span>Max Drawdown</span>'
                    f'<b style="color:#f85149"{_bl}>{_dd["pct"]:.1f}%</b></div>')
    else:
        _why = (_dd or {}).get("why") or "go-live grader is dark or stale"
        rows.append(f'<div class="row"><span>Max Drawdown</span>'
                    f'<b style="color:#8b949e" title="{html.escape(str(_why))}">'
                    f'unknown</b></div>')
    best_trade  = en.get("best_trade")
    worst_trade = en.get("worst_trade")
    if best_trade is not None or worst_trade is not None:
        rows.append(f'<div class="row"><span>Best / Worst trade</span>'
                    f'<b>{money(best_trade)} / {money(worst_trade)}</b></div>')
    # [2026-07-05 INSIGHT] quality metrics from the durable trade ledger
    q = quality or {}
    if q.get("n"):
        pf = q.get("pf")
        pf_txt = f"{pf:.2f}" if pf is not None else ("∞" if q.get("w") else "—")
        rows.append(f'<div class="row"><span>Quality (ledger)</span>'
                    f'<b>{q["wr"]:.0f}% win · PF {pf_txt} · {money(q["exp"])}/trade</b></div>')
        pass  # last-close now rendered for EVERY bot below (2026-07-07)
        # [2026-07-07 RESET-PROOF] All-time P&L from the durable trade ledger —
        # cannot be zeroed by a live-DB wipe, so a reset can never again hide a
        # bot's true history (July-6: card showed $1000/0 while the ledger held
        # 8 real trades). If this row and 'Total P&L' disagree, a reset happened.
        if q.get("pnl") is not None:
            rows.append(f'<div class="row"><span>All-time Σ (ledger, {q["n"]} closed)</span>'
                        f'<b class="{cls(q["pnl"])}">{money(q["pnl"])}</b></div>')
    e = q.get("era") if q else None
    if e is not None:
        _en, _ew = e.get("n") or 0, e.get("w") or 0
        rows.append(f'<div class="row"><span>Since 3 Jul rework</span>'
                    f'<b class="{cls(e.get("pnl"))}">{_en} trades · {_ew}W/{_en - _ew}L · '
                    f'{money(e.get("pnl"))}</b></div>')
    for _t in (q.get("tags") or [])[:3]:
        rows.append(f'<div class="row"><span>&nbsp;&nbsp;↳ {html.escape(str(_t["tag"]))}</span>'
                    f'<b class="{cls(_t["pnl"])}">{_t["n"]} · {_t["w"]}W/{_t["n"] - _t["w"]}L · '
                    f'{money(_t["pnl"])}</b></div>')
    # [2026-07-07 UNIFORM CARDS] Last close with detail for EVERY bot, from
    # the union ledger (bot_trades + paper_trades).
    _lc = en.get("last_close")
    if _lc and _lc.get("ts"):
        try:
            _la, _ = age_str(dt.datetime.fromisoformat(_lc["ts"]), 10 ** 12)
        except Exception:
            _la = ""
        _lp = _lc.get("pnl")
        rows.append(f'<div class="row"><span>Last close</span>'
                    f'<b>{html.escape(str(_lc.get("pair")))} '
                    f'<span class="{cls(_lp)}">{money(_lp)}</span>'
                    f'{" · " + html.escape(str(_lc.get("reason"))) if _lc.get("reason") else ""}'
                    f'{" · " + html.escape(_la) if _la else ""}</b></div>')
    if spark:
        _svg, _dd = spark
        rows.append(f'<div class="row"><span>7d equity · DD {_dd:+.1f}%</span><b>{_svg}</b></div>')
    # live open positions passed through by the freqtrade poller
    open_pos_html = ""
    _op = extra.get("open_pos") if isinstance(extra, dict) else None
    if _op:
        _lines = "".join(
            f'<div class="row"><span>{html.escape(str(p.get("pair")))}'
            f'{" · " + html.escape(str(p.get("tag"))) if p.get("tag") else ""}'
            f'{" · " + str(p.get("h")) + "h" if p.get("h") is not None else ""}</span>'
            f'<b class="{cls(p.get("pnl"))}">'
            f'{p.get("pnl"):+.2f}%</b></div>'
            for p in _op[:6] if isinstance(p, dict) and p.get("pnl") is not None)
        if _lines:
            open_pos_html = f'<div class="sub">open positions</div>{_lines}'
    # [2026-07-07 UNIFORM CARDS] Perps + funding books live in bot_state, not
    # in bot_pnl.extra — render them the same way the freqtrade bots render.
    if not open_pos_html and en.get("positions"):
        _lines = "".join(
            f'<div class="row"><span>{html.escape(str(p.get("pair")))}'
            f' · {html.escape(str(p.get("side")))}'
            f'{" · $" + format(p["qty"], ".0f") if p.get("side") and isinstance(p.get("qty"), (int, float)) and p.get("entry") is None else ""}'
            f'{" @ " + format(p["entry"], ".4g") if isinstance(p.get("entry"), (int, float)) else ""}</span>'
            f'<b class="{cls(p.get("upnl"))}">'
            f'{money(p.get("upnl")) if p.get("upnl") is not None else "—"}</b></div>'
            for p in en["positions"][:8])
        open_pos_html = (f'<div class="sub">open positions '
                         f'({len(en["positions"])})</div>{_lines}')
    return f'''<div class="card">
      <h2>{html.escape(label_for(bot))}{badge} <span class="dot {dot}"></span></h2>
      {_desc_html}
      <div class="muted">{html.escape(str(status))} · updated {html.escape(age)}{" · STALE" if stale else ""}</div>
      {f'<div class="muted" style="color:#d29922">{html.escape(mode_note)}</div>' if mode_note else ''}
      {"".join(rows)}
      {open_pos_html}
      {holdings_html}
      {orders_html}
      {f'<div class="sub">{extra_bits}</div>' if extra_bits else ''}
      {extra_html}
    </div>'''


def render():
    hidden = fetch_hidden_bots()
    try:
        rows = fetch_rows(hidden=hidden)
        db_err = None
    except Exception as e:
        rows, db_err = {}, f"{type(e).__name__}: {e}"

    try:
        open_trades = fetch_open_trades()
    except Exception:  # noqa: BLE001
        open_trades = {}
    try:
        quality = fetch_bot_quality()
    except Exception:  # noqa: BLE001
        quality = {}
    try:
        enrich = fetch_ledger_enrich()
    except Exception:  # noqa: BLE001
        enrich = {}
    # [(vg)] MAX DRAWDOWN REACHES THE CARD. It is one of the six GO-LIVE BARS
    # and the card read it off `row["max_drawdown"]` — a bot_pnl column that
    # does not exist — so the line silently never rendered and a reader could
    # not tell "this book has no drawdown" from "this number was never
    # computed". IMPORTED, never recomputed: `scripts/golive_readiness.py`
    # owns this number (the WORSE of realised and MTM, per I9) and a second
    # computation here would be a second rule ((hj)). The payload was already
    # fetched twice per render for other cards; it just never reached this
    # scope.
    try:
        for _bot, _dd in fetch_golive_dd().items():
            enrich.setdefault(_bot, {})["golive_dd"] = _dd
    except Exception:  # noqa: BLE001
        pass          # a dark grader leaves `golive_dd` ABSENT -> renders unknown
    sparks = build_sparks()
    pulse_strip, pulse_latest = fetch_pulse_strip()
    # [2026-07-30] 🚦 the go-live grader sits directly after the radar: the
    # radar says "is there an edge?", the grader says "has it earned real
    # money?" — the same books, the next question.
    # [2026-08-26] 🏭 the production pipe closes the sequence: the radar asks
    # "is there an edge?", the grader "has it earned real money?", and the pipe
    # "then why has nothing arrived?" — joining the grader, the judge, the
    # allocation organ and the incubator into one answer sorted by who can act.
    brain_html = brain_card_html() + evidence_board_card() + autonomy_rail_card() + parliament_card() + incubator_card() + radar_card() + golive_card() + pipeline_card()

    # V5's regime-driven mode, so its card explains its own quietness/activity
    mode_notes = {}
    _reg = (pulse_latest or {}).get("btc_regime") or {}
    if _reg:
        # [2026-07-13] risk-off text updated: bear_bounce retired 07-12,
        # range_meanrev retired 07-13 — bounce_pullback is the only risk-off leg.
        mode_notes["crypto-intraday-15m"] = (
            "mode: range_on pullbacks + breakouts (BTC 4h RISK-ON)" if _reg.get("risk_on")
            else "mode: bounce_pullback only — confirmed relief rallies (BTC 4h RISK-OFF)")

    # union of expected + whatever actually published. Hidden bots are already
    # out of `rows` (fetch_rows), but EXPECTED would resurrect a placeholder
    # card for them — filter here too so hide really means gone.
    # [2026-07-28 AUDIT FIX] ...and filter RETIRED_ROWS too: EXPECTED still
    # listed perps-funding-carry + event-listing-sniper (both retired
    # 17-Jul), so every render produced two permanent 'no data yet' ghost
    # cards — the Launch Sniper's with red go-live gate chips — for bots the
    # fleet retired. A retirement must not leave a placeholder haunting the
    # staged sections.
    names = [b for b in list(EXPECTED) + [b for b in rows if b not in EXPECTED]
             if b not in hidden and b not in RETIRED_ROWS]
    # [2026-07-10] Real-money Lighter bots get their OWN section at the top of the
    # page, not interspersed with the paper fleet. is_live_bot = <bot>-lighter rows.
    # [2026-07-15 LIFECYCLE SECTIONS] Everything else is grouped by promotion
    # stage, with the go-live gates COMPUTED per bot (see fetch_gate_metrics).
    try:
        gates = fetch_gate_metrics()
    except Exception:  # noqa: BLE001
        gates = {}

    def _mk(b, extra=""):
        return card(b, rows.get(b), open_trades, quality.get(b), sparks.get(b),
                    mode_notes.get(b), enrich.get(b), extra_html=extra)

    live_cards = [_mk(b) for b in names if is_live_bot(b)]
    staged = {"ready": [], "proving": [], "experiment": [], "control": [],
              "scanner": []}
    stage_pnl = {k: 0.0 for k in staged}
    for b in names:
        if is_live_bot(b):
            continue
        stg = classify_stage(b, gates)
        extra = ""
        # [2026-07-16] "experiment" now shows its go-live gates too. It was
        # excluded, so the EXPERIMENT_BASES books (Ticket Taker, Snap Back,
        # Perp Sniper, Launch Sniper) rendered NO progress-to-live — including
        # Snap Back, which is the standing next go-live candidate. Stage
        # classification is unchanged (they stay in the experiment section and
        # can never auto-promote to "ready" on gates alone); this only makes
        # their distance from the bar visible. "control"/"scanner" stay off by
        # design — a reference book isn't on the promotion track.
        if stg in ("ready", "proving", "experiment"):
            _ok, chips = _gate_eval(gates.get(b) or {})
            extra = f'<div class="gates">{chips}</div>'
        staged[stg].append(_mk(b, extra))
        stage_pnl[stg] += ((rows.get(b) or {}).get("pnl_abs") or 0)
    # [2026-07-15 AUDIT FIX] brain card joins the scanners SECTION BODY, not
    # the staged list, so the header's bot count stays honest.
    stage_organ = {"scanner": brain_html or ""}

    # [2026-07-05] Ambient health checks — the silent-failure classes we have
    # actually hit (persistence resets, over-trading) surfaced on every load.
    checks = []
    for b, r in rows.items():
        # [2026-07-16 FIX] STOCKS holds BASE names but rows are venue-suffixed
        # (equities-regime-lshadow), so this skip never matched. Latent while
        # `quality` was empty for those rows — unifying the ledgers arms it.
        if b in SCANNERS or venue_variant(b)[0] in STOCKS:
            continue
        q = quality.get(b) or {}
        eq = r.get("equity")
        if (isinstance(eq, (int, float)) and abs(eq - 1000.0) < 1e-9
                and (q.get("n") or 0) > 0 and (r.get("closed_trades") or 0) == 0):
            checks.append(f"{label_for(b)}: equity exactly $1000 with ledger history — possible persistence reset")
        _ot = OVERTRADE_LIMIT.get(venue_variant(b)[0], OVERTRADE_DEFAULT)
        if (q.get("n24") or 0) > _ot:
            checks.append(f"{label_for(b)}: {q['n24']} closed trades in 24h "
                          f"(>{_ot}) — over-trading vs design")
    _era5 = (quality.get("crypto-intraday-15m") or {}).get("era") or {}
    if (_era5.get("pnl") or 0) < -5:
        checks.append(f"V5 probation breach: since-rework P&L {money(_era5.get('pnl'))}")
    health_html = ('<div class="banner">HEALTH: ' + " · ".join(html.escape(c) for c in checks) + "</div>"
                   if checks else
                   '<div class="okline">Health ✓ persistence intact · no over-trading · probation within bounds</div>')

    # [2026-07-15 OPERATING HUB] fleet cockpit strip — risk light, budget
    # usage, drawdown governor, venue stress, alert pressure. One glance =
    # "should the fleet be trading right now".
    try:
        ops_html = ops_strip_html()
    except Exception:  # noqa: BLE001
        ops_html = ""
    health_html = ops_html + health_html

    # [2026-07-11 EVIDENCE ALERTS] recent alerts from market_context's evidence
    # evaluator (dislocation census hits, factor-sample milestones, coin-veto
    # changes, live-vs-shadow divergence). Signal layer only — the sole
    # automated ACTION in the fleet is the restrict-only coin-veto list.
    # [2026-07-15 EVIDENCE REFRESH] The feed is append-only, so the banner used
    # to replay superseded items for 48h. Now: latest-per-key only, each item
    # age-stamped, items the daily autonomous review marked RESOLVED are
    # dropped, and the review's own stamp is shown so staleness is visible.
    _fa = fetch_fleet_alerts()
    if _fa:
        _byk = {}
        for a in _fa:                        # chronological — last wins per key
            _byk[a.get("key") or a.get("msg")] = a
        _sts = fetch_states(["evidence-review", "evidence-board"])
        _rev = _sts.get("evidence-review") or {}
        # resolved = condition no longer true; stale = recorded evidence whose
        # decision gate lives elsewhere (weekly census/settlement reviews).
        # Both clear from the banner; 'active' verdicts (and unreviewed items)
        # stay. History is never deleted — fleet-alerts stays append-only.
        # [2026-07-15 EVIDENCE BOARD v2] the organ's mechanical auto-verdicts
        # also suppress; MANUAL evidence-review verdicts stay senior (a human
        # 'active' overrides an organ 'stale', and vice versa).
        _auto = {i.get("key"): i.get("verdict")
                 for i in ((_sts.get("evidence-board") or {}).get("items") or [])}
        _manual = {v.get("key"): v.get("status")
                   for v in (_rev.get("verdicts") or []) if v.get("key")}
        _resolved = {k for k, s in {**_auto, **_manual}.items()
                     if s in ("resolved", "stale")}
        _now = time.time()

        def _age_txt(a):
            m = int(max(0, _now - (a.get("ts") or _now)) // 60)
            return f"{m}m" if m < 120 else f"{m // 60}h"
        _items = [a for a in sorted(_byk.values(), key=lambda a: -(a.get("ts") or 0))
                  if (a.get("key") or a.get("msg")) not in _resolved][:6]
        _rev_note = ""
        if _rev.get("reviewed_at"):
            _rt = _iso_dt(_rev.get("reviewed_at"))
            _rage = (f"{int((_now - _rt.timestamp()) // 3600)}h ago"
                     if _rt else str(_rev.get("reviewed_at"))[:16])
            _n_res = len(_resolved)
            _rev_note = (f' <span class="muted">· 🧾 reviewed {_rage}'
                         + (f" · {_n_res} resolved" if _n_res else "") + "</span>")
        elif _items:
            _rev_note = ' <span class="muted">· no autonomous review yet</span>'
        if _items:
            health_html += ('<div class="banner">🔔 EVIDENCE: '
                            + " · ".join(f'{html.escape(a.get("msg") or "")} '
                                         f'<span class="muted">({_age_txt(a)})</span>'
                                         for a in _items)
                            + _rev_note + "</div>")

    live = [r for r in rows.values() if r]
    # [2026-07-09 LIGHTER GO-LIVE] Venue-variant rows (live/testnet/shadow on
    # Lighter) are their OWN groups — never folded into the paper headline, so
    # the paper curve stays clean and the LIVE fleet gets its own P&L line.
    def _variant_kind(r):
        return venue_variant(r.get("bot") or "")[1]
    live_rows = [r for r in live if is_live_bot(r.get("bot") or "")]
    shadow_rows = [r for r in live if _variant_kind(r) in ("-lshadow", "-ltest")]
    _crypto = [r for r in live if r.get("bot") not in STOCKS and not _variant_kind(r)]
    # Crypto trading-bot P&L (the real headline) excludes scanners AND stocks AND
    # venue variants; each of those is shown as its own subtotal so it can't
    # distort the paper total.
    tot_pnl = sum((r.get("pnl_abs") or 0) for r in _crypto
                  if r.get("bot") not in SCANNERS)
    scan_pnl = sum((r.get("pnl_abs") or 0) for r in live
                   if r.get("bot") in SCANNERS)
    stock_pnl = sum((r.get("pnl_abs") or 0) for r in live if r.get("bot") in STOCKS)
    # LIVE (real money on Lighter) — the number that actually matters once funded.
    live_pnl = sum((r.get("pnl_abs") or 0) for r in live_rows)
    live_equity = sum((r.get("equity") or 0) for r in live_rows if r.get("equity") is not None)
    n_live_bots = len(live_rows)
    shadow_pnl = sum((r.get("pnl_abs") or 0) for r in shadow_rows)
    n_shadow_bots = len(shadow_rows)
    tot_equity = sum((r.get("equity") or 0) for r in _crypto if r.get("equity") is not None)
    stock_equity = sum((r.get("equity") or 0) for r in live
                       if r.get("bot") in STOCKS and r.get("equity") is not None)
    # [2026-08-04 (iy)] Trades counts the WHOLE living fleet, not the legacy
    # non-variant paper cohort — that cohort has been empty since the 14/17-Jul
    # retirements, so the most prominent line on the page read "Trades 0
    # closed · 0 open" over cards showing hundreds of closes and ~54 open
    # positions. I12 rot, in the UI.
    n_open = sum((r.get("open_trades") or 0) for r in live)
    n_closed = sum((r.get("closed_trades") or 0) for r in live)
    online = sum(1 for r in live
                 if not age_str(r.get("updated_at"), stale_secs_for(r.get("bot")))[1]
                 and r.get("status") not in ("halted", "error"))

    # Grand total across EVERYTHING (the full picture). [2026-08-04 (iy)] Both
    # sides are now SPLIT real vs modelled: the old line summed 20 modelled $1k
    # shadow books into eq while excluding them from P&L — three cohort
    # definitions in one span, and the reader had no way to tell $20k of
    # modelled paper from $267 of real money.
    grand_equity = sum((r.get("equity") or 0) for r in live if r.get("equity") is not None)
    modelled_pnl = sum((r.get("pnl_abs") or 0) for r in live) - live_pnl

    # Whole-feed staleness. The DB can be reachable and rows can exist, yet every
    # row is old because the bots lost their write path (the exact failure mode on
    # 2026-06-22: bots alive, hardcoded DATABASE_URL went stale, no fresh writes).
    # A frozen feed must NOT look like "all bots flat", so flag it loudly here and
    # in /pnl.json.
    def _age_secs(r):
        ua = r.get("updated_at")
        if ua is None:
            return None
        if ua.tzinfo is None:
            ua = ua.replace(tzinfo=dt.timezone.utc)
        return (dt.datetime.now(dt.timezone.utc) - ua).total_seconds()

    _ages = [s for s in (_age_secs(r) for r in live) if s is not None]
    freshest = min(_ages) if _ages else None
    n_stale_live = sum(1 for r in live
                       if age_str(r.get("updated_at"), stale_secs_for(r.get("bot")))[1])
    feed_stale = bool(live) and freshest is not None and n_stale_live == len(live)

    banner = ""
    if db_err:
        banner = (f'<div class="banner">Database unreachable: {html.escape(db_err)}. '
                  f'Check DATABASE_URL on this service.</div>')
    elif not live:
        banner = ('<div class="banner">Connected to Postgres, but no bot has published yet. '
                  'Make sure each bot has DATABASE_URL set and has run at least one loop.</div>')
    elif feed_stale:
        _m = int(freshest // 60)
        _age = f"{_m} min" if _m < 120 else f"{_m // 60}h {_m % 60}m"
        banner = (f'<div class="banner crit">FEED STALE — no bot has published in {_age}. '
                  f'Showing last-known values, not live P&amp;L. The bots may be running '
                  f'but unable to write to Postgres — check the DATABASE_URL reference on '
                  f'each bot service and redeploy.</div>')

    # [2026-07-09 LIGHTER GO-LIVE] The LIVE fleet gets its own prominent P&L line
    # (real money on Lighter, separate from every paper number). Shadow/testnet
    # get a muted line so the compressed gate ladder is visible at a glance.
    live_total_line = ""
    if n_live_bots:
        live_total_line += (
            f'<span style="border:1px solid #1a7f37;border-radius:6px;padding:2px 9px;'
            f'background:#1a7f3718;font-weight:600">🟢 LIVE · Lighter '
            f'<b>{money(live_equity)}</b> eq · '
            f'<b class="{cls(live_pnl)}">{money(live_pnl)}</b> P&amp;L · '
            f'{n_live_bots} bot{"s" if n_live_bots != 1 else ""}</span>')
    if n_shadow_bots:
        live_total_line += (
            f'<span class="muted" style="border:1px solid #30363d;border-radius:6px;'
            f'padding:2px 9px">shadow/testnet <b class="{cls(shadow_pnl)}">'
            f'{money(shadow_pnl)}</b> · {n_shadow_bots} bot'
            f'{"s" if n_shadow_bots != 1 else ""} (modelled)</span>')

    # [2026-08-04 (iy)] The legacy paper-cohort spans render ONLY when their
    # cohort has members. All three (non-variant crypto paper, scanners,
    # stocks) have been empty since the 14/17-Jul retirements, so the header
    # permanently asserted "Crypto (paper) +0.00 · Scanner paper +0.00 ·
    # Stocks (paper) +0.00" — a fleet that no longer exists, rendered above 22
    # trading books. A span that can only ever read zero is the UI form of the
    # warning-shaped guard.
    paper_spans = ""
    if _crypto:
        paper_spans += (f'<span>Crypto (paper) <b class="{cls(tot_pnl)}">'
                        f'{money(tot_pnl)}</b> · eq {money(tot_equity)}</span>')
    if any(r.get("bot") in SCANNERS for r in live):
        paper_spans += (f'<span>Scanner paper <b class="{cls(scan_pnl)}">'
                        f'{money(scan_pnl)}</b></span>')
    if any(r.get("bot") in STOCKS for r in live):
        paper_spans += (f'<span>Stocks (paper) <b class="{cls(stock_pnl)}">'
                        f'{money(stock_pnl)}</b> · eq {money(stock_equity)}</span>')

    # [2026-07-13 INTERACTIVE MANAGE] Hide/unhide/delete panel. Hide = persisted
    # in bot_state (reversible, survives redeploys, respected by the grid, the
    # totals and /pnl.json). Delete = drop the bot_pnl row only (ledger history
    # stays; an active bot's row reappears on its next publish, so delete can
    # only permanently remove bots that no longer run).
    try:
        _all_ids = fetch_all_bot_ids()
    except Exception:  # noqa: BLE001
        _all_ids = []

    def _mrow(b, kind):
        lbl = html.escape(label_for(b))
        bid = html.escape(b, quote=True)
        btns = ""
        if kind == "visible":
            btns += (f'<button class="mbtn" onclick="botAdmin(\'hide\',\'{bid}\')">'
                     f'hide</button>')
        elif kind == "hidden":
            btns += (f'<button class="mbtn" onclick="botAdmin(\'unhide\',\'{bid}\')">'
                     f'unhide</button>')
        btns += (f'<button class="mbtn del" onclick="botAdmin(\'delete\',\'{bid}\')">'
                 f'delete row</button>')
        note = {"visible": "", "hidden": " · hidden by you",
                "retired": " · retired in code"}[kind]
        return (f'<div class="mrow"><span class="mname">{lbl}'
                f'<span class="muted"> — {bid}{note}</span></span>{btns}</div>')

    _visible_ids = sorted(set(list(rows.keys()) + [b for b in names if b in CURRENT_BOTS]))
    _hidden_ids = sorted(hidden.keys())
    _retired_ids = sorted(b for b in _all_ids
                          if b in RETIRED_ROWS and b not in hidden)
    manage_html = (
        '<details class="manage"><summary>🗂 Manage bots — hide or delete retired/bunk rows</summary>'
        '<div class="mnote">Hide removes a bot from the grid, totals and feeds (reversible, '
        'survives redeploys). Delete drops the dashboard row only — trade history stays in the '
        'ledgers, and an <b>active</b> bot\'s row reappears on its next publish, so delete is '
        'only permanent for bots that no longer run.</div>'
        + '<div class="mgroup">Visible</div>'
        + ("".join(_mrow(b, "visible") for b in _visible_ids) or '<div class="muted">none</div>')
        + '<div class="mgroup">Hidden by you</div>'
        + ("".join(_mrow(b, "hidden") for b in _hidden_ids) or '<div class="muted mrow">none</div>')
        + ('<div class="mgroup">Retired in code (already hidden — rows still in the table)</div>'
           + "".join(_mrow(b, "retired") for b in _retired_ids) if _retired_ids else "")
        + '</details>'
        + '''<script>
async function botAdmin(action, bot){
  if (action === 'delete' &&
      !confirm('Delete the dashboard row for "' + bot + '"?\\n\\nLedger history stays. ' +
               'If the bot still runs, the row reappears on its next publish.')) return;
  try {
    const r = await fetch('/admin/bot', {method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-Requested-With': 'fetch'},
      body: JSON.stringify({action: action, bot: bot})});
    const j = await r.json();
    if (!j.ok) { alert('failed: ' + (j.error || r.status)); return; }
  } catch (e) { alert('failed: ' + e); return; }
  location.reload();
}
</script>''')

    # [2026-07-15 LIFECYCLE SECTIONS] Render the staged groups. READY renders
    # even when empty — the bar itself is information (what promotion takes).
    _stage_meta = [
        ("ready", "🟢 Ready for live",
         "passes every house gate (≥{n} trades/30d · WR &gt;{wr}% · dd &lt;{dd}% · "
         "{age}d record) — going live still needs your sign-off + GO_LIVE_CHECKLIST".format(
             n=GATE_MIN_TRADES_30D, wr=int(GATE_MIN_WR * 100),
             dd=int(-GATE_MAX_DD * 100), age=GATE_MIN_AGE_DAYS)),
        ("proving", "🔵 Proving",
         "shadow/paper books building the 30-day record the gates demand"),
        ("experiment", "🧪 Experiments",
         "evidence collectors — unvalidated by design (census/lens/listing theses); "
         "they graduate through the validation doctrine, not through P&amp;L"),
        ("control", "⚖️ Controls &amp; references",
         "kept for comparison (delta-neutral / venue A/B baselines), not on the "
         "promotion track"),
        ("scanner", "🛰 Scanners &amp; fleet organs",
         "market intelligence and the learning loop — optimistic-fill paper is "
         "never folded into trading P&amp;L"),
    ]
    sections_html = ""
    for key, title, note in _stage_meta:
        cards_k = staged[key]
        organ = stage_organ.get(key, "")
        if not cards_k and not organ and key != "ready":
            continue
        pnl_k = stage_pnl[key]
        subtotal = (f' · <b class="{cls(pnl_k)}">{money(pnl_k)}</b> P&amp;L'
                    if cards_k else "")
        if cards_k or organ:
            body = f'<div class="grid">{"".join(cards_k)}{organ}</div>'
        else:
            body = ('<div class="stageempty">none yet — the gates above are the '
                    'bar. Proving bots that clear every gate appear here '
                    'automatically.</div>')
        sections_html += (f'<div class="stagehdr">{title} '
                          f'<span class="stagecount">{len(cards_k)} bot'
                          f'{"s" if len(cards_k) != 1 else ""}{subtotal}</span>'
                          f'<div class="stagenote">{note}</div></div>{body}')

    # [2026-07-10] Dedicated "Lighter Live" section — real-money bots grouped at
    # the top in their own bordered block so live money is never lost in the grid.
    live_section = ""
    if live_cards:
        live_section = (
            f'<section class="livewrap">'
            f'<div class="livehdr">⚡ Lighter Live <span class="livetag">REAL MONEY</span>'
            f'<span class="livesum">{money(live_equity)} eq · '
            f'<b class="{cls(live_pnl)}">{money(live_pnl)}</b> P&amp;L · '
            f'{n_live_bots} bot{"s" if n_live_bots != 1 else ""}</span></div>'
            f'<div class="grid">{"".join(live_cards)}</div></section>')

    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<noscript><meta http-equiv="refresh" content="30"></noscript>
<title>All Bots — Live P&amp;L</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Permanent+Marker&amp;display=swap" rel="stylesheet">
<style>
 @keyframes gradientshift{{0%{{background-position:0% 50%}}50%{{background-position:100% 50%}}100%{{background-position:0% 50%}}}}
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;color:#16232c;
   background-color:#eef7fd;
   background-image:repeating-linear-gradient(180deg,#ffffff 0 70px,#aed8f6 70px 140px);
   background-attachment:fixed}}
 /* the "$ EJMC $" graffiti piece — fixed behind the cards (z-index:-1 so the
    striped body shows behind it and the cards sit on top). */
 .wm{{position:fixed;inset:0;z-index:-1;display:flex;align-items:center;
   justify-content:center;pointer-events:none;overflow:hidden}}
 .wm svg{{width:min(97vw,2000px);height:auto}}
 header{{padding:16px 18px;background:#ffffffd9;backdrop-filter:blur(2px);
   border-bottom:3px solid #caa227;position:relative}}
 header::after{{content:"";position:absolute;left:0;right:0;bottom:-6px;height:2px;
   background:linear-gradient(90deg,#f4d879,#caa227,#8a6d1a,#caa227,#f4d879);
   background-size:300% 100%;animation:gradientshift 6s ease infinite}}
 h1{{margin:0 0 6px;font-size:19px;font-weight:800;letter-spacing:.2px;
   background:linear-gradient(90deg,#8a6d1a,#caa227 35%,#2f7fd6 65%,#8a6d1a);
   background-size:300% 100%;-webkit-background-clip:text;background-clip:text;
   color:transparent;animation:gradientshift 8s ease infinite;display:inline-block}}
 h1 a{{-webkit-text-fill-color:#1462c9;color:#1462c9}}
 .totals{{display:flex;gap:18px;flex-wrap:wrap;font-size:14px;color:#16232c}}
 .totals b{{font-size:16px}}
 .banner{{margin:12px 14px 0;padding:10px 12px;background:#fff6dd;border:1px solid #caa227;border-radius:8px;color:#7a5b12;font-size:13px}}
 .banner.crit{{background:#ffe3e3;border-color:#d1242f;color:#a3121b;font-weight:600}}
 .okline{{margin:12px 14px 0;padding:8px 12px;background:#e6f7ec;border:1px solid #caa227;border-radius:8px;color:#1a7f37;font-size:12px}}
 .ops{{margin:12px 14px 0;padding:8px 12px;background:#ffffffd9;border:1px solid #caa227;
   border-radius:8px;font-size:12.5px;display:flex;gap:14px;flex-wrap:wrap;align-items:center}}
 .ops .chip{{white-space:nowrap;color:#16232c}}
 .stagehdr{{margin:18px 14px 0;padding:9px 13px;background:#ffffffd9;border:1px solid #caa227;
   border-radius:10px;font-size:15px;font-weight:700;color:#16232c}}
 .stagecount{{font-weight:500;font-size:12.5px;color:#5b7184;margin-left:6px}}
 .stagenote{{font-weight:400;font-size:11.5px;color:#5b7184;margin-top:3px;line-height:1.4}}
 .stageempty{{margin:8px 14px;padding:12px;border:1px dashed #caa227;border-radius:10px;
   color:#5b7184;font-size:12.5px;background:#ffffff90}}
 .gates{{margin-top:8px;padding-top:7px;border-top:1px dashed #d4af3766;font-size:11px;
   color:#5b7184;line-height:1.6}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px;padding:14px}}
 /* [2026-07-10] Lighter Live section — real money, visually set apart.
    [2026-07-13] Red -> GREEN on user request (red read as "alarm", not "live"). */
 .livewrap{{margin:14px 14px 4px;border:2px solid #1a7f37;border-radius:12px;
   box-shadow:0 0 0 1px #caa227 inset,0 0 22px -6px #1a7f3766;
   background:linear-gradient(180deg,#e6f7eccc,#f3fbf6cc);overflow:hidden}}
 .livewrap .grid{{padding:12px}}
 .livehdr{{display:flex;align-items:center;gap:12px;flex-wrap:wrap;
   padding:11px 14px;background:#1a7f3714;border-bottom:1px solid #1a7f3733;
   font-size:15px;font-weight:700;color:#116329}}
 .livetag{{font-size:10px;font-weight:800;letter-spacing:.5px;color:#fff;
   background:#1a7f37;border-radius:6px;padding:2px 7px;box-shadow:0 0 10px #1a7f3766}}
 .livesum{{margin-left:auto;font-size:13px;font-weight:500;color:#16232c}}
 .card{{background:#ffffffcc;border:2.5px solid #d4af37;border-radius:10px;padding:14px;
   box-shadow:0 0 0 1px #b8860b55,0 1px 0 #ffffffaa inset;
   transition:border-color .2s,box-shadow .2s}}
 .card:hover{{border-color:#b8860b;box-shadow:0 0 0 1px #b8860b,0 0 16px -6px #d4af37cc}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .desc{{font-size:11px;color:#5b7184;margin:0 0 6px;line-height:1.35;
   border-left:2px solid #d4af3766;padding-left:7px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:10px 0 4px;font-size:12px;color:#5b7184}}
 .muted{{color:#5b7184;font-size:12px}}
 .pos{{color:#1a7f37}} .neg{{color:#d1242f}}
 .dot{{display:inline-block;width:8px;height:8px;border-radius:50%;margin-left:4px}}
 .dot.on{{background:#1a7f37;box-shadow:0 0 6px #1a7f37}} .dot.off{{background:#d1242f;box-shadow:0 0 6px #d1242f}} .dot.warn{{background:#b8860b;box-shadow:0 0 6px #b8860b}}
 footer{{padding:10px 18px;color:#5b7184;font-size:11px}}
 /* [2026-07-18] live-station heartbeat */
 .hbwrap{{display:inline-flex;align-items:center;gap:5px;font-weight:600}}
 .hb{{width:9px;height:9px;border-radius:50%;background:#8b949e;display:inline-block;
   box-shadow:0 0 0 0 rgba(46,160,67,.5);animation:hbpulse 2s infinite}}
 @keyframes hbpulse{{0%{{box-shadow:0 0 0 0 rgba(46,160,67,.45)}}
   70%{{box-shadow:0 0 0 6px rgba(46,160,67,0)}}100%{{box-shadow:0 0 0 0 rgba(46,160,67,0)}}}}
 /* [2026-07-13] Manage bots panel */
 .manage{{margin:6px 14px 0;border:1px solid #caa227;border-radius:10px;
   background:#ffffffd9;font-size:13px}}
 .manage summary{{cursor:pointer;padding:9px 13px;font-weight:600;color:#5b4a12}}
 .manage[open] summary{{border-bottom:1px solid #eadfae}}
 .mnote{{padding:8px 13px 2px;color:#5b7184;font-size:12px}}
 .mgroup{{padding:10px 13px 3px;font-weight:700;color:#2f5a7a;font-size:12px;
   text-transform:uppercase;letter-spacing:.4px}}
 .mrow{{display:flex;align-items:center;gap:8px;padding:4px 13px}}
 .mname{{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
 .mbtn{{border:1px solid #b8860b;background:#fff;border-radius:6px;padding:2px 10px;
   font-size:12px;cursor:pointer;color:#5b4a12}}
 .mbtn:hover{{background:#fff6dd}}
 .mbtn.del{{border-color:#d1242f;color:#a3121b}}
 .mbtn.del:hover{{background:#ffe3e3}}
</style></head><body>
{WATERMARK_HTML}
<div id="station">
<header>
 <h1>All Bots — live P&amp;L &nbsp;·&nbsp; <a href="/history" style="color:#58a6ff;font-size:14px">history →</a> &nbsp;·&nbsp; <a href="/periods" style="color:#58a6ff;font-size:14px">P&amp;L by day/week/month →</a> &nbsp;·&nbsp; <a href="/market" style="color:#58a6ff;font-size:14px">market regime →</a> &nbsp;·&nbsp; <a href="/learning" style="color:#58a6ff;font-size:14px">learning →</a> &nbsp;·&nbsp; <a href="/vitals" style="color:#58a6ff;font-size:14px">health →</a></h1>
 <div class="totals">
   <span>Bots live <b>{online}</b></span>
   <span style="border-right:1px solid #30363d;padding-right:18px">TOTAL eq real <b>{money(live_equity)}</b> · modelled {money(grand_equity - live_equity)} &nbsp;—&nbsp; P&amp;L real <b class="{cls(live_pnl)}">{money(live_pnl)}</b> · modelled <span class="{cls(modelled_pnl)}">{money(modelled_pnl)}</span></span>
   {live_total_line}
   {paper_spans}
   <span>Trades <b>{n_closed} closed · {n_open} open</b></span>
   {pulse_strip}
 </div>
</header>
{banner}
{health_html}
{live_section}
{sections_html}
</div>
{manage_html}
<footer><span class="hbwrap"><span id="hb" class="hb" title="live"></span> <span class="hbtxt">live</span> · <span id="hbage">updated 0s ago</span></span> · Reads the shared bot_pnl Postgres table. Live-updating (in-place, no reload). Times UTC.
Snapshots older than {STALE_SECONDS}s are flagged stale.</footer>
{live_js("station")}
</body></html>'''


# ---------------------------------------------------------------------------
# [2026-07-15 OPERATING HUB] Cross-tab intelligence. Every tab renders the
# WHOLE running fleet from state the organs already publish (bot_state /
# paper_trades / bot_trades) — no new collectors, just surfacing what the
# fleet already knows. Guarded: a missing/stale organ renders as an honest
# "unavailable" line, never an exception.


# ---------------------------------------------------------------------------
# [2026-07-15 VITALS] /vitals — the fleet's HEALTH TAB (user: "upgrade and
# advance the health tab and integrate with evidence and brain and scanner").
# Three layers no other surface shows together:
#   ORGAN VITALS — every intelligence organ's freshness vs its OWN ttl (the
#     5-7 Jul scar: the brain died silently for two days because nothing
#     watched the organs' pulse; the watchdog now reads this and pushes
#     ORGAN DARK to the phone).
#   CONSUMPTION MATRIX — the 15-Jul consumption audit as a PERMANENT live
#     surface: who publishes, who consumes, what mode, is the contract fresh.
#   FLOW VITALS — is data actually moving: ledger writes, skips, history
#     rows, alert pressure over the last 24h.
# /vitals.json is read-only no-auth (same contract as /watchdog.json).
# ---------------------------------------------------------------------------

def organ_status(age_s, ttl_s):
    """FRESH within ttl, LATE to 3x ttl, DARK beyond. ttl None = event-driven
    feed (never DARK — silence is an answer, not a failure)."""
    if ttl_s is None:
        return "EVENT"
    if age_s is None:
        return "DARK"
    if age_s <= ttl_s:
        return "FRESH"
    if age_s <= 3 * ttl_s:
        return "LATE"
    return "DARK"


def _v(fmt, *vals):
    # [2026-07-16 AUDIT FIX] None formats successfully ("$None", "phase None"
    # leaked to the operator on /vitals + the Autonomy card) — render a dash
    # per missing VALUE; only a genuinely broken format degrades the line.
    try:
        return fmt.format(*("—" if v is None else v for v in vals))
    except Exception:  # noqa: BLE001
        return "—"


def lever_lane_summary(levers, max_lanes=4):
    """Compact per-LANE breakdown of the active levers, e.g.
    "books carry×2, disloc×1 · live×1". Pure — selftested.

    [2026-07-30] The autonomy card and the vitals row both showed only a COUNT.
    That was adequate while the rail moved scout/taker bars, but `(fz)` added
    nine `lighter-books` levers across SIX different books, so a bare integer
    now hides the one thing the operator needs: WHICH book the rail just moved.
    Lane names are shortened to the book prefix (`carry`, `fundspread`,
    `disloc`, `index`, `trend`, `sniper`) because that is the identity that
    matters — the lane alone would say "lighter-books" six different ways.
    """
    if not isinstance(levers, dict) or not levers:
        return ""
    books, other = {}, {}
    for name, spec in levers.items():
        lane = (spec or {}).get("lane") if isinstance(spec, dict) else None
        if lane == "lighter-books":
            books[str(name).split(".")[0]] = books.get(
                str(name).split(".")[0], 0) + 1
        else:
            key = str(lane or "?").replace("lighter-", "")
            other[key] = other.get(key, 0) + 1
    parts = []
    if books:
        top = sorted(books.items(), key=lambda kv: (-kv[1], kv[0]))[:max_lanes]
        parts.append("books " + ", ".join(f"{k}×{v}" for k, v in top))
    for k, v in sorted(other.items(), key=lambda kv: (-kv[1], kv[0]))[:max_lanes]:
        parts.append(f"{k}×{v}")
    return " · ".join(parts)


def _lever_unexpired(x):
    """[2026-07-16 AUDIT FIX] the dashboard counted EXPIRED levers as active
    (the payload lingers until the next author write) — including LIVE-flagged
    ones, for hours after they reverted. Entries without `expires` (legacy)
    count as active."""
    try:
        if not isinstance(x, dict):
            return False
        e = x.get("expires")
        if not e:
            return True
        d = _iso_dt(e)
        return d is None or d.timestamp() > time.time()
    except Exception:  # noqa: BLE001
        return True


def _organ_vital(key, st):
    """One-line vital sign per organ — the number you'd ask for first."""
    try:
        if key == "fleet-risk":
            # [2026-07-21 AUDIT FIX] the 'L' slot renders long_positions —
            # `gross` includes shorts, so this read "23L/20" while longs
            # were 22 (a short inflating a LONG budget readout). gross stays
            # as the fallback for payloads predating long_positions.
            return _v("light {} · {}L/{} · clip {}x · 7d dd {:+.2f}%",
                      st.get("light"),
                      st.get("long_positions", st.get("gross")),
                      st.get("long_budget"),
                      st.get("clip_scale"), 100 * (st.get("fleet_dd_7d") or 0))
        if key == "lighter-market":
            s = st.get("stress") or {}
            tk = st.get("tickets") or {}
            return _v("{} books ({} liquid) · stress med {}bps · tickets {}",
                      st.get("n_books"), st.get("n_liquid"), s.get("med"),
                      sum(len(v) for v in tk.values() if isinstance(v, list)))
        if key == "coin-vetoes":
            # 0 vetoes is a LEGITIMATE healthy reading (nothing is failing
            # quality), so the count alone can't distinguish "clean" from
            # "publisher dead" — which is precisely why this organ is
            # `critical`: the DARK/LATE badge beside it carries that half.
            _cv = st.get("coins")
            return _v("{} coin(s) vetoed{}",
                      None if _cv is None else len(_cv),
                      f" · {', '.join(sorted(_cv)[:3])}" if _cv else "")
        if key == "market-pulse":
            # [2026-07-17 AUDIT] mood/panic live under `latest` (market_pulse.py
            # :408) — reading them TOP-LEVEL got None for both, and `or 0` then
            # rendered a confident "mood +0.00 · calm" through a genuine PANIC
            # (measured: publisher mood -0.62 / panic True -> "mood +0.00 ·
            # calm"). Not a blank: a WRONG answer indistinguishable from a
            # healthy neutral market, on the one organ whose panic flag the
            # strategies actually consume. `mood or 0` is dropped with it — a
            # missing mood must read "—", not a serene zero. fetch_pulse_strip
            # (:864) and fleet_risk (:603) already read `latest`; this was the
            # lone outlier.
            # `calm` is TRI-STATE for the same reason: absent panic data is
            # UNKNOWN, not calm. A binary flag read off a payload that may not
            # be there answers "is the market ok?" with "yes" when the honest
            # answer is "I can't see" — the convergent-metric trap this fleet
            # already ate once (a `watching:201` that matched under total
            # failure). Freshness is shown beside this, but the words must
            # stand alone: nobody reads DARK and un-reads "calm".
            latest = st.get("latest") or {}
            mood, panic = latest.get("mood"), latest.get("panic")
            return _v("mood {} · {}",
                      None if mood is None else f"{float(mood):+.2f}",
                      None if panic is None else ("PANIC" if panic else "calm"))
        if key == "learning-brain":
            return _v("run {} · {} hypotheses", st.get("runs"),
                      len(st.get("hypotheses") or {}))
        if key == "brain-stake-mults":
            return _v("{} active mults · {}", len(st.get("mults") or {}), st.get("mode"))
        if key == "brain-lens-forward":
            ls = st.get("lenses") or {}
            return " · ".join(f"{k} n4h={int((v or {}).get('n4h') or 0)}"
                              for k, v in sorted(ls.items())) or "—"
        if key == "brain-diagnosis":
            return _v("{} diagnoses", len(st.get("diagnoses") or {}))
        if key == "brain-vitals":
            c = st.get("counts") or {}
            return _v("{} · {} mults · watch {} · {} regime splits",
                      st.get("engine"), c.get("mults_published"),
                      c.get("watchlist"), len(st.get("regime_splits") or {}))
        if key == "event-sentinel":
            c = st.get("counts") or {}
            fresh = [e for e in (st.get("active_events") or []) if e.get("fresh")]
            top = (f" · top: {fresh[0]['type']} sev={fresh[0]['severity']}"
                   if fresh else "")
            return _v("{} events · bias {} · {} heads{}",
                      len(fresh), st.get("market_bias"),
                      c.get("headlines"), top)
        if key == "evidence-board":
            return _v("{} items · {} proposals · mode {}",
                      len(st.get("items") or []), len(st.get("proposals") or []),
                      st.get("mode"))
        if key == "signal-bus":
            # [2026-07-17 AUDIT] both are DICTS, not scalars (fleet_risk.py
            # :593-601): prem is {sym: bps}, stress is {med,max,n}. Formatted
            # as scalars they rendered the raw repr —
            #   "prem {'HYPE': 42.1, 'FARTCOIN': -31.0}bps · stress
            #    {'med': 3.2, 'max': 88.0, 'n': 214}bps"
            # Show what the gauge is FOR: how stressed the venue is, and the
            # single book furthest from fair value. (fleet_risk:587 claims a
            # "signal-bus card" formats these — no such card exists; this line
            # is the only formatter, so that comment is stale.)
            _pr = st.get("lighter_prem_bps")
            _sr = st.get("lighter_venue_stress_bps")
            _med = (_sr or {}).get("med") if isinstance(_sr, dict) else _sr
            _top = None
            if isinstance(_pr, dict) and _pr:
                _sym = max(_pr, key=lambda k: abs(_pr[k] or 0))
                _top = f"{_sym} {_pr[_sym]:+.0f}bps"
            return _v("stress med {}bps · widest {}", _med, _top)
        if key == "fleet-radar":
            su = st.get("summary") or {}

            def _n(*cs):
                return sum(len(su.get(c) or []) for c in cs)
            return _v("{} books · {} plausible/edge · {} artifact · {} noise · "
                      "{} losing · {} starved", st.get("n_books"),
                      _n("plausible", "real_edge"), _n("artifact"),
                      _n("noise", "weak"), _n("losing"), _n("starved"))
        if key == "regime-oracle":
            # [2026-07-17] This counted TOP-LEVEL PAYLOAD KEYS, not majors —
            # params/pairs/fleet/errors made it read "4 majors tracked" for a
            # 16-major universe, and the HL->Lighter swap's additive
            # `coverage` key would have silently moved it to 5. Read the
            # majors from `pairs`, and surface coverage: a major dropped for
            # want of Lighter history is exactly what the operator must see
            # here. Pre-swap payloads carry no `coverage` — hence the guards.
            cov = st.get("coverage") or {}
            miss = cov.get("missing") or {}
            # [2026-07-21 item 18] `pairs` now carries the non-crypto books
            # too — counting it as "majors" would blend asset classes, the
            # exact read the per-asset build exists to avoid. Majors come
            # from the coverage block (crypto contract, n_published); the
            # non-crypto coverage gets its own tail. Payloads predating
            # either addition render exactly as before (both guards).
            nc = st.get("noncrypto") or {}
            n_major = cov.get("n_published", len(st.get("pairs") or {}))
            # [2026-07-22 (bs)] self-grade tail: a COUNT only — a pooled
            # hit rate across crypto+SPY would blend classes (item 18).
            _gr = st.get("grades") or {}
            _ng = sum(1 for g in _gr.values()
                      if isinstance(g, dict) and (g.get("d1") or {}).get("n"))
            return _v("{} majors tracked{}{}{}", n_major,
                      (f" · MISSING {', '.join(sorted(miss))}" if miss else
                       (f" · coverage {cov.get('n_published')}/"
                        f"{cov.get('universe')}" if cov else "")),
                      (f" · non-crypto {nc.get('n_published')}/"
                       f"{nc.get('universe')}" if nc else ""),
                      (f" · self-grade d1 on {_ng}" if _ng else ""))
        if key == "fleet-alerts":
            al = st.get("alerts") or []
            return _v("{} alerts total · last: {}", len(al),
                      (al[-1].get("msg") or "")[:60] if al else "none")
        if key == "evidence-review":
            return _v("{} verdicts · reviewed {}", len(st.get("verdicts") or []),
                      str(st.get("reviewed_at"))[:16])
        # [2026-07-16] growth-rail organs (make the autonomy stack visible)
        if key == "fleet-tuning":
            lv = {k: x for k, x in (st.get("levers") or {}).items()
                  if _lever_unexpired(x)}
            live = sum(1 for x in lv.values()
                       if isinstance(x, dict) and x.get("lane") == "lighter-live")
            _brk = lever_lane_summary(lv)
            return _v("{} active levers · {} lighter-live{}", len(lv), live,
                      f" — {_brk}" if _brk else "")
        if key == "scout-tuner":
            return _v("{} enacted · baseline net ${}",
                      len(st.get("enacted") or {}), st.get("baseline_net"))
        if key == "fleet-proprioception":
            c = st.get("counts") if isinstance(st.get("counts"), dict) else {}
            return _v("{} episodes ({} graded) · {} helping · {} hurting",
                      c.get("episodes") or 0, c.get("graded") or 0,
                      c.get("helping") or 0, c.get("hurting") or 0)
        if key == "strategy-incubator":
            ch = st.get("champion") or {}
            return _v("champion {} · net ${} · {} prospects",
                      ch.get("confidence") or "none", ch.get("net"),
                      len(st.get("prospects") or []))
        if key == "xp-queue":
            return _v("{} candidates queued", len(st.get("candidates") or []))
        if key == "xp-judge":
            return _v("phase {} · cand {}", st.get("phase"), st.get("candidate") or "—")
        if key == "fleet-immune":
            return _v("{} sick · {} quarantined",
                      len(st.get("sick") or []), len(st.get("quarantined_levers") or {}))
        if key == "fleet-regen":
            return _v("{} repaired · {} need operator",
                      len(st.get("repaired") or []), len(st.get("needs_operator") or []))
        if key == "fleet-respiration":
            return _v("SpO2 {}% · {}",
                      int(round((st.get("spo2") or 0) * 100)), st.get("state"))
        if key == "fleet-clock":
            ny = (st.get("markets") or {}).get("nyse") or {}
            ne = st.get("next_event") or {}
            return _v("session {}{}{}{}",
                      st.get("primary"),
                      " · THIN" if st.get("thin_liquidity") else "",
                      (" · NYSE " + ("open" if ny.get("open") else "closed")) if ny else "",
                      (f' · {ne.get("market")} {ne.get("event")}'
                       f'{_mins_until(ne.get("at_utc"))}') if ne.get("at_utc") else "")
        if key == "impl-shortfall":
            return _v("{} · gap {}pp", st.get("verdict"), st.get("gap_pp"))
        if key == "gapscout-census":
            return _v("{} episodes open · quiet {}h",
                      st.get("episodes_open"), st.get("quiet_hours"))
        if key == "parliament":
            books = st.get("books") or {}
            sc = st.get("scanners") or {}
            bench = sc.get("bench") or {}
            quiet = sum(1 for b in bench.values()
                        if isinstance(b, dict) and not b.get("n"))
            stalled = (st.get("health") or {}).get("stalled") or []
            return _v("{} books · {} closed · {} signals/{} scanners{}{}",
                      len(books),
                      sum(int(b.get("closed") or 0) for b in books.values()
                          if isinstance(b, dict)),
                      sc.get("emitted"), len(bench) or "—",
                      f" · {quiet} quiet" if bench and quiet else "",
                      f" · STALLED {','.join(stalled)}" if stalled else "")
        if key == "actions-heartbeat":
            return _v("run {} · {}", st.get("run_id"), st.get("src"))
        if key == "parliament-tuning":
            act = st.get("active") or {}
            n = sum(len(v) for v in act.values() if isinstance(v, list))
            return _v("{} active levers · {} enacted lifetime",
                      n, st.get("enacted"))
    except Exception:  # noqa: BLE001
        pass
    return "—"


# (key, label, critical-for-watchdog, fallback ttl seconds when payload has none)
ORGAN_SPECS = [
    ("fleet-risk",         "💡 fleet_risk — light/budget/governor",  True,  900),
    ("lighter-market",     "🛰️ Lighter Scout — venue map + tickets", True,  900),
    # [2026-07-17 AUDIT] coin-vetoes was the fleet's one automated action with
    # NO organ row — so the watchdog (which pages only on `critical` organs in
    # this list, fleet_watchdog_svc.py:213) could not page for it. It gates the
    # LIVE Funding Farmer, it FAILS OPEN when stale (lighter_funding_bot.py:902
    # `_vetoes = {}`), and its only distress signal is a ONE-SHOT log warning
    # nobody tails. Its publisher (market_context.py) is a SEPARATE Railway
    # service that can die on its own — so market-context dying silently
    # disarmed a real-money quality filter, invisibly and unpaged. CRITICAL
    # because fail-open + real money is exactly what a pager is for. This is
    # also the market-context service's liveness beacon: `updated` is re-stamped
    # every loop (market_context.py:626) even when the veto CONTENT is
    # unchanged, so a fresh row really does attest a living publisher.
    ("coin-vetoes",        "🚫 Coin vetoes — quality filter (LIVE)", True,  3600),
    # [2026-08-05] CI-LIVENESS dead-man's switch. A GitHub billing lockout
    # kills EVERY workflow silently (28-Jul: 3-16s not-started "failures" —
    # CI, deploys AND the Actions-hosted watchdog all dead at once), so the
    # only detector that survives it is THIS service. fleet-watchdog.yml
    # writes this key on its hourly cron regardless of pushes (no false page
    # on a quiet no-push day); ttl 3900 = one beat + cron jitter, so DARK
    # (3x = 3.25h) means three missed beats. CRITICAL deliberately — I13:
    # the key joins the pageable set the day it is born, and
    # fleet_watchdog_svc.actions_heartbeat_problem adds the diagnosis line
    # (check Actions runs + Settings/Billing) beside the generic ORGAN DARK.
    ("actions-heartbeat",  "🛰️ GitHub Actions heartbeat — CI/deploy liveness", True, 3900),
    ("evidence-board",     "⚖️ Evidence board — scoring/synthesis",  True,  1800),
    ("market-pulse",       "🫀 Market Pulse — news/social mood",     True,  2700),
    ("learning-brain",     "🧠 Brain — hypotheses/diagnosis",        True,  26000),
    ("brain-stake-mults",  "✋ L4 stake multipliers",                 False, 26000),
    ("brain-lens-forward", "🎓 Lens-forward (brain grades scanners)", False, 26000),
    ("brain-diagnosis",    "🩺 Per-bucket diagnosis",                 False, 26000),
    # [2026-07-16] v3 statistics engine instrumentation (bot_learn +
    # brain_stats): priors, watchlist, regime splits, lens episodes.
    # [2026-08-01] PROMOTED TO CRITICAL, and its TTL cut 26000 -> 9600.
    # THE BRAIN HAD NO LIVENESS ALARM, ONLY A MEMORY ALARM. `learning-brain`
    # was its one critical key — but that is the key `_save_state` writes, and
    # `(hw)`/`(hx)` established it goes dark for a reason that is NOT process
    # death (the run crashed AFTER publishing, so memory froze while vitals
    # stayed fresh). It has therefore been DARK and paging continuously since
    # 28-Jul, which is exactly how an operator learns to ignore DARK.
    # `brain-vitals` is the per-run HEARTBEAT — published every run, before
    # `_save_state` — so it is the key that distinguishes "the brain is not
    # running" from "the brain cannot remember". The two alarms are different
    # facts and both are worth having.
    # MEASURED 01-Aug: bot_learn stopped at 16:02Z and 13.8h later nothing had
    # paged, while `scout-tuner` logged "brain dark ... lens-keyed bar walks
    # suppressed" — the growth rail degraded with the pager silent.
    # TTL: the loop is 7200s (run_all.sh), and the old 26000s put DARK (3x TTL)
    # at 21.7h — nine missed cycles. 9600s puts LATE at one missed cycle and
    # DARK at 8h / four missed cycles, which is inside a working day.
    ("brain-vitals",       "🔬 Brain vitals — v3 statistics engine",  True,  9600),
    # [2026-07-16] Event Sentinel — typed major-event detection + sector
    # ripple playbook (advisory; grades its own anticipations).
    # [2026-08-01] PROMOTED TO CRITICAL — this is the "promote per-organ once
    # proven" clause below being exercised, and the proof is an incident.
    # MEASURED this morning: `event-sentinel`, `event-sentinel-state` and
    # `tuning-proposals` were all 12.5h stale — 18.8x this key's own TTL, DARK
    # by `organ_status` six times over — while `bot_learn` had also stopped
    # (brain-vitals 12.9h). Exactly two organ loops in a container whose other
    # ~20 organs were seconds fresh, i.e. two dead `( while true ... ) &`
    # subshells, and NOT a class `(hw)`'s `organ_main` wrapper can ever catch:
    # a subshell that has DIED runs no handler and records no error.
    # The pager said nothing for 12.5h, because this was the sentinel's ONLY
    # key and it was non-critical — the organ was entirely unpageable.
    # It is also not merely advisory any more: it is the sole publisher of
    # `tuning-proposals`, a growth-rail author channel, so its death silently
    # removes a proposer. Storm risk is bounded — DARK needs 3x2400s = 2h,
    # i.e. 12 consecutive missed cycles on a 600s loop.
    ("event-sentinel",     "🗞️ Event Sentinel — major events/ripples", True,  2400),
    ("signal-bus",         "🚌 Signal bus mirror",                    False, 900),
    ("regime-oracle",      "🧭 Regime oracle",                        False, 14400),
    # [2026-07-16] growth-rail cohort — was headless; now health-graded.
    # Only immune + respiration are watchdog-critical for the first rollout
    # (a DARK immune/lungs = the fleet is flying blind); the rest bed in as
    # non-critical to avoid a pager storm, promote per-organ once proven.
    # [2026-07-16] EVENT, not TTL'd: write_levers() returns None and writes
    # NOTHING when no lever is authored, so a quiet key means "no levers
    # active — they auto-reverted", which is the HEALTHY resting state, not a
    # dead organ. It sat permanently DARK on a calm fleet, which is exactly
    # how operators learn to ignore DARK. The tuner's real liveness is proven
    # by 'scout-tuner' below, which IS an unconditional per-run heartbeat.
    ("fleet-tuning",       "🎚️ Fleet tuning — active levers",        False, None),
    ("scout-tuner",        "🔧 Scout tuner — self-enacted levers",    False, 10800),
    # [2026-07-16] proprioception — the growth rail grading its own
    # enactments (out-of-sample); the tuner consumes hurting verdicts.
    ("fleet-proprioception", "🦾 Proprioception — enactment outcomes", False, 2700),
    ("strategy-incubator", "🧬 Incubator — champion genotype",        False, 10800),
    # [2026-07-23] edge radar — per-book significance/both-halves/median/ETA.
    # Publish-only, 30-min loop; a fresh row attests the fleet_radar organ ran.
    ("fleet-radar",        "📡 Edge radar — book verdicts + ETA",     False, 5400),
    # [2026-08-04 (iy)] allocation organ — I16's instrument (claims table +
    # evidence-weighted split). Publishes on the radar's 30-min loop; it was
    # publishing healthily with NO surface serving it and NO roster entry, so
    # it could go dark unseen — both halves of the (hw)/I13 class at once.
    ("fleet-allocation",   "💰 Allocation — capital vs measured claims", False, 5400),
    # [2026-07-30] go-live grader — the (fk) bar, now an organ on a 6-hourly
    # loop. Staleness matters here for a specific reason: this is the ONLY
    # published view of how close a book is to holding real money, so a dark
    # row means the operator is reading a frozen scoreboard. 8h allows one
    # missed publish on a 6h cadence.
    ("golive-readiness",   "🚦 Go-live grader — bars per book",       False, 28800),
    # [2026-07-28] RE-TYPED heartbeat: the incubator now republishes the
    # queue EVERY cycle (queue_carry heartbeat — the §3b residual fix), and
    # the judge consumes it FAIL-CLOSED on its own updated+ttl_sec, so a
    # stale queue is a REAL failure mode (candidates silently expiring
    # unseen) that this card must show — the old EVENT typing ("silence ≠
    # failure") described the pre-heartbeat publisher and would have hidden
    # exactly the starvation the judge now enforces against.
    ("xp-queue",           "📥 XP queue — candidates for the judge",  False, 10800),
    ("xp-judge",           "⚖️ XP judge — promotion state machine",   False, 10800),
    ("fleet-immune",       "🛡️ Fleet immune — sick/quarantine",       True,  2400),
    ("fleet-regen",        "🩹 Fleet regen — auto-heal",              False, 2400),
    ("fleet-respiration",  "🫁 Respiration — data-feed SpO2",         True,  1200),
    ("fleet-clock",        "🕰️ Fleet clock — sessions/market events", False, 1800),
    ("impl-shortfall",     "📉 Impl shortfall — live vs shadow slip", False, 3600),
    # [2026-07-17 AUDIT] gapscout-census REMOVED: Gap Scout was retired today
    # (6432868 — it arb'd Kraken/Binance/Coinbase with no Lighter leg) and now
    # IDLES with no publishes, while cleanup_legacy_bots prunes bot_pnl only —
    # so the frozen bot_state row would have sat DARK forever and the Autonomy
    # card rendered "· STALE" forever. A row that is permanently DARK by design
    # is how operators learn to ignore DARK, which is the one thing this list
    # cannot afford: fleet-alerts/fleet-tuning/xp-queue are EVENT-typed for
    # exactly this reason. The ledger + odometer history are kept; if Gap Scout
    # is ever resurrected (GAPSCOUT_RETIRED_OVERRIDE=run) restore this line.
    ("fleet-alerts",       "🔔 Alert feed (event-driven)",            False, None),
    ("evidence-review",    "🧾 Evidence review (daily + operator)",   False, None),
    # [2026-07-21] 🏛️ the Parliament — Howard's vitals (6 books, 10-scanner
    # bench, 5-model ML, per-organ beats) + the tuner bench's active levers.
    # Non-critical for the first rollout per the growth-rail bedding-in
    # doctrine above; promote once a few quiet weeks prove the baseline.
    # Both keys are UNCONDITIONAL per-cycle publishes (never event-typed),
    # so a stale row here really is a sick chamber.
    ("parliament",         "🏛️ Parliament — six PM books + organs",   False, 900),
    ("parliament-tuning",  "🎚️🏛️ Parliament tuners — active levers",  False, 900),
]

# The consumption matrix: (signal, publisher, consumers, mode, freshness key).
# Static contract truth — freshness comes live from the organ read. An honest
# row for everything published-but-unconsumed keeps the map from flattering.
CONTRACTS = [
    ("light + long-budget veto", "fleet_risk.py",
     "family bot · Ticket Taker · Tide Rider LIVE",
     "ENFORCED (kill switch FLEET_RISK_MODE=advisory)", "fleet-risk"),
    ("clip_scale (drawdown governor)", "fleet_risk.py",
     "Ticket Taker · family bot (entry sizing)", "enforced", "fleet-risk"),
    ("stake multipliers (L4)", "bot_learn.py",
     "family bot custom_stake_amount via fleet_bus",
     "two-way since 21-Jul · floors n≥30 / 3 runs", "brain-stake-mults"),
    ("panic flag", "market_pulse.py", "strategies (half-stake on panic)",
     "enforced", "market-pulse"),
    ("tickets (per-lens)", "lighter_market_scout.py",
     "Ticket Taker (high-conviction bars, shadow $1k)", "shadow book",
     "lighter-market"),
    ("venue stress", "lighter_market_scout.py", "Ticket Taker stress veto",
     "restrict-only", "lighter-market"),
    ("lens-forward grades", "bot_learn.py",
     "21-Jul lens ruling · taker lens veto", "restrict-only", "brain-lens-forward"),
    # [2026-07-17 AUDIT] freshness key was 'fleet-alerts' — the wrong key. The
    # vetoes publish as 'coin-vetoes'; fleet-alerts is force-set to EVENT (see
    # _organ_status), so this row could NEVER go dark — for what the row itself
    # calls the fleet's one automated action, gating a LIVE book and failing
    # OPEN. It attested the liveness of a different organ entirely.
    ("coin veto list", "market_context.py", "Funding Farmer (LIVE)",
     "restrict-only (the fleet's one automated action) · FAILS OPEN when stale",
     "coin-vetoes"),
    ("evidence proposals", "evidence_board.py",
     "NOTHING yet — shadow; review promotes via EVBOARD_MODE", "shadow",
     "evidence-board"),
    ("enactment outcome verdicts", "fleet_proprioception.py",
     "scout tuner (hurting-skip + helping-walk) · board (🦾 items, clip "
     "gates, ladder discount) · judge early-fade · incubator gene-skip · "
     "LIVE BOTS (get_lever hurting-revert, every loop) · "
     "any bot via fleet_bus.lever_outcome · /bus.json",
     "verdict-gated: restrict-first; live top step fail-closed",
     "fleet-proprioception"),
    ("market open/close events + heavy_ok", "fleet_clock.py",
     "published, unconsumed — first wiring decided at the 21-Jul review",
     "advisory", "fleet-clock"),
    ("regime / listing intel / bus extras", "various",
     "published, unconsumed (info-only by design)", "advisory", "signal-bus"),
]


def fetch_flow_vitals():
    """Is data actually MOVING — 24h write counts across every durable store.
    Returns {} on DB trouble (the page renders without it)."""
    import psycopg2
    out = {}
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.paper_trades') pt, "
                            "to_regclass('public.bot_trades') bt, "
                            "to_regclass('public.bot_equity_history') eh, "
                            "to_regclass('public.venue_orders') vo")
                pt, bt, eh, vo = cur.fetchone()
                if pt:
                    cur.execute(
                        "SELECT COUNT(*) FILTER (WHERE side IS DISTINCT FROM 'skip'), "
                        "COUNT(*) FILTER (WHERE side = 'skip'), "
                        "COUNT(*) FILTER (WHERE side IS DISTINCT FROM 'skip' AND pnl_pct IS NULL) "
                        "FROM paper_trades WHERE seen_at > now() - interval '24 hours'")
                    c, sk, nn = cur.fetchone()
                    out["paper_closes_24h"] = int(c)
                    out["sniper_skips_24h"] = int(sk)
                    out["paper_pct_null_24h"] = int(nn)
                if bt:
                    cur.execute("SELECT COUNT(*) FROM bot_trades "
                                "WHERE close_ts > now() - interval '24 hours'")
                    out["freqtrade_closes_24h"] = int(cur.fetchone()[0])
                if eh:
                    cur.execute("SELECT COUNT(*) FROM bot_equity_history "
                                "WHERE ts > now() - interval '24 hours'")
                    out["equity_samples_24h"] = int(cur.fetchone()[0])
                if vo:
                    # [2026-07-21] the column is `at` (bot_pnl_store.py:1333);
                    # `seen_at` raised here on every call since the counter
                    # shipped, so venue_orders_24h silently never rendered —
                    # the fill-telemetry heartbeat the 28-Jul D4 read needs.
                    cur.execute("SELECT COUNT(*) FROM venue_orders "
                                "WHERE at > now() - interval '24 hours'")
                    out["venue_orders_24h"] = int(cur.fetchone()[0])
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        pass
    return out


def _states_with_ts(keys):
    """Like fetch_states but ALSO returns the bot_state TABLE's updated_at —
    several organs (brain, pulse) carry no timestamp inside their payload;
    the table stamp is the truth of when they last wrote."""
    import psycopg2
    out = {}
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_state') AS t")
                if cur.fetchone()[0] is None:
                    return out
                cur.execute("SELECT bot, state, updated_at FROM bot_state "
                            "WHERE bot = ANY(%s)", (list(keys),))
                for k, s, ts in cur.fetchall():
                    out[k] = (s if isinstance(s, dict) else json.loads(s), ts)
        finally:
            conn.close()
    except Exception:  # noqa: BLE001
        pass
    return out


def vitals_payload():
    """Machine-readable health of the whole operation (serves /vitals.json;
    the in-service watchdog reads it for ORGAN DARK detection)."""
    now = time.time()
    sts = _states_with_ts([k for k, *_ in ORGAN_SPECS])
    organs = []
    for key, label, critical, fb_ttl in ORGAN_SPECS:
        # [2026-07-16 AUDIT FIX] one malformed payload among 23 organ keys
        # used to kill the ENTIRE vitals surface (and with it the watchdog's
        # organ-death detection — the monitoring died of what it monitors).
        # Each organ now degrades alone to a loud ERROR row.
        try:
            st, row_ts = sts.get(key) or ({}, None)
            if not isinstance(st, dict):
                st = {}
            upd = st.get("updated") or st.get("updated_at") or st.get("reviewed_at")
            if key == "fleet-alerts":
                al = st.get("alerts")
                last = (al[-1] if al and isinstance(al, list) else None)
                ts = last.get("ts") if isinstance(last, dict) else None
                if isinstance(ts, (int, float)):
                    age_s = now - float(ts)
                else:
                    _t = _iso_dt(ts)
                    age_s = (now - _t.timestamp()) if _t else None
            else:
                u = _iso_dt(upd)
                if u is None and row_ts is not None:
                    u = row_ts   # table write stamp — when the organ last spoke
                age_s = (now - u.timestamp()) if u else None
            try:
                ttl = float(st.get("ttl_sec")) if st.get("ttl_sec") else fb_ttl
            except Exception:
                ttl = fb_ttl                   # a junk ttl_sec is not a dead organ
            # [2026-08-15 (mw)] A CRITICAL organ's payload may TIGHTEN its
            # paging bar, never slacken it. The 01-Aug promotion cut
            # brain-vitals' spec TTL 26000 -> 9600 ("DARK at 8h, inside a
            # working day") — but this line preferred the payload's own
            # ttl_sec, and bot_learn kept publishing 26000, so runtime DARK
            # sat at 3x26000 = 21.7h and the engraved I13 enforcement was
            # green-while-inert (the (iz) shape). The 01-Aug incident replayed
            # today would read LATE at 13.8h — and LATE never pages. min()
            # closes the class for every FUTURE critical organ whose publisher
            # drifts, not just this one; non-critical organs keep
            # payload-preferred TTLs (their payload IS the contract).
            if critical and ttl is not None and fb_ttl:
                ttl = min(ttl, float(fb_ttl))
            if key in ("fleet-alerts", "evidence-review",
                       # [2026-07-16 AUDIT FIX] written ON EVENTS only (an
                       # enactment / a proposal) — in a healthy, QUIET fleet
                       # they sat permanently DARK, training the operator to
                       # ignore DARK. [2026-07-28] xp-queue REMOVED from this
                       # set: the incubator heartbeats it every cycle now and
                       # the judge fail-closes on staleness, so DARK/LATE is
                       # a real, actionable state again.
                       "fleet-tuning"):
                ttl = None                     # event-driven: silence ≠ failure
            organs.append({
                "key": key, "label": label, "critical": critical,
                "age_min": round(age_s / 60, 1) if age_s is not None else None,
                "ttl_sec": ttl, "status": organ_status(age_s, ttl),
                "vital": _organ_vital(key, st),
            })
        except Exception as e:  # noqa: BLE001
            organs.append({"key": key, "label": label, "critical": critical,
                           "age_min": None, "ttl_sec": None, "status": "ERROR",
                           "vital": f"payload unreadable ({type(e).__name__})"})
    fresh = {o["key"]: o["status"] for o in organs}
    contracts = [{"signal": s, "publisher": p, "consumers": c, "mode": m,
                  "freshness": fresh.get(k, "?")} for s, p, c, m, k in CONTRACTS]
    try:
        import fleet_watchdog_svc
        wd = fleet_watchdog_svc.get_state()
    except Exception:  # noqa: BLE001
        wd = {}
    try:
        flows = fetch_flow_vitals()
    except Exception:  # noqa: BLE001
        flows = {}     # the flows section must never take the organs down
    return {"updated": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "organs": organs, "contracts": contracts,
            "flows": flows, "watchdog": wd}


def render_vitals():
    """The health tab: watchdog headline, organ vitals, consumption matrix,
    flow vitals, and the board/brain/scout minis — one page answering
    'is the ORGANISM working', not just 'are the bots up'."""
    p = vitals_payload()
    _c = {"FRESH": "#3fb950", "LATE": "#d29922", "DARK": "#f85149",
          "ERROR": "#f85149", "EVENT": "#8b949e"}

    wd = p.get("watchdog") or {}
    probs = wd.get("problems") or []
    wd_line = (f'<div class="banner">🚨 {" · ".join(html.escape(x) for x in probs)}</div>'
               if probs else
               '<div class="okline">Watchdog ✓ no problems · snapshot: '
               + html.escape(str(wd.get("snapshot") or "?"))
               + (' · 📱 push armed' if wd.get("push_armed") else ' · 📱 PUSH NOT ARMED')
               + '</div>')
    warns = wd.get("warnings") or []
    if warns:
        wd_line += ('<div class="muted" style="margin:4px">⚠️ '
                    + " · ".join(html.escape(w) for w in warns) + '</div>')

    orows = "".join(
        f'<tr><td>{html.escape(o["label"])}</td>'
        f'<td style="color:{_c.get(o["status"], "#8b949e")};font-weight:600">{o["status"]}</td>'
        f'<td>{("%.0fm" % o["age_min"]) if o.get("age_min") is not None else "—"}</td>'
        f'<td class="muted">{html.escape(str(o.get("vital") or "—"))}</td></tr>'
        for o in p["organs"])
    crows = "".join(
        f'<tr><td>{html.escape(c["signal"])}</td>'
        f'<td class="muted">{html.escape(c["publisher"])}</td>'
        f'<td>{html.escape(c["consumers"])}</td>'
        f'<td class="muted">{html.escape(c["mode"])}</td>'
        f'<td style="color:{_c.get(c["freshness"], "#8b949e")}">{c["freshness"]}</td></tr>'
        for c in p["contracts"])
    fl = p.get("flows") or {}
    chips = " · ".join(f'{k.replace("_", " ")} <b>{v}</b>' for k, v in sorted(fl.items())) or "no flow data"
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>Fleet Health — vitals</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}} h2{{font-size:15px;margin:20px 4px 6px}}
 a{{color:#58a6ff;text-decoration:none;font-size:14px}}
 .wrap{{padding:14px}} .muted{{color:#8b949e;font-size:12px}}
 .banner{{margin:12px 4px;padding:10px 12px;background:#3d1d1d;border:1px solid #6b2a2a;border-radius:8px;color:#f0a0a0;font-size:13px}}
 .okline{{margin:12px 4px;padding:8px 12px;background:#12261a;border:1px solid #1f4d2e;border-radius:8px;color:#7ee2a8;font-size:13px}}
 table{{border-collapse:collapse;width:100%;font-size:13px}}
 td,th{{padding:6px 8px;border-bottom:1px solid #21262d;text-align:left;vertical-align:top}}
 th{{color:#8b949e;font-weight:600;font-size:12px}}
</style></head><body>
<header><h1>Fleet Health — vitals &nbsp;·&nbsp; <a href="/">← live</a> &nbsp; <a href="/history">history</a> &nbsp; <a href="/periods">periods</a> &nbsp; <a href="/market">market</a> &nbsp; <a href="/learning">learning</a></h1></header>
<div class="wrap">
{wd_line}
<h2>🫀 Organ vitals — is every intelligence organ publishing on its own cadence?</h2>
<table><tr><th>organ</th><th>status</th><th>age</th><th>vital sign</th></tr>{orows}</table>
<div class="muted" style="margin:6px 4px">FRESH within its own ttl · LATE to 3× · DARK beyond (critical DARK organs page the phone via the watchdog) · EVENT = event-driven, silence is an answer.</div>
<h2>🔗 Consumption matrix — who publishes, who consumes, what mode (live freshness per contract)</h2>
<table><tr><th>signal</th><th>publisher</th><th>consumed by</th><th>mode</th><th>fresh</th></tr>{crows}</table>
<h2>🚿 Flow vitals — did data actually move in the last 24h?</h2>
<div style="font-size:13px;margin:4px">{chips}</div>
</div>
<footer class="muted" style="padding:10px 18px">Auto-refreshes 60s · machine feed at /vitals.json (no auth) · times UTC.</footer>
</body></html>'''


def fetch_tick():
    """The cheapest possible "has anything changed?" signal for the live page.

    ONE round-trip, two indexed MAX(updated_at) reads over the tables that feed
    every card — bot_pnl (all bot rows) and bot_state (every organ). Returns
    {"v": <latest epoch>, "t": <server now epoch>}. The client polls THIS every
    few seconds and only re-fetches the full page when `v` moves, so the
    expensive full render runs about as often as data actually changes — not on
    a fixed timer. That keeps DB load at or below today's blanket 30s
    meta-refresh while making the page feel live.

    Fail-OPEN: on any error it returns `v=None`, which the client treats as
    "can't tell — refresh anyway on the slow fallback". A dashboard that can't
    prove data is fresh must not pretend it is (an operating station shows when
    it's blind), but it also must never freeze — hence the fallback."""
    import psycopg2
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT extract(epoch from GREATEST("
                    "  (SELECT max(updated_at) FROM bot_pnl),"
                    "  (SELECT max(updated_at) FROM bot_state)))")
                row = cur.fetchone()
                v = float(row[0]) if row and row[0] is not None else None
        finally:
            conn.close()
        return {"v": v, "t": time.time()}
    except Exception:
        return {"v": None, "t": time.time()}


# [2026-07-18] LIVE STATION — turn the auto-refreshing page into a real
# operating console. Replaces the blunt full-page `<meta http-equiv=refresh>`
# (which reloads everything, flickers, and drops your scroll position) with an
# in-place morph: poll the cheap /tick.json, and only when the data version
# changes, fetch the page and swap the #station container's innerHTML. Every
# item updates, nothing flickers, scroll is kept.
#
# DESIGN NOTES (each earned):
#  * The poller lives OUTSIDE #station. innerHTML assignment does not execute
#    <script> tags, so morphing #station can never kill the loop driving it.
#  * <noscript> keeps a slow meta-refresh, so a JS-off browser still updates.
#  * A HEARTBEAT shows live / stale / OFFLINE — an operating station must show
#    when it has stopped seeing the fleet, never present old data as current.
#  * FAIL-SAFE: if /tick.json errors repeatedly the page force-reloads on a slow
#    timer, so a broken poller degrades to today's behaviour, never to a frozen
#    screen watching real money.
#  * A 1-second "updated Ns ago" ticker makes liveness visible between morphs.
LIVE_POLL_MS = int(os.environ.get("DASH_LIVE_POLL_MS", "5000"))
LIVE_FALLBACK_MS = int(os.environ.get("DASH_LIVE_FALLBACK_MS", "60000"))
# [2026-08-04 (iy)] Minimum interval between full-page refetches. /tick.json's
# `v` is MAX(updated_at) over bot_pnl AND bot_state, and with 22 bots + ~30
# organs publishing, `v` moves every ~13-19s (measured) — so the "only when
# data changes" morph was in practice a full 584 KB refetch 3-6x/min per open
# tab. The tick poll stays cheap and fast (heartbeat honesty); the EXPENSIVE
# refetch is throttled to this floor. 30s matches the old blanket meta-refresh
# the station replaced, so liveness is not worse than the design it improved.
LIVE_MIN_MORPH_MS = int(os.environ.get("DASH_LIVE_MIN_MORPH_MS", "30000"))


# [2026-07-18] Interactive charts, morph-safe. The live-station morph replaces
# innerHTML and does NOT re-run <script>, so per-chart init would die on the
# first data update. This handler is DELEGATED on `document` — attached once,
# outside #station, so it survives every morph and simply re-targets whatever
# .ichart SVGs the fresh markup contains. It reads the polyline's OWN points
# for geometry (no per-point data embedded — the shape is already in the DOM)
# and inverts a tiny scale (data-lo/hi + data-t0/t1) to recover value + time at
# the cursor. Tooltip/crosshair are HTML overlays, not SVG: the charts use
# preserveAspectRatio="none", which would stretch any SVG text.
CHART_JS = '''<script>
(function(){
  var tip,cross,dot;
  function el(css){var d=document.createElement("div");d.style.cssText=css;
    d.style.position="fixed";d.style.pointerEvents="none";d.style.zIndex="9999";
    d.style.display="none";document.body.appendChild(d);return d;}
  function ensure(){
    if(tip) return;
    tip=el("background:#0d1117;color:#e6e6e6;border:1px solid #30363d;border-radius:6px;"
      +"padding:5px 8px;font:12px -apple-system,system-ui,sans-serif;white-space:nowrap;"
      +"box-shadow:0 2px 8px rgba(0,0,0,.4)");
    cross=el("width:1px;background:#8b949e;opacity:.6");
    dot=el("width:8px;height:8px;border-radius:50%;background:#fff;"
      +"box-shadow:0 0 0 2px #0d1117;margin:-4px 0 0 -4px");
  }
  function fmtMoney(v){var s=v<0?"-":"+";
    return s+Math.abs(v).toLocaleString("en-US",{minimumFractionDigits:2,maximumFractionDigits:2});}
  function fmtTime(sec){var d=new Date(sec*1000);
    function p(n){return(n<10?"0":"")+n;}
    return d.getUTCFullYear()+"-"+p(d.getUTCMonth()+1)+"-"+p(d.getUTCDate())+" "
      +p(d.getUTCHours())+":"+p(d.getUTCMinutes())+" UTC";}
  function findChart(t){while(t&&t!==document){
    if(t.classList&&t.classList.contains("ichart"))return t;t=t.parentNode;}return null;}
  function hide(){if(tip){tip.style.display=cross.style.display=dot.style.display="none";}}
  document.addEventListener("pointermove",function(e){
    var svg=findChart(e.target); if(!svg){hide();return;}
    var pl=svg.querySelector("polyline"); if(!pl||!pl.points){hide();return;}
    var pts=pl.points, n=pts.numberOfItems; if(n<2){hide();return;}
    var r=svg.getBoundingClientRect();
    var f=Math.min(1,Math.max(0,(e.clientX-r.left)/r.width));
    var idx=Math.round(f*(n-1)); var p=pts.getItem(idx);
    var lo=+svg.dataset.lo, hi=+svg.dataset.hi, h=+svg.dataset.h||170;
    var t0=+svg.dataset.t0, t1=+svg.dataset.t1;
    var val=lo+(1-p.y/h)*(hi-lo);
    var ts=t0+(n>1?idx/(n-1):0)*(t1-t0);
    ensure();
    var snapX=r.left+(idx/(n-1))*r.width;
    var snapY=r.top+(p.y/h)*r.height;
    cross.style.display="block";cross.style.left=snapX+"px";
    cross.style.top=r.top+"px";cross.style.height=r.height+"px";
    dot.style.display="block";dot.style.left=snapX+"px";dot.style.top=snapY+"px";
    tip.innerHTML="<b>"+fmtMoney(val)+"</b><br><span style=\\"color:#8b949e\\">"+fmtTime(ts)+"</span>";
    tip.style.display="block";
    var tw=tip.offsetWidth, left=snapX+12;
    if(left+tw>window.innerWidth-8) left=snapX-tw-12;
    tip.style.left=left+"px";
    tip.style.top=Math.max(8,r.top-8)+"px";
  },true);
  document.addEventListener("pointerleave",hide,true);
  window.addEventListener("scroll",hide,true);
})();
</script>'''


def live_js(container="station"):
    """Vanilla-JS live updater for a page whose morphable content is in
    `#<container>`, PLUS the delegated interactive-chart handler (CHART_JS).
    Both attach to document, so they survive content morphs. No dependencies."""
    return CHART_JS + f'''<script>
(function(){{
  var POLL={LIVE_POLL_MS}, FB={LIVE_FALLBACK_MS}, MM={LIVE_MIN_MORPH_MS}, ID="{container}";
  var last=null, lastOk=Date.now(), lastMorph=0, fails=0, busy=false;
  var hb=document.getElementById("hb"), age=document.getElementById("hbage");
  function beat(state){{
    if(!hb) return;
    var m={{live:["#2ea043","live"],stale:["#d29922","reconnecting…"],
            off:["#f85149","OFFLINE — not updating"]}}[state]||["#8b949e","…"];
    hb.style.background=m[0]; hb.title=m[1];
    var t=hb.nextElementSibling; if(t&&t.classList.contains("hbtxt")) t.textContent=m[1];
  }}
  async function morph(){{
    var r=await fetch(location.href,{{cache:"no-store",headers:{{"X-Live":"1"}}}});
    if(!r.ok) throw new Error("http "+r.status);
    var t=await r.text();
    var doc=new DOMParser().parseFromString(t,"text/html");
    var fresh=doc.getElementById(ID), cur=document.getElementById(ID);
    if(fresh&&cur&&fresh.innerHTML!==cur.innerHTML) cur.innerHTML=fresh.innerHTML;
    lastOk=Date.now();
  }}
  async function tick(){{
    if(busy) return; busy=true;
    try{{
      var r=await fetch("/tick.json",{{cache:"no-store"}});
      var j=await r.json(); fails=0; beat("live");
      if((j.v===null||j.v!==last)&&Date.now()-lastMorph>=MM){{
        last=j.v; lastMorph=Date.now(); await morph(); }}
    }}catch(e){{
      fails++; beat(fails>2?"off":"stale");
      // fail-safe: a persistently blind poller must not leave a frozen page
      if(Date.now()-lastOk>FB){{ location.reload(); }}
    }}finally{{ busy=false; }}
  }}
  function ageTick(){{
    if(!age) return;
    var s=Math.max(0,Math.round((Date.now()-lastOk)/1000));
    age.textContent=s<60?("updated "+s+"s ago"):("updated "+Math.floor(s/60)+"m ago");
  }}
  document.addEventListener("visibilitychange",function(){{
    if(!document.hidden) tick(); // catch up instantly when the tab refocuses
  }});
  setInterval(tick,POLL); setInterval(ageTick,1000); tick();
}})();
</script>'''


# Shared heartbeat CSS + footer widget, injected by live_wrap into the
# drill-down pages (the main page carries its own copy inline).
LIVE_CSS = ('<style>'
            '.hbwrap{display:inline-flex;align-items:center;gap:5px;font-weight:600}'
            '.hb{width:9px;height:9px;border-radius:50%;background:#8b949e;'
            'display:inline-block;animation:hbpulse 2s infinite}'
            '@keyframes hbpulse{0%{box-shadow:0 0 0 0 rgba(46,160,67,.45)}'
            '70%{box-shadow:0 0 0 6px rgba(46,160,67,0)}'
            '100%{box-shadow:0 0 0 0 rgba(46,160,67,0)}}'
            '</style>')
HEARTBEAT_HTML = ('<span class="hbwrap"><span id="hb" class="hb" title="live">'
                  '</span> <span class="hbtxt">live</span> · '
                  '<span id="hbage">updated 0s ago</span></span>')


def live_wrap(page):
    """Turn a static, meta-refresh page into a live-updating one — mechanically,
    so every drill-down page gets the same treatment without hand-surgery.

    Does four things, each idempotent-safe and each a no-op if its anchor is
    absent (a page missing a <footer> or <body> still returns valid HTML):
      1. the <meta refresh> becomes a <noscript> fallback (JS-off still cycles);
      2. injects the heartbeat CSS before </head>;
      3. wraps the body in <div id="station"> … </div> (the morph target),
         closing right before the footer so the footer + poller stay OUTSIDE it;
      4. drops the heartbeat into the footer and the poller before </body>.

    SAFE on these pages specifically because they carry NO inline <script> — a
    morph replaces innerHTML and does not re-run scripts, so a page that drew a
    chart in JS would break; these draw everything server-side. Verified: 0
    <script>/<canvas> across all five drill-downs before wiring this."""
    import re
    if "<div id=\"station\">" in page:      # already wrapped — never double-wrap
        return page
    page = re.sub(r'<meta http-equiv="refresh" content="\d+">',
                  lambda m: f'<noscript>{m.group(0)}</noscript>', page, count=1)
    page = page.replace('</head>', LIVE_CSS + '</head>', 1)
    page = page.replace('<body>', '<body>\n<div id="station">', 1)
    # close #station right before the footer (or, failing that, before </body>)
    idx = page.rfind('<footer')
    if idx == -1:
        idx = page.rfind('</body>')
    if idx != -1:
        page = page[:idx] + '</div>\n' + page[idx:]
    # heartbeat just inside the footer's open tag; poller before </body>
    page = re.sub(r'(<footer[^>]*>)', lambda m: m.group(1) + HEARTBEAT_HTML + ' · ',
                  page, count=1)
    page = page.replace('</body>', live_js("station") + '</body>', 1)
    return page


def fetch_states(keys):
    """{key: state_dict} for several bot_state keys in ONE round-trip."""
    import psycopg2
    out = {}
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_state') AS t")
                if cur.fetchone()[0] is None:
                    return out
                cur.execute("SELECT bot, state FROM bot_state WHERE bot = ANY(%s)",
                            (list(keys),))
                for k, s in cur.fetchall():
                    out[k] = s if isinstance(s, dict) else json.loads(s)
        finally:
            conn.close()
    except Exception:
        pass
    return out


def _chip(label, value, color=None, title=""):
    ve = html.escape(str(value))
    v = f'<b style="color:{color}">{ve}</b>' if color else f'<b>{ve}</b>'
    t = f' title="{html.escape(title)}"' if title else ""
    return f'<span class="chip"{t}>{html.escape(label)} {v}</span>'


def _state_fresh(payload, grace=2.0):
    """Honor the organs' own updated+ttl_sec contract (fleet_bus.is_fresh
    semantics): False when the payload is older than grace×ttl. Payloads
    without the fields are treated as fresh (older organs)."""
    upd = _iso_dt((payload or {}).get("updated"))
    ttl = (payload or {}).get("ttl_sec")
    if upd is None or not ttl:
        return True
    age = (dt.datetime.now(dt.timezone.utc) - upd).total_seconds()
    return age <= float(ttl) * grace


def _state_age_h(payload):
    upd = _iso_dt((payload or {}).get("updated"))
    if upd is None:
        return None
    return (dt.datetime.now(dt.timezone.utc) - upd).total_seconds() / 3600.0


def ops_strip_html():
    """The cockpit line: should the fleet be trading right now? Risk light,
    budget usage, drawdown governor, venue stress, alert pressure — the five
    numbers an operator checks before anything else.
    [2026-07-15 AUDIT FIX] Organs are checked against their own updated+ttl_sec
    contract: a dead publisher renders as a loud red STALE chip instead of
    silently painting its last state as current."""
    st = fetch_states(["fleet-risk", "lighter-market"])
    fr = st.get("fleet-risk") or {}
    lm = st.get("lighter-market") or {}
    parts = []
    if fr and not _state_fresh(fr):
        _a = _state_age_h(fr)
        parts.append(_chip("Risk organ", f"STALE {_a:.0f}h" if _a else "STALE",
                           "#d1242f", "fleet_risk stopped publishing — its last "
                           "light/governor values are NOT current"))
        fr = {}
    if lm and not _state_fresh(lm):
        _a = _state_age_h(lm)
        parts.append(_chip("Scout", f"STALE {_a:.0f}h" if _a else "STALE",
                           "#d1242f", "lighter_market_scout stopped publishing"))
        lm = {}
    light = str(fr.get("light") or "?").upper()
    # fleet_risk emits lowercase green/yellow/red ([2026-07-15 AUDIT FIX]:
    # the map keyed AMBER, so the warning state rendered gray).
    lcol = {"GREEN": "#1a7f37", "YELLOW": "#b8860b", "RED": "#d1242f"}.get(light, "#5b7184")
    parts.append(_chip("Risk light", light, lcol,
                       f"fleet_risk mode={fr.get('mode', '?')} — long-budget veto is "
                       f"ENFORCED in the strategies via fleet_bus"))
    if fr:
        parts.append(_chip(
            "Book", f"{fr.get('long_positions', '?')}L/{fr.get('long_budget', '?')} · "
                    f"{fr.get('short_positions', '?')}S/{fr.get('short_budget', '?')}",
            None, "directional positions vs fleet budget (live + shadow cohort)"))
        eq, dd, cs = (fr.get("fleet_equity"), fr.get("fleet_dd_7d"),
                      fr.get("clip_scale"))
        if eq is not None:
            parts.append(_chip("Fleet eq", money(eq)))
        if dd is not None:
            parts.append(_chip("7d dd", f"{dd * 100:+.2f}%",
                               "#d1242f" if dd < -0.05 else None,
                               "drawdown governor input (clip_scale halves past -5%)"))
        if cs is not None and cs < 1:
            parts.append(_chip("CLIP SCALE", f"{cs:g}x", "#d1242f",
                               "drawdown governor is shrinking clips"))
    stress = lm.get("stress") or {}
    if stress:
        med = stress.get("med")
        parts.append(_chip("Lighter stress",
                           f"{med}bps med · p90 {stress.get('p90')}",
                           "#d1242f" if (med or 0) >= 15 else None,
                           "venue-wide |premium|; Ticket Taker pauses entries at med ≥ 15bps"))
    alerts = fetch_fleet_alerts(hours=24)
    n_act = sum(1 for a in alerts if a.get("severity") in ("warn", "action"))
    parts.append(_chip("Alerts 24h", f"{n_act} warn/action",
                       "#b8860b" if n_act else None, "full feed: /alerts.json"))
    if not fr and not lm and not any("STALE" in p for p in parts):
        return ('<div class="ops muted">fleet organs unreachable — risk light / '
                'governor unavailable (freqtrade-bots container down?)</div>')
    return '<div class="ops">' + "\n ".join(parts) + "</div>"


def taker_lens_card():
    """🎫 The scanner→bot→brain scoreboard: per-lens forward returns from the
    Ticket Taker's durable ledger. This table IS the Ticket Taker's purpose —
    it decides which scout lens earns a validated bot."""
    import psycopg2
    lens = {}
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.paper_trades') AS t")
                if cur.fetchone()[0] is None:
                    return ""
                cur.execute(
                    """SELECT reason, COUNT(*),
                              SUM(CASE WHEN pnl_abs > 0 THEN 1 ELSE 0 END),
                              COALESCE(SUM(pnl_abs), 0), COALESCE(AVG(pnl_pct), 0)
                       FROM paper_trades
                       WHERE bot = 'lighter-ticket-taker-lshadow'
                         AND closed_at IS NOT NULL
                       GROUP BY reason""")
                rows = cur.fetchall()
        finally:
            conn.close()
    except Exception:
        return ""
    for reason, n, w, pnl, avgp in rows:
        tag = (reason or "?").partition("_")[0] or "?"     # <side>-<lens>
        g = lens.setdefault(tag, {"n": 0, "w": 0, "pnl": 0.0, "wavg": 0.0})
        g["n"] += int(n); g["w"] += int(w or 0)
        g["pnl"] += float(pnl); g["wavg"] += float(avgp) * int(n)
    if not lens:
        body = ('<div class="muted">No closed lens trades yet — this book exists to '
                'collect exactly this evidence; rows appear as positions close.</div>')
    else:
        trs = []
        for tag, g in sorted(lens.items(), key=lambda kv: -kv[1]["pnl"]):
            exp = (g["wavg"] / g["n"] * 100) if g["n"] else 0.0
            trs.append(f'<tr><td>{html.escape(tag)}</td><td>{g["n"]}</td>'
                       f'<td>{g["w"]}/{g["n"] - g["w"]}</td>'
                       f'<td class="{cls(g["pnl"])}">{money(g["pnl"])}</td>'
                       f'<td class="{cls(exp)}">{exp:+.2f}%</td></tr>')
        body = ('<table class="tbl"><tr><th>side-lens</th><th>n</th><th>W/L</th>'
                '<th>P&amp;L</th><th>avg/trade</th></tr>' + "".join(trs) + '</table>')
    return (f'<div class="card"><h2>🎫 Ticket Taker — lens report card</h2>'
            f'<div class="muted">Each close is tagged &lt;side&gt;-&lt;lens&gt;_&lt;exit&gt;; '
            f'this grades every scout lens on REAL forward returns. A lens that stays '
            f'green at sample size graduates to the validation doctrine; a red one '
            f'gets switched off. UNVALIDATED by design until then.</div>{body}</div>')


def brain_panel_html():
    """The learning loop itself: venue A/B verdicts, active reduce-only
    throttles, the diagnosis layer's loss post-mortems, and the scout-lens
    forward scoreboard (the brain grading the scanners)."""
    st = fetch_states(["learning-brain", "brain-stake-mults", "brain-diagnosis",
                       "brain-lens-forward"])
    lb = st.get("learning-brain") or {}
    sm = st.get("brain-stake-mults") or {}
    lf = (st.get("brain-lens-forward") or {}).get("lenses") or {}
    dg = (st.get("brain-diagnosis") or {}).get("diagnoses") or lb.get("diagnoses") or {}
    if not lb and not sm:
        return ('<div class="card"><h2>🧠 Learning brain</h2>'
                '<div class="muted">brain state unreachable — bot_learn runs in the '
                'freqtrade-bots container every ~2h.</div></div>')
    # Venue A/B — the pivot's central evidence: same strategy, Kraken paper vs
    # Lighter shadow. The paper leg froze at the 14-Jul retirement; the gap is
    # the venue/execution difference the port is supposed to prove.
    ab = lb.get("venue_ab") or {}
    ab_rows = []
    for bot in sorted(ab):
        p, s = ab[bot].get("paper") or {}, ab[bot].get("shadow") or {}
        gap = ab[bot].get("gap_pnl")
        ab_rows.append(
            f'<tr><td>{html.escape(bot.replace("freqtrade-", ""))}</td>'
            f'<td class="{cls(p.get("pnl_abs"))}">{money(p.get("pnl_abs") or 0)} '
            f'<span class="n">({p.get("wins", 0)}W/{p.get("losses", 0)}L)</span></td>'
            f'<td class="{cls(s.get("pnl_abs"))}">{money(s.get("pnl_abs") or 0)} '
            f'<span class="n">({s.get("wins", 0)}W/{s.get("losses", 0)}L)</span></td>'
            f'<td class="{cls(gap)}">{money(gap or 0)}</td></tr>')
    ab_html = ""
    if ab_rows:
        ab_html = ('<div class="sub">Venue A/B — same strategy, Kraken paper (frozen '
                   '14 Jul) vs Lighter shadow</div>'
                   '<table class="tbl"><tr><th>bot</th><th>Kraken</th>'
                   '<th>Lighter</th><th>gap</th></tr>' + "".join(ab_rows) + '</table>')
    # [2026-07-15 AUDIT FIX] mults is NESTED {bot: {tag: {mult,n,wr,pnl,...}}}
    # (bot_learn.compute_stake_mults) — the flat render printed dicts as "x".
    # [2026-07-21 AUDIT FIX] the labels read the payload's OWN mode stamp —
    # they were hardcoded 'reduce-only' the same day the mults went two-way,
    # so an earned 1.25x/1.5x BOOST would have rendered under a 'throttle'
    # heading (the honest-label field existed precisely for this reader).
    _mode = sm.get("mode") or "reduce-only"
    mults = sm.get("mults") or {}
    if mults:
        _mrows = []
        for _bot, _tags in sorted(mults.items()):
            for _tag, _e in sorted((_tags or {}).items()):
                _m = (_e or {}).get("mult", _e)
                _n = (_e or {}).get("n")
                try:
                    _boost = float(_m) > 1.0
                except (TypeError, ValueError):
                    _boost = False
                _mrows.append(
                    f'<div class="row"><span>{html.escape(f"{_bot} · {_tag}")}</span>'
                    f'<b>{"⬆ " if _boost else ""}{_m}x{f" (n={_n})" if _n else ""}</b></div>')
        m_html = (f'<div class="sub">Active stake multipliers ({html.escape(_mode)})</div>'
                  + "".join(_mrows))
    else:
        m_html = ('<div class="sub">Stake multipliers</div><div class="muted">none active '
                  f'— {html.escape(_mode)} mode, min n={sm.get("min_n", "?")}, '
                  f'{sm.get("promote_runs", "?")} consecutive runs to apply.</div>')
    dg_items = []
    for key, d in sorted(dg.items()):
        prop = d.get("proposal") or ""
        ev = d.get("evidence") or {}
        dg_items.append(f'<li><b>{html.escape(d.get("primary", "?"))}</b> · '
                        f'{html.escape(prop)} <span class="n">(n={ev.get("n", "?")}, '
                        f'{money(ev.get("pnl") or 0)})</span></li>')
    dg_html = ""
    if dg_items:
        # [2026-07-21] label updated with BRAIN ACTS: ACTIONABLE
        # regime_timing findings now gate counter-regime entries
        # (restrict-only, shadow lane); everything else stays human-review.
        dg_html = ('<div class="sub">Loss diagnoses — WHERE each negative sleeve '
                   'loses (ACTIONABLE regime-timing findings gate counter-regime '
                   'entries, restrict-only; all else human-review)</div>'
                   f'<ul class="recs">{"".join(dg_items)}</ul>')
    # [2026-07-15 LENS-FORWARD] the brain grading the scanners: every scout
    # ticket's counterfactual forward return, by lens. This is the sample the
    # taker's ~6 fills can't provide — and the taker's restrict-only lens veto
    # reads exactly this table.
    lf_html = ""
    if lf:
        _rows = []
        for lens, o in sorted(lf.items(),
                              key=lambda kv: -(kv[1].get("avg4h_pct") or 0)):
            hit = o.get("hit4h")
            hit_s = "—" if hit is None else f"{hit * 100:.0f}%"
            a4, a24 = o.get("avg4h_pct"), o.get("avg24h_pct")
            _rows.append(
                f'<tr><td>{html.escape(lens)}</td>'
                f'<td>{o.get("n4h", 0)}</td>'
                f'<td>{hit_s}</td>'
                f'<td class="{cls(a4)}">{"—" if a4 is None else f"{a4:+.2f}%"}</td>'
                f'<td class="{cls(a24)}">{"—" if a24 is None else f"{a24:+.2f}%"}</td></tr>')
        lf_html = ('<div class="sub">Scout lens forward returns — counterfactual, '
                   'EVERY ticket (taker veto reads this at n≥75)</div>'
                   '<table class="tbl"><tr><th>lens</th><th>n·4h</th><th>hit</th>'
                   '<th>avg 4h</th><th>avg 24h</th></tr>' + "".join(_rows)
                   + '</table>')
    meta = (f'run #{lb.get("runs", "?")} · {len(lb.get("hypotheses") or {})} live '
            f'hypotheses · L4 meta-labeling two-way since 21-Jul '
            f'(expand on the v3 mirror bars; reduce unchanged)')
    return (f'<div class="card"><h2>🧠 Learning brain</h2>'
            f'<div class="muted">{meta}</div>{lf_html}{ab_html}{m_html}{dg_html}</div>')


def _iso_dt(s):
    from datetime import datetime, timezone
    try:
        d = datetime.fromisoformat(str(s).replace("Z", "+00:00"))
        # normalize naive -> UTC (fleet_bus.is_fresh semantics): a tz-naive
        # stamp used to TypeError in aware arithmetic (_state_fresh) and take
        # the whole Autonomy card down with it
        return d if d.tzinfo else d.replace(tzinfo=timezone.utc)
    except Exception:
        return None


# ---------------------------------------------------------------------------
# [2026-07-15 LIFECYCLE SECTIONS] The main grid is grouped by promotion stage,
# and the house go-live gates (Rules in CLAUDE.md: 30-day WR > 55% AND max
# drawdown < 15%, plus enough trades and a full 30-day record) are COMPUTED
# per bot, not asserted. A bot that passes every gate surfaces in "READY FOR
# LIVE" automatically — the promotion pipeline as a standing page section.

GATE_MIN_TRADES_30D = 20
GATE_MIN_AGE_DAYS = 30
GATE_MIN_WR = 0.55
GATE_MAX_DD = -0.15

# Books that are evidence collectors by design — never candidates until their
# thesis is validated through the doctrine (census / lens grading / overlap).
EXPERIMENT_BASES = {"lighter-ticket-taker", "lighter-dislocation",
                    "lighter-perp-sniper", "event-listing-sniper"}
# Reference books: kept for comparison, not on the promotion track.
CONTROL_BASES = {"perps-funding-carry"}

_GATES_CACHE = {"data": None, "ts": 0.0}


def fetch_gate_metrics(ttl=600):
    """{bot: {n30, w30, wr, dd, age_days}} from the union ledger + equity
    history. Cached ~10 min — the page refreshes every 30s and these
    aggregates move slowly.
    [2026-07-15 AUDIT FIXES] dd walks hourly MIN/MAX buckets (hourly AVG
    understated true peak-to-trough); age comes from the bot's FIRST-EVER
    snapshot (measuring inside the 30d window pinned the age gate at the
    boundary); failures never populate the cache (a cold-start DB blip froze
    all-failed gate chips for 10 min); the TEXT-timestamp cast is guarded by
    pg_input_is_valid (a prefix-date garbage value aborted the whole union)."""
    now = time.time()
    if _GATES_CACHE["data"] is not None and now - _GATES_CACHE["ts"] < ttl:
        return _GATES_CACHE["data"]
    import psycopg2
    out = {}
    try:
        conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT to_regclass('public.bot_trades') AS bt, "
                            "to_regclass('public.paper_trades') AS pt, "
                            "to_regclass('public.bot_equity_history') AS eh")
                has_bt, has_pt, has_eh = cur.fetchone()
                parts = []
                if has_bt:
                    parts.append("SELECT bot, close_ts, profit_abs FROM bot_trades "
                                 "WHERE is_open IS NOT TRUE AND close_ts IS NOT NULL")
                if has_pt:
                    # [2026-07-16] exclude side='skip' + NULL pnl: those rows are
                    # the sniper's gate-REJECTION logs, not trades. They land
                    # under a separate bot id today (event-listing-sniper-skips),
                    # so this only drops a phantom gate row — but if skips were
                    # ever written under a real bot id they'd silently inflate
                    # n30 and crater its win rate. Same guard as fetch_bot_quality.
                    parts.append("SELECT bot, closed_at::timestamptz, pnl_abs "
                                 "FROM paper_trades WHERE closed_at IS NOT NULL "
                                 "AND pg_input_is_valid(closed_at, 'timestamptz') "
                                 "AND side IS DISTINCT FROM 'skip' "
                                 "AND pnl_abs IS NOT NULL")
                if parts:
                    cur.execute(
                        f"""SELECT bot,
                                   COUNT(*) FILTER (WHERE close_ts > now() - interval '30 days'),
                                   COUNT(*) FILTER (WHERE close_ts > now() - interval '30 days'
                                                      AND profit_abs > 0)
                            FROM ({" UNION ALL ".join(parts)}) t(bot, close_ts, profit_abs)
                            GROUP BY bot""")
                    for bot, n30, w30 in cur.fetchall():
                        out.setdefault(bot, {})["n30"] = int(n30)
                        out[bot]["w30"] = int(w30)
                if has_eh:
                    cur.execute(
                        """SELECT bot, date_trunc('hour', ts) AS h,
                                  MIN(equity), MAX(equity)
                           FROM bot_equity_history
                           WHERE ts > now() - interval '30 days' AND equity IS NOT NULL
                           GROUP BY bot, 2 ORDER BY bot, 2""")
                    series = {}
                    for bot, h, lo, hi in cur.fetchall():
                        series.setdefault(bot, []).append((float(lo), float(hi)))
                    for bot, buckets in series.items():
                        peak, ddv = None, 0.0
                        for lo, hi in buckets:
                            peak = hi if peak is None or hi > peak else peak
                            if peak:
                                ddv = min(ddv, lo / peak - 1.0)
                        out.setdefault(bot, {})["dd"] = ddv
                    cur.execute("SELECT bot, MIN(ts) FROM bot_equity_history "
                                "WHERE equity IS NOT NULL GROUP BY bot")
                    for bot, f in cur.fetchall():
                        if f is None:
                            continue
                        age = (dt.datetime.now(dt.timezone.utc)
                               - f.replace(tzinfo=f.tzinfo or dt.timezone.utc))
                        out.setdefault(bot, {})["age_days"] = \
                            age.total_seconds() / 86400.0
        finally:
            conn.close()
    except Exception:
        # serve the last good cache or the partial once — NEVER cache failure
        if _GATES_CACHE["data"] is not None:
            return _GATES_CACHE["data"]
        for m in out.values():
            n, w = m.get("n30") or 0, m.get("w30") or 0
            m["wr"] = (w / n) if n else None
        return out
    for m in out.values():
        n, w = m.get("n30") or 0, m.get("w30") or 0
        m["wr"] = (w / n) if n else None
    _GATES_CACHE["data"] = out
    _GATES_CACHE["ts"] = now
    return out


def _gate_eval(m):
    """(all_pass, chips_html) for one bot's gate metrics."""
    n30 = m.get("n30") or 0
    wr = m.get("wr")
    dd = m.get("dd")
    age = m.get("age_days")
    def chip(ok, text):
        mark = "✓" if ok else "✗"
        colr = "#1a7f37" if ok else "#a3121b"
        return f'<span style="color:{colr};white-space:nowrap">{text} {mark}</span>'
    c1 = chip(n30 >= GATE_MIN_TRADES_30D, f"{n30}/{GATE_MIN_TRADES_30D} trades·30d")
    c2 = chip(wr is not None and wr >= GATE_MIN_WR,
              f"WR {wr * 100:.0f}%" if wr is not None else "WR —")
    c3 = chip(dd is not None and dd >= GATE_MAX_DD,
              f"dd {dd * 100:+.1f}%" if dd is not None else "dd —")
    c4 = chip(age is not None and age >= GATE_MIN_AGE_DAYS,
              f"age {age:.0f}/{GATE_MIN_AGE_DAYS}d" if age is not None else "age —")
    ok = (n30 >= GATE_MIN_TRADES_30D and wr is not None and wr >= GATE_MIN_WR
          and dd is not None and dd >= GATE_MAX_DD
          and age is not None and age >= GATE_MIN_AGE_DAYS)
    return ok, ("Go-live gates: " + " · ".join((c1, c2, c3, c4)))


def classify_stage(bot, gates):
    """'ready' | 'proving' | 'experiment' | 'control' | 'scanner' for one
    NON-live display bot. Live rows keep their own section."""
    base, _suf = venue_variant(bot)
    if bot in SCANNERS or base in SCANNERS:
        return "scanner"
    if base in EXPERIMENT_BASES:
        return "experiment"
    if base in CONTROL_BASES:
        return "control"
    ok, _chips = _gate_eval(gates.get(bot) or {})
    return "ready" if ok else "proving"


def _svg_chart(series, color, label, height=170, width=760, fmt=None):
    """series: list of (datetime, value) oldest-first. Returns an SVG line chart."""
    series = [(t, v) for t, v in series if v is not None]
    if len(series) < 2:
        return (f'<div class="sub">{label}</div>'
                '<div class="muted">Not enough history yet — the chart fills in as '
                'snapshots accrue (one every 5 min).</div>')
    vals = [v for _, v in series]
    lo, hi = min(vals), max(vals)
    if hi == lo:
        hi = lo + 1
    n = len(series)
    pts = " ".join(
        f"{(i/(n-1))*width:.1f},{height - (v-lo)/(hi-lo)*height:.1f}"
        for i, (_, v) in enumerate(series))
    last = vals[-1]
    fmt = fmt or money

    # [2026-07-18] interactive: hover a crosshair over the curve to read the
    # value + timestamp at that point. The handler (CHART_JS, delegated on
    # document so it survives live-morphs) reads the polyline's OWN points for
    # the shape and inverts THIS tiny scale — lo/hi map y->value, t0/t1 map
    # index->time. Only 5 numbers embedded per chart, not the whole series.
    def _epoch(t):
        try:
            return int(t.timestamp())
        except Exception:      # noqa: BLE001 — a bad stamp just disables time readout
            return 0
    t0, t1 = _epoch(series[0][0]), _epoch(series[-1][0])
    return (f'<div class="sub">{label} · now <b>{fmt(last)}</b> '
            f'<span class="muted">(min {fmt(lo)} / max {fmt(hi)}) · hover to inspect</span></div>'
            f'<div class="ic" style="position:relative;margin-bottom:8px">'
            f'<svg class="ichart" viewBox="0 0 {width} {height}" width="100%" height="{height}" '
            f'preserveAspectRatio="none" data-lo="{lo:.4f}" data-hi="{hi:.4f}" '
            f'data-h="{height}" data-t0="{t0}" data-t1="{t1}" '
            f'style="display:block;background:#0d1117;border:1px solid #222;'
            f'border-radius:8px;cursor:crosshair">'
            f'<polyline fill="none" stroke="{color}" stroke-width="2" points="{pts}"/></svg>'
            f'</div>')


def _max_drawdown_pct(vals):
    """[2026-07-15 SALVAGE] Worst peak-to-trough move as a % of the peak (a
    negative number), or None if the series is unusable (empty / peak <= 0)."""
    peak, dd, seen = None, 0.0, False
    for v in vals:
        if v is None:
            continue
        peak = v if peak is None else max(peak, v)
        if peak and peak > 0:
            dd = min(dd, v / peak - 1.0)
            seen = True
    return dd * 100.0 if seen else None


def render_history(hours=168):
    # [2026-07-15 SALVAGE] window selector: ?hours=<n> (default 168) or ?hours=all
    # — the review week reads this page; 7d-only made longer arcs invisible.
    try:
        hours = (None if str(hours).strip().lower() == "all"
                 else max(1, int(str(hours).strip())))
    except (TypeError, ValueError):
        hours = 168
    try:
        rows = fetch_history(hours=hours)  # None = all history
        db_err = None
    except Exception as e:  # noqa: BLE001
        rows, db_err = [], f"{type(e).__name__}: {e}"

    # [2026-07-15 OPERATING HUB] Cohorts match how the fleet is actually run
    # since the Lighter-first pivot: LIVE real money, Lighter shadow books,
    # remaining HL paper originals, scanners. Retired bots' trailing snapshots
    # are excluded so a row deletion doesn't paint a fake cliff, and the IBKR
    # $250k account can't dwarf the crypto curves.
    def _cohort(bot):
        if bot in RETIRED_ROWS:
            return None
        base, suf = venue_variant(bot)
        if bot not in CURRENT_BOTS and base not in CURRENT_BOTS:
            return None                      # legacy pre-rename rows
        if is_live_bot(bot):
            return "Live"
        if suf == "-lshadow":
            return "Shadow"
        if bot in SCANNERS:
            return "Scanner"
        return "Paper"

    ts_axis = sorted({ts for ts, _, _, _ in rows})
    # [2026-07-15 SALVAGE] "all" can be thousands of 5-min snapshots — thin the
    # time axis to <=500 points (always keeping the newest) so the SVGs stay
    # light. Windowed views under the cap pass through untouched.
    _MAXPTS = 500
    if len(ts_axis) > _MAXPTS:
        _step = -(-len(ts_axis) // _MAXPTS)  # ceil division
        _keep = set(ts_axis[::_step])
        _keep.add(ts_axis[-1])
        ts_axis = [t for t in ts_axis if t in _keep]
        rows = [r for r in rows if r[0] in _keep]
    GROUPS = ["Total", "Live", "Shadow", "Paper", "Scanner"]
    agg = {g: {ts: {"eq": 0.0, "pnl": 0.0} for ts in ts_axis} for g in GROUPS}
    for ts, bot, eq, pnl in rows:
        g = _cohort(bot)
        if g is None:
            continue
        for gg in (g, "Total"):
            if eq is not None:
                agg[gg][ts]["eq"] += eq
            if pnl is not None:
                agg[gg][ts]["pnl"] += pnl

    def series(group, key):
        return [(ts, agg[group][ts][key]) for ts in ts_axis]

    banner = ""
    if db_err:
        banner = f'<div class="banner">Database unreachable: {html.escape(db_err)}.</div>'
    elif not ts_axis:
        banner = ('<div class="banner">No history captured yet. The dashboard snapshots '
                  'every bot\'s equity every 5 minutes — check back shortly.</div>')

    # [2026-07-15 SALVAGE] max-drawdown caption per cohort, from the same
    # aggregated series the charts draw (Scanner books no equity -> P&L curve).
    def _dd_caption(group, key="eq"):
        ddv = _max_drawdown_pct([agg[group][ts][key] for ts in ts_axis]) if ts_axis else None
        return (f' <span class="muted" style="font-weight:400">· max DD {ddv:+.1f}%</span>'
                if ddv is not None else "")

    charts = (
        f'<h2 style="font-size:15px;margin:18px 4px 2px">Whole operation (active fleet){_dd_caption("Total")}</h2>'
        + _svg_chart(series("Total", "eq"), "#e6e6e6", "Total equity")
        + _svg_chart(series("Total", "pnl"), "#3fb950", "Total P&amp;L")
        + f'<h2 style="font-size:15px;margin:18px 4px 2px">🔴 Live — real money on Lighter{_dd_caption("Live")}</h2>'
        + _svg_chart(series("Live", "eq"), "#3fb950", "Live equity")
        + _svg_chart(series("Live", "pnl"), "#3fb950", "Live P&amp;L")
        + f'<h2 style="font-size:15px;margin:18px 4px 2px">Lighter shadow books (the fleet){_dd_caption("Shadow")}</h2>'
        + _svg_chart(series("Shadow", "eq"), "#58a6ff", "Shadow equity")
        + _svg_chart(series("Shadow", "pnl"), "#58a6ff", "Shadow P&amp;L")
        + f'<h2 style="font-size:15px;margin:18px 4px 2px">HL paper originals{_dd_caption("Paper")}</h2>'
        + _svg_chart(series("Paper", "eq"), "#d29922", "Paper equity")
        + _svg_chart(series("Paper", "pnl"), "#d29922", "Paper P&amp;L")
        + f'<h2 style="font-size:15px;margin:18px 4px 2px">Scanners{_dd_caption("Scanner", "pnl")}</h2>'
        + _svg_chart(series("Scanner", "pnl"), "#a371f7", "Scanner paper P&amp;L")
    )
    # [2026-07-15 SALVAGE] window selector (current window bold, not a link)
    _wlabel = ("all time" if hours is None
               else (f"{hours}h" if hours < 48 else f"last {hours // 24}d"))
    _cur = "all" if hours is None else str(hours)
    selector = " ".join(
        (f'<b style="color:#e6e6e6;font-size:14px">{lbl}</b>' if v == _cur
         else f'<a href="/history?hours={v}">{lbl}</a>')
        for v, lbl in (("24", "24h"), ("168", "7d"), ("720", "30d"), ("all", "all")))
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="60">
<title>All Bots — History</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}} a{{color:#58a6ff;text-decoration:none;font-size:14px}}
 .wrap{{padding:14px}}
 .sub{{margin:14px 4px 6px;font-size:14px;color:#c9d1d9;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px}}
 .banner{{margin:12px 4px;padding:10px 12px;background:#3d2b12;border:1px solid #6b4a16;border-radius:8px;color:#f0c674;font-size:13px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>All Bots — history ({_wlabel}) &nbsp;·&nbsp; {selector} &nbsp;·&nbsp; <a href="/">← live</a> &nbsp; <a href="/periods">periods</a> &nbsp; <a href="/market">market</a> &nbsp; <a href="/learning">learning</a></h1></header>
<div class="wrap">{banner}{charts}</div>
<footer>Equity/P&amp;L sampled every 5 min from the shared bot_pnl table ({_wlabel};
charts thinned to &le;500 points). Retired bots are excluded so row prunes don't
paint fake cliffs. Live = real-money Lighter accounts; Shadow = modelled fills on
live Lighter books; Paper = HL-data originals. Auto-refreshes every 60s. Times UTC.</footer>
</body></html>'''


def _slice_table(title, sl):
    if not sl:
        return ""
    # show the few best and worst rows by total_ratio
    items = list(sl.items())
    rowshtml = []
    for k, v in items:
        rowshtml.append(
            f'<tr><td>{html.escape(str(k))}</td><td>{v.get("n")}</td>'
            f'<td>{float(v.get("win_rate",0))*100:.0f}%</td>'
            f'<td class="{cls(v.get("total_ratio"))}">{float(v.get("total_ratio",0))*100:+.2f}%</td></tr>')
    return (f'<div class="sub">{html.escape(title)}</div>'
            f'<table class="tbl"><tr><th>bucket</th><th>n</th><th>win</th><th>total</th></tr>'
            f'{"".join(rowshtml)}</table>')


def learning_card(strategy, rec):
    a = rec.get("analysis") or {}
    age, stale = age_str(rec.get("updated_at"))
    bots = ", ".join(a.get("bots", []))
    if not a or a.get("n", 0) == 0:
        return (f'<div class="card"><h2>{html.escape(strategy)}</h2>'
                f'<div class="muted">{html.escape(bots)} · updated {html.escape(age)}</div>'
                f'<div class="muted" style="margin-top:8px">No closed trades analysed yet — '
                f'history accrues as the bots trade (4h strategies are slow).</div></div>')
    pf = a.get("profit_factor")
    pf_s = "∞" if pf in (None, float("inf")) else f'{pf}'
    headline = (
        f'<div class="row"><span>Trades</span><b>{a.get("n")}</b></div>'
        f'<div class="row"><span>Win rate</span><b>{float(a.get("win_rate",0))*100:.0f}%</b></div>'
        f'<div class="row"><span>Expectancy / trade</span>'
        f'<b class="{cls(a.get("expectancy"))}">{float(a.get("expectancy",0))*100:+.2f}%</b></div>'
        f'<div class="row"><span>Profit factor</span><b>{pf_s}</b></div>'
        f'<div class="row"><span>Total return</span>'
        f'<b class="{cls(a.get("total_return_ratio"))}">{float(a.get("total_return_ratio",0))*100:+.2f}%</b></div>'
        f'<div class="row"><span>Best / worst</span>'
        f'<b>{float(a.get("best",0))*100:+.1f}% / {float(a.get("worst",0))*100:+.1f}%</b></div>'
    )
    recs = "".join(f'<li>{html.escape(r)}</li>' for r in a.get("recommendations", []))
    recs_html = f'<div class="sub">What it learned</div><ul class="recs">{recs}</ul>' if recs else ""
    return f'''<div class="card">
      <h2>{html.escape(strategy)}</h2>
      <div class="muted">{html.escape(bots)} · updated {html.escape(age)}{" · STALE" if stale else ""}</div>
      {headline}
      {recs_html}
      {_slice_table("By exit reason", a.get("by_exit_reason"))}
      {_slice_table("By pair", a.get("by_pair"))}
    </div>'''


def render_learning():
    try:
        data = fetch_analysis()
        db_err = None
    except Exception as e:
        data, db_err = {}, f"{type(e).__name__}: {e}"
    banner = ""
    if db_err:
        banner = f'<div class="banner">Database unreachable: {html.escape(db_err)}.</div>'
    elif not data:
        banner = ('<div class="banner">No analysis yet. The trainer writes this once a day '
                  'after the bots have closed some trades.</div>')
    # [2026-07-15 OPERATING HUB] The tab now shows the whole learning LOOP, not
    # just the daily strategy post-mortems: the brain's venue A/B + throttles +
    # diagnoses, and the Ticket Taker's per-lens scoreboard (the scanner→bot→
    # brain pipeline's output). Strategy cards follow below.
    loop_cards = brain_panel_html() + taker_lens_card()
    cards = "".join(learning_card(s, r) for s, r in data.items())
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Crypto Bots — Learning</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0 0 6px;font-size:18px}}
 a{{color:#58a6ff;text-decoration:none;font-size:13px}}
 .banner{{margin:12px 14px 0;padding:10px 12px;background:#3d2b12;border:1px solid #6b4a16;border-radius:8px;color:#f0c674;font-size:13px}}
 .banner.crit{{background:#3d1218;border-color:#6b1620;color:#f85149;font-weight:600}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(330px,1fr));gap:14px;padding:14px}}
 .card{{background:#161b22;border:1px solid #222;border-radius:10px;padding:14px}}
 .card h2{{margin:0 0 2px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:12px 0 4px;font-size:12px;color:#8b949e;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 ul.recs{{margin:4px 0 0;padding-left:18px}} ul.recs li{{font-size:12px;margin:4px 0;color:#cdd9e5}}
 table.tbl{{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 2px}}
 table.tbl th,table.tbl td{{text-align:left;padding:3px 6px;border-bottom:1px solid #21262d}}
 table.tbl th{{color:#8b949e;font-weight:600}}
 .n{{color:#6e7681;font-size:11px}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header>
 <h1>Fleet — what it's learning</h1>
 <a href="/">← live</a> &nbsp; <a href="/history">history</a> &nbsp; <a href="/periods">periods</a> &nbsp; <a href="/market">market</a>
</header>
{banner}
<div class="grid">{loop_cards}</div>
<div class="grid" style="padding-top:0">{cards}</div>
<footer>Top row: the live learning loop — brain venue A/B + two-way stake multipliers +
loss diagnoses (bot_learn, ~2h cadence) and the Ticket Taker lens scoreboard (durable
paper_trades ledger). Below: per-strategy post-mortems written daily by the trainer.
Auto-applied, all evidence-gated: OOS-validated tuning, two-way stake multipliers
(reduce 0.5x/0.75x, earn 1.25x/1.5x on the v3 mirror bars), and ACTIONABLE
regime-timing gates (restrict-only). Everything else is human-review.
Auto-refreshes every 2 min. Times UTC.</footer>
</body></html>'''


TRADING_BOTS_ORDER = ["crypto-trend-daily", "crypto-intraday-15m",
                      "crypto-swing-daily", "crypto-breakout-4h", "crypto-trendmomo-4h"]


def fetch_period_pnl(period, limit_periods):
    """Realized P&L per calendar {period} from BOTH durable ledgers:
    bot_trades (freqtrade poller era) UNION paper_trades (the Lighter fleet —
    every -lshadow/-lighter book books its closes there). Without the union the
    tab silently showed only the retired Kraken arm. period is
    'day'|'week'|'month'. Returns (periods_newest_first, ordered_bots,
    grid[(period,bot)] -> {pnl,n}). Scanners excluded. Raises on DB error."""
    import psycopg2
    conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT to_regclass('public.bot_trades') AS bt, "
                        "to_regclass('public.paper_trades') AS pt")
            has_bt, has_pt = cur.fetchone()
            parts = []
            if has_bt:
                parts.append("SELECT bot, close_ts, profit_abs FROM bot_trades "
                             "WHERE is_open IS NOT TRUE AND close_ts IS NOT NULL")
            if has_pt:
                # closed_at is TEXT (iso strings from the venue layer) — cast,
                # guarded by a real cast-validity check (PG16+) so one
                # malformed row can't 500 the tab ([2026-07-15 AUDIT FIX]: the
                # old prefix regex passed date-like garbage into the cast).
                parts.append("SELECT bot, closed_at::timestamptz AS close_ts, "
                             "pnl_abs AS profit_abs FROM paper_trades "
                             "WHERE closed_at IS NOT NULL "
                             "AND pg_input_is_valid(closed_at, 'timestamptz') "
                             # [2026-07-15 EVIDENCE] sniper gate-log rows are
                             # not trades — keep them out of P&L periods.
                             "AND side IS DISTINCT FROM 'skip'")
            if not parts:
                return [], [], {}
            cur.execute(
                f"""
                SELECT date_trunc(%s, close_ts) AS p, bot,
                       COALESCE(SUM(profit_abs), 0), COUNT(*)
                FROM ({" UNION ALL ".join(parts)}) t
                GROUP BY 1, 2
                ORDER BY 1 DESC
                """,
                (period,),
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    grid, periods, bots = {}, [], set()
    for p, bot, pnl, n in rows:
        base, _suf = venue_variant(bot)
        if (bot not in CURRENT_BOTS and base not in CURRENT_BOTS) \
                or bot in SCANNERS or bot in RETIRED_ROWS:
            continue
        key = p.date().isoformat()
        if key not in periods:
            periods.append(key)
        grid[(key, bot)] = {"pnl": float(pnl), "n": int(n)}
        bots.add(bot)
    periods = periods[:limit_periods]

    # Live money first, then the Lighter shadow fleet, then remaining paper.
    def _rank(b):
        if is_live_bot(b):
            return (0, b)
        if b.endswith("-lshadow"):
            return (1, b)
        return (2, b)
    ordered = sorted(bots, key=_rank)
    return periods, ordered, grid


def periods_payload():
    """Structured daily/weekly/monthly realized P&L for /periods.json."""
    out = {}
    for label, period, n in (("daily", "day", 31), ("weekly", "week", 13),
                             ("monthly", "month", 13)):
        periods, bots, grid = fetch_period_pnl(period, n)
        out[label] = [
            {"period": key,
             "total": round(sum(grid[(key, b)]["pnl"] for b in bots
                                if (key, b) in grid), 2),
             "trades": sum(grid[(key, b)]["n"] for b in bots if (key, b) in grid),
             "by_bot": {b: round(grid[(key, b)]["pnl"], 2) for b in bots
                        if (key, b) in grid}}
            for key in periods]
    return out


def _period_table(title, period, n):
    try:
        periods, bots, grid = fetch_period_pnl(period, n)
    except Exception as e:
        return (f'<div class="sub">{html.escape(title)}</div>'
                f'<div class="muted">unavailable: {html.escape(str(e))}</div>')
    if not periods:
        return (f'<div class="sub">{html.escape(title)}</div>'
                f'<div class="muted">no closed paper trades yet — check back as the bots trade</div>')
    head = "".join(f"<th>{html.escape(b.replace('-', ' '))}</th>" for b in bots)
    body = []
    for key in periods:
        cells, row_total = [], 0.0
        for b in bots:
            c = grid.get((key, b))
            if c:
                row_total += c["pnl"]
                cells.append(f'<td class="{cls(c["pnl"])}">{money(c["pnl"])}'
                             f'<span class="n"> ({c["n"]})</span></td>')
            else:
                cells.append('<td class="muted">—</td>')
        body.append(f'<tr><td class="pk">{html.escape(key)}</td>{"".join(cells)}'
                    f'<td class="{cls(row_total)}"><b>{money(row_total)}</b></td></tr>')
    return (f'<div class="sub">{html.escape(title)}</div>'
            f'<table class="pt"><tr><th>Period</th>{head}<th>Total</th></tr>'
            f'{"".join(body)}</table>')


def render_periods():
    daily = _period_table("Daily — last 14 days", "day", 14)
    weekly = _period_table("Weekly — last 8 weeks (week starts Mon)", "week", 8)
    monthly = _period_table("Monthly — last 6 months", "month", 6)
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="120">
<title>Crypto Bots — P&amp;L by period</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}}
 a{{color:#58a6ff;text-decoration:none}}
 .wrap{{padding:14px}}
 .sub{{margin:18px 4px 6px;font-size:14px;color:#c9d1d9;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px;margin:0 4px}}
 table.pt{{width:100%;border-collapse:collapse;font-size:12px;background:#161b22;
   border:1px solid #222;border-radius:8px;overflow:hidden}}
 table.pt th,table.pt td{{padding:7px 9px;text-align:right;border-bottom:1px solid #21262d;white-space:nowrap}}
 table.pt th{{background:#1b2230;color:#8b949e;font-weight:600;text-align:right}}
 table.pt td.pk,table.pt th:first-child{{text-align:left;color:#c9d1d9}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 .n{{color:#6e7681;font-size:11px}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>Fleet — P&amp;L by period &nbsp;·&nbsp;
 <a href="/">← live</a> &nbsp; <a href="/history">history</a> &nbsp; <a href="/market">market</a> &nbsp; <a href="/learning">learning →</a></h1></header>
<div class="wrap">{daily}{weekly}{monthly}</div>
<footer>Realized P&amp;L from BOTH durable ledgers (bot_trades + paper_trades — the whole
fleet incl. every Lighter book; -lighter columns are REAL money). Columns ordered live →
shadow → paper. Cells show P&amp;L and (trade count). Times UTC. Auto-refreshes every 120s.</footer>
</body></html>'''


_MKT_CACHE = {"md": None, "ts": 0.0}


def market_md_cached(ttl=1800):
    """Live market-regime snapshot (Fear&Greed, dominance, breadth, per-coin trend),
    cached ~30 min so page loads don't hammer the source APIs."""
    import time as _t
    now = _t.time()
    if _MKT_CACHE["md"] is None or now - _MKT_CACHE["ts"] > ttl:
        try:
            import compile_market_data as _cmd
            _MKT_CACHE["md"] = _cmd.snapshot_markdown()
            _MKT_CACHE["ts"] = now
        except Exception as e:
            if _MKT_CACHE["md"] is None:
                return f"Market snapshot unavailable: {type(e).__name__}: {e}"
    return _MKT_CACHE["md"]


def _ticket_rows(tickets, lens, n=3):
    """[2026-07-15 AUDIT FIX] Divergence tickets carry their OWN schema
    (side/gap_pct/lighter_apr/xvenue_apr — no chg_pct/apr_pct), and any lens
    can carry apr_pct=None (book absent from the funding feed) — the old
    single-shape render printed fabricated zeros and a None crashed the tab."""
    out = []
    for t in (tickets.get(lens) or [])[:n]:
        sym = html.escape(str(t.get("sym", "?")))
        if lens == "divergence":
            out.append(
                f'<tr><td>{sym} <span class="muted">'
                f'{html.escape(str(t.get("side", "")))}</span></td>'
                f'<td class="{cls(t.get("gap_pct"))}">{(t.get("gap_pct") or 0):+.0f}pp</td>'
                f'<td>{(t.get("lighter_apr") or 0):+.0f}%→{(t.get("xvenue_apr") or 0):+.0f}%</td>'
                f'<td>{(t.get("prem_bps") or 0):.1f}</td>'
                f'<td>${(t.get("vol_m") or 0):.1f}M</td></tr>')
        else:
            apr = t.get("apr_pct")
            out.append(
                f'<tr><td>{sym}</td>'
                f'<td class="{cls(t.get("chg_pct"))}">{(t.get("chg_pct") or 0):+.1f}%</td>'
                f'<td>{"—" if apr is None else f"{apr:+.0f}%"}</td>'
                f'<td>{(t.get("prem_bps") or 0):.1f}</td>'
                f'<td>${(t.get("vol_m") or 0):.1f}M</td></tr>')
    return "".join(out)


def render_market():
    """[2026-07-15 OPERATING HUB] The market tab is now the fleet's OWN market
    intelligence first (scout venue map, regime oracle, mood history, vetoes),
    with the external Binance/CoinGecko snapshot demoted to a details block."""
    st = fetch_states(["lighter-market", "regime-oracle", "market-pulse", "coin-vetoes"])
    lm = st.get("lighter-market") or {}
    ro = st.get("regime-oracle") or {}
    mp = st.get("market-pulse") or {}
    cv = (st.get("coin-vetoes") or {}).get("coins") or {}

    # --- Lighter venue map (the scout) -------------------------------------
    if lm:
        stress = lm.get("stress") or {}
        med = stress.get("med", 0) or 0
        scol = "#f85149" if med >= 15 else ("#d29922" if med >= 10 else "#3fb950")
        tickets = lm.get("tickets") or {}
        lens_tbls = []
        for lens_name in ("breakout", "dip", "momentum", "divergence"):
            rows_html = _ticket_rows(tickets, lens_name)
            n_all = len(tickets.get(lens_name) or [])
            hdr = ('<th>sym/side</th><th>gap</th><th>Lighter→x-venue</th>'
                   if lens_name == "divergence"
                   else '<th>sym</th><th>24h</th><th>funding</th>')
            if rows_html:
                lens_tbls.append(
                    f'<div class="sub">{lens_name} tickets ({n_all})</div>'
                    f'<table class="tbl"><tr>{hdr}'
                    f'<th>prem bps</th><th>vol</th></tr>{rows_html}</table>')
            else:
                lens_tbls.append(f'<div class="sub">{lens_name} tickets</div>'
                                 f'<div class="muted">none this cycle</div>')
        fx = "".join(
            f'<tr><td>{html.escape(str(e.get("sym", "?")))}</td>'
            f'<td class="{cls(e.get("apr_pct"))}">{e.get("apr_pct", 0):+.0f}%</td>'
            f'<td>${e.get("vol_m", 0):.1f}M</td></tr>'
            for e in (lm.get("funding_extremes") or [])[:6])
        dv = "".join(
            f'<tr><td>{html.escape(str(d.get("sym", "?")))}</td>'
            f'<td>{d.get("gap_pct", 0):+.0f}pp</td>'
            f'<td>{d.get("lighter_apr", 0):+.0f}%</td>'
            f'<td>{d.get("xvenue_apr", 0):+.0f}%</td></tr>'
            for d in (lm.get("funding_divergence") or [])[:6])
        listings = ", ".join(str(x) for x in (lm.get("new_listings") or [])) or "none"
        scout_card = f'''<div class="card">
  <h2>🛰️ Lighter venue map <span class="muted">— {lm.get("n_liquid", "?")} liquid /
  {lm.get("n_books", "?")} books</span></h2>
  <div class="row"><span>Venue stress (|premium|)</span>
    <b style="color:{scol}">{med}bps med · p90 {stress.get("p90", "?")} · max {stress.get("max", "?")}</b></div>
  <div class="row"><span>New listings this cycle</span><b>{html.escape(listings)}</b></div>
  {"".join(lens_tbls)}
  <div class="sub">Funding extremes (APR)</div>
  <table class="tbl"><tr><th>sym</th><th>APR</th><th>vol</th></tr>{fx}</table>
  <div class="sub">Cross-venue funding divergence (Lighter vs binance/bybit/HL median)</div>
  <table class="tbl"><tr><th>sym</th><th>gap</th><th>Lighter</th><th>x-venue</th></tr>{dv}</table>
</div>'''
    else:
        scout_card = ('<div class="card"><h2>🛰️ Lighter venue map</h2>'
                      '<div class="muted">scout state unreachable</div></div>')

    # --- Regime oracle ------------------------------------------------------
    if ro:
        fleet = ro.get("fleet") or {}
        pairs = ro.get("pairs") or {}
        # [2026-07-22 (bs) receipt] the oracle's SELF-GRADE, per asset —
        # never pooled across pairs (a blended hit rate across BTC and SPY
        # is the exact class-mixing item 18 removed). Payloads predating
        # the grader render exactly as before.
        grades = ro.get("grades") or {}

        def _d1(sym):
            g = grades.get(sym)
            g = g.get("d1") if isinstance(g, dict) else None
            if not isinstance(g, dict) or not g.get("n"):
                return "—"
            return (f'{(g.get("hit") or 0) * 100:.0f}% · '
                    f'{(g.get("avg_pp") or 0):+.1f}pp (n{g["n"]})')
        prow = "".join(
            f'<tr><td>{html.escape(c)}</td>'
            f'<td>{html.escape(str((p or {}).get("verdict", "?")))}</td>'
            f'<td>{(p or {}).get("adx", 0):.0f}</td>'
            f'<td>{html.escape(_d1(c))}</td></tr>'
            for c, p in sorted(pairs.items()))
        n_g = sum(1 for g in grades.values()
                  if isinstance(g, dict) and (g.get("d1") or {}).get("n"))
        n_pend = len((ro.get("grading") or {}).get("pending") or [])
        grade_line = ((f'<div class="muted">self-grade: d1 outcomes on '
                       f'{n_g}/{len(pairs)} pairs · {n_pend} calls pending '
                       f'(hit/avg-pp are per-asset, signed into the call)</div>')
                      if (n_g or n_pend) else "")
        oracle_card = f'''<div class="card">
  <h2>🧭 Regime oracle <span class="muted">— {html.escape(str(fleet.get("read", "?")))}</span></h2>
  <div class="row"><span>Windows</span><b>{fleet.get("n_long", 0)} long ·
    {fleet.get("n_short", 0)} short · {fleet.get("n_flat_or_chop", 0)} flat/chop</b></div>
  {grade_line}
  <table class="tbl"><tr><th>coin</th><th>window</th><th>ADX</th><th>d1 self-grade</th></tr>{prow}</table>
</div>'''
    else:
        oracle_card = ('<div class="card"><h2>🧭 Regime oracle</h2>'
                       '<div class="muted">oracle state unreachable</div></div>')

    # --- Mood history + vetoes ----------------------------------------------
    hist = mp.get("history") or []
    mood_pts = [(_iso_dt(h.get("ts")), h.get("mood")) for h in hist]
    mood_pts = [(t, v) for t, v in mood_pts if t is not None]
    fng_pts = [(_iso_dt(h.get("ts")), h.get("fng")) for h in hist]
    fng_pts = [(t, v) for t, v in fng_pts if t is not None]
    charts = ""
    if mood_pts:
        charts = (_svg_chart(mood_pts, "#58a6ff", "Fleet mood (news/social/funding)",
                             height=120, fmt=lambda v: f"{v:+.2f}")
                  + _svg_chart(fng_pts, "#d29922", "Fear &amp; Greed",
                               height=120, fmt=lambda v: f"{v:.0f}"))
    vet = "".join(f'<div class="row"><span>{html.escape(k)}</span>'
                  f'<b class="neg">{html.escape(str(v))}</b></div>'
                  for k, v in sorted(cv.items())) or '<div class="muted">none</div>'
    pulse_card = f'''<div class="card"><h2>🌡️ Mood — last ~8 days (hourly)</h2>{charts}
  <div class="sub">Coin vetoes (execution evidence — restrict-only)</div>{vet}</div>'''

    md = market_md_cached()
    return f'''<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta http-equiv="refresh" content="300">
<title>Fleet — market &amp; venue intel</title>
<style>
 body{{font-family:-apple-system,system-ui,sans-serif;margin:0;background:#0e1117;color:#e6e6e6}}
 header{{padding:16px 18px;background:#161b22;border-bottom:1px solid #222}}
 h1{{margin:0;font-size:18px}} a{{color:#58a6ff;text-decoration:none}}
 .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(340px,1fr));gap:14px;padding:14px}}
 .card{{background:#161b22;border:1px solid #222;border-radius:10px;padding:14px}}
 .card h2{{margin:0 0 6px;font-size:15px}}
 .row{{display:flex;justify-content:space-between;margin:5px 0;font-size:13px}}
 .sub{{margin:12px 0 4px;font-size:12px;color:#8b949e;font-weight:600}}
 .muted{{color:#8b949e;font-size:12px}}
 .pos{{color:#3fb950}} .neg{{color:#f85149}}
 table.tbl{{width:100%;border-collapse:collapse;font-size:12px;margin:4px 0 2px}}
 table.tbl th,table.tbl td{{text-align:left;padding:3px 6px;border-bottom:1px solid #21262d}}
 table.tbl th{{color:#8b949e;font-weight:600}}
 details{{margin:0 14px 14px}} details pre{{padding:14px;background:#161b22;border:1px solid #222;
   border-radius:10px;font-size:12.5px;line-height:1.5;white-space:pre-wrap;overflow-x:auto}}
 details summary{{cursor:pointer;color:#8b949e;font-size:13px;padding:4px 0}}
 footer{{padding:10px 18px;color:#8b949e;font-size:11px}}
</style></head><body>
<header><h1>Fleet — market &amp; venue intel &nbsp;·&nbsp;
 <a href="/">← live</a> &nbsp; <a href="/history">history</a> &nbsp; <a href="/periods">periods</a> &nbsp; <a href="/learning">learning</a></h1></header>
<div class="grid">{scout_card}{oracle_card}{pulse_card}</div>
<details><summary>External market snapshot (Binance / Fear&amp;Greed / CoinGecko — cached ~30 min)</summary>
<pre>{html.escape(md)}</pre></details>
<footer>Scout maps every Lighter book each ~5 min (premium stress, funding extremes,
cross-venue divergence, per-lens tickets — the Ticket Taker trades the high-conviction
subset). Oracle windows gate the perps books. Vetoes come from measured slippage/stops,
restrict-only. Auto-refreshes every 5 min. Times UTC. Not financial advice.</footer>
</body></html>'''


class H(BaseHTTPRequestHandler):
    def _auth_ok(self):
        if not DASH_PASS:            # no secret configured -> deny everyone
            return False
        hdr = self.headers.get("Authorization", "")
        if not hdr.startswith("Basic "):
            return False
        try:
            u, p = base64.b64decode(hdr[6:]).decode().split(":", 1)
        except Exception:
            return False
        # constant-time compare on the password (the secret); username plain
        return u == DASH_USER and hmac.compare_digest(p, DASH_PASS)

    def _no_cache(self):
        """Forbid any browser/proxy caching. The snapshot is regenerated on every
        request (generated_at = now()), so a cached copy reads as a FROZEN feed:
        a stale JSON gets served with a day-old generated_at and every delta is
        $0.00, which is indistinguishable from genuine zero activity. Railway's
        edge and browsers may cache a 200 with no cache directives, so be explicit
        on every response."""
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")

    def _send_ok(self, body, ctype):
        """[2026-08-04 (iy)] One 200 send path with gzip. Measured before this:
        /bus.json was 8.2 MB and the main page 584 KB, both served UNCOMPRESSED
        even to clients offering gzip — and the live station refetches the full
        page every ~10-20s per open tab, so the waste compounds into MB/min of
        phone data. Compress only when the client asks and it actually pays;
        no-cache semantics unchanged."""
        enc = None
        if "gzip" in (self.headers.get("Accept-Encoding") or "").lower() \
                and len(body) > 1024:
            import gzip as _gz
            gz = _gz.compress(body, 6)
            if len(gz) < len(body):
                body, enc = gz, "gzip"
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self._no_cache()
        if enc:
            self.send_header("Content-Encoding", enc)
            self.send_header("Vary", "Accept-Encoding")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path.startswith("/health"):
            self.send_response(200); self._no_cache(); self.end_headers(); self.wfile.write(b"ok"); return
        if self.path.startswith("/tick.json"):
            # [2026-07-18] the live-station change signal — cheap, no auth (no
            # secrets: it is a single timestamp). The page polls this to decide
            # whether to re-fetch; keeping it public + tiny is the whole point.
            body = json.dumps(fetch_tick()).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body); return
        if self.path.startswith("/watchdog.json"):
            # [2026-07-13 BRANCH MERGE] In-service fleet watchdog state
            # (fleet_watchdog_svc daemon thread) — ported from the main-branch
            # dashboard fork so the two variants serve the same surface.
            # Read-only, no auth — no secrets inside.
            try:
                import fleet_watchdog_svc
                body = json.dumps(fleet_watchdog_svc.get_state(), default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/vitals.json"):
            # [2026-07-15 VITALS] whole-operation health: organ freshness vs
            # ttl, consumption matrix, 24h flow counts, watchdog state.
            # Read-only, no auth — no secrets (same contract as /watchdog.json).
            # The in-service watchdog polls this for ORGAN DARK detection.
            try:
                body = json.dumps(vitals_payload(), default=str).encode()
            except Exception as e:  # noqa: BLE001
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/pulse.json"):
            # Market pulse (news/social/funding mood) written by market_pulse.py
            # into bot_state. Read-only, no auth — no secrets inside. Serves the
            # laptop brain/scans and anything else that wants the mood feed.
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT to_regclass('public.bot_state') AS t")
                        if cur.fetchone()[0] is None:
                            raise LookupError("bot_state table not created yet")
                        cur.execute("SELECT state, updated_at FROM bot_state WHERE bot = 'market-pulse'")
                        row = cur.fetchone()
                finally:
                    conn.close()
                if not row:
                    payload = {"error": "no pulse published yet"}
                else:
                    st = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    payload = {"updated_at": row[1].isoformat() if row[1] else None}
                    payload.update(st)
                body = json.dumps(payload, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/bus.json"):
            # [2026-07-14 review] Cross-bot advisory surface: the live
            # fleet-risk + signal-bus states AND their recent
            # bot_state_history snapshots. The Jul-14 review had to
            # reconstruct the advisory week from the trades ledger because
            # these were unreachable off-Railway; this endpoint is the fix so
            # the Jul-21 review reads evidence directly. Read-only, no auth —
            # no secrets inside (same contract as /pulse.json).
            # Query params: ?hours=<lookback for history, default 24, max 200;
            # 0 = live keys only, no history>. [2026-08-04 (iy)] hours=0 added:
            # the old clamp floored at 1.0, so history could not be turned OFF
            # and every consumer of the live keys paid ~8 MB (97% of the
            # payload is history; lighter-market alone ~4.7 MB). The default
            # stays 24 — existing history consumers see no change.
            q = parse_qs(urlparse(self.path).query)
            try:
                hours = min(max(float(q.get("hours", ["24"])[0]), 0.0), 200.0)
            except (ValueError, TypeError):
                hours = 24.0
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT to_regclass('public.bot_state') AS t")
                        if cur.fetchone()[0] is None:
                            raise LookupError("bot_state table not created yet")
                        # [2026-07-14] brain keys added: the brain died silently
                        # for two days once (5-7 Jul) because nothing external
                        # could see it. Its outputs are now on the same surface.
                        # [2026-07-16] fleet-proprioception added: consumer
                        # support — the outcome verdicts must be reachable
                        # off-Railway (gate0 services, the review, ad-hoc
                        # consumers) exactly like the brain keys are.
                        # [2026-07-21] parliament keys added: Howard's vitals
                        # (books/ML/tuners/health) + active tuner levers must
                        # be reachable off-Railway like every other organ —
                        # "verify a module by its OWN published output".
                        # [2026-07-21 D4 unblock] impl-shortfall added: the
                        # order_slip block (per-fill decision-vs-fill bps from
                        # venue_orders) is THE deciding number for the 28-Jul
                        # Funding Farmer call, and it had no no-auth surface —
                        # DB/dashboard-login gated from every review seat.
                        # xp-judge + scout-tuner added on the same rule: the
                        # promotion pipeline's phase and the growth rail's
                        # active levers were only inferable, not readable.
                        # [2026-07-21] tuning-proposals added: the organs'
                        # proposal channel to the tuners must be visible on
                        # the same surface its enactments are.
                        # [2026-07-28 AUDIT FIX] serve list widened: a dozen
                        # organ keys were unverifiable off-Railway (notably
                        # regime-oracle — whose .grades the weekly item-18
                        # re-read depends on — plus board/sentinel/immune/
                        # tuning/queue/incubator/radar/respiration/clock/
                        # regen/brain-vitals). Observable-only; these
                        # payloads carry no secrets (the endpoint's standing
                        # no-auth contract).
                        cur.execute(
                            "SELECT bot, state, updated_at FROM bot_state "
                            "WHERE bot IN ('fleet-risk', 'signal-bus', "
                            "'learning-brain', 'brain-stake-mults', "
                            "'brain-diagnosis', 'brain-lens-forward', "
                            "'lighter-market', 'fleet-proprioception', "
                            "'parliament', 'parliament-tuning', "
                            "'impl-shortfall', 'xp-judge', 'scout-tuner', "
                            "'tuning-proposals', 'regime-oracle', "
                            "'evidence-board', 'event-sentinel', "
                            "'fleet-immune', 'fleet-tuning', 'xp-queue', "
                            "'strategy-incubator', 'fleet-radar', "
                            # [2026-07-30] the go-live grader's verdicts must be
                            # readable from a review seat with no Railway
                            # login — it is the bar that governs real money.
                            "'golive-readiness', "
                            # [2026-08-04 (iy)] the allocation organ was
                            # publishing healthy 30-min payloads that NO
                            # review surface served — the (hw) wrong-surface
                            # class. Its claims table is I16's instrument.
                            "'fleet-allocation', "
                            "'fleet-respiration', 'fleet-clock', "
                            "'fleet-regen', 'brain-vitals')")
                        live = {}
                        for b, s, u in cur.fetchall():
                            st = s if isinstance(s, dict) else json.loads(s)
                            live[b] = {"updated_at": u.isoformat() if u else None,
                                       **st}
                        cur.execute(
                            "SELECT to_regclass('public.bot_state_history') AS t")
                        hist = []
                        if hours > 0 and cur.fetchone()[0] is not None:
                            cur.execute(
                                "SELECT key, ts, payload FROM bot_state_history "
                                "WHERE key IN ('fleet-risk', 'signal-bus', "
                                "'brain-stake-mults', 'brain-diagnosis', "
                                "'brain-lens-forward', 'lighter-market', "
                                "'fleet-proprioception', 'parliament', "
                                "'impl-shortfall', 'xp-judge', 'scout-tuner', "
                                "'regime-oracle', 'evidence-board', "
                                "'event-sentinel', 'fleet-immune', "
                                "'fleet-radar', 'fleet-respiration', "
                                "'golive-readiness', "
                                "'brain-vitals') "
                                "AND ts > now() - %s * interval '1 hour' "
                                "ORDER BY ts", (hours,))
                            hist = [{"key": k,
                                     "ts": t.isoformat() if t else None,
                                     "payload": (p if isinstance(p, dict)
                                                 else json.loads(p))}
                                    for k, t, p in cur.fetchall()]
                finally:
                    conn.close()
                lm = live.get("lighter-market") or {}
                lm.pop("_marks", None)   # internal diff base, not for consumers
                body = json.dumps({"fleet_risk": live.get("fleet-risk"),
                                   "signal_bus": live.get("signal-bus"),
                                   "brain": live.get("learning-brain"),
                                   "brain_stake_mults": live.get("brain-stake-mults"),
                                   "brain_diagnosis": live.get("brain-diagnosis"),
                                   "brain_lens_forward": live.get("brain-lens-forward"),
                                   "lighter_market": lm or None,
                                   "proprioception": live.get("fleet-proprioception"),
                                   "parliament": live.get("parliament"),
                                   "parliament_tuning": live.get("parliament-tuning"),
                                   "impl_shortfall": live.get("impl-shortfall"),
                                   "xp_judge": live.get("xp-judge"),
                                   "scout_tuner": live.get("scout-tuner"),
                                   "tuning_proposals": live.get("tuning-proposals"),
                                   "regime_oracle": live.get("regime-oracle"),
                                   "evidence_board": live.get("evidence-board"),
                                   "event_sentinel": live.get("event-sentinel"),
                                   "fleet_immune": live.get("fleet-immune"),
                                   "fleet_tuning": live.get("fleet-tuning"),
                                   "xp_queue": live.get("xp-queue"),
                                   "strategy_incubator": live.get("strategy-incubator"),
                                   "fleet_radar": live.get("fleet-radar"),
                                   "golive_readiness": live.get("golive-readiness"),
                                   "fleet_allocation": live.get("fleet-allocation"),
                                   "fleet_respiration": live.get("fleet-respiration"),
                                   "fleet_clock": live.get("fleet-clock"),
                                   "fleet_regen": live.get("fleet-regen"),
                                   "brain_vitals": live.get("brain-vitals"),
                                   "history_hours": hours,
                                   "history": hist}, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            # [2026-08-04 (iy)] gzip-capable send: this is the fleet's heaviest
            # endpoint (8.2 MB measured uncompressed at the 24h default).
            self._send_ok(body, "application/json")
            return
        if self.path.startswith("/disloc.json"):
            # [2026-07-14] Snap Back's dislocation CENSUS — the evidence the
            # bot exists to collect (per-coin count / max_bps / last seen of
            # every >=50bps Lighter-vs-HL print). Read-only, no auth: only the
            # census + counters are exposed, never the broker/position blob.
            # Serves the census reviews the bot's alerts keep asking for.
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT bot, state, updated_at FROM bot_state "
                            "WHERE bot IN ('lighter-dislocation-lshadow', "
                            "'lighter-dislocation-lighter', 'lighter-dislocation')")
                        rows_ = cur.fetchall()
                finally:
                    conn.close()
                payload = {"books": {}}
                for b, st, u in rows_:
                    st = st if isinstance(st, dict) else json.loads(st)
                    census = st.get("census") or {}
                    payload["books"][b] = {
                        "updated_at": u.isoformat() if u else None,
                        "census_events": sum(int(c.get("count") or 0)
                                             for c in census.values()),
                        "census": census,
                    }
                if not payload["books"]:
                    payload = {"error": "no dislocation census published yet"}
                body = json.dumps(payload, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/alerts.json"):
            # [2026-07-11] Evidence alerts + the restrict-only coin-veto list
            # (market_context.py). Read-only, no secrets, no auth — so the
            # scheduled report sessions and any external watchdog can consume.
            try:
                import psycopg2
                conn = psycopg2.connect(DATABASE_URL, connect_timeout=6)
                try:
                    with conn.cursor() as cur:
                        cur.execute("SELECT bot, state, updated_at FROM bot_state "
                                    "WHERE bot IN ('fleet-alerts', 'coin-vetoes')")
                        rows_ = {b: (s if isinstance(s, dict) else json.loads(s), u)
                                 for b, s, u in cur.fetchall()}
                finally:
                    conn.close()
                fa = rows_.get("fleet-alerts", ({}, None))
                cv = rows_.get("coin-vetoes", ({}, None))
                body = json.dumps({
                    "alerts": (fa[0].get("alerts") or [])[-25:],
                    "alerts_updated_at": fa[1].isoformat() if fa[1] else None,
                    "coin_vetoes": cv[0].get("coins") or {},
                    "vetoes_updated_at": cv[1].isoformat() if cv[1] else None,
                }, default=str).encode()
            except Exception as e:
                body = json.dumps({"error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(200); self._no_cache()
            self.send_header("Content-Type", "application/json")
            self.end_headers(); self.wfile.write(body)
            return
        if self.path.startswith("/pnl.json"):
            # Read-only JSON snapshot of every bot, for the scheduled
            # daily/weekly breakdowns. Dry-run paper P&L only — no secrets.
            # No auth on this path so the scheduled fetcher can read it.
            try:
                rows = fetch_rows()
                try:
                    _enr = fetch_ledger_enrich()
                except Exception:  # noqa: BLE001
                    _enr = {}
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = []
                _now = dt.datetime.now(dt.timezone.utc)
                _age_secs = []   # raw ages, for the freshest-update figure
                _stale_flags = []  # per-bot stale booleans, threshold-aware
                for r in rows.values():
                    d = {k: _ser(v) for k, v in r.items()}
                    # Tag so downstream reports never blend scanner paper-arb
                    # P&L with the trading bots' realized P&L.
                    d["kind"] = "scanner" if r.get("bot") in SCANNERS else "trading"
                    # [2026-07-09 LIGHTER GO-LIVE] venue provenance for the feed:
                    # which bots are real-money live vs shadow/testnet vs paper.
                    _vbase, _vsuf = venue_variant(r.get("bot") or "")
                    d["venue_mode"] = (VENUE_SUFFIXES[_vsuf][2] if _vsuf
                                       else (r.get("extra") or {}).get("venue"))
                    d["live"] = bool(_vsuf == "-lighter")
                    d["base_bot"] = _vbase
                    # [2026-07-07 UNIFORM CARDS] same server-side enrichment the
                    # cards use, for feed consumers (artifact, reports).
                    _en = _enr.get(r.get("bot")) or {}
                    if _en:
                        _td = _en.get("today_equity_delta")
                        if _td is None and _en.get("today_n"):
                            _td = _en.get("today_closed")
                        d["enrich"] = {"today_pnl": _td,
                                       "record": _en.get("record"),
                                       "last_close": _en.get("last_close"),
                                       "positions": _en.get("positions")}
                    # Per-bot heartbeat (2026-06-25): expose each bot's age and a
                    # threshold-aware stale flag so the scheduled report can flag a
                    # single laggard (e.g. equities-regime-ibkr running ~85m behind the
                    # fleet) without recomputing thresholds itself.
                    thr = stale_secs_for(r.get("bot"))
                    ua = r.get("updated_at")
                    if ua is not None:
                        if ua.tzinfo is None:
                            ua = ua.replace(tzinfo=dt.timezone.utc)
                        secs = (_now - ua).total_seconds()
                        d["age_sec"] = int(secs)
                        d["stale"] = bool(secs > thr)
                        _age_secs.append(secs)
                        _stale_flags.append(d["stale"])
                    else:
                        d["age_sec"] = None
                        d["stale"] = None
                    data.append(d)
                # Top-level meta so the scheduled report can detect a frozen feed
                # directly instead of inferring it. feed_stale = EVERY published bot
                # is past ITS OWN threshold (stock bots get the longer window), so a
                # single lagging stock bot no longer trips a false whole-feed alarm
                # — while a truly frozen feed (the 2026-06-22 failure) still does.
                freshest = min(_age_secs) if _age_secs else None
                # [2026-07-09 LIGHTER GO-LIVE] real-money live-fleet subtotal so
                # the scheduled daily/weekly reports can headline it separately.
                _live_rows = [d for d in data if d.get("live")]
                live_meta = {
                    "n_live_bots": len(_live_rows),
                    "live_pnl": round(sum((d.get("pnl_abs") or 0) for d in _live_rows), 2),
                    "live_equity": round(sum((d.get("equity") or 0) for d in _live_rows
                                             if d.get("equity") is not None), 2),
                    "live_bots": [d.get("bot") for d in _live_rows],
                }
                meta = {
                    "generated_at": _now.isoformat(),
                    "stale_threshold_sec": STALE_SECONDS,
                    "stock_stale_threshold_sec": STOCK_STALE_SECONDS,
                    "sniper_stale_threshold_sec": SNIPER_STALE_SECONDS,
                    "freshest_update_age_sec": (int(freshest) if freshest is not None else None),
                    "feed_stale": bool(_stale_flags) and all(_stale_flags),
                    "n_stale": sum(1 for s in _stale_flags if s),
                    "n_live": len(_stale_flags),
                    "live_fleet": live_meta,
                }
                payload = json.dumps({"meta": meta, "bots": data}).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/periods.json"):
            # Realized daily/weekly/monthly P&L (no auth, like /pnl.json) so a
            # scheduled fetcher can read it. Dry-run paper P&L only.
            try:
                payload = json.dumps(periods_payload()).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if self.path.startswith("/trades.json"):
            # Read-only per-trade history for the scheduled daily/weekly
            # breakdowns and the win/loss deep dive. Dry-run paper trades only —
            # no secrets. No auth on this path (like /pnl.json) so the scheduled
            # fetcher can read it. Query params: ?bot=<name>&limit=<n>&include_open=1
            q = parse_qs(urlparse(self.path).query)
            bot = q.get("bot", [None])[0]
            include_open = q.get("include_open", ["0"])[0] in ("1", "true", "yes")
            try:
                limit = min(max(int(q.get("limit", ["500"])[0]), 1), 5000)
            except (ValueError, TypeError):
                limit = 500
            source = q.get("source", ["bot"])[0]
            try:
                if source == "paper":
                    rows = fetch_paper_rows(bot=bot, limit=limit)
                else:
                    rows = fetch_trades(bot=bot, limit=limit, include_open=include_open)
                def _ser(v):
                    return v.isoformat() if hasattr(v, "isoformat") else v
                data = [{k: _ser(v) for k, v in r.items()} for r in rows]
                payload = json.dumps({"trades": data, "source": source}).encode("utf-8")
                code = 200
            except Exception as e:
                payload = json.dumps({"error": str(e)}).encode("utf-8")
                code = 500
            self.send_response(code)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(payload)))
            self._no_cache()
            self.end_headers()
            self.wfile.write(payload)
            return
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Crypto Bots"')
            self.end_headers()
            self.wfile.write(b"Auth required")
            return
        try:
            # [2026-07-18] live_wrap() turns each static, meta-refresh drill-down
            # into a live-updating page (in-place morph + heartbeat), the same
            # console treatment the main page carries inline. Applied at the
            # ONE dispatch site so every route gets it uniformly; render() (the
            # main page) is already wired inline, and live_wrap no-ops on it.
            if self.path.startswith("/market"):
                body = live_wrap(render_market()).encode()
            elif self.path.startswith("/periods"):
                body = live_wrap(render_periods()).encode()
            elif self.path.startswith("/learning"):
                body = live_wrap(render_learning()).encode()
            elif self.path.startswith("/history"):
                q = parse_qs(urlparse(self.path).query)
                body = live_wrap(render_history((q.get("hours") or ["168"])[0])).encode()
            elif self.path.startswith("/vitals"):
                body = live_wrap(render_vitals()).encode()
            else:
                body = render().encode()
        except Exception as e:
            body = f"<pre>dashboard error: {html.escape(str(e))}</pre>".encode()
        # [2026-08-04 (iy)] gzip-capable send: the live station refetches this
        # full page (584 KB measured) every ~10-20s per open tab.
        self._send_ok(body, "text/html; charset=utf-8")

    def do_POST(self):
        # [2026-07-13 INTERACTIVE MANAGE] hide / unhide / delete a bot row from
        # the page. Auth-gated like the HTML pages; the custom header makes a
        # cross-site page trigger a CORS preflight this server never approves,
        # so browser-credentialed CSRF can't fire it blind.
        if not self.path.startswith("/admin/bot"):
            self.send_response(404); self._no_cache(); self.end_headers()
            self.wfile.write(b"not found"); return
        if not self._auth_ok():
            self.send_response(401)
            self.send_header("WWW-Authenticate", 'Basic realm="Crypto Bots"')
            self.end_headers(); self.wfile.write(b"Auth required"); return
        if self.headers.get("X-Requested-With") != "fetch":
            self.send_response(403); self._no_cache(); self.end_headers()
            self.wfile.write(b"forbidden"); return
        try:
            length = int(self.headers.get("Content-Length") or 0)
            body = json.loads(self.rfile.read(length) or b"{}")
            bot = str(body.get("bot") or "").strip()
            action = str(body.get("action") or "").strip()
            if not bot or len(bot) > 80 or \
                    not all(c.isalnum() or c in "-_.:" for c in bot):
                raise ValueError(f"bad bot id {bot!r}")
            if action not in ("hide", "unhide", "delete"):
                raise ValueError(f"bad action {action!r}")
            out = {"ok": True, "bot": bot, "action": action}
            if action == "hide":
                hidden = fetch_hidden_bots()
                hidden[bot] = dt.datetime.now(dt.timezone.utc).isoformat()
                save_hidden_bots(hidden)
            elif action == "unhide":
                hidden = fetch_hidden_bots()
                hidden.pop(bot, None)
                save_hidden_bots(hidden)
            else:  # delete — bot_pnl row only; ledgers/history untouched
                out["deleted_rows"] = delete_bot_row(bot)
            payload = json.dumps(out).encode()
            self.send_response(200)
        except Exception as e:  # noqa: BLE001
            payload = json.dumps({"ok": False,
                                  "error": f"{type(e).__name__}: {e}"}).encode()
            self.send_response(400)
        self._no_cache()
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    print(f"[pnl_dashboard] serving live P&L on :{PORT} "
          f"({'DB set' if DATABASE_URL else 'NO DATABASE_URL'})", flush=True)
    # Background: snapshot every bot's equity into history every 5 min so the
    # /history charts build up over time (no changes needed in any bot).
    if DATABASE_URL:
        threading.Thread(target=history_loop, args=(300,), daemon=True).start()
    # Background: cloud-side scheduled P&L emails (dormant until SMTP_* env vars set).
    try:
        import report_emailer, sys as _sys
        threading.Thread(target=report_emailer.run_loop, args=(_sys.modules[__name__],),
                         daemon=True).start()
    except Exception as _e:
        print(f"[pnl_dashboard] emailer not started: {_e}", flush=True)
    # Background: in-service fleet watchdog — 5-min probes of our own /pnl.json,
    # transition-based alert emails (dormant until SMTP_* env vars are set, same
    # opt-in as the emailer). Live state served at /watchdog.json.
    try:
        import fleet_watchdog_svc, sys as _sys2
        threading.Thread(target=fleet_watchdog_svc.run_loop, args=(_sys2.modules[__name__],),
                         daemon=True).start()
    except Exception as _e:
        print(f"[pnl_dashboard] fleet watchdog not started: {_e}", flush=True)
    ThreadingHTTPServer(("0.0.0.0", PORT), H).serve_forever()
