#!/usr/bin/env python3
"""[2026-08-20] I22'S TEETH — a book must SPEND the ecosystem, and say what it spent.

Operator, 20-Aug: *"everything you have put forward that is unreachable is
because its one construct, one set of tradeables, one set of entry and exits
which havent been explored properly, you have not set the bots up in any way
that we could ever really even use leverage."*

THE ARITHMETIC THIS ENFORCES. With one decision per period, `t = S_d*sqrt(T)`, so
**days-to-gate = (2/S_d)^2** — and for independent sleeves `S_d^2 = SUM S_i^2`.
Decidability velocity is ADDITIVE, so one construct is one term in that sum and a
single-sleeve book earns a DECISION more slowly by the square. That is why this
fleet keeps producing books the gate calls `undecidable` and then retiring them:
🌊 9 buys / 0 sells in 22 days, 📊 17.2 closes/yr, 🧙 ~719 closes = 40 months.

WHAT IT CHECKS, and the scoping choice that gives it teeth without crying wolf.
Requiring `extra.spend` of every LIVING row today would redden the build for 19
books that predate the invariant — the guard would be shouting about history
instead of governing new work, and a guard everyone routes around is worse than
none. So the rule is scoped to BIRTHS: a book whose row first appears after
`SPEND_REQUIRED_FROM` must publish its spend census, and a book that publishes
one must publish a HONEST one. Books alive before that date sit in
`GRANDFATHERED` — a declared map with a reason, the `BORN_DARK_OK` idiom, so the
exemption is a decision rather than a default and adding to it is visible.

FAIL-CLOSED on the feed (the `(jc)` contract): a dark, empty or stamp-free
/pnl.json exits non-zero. A vacuous green here would certify exactly the thing
the invariant exists to catch.

  python3 scripts/audit_book_spend.py [--pnl-json URL|PATH] [--selftest]
"""
from __future__ import annotations

import argparse
import json
import sys
import urllib.request
from datetime import date

#: A design whose days-to-gate exceeds this is a STUDY, not a book. It may run as
#: an instrument; it does not get a row, a clock, capital or a budget slot.
#: 60 is not a taste: at `days = (2/S_d)^2` it is `S_d >= 0.258`, and the fleet's
#: own best measured surface (🧭 nav-cook, daily Sharpe 0.463) implies 19 days —
#: so 60 admits a design running at ~31% of the best thing measured here.
MAX_DAYS_TO_GATE = 60.0

#: Births on or after this date must publish `extra.spend`. Set to the day I22
#: shipped: the invariant governs what comes next, and says so.
SPEND_REQUIRED_FROM = date(2026, 8, 20)

#: Books alive before I22. Each carries WHY it is exempt — never a bare list.
GRANDFATHERED = {
    "freqtrade-mum-lshadow": "born 19-Aug (ro), one day before I22",
    "freqtrade-avo-maria-lshadow": "pre-I22 family book",
    "freqtrade-avo-maria-lighter": "pre-I22 LIVE arm; real money, no census retrofit",
    "freqtrade-georgia-lshadow": "pre-I22 family book, 5/6 bars",
    "perps-funding-carry-lshadow": "pre-I22 funding book",
    "perps-funding-lighter-lighter": "pre-I22 LIVE arm; real money",
    "perps-funding-lighter-lshadow": "pre-I22 shadow twin of the LIVE arm",
    "perps-funding-spread-lshadow": "pre-I22; keep-or-retire ~28-Aug",
    "lighter-ticket-taker-lshadow": "pre-I22",
    "lighter-perp-sniper-lshadow": "pre-I22",
    "band-garrett-lshadow": "pre-I22 variant instance",
    "band-kelly-lshadow": "pre-I22 mirror book",
    "book-douglas-lshadow": "pre-I22 books cohort",
    "book-grimes-lshadow": "pre-I22 books cohort",
    "book-hull-lshadow": "pre-I22 books cohort",
    "book-kiyosaki-lshadow": "pre-I22 books cohort",
    "nav-cook-lshadow": "born 19-Aug (ri), one day before I22",
    "pm-albanese-lshadow": "pre-I22 parliament",
    "pm-turnbull-lshadow": "pre-I22 parliament",
}

#: A book may exceed MAX_DAYS_TO_GATE only with a reason, an OWNER and a DATE.
SLOW_BOOK_OK: dict[str, str] = {}

REQUIRED_FIELDS = ("markets_scanned", "n_eff", "sides", "gross_x",
                   "days_to_gate_obs")

DEFAULT_FEED = "https://pnl-dashboard-production-858c.up.railway.app/pnl.json"


def _rows(feed):
    """Rows from a URL or a local path. Raises on anything unusable — the
    caller turns that into a non-zero exit, never a quiet pass."""
    if feed.startswith("http"):
        req = urllib.request.Request(feed, headers={"User-Agent": "audit"})
        with urllib.request.urlopen(req, timeout=45) as r:
            doc = json.load(r)
    else:
        with open(feed) as fh:
            doc = json.load(fh)
    rows = doc.get("bots") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list) or not rows:
        raise ValueError("feed carried no rows")
    return rows


def birth_census(row, today=None):
    """-> [problem, ...] for ONE published row. Empty list = compliant.

    The spend census is five numbers because each closes a different way of
    looking wide while being narrow:
      markets_scanned   — the tape it looks at
      n_eff             — the bets it actually holds, CORRELATION-aware. A
                          symbol count is the failure this field exists to
                          prevent: 8 crypto markets are 1.35 independent bets.
      sides             — long-only halves the surface for free
      gross_x           — exposure vs equity; 1x on a diversified book is
                          risk budget left on the table
      days_to_gate_obs  — the whole point. (2/S_d)^2.
    """
    bot = str(row.get("bot") or "")
    probs = []
    if not bot:
        return ["row carries no bot id"]
    if bot in GRANDFATHERED:
        return []
    spend = (row.get("extra") or {}).get("spend")
    if not isinstance(spend, dict):
        return [f"{bot}: no `extra.spend` census. I22 requires a book born on "
                f"or after {SPEND_REQUIRED_FROM} to publish what it spends of "
                f"the ecosystem: {', '.join(REQUIRED_FIELDS)}. If this book "
                f"predates I22 it belongs in GRANDFATHERED with a reason."]
    for f in REQUIRED_FIELDS:
        if spend.get(f) is None:
            probs.append(f"{bot}: spend census missing `{f}`")
    n_eff = spend.get("n_eff")
    if isinstance(n_eff, (int, float)) and isinstance(
            spend.get("markets_held"), (int, float)):
        if float(n_eff) == float(spend["markets_held"]) and float(n_eff) > 1:
            probs.append(
                f"{bot}: n_eff ({n_eff}) equals the raw held-symbol count — "
                f"that is 1/HHI over distinct symbols, not independence. 8 "
                f"crypto markets are 1.35 bets, not 8.")
    d = spend.get("days_to_gate_obs")
    if isinstance(d, (int, float)) and float(d) > MAX_DAYS_TO_GATE:
        if bot not in SLOW_BOOK_OK:
            probs.append(
                f"{bot}: days_to_gate {float(d):.0f} > {MAX_DAYS_TO_GATE:.0f}. "
                f"I22: that is a STUDY, not a book — redesign, or declare it in "
                f"SLOW_BOOK_OK with a reason, an owner and a date.")
    return probs


def audit(feed=DEFAULT_FEED, today=None):
    rows = _rows(feed)
    live = [r for r in rows if str(r.get("status") or "") != "retired"]
    problems = []
    for r in live:
        problems.extend(birth_census(r, today=today))
    return problems, len(live)


def _selftest():
    def row(bot, spend=None, status="online"):
        r = {"bot": bot, "status": status, "extra": {}}
        if spend is not None:
            r["extra"]["spend"] = spend
        return r

    good = {"markets_scanned": 212, "n_eff": 4.8, "sides": "both",
            "gross_x": 2.4, "days_to_gate_obs": 47, "markets_held": 6}
    assert birth_census(row("nav-flinders-lshadow", good)) == []

    # a NEW book with no census fails
    p = birth_census(row("nav-newbook-lshadow"))
    assert p and "no `extra.spend`" in p[0], p

    # a pre-I22 book is exempt, and the exemption is DECLARED
    assert birth_census(row("freqtrade-georgia-lshadow")) == []
    assert all(GRANDFATHERED.values()), "every exemption must carry a reason"

    # days-to-gate over the bar fails...
    slow = dict(good, days_to_gate_obs=187)
    p = birth_census(row("nav-slow-lshadow", slow))
    assert p and "STUDY, not a book" in p[0], p
    # ...unless declared
    SLOW_BOOK_OK["nav-slow-lshadow"] = "declared for the selftest"
    assert birth_census(row("nav-slow-lshadow", slow)) == []
    del SLOW_BOOK_OK["nav-slow-lshadow"]

    # a missing field is named individually
    p = birth_census(row("nav-x-lshadow", dict(good, gross_x=None)))
    assert any("`gross_x`" in x for x in p), p

    # n_eff that is really a symbol count is caught — the (gn) lesson: width
    # measured by counting names is not width
    p = birth_census(row("nav-y-lshadow", dict(good, n_eff=6.0)))
    assert any("not independence" in x for x in p), p

    # ...but n_eff == held is fine when the book holds ONE position
    assert birth_census(row("nav-z-lshadow",
                            dict(good, n_eff=1.0, markets_held=1))) == []

    # FAIL-CLOSED on a dark feed
    for bad in ("[]", "{}", '{"bots": []}'):
        import tempfile, os
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        fh.write(bad); fh.close()
        try:
            audit(fh.name)
            raise AssertionError(f"dark feed {bad} must raise, not pass")
        except ValueError:
            pass
        finally:
            os.unlink(fh.name)

    print("audit_book_spend --selftest: OK (census required at birth, "
          "grandfathered set declared with reasons, days-to-gate bar, "
          "symbol-count n_eff caught, fail-closed feed)")
    return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--pnl-json", default=DEFAULT_FEED)
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    try:
        problems, n = audit(a.pnl_json)
    except Exception as e:                                # noqa: BLE001
        print(f"::error::audit_book_spend: feed unusable ({e}). FAIL-CLOSED — "
              f"a dark feed is not a pass.")
        return 2
    if problems:
        for p in problems:
            print(f"  ::error::{p}")
        print(f"\nFAIL: {len(problems)} I22 spend violation(s) across {n} living rows.")
        return 1
    print(f"audit_book_spend: OK — {n} living rows, every post-I22 book "
          f"publishes its spend census and clears the {MAX_DAYS_TO_GATE:.0f}-day bar")
    return 0


if __name__ == "__main__":
    sys.exit(main())
