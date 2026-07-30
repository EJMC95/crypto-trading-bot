"""Every book must record WHY its exit fired — the plumbed-but-never-filled class.

[2026-07-30 (gr)] The operator asked for exits "tailored to perfection" per bot.
Attempting it surfaced that the tailoring was not possible, for a reason one
level below where anyone was looking:

    `publish_paper_trade` has accepted `entry_price` / `exit_price` since
    17-Jul. The DB column exists. The INSERT carries them. The reader SELECTs
    them. `/trades.json` exposes them. **Eight of nine bots never passed them.**

In six of those bots the prices were *right there* — computed two lines above
the call to derive `pnl_pct`, then dropped. So the entire pipe was built end to
end and the taps were shut, which is the mirror image of this repo's
registered-but-inert failures: **plumbed-but-never-filled**. Measured on the
live tape before the fix: 0 of 82 carry rows, 0 of 135 taker rows, 0 of 14 Snap
Back rows carried a price. Only the LIVE Farmer did (50 of 85).

WHY IT BLOCKS THE WHOLE EXERCISE: an exit rule can only be judged
counterfactually — "what would a 6% take-profit have done to the trades this
book actually took?" — and that requires joining a PRICE PATH to the trade. With
no entry or exit price on the row there is nothing to join to, so every exit
constant in the fleet was unfalsifiable. (gq) could measure which exit reason
*did* lose money; it could not measure what a different rule would have done.

AND THE PART THAT IS NOT ABOUT PRICES. 🌾 carry is a FUNDING book: its P&L is
`accrued - fees`, so a price-path sweep measures the wrong thing entirely. What
governs its exit is the APR it entered at, the APR it left at, and how much it
had been paid by then — and its publish call carried no `extra` at all. Same
defect class, different missing field. These tests therefore assert
book-appropriate telemetry rather than a uniform price rule.
"""
import ast
import pathlib
import re

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]

#: Books whose P&L is driven by the PRICE path -> need entry/exit price, so an
#: exit rule can be replayed against candles.
PRICE_BOOKS = [
    "lighter_dislocation_bot",       # 🧲 Snap Back
    "lighter_funding_spread_bot",    # ⚖️ Counterweight (legs are priced)
    "lighter_index_bot",             # 📊 Index Rider
    "lighter_trend_bot",             # 🌊 Tide Rider
    "lighter_perp_sniper",           # 🎯 Perp Sniper
    "lighter_family_bot",            # 👩👨🙏🔮 the family
    "lighter_ticket_taker",          # 🎫 Ticket Taker — REAL MONEY
    "lighter_funding_bot",           # 💸 Funding Farmer — REAL MONEY (already did)
]

#: Books whose P&L is driven by FUNDING ACCRUAL -> a price sweep is the wrong
#: instrument; the exit is governed by APR and time-paid.
FUNDING_BOOKS = {
    "funding_carry_bot": ("entry_apr", "exit_apr", "accrued", "held_h"),
}


def _publish_calls(mod):
    """Every `publish_paper_trade(...)` call in a module, as AST nodes."""
    tree = ast.parse((_ROOT / f"{mod}.py").read_text())
    out = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fn = node.func
        name = fn.attr if isinstance(fn, ast.Attribute) else getattr(fn, "id", "")
        if name == "publish_paper_trade":
            out.append(node)
    return out


def _kwargs(call):
    return {k.arg for k in call.keywords if k.arg}


def _extra_keys(call):
    """Literal keys of an `extra={...}` dict argument, if it is a literal."""
    for kw in call.keywords:
        if kw.arg == "extra" and isinstance(kw.value, ast.Dict):
            return {k.value for k in kw.value.keys if isinstance(k, ast.Constant)}
    return set()


# --------------------------------------------------------------------------
# 1. The pipe exists. Assert that FIRST, so a failure below is unambiguous.
# --------------------------------------------------------------------------

def test_the_ledger_can_carry_prices_at_every_layer():
    """If any of these regress, the bots' kwargs become silent no-ops. This is
    the assertion that distinguishes "the store dropped the field" from "the bot
    never sent it" — the two are indistinguishable from the endpoint alone."""
    store = (_ROOT / "bot_pnl_store.py").read_text()
    assert "entry_price=None, exit_price=None" in store, "writer signature"
    assert "ADD COLUMN IF NOT EXISTS entry_price" in store, "DB column"
    assert "entry_price=EXCLUDED.entry_price" in store, "upsert carries it"
    assert "entry_price, exit_price, tag" in store, "reader SELECTs it"


# --------------------------------------------------------------------------
# 2. Price-driven books must send prices.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod", PRICE_BOOKS)
def test_a_price_driven_book_records_its_entry_and_exit_price(mod):
    calls = _publish_calls(mod)
    assert calls, f"{mod} writes no paper trades at all"
    ok = [c for c in calls
          if {"entry_price", "exit_price"} <= _kwargs(c)]
    assert ok, (
        f"{mod} closes trades without recording entry_price/exit_price. The "
        "kwargs are accepted, the column exists, the reader selects them — a "
        "missing pair here makes every exit constant in this book "
        "unfalsifiable, because no price path can be joined to the trade.")


@pytest.mark.parametrize("mod", PRICE_BOOKS)
def test_the_prices_come_from_a_variable_not_a_literal(mod):
    """A hardcoded price would be worse than none — it would look like data.
    Guards against a placeholder like `entry_price=0` being left in."""
    for call in _publish_calls(mod):
        for kw in call.keywords:
            if kw.arg in ("entry_price", "exit_price"):
                assert not isinstance(kw.value, ast.Constant), (
                    f"{mod}: {kw.arg} is a literal — that is fabricated data, "
                    "not telemetry")


# --------------------------------------------------------------------------
# 3. Funding-driven books must send the funding fields instead.
# --------------------------------------------------------------------------

@pytest.mark.parametrize("mod,fields", sorted(FUNDING_BOOKS.items()))
def test_a_funding_driven_book_records_its_APR_and_time_paid(mod, fields):
    """🌾 carry's P&L is `accrued - fees`, so entry/exit PRICE would not answer
    the question its exit poses. (gq) measured +$71.42 on `*_decay_paid` (hold
    65-70h) against -$17.32 on the sided flips (hold 6-10h); asking "should the
    flip have waited?" needs the APR at both ends and the accrual so far, and
    the row carried none of it."""
    calls = _publish_calls(mod)
    assert calls, f"{mod} writes no paper trades at all"
    best = max((_extra_keys(c) for c in calls), key=len, default=set())
    missing = [f for f in fields if f not in best]
    assert not missing, (
        f"{mod} records no {missing} on its close rows. A price sweep is the "
        "WRONG instrument for a funding book — these are the fields that "
        "govern its exit.")


def test_the_funding_book_is_not_asked_for_prices_it_does_not_have():
    """The converse, so a future 'make it uniform' refactor does not bolt a
    meaningless price onto a funding book and call it telemetry. carry's
    position dict has no price in it at all — notional, accrued, fees,
    opened_ts, side, entry_apr."""
    src = (_ROOT / "funding_carry_bot.py").read_text()
    assert 'dict(side, notional, opened_ts, accrued, fees, entry_apr)' in src, (
        "the position shape moved — re-check whether a price now exists before "
        "assuming this book still cannot supply one")
    for mod in FUNDING_BOOKS:
        assert mod not in PRICE_BOOKS, f"{mod} is classified twice"


# --------------------------------------------------------------------------
# 4. The class itself — no ledger-writing bot may leave prices in scope unsent.
#    This is what stops the NEXT bot from being born with the tap shut.
# --------------------------------------------------------------------------

def _enclosing_fn(tree, node):
    best = None
    for m in ast.walk(tree):
        if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if m.lineno <= node.lineno <= (m.end_lineno or m.lineno):
                if best is None or m.lineno > best.lineno:
                    best = m
    return best


#: RETIRED bots that trip the general guard and should not. EXPLICIT, with the
#: reason, and NOT derived — because the obvious derivation is subtly wrong in a
#: dangerous direction. `LEGACY_BOTS` contains `perps-funding-carry` (the HL arm,
#: retired 17-Jul) while the LIVING `perps-funding-carry-lshadow` twin continues,
#: so any substring match from row name to legacy list EXEMPTS THE FLEET'S BEST
#: BOOK. Measured that exact false positive while writing this file. A guard that
#: silently stops guarding is worse than one that occasionally nags, so the
#: exemption is a hand-checked list of three and `test_only_genuinely_dead_bots_
#: are_exempt` re-verifies each one against the live dashboard rows.
RETIRED_EXEMPT = {
    # Trail Blazer — row perps-donchian-breakout, code-guarded off 15-Jul
    "hyperliquid_momo_bot",
    # Bounce Catcher — row perps-rsi-meanrev, LIGHTER-ONLY guard 17-Jul
    "hyperliquid_perps_bot",
    # Stock Leaders — row equities-momentum, retired 17-Jul (maxDD 37-44%)
    "lighter_momentum_bot",
}


def test_only_genuinely_dead_bots_are_exempt():
    """Each exemption must be a bot that idles behind a code guard AND whose row
    is in LEGACY_BOTS. If one is ever resurrected this fails and the guard
    reclaims it."""
    from cleanup_legacy_bots import LEGACY_BOTS
    legacy = set(LEGACY_BOTS)
    for mod in sorted(RETIRED_EXEMPT):
        src = (_ROOT / f"{mod}.py").read_text()
        # Each of the three uses a DIFFERENT guard idiom, which is itself worth
        # pinning: `PERPS_RETIRED_OVERRIDE`, the Trail Blazer idle loop, and
        # `MOMO_RETIRED`. Match the general shape — an env-gated retirement
        # check — rather than any one spelling.
        assert re.search(r"""os\.environ\.get\(\s*["'][A-Z_]*RETIRED""", src) or \
               re.search(r"RETIRED_OVERRIDE", src), (
            f"{mod} has no env-gated retirement guard — is it live again?")
        rows = set(re.findall(r"""["']([a-z0-9]+(?:-[a-z0-9]+)+)["']""", src))
        assert rows & legacy, (
            f"{mod} names no LEGACY_BOTS row — it may have been resurrected")


def test_no_living_book_is_exempt():
    """The assertion that stops the (gr) near-miss from recurring. A LIVING book
    must never appear in the exemption set, however it was derived."""
    for live in PRICE_BOOKS + list(FUNDING_BOOKS):
        assert live not in RETIRED_EXEMPT, (
            f"{live} is a LIVING book and must never be exempt from exit "
            "telemetry — this is exactly the false positive a substring match "
            "from row name to LEGACY_BOTS produced for funding_carry_bot")


def test_no_bot_has_prices_in_scope_and_omits_them():
    """THE GENERAL GUARD. Six of the eight defects were exactly this shape: a
    `_record_close(bot, coin, ent_px, ent_ts, exit_px, ...)` that used the
    prices to compute `pnl_pct` and then did not forward them. Any function
    holding an obvious entry AND exit price parameter, which publishes a paper
    trade, must pass them (or the funding fields, for a funding book)."""
    offenders = []
    for py in sorted(_ROOT.glob("*.py")):
        if py.stem in FUNDING_BOOKS or py.stem in RETIRED_EXEMPT:
            continue                      # funding-graded above / never trades again
        try:
            src = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "publish_paper_trade" not in src:
            continue
        try:
            tree = ast.parse(src)
        except SyntaxError:
            continue
        for call in _publish_calls(py.stem):
            fn = _enclosing_fn(tree, call)
            if fn is None:
                continue
            params = {a.arg for a in fn.args.args}
            has_entry = params & {"ent_px", "entry", "entry_px", "entry_price"}
            has_exit = params & {"exit_px", "exit_price", "px"}
            if has_entry and has_exit and not (
                    {"entry_price", "exit_price"} <= _kwargs(call)):
                offenders.append(f"{py.name}:{call.lineno} in {fn.name}() "
                                 f"(has {sorted(has_entry | has_exit)})")
    assert not offenders, (
        "these publish a close while holding the prices in scope:\n  "
        + "\n  ".join(offenders)
        + "\nThe pipe is built end to end; leaving the tap shut makes the "
          "book's exit unfalsifiable.")
