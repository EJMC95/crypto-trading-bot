#!/usr/bin/env python3
"""audit_book_overlap.py — ARE OUR BOOKS HOLDING THE SAME COIN?

WHY (2026-08-13 (lz)). The fleet grades every book independently and allocates
capital by each book's own claim, so two books holding the SAME position read
as two independent bets. On this venue that assumption broke quietly: THREE
funding books now enter at the same bar — 🌾 carry, 🎸 Barnesy's carry sleeve
and 🏦 Rich Dad all take ~20% TRUE apr / $2M turnover / crypto-only — while the
venue's ENTIRE crypto population at that bar is four names (KAITO, XMR, PAXG,
XRP), present in ~6.7% of scout snapshots.

Nothing in the fleet could ask the question, for a mundane reason: two of those
books published an open-position COUNT and no coin names. Concentration is a
property of the COIN, so a count cannot express it. `(lz)` added `held` to both;
this reads it.

TWO MODES, because there are two moments the question matters:

  (default) NOW — cross-book overlap in the live payload. Which coins are held
      by more than one book, how much notional sits on each, and what the
      fleet's effective bet count actually is once duplicates collapse.

  --gate APR --floor USD — BEFORE A BOOK IS BORN. Replays the scout's own tape
      and answers: how many coins would a book with THIS gate actually get, how
      often, and WHICH BOOKS ALREADY HOLD THEM. A new book whose supply is
      entirely spoken for is not new edge — it is the same bet at a new row id,
      and the fleet has now done that once (🏦 Rich Dad, born into 🌾's slot).

READ-ONLY. Prints and exits non-zero on a finding; moves no capital, writes no
lever, retires nothing. `--strict` makes overlap itself an error (for CI);
by default only a HARD finding (a coin held by 3+ books) exits non-zero, so
this can run in a pipeline without failing on ordinary two-book overlap.
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from collections import defaultdict

# The funding books that share a supply. Membership is RULE-DRIVEN — a book
# belongs here if it enters on a funding rate over the venue's own universe —
# not curated, so a new funding book is a one-line addition rather than a
# silent omission (the census-hole class, (jb)).
FUNDING_BOOKS = [
    "perps-funding-carry-lshadow",       # 🌾 carry
    # 🎸 band-barnes-lshadow RETIRED 17-Aug (pm) — 0 of 9 of its episodes were
    # a coin 🌾 carry was not already holding. Removed here, not just guarded
    # in its own module: `FUNDING_BOOKS` drives every rivalry count in this
    # file, so leaving it would keep a dead book contending for supply it can
    # no longer take — the (gl) phantom-rival class with a corpse in it.
    "book-kiyosaki-lshadow",             # 🏦 Rich Dad
    # 🛢️ band-garrett-lshadow RETIRED 2-Sep (ww) — n=85, t=-2.22, upper
    # bound -0.455% <= 0 on its own ledger. Removed here for the (pm) reason:
    # this list drives every rivalry count, and a corpse in it keeps
    # contending for supply it can no longer take.
    "book-hull-lshadow",                 # 🧮 Hull ([2M,10M) x [7.8%,20%) — the
                                         # tile between Garrett and the Farmer)
    # 💸 the Farmer: LIVE arm retired 22-Aug (ta), SHADOW twin retired 2-Sep
    # (ww) — both rows leave the rivalry counts (the (pm) reason).
    "perps-funding-spread-lshadow",      # ⚖️ Counterweight
]
LIVE_BOOKS = {"perps-funding-lighter-lighter"}
CRYPTO_CLASS = 2

#: TWO ARMS OF ONE BOOK ARE NOT TWO BOOKS. 💸 the Farmer's live row and its
#: `-lshadow` twin are the experiment judge's EXPERIMENT/CONTROL pair — they are
#: SUPPOSED to hold the same coin, and the paired promotion bar depends on it.
#: Counting that as cross-book concentration is a false positive, and a detector
#: that cries wolf on a deliberate design is how a real finding later gets
#: ignored ((gl), and the (iw) currency audit's own first three runs).
#: Within-pair duplication is still REPORTED — divergence between the arms is
#: the implementation-shortfall signal — it just never counts as a finding.
ARM_PAIRS = [{"perps-funding-lighter-lighter", "perps-funding-lighter-lshadow"}]


def same_book(bots):
    """True when every holder of a coin belongs to ONE book's arm set."""
    s = set(bots)
    return len(s) > 1 and any(s <= pair for pair in ARM_PAIRS)


def db_url() -> str:
    u = os.environ.get("DATABASE_URL") or os.environ.get("DATABASE_PUBLIC_URL")
    if u:
        return u.strip()
    try:
        out = subprocess.run(
            ["railway", "variables", "--service", "Postgres", "--kv"],
            capture_output=True, text=True, timeout=60).stdout
    except Exception:  # noqa: BLE001
        out = ""
    for line in out.splitlines():
        if line.startswith("DATABASE_PUBLIC_URL="):
            return line.split("=", 1)[1].strip()
    sys.exit("no DATABASE_URL: set it in the env, or `railway login`")


def _extra(v):
    return v if isinstance(v, dict) else (json.loads(v) if v else {})


def holdings(cur):
    """{bot: {coin: side}} plus the books that DON'T say — reported, never
    silently treated as flat. A book that publishes no `held` is invisible to
    this audit, and invisible must never read as empty (I4/(kw))."""
    cur.execute("SELECT bot, open_trades, extra FROM bot_pnl WHERE bot = ANY(%s)",
                (FUNDING_BOOKS,))
    held, silent = {}, []
    for bot, open_n, extra in cur.fetchall():
        e = _extra(extra)
        h = e.get("held")
        if h is None:
            h = e.get("carries")
        if isinstance(h, dict):
            held[bot] = {c: (v if isinstance(v, str) else "?") for c, v in h.items()}
        elif int(open_n or 0) > 0:
            silent.append((bot, int(open_n or 0)))
        else:
            held[bot] = {}
    return held, silent


def living_gates(cur):
    """{bot: {enter_apr, min_vol}} read from each book's OWN published payload.

    Deliberately read rather than hand-listed: a gate copied into this file
    would drift from the running value, which is the exact failure
    `audit_lever_bounds`'s drift arm exists for. Books publish the pair in two
    shapes — top level (💸 Farmer, 🛢️ Garrett) or under `caps` (🌾 carry,
    🎸 Barnesy, 🏦 Rich Dad) — so both are accepted.
    """
    cur.execute("SELECT bot, extra FROM bot_pnl WHERE bot = ANY(%s)", (FUNDING_BOOKS,))
    out = {}
    for bot, extra in cur.fetchall():
        e = _extra(extra)
        caps = e.get("caps") if isinstance(e.get("caps"), dict) else {}
        g = {}
        for key, dest in (("enter_apr", "enter_apr"), ("min_vol", "min_vol"),
                          ("carry_min_vol", "min_vol"), ("max_vol", "max_vol"),
                          # [(mh)] the apr CEILING — 🧮 Hull is the first
                          # book with one; without this arm admits() counted
                          # a band book as a rival for supply ABOVE its band
                          # (the same (gl) phantom-rival class the volume
                          # ceiling already guards against, on the apr axis)
                          ("apr_hi", "apr_hi"),
                          # [(qx)] the persistence gate — published since the
                          # 🌾 12h move; books on one cell can now differ in
                          # REACH (carry 12h vs Rich Dad 6h), and a probe
                          # that ignores that credits the stricter book with
                          # windows it structurally cannot enter (the same
                          # phantom-rival class, on the TIME axis). Read here
                          # and printed per book; `supply_in`'s persist stays
                          # an explicit CELL parameter — pass the book's own
                          # value when asking about one book's reach.
                          ("persist_h", "persist_h")):
            v = e.get(key, caps.get(key))
            if isinstance(v, (int, float)) and not isinstance(v, bool) \
                    and dest not in g:
                g[dest] = float(v)
        # `max_vol` is legitimately absent on an unbounded book and legitimately
        # null on one that publishes it as "no ceiling" — those are the SAME
        # state and both mean unbounded. What is NOT the same is a book that
        # publishes no volume bound at all: that is UNKNOWN, and the caller
        # must not read it as unbounded (an unpublished ceiling is how 🛢️
        # Garrett's band got counted as a rival for a supply it excludes).
        g["vol_known"] = ("min_vol" in g) or ("max_vol" in g) \
            or ("max_vol" in e) or ("max_vol" in caps)
        # [2026-08-17 (ph)] THE CLASS SCREEN IS PART OF THE GATE, on the same
        # footing as the apr band `(mh)` and the volume band `(gl)` added. A
        # book that refuses non-crypto cannot be a rival for the non-crypto
        # half of a mixed supply, and calling it one is the phantom-rival class
        # those two arms already exist to prevent. Measured before fixing, at
        # `--gate 0.20 --allow-noncrypto`: the supply reads 14 coins deep
        # (MU, SAMSUNGUSD, SKHY, QQQ … all non-crypto) and 🌾 carry, 🎸 Barnes
        # and 🏦 Rich Dad were all listed as claiming it — while every one of
        # them screens crypto-only and can reach exactly 3 of those 14.
        # THREE-VALUED, like every other bound here: True / False / None for
        # "the book does not publish it". None must NOT be read as either — an
        # unpublished screen may not manufacture a finding and may not erase
        # one. `(pf)` gave 🌾 carry and 🎸 Barnes the declaration; until that
        # deploy lands they read None and this arm stays silent on them.
        co = e.get("crypto_only", caps.get("crypto_only"))
        g["crypto_only"] = co if isinstance(co, bool) else None
        # [2026-08-20 (sk)] A CONDITIONAL FLOOR IS NOT THE FLOOR IT PUBLISHES.
        # 🌾 carry's turnover floor became a FAST PATH rather than a verdict:
        # below it, a coin is admitted on MEASURED book depth and payback
        # (`funding_carry_bot.depth_admits`). So `caps.min_vol` still reads
        # $1M while the book's real reach extends underneath it, and this
        # guard — which exists to answer "who else can take this supply?" —
        # would UNDERSTATE the one book whose reach just grew. A gate this
        # file misdescribes is the (gl) phantom-rival class inverted: a rival
        # that is real and invisible, which is the worse direction, because an
        # UNDECLARED collision is what fails the run and a missed one is what
        # silently starves a sibling.
        #
        # NOT a guess at an effective number: there isn't one. The escape is
        # per-coin and depends on the live book, so the honest representation
        # of "how deep can this book reach" is UNBOUNDED BELOW. That is a
        # measurement, not a worst case — 2026-08-20, of the 16 hot books
        # under carry's floor, 16 of 16 filled its clip and repaid inside the
        # max hold (scripts/study_depth_vs_volume.py). The books it cannot
        # reach are excluded by PAYBACK, which is an apr-and-depth question
        # this file's volume axis cannot express, so the floor is the wrong
        # place to encode it and 0 is the truthful entry.
        da = e.get("depth_admit", caps.get("depth_admit"))
        g["depth_admit"] = da if isinstance(da, bool) else None
        if da is True:
            g["min_vol_published"] = g.get("min_vol")
            g["min_vol"] = 0.0
        if g.get("enter_apr") is not None:
            out[bot] = g
    return out


#: DECLARED cell collisions — living books whose gates already admit the same
#: supply region. The acknowledged-recurrence idiom (`STAGGER_OK`,
#: `BORN_DARK_OK`, `PARTIAL_SCREEN_OK`): an entry is a DECISION with an owner,
#: never a snooze, and an UNDECLARED collision fails the run.
#:
#: [2026-08-17 (pl)] Why this exists: I20 says *"run the supply check BEFORE
#: minting, and name every living book whose gate already admits them"* — and
#: that check was a command a human had to remember, with the cell's bounds
#: supplied by hand (`--gate 0.20 --floor 2e6`). Nobody ran it. That is exactly
#: how THREE books ended up on a cell that holds at most two coins at once. The
#: rule existed; the run did not — the `(gk)` shape.

#: [2026-08-27] ⚖️ Counterweight's 30 -> 40 widening, as DATA rather than prose.
#:
#: Written as constants because the first version was a sentence, and a mutation
#: round killed it: dropping a coin from the shared list left the declaration
#: still passing a `coin in why` check, because the same ticker also appears in
#: the admitted list two clauses earlier. That is the "a page-wide substring scan
#: is not a structural claim" rule landing on a guard's own declaration. The
#: prose below INTERPOLATES these, so the sentence and the set cannot drift.
#:
#: ADMITS — the 10 crypto names the scout top-up adds at width 40 (the core is
#: 30, so every width <= 30 admitted none of them).
FUNDSPREAD_TOPUP_ADMITS = ("FARTCOIN", "GRAM", "HBAR", "LIT", "PUMP", "TAO",
                           "TRUMP", "UNI", "ZEC", "ZRO")
#: CARRY_SHARED — the subset 🌾 carry held SHORT at the widening, i.e. the names
#: that will be double-counted in `fleet_allocation`'s independent claims. A
#: SNAPSHOT of a book that turns over: the structural claim (a rank book and a
#: level book meet at the tail of the same distribution) is what the declaration
#: rests on, not this roster.
FUNDSPREAD_CARRY_SHARED = ("FARTCOIN", "GRAM", "UNI", "ZEC", "ZRO")

KNOWN_CELL_COLLISIONS = {
    frozenset({"perps-funding-carry-lshadow", "book-kiyosaki-lshadow"}):
        "THE CARRY CELL (>=20% TRUE / >=$2M / crypto). Measured 17-Aug over "
        "9,662 scout snapshots / 33.7 days: occupied 5.93%, at most 2 coins at "
        "once, 3 distinct coins all window (KAITO 483 snapshots, XMR 71, "
        "PAXG 38). It held THREE books until 🎸 band-barnes was RETIRED (pm) "
        "on the I17 call — 0 of 9 of its episodes were a coin 🌾 carry was not "
        "already holding, i.e. zero independent evidence. The remaining TWO "
        "are differentiated in their rules though not in their published "
        "gate: 🏦 Rich Dad's payback-velocity bar is an EFFECTIVE ~21.9% "
        "(derived inside its exit rule, so `enter_apr` cannot show it) and its "
        "exits are its own (liability_flip 6h, decay_paid). [(qx) 18-Aug: the "
        "persistence AXIS now differentiates them too, and carry PUBLISHES it "
        "— caps.persist_h 12h vs Rich Dad's 6h greed guard, so the two books "
        "no longer take the same entry at the same instant: carry demands six "
        "more proven hours. living_gates reads it and the per-book line "
        "prints it; NOTE every recorded occupancy number (the 13.42% ladder "
        "included) was measured at 6h persist, so a carry-reach question "
        "must re-run supply at --persist-h 12 — a 6h read overstates what "
        "carry can take.] OPEN, OWNER: "
        "OPERATOR, next decision point ~12-Sep when 🏦 becomes gradeable — if "
        "it is still undecidable then, that is the same I17 call again. NOT a "
        "band change: re-banding 🛢️ Garrett to free the tier was measured and "
        "REFUSED (pl) because 6 of 6 of its top-ranked candidates are >=20%, "
        "so the narrowing would strip the fleet's only slot-filling funding "
        "book of its entire top of book. [(py) 18-Aug: PRICED on the band's "
        "own 30d tape — the ceiling takes Garrett +$4.82 -> -$15.71 (a "
        "$20.53 cost) and the tail ALONE is also negative under its "
        "ladder, i.e. the full-band RANKING is the edge; the Rich-Dad "
        "extension walk reads +$20.25 but KAITO is 107% of it — one "
        "episode, not a cell edge. Both halves of the split are measured "
        "REFUSED, not merely unpriced.] Do not stretch this line to cover a "
        "THIRD book: minting one here fails this guard, which is the point.",
    # [2026-08-18 (px)] 🌾 carry's floor moved $2M -> $1M (operator-directed
    # loosening, measured: cell occupancy 5.73% -> 13.42%, 3 -> 6 coins over
    # 34.9d). Its gate now overlaps 🛢️ Garrett's band on [$1M,$2M) x >=20%
    # TRUE — a POPULATED sliver (ROBO/ENA + KAITO's excursions) — so the
    # transitive component fuses all three. DELIBERATE, priced, and NOT the
    # [2026-09-02 (ww)] THE CARRY/GARRETT COMPONENT IS GONE: 🛢️ Garrett is
    # RETIRED (n=85, t=-2.22, upper bound -0.455% <= 0 on its own ledger),
    # so the three-book component (carry + Rich Dad + Garrett) and the
    # carry/Garrett sliver key both drop back to the carry/Rich Dad pair
    # declared above — exactly the fallback that entry pre-named. The
    # ranking-collision carried row (carry-garrett-ranking-collision) closes
    # with it. Kept as a note so the next reader of this map knows the
    # component existed and why it no longer needs a key.
    # [2026-08-27] ⚖️ Counterweight's scout universe widened 30 -> 40, which is
    # the FIRST width that admits any scout book at all (the configured core is
    # 30 names, so every earlier value was structurally inert — the live row
    # read `universe_n: 30` beside `universe: 25`). The 10 names it admits are
    # `FUNDSPREAD_TOPUP_ADMITS` above, and HALF of them —
    # `FUNDSPREAD_CARRY_SHARED` — are supply 🌾 carry is ALREADY holding on the
    # SAME SIDE, so I20's accounting cost
    # arrives at a book that had never been in this map before, and it is
    # declared BEFORE the first shared leg rather than after.
    #
    # WHY THE DETECTOR CANNOT FIND THIS ONE, and why that is the reason to
    # write it down rather than an excuse not to: `living_gates` keys on a
    # published `enter_apr`, and ⚖️ has none — it is a cross-sectional RANK, it
    # takes the top-K and bottom-K of whatever it sees and thresholds nothing.
    # So `collisions()` can never group it, `cells_collide` has no apr band to
    # compare, and this entry will not be MATCHED by a live run today. That is
    # the (sk) shape exactly ("a RANKING collision, not a gate collision ...
    # declared here rather than detected"), and the (pj) lesson beside it: a
    # detector's roster is part of the detector, so an overlap it structurally
    # cannot see is the one most worth declaring by hand.
    frozenset({"perps-funding-carry-lshadow", "perps-funding-spread-lshadow"}):
        "THE RANK/HARVEST OVERLAP ((ki)-screened crypto supply). ⚖️ "
        "Counterweight ranks the venue's funding cross-section and SHORTS its "
        "K=5 most-positive funders; 🌾 carry SHORTS coins paying >=20% TRUE "
        "for 12h. Those are the same names by construction at the extreme of "
        "the distribution, on the SAME SIDE. MEASURED at the 30 -> 40 "
        f"widening, 2026-08-27: of the {len(FUNDSPREAD_TOPUP_ADMITS)} crypto "
        f"names the top-up admits ({', '.join(FUNDSPREAD_TOPUP_ADMITS)}), "
        f"{len(FUNDSPREAD_CARRY_SHARED)} were held SHORT by 🌾 carry at the "
        f"widening — {', '.join(FUNDSPREAD_CARRY_SHARED)} — and four of those "
        "were re-confirmed open on the live /pnl.json at ship (ZEC had closed; "
        "carry turns over, so the set is a snapshot and the STRUCTURAL claim, "
        "not the roster, is what this declares). WHY IT IS DECLARED AND NOT "
        "REFUSED: the double-counted "
        "size is ~2% of the shared position — ⚖️ trades ~$5.00/leg (its $20 "
        "backtested clip at the allocation organ's 0.25 probe floor) against "
        "carry's $225-300 clips — and it is NOT the (lv) starvation shape: "
        "separate processes, separate held-sets, and ⚖️ is ALWAYS-IN with a "
        "fixed 10 legs, so it consumes none of carry's supply and carry "
        "consumes none of its ranking. The cost is I20's accounting one and "
        "the standing correction is the same: a coin held by both counts "
        "TWICE in fleet_allocation's independent claims, so report_now's "
        "effective-bet line is what to read. NOT a differentiation-by-row-id "
        "case either — ⚖️ takes a RANK and carry takes a LEVEL, which is a "
        "genuinely different rule reaching the same names at the tail, not a "
        "second copy of one gate. OPEN, OWNER: OPERATOR, at the row's own "
        "already-scheduled ~28-Aug keep-or-retire call ((jg)'s pre-registered "
        "criterion) for whether ⚖️ lives at all; and if it does, a second "
        "look at ~26-Sep — 30 rebalances, one full 24h-cadence era under the "
        "widened cross-section — asking whether the shared-name share of its "
        "legs is still ~2% of size or has grown. REVERT is one number: "
        "FUNDSPREAD_UNIVERSE_N back to 30 restores the hand list exactly, "
        "because 30 == the configured core.",
}


def cell_of(g):
    """(apr_lo, apr_hi, vol_lo, vol_hi, crypto_only) — the supply region a
    book's own published gate admits. `None` means unbounded on that edge."""
    return (g.get("enter_apr"), g.get("apr_hi"),
            g.get("min_vol"), g.get("max_vol"), g.get("crypto_only"))


def _ranges_overlap(lo_a, hi_a, lo_b, hi_b):
    """Half-open [lo, hi) overlap, with None as unbounded on either edge."""
    lo = max(lo_a or 0.0, lo_b or 0.0)
    hi = min(float("inf") if hi_a is None else hi_a,
             float("inf") if hi_b is None else hi_b)
    return lo < hi


def cells_collide(ga, gb):
    """Do these two books' gates admit any of the same supply?

    Both the apr band and the volume band must overlap. The class screen is
    NOT a separating axis: a crypto-only book and an unscreened one still
    compete for every crypto coin in the region, which is the whole supply the
    crypto-only one can see.
    """
    a, b = cell_of(ga), cell_of(gb)
    return (_ranges_overlap(a[0], a[1], b[0], b[1])
            and _ranges_overlap(a[2], a[3], b[2], b[3]))


def intersect(ga, gb):
    """The supply region both gates admit: (apr_lo, apr_hi, vol_lo, vol_hi,
    crypto_only). `crypto_only` is the STRICTER of the two — the region they
    genuinely contend for is only the part both can take."""
    a, b = cell_of(ga), cell_of(gb)
    return (max(a[0] or 0.0, b[0] or 0.0),
            min(float("inf") if a[1] is None else a[1],
                float("inf") if b[1] is None else b[1]),
            max(a[2] or 0.0, b[2] or 0.0),
            min(float("inf") if a[3] is None else a[3],
                float("inf") if b[3] is None else b[3]),
            bool(a[4]) or bool(b[4]))


def collisions(gates, has_supply=None):
    """Connected components of the gate-overlap graph, size >= 2.

    Components, not pairs: three books on one cell is ONE finding the operator
    decides once, not three pairwise ones they have to reassemble.

    [(pl)] `has_supply(region) -> bool` makes the edge MATERIAL rather than
    merely set-theoretic, and without it this detector is useless. Measured on
    the first run: 🌾/🎸/🏦 (`apr>=20%, vol>=$2M`) and 💸 the Farmer
    (`apr>=5%, vol>=$10M`) DO intersect on paper — at `apr>=20%, vol>=$10M` —
    so the transitive closure fused two genuinely different tiers into one
    5-book blob and reported it as a single cell. **That intersection has ZERO
    supply and always has**: `(ly)` measured it when 🎸's `extreme` sleeve died
    of the same $10M floor — *"no crypto book has ever cleared it at the 20%
    bar: observed max $5.53M, KAITO."* An overlap with no supply is not a
    collision, and a detector that fuses adjacent tiles over an empty sliver is
    one the operator learns to ignore (I20's own corollary).

    Omitting `has_supply` gives the pure set-theoretic answer, which is what
    the tests pin — the tape is not available to them.
    """
    names = sorted(gates)
    parent = {n: n for n in names}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for i, a in enumerate(names):
        for b in names[i + 1:]:
            if not cells_collide(gates[a], gates[b]):
                continue
            if has_supply is not None and not has_supply(
                    intersect(gates[a], gates[b])):
                continue
            parent[find(a)] = find(b)
    groups = defaultdict(set)
    for n in names:
        groups[find(n)].add(n)
    return sorted((frozenset(v) for v in groups.values() if len(v) > 1),
                  key=lambda s: (-len(s), sorted(s)))


def class_reach(g, supply_coins, is_crypto):
    """(n_reachable, note) — how many of THIS supply's coins the book's own
    class screen actually lets it take.

    [2026-08-17 (ph)] The class screen is part of the gate, on the same footing
    as `(mh)`'s apr ceiling and `(gl)`'s volume ceiling: a crypto-only book is
    not a rival for the non-crypto half of a mixed supply.

    Module level, not a closure inside `report_supply`, so it has ONE owner and
    can be tested directly — this file is named in CLAUDE.md as I20's
    enforcement and had no test of any kind before this.

    Three-valued in, three-valued out. `crypto_only is None` means the book does
    not publish the screen: that is UNKNOWN and must not be read as either
    answer, so the reach is left at full and the caller labels it. An
    unpublished screen may neither manufacture a finding nor erase one.
    """
    total = len(supply_coins)
    crypto = [c for c in supply_coins if is_crypto(c)]
    mixed = len(crypto) < total
    if not mixed:
        # Every coin is crypto: a crypto-only book reaches all of it and the
        # annotation would be pure noise.
        return total, ""
    if g.get("crypto_only") is None:
        return total, "  class screen UNPUBLISHED"
    if g.get("crypto_only") is True:
        return len(crypto), f"  crypto-only: reaches {len(crypto)} of {total}"
    return total, ""


def admits(g, gate, floor):
    """Does this living book's gate take the proposed supply?

    Returns "yes" / "no" / "unknown". Three-valued ON PURPOSE: a detector that
    collapses unknown into yes overstates and gets ignored ((gl)'s warning
    class), and one that collapses it into no under-reports the very
    concentration this script exists to find.
    """
    if g["enter_apr"] > gate + 1e-9:
        return "no"                      # stricter apr bar — never sees it
    if g.get("apr_hi") is not None and gate >= g["apr_hi"] - 1e-9:
        return "no"                      # [(mh)] supply sits ABOVE its apr
                                         # band (half-open ceiling)
    if not g.get("vol_known"):
        return "unknown"
    mn, mx = g.get("min_vol"), g.get("max_vol")
    if mx is not None and floor >= mx:
        return "no"                      # the supply sits ABOVE its band
    if mn is not None and mn > floor + 1.0:
        return "no"                      # its floor is above the supply
    return "yes"


def scout_classes(cur):
    cur.execute("SELECT payload FROM bot_state_history WHERE key='lighter-market' "
                "ORDER BY ts DESC LIMIT 1")
    row = cur.fetchone()
    return (row[0] or {}).get("classes", {}) if row else {}


def report_now(cur) -> int:
    held, silent = holdings(cur)
    print("=" * 78)
    print("CROSS-BOOK OVERLAP — what the funding books are holding RIGHT NOW")
    print("=" * 78)
    for bot in sorted(held):
        names = ", ".join(f"{c}({s})" for c, s in sorted(held[bot].items())) or "—"
        tag = "  [REAL MONEY]" if bot in LIVE_BOOKS else ""
        print(f"  {bot:32s} {len(held[bot]):2d}  {names}{tag}")
    if silent:
        print("\n  !! BOOKS HOLDING POSITIONS THEY DO NOT NAME "
              "(invisible to this audit, NOT flat):")
        for bot, n in silent:
            print(f"     {bot:32s} open={n}, no `held` field")

    by_coin = defaultdict(list)
    for bot, h in held.items():
        for c, s in h.items():
            by_coin[c].append((bot, s))
    dupes = {c: v for c, v in by_coin.items() if len(v) > 1}
    arm_only = {c: v for c, v in dupes.items() if same_book(b for b, _s in v)}
    dupes = {c: v for c, v in dupes.items() if c not in arm_only}
    print(f"\n  distinct coins held: {len(by_coin)}   "
          f"positions: {sum(len(h) for h in held.values())}")
    hard = 0
    if dupes:
        print("\n  COINS HELD BY MORE THAN ONE BOOK:")
        for c, v in sorted(dupes.items(), key=lambda kv: -len(kv[1])):
            sides = {s for _b, s in v}
            note = ("  <- SAME SIDE, concentration" if len(sides) == 1
                    else "  (opposing sides — the books partly net out)")
            flag = "  ** REAL MONEY IN THE STACK **" if any(
                b in LIVE_BOOKS for b, _s in v) else ""
            print(f"    {c:10s} x{len(v)}  " +
                  ", ".join(f"{b.split('-lshadow')[0]}({s})" for b, s in v) +
                  note + flag)
            if len(v) >= 3:
                hard += 1
    else:
        print("\n  no coin is held by two DIFFERENT books right now.")
    if arm_only:
        print("\n  (same coin on both arms of ONE book — by design, the judge's"
              " experiment/control\n   pair; reported, never a finding):")
        for c, v in sorted(arm_only.items()):
            print(f"    {c:10s} " + ", ".join(f"{b}({s})" for b, s in v))

    # Effective bet count: positions collapse to distinct (coin, side). The
    # metric is about EVIDENCE independence — `fleet_allocation` ranks each
    # book's claim as its own — so a book's two arms are collapsed into one
    # holder first. They are one book being measured twice on purpose, and
    # counting them as duplication would inflate the correction with the very
    # design the judge depends on.
    collapsed = {}
    for bot, h in held.items():
        key = next((min(p) for p in ARM_PAIRS if bot in p), bot)
        collapsed.setdefault(key, {}).update(h)
    slots = {(c, s) for h in collapsed.values() for c, s in h.items()}
    total = sum(len(h) for h in collapsed.values())
    if total:
        print(f"\n  EFFECTIVE BETS: {len(slots)} distinct (coin, side) across "
              f"{total} positions"
              f"  -> {100.0 * (1 - len(slots) / total):.0f}% of positions are duplicates")
        print("  NOTE: `fleet_allocation` ranks each book's claim independently, "
              "so duplicated\n        positions are counted as independent evidence. "
              "This number is the correction.")
    if hard:
        print(f"\n  FINDING: {hard} coin(s) held by THREE OR MORE books.")
    return hard


def report_supply(cur, gate: float, floor: float, persist_h: float,
                  crypto_only: bool) -> int:
    """What supply would a book with this gate actually get — and who already
    holds it? Run this BEFORE minting a funding book."""
    cur.execute("SELECT ts, payload FROM bot_state_history "
                "WHERE key='lighter-market' ORDER BY ts")
    rows = cur.fetchall()
    classes = (rows[-1][1] or {}).get("classes", {}) if rows else {}

    def is_crypto(c):
        try:
            return int(classes.get(c)) == CRYPTO_CLASS
        except (TypeError, ValueError):
            return False

    hot_since, snaps_with, coins, best = {}, 0, defaultdict(int), 0
    for ts, p in rows:
        t = ts.timestamp()
        f, v = p.get("funding") or {}, p.get("vols") or {}
        q = []
        for c, apr_pct in f.items():
            try:
                apr = abs(float(apr_pct)) / 100.0
            except (TypeError, ValueError):
                hot_since.pop(c, None)
                continue
            if apr >= gate:
                hot_since.setdefault(c, t)
            else:
                hot_since.pop(c, None)
                continue
            try:
                vol = float(v.get(c)) * 1e6
            except (TypeError, ValueError):
                continue
            if vol < floor or (t - hot_since[c]) < persist_h * 3600.0:
                continue
            if crypto_only and not is_crypto(c):
                continue
            q.append(c)
        if q:
            snaps_with += 1
            best = max(best, len(q))
            for c in q:
                coins[c] += 1
    n = len(rows) or 1
    days = (rows[-1][0] - rows[0][0]).total_seconds() / 86400.0 if rows else 0
    print("=" * 78)
    print(f"SUPPLY AT gate={gate:.0%} TRUE  floor=${floor/1e6:.1f}M  "
          f"persist={persist_h:g}h  crypto_only={crypto_only}")
    print("=" * 78)
    print(f"  tape: {n} scout snapshots over {days:.1f} days")
    print(f"  snapshots offering >=1 candidate: {snaps_with} ({100.0*snaps_with/n:.2f}%)")
    print(f"  max simultaneous candidates: {best}")
    print(f"  distinct coins over the window: {len(coins)}")
    for c, k in sorted(coins.items(), key=lambda kv: -kv[1])[:12]:
        print(f"     {c:12s} offered in {k:5d} snapshots  class={classes.get(c)}")
    if not coins:
        print("\n  VERDICT: this gate has NO supply on this venue. A book built "
              "here cannot trade.")
        return 1

    # ---- capacity vs supply ------------------------------------------------
    # A supply that cannot fill ONE book's cap cannot support two books, and
    # this is the fact a per-book census can never show: each book reports
    # "0 eligible" and reads as merely quiet.
    print(f"\n  CAPACITY vs SUPPLY: at most {best} coin(s) qualify at once.")

    # ---- gate collision ----------------------------------------------------
    # The decision input, and NOT the same question as "who holds it now": the
    # books may all be flat this minute and still be three claimants on one
    # supply. A gate ADMITS this supply when its bar is no stricter than the
    # proposed one — i.e. it would take the same coins whenever they appear.
    gates = living_gates(cur)
    buckets = defaultdict(list)
    for b, g in gates.items():
        buckets[admits(g, gate, floor)].append((b, g))
    rivals = buckets["yes"]

    # [(ph)] How much of THIS supply can each book's class screen actually
    # reach? One owner, module level — see `class_reach`.
    def _reach(g):
        return class_reach(g, list(coins), is_crypto)

    def _line(b, g):
        mn, mx = g.get("min_vol"), g.get("max_vol")
        band = ""
        if mn is not None or mx is not None:
            band = (f"  vol=[{(mn or 0)/1e6:.2f}M,"
                    f"{'inf' if mx is None else f'{mx/1e6:.2f}M'})")
        return (f"     {b:32s} enter_apr={g['enter_apr']:.3g}{band}{_reach(g)[1]}"
                + ("   [REAL MONEY]" if b in LIVE_BOOKS else ""))

    print()
    if rivals:
        print("  LIVING BOOKS WHOSE GATE ALREADY ADMITS THIS SUPPLY:")
        for b, g in sorted(rivals):
            print(_line(b, g))
    else:
        print("  no living book's gate admits this supply.")
    if buckets["no"]:
        print("\n  books EXCLUDED by their own band or bar (not rivals):")
        for b, g in sorted(buckets["no"]):
            print(_line(b, g))
    if buckets["unknown"]:
        print("\n  !! books whose VOLUME BOUND IS UNPUBLISHED — cannot be ruled "
              "in or out:")
        for b, g in sorted(buckets["unknown"]):
            print(_line(b, g))
        print("     (these are NOT counted as rivals below — an unpublished "
              "ceiling must not\n      manufacture a finding. Publish "
              "`min_vol`/`max_vol` on them to close the gap.)")

    held, _silent = holdings(cur)
    already = {c: [b for b, h in held.items() if c in h] for c in coins}
    taken = {c: v for c, v in already.items() if v}
    if taken:
        print("\n  ...and these coins are held RIGHT NOW:")
        for c, bots in sorted(taken.items()):
            print(f"     {c:12s} <- " + ", ".join(b.split("-lshadow")[0] for b in bots))

    print()
    if len(rivals) >= 2:
        # [(ph)] DEPTH IS WHAT THE RIVALS CAN REACH, not what the gate yields.
        # Quoting the full count while every rival is class-screened out of most
        # of it overstates the collision, and an overstating detector is one the
        # operator learns to ignore (I20's own corollary).
        depth = max(_reach(g)[0] for _b, g in rivals)
        qual = "" if depth == len(coins) else (
            f" (the gate yields {len(coins)}; the rivals' own class screens "
            f"reach {depth})")
        print(f"  VERDICT: {len(rivals)} living books already claim this supply, and it "
              f"is {depth} coin(s) deep{qual}.\n           A book minted here is largely "
              "the SAME BET at a new row id — not new\n           edge. Differentiate "
              "the gate (a different apr band or volume tier),\n           or do not "
              "mint it.")
        return 1
    if taken and len(taken) / len(coins) >= 0.5:
        print("  VERDICT: most of this supply is already held. Differentiate or "
              "do not mint.")
        return 1
    print("  VERDICT: supply exists and is not already spoken for.")
    return 0


def supply_in(rows, classes, region, persist_h=6.0):
    """(snapshots_with_supply, {coin: count}) for a cell region over the tape.

    The same walk `report_supply` runs, parameterised by a region so the
    collision check can ask "is this intersection actually populated?".

    [(qx)] `persist_h` is a CELL parameter, and 6.0 is only the historical
    convention every recorded occupancy number was measured at ((px)'s
    13.42% ladder included). It is NOT any particular book's reach any more:
    🌾 carry gates at 12h since (qx) while 🏦 Rich Dad stays at 6h — so a
    question about ONE book's reachable supply must pass that book's own
    published `caps.persist_h` (living_gates now reads it), and a 6h-persist
    occupancy read OVERSTATES a 12h book's supply (91% of qualifying windows
    are ≤6h; most of what 6h counts never survives to 12h).
    """
    apr_lo, apr_hi, vol_lo, vol_hi, crypto_only = region

    def is_crypto(c):
        try:
            return int(classes.get(c)) == CRYPTO_CLASS
        except (TypeError, ValueError):
            return False

    hot, snaps, coins = {}, 0, defaultdict(int)
    for ts, p in rows:
        t = ts.timestamp()
        f, v = p.get("funding") or {}, p.get("vols") or {}
        q = []
        for c, apr_pct in f.items():
            try:
                apr = abs(float(apr_pct)) / 100.0
            except (TypeError, ValueError):
                hot.pop(c, None)
                continue
            if apr >= apr_lo:
                hot.setdefault(c, t)
            else:
                hot.pop(c, None)
                continue
            if apr >= apr_hi:
                continue
            try:
                vol = float(v.get(c)) * 1e6
            except (TypeError, ValueError):
                continue
            if not (vol_lo <= vol < vol_hi):
                continue
            if (t - hot[c]) < persist_h * 3600.0:
                continue
            if crypto_only and not is_crypto(c):
                continue
            q.append(c)
        if q:
            snaps += 1
            for c in q:
                coins[c] += 1
    return snaps, dict(coins)


def report_collisions(cur) -> int:
    """Which LIVING books already share a supply cell? Returns the number of
    UNDECLARED collisions — the only thing that fails.

    [(pl)] This is I20's check, run off the books' OWN published gates instead
    of a cell a human had to type. It only became possible once every funding
    book published its full gate: the volume band `(lz)`, the apr ceiling
    `(mh)`, and the class screen `(pf)`/`(pj)`.
    """
    gates = living_gates(cur)
    # TWO ARMS OF ONE BOOK ARE NOT TWO BOOKS — the same rule `report_now` runs.
    # 💸 the Farmer's live row and its control twin have IDENTICAL gates by
    # construction (that is what makes the judge's paired bar valid), so they
    # collide with each other trivially and reporting it is pure noise.
    for pair in ARM_PAIRS:
        keep = sorted(pair & set(gates))
        for drop in keep[1:]:
            gates.pop(drop, None)
    cur.execute("SELECT ts, payload FROM bot_state_history "
                "WHERE key='lighter-market' ORDER BY ts")
    rows = cur.fetchall()
    classes = (rows[-1][1] or {}).get("classes", {}) if rows else {}
    # Fail OPEN on a dark tape: with no history every region reads empty and
    # the guard would report "no collisions" — a false all-clear. Fall back to
    # the set-theoretic answer, which over-reports rather than under-reports.
    _has = (lambda r: bool(supply_in(rows, classes, r)[1])) if rows else None
    found = collisions(gates, has_supply=_has)
    print("=" * 78)
    print("CELL COLLISIONS — living books whose OWN gates admit the same supply")
    print("=" * 78)
    if not found:
        print("  no two living books share a supply cell.")
        return 0
    undeclared = 0
    for grp in found:
        why = KNOWN_CELL_COLLISIONS.get(grp)
        head = "DECLARED" if why else "!! UNDECLARED"
        print(f"\n  {head}: {len(grp)} books share a cell")
        for b in sorted(grp):
            g = gates[b]
            mn, mx = g.get("min_vol"), g.get("max_vol")
            hi = g.get("apr_hi")
            # [(sk)] a floor of 0 that came from a DEPTH ESCAPE must say so:
            # printed bare it reads as "this book has no floor", which is a
            # different and much less useful fact than "this book's floor is
            # conditional and its published one is $Xm".
            _lo = ("depth" if g.get("depth_admit") is True
                   else f"{(mn or 0) / 1e6:.2f}M")
            print(f"     {b:32s} apr=[{g['enter_apr']:.3g},"
                  f"{'inf' if hi is None else f'{hi:.3g}'})"
                  f"  vol=[{_lo},"
                  f"{'inf' if mx is None else f'{mx/1e6:.2f}M'})"
                  # [(qx)] differential REACH on a shared cell: two books at
                  # one apr/vol cell with different persistence do not take
                  # the same entries (91% of qualifying windows die under 6h)
                  + (f"  persist={g['persist_h']:g}h"
                     if isinstance(g.get("persist_h"), float) else "")
                  + ("  crypto-only" if g.get("crypto_only") is True else "")
                  + ("   [REAL MONEY]" if b in LIVE_BOOKS else ""))
        if why:
            print(f"     -> {why}")
        else:
            undeclared += 1
            print("     -> NOT DECLARED. Either differentiate the gate (a "
                  "different apr BAND or volume\n        TIER — 🧮 Hull's "
                  "[2M,10M)x[7.8%,20%) is the worked example), or add this "
                  "group to\n        KNOWN_CELL_COLLISIONS with the "
                  "measurement, the reason and an owner (I20).")
    if undeclared:
        print(f"\n  FINDING: {undeclared} undeclared cell collision(s).")
    return undeclared


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--gate", type=float,
                    help="TRUE apr entry bar of a PROPOSED book, e.g. 0.20")
    ap.add_argument("--floor", type=float, default=2e6,
                    help="24h $ turnover floor of the proposed book (default 2e6)")
    ap.add_argument("--persist-h", type=float, default=6.0)
    ap.add_argument("--allow-noncrypto", action="store_true")
    ap.add_argument("--strict", action="store_true",
                    help="exit non-zero on ANY two-book overlap, not just 3+")
    args = ap.parse_args()

    import psycopg2
    conn = psycopg2.connect(db_url())
    cur = conn.cursor()
    try:
        if args.gate is not None:
            return report_supply(cur, args.gate, args.floor, args.persist_h,
                                 not args.allow_noncrypto)
        # [(pl)] The cell check runs by DEFAULT and needs no arguments — that is
        # the entire point. I20's instruction was to run the supply check before
        # minting, with the cell typed by hand, and it was never run.
        undeclared = report_collisions(cur)
        print()
        hard = report_now(cur)
        if undeclared:
            return 1
        if args.strict:
            held, _s = holdings(cur)
            by = defaultdict(int)
            for h in held.values():
                for c in h:
                    by[c] += 1
            return 1 if any(v > 1 for v in by.values()) else 0
        return 1 if hard else 0
    finally:
        conn.close()


if __name__ == "__main__":
    sys.exit(main())
