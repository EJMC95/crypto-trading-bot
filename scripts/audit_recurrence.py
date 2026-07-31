#!/usr/bin/env python3
"""audit_recurrence.py — the SQUARE-ONE detector.

WHY (2026-07-31 (hz), operator): *"when we make progress on construction, we
don't forget it and go try and work on a random house the next day ... we are
fixing the same issues daily and it's just costing me money"* and *"we can't
refer back to a doctrine that was established at the beginning of our journey —
it needs to be constantly updated and engraved so that we are future proof"*.

WHAT (hy) MISSED. That entry made doctrine ENFORCEABLE — every invariant names
the artifact that enforces it, and a deleted guard reddens the build. It did
nothing about the failure this file exists for, because **the pathology is
invisible per-entry and only exists in aggregate**: every individual changelog
entry is a legitimate fix, and the sickness is that there are SIXTEEN of them
about one book.

MEASURED the day this shipped, over entries since 29-Jul:

    perps-funding-carry        16 entries   hx,hu,ht,hq,hp,ho,hn,hf,he,hd,hc,gr,gn,gl,gg,fk
    funding-carry              13 entries   hx,hu,ht,hs,hq,ho,hf,go,gn,gl,ga,fz,ee
    yield-harvester-shadow      8 entries   hx,hu,ht,ho,hf,go,gn,gl

Three days. One house, rebuilt sixteen times. THAT is the cost, and no
per-entry guard can see it.

THE LOOP THIS CLOSES, and it is what makes doctrine self-updating rather than
archaeological:

    recurrence is MEASURED  ->  a recurring subject must produce an INVARIANT
    (or a declared, reasoned acknowledgement)  ->  the invariant names an
    executable enforcement (hy)  ->  the class actually closes  ->  the subject
    stops recurring.

A doctrine written on day one and never revisited is exactly the artifact the
operator is objecting to. This guard is the input that forces the doctrine to
GROW in response to measured pain, instead of being a historical record of
lessons that keep needing to be re-learned.

FAIL, NOT WARN. Per this repo's own rule, a green build carrying a warning is
indistinguishable from a green build. A subject over threshold either earns an
invariant or is explicitly ACKNOWLEDGED with a reason and an owner — both are
cheap; neither is silence.

WHAT THIS CANNOT DO: it counts mentions, not causes. A subject can recur
because it is genuinely large (a migration), and that is what the
acknowledgement block is for. It measures "are we back here again", not "is
being back here wrong".

Usage:
  python3 scripts/audit_recurrence.py [--days N] [--max N] [--report]
  python3 scripts/audit_recurrence.py --selftest
"""
import argparse
import collections
import datetime as dt
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(_HERE)
DOC = os.path.join(ROOT, "CLAUDE.md")
LOG = os.path.join(ROOT, "CHANGELOG.md")

WINDOW_DAYS = int(os.environ.get("RECUR_WINDOW_DAYS", "7"))
#: More than this many entries about ONE subject inside the window means the
#: class is not closing. Five is deliberately generous: a real investigation
#: legitimately spans a few entries. Sixteen is not an investigation.
MAX_ENTRIES = int(os.environ.get("RECUR_MAX_ENTRIES", "5"))

ACK_BEGIN = "<!-- RECURRING:BEGIN -->"
ACK_END = "<!-- RECURRING:END -->"

RE_ENTRY = re.compile(r"^## (\d{4}-\d{2}-\d{2}) \((\w+)\)\s*[—-]\s*(.+?)\s*$", re.M)
#: Subjects worth tracking: dashboard row ids, Railway service names and the
#: organ keys. Deliberately a NAMED list rather than "any hyphenated token" —
#: an over-broad extractor produces noise, and a noisy guard gets ignored,
#: which is the failure mode this whole file is about.
SUBJECTS = (
    "perps-funding-carry", "perps-funding-spread", "perps-funding-lighter",
    "lighter-ticket-taker", "crypto-trend-daily", "equities-regime",
    "lighter-dislocation", "lighter-perp-sniper", "freqtrade-georgia",
    "funding-carry", "yield-harvester-shadow", "counterweight-shadow",
    "snap-back-shadow", "tide-rider-lighter", "family-lighter-shadow",
    "freqtrade-bots", "pnl-dashboard", "market-context",
    "learning-brain", "fleet-tuning", "fleet-immune", "golive-readiness",
    "brain-stake-mults", "scout-tuner", "evidence-board",
)
RE_ACK = re.compile(r"^\s*-\s*`([^`]+)`\s*[—-]\s*(.+?)\s*$", re.M)


def entries(text):
    """-> [{date, letter, title, body}] newest-first as the file is written."""
    ms = list(RE_ENTRY.finditer(text))
    out = []
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        out.append({"date": m.group(1), "letter": m.group(2),
                    "title": m.group(3), "body": text[m.start():end]})
    return out


def window(ents, days=None, today=None):
    """Entries within `days` of the NEWEST entry.

    Anchored on the newest entry rather than the wall clock on purpose: it
    makes the result deterministic and testable, and it means a quiet week
    cannot silently empty the window and turn the guard green.
    """
    days = WINDOW_DAYS if days is None else days
    if not ents:
        return []
    try:
        anchor = (dt.date.fromisoformat(today) if today
                  else max(dt.date.fromisoformat(e["date"]) for e in ents))
    except (TypeError, ValueError):
        return []
    lo = anchor - dt.timedelta(days=days)
    out = []
    for e in ents:
        try:
            d = dt.date.fromisoformat(e["date"])
        except (TypeError, ValueError):
            continue           # an unreadable date is skipped, never guessed
        if lo <= d <= anchor:
            out.append(e)
    return out


def tally(ents, subjects=SUBJECTS):
    """-> {subject: [letters]} counting each entry AT MOST ONCE per subject.

    OVERLAPPING NAMES ARE RESOLVED LONGEST-FIRST, and this is not a detail.
    `-` is a word boundary, so `\\bfunding-carry\\b` matches INSIDE
    `perps-funding-carry` — every mention of the dashboard ROW silently
    incremented the SERVICE too. The first run of this guard reported
    `funding-carry: 21` against `perps-funding-carry: 16` and most of that gap
    was the substring, not a real second subject. A recurrence detector whose
    headline number is inflated by its own extractor would have made exactly
    the kind of confident-but-wrong claim this file exists to stop. Caught by
    its own selftest fixture; see I3.

    A match fully contained inside a LONGER match's span is dropped, so a body
    that says only `perps-funding-carry` credits only that subject, while one
    that genuinely says `funding-carry` on its own still credits the service.
    """
    hits = collections.defaultdict(list)
    for e in ents:
        body = e["body"]
        spans = []
        for s in subjects:
            for m in re.finditer(r"\b" + re.escape(s) + r"\b", body):
                spans.append((m.start(), m.end(), s))
        kept = set()
        for st, en, s in spans:
            if any(st >= st2 and en <= en2 and (en2 - st2) > (en - st)
                   for st2, en2, _ in spans):
                continue                    # contained in a longer subject
            kept.add(s)
        for s in sorted(kept):
            hits[s].append(e["letter"])
    return dict(hits)


def acknowledged(doc_text):
    """-> {subject: reason} from the RECURRING block in CLAUDE.md."""
    i, j = doc_text.find(ACK_BEGIN), doc_text.find(ACK_END)
    if i < 0 or j < 0 or j < i:
        return {}
    return {k.strip(): v.strip()
            for k, v in RE_ACK.findall(doc_text[i + len(ACK_BEGIN):j])}


def covered_by_invariant(subject, doc_text):
    """True when some INVARIANT names this subject — the class has doctrine."""
    i, j = doc_text.find("<!-- INVARIANTS:BEGIN -->"), doc_text.find("<!-- INVARIANTS:END -->")
    if i < 0 or j < 0 or j < i:
        return False
    return re.search(r"\b" + re.escape(subject) + r"\b", doc_text[i:j]) is not None


MIN_REASON = 30


def audit(log_text, doc_text, days=None, max_entries=None, today=None):
    """-> (findings, tally) — findings name subjects that keep coming back."""
    max_entries = MAX_ENTRIES if max_entries is None else max_entries
    win = window(entries(log_text), days=days, today=today)
    hits = tally(win)
    acks = acknowledged(doc_text)
    bad = []
    for subj, letters in sorted(hits.items(), key=lambda kv: -len(kv[1])):
        if len(letters) <= max_entries:
            continue
        if covered_by_invariant(subj, doc_text):
            continue
        reason = acks.get(subj)
        if reason is None:
            bad.append(
                f"{subj}: {len(letters)} entries in {days or WINDOW_DAYS}d "
                f"({','.join(letters[:12])}) — the class is not closing. Add an "
                f"INVARIANT that closes it, or ACKNOWLEDGE it in the RECURRING "
                f"block with a reason and an owner.")
        elif len(reason) < MIN_REASON:
            bad.append(f"{subj}: acknowledged, but the reason is too thin to be "
                       f"a decision ({reason!r})")
    return bad, hits


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--days", type=int, default=None)
    ap.add_argument("--max", type=int, default=None, dest="max_entries")
    ap.add_argument("--report", action="store_true",
                    help="print the full tally and exit 0 (diagnosis, not a gate)")
    ap.add_argument("--selftest", action="store_true")
    a = ap.parse_args()
    if a.selftest:
        return _selftest()
    try:
        log_text = open(LOG, encoding="utf-8").read()
        doc_text = open(DOC, encoding="utf-8").read()
    except OSError as e:
        print(f"audit_recurrence: cannot read inputs ({e})")
        return 1
    bad, hits = audit(log_text, doc_text, a.days, a.max_entries)
    days = a.days or WINDOW_DAYS
    if a.report:
        print(f"subject recurrence over the last {days}d of entries:\n")
        for s, ls in sorted(hits.items(), key=lambda kv: -len(kv[1])):
            print(f"  {s:<26} {len(ls):>2}  {','.join(ls[:14])}")
        return 0
    if bad:
        print("SQUARE ONE — subjects the changelog keeps returning to:\n")
        for b in bad:
            print(f"  {b}\n")
        print("  Every one of these is a house being rebuilt. Close the class")
        print("  with an enforced INVARIANT, or say out loud why it stays open.")
        print(f"\naudit_recurrence: {len(bad)} unclosed recurring subject(s)")
        return 1
    over = sum(1 for ls in hits.values() if len(ls) > (a.max_entries or MAX_ENTRIES))
    print(f"audit_recurrence: {len(hits)} subject(s) in {days}d, "
          f"{over} over threshold, all covered by an invariant or acknowledged.")
    return 0


def _selftest():
    def mk(pairs):
        return "\n".join(f"## 2026-07-{d} ({l}) — t\nbody about {s}\n"
                         for d, l, s in pairs)

    # SIX entries on one subject inside the window, no doctrine -> FAIL
    log = mk([("31", "aa", "perps-funding-carry"), ("31", "ab", "perps-funding-carry"),
              ("30", "ac", "perps-funding-carry"), ("30", "ad", "perps-funding-carry"),
              ("29", "ae", "perps-funding-carry"), ("29", "af", "perps-funding-carry")])
    bad, hits = audit(log, "no doctrine here")
    assert bad and "perps-funding-carry" in bad[0], bad
    assert len(hits["perps-funding-carry"]) == 6, hits

    # AT the threshold is fine — a real investigation spans a few entries
    ok_log = mk([("31", "aa", "perps-funding-carry"), ("31", "ab", "perps-funding-carry"),
                 ("30", "ac", "perps-funding-carry"), ("30", "ad", "perps-funding-carry"),
                 ("29", "ae", "perps-funding-carry")])
    assert audit(ok_log, "")[0] == [], "5 entries must not trip a >5 threshold"

    # AN INVARIANT COVERING IT CLEARS IT — this is the loop closing
    doc_inv = ("<!-- INVARIANTS:BEGIN -->\n### I1 · X\nabout perps-funding-carry\n"
               "  ENFORCED BY: `x`\n<!-- INVARIANTS:END -->")
    assert audit(log, doc_inv)[0] == [], "an invariant naming the subject closes it"
    # ...but only if it is INSIDE the invariants block, not loose prose
    assert audit(log, "perps-funding-carry is mentioned in passing")[0], \
        "a mention outside the INVARIANTS block must not count as doctrine"

    # AN ACKNOWLEDGEMENT WITH A REAL REASON CLEARS IT
    ack = (f"{ACK_BEGIN}\n- `perps-funding-carry` — deliberately open: the "
           f"duplicate publisher is an operator action nobody in-repo can "
           f"perform\n{ACK_END}")
    assert audit(log, ack)[0] == [], "a reasoned acknowledgement is a decision"
    # ...a thin one does not
    thin = f"{ACK_BEGIN}\n- `perps-funding-carry` — wip\n{ACK_END}"
    b, _ = audit(log, thin)
    assert b and "too thin" in b[0], b

    # THE WINDOW BITES: the same six entries spread across months are not a
    # recurrence, they are a history.
    old = mk([("31", "aa", "perps-funding-carry")]) + "\n" + "\n".join(
        f"## 2026-0{m}-01 (z{m}) — t\nbody about perps-funding-carry\n"
        for m in range(1, 7))
    assert audit(old, "")[0] == [], "entries outside the window must not count"

    # one entry mentioning a subject TWICE counts once
    dbl = "## 2026-07-31 (aa) — t\nperps-funding-carry perps-funding-carry\n"
    assert len(tally(entries(dbl)).get("perps-funding-carry", [])) == 1

    # SUBSTRING SUBJECTS MUST NOT DOUBLE-COUNT. `-` is a word boundary, so a
    # naive \b match credits `funding-carry` for every `perps-funding-carry`.
    # This inflated the guard's own first headline number.
    only_row = "## 2026-07-31 (aa) — t\nall about perps-funding-carry here\n"
    t1 = tally(entries(only_row))
    assert t1.get("perps-funding-carry") == ["aa"], t1
    assert "funding-carry" not in t1, \
        "the ROW mention must not silently credit the SERVICE too"
    # ...but a genuine standalone mention of the shorter name still counts
    both = ("## 2026-07-31 (aa) — t\nthe funding-carry service and the "
            "perps-funding-carry row\n")
    t2 = tally(entries(both))
    assert t2.get("funding-carry") == ["aa"] and \
        t2.get("perps-funding-carry") == ["aa"], t2

    # unreadable dates are skipped, never guessed
    assert window(entries("## not-a-date (aa) — t\nbody\n")) == []
    assert audit("", "")[0] == [] and entries("") == []

    # THE THRESHOLD IS LOAD-BEARING AND MUST NOT BE TUNED INTO SILENCE.
    # A mutation run raised MAX_ENTRIES to 999 and the guard went green — the
    # easiest way to "fix" a recurrence finding is to stop measuring it, which
    # is the square-one routine wearing a config change. Pinned to a range
    # that can still catch the incident this file was built from (16 entries).
    assert 2 <= MAX_ENTRIES <= 8, \
        f"MAX_ENTRIES={MAX_ENTRIES} cannot catch a real recurrence; raising " \
        f"the bar is not closing the class"
    assert 3 <= WINDOW_DAYS <= 30, f"WINDOW_DAYS={WINDOW_DAYS} out of range"

    # ...and the REAL changelog must be clean, or this guard is decorative
    real_log = open(LOG, encoding="utf-8").read()
    real_doc = open(DOC, encoding="utf-8").read()
    rbad, rhits = audit(real_log, real_doc)
    assert not rbad, "the live changelog has unclosed recurrence:\n" + "\n".join(rbad)
    assert rhits, "the extractor found NOTHING in a 288-entry changelog — check SUBJECTS"

    print(f"audit_recurrence selftest OK (over-threshold fails, at-threshold "
          f"passes, invariant closes, block-scoped, reasoned ack closes, thin "
          f"ack fails, window bites, dedup per entry; live log clean over "
          f"{len(rhits)} subjects)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
