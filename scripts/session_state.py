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
  * **STUCK** is read from the live fleet — books with no closes, levers pinned
    at a cage end, organs past their own TTL.
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
        "id": "survivorship-measured-but-not-consumed",
        "owner": "session",
        "what": "(yt) measured the largest distortion in the fleet's own "
                "reporting: every grading instrument scores the LIVING set, so "
                "a loser leaves the sample the day it is retired. On the "
                "Lighter era -- living 16 books +$296.09, retired 18 books "
                "-$260.47, TRUE FLEET TOTAL +$35.63. The living-book figure "
                "overstates the realised result by 8.3x. Each retirement was "
                "individually correct (I17 measured exclusions); the aggregate "
                "had simply never been computed. `baseline_snapshot."
                "survivorship()` now recomputes it every run.",
        "why_open": "the number EXISTS and nothing CONSUMES it -- the same "
                    "shape as (yo), where the fleet kept building the "
                    "measurement and not the tripwire that reads it. No "
                    "dashboard card, no organ, no guard reads it, so a reader "
                    "of /pnl.json still sees only the survivors' sum. Closes "
                    "when some published surface carries the true-total figure "
                    "beside the living one.",
        "closes_when": lambda: (_has("pnl_dashboard.py", "survivorship")
                                or _has("fleet_radar.py", "survivorship")
                                or _has("scripts/organ_board.py", "survivorship")),
    },
    {
        "id": "fleet-risk-effective-n-overstates-independence",
        "owner": "OPERATOR",
        "what": "(yv) measured, like-for-like on the SAME held set: "
                "`fleet_risk.long_effective_n` (1/HHI over DISTINCT SYMBOLS, "
                "fleet_risk.py:366) reads 11.8 while a correlation-aware N_eff "
                "on the same 29 held names reads 2.8 -- the incumbent "
                "overstates independence by 4.2x. The organ's own docstring "
                "already warns that '23 open longs that are all crypto beta is "
                "~one trade, and nothing said so'; the warning is right and the "
                "formula cannot express it. `scripts/fleet_beta.py` publishes "
                "the alternative BESIDE the incumbent and modifies nothing.",
        "why_open": "changing `long_effective_n` changes a field live consumers "
                    "read, which is a risk-policy decision rather than a "
                    "session one -- and the audit's own safety constraints "
                    "forbid touching filters that affect existing bots. Closes "
                    "when the operator decides either to move the formula or to "
                    "record why it stays.",
        "closes_when": lambda: _has("fleet_risk.py", "corr_effective_n"),
    },
    {
        "id": "oi-history-is-not-reachable",
        "owner": "session",
        "what": "(yv) THE CANDLE FIELD `i` IS NOT OPEN INTEREST. Measured on 44 "
                "coins x 1,500 bars: it rose or held in 65,956 of 65,956 "
                "bar-to-bar steps and never fell, at magnitudes (~2.4e10 on "
                "AAVE) far above any plausible level -- a cumulative counter. "
                "The real point-in-time OI is `orderBookDetails.open_interest` "
                "(BTC 2031 base ~ $162M) and its HISTORY lives only in "
                "`market_context`'s own `oi_ntl` state, which is DB-side and "
                "absent from /bus.json. So the price/OI hypothesis cannot be "
                "tested from outside the containers. "
                "`scripts/study_open_interest_2026-09-07.py` exists, carries a "
                "planted-signal positive control that passes, and REFUSES on "
                "the data rather than reporting a vacuous no-signal.",
        "why_open": "the blocker is EXPOSING `oi_ntl` history (a publish-site "
                    "change in market_context, or a /bus.json key), not writing "
                    "the study. Closes when that history is reachable and the "
                    "study runs to a real verdict.",
        # The predicate must test EXPOSURE, not the existence of an internal
        # variable. The first cut read `_has("market_context.py", '"oi_hist"')`
        # and fired immediately, because `oi_hist` is a local in that module's
        # own loop — the guard caught it on the first --check, which is the
        # guard working. /bus.json's key block in pnl_dashboard is where a
        # reachable series would have to appear.
        "closes_when": lambda: _has("pnl_dashboard.py", 'live.get("market-context")'),
    },
    {
        "id": "books-do-not-record-their-own-fill-cost",
        "owner": "session",
        "what": "(yu) only 4 of 14 living books record the venue's quoted "
                "spread on their own fills (kelly, douglas, bezos, Hull). Every "
                "other book's execution cost has to be INFERRED from the venue "
                "rather than read from its record -- the inversion of I14, "
                "where a record exists. The four that do record are what made "
                "`scripts/cost_model.py`'s calibration gate possible at all "
                "(deltas 0.06-3.73bps against an 8.0 tolerance).",
        "why_open": "it is one publish-site edit per book plus the deploy each "
                    "one earns for another reason -- cheap individually, ten "
                    "times over collectively, and none of them urgent. Closes "
                    "when a majority of living books stamp a per-fill spread.",
        "closes_when": lambda: _has("lighter_family_bot.py", "spread_bps_entry"),
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
        "why_open": "the fix is a DECISION with a measurement, not a one-liner: "
                    "(a) give SwingDip a hold bound so the guard passes and "
                    "register xp.avo.rsi_max + max_hold_min with cages (a "
                    "behaviour change on a real-money carrier -> (qu)'s "
                    "measurement first), or (b) narrow apply_book_levers to "
                    "per-attribute and register only xp.avo.rsi_max (cage TBD "
                    "against her rsi<42 cell), or (c) withdraw xp_prefix from "
                    "JUDGED_PAIRS['avo'] so the judge stops reporting a lane "
                    "that cannot apply. Whichever ships, the surface's own "
                    "over-report (it derives names from MUM_LEVER_ATTRS, not "
                    "from the carrier's consumable set) is fixed in the SAME "
                    "push -- and that push touches lighter_family_bot.py, so "
                    "it MUST carry [deploy-live] (both markers): a shadow-only "
                    "redeploy re-splits both live pairs (measured 6-Sep 15:31Z, "
                    "the judge read ARMS ON DIFFERENT CODE). Deferred rather "
                    "than restarting two real-money books for a report-shape "
                    "fix at the tail of the deploy that found it.",
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
    {
        "id": "georgia-v1-preregistered-read-10sep",
        "owner": "session",
        "what": "🔮 georgia v1 was on the (wt) September slate and DEFERRED "
                "on Eamon's confirmed date ('On 10 sep'): her cap-5 "
                "trajectory carries the pre-registered claim "
                "georgia-entry-cap-5-days-to-gate (grade_after 10-Sep, "
                "days-to-gate ~187 predicted at a higher mean). ON 10-SEP: "
                "grade the claim on her post-cap closes ONLY. Prediction "
                "fails -> retire via lighter_family_bot.RETIRED_BOOKS key "
                "'freqtrade-georgia' (override GEORGIA_RETIRED_OVERRIDE) + "
                "both halves + slate-test update; holds -> record the keep "
                "with the fresh number. Either way, close this row with the "
                "verdict.",
        "why_open": "retiring her before the registration's own read voids "
                    "it (I21/I25); the docket's ~4,233d pools ~200 pre-cap "
                    "closes against ~25 post-cap ones.",
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 9, 10),
    },
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
        "id": "counterweight-preregistered-fresh-read",
        "owner": "session",
        "what": "⚖️ Counterweight was KEPT 1-Sep under I17-as-amended with a "
                "PRE-REGISTERED read (I21, recorded in CLAUDE.md's "
                "acknowledged-recurrence line for perps-funding-spread): "
                "grade the FRESH on-class closes (class_split, closes AFTER "
                "1-Sep only — never the window that motivated the keep) at "
                "n>=60 or on 1-Oct, whichever first. RETIRE without further "
                "debate if the fresh on-class upper bound (m+1.28*SE) <= 0; "
                "keep grading if the fresh mean > 0; anything else returns "
                "to Eamon with both numbers.",
        "why_open": "the read date has not arrived. This row is the tripwire "
                    "the registration lacked: its predicate fires on 1-Oct, "
                    "so CI reds until a session actually PERFORMS the read "
                    "and closes this row with the verdict in the CHANGELOG. "
                    "If fresh on-class n reaches 60 EARLIER, do the read "
                    "then — the date is the backstop, not the trigger.",
        # Deliberately date-only: the predicate firing means the read is DUE,
        # and the honest way to close the row is to run the read and record
        # the verdict — deleting it without the verdict is the thing the
        # preamble says somebody has to justify.
        "closes_when": lambda: _dt.date.today() >= _dt.date(2026, 10, 1),
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
                "and re-arm one more read (P3: at most twice).",
        "why_open": "the fresh sample has not accrued. At registration the "
                    "instrument read NOT DECIDABLE on every book: the oracle's "
                    "reachable history is 200h, BTC read LONG-window in 418 of "
                    "418 snapshots, and the largest vetoed sets were 🪁 kelly "
                    "n=122 (-0.273%/t, ub +0.25% — undecided), 💸 farmer-shadow "
                    "n=26 (ub +0.009%, one close short — retired, frozen) and "
                    "🧘 douglas n=18 (ub +0.029% — retired, frozen). The date "
                    "is the backstop, not the trigger.",
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
    {
        "id": "ceiling-slots-georgia",
        "owner": "session",
        "what": "**(sv) ANSWERED THE CENSUS QUESTION AND THE ANSWER RETIRES THE "
                "HEADLINE.** This row read '83.5 DAYS at 0.5 of 5 slots, 7.6 "
                "days at full occupancy — an 11x speed-up'. Measured: her mean "
                "hold is **2.6h**, so occupancy = closes/day x 2.6/24 and FIVE "
                "slots need ~46 opens/day. Her signal supplies 40.9/day at "
                "best. **Full occupancy is unreachable by construction, and it "
                "was never the lever — CLOSES are.** She is flat 68.4% of the "
                "time not because something refuses her but because she exits "
                "in under 3 hours. (sv) took the one gate that cut closes for "
                "no quality reason (the 2/h throttle, +0.633pp in favour of the "
                "entry it refused, six splits) from 2 -> 3.",
        "why_open": "the step is DELIBERATELY one notch: rank 3 has n=1 in her "
                    "whole life because the cap was 2, so everything above it "
                    "is extrapolation. `entry_rank` now rides every close, so "
                    "the next step is graded from a query — re-run "
                    "`scripts/study_georgia_entry_rank_2026-08-22.py` once "
                    "rank-3 rows exist and take 3 -> 4 only if it holds. "
                    "[26-Aug (tm) pass]: rank-3 today reads n=3, 0% win, "
                    "crash-dominated — decides NOTHING either way; 3 of the "
                    "six (sv) controls have flipped negative, so the 3->4 "
                    "step is REFUSED on current data and 3->2 reversion "
                    "equally unsupported. The OTHER half is now MEASURED AND "
                    "CLOSED: the calibrated LAG-1 hold/roi sweep (n=100 "
                    "paired, both intrabar conventions) put every widening "
                    "below the harness's own +0.246pp calibration error, "
                    "roi-x2's gain is h2-NEGATIVE, trail-only sign-disagrees "
                    "between conventions, and the 1440m max_hold fired 0 of "
                    "207 closes ever — exits are a dead dial on this book; "
                    "the mean lever is ENTRY quality (rank1 +0.023% vs rank2 "
                    "+0.656% on her own ledger).",
        # closes when the next throttle decision has been taken on rank-3 data
        "closes_when": lambda: _has(
            "lighter_family_bot.py", 'GEORGIA_MAX_ENTRIES_PER_HOUR", "4"'),
    },
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


def render(now=None):
    now = now or _dt.datetime.now(SYD)
    rows, letters = shipped_today(now)
    status = carried_status()
    L = []
    L.append("# HANDOFF — start here\n")
    L.append(f"_Generated {now.strftime('%Y-%m-%d %H:%M')} Sydney "
             f"({now.astimezone(_dt.timezone.utc).strftime('%H:%M')}Z) by "
             "`scripts/session_state.py`. Do not hand-edit: regenerate it._\n")
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
    text = render()
    if a.write:
        with open(HANDOFF, "w") as fh:
            fh.write(text + "\n")
        print(f"wrote {HANDOFF}")
    if a.check:
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
    if not a.write:
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
    # work a future pass will just pick up
    txt = render()
    assert "owner: **OPERATOR**" in txt and "owner: **session**" in txt, txt[:400]
    assert "Shipped today" in txt and "Carried" in txt
    print("session_state selftest OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
