"""🎯 Perp Sniper: source-stamped close tags — the (ga) experiment made falsifiable.

[2026-08-04] The sniper admits candidates from THREE sources (`new_listings`
market-set diff, `surge_candidates`, `young_candidates`) and every close used
to land in ONE undifferentiated bucket: 9/9 lifetime exits read `long_max_hold`
and nothing could say WHICH source supplied them. The (ga) widening — surge +
young sources added precisely because the listing trigger was unobservable —
was therefore unfalsifiable: the brain's by_tag buckets, the go-live grader and
`study_exit_attribution` all pooled three hypotheses into one row.

THE FIX, the taker's lens pattern: `close_reason()` stamps the admission source
into the close tag (`long-young_max_hold`, `long-surge_tp`, `long-listing_sl`),
recorded per-symbol in `entry_src` at snipe time, persisted beside `entry_ts`,
consumed (popped) at the close. FORWARD-ONLY: an unknown source — a position
opened before the stamp shipped, a landed-but-unacked order folded in as held,
junk restored from state — degrades to the historical `long_<exit>` tag, never
to a guessed source (the (ht) rule).

Tested against the REAL consumers ((hj): a consumer is tested against a payload
its publisher built): the composed tag goes through `bot_pnl_store.split_reason`
(the ONE parser every ledger row passes) and `bot_learn._trade_side` — not
through hand-written expectations of what those functions "should" return.
"""
import pathlib

import pytest

import bot_learn
import bot_pnl_store as store
import lighter_perp_sniper as sniper

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
_SRC = (_ROOT / "lighter_perp_sniper.py").read_text()


# --------------------------------------------------------------------------
# 1. The tag round-trips through the real parser, per source, distinctly.
# --------------------------------------------------------------------------

def test_each_source_yields_a_distinct_brain_bucket():
    """The whole point: three sources, three enter_tags. If two sources ever
    compose to the same tag the experiment collapses back into one bucket."""
    tags = {}
    for src in sniper.SNIPE_SOURCES:
        reason = sniper.close_reason(True, "max_hold", src)
        enter_tag, exit_reason = store.split_reason(reason)
        assert exit_reason == "max_hold", (src, reason, exit_reason)
        assert enter_tag and enter_tag.startswith("long-"), (src, enter_tag)
        tags[src] = enter_tag
    assert len(set(tags.values())) == len(sniper.SNIPE_SOURCES), tags


def test_the_exit_with_its_own_underscore_survives_the_split():
    """`max_hold` contains an underscore; split_reason partitions at the FIRST
    one. This is exactly the sniper's dominant exit (9/9 measured), so a wrong
    split here would mangle every row the stamp exists to differentiate."""
    enter_tag, exit_reason = store.split_reason(
        sniper.close_reason(True, "max_hold", "young"))
    assert (enter_tag, exit_reason) == ("long-young", "max_hold")


def test_source_names_are_underscore_free():
    """The split contract: composers keep the tag part underscore-free
    (split_reason docstring). A source named e.g. 'new_listing' would truncate
    to enter_tag='long-new' and exit='listing_max_hold'."""
    for src in sniper.SNIPE_SOURCES:
        assert "_" not in src, src


def test_the_brain_reads_the_correct_side_from_a_stamped_row():
    """Through bot_learn._trade_side exactly as the read path delivers the row:
    split_reason has already moved the prefix into enter_tag ((hj) — the 17-Jul
    incident was this exact seam misread). A wrong side does not lose a
    verdict, it INVERTS one."""
    for src in sniper.SNIPE_SOURCES:
        reason = sniper.close_reason(True, "max_hold", src)
        enter_tag, exit_reason = store.split_reason(reason)
        row = {"enter_tag": enter_tag, "exit_reason": exit_reason}
        assert bot_learn._trade_side(row) == "long", (src, row)
    # and the un-split HTTP shape (bot_trades carries the reason as stored)
    raw = {"enter_tag": None,
           "exit_reason": sniper.close_reason(True, "tp", "surge")}
    assert bot_learn._trade_side(raw) == "long", raw


# --------------------------------------------------------------------------
# 2. Unknown degrades to the OLD tag — never to a guess.
# --------------------------------------------------------------------------

def test_an_unknown_source_keeps_the_historical_tag():
    """Forward-only. Pre-stamp positions, lost-ack folds and junk state all
    close under `long_<exit>` — byte-identical to every row this book has ever
    written, so no retroactive bucket is invented."""
    assert sniper.close_reason(True, "max_hold", None) == "long_max_hold"
    assert sniper.close_reason(True, "tp", "not-a-source") == "long_tp"
    assert sniper.close_reason(False, "sl", "") == "short_sl"
    enter_tag, exit_reason = store.split_reason(
        sniper.close_reason(True, "max_hold", None))
    assert (enter_tag, exit_reason) == ("long", "max_hold")


def test_the_restore_whitelists_junk_sources():
    """A junk value restored from state must be DROPPED (degrade at close),
    not carried into a tag. The whitelist is SNIPE_SOURCES at the restore
    site."""
    i = _SRC.index('_saved.get("entry_src")')
    block = _SRC[max(0, i - 300):i + 300]
    assert "in SNIPE_SOURCES" in block, (
        "the entry_src restore no longer whitelists through SNIPE_SOURCES — "
        "junk state would compose a junk tag")


# --------------------------------------------------------------------------
# 3. The map is persisted, restored, and consumed — the full lifecycle.
# --------------------------------------------------------------------------

def _save_state_blocks():
    """EVERY save_state writer, not the first found (the half-fix trap the
    zombie-clock test documented)."""
    out, i = [], 0
    needle = "store.save_state(bot_id, {"
    while True:
        i = _SRC.find(needle, i)
        if i < 0:
            break
        out.append(_SRC[i:i + 3600])
        i += len(needle)
    return out


def test_EVERY_save_site_persists_the_source_map():
    """Both writers write the same shape ((ha)). A restart that dropped the
    map would close every held position un-stamped and silently un-grade the
    sources mid-experiment."""
    blocks = _save_state_blocks()
    assert len(blocks) >= 2, f"expected >=2 save sites, found {len(blocks)}"
    for n, b in enumerate(blocks):
        assert '"entry_src"' in b, (
            f"save site #{n + 1} does not persist entry_src — a restart would "
            "strip the stamp off every open position")


def test_the_close_site_consumes_the_source():
    """record_close must pop the symbol's source into close_reason — recorded
    but never consumed is this repo's signature failure (saved-but-never-read).
    Pop, not get: one close consumes the record, same lifecycle as entry_ts."""
    assert "close_reason(was_long, reason, entry_src.pop(coin, None))" in _SRC, (
        "the ledger write no longer routes through close_reason with the "
        "popped entry_src — the stamp is inert at exactly the site it exists "
        "for")


def test_snipe_success_records_the_source():
    """The write half: open_snipe stores the admitting source on success, and
    only a whitelisted one."""
    i = _SRC.index("def open_snipe")
    block = _SRC[i:_SRC.index("def ", i + 10)]
    assert "entry_src[sym] = src" in block, "open_snipe never records the source"
    j = block.index("entry_src[sym] = src")
    assert "in SNIPE_SOURCES" in block[max(0, j - 200):j], (
        "the snipe-time write is no longer whitelisted")


def test_the_source_map_reaches_run_snipe_pass():
    """The plumbing: each pass builds a per-symbol source map (listing wins a
    tie — it is tried first, so it is the source that actually admitted the
    symbol) and try_snipe forwards it. Without this, open_snipe's src is
    always None and every tag silently degrades."""
    assert 'src=_src_map.get(s)' in _SRC, (
        "try_snipe no longer forwards the admission source")
    i = _SRC.index("_src_map = {")
    block = _SRC[i:i + 400]
    assert '"listing"' in block and "setdefault" in block, block


# --------------------------------------------------------------------------
# [2026-08-13 (lk)] The surge + young sources screen instrument class.
# Era-measured on this book's own ledger: non-crypto surge −$5.01/13 and
# young −$1.19/2 vs crypto +$1.13/5 across sources; every surge close exits
# `max_hold` ((gt): the tp/sl are unreachable literals), so a surge-long on
# an FX cross or ETF is a timer-held drift bet on an instrument whose venue
# volume event is its UNDERLYING's market event. The LISTING source is
# deliberately unscreened (n=1, +$0.28 — unmeasured, and the founding
# thesis). Offline, `fleet_bus.is_crypto` runs its hand-list fallback, which
# carries WTI/USDKRW/BOTZ — the measured losers' own class.
# --------------------------------------------------------------------------

def _surge_rows(*syms, ratio=9.0):
    return [{"sym": s, "ratio": ratio} for s in syms]


def test_surge_screens_noncrypto_and_does_not_burn_limit_slots():
    out = sniper.surge_candidates(
        _surge_rows("WTI", "USDKRW", "KAITO"), 2.0, set(), limit=1)
    assert out == ["KAITO"], (
        "a screened symbol must neither pass nor consume the limit slot")


def test_young_screens_noncrypto():
    bars = {"BOTZ": 3, "NEWCOIN": 4}
    vols = {"BOTZ": 9.0, "NEWCOIN": 9.0}
    out = sniper.young_candidates(bars, 21, vols, 1.0, set(), 4)
    assert out == ["NEWCOIN"], out


def test_the_screen_is_reversible_without_a_deploy(monkeypatch):
    monkeypatch.setattr(sniper, "ALLOW_NONCRYPTO", True)
    assert sniper.surge_candidates(_surge_rows("WTI"), 2.0, set()) == ["WTI"]
    assert sniper.young_candidates({"BOTZ": 3}, 21, {"BOTZ": 9.0},
                                   1.0, set(), 4) == ["BOTZ"]


def test_a_missing_fleet_bus_fails_open(monkeypatch):
    """An import regression must not shrink the book's universe."""
    monkeypatch.setattr(sniper, "fleet_bus", None)
    assert sniper.surge_candidates(_surge_rows("WTI"), 2.0, set()) == ["WTI"]


def test_an_injected_predicate_overrides_the_default():
    out = sniper.surge_candidates(_surge_rows("AAA", "BBB"), 2.0, set(),
                                  class_ok=lambda s: s == "BBB")
    assert out == ["BBB"], out
    out = sniper.young_candidates({"AAA": 2, "BBB": 3}, 21,
                                  {"AAA": 9.0, "BBB": 9.0}, 1.0, set(), 4,
                                  class_ok=lambda s: s == "AAA")
    assert out == ["AAA"], out
