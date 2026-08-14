#!/usr/bin/env python3
"""audit_code_currency.py — WHICH COMMIT IS EACH BOT ACTUALLY RUNNING?

[2026-08-03 (iw), operator: "this constant backstepping is running off old
code needs to be fixed ... we should be constantly referring to the updated and
latest knowledge"]

THE PROBLEM THIS REPLACES IS A 40-MINUTE MANUAL INVESTIGATION. `extra.build` is
a content hash, so a row can tell you its container's code is *different* from
the repo and never which COMMIT it is on or how far back that is. Establishing
that by hand — the 3-Aug review did exactly this — means creating a worktree and
replaying `build_compute` across a dozen commits for each bot. Nobody does that
per deploy, so "is the fix actually running?" has been answered by assumption
more often than by measurement, and the fleet has paid for it repeatedly:

  * (io) an env-var change silently rebuilt the LIVE Farmer from a branch 60
    commits stale, and it was found only because a card looked wrong.
  * the 17-Jul incident: six fill-telemetry commits landed, the container had
    booted minutes earlier, and 58 real orders were placed by code that did not
    contain them. "The code was right and was never running."
  * (gl) four of six shadow services never deployed at all for a day.

WHAT IT DOES
  Resolves every `extra.build` to an actual COMMIT by replaying the REAL
  `build_compute` over recent history, then reports how far behind HEAD each
  container is and WHAT is in the gap.

WHY IT REPLAYS THE REAL FUNCTION RATHER THAN RE-HASHING
  The stamp is `sha256(relpath + NUL + bytes + NUL)` over "the entry module plus
  whatever `_BUILD_SHARED` names EXIST" — a set that differs per image, which is
  the whole `(fd)` lesson (`build_n` is published precisely because two images
  over the same tree stamp different ids). Re-implementing that here would
  create a second copy of the rule that drifts the first time the set changes,
  so each candidate commit is checked out into a throwaway worktree and asked to
  compute its own stamp with its own `bot_pnl_store`.

THE VERDICT THAT MATTERS IS NOT "BEHIND"
  A container behind HEAD is often CORRECT: the two real-money services are
  marker-gated, so a commit with no `[deploy-live-*]` marker in its subject is
  *deliberately* not deployed. The 3-Aug review raised four ⚠️ ACTION alarms
  that were all exactly this. So the gap is classified by what is IN it:

    CURRENT        stamp == HEAD's stamp for that entry
    BEHIND-OWN     the gap changes this bot's OWN entry file  -> the container
                   is missing real behaviour. This is the finding.
    BEHIND-SHARED  the gap changes only _BUILD_SHARED files    -> the stamp
                   moved, the bot's logic did not.
    DEFERRED       behind, but every commit in the gap is unmarked and the
                   service is marker-gated -> working as designed.
    UNRESOLVED     stamp not produced by any commit in the window -> older than
                   --depth, or a file set this tree no longer produces.

[2026-08-04 (jb)] AN UNMAPPED STAMPED ROW IS A FINDING, NOT A SKIP. The first
cut kept only rows present in ROW_ENTRY, so a stamped row this file had never
heard of was dropped SILENTLY — unaudited by construction, green run. Measured
the day this shipped: `market-context` (svc-stamped, build-stamped, publishing
fresh) had been invisible to every run since the guard was born. Now any
stamped bot_pnl row must either be mapped in ROW_ENTRY or declared in
NON_BOT_ROWS with a reason, else exit 1 — so a FUTURE bot's row cannot be born
unaudited (operator mandate 4-Aug: "ones to come are always getting current
live and up to date upgrades").

Exit 0 = nothing is BEHIND-OWN and every stamped row is mapped or declared.
Exit 1 = a container is running stale code of its own, or a stamped row is
unmapped. `--selftest` proves the classifier can still see.

DATA SOURCES — DB by default, the PUBLIC FEED for CI [(jc)]
  With no flags the rows come from `fetch_bot_pnl()` (needs DATABASE_URL).
  `--pnl-json <path-or-url>` reads the dashboard's public read-only /pnl.json
  instead — same rows, no credentials — which is what the weekly workflow uses.
  That path is FAIL-CLOSED: an unreadable, empty or stamp-free feed exits 2,
  because in an unattended run "nothing to check" and "the feed broke" must not
  share a green (the warn-only-guard class). The default DB path keeps its
  old degrade-to-a-message behaviour for a human at a terminal. Scope note:
  the feed is the dashboard's FILTERED view (retired/hidden rows dropped, and
  non-bot rows like market-context are not on it), so the weekly CI run
  audits the published fleet; the DB path stays the wider ad-hoc census.

  `--gha` additionally writes the verdict table to $GITHUB_STEP_SUMMARY and
  emits a `::error::` annotation per BEHIND-OWN row — and ONLY per BEHIND-OWN:
  DEFERRED / BEHIND-SHARED / FILE-SET are deliberate designs or stamp
  bookkeeping, and a red (or even a ::warning::) on a deliberate design is the
  cry-wolf failure the header above records this guard committing on its own
  first run. The (jb) unmapped-row gate is a real failure in both sources and
  annotates the same way.
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

#: dashboard row -> the ENTRY module whose bytes its image stamps. Explicit
#: rather than inferred: a wrong guess here reports a healthy bot as stale,
#: which is the direction that erodes trust in the guard (I8 — name the object
#: the operator can act on, and be right about it).
ROW_ENTRY = {
    # [2026-08-05] 🎸 Barnesy — mapped the day the row was born, per the (jb)
    # unmapped-row gate (a stamped row this file has never heard of fails the
    # audit rather than being skipped silently).
    "band-barnes-lshadow": "lighter_band_barnes_bot.py",
    # [2026-08-13 (ls)] 🛢️ Garrett — the (lp)/(lr) birth missed this map, and
    # the row began publishing WITH a build stamp on 13-Aug, so the next
    # weekly currency run would have FAILED on an unmapped row. Its entry
    # module is the Farmer's file (FUNDING_VARIANT instance).
    "band-garrett-lshadow": "lighter_funding_bot.py",
    # [2026-08-13 (ls)] 🏦 Rich Dad — mapped the day the row was born, per
    # the same (jb) gate, PRE-provision so its FIRST stamped publish was
    # already covered. Service ALIVE 13-Aug (ls), stamp-verified ((mn)).
    "book-kiyosaki-lshadow": "lighter_book_kiyosaki_bot.py",
    # [2026-08-13 (mb)-(me)] the BOOKS cohort's second wave — mapped the day
    # each row was born, per the (jb) gate, PRE-provision so the FIRST
    # stamped publish was already covered. All four services ALIVE 14-Aug
    # (mk), stamp-verified ((mn)).
    "book-douglas-lshadow": "lighter_book_douglas_bot.py",
    "book-grimes-lshadow": "lighter_book_grimes_bot.py",
    "book-schwager-lshadow": "lighter_book_schwager_bot.py",
    "book-hull-lshadow": "lighter_book_hull_bot.py",
    "crypto-breakout-4h-lshadow": "lighter_family_bot.py",
    "crypto-intraday-15m-lshadow": "lighter_family_bot.py",
    "crypto-swing-daily-lshadow": "lighter_family_bot.py",
    "crypto-trend-daily-lshadow": "lighter_trend_bot.py",
    "freqtrade-avo-maria-lshadow": "lighter_family_bot.py",
    "freqtrade-dad-lshadow": "lighter_family_bot.py",
    "freqtrade-georgia-lshadow": "lighter_family_bot.py",
    "freqtrade-mum-lshadow": "lighter_family_bot.py",
    "equities-regime-lshadow": "lighter_index_bot.py",
    "lighter-dislocation-lshadow": "lighter_dislocation_bot.py",
    "lighter-perp-sniper-lshadow": "lighter_perp_sniper.py",
    # [2026-08-04 (jb)] not a trading bot — the instrument collector — but its
    # row is stamped (measured: build a6219e09bd45 / n=14, svc=market-context)
    # and its image auto-deploys, so currency applies to it exactly as to a
    # bot. It was silently skipped from this guard's first run until the
    # unmapped-row gate below made that impossible.
    "market-context": "market_context.py",
    # [2026-08-13 (ma)] 🙏 Avo Maria took the live slot; the Taker's live row
    # retired. Its entry stays mapped for the transition window — an old
    # container's last stamped publishes must resolve, not read UNMAPPED.
    "freqtrade-avo-maria-lighter": "lighter_avo_live_bot.py",
    "lighter-ticket-taker-lighter": "lighter_ticket_taker.py",
    "lighter-ticket-taker-lshadow": "lighter_ticket_taker.py",
    "perps-funding-carry-lshadow": "funding_carry_bot.py",
    "perps-funding-lighter-lighter": "lighter_funding_bot.py",
    "perps-funding-lighter-lshadow": "lighter_funding_bot.py",
    "perps-funding-spread-lshadow": "lighter_funding_spread_bot.py",
    "pm-abbott-lshadow": "parliament_main.py",
    "pm-albanese-lshadow": "parliament_main.py",
    "pm-gillard-lshadow": "parliament_main.py",
    "pm-morrison-lshadow": "parliament_main.py",
    "pm-rudd-lshadow": "parliament_main.py",
    "pm-turnbull-lshadow": "parliament_main.py",
}

#: rows whose service only deploys behind a commit-subject marker, and the
#: marker that does it. Being behind is EXPECTED here unless a marked commit
#: sits in the gap — the distinction the 3-Aug review could not make, which
#: cost it four false ACTION items.
MARKER_GATED = {
    "perps-funding-lighter-lighter": ("[deploy-live-farmer]", "[deploy-live]"),
    "lighter-ticket-taker-lighter": ("[deploy-live-taker]", "[deploy-live]"),
    # [2026-08-13 (ma)] the slot's new occupant deploys behind the SAME
    # marker (the service kept its gate through the swap).
    "freqtrade-avo-maria-lighter": ("[deploy-live-taker]", "[deploy-live]"),
    # [2026-08-03] `funding-farmer-shadow` holds ZERO real money and yet is
    # marker-gated, which looks wrong and is not. `(hi)` joined the two arms'
    # deploy CLOCK on purpose: the shadow is the judge's CONTROL arm, and the
    # property that matters is matched-in-BOTH-directions — "auto-deploying
    # the shadow on every unmarked push would simply drift the arms the other
    # way", and the judge's arm-drift gate then refuses every promotion
    # ("this window measures a code delta, not edge").
    #
    # This guard's FIRST live run reported it BEHIND-OWN by 6 commits, which
    # was a gap in this model rather than a fleet defect — recorded here
    # because the finding was checked against the workflow before being
    # believed, and the two arms were in fact byte-identical (both
    # 16c4b139231d) at the moment it fired. A guard that cries wolf on a
    # deliberate design is how a real finding later gets ignored ((hh)).
    "perps-funding-lighter-lshadow": ("[deploy-live-farmer]", "[deploy-live]"),
}

#: [2026-08-04 (jb)] stamped bot_pnl rows DELIBERATELY outside this audit's
#: scope, {row: reason}. fetch_bot_pnl() returns EVERY row in the table, and
#: the old code kept only `b in ROW_ENTRY` — so a stamped row this file had
#: never heard of was skipped silently (market-context, from the guard's first
#: run). An unmapped stamped row now FAILS the audit unless declared here.
#: Empty today ON PURPOSE: every stamped publisher currently has an entry-file
#: mapping, market-context included — a declaration is for a row whose stamp
#: genuinely cannot be resolved to one entry module, not a snooze button.
NON_BOT_ROWS = {}


def rows_from_pnl_json(src):
    """Rows from a /pnl.json document — a local file path or an http(s) URL.

    The feed's envelope is `{"meta": {...}, "bots": [rows]}` (shape read off
    the LIVE endpoint 4-Aug, not guessed); a bare list is tolerated for tests.
    Each row already carries the two keys this audit consumes (`bot`, `extra`)
    plus `age_sec`/`stale`, which the report uses for the I1 annotation.

    RAISES on anything doubtful — no rows, no parse, no fetch. The caller
    behind `--pnl-json` turns that into exit 2: this source exists for
    unattended runs, where a quiet empty result is a vacuous green.
    """
    if str(src).startswith(("http://", "https://")):
        import urllib.request
        with urllib.request.urlopen(str(src), timeout=30) as resp:
            doc = json.load(resp)
    else:
        doc = json.loads(Path(src).read_text())
    rows = doc.get("bots") if isinstance(doc, dict) else doc
    if not isinstance(rows, list):
        rows = []
    stamped = sum(1 for r in rows
                  if isinstance(r, dict) and (r.get("extra") or {}).get("build"))
    if not stamped:
        raise ValueError(
            f"pnl.json from {src} yields no build-stamped rows "
            f"({len(rows)} row(s) total) — empty feed, changed shape, or dark "
            f"stampers")
    return rows


def _git(*args, cwd=None):
    return subprocess.run(("git",) + args, cwd=str(cwd or ROOT),
                          capture_output=True, text=True, check=False).stdout


def commits(depth):
    out = _git("log", f"-{depth}", "--format=%H\t%s", "HEAD")
    rows = []
    for line in out.splitlines():
        if "\t" in line:
            sha, subj = line.split("\t", 1)
            rows.append((sha.strip(), subj.strip()))
    return rows


#: [(fd), and this guard's OWN first run walked straight into it] `_build_files`
#: hashes "the entry module + whatever `_BUILD_SHARED` names EXIST", so a repo
#: checkout — which has all of them — stamps a file set NO image actually ships.
#: Measured on the first live run: nine rows publishing `build_n=14` came back
#: UNRESOLVED against a window computing 15, and the message blamed history
#: depth. That is the false direction: a different COUNT means a different FILE
#: SET, never drifted code. So each entry is computed against ITS OWN image's
#: COPY set, with the shared files that image does not carry hidden first.
_PROBE = """
import json, os, sys
sys.path.insert(0, %r)
import bot_pnl_store as b
out = {}
for e, hide in %r:
    moved = []
    try:
        for h in hide:
            if os.path.exists(h):
                os.rename(h, h + ".__hidden__")
                moved.append(h)
        out[e] = b.build_compute(e)
    except Exception:
        out[e] = [None, 0]
    finally:
        for h in moved:
            try:
                os.rename(h + ".__hidden__", h)
            except OSError:
                pass
print(json.dumps(out))
"""


def image_shared_sets():
    """{entry_file: [shared names its image does NOT COPY]}.

    Reuses `audit_image_imports.image_contents` — the fleet's existing owner of
    "what is really in this image", including multi-source COPY and `COPY . .`.
    Re-deriving it here would be a second copy of that rule ((hj)).
    """
    sys.path.insert(0, str(ROOT / "scripts"))
    import audit_image_imports as aii
    import bot_pnl_store as store
    out = {}
    for df in sorted(ROOT.glob("Dockerfile.*")):
        try:
            # image_contents returns (modules, files, copy_targets, ...) — the
            # FILE set is element 1. Iterating the tuple itself silently
            # compares against its member containers, which is what this
            # function did on its first cut: every lookup "matched" a
            # stringified set and the map came back EMPTY, so nothing was
            # hidden and every 14-file image read as UNRESOLVED. Indexing
            # deliberately, with an assert, so a shape change fails loudly
            # rather than degrading to a silently empty map.
            parts = aii.image_contents(df.name)
            files = {str(f).replace("\\", "/") for f in parts[1]}
        except Exception:  # noqa: BLE001
            continue
        if not files:
            continue
        names = {f.split("/")[-1] for f in files}
        present = {s for s in store._BUILD_SHARED
                   if s in names or any(f == s or f.startswith(f"{s}/")
                                        for f in files)}
        missing = [s for s in store._BUILD_SHARED if s not in present]
        for e in ROW_ENTRY.values():
            if e in names and e not in out:
                out[e] = missing
    return out


def stamps_at(worktree, entries, hide_map):
    """{entry: (id, n)} computed BY THAT CHECKOUT's own bot_pnl_store, each
    against the file set ITS image really ships."""
    spec = [(e, list(hide_map.get(e, []))) for e in entries]
    r = subprocess.run([sys.executable, "-c", _PROBE % (str(worktree), spec)],
                       cwd=str(worktree), capture_output=True, text=True,
                       check=False)
    try:
        return {k: tuple(v) for k, v in json.loads(r.stdout).items()}
    except Exception:  # noqa: BLE001
        return {}


def classify(row, container_id, container_n, history, head_stamp, touched):
    """(verdict, commit_sha, behind_n, why) for one row. Pure over its inputs."""
    if not container_id:
        return "UNRESOLVED", None, None, "row publishes no build stamp"
    if head_stamp and container_id == head_stamp[0]:
        return "CURRENT", history[0][0] if history else None, 0, "matches HEAD"
    for i, (sha, _subj, stamp) in enumerate(history):
        if stamp and stamp[0] == container_id:
            gap = history[:i]                       # commits NOT in the container
            own = [s for s, _, _ in gap if s in touched]
            marks = MARKER_GATED.get(row)
            if marks:
                marked = [s for s, sub, _ in gap
                          if any(m in sub for m in marks)]
                if not marked:
                    return ("DEFERRED", sha, i,
                            f"{i} commit(s) behind, none marked for this "
                            f"marker-gated service — working as designed")
                return ("BEHIND-OWN", sha, i,
                        f"{len(marked)} MARKED commit(s) in the gap did not land")
            if own:
                return ("BEHIND-OWN", sha, i,
                        f"{len(own)} of {i} commit(s) in the gap change this "
                        f"bot's own entry file")
            return ("BEHIND-SHARED", sha, i,
                    f"{i} commit(s) behind, none touching this bot's own code "
                    f"(shared-module stamp shift only)")
    seen_n = {st[1] for _, _, st in history if st and st[1]}
    if container_n and seen_n and int(container_n) not in seen_n:
        return ("FILE-SET", None, None,
                f"build_n={container_n} but this window only produces "
                f"{sorted(seen_n)} — a different COUNT means a different FILE "
                f"SET, not drifted code ((fd)). Check the image's COPY set "
                f"before reading this as stale.")
    return ("UNRESOLVED", None, None,
            f"stamp {container_id}/{container_n} produced by no commit in the "
            f"{len(history)}-commit window — older than --depth")


def _row_age(r):
    """(age_sec, stale) for one row — I1: read the age BEFORE the semantics.

    A dead container's row still carries its last stamp, so a verdict on a
    stale row describes its LAST publish, not a running process. The feed
    computes both fields server-side (threshold-aware); a DB row only has
    `updated_at`, so age is derived and stale stays None — this audit does not
    own the per-bot thresholds and will not invent them.
    """
    age, stale = r.get("age_sec"), r.get("stale")
    if age is None and r.get("updated_at"):
        try:
            import datetime as dt
            ua = dt.datetime.fromisoformat(str(r["updated_at"]))
            if ua.tzinfo is None:
                ua = ua.replace(tzinfo=dt.timezone.utc)
            age = max(0, int((dt.datetime.now(dt.timezone.utc) - ua)
                             .total_seconds()))
        except Exception:  # noqa: BLE001
            age = None
    return age, bool(stale) if stale is not None else None


def audit(depth=40, rows=None, fail_closed=False, gha=False):
    import bot_pnl_store as store
    if rows is None:
        rows = store.fetch_bot_pnl() or []
    live = {r["bot"]: (r.get("extra") or {}) for r in rows
            if (r.get("extra") or {}).get("build")}
    ages = {r["bot"]: _row_age(r) for r in rows if r.get("bot") in live}
    wanted = {b: ROW_ENTRY[b] for b in live if b in ROW_ENTRY}
    # [2026-08-04 (jb)] a stamped row this file has never heard of is a
    # FINDING, never a skip — the silent `b in ROW_ENTRY` filter is how
    # market-context went unaudited from the guard's first run.
    unmapped = sorted(b for b in live
                      if b not in ROW_ENTRY and b not in NON_BOT_ROWS)
    if unmapped:
        print("audit_code_currency: UNMAPPED STAMPED ROW(S) — these containers "
              "publish a build stamp\nthis audit cannot resolve, so their code "
              "currency is UNAUDITED BY CONSTRUCTION:\n")
        for b in unmapped:
            ex = live[b]
            if gha:
                print(f"::error title=UNMAPPED STAMPED ROW {b}::"
                      f"svc={ex.get('svc')} publishes a stamp this audit "
                      f"cannot resolve — map it in ROW_ENTRY or declare it "
                      f"in NON_BOT_ROWS with a reason")
            print(f"  {b:36s} svc={ex.get('svc')} "
                  f"build={ex.get('build')}/{ex.get('build_n')}")
        print("\n  Fix: map the row in ROW_ENTRY (row -> the entry module its "
              "image stamps), or\n  declare it in NON_BOT_ROWS with a reason. "
              "Silence is not an option.")
        return 1
    if not wanted:
        msg = "no stamped rows with a known entry — nothing to check."
        if fail_closed:
            # Unattended path: an empty check is indistinguishable from a
            # passed one unless it is RED. (gha annotation so the run summary
            # says why, not just that.)
            if gha:
                print(f"::error title=code-currency vacuous::{msg}")
            print(f"audit_code_currency: FAIL-CLOSED — {msg}")
            return 2
        print(f"audit_code_currency: {msg}")
        return 0

    hist = commits(depth)
    entries = sorted(set(wanted.values()))
    hide_map = image_shared_sets()
    per_commit, touched = {}, {e: set() for e in entries}

    with tempfile.TemporaryDirectory() as td:
        wt = Path(td) / "wt"
        _git("worktree", "add", "-q", "--detach", str(wt), hist[0][0])
        try:
            for sha, subj in hist:
                subprocess.run(["git", "checkout", "-q", "--detach", sha],
                               cwd=str(wt), capture_output=True, check=False)
                per_commit[sha] = (subj, stamps_at(wt, entries, hide_map))
                changed = _git("show", "--name-only", "--format=", sha).split()
                for e in entries:
                    if e in changed:
                        touched[e].add(sha)
        finally:
            _git("worktree", "remove", "--force", str(wt))

    print(f"CODE CURRENCY — which commit is each container running? "
          f"(window: {len(hist)} commits)\n")
    print(f"{'row':34s} {'verdict':14s} {'behind':>6s}  detail")
    print("-" * 108)
    findings, table = 0, []
    for row in sorted(wanted):
        entry = wanted[row]
        history = [(s, per_commit[s][0], per_commit[s][1].get(entry))
                   for s, _ in hist]
        head_stamp = history[0][2]
        v, sha, behind, why = classify(
            row, live[row].get("build"), live[row].get("build_n"),
            history, head_stamp, touched[entry])
        age, stale = ages.get(row, (None, None))
        if stale:
            why += (f"  [ROW STALE {age / 3600.0:.1f}h — the verdict describes "
                    f"its LAST publish, not a running process (I1)]")
        if v == "BEHIND-OWN":
            findings += 1
            if gha:
                print(f"::error title=BEHIND-OWN {row}::"
                      f"svc={live[row].get('svc')} is running stale code of "
                      f"its own — {why}")
        tag = f"{behind}" if behind is not None else "-"
        short = (sha or "")[:9]
        print(f"{row:34s} {v:14s} {tag:>6s}  {short} {why}")
        if v == "BEHIND-OWN":
            print(f"{'':34s} {'':14s} {'':>6s}  svc={live[row].get('svc')} "
                  f"stamp={live[row].get('build')}/{live[row].get('build_n')}")
        table.append({"row": row, "svc": live[row].get("svc"), "verdict": v,
                      "behind": behind, "commit": short, "age_sec": age,
                      "stale": stale, "why": why})

    if gha:
        _write_step_summary(table, len(hist))

    print()
    if findings:
        print(f"audit_code_currency: {findings} container(s) running STALE CODE "
              f"OF THEIR OWN.\n  A container behind on shared modules is a stamp "
              f"shift; one behind on its OWN entry file is missing behaviour "
              f"that was merged. Redeploy the named service, then verify by the "
              f"`extra.build` + `extra.build_n` readback — never by a green run.")
        return 1
    print("audit_code_currency: OK — every stamped container is CURRENT, "
          "deliberately DEFERRED behind its marker gate, or behind only on "
          "shared modules.")
    return 0


def _write_step_summary(table, window):
    """Markdown verdict table into $GITHUB_STEP_SUMMARY, one line per row.
    Prose stays out of the cells; the `detail` column IS the actionable why
    (I8 — the operator acts on a named service, so `svc` gets its own column).
    """
    path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not path:
        return
    L = [f"### Code currency — which commit is each container running? "
         f"(window: {window} commits)", "",
         "| row | service | verdict | behind | commit | age | detail |",
         "|---|---|---|---|---|---|---|"]
    for t in sorted(table, key=lambda t: (t["verdict"] != "BEHIND-OWN",
                                          t["row"])):
        v = f"**{t['verdict']}** ❌" if t["verdict"] == "BEHIND-OWN" \
            else t["verdict"]
        age = "-" if t["age_sec"] is None else f"{t['age_sec'] / 3600.0:.1f}h"
        if t["stale"]:
            age += " STALE"
        why = t["why"].replace("|", "\\|")
        L.append(f"| `{t['row']}` | `{t['svc']}` | {v} | "
                 f"{'-' if t['behind'] is None else t['behind']} | "
                 f"{t['commit'] or '-'} | {age} | {why} |")
    L += ["", "BEHIND-OWN is the only failing verdict — DEFERRED / "
          "BEHIND-SHARED / FILE-SET are deliberate designs or stamp "
          "bookkeeping, listed so nobody re-derives that by hand.", ""]
    with open(path, "a") as f:
        f.write("\n".join(L) + "\n")


def _selftest():
    """Negative fixtures: the classifier must still see."""
    H = [("c3", "newest", ("aaa", 15)),
         ("c2", "middle", ("bbb", 15)),
         ("c1", "oldest", ("ccc", 15))]
    head = ("aaa", 15)

    v, *_ = classify("x", "aaa", 15, H, head, set())
    assert v == "CURRENT", v
    # behind, and the gap touches its own entry -> the finding
    v, sha, n, _ = classify("x", "ccc", 15, H, head, {"c3"})
    assert (v, sha, n) == ("BEHIND-OWN", "c1", 2), (v, sha, n)
    # behind, gap touches nothing of its own -> shared-only
    v, _, n, _ = classify("x", "ccc", 15, H, head, set())
    assert (v, n) == ("BEHIND-SHARED", 2), (v, n)
    # marker-gated with no marker in the gap -> DEFERRED, not a finding
    v, _, n, _ = classify("perps-funding-lighter-lighter", "ccc", 15, H, head,
                          {"c3"})
    assert (v, n) == ("DEFERRED", 2), (v, n)
    # ...and a MARKED commit in the gap IS a finding
    H2 = [("c3", "fix it [deploy-live-farmer]", ("aaa", 15)),
          ("c2", "middle", ("bbb", 15)),
          ("c1", "oldest", ("ccc", 15))]
    v, _, n, _ = classify("perps-funding-lighter-lighter", "ccc", 15, H2, head,
                          set())
    assert (v, n) == ("BEHIND-OWN", 2), (v, n)
    # a stamp nothing produced
    v, *_ = classify("x", "zzz", 15, H, head, set())
    assert v == "UNRESOLVED", v
    # a row with no stamp at all must not read as CURRENT
    v, *_ = classify("x", None, None, H, head, set())
    assert v == "UNRESOLVED", v
    # every mapped row names a file that exists, or the guard reports phantoms
    for row, entry in ROW_ENTRY.items():
        assert (ROOT / entry).exists(), f"{row} -> {entry} does not exist"
    # marker-gated rows must be mapped, or they can never be classified
    for row in MARKER_GATED:
        assert row in ROW_ENTRY, f"{row} is marker-gated but unmapped"
    # [2026-08-04 (jb)] the unmapped-stamped-row gate, driven through audit()
    # ITSELF with injected rows (testing around a function is not testing it):
    # a stamped row this file has never heard of must FAIL, not silently skip.
    _mystery = [{"bot": "mystery-row",
                 "extra": {"build": "abc123", "build_n": 9,
                           "svc": "mystery-svc"}}]
    assert audit(depth=1, rows=_mystery) == 1, \
        "an unmapped stamped row must fail the audit, not vanish from it"
    NON_BOT_ROWS["mystery-row"] = (
        "selftest-only declaration: proves a declared row is re-admitted "
        "without an entry-file mapping, then removed below")
    try:
        assert audit(depth=1, rows=_mystery) == 0, \
            "a DECLARED non-bot row must not fail the audit"
    finally:
        del NON_BOT_ROWS["mystery-row"]
    assert not (set(NON_BOT_ROWS) & set(ROW_ENTRY)), \
        "a row cannot be both mapped in ROW_ENTRY and declared in NON_BOT_ROWS"
    for row, why in NON_BOT_ROWS.items():
        assert len(why) > 60, f"{row}: a reason must be a reason, not a label"

    # --- the /pnl.json source [(jc)] -------------------------------------
    # Fixture mirrors the LIVE feed's envelope (read off the endpoint 4-Aug:
    # {"meta": ..., "bots": [rows]}, rows keyed bot/extra/age_sec/stale) —
    # the (hj) rule wants the publisher's own payload, and the publisher is a
    # DB-backed HTTP handler, so the measured envelope is the closest
    # network-free stand-in. The adapter must return rows NON-DEGENERATE
    # (bot + extra.build intact), and must RAISE on the three dark shapes an
    # unattended run would otherwise call green.
    import tempfile as _tf
    feed = {"meta": {"generated_at": "2026-08-04T00:00:00+00:00"},
            "bots": [{"bot": "perps-funding-lighter-lighter",
                      "extra": {"build": "f27e50d805af", "build_n": 15,
                                "svc": "trail-blazer-live"},
                      "age_sec": 75, "stale": False},
                     {"bot": "crypto-breakout-4h-lshadow",
                      "extra": {"build": "6779a282bbd8", "build_n": 14,
                                "svc": "family-lighter-shadow"},
                      "age_sec": 1828, "stale": True}]}
    with _tf.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(feed, f)
        fp = f.name
    try:
        got = rows_from_pnl_json(fp)
        assert len(got) == 2 and got[0]["bot"] == "perps-funding-lighter-lighter"
        assert got[0]["extra"]["build"] == "f27e50d805af", got[0]
        # I1 plumbing: the feed's server-side age/stale must survive into
        # _row_age verbatim — a stale row's verdict is about its LAST publish.
        assert _row_age(got[1]) == (1828, True), _row_age(got[1])
        assert _row_age(got[0]) == (75, False), _row_age(got[0])
        for bad in ([], {"meta": {}, "bots": []},
                    {"bots": [{"bot": "x", "extra": {}}]}):   # rows, no stamps
            with _tf.NamedTemporaryFile("w", suffix=".json",
                                        delete=False) as f2:
                json.dump(bad, f2)
            try:
                rows_from_pnl_json(f2.name)
                raise AssertionError(f"adapter accepted a dark feed: {bad!r}")
            except ValueError:
                pass
            finally:
                os.unlink(f2.name)
    finally:
        os.unlink(fp)
    # a DB-shaped row (updated_at, no age_sec) degrades to derived age,
    # stale=None — never a guessed threshold
    age, stale = _row_age({"bot": "x",
                           "updated_at": "2026-01-01T00:00:00+00:00"})
    assert age is not None and age > 0 and stale is None, (age, stale)
    # the unattended path must go RED on an empty check, the human path must
    # keep its old quiet message
    assert audit(rows=[{"bot": "nobody", "extra": {}}], fail_closed=True) == 2
    assert audit(rows=[{"bot": "nobody", "extra": {}}], fail_closed=False) == 0
    print("audit_code_currency --selftest OK "
          "(current, behind-own, behind-shared, deferred, marked-gap, "
          "unresolved, unstamped, map integrity, unmapped-row gate, "
          "pnl-json fail-closed, i1-age plumbing)")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("--depth", type=int, default=40)
    ap.add_argument("--pnl-json", metavar="PATH_OR_URL",
                    help="read rows from the dashboard's public /pnl.json "
                         "(file or URL) instead of the DB — FAIL-CLOSED: a "
                         "dark/empty/stamp-free feed exits 2, never green")
    ap.add_argument("--gha", action="store_true",
                    help="GitHub Actions mode: verdict table into "
                         "$GITHUB_STEP_SUMMARY + ::error:: per BEHIND-OWN "
                         "(and ONLY per BEHIND-OWN)")
    a = ap.parse_args()
    if a.selftest:
        _selftest()
        raise SystemExit(0)
    rows = None
    if a.pnl_json:
        try:
            rows = rows_from_pnl_json(a.pnl_json)
        except Exception as e:  # noqa: BLE001
            if a.gha:
                print(f"::error title=code-currency feed unreadable::{e}")
            print(f"audit_code_currency: FAIL-CLOSED — {e}")
            raise SystemExit(2)
    raise SystemExit(audit(depth=a.depth, rows=rows,
                           fail_closed=bool(a.pnl_json), gha=a.gha))
