#!/usr/bin/env python3
"""
audit_venue_purity.py — the LIGHTER-FIRST guard (2026-07-17).

WHY THIS EXISTS
CLAUDE.md has carried a standing user decision since 2026-07-14: "all services
must run off lighter". Nothing enforced it. A rule with no detective control is
a preference, and this one rotted exactly the way an unenforced rule always
does — silently, one import at a time, while every doc kept saying
LIGHTER-FIRST. The failure shape is the born-dark shape (see
audit_image_imports.py): the repo says one thing, the running code does
another, and NOTHING crashes — a bot happily trades Lighter off a foreign
venue's prices forever.

WHAT IT CHECKS (pure static analysis; no network, no DB, stdlib only)
Walks every shipped python file and reports each file's EXTERNAL DATA SOURCES,
flagging every non-Lighter MARKET-DATA source that is not DECLARED below.
Sources are found four ways, because a literal-URL grep is not enough:
  1. host:<h>        `https://host/...` in a CODE string (f-strings included).
  2. ccxt:<id>       `ccxt.kraken(...)` / `getattr(ccxt, id)`. A ccxt call
                     names NO url — cross_exchange_arb.py and triangular_arb.py
                     reach Kraken/Coinbase/Gemini with zero URLs in the file.
                     Grep sees a clean file. This is the gap that mattered.
  3. ccxt:<dynamic>  `ccxt.exchanges` — an unbounded venue universe chosen at
                     runtime (listing_sniper.py polls the top-100 CEXes).
  4. env:<N>=<v>     `os.environ.get("VENUE", "hl_paper")` — a foreign venue
                     as the shipped DEFAULT is a foreign venue in production.

DOCSTRINGS AND COMMENTS ARE NOT DEPENDENCIES. Sources are read off the AST and
docstrings are skipped, so prose like "pip install ccxt" or a commented-out
endpoint is not a finding. Comments never enter the AST at all.

DECLARING INTENT
Same pattern as BORN_DARK_OK: a foreign source that is CORRECT is DECLARED in
VENUE_PURITY_OK with a REASON. Exceptions are keyed (file, source) — NOT
per-file — and that precision earned its keep immediately: market_pulse.py was
handed to this script as a blanket "news/sentiment, not price data" exception,
but it also pulls Binance klines and Binance funding. A per-file exception
would have declared a real violation invisible. The news hosts are exempt; the
Binance price/funding hosts are findings.

USAGE
    python3 scripts/audit_venue_purity.py            # audit; exit 1 on findings
    python3 scripts/audit_venue_purity.py --selftest
    python3 scripts/audit_venue_purity.py --all      # show OK sources too

Read-only: reads repo files, writes nothing, never edits another file.

-----------------------------------------------------------------------------
REAL OUTPUT — `python3 scripts/audit_venue_purity.py`, measured 2026-07-17.
This is the actual audit, not a sample. Both runs below are reproducible.

  VIOLATIONS of the LIGHTER-FIRST rule (CLAUDE.md, user decision 2026-07-14):

    bot_learn.py                   [SHIPPED]  host:api.kraken.com       :417
    compile_market_data.py         [SHIPPED]  host:api.binance.com      :39
                                              host:api.coingecko.com    :99
                                              host:api.coinpaprika.com  :107
                                              host:api.kraken.com       :47
    funding_carry_bot.py           [SHIPPED]  env:VENUE=hl_paper        :180
    lighter_dislocation_bot.py     [SHIPPED]  host:api.hyperliquid.xyz  :75
    lighter_funding_spread_bot.py  [SHIPPED]  host:api.hyperliquid.xyz  :85
    listing_sniper.py              [SHIPPED]  ccxt:<dynamic>            :234
    market_context.py              [SHIPPED]  host:api.hyperliquid.xyz  :44
    market_pulse.py                [SHIPPED]  host:api.binance.com      :129   [FIXED 17-Jul]
                                              host:fapi.binance.com     :146   [FIXED 17-Jul]
    regime_oracle.py               [SHIPPED]  host:api.hyperliquid.xyz  :56
    triangular_arb.py              [SHIPPED]  ccxt:kraken               :267
    venues/__init__.py             [SHIPPED]  env:VENUE=hl_paper        :110

  audit_venue_purity: 15 VIOLATION(s) in 11 file(s); 83 files scanned
  (59 root + 10 venues/ + 14 user_data/strategies/), 17 declared exception(s).
  exit 1.

  $ python3 scripts/audit_venue_purity.py --selftest
  audit_venue_purity selftest OK (NEGATIVE fixture, docstring+comment prose
  ignored, ccxt static+dynamic, env defaults, f-strings, unparseable=LOUD,
  no stale exceptions, detector alive on the real tree)   exit 0.

VERDICT: the rule has rotted in ELEVEN shipped files — 15 violations, of which
**10 were on NO list handed to this guard** and 5 were. The briefed list was
both INCOMPLETE and WRONG in one place (it handed market_pulse over as a
declared exception; it is a real violation). Every claim below is measured.
[2026-07-17 CORRECTION: this verdict first read "7 findings it never mentioned"
and "the 4 findings the brief did name" — both unmeasurable (no BRIEF constant
exists in this code) and both refuted by this header's OWN itemisation, which
sums to 10 + 5 = 15 = the measured total. Fixed to the numbers the list
actually supports. A guard whose self-description is unchecked prose, under a
banner reading "every claim below is measured", is the exact failure it exists
to catch.]

  * venues/__init__.py:110 — `venue_context()` defaults VENUE to "hl_paper",
    which constructs a HyperliquidClient. This is the SHARED REAL-MONEY
    surface: the fallback venue for any service that does not set VENUE is
    Hyperliquid, not Lighter. Invisible to a URL grep (venues/ carries only
    Lighter hosts — measured). The most load-bearing finding here, and it
    was on no list.
    [2026-07-17, MEASURED against the live Railway project — and this entry
    got it wrong TWICE before it got it right. Read the whole note; the
    method failure is the lesson, not the numbers.
    v1 said: "in practice each service sets VENUE explicitly, so this is a
      LATENT default, not a live misroute." UNVERIFIED. Nobody had checked.
    v2 said: "FALSE — THREE services run with VENUE UNSET, including
      funding-carry." ALSO WRONG, and wrong for an embarrassing reason: the
      probe was `railway variables --service X --kv 2>/dev/null | grep ^VENUE=`
      and read NO OUTPUT as NOT SET. A transient CLI failure returned empty,
      `2>/dev/null` ate the error, and absence-of-evidence was recorded as
      evidence-of-absence. That is the exact `or 0` / swallowed-None class this
      guard exists to catch, committed by the guard's own author, in the commit
      whose entire point was correcting an unverified claim.
    v3, MEASURED with the error path VISIBLE (rc checked, empty != unset):
      funding-carry    vars=12  VENUE=hl_paper          <- SET. Explicit.
      momo-bot         vars=12  VENUE genuinely absent
      triangular-arb   vars=10  VENUE genuinely absent
      trail-blazer-live         VENUE=lighter_live      <- REAL MONEY, explicit
      tide-rider-lighter-live   VENUE=lighter_live      <- REAL MONEY, explicit
    SO THE TRUE BLAST RADIUS of this default is TWO services, both ZOMBIES of
    already-retired bots that Railway auto-deploy keeps resurrecting (see the
    railway-autodeploy-resurrects-stopped-services memory): `momo-bot`
    (hyperliquid_momo_bot.py = Trail Blazer, retired 11-Jul) and
    `triangular-arb` (retired 22-Jun) — and triangular_arb.py does not even
    call venue_context(), so it is untouched by this default. ONE zombie
    actually depends on it. Both live real-money bots set VENUE explicitly and
    were never exposed. The honest fix for the zombies is RETIREMENT, not a
    venue swap.
    METHOD RULE this entry pays for: when probing infrastructure, an ERROR and
    an ABSENCE are different facts. Never let `2>/dev/null` turn one into the
    other, and never state "X is not configured" from a command you did not
    check the exit code of.]
  * bot_learn.py:417 — THE BRAIN grades LIGHTER trades' post-exit drift on
    KRAKEN candles, 3 days after Kraken was retired. The bias is worse than
    a wrong number: `_kraken_hourly` caches None for any pair Kraken does
    not list, so drift evidence is silently ABSENT for exactly the
    Lighter-only perp alts that are the fleet's real universe. Diagnosis is
    skewed toward whichever coins Kraken happens to carry, and says nothing.
  * market_pulse.py:129,146 — the exception this guard was handed
    ("news/sentiment feeds, not price data") is FALSE AS WRITTEN.
    fetch_btc_regime() is Binance klines; fetch_funding() is Binance
    premiumIndex. Both are price/funding, published fleet-wide on the
    `market-pulse` bus key. This is why exceptions here are keyed
    (file, source), not per-file: a per-file exemption would have made a
    real violation invisible behind a true statement about the same file.
    MEASURED consumer check (severity, not existence): lighter_family_bot.py
    consumes only `panic` (news-derived) and computes its own regime from
    the Lighter cache; the Binance `btc_regime` reaches only the dashboard
    display (pnl_dashboard.py:830,1669). Advisory TODAY — a Binance-derived
    regime sitting on a Lighter-first fleet's bus, one consumer from biting.
    [FIXED 2026-07-17 — this finding is CLOSED; kept here because the lesson
    about per-(file, source) keying is why it was ever visible. Both price
    feeds moved to the venue we trade: fetch_btc_regime() -> Lighter
    /api/v1/candles, fetch_funding() -> Lighter /funding-rates (exchange ==
    'lighter' rows only — that endpoint republishes binance/bybit/hyperliquid
    benchmarks, so an unfiltered read would have been a COSMETIC swap: a
    Binance rate served through a Lighter URL, and this guard would have
    called it clean). Behaviour-neutrality MEASURED, not assumed: the regime
    rule replayed at every step over 500 aligned 4h bars agreed 251/251 =
    100.0%, zero flips. The NEWS hosts stay declared above and are asserted
    NOT-a-finding in the selftest — that half of this entry is still live.
    The output block at the top of this header is the PRE-FIX snapshot; the
    counts there move as violations land, and market_pulse's two are gone.]
  * triangular_arb.py:267 (ccxt.kraken) and listing_sniper.py:234
    (ccxt.exchanges — the top-100 CEX universe). Zero URLs in either file.
    A literal-URL grep calls both clean. This is the gap detector #2 exists
    for, and it is 2 of the 15.
  * compile_market_data.py — 4 foreign price hosts feeding the research
    brief's "breadth gauge" (its F&G sentiment host IS declared).
  * The 5 findings the brief DID name (api.hyperliquid.xyz in the dislocation
    bot and in the funding-spread bot, regime_oracle, market_context, and
    funding_carry's hl_paper default) all reproduce exactly.
  (10 novel + 5 named = 15 = the measured violation count. The counts in this
  header are the itemisation above, added up — not a recollection of a brief.)

NOT violations — measured, and worth stating so nobody "fixes" them:
  * lighter_index_bot / lighter_momentum_bot -> Yahoo. PRINCIPLED, permanent
    (see VENUE_PURITY_OK). Do not touch.
  * hyperliquid_momo_bot.py / hyperliquid_perps_bot.py — despite the names,
    they hold NO host and NO venue default: both go through venues/. Clean.
  * user_data/strategies/ (14 files) and venues/ (10 files) carry no foreign
    HOST at all.

LIMITATIONS (read before trusting a clean run)
  * STATIC. It proves what the code CAN reach, never what it did reach. A
    clean run is not evidence any bot is trading Lighter data.
  * A host assembled entirely from variables (`BASE + path` where BASE comes
    from a DB) is invisible. Every source in the fleet today is a literal or
    an env default, so this is a latent gap, not a live one.
  * ccxt ids are matched against a static roster (_CCXT_IDS). A NEW ccxt
    exchange id would read as an ordinary attribute and be missed. It is
    reported LOUDLY when `getattr(ccxt, <variable>)` is seen, which is the
    shape that hides this.
  * It cannot know whether a foreign source is *load-bearing*. bot_learn's
    Kraken call and market_pulse's Binance call are both findings here; only
    reading the consumers (done above) separates "advisory" from "steering".
  * It does not audit venues/ for CORRECTNESS, only for purity. venues/ is
    clean (Lighter hosts only) — measured, not assumed.
"""
import argparse
import ast
import os
import re
import tempfile
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# The compliant venue. Anything here is the point of the fleet.
# ---------------------------------------------------------------------------
LIGHTER_HOSTS = {
    "mainnet.zklighter.elliot.ai",
    "testnet.zklighter.elliot.ai",
    "app.lighter.xyz",
}

# ---------------------------------------------------------------------------
# NOT MARKET DATA — infrastructure, in any file. These carry no price, funding
# or venue opinion, so LIGHTER-FIRST has nothing to say about them.
# ---------------------------------------------------------------------------
INFRA_HOSTS = {
    "ntfy.sh": "phone push (watchdog/board/organ alerts) — a notification "
               "transport, no market data",
    "pnl-dashboard-production-858c.up.railway.app":
        "the fleet's OWN dashboard — reading our own published state back "
        "(/bus.json, /pnl.json), not an external venue",
    "127.0.0.1": "local freqtrade API on the same host — not an external feed",
    "localhost": "local API — not an external feed",
    "fonts.googleapis.com": "dashboard webfont CSS — presentation only",
    "fonts.gstatic.com": "dashboard webfont payload — presentation only",
    "cdnjs.cloudflare.com": "dashboard JS/CSS asset — presentation only",
    "www.w3.org": "SVG xmlns namespace URI — never fetched",
    "x-access-token": "git-over-HTTPS credential prefix in a GitHub clone URL "
                      "(freqtrade_retrain.py) — source control, not a feed",
    "github.com": "source control, not a feed",
    "api.github.com": "source control, not a feed",
}

# ---------------------------------------------------------------------------
# DECLARED-DELIBERATE foreign sources: (file, source) -> why.
#
# Keyed per (file, source) ON PURPOSE. A per-FILE exception would have hidden
# market_pulse.py's Binance price feeds behind its (true) news-feed exemption.
# An entry here says "this foreign source is CORRECT and must stay". Anything
# not listed is a VIOLATION.
# ---------------------------------------------------------------------------
VENUE_PURITY_OK = {
    # -- Gap Scout: comparison across venues IS the product ------------------
    # MEASURED, not assumed: the venue ids are never named as `ccxt.<id>` —
    # add_venue() does `getattr(ccxt, ex_id)` on a runtime id (so the growth
    # rail can hot-add from gapscout.extra_exchanges). It therefore reports
    # ccxt:<dynamic> + the env default, and nothing else. An earlier draft of
    # this table declared ccxt:kraken/gemini/... here from assumption; the
    # stale-exception selftest caught that they never existed.
    **{("cross_exchange_arb.py", s):
       "Gap Scout — a CROSS-EXCHANGE dislocation scanner needs other venues "
       "by definition; it compares CEX quotes AGAINST Lighter and publishes "
       "the Lighter premium. Removing the foreign venues deletes the bot."
       for s in ("ccxt:<dynamic>",
                 "env:ARB_EXCHANGES=kraken,coinbaseexchange,gemini")},

    # -- Equity perps: Yahoo is the PRIMARY market, not a substitute --------
    # This is a PRINCIPLED exception, not a TODO. Do not "fix" it.
    **{(f, "host:query1.finance.yahoo.com"):
       "PRINCIPLED, permanent: Lighter's equity perp is a DERIVATIVE of an "
       "NYSE-listed underlying, and its index is FROZEN while NYSE is shut. "
       "Deriving the signal from the perp would be predicting the instrument "
       "from itself (circular) off a stale index. Yahoo is the primary "
       "market — the correct source. LIGHTER-FIRST governs where we TRADE; "
       "for a derivative, the underlying's own market is the honest input."
       for f in ("lighter_index_bot.py", "lighter_momentum_bot.py")},

    # -- News / sentiment / listing feeds: not price data -------------------
    # NOTE the precision: market_pulse.py is exempt for its NEWS hosts ONLY.
    # Its api.binance.com (klines) and fapi.binance.com (premiumIndex) are
    # PRICE and FUNDING data and are deliberately NOT declared here — they
    # are real findings. See the header.
    **{("market_pulse.py", f"host:{h}"):
       "news/social sentiment feed — mood + panic-headline scoring, carries "
       "no price or venue quote"
       for h in ("www.reddit.com", "www.coindesk.com", "cointelegraph.com",
                 "api.alternative.me")},
    **{("event_sentinel.py", f"host:{h}"):
       "the event organ's RSS/GDELT sweep — discrete world-event text, not "
       "market data"
       for h in ("www.coindesk.com", "cointelegraph.com",
                 "api.gdeltproject.org")},
    **{("listing_intel.py", f"host:{h}"):
       "CEX new-listing announcement feed — the sniper's intel is WHERE a "
       "coin is about to list, which is by nature other venues' news"
       for h in ("www.binance.com", "api.kucoin.com", "api.bybit.com",
                 "api-manager.upbit.com", "api.coingecko.com")},
    ("compile_market_data.py", "host:api.alternative.me"):
        "Fear & Greed sentiment index — a mood gauge, not price or a venue "
        "quote (same class as market_pulse's news feeds). This file's price "
        "hosts are its dashboard display panel, declared below.",

    # -- compile_market_data's price panel: DASHBOARD DISPLAY, not a trader ---
    # [2026-07-18 operator decision] These four price hosts feed the dashboard's
    # breadth/regime DISPLAY gauge only. CLAUDE.md already lists this file as
    # "Still non-Lighter and DELIBERATELY kept ... for the DASHBOARD's display —
    # not a trader". It steers no orders and publishes to no strategy bus, so
    # LIGHTER-FIRST (which governs where we TRADE and MEASURE) has no claim on
    # it. Declared so the guard can be CI-blocking on the SHIPPED rule; if this
    # file ever feeds a strategy, remove the entry and it becomes a finding
    # again. (An earlier revision left these flagged; the operator's call is to
    # exempt the display panel and enforce the rest.)
    **{("compile_market_data.py", f"host:{h}"):
       "dashboard DISPLAY breadth/regime gauge — multi-venue spot prices for "
       "the dashboard's own view, not a trader (CLAUDE.md deliberately keeps "
       "this); steers no orders and publishes to no strategy bus."
       for h in ("api.binance.com", "api.coingecko.com",
                 "api.coinpaprika.com", "api.kraken.com")},

    # -- RETIRED bots that idle at boot (LIGHTER-ONLY cut, 2026-07-17) --------
    # Both rows are in cleanup_legacy_bots.LEGACY_BOTS and both bots idle at
    # boot behind a code guard, so the foreign-venue path is never reached in
    # production. Declared here (not left as findings) because a retired,
    # guarded-off bot is not a live LIGHTER-FIRST violation — same rationale as
    # BACKTEST_VENUE_OK's retired-history section.
    ("listing_sniper.py", "ccxt:<dynamic>"):
        "🎯 Launch Sniper RETIRED 2026-07-17 — the row is in LEGACY_BOTS and "
        "the bot idles at boot behind LISTING_SNIPER_OVERRIDE, so the ccxt CEX "
        "universe is never reached; replaced by lighter_perp_sniper.py.",
    ("triangular_arb.py", "ccxt:kraken"):
        "scanner-triangular-arb RETIRED — row in LEGACY_BOTS and the bot idles "
        "at boot behind ARB_RETIRED_OVERRIDE (LIGHTER-ONLY cut); the Kraken "
        "triangular scan is never reached in production.",
}

# A conservative roster of ccxt exchange ids the fleet plausibly touches, plus
# every id named anywhere in this repo. Used to tell `ccxt.kraken(...)` (an
# exchange) from `ccxt.exchanges` / `ccxt.NetworkError` (not exchanges).
_CCXT_IDS = {
    "kraken", "krakenfutures", "binance", "binanceus", "binancecoinm",
    "binanceusdm", "coinbase", "coinbaseexchange", "coinbasepro",
    "coinbaseadvanced", "gemini", "kucoin", "kucoinfutures", "gateio", "gate",
    "mexc", "okx", "bybit", "huobi", "htx", "bitfinex", "bitstamp", "bitget",
    "upbit", "bithumb", "poloniex", "cryptocom", "deribit", "bitmex", "phemex",
    "woo", "whitebit", "lbank", "bingx", "hyperliquid",
}

# Foreign venue tokens that make an env DEFAULT a foreign data source.
# "lighter" is deliberately absent — that's the compliant venue.
_FOREIGN_ENV_TOKENS = {
    "hl_paper", "hl", "hyperliquid", "kraken", "binance", "coinbase",
    "coinbaseexchange", "gemini", "kucoin", "bybit", "okx", "gateio", "mexc",
    "upbit", "yahoo", "ibkr", "alpaca",
}

# Env vars whose default we inspect for a venue token. Names, not values, so a
# new venue-selecting env var must be added here deliberately.
_VENUE_ENV_HINTS = ("VENUE", "EXCHANGE", "EXCHANGES", "BROKER", "DATA_SOURCE",
                    "MARKET_SOURCE", "FEED")

_URL_RE = re.compile(r"https?://([A-Za-z0-9._-]+)")

# Directories that are not the shipped fleet.
_SKIP_DIRS = {".git", "__pycache__", ".venv", "venv", ".claude", "scripts",
              "node_modules", ".mypy_cache", ".pytest_cache", "reports",
              "logs", "backtest_results"}


def shipped_files(root=None):
    """Every shipped python file under `root` (default: the real repo).

    [2026-07-17] `root` is a PARAMETER so the negative fixture can run in a
    tempdir. It used to write its probe into the live repo root — the audit's
    own scan target AND the `COPY . .` image surface — which made a concurrent
    audit report a phantom violation and two concurrent selftests crash. A
    detective control that mutates the thing it inspects is not a control.

    Repo root is the fleet's module surface. venues/ and user_data/strategies/
    are included deliberately: they are COPY'd packages and venues/ is the
    SHARED REAL-MONEY surface (CLAUDE.md: live bots are in every audit's
    scope, whatever its nominal scope). Excluded: scripts/ (research tools,
    this file included), .venv, .claude (worktrees live there), caches.
    """
    root = root or ROOT
    out = []
    for f in sorted(os.listdir(root)):
        if f.endswith(".py") and os.path.isfile(os.path.join(root, f)):
            out.append(f)
    for pkg in ("venues", os.path.join("user_data", "strategies")):
        base = os.path.join(root, pkg)
        if not os.path.isdir(base):
            continue
        for r, dirs, fs in os.walk(base):
            dirs[:] = [d for d in dirs if d not in _SKIP_DIRS]
            for f in sorted(fs):
                if f.endswith(".py"):
                    out.append(os.path.relpath(os.path.join(r, f), root))
    return out


def _docstrings(tree):
    """Every docstring node id in the tree.

    Docstrings and comments are PROSE, not dependencies: cross_exchange_arb's
    docstring says "pip install ccxt" and funding_basis's comments discuss
    hyperliquid periods. Neither fetches anything. Comments never reach the
    AST; docstrings do, so they are skipped by identity here.
    """
    out = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef,
                             ast.ClassDef)):
            body = getattr(node, "body", None)
            if (body and isinstance(body[0], ast.Expr)
                    and isinstance(body[0].value, ast.Constant)
                    and isinstance(body[0].value.value, str)):
                out.add(id(body[0].value))
    return out


def _code_strings(tree):
    """[(string, lineno)] for every string constant that is NOT a docstring —
    including the literal chunks of f-strings (JoinedStr), which is where an
    interpolated endpoint like f"{BASE}/api/v1/x" hides its host."""
    docs = _docstrings(tree)
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if id(node) in docs:
                continue
            out.append((node.value, getattr(node, "lineno", 0)))
    return out


def detect_sources(path):
    """{source: sorted[lineno]} for one file, or None if it does not parse.

    Sources: host:<h> | ccxt:<id> | ccxt:<dynamic> | env:<NAME>=<default>
    """
    try:
        src = open(path, encoding="utf-8", errors="ignore").read()
    except Exception:  # noqa: BLE001
        return None
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return None                     # reported LOUDLY by the caller

    found = {}

    def add(source, line):
        found.setdefault(source, set()).add(line)

    # 1 + 2. hosts in code strings (f-string chunks included).
    for s, line in _code_strings(tree):
        for host in _URL_RE.findall(s):
            add(f"host:{host}", line)

    for node in ast.walk(tree):
        # 3. ccxt.<exchange_id>(...) and ccxt.exchanges
        if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) \
                and node.value.id == "ccxt":
            if node.attr in _CCXT_IDS:
                add(f"ccxt:{node.attr}", node.lineno)
            elif node.attr == "exchanges":
                # an UNBOUNDED, runtime-chosen venue universe
                add("ccxt:<dynamic>", node.lineno)
        # 4. getattr(ccxt, x) — the id is a variable: dynamic by construction.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) \
                and node.func.id == "getattr" and len(node.args) >= 2:
            tgt = node.args[0]
            if isinstance(tgt, ast.Name) and tgt.id == "ccxt":
                a = node.args[1]
                if isinstance(a, ast.Constant) and isinstance(a.value, str):
                    add(f"ccxt:{a.value}", node.lineno)
                else:
                    add("ccxt:<dynamic>", node.lineno)
        # 5. os.environ.get("VENUE", "hl_paper") — a foreign SHIPPED default.
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                and node.func.attr == "get" and len(node.args) >= 2:
            recv = node.func.value
            is_environ = (
                (isinstance(recv, ast.Attribute) and recv.attr == "environ")
                or (isinstance(recv, ast.Name) and recv.id == "environ"))
            if not is_environ:
                continue
            name_n, dflt_n = node.args[0], node.args[1]
            if not (isinstance(name_n, ast.Constant)
                    and isinstance(name_n.value, str)
                    and isinstance(dflt_n, ast.Constant)
                    and isinstance(dflt_n.value, str)):
                continue
            name, dflt = name_n.value, dflt_n.value
            if not any(h in name.upper() for h in _VENUE_ENV_HINTS):
                continue
            if _URL_RE.search(dflt):
                continue                # a URL default is caught as host: above
            toks = {t.strip().lower() for t in re.split(r"[,\s|;]+", dflt)}
            if toks & _FOREIGN_ENV_TOKENS:
                add(f"env:{name}={dflt}", node.lineno)
    return {k: sorted(v) for k, v in found.items()}


def classify(rel, source):
    """('ok'|'lighter'|'infra'|'declared'|'violation', reason)."""
    if source.startswith("host:"):
        host = source[5:]
        if host in LIGHTER_HOSTS:
            return "lighter", "Lighter — the fleet's venue"
        if host in INFRA_HOSTS:
            return "infra", INFRA_HOSTS[host]
    key = (os.path.basename(rel), source)
    if key in VENUE_PURITY_OK:
        return "declared", VENUE_PURITY_OK[key]
    return "violation", ""


def _run_paths():
    """{module_basename} that some image/run path actually ships.

    Same idea as audit_image_imports' run-path seeding, kept deliberately
    coarse: this guard reports purity for every file and uses SHIPPED only to
    RANK severity. A violation in an unshipped file is still a violation (it
    is one COPY away from shipping) — it is just not steering money today.
    """
    shipped, texts = set(), []
    for f in os.listdir(ROOT):
        p = os.path.join(ROOT, f)
        if not os.path.isfile(p):
            continue
        if f == "Dockerfile" or f.startswith("Dockerfile.") \
                or (f.startswith("railway") and f.endswith(".toml")) \
                or f.endswith(".sh"):
            try:
                texts.append(open(p, encoding="utf-8",
                                  errors="ignore").read())
            except Exception:  # noqa: BLE001
                pass
    blob = "\n".join(texts)
    for f in os.listdir(ROOT):
        if f.endswith(".py") and re.search(r"\b" + re.escape(f), blob):
            shipped.add(f)
    # Package files ship as a DIRECTORY COPY ("COPY venues/ ./venues/"), so
    # their basename never appears in a Dockerfile. Keying on the basename
    # alone mislabelled venues/__init__.py "not shipped" — the shared
    # REAL-MONEY surface, shipped in every live image. Rank by the package.
    for pkg in ("venues", "user_data"):
        if re.search(r"\b" + re.escape(pkg) + r"/", blob):
            shipped.add(pkg + "/")
    return shipped


def _is_shipped(rel, shipped):
    if os.path.basename(rel) in shipped:
        return True
    return any(rel.startswith(p) for p in shipped if p.endswith("/"))


# ===========================================================================
# BACKTEST SECTION [2026-07-17] — a SEPARATE pass, deliberately.
#
# The operator rule (CLAUDE.md 17-Jul) is "BACKTEST ON LIGHTER ONLY — the venue
# we trade is the venue we measure". This file enforced it on SHIPPED code and
# skipped `scripts/` entirely (_SKIP_DIRS, rationalised as "research tools") —
# which is precisely where every backtest lives. So the rule that matters most
# was the one nothing checked.
#
# WHY NOT JUST DROP "scripts" FROM _SKIP_DIRS: because that answer is CONFIDENT
# AND WRONG. Measured 17-Jul: the host: detector flags 17 files in scripts/, but
# 26 of 32 actually load a foreign venue. Nine launder it past an AST host scan:
#   * `.dirfund_cache.json` is WRITTEN by backtest_directional_funding.py (HL)
#     and READ by backtest_leverage_operator / _overdrive / _xsect_momentum /
#     _xsect_factor_lab — zero host literals in any of them.
#   * `import backtest_directional_funding as bdf` (backtest_funding_leverage,
#     which justifies the LIVE 2x config), `bl.HL` (backtest_bounce_catcher_audit
#     borrowing another module's constant), `.tiderider_scanner_cache.json`
#     (Binance+HL -> backtest_strategy_shootout / _tide_rider_adaptive).
# Dropping the skip alone would mark backtest_funding_leverage.py CLEAN. A guard
# that says "clean" about the file justifying a live real-money constant is worse
# than no guard: it launders the assumption it was built to catch.
#
# So: trace PROVENANCE (cache writes + intra-scripts imports), keep a SEPARATE
# BACKTEST_VENUE_OK table, and report in a SEPARATE section that does NOT change
# the shipped verdict or the exit code yet. Turning these into build failures is
# a deliberate later step once the triage below is agreed — the same staging the
# born-dark guard got.
# ===========================================================================

BACKTEST_VENUE_OK = {
    "study_lighter_vs_hl_equivalence.py": (
        "DECLARED CROSS-VENUE by CLAUDE.md itself: the HL-vs-Lighter equivalence "
        "study. Its whole subject is the relationship between two venues, so it "
        "cannot be Lighter-only without ceasing to exist."
    ),
    "study_hl_as_lighter_funding_proxy.py": (
        "Asks 'is HL a usable proxy for Lighter funding?' — a question that "
        "requires both tapes. Its own verdict (APPROXIMATELY SURVIVES, BY LUCK, "
        "NOT BY METHOD) is what makes the Tide Rider header indefensible."
    ),
    "study_fundspread_basis_mixing.py": (
        "8h-vs-1h basis mixing across venues — the measurement that produced the "
        "funding_basis.py per-venue authority. Cross-venue by construction."
    ),
    "study_market_pulse_venue_swap.py": (
        "Proved the market_pulse Binance->Lighter swap behaviour-neutral. An A/B "
        "of a venue swap needs both sides of the swap."
    ),
    "backtest_index_pilot_macro.py": (
        "Yahoo dailies for the equity-perp UNDERLYING. Lighter's equity perps are "
        "a DERIVATIVE of NYSE — the underlying index is not available on Lighter "
        "at all, and using Lighter's own perp mark as its own signal is circular. "
        "Same principled exception as VENUE_PURITY_OK's Index Rider entry."
    ),

    # ---- RETIRED-HISTORY [2026-07-17 triage] -------------------------------
    # These load a foreign venue AND that is correct, because the bot they
    # justify does not trade. CLAUDE.md: "Retired-bot backtests are HISTORY — do
    # not re-run them; they justify nothing that still trades." Re-running them
    # on Lighter would spend days manufacturing evidence for a corpse. Each row
    # below was VERIFIED against cleanup_legacy_bots.LEGACY_BOTS (the prune
    # list), not against a doc — hiding-a-row-is-NOT-retiring-it.
    "backtest_regime.py": (
        "HL. Justifies Trail Blazer (hyperliquid_momo_bot.py), retired 11-Jul: "
        "row `momo-bot` is in LEGACY_BOTS and the bot idles at boot behind "
        "MOMO_RETIRED_OVERRIDE. Its verdict is history; see "
        "trail-blazer-no-durable-edge (paper +$197 was a lucky ~30d window)."
    ),
    "backtest_leverage.py": (
        "HL. Trail Blazer's leverage study — same retired bot as "
        "backtest_regime.py (`momo-bot` in LEGACY_BOTS, guarded off 15-Jul)."
    ),
    "backtest_leverage_rails.py": (
        "HL, inherited via `import backtest_leverage`. Same retired Trail Blazer "
        "lineage; it can only be as current as its parent, which justifies a bot "
        "that no longer trades."
    ),
    "backtest_bounce_catcher_audit.py": (
        "HL, inherited via `import backtest_leverage`. Justifies Bounce Catcher "
        "(hyperliquid_perps_bot.py): row `perps-rsi-meanrev` is in LEGACY_BOTS "
        "and the bot idles behind PERPS_RETIRED_OVERRIDE since the 17-Jul "
        "LIGHTER-ONLY cut."
    ),
    "backtest_tide_rider.py": (
        "Binance. The KRAKEN-ERA SPOT original — row `crypto-trend-daily` is in "
        "LEGACY_BOTS (14-Jul Kraken retirement, an operator decision, not an "
        "outage). Distinct from backtest_tide_rider_perp.py, which is NOT "
        "declared: that one is still cited by lighter_trend_bot.py:11 as the live "
        "bot's justification and is a real defect."
    ),
}

# Files whose venue is inherited rather than literal. Maps a provenance marker
# -> the file that actually fetches. Derived by reading each fetcher's own CACHE
# constant; kept explicit because guessing a cache's owner from its name is how
# you get a confident wrong answer.
_CACHE_OWNER = {
    ".dirfund_cache.json": "backtest_directional_funding.py",
    ".tiderider_scanner_cache.json": "backtest_tide_rider_scanner.py",
    ".fundpersist_cache.json": "backtest_funding_persistence.py",
    ".funding_cache.json": "backtest_funding.py",
    ".lighterfund_cache.json": "backtest_funding_lighter.py",   # LIGHTER-native
}


# The LIVE real-money bots. A foreign-venue backtest CITED by one of these is a
# different animal from one cited by nobody: it is the stated justification for a
# constant that is moving real money right now.
# [2026-08-15 (mz)] DERIVED from fleet_books.DECLARED_LIVE, not hand-listed —
# the hand list here named the RETIRED trend bot and the Taker's retired live
# arm while missing 🙏 Avo entirely, which mis-bucketed the blast-radius
# ranking (a stale live roster inside a guard is the exact class (mo) built
# `fleet_books` to end). `lighter_family_bot.py` rides along explicitly: the
# Avo live entry imports its strategy from it, so both files are live surface
# (the standing audit-scope rule).
def _live_bots():
    try:
        import fleet_books
        out = {fleet_books.ROW_ENTRY[r] for r in fleet_books.DECLARED_LIVE
               if r in fleet_books.ROW_ENTRY}
        if "lighter_avo_live_bot.py" in out:
            out.add("lighter_family_bot.py")
        return out
    except Exception:  # noqa: BLE001
        # a broken roster import must FAIL LOUD, not quietly grade nothing
        # as live — return a sentinel the caller can see
        raise


_LIVE_BOTS = _live_bots()

# [2026-08-15 (mz)] The fleet's OWN infrastructure is not a foreign venue.
# `study_div_vol_floor.py` reads the pnl-dashboard endpoint — the fleet's own
# ledger, i.e. Lighter's tape as this fleet recorded it — and the host
# detector charged it as a venue-purity offender. A guard that cries wolf on
# the one compliant data source teaches the operator to stop reading it.
_OWN_INFRA_HOSTS = {"pnl-dashboard-production-858c.up.railway.app"}

# [2026-08-15 (mz)] THE RATCHET. These foreign-venue backtests are CITED BY
# SHIPPED CODE as justification TODAY, and were passing an advisory section
# green for 29 days ("turning these into build failures is a deliberate later
# step" — the later step never came; the (gk) rule-nobody-runs shape). They
# are GRANDFATHERED by name with their citation sets FROZEN: any NEW
# foreign-venue backtest cited by shipped code, or any NEW citer of a legacy
# file, is a BUILD FAILURE. Each entry owes a Lighter-tape re-justification;
# removing one from this table is the act of paying that debt.
BACKTEST_VENUE_LEGACY = {
    "backtest_directional_funding.py": {
        "citers": {"lighter_funding_bot.py"},
        "why": "HL tape; the LIVE Farmer's stated justification (line ~282). "
               "The 17-Jul basis story already caught its worst export "
               "(ENTER_APR fitted on HL hourly); what remains owed is a "
               "Lighter-tape re-run of the gate constants."},
    "backtest_funding_leverage.py": {
        "citers": {"lighter_funding_bot.py", "market_context.py"},
        "why": "HL via `import backtest_directional_funding`; justifies the "
               "live 2x leverage config."},
    "backtest_scanner.py": {
        "citers": {"lighter_funding_bot.py"},
        "why": "HL tape; cited three times by the live Farmer's scanner "
               "constants."},
    "backtest_tide_rider_perp.py": {
        "citers": {"lighter_trend_bot.py"},
        "why": "Binance+HL; its bot (🌊 Tide Rider) is RETIRED 1-Aug — this "
               "is history the moment the citation line is, but the file "
               "still ships and cites, so it stays frozen here rather than "
               "silently green."},
    "backtest_xsect_factor_lab.py": {
        "citers": {"lighter_funding_spread_bot.py"},
        "why": "HL via .dirfund_cache.json; ⚖️ Counterweight factor study. "
               "The book's Lighter-native validation (ia) supersedes it as "
               "the load-bearing evidence."},
    "backtest_xsect_momentum.py": {
        "citers": {"lighter_funding_spread_bot.py"},
        "why": "HL via .dirfund_cache.json; same book, same status."},
}


def backtest_citations(root=None):
    """{backtest_name: {citing_file: [lines]}} — read from the SHIPPED bots.

    THE TRIAGE IS DERIVED, NOT DECLARED. A hand-written "which bot does this
    justify?" table is the same rotting artifact as the deploy path list and the
    07-07 organ list: correct the day it is written, silently wrong a week later.
    Every bot here already NAMES its own backtests in source ("TUNED on
    scripts/backtest_directional_funding.py"), so the citation IS the map, and it
    cannot drift from the code because it IS the code.

    Blast radius, measured 17-Jul: 5 backtests are cited by a LIVE real-money
    bot, and 4 of the 5 load Hyperliquid or Binance."""
    root = root or ROOT
    out = {}
    for rel in shipped_files(root):
        p = os.path.join(root, rel)
        try:
            txt = open(p, encoding="utf-8", errors="ignore").read()
        except Exception:  # noqa: BLE001
            continue
        for m in re.finditer(r"scripts/((?:backtest|study)_[a-z_]+\.py)", txt):
            line = txt[:m.start()].count("\n") + 1
            out.setdefault(m.group(1), {}).setdefault(rel, []).append(line)
    return out


def backtest_files(root=None):
    """Every backtest/study in scripts/ — the files _SKIP_DIRS excludes."""
    root = root or ROOT
    d = os.path.join(root, "scripts")
    if not os.path.isdir(d):
        return []
    return sorted(f for f in os.listdir(d)
                  if (f.startswith("backtest_") or f.startswith("study_"))
                  and f.endswith(".py"))


def backtest_venues(name, root=None, _seen=None):
    """{source: why} for one backtest — direct AND inherited.

    Inheritance is what makes this more than a host: grep. A file with no host
    literal that reads another file's cache, or imports it, loads that file's
    venue as surely as if it had fetched it itself. Recursion is depth-guarded
    on _seen: backtest_leverage_rails imports backtest_leverage imports ...
    """
    root = root or ROOT
    _seen = _seen if _seen is not None else set()
    if name in _seen:
        return {}                       # import cycle — already accounted
    _seen.add(name)
    path = os.path.join(root, "scripts", name)
    if not os.path.exists(path):
        return {}
    out = {}
    srcs = detect_sources(path)
    if srcs is None:
        return {"UNPARSED": "does not parse — its venue is UNKNOWN, not clean"}
    for s in srcs:
        if s.startswith("host:") or s.startswith("ccxt:"):
            out[s] = "direct"
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="ignore").read())
    except Exception:  # noqa: BLE001
        return out

    # [2026-07-17] AST, NOT a substring scan over the raw text. My first cut did
    # `if cache in text` and FALSE-FLAGGED backtest_xsect_funding_lighter.py —
    # a genuinely Lighter-native file whose line 8 is a COMMENT saying "...it ran
    # on `.dirfund_cache.json`, which [was the bug]". The tracer read the
    # sentence describing the FIX and charged the file for it. That is the exact
    # blind spot this module's own detector was built to avoid ("docstring+
    # comment prose ignored" is in its selftest name), reintroduced by me one
    # function later. A guard that cries wolf about the one compliant file is as
    # useless as a guard that is blind — both teach you to stop reading it.
    lits = set(_code_strings(tree))          # string literals in CODE, not prose
    for cache, owner in _CACHE_OWNER.items():
        if owner == name:
            continue
        if any(cache in s for s in lits):
            for s in backtest_venues(owner, root, _seen):
                if s != "UNPARSED":
                    out.setdefault(s, f"via {cache} (written by {owner})")

    # imports, from the AST — a commented-out or docstring'd import is not one
    deps = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            deps.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            deps.add(node.module)
    for d in sorted(deps):
        if not (d.startswith("backtest_") or d.startswith("study_")):
            continue
        dep = d + ".py"
        if dep == name:
            continue
        for s in backtest_venues(dep, root, _seen):
            if s != "UNPARSED":
                out.setdefault(s, f"via `import {d}`")
    return out


def audit_backtests(root=None):
    """(offenders, declared) — offenders are (name, {source: why})."""
    root = root or ROOT
    offenders, declared = [], []
    for name in backtest_files(root):
        v = backtest_venues(name, root)
        foreign = {s: w for s, w in v.items()
                   if s != "UNPARSED" and "lighter" not in s.lower()
                   and not any(h in s for h in _OWN_INFRA_HOSTS)}
        if not foreign:
            continue
        if name in BACKTEST_VENUE_OK:
            declared.append((name, foreign))
        else:
            offenders.append((name, foreign))
    return offenders, declared


def backtest_failures(offenders, cites):
    """[2026-08-15 (mz)] The ratchet's decision, pure so the selftest can
    drive it. A foreign-venue backtest FAILS the build iff it is cited by
    shipped code and either (a) it is not declared in BACKTEST_VENUE_OK or
    BACKTEST_VENUE_LEGACY at all, or (b) it is LEGACY but has grown a citer
    outside its frozen set. Uncited foreign backtests stay advisory — they
    justify nothing, and red-flagging history nobody cites trains the
    operator to ignore the section."""
    fails = []
    for name, _foreign in offenders:
        by = set(cites.get(name, {}))
        if not by:
            continue
        legacy = BACKTEST_VENUE_LEGACY.get(name)
        if legacy is None:
            fails.append(
                f"scripts/{name} loads a foreign venue and is cited by "
                f"{sorted(by)} — a NEW foreign-venue justification. "
                f"Re-run it on Lighter's own tape, or declare it with a "
                f"reason (BACKTEST_VENUE_OK if principled, "
                f"BACKTEST_VENUE_LEGACY if grandfathered debt).")
        else:
            new = by - set(legacy["citers"])
            if new:
                fails.append(
                    f"scripts/{name} is grandfathered foreign-venue DEBT and "
                    f"gained NEW citer(s) {sorted(new)} — a legacy backtest "
                    f"may not justify anything new. Cite Lighter-tape "
                    f"evidence instead.")
    return fails


def audit(root=None):
    """(violations, oks, unparsed) — violations are (rel, source, lines).

    `root` defaults to the real repo; the selftest passes a tempdir so its
    negative fixture never touches the tree it is auditing."""
    root = root or ROOT
    violations, oks, unparsed = [], [], []
    for rel in shipped_files(root):
        srcs = detect_sources(os.path.join(root, rel))
        if srcs is None:
            unparsed.append(rel)
            continue
        for source, lines in sorted(srcs.items()):
            kind, reason = classify(rel, source)
            if kind == "violation":
                violations.append((rel, source, lines))
            else:
                oks.append((rel, source, kind, reason))
    return violations, oks, unparsed


def main(argv):
    ap = argparse.ArgumentParser(description="LIGHTER-FIRST venue-purity guard")
    ap.add_argument("--all", action="store_true",
                    help="also list compliant/declared sources")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    violations, oks, unparsed = audit()
    shipped = _run_paths()
    n_files = len(shipped_files())

    if args.all:
        print("COMPLIANT / DECLARED sources:")
        for rel, source, kind, reason in oks:
            print(f"  [{kind:8}] {rel:34} {source}")
            if kind == "declared":
                print(f"             ^ {reason}")
        print()

    for rel in unparsed:
        print(f"UNAUDITED: {rel} does not parse (syntax error or merge "
              f"conflict) — its venue sources are UNKNOWN, not clean.")

    if violations:
        print("VIOLATIONS of the LIGHTER-FIRST rule "
              "(CLAUDE.md, user decision 2026-07-14):\n")
        by_file = {}
        for rel, source, lines in violations:
            by_file.setdefault(rel, []).append((source, lines))
        for rel in sorted(by_file):
            tag = "SHIPPED" if _is_shipped(rel, shipped) else "not shipped"
            print(f"  {rel}  [{tag}]")
            for source, lines in sorted(by_file[rel]):
                ln = ",".join(str(x) for x in lines[:4])
                print(f"      {source:42} line {ln}")
        print(f"\n  Fix: move it to Lighter data, or DECLARE it in "
              f"VENUE_PURITY_OK with a reason.")

    # ---- BACKTESTS: separate section. [2026-08-15 (mz)] RATCHETED: cited-by-
    # shipped offenders outside the OK/LEGACY tables FAIL the build; uncited
    # history stays advisory (see backtest_failures).
    bt_offenders, bt_declared = audit_backtests()
    bt_fails = backtest_failures(bt_offenders, backtest_citations())
    if bt_offenders:
        print("\n" + "=" * 74)
        print("BACKTEST VENUE PURITY [ratcheted (mz): new cited offenders "
              "FAIL; uncited history advisory]")
        print("  Operator rule 17-Jul: \"the venue we trade is the venue we "
              "measure\".\n  A backtest on another venue's data is not "
              "validation of a Lighter bot —\n  it is a hypothesis about "
              "Lighter.\n")
        cites = backtest_citations()

        def radius(item):
            """Rank by BLAST RADIUS: what does this thing justify, and does that
            justification still move money? An undifferentiated list of 22 is a
            list nobody triages."""
            name = item[0]
            by = cites.get(name, {})
            if any(b in _LIVE_BOTS for b in by):
                return 0                       # justifies a LIVE real-money bot
            if by:
                return 1                       # justifies some shipped bot
            return 2                           # cited by nothing shipped

        BUCKET = {0: "LIVE REAL MONEY", 1: "shipped (shadow/retired bot)",
                  2: "cited by no shipped code"}
        last = None
        for name, foreign in sorted(bt_offenders, key=lambda i: (radius(i), i[0])):
            r = radius((name, foreign))
            if r != last:
                print(f"\n  --- {BUCKET[r]} " + "-" * (56 - len(BUCKET[r])))
                last = r
            inherited = not any(w == "direct" for w in foreign.values())
            flag = "  [LAUNDERED — invisible to a host: scan]" if inherited else ""
            print(f"  scripts/{name}{flag}")
            for s, why in sorted(foreign.items()):
                print(f"      {s:34} {why}")
            for b, lines in sorted(cites.get(name, {}).items()):
                mark = "  <-- ITS STATED JUSTIFICATION" if b in _LIVE_BOTS else ""
                ln = ",".join(str(x) for x in lines[:3])
                print(f"      cited by {b}:{ln}{mark}")
        live_n = sum(1 for i in bt_offenders if radius(i) == 0)
        print(f"\n  {len(bt_offenders)} undeclared / {len(bt_declared)} declared. "
              f"{live_n} are cited BY A LIVE REAL-MONEY BOT as the\n  justification "
              f"for a constant moving real money today — triage those first.\n"
              f"  Declare in BACKTEST_VENUE_OK with a reason, or re-run on "
              f"Lighter's own ~438d tape.\n  Retired-bot backtests are HISTORY: "
              f"declare them, do not re-run them.")
        print("=" * 74)

    if bt_fails:
        print("\nBACKTEST RATCHET FAILURES:")
        for f in bt_fails:
            print(f"  ERROR: {f}")

    total = len(violations) + len(unparsed) + len(bt_fails)
    if total:
        n_v_files = len({r for r, _s, _l in violations})
        print(f"\naudit_venue_purity: {len(violations)} VIOLATION(s) in "
              f"{n_v_files} file(s) + {len(bt_fails)} backtest ratchet "
              f"failure(s); {n_files} files scanned, "
              f"{len(VENUE_PURITY_OK)} declared exception(s).")
        if unparsed:
            print(f"                    {len(unparsed)} file(s) UNAUDITED.")
        return 1
    print(f"audit_venue_purity: OK — {n_files} shipped files; every external "
          f"market-data source is Lighter, infrastructure, or declared in "
          f"VENUE_PURITY_OK ({len(VENUE_PURITY_OK)} declared).")
    return 0


def _selftest():
    import tempfile

    # --- NEGATIVE FIXTURE: the whole point of a detective control. ----------
    # A synthetic shipped file with an UNDECLARED foreign host MUST be flagged.
    # Without this, "0 violations" is indistinguishable from a broken detector.
    # [2026-07-17 FIX] This fixture used to write its probe into the LIVE repo
    # root and call the global audit() — mutating the very tree it inspects, on
    # the `COPY . .` image surface, ungitignored. Reproduced by a reviewer: a
    # concurrent audit saw a phantom `host:api.foreign-venue.example`, and two
    # of three concurrent selftests died on FileNotFoundError. It also made this
    # file's own "writes nothing, never edits another file" claim FALSE. It now
    # runs in a tempdir like the other three fixture blocks below already did.
    with tempfile.TemporaryDirectory() as d:
        probe_name = "_venue_purity_selftest_probe.py"
        open(os.path.join(d, probe_name), "w").write(
            '"""Docstring mentioning https://api.evil-exchange.com — PROSE, '
            'must NOT be a finding."""\n'
            "import os, urllib.request\n"
            "# comment: https://api.also-not-a-finding.com\n"
            'BAD = "https://api.foreign-venue.example/klines"\n'
            'OK_ = "https://mainnet.zklighter.elliot.ai/api/v1/candles"\n'
            'PUSH = "https://ntfy.sh/topic"\n')
        v, _oks, unp = audit(root=d)
        assert not unp, unp
        got = {s for r, s, _l in v if r == probe_name}
        assert got == {"host:api.foreign-venue.example"}, \
            f"negative fixture: expected the foreign host ONLY, got {got}"
        # and the compliant/infra/prose ones must NOT be findings
        assert "host:mainnet.zklighter.elliot.ai" not in got, "Lighter flagged"
        assert "host:ntfy.sh" not in got, "infra flagged"
        assert "host:api.evil-exchange.com" not in got, \
            "DOCSTRING host flagged — prose is not a dependency"
        assert "host:api.also-not-a-finding.com" not in got, "COMMENT flagged"
    # PROVE the fixture left no trace in the real tree — the defect it replaces
    # was invisible precisely because nobody checked.
    assert not os.path.exists(os.path.join(ROOT, "_venue_purity_selftest_probe.py")), \
        "selftest leaked a probe into the repo root"

    # --- ccxt: the gap a URL grep cannot see -------------------------------
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        open(p, "w").write(
            "import ccxt\n"
            "ex = ccxt.kraken({'enableRateLimit': True})\n"
            "e2 = getattr(ccxt, 'binance')()\n"
            "e3 = getattr(ccxt, some_var)()\n"
            "for e in ccxt.exchanges: pass\n"
            "err = ccxt.NetworkError\n")
        s = detect_sources(p)
        assert "ccxt:kraken" in s, s
        assert "ccxt:binance" in s, s
        assert "ccxt:<dynamic>" in s, "getattr(ccxt, var)/ccxt.exchanges missed"
        assert "ccxt:NetworkError" not in s, "non-exchange attr misread as venue"
        # a URL grep finds NOTHING in that file — the point:
        assert not _URL_RE.search(open(p).read()), "fixture must have no URL"

    # --- env defaults + f-strings ------------------------------------------
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        open(p, "w").write(
            "import os\n"
            'M = os.environ.get("VENUE", "hl_paper")\n'
            'L = os.environ.get("VENUE2", "lighter_shadow")\n'
            'X = os.environ.get("ARB_EXCHANGES", "kraken,gemini")\n'
            'N = os.environ.get("LOG_LEVEL", "info")\n'
            'B = os.environ.get("LIGHTER_API_BASE", "https://mainnet.zklighter.elliot.ai")\n'
            'u = f"https://api.hyperliquid.xyz/info?x={M}"\n')
        s = detect_sources(p)
        assert "env:VENUE=hl_paper" in s, s
        assert "env:VENUE2=lighter_shadow" not in s, "lighter default flagged"
        assert "env:ARB_EXCHANGES=kraken,gemini" in s, s
        assert not any(k.startswith("env:LOG_LEVEL") for k in s), \
            "non-venue env var flagged"
        assert "host:mainnet.zklighter.elliot.ai" in s, "url env default missed"
        assert not any(k.startswith("env:LIGHTER_API_BASE") for k in s), \
            "url env default double-counted as env:"
        assert "host:api.hyperliquid.xyz" in s, "f-string host missed"

    # --- unparseable is LOUD, never silently clean -------------------------
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "t.py")
        open(p, "w").write("<<<<<<< Updated upstream\nx = 1\n")
        assert detect_sources(p) is None, \
            "a conflicted/broken file must report UNKNOWN, not clean"

    # --- the declared exceptions must actually MATCH the real repo ---------
    # A stale exception is worse than none: it silently exempts nothing while
    # reading as coverage. Every declared (file, source) must be REAL.
    live = {}
    for rel in shipped_files():
        s = detect_sources(os.path.join(ROOT, rel)) or {}
        live[os.path.basename(rel)] = set(s)
    stale = [(f, s) for (f, s) in VENUE_PURITY_OK
             if f in live and s not in live[f]]
    assert not stale, f"stale VENUE_PURITY_OK entries (source gone): {stale}"

    # --- every exception carries a REASON ----------------------------------
    assert all(isinstance(v, str) and len(v) > 30
               for v in VENUE_PURITY_OK.values()), "an exception lacks a reason"
    assert all(isinstance(v, str) and len(v) > 20
               for v in INFRA_HOSTS.values()), "an infra host lacks a reason"

    # --- the detector still WORKS on the real tree --------------------------
    # [2026-07-17 REDESIGNED — the original version of this block was wrong in
    # a way worth recording, because it is a trap any "known findings" fixture
    # falls into.] It hardcoded the five violations found on the day it was
    # written and asserted each one STILL EXISTS:
    #     ("regime_oracle.py", "host:api.hyperliquid.xyz"), ("bot_learn.py",
    #     "host:api.kraken.com"), ("venues/__init__.py", "env:VENUE=hl_paper"), ...
    # So the selftest DEMANDED THAT THE DEFECTS REMAIN. It went red the moment
    # venues/__init__.py's real-money default was fixed, and again as each bot
    # moved to Lighter data — i.e. it FAILS ON GOOD NEWS. A control that breaks
    # when the fleet gets healthier trains the next session to delete
    # assertions to get green, which is how a detective control dies.
    # THE FIX: assert the DETECTOR'S CAPABILITY, never the fleet's illness.
    # Each detector KIND is already proven permanently by a SYNTHETIC fixture
    # above (host: / ccxt: static+dynamic / env: defaults, all on tempdir
    # files). What is worth asserting against the REAL tree is only that the
    # detector is alive on it and not silently blind:
    v, _oks, unparsed = audit()
    real = {(r, s) for r, s, _l in v}
    assert not unparsed, f"detector went BLIND on real files: {unparsed}"
    scanned = shipped_files()
    assert len(scanned) > 50, f"shipped_files() collapsed to {len(scanned)}"
    # The real tree must still be REACHABLE by every detector kind — proven by
    # the declared exceptions (which are stable by construction: a principled
    # exception is not something anyone 'fixes'), not by open violations.
    _, oks_now, _ = audit()
    kinds = {s.split(":", 1)[0] for _r, s, _k, _reason in oks_now} | {
        s.split(":", 1)[0] for _r, s in real}
    for kind in ("host", "ccxt", "env"):
        assert kind in kinds, \
            f"detector kind '{kind}' produced NOTHING on the real tree — blind?"
    # Violations are REPORTED, never asserted. If this fleet ever reaches zero
    # violations that is a SUCCESS, and this selftest must stay green.
    # ...and must NOT flag the principled/compliant ones
    for never in (("lighter_index_bot.py", "host:query1.finance.yahoo.com"),
                  ("cross_exchange_arb.py", "ccxt:<dynamic>"),
                  ("market_pulse.py", "host:www.reddit.com")):
        assert never not in real, f"declared exception not honored: {never}"

    # venues/ carries NO foreign HOST (measured) — the SHARED REAL-MONEY
    # surface. This one still asserts a live property and stays.
    vsrc = detect_sources(os.path.join(ROOT, "venues", "__init__.py")) or {}
    assert not [h for h in vsrc if h.startswith("host:")
                and h[5:] not in LIGHTER_HOSTS], \
        f"venues/ gained a foreign HOST — real-money surface: {sorted(vsrc)}"
    # [2026-07-17] The companion assertion — `("venues/__init__.py",
    # "env:VENUE=hl_paper") in real`, "venue_context()'s Hyperliquid default
    # must stay visible" — is DELIBERATELY GONE. It was written when that
    # default WAS hl_paper; the default has since been fixed to lighter_shadow,
    # so the assertion demanded that a REAL-MONEY DEFECT remain in place and
    # went red the moment the fleet got safer. A selftest must never require a
    # violation to persist.
    # Nothing is lost. Two things still cover it, both stronger:
    #   1. the SYNTHETIC fixture above proves the env detector SEES an
    #      hl_paper default (on a tempdir file, forever, regardless of what
    #      the real tree does);
    #   2. the real audit() FLAGS any foreign VENUE default in venues/ as a
    #      violation and exits non-zero — that, not a selftest assert, is what
    #      protects the real-money surface from regressing.
    # Deliberately NOT replaced with "assert the fix holds": that would couple
    # this committed test to another session's working-tree change and go red
    # on a fresh clone. The audit covers the regression; the fixture covers the
    # detector.

    # SHIPPED ranking must survive a directory COPY (venues/ has no basename
    # in any Dockerfile, yet ships in every live image).
    assert _is_shipped("venues/__init__.py", _run_paths()), \
        "package files mislabelled unshipped"

    # ---- BACKTEST provenance tracer [2026-07-17] ---------------------------
    # Fixtures, not the real tree's current counts: asserting today's 22
    # violations still exist would demand the defects remain
    # (tests-must-not-fail-on-good-news).
    with tempfile.TemporaryDirectory() as d:
        s = os.path.join(d, "scripts")
        os.makedirs(s)
        w = lambda n, t: open(os.path.join(s, n), "w").write(t)
        w("backtest_directional_funding.py",
          'CACHE = ".dirfund_cache.json"\nURL = "https://api.hyperliquid.xyz/info"\n')
        # inherits via the cache STRING LITERAL
        w("backtest_child_cache.py", 'C = ".dirfund_cache.json"\nx = 1\n')
        # inherits via an AST import
        w("backtest_child_import.py", 'import backtest_directional_funding as b\n')
        # THE REGRESSION FIXTURE: names the cache only in PROSE. My first cut
        # substring-scanned raw text and charged this file for a comment that
        # described the bug being FIXED (the real backtest_xsect_funding_lighter).
        w("backtest_prose_only.py",
          '"""We used to read .dirfund_cache.json — that was the bug, now fixed."""\n'
          '# never touch .dirfund_cache.json again\n'
          'URL = "https://mainnet.zklighter.elliot.ai/api/v1/candles"\n')
        HL = "host:api.hyperliquid.xyz"
        assert HL in backtest_venues("backtest_child_cache.py", d), "cache literal"
        assert HL in backtest_venues("backtest_child_import.py", d), "AST import"
        got = backtest_venues("backtest_prose_only.py", d)
        assert HL not in got, f"PROSE must not taint a clean file: {got}"
        assert any("lighter" in k for k in got), got
        assert set(backtest_files(d)) == {
            "backtest_directional_funding.py", "backtest_child_cache.py",
            "backtest_child_import.py", "backtest_prose_only.py"}, backtest_files(d)
        # a self-import / cycle must terminate, not recurse forever
        w("backtest_cycle_a.py", "import backtest_cycle_b\n")
        w("backtest_cycle_b.py", "import backtest_cycle_a\n")
        backtest_venues("backtest_cycle_a.py", d)      # must return, not hang
    for k, v in BACKTEST_VENUE_OK.items():
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"

    # --- [(mz)] the backtest RATCHET's decision table, driven pure ---------
    _off = [("brand_new_hl_backtest.py", {"host:api.hyperliquid.xyz": "direct"}),
            ("backtest_scanner.py", {"host:api.hyperliquid.xyz": "direct"}),
            ("uncited_history.py", {"host:api.hyperliquid.xyz": "direct"})]
    # a NEW cited offender fails; a legacy one inside its frozen citers does
    # not; uncited history stays advisory
    _f = backtest_failures(_off, {
        "brand_new_hl_backtest.py": {"some_new_bot.py": [1]},
        "backtest_scanner.py": {"lighter_funding_bot.py": [340]}})
    assert len(_f) == 1 and "brand_new_hl_backtest.py" in _f[0], _f
    # a legacy file growing a NEW citer fails, and the message names it
    _f2 = backtest_failures(_off, {
        "backtest_scanner.py": {"lighter_funding_bot.py": [340],
                                "shiny_new_bot.py": [7]}})
    assert len(_f2) == 1 and "shiny_new_bot.py" in _f2[0], _f2
    # nothing cited -> nothing fails (history is advisory, not red)
    assert backtest_failures(_off, {}) == []
    # the LIVE roster is DERIVED and contains the real live pair's surface
    assert "lighter_funding_bot.py" in _LIVE_BOTS
    assert "lighter_family_bot.py" in _LIVE_BOTS, (
        "Avo's strategy module is live surface — the derived roster must "
        "carry it")
    assert "lighter_trend_bot.py" not in _LIVE_BOTS, (
        "the retired trend bot must not rank citations as LIVE money")

    print("audit_venue_purity selftest OK (NEGATIVE fixture, docstring+comment "
          "prose ignored, ccxt static+dynamic, env defaults, f-strings, "
          "unparseable=LOUD, no stale exceptions, detector alive on the real "
          "tree; backtest provenance: cache+import inherit, PROSE does not, "
          "cycles terminate)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main(sys.argv[1:]))
