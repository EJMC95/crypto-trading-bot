#!/usr/bin/env python3
"""
fleet_watchdog_svc.py — in-service fleet watchdog (the "C layer").

Runs as a guarded daemon thread inside the always-on pnl-dashboard service
(same opt-in pattern as report_emailer). Every WATCHDOG_INTERVAL_SEC (default
300s) it reads the dashboard's own /pnl.json via localhost and evaluates:

  problems  : feed unreachable · feed stale · any bot stale · any bot offline
  warnings  : fleet open positions > WATCHDOG_MAX_OPEN (default 20)
              any bot pnl_daily < WATCHDOG_DAILY_LOSS_ALERT (default -100)

Alerting is TRANSITION-based, to either or both channels:
  phone push  via ntfy.sh (set NTFY_TOPIC; user-requested 2026-07-15 — the
              operator's preferred channel; no account/credentials, the phone
              app subscribes to the same topic)
  email       via report_emailer.send_email (dormant until SMTP_* is set)
  ok -> problems        🚨 alert
  problem set changes   updated alert (min 30-min gap)
  problems -> ok        ✅ recovery

Current state is always served at /watchdog.json (no auth, no secrets) so the
external GitHub-Actions fleet-watchdog and humans can read it. Read-only
towards the fleet; never raises into the server.

2026-07-08 — added as the in-Railway layer alongside the GH-Actions watchdog.
"""
import json
import os
import threading
import time
import traceback
import urllib.request
import datetime as dt

_LOCK = threading.Lock()
_STATE = {"started": None, "checked_at": None, "problems": [], "warnings": [],
          "snapshot": "", "email_armed": False, "push_armed": False,
          "last_email_at": None, "last_email_kind": None, "error": None}

# [2026-07-15 PUSH] ntfy.sh phone push — auth-free pub/sub: unguessable topic
# is the only secret, the operator's phone app subscribes to the same topic.
NTFY_SERVER = os.environ.get("NTFY_SERVER", "https://ntfy.sh").rstrip("/")


def ntfy_topic():
    return os.environ.get("NTFY_TOPIC", "").strip()


def send_push(title, body, priority="urgent", tags="rotating_light"):
    """One push to the ntfy topic. Returns True on 2xx; never raises.
    HTTP headers are latin-1 in urllib, so the title is ASCII-sanitized and
    emoji ride in `tags` (ntfy renders shortcodes ahead of the title)."""
    topic = ntfy_topic()
    if not topic:
        return False
    try:
        req = urllib.request.Request(f"{NTFY_SERVER}/{topic}",
                                     data=body.encode("utf-8"), method="POST")
        req.add_header("Title", title.encode("ascii", "ignore").decode().strip())
        req.add_header("Priority", priority)
        req.add_header("Tags", tags)
        with urllib.request.urlopen(req, timeout=15) as r:
            return 200 <= r.status < 300
    except Exception as e:  # noqa: BLE001
        print(f"[fleet_watchdog] push failed: {type(e).__name__}: {e}", flush=True)
        return False


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def get_state():
    with _LOCK:
        return dict(_STATE)


def evaluate(data):
    """Pure function: pnl.json dict -> (problems, warnings, snapshot)."""
    meta = data.get("meta") or {}
    bots = data.get("bots") or []
    problems, warnings = [], []
    if meta.get("feed_stale"):
        problems.append(f"FEED STALE (freshest={meta.get('freshest_update_age_sec')}s)")
    if not bots:
        problems.append("NO BOTS in feed")
    stale = sorted(b.get("bot", "?") for b in bots if b.get("stale"))
    off = sorted(b.get("bot", "?") for b in bots if b.get("status") not in (None, "online"))
    if stale:
        problems.append("STALE: " + ", ".join(stale))
    if off:
        problems.append("NOT ONLINE: " + ", ".join(off))
    # [2026-07-14 APPLES-TO-APPLES FIX] The budget warning summed open_trades
    # over EVERYTHING — shadow twins (modelled copies of their originals),
    # delta-neutral funding books, stocks, the event sniper — and compared
    # that to the 20-position DIRECTIONAL budget, so it read 64-vs-20 on a
    # healthy day and warned forever, drowning real alerts. Warn on the
    # directional cohort only (paper + real-money live trading rows, same
    # cohort fleet_risk budgets); the raw everything-count stays in the
    # snapshot line for context.
    # [2026-07-15 AUDIT FIX] After the Kraken retirement the -lshadow books ARE
    # the fleet-risk cohort, so the blanket shadow exclusion left the budget
    # warning covering almost nothing. Mirror fleet_risk.authoritative_row:
    # one row per base, live > shadow (shadow only counts when no live twin).
    opens, dir_opens = 0, 0
    # [2026-07-15b VERIFIED FIX] perps-funding-lighter is DIRECTIONAL (one-
    # sided funding receiver) and counted by fleet_risk — only the truly
    # delta-neutral/market-neutral funding books stay excluded. live_bases
    # honors row freshness so a dead live publisher can't permanently
    # suppress its running shadow twin.
    non_directional = ("perps-funding-carry", "perps-funding-spread",
                       "equities-", "event-listing-sniper")
    live_bases = {(b.get("base_bot") or b.get("bot") or "") for b in bots
                  if b.get("kind") == "trading"
                  and b.get("venue_mode") == "lighter_live"
                  and not b.get("stale")}
    for b in bots:
        try:
            n = int(b.get("open_trades") or 0)
        except (TypeError, ValueError):
            continue
        opens += n
        if b.get("kind") != "trading":
            continue                      # scanners hold nothing real
        base = b.get("base_bot") or b.get("bot") or ""
        vm = b.get("venue_mode")
        if vm == "lighter_testnet":
            continue                      # faucet funds, never budgeted
        if vm == "lighter_shadow" and base in live_bases:
            continue                      # live twin supersedes; avoid double count
        if any(base == p or base.startswith(p) for p in non_directional):
            continue                      # delta-neutral / stocks / event-class
        dir_opens += n
    max_open = int(os.environ.get("WATCHDOG_MAX_OPEN", "20"))
    if dir_opens > max_open:
        warnings.append(f"directional positions {dir_opens} exceed the "
                        f"{max_open}-position budget ({opens} gross incl. shadows)")
    loss_floor = float(os.environ.get("WATCHDOG_DAILY_LOSS_ALERT", "-100"))
    big = [f"{b.get('bot')} ({b.get('pnl_daily'):+.1f})" for b in bots
           if isinstance(b.get("pnl_daily"), (int, float)) and b["pnl_daily"] < loss_floor]
    if big:
        warnings.append("daily P&L below " + str(loss_floor) + ": " + ", ".join(big))
    snapshot = f"bots={len(bots)} open_positions={opens} freshest={meta.get('freshest_update_age_sec')}s"
    return problems, warnings, snapshot


def run_loop(dash):
    """Daemon loop. `dash` is the pnl_dashboard module (for PORT)."""
    try:
        import report_emailer
    except Exception:
        report_emailer = None
    port = int(getattr(dash, "PORT", 8080))
    interval = int(os.environ.get("WATCHDOG_INTERVAL_SEC", "300"))
    min_gap = int(os.environ.get("WATCHDOG_EMAIL_MIN_GAP_SEC", "1800"))
    with _LOCK:
        _STATE["started"] = _now_iso()
    time.sleep(60)  # let the server come up before the first probe
    last_emailed = None      # None = never evaluated-for-email; () = known-good
    last_email_ts = 0.0
    while True:
        try:
            url = f"http://127.0.0.1:{port}/pnl.json?nc={int(time.time())}"
            try:
                with urllib.request.urlopen(url, timeout=20) as r:
                    data = json.load(r)
                problems, warnings, snapshot = evaluate(data)
            except Exception as fe:  # noqa: BLE001
                problems = [f"LOCAL FEED UNREACHABLE: {type(fe).__name__}: {fe}"]
                warnings, snapshot = [], "(no data)"
            # [2026-07-15 VITALS] ORGAN-DEATH detection — the 5-7 Jul scar:
            # the brain died silently for two days because the watchdog only
            # watched BOTS. Critical organs (scout/risk/brain/pulse/board)
            # going DARK (>3x their own ttl) are now problems -> phone push.
            # Guarded: vitals unreachable adds nothing (pnl.json staleness
            # already covers whole-feed death).
            try:
                vurl = f"http://127.0.0.1:{port}/vitals.json?nc={int(time.time())}"
                with urllib.request.urlopen(vurl, timeout=20) as r:
                    vd = json.load(r)
                for o in (vd.get("organs") or []):
                    if o.get("critical") and o.get("status") == "DARK":
                        age = o.get("age_min")
                        problems.append(
                            f"ORGAN DARK: {o.get('key')}"
                            + (f" (last publish {age:.0f}m ago)" if age is not None else " (never published)"))
            except Exception:  # noqa: BLE001
                pass
            email_armed = bool(report_emailer and report_emailer.smtp_configured())
            push_armed = bool(ntfy_topic())
            armed = email_armed or push_armed
            cur = tuple(problems)
            now = time.time()
            kind = None
            if cur:
                if last_emailed in (None, ()) or (cur != last_emailed and now - last_email_ts >= min_gap):
                    kind = "alert"
            else:
                if last_emailed not in (None, ()):
                    kind = "recovery"
            if kind and armed:
                subj = ("🚨 fleet-watchdog: " + problems[0][:70]) if kind == "alert" else \
                       "✅ fleet-watchdog: recovered — all bots fresh"
                body_lines = [f"Time: {_now_iso()}", f"Snapshot: {snapshot}", ""]
                if problems:
                    body_lines += ["Problems:"] + ["  - " + p for p in problems]
                if warnings:
                    body_lines += ["Warnings (non-fatal):"] + ["  - " + w for w in warnings]
                body_lines += ["", "State: /watchdog.json on the pnl-dashboard service.",
                               "This is a transition alert (max one per state change, 30-min gap)."]
                body = "\n".join(body_lines)
                # [2026-07-15 PUSH] phone first (operator's channel), email if
                # also configured. Either delivery marks the transition sent —
                # the 30-min gap applies to the state change, not per channel.
                sent = False
                if push_armed:
                    sent = send_push(
                        subj, body,
                        priority="urgent" if kind == "alert" else "default",
                        tags="rotating_light" if kind == "alert" else "white_check_mark",
                    ) or sent
                if email_armed:
                    sent = report_emailer.send_email(subj, body) or sent
                if sent:
                    last_email_ts = now
                    last_emailed = cur if kind == "alert" else ()
                    with _LOCK:
                        _STATE["last_email_at"] = _now_iso()
                        _STATE["last_email_kind"] = kind
            elif kind and not armed:
                # Neither channel configured — remember state anyway so
                # /watchdog.json and logs still show transitions without
                # spamming later.
                last_emailed = cur if kind == "alert" else ()
                print(f"[fleet_watchdog] {kind} (alerts dormant): {problems or 'ok'}", flush=True)
            elif not cur and last_emailed is None:
                last_emailed = ()
            with _LOCK:
                _STATE.update({"checked_at": _now_iso(), "problems": list(problems),
                               "warnings": list(warnings), "snapshot": snapshot,
                               "email_armed": email_armed, "push_armed": push_armed,
                               "error": None})
        except Exception:  # noqa: BLE001
            with _LOCK:
                _STATE["error"] = traceback.format_exc(limit=3)
            print("[fleet_watchdog] loop error:\n" + traceback.format_exc(), flush=True)
        time.sleep(interval)


if __name__ == "__main__":
    # --selftest for the push channel: fake urlopen, no network.
    import contextlib
    import io

    calls = []

    class _FakeResp:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def _fake_urlopen(req, timeout=None):
        calls.append({"url": req.full_url, "data": req.data,
                      "headers": dict(req.header_items())})
        return _FakeResp()

    _real = urllib.request.urlopen
    urllib.request.urlopen = _fake_urlopen
    try:
        os.environ["NTFY_TOPIC"] = "test-topic-abc"
        assert send_push("🚨 fleet-watchdog: STALE: mum", "body ünïcode ok", tags="rotating_light")
        c = calls[-1]
        assert c["url"].endswith("/test-topic-abc"), c["url"]
        assert c["headers"]["Title"] == "fleet-watchdog: STALE: mum", c["headers"]   # emoji stripped, ASCII kept
        assert c["headers"]["Priority"] == "urgent" and c["headers"]["Tags"] == "rotating_light"
        assert c["data"].decode("utf-8") == "body ünïcode ok"                        # UTF-8 rides in the body
        os.environ["NTFY_TOPIC"] = ""
        assert send_push("t", "b") is False and len(calls) == 1                      # unconfigured -> no post
        os.environ["NTFY_TOPIC"] = "test-topic-abc"

        def _boom(req, timeout=None):
            raise OSError("network down")
        urllib.request.urlopen = _boom
        with contextlib.redirect_stdout(io.StringIO()):
            assert send_push("t", "b") is False                                     # failure -> False, never raises
    finally:
        urllib.request.urlopen = _real
    print("fleet_watchdog_svc selftest OK (push channel)")
