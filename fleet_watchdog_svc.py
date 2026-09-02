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
import re
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


# [2026-08-05 CI-LIVENESS dead-man's switch — the OFF-ACTIONS half.]
# A GitHub billing lockout kills EVERY workflow silently (28-Jul, measured:
# 3-16s not-started "failures", no email, CI AND deploys dead) — including the
# Actions-hosted fleet-watchdog itself, so no Actions-side check can ever
# detect it (I13: a dead loop runs no handler; liveness is only visible from
# OUTSIDE). fleet-watchdog.yml now writes bot_state 'actions-heartbeat'
# {updated, ttl_sec, run_id} on its hourly cron REGARDLESS of pushes, and THIS
# service — on Railway, unaffected by a lockout — pages when the beat goes
# silent. Quiet no-push days cannot false-page: the cron never depended on
# pushes. The key is also in ORGAN_SPECS as critical (the I13 "joins the
# pageable set deliberately" half), so the vitals card shows it; this direct
# DB read is the pager's own path and must not depend on the vitals surface
# it backstops.
ACTIONS_HB_KEY = "actions-heartbeat"
# [2026-09-02] THE PAGE BAR IS SET FROM THE MEASURED DELIVERY DISTRIBUTION,
# NOT FROM THE NOMINAL CRON — and the beat no longer rides the cron alone.
# The old single bar ("3 missed hourly beats + jitter" = 11700s) assumed
# GitHub delivers `schedule` events roughly hourly. Measured over 198
# consecutive scheduled deliveries (18-Aug -> 2-Sep,
# `gh run list --workflow=fleet-watchdog.yml`):
#     median 0.99h · p90 3.33h · p95 5.77h · max 21.52h
#     20 of 198 gaps (10.1%) exceeded the old 3.25h bar
# — so the pager fired on one ordinary interval in ten, and worse, its
# diagnosis ("CI AND deploys dead") was FALSE each time: push-triggered
# workflows ran fine straight through every one of those gaps (entries
# landed on main on 27/28-Aug while the cron sat 21.5h starved). Scheduler
# starvation delays only `schedule` events; a lockout kills everything.
# TWO CHANGES CLOSE IT TOGETHER:
#   * the beat is also written by every main-push CI run (changelog-check.yml
#     piggyback step, src-stamped), so its age measures "any Actions
#     delivery", the quantity the diagnosis actually claims. Merged-stream
#     control over the same tape (1,000 runs, 26-Aug -> 2-Sep): max gap
#     8.39h, 0 of 999 over 12h — where the schedule-only stream ran five
#     7-21.5h gaps the same week.
#   * two rungs. LATE (>= ACTIONS_HB_LATE_S, 4h = the vitals ttl) is a
#     WARNING — visible on /watchdog.json and the vitals card, never paged.
#     DARK (>= ACTIONS_HB_MAX_S, 12h = 3x ttl, one story with the organ
#     page) pages: 12h of NO deliveries of any kind is the lockout/outage
#     class, permanent until a human acts, and 0 of 999 merged gaps reach
#     it. The trade is stated: a real lockout is detected in up to 12h
#     rather than 3.25h — on a bar whose page the operator can finally
#     trust, which is the property that makes detection real ((gl): a
#     pager that cries wolf is not detection).
ACTIONS_HB_LATE_S = int(os.environ.get("WATCHDOG_ACTIONS_HB_LATE_SEC", "14400"))
ACTIONS_HB_MAX_S = int(os.environ.get("WATCHDOG_ACTIONS_HB_MAX_SEC", "43200"))


def actions_heartbeat_late(hb, read_ok, now_ts):
    """warning-string or None — the LATE rung. Pure, like its sibling below.

    Fires only in the band (LATE, MAX]: beyond MAX the page owns the story and
    a warning beside a problem would be two lines about one fault. Absent key,
    failed read and junk stamps are deliberately NOT warned here — each of
    those already has an owner in actions_heartbeat_problem.
    """
    if not read_ok or not isinstance(hb, dict) or not hb:
        return None
    try:
        u = dt.datetime.fromisoformat(str(hb.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=dt.timezone.utc)
        age = now_ts - u.timestamp()
    except Exception:  # noqa: BLE001
        return None                     # the unreadable stamp is a PAGE, below
    if ACTIONS_HB_LATE_S < age <= ACTIONS_HB_MAX_S:
        return (f"github actions slow: last beat {age / 3600:.1f}h ago "
                f"(scheduled deliveries measured p95 5.8h on the free tier; "
                f"pages as DARK at {ACTIONS_HB_MAX_S / 3600:.0f}h)")
    return None



def actions_heartbeat_problem(hb, read_ok, uptime_s, now_ts):
    """problem-string or None. Pure — tests/autonomy/test_actions_heartbeat.py.

    hb       : the bot_state payload dict (None = genuinely no row)
    read_ok  : False when the DB READ itself failed — that darkness belongs to
               the FEED STALE layer (the dashboard reads the same DB); paging
               "ACTIONS DARK" on a Postgres blip would send the operator to
               GitHub while the fault is the DB (I8: name the object the
               operator can act on).
    uptime_s : this service's own uptime. Absence of the key pages only after
               we have been up longer than the stale bar — so the bootstrap
               window (workflow not yet run once) is quiet, while a heartbeat
               that NEVER arrives still pages (a dead-man's switch that never
               arms is the I13 trap).
    """
    if not read_ok:
        return None
    if not isinstance(hb, dict) or not hb:
        if uptime_s is not None and uptime_s > ACTIONS_HB_MAX_S:
            return ("GITHUB ACTIONS HEARTBEAT NEVER SEEN: no bot_state "
                    f"'{ACTIONS_HB_KEY}' after {uptime_s / 3600:.1f}h up — "
                    "Actions dead or the heartbeat step broken; check the "
                    "repo's Actions runs + Settings/Billing")
        return None
    try:
        u = dt.datetime.fromisoformat(str(hb.get("updated")).replace("Z", "+00:00"))
        if u.tzinfo is None:
            u = u.replace(tzinfo=dt.timezone.utc)
        age = now_ts - u.timestamp()
    except Exception:  # noqa: BLE001
        # A row that EXISTS with an unreadable stamp is a broken writer, not
        # bootstrap — fail toward the page (the (hc) unreadable-stamp rule).
        return (f"GITHUB ACTIONS HEARTBEAT UNREADABLE: bot_state "
                f"'{ACTIONS_HB_KEY}' has no parseable 'updated' — fix the "
                "fleet-watchdog.yml heartbeat step")
    if age > ACTIONS_HB_MAX_S:
        return (f"GITHUB ACTIONS DARK: hourly heartbeat {age / 3600:.1f}h old "
                f"(last run_id {hb.get('run_id')}) — a billing lockout kills "
                "CI AND deploys silently (28-Jul scar); check the repo's "
                "Actions runs + Settings/Billing")
    return None


def _now_iso():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _now_op():
    """[2026-07-15 OPERATOR TZ] Sydney-local stamp for anything the OPERATOR
    reads (push bodies) — AEST/AEDT as actually in effect, so alert times
    match Eamon's clock. tzdata can be absent on slim images; the fixed +10
    fallback is right in winter and only off by 1h in DST — labeled anyway."""
    try:
        from zoneinfo import ZoneInfo
        n = dt.datetime.now(ZoneInfo("Australia/Sydney"))
        return n.strftime("%Y-%m-%d %H:%M ") + (n.tzname() or "AET")
    except Exception:  # noqa: BLE001
        return (dt.datetime.now(dt.timezone.utc)
                + dt.timedelta(hours=10)).strftime("%Y-%m-%d %H:%M AEST*")


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
    # [2026-07-16 AUDIT FIX] "halted" is the NORMAL daily-loss state (nine
    # publishers use it) and "paper" is the hl_paper row's resting status —
    # neither is a death; they paged as NOT ONLINE all day. Halted rows
    # surface as a warning instead (visible, not paged).
    off = sorted(b.get("bot", "?") for b in bots
                 if b.get("status") not in (None, "online", "halted", "paper"))
    # [2026-08-22 (ta)] A RETIRED ARM IS NOT A DAILY-LOSS HALT, AND SAYING SO
    # HOURLY FOREVER IS HOW A WARNING STOPS BEING READ.
    #
    # A retired live arm holds its halt permanently by design (it is how the
    # book flattens and stays flat), so without this it joins the daily-loss
    # line on every run, for the rest of the row's life, misattributing its own
    # cause. Two costs, and the second is the real one: the operator is told to
    # look at a rule that did not fire, and a line that is always present is a
    # line nobody reads when a REAL daily-loss halt lands beside it.
    #
    # Split on the row's own `extra.retired`, which the publisher stamps
    # precisely so `halted` stops being byte-identical between the two states
    # (I1/I18). Retired rows are reported as a NOTE, not a warning: there is no
    # action to take, and I8 says a detector's output must name something the
    # operator can act on. Still SHOWN, though — a retired row silently
    # vanishing from the watchdog is how a book stops being watched.
    def _retired(b):
        e = b.get("extra")
        return isinstance(e, dict) and isinstance(e.get("retired"), dict)

    halted_rows = [b for b in bots if b.get("status") == "halted"]
    halted = sorted(b.get("bot", "?") for b in halted_rows if not _retired(b))
    retired = sorted(b.get("bot", "?") for b in halted_rows if _retired(b))
    # `open` is the flatten's own receipt: non-zero means the retirement has
    # NOT finished unwinding, and on a real-money arm that is worth a warning
    # rather than a note — those positions are held by a book that will never
    # manage them again.
    unflat = sorted(
        f"{b.get('bot', '?')} ({b['extra']['retired'].get('open')} open)"
        for b in halted_rows
        if _retired(b) and (b["extra"]["retired"].get("open") or 0) > 0)
    if stale:
        problems.append("STALE: " + ", ".join(stale))
    if off:
        problems.append("NOT ONLINE: " + ", ".join(off))
    if halted:
        warnings.append("halted (daily-loss rule): " + ", ".join(halted))
    if unflat:
        warnings.append("RETIRED but still holding (flatten unfinished): "
                        + ", ".join(unflat))
    # `retired` itself is carried on the SNAPSHOT line below, not here — see
    # the note above. A standing warning is one nobody reads.
    # [2026-07-29 audit R5] a live bot's DEGRADED boot (':live' state read
    # failed: entries blocked, save suppressed, exits still running) was
    # log-only — the row said "online" and only container logs said why. The
    # Farmer now publishes extra.live_state_blind while degraded; a PROBLEM
    # (pages) because it means the bot cannot heal its durable state and a
    # restart in that window loses stop-quarantine changes. Self-clears on
    # heal (the key is absent when healthy).
    blind = sorted(b.get("bot", "?") for b in bots
                   if isinstance(b.get("extra"), dict)
                   and b["extra"].get("live_state_blind"))
    if blind:
        problems.append("LIVE-STATE BLIND (entries blocked, state save "
                        "suppressed): " + ", ".join(blind))
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
    # [2026-07-21 AUDIT FIX] prefer fleet_risk's OWN published LONG count +
    # budget: the local recompute was side-blind (the live Farmer's SHORTS
    # counted against the 20-LONG budget) and its cohort a superset of the
    # budget's (pm-* Parliament books, dislocation, perp-sniper — none
    # budgeted by fleet_risk), so the warning could fire while the budgeted
    # cohort was fine — and WATCHDOG_MAX_OPEN could silently drift from
    # LONG_BUDGET. One authority, apples to apples; the local count stays
    # the fallback when the fleet-risk state is dark/stale (a dead publisher
    # must not blind the watchdog).
    _fr_longs = _fr_budget = None
    try:
        import bot_pnl_store as _store
        _fr = _store.load_state("fleet-risk") or {}
        _u = dt.datetime.fromisoformat(
            str(_fr.get("updated")).replace("Z", "+00:00"))
        if _u.tzinfo is None:
            _u = _u.replace(tzinfo=dt.timezone.utc)
        if (dt.datetime.now(dt.timezone.utc) - _u).total_seconds() \
                <= float(_fr.get("ttl_sec") or 900):
            _fr_longs = int(_fr.get("long_positions"))
            _fr_budget = int(_fr.get("long_budget"))
    except Exception:  # noqa: BLE001
        _fr_longs = _fr_budget = None
    if _fr_longs is not None and _fr_budget is not None:
        if _fr_longs > _fr_budget:
            warnings.append(f"directional longs {_fr_longs} exceed the "
                            f"{_fr_budget}-long budget (fleet_risk cohort; "
                            f"{opens} gross incl. shadows)")
    elif dir_opens > max_open:
        warnings.append(f"directional positions {dir_opens} exceed the "
                        f"{max_open}-position budget ({opens} gross incl. "
                        f"shadows; fleet-risk state dark — local count)")
    loss_floor = float(os.environ.get("WATCHDOG_DAILY_LOSS_ALERT", "-100"))

    # [2026-07-28 AUDIT FIX] publisher-sent pnl_daily stays SENIOR, but the
    # only publisher that sends it is the Parliament — the two LIVE bots and
    # every shadow book carried pnl_daily=None, so this backstop was dormant
    # for exactly the rows real money lives on. Fall back to the feed's own
    # computed enrich.today_pnl (the dashboard's UTC-day figure).
    def _day_pnl(b):
        v = b.get("pnl_daily")
        if isinstance(v, (int, float)):
            return v
        v = (b.get("enrich") or {}).get("today_pnl")
        return v if isinstance(v, (int, float)) else None

    big = []
    for b in bots:
        v = _day_pnl(b)
        if v is not None and v < loss_floor:
            big.append(f"{b.get('bot')} ({v:+.1f})")
    if big:
        warnings.append("daily P&L below " + str(loss_floor) + ": " + ", ".join(big))
    snapshot = (f"bots={len(bots)} open_positions={opens} "
                f"freshest={meta.get('freshest_update_age_sec')}s")
    # [(ta)] retired arms ride the CONTEXT line, never the warning list: there
    # is nothing to act on, and a line that is always present is one that gets
    # skimmed past when a real warning lands beside it. Visible, not paged, and
    # not a third return channel — `evaluate` returns
    # (problems, warnings, snapshot) and every caller unpacks exactly that.
    if retired:
        snapshot += " retired=" + ",".join(retired)
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
    started_ts = time.time()
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
                # [2026-07-16 AUDIT FIX] a REACHABLE vitals endpoint returning
                # an error payload / zero organs used to read as "no problems"
                # — one malformed organ payload silently disabled this whole
                # pager layer. Monitoring being down IS a problem.
                if vd.get("error") or not vd.get("organs"):
                    problems.append("VITALS UNREADABLE: organ-death detection blind"
                                    + (f" ({str(vd.get('error'))[:80]})" if vd.get("error") else ""))
                for o in (vd.get("organs") or []):
                    if o.get("critical") and o.get("status") in ("DARK", "ERROR"):
                        age = o.get("age_min")
                        problems.append(
                            f"ORGAN {o.get('status')}: {o.get('key')}"
                            + (f" (last publish {age:.0f}m ago)" if age is not None else
                               (" (never published)" if o.get("status") == "DARK"
                                else " (payload unreadable)")))
            except Exception:  # noqa: BLE001
                pass
            # [2026-08-05] CI-liveness dead-man's switch — see
            # actions_heartbeat_problem above. Reads the DB DIRECTLY (not
            # /vitals.json): this pager must not depend on the surface it
            # backstops. The guard clause only covers the import; the check
            # itself is total (load_state_checked never raises).
            try:
                import bot_pnl_store as _hb_store
                _hb_ok, _hb = _hb_store.load_state_checked(ACTIONS_HB_KEY)
                _hb_p = actions_heartbeat_problem(
                    _hb, _hb_ok, time.time() - started_ts, time.time())
                if _hb_p:
                    problems.append(_hb_p)
                # the LATE rung: a visible warning while deliveries are merely
                # starved, so the DARK page above stays trustworthy.
                _hb_w = actions_heartbeat_late(_hb, _hb_ok, time.time())
                if _hb_w:
                    warnings.append(_hb_w)
            except Exception:  # noqa: BLE001
                pass
            email_armed = bool(report_emailer and report_emailer.smtp_configured())
            push_armed = bool(ntfy_topic())
            armed = email_armed or push_armed
            # [2026-07-16 AUDIT FIX] dedup on VALUE-STABLE keys: problem
            # strings embed live numbers ("freshest=312s", "last publish 47m
            # ago"), so a persistent problem read as a permanently-changing
            # set and re-paged every 30 min forever. The min gap now applies
            # to EVERY alert send (incl. right after a recovery) so a bot
            # flapping at its staleness boundary can't page on each flap.
            cur = tuple(re.sub(r"\d+", "#", p) for p in problems)
            now = time.time()
            kind = None
            if cur:
                if (last_emailed in (None, ()) or cur != last_emailed) \
                        and now - last_email_ts >= min_gap:
                    kind = "alert"
            else:
                if last_emailed not in (None, ()):
                    kind = "recovery"
            if kind and armed:
                subj = ("🚨 fleet-watchdog: " + problems[0][:70]) if kind == "alert" else \
                       "✅ fleet-watchdog: recovered — all bots fresh"
                body_lines = [f"Time: {_now_op()} ({_now_iso()} UTC)",
                              f"Snapshot: {snapshot}", ""]
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
    # [2026-07-29 audit R5] evaluate() fixtures for the LIVE-STATE BLIND rule:
    # a degraded live boot must PAGE (problem), a healthy row must not, and a
    # junk/string extra must never crash the evaluator (fail-safe skip).
    _base = {"bot": "perps-funding-lighter-lighter", "status": "online",
             "stale": False, "extra": {}}
    p0, _w0, _ = evaluate({"meta": {}, "bots": [dict(_base)]})
    assert not any("BLIND" in x for x in p0), p0
    p1, _w1, _ = evaluate({"meta": {}, "bots": [
        dict(_base, extra={"live_state_blind": True})]})
    assert any("LIVE-STATE BLIND" in x for x in p1), p1
    p2, _w2, _ = evaluate({"meta": {}, "bots": [
        dict(_base, extra="junk-string")]})
    assert not any("BLIND" in x for x in p2), "string extra must fail-safe skip"
    print("fleet_watchdog_svc selftest OK (push channel + live-state-blind rule)")
