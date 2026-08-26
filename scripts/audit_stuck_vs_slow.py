#!/usr/bin/env python3
"""[2026-08-26] STUCK vs SLOW — `{closed: 0}` is byte-identical between a book
that CANNOT trade and one that has simply not finished a trade yet.

**Eamon, 26-Aug:** *"a lot of the time we've thought it's stuck it's slow."*

He is right, and the fleet has repeatedly made keep-or-retire calls on the word
"undecidable" while that word was covering at least five different states. This
is I1 (LIVENESS BEFORE SEMANTICS) at BOOK scale: before interpreting what a
book's ledger SAYS, establish whether anything is stopping it. A frozen book and
a patient one are byte-identical if you read the close count — the close count
is the one quantity the fault holds fixed (I2).

THE DISCRIMINATOR IS NOT CLOSES, IT IS OCCUPANCY.

  * a book holding at its own cap is DEPLOYED — nothing is refusing it, and its
    zero closes are a HOLD TIME, not a defect;
  * a book empty while its own census shows candidates that passed its gate is
    being REFUSED by one of its own gates, and the census names which one;
  * a book empty with an empty census has no SUPPLY — there was nothing to
    refuse;
  * a book empty, with supply, with free slots, and with NOTHING in its census
    explaining the refusal is the only shape that asserts a DEFECT.

STATES: TRADING · SLOW · REFUSING · SUPPLY_EMPTY · STUCK · UNKNOWN.
REFUSING IS NOT AN ALARM — it is a gate doing its job, and most empty books are
in it most loops. **STUCK is the only state that asserts a defect**, so it is
deliberately the hardest to reach: anything ambiguous degrades to UNKNOWN. A
detector that cries wolf is one the operator learns to ignore ((gl)).

═══════════════════════════════════════════════════════════════════════════════
THE HONESTY REQUIREMENT — A SNAPSHOT IS NOT A STRUCTURAL VERDICT
═══════════════════════════════════════════════════════════════════════════════
One loop's census cannot separate "quiet right now" from "always quiet". 🧘
Douglas fades impulses and is quiet on most loops; a single sample would read it
REFUSING and a careless reader would call that a fault.

And the fleet's own history channel does NOT close this gap: `/bus.json?hours=`
carries **bot_state** history (organ keys — fleet-risk, lighter-market, …), and a
book's census lives in its **bot_pnl** row's `extra.scan` / `extra.census`, which
that endpoint does not retain. Measured 26-Aug: `?hours=6` returned 510 rows
across 19 organ keys and ZERO book rows. So there is no retained series to mine,
and this tool samples FORWARD instead:

    --samples N --interval S     poll the live feed N times, S seconds apart
    --pnl-json A --pnl-json B    or replay N saved snapshots, oldest first

Two consequences, both enforced in code rather than written in prose:

  1. **STUCK requires `MIN_STUCK_PUBLISHES` DISTINCT PUBLISHES agreeing.** Not
     samples — PUBLISHES, keyed on the row's own `updated_at`. Polling faster
     than the bot publishes yields no new information (a sensor cannot outrun
     its own sampling rate), and counting those re-reads as evidence is how a
     snapshot masquerades as a structural verdict.
  2. **Every verdict carries its sample count**, and a run that cannot reach
     the STUCK bar says so at the TOP of its output, not in a footnote.

═══════════════════════════════════════════════════════════════════════════════
WHAT IT CROSS-REFERENCES, AND WHY THAT IS THE POINT
═══════════════════════════════════════════════════════════════════════════════
`golive_readiness`'s DECISION DOCKET asks Eamon to retire books it calls
`zero_ledger` — "no closes ever". Measured the day this shipped, three books
were on that list and **two of them were merely SLOW**: 🧮 Hull (6 of 6 slots
held, ~6 closes/30d DECLARED AT BIRTH) and 🏦 Rich Dad (6 of 6 held). Retiring a
book for not having finished a trade it is still holding is a retirement made
for the wrong reason, and this lens exists to stop exactly that.

This tool is READ-ONLY and ADVISORY. It grades nothing, promotes nothing, moves
no capital and writes no lever; the go-live gate and the docket stay senior. It
re-reads them.

    python3 scripts/audit_stuck_vs_slow.py
    python3 scripts/audit_stuck_vs_slow.py --samples 3 --interval 120
    python3 scripts/audit_stuck_vs_slow.py --pnl-json snap.json --bus-json bus.json
    python3 scripts/audit_stuck_vs_slow.py --selftest

EXIT CODES: 0 clean · 1 findings (a STUCK book, or a docket entry that would
retire a book this lens reads as SLOW) · 2 the feed was unusable (FAIL-CLOSED —
a dark feed is never a pass, the (jc) contract).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import re
import sys
import time
import urllib.request
from dataclasses import dataclass, field

DASH = os.environ.get(
    "DASH_URL", "https://pnl-dashboard-production-858c.up.railway.app")
DEFAULT_PNL = f"{DASH}/pnl.json"
DEFAULT_BUS = f"{DASH}/bus.json"

#: The six states. Ordered worst-news-first for the report.
STATES = ("STUCK", "UNKNOWN", "SUPPLY_EMPTY", "REFUSING", "SLOW", "TRADING")

#: STUCK asserts a DEFECT, so it needs agreement across this many DISTINCT
#: publishes (keyed on the row's own `updated_at`). Three, not two: two
#: consecutive loops of a bot with a slow cadence is one story told twice, and
#: the cost of a false STUCK is an operator who stops reading the tool.
MIN_STUCK_PUBLISHES = 3

#: Fallback only. The feed publishes its OWN staleness verdict per row
#: (`stale`) and its own threshold (`meta.stale_threshold_sec`) — different
#: books legitimately carry different thresholds (the sniper's is 900s, the
#: stock books' 93600s), so the publisher's verdict is preferred and this
#: constant is used only when a snapshot predates those fields.
FALLBACK_STALE_S = 900

#: A row is a BOOK when the dashboard says so. Rows of another kind are not
#: books and are skipped rather than mis-graded.
BOOK_KIND = "trading"

#: Census fields that mean "candidates that passed THIS book's own gate this
#: loop and were available to open". Books name it differently; the concept is
#: the same, and a book that publishes none of these cannot be read by this
#: lens (which is a finding about the book, not a verdict about its health).
SUPPLY_FIELDS = ("eligible", "in_band", "signal", "events", "offered")

#: "How much tape did it look at" — the denominator that separates a gate that
#: refused everything from a universe that offered nothing.
SCAN_FIELDS = ("scanned", "universe", "universe_n")

HELD_FIELDS = ("held",)
OPENED_FIELDS = ("opened",)

#: Never counted as an explanation for an empty book: supply/scan/held/opened
#: are the frame, and these are capacity or display fields.
_NOT_EXPLANATIONS = (set(SUPPLY_FIELDS) | set(SCAN_FIELDS) | set(HELD_FIELDS)
                     | set(OPENED_FIELDS) | {"max_open", "free_slots", "top",
                                             "next"})

#: Census keys that are TELEMETRY (a rate, a level, a threshold), not a count
#: of candidates. Matching here means "not an explanation bucket"; the
#: fail-safe direction is the opposite one, so this list is kept tight and the
#: integral-value test below does most of the work.
_TELEMETRY_RE = re.compile(
    r"(_bps|_pct|_usd|_apr|_sec|_h|_m|_med|_max|_min|_s)$|^(rsi_|dev_|gate_)")

#: Docket reasons that name an EVIDENCE verdict rather than a mechanical one.
#: A docket entry is only ever re-read here — never overruled.
DOCKET_ZERO_LEDGER = "zero_ledger"


# ── time ────────────────────────────────────────────────────────────────────
def sydney(iso_utc):
    """Eamon reads times on his own clock (CLAUDE.md). Internals stay UTC; this
    is the reporting surface, and it degrades to the UTC string it was handed
    if the zone database is absent rather than losing the stamp."""
    if not iso_utc:
        return "unknown"
    try:
        t = dt.datetime.fromisoformat(str(iso_utc).replace("Z", "+00:00"))
        if t.tzinfo is None:
            t = t.replace(tzinfo=dt.timezone.utc)
        from zoneinfo import ZoneInfo
        t = t.astimezone(ZoneInfo("Australia/Sydney"))
        return f"{t:%Y-%m-%d %H:%M} {t:%Z} (Sydney)"
    except Exception:                                        # noqa: BLE001
        return f"{iso_utc} UTC"


# ── feed ────────────────────────────────────────────────────────────────────
def load(feed, timeout=45):
    """A URL or a local path. RAISES on anything unusable — the caller turns
    that into a non-zero exit, never a quiet pass."""
    if str(feed).startswith("http"):
        req = urllib.request.Request(feed, headers={"User-Agent": "audit"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    with open(feed) as fh:
        return json.load(fh)


def book_rows(doc):
    """The living BOOK rows of a /pnl.json document.

    Retired rows are already filtered by the dashboard's own roster; this drops
    anything the feed itself labels as not-a-book, and raises on an empty or
    shapeless document (FAIL-CLOSED)."""
    rows = doc.get("bots") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list) or not rows:
        raise ValueError("feed carried no rows")
    out = []
    for r in rows:
        if not isinstance(r, dict) or not r.get("bot"):
            continue
        kind = r.get("kind")
        if kind is not None and kind != BOOK_KIND:
            continue
        if str(r.get("status") or "") == "retired":
            continue
        out.append(r)
    if not out:
        raise ValueError("feed carried rows but no living book rows")
    return out


def _num(v):
    """A real number, or None. `True` is not a count."""
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return None
    return v


def _count(v):
    """A COUNT: a non-negative whole number. `74.8` (a bps level) is not."""
    n = _num(v)
    if n is None:
        return None
    if isinstance(n, float) and not n.is_integer():
        return None
    return int(n)


# ── the census ──────────────────────────────────────────────────────────────
@dataclass
class Census:
    """A book's own published account of what it looked at and what it did.

    `present=False` is itself a finding (I18: a component that opens nothing
    must publish its OWN census — `{open: 0}` is byte-identical between "quiet"
    and "structurally impossible")."""
    present: bool = False
    source: str | None = None
    scanned: int | None = None
    supply: int | None = None
    supply_field: str | None = None
    supply_inferred: bool = False
    held: int | None = None
    opened: int | None = None
    explanations: dict = field(default_factory=dict)

    @property
    def top_explanation(self):
        if not self.explanations:
            return None
        k = max(self.explanations, key=lambda x: self.explanations[x])
        return k, self.explanations[k]


def _flatten(census):
    """One level of nesting, prefixed. 👩 mum publishes `verdicts: {no_signal:
    22, uptrend_blocked: 1}` — the per-candidate outcome map that accounts for
    her whole universe, and a flat scan would never see it."""
    flat = {}
    for k, v in census.items():
        if isinstance(v, dict):
            for ik, iv in v.items():
                if _num(iv) is not None:
                    flat[f"{k}.{ik}"] = iv
        else:
            flat[k] = v
    return flat


def read_census(row):
    """-> Census. Reads `extra.scan` (most books) or `extra.census` (the funding
    variants). Both are the publisher's own field; nothing is recomputed here.

    THE SUPPLY RULE, and its fail-safe direction. `supply` is read from an
    explicit field where the book publishes one. Where it does not, it is
    INFERRED as zero only when the census's own buckets ACCOUNT FOR THE WHOLE
    SCAN (`sum(explanations) + held >= scanned`) — i.e. the book has said in its
    own numbers where every candidate went. Anything else leaves `supply=None`,
    which reads as UNKNOWN, never as STUCK."""
    extra = row.get("extra") or {}
    raw, src = None, None
    for key in ("scan", "census"):
        v = extra.get(key)
        if isinstance(v, dict) and v:
            raw, src = v, f"extra.{key}"
            break
    if raw is None:
        return Census(present=False)

    flat = _flatten(raw)
    c = Census(present=True, source=src)

    for f in SCAN_FIELDS:
        if _count(flat.get(f)) is not None:
            c.scanned = _count(flat[f])
            break
    for f in SUPPLY_FIELDS:
        if _count(flat.get(f)) is not None:
            c.supply, c.supply_field = _count(flat[f]), f
            break
    for f in HELD_FIELDS:
        if _count(flat.get(f)) is not None:
            c.held = _count(flat[f])
            break
    for f in OPENED_FIELDS:
        if _count(flat.get(f)) is not None:
            c.opened = _count(flat[f])
            break

    for k, v in flat.items():
        base = k.split(".")[-1]
        if base in _NOT_EXPLANATIONS or k in _NOT_EXPLANATIONS:
            continue
        if _TELEMETRY_RE.search(base):
            continue
        n = _count(v)
        if n is not None and n > 0:
            c.explanations[k] = n

    if c.supply is None and c.scanned:
        accounted = sum(c.explanations.values()) + (c.held or 0)
        if accounted >= c.scanned:
            c.supply, c.supply_inferred = 0, True
    return c


def read_cap(row):
    """-> (cap, source). The book's OWN declared position cap.

    Read from the publisher, in the order the fleet actually publishes it. An
    unknown cap is None and is never guessed — I8: unknown degrades to the
    honest identifier, never to a number a reader would act on."""
    extra = row.get("extra") or {}
    caps = extra.get("caps") if isinstance(extra.get("caps"), dict) else {}
    for holder, name, label in (
            (caps, "max_positions", "extra.caps.max_positions"),
            (caps, "max_open", "extra.caps.max_open"),
            (extra, "max_open", "extra.max_open"),
            (caps, "legs", "extra.caps.legs"),
    ):
        n = _count(holder.get(name))
        if n is not None and n > 0:
            return n, label
    census = extra.get("census") if isinstance(extra.get("census"), dict) else {}
    free, held = _count(census.get("free_slots")), _count(census.get("held"))
    if free is not None and held is not None:
        return free + held, "extra.census.free_slots+held"
    return None, None


# ── one observation ─────────────────────────────────────────────────────────
@dataclass
class Obs:
    bot: str
    sampled_at: str
    published_at: str | None
    status: str
    stale: bool
    open_n: int | None
    closed_n: int | None
    cap: int | None
    cap_src: str | None
    census: Census


def observe(row, sampled_at, stale_threshold_s=None):
    """One /pnl.json row -> one Obs. Liveness FIRST (I1): the row's own `stale`
    verdict is preferred, because the dashboard applies a per-book threshold
    this script has no business re-deriving."""
    stale = row.get("stale")
    if not isinstance(stale, bool):
        age = _num(row.get("age_sec"))
        thr = stale_threshold_s or FALLBACK_STALE_S
        stale = age is None or age > thr
    return Obs(
        bot=str(row.get("bot")),
        sampled_at=sampled_at,
        published_at=row.get("updated_at"),
        status=str(row.get("status") or ""),
        stale=bool(stale),
        open_n=_count(row.get("open_trades")),
        closed_n=_count(row.get("closed_trades")),
        cap=read_cap(row)[0],
        cap_src=read_cap(row)[1],
        census=read_census(row),
    )


# ── the classifier ──────────────────────────────────────────────────────────
@dataclass
class Verdict:
    bot: str
    state: str
    why: str
    samples: int = 0
    publishes: int = 0
    evidence: dict = field(default_factory=dict)

    @property
    def asserts_defect(self):
        return self.state == "STUCK"


def _stuck_shaped(o):
    """Is THIS observation the shape that asserts a defect?

    Every clause is a way the book could be innocent, and each one is checked
    rather than assumed. Returns (bool, why_not)."""
    if o.stale:
        return False, "row is stale"
    if o.open_n is None:
        return False, "row publishes no open count"
    if o.open_n != 0:
        return False, "book is holding"
    if not o.census.present:
        return False, "no census"
    if o.cap is not None and o.cap <= 0:
        return False, "cap is zero — the book has no slot to fill"
    if o.census.held:
        return False, "census says it holds positions the row does not"
    if o.census.opened:
        return False, "census says it opened this loop"
    if o.census.supply is None:
        return False, "census publishes no supply count"
    if o.census.supply <= 0:
        return False, "no supply passed its gate"
    if o.census.explanations:
        return False, "census names a reason"
    return True, ""


def classify(obs_seq):
    """-> Verdict for ONE book from one or more observations, oldest first.

    The LATEST observation decides every state except STUCK; STUCK additionally
    requires `MIN_STUCK_PUBLISHES` distinct publishes all agreeing, so a single
    snapshot can never assert a defect."""
    obs = [o for o in obs_seq if o is not None]
    if not obs:
        return Verdict("?", "UNKNOWN", "no observation")
    obs = sorted(obs, key=lambda o: o.sampled_at or "")
    cur = obs[-1]
    ev = {
        "open": cur.open_n, "cap": cur.cap, "cap_src": cur.cap_src,
        "closed": cur.closed_n, "census": cur.census.source,
        "scanned": cur.census.scanned, "supply": cur.census.supply,
        "supply_field": cur.census.supply_field,
        "supply_inferred": cur.census.supply_inferred,
        "top_refusal": cur.census.top_explanation,
        "published_at": cur.published_at, "status": cur.status,
    }
    publishes = len({o.published_at for o in obs if o.published_at})
    v = lambda st, why: Verdict(cur.bot, st, why, len(obs), publishes, ev)  # noqa: E731

    # I1 — liveness before semantics. A dead row and a healthy one are
    # byte-identical in every field but the timestamp.
    if cur.stale:
        return v("UNKNOWN", "row is STALE — I1: establish that something still "
                            "writes it before reading what it says")
    if cur.status not in ("online", "paper"):
        return v("UNKNOWN", f"status={cur.status!r} — this lens reads a "
                            f"RUNNING book; a halted or standby row is a "
                            f"different question")
    if cur.open_n is None:
        return v("UNKNOWN", "row publishes no open-position count")

    # DEPLOYED. Nothing is refusing a book that is holding, so its close count
    # is a hold time. This is the read the docket cannot make.
    if cur.open_n > 0:
        at_cap = cur.cap is not None and cur.open_n >= cur.cap
        where = (f"{cur.open_n}/{cur.cap} slots"
                 if cur.cap is not None else f"{cur.open_n} open")
        if cur.closed_n:
            return v("TRADING", f"holding {where} and has closed "
                                f"{cur.closed_n}")
        return v("SLOW", f"holding {where}"
                         f"{' — FULL' if at_cap else ''} with ZERO closes: it "
                         f"is DEPLOYED, not blocked. Its zero ledger is a HOLD "
                         f"TIME, and no gate is refusing it")

    # EMPTY. The census is the only thing that can say why.
    c = cur.census
    if not c.present:
        return v("UNKNOWN", "EMPTY and publishes NO census — nothing can say "
                            "whether it is refused, unsupplied or stuck (I18)")
    if c.held:
        return v("UNKNOWN", f"census says held={c.held} while the row says 0 "
                            f"open — mid-loop skew; not read")
    if c.opened:
        return v("UNKNOWN", f"census says opened={c.opened} this loop while "
                            f"the row shows 0 open — mid-loop skew; not read")
    if c.supply is None:
        return v("UNKNOWN", f"EMPTY, census {c.source} publishes no "
                            f"eligible-equivalent count and its buckets do not "
                            f"account for the scan — cannot tell refused from "
                            f"unsupplied")
    if c.supply <= 0:
        top = c.top_explanation
        how = " (inferred: its buckets account for the whole scan)" \
            if c.supply_inferred else ""
        # A REFUSAL BUCKET IS PROOF IT LOOKED, even when the book publishes no
        # `scanned` total: 🎯 the sniper's census carries `not_young: 69` and no
        # scan count at all, and reading that as "nothing to refuse" would
        # invert the finding. SUPPLY_EMPTY is reserved for a census that says,
        # in its own numbers, that nothing reached the gate.
        if top:
            seen = f"{c.scanned} scanned, " if c.scanned else ""
            return v("REFUSING", f"EMPTY: {seen}0 passed its own gate{how}, "
                                 f"biggest bucket {top[0]}={top[1]}. Its gate "
                                 f"is working, not broken")
        if c.scanned:
            return v("REFUSING", f"EMPTY: {c.scanned} scanned, 0 passed its "
                                 f"own gate — but NO bucket names the refusal, "
                                 f"so the census cannot say which gate bound "
                                 f"(I18)")
        return v("SUPPLY_EMPTY", "EMPTY, and its census reports neither a scan "
                                 "nor a single refusal — nothing reached the "
                                 "gate to be refused")
    if c.explanations:
        top = c.top_explanation
        return v("REFUSING", f"EMPTY with {c.supply} past its gate, and its "
                             f"census names why nothing opened: {top[0]}="
                             f"{top[1]}")

    # Supply exists, slots are free, and nothing in the book's own numbers
    # explains the refusal. This is the ONLY shape that asserts a defect, and
    # one loop is not allowed to assert it.
    agree = [o for o in obs if _stuck_shaped(o)[0]]
    agree_pub = len({o.published_at for o in agree if o.published_at})
    if agree_pub >= MIN_STUCK_PUBLISHES and len(agree) == len(obs):
        return Verdict(
            cur.bot, "STUCK",
            f"{c.supply} candidates passed its own gate, slots are free, and "
            f"NOTHING in its census explains why none opened — held across "
            f"{agree_pub} distinct publishes", len(obs), publishes, ev)
    return v("UNKNOWN",
             f"STUCK-SHAPED ({c.supply} past its gate, slots free, no reason "
             f"published) but only {agree_pub} of {MIN_STUCK_PUBLISHES} "
             f"distinct publishes agree — a snapshot is not a structural "
             f"verdict. Re-run with --samples")


# ── the gate's own reading ──────────────────────────────────────────────────
def gate_view(bus_doc):
    """-> (per-book gate reading, docket list, gate `updated`).

    Read, never recomputed: `golive_readiness` owns the horizon and the docket,
    and a second copy of a rule is a second rule ((hj))."""
    g = (bus_doc or {}).get("golive_readiness") or {}
    if not isinstance(g, dict):
        return {}, [], None
    view = {}
    for src in ("books", "below_floor"):
        for bot, b in (g.get(src) or {}).items():
            if not isinstance(b, dict):
                continue
            h = b.get("horizon") if isinstance(b.get("horizon"), dict) else {}
            view[bot] = {
                "n": b.get("n"), "days": b.get("days"),
                "verdict": h.get("verdict"), "why": h.get("why"),
                "eta": h.get("eta"), "src": src,
            }
    docket = g.get("decision_docket")
    docket = docket if isinstance(docket, list) else []
    return view, docket, g.get("updated")


# ── the audit ───────────────────────────────────────────────────────────────
def audit(samples, bus_doc=None):
    """-> (verdicts, docket_reads, no_census, meta).

    `samples` is a list of (sampled_at, /pnl.json document), OLDEST FIRST."""
    if not samples:
        raise ValueError("no samples")
    per_book = {}
    for ts, doc in samples:
        meta = doc.get("meta") if isinstance(doc, dict) else {}
        thr = (meta or {}).get("stale_threshold_sec")
        for row in book_rows(doc):
            per_book.setdefault(str(row.get("bot")), []).append(
                observe(row, ts, thr))

    verdicts = {b: classify(o) for b, o in sorted(per_book.items())}
    no_census = sorted(
        b for b, o in per_book.items() if not o[-1].census.present)

    gv, docket, gate_updated = gate_view(bus_doc)
    reads = []
    for e in docket:
        if not isinstance(e, dict):
            continue
        bot = str(e.get("book") or "")
        v = verdicts.get(bot)
        reads.append({
            "book": bot,
            "docket_reason": e.get("reason"),
            "docket_why": e.get("why"),
            "asks": e.get("asks"),
            "since": e.get("since"),
            "days_held": e.get("days_held"),
            "state": v.state if v else "UNKNOWN",
            "why": v.why if v else "not in the /pnl.json feed at all",
            # THE FLAG. A docket entry that would retire a book this lens reads
            # as DEPLOYED-AND-HOLDING is a retirement about to be made for the
            # wrong reason — the exact error this instrument exists to prevent.
            "misread": bool(v and v.state == "SLOW"),
        })

    last = samples[-1][1]
    meta = {
        "generated_at": ((last.get("meta") or {}).get("generated_at")
                         if isinstance(last, dict) else None),
        "samples": len(samples),
        "gate_updated": gate_updated,
        "gate_seen": len(gv),
        "bus": bus_doc is not None,
    }
    return verdicts, reads, no_census, meta


# ── report ──────────────────────────────────────────────────────────────────
def render(verdicts, reads, no_census, meta, gate=None):
    gate = gate or {}
    out = []
    a = out.append
    a("═" * 78)
    a("STUCK vs SLOW — occupancy, not closes, is the discriminator")
    a("═" * 78)
    a(f"feed generated : {sydney(meta.get('generated_at'))}")
    a(f"gate published : {sydney(meta.get('gate_updated'))}"
      if meta.get("bus") else "gate published : (no --bus-json; docket unread)")
    # Publishes per BOOK, not per run: books publish on their own cadence, so a
    # run that gave one book three fresh loops may have re-read another's single
    # loop three times. The range is the honest statement of what was sampled.
    pubs_all = [v.publishes for v in verdicts.values()] or [0]
    lo, pubs = min(pubs_all), max(pubs_all)
    a(f"samples        : {meta.get('samples')} · distinct publishes per book "
      f"{lo}–{pubs} (STUCK needs {MIN_STUCK_PUBLISHES})")
    if pubs < MIN_STUCK_PUBLISHES:
        a("")
        a(f"  !! SNAPSHOT ONLY — {pubs} distinct publish(es) < "
          f"{MIN_STUCK_PUBLISHES}. STUCK cannot be asserted from this run, by")
        a("     construction. A one-loop census cannot separate 'quiet right "
          f"now' from 'always")
        a("     quiet'; a stuck-shaped book therefore reads UNKNOWN here. "
          "Re-run with")
        a(f"     --samples {MIN_STUCK_PUBLISHES} --interval <the book's loop "
          f"period> to reach a verdict.")
    a("")
    a(f"{'BOOK':32s} {'STATE':13s} {'open/cap':9s} {'closed':>6s}  WHY")
    a("─" * 78)
    for st in STATES:
        for bot, v in verdicts.items():
            if v.state != st:
                continue
            e = v.evidence
            cap = e.get("cap")
            occ = f"{e.get('open')}/{cap}" if cap is not None \
                else f"{e.get('open')}/?"
            a(f"{bot:32s} {st:13s} {occ:9s} {str(e.get('closed')):>6s}  "
              f"{v.why}")
            g = gate.get(bot)
            if g and g.get("why"):
                a(f"{'':32s} {'':13s} {'':9s} {'':>6s}  gate: "
                  f"{g.get('verdict') or '—'} · {str(g['why'])[:96]}")
    a("")
    a("PUBLISHES NO CENSUS — the observability hole (I18: a component that "
      "opens nothing")
    a("must publish its OWN census; without one, {open: 0} is byte-identical "
      "between")
    a("'quiet' and 'structurally impossible')")
    a("─" * 78)
    if no_census:
        for b in no_census:
            v = verdicts.get(b)
            blind = " <- EMPTY, so this gap is what blinds the verdict" \
                if v and v.evidence.get("open") == 0 else ""
            a(f"  {b:32s} {v.state if v else '?':13s}{blind}")
    else:
        a("  (none — every living book publishes a census)")
    a("")
    a("DECISION DOCKET, RE-READ THROUGH OCCUPANCY")
    a("─" * 78)
    if not meta.get("bus"):
        a("  (no --bus-json / bus feed — docket not read)")
    elif not reads:
        a("  (docket empty)")
    else:
        for r in reads:
            flag = "  ⚑ MISREAD" if r["misread"] else ""
            a(f"  {r['book']:32s} docket={str(r['docket_reason']):13s} "
              f"-> {r['state']}{flag}")
            a(f"  {'':32s} since {sydney(r['since'])}"
              f" · {r['days_held']}d on the docket")
            a(f"  {'':32s} this lens: {r['why']}")
            if r["misread"]:
                a(f"  {'':32s} ** the docket asks: {r['asks']}")
                a(f"  {'':32s} ** it is not undecidable — it is DEPLOYED and "
                  f"HOLDING. Retiring")
                a(f"  {'':32s} ** it here is a retirement made for the wrong "
                  f"reason.")
            a("")
    stuck = [v for v in verdicts.values() if v.asserts_defect]
    misread = [r for r in reads if r["misread"]]
    a("SUMMARY")
    a("─" * 78)
    counts = {s: sum(1 for v in verdicts.values() if v.state == s)
              for s in STATES}
    a("  " + " · ".join(f"{s} {counts[s]}" for s in STATES))
    a(f"  STUCK (asserts a defect): {len(stuck)}")
    a(f"  docket entries this lens reads as merely SLOW: {len(misread)}")
    a("")
    a("  REFUSING is NOT an alarm — it is a gate doing its job. SLOW is not a")
    a("  failure — it is a hold time. Only STUCK asserts a defect.")
    return "\n".join(out)


# ── selftest ────────────────────────────────────────────────────────────────
def _selftest():
    """Offline and pure: no network, no DB, no git. Fixtures are TRANSCRIPTS of
    real publisher output captured from /pnl.json on 26-Aug — not shapes
    invented to match the reader."""
    def row(bot, open_n, closed_n, extra, status="online", stale=False,
            updated="2026-08-27T12:00:00+00:00"):
        return {"bot": bot, "kind": "trading", "status": status,
                "open_trades": open_n, "closed_trades": closed_n,
                "stale": stale, "age_sec": 5, "updated_at": updated,
                "extra": extra}

    def one(r, ts="2026-08-27T12:00:00+00:00"):
        return classify([observe(r, ts)])

    # 🧮 Hull — real row: 6 of 6 held, zero closes. SLOW, not undecidable.
    hull = row("book-hull-lshadow", 6, 0, {
        "scan": {"deep": 4, "held": 6, "thin": 85, "scanned": 228,
                 "waiting": 2, "eligible": 1, "noncrypto": 0,
                 "above_band": 23, "below_band": 107, "adverse_basis": 0},
        "caps": {"max_positions": 6, "min_vol": 2000000.0}})
    v = one(hull)
    assert v.state == "SLOW", v
    assert "6/6" in v.why and "DEPLOYED" in v.why, v.why

    # 🏦 Rich Dad — same shape, different book.
    kiyo = row("book-kiyosaki-lshadow", 6, 0, {
        "scan": {"cold": 203, "held": 6, "thin": 16, "scanned": 228,
                 "waiting": 1, "eligible": 2, "noncrypto": 0,
                 "slow_payback": 0},
        "caps": {"max_positions": 6}})
    assert one(kiyo).state == "SLOW"

    # 📐 Grimes — empty, supply past the setup scan, its own gate refusing.
    grimes = row("book-grimes-lshadow", 0, 0, {
        "scan": {"held": 0, "gated": 8, "quiet": 4, "capped": 0, "opened": 0,
                 "signal": 8, "no_bars": 0, "scanned": 18, "trend_dark": 0,
                 "ungraded_skip": 6},
        "caps": {"max_positions": 2}})
    v = one(grimes)
    assert v.state == "REFUSING", v
    assert "gated=8" in v.why, v.why

    # 🧭 nav-cook — empty, 39 of 40 below its band.
    cook = row("nav-cook-lshadow", 0, 3, {
        "scan": {"held": 0, "slip": 0, "capped": 0, "opened": 0, "preipo": 0,
                 "in_band": 0, "scanned": 40, "below_band": 39,
                 "above_band": 0, "confirming": 0},
        "caps": {"max_positions": 4}})
    v = one(cook)
    assert v.state == "REFUSING", v
    assert "below_band=39" in v.why, v.why

    # NEGATIVE CONTROL — a healthy trading book is never STUCK.
    taker = row("lighter-ticket-taker-lshadow", 3, 261, {"max_open": 6})
    assert one(taker).state == "TRADING"
    carry = row("perps-funding-carry-lshadow", 18, 104, {
        "scan": {"cold": 193, "held": 18, "thin": 14, "scanned": 228,
                 "waiting": 3, "eligible": 0},
        "caps": {"max_positions": 16}})
    assert one(carry).state == "TRADING"

    # 👩 mum — no explicit supply field; her `verdicts` map accounts for the
    # whole universe, so supply is INFERRED zero rather than left unknown.
    mum = row("freqtrade-mum-lighter", 0, 0, {
        "max_open": 4,
        "scan": {"held": 0, "rsi_bar": 30.0, "rsi_med": 43.9, "near_bar": 2,
                 "rsi_read": 23, "universe": 23,
                 "verdicts": {"no_signal": 22, "uptrend_blocked": 1}}})
    v = one(mum)
    assert v.state == "REFUSING", v
    assert "inferred" in v.why, v.why

    # SUPPLY_EMPTY — scanned nothing, refused nothing.
    dry = row("nav-dry-lshadow", 0, 4, {
        "scan": {"held": 0, "scanned": 0, "eligible": 0},
        "caps": {"max_positions": 4}})
    assert one(dry).state == "SUPPLY_EMPTY"

    # 🎯 the sniper — real row: NO `scanned` key at all, but `not_young: 69`
    # proves it looked. A refusal bucket outranks a missing denominator, or the
    # finding inverts: "refused 69" would read as "nothing to refuse".
    sniper = row("lighter-perp-sniper-lshadow", 0, 36, {
        "scan": {"dupe": 0, "held": 0, "surge": 0, "young": 0, "capped": 0,
                 "opened": 0, "listing": 0, "offered": 0, "pending": 2,
                 "max_open": 4, "not_young": 69, "surge_cooldown": 3},
        "caps": {"max_open": 4, "surge_mult": 2.0}})
    v = one(sniper)
    assert v.state == "REFUSING", v
    assert "not_young=69" in v.why, v.why

    # a census with a scan and NO bucket at all is REFUSING, and says the
    # census is the thing that cannot answer
    thin = row("nav-thin-lshadow", 0, 1, {
        "scan": {"held": 0, "scanned": 30, "eligible": 0},
        "caps": {"max_positions": 4}})
    v = one(thin)
    assert v.state == "REFUSING" and "NO bucket names the refusal" in v.why, v

    # NO CENSUS — an empty book that publishes nothing readable.
    blind = row("pm-turnbull-lshadow", 0, 23, {"held": {}})
    v = one(blind)
    assert v.state == "UNKNOWN" and "NO census" in v.why, v

    # STUCK IS UNREACHABLE FROM ONE SAMPLE, by construction.
    stuck_row = row("nav-stuck-lshadow", 0, 0, {
        "scan": {"held": 0, "scanned": 40, "eligible": 3, "opened": 0},
        "caps": {"max_positions": 4}})
    v = one(stuck_row)
    assert v.state == "UNKNOWN", v
    assert "snapshot is not a structural verdict" in v.why, v.why

    # ...and reachable from MIN_STUCK_PUBLISHES DISTINCT publishes.
    obs = [observe(row("nav-stuck-lshadow", 0, 0, stuck_row["extra"],
                       updated=f"2026-08-27T1{i}:00:00+00:00"),
                   f"2026-08-27T1{i}:00:05+00:00")
           for i in range(MIN_STUCK_PUBLISHES)]
    v = classify(obs)
    assert v.state == "STUCK", v
    assert v.publishes == MIN_STUCK_PUBLISHES, v

    # A SENSOR CANNOT OUTRUN ITS OWN SAMPLING RATE: re-reading ONE publish
    # many times is one observation told many times, and must NOT reach STUCK.
    same = [observe(stuck_row, f"2026-08-27T12:00:0{i}+00:00")
            for i in range(MIN_STUCK_PUBLISHES + 3)]
    assert classify(same).state == "UNKNOWN", classify(same)

    # ORDER MATTERS: the LATEST sample decides, and one recovered loop clears
    # the defect assertion even with a long stuck history.
    healed = obs + [observe(
        row("nav-stuck-lshadow", 2, 0, stuck_row["extra"],
            updated="2026-08-27T19:00:00+00:00"),
        "2026-08-27T19:00:05+00:00")]
    assert classify(healed).state == "SLOW", classify(healed)

    # I1 — a STALE row is never read for semantics, however stuck-shaped.
    st = row("nav-stuck-lshadow", 0, 0, stuck_row["extra"], stale=True)
    assert one(st).state == "UNKNOWN"
    assert classify([observe(st, f"2026-08-27T1{i}:00:00+00:00")
                     for i in range(MIN_STUCK_PUBLISHES)]).state == "UNKNOWN"

    # a halted / standby row is a different question and says so
    assert one(row("x-lshadow", 0, 0, {"scan": {"scanned": 1, "eligible": 1}},
                   status="halted")).state == "UNKNOWN"

    # cap reading, from every shape the fleet publishes
    assert read_cap({"extra": {"caps": {"max_positions": 6}}})[0] == 6
    assert read_cap({"extra": {"max_open": 5}})[0] == 5
    assert read_cap({"extra": {"caps": {"max_open": 4}}})[0] == 4
    assert read_cap({"extra": {"census": {"free_slots": 2, "held": 4}}})[0] == 6
    assert read_cap({"extra": {}})[0] is None

    # telemetry is never mistaken for a candidate bucket
    c = read_census({"extra": {"scan": {
        "scanned": 40, "eligible": 2, "dev_med_bps": 10.9, "rsi_bar": 42.0,
        "next_eta_h": 4.58, "gate_apr": 0.05, "below_gate": 36}}})
    assert c.supply == 2 and set(c.explanations) == {"below_gate"}, c

    # the DOCKET cross-reference fires on a SLOW book it wants retired
    docket = [{"book": "book-hull-lshadow", "reason": "zero_ledger",
               "why": "no closes ever — undecidable until the book closes",
               "asks": "keep-or-retire (I17)", "since":
                   "2026-08-13T23:58:11+00:00", "days_held": 12.5},
              {"book": "book-douglas-lshadow", "reason": "unreachable",
               "why": "mean <= 0", "asks": "keep-or-retire (I17)",
               "since": "2026-08-18T05:03:19+00:00", "days_held": 7.3}]
    douglas = row("book-douglas-lshadow", 0, 60, {
        "scan": {"held": 0, "quiet": 18, "signal": 0, "scanned": 18},
        "caps": {"max_positions": 4}})
    doc = {"meta": {"generated_at": "2026-08-27T12:00:00+00:00",
                    "stale_threshold_sec": 180},
           "bots": [hull, kiyo, grimes, cook, taker, carry, mum, blind,
                    douglas]}
    bus = {"golive_readiness": {
        "updated": "2026-08-27T10:54:07+00:00",
        "decision_docket": docket,
        "below_floor": {"book-hull-lshadow": {
            "horizon": {"verdict": "no_rate", "why": "no closes ever"}}}}}
    verdicts, reads, nocen, meta = audit(
        [("2026-08-27T12:00:00+00:00", doc)], bus)
    hull_read = [r for r in reads if r["book"] == "book-hull-lshadow"][0]
    assert hull_read["misread"] is True, hull_read
    assert hull_read["state"] == "SLOW"
    doug_read = [r for r in reads if r["book"] == "book-douglas-lshadow"][0]
    assert doug_read["misread"] is False, doug_read
    assert "pm-turnbull-lshadow" in nocen and "book-hull-lshadow" not in nocen

    # the report renders, names the misread, and carries the snapshot caveat
    gv, _, _ = gate_view(bus)
    text = render(verdicts, reads, nocen, meta, gv)
    assert "MISREAD" in text and "book-hull-lshadow" in text
    assert "SNAPSHOT ONLY" in text
    assert "(Sydney)" in text or "UTC" in text

    # FAIL-CLOSED on a dark feed — a vacuous green would certify the very
    # thing this tool exists to catch.
    import tempfile
    for bad in ("[]", "{}", '{"bots": []}', '{"bots": [{"kind": "organ"}]}'):
        fh = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
        fh.write(bad)
        fh.close()
        try:
            book_rows(load(fh.name))
            raise AssertionError(f"dark feed {bad!r} must raise, not pass")
        except ValueError:
            pass
        finally:
            os.unlink(fh.name)

    print("audit_stuck_vs_slow --selftest: OK (SLOW/REFUSING/SUPPLY_EMPTY/"
          "TRADING/UNKNOWN on real publisher rows; STUCK unreachable from one "
          "snapshot and from re-reads of one publish; stale and halted rows "
          "refused; docket misread flagged; fail-closed feed)")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Classify every living book: TRADING / SLOW / REFUSING / "
                    "SUPPLY_EMPTY / STUCK / UNKNOWN.")
    ap.add_argument("--pnl-json", action="append", default=None,
                    help="URL or path; repeat for saved snapshots, OLDEST "
                         "FIRST. Default: the live feed.")
    ap.add_argument("--bus-json", default=None,
                    help="URL or path for the gate + decision docket. Default: "
                         "the live feed. Pass '' to skip.")
    ap.add_argument("--samples", type=int, default=1,
                    help=f"poll the live feed this many times "
                         f"(>={MIN_STUCK_PUBLISHES} to make STUCK reachable)")
    ap.add_argument("--interval", type=float, default=120.0,
                    help="seconds between --samples polls")
    ap.add_argument("--json", action="store_true", help="machine-readable")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args(argv)
    if a.selftest:
        return _selftest()

    samples = []
    try:
        feeds = a.pnl_json or [DEFAULT_PNL]
        if len(feeds) > 1:
            for f in feeds:
                samples.append((dt.datetime.now(dt.timezone.utc).isoformat(),
                                load(f)))
        else:
            for i in range(max(1, a.samples)):
                if i:
                    time.sleep(a.interval)
                samples.append((dt.datetime.now(dt.timezone.utc).isoformat(),
                                load(feeds[0])))
        bus_doc = None
        if a.bus_json != "":
            bus_doc = load(a.bus_json or DEFAULT_BUS, timeout=120)
        verdicts, reads, nocen, meta = audit(samples, bus_doc)
    except Exception as e:                                   # noqa: BLE001
        print(f"::error::audit_stuck_vs_slow: feed unusable ({e}). "
              f"FAIL-CLOSED — a dark feed is not a pass.")
        return 2

    if a.json:
        print(json.dumps({
            "meta": meta,
            "books": {b: {"state": v.state, "why": v.why,
                          "samples": v.samples, "publishes": v.publishes,
                          "evidence": v.evidence}
                      for b, v in verdicts.items()},
            "docket": reads, "no_census": nocen}, indent=2, default=str))
    else:
        gv, _, _ = gate_view(bus_doc)
        print(render(verdicts, reads, nocen, meta, gv))

    stuck = [v for v in verdicts.values() if v.asserts_defect]
    misread = [r for r in reads if r["misread"]]
    return 1 if (stuck or misread) else 0


if __name__ == "__main__":
    sys.exit(main())
