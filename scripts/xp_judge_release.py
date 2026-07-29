#!/usr/bin/env python3
"""Operator release of the experiment judge's RUNNING shadow candidate.

[2026-07-28 (dw) — born from the 28-Jul review, §8 D3(a).] The judge has
promote/fade/abandon transitions but NO operator-release path: when the
operator decides a running candidate's window is invalid (the live case: the
0.075 gate candidate became a 3-variable A/B once the shadow twin's
explore/conviction env levers went on mid-window), the only exits were waiting
out MAX_DAYS or raw DB surgery. This tool is the sanctioned middle: it
performs EXACTLY the judge's own ABANDON state transition (phase idle, name
into done/done_at, 48h cooldown, verdict appended, last_eval preserved) with
verdict "RELEASED-OPERATOR" and the operator's stated reason, through a
guarded transaction (row lock + still-running + name match, abort if the
judge moved). The xp levers are deliberately NOT touched: the idle judge
stops re-asserting them and they TTL-expire (~2h), reverting the twin to env
defaults — the same fail-safe lapse the judge itself relies on.

[2026-07-29 audit R1 — the race is CLOSED by a request channel.] The original
--execute wrote the judge's state directly under a row lock, but the judge's
own hourly read→compute→save holds no lock: a release committed while a
cycle was in flight was overwritten by the judge's stale save — the release,
verdict and cooldown vanished AFTER this tool printed RELEASED. Now:
DRY-RUN by default (prints the payload + preflight-refuses wrong phase/name);
--execute QUEUES a TTL'd request row the judge consumes at its next cycle
through its own save path (single-writer, race-free, ≤1h latency; outcome
tombstoned on the request key, phone push on release); --execute-direct
keeps the old direct write for the one case queuing cannot serve — a DEAD
judge container — with the race caveat printed. The transition itself lives
in experiment_judge.release_transition (single source; this tool and the
judge cannot drift apart). Judge stays the only writer of live.funding.* —
this releases a SHADOW candidate only and refuses phase == "promoted"
(releasing a promotion is fade/proposal territory).

Usage:
  python3 scripts/xp_judge_release.py --name <candidate> --why "<reason>"
  python3 scripts/xp_judge_release.py --name <candidate> --why "<reason>" --execute
  python3 scripts/xp_judge_release.py --name <candidate> --why "<reason>" --execute-direct
  python3 scripts/xp_judge_release.py --selftest
"""
import json
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

import experiment_judge as ej                      # noqa: E402  (KEY/TTL/COOLDOWN/iso — single source, no drift)


def release_payload(st, name, why, now):
    """[2026-07-29 audit R1] Thin wrapper over the SINGLE-SOURCE transition,
    which moved into experiment_judge.release_transition — the judge's
    request-consume path and this tool must produce byte-identical payloads,
    and two copies of a state transition is how mirrors drift. This wrapper
    only translates the pure function's ValueError refusals into the tool's
    operator-facing SystemExit messages."""
    try:
        return ej.release_transition(st, name, why, now)
    except ValueError as e:
        msg = str(e)
        if "phase" in msg:
            raise SystemExit(f"REFUSED: {msg} — nothing to release (a "
                             f"promoted lever releases via fade/proposal, "
                             f"not this tool)")
        raise SystemExit(f"REFUSED: {msg} — the judge moved; re-check")


def _selftest():
    now = 1_785_000_000.0
    st = {"phase": "running", "current": "cand-x", "spec": {"n": "cand-x"},
          "done": ["old"], "done_at": {"old": now - 9e5},
          "started_ts": now - 6 * 86400, "blind_cycles": 2,
          "verdicts": [{"name": "old", "verdict": "ABANDONED"}],
          "last_eval": {"promote": False, "why": "floors"}}
    p = release_payload(st, "cand-x", "test reason", now)
    assert p["phase"] == "idle" and p["current"] is None and p["candidate"] is None
    assert p["done"] == ["old", "cand-x"] and p["done_at"]["cand-x"] == now
    assert p["started_ts"] is None and p["spec"] == {}
    assert p["cooldown_until"] == now + ej.COOLDOWN_H * 3600
    assert p["verdicts"][-1]["verdict"] == "RELEASED-OPERATOR"
    assert p["verdicts"][-1]["why"] == "test reason"
    assert p["verdicts"][-1]["eval"] == {"promote": False, "why": "floors"}
    assert p["last_eval"] == {"promote": False, "why": "floors"}
    # [2026-07-28] the growth pair + drift flag survive a main-candidate
    # release (mutation check: dropping any pass-through turns this red)
    st2 = dict(st, growth={"promoted": True, "promoted_ts": now - 86400},
               last_growth={"kind": "reassert"}, drift_notified=True)
    p2 = release_payload(st2, "cand-x", "r", now)
    assert p2["growth"] == {"promoted": True, "promoted_ts": now - 86400}, p2
    assert p2["last_growth"] == {"kind": "reassert"} and p2["drift_notified"] is True
    assert p["blind_cycles"] == 2
    # verdict cap mirrors save()'s [-10:]
    st2 = dict(st, verdicts=[{"name": f"v{i}"} for i in range(12)])
    assert len(release_payload(st2, "cand-x", "r", now)["verdicts"]) == 10
    # refusal guards: wrong phase, wrong name (mutation check: dropping either
    # guard in release_payload turns these red)
    for bad in (dict(st, phase="promoted"), dict(st, phase="idle")):
        try:
            release_payload(bad, "cand-x", "r", now)
            raise AssertionError("must refuse non-running phase")
        except SystemExit:
            pass
    try:
        release_payload(st, "other-cand", "r", now)
        raise AssertionError("must refuse a name mismatch")
    except SystemExit:
        pass
    print("xp_judge_release selftest OK (transition mirrors ABANDON; refusals "
          "guard phase + name; verdict cap 10)")
    return 0


def main():
    if "--selftest" in sys.argv:
        sys.exit(_selftest())
    args = dict(zip(sys.argv[1::2], sys.argv[2::2]))
    name, why = args.get("--name"), args.get("--why")
    if not name or not why:
        raise SystemExit(__doc__)
    execute = "--execute" in sys.argv
    direct = "--execute-direct" in sys.argv
    url = (os.environ.get("DATABASE_PUBLIC_URL")
           or os.environ.get("DATABASE_URL"))
    if not url:
        raise SystemExit("set DATABASE_PUBLIC_URL (railway variables "
                         "--service Postgres --kv | grep DATABASE_PUBLIC_URL)")
    import psycopg2
    now = time.time()
    cn = psycopg2.connect(url)
    cn.autocommit = False
    cu = cn.cursor()
    cu.execute("SELECT state FROM bot_state WHERE bot=%s FOR UPDATE", (ej.KEY,))
    row = cu.fetchone()
    if not row:
        raise SystemExit(f"no bot_state row for {ej.KEY!r}")
    payload = release_payload(row[0], name, why, now)   # preflight: refuses
    if not (execute or direct):                          # wrong phase/name NOW
        cn.rollback()
        print(json.dumps(payload, indent=1))
        print(f"\nDRY-RUN — would release {name!r} (cooldown to "
              f"{ej.iso(payload['cooldown_until'])} UTC). Re-run with "
              f"--execute to QUEUE the request for the judge's next cycle "
              f"(race-free, ≤1h), or --execute-direct to write state "
              f"directly (only if the judge container is DOWN — a judge "
              f"cycle mid-write can overwrite a direct release).")
        return
    if direct:
        # [2026-07-29 audit R1] the old path, kept ONLY for a dead judge
        # container: the judge's own lockless read→compute→save can overwrite
        # this write if a cycle is in flight — that race is WHY --execute now
        # queues instead. If the judge is running, use --execute.
        cu.execute("UPDATE bot_state SET state=%s, updated_at=now() WHERE bot=%s",
                   (json.dumps(payload), ej.KEY))
        cu.execute("INSERT INTO bot_state_history (key, ts, payload) "
                   "VALUES (%s, now(), %s)", (ej.KEY, json.dumps(payload)))
        cn.commit()
        print(f"RELEASED {name!r} DIRECTLY: phase=idle, cooldown until "
              f"{ej.iso(payload['cooldown_until'])} UTC. CAVEAT: if a judge "
              f"cycle was in flight, its save can overwrite this — verify "
              f"xp-judge.phase reads idle in a minute (/bus.json).")
        return
    # --execute: QUEUE the request; the judge (sole writer of its own state)
    # consumes it at cycle start and performs the identical transition.
    req = {"updated": ej.iso(now), "ttl_sec": ej.RELEASE_REQ_TTL,
           "name": name, "why": why, "requested": ej.iso(now)}
    cu.execute(
        "INSERT INTO bot_state (bot, updated_at, state) VALUES (%s, now(), %s) "
        "ON CONFLICT (bot) DO UPDATE SET updated_at=now(), state=EXCLUDED.state",
        (ej.RELEASE_REQ_KEY, json.dumps(req)))
    cn.commit()
    print(f"QUEUED release request for {name!r} (ttl {ej.RELEASE_REQ_TTL}s). "
          f"The judge consumes it at its next hourly cycle and phones on "
          f"release; outcome lands on bot_state {ej.RELEASE_REQ_KEY!r} "
          f"(visible on /bus.json). If the judge is DOWN, use "
          f"--execute-direct instead.")


if __name__ == "__main__":
    main()
