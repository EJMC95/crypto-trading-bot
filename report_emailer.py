#!/usr/bin/env python3
"""
report_emailer.py — cloud-side (Mac-independent) scheduled P&L emails via SMTP.

Runs as a guarded daemon thread inside the always-on pnl-dashboard service. It is
DORMANT until SMTP env vars are set, so it changes nothing until you opt in.

Enable by setting these on the pnl-dashboard Railway service:
  SMTP_HOST   e.g. smtp.gmail.com   (iCloud: smtp.mail.me.com)
  SMTP_PORT   587                   (default)
  SMTP_USER   your full email address
  SMTP_PASS   an APP PASSWORD (Gmail: Account>Security>App passwords;
                                iCloud: appleid.apple.com app-specific password)
  REPORT_TO   where to send (default: SMTP_USER)
  REPORT_FROM optional (default: SMTP_USER)
  REPORT_HOUR_UTC  hour to send the daily/weekly/monthly mail (default 22)

Idempotent: records what it sent in a Postgres table so a dashboard restart never
double-sends. Never raises into the server.
"""
import os, time, smtplib, ssl, traceback
from email.message import EmailMessage
from datetime import datetime, timezone


def _env(k, d=None):
    return os.environ.get(k, d)


def smtp_configured():
    return all(_env(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))


def send_email(subject, body):
    """Send a plain-text email. Returns True on success, False (no raise) otherwise."""
    if not smtp_configured():
        return False
    try:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = _env("REPORT_FROM") or _env("SMTP_USER")
        msg["To"] = _env("REPORT_TO") or _env("SMTP_USER")
        msg.set_content(body)
        host, port = _env("SMTP_HOST"), int(_env("SMTP_PORT", "587"))
        ctx = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=30) as s:
            s.starttls(context=ctx)
            s.login(_env("SMTP_USER"), _env("SMTP_PASS"))
            s.send_message(msg)
        return True
    except Exception:
        print("[report_emailer] send failed:\n" + traceback.format_exc(), flush=True)
        return False


# ---- idempotency (Postgres) -------------------------------------------------
def _already_sent(conn, key):
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS report_sent "
                    "(report_key TEXT PRIMARY KEY, sent_at TIMESTAMPTZ NOT NULL DEFAULT now())")
        cur.execute("SELECT 1 FROM report_sent WHERE report_key=%s", (key,))
        return cur.fetchone() is not None


def _mark_sent(conn, key):
    with conn.cursor() as cur:
        cur.execute("INSERT INTO report_sent (report_key) VALUES (%s) "
                    "ON CONFLICT DO NOTHING", (key,))


# ---- report bodies (reuse the dashboard's own data fns) ---------------------
def _bodies(dash):
    """Build (period_key, subject, body) tuples that are DUE today. `dash` is the
    pnl_dashboard module (passed in to avoid circular import)."""
    now = datetime.now(timezone.utc)
    out = []
    try:
        market = dash.market_md_cached()
    except Exception:
        market = "(market snapshot unavailable)"
    try:
        pay = dash.periods_payload()
    except Exception:
        pay = {"daily": [], "weekly": [], "monthly": []}

    def fmt_rows(rows, n):
        if not rows:
            return "  (no closed paper trades yet)"
        lines = []
        for r in rows[:n]:
            by = ", ".join(f"{k}={v:+.2f}" for k, v in (r.get("by_bot") or {}).items())
            lines.append(f"  {r['period']}: total {r['total']:+.2f}  ({r.get('trades',0)} trades)"
                         + (f"  [{by}]" if by else ""))
        return "\n".join(lines)

    # daily — every day
    out.append((f"daily-{now:%Y-%m-%d}",
                f"Crypto bots — daily P&L {now:%Y-%m-%d}",
                f"{market}\n\n## Daily realized P&L (last 7)\n{fmt_rows(pay['daily'],7)}\n\n"
                f"Dry-run/paper. Dashboard: https://pnl-dashboard-production-858c.up.railway.app/periods"))
    # weekly — Mondays
    if now.weekday() == 0:
        out.append((f"weekly-{now:%G-W%V}",
                    f"Crypto bots — weekly P&L {now:%Y-%m-%d}",
                    f"{market}\n\n## Weekly realized P&L (last 6)\n{fmt_rows(pay['weekly'],6)}\n\n"
                    f"Dry-run/paper."))
    # monthly — 1st
    if now.day == 1:
        out.append((f"monthly-{now:%Y-%m}",
                    f"Crypto bots — monthly P&L {now:%Y-%m}",
                    f"{market}\n\n## Monthly realized P&L (last 6)\n{fmt_rows(pay['monthly'],6)}\n\n"
                    f"Dry-run/paper."))
    return out


def run_loop(dash):
    """Daemon loop: once past REPORT_HOUR_UTC each day, send any due, not-yet-sent
    reports. Polls every 15 min. Dormant (logs once) until SMTP is configured."""
    if not smtp_configured():
        print("[report_emailer] dormant — set SMTP_HOST/USER/PASS to enable cloud email", flush=True)
    send_hour = int(_env("REPORT_HOUR_UTC", "22"))
    while True:
        try:
            if smtp_configured() and datetime.now(timezone.utc).hour >= send_hour:
                import psycopg2
                url = _env("DATABASE_URL", "")
                conn = psycopg2.connect(url, connect_timeout=8); conn.autocommit = True
                try:
                    for key, subj, body in _bodies(dash):
                        if _already_sent(conn, key):
                            continue
                        if send_email(subj, body):
                            _mark_sent(conn, key)
                            print(f"[report_emailer] sent {key}", flush=True)
                finally:
                    conn.close()
        except Exception:
            print("[report_emailer] loop error:\n" + traceback.format_exc(), flush=True)
        time.sleep(900)
