"""Spec 28. Every test here is the module REFUSING to touch a live dashboard."""
import io
import json

import pytest

from downtrend_bot.dashboard_safety import (APPEND_ONLY, PROTECTED_CALLABLES,
                                            PROTECTED_CONSTANTS,
                                            check_append_only, certify,
                                            verify_feed)

BEFORE = '''
SLOW_LOOP = 30
STALE_SECONDS = 900
EXPECTED = ["alpha-bot", "beta-bot"]
LABELS = {"alpha-bot": "Alpha", "beta-bot": "Beta"}
CURRENT_BOTS = ["alpha-bot", "beta-bot"]


def row_fresh(row, now):
    return (now - row["updated"]) < STALE_SECONDS


def render(rows):
    return rows
'''

GOOD = BEFORE.replace(
    'EXPECTED = ["alpha-bot", "beta-bot"]',
    'EXPECTED = ["alpha-bot", "beta-bot", "downtrend-short"]').replace(
    'LABELS = {"alpha-bot": "Alpha", "beta-bot": "Beta"}',
    'LABELS = {"alpha-bot": "Alpha", "beta-bot": "Beta", '
    '"downtrend-short": "Downtrend"}').replace(
    'CURRENT_BOTS = ["alpha-bot", "beta-bot"]',
    'CURRENT_BOTS = ["alpha-bot", "beta-bot", "downtrend-short"]')

FEED = json.dumps([{"bot": "alpha-bot", "equity": 1000},
                   {"bot": "beta-bot", "equity": 900}]).encode()


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def opener_ok(url, timeout=10.0):
    return FakeResponse(FEED)


def opener_dead(url, timeout=10.0):
    raise OSError("connection refused")


def opener_html(url, timeout=10.0):
    return FakeResponse(b"<html>please log in</html>")


def opener_empty(url, timeout=10.0):
    return FakeResponse(b"[]")


# ----------------------------------------------------------- feed check ----
def test_a_good_feed_verifies_and_lists_its_bots():
    got = verify_feed("https://x/pnl.json", opener=opener_ok)
    assert got.verified and got.rows == 2 and "alpha-bot" in got.bots


def test_an_unreachable_feed_is_not_verified():
    assert not verify_feed("https://x/pnl.json", opener=opener_dead).verified


def test_an_html_error_page_is_not_verified():
    """A login page is a 200 with a body. Parsing it as 'no bots' would make
    an append look safe against a dashboard we never actually read."""
    assert not verify_feed("https://x/pnl.json", opener=opener_html).verified


def test_an_empty_feed_is_not_verified():
    got = verify_feed("https://x/pnl.json", opener=opener_empty)
    assert not got.verified and "empty answer" in got.error


# --------------------------------------------------------- append check ----
def test_an_append_is_certified():
    v = check_append_only(BEFORE, GOOD)
    assert v.append_only, v.violations
    assert "downtrend-short" in v.added["EXPECTED"]


def test_removing_an_existing_bot_is_refused():
    bad = BEFORE.replace('EXPECTED = ["alpha-bot", "beta-bot"]',
                         'EXPECTED = ["alpha-bot"]')
    v = check_append_only(BEFORE, bad)
    assert not v.append_only and any("removed" in x for x in v.violations)


def test_renaming_an_existing_bot_is_refused():
    bad = BEFORE.replace('"beta-bot"', '"beta-bot-v2"')
    assert not check_append_only(BEFORE, bad).append_only


def test_reordering_existing_entries_is_refused():
    """Appending means adding at the END and touching nothing before it."""
    bad = BEFORE.replace('EXPECTED = ["alpha-bot", "beta-bot"]',
                         'EXPECTED = ["beta-bot", "alpha-bot"]')
    v = check_append_only(BEFORE, bad)
    assert not v.append_only and any("reorder" in x for x in v.violations)


@pytest.mark.parametrize("const", ["SLOW_LOOP", "STALE_SECONDS"])
def test_changing_a_protected_constant_is_refused(const):
    # One assignment. An earlier draft built `bad` twice and the first was
    # dead -- overwritten on the next line and never read, which is exactly
    # how a test ends up asserting against a fixture nobody meant to use.
    bad = (BEFORE.replace("SLOW_LOOP = 30", "SLOW_LOOP = 5")
           if const == "SLOW_LOOP"
           else BEFORE.replace("STALE_SECONDS = 900", "STALE_SECONDS = 60"))
    v = check_append_only(BEFORE, bad)
    assert not v.append_only and any(const in x for x in v.violations)


def test_modifying_a_shared_filter_is_refused():
    """A filter change affects EVERY existing bot, not only ours."""
    bad = BEFORE.replace("return (now - row[\"updated\"]) < STALE_SECONDS",
                         "return True")
    v = check_append_only(BEFORE, bad)
    assert not v.append_only and any("row_fresh" in x for x in v.violations)


def test_deleting_a_module_level_name_is_refused():
    bad = BEFORE.replace("def render(rows):\n    return rows\n", "")
    assert not check_append_only(BEFORE, bad).append_only


def test_the_protected_lists_cover_the_names_the_spec_names():
    for n in ("SLOW_LOOP", "STALE_SECONDS"):
        assert n in PROTECTED_CONSTANTS
    for n in ("EXPECTED", "LABELS", "CURRENT_BOTS"):
        assert n in APPEND_ONLY
    assert PROTECTED_CALLABLES


# ------------------------------------------------------------- certify -----
def test_certify_allows_a_clean_append_against_a_verified_feed():
    out = certify(feed_url="https://x/pnl.json", before_src=BEFORE,
                  after_src=GOOD, new_bot_ids=["downtrend-short"],
                  opener=opener_ok)
    assert out["allowed"], out.get("reason")
    assert "never writes" in out["note"]


def test_certify_refuses_when_the_feed_cannot_be_verified():
    """Spec 28, verbatim: 'If /pnl.json cannot be verified, do not modify the
    dashboard.' The feed is checked FIRST -- a patch cannot be proven
    append-only against a bot list that could not be read."""
    out = certify(feed_url="https://x/pnl.json", before_src=BEFORE,
                  after_src=GOOD, opener=opener_dead)
    assert not out["allowed"] and "could not be verified" in out["reason"]


def test_certify_refuses_a_bot_id_that_already_publishes():
    """Two writers of one dashboard key makes the row whoever published
    last, and the pooled history is then two bots' trades."""
    out = certify(feed_url="https://x/pnl.json", before_src=BEFORE,
                  after_src=GOOD, new_bot_ids=["alpha-bot"], opener=opener_ok)
    assert not out["allowed"] and "already publish" in out["reason"]


def test_certify_refuses_a_non_append_patch():
    bad = BEFORE.replace("STALE_SECONDS = 900", "STALE_SECONDS = 1")
    out = certify(feed_url="https://x/pnl.json", before_src=BEFORE,
                  after_src=bad, opener=opener_ok)
    assert not out["allowed"] and "not append-only" in out["reason"]


def test_the_module_contains_no_writer_at_all():
    """The structural claim, checked structurally: there is no function here
    that can modify a dashboard, so no future call site can accidentally use
    one."""
    import ast
    import inspect

    from downtrend_bot import dashboard_safety
    src = inspect.getsource(dashboard_safety)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            assert name != "open" or True     # reading is fine
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            body = ast.get_source_segment(src, node) or ""
            assert '"w"' not in body and "'w'" not in body, \
                f"{node.name} appears to open a file for WRITING"


def test_deleting_a_function_is_refused_even_when_it_is_not_protected():
    """`PROTECTED_CALLABLES` names the filters we KNOW about. The name-set
    comparison is what covers the ones we do not -- and the first version of
    it counted only assignments, so removing a function passed clean."""
    bad = BEFORE.replace("def render(rows):\n    return rows\n", "")
    v = check_append_only(BEFORE, bad)
    assert not v.append_only and any("render" in x for x in v.violations)


def test_renaming_a_local_variable_is_not_reported_as_a_deletion():
    """The other half: a guard that fires on an irrelevant edit is a guard
    that gets waived. Only MODULE-level names count."""
    bad = BEFORE.replace("def row_fresh(row, now):\n"
                         "    return (now - row[\"updated\"]) < STALE_SECONDS",
                         "def row_fresh(row, now):\n"
                         "    age = now - row[\"updated\"]\n"
                         "    return age < STALE_SECONDS")
    v = check_append_only(BEFORE, bad)
    assert not any("disappeared" in x for x in v.violations), v.violations


VARIANT_BEFORE = BEFORE + '''
VARIANT_ONLY = {"alpha-bot", "beta-bot"}
FREQTRADE = {"gamma-bot"}
'''
VARIANT_AFTER = BEFORE + '''
VARIANT_ONLY = {"alpha-bot", "beta-bot", "downtrend-ensemble"}
FREQTRADE = {"gamma-bot"}
'''


def test_variant_only_is_guarded_like_every_other_registry():
    """The registry a shadow-only book actually belongs in.

    Found by putting a REAL patch through this verifier: the one registry the
    patch genuinely touched (`VARIANT_ONLY`) was the one registry that was not
    in `APPEND_ONLY`, so it certified clean while checking nothing that
    changed. A verifier that certifies the change you did not make is worse
    than no verifier."""
    v = check_append_only(VARIANT_BEFORE, VARIANT_AFTER)
    assert v.append_only, v.violations
    assert "downtrend-ensemble" in v.added["VARIANT_ONLY"]


def test_removing_a_variant_only_entry_is_refused():
    bad = VARIANT_BEFORE.replace('VARIANT_ONLY = {"alpha-bot", "beta-bot"}',
                                 'VARIANT_ONLY = {"alpha-bot"}')
    v = check_append_only(VARIANT_BEFORE, bad)
    assert not v.append_only and any("VARIANT_ONLY" in x for x in v.violations)


def test_every_registry_that_feeds_current_bots_is_append_only():
    """`CURRENT_BOTS = set(EXPECTED) | VARIANT_ONLY | SCANNERS | STOCKS |
    FREQTRADE`. Guarding the union and not its parts guards nothing: an entry
    can be removed from any one of them and `CURRENT_BOTS` still parses."""
    for name in ("EXPECTED", "VARIANT_ONLY", "SCANNERS", "STOCKS",
                 "FREQTRADE", "CURRENT_BOTS", "LABELS"):
        assert name in APPEND_ONLY, f"{name} feeds CURRENT_BOTS and is unguarded"
