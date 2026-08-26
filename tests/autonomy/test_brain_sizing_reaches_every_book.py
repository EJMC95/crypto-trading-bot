"""[2026-08-20 (so)] THE BRAIN SIZES EVERY LIVING BOOK — and the rails still
refuse it.

Eamon: *"Implement into live and other bots without it."*

WHAT WAS MEASURED, and why this is not a refactor. On the morning this shipped
the brain's ENTIRE published opinion across a twenty-book fleet was two
multipliers:

    lighter-ticket-taker-lshadow | short-divergence   0.75   (streak 11)
    perps-funding-spread-lshadow | long               0.75   (streak 91)

and **neither book could hear it**. Ninety-one consecutive brain runs asking
⚖️ Counterweight to take less risk on its long side, into a consumer that did
not exist. Every book that COULD hear the brain had nothing to hear; the two it
was talking to were deaf. That is I18's unreachable-lever shape with the arrow
reversed — not a knob with no reader, a reader with no knob.

The four guards below are the class, not the instances:

  1. every living book reaches a brain sizing accessor (roster-driven, so a NEW
     book cannot ship deaf);
  2. the key each book looks the mult up under is the key its own ledger rows
     bucket under (the failure that would make all of this inert, silently, and
     which really did fire on 💸 the Farmer before it shipped);
  3. on every order-sending book the SIZED clip is what the operator's notional
     rail sees (the multiplier proposes; the rails dispose);
  4. nobody reads the brain payload directly and skips the clamp.
"""
import ast
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]

#: (module, row-suffixless expectations) — every LIVING book that sizes its own
#: entries. Retired books are absent because they open nothing.
BOOKS = [
    "lighter_funding_bot.py",          # 💸 the Farmer          (LIVE + shadow)
    "lighter_avo_live_bot.py",         # 🙏 Avo Maria           (LIVE)
    "lighter_ticket_taker.py",         # 🎫 the Ticket Taker
    "funding_carry_bot.py",            # 🌾 the Yield Harvester
    "lighter_funding_spread_bot.py",   # ⚖️ Counterweight
    "lighter_band_kelly_bot.py",       # 🪁 the Mirror
    "lighter_nav_cook_bot.py",         # 🧭 Captain Cook
    "lighter_book_douglas_bot.py",     # 🧘 The Zone
    "lighter_book_hull_bot.py",        # 🧮 The Professor
    "lighter_book_kiyosaki_bot.py",    # 🏦 Rich Dad
    "lighter_book_grimes_bot.py",      # 📐 The Technician
    "lighter_perp_sniper.py",          # 🎯 the Perp Sniper
    "lighter_family_bot.py",           # 👩🙏🔮 the family books
]

#: the accessors that ARE "reading the brain for size". Derived nowhere else —
#: this is the definition, and (4) below pins that nothing bypasses them.
SIZERS = {"brain_clip", "brain_clip_multi", "brain_mult_multi",
          "brain_stake_mult", "brain_clip_for", "stake_multiplier"}

#: books that DELIBERATELY do not size off the brain, each with the measured
#: reason. An entry here is a decision; an omission is a bug.
DEAF_OK = {
    # (none today — the whole point of (so). Kept so the next refusal has to be
    # written down rather than silently dropped from BOOKS.)
}


def _tree(name):
    return ast.parse((ROOT / name).read_text())


def _calls(tree):
    for n in ast.walk(tree):
        if isinstance(n, ast.Call):
            yield n


def _callee(node):
    return getattr(node.func, "attr", "") or getattr(node.func, "id", "")


def test_the_sizer_list_is_not_blind():
    """A roster test whose roster matches nothing passes for free. Anchor it:
    fleet_bus must actually define the accessors this file names, and the two
    multi-bucket ones must exist because two books depend on that exact rule.
    """
    import fleet_bus
    for fn in ("brain_clip", "brain_clip_multi", "brain_mult_multi",
               "brain_mult_raw", "stake_multiplier"):
        assert callable(getattr(fleet_bus, fn, None)), fn
    for name in BOOKS:
        assert (ROOT / name).exists(), name


@pytest.mark.parametrize("name", BOOKS)
def test_every_living_book_sizes_off_the_brain(name):
    """(1) No book is deaf. The fleet ran twenty books off constants while the
    organ holding every close it has ever made had nothing to say to them."""
    if name in DEAF_OK:
        pytest.skip(DEAF_OK[name])
    hits = [n.lineno for n in _calls(_tree(name)) if _callee(n) in SIZERS]
    assert hits, (
        f"{name} never asks the brain how big to be. Either wire "
        "fleet_bus.brain_clip at its sizing site, or add it to DEAF_OK with "
        "the measured reason — an omission is a bug, a declaration is a "
        "decision.")


#: the LEDGER bucket key each book's closes carry, as a regex over the source
#: that composes it. Two sources, and getting the wrong one is the whole
#: hazard: `bot_pnl_store.fetch_paper_trades` prefers the stored `tag` COLUMN
#: over the `reason` prefix ("a stored tag is richer than the reason prefix:
#: 'long-funding' beats 'long'"), so a book that stamps `tag=` buckets under
#: THAT and a lookup on the reason prefix returns 1.0 forever.
LEDGER_KEY = {
    "lighter_funding_bot.py": "funding",      # tag= column, NOT the prefix
    "lighter_nav_cook_bot.py": "navband",     # tag= column
    "lighter_ticket_taker.py": None,          # reason: <side>-<lens>, dynamic
    "lighter_book_douglas_bot.py": "impulse",
    "lighter_book_hull_bot.py": "basis",
    "lighter_book_kiyosaki_bot.py": "cashflow",
    "lighter_book_grimes_bot.py": None,       # reason: <side>-<setup>, dynamic
    "lighter_band_kelly_bot.py": None,        # reason: <side>-<family>, two
    "funding_carry_bot.py": "",               # reason: bare <side>
    "lighter_funding_spread_bot.py": "",      # reason: bare <side>
    "lighter_perp_sniper.py": None,           # entry_tag(), shared by both
    "lighter_avo_live_bot.py": None,          # ledger_tag(), shared by both
    "lighter_family_bot.py": None,            # ledger_tag(), shared by both
}


@pytest.mark.parametrize("name", sorted(k for k, v in LEDGER_KEY.items()
                                        if v is not None))
def test_the_sizing_key_matches_the_ledger_bucket_key(name):
    """(2) THE FAILURE THAT WOULD MAKE ALL OF THIS INERT, SILENTLY.

    A book whose sizing lookup uses a key its ledger never writes gets 1.0
    forever and nothing anywhere says so. It is not hypothetical: 💸 the
    Farmer stamps the `tag` column `long-funding` while its `reason` prefix
    reads `long`, and the first draft of (so) looked the mult up under `long`
    — on the fleet's REAL MONEY. Caught by reading the publisher, not the
    consumer.

    Books whose key is fully dynamic (a lens, a setup, a family) or built by a
    shared composer (`entry_tag`, `ledger_tag`) are covered by
    `test_dynamic_keys_come_from_one_owner` instead: for them the guarantee is
    structural rather than textual.
    """
    src = (ROOT / name).read_text()
    suffix = LEDGER_KEY[name]
    calls = [n for n in _calls(ast.parse(src)) if _callee(n) in SIZERS]
    assert calls, name
    seen = []
    for c in calls:
        for a in list(c.args) + [k.value for k in c.keywords]:
            seen.append(ast.unparse(a))
    blob = " ".join(seen)
    if suffix:
        assert suffix in blob, (
            f"{name} sizes on a key that does not carry '{suffix}', but its "
            f"ledger rows bucket under it: {seen}")
    else:
        # a bare-side book: the key must be exactly the side words, with no
        # family suffix invented at the sizing site
        assert re.search(r"['\"](?:long|short)['\"]", blob), seen
        assert not re.search(r"['\"](?:long|short)-\w", blob), (
            f"{name} sizes on a suffixed key while its ledger writes a bare "
            f"side prefix: {seen}")


def test_dynamic_keys_come_from_one_owner():
    """(2b) For the books whose key is dynamic, the guarantee is that the
    sizing site and the ledger row are built from THE SAME expression — a
    retyped key is a key that drifts.
    """
    # 🎯 the sniper: `entry_tag()` was extracted FROM `close_reason` so both
    # move together. Assert the composition, not the string.
    src = (ROOT / "lighter_perp_sniper.py").read_text()
    assert "def entry_tag(" in src
    assert "entry_tag(was_long, src)" in src, \
        "close_reason must compose from entry_tag, not retype it"
    # [2026-08-26] This asserted the literal `entry_tag(DIRECTION_LONG`, which
    # is a retyped string standing in for the real invariant — the exact shape
    # this file's own docstring warns about ("a retyped key is a key that
    # drifts"). It broke the moment the sniper's side became PER-SOURCE, and it
    # broke in the direction of the FIX: the sizing site now passes the same
    # side the OPEN site passes, where before it passed a module constant that
    # would have asked the brain for `long-young` while the ledger wrote
    # `short-young`.
    #
    # The invariant, asserted by AST instead of by substring: the side
    # expression handed to `entry_tag` at the sizing site is IDENTICAL to the
    # one handed to the broker/venue at the open site. Whatever either becomes,
    # they move together.
    tree = ast.parse(src)
    sides = {"entry_tag": set(), "open": set()}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not node.args:
            continue
        callee = _callee(node)
        if callee == "entry_tag" and len(node.args) >= 1:
            sides["entry_tag"].add(ast.unparse(node.args[0]))
        elif callee in ("broker.open", "market_open") and len(node.args) >= 2:
            sides["open"].add(ast.unparse(node.args[1]))
    # `close_reason` composes `entry_tag(was_long, src)`, so that parameter name
    # is expected here alongside the sizing site's real expression.
    sizing = sides["entry_tag"] - {"was_long"}
    assert sizing, f"no sizing-site entry_tag call found: {sides}"
    assert sizing <= sides["open"], (
        f"the sizing site keys the brain off {sizing} while the position is "
        f"opened with {sides['open']} — the lookup would ask for a tag the "
        f"ledger never writes, and return 1.0 forever in silence")

    # 🙏 Avo + the family: `ledger_tag` is the one composer, and
    # `brain_clip_for` applies it internally so a caller cannot pass a raw tag.
    fam = (ROOT / "lighter_family_bot.py").read_text()
    assert "def brain_clip_for(" in fam
    fn = [f for f in ast.walk(ast.parse(fam))
          if isinstance(f, ast.FunctionDef) and f.name == "brain_clip_for"][0]
    assert "ledger_tag" in ast.unparse(fn), \
        "brain_clip_for must key on ledger_tag, or a caller can drift"

    # 🎫 / 📐 / 🪁: the side+family is built inline at both ends. Assert the
    # sizing site's f-string carries the SAME two parts the reason does.
    for name, parts in (("lighter_ticket_taker.py", ("lens",)),
                        ("lighter_book_grimes_bot.py", ("side", "s")),
                        ("lighter_band_kelly_bot.py", ("snap", "dip"))):
        src = (ROOT / name).read_text()
        calls = [n for n in _calls(ast.parse(src)) if _callee(n) in SIZERS]
        blob = " ".join(ast.unparse(a) for c in calls
                        for a in list(c.args) + [k.value for k in c.keywords])
        assert any(p in blob for p in parts), (name, blob)


#: files allowed to read the raw `brain-stake-mults` payload, each with the
#: reason. NOT an exemption — `test_a_declared_raw_reader_still_cannot_size_
#: with_it` below proves the value stays a boolean.
RAW_READ_OK = {
    # (dm) INCREMENT B: 🎫 the taker grades its OWN `long-breakoutup` closes
    # for a RESTRICT-ONLY lens veto. brain-lens-forward structurally cannot
    # carry breakoutup (it grades SCOUT lenses' forward marks), so the
    # per-close-tag grade has to come from this key. It yields a BOOL.
    "lighter_ticket_taker.py":
        "(dm) breakoutup self-veto — reads the payload to VETO a lens, "
        "never to size; the sizing path goes through fleet_bus.brain_clip",
}

#: books that SEND ORDERS (live or funded paths). For these the operator's
#: notional rail must see the SIZED clip.
ORDER_SENDING = {
    "lighter_funding_bot.py": "notional_ok",
    "lighter_avo_live_bot.py": "notional_ok",
    "lighter_ticket_taker.py": "notional_ok",
    "lighter_perp_sniper.py": "notional_ok",
}


@pytest.mark.parametrize("name", sorted(ORDER_SENDING))
def test_the_rails_see_the_sized_clip(name):
    """(3) THE MULTIPLIER PROPOSES; THE RAILS DISPOSE.

    This is the property that makes wiring the brain into real money a
    number-passing change rather than a authority change. The variable the
    brain assigns must be the variable `SafetyRails.notional_ok` is handed —
    not the pre-scale one. A 6.7x clip admitted against a 1x cap check is
    exactly the 15-Jul cap breach, rebuilt.
    """
    tree = _tree(name)
    assigns = [n for n in ast.walk(tree) if isinstance(n, ast.Assign)]

    def _targets(n):
        out = set()
        for tgt in n.targets:
            if isinstance(tgt, ast.Tuple):
                # `clip, bmult = brain_clip(...)` — the SIZE is the first
                # element; `bmult` is the receipt and reaching the rail with
                # THAT would be a different bug.
                if tgt.elts and isinstance(tgt.elts[0], ast.Name):
                    out.add(tgt.elts[0].id)
            elif isinstance(tgt, ast.Name):
                out.add(tgt.id)
        return out

    scaled = set()
    for n in assigns:
        # the value may be a bare call OR the fleet's guarded-import idiom
        # `(fleet_bus.brain_clip(...) if fleet_bus is not None else (base, 1.0))`
        # — an IfExp. The first draft matched only ast.Call and reported 🎯 the
        # sniper as un-scaled while it was correctly wired: a guard that
        # silently misses the idiom half the fleet uses is the (po) class.
        if any(_callee(c) in SIZERS for c in ast.walk(n.value)
               if isinstance(c, ast.Call)):
            scaled |= _targets(n)
    # [(sp)] ...and FOLLOW THE TAINT ONE HOP AT A TIME. 🎫 the taker no longer
    # binds the sized clip directly: the brain's mult goes in as a RISK budget
    # and comes out of `vol_clip`, so the rail is handed a name two assignments
    # downstream. Requiring a DIRECT binding made this guard report the taker
    # as unrailed while it was correctly wired — the same
    # miss-the-idiom failure as the IfExp above, one refactor later. A
    # transitive closure over assignments is what the guard actually means:
    # "does the value the rail sees depend on the brain's number?"
    # TWO HOPS, NOT A FIXPOINT. Run to convergence the closure swallows the
    # module: `clip` taints `size`, `size` taints `res`, and eventually
    # `is_long` and `reason` are "scaled" — at which point the assertion below
    # passes for anything and the guard means nothing. Two hops is what the
    # real shape needs (🎫 the taker: `_bm` -> `clip` via `vol_clip`) and it
    # keeps `open_ntl` — computed FROM the sized clip, but not the value under
    # test — out of the set.
    for _ in range(2):
        for n in assigns:
            used = {x.id for x in ast.walk(n.value) if isinstance(x, ast.Name)}
            if used & scaled:
                scaled |= _targets(n)
    assert scaled, (
        f"{name} never binds a brain-scaled clip to a name — either it does "
        "not size off the brain (test 1 should have caught that) or the "
        "scale is applied somewhere this guard cannot see, which is worse")
    # [(sp)] THE SECOND ARGUMENT ONLY. `notional_ok(deployed, clip)` — and a
    # SURVIVING mutation showed why the distinction is load-bearing: the taint
    # closure reaches `open_ntl` too (it is computed FROM the sized clip), so
    # scanning every argument let 🙏 Avo pass while its rail was handed the
    # PRE-brain clip. The guard is about the value under test, not about
    # anything that merely touched it.
    # EVERY call site, not any. A SURVIVING mutation showed why: (sp) gave 💸
    # the Farmer a second, post-trim `notional_ok` — so an "any" test stayed
    # green while the FIRST call was mutated to read the pre-brain clip. One
    # correct call does not make a rail correct; the weakest one governs.
    checked = []
    for c in _calls(tree):
        if _callee(c) != ORDER_SENDING[name]:
            continue
        # skip a fake/delegating rail defined inside the module's own
        # selftest — walk the receiver chain to its ROOT, because the shape is
        # `self._real.notional_ok(...)` and a one-level check misses it.
        _recv = getattr(c.func, "value", None)
        while isinstance(_recv, ast.Attribute):
            _recv = _recv.value
        if isinstance(_recv, ast.Name) and _recv.id == "self":
            continue
        if len(c.args) >= 2 and isinstance(c.args[1], ast.Name):
            checked.append((c.lineno, c.args[1].id))
    assert checked, f"{name}: no {ORDER_SENDING[name]} call takes a named clip"
    unrailed = [(ln, nm) for ln, nm in checked if nm not in scaled]
    assert not unrailed, (
        f"{name}: the brain scales {sorted(scaled)} but the notional rail is "
        f"handed an UNSCALED value at {unrailed} — the cap would admit a clip "
        "it never saw. The multiplier proposes; the rails must dispose.")


def test_no_book_reads_the_brain_payload_directly():
    """(4) The clamp is the safety, so nothing may go around it. Only
    `fleet_bus` may touch the `brain-stake-mults` key; a book that loads it
    itself has an unbounded multiplier and would not even know.
    """
    offenders = []
    for path in list(ROOT.glob("*.py")) + list((ROOT / "parliament").glob("*.py")):
        if path.name in ("fleet_bus.py", "bot_learn.py", "pnl_dashboard.py",
                         "fleet_immune.py", "evidence_board.py",
                         "fleet_radar.py"):
            continue                      # publisher, renderers, monitors
        if path.name in RAW_READ_OK:
            continue
        src = path.read_text()
        if "brain-stake-mults" in src:
            offenders.append(path.name)
    assert not offenders, (
        "a consumer reads the brain's raw payload and therefore skips the "
        f"[MULT_FLOOR, MULT_CEIL] clamp: {offenders}")


def test_a_declared_raw_reader_still_cannot_size_with_it():
    """An entry in `RAW_READ_OK` is a declaration, not an exemption. The one
    reader there consumes the payload as a BOOLEAN veto; assert that it can
    never become a size — the value it binds must never enter a multiplication
    or land on a clip/stake/notional name. Without this the declaration would
    be a hole in the guard, which is the `DRIFT_OK` lesson.
    """
    for name in RAW_READ_OK:
        tree = _tree(name)
        bound = set()
        for n in ast.walk(tree):
            if (isinstance(n, ast.Assign)
                    and "brain-stake-mults" in ast.unparse(n.value)):
                for t in n.targets:
                    if isinstance(t, ast.Name):
                        bound.add(t.id)
        assert bound, f"{name}: RAW_READ_OK names a file that no longer reads it"
        for n in ast.walk(tree):
            if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Mult):
                used = {x.id for x in ast.walk(n) if isinstance(x, ast.Name)}
                assert not (used & bound), (
                    f"{name}:{n.lineno} multiplies with a RAW brain payload "
                    f"read — that is an UNCLAMPED size: {ast.unparse(n)}")
            if isinstance(n, ast.Assign):
                tgts = {t.id for t in n.targets if isinstance(t, ast.Name)}
                if tgts & {"clip", "stake", "notional", "order_usd", "size"}:
                    used = {x.id for x in ast.walk(n.value)
                            if isinstance(x, ast.Name)}
                    assert not (used & bound), (
                        f"{name}:{n.lineno} sizes from a RAW brain read")
