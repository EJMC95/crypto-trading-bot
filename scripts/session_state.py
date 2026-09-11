#!/usr/bin/env python3
"""START HERE. What shipped, what is carried, what is stuck — DERIVED, not remembered.

**Operator, 2026-08-20: "can all of the works done today; every day be recorded
properly so I am starting from where I left off every day rather than doing
circles like an incompetent."**

The fleet already had a record: `CHANGELOG.md`, 9,000+ lines of prose. It is an
excellent history and a terrible handoff — nothing in it answers "what do I pick
up first?" without reading a day's worth of entries, and `audit_recurrence`
exists precisely because that failure is measurable: the changelog keeps
returning to subjects nobody closed.

I11 already says the right thing — *"State at the end of every pass what is
carried, and start the next pass from that list"* — and it is the one invariant
with no executable enforcement, which is why it has been observed by memory and
therefore not at all.

WHAT MAKES THIS DIFFERENT FROM ANOTHER DOCUMENT THAT ROTS: almost nothing here
is typed by hand.

  * **SHIPPED** is read from git — commits since local midnight, and the
    changelog letters they carry.
  * **FLEET SIGNALS** are read from the live fleet — staleness on the feed's
    own verdict, any live book shut right now, and any book at or one bar from
    the go-live gate. [2026-09-10, CORRECTED IN PLACE per I12: this line read
    *"STUCK is read from the live fleet — books with no closes, levers pinned at
    a cage end, organs past their own TTL"* from (sl) until today, and **no such
    section existed and this file read no feed at all**. A handoff that
    advertises a check it does not run is worse than one that admits the gap —
    a session reads the promise and stops looking. `fleet_signals()` is that
    section, built to Eamon's ask on 10-Sep; levers-at-a-cage-end and
    organ-TTL remain UNBUILT and are deliberately not claimed here.]
  * **CARRIED** is the one hand-written part, and every entry carries a
    `closes_when` PREDICATE that this script evaluates against the repo. An
    item whose predicate says DONE is reported as **CLOSE THIS** and fails
    `--check`. **You cannot carry work that is already finished, and the list
    cannot quietly become a museum** — which is the exact failure mode of every
    to-do list this repo has tried.

Times are Australia/Sydney, because the operator reads them (CLAUDE.md's
reporting rule); everything internal stays UTC.

    python3 scripts/session_state.py            # print it
    python3 scripts/session_state.py --write    # regenerate HANDOFF.md
    python3 scripts/session_state.py --check    # CI: no stale carried item
    python3 scripts/session_state.py --selftest
"""
import argparse
import datetime as _dt
import json
import os
import re
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HANDOFF = os.path.join(ROOT, "HANDOFF.md")
SYD = _dt.timezone(_dt.timedelta(hours=10))     # AEST; AEDT Oct-Apr is +11


def _sh(*args):
    try:
        return subprocess.run(args, cwd=ROOT, capture_output=True, text=True,
                              timeout=30).stdout.strip()
    except Exception:                                            # noqa: BLE001
        return ""


def _has(path, needle):
    try:
        with open(os.path.join(ROOT, path)) as fh:
            return needle in fh.read()
    except OSError:
        return False


# ---------------------------------------------------------------------------
# CARRIED — the one hand-written list, and every row must be falsifiable.
#
# `closes_when` returns True when the item is DONE. A row whose predicate is
# True is reported CLOSE THIS and fails --check, so the list cannot rot in
# either direction: a finished item cannot linger, and an unfinished one cannot
# be dropped without deleting a row somebody has to justify deleting.
#
# `owner` is who can close it. "session" = the next session may just do it;
# "OPERATOR" = it needs a decision this repo may not make.
# ---------------------------------------------------------------------------
CARRIED = [
    {
        "id": "market-context-realerts-a-retired-books-frozen-census",
        "owner": "session",
        "what": "(aba) THE SOURCE HALF OF THE FOSSIL-ALERT FIX IS NOT SHIPPED. "
                "`market_context.fire_alerts` reads "
                "`lighter-dislocation-lshadow` and fires one `disloc:<coin>` "
                "alert per census entry with NO age check on the publisher -- "
                "content before liveness, which is I1 -- and `_alert`'s dedup "
                "refreshes `last_seen` on every hit, so `fleet_immune."
                "alert_fossils`' age arm can never reach them. 🧲 Snap Back "
                "was retired 4-Aug (jh); its census has been frozen since, "
                "and it was still manufacturing 19 fresh alerts a day five "
                "weeks later. MEASURED on the 10-Sep evidence review: 19 of "
                "23 verdict rows were that one dead book repeating one "
                "sentence. TWO layers shipped today -- the antibodies that "
                "neutralise it in the bloodstream (`fleet_immune.ANTIBODIES`, "
                "aim-tested against the publisher's own format strings) and "
                "the render-side fold that stops the report being 83% fossil "
                "-- and BOTH are downstream of a source that keeps lying.",
        "why_open": "The source fix is an age gate at that read, in "
                    "`market_context.py`, which is a SHIPPED service: it "
                    "needs the publisher's `updated` stamp read and a bar "
                    "chosen, then a deploy and a payload readback, which is "
                    "more than an antibody costs and was not done in the pass "
                    "that found it. The same `_alert` shape appears at SIX "
                    "other call sites in that file, so the honest fix is the "
                    "CLASS (a freshness gate every alert source passes "
                    "through), not a seventh instance. Closes when "
                    "`market_context.py` reads the publisher's age before its "
                    "census and the CHANGELOG records it -- at which point "
                    "the two antibodies can be deleted and this row with them.",
        # Closes when the SOURCE reads the publisher's age. Keyed on the
        # CHANGELOG rather than on market_context's source, so a half-edit
        # that adds the words without shipping the behaviour cannot close it.
        "closes_when": lambda: _has("CHANGELOG.md",
                                    "fossil-alert source gate READ:"),
    },
    {
        "id": "offered-set-feed-window-caps-the-only-powered-search",
        "owner": "session",
        "what": "(aaq) THE CHEAPEST LARGE WIDENING AVAILABLE TO THIS FLEET, "
                "and it is a FEED CONSTANT rather than a recording gap. The "
                "scout's OFFERED ticket population -- the only taker "
                "population with enough power to resolve an effect the size "
                "anyone hopes for (mde80 0.30%/trade at n=2,736, against the "
                "ledger's 1.26) -- is retained for 60 DAYS by "
                "`bot_pnl_store.prune_history`, and the only reason the "
                "11-Sep search saw 8.3 of them is that `pnl_dashboard` caps "
                "`/bus.json?hours=` at 200h. Measured: `tickets` are 9.7% of "
                "the lighter-market payload (1.09 MB of 11.21 MB per 24h), so "
                "60d of TICKETS is ~65 MB against 672 MB for the whole "
                "payload. A tickets-only projection on that SELECT plus a "
                "higher cap on that path takes the search from 8.3d to 60d -- "
                "~7x n, mde80 0.30 -> ~0.11%/trade -- and it is "
                "DASHBOARD-ONLY: no trading image, no deploy marker, no "
                "expectancy price, no trade changes.",
        "why_open": "NOT shipped in the pass that found it, deliberately. It "
                    "changes a shared READ PATH on `bot_state_history` -- the "
                    "table behind (zq)'s lock convoy, where a never-committed "
                    "read transaction blocked every bot's publish fleet-wide "
                    "for ~40 minutes including both real-money rows. A wider "
                    "SELECT on that table earns its own careful pass with the "
                    "autocommit/lock_timeout discipline and a measured query "
                    "plan, not a tired one at the end of a long session. "
                    "BEFORE SHIPPING: confirm the projection actually reduces "
                    "the scan (not just the payload), check "
                    "`pg_blocking_pids` during a trial run, and verify no "
                    "publisher queues behind it. THEN re-run "
                    "`scripts/study_taker_offered_2026-09-11.py` at the wider "
                    "window -- its pre-registration "
                    "(PREREG_TAKER_OFFERED_2026-09-11.md) still governs and "
                    "the bar does not move. Closes when the CHANGELOG records "
                    "'offered-set 60d READ:' with the re-run verdict.",
        "closes_when": lambda: _has("CHANGELOG.md", "offered-set 60d READ:"),
    },
    {
        "id": "null-basis-and-window-mismatch",
        "owner": "session",
        "what": "(aar) adversarial verification of the taker's random-entry "
                "null found THREE defects. One is FIXED (the side inference "
                "read a nullable column and replayed 7 of 208 era closes as "
                "SHORTS; corrected to derive from the tag, AST-pinned at both "
                "call sites, verdict unchanged and stronger on every family). "
                "TWO ARE RECORDED AND NOT PATCHED. (1) THE CALIBRATION GATE "
                "CERTIFIES A PRICE BASIS THE NULL NEVER USES: `replay_real` "
                "enters at the ledger's own FILL price while the null's `mu` "
                "enters at an HOURLY BAR CLOSE, so `d_i` mixes two bases; run "
                "the book's own closes through the null's path and the drift "
                "is 0.661pp, ABOVE the 0.60pp tolerance -- i.e. on one "
                "consistent basis the gate would REFUSE, and the family "
                "excess reads -0.993pp (t -1.17) rather than -0.242pp. (2) "
                "THE NULL IS TIME-BLIND: both docstrings claim 'same coin, "
                "SAME window' and the draw is uniform over the coin's entire "
                "~46d tape. Hour bias is small (-0.100 to +0.136pp); WEEKEND "
                "bias is +0.632pp.",
        "why_open": "NOT patched in the same pass under the fleet's own 'ship "
                    "narrow, verify in the live payload, then widen' rule -- "
                    "(fz) changed six surfaces at once and spent six entries "
                    "repairing itself. BOTH defects push the refusal the SAME "
                    "way (against the book), so no verdict of (aaf)/(aan)/"
                    "(aar) depends on them and nothing is blocked on this. "
                    "What IS blocked: no time-conditioned cell from this null "
                    "may be read as matched until (2) is fixed, and no "
                    "absolute level from it may be quoted until (1) is. Fix "
                    "(1) by walking BOTH arms from the same price basis "
                    "(prefer the bar close, which the null cannot avoid) and "
                    "re-running the gate; fix (2) by drawing within a matched "
                    "window rather than the whole tape. Closes when the "
                    "CHANGELOG records 'null basis+window READ:' with the "
                    "re-run numbers.",
        "closes_when": lambda: _has("CHANGELOG.md", "null basis+window READ:"),
    },
    {
        "id": "live-vs-graded-policy-two-mechanisms-uncovered",
        "owner": "session",
        "what": "(aan) shipped `golive_readiness.live_fillable`, which closes "
                "ONE of the three mechanisms by which a book's LIVE arm can "
                "run a narrower or different policy than the arm the go-live "
                "gate grades: the per-mode LENS/SIDE allow-list. A fleet "
                "sweep of all 14 graded books confirms the other two are real "
                "and UNCOVERED. (2) THE LEVER LANE: `apply_tuning()` returns "
                "{} on 🎫 the taker's live arm, so a live arm takes NO "
                "growth-rail lever while the graded shadow ran tuner-moved "
                "bars -- its era spans 19 distinct bracket settings (tp in "
                "{0.03,0.04,0.05,0.06}, max_hold_h in {24,48,72}, brk_range "
                "in {0.91,0.93,0.95,0.97}). Intersecting both taker "
                "mechanisms: **2 of 208 closes (1.0%) are BOTH live-fillable "
                "AND booked at bars a live arm would run.** (3) THE CAPACITY "
                "PIN: ⚖️ Counterweight's live arm pins `K = GOLIVE_K` and "
                "refuses the `fundspread.k` lever; K is a rank truncation, so "
                "it changes WHICH coins are held. LATENT today (env default "
                "K=5 == GOLIVE_K=5, no lever open), not absent. AND A SECOND "
                "CONFIRMED BOOK, DIRECTION INVERTED: 👩 mum's shadow is "
                "NARROWER than live -- the judge's `xp.mum.vel_lo/vel_hi` "
                "steer the twin only, the velocity band is an ENTRY filter, "
                "and her own census reads `vel_in_band 2 of vel_read 102`, so "
                "the graded sample is a strict SUBSET of the live population. "
                "CLAUDE.md already says 'while running, the twin is an "
                "EXPERIMENT arm, not a control arm'; the GRADER does not know "
                "it.",
        "why_open": "DELIBERATELY NOT SHIPPED IN (aan), under the fleet's own "
                    "'SHIP NARROW, VERIFY IN THE LIVE PAYLOAD, THEN WIDEN' "
                    "rule -- (fz) changed six surfaces in one pass and "
                    "produced six follow-up entries repairing itself. "
                    "`live_fillable` is verified end-to-end on the deployed "
                    "payload for mechanism (1) ONLY; mechanisms (2) and (3) "
                    "have no instrument. THE PRIOR ART TO START FROM, both "
                    "found by the sweep: the experiment judge ALREADY "
                    "detects live/shadow policy divergence precisely "
                    "(`policy_stamp` as ONE builder shared by both hosts, "
                    "`policy_fields`, `policy_waived`, publishing "
                    "`unjudgeable:policy_mismatch`) -- but it gates "
                    "PROMOTION, and nothing equivalent gates the GO-LIVE "
                    "GATE; and ⚖️ Counterweight is the ONE book that solved "
                    "the gate half, its `golive_blocker` keyed on the LIVE "
                    "row id with the (ry) note 'a READY SHADOW twin must "
                    "never arm the LIVE arm' -- no other book has that guard, "
                    "and its honest cost is that the gate is then unpassable "
                    "until a live arm has its own 30-close ledger. NOTE the "
                    "class was named in PROSE seven weeks ago on this same "
                    "book -- lighter_ticket_taker.py:361-365, (hr) 31-Jul: "
                    "'the shadow arm was admitting books the money arm would "
                    "never touch -- which is not a conservative difference, "
                    "it is a grading error in the permissive direction' -- "
                    "and that entry fixed the INSTANCE and left the class "
                    "open. FLAGGED, NOT COUNTED: scanned-universe width "
                    "differs on both live pairs (mum 94 live vs 103 shadow, "
                    "avo 63 vs 77) and universe is not a policy_stamp field, "
                    "so a real narrowing would be invisible to the era, the "
                    "judge AND the gate -- unattributed, verify before "
                    "acting. Closes when the CHANGELOG records "
                    "'live-vs-graded mechanisms READ:' with a verdict on "
                    "each of (2) and (3).",
        "closes_when": lambda: _has("CHANGELOG.md",
                                    "live-vs-graded mechanisms READ:"),
    },
    {
        "id": "hull-cap-13-deferred-to-one-turnover",
        "owner": "session",
        "what": "(aaa) 🧮 Hull's cap raise (MAX_POSITIONS 10 -> 13 with "
                "CLIP_USD 80 -> 60 at constant gross) is MEASURED AND "
                "DEFERRED, not refused. The cap binds hard -- 83.2% of 3,906 "
                "census snapshots at cap, 37.6% at cap WITH an eligible coin "
                "it cannot take, 2,809 coin-snapshots denied -- and the "
                "marginal coin is FREE, because the |apr| ranking is "
                "degenerate at the venue's 10.512% resting pin (ranks 1-10 "
                "and 11+ both mean 10.5000%, delta 0.0000pp; all 16 positions "
                "this book has ever opened carry entry_apr 0.10512 exactly). "
                "Expectancy price measures to ZERO (-0.0024pp/trade). The "
                "gain is +12.5% to +16.7% closes, NOT the +30% first claimed, "
                "and it buys ~10 days to the 30-close bar, not a rescue -- "
                "the grader's `undecidable/130d` is a RAMP ARTIFACT of the "
                "cap itself moving 4->6->10 inside the measured window.",
        "why_open": "DEFERRED on four measured reasons, any one of which "
                    "would be enough: (1) the two tapes DISAGREE IN SIGN -- "
                    "250d settled fundings read -15%, 42d live venue with MTM "
                    "folded reads +1.6% -- and (ne) is explicit that two "
                    "calibrating conventions with opposite verdicts REFUTE a "
                    "finding rather than ship it; (2) the last cap change "
                    "(26-Aug, 4->6->10) has NOT completed one MAX_HOLD_H "
                    "turnover (504h = 21d, so ~16-Sep), and changing again "
                    "first makes neither change separately gradeable (I11/"
                    "I25); (3) the migration transient carries 10 legacy $80 "
                    "legs beside 3 new $60 ones = $980 = 98% of the book for "
                    "up to 504h, above the module's own 80% assert; (4) the "
                    "urgency was the ramp artifact and it is gone. READ ON OR "
                    "AFTER 16-SEP: ship if the two tapes then agree in sign "
                    "on a re-run, keep deferring if they do not. The "
                    "marginal-coin finding stands and needs no re-measuring. "
                    "Closes when the CHANGELOG records the read.",
        "closes_when": lambda: _has("CHANGELOG.md", "hull-cap-13 READ:"),
    },
    {
        "id": "mum-breadth-candidate-preregistered",
        "owner": "session",
        "what": "(zr) 👩 mum's edge lives in the BREADTH of the oversold, on "
                "her own record (9-Sep excluded, I25): closes opened in a "
                "same-loop batch of >=3 coins read +1.114%/trade live (n=37) / "
                "+1.003% twin (n=41) with a 2.7%/2.4% stop rate, positive in "
                "every ISO week and under a coin jackknife; closes opened alone "
                "or in a pair read -0.037% / +0.243% with 9.5-10.5% stops. "
                "Four of the six stops that cost the live book $56 on 9-Sep "
                "were single/pair entries. HONEST SIZE: the live batch closes "
                "are SEVEN open-events (7/7 positive, event-level t +5.7) and a "
                "permutation of event sizes across her 64 events reads P=0.097 "
                "(twin P=0.137) -- hypothesis-grade. SHIPPED: the breadth "
                "pre-pass + `breadth_n` stamp on every close on BOTH hosts, an "
                "INERT caged lever pair (xp.mum.breadth_min / "
                "live.mum.breadth_min, env default 1), and the judge candidate "
                "`mum-breadth-3` queued BEHIND `mum-vel-12-20`. No trade, gate "
                "or size moved on either arm.",
        "why_open": "the read is the JUDGE'S OWN PAIRED BAR (I21 -- graded on "
                    "fresh shadow closes under the candidate against the live "
                    "control, never the window that motivated it): it starts "
                    "when `mum-vel-12-20` resolves (ETA ~16-Sep) and runs "
                    "~4-12 days at the narrowed rate under the (zn) extended "
                    "clock. PROMOTE only on the judge's bar; a refutation is "
                    "recorded in the CHANGELOG as 'mum-breadth-3 READ:' with "
                    "the paired numbers. A session may NOT arm MUM_BREADTH_MIN "
                    "on the live arm itself -- 7 events is not evidence for "
                    "real money, and the shadow twin is mid-experiment.",
        "closes_when": lambda: _has("CHANGELOG.md", "mum-breadth-3 READ:"),
    },
    {
        "id": "mum-live-rho-read-preregistered",
        "owner": "session",
        "what": "(yp) put every book's sizing on ONE axis for the first time -- "
                "risk at the stop per position as a fraction of equity, "
                "rho = clip_fraction x stop -- and the fleet spans 83x on it "
                "(avo-live 3.33%, mum-live 1.67%, the taker 0.30%, turnbull "
                "0.04%). The one real-money reading: 👩 mum's LIVE arm runs "
                "rho 1.67% (clip $240 on $576 equity = 41.7% of the account "
                "behind a 4% stop) against a proposed 0.25% and an admissible "
                "0.5% -- 6.7x the proposal. Corroborated from three independent "
                "directions by her OWN published row: all_slots_stop_pct 0.20 "
                "against the gate's 0.15 bar, vol_target_at_neff1 3.75x against "
                "a configured 5.0x, and stop_reachable FALSE (stop_dead_above "
                "4.17x) on the worst-margin book in her universe. NOT acted on: "
                "the study's reading rests on 10 trading days at its own 10x "
                "extrapolation cap, and her measured n_eff 1.824 puts her "
                "vol_target_here at 5.06x, i.e. exactly at her own framework's "
                "target. So it is REGISTERED, not executed.",
        "why_open": "the read is pre-registered (I21) and its date has not "
                    "arrived: scripts/study_position_sizing_2026-09-07."
                    "PRE_REGISTERED['freqtrade-mum-lighter'] declares the "
                    "at-registration numbers as a COMMITMENT and the study "
                    "prints the fresh-day count and 'DUE NOW' on every run. "
                    "Graded on days AFTER 2026-09-07 ONLY -- never the window "
                    "that motivated it (I25) -- at n_days >= 30 or 2026-10-07, "
                    "whichever first. If the fresh rho_adm is still below her "
                    "running rho, the cut goes to Eamon with both numbers; if "
                    "not, the flag is withdrawn and recorded as withdrawn. "
                    "Cutting a real-money book's clip 6.7x on ten days of a "
                    "hot sample is exactly what I25 forbids.",
        "closes_when": lambda: not _has(
            "scripts/study_position_sizing_2026-09-07.py", "mum-live-rho-read"),
    },
    {
        "id": "avo-judge-lane-declared-but-not-lever-capable",
        "owner": "session",
        "what": "(yg)'s lever surface, on its FIRST loop after the 6-Sep deploy, "
                "published on freqtrade-avo-maria-lshadow: {prefix: 'xp.avo.', "
                "registry: true, registered_n: 0, unregistered: [xp.avo.rsi_max, "
                "xp.avo.max_hold_min, xp.avo.vel_lo, xp.avo.vel_hi]}. Sized: "
                "fleet_bus.JUDGED_PAIRS['avo'] DECLARES xp_prefix 'xp.avo.'; "
                "fleet_tuning.LEVERS registers ZERO xp.avo.* levers; and her "
                "carrier SwingDip defines RSI_MAX but not MAX_HOLD_MIN, so "
                "lighter_family_bot.apply_book_levers returns at its own guard "
                "before asking get_lever for anything. The judge's avo lane -- "
                "judgeable since (ye) matched the caps at 6/6 -- is therefore "
                "structurally INERT: the (ye) class-closers pin that every "
                "REGISTERED xp.* lever is reachable and cannot see a declared "
                "prefix with nothing under it. Same class as (yb)/(ye), one "
                "namespace over; found by the instrument built to find it.",
        "why_open": "[9-Sep (zj)] THE MECHANISM HALF IS DONE -- DO NOT REBUILD "
                    "IT (the (xj) stale-row trap: a row that describes work "
                    "already shipped gets it done twice). Option (b)'s first "
                    "half shipped: `consumable_lever_attrs` is the ONE owner "
                    "both `apply_book_levers` and `lever_surface` read, the "
                    "all-or-nothing RSI_MAX-and-MAX_HOLD_MIN guard is now "
                    "per-attribute, and the surface derives names from the "
                    "CARRIER's consumable set -- so her row reads "
                    "{consumable: ['rsi_max'], registered_n: 0, unregistered: "
                    "['xp.avo.rsi_max']} instead of four names three of which "
                    "SwingDip cannot hold. Her lane is MECHANICALLY CAPABLE and "
                    "zero values moved on any carrier (pinned). WHAT REMAINS IS "
                    "ONLY THE CAGE, and it is REFUSED-WITH-EVIDENCE until "
                    "measured: a cage must fit a measured value and there is "
                    "none -- (qu) asked her entry exit-free over 1,156 signals "
                    "/ 475d / 23 coins and 0 of 21 cells survive BH at FDR "
                    "0.05, while her own arms hold n=18 live / n=34 shadow, so "
                    "no rsi_max dose-response is estimable from either. TO "
                    "CLOSE THIS: re-run her exit-free signal test at several "
                    "rsi_max cells on the CURRENT tape, with a random-entry "
                    "null (I14/hm) and a permutation across cells to price the "
                    "selection ((uz)'s ~1.85 t-unit premium); register "
                    "xp.avo.rsi_max + the live.avo.rsi_max mirror at the "
                    "measured bounds, or record the refusal and withdraw "
                    "xp_prefix from JUDGED_PAIRS['avo'] (option (c)) so the "
                    "judge stops reporting a lane nothing can drive. Either "
                    "way it is a REGISTRY edit, not a host edit, so it no "
                    "longer needs a live marker.",
        "closes_when": lambda: _has("fleet_tuning.py", '"xp.avo.')
                       or not _has("fleet_bus.py", "xp.avo."),
    },
    {
        "id": "mum-halt-cost-preregistered-read",
        "owner": "session",
        "what": "(xv) pre-registered whether 👩 mum's daily-loss halt costs or "
                "saves her, paired same-coin against her never-halting shadow "
                "twin. At registration her ledger holds exactly ONE daily-loss "
                "halt (2-Sep 17:19:45Z, 8 legs, +1.76pp/leg cost against the "
                "twin) -- one flatten instant is ONE observation, not eight, "
                "so it decides nothing. READ at n>=5 halt EVENTS occurring "
                "AFTER 2026-09-03: LOOSEN only if mean paired cost > 1.0pp/leg "
                "AND the sign is consistent across events; otherwise KEEP. "
                "Instrument: scripts/study_mum_halt_cost_2026-09-03.py (its "
                "calibration gate REFUSES unless it reproduces both the "
                "registered event and the registered baseline).",
        "why_open": "the rail is HELD until the criterion is met -- a cost-only "
                    "study of a daily-loss halt reads 'loosen' on every "
                    "ordinary halt day right up until the day it saves the "
                    "book, so the burden sits on loosening. Closes when the "
                    "read is taken and recorded (the PRE_REGISTERED block "
                    "removed from the study).",
        "closes_when": lambda: not _has(
            "scripts/study_mum_halt_cost_2026-09-03.py", "PRE_REGISTERED = {"),
    },
    {
        "id": "kelly-fresh-read-pre-registered",
        "owner": "OPERATOR",
        "what": "EDGE_AUDIT_2026-09-02.md section 6.1 pre-registered a keep-or-"
                "retire read on 🪁 kelly at the (vy) $80 clip: at n>=60 fresh "
                "closes since 1-Sep or on 1-Oct, whichever first -- RETIRE if the "
                "fresh upper bound (m+1.28*SE) <= 0, keep grading if the fresh "
                "mean > 0, anything else returns to Eamon. "
                "[7-Sep (yo)] THE READ HAS BEEN TAKEN -- the SAMPLE tripped it "
                "3.5 weeks before the date backstop (n=233 vs a bar of 60) and "
                "nothing was measuring the trigger. Verdict: RETURNS TO EAMON. "
                "Fresh mean -0.044%/trade, SE 0.132, t -0.33, upper bound "
                "+0.125% -- so the sample has NOT excluded a positive mean "
                "(I17-as-amended forbids retiring) and the mean is not above "
                "zero (so 'keep grading' is not met either). The fresh window "
                "reads 0.098pp better than all-time (-0.142% on n=589), but it "
                "is TAIL-DOMINATED: top-3 closes are +18.68pp of a -10.24pp "
                "total and the ex-top-3 fresh mean is -0.126%/trade, i.e. "
                "materially unchanged. Reproduce with "
                "scripts/study_kelly_fresh_read_2026-09-07.py (calibration "
                "gate REFUSES on a dark feed or a wrong basis).",
        "why_open": "the READ is done; the DECISION is Eamon's and has not been "
                    "made. The registered rule's third branch is explicitly "
                    "'returns to Eamon with both numbers', so a session may not "
                    "close this by choosing one -- retiring needs a measured "
                    "exclusion the sample does not provide, and 'keep grading' "
                    "needs a positive mean it also does not provide. Do NOT "
                    "re-take the read to try for a different answer (I25). "
                    "Closes when the decision is recorded and the `band-kelly` "
                    "entry is removed from golive_readiness.DECIDED_UNTIL.",
        "closes_when": lambda: not _has("scripts/golive_readiness.py",
                                        '"band-kelly": ('),
    },
    # [2026-09-09 (zo)] `georgia-v1-preregistered-read-10sep` DELETED — the
    # read was TAKEN (Eamon: "take georgia's read now", a day early) and the
    # (vb) prediction FAILED on her post-cap closes: n=75 whose own policy
    # stamp reads cap 5, mean -0.0025%/trade vs +0.108% predicted, t -0.02,
    # t bar unreachable where 187d was promised. Retired via
    # lighter_family_bot.RETIRED_BOOKS (GEORGIA_RETIRED_OVERRIDE), both
    # halves, slate test flipped, claim row GRADED in claims_ledger — every
    # act the row named. Cited as I17's UNDECIDABLE call (8,094 closes to
    # t=2), never a measured exclusion (post-cap ub +0.196% > 0). Instrument:
    # scripts/study_georgia_cap5_read_2026-09-09.py.
    {
        "id": "avo-live-slot-6-preregistered-read",
        "owner": "session",
        "what": "🙏 avo's LIVE cap went 5 -> 6 at (ye) (6-Sep) on the twin's "
                "own record: the 4 shadow trades opened with >=5 already held "
                "earned +6.877%/trade (+$13.76, 53% of its +$25.80) vs +1.027% "
                "for the other 28, and the (sr) premise '6 never' had become "
                "false (6 held 8.3% of the time, peak 7). PRE-REGISTERED "
                "READ (I21/I26 — graded on FRESH live closes only, never the "
                "window that motivated it): at >=10 LIVE closes opened with "
                ">=5 held, or on 6-Oct, whichever first — REVERT the literal "
                "to 5 (lighter_family_bot.STRATEGIES, [deploy-live-taker]) if "
                "their mean <= the live book's other closes' mean over the "
                "same window; KEEP if greater; record either verdict as "
                "'avo-live-slot-6 READ:' in the CHANGELOG and remove this row.",
        "why_open": "the read date has not arrived and the live arm has no "
                    "post-change closes yet; this row is the tripwire the "
                    "registration would otherwise lack (the I21 prose shape).",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 10, 6),
    },
    {
        "id": "avo-floor-0.15-preregistered-read",
        "owner": "session",
        "subject": ("freqtrade-avo-maria-lighter",),
        "what": "🙏 avo's crypto volume floor went $0.5M -> $0.15M at (aae) "
                "(10-Sep), RE-DERIVED from (vd)'s own ratio rather than "
                "overridden: $684 clip / $0.5M = 0.1368% of daily volume, and "
                "her clip is $165.95 today (4.1x smaller), which puts the same "
                "ratio at $0.121M. Shipped strictly above it and 1.5x (qq)'s "
                "$0.1M cliff. The proxy was measurably the wrong instrument — "
                "2 of the 3 coins vetoed for SLIPPAGE sit ABOVE the old floor "
                "(SHEIN $0.740M, USELESS $3.856M = 7.7x it). Admits 20 crypto "
                "names, 33 -> 53. PRE-REGISTERED READ (I21/I25 — judged "
                "against her OWN other closes in the SAME window, never the "
                "window that motivated it): at >=30 fresh LIVE closes on "
                "admitted coins (entry volume < $0.5M), or on 10-Oct, "
                "whichever first — REVERT to 0.5 (lighter_family_bot."
                "FAMILY_CRYPTO_MIN_VOL_M, [deploy-live]) if their mean is "
                "worse than her >=$0.5M closes' mean over the same window by "
                "more than one SE of the difference; KEEP if not worse; "
                "anything else returns to Eamon with both numbers. Record as "
                "'avo-floor-0.15 READ:' in the CHANGELOG and remove this row.",
        "why_open": "the read date has not arrived and the live arm has no "
                    "closes on an admitted coin yet. DECLARED BLIND SPOT this "
                    "read exists to watch: the coin-quality slip veto needs "
                    "n>=5 MEASURED FILLS, so a newly admitted coin is "
                    "unprotected on its first fills and the floor is its only "
                    "screen — which is why the floor was lowered "
                    "proportionately rather than removed.",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 10, 10),
    },
    {
        "id": "counterweight-preregistered-fresh-read",
        "owner": "session",
        "what": "⚖️ Counterweight was KEPT 1-Sep under I17-as-amended with a "
                "PRE-REGISTERED read (I21, recorded in CLAUDE.md's "
                "acknowledged-recurrence line for perps-funding-spread): "
                "grade the FRESH on-class closes (class_split, closes AFTER "
                "1-Sep only — never the window that motivated the keep) at "
                "n>=60 or on 10-Oct, whichever first. [10-Sep (zt)] BASIS "
                "DECLARED: CLOSED-after 1-Sep, not opened-after -- it was "
                "ambiguous and two sessions read it differently on the "
                "same day (n=13 vs n=21, 2.2pp of mean, 16 days of "
                "trigger date). Pinned in code by "
                "scripts/study_counterweight_fresh_read_2026-09-10.py, "
                "which reports BOTH bases and REFUSES to take the read "
                "before the trigger fires. RETIRE without further "
                "debate if the fresh on-class upper bound (m+1.28*SE) <= 0; "
                "keep grading if the fresh mean > 0; anything else returns "
                "to Eamon with both numbers.",
        "why_open": "the read date has not arrived. This row is the tripwire "
                    "the registration lacked: its predicate fires on 1-Oct, "
                    "so CI reds until a session actually PERFORMS the read "
                    "and closes this row with the verdict in the CHANGELOG. "
                    "[9-Sep (zp)] CHECKED ON EAMON'S ASK, AND THE TRIGGER "
                    "HAS NOT FIRED — fresh on-class n=13 against the bar of "
                    "60, 47 short, measured on a feed refreshed the same "
                    "hour (era rows 158, newest close 9-Sep 00:40Z). "
                    "CORRECTED IN PLACE per I12, because the sentence below "
                    "used to end 'the date is the backstop, not the trigger' "
                    "and for THIS book that is measurably backwards: at "
                    "the observed 1.52 on-class closes/day since 1-Sep, "
                    "n=60 arrives ~10-Oct — NINE DAYS AFTER the 1-Oct date. "
                    "So the DATE binds first and the read will be taken at "
                    "n~44, ~27% below the registration's own floor. That "
                    "is recorded now, BEFORE the read, so the schedule is "
                    "decided on arithmetic rather than on the result; NO "
                    "THRESHOLD IS MOVED (I21 — the registered bars are a "
                    "commitment). Expect the 'returns to Eamon' branch and "
                    "read the power, not just the sign. REPORTED, not the "
                    "read: fresh on-class mean +0.538%/trade, SE 1.519, "
                    "t=+0.35, net +$1.23 — a POSITIVE mean, which is "
                    "exactly why taking it early would have manufactured a "
                    "'keep grading' verdict from a sample that decides "
                    "nothing (this book closes ~10 legs at once, so its "
                    "per-trade dispersion is enormous). [10-Sep (zs)] EAMON "
                    "MOVED THE BACKSTOP 1-Oct -> 10-Oct on that arithmetic, so "
                    "the read lands near the registration's own n floor rather "
                    "than ~27% under it. NO THRESHOLD MOVED. Declared per I21: "
                    "the amendment was NOT blind (the interim +0.538%/t=+0.35 "
                    "was visible) and is admissible on arithmetic — a larger "
                    "sample shrinks SE, and RETIRE fires on m+1.28*SE <= 0, so "
                    "more closes make RETIREMENT more reachable when the mean "
                    "is negative; it tightens both bounds, it does not favour "
                    "keeping. DECLARED SHORTFALL: at the measured 1.43 "
                    "closes/day 10-Oct projects to n~56, not 60 — the date is "
                    "a BACKSTOP and the n>=60 branch still fires early if it "
                    "is met; ~13-Oct is the date that would make the floor "
                    "near-certain, and that is Eamon's to move again.",
        # Deliberately date-only: the predicate firing means the read is DUE,
        # and the honest way to close the row is to run the read and record
        # the verdict — deleting it without the verdict is the thing the
        # preamble says somebody has to justify.
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 10, 10),
    },
    {
        "id": "regime-short-veto-preregistered-read",
        "owner": "session",
        "what": "The edge audit's hypothesis #3 is a PRE-REGISTERED instrument "
                "now (I21): `scripts/study_regime_short_veto_2026-09-02.py` "
                "labels every close by the oracle's verdict for its coin at the "
                "OPEN and grades the vetoed set (short in LONG-window / long in "
                "SHORT-window) at t_crit(n). Registered 2-Sep 09:30Z. READ: run "
                "it with `--fresh` when the largest living vetoed set reaches "
                "n>=30 fresh closes (🪁 kelly's shorts run ~11/day; ⚖️ "
                "counterweight's ~1/day) or on 16-Sep, whichever first. "
                "CONFIRMED -> build the veto shadow-first on THAT book, graded "
                "against its un-gated twin, own entry; REFUTED -> record it "
                "beside the audit's hypothesis table; else record the numbers "
                "and re-arm one more read (P3: at most twice). "
                "[9-Sep (zp)] RE-ARMED ONCE, CONDITIONALLY: a second read "
                "is only informative if the post-registration window "
                "contains regime VARIANCE, so it fires when the oracle "
                "shows BTC leaving LONG-window, or on the 16-Sep backstop. "
                "If the window still has no variance at that read, CLOSE "
                "the registration as untestable rather than re-arm again. "
                "TWO METHOD REQUIREMENTS attach to that read. (1) NO "
                "SESSION MAY QUOTE A PROBABILITY for the turn: the "
                "oracle's 59d history holds SEVEN runs and exactly ONE "
                "LONG-window run — the current, open, 19.50d one, already "
                "longer than the longest COMPLETED run of any kind; zero "
                "completed LONG runs means there is no distribution. "
                "(2) DAY-PAIR the cell before counting it: on a "
                "single-regime tape the label IS the calendar epoch, so "
                "after a flip every short/veto row is dated before it and "
                "every short/pass row after — the identified cell arrives "
                "confounded with time BY CONSTRUCTION (I25). Wait, then "
                "day-pair; never wait, then re-run. AND THE ORDERING "
                "CONSTRAINT: \U0001fa81 kelly's own keep-or-retire read "
                "(7-Sep) RETURNS TO EAMON and is undecided; a short veto "
                "on her removes 73 of 257 fresh closes (28%) on exactly "
                "the side that verdict turns on, so adopting one first "
                "re-specifies the book mid-registration and voids the "
                "7-Sep read (the (tt) failure I21 was amended for). "
                "Eamon's decision FIRST, any veto second. If a next read "
                "is pointed anywhere it is \u2696\ufe0f Counterweight — the only "
                "LIVING book whose identified cells agree on both sides, "
                "and it already carries a 1-Oct read to hang this on.",
        "why_open": "[9-Sep (zp)] THE READ HAS BEEN TAKEN — three days early, "
                    "because the SAMPLE tripped it (🪁 kelly's vetoed set "
                    "reached n=73 against a bar of 30). Verdict: NOT IDENTIFIED, "
                    "which is neither of the branches the registration "
                    "anticipated. On the post-registration window BTC read "
                    "LONG-window in 351 of 351 snapshots, so every crypto short "
                    "is vetoed BY CONSTRUCTION: 🪁 kelly's label-vs-side "
                    "Cramer's V is 0.981 (73 of 73 vetoed closes are shorts) and "
                    "🚀 bezos's is 1.000 (31 shorts vetoed, 6 longs passed, "
                    "zero crossover) — and bezos is the book the rule said "
                    "CONFIRMED. Fleet-wide there are ZERO within-side cells at "
                    "n>=10, so no identified comparison exists on this window at "
                    "all. On the POOLED window, where one does exist (11 cells), "
                    "the effect has the WRONG SIGN at +0.221pp against a "
                    "rotated-label null P=0.858 (living books only: +0.294pp, "
                    "P=0.983). Shipped with the read: an identifiability "
                    "precondition + a corroboration gate in the instrument "
                    "itself, both strictly conservative (6/6 mutations red), so "
                    "the next read cannot crown a side cut. Full working: "
                    "STUDY_REGIME_VETO_IDENTIFIABILITY_2026-09-09.md.",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 9, 16),
    },
    {
        "id": "taker-hold-floor-preregistered-read",
        "owner": "session",
        "what": "The edge audit's hypothesis #2 is a PRE-REGISTERED instrument "
                "now (I21): `scripts/study_taker_hold_floor_2026-09-02.py` walks "
                "🎫 the taker's OWN entries through `exit_reason` with a hold "
                "floor (no tp/sl/trail before F h) against the shipped rule, "
                "paired, calibrated against the realised closes, on the scout "
                "tape. Registered 2-Sep 09:30Z. READ: run it with `--fresh` at "
                "n>=30 fresh walked closes (~4.7 closes/day -> ~10 days) or on "
                "16-Sep, whichever first. CONFIRMED -> register `TT_MIN_HOLD_H` "
                "as a caged shadow-lane lever at the confirmed floor, its own "
                "entry, era untouched (an exit bar is not in the (jf) signature); "
                "REFUTED -> record it; else record and re-arm once.",
        "why_open": "the fresh sample has not accrued; the read at registration "
                    "is in the (wy) changelog entry. Declared limit: the "
                    "replay form of this test (a floor's effect on the ENTRIES "
                    "it blocks by holding a slot) needs the up-resolver, which "
                    "this environment's egress refuses — run that half in the "
                    "container when the walk confirms.",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 9, 16),
    },
    {
        "id": "mum-noncrypto-sleeve-preregistered-read",
        "owner": "session",
        "what": "👩 mum's NON-CRYPTO sleeve read 7 closes at −0.383%/trade live "
                "(−0.540% twin), 5 of 7 `max_hold` losers on both arms — and the "
                "SAME DAY an adversarial review REFUTED the mechanism that "
                "motivated it and the bar that would have acted on it. The "
                "closed-hours story is dead (0 of 10 max_hold losses expired "
                "before the underlying reopened; entry-while-OPEN is WORSE). The "
                "7 closes are 4 ENTRY DAYS (3 share one `opened_at`), the upper "
                "bound is <=0 only on the iid read (+0.170% day-clustered), and "
                "the raw −0.98pp class gap FLIPS to +0.18pp under a close-day "
                "effect. PRE-REGISTERED (I21), corrected rule: run "
                "`scripts/study_mum_noncrypto_sleeve_2026-09-02.py` at G>=10 "
                "distinct ENTRY DAYS on the live arm or on 16-Sep, whichever "
                "first. CUT (set FAMILY_NONCRYPTO_EXCLUDE='freqtrade-mum:*' — the "
                "whole class, so the act matches the graded population — on "
                "mum-live AND family-lighter-shadow so the control twin moves "
                "with her) ONLY if the DAY-CLUSTERED upper bound <= 0 AND the "
                "sleeve is worse than CRYPTO on matched close-days. KEEP if the "
                "sleeve mean > 0. The twin is REPORTED, not a condition. Anything "
                "else re-arm once — and note the supported mechanism is a "
                "vol/bracket mismatch whose remedy is a class-aware ladder "
                "(I26 feed-it), measured on its own, NOT this cut.",
        "why_open": "G is 4; the floor is 10 entry days. The mechanism "
                    "(`noncrypto_exclude`, per carrier, ENTRY-ONLY, inert at '') "
                    "shipped with the registration so the cut is one env, not a "
                    "build, if the corrected read ever passes.",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 9, 16),
    },
    # [2026-08-25 (tc)] `farmer-live-swap-operator-steps` DELETED — spent, and
    # its closes_when could never fire: it watched for a `georgia-live` service
    # while the (tb) plan change converted `trail-blazer-live` IN PLACE (so no
    # credential was ever read), and the swap EXECUTED 22-Aug with the flatten
    # receipt read (`open == 0`), the row hidden + pruned, and the registries
    # synced ((tb) + the (tc) sweep that caught the three it missed:
    # deploy_live_verify's service->row map, respiration's LIVE_BREATHS,
    # market_context's LIVE_CADENCE_SEC). The row's own text also named two
    # registries that never existed (`fleet_books.LIVE_DEPLOY`,
    # `PROP_LIVE_ROWS`) — corrected in MUM_GOLIVE_RUNBOOK.md's activation list.
    # [2026-09-02] `funding-studies-inherit-the-rank-universe` DELETED —
    # CLOSED by its own predicate: study_farmer_take_profit now applies the
    # live $10M/day floor by DEFAULT via the loader-owned minvol_entry_ok
    # (moved into backtest_funding_lighter, one owner; the gate study
    # imports it by identity). breadth + persistence stay header-recorded
    # refusals: (vj) measured their floored populations at n=0 / all-zero
    # arms, so wiring the floor there yields an instrument that measures
    # nothing; xsect never used the rank loader.
    {
        "id": "allocation-clamp-is-a-per-position-bound-doing-per-book-duty",
        "owner": "OPERATOR",
        "what": "💰 fleet_allocation's [0.25, 4.0] clamp is a per-POSITION "
                "slippage bound being asked to do a per-BOOK job. **[(vj)] THE "
                "4.0 ALARM THIS ROW USED TO CARRY IS WITHDRAWN — it was "
                "measured stale.** It read '💰 sits AT its 4.0 ceiling on 🌾 "
                "carry right now, delta_usd +13,500, $14,400 of gross on a "
                "$1,000 book'. Measured on the live payload 27-Aug: the MAXIMUM "
                "scale anywhere in the fleet is **1.594** (🙏 avo shadow) and "
                "carry sits at **1.272** ($1,271.75 target on a $1,000 book). "
                "(tz) replaced the winner-take-all split with a tilted flat "
                "prior, which made 4.0 structurally unreachable — so the row "
                "described the organ as it behaved BEFORE the fix that had "
                "already shipped. What survives is LATENT, not live: the "
                "ceiling still PERMITS a scale that breaches the 15% go-live "
                "drawdown bar, because maxDD is the one bar that is NOT "
                "clip-invariant ((hl) measured per-trade % invariance for the "
                "other five) — ⚖️ Counterweight breaches at 3.06x, inside the "
                "4.0 ceiling.",
        "why_open": "the clamp is a capital-allocation policy and moving it "
                    "moves money between books — an operator call (I16), not a "
                    "session one. It is NOT urgent: nothing is near the "
                    "ceiling today. **[(xj)] THE SESSION-DOABLE HALF THIS ROW "
                    "NAMED IS DONE, AND THE ROW WAS FIVE DAYS STALE — it read "
                    "\'what a session CAN do first is derive the per-book "
                    "bound the drawdown bar implies and publish it beside the "
                    "claim\', which shipped at (vd) on 28-Aug as "
                    "`fleet_allocation.dd_bound` and is LIVE on all 16 books. "
                    "The stale row nearly caused it to be rebuilt.** What is "
                    "actually left, measured on the live payload 2-Sep: 6 books "
                    "bounded (incl. all three live arms — mum 3.75x, avo 1.5x), "
                    "1 declared NO_STOP_BY_DESIGN, and **9 living books with no "
                    "bound at all**, so the shared ceiling governs them blind. "
                    "(xj) built the drift guard `_STOP_BRIDGE` promised and "
                    "never got (all 10 retyped stops verified correct, 6/6 "
                    "mutations red both directions) and DECLARED the 9 as a "
                    "shrink-only ratchet. Draining that backlog needs a per-book "
                    "reading — a bleed stop is a genuine loss bound but whether "
                    "it is the right input to 0.15/|stop| is a claim nobody has "
                    "studied. The OPERATOR half is untouched: moving the clamp "
                    "moves money between books (I16).",
        # closes when the clamp is re-decided (either bound moves) or carry's
        # slot count and clip stop multiplying out past its own equity.
        "closes_when": lambda: not _has("fleet_bus.py",
                                        "ALLOC_SCALE_CEIL = 4.0"),
    },
    {
        "id": "brain-mult-transition-oscillation",
        "owner": "session",
        "what": "The brain's `t` is computed on DOLLARS "
                "(`brain_stats.weighted_bucket` reads `profit_abs`), so a "
                "bucket MID-TRANSITION is a mixture of two clip scales: sd "
                "inflates against mean and `t` falls on a book whose edge has "
                "not moved. Predicted shape: a bucket that clears a rung steps "
                "back down a rung within ~10 closes, then climbs again. A "
                "uniform scale is invariant, so there is no runaway — this is "
                "a transient limit cycle, damped by the 14d decay and the "
                "3-run streak gate.",
        "why_open": "the fix is hysteresis in the PUBLISHER (`qualify_v3` is "
                    "stateless; the held rung lives in bot_learn's "
                    "`mult_streaks`), and rewriting the brain's ladder on the "
                    "same day 13 consumers were wired to it is the untested-"
                    "rewrite-of-an-authority the doctrine forbids. It is now "
                    "MEASURABLE for the first time — every close carries its "
                    "`brain_mult` — so the next pass tests the prediction "
                    "against real closes instead of a model.",
        "closes_when": lambda: _has("brain_stats.py", "HYSTERESIS"),
    },
    # [2026-09-02] `taker-replay-blind-to-breakoutup` DELETED — BOTH halves
    # done. The blindness half was fixed 20-Aug (daily_up_resolver + the
    # relabel, forwarded by the tuner and incubator, selftest-pinned) and
    # this row never fired because its predicate watched a string that
    # legitimately survives as the no-resolver fallback. The cage half was
    # re-decided 2-Sep on LIVE evidence (tuner baseline breakoutup
    # taken=26 closed=23): brk_range/max_hold_h two-way again, coupled to
    # sight by test_breakoutup_ratchet.test_the_unpin_is_coupled_to_the_
    # gates_sight; brk_trail/brk_sl stay pinned (walked by nothing,
    # widenings measured-and-withheld).
    # [CLOSED 2026-09-02] breakout-arm-inherits-reversion-clock — the clock is
    # SPLIT: `BRK_MAX_HOLD_H` (env TT_BRK_MAX_HOLD_H, default inherits
    # TT_MAX_HOLD_H then 48) now times the trend exit, `taker.max_hold_h`
    # steers only the divergence bracket, and the taker's selftest pins the
    # decoupling by AST. No widening shipped (the 48->96 evidence died to
    # leave-one-symbol-out); behaviour-neutral at ship.
    # [2026-09-09 (zo)] `ceiling-slots-georgia` DELETED — its SUBJECT retired
    # under it (the (vj) rule: a row pointed at a corpse is re-pointed or
    # closed with a reason). The entry-rank question it carried is answered
    # by the read that retired her: the cap 3 -> 5 admitted 4 of 75 post-cap
    # trades (ranks 4-5) and her mean is ~zero at every rank, so the "next
    # notch" this row waited for had nothing to move. Its closes_when watched
    # for a cap of "4" that will now never ship.
    # [2026-09-02, (ww) readback] `family-shadow-stale-writer` CLOSED on the feed
    # readback, the only thing that could close it: at 06:33Z the family rows
    # stamp 97dbe3986551/15 (the (wv) build), 👩 mum-lshadow publishes the
    # 12-position book the running container restores (the zombie held 2),
    # and 🔮 georgia-v3-lshadow has a row for the first time. Two defects,
    # one symptom: a stale instance that could not be seen (this row) and a
    # live instance that could not speak ((wv): spend_extra raising inside
    # the publish's except: pass). The 16-file (ww) image lands on the next
    # family deploy; the stamp is the receipt, never the deploy log.
    {
        "id": "ceiling-capital-inversion",
        "owner": "OPERATOR",
        "what": "Capital sits in INVERSE proportion to measured edge: the two "
                "worst books run at 88-102% of capacity (⚖️ Counterweight "
                "-1.433%, 🛢️ Garrett -1.460%) while 👩 mum at +4.658%/trade is "
                "capped at FOUR slots and 🙏 avo at +1.085% uses 40% of six. "
                "`fleet_allocation` computes the right answer and is ADVISORY "
                "with consumers on three funding books only.",
        "why_open": "moving capital between books is an operator call, not a "
                    "session one — the organ already ranks it honestly (I16).",
        "closes_when": lambda: False,
    },
    {
        "id": "books-should-declare-themselves",
        "owner": "session",
        "what": "18 of 19 living books do not publish `extra.thesis` — their "
                "design lives in `fleet_manifest`'s bridge table instead of on "
                "the row. `design_for` already prefers a book's own "
                "publication, so each migration is one publish-site edit and "
                "the manifest entry goes quiet on its own.",
        "why_open": "18 bot edits and 18 deploys; do it a book at a time on "
                    "the next deploy each one earns for another reason.",
        "closes_when": lambda: _thesis_coverage_complete(),
    },
    {
        "id": "unmeasurable-lever-backlog",
        "owner": "session",
        "what": "30 registered levers still have no QUANTITIES spec — no "
                "recorded quantity to profile them against. The ratchet in "
                "audit_lever_measurability stops the pile GROWING; draining it "
                "is per-lever work: record what the knob cuts, then spec it.",
        "why_open": "each one needs the bot to stamp its own governing "
                    "quantity first (the (sk) give_back/mae_ret pattern).",
        "closes_when": lambda: _ratchet_at_or_below("unmeasurable", 0),
    },
    # [2026-09-02] `taker-divergence-stop-unpriced` DELETED — THE MEASUREMENT
    # WAS RUN (scripts/study_taker_divergence_stop_2026-09-02.py, 503.7h of
    # recorded tape through the taker's own replay) and the verdict is a
    # REFUSAL WITH EVIDENCE: (1) the study's own calibration gate refuses —
    # the book's last REAL divergence close is 20-Aug and the lens is vetoed
    # by its own realised record, so the instrument cannot be calibrated
    # against a live sample it can no longer produce; (2) descriptively, the
    # only cage-reachable move (taker.sl -0.03 -> -0.04) measured NEGATIVE
    # (-$2.80 full-tape) — the apparent gains live beyond the cage (-0.05:
    # +$16.45, -0.06: +$29.96) on div n of 9-20 with unstable halves, i.e.
    # slot-reallocation noise as much as exit value. Pricing a stop for a
    # lens the book refuses to trade is not a candidate; if the veto ever
    # lifts on fresh evidence, re-run the study THEN, on the closes that
    # lifted it.
    {
        "id": "georgia-t-bar",
        "owner": "session",
        "what": "🔮 georgia is 5 of 6 go-live bars, failing only t. "
                "[MEASURED 26-Aug (tm) pass]: the weak t is ONE real 3-leg "
                "flash-crash batch (22-Aug 05:11Z: XRP -16.4/NEAR -19.5/TRX "
                "-3.0) = 73.5% of cluster variance — drop those 3 rows and "
                "t_cluster reads +2.51. Tail CONTROL cannot clear the bar "
                "honestly (at the live arm's own measured -7.17% crash fill "
                "for a -5% stop, t_cluster caps at ~1.40), and the "
                "stress-metric entry pause is REFUTED on the fleet's own "
                "instrument (scout stress read 8.6bps at the 05:00:33 entry "
                "vs the taker's 15bps bar; the 11.8 peak came 13 MINUTES "
                "after the dump started). Exits are a dead dial (see "
                "ceiling-slots-georgia). What remains is ENTRY QUALITY: the "
                "crash entry rode a +7.5%-in-50-min parabolic spike, and "
                "rank1 entries earn +0.023% vs rank2's +0.656%.",
        "why_open": "[26-Aug (tp)]: the parabolic-extension veto was RUN and "
                    "REFUTED-AS-OVERFIT, adversarially confirmed — the best "
                    "cell's whole effect is the three crash rows; ex-crash it "
                    "forgoes $+10.17 of winners and refuses 73% of "
                    "trend_breakout's supply (I7); random-veto null P~0.10, "
                    "forced-kept P=0.0002 / conditional P=0.37. BOTH her "
                    "dials are now measured dead (exits at (tm), the entry "
                    "filter at (tp)). What remains: (1) the rank1-vs-rank2 "
                    "gap (+0.55pp, NOT explained by extension — corr −0.050) "
                    "gets its own pre-registered study on fresh closes once "
                    "rank-3 stamps accrue; (2) her live arm accrues under "
                    "the (tm)-fixed policy — time, not tuning.",
        "closes_when": lambda: False,
    },
    # [2026-09-02 (ww)] `carry-garrett-ranking-collision` DELETED — 🛢️ Garrett
    # retired at (wv) (unreachable, n=85, t=-2.22, ub -0.455%); the component
    # is the carry/Rich Dad pair, already declared in KNOWN_CELL_COLLISIONS
    # with its own ~12-Sep decision point.
]


def _thesis_coverage_complete():
    """True once every living row publishes its OWN design and the bridge
    table is empty — the state this carried item is waiting for."""
    try:
        import fleet_manifest
        return not fleet_manifest.DESIGN
    except Exception:                                            # noqa: BLE001
        return False


def _ratchet_at_or_below(key, n):
    try:
        import audit_lever_measurability as alm
        ok, _lines, counts = alm.check()
        return counts.get({"unmeasurable": "UNMEASURABLE",
                           "dead": "DEAD"}[key], 99) <= n
    except Exception:                                            # noqa: BLE001
        return False


# ---------------------------------------------------------------------------

def shipped_today(now=None, since=None):
    """Commits since local midnight, with the changelog letters they carry.

    `since` is injectable so a test can prove this READS GIT rather than
    returning a plausible empty list — a function that always answers "nothing
    shipped" is indistinguishable from a quiet day, and that is precisely the
    silence the operator asked to be rid of.
    """
    now = now or _dt.datetime.now(SYD)
    if since is None:
        since = (now.replace(hour=0, minute=0, second=0, microsecond=0)
                 .astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S"))
    elif not isinstance(since, str):
        since = since.astimezone(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")
    out = _sh("git", "log", "--since", since, "--format=%h\t%s")
    rows = [ln.split("\t", 1) for ln in out.splitlines() if "\t" in ln]
    letters = sorted({m.group(1) for _h, s in rows
                      for m in [re.search(r"\(([a-z]{1,2})\)\s*$", s)] if m})
    return rows, letters


#: The public read-only feeds. Overridable so a test drives a fixture and so a
#: session behind a proxy can point at a mirror. No auth, no DATABASE_URL — this
#: has to work from a laptop and from CI.
FEED_URL = os.environ.get(
    "SESSION_STATE_FEED",
    "https://pnl-dashboard-production-858c.up.railway.app/pnl.json")
BUS_URL = os.environ.get(
    "SESSION_STATE_BUS",
    "https://pnl-dashboard-production-858c.up.railway.app/bus.json")


def _fetch(url, timeout=6.0):
    """-> parsed JSON, or None on ANY trouble. Never raises and never hangs:
    a session must be able to start when the feed is down, and a 30-second
    stall at `--write` is how a tool stops being run."""
    try:
        import urllib.request
        with urllib.request.urlopen(url, timeout=timeout) as r:
            return json.loads(r.read().decode("utf-8"))
    except Exception:                                        # noqa: BLE001
        return None


#: Sentinel for "go and fetch it". `None` is a REAL value here — it is what a
#: failed fetch returns — so it cannot double as the default, or a caller (and
#: the selftest) has no way to say "this feed is dark" without unplugging the
#: network. Found by the selftest on the first run.
_FETCH = object()


def fleet_signals(pnl=_FETCH, bus=_FETCH):
    """WHAT THE BOOKS ARE REPORTING THAT NOBODY THOUGHT TO ASK.

    **Eamon, 2026-09-10: "set up the bots to send you important information so
    you have all of it in case I forget to ask and miss things, that way you can
    bring them up whenever I start a session."**

    This file's own module docstring has claimed since (sl) that *"STUCK is read
    from the live fleet"* and it never read a feed at all — the section was
    advertised and never built, which is the (ac) doc-rot shape in the one file
    every session starts from. Three things bit a single session on 10-Sep and
    every one of them was sitting in a payload the whole time:

      * 🎫 the taker and 🙏 avo's twin had BOTH reached `ready` 6/6 — the
        fleet's first-ever gate passes, its own declared forward metric
        ("BOOKS THAT CAN BE GRADED, THEN GO LIVE"), and nothing surfaced it;
      * 👩 mum's LIVE arm was locked out by `slguard` at that moment;
      * 🙏 avo's 98h of `maxdd` lockout was PRE-FIX residue, and a session
        nearly acted on it as a current condition.

    THREE RULES THIS FOLLOWS, because a briefing that misleads is worse than
    none:
      * **I1 — liveness before semantics.** Staleness is reported FIRST and
        from the feed's OWN verdict (`meta.feed_stale` / `meta.n_stale`), never
        re-derived here: the dashboard owns which per-row threshold applies to a
        stock, a sniper and everything else, and a second copy of that rule is a
        second rule.
      * **A dark feed is never byte-identical to a clean one** ((kw), I4). An
        unreachable feed reports DARK loudly; it does not silently render an
        empty, reassuring section.
      * **The gate is IMPORTED, not recomputed** — `golive_readiness` is the
        fleet's one grading authority and this reads its published verdict.

    -> {"dark": [str], "gate": [str], "live": [str], "stale": [str]}
    """
    pnl = _fetch(FEED_URL) if pnl is _FETCH else pnl
    bus = _fetch(BUS_URL) if bus is _FETCH else bus
    out = {"dark": [], "gate": [], "live": [], "stale": []}

    if not isinstance(pnl, dict):
        out["dark"].append(
            f"`/pnl.json` UNREACHABLE ({FEED_URL}) — no book state read. "
            "This section is blind, not clear.")
    if not isinstance(bus, dict):
        out["dark"].append(
            f"`/bus.json` UNREACHABLE ({BUS_URL}) — no gate verdicts read. "
            "This section is blind, not clear.")

    # ---- I1: liveness first, on the feed's own verdict ------------------
    rows = (pnl or {}).get("bots") or []
    meta = (pnl or {}).get("meta") or {}
    if isinstance(pnl, dict):
        if meta.get("feed_stale"):
            out["stale"].append("**the FEED ITSELF is stale** — every reading "
                                "below is suspect until it refreshes.")
        n_stale = meta.get("n_stale")
        if isinstance(n_stale, int) and n_stale > 0:
            aged = sorted(
                ((r.get("bot"), r.get("age_sec")) for r in rows
                 if isinstance(r, dict) and isinstance(r.get("age_sec"),
                                                       (int, float))),
                key=lambda kv: -kv[1])[:n_stale]
            out["stale"].append(
                f"the feed reports **{n_stale} stale row(s)**; oldest: "
                + ", ".join(f"`{b}` {a/3600.0:.1f}h" for b, a in aged))

    # ---- the payoff event: a book at the gate ---------------------------
    g = (bus or {}).get("golive_readiness") or {}
    books = (g.get("books") if isinstance(g, dict) else None) or {}
    for bot, v in sorted(books.items()):
        if not isinstance(v, dict):
            continue
        bars = v.get("bars") or v.get("bar_map") or {}
        if not isinstance(bars, dict) or not bars:
            continue
        passed = sum(1 for x in bars.values() if x is True)
        if v.get("ready") is True:
            # [(aan)] READY DESCRIBES THE GRADED ARM, AND ON A BOOK WHOSE LIVE
            # MODE RUNS A NARROWER POLICY THAT IS NOT THE ARM BEING PROMOTED.
            # This line said "READY — 6/6 bars" for six days about 🎫 the
            # taker, whose live allow-list could fill NONE of the 208 closes
            # that earned it. The handoff is the first thing a session reads
            # (I11), so the qualification belongs HERE, not only on the card.
            lf = v.get("live_fillable") if isinstance(
                v.get("live_fillable"), dict) else None
            note = ""
            if lf and lf.get("inert") is True:
                note = (" **BUT ITS LIVE ARM WOULD FILL NOTHING** — "
                        + str(lf.get("why") or "").strip())
            elif lf and (lf.get("unfillable") or {}).get("n"):
                _ef, _uf = (lf.get("effective") or {}), (lf.get("unfillable") or {})
                note = (f" Its LIVE arm could have filled {_ef.get('n')} of "
                        f"{(_ef.get('n') or 0) + (_uf.get('n') or 0)} of those "
                        f"closes — read `live_fillable` before promoting.")
            # [(aau)] and the screen the six bars cannot apply — they test
            # against ZERO, and (hm) requires a directional book to be graded
            # against a random-entry benchmark. HANDOFF is where a session
            # decides what to pick up, so the caveat has to be HERE and not
            # only in a CLI footer nobody reads.
            nb = v.get("null_band") if isinstance(
                v.get("null_band"), dict) else None
            if nb and nb.get("inside_random_band") is True:
                note += (f" Its mean ({nb.get('mean_pct')}%/trade) sits INSIDE "
                         f"the {nb.get('band_pct')}%/trade band a RANDOM entry "
                         f"pays on this venue — the six bars test against ZERO "
                         f"and cannot tell it from drift ((hm)).")
            out["gate"].append(
                f"`{bot}` is **READY — {passed}/{len(bars)} bars**. Going live "
                "is Eamon's explicit act; it is never an automatic consequence "
                "of passing." + note)
        elif passed == len(bars) - 1:
            missing = sorted(k for k, x in bars.items() if x is not True)
            out["gate"].append(
                f"`{bot}` is one bar short ({passed}/{len(bars)}) — "
                f"failing: {', '.join(missing)}.")

    # ---- real money, right now -----------------------------------------
    try:
        import fleet_books as _fb
        live = _fb.live_rows_from_feed(pnl) or list(_fb.DECLARED_LIVE)
    except Exception:                                        # noqa: BLE001
        live = []
    by_id = {r.get("bot"): r for r in rows if isinstance(r, dict)}
    for bot in live:
        r = by_id.get(bot)
        if not isinstance(r, dict):
            out["live"].append(f"`{bot}` is DECLARED LIVE and **absent from "
                               "the feed** — check the service is publishing.")
            continue
        ev = (r.get("extra") or {}).get("entry_vetoes") or {}
        if ev.get("shut_now"):
            until = ev.get("locked_until")
            when = ""
            if isinstance(until, str):
                try:
                    t = _dt.datetime.fromisoformat(until.replace("Z", "+00:00"))
                    when = f" until {t.astimezone(SYD).strftime('%H:%M')} Sydney"
                except ValueError:
                    when = f" until {until}"
            out["live"].append(
                f"`{bot}` is **SHUT right now** — `{ev.get('shut_now')}`"
                f"{when} ({ev.get('shut_reason') or 'no reason published'}).")
        lo = ev.get("lockout_hours_30d") or {}
        tot, span = lo.get("total"), lo.get("span_h")
        if isinstance(tot, (int, float)) and isinstance(span, (int, float)) \
                and span > 0 and tot / span >= 0.10:
            worst = max(((k, v) for k, v in lo.items()
                         if k not in ("total", "span_h", "loops")
                         and isinstance(v, (int, float))),
                        key=lambda kv: kv[1], default=(None, 0))
            out["live"].append(
                f"`{bot}` was shut **{tot/span:.0%} of the last "
                f"{span/24.0:.1f}d** ({tot:.0f}h), mostly `{worst[0]}` "
                f"({worst[1]:.0f}h). NOTE: a rolling window keeps reporting a "
                "rail that has since been FIXED — date the events before "
                "acting on this.")
    return out


def _dead_rows():
    """Row ids the fleet has retired, from the two registries that declare it.

    Fail-OPEN (empty set on any import trouble): a dark registry must not start
    reporting live rows as dead. The cost of failing open is a missed stale
    row; the cost of failing closed is a session sent to re-point a book that
    is trading fine."""
    try:
        import cleanup_legacy_bots as _legacy
        import fleet_bus as _fb
        return set(getattr(_fb, "RETIRED_LIVE_ARMS", {}) or {}) | \
            set(getattr(_legacy, "LEGACY_BOTS", ()) or ())
    except Exception:                                        # noqa: BLE001
        return set()


def subject_status():
    """-> [(id, row, why)] for every CARRIED row whose SUBJECT has been retired.

    [(vj)] A HANDOFF ROW OUTLIVED THE BOOK IT WAS ABOUT. `carried_status`
    answers "is the work done?" and nothing answered "does the thing still
    exist?" — so `farmer-cap-collapses-slots-under-conviction` kept demanding
    attention for 💸 the LIVE Farmer five days after (ta) retired it, with a
    predicate that could never fire. I11 makes this file the thing a session
    STARTS from, so a row pointed at a corpse spends the scarcest resource
    there is: the first hour of the next pass.

    Deliberately NOT folded into `closes_when`. A dead subject does not mean
    the work is DONE — it means the row must be re-pointed at a living book or
    retired with a reason, and those are different acts with different owners.
    """
    dead = _dead_rows()
    if not dead:
        return []
    return [(it["id"], row,
             "subject retired — re-point this row at a living book or close it")
            for it in CARRIED for row in it.get("subject", ()) if row in dead]


def carried_status():
    """-> [(item, done)]. A predicate that RAISES counts as not-done, and says
    so: a broken predicate must not silently close an item."""
    out = []
    for it in CARRIED:
        try:
            done = bool(it["closes_when"]())
        except Exception as e:                                   # noqa: BLE001
            done = False
            it = dict(it, why_open=f"[predicate error: {type(e).__name__}] "
                                   + it["why_open"])
        out.append((it, done))
    return out


def render(now=None, signals=None):
    now = now or _dt.datetime.now(SYD)
    rows, letters = shipped_today(now)
    status = carried_status()
    if signals is None:
        signals = fleet_signals()
    L = []
    L.append("# HANDOFF — start here\n")
    L.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M')} Sydney "
             f"({now.astimezone(_dt.timezone.utc).strftime('%H:%M')}Z) by "
             "`scripts/session_state.py`. Do not hand-edit: regenerate it._\n")

    # Liveness and real money come before the work queue: I1 reads `age_sec`
    # before it reads content, and a live book that is SHUT right now outranks
    # any carried item. Quiet is stated explicitly — an empty section here must
    # never be mistakable for an unread one ((kw)).
    L.append("## Fleet signals — read before anything else\n")
    order = (("dark", "🕳️ FEED DARK"), ("stale", "⏳ STALENESS (I1)"),
             ("live", "💵 REAL MONEY, RIGHT NOW"), ("gate", "🚦 AT THE GATE"))
    if not any(signals.get(k) for k, _ in order):
        L.append("_Feed read, nothing flagged: no stale rows, no live book "
                 "shut, no book at or one bar from the gate._\n")
    for key, title in order:
        items = signals.get(key) or []
        if not items:
            continue
        L.append(f"**{title}**\n")
        for s in items:
            L.append(f"- {s}")
        L.append("")

    L.append("## Carried — pick these up FIRST (I11)\n")
    open_items = [(i, d) for i, d in status if not d]
    done_items = [(i, d) for i, d in status if d]
    if done_items:
        L.append("**CLOSE THESE — their own predicate says they are done:**\n")
        for it, _ in done_items:
            L.append(f"- ~~`{it['id']}`~~ — DONE, delete the row.")
        L.append("")
    if not open_items:
        L.append("_Nothing carried._\n")
    for it, _ in open_items:
        L.append(f"### `{it['id']}`  ·  owner: **{it['owner']}**")
        L.append(f"{it['what']}\n")
        L.append(f"_Still open because:_ {it['why_open']}\n")
    L.append(f"## Shipped today ({len(rows)} commit(s)"
             + (f", entries {', '.join('(' + x + ')' for x in letters)}"
                if letters else "") + ")\n")
    if not rows:
        L.append("_Nothing yet today._\n")
    for h, s in rows:
        L.append(f"- `{h}` {s}")
    L.append("")
    L.append("## How this file stays honest\n")
    L.append("Every carried row above carries a `closes_when` predicate that "
             "`--check` evaluates against the repo. A finished item cannot "
             "linger (it is reported CLOSE THIS and reddens CI) and an "
             "unfinished one cannot be dropped without deleting a row somebody "
             "has to justify. The shipped list is read from git, not typed.\n")
    return "\n".join(L)


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true")
    ap.add_argument("--check", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    if a.check:
        # [2026-09-10] `--check` is the CI arm and renders NOTHING: since
        # `render` learned to read the live feeds, rendering here would make
        # every push depend on the dashboard being up. A guard has two regimes
        # and the CI one has no network.
        stale = [i["id"] for i, d in carried_status() if d]
        if stale:
            print("audit_session_state: FAIL — carried item(s) whose own "
                  f"predicate says they are DONE: {', '.join(stale)}. "
                  "Delete the row (and say so in the changelog).")
            return 1
        # [(vj)] ...and a SECOND way a row goes stale: its subject retires
        # under it. Reported separately from `stale` because the remedy
        # differs — a done row is DELETED, a dead-subject row is RE-POINTED at
        # a living book or closed with a reason.
        orphan = subject_status()
        if orphan:
            print("audit_session_state: FAIL — carried item(s) pointed at a "
                  "RETIRED row:")
            for _id, _row, _why in orphan:
                print(f"  {_id}: {_row} — {_why}")
            return 1
        print(f"audit_session_state: OK — {len(CARRIED)} carried item(s), "
              "none stale, none orphaned.")
        return 0
    text = render()
    if a.write:
        with open(HANDOFF, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {HANDOFF}")
    else:
        print(text)
    return 0


def selftest():
    # every row is well-formed and its predicate is callable and total
    ids = [i["id"] for i in CARRIED]
    assert len(ids) == len(set(ids)), f"duplicate carried id: {ids}"
    for it in CARRIED:
        # `subject` is OPTIONAL on purpose: several rows are about the fleet's
        # machinery rather than a book, and forcing a row id on those would
        # invite a made-up one. Where it IS given it must be a tuple of row
        # ids, so `subject_status` can never be handed a bare string and
        # iterate its characters.
        assert set(it) <= {"id", "owner", "what", "why_open", "subject",
                           "closes_when"}, it
        assert {"id", "owner", "what", "why_open", "closes_when"} <= set(it), it
        assert isinstance(it.get("subject", ()), tuple), it["id"]
        assert it["owner"] in ("session", "OPERATOR"), it
        assert it["what"].strip() and it["why_open"].strip(), it
        assert isinstance(it["closes_when"](), bool), it["id"]

    # a RAISING predicate must not close an item — it degrades to open and
    # labels itself, because a broken check that silently finishes work is the
    # worst outcome this file can produce
    boom = {"id": "x", "owner": "session", "what": "w", "why_open": "y",
            "closes_when": lambda: (_ for _ in ()).throw(RuntimeError("nope"))}
    CARRIED.append(boom)
    try:
        st = dict((i["id"], (i, d)) for i, d in carried_status())
        assert st["x"][1] is False
        assert "predicate error: RuntimeError" in st["x"][0]["why_open"]
    finally:
        CARRIED.remove(boom)

    # a predicate that reads TRUE is surfaced as CLOSE THIS and fails --check
    done = {"id": "already-done", "owner": "session", "what": "w",
            "why_open": "y", "closes_when": lambda: True}
    CARRIED.append(done)
    try:
        assert main(["--check"]) == 1
        assert "CLOSE THESE" in render() and "already-done" in render()
    finally:
        CARRIED.remove(done)
    assert main(["--check"]) == 0, "the real list has a stale row"

    # the live predicates actually discriminate — a check that can only ever
    # return False is decoration (the (po) inspects-nothing rule)
    assert _has("lighter_ticket_replay.py", "_up = False if lens") is True
    assert _has("lighter_ticket_replay.py", "a string that is not there") is False
    assert _has("no_such_file.py", "x") is False

    # the render names the owner, so an OPERATOR item cannot look like session
    # work a future pass will just pick up. `signals={}` keeps the selftest
    # OFF the network — the fetch is exercised separately, below, against
    # fixtures shaped like the real publishers.
    txt = render(signals={})
    assert "owner: **OPERATOR**" in txt and "owner: **session**" in txt, txt[:400]
    assert "Shipped today" in txt and "Carried" in txt

    # ---- fleet_signals ---------------------------------------------------
    # A DARK FEED IS NOT A CLEAN ONE. This is the whole point of the section:
    # the failure it must never have is rendering silence that reads as "all
    # well" ((kw), I4).
    dark = fleet_signals(pnl=None, bus=None)
    assert dark["dark"], "an unreachable feed must SAY so"
    _d = " ".join(dark["dark"])
    # BOTH feeds are named. Asserting only that the list is non-empty let a
    # mutation delete the /pnl.json branch and stay GREEN on the /bus.json one
    # — i.e. one feed could go dark in silence. Caught by mutation M1.
    assert "/pnl.json" in _d and "/bus.json" in _d, _d
    assert _d.count("blind, not clear") == 2, _d
    # and each feed is independently reported, not just the pair
    only_bus = fleet_signals(pnl={"bots": [], "meta": {}}, bus=None)
    assert len(only_bus["dark"]) == 1 and "/bus.json" in only_bus["dark"][0]
    only_pnl = fleet_signals(pnl=None, bus={})
    assert len(only_pnl["dark"]) == 1 and "/pnl.json" in only_pnl["dark"][0]
    dtxt = render(signals=dark)
    assert "FEED DARK" in dtxt and "nothing flagged" not in dtxt

    # ...and quiet is stated explicitly, so an EMPTY section is never
    # mistakable for an UNREAD one.
    qtxt = render(signals={"dark": [], "stale": [], "live": [], "gate": []})
    assert "nothing flagged" in qtxt

    # a READY book is surfaced — this is the fleet's declared forward metric
    # and on 10-Sep two books reached it with nothing to announce it
    bus_fx = {"golive_readiness": {"books": {
        "book-ready": {"ready": True,
                       "bars": {"window": True, "closes": True, "mean": True,
                                "t": True, "halves": True, "maxdd": True}},
        "book-one-short": {"ready": False,
                           "bars": {"window": True, "closes": True,
                                    "mean": True, "t": False, "halves": True,
                                    "maxdd": True}},
        "book-far": {"ready": False,
                     "bars": {"window": True, "closes": False, "mean": False,
                              "t": False, "halves": True, "maxdd": True}}}}}
    sig = fleet_signals(pnl={"bots": [], "meta": {}}, bus=bus_fx)
    joined = " ".join(sig["gate"])
    assert "book-ready" in joined and "READY" in joined, joined
    assert "book-one-short" in joined and "t" in joined, joined
    # a book three bars out is NOT noise-listed — a section that flags
    # everything trains the reader to ignore it ((gl))
    assert "book-far" not in joined, joined
    # going live stays an explicit operator act, and the briefing says so
    assert "explicit act" in joined

    # a live book SHUT right now is surfaced, with the time in Sydney
    pnl_fx = {"meta": {"feed_stale": False, "n_stale": 0}, "bots": [
        {"bot": "freqtrade-mum-lighter", "age_sec": 10, "extra": {
            "entry_vetoes": {"shut_now": "slguard",
                             "shut_reason": "protections_locked",
                             "locked_until": "2026-09-10T09:56:59+00:00",
                             "lockout_hours_30d": {"total": 48.3,
                                                   "span_h": 330.5,
                                                   "slguard": 28.1,
                                                   "cooldown": 13.3}}}}]}
    sig = fleet_signals(pnl=pnl_fx, bus={})
    live = " ".join(sig["live"])
    assert "SHUT right now" in live and "slguard" in live, live
    assert "19:56 Sydney" in live, live          # 09:56Z -> AEST, never bare UTC
    assert "15%" in live and "slguard" in live, live
    # the rolling-window trap that cost this session an hour is stated inline
    assert "has since been FIXED" in live, live

    # a DECLARED-live row missing from the feed is itself a signal: that is a
    # real-money book whose service has stopped publishing, and silence about
    # it is the worst possible reading
    gone = " ".join(fleet_signals(pnl=pnl_fx, bus={})["live"])
    assert "freqtrade-avo-maria-lighter" in gone and "absent" in gone, gone

    # a quiet live book produces NO live signal — the section must not cry wolf
    def _q(bot):
        return {"bot": bot, "age_sec": 10, "extra": {"entry_vetoes": {
            "shut_now": None,
            "lockout_hours_30d": {"total": 1.0, "span_h": 330.5}}}}
    quiet = {"meta": {"feed_stale": False, "n_stale": 0},
             "bots": [_q("freqtrade-mum-lighter"),
                      _q("freqtrade-avo-maria-lighter")]}
    assert fleet_signals(pnl=quiet, bus={})["live"] == []

    # I1: staleness rides the FEED's OWN verdict, never a threshold retyped here
    stale_fx = {"meta": {"feed_stale": True, "n_stale": 1}, "bots": [
        {"bot": "sleepy-book", "age_sec": 99999, "extra": {}},
        {"bot": "awake-book", "age_sec": 5, "extra": {}}]}
    st = " ".join(fleet_signals(pnl=stale_fx, bus={})["stale"])
    assert "FEED ITSELF is stale" in st and "sleepy-book" in st, st
    assert "awake-book" not in st, st

    print("session_state selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
