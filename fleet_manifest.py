#!/usr/bin/env python3
"""WHAT EACH BOOK IS FOR, AND WHAT FLYING LOOKS LIKE FOR IT.

**Operator, 2026-08-20: "we are tasked to create multiple strategy bots, who get
complimented and enhanced by instruments that let them fly to the ceiling if
they wish to, they know the floor all too well... they need to start growing and
learning with the brain that has every loss we've had or win and can let the
bots adjust themselves accordingly so they can achieve their designated
different designs. We need synergy."**

THE GAP THIS CLOSES. Measured 20-Aug: of nineteen living rows, **exactly one**
(🧭 nav-cook, the newest) publishes what it is FOR. Every other book's design
lives in 1,400 lines of `CLAUDE.md` prose — which no organ can read, no grader
can score against, and no operator can check a book's behaviour against without
finding the right paragraph. So every instrument in the fleet grades every book
against ONE rule, and the operator's word for what is missing is exactly right:
**synergy** — the fleet has nineteen different designs and one way of judging
them.

WHAT A DESIGN ENTRY IS, and each field earns its place:
  * `design`     — what this book is FOR, in its own terms. Not the strategy's
                   mechanics (the module has those); the JOB.
  * `flies_when` — **what the ceiling looks like FOR THIS BOOK.** This is the
                   divergent part and the reason the file exists: 🌾 carry flies
                   by holding more good carries at once, 🔮 georgia by filling
                   slots fast enough to become gradeable, 🧮 Hull by simply
                   surviving to 30 closes. One fleet-wide notion of "better"
                   cannot say any of that.
  * `floor`      — the constraint it must never trade away. Stated NEXT TO the
                   ceiling on purpose: a ceiling with no floor beside it is how
                   an instrument that says "go higher" becomes reckless.

THE BOOK'S OWN PUBLICATION WINS. `design_for` prefers `extra.thesis` off the
live row whenever a book publishes one, and falls back to the table here. That
is deliberate: this file is a BRIDGE, not a second source of truth — as each
book learns to declare itself (nav-cook's pattern) its entry here goes quiet on
its own, and the two can never drift into disagreeing, because the book wins.

NOTHING HERE DECIDES ANYTHING. It is read by `scripts/ceiling.py` to render a
book's ambition beside its measured headroom, and by the coverage guard. No
gate, no lever, no order.
"""

#: row id -> the book's design. Keyed by the DASHBOARD ROW, because that is
#: what every payload, ledger and grader uses.
DESIGN = {
    # ---- funding: paid to hold, not to be right about direction -----------
    "perps-funding-carry-lshadow": {
        "emoji": "🌾", "name": "Yield Harvester",
        "design": "Harvest persistent funding on the richest crypto perps, "
                  "delta-neutral, and get paid for patience rather than for "
                  "being right about price.",
        "flies_when": "it holds MORE good carries at once — its ceiling is "
                      "slots x supply, and its supply gate now measures depth "
                      "instead of guessing at it ((sk)).",
        "floor": "a carry must repay its own round trip; decay_paid is the "
                 "measured winner and the sided flips are the measured loss.",
    },
    "perps-funding-lighter-lighter": {
        "emoji": "💸", "name": "Funding Farmer (LIVE ARM RETIRED 22-Aug)",
        "design": "WAS the fleet's real money — take the venue's most extreme "
                  "funding directionally on the receiving side and bank the "
                  "reversion. RETIRED (ta): horizon `unreachable` on BOTH arms, "
                  "and 🔮 georgia takes the sub-account.",
        "flies_when": "nothing does, and that is the finding. Its take-profit "
                      "exit is 100% win on both arms while everything else is "
                      "drag ((sk)), and (su) then measured that no gate from "
                      "0.05 to 0.60 and no exit of twelve turns the rest "
                      "positive on the population the book can actually trade. "
                      "A book whose only winning exit cannot be reached more "
                      "often has no ceiling to raise.",
        "floor": "the SHADOW twin is not retired and must keep trading — it is "
                 "the control arm, and silencing it was the one expensive way "
                 "to get this retirement wrong.",
    },
    "freqtrade-georgia-lighter": {
        "emoji": "🔮", "name": "Georgia (LIVE)",
        "design": "The fleet's real money from 22-Aug (ta): the same intraday "
                  "15m three-tag book as the shadow arm, on the sub-account 💸 "
                  "the Farmer gave up, running the shared variant host.",
        "flies_when": "its shadow twin's `t` finally clears 2.0 and the live "
                      "ledger agrees. It went live at 5 of 6 bars — the "
                      "missing one is `t` = 1.48 — so what it needs is CLOSES "
                      "at the same mean, not a better idea.",
        "floor": "it went live WITHOUT passing the gate, on Eamon's explicit "
                 "call, so the drawdown arithmetic is the whole guardrail: "
                 "above 9.09x its -5% stop cannot fire before liquidation, and "
                 "that is a broken rail rather than a risk preference.",
    },
    "perps-funding-lighter-lshadow": {
        "emoji": "💸", "name": "Funding Farmer (shadow twin)",
        "design": "The control arm and the experiment bench for the live "
                  "Farmer — the ONLY designed path to more real money.",
        "flies_when": "the paired bar can actually promote something. It had "
                      "not in five weeks, because the comparison was rigged "
                      "against it ((sk)).",
        "floor": "it must stay comparable to the live arm, or it measures a "
                 "policy delta and calls it edge.",
    },
    "perps-funding-spread-lshadow": {
        "emoji": "⚖️", "name": "Counterweight",
        "design": "A dollar-neutral funding cross-section: long the payers, "
                  "short the receivers, and collect the spread between them.",
        "flies_when": "it has an exit that is not a clock. Its only two exits "
                      "are the 24h rebalance, and it is always-in by "
                      "construction, so every I7 reading applies to it first.",
        "floor": "delta-neutrality is the thesis; a drifting basket is a "
                 "directional book nobody chose to run.",
    },
    "band-garrett-lshadow": {
        "emoji": "🛢️", "name": "Garrett",
        "design": "The thin-tier funding band [$0.1M, $2M) — the tier the "
                  "fleet's own study measured RICHER per episode than the "
                  "liquid one, run by the proven funding machine.",
        "flies_when": "its band stays its own. 🌾 carry's measured-depth gate "
                      "now reaches the same coins, and 6 of 6 of Garrett's "
                      "top-ranked candidates are >=20% APR ((sk)).",
        "floor": "env-only config and no tuning lane — a single-policy clock "
                 "by construction.",
    },
    "book-hull-lshadow": {
        "emoji": "🧮", "name": "The Professor",
        "design": "Hull's cost-of-carry machinery on the one funding cell no "
                  "other book enters: TRUE |apr| in [7.82%, 20%) x [$2M, $10M).",
        "flies_when": "it simply REACHES 30 closes. Its founding claim is the "
                      "only one in the books cohort that survived "
                      "re-measurement (n=50, +$6.69, t=+3.92); its binding bar "
                      "is the clock, not the statistic.",
        "floor": "delta-neutral MODELLED — P&L is accrued minus fees with no "
                 "price term, and that is structural.",
    },
    "book-kiyosaki-lshadow": {
        "emoji": "🏦", "name": "Rich Dad",
        "design": "Kiyosaki as mechanical rules: hold only assets that PAY "
                  "you, sell a liability the moment it starts charging, and "
                  "close only after the trade has paid itself back.",
        "flies_when": "the carry cell has room for two books. It shares that "
                      "cell with 🌾 carry by declaration, owner OPERATOR, "
                      "~12-Sep.",
        "floor": "payback velocity — funding must repay 30bps within 120h, a "
                 "TIGHTENING of the validated gate, never a loosening.",
    },
    # ---- directional: right about price, or nothing ------------------------
    "lighter-ticket-taker-lshadow": {
        "emoji": "🎫", "name": "Ticket Taker",
        "design": "Trade the scout's high-conviction tickets and grade every "
                  "lens independently, so the fleet learns WHICH signal works "
                  "rather than whether signals work.",
        "flies_when": "its breakout arm is allowed to run. The trend exit has "
                      "no TP cap, a wide stop and a trail — every part says "
                      "let it run — and it inherits a reversion book's clock.",
        "floor": "the realised lens veto is senior to any proxy: a lens that "
                 "loses on its OWN record stops trading, whatever a forward "
                 "grade says (I14).",
    },
    "freqtrade-georgia-lshadow": {
        "emoji": "🔮", "name": "Georgia",
        "design": "Intraday 15m day-trading across three tags — trend "
                  "breakout, range mean-reversion and bounce pullback — each "
                  "graded on its own.",
        "flies_when": "it FILLS ITS SLOTS. 5 of 6 go-live bars, failing only "
                      "t; 310 closes from gradeable at 0.5 of 5 slots (83.5 "
                      "days) or 7.6 days at full occupancy. It is the closest "
                      "book in the fleet to real money ((sm)).",
        "floor": "its trailing stop is NOT the leak — reclaim 74% against a "
                 "placebo of 75%. Do not widen it.",
    },
    "freqtrade-avo-maria-lshadow": {
        "emoji": "🙏", "name": "Avo Maria (shadow)",
        "design": "Buy the dip inside a 4h uptrend and sell into strength.",
        "flies_when": "…it is honest about what it is. Its ENTRY was measured "
                      "exit-free against matched-random and predicts NOTHING "
                      "((qu)); the operator KEPT it on the record at a measured "
                      "-$0.68/month with a pre-registered revert criterion.",
        "floor": "do not widen the entry — that is refuted, not unmeasured.",
    },
    "freqtrade-avo-maria-lighter": {
        "emoji": "🙏", "name": "Avo Maria (LIVE)",
        "design": "The live expression of the dip-in-uptrend book, sized to "
                  "the balance rather than to a paper grand.",
        "flies_when": "its shadow twin's revert criterion resolves in its "
                      "favour on the pooled ledger.",
        "floor": "real money: no brain multiplier, no allocation read, no "
                 "tuning lane of its own.",
    },
    "freqtrade-mum-lshadow": {
        "emoji": "👩", "name": "Mum v2",
        "design": "Deep-oversold rebound on 1h, OUTSIDE the uptrend — "
                  "deliberately disjoint from 🙏 avo's cell — with the bracket "
                  "fixed at entry and a 12h carry-bounded cap.",
        "flies_when": "her clock keeps working. v1 died of the CLOCK, not of "
                      "losing: ~2.4 closes/30d meant ~12 months to a 30-close "
                      "bar. She is +4.658%/trade on a cap of FOUR ((sm)).",
        "floor": "she carries her own CONTROL ARM — the first live book to do "
                 "so — so her edge is answered from her own payload.",
    },
    "band-kelly-lshadow": {
        "emoji": "🪁", "name": "the Mirror",
        "design": "Hold the OPPOSITE side of the fleet's measured losers over "
                  "exactly the windows the loser would have traded. From "
                  "little things big things grow.",
        "flies_when": "its ghosts keep being wrong. Its roster is measured, "
                      "not assumed — brkfade was REFUSED because its ghost "
                      "does not actually lose.",
        "floor": "a mirror's haircut scales with the GHOST's coin liquidity; "
                 "grade against +0.397%/trade, not the naive negation.",
    },
    "nav-cook-lshadow": {
        "emoji": "🧭", "name": "Captain Cook",
        "design": "Chart the shallows: the residual dislocation band [45, 60) "
                  "bps, strictly BELOW 🪁 Kelly's floor, so the two TILE the "
                  "surface and neither can starve the other.",
        "flies_when": "it holds to its measured horizon instead of harvesting "
                      "its own entry gate — 34 of 34 exits `converged` at a 5.5 "
                      "minute median against a 4h plateau.",
        "floor": "the deep tail is measured NEGATIVE and refused; this is a "
                 "band with a ceiling, not a floor.",
    },
    "book-douglas-lshadow": {
        "emoji": "🧘", "name": "The Zone",
        "design": "Fade extreme impulses with a bracket fixed at entry and "
                  "never widened. Consistency is STRUCTURAL — the same clip "
                  "every trade, whatever the last one did.",
        "flies_when": "its measured edge survives contact with its own ledger; "
                      "its tp side is 11 of 11 winners and its sl side is the "
                      "whole loss.",
        "floor": "the revenge-guard overlay was measured HARMFUL. Douglas's "
                 "own rule — the market does not know about your last trade — "
                 "beat the first reading of him.",
    },
    "book-grimes-lshadow": {
        "emoji": "📐", "name": "The Technician",
        "design": "Ship the TEST, not the setup: a roster behind a rolling "
                  "replay gate that re-decides every 6h which setups may "
                  "trade at all. Twelve pre-declared variants beat random; "
                  "none of them beat random.",
        "flies_when": "its gate opens on EDGE rather than on universe churn — "
                      "coin selection alone moved its `t` by 3.82 against a "
                      "bar of 0.5 ((oe)), which is why it now grades a fixed set.",
        "floor": "a gate that stays shut long enough is a keep-or-retire call, "
                 "never a bar-lowering session.",
    },
    "lighter-perp-sniper-lshadow": {
        "emoji": "🎯", "name": "Perp Sniper",
        "design": "Catch a book in its debut regime — new listings, volume "
                  "surges, and young books the venue has only just created.",
        "flies_when": "it banks a winner. Every exit but ONE in its life is "
                      "the 6h clock; the exception is a listing tp at +15.2%.",
        "floor": "the listing thesis is REFUTED and its supply is dead — 0 "
                 "crypto births Jun-Aug ((qi)). Surge is the only live source.",
    },
    "pm-albanese-lshadow": {
        "emoji": "🏛️", "name": "Albanese",
        "design": "One of the Parliament's surviving shadow books — trend, "
                  "graded by Howard's ecosystem brain and tuned by its own "
                  "replay-gated tuners.",
        "flies_when": "it accumulates decidable sample: 632 closes to t=2.0, "
                      "639 days at today's occupancy and 147 at full.",
        "floor": "shadow-only forever until the standard go-live gate.",
    },
    "pm-turnbull-lshadow": {
        "emoji": "🏛️", "name": "Turnbull",
        "design": "The Parliament's mean-reversion book — fade the stretch "
                  "and take the snap back, on the same six-layer ecosystem "
                  "the other PMs run.",
        "flies_when": "it trades at all — 0.2 of 4 slots, and 1,891 days to "
                      "decidability at that rate against 117 at full.",
        "floor": "shadow-only forever until the standard go-live gate.",
    },
}


def design_for(row, extra=None):
    """The book's design. Its OWN published `extra.thesis` wins.

    A book that declares itself is authoritative — this table is a bridge for
    the eighteen that do not yet, and each entry goes quiet on its own the day
    its book learns to publish. Returns None for an unknown row rather than
    inventing a design, because a made-up purpose is worse than no purpose.
    """
    own = (extra or {}).get("thesis") if isinstance(extra, dict) else None
    if isinstance(own, dict) and own:
        d = dict(own)
        d.setdefault("source", "the book's own payload")
        return d
    d = DESIGN.get(row)
    if not d:
        return None
    d = dict(d)
    d["source"] = "fleet_manifest (the book does not publish one yet)"
    return d


def uncovered(rows):
    """Living rows with no design anywhere — the coverage the guard enforces."""
    return sorted(r for r in rows if not design_for(r))


def _selftest():
    assert DESIGN, "the manifest is empty"
    for row, d in DESIGN.items():
        for k in ("emoji", "name"):
            assert d.get(k), (row, k)
        # the three that must SAY something — a one-word design is a label
        for k in ("design", "flies_when", "floor"):
            assert d.get(k) and len(d[k]) > 40, (row, k)
        # the whole point: `flies_when` must say something about THIS book, not
        # repeat a fleet-wide platitude
        assert d["flies_when"] != d["floor"], row
    # divergence, asserted: no two books may share a ceiling description
    flies = [d["flies_when"] for d in DESIGN.values()]
    assert len(set(flies)) == len(flies), "two books share a `flies_when`"

    # the book's own publication WINS, and is labelled as its own
    own = design_for("nav-cook-lshadow",
                     {"thesis": {"cell": "residual band", "declared": "x"}})
    assert own["cell"] == "residual band"
    assert own["source"] == "the book's own payload"
    # …and the table is the fallback, labelled as such
    fb = design_for("perps-funding-carry-lshadow", {})
    assert fb["emoji"] == "🌾" and "does not publish" in fb["source"]
    # an empty/junk thesis does NOT win — it falls back rather than publishing
    # a book with no design at all
    for junk in ({}, {"thesis": {}}, {"thesis": "words"}, {"thesis": None}):
        assert design_for("perps-funding-carry-lshadow", junk)["emoji"] == "🌾"
    # an unknown row gets NOTHING — a made-up purpose is worse than none
    assert design_for("no-such-book") is None
    assert uncovered(["no-such-book", "nav-cook-lshadow"]) == ["no-such-book"]
    print(f"fleet_manifest selftest OK ({len(DESIGN)} books declared)")
    return 0


if __name__ == "__main__":
    import sys
    if "--selftest" in sys.argv:
        raise SystemExit(_selftest())
    for row, d in sorted(DESIGN.items()):
        print(f"\n{d['emoji']}  {d['name']}  ({row})")
        print(f"   DESIGN     {d['design']}")
        print(f"   FLIES WHEN {d['flies_when']}")
        print(f"   FLOOR      {d['floor']}")
