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

DRY-RUN by default (prints the payload it would write); --execute writes
state + the fleet_regen history snapshot in one transaction. Judge stays the
only writer of live.funding.* — this tool touches a SHADOW candidate's state
only and refuses to run while phase == "promoted" (releasing a promotion is
fade/proposal territory, not this tool's).

Usage:
  python3 scripts/xp_judge_release.py --name <candidate> --why "<reason>"
  python3 scripts/xp_judge_release.py --name <candidate> --why "<reason>" --execute
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
    """The judge's ABANDON transition as a pure function of current state —
    mirrors experiment_judge.run_once's abandon `save(...)` field-for-field
    (phase idle, done+name, done_at stamp, 48h cooldown, started_ts cleared,
    verdicts appended + capped at 10, last_eval preserved). Pure — selftested."""
    if st.get("phase") != "running":
        raise SystemExit(f"REFUSED: judge phase is {st.get('phase')!r}, not "
                         f"'running' — nothing to release (a promoted lever "
                         f"releases via fade/proposal, not this tool)")
    if st.get("current") != name:
        raise SystemExit(f"REFUSED: running candidate is {st.get('current')!r}"
                         f", not {name!r} — the judge moved; re-check")
    done = list(st.get("done") or []) + [name]
    done_at = dict(st.get("done_at") or {})
    done_at[name] = now
    verdicts = list(st.get("verdicts") or []) + [{
        "name": name, "verdict": "RELEASED-OPERATOR", "ts": ej.iso(now),
        "eval": st.get("last_eval"), "why": why}]
    return {"updated": ej.iso(now), "ttl_sec": ej.TTL_SEC,
            "phase": "idle", "current": None, "spec": {}, "candidate": None,
            "done": done, "done_at": done_at,
            "started_ts": None, "promoted_ts": st.get("promoted_ts"),
            "cooldown_until": now + ej.COOLDOWN_H * 3600,
            "blind_cycles": st.get("blind_cycles") or 0,
            "skew_notified": bool(st.get("skew_notified")),
            "assert_fail_notified": bool(st.get("assert_fail_notified")),
            "promote_baseline": st.get("promote_baseline"),
            "verdicts": verdicts[-10:], "last_eval": st.get("last_eval")}


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
    payload = release_payload(row[0], name, why, now)
    if not execute:
        cn.rollback()
        print(json.dumps(payload, indent=1))
        print(f"\nDRY-RUN — would release {name!r} (cooldown to "
              f"{ej.iso(payload['cooldown_until'])} UTC). "
              f"Re-run with --execute to write.")
        return
    cu.execute("UPDATE bot_state SET state=%s, updated_at=now() WHERE bot=%s",
               (json.dumps(payload), ej.KEY))
    cu.execute("INSERT INTO bot_state_history (key, ts, payload) "
               "VALUES (%s, now(), %s)", (ej.KEY, json.dumps(payload)))
    cn.commit()
    print(f"RELEASED {name!r}: phase=idle, cooldown until "
          f"{ej.iso(payload['cooldown_until'])} UTC; the xp levers lapse on "
          f"their own TTL (~2h) and the twin reverts to env defaults. "
          f"State + regen history snapshot written.")


if __name__ == "__main__":
    main()
