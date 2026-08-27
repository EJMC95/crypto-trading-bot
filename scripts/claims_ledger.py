#!/usr/bin/env python3
"""THE LEDGER OF CLAIMS — every number doctrine leans on names the organ that
can recompute it, and gets recomputed.

**Eamon, 2026-08-27, asked for this one by name.** The reason is an asymmetry
that is measurable rather than felt. Counted the day this shipped:

  * THE FAULT SIDE — 25 invariants (24 with executable enforcement), 29
    `scripts/audit_*.py`, 152 files under `tests/autonomy/`, plus
    `session_state.CARRIED` whose every row carries a `closes_when` predicate
    evaluated against the repo. Nothing rots there without something going red.
  * THE WIN SIDE — ONE script, `scripts/winners_docket.py`, whose own line 38
    says *"Read-only: writes nothing, publishes nothing"*, appearing in NO
    workflow and NO `run_all.sh` loop. It has never been scheduled, and its
    `PRE_REGISTERED` table is two hand-typed rows from 18-Aug. That is exactly
    the `(gk)` shape — a rule nobody runs is not a control — on the one
    instrument the fleet has for saying a thing is WORKING.

**AND THE FAULT SIDE LEAKS TOO, in the one direction nobody guards.** CLAUDE.md
records the justification for putting REAL MONEY on 🔮 georgia — *"5 of 6 bars,
both halves positive, failing only `t` (1.48 < 2.0)"*. Measured 27-Aug against
the organ that owns that number: **t = 0.62, verdict `undecidable`, ~776 days.**
The figure that moved a live sub-account is 2.4x stale and had stood five days.
Twenty-nine audits, and not one asks whether a number quoted in doctrine still
matches the organ that owns it.

WHAT THIS IS. A declared list of CLAIMS, in code, reviewable in a diff — the
`session_state.CARRIED` shape, and for the same reason: hand-written where it
has to be, MECHANICALLY GRADED where it can be. Every row names
`owner = (organ_key, dotted.path)`, and `scripts/audit_claim_freshness.py`
walks that path in the organ's own published payload and compares.

THE ONE RULE THAT MAKES IT A LEDGER RATHER THAN A DOCUMENT: **a row that does
not name an owner who can recompute it CANNOT BE ADDED.** `validate()` refuses
it at declaration time — before any network, in `--selftest`, offline — so an
unfalsifiable number cannot enter the ledger at all. That is what stops this
becoming the thing it exists to catch.

FOUR VERDICTS, and the distinctions are load-bearing:

  HOLDS       the live number is inside the row's declared tolerance.
  STALE       it is outside. The doctrine is wrong NOW and says so.
  PENDING     a registered PREDICTION whose `grade_after` has not arrived, or
              whose owner field is legitimately not computable yet. Reported,
              never a pass and never a failure — the I21 discipline: a claim is
              registered with the date it becomes checkable, so it can neither
              redden the build early nor be quietly forgotten.
  DARK        the organ did not answer. **Never graded** — an unread number is
              not a matching number, and the run exits 2 rather than 0 (I1/I5:
              unknown degrades to unknown, never to a measurement).

WHAT IT IS NOT, stated so nobody stretches it: publish-only. It moves no
capital, writes no lever, promotes nothing, and is junior to every gate — the
go-live bar is `golive_readiness`'s and is untouched. A STALE row means a
SENTENCE needs correcting (I12, in place), never that a book's verdict moved.

    python3 scripts/claims_ledger.py                 # print the ledger
    python3 scripts/claims_ledger.py --publish       # + bot_state 'claims-ledger'
    python3 scripts/claims_ledger.py --bus-json URL  # grade off the public feed
    python3 scripts/claims_ledger.py --selftest      # offline, pure
"""
import argparse
import datetime as _dt
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
for _p in (HERE, ROOT):
    if _p not in sys.path:
        sys.path.insert(0, _p)

KEY = "claims-ledger"
TTL_SEC = int(os.environ.get("CLAIMS_TTL_SEC", "43200"))   # 12h over a 6h loop
KINDS = ("win", "refusal", "doctrine")

#: The public feed's default location — the same read `audit_code_currency`
#: uses, so this instrument works from a seat with no Railway login.
BUS_JSON = "https://pnl-dashboard-production-858c.up.railway.app/bus.json"


# ---------------------------------------------------------------------------
# THE CLAIMS. Hand-written; every row falsifiable.
#
# id          stable, cited from elsewhere; never reused.
# subject     the row/book/organ the claim is ABOUT (free text, for humans).
# kind        win | refusal | doctrine.
# claim       the prose, as a reader would state it.
# number      the number that prose asserts.
# tol         how far the live value may drift before the prose is WRONG.
#             Declared per row on purpose: 0.30 on a t-stat is a different
#             quantity from 60 on a days-to-gate, and one global epsilon would
#             be a constant nobody could defend on either.
# as_of       when `number` was measured. A commitment (I21) — do NOT edit it
#             to match a later reading; that is the re-mining the winners'
#             docket already paid for.
# owner       (organ bot_state key, dotted path into its payload).
# owner_ref   `path::symbol`, checked by audit_doctrine_enforcement.check_ref —
#             the SAME mechanism the invariants use, IMPORTED not copied, so
#             deleting the organ that owns a claim breaks the claim's build.
# grade_after ISO date from which an unresolvable owner is a FAILURE rather
#             than PENDING. For a measurement already taken this is `as_of`;
#             for a registered prediction it is when the prediction becomes
#             checkable.
# cites       where the prose lives, so a STALE verdict names the file to fix.
# covers      real-money rows this claim justifies (see the ratchet in
#             audit_claim_freshness) — empty tuple for a claim about no live row.
# ---------------------------------------------------------------------------
CLAIMS = [
    {
        "id": "georgia-golive-justification",
        "subject": "freqtrade-georgia-lshadow",
        "kind": "doctrine",
        "claim": "🔮 georgia took 💸 the Farmer's real-money sub-account on "
                 "22-Aug (ta) with '5 of 6 bars, both halves positive, failing "
                 "only t (1.48 < 2.0)'. That t is the whole distance between "
                 "her record and the gate, and it is the number the swap was "
                 "argued on.",
        "number": 1.48,
        "tol": 0.30,
        "as_of": "2026-08-22",
        "owner": ("golive-readiness", "books.freqtrade-georgia-lshadow.t"),
        "owner_ref": 'scripts/golive_readiness.py::KEY = "golive-readiness"',
        "grade_after": "2026-08-22",
        "cites": ("CLAUDE.md", "GEORGIA_GOLIVE_RUNBOOK.md"),
        "covers": ("freqtrade-georgia-lighter",),
    },
    {
        "id": "georgia-exit-sweep-refusal-uw",
        "subject": "freqtrade-georgia-lshadow",
        "kind": "refusal",
        "claim": "(uw) walked 48 exit configurations over 🔮 georgia's own 212 "
                 "REAL priced entries and admitted NONE — 0 of 48 with a "
                 "positive mean, 0 of 48 with both halves positive — so the "
                 "shipped exit stands and the exit is not the lever. The "
                 "refusal was made against a book reading +0.087%/trade on "
                 "n=197; if her realised mean moves materially the refusal is "
                 "re-openable, and this row is what says so.",
        "number": 0.087,
        "tol": 0.10,
        "as_of": "2026-08-27",
        "owner": ("golive-readiness",
                  "books.freqtrade-georgia-lshadow.mean_pct"),
        "owner_ref": 'scripts/golive_readiness.py::KEY = "golive-readiness"',
        "grade_after": "2026-08-27",
        "cites": ("CHANGELOG.md",),
        "covers": (),
    },
    {
        "id": "georgia-entry-cap-5-days-to-gate",
        "subject": "freqtrade-georgia-lshadow",
        "kind": "win",
        "claim": "(vb) graded 🔮 georgia's entry cap on the UNCENSORED "
                 "population (1,816 replayed entries, harness calibrated to "
                 "−0.079pp against her own trades): rank 3 is her BEST entry "
                 "(n=208, +0.313%/trade, t_cl +2.44) where her censored ledger "
                 "said −7.752% on n=3, and cap 3 → 5 takes days-to-gate 344 → "
                 "187 at a HIGHER mean. A PREDICTION, registered here so it is "
                 "graded by the organ rather than remembered: the cap shipped "
                 "27-Aug, so her horizon needs post-cap closes before it can "
                 "speak.",
        "number": 187.0,
        "tol": 60.0,
        "as_of": "2026-08-27",
        "owner": ("golive-readiness",
                  "books.freqtrade-georgia-lshadow.horizon.eta_days"),
        "owner_ref": 'scripts/golive_readiness.py::KEY = "golive-readiness"',
        # ~5.47 closes/day at cap 5; a fortnight is ~75 closes, enough for the
        # horizon to stop reading `undecidable`. Before then an absent
        # `eta_days` is PENDING, not a failure — the claim is about a
        # trajectory that has not had time to exist.
        "grade_after": "2026-09-10",
        "cites": ("CHANGELOG.md",),
        "covers": (),
    },
]


# ---------------------------------------------------------------------------
def _num(v):
    """float or None — never a coercion that turns junk into a measurement.

    TYPE, not `float()`. A STRING is refused even when it parses: an organ that
    starts publishing `"undecidable"` where it published a t-stat must read
    UNRESOLVED, and `float()`-ing a verdict is how a string becomes a fake
    measurement (`bot_pnl_store._census_number` refuses the same class for the
    same reason). A BOOL is refused too — and that is the one place this
    DELIBERATELY differs from `_census_number`, which counts a bool because a
    census field like `capped: False` genuinely is a count. Here a flag where a
    number used to be is a payload that changed shape, and `True` silently
    grading as the claim 1.0 is the worst reading available.
    """
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return float(v)
    if isinstance(v, float):
        return v if v == v and v not in (float("inf"), float("-inf")) else None
    return None


def resolve(payload, path):
    """Walk `a.b.c` into a published payload. -> value or None. Never raises.

    Dotted rather than clever: an owner has to be readable in a diff by
    somebody deciding whether the row is honest, and a lambda in the table
    would be a second place to hide a rule.
    """
    cur = payload
    for part in str(path).split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def _date(s):
    try:
        return _dt.date.fromisoformat(str(s)[:10])
    except (TypeError, ValueError):
        return None


def validate(claims=None):
    """-> [problem]. The DECLARATION gate: a row that cannot be recomputed
    cannot be added. Offline and pure — no network, no DB, no clock."""
    claims = CLAIMS if claims is None else claims
    try:
        from audit_doctrine_enforcement import check_ref
    except Exception as e:                                       # noqa: BLE001
        # IMPORTED, never re-implemented (a second copy of a rule is a second
        # rule). If the import breaks, say so — do not fall back to a private
        # copy that would then be free to disagree with the invariants' one.
        return [f"cannot import audit_doctrine_enforcement.check_ref ({e}) — "
                f"the owner-reference check has ONE owner and it is that one"]
    bad, seen = [], set()
    for row in claims:
        rid = row.get("id") or "<no id>"
        missing = {"id", "subject", "kind", "claim", "number", "tol", "as_of",
                   "owner", "owner_ref", "grade_after", "cites",
                   "covers"} - set(row)
        if missing:
            bad.append(f"{rid}: missing field(s) {sorted(missing)}")
            continue
        extra = set(row) - {"id", "subject", "kind", "claim", "number", "tol",
                            "as_of", "owner", "owner_ref", "grade_after",
                            "cites", "covers"}
        if extra:
            bad.append(f"{rid}: unknown field(s) {sorted(extra)}")
        if rid in seen:
            bad.append(f"{rid}: duplicate id — every citation of it is now "
                       f"ambiguous (the changelog-letter failure, in a table)")
        seen.add(rid)
        if row["kind"] not in KINDS:
            bad.append(f"{rid}: kind {row['kind']!r} is not one of {KINDS}")
        if _num(row["number"]) is None:
            bad.append(f"{rid}: `number` is not a finite number")
        tol = _num(row["tol"])
        if tol is None or tol <= 0:
            bad.append(f"{rid}: `tol` must be a positive number — a zero "
                       f"tolerance makes every row STALE on rounding, which "
                       f"is how a guard gets switched off")
        for f in ("as_of", "grade_after"):
            if _date(row[f]) is None:
                bad.append(f"{rid}: `{f}` is not an ISO date: {row[f]!r}")
        for f in ("cites", "covers"):
            if not isinstance(row[f], tuple):
                bad.append(f"{rid}: `{f}` must be a tuple (a bare string "
                           f"iterates as characters)")
        # THE RULE THIS TABLE EXISTS FOR: name an owner that can recompute it.
        owner = row["owner"]
        if (not isinstance(owner, tuple) or len(owner) != 2
                or not all(isinstance(x, str) and x.strip() for x in owner)):
            bad.append(f"{rid}: `owner` must be (organ_key, dotted.path) and "
                       f"both non-empty — a claim with no recomputable owner "
                       f"CANNOT BE ADDED")
            continue
        why = check_ref(row["owner_ref"], ROOT)
        if why:
            bad.append(f"{rid}: owner_ref `{row['owner_ref']}` no longer "
                       f"resolves — {why}")
    return bad


def grade(row, states, today=None):
    """-> {status, live, drift, why} for ONE row against a states map.

    `states` is {organ_key: payload}, as `bot_pnl_store.fetch_states` returns
    it. A key absent from a SUCCESSFUL read is DARK for that row, never STALE:
    an organ that stopped answering has not disagreed with the claim.
    """
    today = today or _dt.date.today()
    key, path = row["owner"]
    out = {"id": row["id"], "kind": row["kind"], "subject": row["subject"],
           "owner": f"{key}::{path}", "number": row["number"],
           "tol": row["tol"], "as_of": row["as_of"],
           "grade_after": row["grade_after"], "cites": list(row["cites"]),
           "live": None, "drift": None}
    gafter = _date(row["grade_after"]) or today
    due = today >= gafter
    if key not in (states or {}):
        out.update(status="DARK",
                   why=f"organ '{key}' published nothing readable — an unread "
                       f"number is not a matching number")
        return out
    live = _num(resolve(states[key], path))
    if live is None:
        out.update(status=("UNRESOLVED" if due else "PENDING"),
                   why=(f"'{path}' is absent or non-numeric in '{key}'"
                        + ("" if due else
                           f" — PENDING until {row['grade_after']}")))
        return out
    drift = abs(live - float(row["number"]))
    out.update(live=live, drift=round(drift, 6))
    if not due:
        out.update(status="PENDING",
                   why=f"registered prediction, graded from {row['grade_after']}"
                       f" (live {live:g} today)")
        return out
    if drift > float(row["tol"]):
        out.update(status="STALE",
                   why=f"doctrine says {row['number']:g}, the organ says "
                       f"{live:g} — drift {drift:g} > tol {row['tol']:g}")
        return out
    out.update(status="HOLDS",
               why=f"organ says {live:g}, within {row['tol']:g} of "
                   f"{row['number']:g}")
    return out


def grade_all(states, claims=None, today=None):
    claims = CLAIMS if claims is None else claims
    return [grade(r, states, today) for r in claims]


def counts(rows):
    out = {s: 0 for s in ("HOLDS", "STALE", "PENDING", "UNRESOLVED", "DARK")}
    for r in rows:
        out[r["status"]] = out.get(r["status"], 0) + 1
    return out


def build(rows, today=None):
    """The published payload. Pure — the selftest drives it with no DB."""
    today = today or _dt.date.today()
    return {
        "updated": _dt.datetime.now(_dt.timezone.utc).replace(
            microsecond=0).isoformat(),
        "ttl_sec": TTL_SEC,
        "advisory": True,
        "moves_capital": False,
        "rule": ("every claim names (organ_key, dotted.path); the organ's own "
                 "published number is compared to the declared one against the "
                 "row's declared tolerance. DARK is never graded, and a "
                 "registered prediction is PENDING until its grade_after."),
        "n_claims": len(rows),
        "counts": counts(rows),
        "claims": {r["id"]: r for r in rows},
    }


# ------------------------------------------------------------------- I/O shell
def read_states(keys, bus_json=None):
    """-> ({organ_key: payload}, source). {} means DARK, never 'nothing'.

    Two sources on purpose, and the fallback direction matters: a seat with no
    DATABASE_URL (CI, a laptop) can still grade off the PUBLIC feed, which is
    how the 27-Aug georgia measurement in this file's header was taken.
    """
    if bus_json:
        try:
            import urllib.request
            with urllib.request.urlopen(bus_json, timeout=30) as fh:
                doc = json.load(fh)
        except Exception as e:                                   # noqa: BLE001
            print(f"[claims-ledger] bus feed unreadable ({e})", file=sys.stderr)
            return {}, f"bus-json {bus_json} (DARK)"
        if not isinstance(doc, dict):
            return {}, f"bus-json {bus_json} (DARK)"
        out = {}
        for k in keys:
            # /bus.json renames a hyphenated bot_state key with underscores.
            # TWO SPELLINGS TRIED rather than a table: a mapping here would be
            # a second copy of the dashboard's own naming and free to drift.
            for cand in (k, k.replace("-", "_")):
                if isinstance(doc.get(cand), dict):
                    out[k] = doc[cand]
                    break
        return out, f"bus-json {bus_json}"
    try:
        import bot_pnl_store as store
        return (store.fetch_states(list(keys)) or {}), "bot_state"
    except Exception as e:                                       # noqa: BLE001
        print(f"[claims-ledger] state read failed ({e})", file=sys.stderr)
        return {}, "bot_state (DARK)"


def run_once(publish=False, bus_json=None, claims=None, today=None):
    claims = CLAIMS if claims is None else claims
    keys = sorted({r["owner"][0] for r in claims})
    states, source = read_states(keys, bus_json)
    rows = grade_all(states, claims, today)
    payload = build(rows, today)
    payload["source"] = source
    if publish:
        try:
            import bot_pnl_store as store
            if not store.save_state(KEY, payload):
                print("[claims-ledger] publish FAILED (no DB or write "
                      "refused) — the ledger did not update", file=sys.stderr)
        except Exception as e:                                   # noqa: BLE001
            print(f"[claims-ledger] publish failed: {e}", file=sys.stderr)
    return payload


def render(payload):
    c = payload["counts"]
    L = [f"THE LEDGER OF CLAIMS — {payload['n_claims']} claim(s), "
         f"source {payload.get('source', '?')}",
         f"  HOLDS {c['HOLDS']}  STALE {c['STALE']}  PENDING {c['PENDING']}  "
         f"UNRESOLVED {c['UNRESOLVED']}  DARK {c['DARK']}", ""]
    for r in payload["claims"].values():
        L.append(f"  [{r['status']:<10}] {r['id']}  ({r['kind']})")
        L.append(f"      owner {r['owner']}")
        L.append(f"      {r['why']}")
        if r["cites"]:
            L.append(f"      cited in: {', '.join(r['cites'])}")
    return "\n".join(L)


def _cli(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--publish", action="store_true")
    ap.add_argument("--bus-json", nargs="?", const=BUS_JSON, default=None,
                    help="grade off the public feed instead of bot_state")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return selftest()
    bad = validate()
    if bad:
        print("CLAIMS LEDGER REFUSES ITS OWN TABLE:")
        for b in bad:
            print(f"  {b}")
        return 1
    print(render(run_once(publish=a.publish, bus_json=a.bus_json)))
    return 0


# ---------------------------------------------------------------------- tests
def _fixture():
    """Rows shaped exactly like the real ones, for the offline arms."""
    base = dict(subject="s", claim="c", owner_ref='CLAUDE.md::I1 ·',
                cites=(), covers=())
    return [
        dict(base, id="holds", kind="win", number=2.0, tol=0.5,
             as_of="2026-08-01", grade_after="2026-08-01",
             owner=("k", "books.b.t")),
        dict(base, id="stale", kind="doctrine", number=2.0, tol=0.01,
             as_of="2026-08-01", grade_after="2026-08-01",
             owner=("k", "books.b.t")),
        dict(base, id="pending", kind="win", number=9.0, tol=0.1,
             as_of="2026-08-01", grade_after="2999-01-01",
             owner=("k", "books.b.missing")),
        dict(base, id="unresolved", kind="win", number=9.0, tol=0.1,
             as_of="2026-08-01", grade_after="2026-08-01",
             owner=("k", "books.b.missing")),
        dict(base, id="dark", kind="refusal", number=9.0, tol=0.1,
             as_of="2026-08-01", grade_after="2026-08-01",
             owner=("gone", "books.b.t")),
    ]


def selftest():
    today = _dt.date(2026, 8, 27)
    rows = _fixture()

    # the real table declares nothing unfalsifiable — this is the gate that
    # keeps the ledger from becoming the document it exists to replace
    assert not validate(), validate()

    st = {"k": {"books": {"b": {"t": 2.05}}}}
    g = {r["id"]: r for r in grade_all(st, rows, today)}
    assert g["holds"]["status"] == "HOLDS", g["holds"]
    assert g["stale"]["status"] == "STALE", g["stale"]
    assert g["pending"]["status"] == "PENDING", g["pending"]
    assert g["unresolved"]["status"] == "UNRESOLVED", g["unresolved"]
    assert g["dark"]["status"] == "DARK", g["dark"]
    # a STALE row must NAME the file to fix and both numbers, or the operator
    # cannot act on it (I8 — a detector names the object you can open)
    assert "2" in g["stale"]["why"] and "2.05" in g["stale"]["why"]

    # DARK IS NEVER GRADED. An organ that stops answering has not agreed with
    # the claim and has not disagreed — the one outcome that must never read
    # as a pass (I1/I5).
    dark = grade_all({}, rows, today)
    assert {r["status"] for r in dark} == {"DARK"}, dark
    assert counts(dark)["HOLDS"] == 0

    # a PENDING row that CAN be read is still PENDING — grade_after is a
    # commitment about WHEN, not a fallback for a missing field
    early = grade(dict(rows[0], grade_after="2999-01-01"), st, today)
    assert early["status"] == "PENDING" and early["live"] == 2.05, early

    # junk never becomes a measurement: a bool, a string, a NaN and a missing
    # branch all read UNRESOLVED rather than 1.0 / 0.0
    for junk in (True, "2.05", float("nan"), None, [2.05], float("inf")):
        s = {"k": {"books": {"b": {"t": junk}}}}
        assert grade(rows[0], s, today)["status"] == "UNRESOLVED", junk
    # ...but a plain int is a number
    assert grade(rows[0], {"k": {"books": {"b": {"t": 2}}}},
                 today)["status"] == "HOLDS"

    # resolve() walks, and refuses to walk through a non-dict
    assert resolve({"a": {"b": 1}}, "a.b") == 1
    assert resolve({"a": 1}, "a.b") is None
    assert resolve({}, "a") is None

    # DECLARATION GATE — each refusal, driven one at a time
    ok = _fixture()[0]
    for mutant, needle in (
            (dict(ok, owner="not-a-tuple"), "CANNOT BE ADDED"),
            (dict(ok, owner=("k",)), "CANNOT BE ADDED"),
            (dict(ok, owner=("", "p")), "CANNOT BE ADDED"),
            (dict(ok, owner_ref="scripts/no_such_file.py"), "no longer resolves"),
            (dict(ok, owner_ref="CLAUDE.md::zzz_not_here_zzz"), "no longer resolves"),
            (dict(ok, kind="vibes"), "is not one of"),
            (dict(ok, tol=0), "positive number"),
            (dict(ok, tol=-1), "positive number"),
            (dict(ok, number="lots"), "not a finite number"),
            (dict(ok, as_of="soon"), "not an ISO date"),
            (dict(ok, cites="CLAUDE.md"), "must be a tuple"),
    ):
        b = validate([mutant])
        assert b and any(needle in x for x in b), (needle, b)
    assert validate([{k: v for k, v in ok.items() if k != "owner"}])
    assert validate([dict(ok, surprise=1)])
    dupes = validate([ok, dict(ok)])
    assert any("duplicate id" in x for x in dupes), dupes

    # the payload carries the bus contract's two fields, and PUBLISH-ONLY holds
    # structurally: this module names no lever and no order path
    pay = build(grade_all(st, rows, today), today)
    assert pay["ttl_sec"] > 0 and pay["updated"] and pay["advisory"] is True
    assert pay["counts"]["STALE"] == 1 and pay["n_claims"] == len(rows)
    # ...and PUBLISH-ONLY holds STRUCTURALLY, by AST rather than by a page-wide
    # substring scan — three tests in one 30-Jul session failed on the very
    # sentence promising the property they checked, so the names below are
    # asserted as CALLED FUNCTIONS, not as text (this file names all four in
    # the line above and must stay green).
    import ast
    called = set()
    for node in ast.walk(ast.parse(open(os.path.join(
            HERE, "claims_ledger.py"), encoding="utf-8").read())):
        if isinstance(node, ast.Call):
            f = node.func
            called.add(f.attr if isinstance(f, ast.Attribute)
                       else getattr(f, "id", ""))
    forbidden = {"write_levers", "get_lever", "market_open",
                 "publish_paper_trade", "publish"} & called
    assert not forbidden, f"publish-only violated: {sorted(forbidden)}"

    # AN UNREADABLE SOURCE IS DARK, NOT EMPTY. Driven through the real reader
    # with a URL that cannot resolve (no network reached: urlopen raises on the
    # missing file), because "the feed was down" and "the organ says nothing"
    # must never be the same byte-string to a consumer.
    st_bad, src_bad = read_states(["k"], "file:///claims_ledger_no_such_file")
    assert st_bad == {} and "DARK" in src_bad, (st_bad, src_bad)
    assert counts(grade_all(st_bad, rows, today))["DARK"] == len(rows)

    print(f"claims_ledger selftest OK ({len(CLAIMS)} real claim(s); HOLDS/"
          f"STALE/PENDING/UNRESOLVED/DARK all driven; 12 declaration refusals)")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        raise SystemExit(selftest())
    import bot_pnl_store as _store
    raise SystemExit(_store.organ_main(KEY, _cli))
