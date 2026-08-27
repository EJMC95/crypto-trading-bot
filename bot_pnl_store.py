#!/usr/bin/env python3
"""
bot_pnl_store.py — tiny shared P&L publisher backed by Railway Postgres.

Every bot calls publish(...) once per loop with whatever it knows about its own
state (equity, paper P&L, trade counts). The row is upserted into a single
`bot_pnl` table keyed by bot name. The live dashboard (pnl_dashboard.py) reads
that table and renders all bots on one page.

DESIGN GOALS
  * Zero impact on the trading loop. If DATABASE_URL is unset, psycopg2 is
    missing, or Postgres is unreachable, publish() quietly no-ops and returns
    False. It NEVER raises into the caller.
  * One dependency (psycopg2-binary). Connection is cached and lazily
    re-established if it drops.

USAGE
    import bot_pnl_store as store
    store.publish("triangular-arb", status="online",
                  pnl_abs=virtual_balance, extra={"cycles": n})

Set DATABASE_URL on each Railway service to a reference to the Postgres
service's connection string (Railway: Variables -> add reference -> Postgres
DATABASE_URL). Locally, leave it unset and this module is a no-op.
"""
import os
import sys
import json
import math
import time
import hashlib

_DATABASE_URL = os.environ.get("DATABASE_URL", "").strip()

_conn = None
_warned = False
_table_ready = False


def _warn_once(msg):
    global _warned
    if not _warned:
        print(f"[bot_pnl_store] disabled: {msg}", flush=True)
        _warned = True


def _get_conn():
    """Return a live connection, or None if unavailable (no raise)."""
    global _conn
    if not _DATABASE_URL:
        _warn_once("DATABASE_URL not set")
        return None
    try:
        import psycopg2  # noqa: imported lazily so missing dep is a no-op
    except Exception as e:
        _warn_once(f"psycopg2 not importable ({e})")
        return None
    if _conn is not None:
        try:
            # cheap liveness check
            with _conn.cursor() as cur:
                cur.execute("SELECT 1")
            return _conn
        except Exception:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    try:
        _conn = psycopg2.connect(_DATABASE_URL, connect_timeout=5)
        _conn.autocommit = True
        return _conn
    except Exception as e:
        _warn_once(f"connect failed ({e})")
        return None


def _ensure_table(conn):
    global _table_ready
    if _table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_pnl (
                bot            TEXT PRIMARY KEY,
                updated_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
                status         TEXT,
                equity         DOUBLE PRECISION,
                pnl_abs        DOUBLE PRECISION,
                pnl_pct        DOUBLE PRECISION,
                open_trades    INTEGER,
                closed_trades  INTEGER,
                wins           INTEGER,
                losses         INTEGER,
                extra          JSONB
            )
            """
        )
        # [2026-07-08] bot-supplied daily P&L. The dashboard prefers this over
        # its server-side equity-curve delta when present — lets bots with an
        # authoritative broker daily figure (Alpaca equity vs last_equity)
        # override the glitch-prone cross-snapshot estimate.
        cur.execute(
            "ALTER TABLE bot_pnl ADD COLUMN IF NOT EXISTS pnl_daily DOUBLE PRECISION"
        )
    _table_ready = True


# ---------------------------------------------------------------------------
# BUILD ID — what code is this process actually running?
# ---------------------------------------------------------------------------
# WHY IT LIVES HERE and not in its own module. It was `build_id.py` for about
# ten minutes, until the born-dark guard reported it MISSING FROM 19 OF 20
# IMAGES — because this file is universal and nothing COPYs that one. The fix
# is not 20 `COPY build_id.py` lines: that is a ROSTER, and a roster nobody
# maintains is the control that already failed (17-Jul: LIVE_FRESHNESS_LIMITS
# rotted, the deploy path list rotted, and this very guard exists because
# `brain_stats` shipped to an image that lacked it). A new image tomorrow
# forgets the COPY, that bot silently never stamps, and the drift detector goes
# quiet for exactly the bot that changed. Here, "can publish" == "can stamp",
# by construction — the property no list can give you.
#
# WHY BYTES, NOT A LABEL. Every self-describing label in this fleet has lied:
# `RAILWAY_GIT_*` reads 0 on EVERY service, connected or not (it produced a
# false fleet-wide "nothing is git-connected" verdict on 17-Jul);
# `railway status` meta.branch is blank for every `railway up`, so CI and a
# desk upload are indistinguishable; `lighter.__version__` reports "1.0.0", a
# release PyPI does not have, while the wheel signing real orders was 1.1.2.
# A hash of the source bytes cannot lie about being those bytes.
#
# WHAT IT CATCHES — ARM DRIFT. Every live bot has a `-lshadow` CONTROL arm in a
# DIFFERENT Railway service (Farmer: trail-blazer-live vs funding-farmer-shadow;
# Taker: tide-rider-lighter-live vs the organ container) — separate deploy
# clocks. `experiment_judge` promotes to `live.funding.*` on "shadow beats live
# per-trade", and `implementation_shortfall` reads that same gap as execution
# quality. Drifted arms put a strategy delta into both numbers, and neither
# organ can see it: they compare OUTCOMES, the drift is in the INPUTS.
_BUILD_ROOT = os.path.dirname(os.path.abspath(__file__))
# A FIXED, DECLARED set — the entry module + the real-money surface both arms
# share. NOT "every repo-local module in sys.modules": a lazy or conditional
# import (`if VENUE.startswith('lighter')`, a try/except organ guard) changes
# the module set without changing the code, so identical arms would report
# different ids and the detector would cry drift forever. The set must not
# depend on the execution path — the same reason `if dry_run` branches cannot
# be compared across arms.
# [2026-07-30 (ev)] fleet_tuning.py joined the set: it is the CLAMP CAGE at
# every real-money lever consumer — a stamp that cannot see the cage cannot
# see cage drift between arms (found when the A1 bound widening would have
# deployed hash-invisibly). Adding a file shifts every build id at each
# service's NEXT deploy — expected, documented here.
# [2026-08-14 (mp)] fleet_bus.py joined for the same reason one level out: it
# is the READ CLIENT for every cross-bot signal a book acts on — brain stake
# mults, the fleet-risk long-budget veto, `allocation_scale`, the per-asset
# oracle regimes, `scout_universe`, `lever_outcome`. `fleet_tuning` is the cage
# on what the rail may WRITE; this is the layer that decides what each book
# READS, and drift here changes behaviour on both arms with nothing to show for
# it. FOUND BY A DEPLOY THAT COULD NOT BE VERIFIED: `(lx)` changed
# `allocation_scale` so a book may only be scaled past flat on its own era's
# evidence — a real change to shadow sizing — and the stamp read BYTE-IDENTICAL
# before and after (`f80d5c78d168`, n=15). Stamp readback is the fleet's only
# accepted proof a deploy landed ([[railway-cli-frozen-services]]), so a file
# outside this set is a file whose deploys cannot be proved.
#   THE COST, stated rather than discovered: 15 of 26 images COPY fleet_bus.py,
#   so those stamp a new id at n+1 on their next deploy and the other 11 do not
#   move at all (absent names are skipped — the (fd) rule). Until each service
#   redeploys, a repo-side prediction will not match its row. That is
#   BEHIND-SHARED, not BEHIND-OWN: `audit_code_currency` classifies it and only
#   BEHIND-OWN is a finding, and the daily review states it UNCLASSIFIED and
#   names that authority rather than escalating ((ke), after `(ka)` tripped the
#   same wire on both real-money rows). NOT a live deploy on its own — it
#   changes no trade either live book would take, so under (mm)'s push-both-ways
#   rule it rides free on the next deploy that DOES qualify.
# [2026-08-15 (mu)] lighter_family_bot.py joins: it is the STRATEGY MODULE of
# a REAL-MONEY image. `Dockerfile.avolive` COPYs it (the configured SwingDip
# instance 🙏 Avo Maria live actually trades) and the stamp did not hash it —
# so the fleet's mandated deploy-verification instrument ((hj): verify by
# `extra.build`+`build_n` readback, never by a green run) was blind to exactly
# the file the live deploy route carries. A strategy edit could ship to the
# live book and the stamp would read BYTE-IDENTICAL. Found by the 15-Aug
# fleet audit; adversarially verified before shipping. MEASURED per image
# (grep of the COPY sets, not image_contents — whose 4-tuple return has
# already produced one silently-empty carrier map): exactly 2 of 26 images
# carry it (avolive, familyshadow); the other 24 skip the absent name and
# move only because this file itself changed — the same one-deploy-cycle
# BEHIND-SHARED cost (mp) documented above.
_BUILD_SHARED = ("venues", "funding_basis.py", "bot_pnl_store.py",
                 "fleet_tuning.py", "fleet_bus.py", "lighter_family_bot.py")
_BUILD_CACHE = None


def _build_rel(path):
    """The name a file has INSIDE its image — the only path two arms share.

    LOAD-BEARING: the same module sits at DIFFERENT absolute paths in different
    images (`/app/...` on the live Farmer, `/freqtrade/...` in the organ
    container). Keying on the absolute path would report permanent drift
    between identical code. Falls back to the basename for anything outside the
    root (test tmpdirs only) rather than raising.

    NOTE the explicit prefix test rather than a bare `os.path.relpath`: relpath
    does NOT fail for a path outside the root, it happily returns
    `../../tmp/xyz/arm.py` — so two identical files in different temp dirs got
    different keys and the path-independence fixture caught it. A fallback that
    triggers on an exception is worthless when the function never raises."""
    p = os.path.abspath(path)
    root = _BUILD_ROOT.rstrip(os.sep) + os.sep
    if p.startswith(root):
        return p[len(root):]
    return os.path.basename(p)


def _build_files(entry=None):
    """The hashed set: the entry module + whatever _BUILD_SHARED names EXIST.

    [2026-07-29 (fd)] A declared-but-ABSENT name is silently skipped, and that
    is deliberate — images legitimately carry different subsets (the shadow
    images do not COPY fleet_tuning.py at all: the growth-rail clip lever must
    not size a book outside the board's LIVE_ROWS, declared in
    audit_image_imports.BORN_DARK_OK). But the silence has a cost that bit on
    the day fleet_tuning.py joined the set: the SAME source tree stamps
    6de64508c304 over 15 files in an image that carries it and 74d3b3178fa8
    over 14 in one that does not, so a hash predicted from the REPO reads as
    "the deploy never landed" on a perfectly converged shadow service.
    The born-dark guard cannot catch this class: fleet_tuning.py is a DATA
    dependency of the stamp, not an import of the entry module.
    THE FIX IS NOT to hash absent files (that would make every image's id
    depend on files it does not run); it is to publish the COUNT alongside the
    id — see _stamp_build — so a short set is self-describing and a reader can
    tell "different file set" from "different code".
    """
    out, seen = [], set()

    def _add(p):
        # [2026-08-15 (nh)] DEDUP BY REAL PATH. Since (mu) an ENTRY can also be
        # a _BUILD_SHARED name (`lighter_family_bot.py` is the family image's
        # entry AND the module the live Avo image carries), and the two
        # appends use different path forms — `abspath(entry)` vs
        # `join(_BUILD_ROOT, name)`. Where those forms differ only by a
        # SYMLINK (macOS /tmp -> /private/tmp, a git worktree under a symlinked
        # temp dir), the same file was hashed TWICE and the stamp depended on
        # who was asking: the container counted 15 files, audit_code_currency's
        # per-commit probe counted 16, so the family rows could never resolve —
        # the audit printed UNRESOLVED and still exited OK, leaving "which
        # commit is this bot running?" silently unanswered for the image
        # carrying the live Avo strategy module's shadow twin.
        rp = os.path.realpath(p)
        if rp in seen:
            return
        seen.add(rp)
        out.append(p)

    if entry and os.path.isfile(entry):
        _add(os.path.abspath(entry))
    for name in _BUILD_SHARED:
        p = os.path.join(_BUILD_ROOT, name)
        if os.path.isdir(p):
            for d, _sub, fs in os.walk(p):
                for f in fs:
                    if f.endswith(".py"):
                        _add(os.path.join(d, f))
        elif os.path.isfile(p):
            _add(p)
    return sorted(set(out), key=_build_rel)


def build_compute(entry=None):
    """(id12, n_files) — sha256 over name+bytes of a fixed file set.
    None on any read failure: a sensor that cannot see must not vote, and a
    fabricated id would read as agreement between two drifted arms."""
    try:
        if entry is None:
            m = sys.modules.get("__main__")
            entry = getattr(m, "__file__", None)
            entry = os.path.abspath(entry) if entry else None
        files = _build_files(entry)
        if not files:
            return None, 0
        h = hashlib.sha256()
        for p in files:
            h.update(_build_rel(p).encode())
            h.update(b"\0")
            with open(p, "rb") as fh:
                h.update(fh.read())
            h.update(b"\0")
        return h.hexdigest()[:12], len(files)
    except Exception:      # noqa: BLE001 — never break a publish
        return None, 0


def build_code_id():
    """Cached per process — the bytes cannot change under a running process."""
    global _BUILD_CACHE
    if _BUILD_CACHE is None:
        _BUILD_CACHE = build_compute()
    return _BUILD_CACHE[0]


def build_code_files():
    """How many files the cached id was computed over — the id's other half.

    [2026-07-29 (fd)] Published as `extra.build_n` so a row says which SET it
    hashed, not just the digest (see _build_files for the incident)."""
    global _BUILD_CACHE
    if _BUILD_CACHE is None:
        _BUILD_CACHE = build_compute()
    return _BUILD_CACHE[1]


def service_name():
    """[2026-07-31 (ht)] WHICH RAILWAY SERVICE is this process? '' if unknown.

    THE GAP THIS CLOSES, and it has blocked an OPERATOR ACTION for four
    entries. 🌾 carry is published by TWO services — `funding-carry` and
    `yield-harvester-shadow` — and one of them must be stopped by hand. Every
    attempt to say WHICH ran into the same wall, written down three times in
    three files: `(gl)` "this repo could not say which owned the row",
    `(gn)`/(railway-redeploy.yml) "this repo cannot tell which of the two
    publishes the row ... left for the operator rather than resolved by
    guessing", `(hf)` the ledger is two books.

    Then `(ho)`/`(hp)` shipped the sole-writer guard — and it reports
    `_writer_id()`, which is `RAILWAY_REPLICA_ID`/`HOSTNAME`: an OPAQUE id
    that names a container, not a service. So the guard that finally detects
    the duplicate still cannot name the thing the operator has to switch off.
    The diagnosis was complete and the instruction was unactionable.

    Railway sets `RAILWAY_SERVICE_NAME` in every container. It was used
    NOWHERE in this repo (measured 31-Jul: zero hits across *.py/*.yml/*.toml)
    while four entries reported the question it answers.

    Empty string, never a guess: a missing env var means "unknown", and
    "unknown" must not render as a service name somebody might go and stop.
    """
    return str(os.environ.get("RAILWAY_SERVICE_NAME") or "")[:64]


def describe_writer(writer_id, svc=None):
    """Render a writer as 'service (replica)' — or the bare id when the
    service is unknown. The operator reads this to decide what to stop, so an
    unknown service must degrade to the old opaque id rather than to a blank
    that looks like an answer."""
    wid = str(writer_id or "")[:64]
    svc = str(svc or "")[:64]
    return f"{svc} ({wid})" if svc and wid else (svc or wid)


def _stamp_build(extra):
    """Stamp `extra.build` (+ `extra.build_n`, + `extra.svc`) on every publish.
    Never raises, never overwrites a caller's key: telemetry must not break a
    publish that reports real money.

    [2026-07-31 (ht)] `svc` rides HERE, the one hook every book's publish
    already passes through, rather than in the carry bot — so the attribution
    covers all 24 books and the NEXT duplicate is named on sight instead of
    starting another multi-entry investigation. Doctrine rule 2: a fix closes
    a class or it is not finished.
    """
    try:
        cid = build_code_id()
        out = dict(extra or {})
        svc = service_name()
        if svc:
            out.setdefault("svc", svc)
        if not cid:
            # still return `out` — an unstampable build must not also cost the
            # row its service attribution (these two are independent).
            return out if svc else extra
        out.setdefault("build", cid)
        n = build_code_files()
        if n:
            out.setdefault("build_n", n)
        return out
    except Exception:      # noqa: BLE001
        return extra


def _finite_or_none(x):
    """Coerce a money field to a FINITE float, else None.

    [2026-07-18] The shared bot_pnl schema is nullable and every consumer treats
    None as 'no value'. A NaN/inf/garbage value does NOT fail the write —
    Postgres float8 accepts 'NaN'/'Infinity' — it silently poisons every
    aggregate that reads the column: SUM(pnl_abs) over the fleet becomes NaN, so
    ONE mis-publishing bot corrupts the whole fleet total (and the dashboard's
    `money()` would render it '+nan'). Nulling the bad value contains the blast
    radius to the one row. Never raises; identity on a valid finite number.
    """
    if x is None:
        return None
    try:
        f = float(x)
    except (TypeError, ValueError):
        return None
    return f if math.isfinite(f) else None


def publish(bot, status="online", equity=None, pnl_abs=None, pnl_pct=None,
            open_trades=None, closed_trades=None, wins=None, losses=None,
            extra=None, pnl_daily=None):
    """Upsert this bot's current snapshot. Returns True on success, else False.

    Safe to call every loop. Never raises.
    """
    conn = _get_conn()
    if conn is None:
        return False
    extra = _stamp_build(extra)
    # Sanitize the money fields BEFORE they reach the shared table — a single
    # NaN/inf poisons the fleet-wide SUM() aggregates (see _finite_or_none).
    equity = _finite_or_none(equity)
    pnl_abs = _finite_or_none(pnl_abs)
    pnl_pct = _finite_or_none(pnl_pct)
    pnl_daily = _finite_or_none(pnl_daily)
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_pnl (bot, updated_at, status, equity, pnl_abs,
                    pnl_pct, open_trades, closed_trades, wins, losses, extra,
                    pnl_daily)
                VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at    = now(),
                    status        = EXCLUDED.status,
                    equity        = EXCLUDED.equity,
                    pnl_abs       = EXCLUDED.pnl_abs,
                    pnl_pct       = EXCLUDED.pnl_pct,
                    open_trades   = EXCLUDED.open_trades,
                    closed_trades = EXCLUDED.closed_trades,
                    wins          = EXCLUDED.wins,
                    losses        = EXCLUDED.losses,
                    extra         = EXCLUDED.extra,
                    pnl_daily     = EXCLUDED.pnl_daily
                """,
                (bot, status, equity, pnl_abs, pnl_pct, open_trades,
                 closed_trades, wins, losses,
                 # [(kh)] sanitised — see publish_paper_trade for the class.
                 # A NaN here makes Postgres reject the row and the dashboard
                 # silently freezes at its last good publish.
                 json.dumps(json_safe(extra), allow_nan=False)
                 if extra is not None else None,
                 pnl_daily),
            )
        return True
    except Exception as e:
        # [2026-07-12 GO-GREEN] one immediate reconnect+retry so a transient
        # Postgres blip doesn't cost a whole publish cycle. Second failure
        # falls through to the original guarded behaviour.
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        try:
            conn2 = _get_conn()
            if conn2 is not None:
                with conn2.cursor() as cur:
                    cur.execute(
                        """
                        INSERT INTO bot_pnl (bot, updated_at, status, equity, pnl_abs,
                            pnl_pct, open_trades, closed_trades, wins, losses, extra,
                            pnl_daily)
                        VALUES (%s, now(), %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                        ON CONFLICT (bot) DO UPDATE SET
                            updated_at    = now(),
                            status        = EXCLUDED.status,
                            equity        = EXCLUDED.equity,
                            pnl_abs       = EXCLUDED.pnl_abs,
                            pnl_pct       = EXCLUDED.pnl_pct,
                            open_trades   = EXCLUDED.open_trades,
                            closed_trades = EXCLUDED.closed_trades,
                            wins          = EXCLUDED.wins,
                            losses        = EXCLUDED.losses,
                            extra         = EXCLUDED.extra,
                            pnl_daily     = EXCLUDED.pnl_daily
                        """,
                        (bot, status, equity, pnl_abs, pnl_pct, open_trades,
                         closed_trades, wins, losses,
                         # [(kh)] sanitised — the reconnect RETRY path had the
                         # same hole, so a NaN failed twice and looked like a
                         # connection problem.
                         json.dumps(json_safe(extra), allow_nan=False)
                         if extra is not None else None,
                         pnl_daily),
                    )
                return True
        except Exception as e2:
            _warn_once(f"write failed twice ({e}; retry: {e2})")
            try:
                _conn.close()  # type: ignore[union-attr]
            except Exception:
                pass
            _conn = None
            return False
        _warn_once(f"write failed ({e})")
        return False


# ---------------------------------------------------------------------------
# Durable bot state (one JSON blob per bot). Lets the dry-run bots restore
# their paper account (equity, open positions, risk state) after a redeploy or
# restart, so equity curves GROW across deploys instead of resetting to $1000.

_state_table_ready = False


def _ensure_state_table(conn):
    global _state_table_ready
    if _state_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state (
                bot        TEXT PRIMARY KEY,
                updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                state      JSONB
            )
            """
        )
    _state_table_ready = True


def json_safe(obj, _depth=0):
    """[2026-07-31 (hx)] Recursively replace NaN/inf with None so a payload can
    survive `json.dumps` -> Postgres `jsonb`.

    THE INCIDENT, and it cost the brain THREE DAYS OF MEMORY silently.
    `save_state` dumped with bare `json.dumps`, which emits `NaN`/`Infinity`
    for those floats — tokens that are NOT valid JSON. Postgres jsonb rejects
    the whole write, the exception was caught, `_warn_once` logged it ONCE into
    a container nobody reads, and `bot_learn._save_state` discarded the False.
    MEASURED 31-Jul: `learning-brain.runs` stuck at 337 with `updated`
    2026-07-28, while `brain-vitals.run` read 338 and published fresh every
    cycle. The brain reloaded the 28-Jul state every run, recomputed, published
    fresh vitals/mults/diagnosis, and could not remember — so `mult_streaks`
    froze and the 3-run promotion gate became unreachable. `mults_published: 1`
    of 20 living bots, and that survivor carried `streak: 15` from BEFORE the
    freeze. An amnesiac organ that looks healthy from every other key.

    This is the `_finite_or_none` discipline the money columns have had since
    18-Jul, applied to the arbitrary nested blobs `save_state` accepts. Same
    direction (a bad value becomes null, the row still writes), because losing
    one field beats losing the whole state.

    Depth-bounded: a self-referential structure would otherwise recurse
    forever, and this runs inside a never-raises writer.
    """
    if _depth > 60:
        return None
    if isinstance(obj, float):
        return None if (obj != obj or obj in (float("inf"), float("-inf"))) else obj
    if isinstance(obj, dict):
        # keys must be JSON strings; non-str keys are stringified the way
        # json.dumps would, so this never changes the emitted shape
        return {(k if isinstance(k, str) else str(k)): json_safe(v, _depth + 1)
                for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_safe(v, _depth + 1) for v in obj]
    return obj


def save_state(bot, state):
    """Upsert this bot's durable state blob. Safe to call every loop. Never raises.

    Returns True ONLY on a committed write. Callers that silently ignore a
    False here get an organ that quietly stops remembering — see `json_safe`.
    """
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO bot_state (bot, updated_at, state)
                VALUES (%s, now(), %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at = now(),
                    state      = EXCLUDED.state
                """,
                # allow_nan=False turns a non-finite that slipped past
                # json_safe into a LOUD ValueError here rather than an
                # invalid-JSON rejection at the database.
                (bot, json.dumps(json_safe(state), allow_nan=False)),
            )
        return True
    except Exception as e:
        _warn_once(f"state write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


_WRITER_ID = None
WRITER_CLAIM_TTL = int(os.environ.get("WRITER_CLAIM_TTL_SEC", "1800"))


def _writer_id():
    """This PROCESS's identity — stable for its lifetime, unique across
    containers. Not the build stamp: two containers can run the same image."""
    global _WRITER_ID
    if _WRITER_ID is None:
        import uuid
        _WRITER_ID = (os.environ.get("RAILWAY_REPLICA_ID")
                      or os.environ.get("HOSTNAME")
                      or uuid.uuid4().hex[:12])
    return str(_WRITER_ID)[:64]


def _claim_is_my_own_dead_replica(claim):
    """[2026-08-01 (id)] Is this claim held by a PREVIOUS REPLICA OF ME?

    `_writer_id()` is `RAILWAY_REPLICA_ID`, and Railway mints a new one on
    every deploy. So a redeployed container meets a claim written by its own
    dead predecessor, sees a writer id that is not its own, and stands down
    against ITSELF. MEASURED 1-Aug, from `funding-carry`'s own log:

        STANDING DOWN — perps-funding-carry-lshadow is already claimed by
        another container (funding-carry (838bd2e8-...))

    — the service name in the "other container" slot is its own. It idled
    four consecutive loops and would have idled the book for the full
    WRITER_CLAIM_TTL (30 min) after EVERY deploy. It was invisible until (ic)
    stopped the stood-down container from publishing the book's row, which is
    the only reason the stall became observable at all.

    THE TEST IS THE SERVICE, NOT THE REPLICA. Same `svc` + different replica
    means Railway replaced the container — it does not run the old and new
    together. Cross-SERVICE protection is untouched: `funding-carry` still
    cannot steal from `yield-harvester-shadow`, which is the duplicate this
    whole guard exists for.

    DECLARED ASSUMPTION — SINGLE REPLICA PER SERVICE. If a carry service is
    ever scaled past one replica, two live replicas would share a `svc` and
    could steal from each other, which is exactly the duplicate-writer state
    this guard prevents. No Railway env reports replica COUNT, so this cannot
    be asserted at runtime; it is written down instead of assumed silently.
    Every service in this project is single-replica today.

    Fail-CLOSED on doubt: an unknown or empty `svc` on either side is NOT a
    match, so pre-(ht) claims (which carry no `svc`) fall through to the TTL
    exactly as before rather than being stolen on a guess — the (ht) rule that
    unknown degrades to the old behaviour, never to a guess.
    """
    mine = (service_name() or "").strip()
    theirs = str(claim.get("svc") or "").strip()
    return bool(mine) and bool(theirs) and mine == theirs


def claim_writer(bot, now=None):
    """-> (ok, other) — is THIS process the sole writer of `bot`'s ledger?

    [2026-07-30 (ho)] TWO CONTAINERS WRITING ONE BOOK IS SILENT AND IT
    DESTROYS THE EVIDENCE. Measured on 🌾 perps-funding-carry-lshadow, the
    fleet's only go-live candidate: 14 OVERLAPPING same-pair positions (one
    book cannot hold BNB twice at once) and TWO distinct `extra.build` stamps
    on recent rows. `(gl)` deployed both `funding-carry` and
    `yield-harvester-shadow` because this repo could not say which owned the
    row — a reasonable call with the information available, and the
    consequence is that both now do. The ledger became a mixture of two
    independent books, so `n` is not one book's trades and every statistic
    computed on it — including its go-live grade — is meaningless.

    THE CONTRACT, and the direction of failure is deliberate:
      * FAIL-OPEN. A dark DB, an unreadable claim or any exception returns
        (True, None). A duplicate writer corrupts EVIDENCE; a false positive
        would stop a book from TRADING. Evidence is recoverable, a halted book
        is lost opportunity, so the safe direction is to keep trading and
        shout.
      * FIRST CLAIMANT WINS, and the claim EXPIRES. The incumbent refreshes on
        every call, so a container that dies frees the book within
        WRITER_CLAIM_TTL rather than locking it forever.
      * A REDEPLOY IS NOT A DUPLICATE. A claim held by this process's OWN
        SERVICE under a different replica id is its own dead predecessor and
        is taken immediately — see `_claim_is_my_own_dead_replica`. Without
        this the book idled for the full TTL after every deploy, standing
        down against its own service name.
      * ADVISORY. This returns a verdict; it does not halt anything. The
        caller decides, and today every caller only reports. Making it halt a
        real book is an operator decision, not a library default.
    """
    me = _writer_id()
    try:
        cur = load_state("writer:" + str(bot)) or {}
        who, ts = cur.get("writer"), float(cur.get("ts") or 0)
        now = float(now if now is not None else time.time())
        if who and who != me and (now - ts) < WRITER_CLAIM_TTL \
                and not _claim_is_my_own_dead_replica(cur):
            # [2026-07-31 (ht)] Return the SERVICE, not just the replica id.
            # The whole point of this verdict is to tell the operator what to
            # switch off, and `_writer_id()` is an opaque container id. Claims
            # written before this change carry no `svc`, so `describe_writer`
            # degrades to exactly the old string rather than inventing one.
            return False, describe_writer(who, cur.get("svc"))
        save_state("writer:" + str(bot),
                   {"writer": me, "svc": service_name(), "ts": now})
        return True, None
    except Exception:                      # noqa: BLE001 — fail OPEN, always
        return True, None


def heartbeat(bot):
    """[2026-07-12 GO-GREEN] Touch ONLY updated_at on the bot's existing row —
    a liveness proof that never clobbers the last good snapshot. Cheap enough
    to call at the TOP of every loop, so slow scans, venue outages and
    skip-paths that never reach the full publish can't read as a dead bot."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute("UPDATE bot_pnl SET updated_at = now() WHERE bot = %s", (bot,))
        return True
    except Exception as e:
        _warn_once(f"heartbeat failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def set_status(bot, status):
    """[2026-07-12 GO-GREEN] Update ONLY status+updated_at (keeps the last
    equity/P&L intact). Used by boot-refusal paths so an ARMED/misconfigured
    bot shows as ERROR on the dashboard instead of silently going stale."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """INSERT INTO bot_pnl (bot, updated_at, status)
                   VALUES (%s, now(), %s)
                   ON CONFLICT (bot) DO UPDATE SET
                       updated_at = now(), status = EXCLUDED.status""",
                (bot, status))
        return True
    except Exception as e:
        _warn_once(f"set_status failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def save_daily_halt(bot, day_iso, day_start_equity=None):
    """Persist a tripped daily-loss halt under <bot>:halt. Never raises.

    [2026-07-11 DURABLE HALT] halted_today was memory-only in every perps bot,
    so a restart/redeploy on the same UTC day silently resumed trading after
    the loss rail fired. Bots call load_daily_halt at boot to stay halted.
    """
    return save_state(bot + ":halt", {"halted_date": day_iso,
                                      "day_start_equity": day_start_equity})


def load_daily_halt(bot, day_iso):
    """Return the halt state saved for day_iso (UTC 'YYYY-MM-DD'), else None.

    NOTE: None means "not halted OR the read failed" — see
    load_daily_halt_checked(). Any caller that lets trading RESUME on a None
    must use the checked form instead: this one cannot tell a Postgres blip
    from a clean day.
    """
    return load_daily_halt_checked(bot, day_iso)[1]


def load_daily_halt_checked(bot, day_iso):
    """(ok, halt) — `ok` is False only if the READ ITSELF failed.

    [2026-08-18 (pq)] `load_daily_halt` collapses "no halt today" and "I could
    not find out" into the same None, and its consumers are DAILY-LOSS RAILS on
    real money: on a failed read the book resumes entering positions on a day it
    had already halted. The commit that introduced the function is titled
    "daily-loss halt survives redeploys" — durability is its whole purpose, and
    a silent fail-OPEN is precisely the failure it was built to prevent.

    This is `load_state_checked`'s contract applied to the halt, for the same
    reason and with the same three states:

      ok=True,  halt=dict -> halted today, this is the record
      ok=True,  halt=None -> read succeeded, genuinely not halted
      ok=False, halt=None -> read FAILED; the caller must NOT resume trading

    A caller that treats ok=False as "not halted" has reintroduced the bug.
    The safe degrade is to hold the last known halt state and block NEW entries
    while blind — never to block EXITS, which must always be able to run.
    """
    ok, st = load_state_checked(bot + ":halt")
    if not ok:
        return False, None
    st = st or {}
    return True, (st if st.get("halted_date") == day_iso else None)


def locked_state_update(key, fn):
    """[2026-07-16 MERGE-RACE FIX] Serialize a read-modify-write on ONE
    bot_state key across processes: read under a Postgres session advisory
    lock, apply fn(old_dict_or_None) -> new_dict, upsert, release. The
    fleet-tuning key has three authors on independent timers — an unlocked
    merge off a stale read silently dropped the other author's just-written
    levers. Returns the written dict, or None when the DB/lock path is
    unavailable (callers keep their unlocked fallback). fn must be pure and
    fast — the lock is held while it runs. Never raises."""
    conn = _get_conn()
    if conn is None:
        return None
    lock_id = None
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT hashtext(%s)", (key,))
            lock_id = cur.fetchone()[0]
            cur.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (key,))
            row = cur.fetchone()
            old = row[0] if row else None
            if isinstance(old, str):
                try:
                    old = json.loads(old)
                except Exception:
                    old = None
            new = fn(old if isinstance(old, dict) else None)
            if not isinstance(new, dict):
                return None
            cur.execute(
                """
                INSERT INTO bot_state (bot, updated_at, state)
                VALUES (%s, now(), %s)
                ON CONFLICT (bot) DO UPDATE SET
                    updated_at = now(),
                    state      = EXCLUDED.state
                """,
                (key, json.dumps(new)))
            return new
    except Exception as e:  # noqa: BLE001
        _warn_once(f"locked state update failed ({e})")
        return None
    finally:
        if lock_id is not None:
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
            except Exception:  # noqa: BLE001
                pass


def load_state_checked(bot):
    """(ok, state) — `ok` is False only if the READ ITSELF failed.

    [2026-07-17] load_state() collapses "no row" and "read failed" into the same
    None. That is fine for a bot that just wants its last state, but it is a trap
    for any caller that SEEDS durable state on an empty read: a Postgres blip
    then looks identical to a first run. The perp sniper seeds its listing
    baseline that way, and a false seed there silently absorbs every live market
    (see the 17-Jul RETRY FIX in lighter_perp_sniper.py). Such callers must be
    able to tell "definitely nothing stored" from "I could not find out".

    ok=True,  state=dict -> the row exists
    ok=True,  state=None -> read succeeded, genuinely no row
    ok=False, state=None -> read FAILED; the caller must NOT infer emptiness
    """
    conn = _get_conn()
    if conn is None:
        return False, None
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT state FROM bot_state WHERE bot = %s", (bot,))
            row = cur.fetchone()
        if row and row[0] is not None:
            return True, (row[0] if isinstance(row[0], dict) else json.loads(row[0]))
        return True, None
    except Exception as e:
        _warn_once(f"state read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False, None


def load_state(bot):
    """Return the bot's saved state dict (from save_state), or None. Never raises.

    NOTE: None means "no state OR the read failed" — see load_state_checked().
    """
    return load_state_checked(bot)[1]


def load_state_required(bot, tries=3, sleep_s=60.0):
    """Boot-time restore for a daemon that save_state()s durable state each loop.

    [2026-08-04] The seed-on-failed-read class, ONE home instead of a copy per
    bot (a second copy of a rule is a second rule): a bot that boots with
    `load_state(bot) or fresh` cannot tell a Postgres blip from a first run, so
    a blip at boot starts a fresh book whose very next save_state OVERWRITES
    the durable record. The sniper's 17-Jul fix established the degrade; this
    is that degrade, callable.

    Semantics:
      * no DATABASE_URL         -> None, immediately. Nothing durable exists to
        protect, and nothing CAN be overwritten — save_state needs the same DB
        — so a fresh in-memory book is safe (local smoke / selftests / inert
        backtests keep working).
      * read OK                 -> the state dict, or None for genuinely-no-row.
      * read FAILS `tries` times (sleep_s between) -> SystemExit. Crash-loop
        LOUDLY — Railway restarts us, the watchdog sees the stale row — rather
        than silently poison the book. A blip clears, so the loop is
        self-healing; this is not the forbidden exit-as-retirement shape.
    """
    if not _DATABASE_URL:
        return None
    for try_n in range(1, max(1, int(tries)) + 1):
        ok, saved = load_state_checked(bot)
        if ok:
            return saved
        print(f"[bot_pnl_store] {bot}: state read FAILED (try {try_n}/{tries})"
              " — NOT seeding: an unreadable state is indistinguishable from a"
              " fresh bot, and seeding now would let the next save_state"
              " overwrite the durable record.", flush=True)
        if try_n < tries:
            time.sleep(max(0.0, float(sleep_s)))
    raise SystemExit(
        f"{bot}: durable state unreadable after {tries} tries — refusing to "
        "run rather than seed a fresh book over a blip (load_state_required).")


def fetch_states(keys):
    """[2026-07-15 BLOODSTREAM] Batch read: {key: state_dict} for many keys in
    ONE query instead of N round-trips. Organs that read a fistful of bus keys
    per cycle (immune, respiration, regen, evidence board) get their whole
    working set in a single beat. Missing keys are simply absent from the
    result. Returns {} on any failure — callers fall back to load_state /
    defaults, so this is a pure optimization with the same fail-safe contract."""
    keys = [k for k in (keys or []) if k]
    if not keys:
        return {}
    conn = _get_conn()
    if conn is None:
        return {}
    try:
        _ensure_state_table(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT bot, state FROM bot_state WHERE bot = ANY(%s)",
                        (list(keys),))
            out = {}
            for k, v in cur.fetchall():
                if v is None:
                    continue
                out[k] = v if isinstance(v, dict) else json.loads(v)
        return out
    except Exception as e:
        _warn_once(f"batch state read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return {}


_trades_table_ready = False


def _ensure_trades_table(conn):
    """Per-trade history table. Keyed by (bot, open_ts, pair) — stable across
    redeploys. Pair is included so two bots entering the same coin at the same
    candle time never collide on the PK."""
    global _trades_table_ready
    if _trades_table_ready:
        return
    with conn.cursor() as cur:
        # [2026-07-06] Migrate old (bot, open_ts) PK -> (bot, open_ts, pair).
        # Recreate the table if the old constraint exists to fix cross-bot collisions.
        cur.execute("""
            DO $$
            BEGIN
                IF EXISTS (
                    SELECT 1 FROM information_schema.table_constraints
                    WHERE table_name = 'bot_trades'
                    AND constraint_type = 'PRIMARY KEY'
                ) THEN
                    -- Check if pair is NOT already in the PK
                    IF NOT EXISTS (
                        SELECT 1 FROM information_schema.key_column_usage
                        WHERE table_name = 'bot_trades'
                        AND constraint_name = (
                            SELECT constraint_name FROM information_schema.table_constraints
                            WHERE table_name = 'bot_trades' AND constraint_type = 'PRIMARY KEY'
                        )
                        AND column_name = 'pair'
                    ) THEN
                        DROP TABLE bot_trades;
                    END IF;
                END IF;
            END
            $$;
        """)
        conn.commit()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_trades (
                bot           TEXT NOT NULL,
                open_ts       TIMESTAMPTZ NOT NULL,
                pair          TEXT,
                is_open       BOOLEAN,
                profit_ratio  DOUBLE PRECISION,
                profit_abs    DOUBLE PRECISION,
                close_ts      TIMESTAMPTZ,
                open_rate     DOUBLE PRECISION,
                close_rate    DOUBLE PRECISION,
                amount        DOUBLE PRECISION,
                stake_amount  DOUBLE PRECISION,
                duration_min  DOUBLE PRECISION,
                enter_tag     TEXT,
                exit_reason   TEXT,
                leverage      DOUBLE PRECISION,
                seen_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (bot, open_ts, pair)
            )
            """
        )
    _trades_table_ready = True


def publish_trades(bot, trades):
    """Idempotently upsert a list of freqtrade trade dicts (from /api/v1/trades).
    Safe to call every loop; only changed/closed rows actually move. Never raises."""
    conn = _get_conn()
    if conn is None or not trades:
        return 0
    try:
        _ensure_trades_table(conn)
        n = 0
        with conn.cursor() as cur:
            for t in trades:
                open_ts = t.get("open_date") or t.get("open_timestamp")
                if open_ts is None:
                    continue
                cur.execute(
                    """
                    INSERT INTO bot_trades (bot, open_ts, pair, is_open,
                        profit_ratio, profit_abs, close_ts, open_rate, close_rate,
                        amount, stake_amount, duration_min, enter_tag, exit_reason,
                        leverage, seen_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, now())
                    ON CONFLICT (bot, open_ts, pair) DO UPDATE SET
                        is_open=EXCLUDED.is_open, profit_ratio=EXCLUDED.profit_ratio,
                        profit_abs=EXCLUDED.profit_abs, close_ts=EXCLUDED.close_ts,
                        close_rate=EXCLUDED.close_rate, duration_min=EXCLUDED.duration_min,
                        exit_reason=EXCLUDED.exit_reason, seen_at=now()
                    """,
                    (bot, _ts(open_ts), t.get("pair"), t.get("is_open"),
                     t.get("profit_ratio"), t.get("profit_abs"),
                     _ts(t.get("close_date") or t.get("close_timestamp")),
                     t.get("open_rate"), t.get("close_rate"), t.get("amount"),
                     t.get("stake_amount"),
                     (t.get("trade_duration") if t.get("trade_duration") is not None
                      else _dur_min(t)),
                     t.get("enter_tag"), t.get("exit_reason"), t.get("leverage")),
                )
                n += 1
        return n
    except Exception as e:  # noqa: BLE001
        _warn_once(f"trade write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return 0


def _ts(v):
    """Accept ISO string or epoch ms/s -> something psycopg2 stores as timestamptz."""
    if v is None:
        return None
    if isinstance(v, (int, float)):
        # freqtrade timestamps are epoch milliseconds
        from datetime import datetime, timezone
        sec = v / 1000.0 if v > 1e12 else v
        return datetime.fromtimestamp(sec, tz=timezone.utc)
    return v  # ISO8601 string; Postgres parses it


def _dur_min(t):
    o = t.get("open_timestamp"); c = t.get("close_timestamp")
    if isinstance(o, (int, float)) and isinstance(c, (int, float)):
        return (c - o) / 60000.0
    return None


def fetch_trades(strategy_bot_names):
    """Return closed trades for the given bot names (list) as dicts, newest first.
    Used by the analyzer. Returns [] if DB unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT bot, open_ts, pair, profit_ratio, profit_abs, close_ts,
                       duration_min, enter_tag, exit_reason
                FROM bot_trades
                -- [2026-07-29 AUDIT] IS NOT TRUE, not = FALSE: the (ea)
                -- union doctrine (NULL is_open == closed) reached every
                -- dashboard reader but skipped this one — trade_analyzer
                -- silently dropped NULL-is_open closed rows.
                WHERE bot = ANY(%s) AND is_open IS NOT TRUE
                ORDER BY close_ts DESC NULLS LAST
                """,
                (list(strategy_bot_names),),
            )
            cols = [d[0] for d in cur.description]
            return [dict(zip(cols, row)) for row in cur.fetchall()]
    except Exception as e:  # noqa: BLE001
        _warn_once(f"trade read failed ({e})")
        return []


def store_analysis(strategy, payload):
    """Persist the latest per-strategy analysis JSON for later viewing."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS bot_trade_analysis (
                    strategy   TEXT PRIMARY KEY,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
                    analysis   JSONB
                )
                """
            )
            cur.execute(
                """
                INSERT INTO bot_trade_analysis (strategy, updated_at, analysis)
                VALUES (%s, now(), %s)
                ON CONFLICT (strategy) DO UPDATE SET
                    updated_at=now(), analysis=EXCLUDED.analysis
                """,
                (strategy, json.dumps(payload)),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"analysis write failed ({e})")
        return False


# --------------------------------------------------------------------------- #
# Durable paper-trade ledger (2026-06-25)
#
# Bots that compute their cumulative P&L by re-reading a LOCAL csv each loop
# (e.g. listing_sniper.py reading sniper_trades.csv) silently reset to $0 / 0
# closed whenever that ephemeral file is wiped on a Railway redeploy — which is
# exactly what happened on 2026-06-24/25 (listing-sniper: -$300/6 closed -> 0/0).
# This table persists each closed paper trade in Postgres, keyed by a caller-
# supplied stable id, so the cumulative aggregate survives restarts. Idempotent.
# --------------------------------------------------------------------------- #
_paper_trades_table_ready = False


def _ensure_paper_trades_table(conn):
    global _paper_trades_table_ready
    if _paper_trades_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS paper_trades (
                bot        TEXT NOT NULL,
                trade_id   TEXT NOT NULL,
                pair       TEXT,
                pnl_abs    DOUBLE PRECISION,
                pnl_pct    DOUBLE PRECISION,
                opened_at  TEXT,
                closed_at  TEXT,
                reason     TEXT,
                seen_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
                PRIMARY KEY (bot, trade_id)
            )
            """
        )
        # [2026-07-09 LIGHTER GATE-0] venue provenance so shadow/testnet/live
        # rows are queryable apart from the HL paper era (venue NULL = hl paper).
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS venue TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS shadow BOOLEAN")
        # [2026-07-15 EVIDENCE] learning-layer widening (revives the 7-Jul
        # b82c5aa design that never reached the deployed line): WHERE the trade
        # happened (prices/size/side), the publisher's own tag, and a JSONB
        # extra for entry-time context (e.g. the sniper's book microstructure).
        # side='skip' is reserved for gate-rejection log rows — every trade
        # reader must exclude it (fetch_paper_trades does; per-bot aggregates
        # are safe because skips publish under a separate '<bot>-skips' name).
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS side TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS tag TEXT")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS entry_price DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS exit_price DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS size DOUBLE PRECISION")
        cur.execute("ALTER TABLE paper_trades ADD COLUMN IF NOT EXISTS extra JSONB")
    _paper_trades_table_ready = True


def publish_paper_trade(bot, trade_id, pnl_abs, pnl_pct=None, pair=None,
                        opened_at=None, closed_at=None, reason=None,
                        venue=None, shadow=None, side=None, tag=None,
                        entry_price=None, exit_price=None, size=None,
                        extra=None):
    """Idempotently record one closed paper trade so cumulative P&L survives a
    redeploy. `trade_id` must be stable+unique for the trade. Never raises.
    [2026-07-15 EVIDENCE] optional learning fields: side ('long'/'short', or
    'skip' for gate-rejection logs), publisher tag, entry/exit price, size, and
    a JSON-able `extra` dict for entry-time context."""
    conn = _get_conn()
    if conn is None or trade_id is None:
        return False
    # [2026-07-28 REVIEW] Stamp extra.build on the CLOSE ROW too. The
    # experiment judge's arm-drift gate reads builds off paper_trades rows
    # (one snapshot with the numbers it gates) — but only bot_pnl publishes
    # were ever stamped, so 0 of 143 all-time Farmer rows carried a build and
    # the drift HOLD structurally could not fire while the two arms ran
    # different code. Forward-only; _stamp_build never raises and never
    # overwrites a caller's key.
    extra = _stamp_build(extra)
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO paper_trades (bot, trade_id, pair, pnl_abs, pnl_pct,
                    opened_at, closed_at, reason, venue, shadow, side, tag,
                    entry_price, exit_price, size, extra, seen_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                        %s, %s, %s, %s, now())
                ON CONFLICT (bot, trade_id) DO UPDATE SET
                    pnl_abs=EXCLUDED.pnl_abs, pnl_pct=EXCLUDED.pnl_pct,
                    closed_at=EXCLUDED.closed_at, reason=EXCLUDED.reason,
                    venue=EXCLUDED.venue, shadow=EXCLUDED.shadow,
                    side=EXCLUDED.side, tag=EXCLUDED.tag,
                    entry_price=EXCLUDED.entry_price,
                    exit_price=EXCLUDED.exit_price, size=EXCLUDED.size,
                    -- [2026-07-28 AUDIT FIX] the FIRST build stamp is the
                    -- truth about which code CLOSED the trade: a documented-
                    -- idempotent re-publish after a redeploy (the recovery
                    -- pattern this table exists for) used to restamp an old
                    -- close with the NEW build id, corrupting the judge's
                    -- row-based arm-drift evidence. Preserve it on conflict.
                    extra=CASE
                        WHEN paper_trades.extra ? 'build'
                        THEN jsonb_set(COALESCE(EXCLUDED.extra, '{}'::jsonb),
                                       '{build}', paper_trades.extra->'build')
                        ELSE EXCLUDED.extra
                    END,
                    seen_at=now()
                """,
                (bot, str(trade_id), pair, pnl_abs, pnl_pct,
                 opened_at, closed_at, reason, venue, shadow, side, tag,
                 entry_price, exit_price, size,
                 # [2026-08-05 (kh)] SANITISED — this was a bare
                 # `json.dumps(extra)` and it is a hole in I5's OWN declared
                 # enforcement. I5 says "non-finite floats must never reach
                 # storage" and names `json_safe` as the guard; `save_state`
                 # uses it (`json.dumps(json_safe(state), allow_nan=False)`)
                 # and THE CLOSE LEDGER DID NOT.
                 #
                 # Why this site is the worst of the three: `json.dumps` emits
                 # bare `NaN`/`Infinity`, Postgres `jsonb` REJECTS the whole
                 # statement, and this function never raises — so the close row
                 # is silently LOST. Not a stale row a reader can spot by its
                 # age: a trade that happened and left no record, in the
                 # ledger that IS the fleet's evidence base. `extra` here
                 # routinely carries ratios, APRs and t-stats — precisely the
                 # fields I5 was written about.
                 json.dumps(json_safe(extra), allow_nan=False)
                 if extra is not None else None),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def fetch_paper_aggregate(bot):
    """Return {'realized','closed','wins','losses'} from the durable ledger, or
    None if the DB is unavailable. Lets a bot recover its cumulative totals after
    a local-file wipe."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(pnl_abs), 0.0),
                       COUNT(*),
                       COUNT(*) FILTER (WHERE pnl_abs > 0),
                       COUNT(*) FILTER (WHERE pnl_abs = 0
                                     OR extra->>'non_economic' = 'true')
                FROM paper_trades WHERE bot = %s
                """,
                (bot,),
            )
            # 4th column is a CANDIDATE count, not a verdict: `is_non_economic`
            # still decides. It exists so a clean book pays ONE round trip —
            # the contract `test_a_clean_book_is_untouched_and_asks_no_second_query`
            # pins, and which the first draft of this pass broke.
            _agg = cur.fetchone() or (0.0, 0, 0, 0)
            realized, closed, wins = _agg[0], _agg[1], _agg[2]
            _cand = int(_agg[3] or 0) if len(_agg) > 3 else 0
        closed = int(closed or 0)
        wins = int(wins or 0)
        realized = float(realized or 0.0)
        # [2026-08-19 fleet audit] THE QUARANTINE HAD TO REACH THIS PATH TOO.
        # `fetch_paper_trades` below withholds LEDGER_QUARANTINE rows from
        # every GRADING consumer (gate, brain, allocation, exit studies); this
        # aggregate — the SEED a book re-reads at boot to recover its own
        # cumulative totals — was raw SQL over the same table with no such
        # filter. So the two answers disagreed about the same ledger, and the
        # book's OWN published numbers carried what the fleet had already
        # ruled inadmissible: 🧘 douglas re-seeded the two (nm)/(pv) void rows
        # (phantom boot-frozen entry marks the venue never offered) on EVERY
        # reboot, publishing pnl_abs -$24.68 / 8 closes against a graded record
        # of +$1.81 / 6 closes — a $26.48 disagreement, permanent and
        # self-healing in the wrong direction.
        # `is_quarantined` stays the ONE owner of the question (a second copy
        # of the rule is a second rule, (hj)); the pre-filter on `pair` is only
        # a cheap way to avoid scanning a whole ledger to ask it. Fail-OPEN is
        # inherited: an unparseable row is ADMITTED, so this can never silently
        # shrink a book's totals beyond the declared windows.
        # [2026-08-27 (tw)] EVENTS ARE NOT TRADES — the same withholding
        # shape as the quarantine pass below, and for the same reason. A
        # halt/flatten row has no basis (no entry price, no P&L) and was
        # counted here as a CLOSE and, via `losses = closed - wins`, as a
        # LOSS: 🙏 avo published 3W/10L over 13 "closes" on a book that had
        # taken 4 real trades. The book re-seeds these counters from this
        # aggregate at every boot, so the miscount was self-healing in the
        # wrong direction.
        #
        # SQL narrows to CANDIDATES cheaply; `is_non_economic` DECIDES. The
        # predicate is written once, in the owner ((hj)) — an earlier draft
        # of this pass re-expressed it as a SQL FILTER and immediately
        # drifted from it (three of the five funding-form keys), which is
        # the second-copy failure in miniature.
        #
        # `realized` is deliberately NOT adjusted: an event's P&L is 0.00 by
        # definition, so equity and pnl_abs cannot move — only the COUNTS.
        try:
            with conn.cursor() as cur:
                if not _cand:
                    raise StopIteration           # no candidates: no 2nd query
                cur.execute(
                    "SELECT pnl_abs, entry_price, extra FROM paper_trades "
                    "WHERE bot = %s AND (pnl_abs = 0 "
                    "      OR extra->>'non_economic' = 'true')",
                    (bot,),
                )
                cand = cur.fetchall()
            n_events = sum(1 for _p, _e, _x in cand
                           if is_non_economic(_p, _e, _x))
            if n_events:
                closed -= n_events
                # an event never has pnl > 0, so it was never in `wins`;
                # subtracting it from `closed` alone is what turns a phantom
                # LOSS back into nothing at all.
        except StopIteration:
            pass
        except Exception as e:  # noqa: BLE001
            _warn_once(f"paper-aggregate event filter failed ({e})")

        try:
            q_pairs = sorted({str(qp) for qp, qb, _lo, _hi, _why
                              in LEDGER_QUARANTINE if qb in str(bot or "")})
            if q_pairs:
                with conn.cursor() as cur:
                    cur.execute(
                        "SELECT pair, closed_at, pnl_abs FROM paper_trades "
                        "WHERE bot = %s AND pair = ANY(%s)",
                        (bot, q_pairs),
                    )
                    rows = cur.fetchall()
                for pair, closed_at, pnl in rows:
                    if not is_quarantined(bot, pair, closed_at):
                        continue
                    pnl = float(pnl or 0.0)
                    realized -= pnl
                    closed -= 1
                    if pnl > 0:
                        wins -= 1
        except Exception as e:  # noqa: BLE001
            # Never let the withholding pass break the recovery it refines:
            # an unfiltered total beats no total at all (the seed's whole job
            # is surviving a local-file wipe).
            _warn_once(f"paper-aggregate quarantine filter failed ({e})")
        return {"realized": realized, "closed": max(0, closed),
                "wins": max(0, wins), "losses": max(0, closed - wins)}
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade read failed ({e})")
        return None


def split_reason(reason):
    """(enter_tag | None, exit_reason) from a paper-ledger close `reason`.

    [2026-07-14 TAG-SEMANTICS FIX] Only a real direction prefix
    (long_/short_) carries entry info. Splitting EVERY reason made exit
    reasons masquerade as entry modes — funding-carry's 'flip' and the
    sniper's 'delisted' became enter_tags, and the brain spent 92 runs
    proposing to "tighten the 'flip' entry gates" (an exit path, not an
    entry). No direction prefix -> untagged entry + the FULL reason kept as
    exit_reason (also fixes 'decay_paid' being mangled into 'decay'/'paid').
    [2026-07-15 AUDIT FIX] also accept the Ticket Taker's hyphenated
    side-lens tags ('long-breakout_tp' -> enter 'long-breakout', exit 'tp')
    — the underscore-only gate silently untagged every taker close.
    [2026-07-15 LEARNING-LOOP WIRING] the split is at the FIRST underscore,
    so composers must keep the tag part underscore-free — the family bot
    hyphenates its strategy tags ('long-bounce-pullback_<exit>', see
    lighter_family_bot.ledger_reason). This helper is the ONE parser those
    composers round-trip against."""
    reason = reason or ""
    if reason.startswith(("long_", "short_", "long-", "short-")):
        direction, _sep, exit_reason = reason.partition("_")
        return (direction or None), (exit_reason or "trade")
    return None, (reason or "trade")


# [2026-07-31 (hr)] THE LEDGER QUARANTINE — rows that are real trades but not
# EVIDENCE. Every entry needs a measured reason and a bounded window; this is
# not a place to hide losses.
#
# BOT/USDC 21-22 Jul: the venue's mark sat ~747 bps from its own book top (mean
# |px_fill/px_decision-1| over 93 orders, against a ~9 bps ledger median), so a
# short opened at the book fill was born ~+7.5% in profit ON THE MARK BASIS,
# tripped its take-profit on the very next 5-minute cycle, and closed by
# crossing an 81.9 bps spread at a loss. `pos.pop()` freed the slot and the
# SL cooldown only gates re-entry after an `sl`, so it re-entered every loop:
# 43 closes in 4.5 hours, 42 of them with close[i] == open[i+1] TO THE SECOND.
# ONE EPISODE, not 43 trades — and it supplied 45 of the 98 rows in every
# pooled short-divergence grade the fleet has ever computed.
# CXMT is the mirror case that proves the mechanism rather than a second bug: a
# `short-divergence_sl` that booked +$0.4242 on a -735 bps decision-vs-fill gap.
#
# NOT swept, deliberately: the two 20-Jul BOT `long-divergence_sl` rows (gaps
# 47.9 and 87.2 bps) are GENUINE stops on a normal book and stay in the sample.
# The window is closed and dated for that reason.
LEDGER_QUARANTINE = (
    # (pair, bot-substring, first_utc_date, last_utc_date, why)
    ("BOT/USDC", "ticket-taker", "2026-07-21", "2026-07-22",
     "mark ~747bps off the book top -> instant phantom TP, 43 closes in 4.5h; "
     "one episode, not 43 trades (hm)"),
    # [2026-08-15 (ne)] window 21..22 -> 28..28: the entry was MIS-DATED from
    # birth — the row its own comment describes (+$0.4242) closed 28-Jul, and
    # the 21..22 window contained ZERO CXMT rows, so is_quarantined admitted
    # the defective row into every graded taker sample for 18 days. Found by
    # the X1 census, adversarially confirmed (the ledger has exactly one such
    # row). The 16-Jul and 30-Jul CXMT rows are genuine stops and stay.
    ("CXMT/USDC", "ticket-taker", "2026-07-28", "2026-07-28",
     "same basis defect, mirrored: an _sl that booked +$0.42 (hm)"),
    # [2026-08-18 (pv)] THE PRE-(nm) FROZEN-MARK ENTRIES. `(nm)` measured both
    # of these against the venue's own 1h bars and ruled them "void rather
    # than a -3.5R signal" — and then wired that verdict into nothing, so
    # every grader kept counting them. `funding_map()` served a mark frozen at
    # client construction, so the ENTRY was booked at a price the venue never
    # offered while the exit was a real contemporaneous one; the gap between
    # the two vintages IS the loss. ROBO's real 12:04->13:35 move was -6.7%,
    # INSIDE its own 7.03% stop — the stop fired on a phantom loss at a
    # phantom entry. Both closed in the same loop tick (13:35:41.02/.14) after
    # opening 8.5h apart, which is the frozen mark unfreezing at a restart.
    # Between them they are 97% of this book's realised record (-$26.48 of
    # -$23.84 net), so leaving them in makes its ~12-Sep grade meaningless.
    # SCOPED TO THE TWO MEASURED ROWS, not to "everything pre-(nm)": (nm)'s own
    # in-place correction refuted that inference — 🧙 Schwager's four legs all
    # priced INSIDE their bars, because the frozen mark's error grows with
    # container uptime. The 17-Aug closes are on the fixed build and stay.
    ("ROBO", "douglas", "2026-08-15", "2026-08-15",
     "pre-(nm) frozen boot mark: entry 0.017707 vs the 12:00 bar's "
     "[0.014507, 0.014938] — 21% above the whole hour's high; real move was "
     "-6.7%, inside its own 7.03% stop (nm)"),
    ("LINK", "douglas", "2026-08-15", "2026-08-15",
     "pre-(nm) frozen boot mark: entry 9.15316 vs the 03:00 bar's "
     "[9.53046, 9.74586] — below the hour's low, matches ~01:00; realised "
     "-3.31% against a 0.888% stop, 3.73x (nm)"),
    # [2026-08-18 (qc)] NOT A TRADE AT ALL: a full-suite pytest run in a shell
    # carrying `export DATABASE_URL` let a parliament book test publish its
    # FIXTURE close through the real path (parliament/strategies.py publishes
    # whenever the env is set). Entry 100.01 is the fixture price; +$1.27 "tp"
    # in 2.2 seconds on a book the red-stop slate kept alive BECAUSE it was
    # positive. The class is closed at the root conftest (the env strip); this
    # entry withholds the one row that landed. Deleting the row outright is an
    # operator call — until then every grader must not see it.
    ("BTC/USD", "pm-albanese", "2026-08-18", "2026-08-18",
     "fabricated by a test run with DATABASE_URL exported: fixture entry "
     "100.01, +5.09% in 2.2s; not a trade (qc)"),
)


# The funding form: a funding book books ACCRUAL, never a price, so its
# price-free rows are real trades and must never match the event signature.
_FUNDING_FORM = ("entry_apr", "exit_apr", "accrued", "held_h", "fees")


def is_non_economic(pnl_abs, entry_price, extra):
    """True when a ledger row records an EVENT, not a TRADE.

    [2026-08-27 (tw)] A daily-loss halt flattens positions the book cannot
    attest — no entry basis, no P&L — and `publish_paper_trade` wrote them
    into the closed-trade ledger anyway. `fetch_paper_aggregate` then counted
    every one as a CLOSE and, because `losses = closed - wins`, as a LOSS.

    Measured on the two real-money books: 🙏 avo published **3W / 10L on 13
    closes** where the book had taken **4 real trades (3W / 1L)** — 9 of 13
    "trades" were the 23/24-Aug flatten events — and 🔮 georgia 24W / 28L on
    52 where the real record is 24W / 24L. The dashboard, the daily review
    and every W/L reader has been reading a real-money book's record with
    phantom losses in it, and the book itself re-seeds those counters from
    this aggregate at every boot.

    THE DISTINCTION IS NOT THE REASON STRING, and that is the whole care
    needed here: `daily_loss` appears on BOTH. georgia's 25-Aug rail closed
    five REAL positions at real prices for -$30.96, and her 22-Aug TRX
    -$3.87 is a real forced flatten; those are losses the book genuinely
    took and they MUST stay in the sample. The events are the rows with **no
    basis at all**:

      * `extra.non_economic is True` — the (th) write-site marker. This is
        the forward CONTRACT and the only exact test.
      * the LEGACY BRIDGE, declared rather than permanent: pnl == 0 AND no
        entry price AND no funding form. The 13 rows above predate the
        marker and no DB row carries it yet, so without this they would
        stay miscounted forever.

    The bridge's blast radius was MEASURED before it shipped, not assumed:
    fleet-wide, `pnl == 0 AND entry_price IS NULL` matches **exactly those
    13 rows and nothing else**. Funding books are the population that could
    have been hurt — they legitimately record no price — and they have
    **zero** zero-P&L rows (carry 0 of 105, farmer-shadow 0 of 215, garrett
    0 of 56), so the conjunction cannot fire on them today. `_FUNDING_FORM`
    makes that structural rather than lucky: a row carrying accrual
    telemetry is a funding TRADE whatever its P&L rounds to.

    Fail-OPEN on anything unparseable — a row that cannot be classified is
    ADMITTED as a trade. A filter that swallows what it cannot read would
    silently shrink the samples it touches, which is the disease and not the
    cure (`is_quarantined`'s contract, verbatim, for the same reason).
    """
    try:
        # ABSENT and UNREADABLE are different, and collapsing them is the
        # same class again: `extra if isinstance(extra, dict) else {}` reads
        # a malformed extra as "no funding telemetry", which is an
        # ASSUMPTION about data it could not parse. None is genuinely empty;
        # anything else non-dict is unreadable, so fail-OPEN and admit.
        if extra is None:
            ex = {}
        elif isinstance(extra, dict):
            ex = extra
        else:
            return False
        if ex.get("non_economic") is True:
            return True
        # `float(pnl_abs or 0.0)` would coerce a MISSING P&L to zero — the
        # very "fabricate what you do not know" class this owner exists to
        # close, reproduced inside it. Caught by its own test before it
        # shipped. An unknown P&L is NOT a zero P&L: admit the row.
        if pnl_abs is None or float(pnl_abs) != 0.0:
            return False
        if entry_price is not None:
            return False
        if any(k in ex for k in _FUNDING_FORM):
            return False
        return True
    except Exception:  # noqa: BLE001
        return False


def is_quarantined(bot, pair, closed_at):
    """True when this row is a real trade but NOT admissible evidence.

    Fail-OPEN: anything unparseable is ADMITTED. A quarantine that swallows
    rows it cannot classify would silently shrink every sample it touches,
    which is the disease, not the cure.
    """
    try:
        b, p = str(bot or ""), str(pair or "")
        d = str(closed_at or "")[:10]
        if len(d) != 10:
            return False
        for q_pair, q_bot, lo, hi, _why in LEDGER_QUARANTINE:
            if p == q_pair and q_bot in b and lo <= d <= hi:
                return True
    except Exception:  # noqa: BLE001
        return False
    return False


def fetch_paper_trades(limit=2000):
    """Per-trade rows from the durable paper_trades ledger (perps + sniper),
    normalized to the SAME shape bot_learn expects from the freqtrade /trades.json
    feed — so the learning brain can analyse the whole fleet, not just the
    freqtrade bots. The stored `reason` is '<direction>_<exit>' (e.g.
    'long_range_high', 'short_stop'); we split it so the brain gets enter_tag
    (long/short) AND exit_reason. Returns [] if the DB is unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_paper_trades_table(conn)
        with conn.cursor() as cur:
            # [2026-07-15 EVIDENCE] side='skip' rows are gate-rejection logs
            # (sniper), not trades — they must never reach the brain/analyzer.
            # [2026-07-16] `extra` carries the arm's PROOF-OF-APPLICATION
            # receipt (extra.bars, stamped only inside the bot's apply_levers).
            # It was written since 15-Jul and never selected, so the experiment
            # judge — whose docstring already relies on it ("Every close row
            # carries extra.bars") — could not see which params produced a
            # close, and scored an arm that ignores its levers. Additive: every
            # other consumer ignores unknown keys.
            # [2026-07-17 DRIFT PLUMBING] venue/entry_price/exit_price were in
            # the table since day one and NEVER selected, so every paper row
            # reached the brain with open_rate/close_rate = None. bot_learn's
            # _post_exit_drift needs both rates and returned None at its guard
            # for ALL 409 recent losers on the living fleet — drift evidence was
            # 0 of 409, silently, because the fetch dropped the columns rather
            # than because the data was missing. `venue` comes along so a
            # consumer can grade a trade on the venue it actually happened on
            # (the brain now refuses to price a Lighter close off any other
            # book). Additive, like the 16-Jul `extra` fix above: every other
            # consumer ignores unknown keys.
            # [2026-07-21 AUDIT FIX] `tag` joins the SELECT: the (bb) "brain
            # jurisdiction over the Farmer" change stamps tag on every
            # Farmer close, but this fetch — the brain's ONLY paper-ledger
            # ingest — never selected the column, so the stamped tag reached
            # no consumer and the jurisdiction was a silent no-op (the same
            # written-but-never-SELECTed class as the 17-Jul entry_price/
            # exit_price fix directly above). Additive as ever.
            cur.execute(
                "SELECT bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, "
                "reason, extra, venue, entry_price, exit_price, tag "
                "FROM paper_trades WHERE side IS DISTINCT FROM 'skip' "
                "ORDER BY closed_at DESC NULLS LAST LIMIT %s",
                (int(limit),),
            )
            rows = cur.fetchall()
        from datetime import datetime
        out = []
        _quarantined = 0
        for (bot, pair, pnl_abs, pnl_pct, opened_at, closed_at, reason,
             extra, venue, entry_price, exit_price, tag) in rows:
            # [(hr)] real trades, not evidence — see LEDGER_QUARANTINE.
            if is_quarantined(bot, pair, closed_at):
                _quarantined += 1
                continue
            direction, exit_reason = split_reason(reason)
            # a stored tag is richer than the reason prefix ('long-funding'
            # beats 'long'); split_reason strips any '_exit' suffix a
            # publisher folded in (the Parliament stamps tag=full_tag), so
            # the bucket key is always entry-side only. Reason-derived
            # direction stays the fallback for pre-stamp rows.
            if tag:
                _tdir, _ = split_reason(tag)
                direction = _tdir or direction
            # [2026-07-15 AUDIT FIX] tolerant timestamp parse — the listing
            # sniper writes '2026-07-13 15:05:04 UTC', which fromisoformat
            # rejects, so its 337 rows carried duration_min=None forever.
            def _pts(s):
                s = str(s).strip().replace("Z", "+00:00")
                if s.endswith(" UTC"):
                    s = s[:-4] + "+00:00"
                return datetime.fromisoformat(s)
            dur = None
            try:
                if opened_at and closed_at:
                    dur = max(0.0, (_pts(closed_at) - _pts(opened_at))
                              .total_seconds() / 60.0)
            except Exception:
                dur = None
            def _rate(x):
                # None stays None: a missing fill price must read as ABSENT
                # evidence, never as 0.0 (which would look like a real price).
                try:
                    return float(x) if x is not None else None
                except (TypeError, ValueError):
                    return None
            out.append({
                "bot": bot, "pair": pair,
                "profit_abs": float(pnl_abs) if pnl_abs is not None else 0.0,
                "profit_ratio": pnl_pct,
                "enter_tag": direction or None,   # None -> brain's "(untagged)"
                "exit_reason": exit_reason or "trade",
                "duration_min": dur,
                "open_ts": opened_at, "close_ts": closed_at,
                "is_open": False,
                # [2026-07-17] the venue this trade actually executed on
                # ('lighter' | None for the CEX sniper / HL-data carry book).
                "venue": venue,
                # freqtrade's names, so a paper row and a bot_trades row carry
                # rates under the SAME keys (bot_learn reads open_rate /
                # close_rate for both).
                "open_rate": _rate(entry_price),
                "close_rate": _rate(exit_price),
                # dict or {} — never None, so consumers can .get() safely
                "extra": extra if isinstance(extra, dict) else {},
            })
        if _quarantined:
            print(f"[bot_pnl_store] ledger quarantine: {_quarantined} row(s) "
                  f"withheld from grading (see LEDGER_QUARANTINE) — real trades, "
                  f"not admissible evidence", flush=True)
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"paper-trade fetch failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return []


def _selftest_build():
    """The build-id contract. It had its own module and its own suite for ten
    minutes; the born-dark guard sent it in here, so the suite comes too — a
    guard that moves house without its tests is how `brain_stats` shipped."""
    global _BUILD_ROOT, _BUILD_SHARED, _BUILD_CACHE
    import tempfile
    a, n = build_compute(__file__)
    assert a and n >= 2, (a, n)
    assert build_compute(__file__)[0] == a, "must be deterministic across calls"

    # THE CONTRACT: different bytes -> different id. Without this the detector
    # reports agreement between two drifted arms — a green light on the judge's
    # invalid promotion bar, which is worse than having no detector.
    with tempfile.TemporaryDirectory() as d:
        m = os.path.join(d, "m.py")
        open(m, "w").write("x = 1\n")
        b1, _ = build_compute(m)
        open(m, "w").write("x = 2\n")
        b2, _ = build_compute(m)
        assert b1 and b2, f"a readable entry must yield an id: {b1!r}/{b2!r}"
        assert b1 != b2, "a byte change MUST change the id"

    # SAME bytes, DIFFERENT path -> SAME id. This is production: the live arm
    # runs /app/<mod>.py, the shadow arm /freqtrade/<mod>.py. Keying on the
    # absolute path would flag permanent drift between identical code.
    with tempfile.TemporaryDirectory() as d1, tempfile.TemporaryDirectory() as d2:
        for d in (d1, d2):
            open(os.path.join(d, "arm.py"), "w").write("SAME = 'bytes'\n")
        i1, _ = build_compute(os.path.join(d1, "arm.py"))
        i2, _ = build_compute(os.path.join(d2, "arm.py"))
        assert i1 and i1 == i2, f"same bytes must agree across paths: {i1} vs {i2}"

    # The ENTRY MODULE COUNTS — two bots sharing venues/ are NOT one build.
    # Asserted with a file that is NOT already in _BUILD_SHARED: this module is
    # both the entry and a shared file, so compute(__file__) == the shared-only
    # id and the naive form of this check passes vacuously. A fixture that can
    # only pass is not a fixture (`tests-must-not-fail-on-good-news`, inverted).
    _probe = os.path.join(_BUILD_ROOT, "implementation_shortfall.py")
    if os.path.isfile(_probe):
        _with = build_compute(_probe)[0]
        _without = build_compute(os.path.join(_BUILD_ROOT, "nope.py"))[0]
        assert _with and _without and _with != _without, \
            f"the entry file must change the id: {_with} vs {_without}"

    # [2026-07-29 (fd) THE SHORT-SET INCIDENT] A DECLARED-but-ABSENT shared file
    # is skipped silently. That is legitimate — images carry different subsets
    # on purpose (the shadow images never COPY fleet_tuning.py) — but it means
    # ONE source tree stamps TWO ids, and on the day fleet_tuning.py joined the
    # set a hash predicted from the repo read as "the deploy never landed" on a
    # perfectly converged shadow service. The id alone cannot say which set it
    # hashed. The COUNT can, so the count is published — and pinned here.
    _saved_bs = (_BUILD_ROOT, _BUILD_SHARED, _BUILD_CACHE)
    try:
        with tempfile.TemporaryDirectory() as d:
            _BUILD_ROOT, _BUILD_SHARED, _BUILD_CACHE = d, ("shared_a.py",), None
            open(os.path.join(d, "entry.py"), "w").write("E = 1\n")
            open(os.path.join(d, "shared_a.py"), "w").write("S = 1\n")
            _full, _nfull = build_compute(os.path.join(d, "entry.py"))
            os.remove(os.path.join(d, "shared_a.py"))
            _short, _nshort = build_compute(os.path.join(d, "entry.py"))
            assert (_nfull, _nshort) == (2, 1), (_nfull, _nshort)
            assert _full and _short and _full != _short, \
                "a missing shared file changes the id — silently, which is the trap"
            assert _nshort < _nfull, \
                "the COUNT is what makes a short set self-describing; publish it"
    finally:
        _BUILD_ROOT, _BUILD_SHARED, _BUILD_CACHE = _saved_bs

    # the stamp: adds `build` + `build_n`, preserves caller keys, never
    # overwrites one
    e = _stamp_build({"venue": "lighter_live"})
    assert e["build"] == build_code_id() and e["venue"] == "lighter_live", e
    assert e["build_n"] == build_code_files() == n, e
    assert _stamp_build(None)["build"] == build_code_id()
    assert _stamp_build({"build": "caller"})["build"] == "caller"
    assert _stamp_build({"build_n": 99})["build_n"] == 99, \
        "a caller's own key wins — build_n follows build's contract"
    # [2026-07-28 REVIEW] the PAPER-TRADE write path must stamp too — the
    # judge's arm-drift gate reads builds off paper_trades rows and was dark
    # for its whole life because only bot_pnl publishes were stamped (0/143
    # Farmer rows carried a build). The DB path can't run here, so pin the
    # call the way the drift guard pins env defaults: by source — on the
    # exact CALL expression, not the bare name (a docstring/comment mention
    # must never satisfy this; that near-miss was caught by its own mutation
    # run). Mutation check: deleting the call line reddens.
    import inspect as _ins
    assert "extra = _stamp_build(extra)" in _ins.getsource(publish_paper_trade), \
        "publish_paper_trade must stamp extra.build (arm-drift's row feed)"

    # ---- [2026-07-31 (ht)] SERVICE ATTRIBUTION -------------------------
    # The duplicate-writer guard names a CONTAINER; the operator has to stop a
    # SERVICE. Four entries reported "this repo cannot tell which of the two
    # publishes the row" while RAILWAY_SERVICE_NAME sat unread in every one.
    _saved_svc = os.environ.get("RAILWAY_SERVICE_NAME")
    try:
        os.environ["RAILWAY_SERVICE_NAME"] = "yield-harvester-shadow"
        assert service_name() == "yield-harvester-shadow"
        assert _stamp_build({})["svc"] == "yield-harvester-shadow", \
            "every publish must carry its service — this is the class fix"
        assert _stamp_build({"svc": "caller"})["svc"] == "caller", \
            "a caller's own key wins; svc follows build's contract"
        # UNKNOWN must degrade to absent, never to a name somebody might stop
        os.environ.pop("RAILWAY_SERVICE_NAME", None)
        assert service_name() == ""
        assert "svc" not in _stamp_build({}), \
            "an unknown service must be ABSENT, not blank-but-present"
        # the stamp must survive an unstampable build without losing svc
        os.environ["RAILWAY_SERVICE_NAME"] = "funding-carry"
        _sv_cache = _BUILD_CACHE
        try:
            globals()["_BUILD_CACHE"] = (None, 0)
            assert _stamp_build({})["svc"] == "funding-carry", \
                "build and service attribution are independent failures"
        finally:
            globals()["_BUILD_CACHE"] = _sv_cache
    finally:
        if _saved_svc is None:
            os.environ.pop("RAILWAY_SERVICE_NAME", None)
        else:
            os.environ["RAILWAY_SERVICE_NAME"] = _saved_svc

    # ---- [2026-07-31 (hx)] NaN MUST NOT SILENCE AN ORGAN'S MEMORY --------
    # `json.dumps` emits bare NaN/Infinity, which Postgres jsonb REJECTS. The
    # brain lost three days of memory to exactly this: runs frozen at 337 while
    # vitals published 338 every cycle.
    _nan, _inf = float("nan"), float("inf")
    _clean = json_safe({"t": _nan, "ok": 1.5, "deep": [{"x": -_inf}, {"y": 2}],
                        "s": "keep", "b": True, "n": None})
    assert _clean["t"] is None and _clean["deep"][0]["x"] is None, _clean
    assert _clean["ok"] == 1.5 and _clean["s"] == "keep" and _clean["b"] is True
    assert _clean["deep"][1]["y"] == 2 and _clean["n"] is None
    # the whole point: the sanitized payload must be VALID strict JSON
    json.dumps(json_safe({"t": _nan, "u": [_inf, -_inf]}), allow_nan=False)
    # ...and the raw one must not be, or this test proves nothing
    try:
        json.dumps({"t": _nan}, allow_nan=False)
        raise AssertionError("json.dumps must reject NaN in strict mode")
    except ValueError:
        pass
    # tuples become lists (jsonb has no tuple), non-str keys stringify
    assert json_safe((1, _nan)) == [1, None]
    assert json_safe({3: _nan}) == {"3": None}
    # depth-bounded: a self-referential blob must terminate, not hang, inside
    # a writer whose contract is "never raises"
    _cyc = {}
    _cyc["self"] = _cyc
    json_safe(_cyc)
    # save_state must ROUTE through it — a sanitizer nothing calls is a note
    assert "json_safe(state)" in _ins.getsource(save_state), \
        "save_state must sanitize before dumping"
    assert "allow_nan=False" in _ins.getsource(save_state), \
        "strict mode turns a leak into a loud error, not a silent DB reject"

    # describe_writer: the string the operator acts on
    assert describe_writer("abc123", "funding-carry") == "funding-carry (abc123)"
    assert describe_writer("abc123", None) == "abc123", \
        "a claim written before (ht) has no svc — degrade to the OLD string"
    assert describe_writer("abc123", "") == "abc123"
    assert describe_writer(None, "funding-carry") == "funding-carry"
    # claim_writer must RECORD svc, or the other side can never read it
    _src = _ins.getsource(claim_writer)
    assert '"svc": service_name()' in _src, \
        "the claim must record its own service or the report stays opaque"
    assert "describe_writer(who, cur.get(\"svc\"))" in _src, \
        "the contended path must report the SERVICE, not the replica id"

    print(f"bot_pnl_store selftest OK (build id: deterministic, byte-sensitive, "
          f"path-independent, entry counts, short-set self-describing; stamp "
          f"preserves caller keys; svc attribution + writer description) "
          f"build={a} over {n} files")
    return 0


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        sys.exit(_selftest_build())
    # quick self-test: writes a dummy row if DATABASE_URL is set, else no-ops.
    ok = publish("selftest", status="online", pnl_abs=1.23, pnl_pct=0.0123,
                 extra={"note": "self-test"})
    print("publish ->", ok, "(DATABASE_URL set)" if _DATABASE_URL else "(no DATABASE_URL; no-op)")
    time.sleep(0.1)


# ---------------------------------------------------------------------------
# [2026-07-07 CROSS-BOT] Fleet-level reader + append-only history for the
# shared layers (regime oracle, fleet risk, signal bus). Same guarded,
# never-raise pattern as everything above.


def fetch_realized_window(bots, days=7):
    """[2026-07-16 LIVE-LANE BALANCE] Per-bot realized P&L over the trailing
    window, straight from the paper_trades ledger: {bot: {"pnl", "closes"}}.
    Bots with no closes in the window get {"pnl": 0.0, "closes": 0} — present,
    not missing, so callers can tell "quiet book" from "DB dark". Returns None
    if the DB is unavailable (callers must fail toward their conservative
    side). Read-only; used by evidence_board's live clip lane, which needed a
    time-local view: lifetime pnl_abs anchors never heal (a healed book stayed
    'hurt' forever) and never forgive (one good month masked a bad week)."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_paper_trades_table(conn)
        from datetime import datetime, timedelta, timezone
        cut = (datetime.now(timezone.utc) - timedelta(days=float(days))).isoformat()
        out = {str(b): {"pnl": 0.0, "closes": 0} for b in bots}
        with conn.cursor() as cur:
            cur.execute(
                "SELECT bot, COUNT(*), COALESCE(SUM(pnl_abs), 0) FROM paper_trades "
                "WHERE bot = ANY(%s) AND side IS DISTINCT FROM 'skip' "
                "AND closed_at >= %s GROUP BY bot",
                (list(out), cut))
            for b, n, s in cur.fetchall():
                out[str(b)] = {"pnl": float(s or 0.0), "closes": int(n or 0)}
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"realized-window read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return None


def fetch_bot_pnl():
    """Return every bot's latest bot_pnl row as a list of dicts, or None if
    the DB is unavailable. Read-only; used by fleet_risk.py."""
    conn = _get_conn()
    if conn is None:
        return None
    try:
        _ensure_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                # [2026-07-15 AUDIT FIX] include pnl_pct — the immune organ's
                # NaN/absurd-pnl_pct sickness check reads it; it was omitted, so
                # that check silently never fired on real rows.
                "SELECT bot, updated_at, status, equity, pnl_abs, pnl_pct, "
                "open_trades, closed_trades, wins, losses, extra FROM bot_pnl")
            cols = [d[0] for d in cur.description]
            out = []
            for row in cur.fetchall():
                d = dict(zip(cols, row))
                if isinstance(d.get("extra"), str):
                    try:
                        d["extra"] = json.loads(d["extra"])
                    except Exception:
                        d["extra"] = {}
                if d.get("updated_at") is not None:
                    d["updated_at"] = d["updated_at"].isoformat()
                out.append(d)
        return out
    except Exception as e:
        _warn_once(f"bot_pnl read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return None


_history_table_ready = False


def _ensure_history_table(conn):
    global _history_table_ready
    if _history_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_state_history (
                key     TEXT NOT NULL,
                ts      TIMESTAMPTZ NOT NULL DEFAULT now(),
                payload JSONB
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS bot_state_history_key_ts "
            "ON bot_state_history (key, ts)")
    _history_table_ready = True


_HISTORY_KEEP_DAYS = float(os.environ.get("BOT_STATE_HISTORY_KEEP_DAYS", "60"))
_hist_writes = 0

#: [2026-08-02] The retention DELETE, as a named constant so a test can assert
#: on the statement this function actually runs rather than on a description of
#: it. `%s * interval '1 day'` accepts a NUMERIC bind; `make_interval(days =>
#: %s)` demands an INTEGER and raised on every call for 17 days. See
#: `prune_history`.
HISTORY_PRUNE_SQL = ("DELETE FROM bot_state_history "
                     "WHERE ts < now() - (%s * interval '1 day')")


def prune_history(conn=None, keep_days=None):
    """[2026-07-16 AUDIT FIX] bot_state_history had NO retention anywhere in
    the repo (~400+ rows/day from the 15-Jul organs alone — the shared
    Railway Postgres bloated indefinitely). Deletes rows older than
    keep_days (default 60 — every consumer reads days, not months: brain
    lens grading, replay tape, regen last-good 24h, /bus.json?hours<=200).
    Returns rows deleted, or None on DB trouble. Never raises.

    [2026-08-02] THIS HAD NEVER ONCE SUCCEEDED, and it said so in the logs
    every boot while nobody read them. `make_interval(days => ...)` takes an
    **integer**, and `days` is built with `float(...)`, so psycopg2 bound a
    `numeric` and Postgres found no matching function:

        function make_interval(days => numeric) does not exist

    Every call raised, `_warn_once` logged it a single time per process, and
    the retention this function exists to provide has never run — so
    `bot_state_history` has grown without bound since 16-Jul. The failure was
    invisible in exactly the way `(I4)` names: a persistent condition reported
    by a one-shot warning, behind a `return None` the caller discards.

    The fix is the multiplication idiom, which is typed for `numeric` and so
    keeps FRACTIONAL retention working (`keep_days=0.5` is meaningful and
    `make_interval` could never have expressed it). Found by reading a
    container's logs during the daily review — not by any test, because no
    test ever ran this function against a real Postgres."""
    conn = conn or _get_conn()
    if conn is None:
        return None
    try:
        _ensure_history_table(conn)
        days = float(keep_days if keep_days is not None else _HISTORY_KEEP_DAYS)
        with conn.cursor() as cur:
            cur.execute(HISTORY_PRUNE_SQL, (days,))
            return cur.rowcount
    except Exception as e:  # noqa: BLE001
        _warn_once(f"history prune failed ({e})")
        return None


def record_organ_error(key, exc=None, where=None):
    """Stamp an organ's OWN failure onto its OWN bot_state key. Never raises.

    [2026-08-01 (hw)] THE LEAK THIS CLOSES. `run_all.sh` invokes every organ as
    `python3 <organ>.py || true` — correct, so one sick organ can never take the
    supervisor down with it, and it makes every organ crash INVISIBLE: the exit
    code goes to `|| true` and the traceback goes to a container log nobody
    tails.

    MEASURED the day this shipped: **20 of 22 organs had no way to report their
    own death.** The learning brain had been raising KeyError('paper') on EVERY
    run — the Kraken paper twin it compares against was retired 14-Jul — dying
    before `_save_state`, so `learning-brain.runs` sat frozen at 337 while
    `brain-vitals.run` read 338. It published its four read-only keys on time
    and looked perfectly healthy from the outside while its memory, and
    therefore the 3-run streak gate that moves every stake multiplier, could
    never advance. A learning loop that cannot learn, for weeks, in silence.

    A failure that exists only in an unread log is a silent failure. This puts
    it in the payload the fleet ALREADY watches, so `fleet_immune` reaches the
    operator by the path every organ already uses — no new plumbing.
    """
    # [2026-08-20 (ry)] THE MISSING IMPORT THAT MADE THIS A NO-OP FROM THE DAY
    # IT SHIPPED. `datetime` is not a module-level name in this file — every
    # other user imports it locally — so the `datetime.now(...)` below raised
    # NameError on EVERY call, the blanket `except Exception: return False`
    # swallowed it, and the function returned False without ever reaching
    # `save_state`. Proved by stubbing both DB calls to succeed and counting:
    # save_state was called ZERO times.
    #
    # So `(hw)`'s whole deliverable — "20 of 22 organs had no way to report
    # their own death" — has never recorded a single organ death, and the
    # caller made it worse than silent by printing "ORGAN FAULT recorded ... so
    # the immune organ can see it", a sentence that has never been true (I4's
    # discarded result and I8's unactionable instruction in one line).
    from datetime import datetime, timezone      # noqa: PLC0415 — file convention
    try:
        payload = load_state(key) or {}
        if not isinstance(payload, dict):
            payload = {}
        payload["healthy"] = False
        payload["error"] = (f"{type(exc).__name__}: {exc}" if exc else "unknown")
        if where:
            payload["error_where"] = str(where)[:200]
        payload["error_at"] = datetime.now(timezone.utc).isoformat(
            timespec="seconds")
        return bool(save_state(key, payload))
    except Exception:                                # noqa: BLE001
        return False


def clear_organ_error(payload):
    """Mark a payload healthy, in place, before it is published.

    A sticky error would page once and then mean nothing — the detector has to
    be able to say RECOVERED, not only DIED. Callers stamp this on the happy
    path; `record_organ_error` stamps the other one.
    """
    if isinstance(payload, dict):
        payload["healthy"] = True
        payload.pop("error", None)
        payload.pop("error_where", None)
        payload.pop("error_at", None)
    return payload


def organ_main(key, fn, *args, **kwargs):
    """Run an organ's entry point; record its own death on `key` if it dies.

    Returns fn's exit code, or 1 on a fault. NEVER re-raises — the caller is a
    `|| true` shell line and a traceback there is exactly the silence this
    exists to end. The organ stays responsible for stamping `healthy=True` on
    its own successful publish (see clear_organ_error).
    """
    import traceback
    try:
        rc = fn(*args, **kwargs)
        return 0 if rc is None else rc
    except SystemExit as e:                          # an organ's own exit code
        return int(getattr(e, "code", 0) or 0)
    except Exception as e:                           # noqa: BLE001
        tb = traceback.format_exc()
        print(tb, file=sys.stderr)
        where = ""
        lines = [ln.strip() for ln in tb.strip().splitlines()]
        if len(lines) >= 2:
            where = lines[-2][:200]
        # [2026-08-20 (ry)] READ THE RESULT AND SAY WHICH HAPPENED (I4/I8).
        # This discarded the return value and printed "recorded ... so the
        # immune organ can see it" unconditionally — FALSE on every call for as
        # long as `record_organ_error` carried its missing import, and false
        # again any time the DB is down. The two cases need different words
        # because they need different acts: one says the operator will be
        # paged, the other says nobody will.
        if record_organ_error(key, e, where):
            print(f"[{key}] ORGAN FAULT recorded on its own bot_state key so "
                  f"the immune organ can see it: {type(e).__name__}: {e}",
                  file=sys.stderr)
        else:
            print(f"[{key}] ORGAN FAULT — AND IT COULD NOT BE RECORDED. This "
                  f"death is visible ONLY in this container's log, which is "
                  f"the silence record_organ_error exists to end: "
                  f"{type(e).__name__}: {e}", file=sys.stderr)
        return 1


def snapshot_equity(bot, equity, open_trades=None, realized=None):
    """[2026-07-30 (hl)] Append one MARK-TO-MARKET equity sample for `bot` to
    bot_state_history under '<bot>:equity'. Never raises; a dark DB is a no-op.

    WHY THIS EXISTS, and it governs REAL MONEY. `golive_readiness.stats()` —
    the grader for the rule deciding whether a $1,000 shadow book may ever hold
    real money — accumulates REALISED closed-trade P&L only. For a book that
    holds most of the time, most of its drawdown is OPEN and therefore
    INVISIBLE to the bar. Measured on 📊 Index Rider (long on 64% of days): at
    the 3y plateau all four stop x lag cells PASS the gate on realised
    drawdown 9.9-10.7% while true mark-to-market drawdown is 15.6-17.4% —
    the two definitions disagree about the VERDICT, not just the number.

    The books already publish MTM equity to bot_pnl every loop, but bot_pnl is
    ONE UPSERTED ROW per book: there is no series, so no drawdown can be
    computed from it. This starts the series.

    [2026-08-04 (ja) — the paragraph that stood here said "DELIBERATELY NOT
    WIRED INTO THE GRADER YET"; that became false in (ia) and then MASKED a
    real bug: the grader WAS wired, behind sample floors (200 samples / 7d),
    but its reader called a store method that never existed ((iz)) and the
    blanket except made that look like the deliberate deferral this text
    described. Corrected per I12.] The grader consumes this series via
    `golive_readiness.equity_series` -> `apply_mtm`, floor-gated, taking the
    WORSE of realised and MTM. Re-grade 🌾 carry first when its floor clears:
    a stricter drawdown definition lands on the book nearest the gate first.
    """
    try:
        row = {"equity": round(float(equity), 4)}
    except (TypeError, ValueError):
        return False
    if open_trades is not None:
        try:
            row["open"] = int(open_trades)
        except (TypeError, ValueError):
            pass
    if realized is not None:
        try:
            row["realized"] = round(float(realized), 4)
        except (TypeError, ValueError):
            pass
    return save_history(str(bot) + ":equity", row)


def save_history(key, payload):
    """Append one snapshot to bot_state_history (oracle calls, risk lights) so
    the shared layers become backtestable. Safe every loop. Never raises.
    Every ~200th write also age-prunes the table (see prune_history)."""
    global _hist_writes
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO bot_state_history (key, ts, payload) "
                "VALUES (%s, now(), %s)",
                (key, json.dumps(payload)))
        _hist_writes += 1
        if _hist_writes % 200 == 0:
            n = prune_history(conn)
            if n:
                print(f"[bot_pnl_store] history prune: {n} rows older than "
                      f"{_HISTORY_KEEP_DAYS:g}d removed", flush=True)
        return True
    except Exception as e:
        _warn_once(f"history write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False


def fetch_state_history(key, limit=800):
    """[2026-07-14] Read side of save_history: recent bot_state_history
    snapshots for one shared-layer key, NEWEST FIRST -> [{"ts": iso, "payload":
    dict}]. Built for the brain's diagnosis layer (joining trades to the
    regime-oracle reading at their open time). Returns [] when unavailable."""
    conn = _get_conn()
    if conn is None:
        return []
    try:
        _ensure_history_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                "SELECT ts, payload FROM bot_state_history "
                "WHERE key = %s ORDER BY ts DESC LIMIT %s",
                (key, int(limit)))
            rows = cur.fetchall()
        out = []
        for ts, payload in rows:
            if isinstance(payload, str):
                try:
                    payload = json.loads(payload)
                except Exception:
                    continue
            out.append({"ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                        "payload": payload or {}})
        return out
    except Exception as e:  # noqa: BLE001
        _warn_once(f"state-history read failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return []


# --------------------------------------------------------------------------
# venue order log [2026-07-09 LIGHTER GATE-0]
# Order-level provenance for the Lighter migration: every shadow-modelled fill
# AND (later) every live order lands here with the raw exchange response, so
# Gate-3 can price realizable spread/slippage per market from real evidence.
_venue_orders_table_ready = False


def _ensure_venue_orders_table(conn):
    global _venue_orders_table_ready
    if _venue_orders_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS venue_orders (
                id            BIGSERIAL PRIMARY KEY,
                at            TIMESTAMPTZ NOT NULL DEFAULT now(),
                bot           TEXT NOT NULL,
                venue         TEXT NOT NULL,
                shadow        BOOLEAN NOT NULL DEFAULT TRUE,
                coin          TEXT,
                side          TEXT,
                size          DOUBLE PRECISION,
                px_decision   DOUBLE PRECISION,
                px_fill       DOUBLE PRECISION,
                spread_bps    DOUBLE PRECISION,
                slippage_bps  DOUBLE PRECISION,
                raw           JSONB
            )
            """
        )
        cur.execute(
            "CREATE INDEX IF NOT EXISTS venue_orders_bot_at "
            "ON venue_orders (bot, at)")
    _venue_orders_table_ready = True


def publish_venue_order(bot, venue, shadow, coin, side, size,
                        px_decision=None, px_fill=None, spread_bps=None,
                        slippage_bps=None, raw=None):
    """Append one venue order (shadow or live) to the durable order log.
    Guarded like every publisher here: never raises into a trading loop."""
    conn = _get_conn()
    if conn is None:
        return False
    try:
        _ensure_venue_orders_table(conn)
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO venue_orders (bot, venue, shadow, coin, side, size,
                    px_decision, px_fill, spread_bps, slippage_bps, raw)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (bot, venue, bool(shadow), coin, side, size, px_decision,
                 px_fill, spread_bps, slippage_bps,
                 json.dumps(raw) if raw is not None else None),
            )
        return True
    except Exception as e:  # noqa: BLE001
        _warn_once(f"venue-order write failed ({e})")
        global _conn
        try:
            conn.close()
        except Exception:
            pass
        _conn = None
        return False
