"""[(lj)] /bus.json's three key lists must AGREE, as sets.

THE CLASS THIS CLOSES. `/bus.json` names its bot_state keys in three separate
places inside one handler: the live `SELECT ... WHERE bot IN (...)`, the
history `SELECT ... WHERE key IN (...)`, and the output dict of
`live.get("...")` calls. Adding an organ means editing all three, and the
existing guards are per-key substring asserts —

    assert '"fleet_allocation": live.get("fleet-allocation")' in src

— which are only ever written for a key someone already remembered. They pin
the keys that are there; they are structurally unable to notice a NEW key that
is fetched and never served, or served and never fetched. That is exactly how
`golive-docket-seen` sat unserved: (lf) split the docket's clocks into their own
key, the grader published them, and no review seat off Railway could read them,
because nothing compared the lists to each other.

Both directions are real failures, and they fail DIFFERENTLY:
  * fetched, not served  — the row is loaded and silently dropped. Invisible.
  * served, not fetched  — `live.get(k)` returns None forever, so the field is
    present and permanently null. A consumer cannot tell that from "the organ
    is dark", which is the (kw) receipt problem one endpoint over.

This is a set relationship between two lists extracted from the code, not an
assertion that a name appears somewhere — the mutation "add a key to the SQL
and forget the dict" is caught, which is the mutation that actually happens.
"""
import ast
import pathlib
import re

import pytest

pytestmark = pytest.mark.autonomy

SRC = pathlib.Path(__file__).resolve().parents[2] / "pnl_dashboard.py"


def _bus_handler_node():
    """The `if self.path.startswith("/bus.json")` subtree, by AST.

    Scoped by AST rather than by slicing text: pnl_dashboard.py is ~300 KB with
    many `cur.execute` calls, and a text window would silently widen or narrow
    as the file moves.
    """
    tree = ast.parse(SRC.read_text())
    for node in ast.walk(tree):
        if not isinstance(node, ast.If):
            continue
        for sub in ast.walk(node.test):
            if isinstance(sub, ast.Constant) and sub.value == "/bus.json":
                return node
    raise AssertionError("could not find the /bus.json handler in pnl_dashboard.py")


def _sql_in_lists(node):
    """The bot_state key sets from each `cur.execute` SQL in the handler.

    Python folds implicit string concatenation at parse time, so each multi-line
    SQL literal arrives as ONE ast.Constant — the reason this reads cleanly.
    """
    out = []
    for sub in ast.walk(node):
        if not (isinstance(sub, ast.Call)
                and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "execute" and sub.args):
            continue
        arg = sub.args[0]
        if not (isinstance(arg, ast.Constant) and isinstance(arg.value, str)):
            continue
        sql = arg.value
        m = re.search(r"\b(?:bot|key)\s+IN\s*\((.*?)\)", sql, re.S)
        if m:
            out.append(set(re.findall(r"'([a-z0-9][a-z0-9-]*)'", m.group(1))))
    return out


def _served_keys(node):
    """Every key passed to `live.get(...)` in the handler's output dict."""
    served = set()
    for sub in ast.walk(node):
        if (isinstance(sub, ast.Call) and isinstance(sub.func, ast.Attribute)
                and sub.func.attr == "get"
                and isinstance(sub.func.value, ast.Name)
                and sub.func.value.id == "live"
                and sub.args and isinstance(sub.args[0], ast.Constant)):
            served.add(sub.args[0].value)
    return served


@pytest.fixture(scope="module")
def bus():
    node = _bus_handler_node()
    lists = _sql_in_lists(node)
    assert len(lists) >= 2, (
        "expected a live and a history IN-list in the /bus.json handler; "
        f"found {len(lists)} — the extractor has gone blind, which is worse "
        "than a failing assert because it would pass vacuously")
    # the live list is the larger one (history is a deliberate subset)
    live, hist = max(lists, key=len), min(lists, key=len)
    return {"live": live, "hist": hist, "served": _served_keys(node)}


def test_the_extractor_actually_found_keys(bus):
    """The empty-collection trap: every assertion below passes on empty sets.

    Without this, a regex that stops matching turns the whole file green.
    """
    assert len(bus["live"]) >= 20, bus["live"]
    assert len(bus["served"]) >= 20, bus["served"]
    assert "fleet-risk" in bus["live"] and "fleet-risk" in bus["served"]


def test_every_fetched_key_is_served(bus):
    """A key in the SQL but not in the output dict is loaded and dropped."""
    missing = bus["live"] - bus["served"]
    assert not missing, (
        "fetched by /bus.json and never served, so the row is read and "
        f"silently discarded: {sorted(missing)}")


def test_every_served_key_is_fetched(bus):
    """A key in the output dict but not the SQL is permanently null — and a
    consumer cannot distinguish that from a dark organ."""
    phantom = bus["served"] - bus["live"]
    assert not phantom, (
        "served by /bus.json but never fetched, so the field is present and "
        f"forever null: {sorted(phantom)}")


def test_the_history_list_is_a_subset_of_the_live_list(bus):
    """History for a key the endpoint does not serve live has no reader."""
    orphan = bus["hist"] - bus["live"]
    assert not orphan, (
        f"history fetched for keys that are never served live: {sorted(orphan)}")


def test_the_docket_clocks_are_reachable_off_railway(bus):
    """The specific case that motivated this file.

    (lf) moved the docket's authoritative clocks into their own bot_state key
    so a failed read would cost the clocks and never the grade. The grade's
    `docket_seen` is a MIRROR; the durable record is this key, and a review
    seat with no Railway login must be able to read it — otherwise
    `docket_valid` is a claim nobody can check.
    """
    import scripts.golive_readiness as GR
    assert GR.DOCKET_SEEN_KEY in bus["live"], (
        f"{GR.DOCKET_SEEN_KEY!r} is not on /bus.json's key list")
    assert GR.DOCKET_SEEN_KEY in bus["served"]
