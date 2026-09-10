"""[2026-09-10 (zu)] THE WEEK'S TELEMETRY REACHES THE CARD — AND EVERY KEY IT
READS IS PINNED TO THE PUBLISHER THAT EMITS IT.

WHY THIS FILE EXISTS. In the week to 10-Sep the books started publishing the
numbers doctrine had been asking for — a per-book random-entry CONTROL ARM
((zc)/(zb)), the I22 SPEND census, the LEVERAGE block with its vol target and
all-slots-stop arithmetic ((yz)/(yp)), the judge's LEVER SURFACE ((yg)/(zj)),
🎫 the taker's GATE CENSUS ((xs)), the entry-veto ledger with its 30-day
lockout cost ((vm)/(xg)), the measured stop OVERSHOOT ((xp)) — and the operator
card rendered every one of them as one 900-character line of
`leverage: {'mmf': 0.2, 'set': 5.0, …}` in the raw `extra` dump. That is the
`class_split` rule going unserved at the reporting layer: *a number a decision
depends on must be READABLE, not recomputable.*

THE FAILURE MODE THIS FILE IS POINTED AT is not "the row looks ugly". It is
`.get()` returning None forever. A consumer reading a key its publisher does
not emit raises nothing, logs nothing and renders nothing — and on this
surface "renders nothing" is indistinguishable from "the book has no
leverage", which is why the fleet has already paid for this class four times
in one day ((hj)) and again at (yq)/(uy). So:

  * every key each `_t_*` renderer reads is extracted FROM ITS OWN AST and
    required to be a subset of the keys extracted from the PUBLISHER's AST —
    a rename on either side reddens, and nothing here restates a contract;
  * every extractor carries a POSITIVE CONTROL, because an extractor that
    finds nothing makes `read <= emitted` vacuously true (the "a check that
    inspects nothing reports clean" class);
  * the fixtures' KEY NAMES come from the publisher too, so a fixture cannot
    quietly test a shape production never emits.

AND ONE FINDING WORTH THE FILE ON ITS OWN: **Postgres `jsonb` sorts object
keys by (length, bytes)**, so the taker's deliberately gate-ORDERED census
(`(xs)`: *"read them in gate order … the first large counter names the binding
gate"*) arrives scrambled — measured on the live payload as
`no_mark, tickets_in, coin_vetoed, …`. The instruction `(xs)` shipped is
unfollowable from the payload, and reading `items[0]` gets the SHORTEST key
rather than the denominator. The order is therefore DECLARED in the card and
pinned here, in order, against the bot's own literal.
"""
import ast
import html as _h
import pathlib
import re
import sys

import pytest

pytestmark = pytest.mark.autonomy

_ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import pnl_dashboard as dash          # noqa: E402


# --------------------------------------------------------------------------
# publisher-side extraction — three shapes, because the fleet builds payload
# blocks three ways and a single strategy would silently find nothing on two
# of them (which is the vacuous-guard failure, not a clean bill).
# --------------------------------------------------------------------------
def _tree(mod):
    return ast.parse((_ROOT / mod).read_text(encoding="utf-8"))


def _str_keys(nodes):
    return {n.value for n in nodes
            if isinstance(n, ast.Constant) and isinstance(n.value, str)}


def _keys_in(node):
    """String keys from dict literals AND `x["k"] = …` targets inside `node`.

    The subscript half is load-bearing: `progression_block` and `lever_surface`
    build `out` incrementally, so a dict-literal-only scan returns almost
    nothing for them and every subset assertion passes vacuously."""
    ks = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Dict):
            ks |= _str_keys([k for k in n.keys if k is not None])
        targets = (n.targets if isinstance(n, ast.Assign)
                   else [n.target] if isinstance(n, ast.AugAssign) else [])
        for t in targets:
            if (isinstance(t, ast.Subscript) and isinstance(t.slice, ast.Constant)
                    and isinstance(t.slice.value, str)):
                ks.add(t.slice.value)
    return ks


def pub_from_func(mod, name):
    """Keys built inside a named builder function (docstring excluded — prose
    is not a contract, and a docstring scan is how (po)'s substring class
    keeps recurring)."""
    fns = [n for n in ast.walk(_tree(mod))
           if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
           and n.name == name]
    assert fns, f"{name}() not found in {mod} — the extractor is aimed at nothing"
    ks = set()
    for f in fns:
        body = f.body
        if (body and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)):
            body = body[1:]
        for stmt in body:
            ks |= _keys_in(stmt)
    return ks


def pub_from_nested(mod, block):
    """Keys of every dict literal that is the VALUE of `"<block>": {...}` —
    the shape the live hosts use when they build a block inline in the
    publish call."""
    ks = set()
    for n in ast.walk(_tree(mod)):
        if not isinstance(n, ast.Dict):
            continue
        for k, v in zip(n.keys, n.values):
            if (isinstance(k, ast.Constant) and k.value == block
                    and isinstance(v, ast.Dict)):
                ks |= _str_keys([c for c in v.keys if c is not None])
    return ks


def pub_from_var(mod, name):
    """Keys of a `<name> = {...}` module/function-level dict literal — the
    taker's two censuses, which are seeded once and incremented at each gate."""
    ks = set()
    for n in ast.walk(_tree(mod)):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    ks |= _str_keys([c for c in n.value.keys if c is not None])
    return ks


def pub_var_order(mod, name):
    """The DECLARED ORDER of a `<name> = {...}` literal. Only order-bearing
    extractor here, and it exists for exactly one reason — see the jsonb note
    in this module's docstring."""
    for n in ast.walk(_tree(mod)):
        if isinstance(n, ast.Assign) and isinstance(n.value, ast.Dict):
            for t in n.targets:
                if isinstance(t, ast.Name) and t.id == name:
                    return tuple(c.value for c in n.value.keys
                                 if isinstance(c, ast.Constant)
                                 and isinstance(c.value, str))
    return ()


LIVE_HOST = "lighter_avo_live_bot.py"
FAMILY = "lighter_family_bot.py"
TAKER = "lighter_ticket_taker.py"
KELLY = "lighter_band_kelly_bot.py"
VENUE = "venues/lighter_client.py"

#: renderer -> (its parameter name, the publisher's key set). One row per
#: structured block the card renders. `min_keys` is the POSITIVE CONTROL: an
#: extractor that silently found nothing makes the subset check vacuous.
BLOCKS = {
    "_t_control":        ("control", lambda: pub_from_func(FAMILY, "control_block"), 6),
    "_t_spend":          ("spend", lambda: (pub_from_nested(LIVE_HOST, "spend")
                                            | pub_from_nested(FAMILY, "spend")), 7),
    "_t_leverage":       ("leverage", lambda: pub_from_nested(LIVE_HOST, "leverage"), 15),
    "_t_progression":    ("progression",
                          lambda: pub_from_func(LIVE_HOST, "progression_block"), 8),
    "_t_stop_overshoot": ("stop_overshoot",
                          lambda: pub_from_nested(LIVE_HOST, "stop_overshoot"), 4),
    "_t_entry_vetoes":   ("entry_vetoes",
                          lambda: pub_from_nested(LIVE_HOST, "entry_vetoes"), 15),
    "_t_levers":         ("levers", lambda: pub_from_func(FAMILY, "lever_surface"), 5),
    "_t_margin":         ("margin",
                          lambda: pub_from_func(VENUE, "margin_state_from"), 10),
    "_t_holdwatch":      ("holdwatch",
                          lambda: pub_from_func(KELLY, "holdwatch_block"), 6),
}


def _reader_keys(fn_name, param):
    """`param.get("literal")` reads inside one renderer, receiver scoped to the
    BARE parameter name.

    The scoping is load-bearing (the (uy) lesson): `(x.get("a") or {}).get("b")`
    has a BoolOp receiver and is a SUB-dict read, not a key of this block.
    Pooling them makes the guard cry wolf on every nested field, and a guard
    that cries wolf gets exempted and then guards nothing."""
    fns = [n for n in ast.walk(_tree("pnl_dashboard.py"))
           if isinstance(n, ast.FunctionDef) and n.name == fn_name]
    assert fns, f"{fn_name} is gone from pnl_dashboard"
    ks = set()
    for n in ast.walk(fns[0]):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                and n.func.attr == "get"
                and isinstance(n.func.value, ast.Name)
                and n.func.value.id == param
                and n.args and isinstance(n.args[0], ast.Constant)
                and isinstance(n.args[0].value, str)):
            ks.add(n.args[0].value)
    return ks


@pytest.mark.parametrize("fn_name", sorted(BLOCKS))
def test_every_key_the_card_reads_is_one_its_publisher_emits(fn_name):
    """THE LOAD-BEARING TEST. A consumer reading a key its publisher does not
    emit renders nothing, forever, in silence."""
    param, pub_fn, min_keys = BLOCKS[fn_name]
    emitted = pub_fn()
    assert len(emitted) >= min_keys, (
        f"publisher extractor for {fn_name} found only {sorted(emitted)} — "
        f"it is inspecting nothing, which makes the subset check below "
        f"vacuously true")
    read = _reader_keys(fn_name, param)
    assert read, f"{fn_name} reads no key off `{param}` — is it still wired?"
    missing = read - emitted
    assert not missing, (
        f"{fn_name} reads {sorted(missing)} off `{param}`, which no publisher "
        f"emits. `.get()` returns None silently, so this renders nothing "
        f"forever. Publisher keys: {sorted(emitted)}")


def test_the_extractors_are_aimed_at_different_functions():
    """A pooling extractor is still non-empty, so non-emptiness is not proof.
    Two renderers reading different blocks must yield DISJOINT key sets."""
    lev = _reader_keys("_t_leverage", "leverage")
    prog = _reader_keys("_t_progression", "progression")
    assert lev and prog
    assert not (lev & prog), (
        "the reader extractor is pooling across functions — it would pass "
        "against a consumer reading anything at all")


# --------------------------------------------------------------------------
# the jsonb ordering hazard
# --------------------------------------------------------------------------
def test_the_taker_gate_order_matches_the_publishers_own_literal():
    """The card DECLARES the gate order because the payload cannot carry it.

    Pinned in ORDER, not as a set: `(xs)` built the census so that reading it
    top-to-bottom names the binding gate, and Postgres `jsonb` destroys that
    order on write. A new gate, a renamed one or a reordered one must redden
    here rather than silently mis-report which gate binds."""
    published = pub_var_order(TAKER, "gate_census")
    assert len(published) >= 12, (
        f"gate_census literal not found in {TAKER} (got {published!r})")
    assert tuple(dash.TAKER_GATE_ORDER) == published, (
        "TAKER_GATE_ORDER has drifted from the bot's own gate_census literal.\n"
        f"  card: {tuple(dash.TAKER_GATE_ORDER)}\n"
        f"  bot : {published}")
    assert published[0] == "tickets_in", (
        "the first counter is the DENOMINATOR — the whole census is read "
        "against it")


def test_the_gate_census_is_read_by_name_never_by_position():
    """The defect this closes, measured: `items[0]` on the live payload
    returned `no_mark`, because jsonb had sorted the shortest key to the
    front. Reading by position is the bug; reading by declared name is the
    fix, and this pins that it cannot come back."""
    fn = next(n for n in ast.walk(_tree("pnl_dashboard.py"))
              if isinstance(n, ast.FunctionDef) and n.name == "_t_gate_census")
    for n in ast.walk(fn):
        if isinstance(n, ast.Subscript) and isinstance(n.value, ast.Name):
            assert n.value.id != "items", (
                "_t_gate_census indexes a positional list again — jsonb "
                "sorts object keys by length, so position is not gate order")
    src = ast.unparse(fn)
    assert "TAKER_GATE_ORDER" in src, (
        "_t_gate_census no longer reads the declared order")


def test_a_census_counter_the_declaration_misses_is_shown_not_dropped():
    """I8: unknown degrades to honest, never to a guess. A gate the bot grows
    and this card has not learned about must still appear."""
    census = {"tickets_in": 9, "lens_vetoed": 2, "brand_new_gate": 4}
    out = dash._t_gate_census(census, None)
    assert out is not None
    assert "brand_new_gate" in out and "4" in out
    assert "?" in out, "an undeclared counter must be marked as unrecognised"


def test_a_census_with_no_denominator_renders_nothing():
    assert dash._t_gate_census({"lens_vetoed": 3}, None) is None
    assert dash._t_gate_census({"tickets_in": "nine"}, None) is None


# --------------------------------------------------------------------------
# fail-safety: dark is not zero, and a block that did not render stays visible
# --------------------------------------------------------------------------
@pytest.mark.parametrize("fn_name", sorted(BLOCKS))
def test_an_empty_or_junk_block_renders_nothing(fn_name):
    """`0` and `green` are REAL everyday readings on this fleet, so a missing
    source coerced into either is a confident wrong answer. Every renderer
    must decline instead."""
    fn = getattr(dash, fn_name)
    n_args = fn.__code__.co_argcount
    for payload in ({}, {"unrelated": None}, {"n": None, "set": None}):
        assert fn(*([payload] + [None] * (n_args - 1))) is None, (
            f"{fn_name} rendered something from {payload!r}")


def test_a_block_that_did_not_render_stays_in_the_raw_dump():
    """The consumed contract: telemetry_rows may only hide what it SHOWED, and
    it reports that per SUB-KEY, not per block."""
    rows, used = dash.telemetry_rows({
        "leverage": {"set": 5.0},                  # renders
        "stop_overshoot": {"nonsense": 1},         # does NOT render
    })
    assert any("Leverage" in r for r in rows)
    assert "set" in used.get("leverage", set())
    assert "stop_overshoot" not in used, (
        "a block that rendered nothing was hidden from the raw dump — the "
        "reader then has no way to see a shape this code cannot read")


def test_a_summary_never_deletes_the_detail_it_summarised():
    """THE REGRESSION THIS FILE'S OWN CHANGE INTRODUCED, now pinned.

    The first cut rendered 8 of `leverage`'s 26 fields and marked the WHOLE
    key consumed — so the daily-loss halt geometry, the ruin gate's verdict,
    the MEASURED all-slots stop and the held-basket liquidation gap dropped off
    a page they had been visible on. A summary that deletes its own detail is
    strictly worse than the wall of text it replaced."""
    payload = {"leverage": {"set": 5.0, "never_rendered_field": 7,
                            "another_one": {"deep": 1}}}
    rows, used = dash.telemetry_rows(payload)
    assert any("Leverage" in r for r in rows)
    shown = used["leverage"]
    assert "set" in shown and "never_rendered_field" not in shown

    out = dash.card("x-lshadow", {"status": "online", "updated_at": None,
                                  "equity": 1000.0, "extra": payload})
    assert "never_rendered_field" in out, (
        "a published field no row rendered was hidden from the raw dump")
    assert "another_one" in out
    assert "'set': 5.0" not in out, "the rendered field was also dumped raw"


def test_the_subkey_extractor_is_not_silently_empty():
    """POSITIVE CONTROL. An empty read-set consumes nothing, so the page just
    degrades — which is the safe direction and therefore an invisible failure.
    It is exactly how the first cut shipped dead: `ast` was not imported and a
    bare `except Exception` turned the NameError into a no-op."""
    got = dash._reader_subkeys("_t_leverage", "leverage")
    assert len(got) >= 8, f"extractor found only {sorted(got)}"
    assert "set" in got and "all_slots_stop_pct" in got
    assert not dash._reader_subkeys("_t_leverage", "not_a_param")


def test_the_daily_halt_geometry_reaches_the_card():
    """`leverage.halt` is the rail that stops a REAL-MONEY book for the rest of
    the UTC day, published by both live rows and read by nothing."""
    out = dash._t_halt({"abs_usd": 105.0, "binding": "abs",
                        "daily_loss_frac": 0.2,
                        "basket_move_now_pct": 0.1514,
                        "basket_move_now_state": "measured",
                        "basket_move_at_full_gross_pct": 0.04})
    assert "$105" in out and "binds" in out
    assert "15.1%" in out, "the distance to the halt is the whole point"
    rows, used = dash.telemetry_rows({"leverage": {"set": 5.0, "halt": {
        "abs_usd": 105.0, "binding": "abs", "daily_loss_frac": 0.2}}})
    assert any("Daily halt" in r for r in rows)
    assert "halt" in used["leverage"]


def test_an_unpriced_ruin_gate_is_not_rendered_as_danger():
    """`headroom` reads `{ok: false, reason: "liq_unpriced"}` on BOTH live
    rows: the venue quotes no liquidation for those legs, so the gate has no
    measurement. UNPRICED is not BLOCKED — rendering it red would be a
    permanent false alarm, which is how an operator learns to ignore one."""
    unpriced = dash._t_leverage({"set": 5.0, "headroom": {
        "ok": False, "reason": "liq_unpriced"}})
    assert "UNPRICED" in unpriced and "BLOCKED" not in unpriced
    blocked = dash._t_leverage({"set": 5.0, "headroom": {
        "ok": False, "reason": "stop_inside_liq"}})
    assert "BLOCKED" in blocked
    assert "ruin gate ✓" in dash._t_leverage({"set": 5.0,
                                              "headroom": {"ok": True}})


def test_the_measured_all_slots_stop_is_shown_beside_the_modelled_one():
    """(xp): the modelled figure prices every stop AT its level; mum's own
    fills land past it, and the publisher ships the measured number."""
    out = dash._t_leverage({"set": 5.0, "all_slots_stop_pct": 0.20,
                            "all_slots_stop_pct_measured": 0.226})
    assert "all-slots stop 20%" in out and "measured 22.6%" in out


def test_a_stop_dead_on_the_universe_but_live_on_the_held_basket_says_so():
    out = dash._t_leverage({"set": 5.0, "stop_reachable": False,
                            "stop_dead_above": 4.17,
                            "stop_reachable_held": True,
                            "stop_dead_above_held": 11.11})
    assert "HELD basket" in out and "stop DEAD" not in out


def test_a_mixed_held_map_never_fabricates_a_tag():
    """One coin's tag attributed to an untagged coin is a fabricated claim
    about which strategy opened a position."""
    out = dash._t_held({"AAVE": "oversold-rebound", "SPY": None})
    assert "AAVE" in out and "SPY" in out
    assert out.count("oversold-rebound") == 1


def test_every_slot_throttle_is_rendered():
    """(uo): the census exists to say WHICH constraint binds — a cap, a
    per-lens throttle, or a coin already held."""
    out = dash._t_gate_census({"tickets_in": 20},
                              {"offered": 9, "opened": 1, "slots_full": 3,
                               "lens_once": 4, "held_sym": 2})
    for needle in ("slots full ×3", "lens already taken ×4", "already held ×2"):
        assert needle in out, needle


def test_an_old_payload_without_shut_now_is_not_a_green_all_clear():
    old = dash._t_entry_vetoes({"coin_veto": {"AI": "slip"}})
    assert "unreported" in old and ">open<" not in old
    fresh = dash._t_entry_vetoes({"shut_now": None, "coin_veto": {}})
    assert "open" in fresh


def test_a_vetoed_lens_with_no_era_sample_still_appears():
    out = dash._t_lens_evidence(
        {"breakoutup": {"n": 161, "t": 3.0, "mean_pct": 1.549}},
        ["dip", "divergence"])
    assert "dip" in out and "divergence" in out
    assert "no era sample" in out


def test_the_card_hides_exactly_what_it_rendered():
    """End to end through `card()`: a rendered block leaves the raw dump, an
    unrendered one stays in it."""
    row = {"status": "online", "updated_at": None, "equity": 1000.0,
           "extra": {"leverage": {"set": 4.0}, "weird_block": {"a": 1}}}
    out = dash.card("freqtrade-mum-lshadow", row)
    assert "4× set" in out
    assert "weird_block" in out, "an unrecognised block must stay visible"
    assert "'set': 4.0" not in out, "the rendered block was dumped raw as well"


def test_a_partly_rendered_caps_block_is_not_hidden():
    """`caps` mixes scalars with nested sleeves (🌾 carry's `cost_bps`, 🪁
    kelly's `dip`). The scalars render; the key stays in the raw dump because
    the nested part did not."""
    rows, used = dash.telemetry_rows(
        {"caps": {"enter_apr": 0.2, "cost_bps": {"n": 23}}})
    assert any("Caps" in r for r in rows)
    assert used["caps"] == {"enter_apr"}, (
        "the nested sleeve must stay in the dump")
    rows2, used2 = dash.telemetry_rows({"caps": {"enter_apr": 0.2, "k": 5}})
    assert used2["caps"] == {"enter_apr", "k"}, (
        "an all-scalar caps block IS fully rendered")


def test_a_volume_floor_does_not_render_in_exponent_notation():
    r, _full = dash._t_caps({"min_vol": 1000000.0, "k": 5})
    assert "1,000,000" in r and "1e+06" not in r


# --------------------------------------------------------------------------
# units — the publisher's units, not the reader's guess
# --------------------------------------------------------------------------
def test_a_fractional_stop_is_rendered_as_a_percent():
    """`all_slots_stop_pct` is a FRACTION (0.20 = 20%) — it is `gross_x *
    |stoploss|` at the publisher. Rendering it raw prints "all-slots stop
    0.2%" for a book risking a fifth of the account."""
    out = dash._t_leverage({"set": 5.0, "all_slots_stop_pct": 0.20,
                            "all_slots_stop_over_bar_pp": 5.0})
    assert "all-slots stop 20%" in out
    assert "over the bar" in out, "past the 15% gate bar and it did not say so"


def test_the_liquidation_distance_reads_the_publishers_own_field():
    """`margin_state_from` emits `nearest_liq = {"coin", "dist_frac", …}` and
    says in its own source that this is a FRACTION, not `dist_pct`. Reading it
    as a number returns None on every populated payload; rendering it without
    the ×100 turns a 30%-away liquidation into "0.3%" — imminent."""
    assert "dist_frac" in pub_from_func(VENUE, "margin_state_from")
    out = dash._t_margin({"mode": "cross", "gross": 700.0, "leverage": 1.3,
                          "nearest_liq": {"coin": "BTC", "dist_frac": 0.3042}})
    assert "30.4%" in out and "BTC" in out
    assert "0.3%" not in out
    dark = dash._t_margin({"mode": "cross", "gross": 700.0, "leverage": 1.3,
                           "nearest_liq": None, "liq_unknown": ["A", "B"]})
    assert "unpriced" in dark and "(2)" in dark


def test_a_control_arm_with_no_settled_pairs_is_not_an_edge_of_zero():
    """(I6) `n=0` is the arm RUNNING and not yet decided — never "edge 0.00%"."""
    out = dash._t_control({"n": 0, "null_n": 0, "mean_pct": None,
                           "null_pct": None, "edge_pct": None, "basis": "x"})
    assert "no edge yet" in out and "0.00%" not in out


# --------------------------------------------------------------------------
# escaping — payload strings are operator-visible and some are venue-supplied
# --------------------------------------------------------------------------
def test_payload_strings_cannot_break_out_of_the_markup():
    evil = '"><script>alert(1)</script>'
    outs = [
        dash._t_entry_vetoes({"shut_now": evil, "shut_reason": evil,
                              "coin_veto": {evil: evil}}),
        dash._t_levers({"prefix": evil, "registry": True, "registered_n": 0,
                        "consumable": [evil], "unregistered": [evil]}),
        dash._t_gate_census({"tickets_in": 3, evil: 2}, None),
        dash._t_held({evil: evil}),
        dash._t_caps({evil: evil})[0],
        dash._t_sources({evil: {"admitted": 0, "scan": "fresh"}},
                        {evil: evil}, {evil: "measured"}, {}),
    ]
    for out in outs:
        assert out is not None
        assert "<script>" not in out, f"unescaped payload string in: {out[:200]}"


# --------------------------------------------------------------------------
# the prose ratchet — numbers come from the publisher
# --------------------------------------------------------------------------
_SLOTS = re.compile(r"\d+\s*slots")
_CLIP = re.compile(r"\$\s?\d[\d,.]*\s*(?:×|x)\s*\d")

#: MEASURED 2026-09-10. Every entry is either a RETIRED book (its description
#: is history and I12 keeps history) or a 🏛️ Parliament book, which publishes
#: `params` but no `clip_usd`/`cap_usd`/`max_open` — so for those six the prose
#: is the ONLY place the size appears and deleting it would lose information.
#: A RATCHET, not a bar: this set may only SHRINK. A book that starts
#: publishing its units leaves it; a NEW description asserting a sizing number
#: fails immediately.
SIZING_CLAIM_BACKLOG = {
    "band-barnes", "crypto-breakout-4h", "crypto-intraday-15m",
    "crypto-swing-daily", "equities-momentum", "equities-regime",
    "freqtrade-dad", "freqtrade-georgia",
    "pm-abbott", "pm-albanese", "pm-gillard", "pm-morrison", "pm-rudd",
    "pm-turnbull",
}


def test_no_new_description_asserts_a_runtime_sizing_number():
    """(za)'s rule, made a ratchet: *the mechanism may be prose; the numbers
    come from the publisher.*

    Measured the day this shipped, on LIVING books: 👩 mum's REAL-MONEY card
    said "$50 × 4 slots" while she ran 12 slots at a $221.90 clip and 5× gross;
    🙏 avo's said "÷ 5 slots, levered 1.4×" against 6 slots at 2.0×; ⚖️
    Counterweight advertised the K=8 widening that was pre-registered-REVERTED
    five weeks earlier. A hardcoded number and a live one render identically,
    which is exactly why this needs a guard and not a habit."""
    offenders = {b for b, v in dash.DESCRIPTIONS.items()
                 if _SLOTS.search(v) or _CLIP.search(v)}
    new = offenders - SIZING_CLAIM_BACKLOG
    assert not new, (
        f"{sorted(new)} assert a sizing number in prose. Describe the "
        f"MECHANISM and let live_units render clip/cap/slots/gross from the "
        f"payload — prose can only ever drift from what the process runs.")
    stale = SIZING_CLAIM_BACKLOG - offenders
    assert not stale, (
        f"{sorted(stale)} were cleaned — remove them from "
        f"SIZING_CLAIM_BACKLOG so the ratchet cannot slip back")


def test_the_units_line_carries_the_gross_multiplier():
    """Since (sr) the clip is `equity × gross_x ÷ slots`, so `clip × slots` no
    longer says what a book has deployed — and gross_x is an operator env that
    moves with no code change."""
    assert "5× gross" in dash.live_units({"extra": {"gross_x": 5.0}})
    assert "gross" not in dash.live_units({"extra": {"gross_x": 1.0}}), (
        "an unlevered book must not grow a noise chip")
    assert "gross" not in dash.live_units({"extra": {"gross_x": True}}), (
        "a bool is not a multiplier")


def test_the_live_books_descriptions_no_longer_name_a_retired_arm():
    """🎫 the taker's card described the real-money policy of a live row
    RETIRED on 13-Aug, and 🌾 carry's named its HL arm, retired 17-Jul."""
    taker = dash.DESCRIPTIONS["lighter-ticket-taker"]
    assert "retired 13-Aug" in taker
    assert "DIVERGENCE-ONLY" not in taker
    assert "HL data" not in dash.DESCRIPTIONS["perps-funding-carry"]


def test_descriptions_hold_no_html_entities():
    """DESCRIPTIONS are escaped at render (`html.escape(_desc)`), so an entity
    typed here double-escapes and the operator reads a literal `&lt;`."""
    for base, v in dash.DESCRIPTIONS.items():
        assert not re.search(r"&(?:lt|gt|amp|quot|#\d+);", v), (
            f"DESCRIPTIONS[{base!r}] contains an HTML entity; write the raw "
            f"character — the renderer escapes it")


# --------------------------------------------------------------------------
# the ops strip: lead with the light the consumers actually enforce
# --------------------------------------------------------------------------
def _strip(monkeypatch, risk):
    monkeypatch.setattr(dash, "fetch_states",
                        lambda keys: {"fleet-risk": risk} if risk else {})
    monkeypatch.setattr(dash, "fetch_fleet_alerts", lambda hours=24: [])
    return dash.ops_strip_html()


_RISK = {
    "light": "yellow", "mode": "enforce",
    "long_positions": 15, "long_budget": 20,
    "short_positions": 0, "short_budget": 12,
    "fleet_equity": 3098.15, "fleet_dd_7d": -0.0345, "clip_scale": 1.0,
    "cohorts": {"live": {"long_positions": 9, "long_budget": 20,
                         "light": "green"},
                "shadow": {"long_positions": 14, "long_budget": 26,
                           "light": "green"}},
}


def test_the_strip_leads_with_the_enforced_cohort_light(monkeypatch):
    """MEASURED on the live payload: pooled YELLOW at 15L/20 while BOTH
    enforced cohorts read GREEN (live 9/20, shadow 14/26). `(wp)`/`(wy)` gave
    each cohort its own budget and every veto consumer now reads
    `fleet_bus.cohort_long_state` — so the pooled light was the one number on
    the page that nobody obeys, in the first position an operator reads."""
    out = _strip(monkeypatch, _RISK)
    assert "9L/20" in out and "14L/26" in out
    assert out.index("live") < out.index("pooled"), (
        "the pooled light still leads")
    assert "15L/20" in out, "the fleet-wide picture must still be published"


def test_the_governor_chips_survive_the_cohort_split(monkeypatch):
    """REGRESSION PIN. Splitting the old single `if fr:` block for the cohort
    read stranded `fleet_equity` / `fleet_dd_7d` / `clip_scale` in the DARK
    branch, so the drawdown governor — an actuator that shrinks every
    consuming book's clip — rendered only when fleet_risk was dead. Found by
    an adversarial review of that change."""
    out = _strip(monkeypatch, _RISK)
    assert "Fleet eq" in out and "7d dd" in out
    scaled = dict(_RISK, clip_scale=0.5)
    assert "CLIP SCALE" in _strip(monkeypatch, scaled)


def test_a_payload_without_cohorts_keeps_the_pooled_reading(monkeypatch):
    """A pre-(wp) payload has only the pooled light, and there it IS the
    enforced number."""
    out = _strip(monkeypatch, {k: v for k, v in _RISK.items() if k != "cohorts"})
    assert "Risk light" in out and "15L/20" in out
    assert "Fleet eq" in out


def test_a_dark_risk_organ_never_paints_a_green_fleet(monkeypatch):
    out = _strip(monkeypatch, None)
    assert "GREEN" not in out


# --------------------------------------------------------------------------
# the go-live card: the disagreements the week published
# --------------------------------------------------------------------------
def _gl(monkeypatch, book):
    monkeypatch.setattr(dash, "fetch_states", lambda keys: {
        "golive-readiness": {"books": {"a-lshadow": book},
                             "ready": [], "bar": {}}})
    return dash.golive_card()


_BOOK = {"bars": {"t": True, "mean": True, "maxdd": True, "closes": True,
                  "halves": True, "window": True},
         "bars_passed": 6, "n": 204, "t": 2.25, "win_pct": 49.0,
         "max_dd_pct": 4.6, "fails": []}


def test_a_permissive_t_bar_is_flagged(monkeypatch):
    """(zm): the bar and its own cluster-robust read disagree on exactly the
    two books holding REAL MONEY, and nothing said so. `permissive` is the
    asymmetric direction — the bar admits where the honest statistic refuses."""
    out = _gl(monkeypatch, dict(_BOOK, t_bar={
        "bar": 2.0, "basis": "iid", "t_iid": 2.65, "t_cluster": 1.86,
        "passes_iid": True, "passes_cluster": False, "agree": False,
        "permissive": True}))
    assert "t permissive" in out
    assert "1.86" in out


def test_the_harmless_direction_is_muted_not_alarming(monkeypatch):
    out = _gl(monkeypatch, dict(_BOOK, t_bar={
        "bar": 2.0, "basis": "iid", "t_iid": 1.90, "t_cluster": 2.10,
        "passes_iid": False, "passes_cluster": True, "agree": False,
        "permissive": False}))
    assert "t strict" in out and "t permissive" not in out


def test_an_agreeing_book_grows_no_chip(monkeypatch):
    out = _gl(monkeypatch, dict(_BOOK, t_bar={
        "bar": 2.0, "basis": "iid", "t_iid": 2.25, "t_cluster": 2.24,
        "passes_iid": True, "passes_cluster": True, "agree": True,
        "permissive": False}))
    assert "permissive" not in out and "t strict" not in out


def test_a_missing_t_bar_is_silence_not_agreement(monkeypatch):
    """The grader returns None on any doubt rather than a fabricated `agree`."""
    out = _gl(monkeypatch, dict(_BOOK))
    assert "permissive" not in out and "t strict" not in out


def test_the_vetoed_share_of_a_passing_sample_is_shown(monkeypatch):
    """(yn): a QUARTER of the fleet's first-ever READY sample came from lenses
    the book has since vetoed on its own realised record."""
    out = _gl(monkeypatch, dict(_BOOK, veto_split={
        "vetoed": ["dip", "divergence"],
        "now_vetoed": {"n": 46, "t": -1.31, "mean_pct": -0.788},
        "still_tradeable": {"n": 158, "t": 2.84, "mean_pct": 1.481},
        "why": "46 of 204 graded closes come from lenses this book has "
               "since VETOED"}))
    assert "veto 46/204" in out
    assert "+1.48%" in out, "the still-tradeable mean is the number that decides"


def test_a_book_with_nothing_vetoed_grows_no_chip(monkeypatch):
    out = _gl(monkeypatch, dict(_BOOK, veto_split={
        "vetoed": [], "now_vetoed": {"n": 0, "net_usd": 0.0},
        "still_tradeable": {"n": 204}}))
    assert "veto " not in out


def test_a_policy_stamp_era_renders_as_a_date(monkeypatch):
    """The era chip trimmed `[5:]` off whatever it was handed. A policy-stamp
    era is a full ISO INSTANT, so 🎫 the taker — the one book at the bar — grew
    the longest chip on the card: `era 07-30T11:09:46+00:00`."""
    out = _gl(monkeypatch, dict(_BOOK, era={
        "since": "2026-07-30T11:09:46+00:00", "closes_in_era": 204,
        "closes_all_time": 300, "why": "policy stamp"}))
    assert "era 07-30<" in out, "the visible chip label is not a bare date"
    # the PRECISE boundary still belongs in the tooltip — that is where a
    # reader goes for the exact instant; what must not leak is the chip label.
    assert ">era 2026-07-30T" not in out and ">era 07-30T" not in out
    assert "11:09:46" in out, "the tooltip lost the exact era boundary"


# --------------------------------------------------------------------------
# the autonomy rail
# --------------------------------------------------------------------------
def _rail(monkeypatch, states):
    monkeypatch.setattr(dash, "fetch_states", lambda keys: states)
    return dash.autonomy_rail_card()


def test_the_ready_freeze_is_visible_when_it_is_holding(monkeypatch):
    """(ye) gave "freeze its bars first" an actuator: a READY book keeps the
    bracket it passed on. A rail deliberately NOT acting is byte-identical to
    a rail with nothing to do, so the freeze STATE is what is rendered — not
    only its casualties."""
    out = _rail(monkeypatch, {"scout-tuner": {
        "enacted": {"scout.momo_chg_min": 2.0}, "baseline_net": 24.47,
        "ready_freeze": {"book": "lighter-ticket-taker-lshadow",
                         "ready": True, "fresh": True, "dropped": []}}})
    assert "FROZEN" in out and "lighter-ticket-taker-lshadow" in out


def test_a_stale_gate_does_not_claim_a_freeze(monkeypatch):
    """Fail-OPEN is the tuner's own contract: a dark gate restricts nothing,
    so the card must not assert a freeze that is not in force."""
    out = _rail(monkeypatch, {"scout-tuner": {
        "enacted": {}, "ready_freeze": {"book": "x", "ready": True,
                                        "fresh": False, "dropped": []}}})
    assert "FROZEN" not in out


def test_the_candidates_own_clock_and_horizon_reach_the_rail(monkeypatch):
    """(zl)/(zn): a candidate that narrows its own arm changes the very rate
    any projection is built from, and the lane is SERIAL — a candidate burning
    days it cannot use is the fleet's only path to more real money standing
    still."""
    out = _rail(monkeypatch, {"xp-judge": {
        "phase": "running", "candidate": "mum-vel-12-20",
        "lanes": {"serial_lane": "mum", "judging": "2 of 4"},
        "last_eval": {"clock": {"max_days": 14.0, "effective": 16.3,
                                "extended": True},
                      "horizon": {"met": False, "days_elapsed": 0.53,
                                  "days_req_total": 3.2, "binding": "shadow",
                                  "reachable": True,
                                  "verdict_if_expired": "UNDERPOWERED"}}}})
    assert "lane mum" in out and "2 of 4" in out
    assert "day 0.5/16.3" in out and "EXTENDED" in out
    assert "needs 3.2d" in out and "shadow" in out


def test_an_unreachable_candidate_is_loud(monkeypatch):
    """`UNDERPOWERED` is not a refutation — it is the absence of one — and it
    burns a serial-lane slot either way."""
    out = _rail(monkeypatch, {"xp-judge": {
        "phase": "running", "candidate": "c",
        "last_eval": {"clock": {"effective": 14.0},
                      "horizon": {"met": False, "reachable": False,
                                  "days_req_total": 40.0,
                                  "verdict_if_expired": "UNDERPOWERED"}}}})
    assert "UNREACHABLE" in out and "UNDERPOWERED" in out


def test_an_old_judge_payload_still_renders(monkeypatch):
    """Every one of these fields is additive — a container predating them must
    render exactly as before, never an exception that vanishes the card."""
    out = _rail(monkeypatch, {"xp-judge": {"phase": "idle", "candidate": None}})
    assert "XP judge" in out and "idle" in out


# --------------------------------------------------------------------------
# organ registry
# --------------------------------------------------------------------------
def test_the_two_found_organs_have_a_vitals_row():
    """Found by diffing ORGAN_SPECS against the live `bot_state` table rather
    than against itself: both published on their own cadence with no row here,
    so /vitals could not grade them and the watchdog could not see them."""
    src = (_ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    blk = src[src.index("ORGAN_SPECS = ["):]
    blk = blk[:blk.index("\n]")]
    keys = set(re.findall(r'^\s*\("([a-z0-9-]+)"', blk, re.M))
    assert {"coin-quality", "tuning-proposals"} <= keys
    for key in ("coin-quality", "tuning-proposals"):
        assert dash._organ_vital(key, {}) is not None, (
            f"{key} has a spec row but no vital line")


def test_a_dark_coin_quality_does_not_report_zero_measured_coins():
    """A fold that stopped makes every consumer read "unmeasured", which is
    the accessor's own fail-safe and therefore invisible. The vitals line must
    not paint that as a measurement of zero."""
    line = dash._organ_vital("coin-quality", {})
    assert "0 coins" not in line


# --------------------------------------------------------------------------
# the promotion section reads the ONE gate, and it fails closed
# --------------------------------------------------------------------------
_GRADE_READY = {"bars": {"window": True, "closes": True, "mean": True,
                         "t": True, "halves": True, "maxdd": True},
                "bars_passed": 6, "ready": True, "n": 204, "t": 2.25,
                "fails": []}
_GRADE_FOUR = {"bars": {"window": False, "closes": True, "mean": True,
                        "t": False, "halves": True, "maxdd": True},
               "bars_passed": 4, "ready": False, "n": 103, "t": 1.94,
               "fails": ["window 15.7d < 30d", "t 1.94 < 2"]}


def test_the_retired_win_rate_gate_is_gone_from_the_module():
    """(fk) removed win rate as a promotion bar on 29-Jul, for cause. The
    dashboard kept a second copy and used it for the page's most prominent
    promotion signal — the (hj) "a second copy of a rule is a second rule"
    defect, on the surface that answers *who is next for real money*."""
    src = (_ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    tree = ast.parse(src)
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign)
                for t in n.targets if isinstance(t, ast.Name)}
    for name in ("GATE_MIN_WR", "GATE_MIN_TRADES_30D", "GATE_MAX_DD",
                 "GATE_MIN_AGE_DAYS"):
        assert name not in assigned, (
            f"{name} is defined again — the retired win-rate gate is back")
    fns = {n.name for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)}
    assert "fetch_gate_metrics" not in fns
    assert "fetch_golive_stages" in fns


def test_the_stage_reads_the_graders_verdict_and_never_re_derives_it():
    """`_gate_eval` must CONSUME the grader's `bars`/`ready`, never compute a
    verdict of its own — the (hj) rule, pinned structurally.

    THE FIRST VERSION OF THIS TEST WAS A SUBSTRING SCAN AND IT FAILED ON
    `nowrap`, which contains `wr`. That is this repo's own recorded trap — *a
    page-wide substring scan is not a structural claim* ((gn)/(po)) — reproduced
    in the test written to enforce a structural property. It reads the AST now:
    the keys the function pulls off the grade, and the numeric literals it
    compares against."""
    fn = next(n for n in ast.walk(ast.parse(
        (_ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")))
        if isinstance(n, ast.FunctionDef) and n.name == "_gate_eval")

    read = {n.args[0].value for n in ast.walk(fn)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
            and n.func.attr == "get" and n.args
            and isinstance(n.args[0], ast.Constant)
            and isinstance(n.args[0].value, str)}
    assert {"bars", "ready"} <= read, (
        f"_gate_eval does not read the grader's verdict; it reads {sorted(read)}")
    published = {"bars", "ready", "bars_passed", "fails", "n", "t", "win_pct",
                 "max_dd_pct", "era", "horizon", "integrity", "mean_pct",
                 "t_bar", "veto_split", "cluster", "shape", "mde80_pct",
                 "maxdd_basis", "maxdd_denom", "alltime", "legacy_ready"}
    assert read <= published, (
        f"_gate_eval reads {sorted(read - published)}, which the grader does "
        f"not publish per book")
    assert "win_pct" not in read, (
        "the win rate is REPORTED, never a bar — (fk) removed it for cause")

    # no threshold of its own: the grader already decided. The only numbers a
    # pass-through needs are display constants.
    nums = {n.value for n in ast.walk(fn)
            if isinstance(n, ast.Constant) and isinstance(n.value, float)}
    assert not nums, f"_gate_eval carries its own thresholds: {sorted(nums)}"


def test_a_book_the_grader_passes_is_ready_whatever_its_label():
    """🎫 the taker is in EXPERIMENT_BASES and passed all six bars — the
    fleet's first ever. The label says why a book was MINTED; the grader says
    what its record is now, and the record outranks the label."""
    assert "lighter-ticket-taker" in dash.EXPERIMENT_BASES
    stages = {"lighter-ticket-taker-lshadow": _GRADE_READY}
    assert dash.classify_stage("lighter-ticket-taker-lshadow", stages) == "ready"
    assert "perps-funding-carry" in dash.CONTROL_BASES
    assert dash.classify_stage("perps-funding-carry-lshadow",
                               {"perps-funding-carry-lshadow": _GRADE_READY}) == "ready"


def test_a_book_the_grader_refuses_is_not_promoted():
    """👩 mum's twin and 💼 turnbull were both in "Ready for live" while the
    grader had them at 4/6 and 5/6."""
    assert dash.classify_stage("freqtrade-mum-lshadow",
                               {"freqtrade-mum-lshadow": _GRADE_FOUR}) == "proving"


def test_a_dark_grader_promotes_nobody():
    """FAIL-CLOSED, and this is the direction that matters: under the old path
    a book could be "ready" because a local DB query happened to succeed."""
    assert dash.classify_stage("freqtrade-mum-lshadow", {}) == "proving"
    ready, chips = dash._gate_eval({})
    assert ready is False
    assert "unknown" in chips
    assert "✓" not in chips, "a dark grader rendered a passing chip"


def test_the_gate_chips_are_the_graders_six_bars():
    ready, chips = dash._gate_eval(_GRADE_FOUR)
    assert ready is False
    assert "4/6" in chips and "n103" in chips and "t+1.94" in chips
    for _key, glyph, _tip in dash.GOLIVE_BARS:
        assert glyph in chips, f"bar {glyph} missing from the chip row"
    assert "window 15.7d &lt; 30d" in chips, "the grader's own reason is dropped"


def test_a_stale_grader_payload_is_treated_as_dark(monkeypatch):
    """I1 — liveness before semantics. A frozen grade must not promote."""
    stale = {"updated": "2020-01-01T00:00:00+00:00", "ttl_sec": 60,
             "books": {"a-lshadow": _GRADE_READY}}
    monkeypatch.setattr(dash, "fetch_states",
                        lambda keys: {"golive-readiness": stale})
    assert dash.fetch_golive_stages() == {}


def test_the_ready_section_note_states_the_gate_it_applies():
    src = (_ROOT / "pnl_dashboard.py").read_text(encoding="utf-8")
    i = src.index('"ready", "🟢 Ready for live"')
    note = src[i:i + 900]
    assert "six bars" in note and "t &ge; 2.0" in note
    assert "WR &gt;" not in note, "the note still advertises the retired bar"


def test_a_halves_bar_decided_by_row_order_says_so(monkeypatch):
    """(za): TRUE on exactly two graded books — 🙏 avo's LIVE real-money arm
    and 🎫 the taker, the fleet's first-ever READY — and both painted a flat
    green ½ identical to three clean passes."""
    out = _gl(monkeypatch, dict(_BOOK, shape={"halves_tie": True}))
    assert ">tie<" in out and "row ORDER" in out
    clean = _gl(monkeypatch, dict(_BOOK, shape={"halves_tie": False}))
    assert ">tie<" not in clean
    old = _gl(monkeypatch, dict(_BOOK))
    assert ">tie<" not in old, "an older payload must render exactly as before"


def test_the_resampled_drawdown_rides_beside_the_single_path(monkeypatch):
    """👩 mum's LIVE arm reads 12.0% against a 15% bar while her own published
    p99 is 31.8% and 3.15% of resampled orderings breach it. The column showed
    the most flattering of the three numbers the grader publishes."""
    out = _gl(monkeypatch, dict(_BOOK, max_dd_pct=12.0, dd_resampled={
        "p50_pct": 10.21, "p95_pct": 23.16, "p99_pct": 31.82,
        "p_over_bar_at_book_denom": 0.0315}))
    assert "p95 23.2%" in out and "p99 31.8%" in out
    assert "P(over the 15% bar) 3.1%" in out
    assert ">12.0%<" in out, "the graded number is unchanged — this is a report"
    bare = _gl(monkeypatch, dict(_BOOK, max_dd_pct=12.0))
    assert "no resampled distribution" in bare, (
        "a missing risk number must not read as a clean distribution")


def test_a_renderer_that_iterates_a_block_consumes_all_of_it():
    """`_reader_subkeys` scans `.get("literal")`, so a renderer that walks the
    block instead — `for k, v in held.items()` — reads every key and finds
    none, and the block would be dumped in full beside the row that already
    rendered it. Detected from the CODE, never from a list of renderer names."""
    for fn_name, param in (("_t_held", "held"),
                           ("_t_lens_evidence", "lens_evidence"),
                           ("_t_holdwatch", "holdwatch"),
                           ("_t_sources", "sources")):
        assert dash._reads_whole_block(fn_name, param), fn_name
    # a PARTIAL renderer must NOT be detected as whole-block, or its unshown
    # fields would be hidden — the regression this whole mechanism exists for.
    for fn_name, param in (("_t_scan", "scan"), ("_t_leverage", "leverage")):
        assert not dash._reads_whole_block(fn_name, param), fn_name

    rows, used = dash.telemetry_rows({"held": {"AAVE": "x", "SPY": "y"}})
    assert used["held"] == {"AAVE", "SPY"}
    out = dash.card("x-lshadow", {"status": "online", "updated_at": None,
                                  "equity": 1000.0,
                                  "extra": {"held": {"AAVE": "oversold"}}})
    assert "Held (1)" in out
    assert "'AAVE': 'oversold'" not in out, "the held map was dumped twice"


def test_a_partial_renderer_still_leaves_its_residue():
    """The counter-case, pinned beside it: `_t_scan` renders the top few
    refusals, so everything it did not show must stay in the dump."""
    out = dash.card("x-lshadow", {
        "status": "online", "updated_at": None, "equity": 1000.0,
        "extra": {"scan": {"scanned": 91, "no_signal": 56,
                           "some_unshown_counter": 3, "rsi_med": 40.4}}})
    assert "Scan census" in out and "91 scanned" in out
    assert "rsi_med" in out, "a census field no row showed was hidden"
