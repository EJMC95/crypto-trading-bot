"""🎯 Perp Sniper: the PER-SOURCE CENSUS — I18/(lv) on a book with three sources.

[2026-08-20 (sd)] `{admitted: 0}` is byte-identical between "this source was
quiet today" and "this source is structurally incapable of ever admitting
anything". That ambiguity is not hypothetical here — it hid two dead sources
for months, measured the day this shipped:

  * `listing` — ZERO crypto births on the venue for 86 days (the last were
    CTR/RAIL on 25-May). The (qi) study had already refuted the listing-LONG
    thesis; what nothing could see from the payload is that the source has had
    no crypto supply AT ALL to apply it to.
  * `young`   — EMPTY for 66 days. Three independent gates each take it to
    zero: the class-2 birth rate is 0.00/30d, the venue files memecoin debuts
    under `strategy_index` 7 which the (lk) crypto screen excludes, and the
    $0.25M volume floor was cleared by CTR/RAIL on 1 of 21 young days each.

Throughout, `extra` published `watching: 212` and `pending: N` — book-wide
counters that say nothing per source — so the row looked the same on day 1 and
day 66. This is the exact condition (lv) names, and the reason 🎸 Barnesy's
`extreme` sleeve ran dead for 8 days before anyone could ask.

WHAT THE CENSUS MUST DO, and therefore what these tests pin:

1. COUNT THE REAL GATE. The funnel is filled by the admission functions
   themselves, one counter per stage, so it cannot drift from admission the way
   a re-implemented census would ((hj): a second copy of a rule is a second
   rule). `test_the_census_tracks_the_gate_not_a_copy_of_it` is the mutation
   arm — it moves each gate in turn and requires the funnel to move WITH it.
2. NAME THE KILLING GATE. A reader must be able to say WHICH stage a source
   dies at without opening this file — that is the difference between "quiet"
   and "impossible".
3. READ LIVENESS FIRST (I1). A dark or stale scout must not publish an all-zero
   funnel, which is indistinguishable from a live scan that found nothing.
4. CHANGE NO TRADE. The census is publish-only: admission with a census must be
   byte-identical to admission without one.
"""
import pathlib

import pytest

import lighter_perp_sniper as sniper

SRC = pathlib.Path(sniper.__file__).read_text()


def _crypto_only(*allowed):
    """A stand-in for the (lk) class screen admitting exactly `allowed`."""
    allow = set(allowed)
    return lambda s: s in allow


# --------------------------------------------------------------------------
# 1 · THE MUTATION ARM — the census must track the gate, not a copy of it
# --------------------------------------------------------------------------

def test_the_census_tracks_the_gate_not_a_copy_of_it_surge():
    """Move each surge gate in turn; the funnel must move with it.

    This is the arm that makes the census trustworthy. A hand-rolled census
    would keep reporting the old numbers when the gate changed — and would do
    it silently, which is worse than no census at all.
    """
    surges = [{"sym": "AAA", "ratio": 9.0}, {"sym": "BBB", "ratio": 4.0},
              {"sym": "CCC", "ratio": 1.5}]

    # Baseline: mult 3.0 admits AAA+BBB; CCC fails the ratio gate.
    cen = {}
    out = sniper.surge_candidates(surges, 3.0, set(), limit=9,
                                  class_ok=lambda s: True, census=cen)
    assert out == ["AAA", "BBB"], out
    assert (cen["offered"], cen["ratio_ok"], cen["admitted"]) == (3, 2, 2), cen

    # MUTATE the ratio gate up — the funnel must follow admission down.
    cen2 = {}
    out2 = sniper.surge_candidates(surges, 5.0, set(), limit=9,
                                   class_ok=lambda s: True, census=cen2)
    assert out2 == ["AAA"], out2
    assert cen2["ratio_ok"] == 1 and cen2["admitted"] == 1, cen2
    assert cen2["offered"] == 3, "offered is SUPPLY — it must not move with the bar"

    # MUTATE the dedup set — `fresh` must drop, `ratio_ok` must not.
    cen3 = {}
    sniper.surge_candidates(surges, 3.0, {"AAA"}, limit=9,
                            class_ok=lambda s: True, census=cen3)
    assert cen3["ratio_ok"] == 2 and cen3["fresh"] == 1, cen3

    # MUTATE the class screen — `class_ok` must drop, `fresh` must not.
    cen4 = {}
    out4 = sniper.surge_candidates(surges, 3.0, set(), limit=9,
                                   class_ok=_crypto_only("BBB"), census=cen4)
    assert out4 == ["BBB"], out4
    assert cen4["fresh"] == 2 and cen4["class_ok"] == 1, cen4


def test_the_census_tracks_the_gate_not_a_copy_of_it_young():
    """Same mutation discipline on the young source's four gates."""
    bars = {"AAA": 3, "BBB": 10, "CCC": 400}
    vols = {"AAA": 1.0, "BBB": 0.01, "CCC": 50.0}

    cen = {}
    out = sniper.young_candidates(bars, 21, vols, 0.25, set(), 9,
                                  class_ok=lambda s: True, census=cen)
    assert out == ["AAA"], out
    # CCC is too old; BBB is young enough but too thin.
    assert cen["scanned"] == 3 and cen["age_ok"] == 2, cen
    assert cen["class_ok"] == 2 and cen["vol_ok"] == 1, cen

    # MUTATE the age bar — `age_ok` follows.
    cen2 = {}
    sniper.young_candidates(bars, 5, vols, 0.25, set(), 9,
                            class_ok=lambda s: True, census=cen2)
    assert cen2["scanned"] == 3 and cen2["age_ok"] == 1, cen2

    # MUTATE the volume floor — `vol_ok` follows, `class_ok` does not.
    cen3 = {}
    sniper.young_candidates(bars, 21, vols, 0.0, set(), 9,
                            class_ok=lambda s: True, census=cen3)
    assert cen3["class_ok"] == 2 and cen3["vol_ok"] == 2, cen3

    # MUTATE the class screen — this is the gate that actually kills the
    # source in production, so it gets its own assertion.
    cen4 = {}
    out4 = sniper.young_candidates(bars, 21, vols, 0.25, set(), 9,
                                   class_ok=lambda s: False, census=cen4)
    assert out4 == [], out4
    assert cen4["age_ok"] == 2 and cen4["class_ok"] == 0, cen4


# --------------------------------------------------------------------------
# 2 · THE POINT OF THE WHOLE THING — quiet vs structurally impossible
# --------------------------------------------------------------------------

def test_a_quiet_source_and_an_impossible_source_are_distinguishable():
    """The (lv) property. Both admit nothing; the funnels must NOT match.

    This is the test that would have caught the live condition: `young` reading
    `age_ok: 7, class_ok: 0` says "seven young books exist and the class screen
    refuses every one" — a structural verdict. `scanned: 0` says "the venue has
    no young books at all" — a supply verdict. They need different fixes, and
    before the census they published identically.
    """
    quiet = {}
    sniper.young_candidates({}, 21, {}, 0.25, set(), 9,
                            class_ok=lambda s: True, census=quiet)

    impossible = {}
    sniper.young_candidates({"MEME": 3}, 21, {"MEME": 9.0}, 0.25, set(), 9,
                            class_ok=lambda s: False, census=impossible)

    assert quiet["admitted"] == impossible["admitted"] == 0
    assert quiet != impossible, (
        "a source with NO supply and a source whose gate refuses all of its "
        "supply published the same funnel — the (lv) ambiguity is back")
    assert quiet["scanned"] == 0 and impossible["scanned"] == 1
    assert impossible["age_ok"] == 1 and impossible["class_ok"] == 0


def test_the_funnel_names_the_gate_that_killed_the_source():
    """A reader must find the killing gate as the first zero, in gate order.

    The stage order is DERIVED from the funnel the module itself builds (dicts
    preserve insertion order and `_new_funnel` inserts in gate order), never
    retyped here — a retyped constant is a constant that drifts, and this one
    would drift silently into blaming the wrong gate.
    """
    cen = {}
    sniper.young_candidates({"MEME": 3}, 21, {"MEME": 9.0}, 0.25, set(), 9,
                            class_ok=lambda s: False, census=cen)
    stages = [k for k in cen if k not in ("admitted", "capped", "scan")]
    assert stages, "the funnel published no stages at all"
    first_zero = next((k for k in stages if cen[k] == 0), None)
    assert first_zero == "class_ok", (
        f"the funnel blames {first_zero}; the (lk) class screen is what refused "
        f"this book, and naming the wrong gate sends the next reader to tune a "
        f"knob that was never binding. Stage order as published: {stages}")


def test_supply_is_reported_even_when_the_pass_is_capped():
    """A capped pass must still say how much supply it turned away.

    The pre-census loop `break`s at the cap, so a source offering 50 candidates
    and one offering 4 both reported the same admissions. Capacity and supply
    are different diagnoses ((hs)) and the payload must not conflate them.
    """
    surges = [{"sym": f"S{i}", "ratio": 9.0} for i in range(20)]
    cen = {}
    out = sniper.surge_candidates(surges, 3.0, set(), limit=3,
                                  class_ok=lambda s: True, census=cen)
    assert len(out) == 3 and cen["admitted"] == 3
    assert cen["offered"] == 20 and cen["class_ok"] == 20, cen
    assert cen["capped"] is True, "a capped pass must say so"

    uncapped = {}
    sniper.surge_candidates(surges[:2], 3.0, set(), limit=3,
                            class_ok=lambda s: True, census=uncapped)
    assert uncapped["capped"] is False


# --------------------------------------------------------------------------
# 3 · I1 — liveness before semantics
# --------------------------------------------------------------------------

@pytest.mark.parametrize("state", ["dark", "stale", "error", "off"])
def test_a_dark_scout_never_publishes_a_live_looking_funnel(state):
    """`scan` must carry a non-fresh verdict for every non-scanning path.

    An all-zero funnel from a dead scout is byte-identical to a live scan that
    found nothing — I1's exact failure, and the one that let 🌾 carry read as a
    healthy live writer for 13 hours after it died.
    """
    assert f'"{state}"' in SRC, (
        f"the loop no longer publishes a `{state}` scan verdict; a non-scanning "
        "pass would fall back to an all-zero funnel that reads as a live scan")


def test_the_loop_sets_the_scan_verdict_before_it_can_be_skipped():
    """The verdict is assigned at declaration, not inside the success branch."""
    for var, default in (("_surge_cen", 'SURGE_MULT <= 0'),
                         ("_young_cen", 'YOUNG_MAX_BARS <= 0')):
        decl = next(ln for ln in SRC.splitlines()
                    if ln.strip().startswith(f"{var} = "))
        assert '"scan"' in decl and default in decl, (
            f"{var} must be born carrying its liveness verdict, so a source "
            f"whose scan never runs cannot publish a fresh-looking funnel: {decl}")


# --------------------------------------------------------------------------
# 4 · PUBLISH-ONLY — the census must change no trade
# --------------------------------------------------------------------------

def test_admission_is_byte_identical_with_and_without_a_census():
    """Threading a census must not move a single admission."""
    surges = [{"sym": "AAA", "ratio": 9.0}, {"sym": "BBB", "ratio": 4.0},
              {"sym": "CCC", "ratio": 1.5}, {"sym": "", "ratio": 9.0},
              {"sym": "DDD", "ratio": None}]
    bars = {"AAA": 3, "BBB": 10, "CCC": 400, None: 1, "DDD": "junk"}
    vols = {"AAA": 1.0, "BBB": 0.01, "CCC": 50.0}

    for limit in (1, 2, 9):
        for already in (set(), {"AAA"}):
            for ok in (lambda s: True, _crypto_only("BBB"), lambda s: False):
                assert sniper.surge_candidates(
                    surges, 3.0, already, limit=limit, class_ok=ok) == \
                    sniper.surge_candidates(
                        surges, 3.0, already, limit=limit, class_ok=ok,
                        census={}), (limit, already)
                assert sniper.young_candidates(
                    bars, 21, vols, 0.25, already, limit, class_ok=ok) == \
                    sniper.young_candidates(
                        bars, 21, vols, 0.25, already, limit, class_ok=ok,
                        census={}), (limit, already)


def test_no_decision_in_the_file_reads_a_census_counter():
    """Publish-only, asserted structurally rather than by reading the diff.

    The counters exist to be looked at by a human, never to gate a trade. If a
    future change makes admission depend on one, this book acquires a feedback
    loop nothing has measured.
    """
    import re
    publish = re.compile(
        r'^(?:"sources": \{)?"(?:listing|surge|young)": _\w+_cen[,}]*$')
    for var in ("_surge_cen", "_young_cen", "_listing_cen"):
        uses = [ln.strip() for ln in SRC.splitlines()
                if var in ln and not ln.strip().startswith("#")]
        assert uses, f"{var} vanished from the file"
        for ln in uses:
            ok = (ln.startswith(f"{var} = ")            # born, with its verdict
                  or ln.startswith(f'{var}["scan"] = ')  # liveness verdict
                  or f"census={var}" in ln               # handed to the gate
                  or publish.match(ln))                  # published
            assert ok, (
                f"`{var}` appears somewhere that is not its own assignment, the "
                f"census= argument or the publish payload. The census must gate "
                f"no decision in this book — a counter that steers admission is "
                f"a feedback loop nothing has measured: {ln}")


def test_the_census_reaches_the_published_payload():
    """A census nothing publishes is a census nobody can read ((gk))."""
    assert '"sources": {"listing": _listing_cen,' in SRC, \
        "the per-source census is not wired into extra{}"
    assert '"surge": _surge_cen,' in SRC and '"young": _young_cen}' in SRC


def test_every_source_the_book_admits_from_has_a_funnel():
    """Sources and funnels must not drift apart.

    `SNIPE_SOURCES` is the book's own declaration of its routes in — already the
    whitelist for the close-tag composer and the state restore — so binding the
    census to it means a fourth source cannot arrive without one. Extra funnels
    are allowed: a RETIRED source keeps publishing its census so the retirement
    stays falsifiable (the (ly) precedent).
    """
    declared = set(getattr(sniper, "SNIPE_SOURCES", ()) or ())
    assert declared, "SNIPE_SOURCES vanished — the source list is the contract"
    published = {"listing", "surge", "young"}
    assert declared <= published, (
        f"source(s) {sorted(declared - published)} admit trades but publish no "
        "funnel — `admitted: 0` is ambiguous again for exactly those")
