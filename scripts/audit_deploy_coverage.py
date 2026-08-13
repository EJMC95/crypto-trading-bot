#!/usr/bin/env python3
"""
scripts/audit_deploy_coverage.py — does a change to this file ever REACH the fleet?

╔══════════════════════════════════════════════════════════════════════════╗
║ WHY THIS EXISTS (measured 2026-07-17, and it is the whole story)          ║
║                                                                          ║
║ CLAUDE.md says: "Deploy trigger: push to main branch → Railway auto-      ║
║ deploys". **That is FALSE for 16 of the 20 organs in run_all.sh and for   ║
║ BOTH real-money bots.** Measured, not inferred:                           ║
║                                                                          ║
║  * NOT ONE of the 12 Railway services is git-connected — `railway         ║
║    variables` returns zero RAILWAY_GIT_* keys on every one. Railway-side  ║
║    Auto Deploy is OFF fleet-wide.                                         ║
║  * The ONLY automated path is `.github/workflows/railway-redeploy.yml`,   ║
║    which runs `railway up` — but only for a HARDCODED path list, and only ║
║    for freqtrade-bots / pnl-dashboard / funding-carry.                    ║
║  * That list was last extended 2026-07-07. Everything built since — the   ║
║    ENTIRE intelligence layer (bot_learn, experiment_judge, evidence_board,║
║    fleet_immune, fleet_proprioception, fleet_regen, fleet_respiration,    ║
║    implementation_shortfall, lighter_market_scout, lighter_scout_tuner,   ║
║    strategy_incubator, event_sentinel, fleet_clock) plus lighter_ticket_  ║
║    taker — ships ONLY when a human remembers `railway up`.                ║
║  * The retired HL `funding-carry` arm auto-deploys. The LIVE Funding      ║
║    Farmer does not.                                                       ║
║                                                                          ║
║ WHAT IT COST: six commits of fill telemetry landed 2026-07-17 between     ║
║ 04:27 and 10:52 UTC. The funding container booted 04:34 and never picked  ║
║ any of them up. `venue_orders` has never carried a `measured` or          ║
║ `fill_src` key — 58 real orders, 0 measured fills — and the Funding       ║
║ Farmer's entire gate/stop verdict turns on the friction number that       ║
║ telemetry exists to measure. The code was right. It was never running.    ║
║ This is the mechanism behind every "frozen service" incident in           ║
║ [[railway-cli-frozen-services]]: not mystery, a stale list.               ║
║                                                                          ║
║ THE 7-JUL COMMENT IN THAT WORKFLOW SAYS IT ALREADY HAPPENED ONCE:         ║
║   "cross-bot layer (runs inside freqtrade-bots via run_all.sh) — added    ║
║    2026-07-07 after 9cedf08 (SUI + historize) silently didn't deploy"     ║
║ They added the two organs that had bitten them and left the list to rot   ║
║ again. **A list that must be remembered is the control that already       ║
║ failed.** Hence a guard, not a longer list.                               ║
╚══════════════════════════════════════════════════════════════════════════╝

WHAT IT CHECKS. For each image, the Dockerfile declares what is IN it (COPY)
and what it RUNS (CMD / run_all.sh). The workflow declares which paths trigger
a deploy of which service. A file that ships in an auto-deployed image but is
NOT on that image's path filter is ORPHANED: editing it is a silent no-op.

[2026-08-04 (jb)] AND, BEFORE ANY PER-FILE QUESTION: every Dockerfile in the
repo root must be CLAIMED by a deploy story at all. The per-file check can only
interrogate images already listed in AUTO_IMAGES, so a brand-new Dockerfile.* +
service was INVISIBLE — the audit stayed green while the new bot had no deploy
route whatsoever, which is exactly how the (fz) shadow books were born
routeless. The census: repo-root Dockerfile* ⊆ AUTO_IMAGES ∪ the live
marker-grep image set ∪ MANUAL_IMAGES_OK (declared, with reasons). An unclaimed
image fails the build (operator mandate 4-Aug: "ones to come are always getting
current live and up to date upgrades").

WHAT IT DELIBERATELY DOES NOT CHECK. Whether a service is git-connected, and
whether the running container matches git — both need the network, and this
guard must stay a static, offline, CI-safe check like its siblings
(audit_image_imports / audit_venue_purity / audit_sdk_pin). Marker-grepping
the RUNNING container remains the only proof a deploy landed
([[railway-cli-frozen-services]]); this catches the class one level earlier —
the change that could never have deployed in the first place.

Read-only. Touches no bot, no DB, no network.
"""
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORKFLOW = os.path.join(ROOT, ".github", "workflows", "railway-redeploy.yml")

# ---------------------------------------------------------------------------
# DECLARED: a file here is KNOWN not to auto-deploy, WITH A REASON. Silence is
# not an option — the same rule as BORN_DARK_OK. A reason must say why the
# omission is correct, not merely restate it.
# ---------------------------------------------------------------------------
DEPLOY_COVERAGE_OK = {
    "lighter_funding_bot.py": (
        "LIVE REAL MONEY (trail-blazer-live). Auto-deploy on EVERY push stays "
        "marker-gated for two CURRENT reasons: (1) a push may carry unfinished "
        "WIP and a redeploy RESTARTS a real-money book; (2) the slope gate 'fails "
        "open ~1h after restart' (in-process history), so each restart relaxes a "
        "validated ENTRY refinement. The earlier memory-only-halt hazard "
        "(lighter-flatten-silent-halt-redeploy-incident: a halt wiped, HYPE "
        "re-bought 37s after boot) is NO LONGER the reason — it was FIXED: the "
        "daily-loss halt (07-11), day-start baseline (07-21 D3), and post-stop "
        "quarantine (07-22) all survive restarts now ('a restart no longer "
        "re-arms a stopped coin'). Ship DELIBERATELY via workflow_dispatch OR the "
        "[deploy-live-farmer]/[deploy-live] commit marker (both check out clean "
        "main; added 2026-07-25) — never on EVERY push, never from a local "
        "`railway up` which uploads your desk (deploy-live-from-a-clean-worktree)."
    ),
    "lighter_trend_bot.py": (
        "Same restart hazard as lighter_funding_bot.py, and its service "
        "(tide-rider-lighter-live) now runs the Ticket Taker's image. Its live "
        "row is RETIRED and REAL_MONEY_KILL is the only thing holding it — an "
        "automatic redeploy of this file is exactly the loaded gun in "
        "golive-name-the-image-before-the-env. Operator-dispatched only."
    ),
    "lighter_ticket_taker.py": (
        "LIVE REAL MONEY since 17-Jul (tide-rider-lighter-live, "
        "Dockerfile.tickettaker). Same deliberate-dispatch rule as the Farmer. "
        "NOTE it also runs as a SHADOW arm inside freqtrade-bots via run_all.sh, "
        "so a freqtrade-bots deploy DOES move the shadow twin — the two arms can "
        "drift, and that is a real hazard worth a review item, not a reason to "
        "auto-ship the live one."
    ),
    "venues/": (
        "The shared real-money surface (SafetyRails, notional caps, the signer, "
        "the fill read). Imported by BOTH live bots; auto-deploying it would "
        "auto-restart them. Same operator-dispatch rule."
    ),
}


def _read(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------------------
# [2026-08-13 (ls)] THE RUN-SCALAR BUDGET. GitHub evaluates a `run:` scalar
# that contains ANY ${{ }} expression as ONE template with a hard
# 21,000-character cap — one character over and the WHOLE workflow file fails
# validation at push time: the run is recorded with the file PATH as its name,
# ZERO jobs, no logs, and NOTHING deploys. Measured the day this shipped: the
# (ls) birth merge added 15 comment lines to the decide step (20,541 →
# 21,390) and main's deploy workflow was DEAD from a002b1f until the repair —
# every push red, dashboard and organs frozen, invisibly to every other
# guard because the failure produces no job to fail. The budget sits below
# the cap so this audit reds while pushes still deploy, with runway left to
# trim. Comments inside the scalar COUNT — prose provenance belongs in the
# CHANGELOG, not in this one string GitHub measures.
# ---------------------------------------------------------------------------
RUN_SCALAR_CAP = 21000          # GitHub's hard limit (its own 422 names it)
RUN_SCALAR_BUDGET = 20500       # fail here, with 500 chars of runway


def run_scalar_lengths(src=None):
    """[(line_no, length, has_expr), ...] for every `run:` scalar in the
    deploy workflow — length measured as YAML delivers it (block content
    DEDENTED to the block's own indentation), because that is the string
    GitHub's expression parser measures. Indentation-based on purpose: this
    audit deliberately has no yaml dependency, and the selftest pins the
    extractor against a fixture with a known exact length."""
    src = _read(WORKFLOW) if src is None else src
    out = []
    lines = src.splitlines(keepends=True)
    i = 0
    while i < len(lines):
        m = re.match(r"^(\s*)(?:-\s+)?run:\s*([|>][+\-0-9]*\s*)?(.*)$",
                     lines[i])
        if not m:
            i += 1
            continue
        indent, block, rest = m.group(1), m.group(2), m.group(3)
        if not block:                              # single-line run
            out.append((i + 1, len(rest), "${{" in rest))
            i += 1
            continue
        body, j, base = [], i + 1, len(indent)
        while j < len(lines):
            ln = lines[j]
            if ln.strip() == "":
                body.append(ln)
                j += 1
                continue
            if (len(ln) - len(ln.lstrip())) <= base:
                break
            body.append(ln)
            j += 1
        while body and not body[-1].strip():
            body.pop()                     # clip mode: trailing blanks vanish
        pad = min((len(x) - len(x.lstrip())
                   for x in body if x.strip()), default=0)
        text = "".join(x[pad:] if x.strip() else "\n" for x in body)
        out.append((i + 1, len(text), "${{" in text))
        i = j
    return out


def oversized_run_scalars(src=None, budget=RUN_SCALAR_BUDGET):
    """(line_no, length) for every expression-bearing run scalar over the
    budget. Scalars with no ${{ }} are exempt — GitHub only templates the
    ones that interpolate, and only those hit the cap."""
    return [(ln, n) for ln, n, has_expr in run_scalar_lengths(src)
            if has_expr and n > budget]


def _shell_vars(src):
    """Single-quoted shell assignments in the decide step, e.g.
    `_shared='a\\.py$|venues/'` — so a grep that INTERPOLATES one can still be
    parsed. Longest name first, so `$taker_files` is not clipped by `$taker`."""
    return dict(sorted(re.findall(r"(\w+)='([^']+)'", src),
                       key=lambda kv: -len(kv[0])))


def workflow_filters():
    """(service -> compiled path regex) from the `grep -qE` lines in the decide
    step — the list that chooses WHICH SERVICE gets deployed.

    [2026-07-30 (gl)] Reads the DOUBLE-quoted, variable-interpolating form too.
    The six shadow services' rules are written
    `grep -qE "^(lighter_x\\.py$|Dockerfile\\.x$|$_shared)"`, which the
    single-quote-only parser could not see at all — so this guard reported them
    as having no rule whatsoever, which is the same blindness
    `live_marker_filters()` exists to fix, recurring one pass later. The fix is
    here rather than by inlining `$_shared` six times, because the guard being
    unable to read a legitimate shell idiom is the defect."""
    src = _read(WORKFLOW)
    var = _shell_vars(src)
    out = {}
    # grep -qE '<regex>' | "<regex>"; then svcs="..." / svcs="${svcs:+$svcs,}..."
    for m in re.finditer(
        r"grep\s+-qE\s+(?:'([^']+)'|\"([^\"]+)\")"
        r".*?\n\s*svcs=\"(?:\$\{svcs:\+\$svcs,\})?([a-z0-9-]+)\"",
        src, re.S,
    ):
        rx, svc = (m.group(1) or m.group(2)), m.group(3)
        # A pattern that is ONLY a variable reference is the live-bot marker
        # form, handled by live_marker_filters() — leave it to that parser.
        if re.fullmatch(r"\$\w+", rx.strip()):
            continue
        for name, val in var.items():
            rx = rx.replace(f"${name}", val)
        if "$" in re.sub(r"\$\)|\$\||\$\"|\$$", "", rx):
            # an UNRESOLVED interpolation would silently compile to a regex
            # that matches nothing — refuse it loudly rather than pass green
            raise SystemExit(f"audit_deploy_coverage: unresolved shell "
                             f"interpolation in the '{svc}' grep: {rx!r}")
        out.setdefault(svc, []).append(re.compile(rx))
    return out


def live_marker_filters():
    """(service -> raw regex string) for the OPT-IN live-bot marker path.

    [2026-07-29 AUDIT] #100 moved the live greps into shell VARIABLES
    (`taker_files='^(...)'` … `grep -qE "$taker_files"`), which the
    inline-quoted parser in workflow_filters() cannot see — so the parsed
    filter map silently lost both live services, and the audit had no way
    to apply any rule to the marker path at all. This parser reads the
    variable form; marker_orphans() below applies the both-lists rule to
    it (the live images are still deliberately NOT in AUTO_IMAGES — the
    marker path is opt-in, but its file set must still be reachable, and
    `paths:` is what makes it reachable)."""
    src = _read(WORKFLOW)
    vars_ = dict(re.findall(r"(\w+_files)='([^']+)'", src))
    out = {}
    # [2026-07-30 (hi)] ONE BRANCH MAY APPEND SEVERAL SERVICES. The Farmer's
    # branch now appends `trail-blazer-live,funding-farmer-shadow` so its two
    # experiment arms cannot ship apart, and the old `([a-z0-9-]+)` read that
    # whole comma-joined string as a SINGLE service name — which silently
    # dropped `trail-blazer-live` from the marker map and, with it, every
    # both-lists rule applied to the real-money path. Caught by this file's own
    # selftest, which is the only reason it is not shipping broken: the parser
    # returned a plausible-looking dict with the wrong keys.
    for var, svcs in re.findall(
            r'grep\s+-qE\s+"\$(\w+_files)".*?\n\s*svcs="\$\{svcs:\+\$svcs,\}'
            r'([a-z0-9,-]+)"', src, re.S):
        if var not in vars_:
            continue
        for svc in (s.strip() for s in svcs.split(",")):
            if svc:
                out[svc] = vars_[var]
    return out


def marker_source_ok():
    """(ok, detail) — the live-marker grep must read commit SUBJECTS, not bodies.

    [2026-07-30 (hj)] It read `git log --format='%B'` (full body), so a commit
    that merely MENTIONED a marker deployed real money. Measured on the (hj)
    commit itself: the body sentence "NOT deployed to the live taker: no
    [deploy-live-taker] marker" matched, and `tide-rider-lighter-live` — the
    LIVE Ticket Taker — was redeployed. The sentence saying the deploy was not
    happening is what caused it.

    A real-money trigger must not be reachable by prose ABOUT the trigger.
    Every genuine marker in this repo's history sits in the subject, which is
    also the documented usage, so subjects are the correct and sufficient
    source. This pins it: a silent revert to %B re-arms the same defect on the
    one path that moves real money.
    """
    src = _read(WORKFLOW)
    m = re.search(r"msgs=\"\$\(git log --format='(%[a-zA-Z])'", src)
    if not m:
        return False, ("could not find the live-marker `msgs=$(git log "
                       "--format=...)` line at all — the marker gate may have "
                       "moved; re-check it by hand before trusting this guard")
    fmt = m.group(1)
    if fmt != "%s":
        return False, (f"live-marker grep reads git log --format='{fmt}'. It "
                       f"MUST be '%s' (subject only): with '%B' a commit body "
                       f"that merely mentions [deploy-live-taker] deploys the "
                       f"REAL-MONEY taker — measured 2026-07-30 (hj).")
    return True, "live-marker grep reads commit SUBJECTS only (%s)"


def marker_atoms(pattern):
    """(files, prefixes) — the concrete path atoms inside a `^(a\\.py$|dir/)`
    alternation. File atoms end `$` (unescaped to plain paths); prefix atoms
    end `/`. Anything else is ignored (fail-open per atom — the both-lists
    check is advisory-shaped, the greps stay authoritative for MATCHING)."""
    body = pattern
    if body.startswith("^(") and body.endswith(")"):
        body = body[2:-1]
    files, prefixes = [], []
    for alt in body.split("|"):
        alt = alt.strip()
        if alt.endswith("$"):
            files.append(alt[:-1].replace(r"\.", "."))
        elif alt.endswith("/"):
            prefixes.append(alt)
    return files, prefixes


def marker_orphans(marker_map, globs):
    """[(service, atom)] for every marker-grep atom the `paths:` block cannot
    reach. `paths:` gates whether the job RUNS; a file in a live marker grep
    but absent from `paths:` means a marker push touching only that file
    fires NO workflow — the marker can never work for it. That is the exact
    both-lists class this guard exists for, on the real-money path: measured
    2026-07-29 (the 28-Jul grep widening added tickettaker_loop.sh, the two
    live Dockerfiles and later requirements.txt to the greps only)."""
    if globs is None:
        return [("<unparseable>", "paths:")]      # fail closed
    out = []
    for svc, pattern in sorted((marker_map or {}).items()):
        files, prefixes = marker_atoms(pattern)
        for f in files:
            if not _path_listed(f, globs):
                out.append((svc, f))
        for pre in prefixes:
            if not _path_listed(pre + "x.py", globs):
                out.append((svc, pre + "**"))
    return out


def workflow_paths():
    """The `on: push: paths:` globs — the list that decides whether the job RUNS
    AT ALL.

    [2026-07-17 CORRECTION — this guard shipped with a FALSE-OK.] It read only
    the greps above and argued in its own docstring that "the greps are what
    bind". Wrong, and backwards: `paths:` is evaluated by GitHub BEFORE the job
    starts. A file present in a grep but absent from `paths:` never reaches the
    grep, because the workflow never runs. So the binding list is the INTERSECTION
    — a file needs BOTH — and a guard that checked only one half would hand out a
    green OK for a file that can never deploy. That is the exact failure class
    this file exists to catch, committed inside the file catching it.
    Found by reconciling with scripts/audit_deploy_filter.py, which a concurrent
    session wrote against the SAME bug from the other side: it checks `paths:`
    and not the greps. Neither guard was right alone."""
    src = _read(WORKFLOW)
    m = re.search(r"^\s*paths:\s*\n((?:\s*(?:#.*)?\n|\s*-\s*'[^']+'\s*\n)+)",
                  src, re.M)
    if not m:
        return None                     # unparseable -> caller fails closed
    return [g.group(1) for g in re.finditer(r"-\s*'([^']+)'", m.group(1))]


def _path_listed(rel, globs):
    """Does `rel` match any `paths:` glob? Supports the two forms the workflow
    actually uses: an exact filename and a `dir/**` prefix."""
    for g in globs:
        if g.endswith("/**"):
            if rel.startswith(g[:-2]):
                return True
        elif g == rel:
            return True
    return False


def image_files(dockerfile):
    """Repo-relative paths COPY'd into an image. Mirrors audit_image_imports's
    reconstruction closely enough for coverage: multi-source COPY, `COPY dir/`,
    and the `COPY . .` catch-all."""
    files, catch_all = set(), False
    for line in _read(dockerfile).splitlines():
        line = line.strip()
        if not line.upper().startswith("COPY "):
            continue
        parts = line[5:].split()
        parts = [p for p in parts if not p.startswith("--")]
        if len(parts) < 2:
            continue
        for src in parts[:-1]:            # last token is the destination
            if src == ".":
                catch_all = True
            else:
                files.add(src.rstrip("/") + ("/" if src.endswith("/") else ""))
    return files, catch_all


def run_all_organs():
    p = os.path.join(ROOT, "run_all.sh")
    if not os.path.exists(p):
        return set()
    return set(re.findall(r"([a-z_]+\.py)", _read(p)))


def declared(path):
    """Longest-prefix match, so `venues/` covers `venues/lighter_client.py`."""
    if path in DEPLOY_COVERAGE_OK:
        return DEPLOY_COVERAGE_OK[path]
    for k, v in DEPLOY_COVERAGE_OK.items():
        if k.endswith("/") and path.startswith(k):
            return v
    return None


# Dockerfile -> the service the workflow can deploy. Only images the workflow
# knows about can be covered at all; the rest are manual by construction.
AUTO_IMAGES = {"Dockerfile.freqtrade": "freqtrade-bots",
               "Dockerfile.dashboard": "pnl-dashboard",
               "Dockerfile.funding": "funding-carry",
               # [2026-07-28] auto-deployed by the workflow since 17-Jul
               # (its own comment: "the fleet's ONLY cross-region check on
               # the real-money books") but never audited here — a future
               # COPY added to that image could go deploy-orphaned unseen.
               "Dockerfile.marketcontext": "market-context",
               # [2026-07-30 (gl)] THE SIX SHADOW IMAGES. They gained deploy
               # rules in (fz) but were never listed here, so this guard was
               # green while FOUR of their service names did not resolve at
               # all — the guard can only check images it knows about, and
               # "has a rule" is not "has a working rule". Names verified
               # against the live `railway service list` printed by run
               # 30494145090, not inferred from the dashboard row ids (the
               # Railway names follow the EMOJI NICKNAME, which is exactly
               # why four of the five guesses were wrong).
               # [2026-08-05] Dockerfile.dislocation + Dockerfile.trendlighter
               # moved to MANUAL_IMAGES_OK: their books are RETIRED ((jh)/(if))
               # and their deploy rules are removed from the workflow so the
               # operator can delete the services without auto-deploy
               # resurrecting them (operator-queue item 3, guard-first order).
               "Dockerfile.fundspread": "counterweight-shadow",
               "Dockerfile.indexshadow": "equities-regime-shadow",
               "Dockerfile.psniper": "perp-sniper-shadow",
               "Dockerfile.familyshadow": "family-lighter-shadow",
               # [2026-08-05] 🎸 Barnesy — the funding super-book, routed the
               # day it was born (the (jb) census fails an unclaimed image, so
               # a route-less birth is no longer possible; this entry is the
               # claim). Name created by `railway add --service
               # band-barnes-shadow` in the same session as this rule.
               "Dockerfile.bandbarnes": "band-barnes-shadow",
               # [2026-08-13 (ls)] 🏦 Rich Dad — moved here from
               # MANUAL_IMAGES_OK at activation: service provisioned by the
               # dispatched workflow, row verified publishing with a build
               # stamp, decide rule live in the same commit.
               "Dockerfile.kiyosaki": "book-kiyosaki-shadow",
               # [2026-08-13 (mi)] the BOOKS wave 2 — moved here from
               # MANUAL_IMAGES_OK at activation: services provisioned by the
               # dispatched workflow, all four rows verified publishing with
               # their locally predicted build stamps, decide rules live in
               # the same commit.
               "Dockerfile.douglas": "book-douglas-shadow",
               "Dockerfile.grimes": "book-grimes-shadow",
               "Dockerfile.schwager": "book-schwager-shadow",
               "Dockerfile.hull": "book-hull-shadow"}


# ---------------------------------------------------------------------------
# [2026-08-04 (jb)] THE IMAGE CENSUS's declared-manual set. Same rule as
# DEPLOY_COVERAGE_OK: silence is not an option — an image with no deploy route
# is either a defect (list it in AUTO_IMAGES / a live marker grep) or a
# decision, and a decision is written down with its reason. Every entry below
# was verified against the fleet tables in CLAUDE.md the day it was written; a
# key whose file is deleted fails the selftest (a declaration for a deleted
# image is archaeology, I12).
# ---------------------------------------------------------------------------
MANUAL_IMAGES_OK = {
    "Dockerfile": (
        "The legacy single shared image from the pre-split era — its own header "
        "says each Railway service overrides the Start Command. No living "
        "service builds from it: every current service pins its own "
        "Dockerfile.* via RAILWAY_DOCKERFILE_PATH or a railway.*.toml config "
        "(which silently OVERRIDES the env var — see "
        "railway-config-as-code-overrides-env). Kept as history."
    ),
    "Dockerfile.arb": (
        "Triangular arb (scanner-triangular-arb) — RETIRED in the 17-Jul "
        "LIGHTER-ONLY cut; the bot idles at boot behind ARB_RETIRED_OVERRIDE. "
        "No deploy route on purpose: a deploy would only reboot an idler."
    ),
    "Dockerfile.crossarb": (
        "Gap Scout (scanner-cross-exchange-arb) — RETIRED 17-Jul. CEX-to-CEX "
        "arb has no Lighter leg, so the book could not be moved, only stopped; "
        "it idles at boot behind GAPSCOUT_RETIRED_OVERRIDE."
    ),
    "Dockerfile.momolive": (
        "Trail Blazer's ORIGINAL live image. Its service name "
        "(trail-blazer-live) survives as the LIVE FUNDING FARMER, which "
        "deploys Dockerfile.fundinglighter behind the [deploy-live-farmer] "
        "marker — routing THIS image anywhere would point retired momo code at "
        "a real-money slot (golive-name-the-image-before-the-env)."
    ),
    "Dockerfile.momoshadow": (
        "Stock Leaders (equities-momentum-lshadow) — RETIRED 17-Jul at maxDD "
        "37-44% vs the 15% go-live gate. Row hidden + pruned; re-building this "
        "image is an operator decision, never an auto-route."
    ),
    "Dockerfile.perpslive": (
        "Bounce Catcher (perps-rsi-meanrev) — a Hyperliquid bot, retired in "
        "the LIGHTER-ONLY cut; idles at boot behind PERPS_RETIRED_OVERRIDE. "
        "Same no-route-for-an-idler rule as the arb images."
    ),
    "Dockerfile.regime": (
        "Kraken-era freqtrade image (RegimeSwitchV1 dry-run, its own header). "
        "Its book predates the 14-Jul Kraken retirement and is not in the "
        "living fleet; the living regime book is equities-regime-shadow, built "
        "from Dockerfile.indexshadow, which IS in AUTO_IMAGES."
    ),
    "Dockerfile.trainer": (
        "The on-demand hyperopt trainer — deliberately MANUAL: a heavy, "
        "human-dispatched job on its own service precisely so it can never "
        "compete with or OOM the freqtrade-bots container. An auto-deploy "
        "would restart it mid-hyperopt and discard the run."
    ),
    "Dockerfile.trendlighter": (
        "Tide Rider (crypto-trend-daily-lshadow) — RETIRED 1-Aug (if): 9 buys "
        "/ zero sells in 22 days holding a third of the long budget. Idles at "
        "boot behind TIDE_RIDER_RETIRED_OVERRIDE; deploy rule removed 5-Aug "
        "so the operator can delete tide-rider-lighter-shadow without a "
        "shared-file push resurrecting it (no route for an idler)."
    ),
    "Dockerfile.dislocation": (
        "Snap Back (lighter-dislocation-lshadow) — RETIRED 4-Aug (jh): the "
        "fleet's only statistically significant loser (t=-2.97, both halves "
        "negative). Idles at boot behind SNAPBACK_RETIRED_OVERRIDE; deploy "
        "rule removed 5-Aug so the operator can delete snap-back-shadow "
        "without a shared-file push resurrecting it (no route for an idler)."
    ),
}


def live_marker_dockerfiles(marker_map=None):
    """The Dockerfile atoms named inside the LIVE marker greps — the
    marker-gated image set. Derived from the workflow rather than hardcoded so
    a renamed live image moves the census's claimed set with it instead of
    leaving a stale claim behind."""
    marker_map = live_marker_filters() if marker_map is None else marker_map
    out = set()
    for pattern in (marker_map or {}).values():
        files, _ = marker_atoms(pattern)
        out.update(f for f in files if f.startswith("Dockerfile"))
    return out


def dockerfile_census(names=None, auto=None, marker=None, manual=None):
    """[name, ...] of every Dockerfile in the repo root that NO deploy story
    claims: not workflow-deployed (AUTO_IMAGES), not a live marker-gated image,
    not declared manual-with-a-reason (MANUAL_IMAGES_OK). Parameters are
    injectable for the same reason covered() takes them — a census that can
    only run against today's clean tree cannot prove it would SEE a gap."""
    if names is None:
        names = sorted(n for n in os.listdir(ROOT)
                       if n == "Dockerfile" or n.startswith("Dockerfile."))
    auto = set(AUTO_IMAGES) if auto is None else set(auto)
    marker = live_marker_dockerfiles() if marker is None else set(marker)
    manual = set(MANUAL_IMAGES_OK) if manual is None else set(manual)
    claimed = auto | marker | manual
    return [n for n in names if n not in claimed]


_UNSET = object()   # "not supplied" — distinct from None, which means UNPARSEABLE


def covered(svc, rel, filters=_UNSET, globs=_UNSET):
    """Can a push to `rel` deploy `svc`? BOTH lists must contain it.

    Module-level ON PURPOSE. This was a lambda inside main(), and the selftest
    that "proved" the both-lists rule mutation-SURVIVED reverting it to grep-only
    — because the test drove _path_listed() in isolation and never touched the
    integration. A test that cannot fail when the rule is removed is decoration.
    Same closure-untestable shape as lighter_funding_bot's fill helpers, made by
    the same author, one hour later."""
    # [2026-07-17] _UNSET, not None. `globs=None` used to mean BOTH "caller did
    # not supply it, go read the workflow" AND "the paths: block did not parse".
    # One value, two meanings — the load_state_seeds_on_a_failed_read shape — and
    # it made the fail-closed branch UNREACHABLE from a test: passing None just
    # re-fetched the real workflow. My mutation test caught it by surviving.
    filters = workflow_filters() if filters is _UNSET else filters
    globs = workflow_paths() if globs is _UNSET else globs
    if globs is None:
        return False                      # unparseable paths: -> fail CLOSED
    return (any(rx.match(rel) for rx in filters.get(svc, []))
            and _path_listed(rel, globs))


#: [2026-07-30 (hi)] PAIRED ARMS. An A/B experiment is only valid while both
#: arms run the SAME code, and `experiment_judge`'s ARM DRIFT gate enforces that
#: at grade time by refusing to promote on mismatched build stamps. But nothing
#: enforced it at DEPLOY time, and the consequence is not a red build — it is a
#: promotion pipeline that silently freezes.
#:
#: MEASURED: `funding-farmer-shadow`, the control arm, appeared NOWHERE in the
#: workflow — only in a comment inside experiment_judge.py — so it had no deploy
#: route at all. After (hb) shipped the live arm this morning: live
#: 705425a83422 vs shadow 128995c2fd76. The judge was idle, so nothing was
#: blocked; the next candidate would have been drift-held on arrival.
#:
#: This guard could not see it, and that is the point worth recording: it asks
#: "does this FILE have a deploy route?" and `lighter_funding_bot.py` does — to
#: the LIVE service. A per-file question cannot express a per-PAIR invariant.
#: {live service: control service} — both must appear in the same decide branch.
PAIRED_ARMS = {"trail-blazer-live": "funding-farmer-shadow"}


def arm_pairing_orphans(src=None):
    """[(live, control, why)] for every arm pair that is not deployed together.

    Textual on purpose: the decide step is shell, and what must hold is that the
    two service names are appended by the SAME `if` — i.e. under one condition,
    so neither arm can ship without the other. Parsing the shell would be a
    second implementation of bash; finding both names in one appended value is
    the invariant stated directly."""
    if src is None:
        with open(os.path.join(ROOT, WORKFLOW)) as fh:
            src = fh.read()
    out = []
    for live, ctrl in sorted(PAIRED_ARMS.items()):
        if live not in src:
            out.append((live, ctrl, f"{live} is not routed by the workflow at all"))
            continue
        if ctrl not in src:
            out.append((live, ctrl,
                        f"{ctrl} has NO deploy route — every {live} deploy drifts "
                        f"the arms and the judge's drift gate freezes promotions"))
            continue
        # both present: they must be appended together, under ONE condition
        together = any(live in line and ctrl in line
                       for line in src.splitlines() if "svcs=" in line)
        if not together:
            out.append((live, ctrl,
                        f"{ctrl} is routed but NOT in the same decide branch as "
                        f"{live} — the arms can ship on different pushes, which "
                        f"is the same drift by a slower route"))
    return out


def main():
    filters = workflow_filters()
    globs = workflow_paths()
    if not filters or globs is None:
        print("audit_deploy_coverage: FAILED — could not parse the workflow's "
              f"{'service greps' if not filters else 'paths: block'} from "
              f"{WORKFLOW}. The guard cannot vouch for a file it cannot read; "
              "failing closed.")
        return 1
    # [(hj)] the real-money marker's SOURCE, before any coverage question —
    # a gate reachable by prose about the gate is worse than a missing path.
    _mk_ok, _mk_why = marker_source_ok()
    if not _mk_ok:
        print(f"audit_deploy_coverage: FAILED — {_mk_why}")
        return 1
    # [2026-08-04 (jb)] THE IMAGE CENSUS — before any per-file question, is
    # every image in the repo CLAIMED by a deploy story at all? The per-file
    # checks below can only interrogate images listed in AUTO_IMAGES, so a
    # brand-new Dockerfile.* + service used to be invisible here: green audit,
    # zero deploy route — the (fz) shadow books' birth defect, waiting for the
    # next bot.
    # [(ls)] the run-scalar budget, before any coverage question: a workflow
    # whose file GitHub refuses to parse deploys NOTHING, whatever its rules
    # say — and the failure mode (zero-job red run) is invisible to every
    # per-file check below.
    fat = oversized_run_scalars()
    if fat:
        for ln, n in fat:
            print(f"audit_deploy_coverage: FAILED — the run: scalar at "
                  f"{WORKFLOW}:{ln} is {n} chars with ${{{{ }}}} expressions "
                  f"inside (budget {RUN_SCALAR_BUDGET}, GitHub's hard cap "
                  f"{RUN_SCALAR_CAP}). Over the cap the whole workflow file "
                  f"fails validation at push time — zero jobs, nothing "
                  f"deploys (the (ls) incident: main dead at 21,390). TRIM "
                  f"COMMENTS from the scalar — provenance prose belongs in "
                  f"the CHANGELOG, not in the one string GitHub measures.")
        return 1
    census_bad = dockerfile_census()
    if census_bad:
        print("UNROUTED IMAGE — these Dockerfiles are claimed by NO deploy "
              "story.\nA service built from one has no deploy route at all: "
              "every change to it ships\nonly when a human remembers `railway "
              "up` — the exact mechanism that left the\n(fz) shadow books "
              "routeless for a day.\n")
        for df in census_bad:
            print(f"  {df}")
        print("\n  Fix: give the image a deploy rule and list it in "
              "AUTO_IMAGES (or, for a\n  real-money image, a live marker "
              "grep), or DECLARE it in MANUAL_IMAGES_OK\n  with a reason.\n")
    # A file must be in BOTH lists to deploy: `paths:` gates whether the job
    # runs, the greps choose the service. Fold `paths:` into the service test so
    # a file listed in one and not the other is reported, not passed.
    _cov = lambda svc, p: covered(svc, p, filters, globs)

    orphans, ok_declared = [], []
    for df, svc in sorted(AUTO_IMAGES.items()):
        dfp = os.path.join(ROOT, df)
        if not os.path.exists(dfp):
            continue
        files, catch_all = image_files(dfp)
        if catch_all:
            continue                       # `COPY . .` — everything ships
        for f in sorted(files):
            # only python we actually run is interesting; assets/configs churn
            if not (f.endswith(".py") or f.endswith(".sh")):
                continue
            if _cov(svc, f):
                continue
            why = declared(f)
            (ok_declared if why else orphans).append((f, svc, df))

    organs = run_all_organs()
    organ_orphans = sorted(
        o for o in organs
        if not _cov("freqtrade-bots", o) and not declared(o)
        and os.path.exists(os.path.join(ROOT, o))
    )

    # [2026-07-29] the live-bot MARKER path's both-lists rule: every file a
    # marker grep can match must also be in `paths:`, or the marker push
    # never starts the workflow (real-money deploys silently skipped).
    m_orphans = marker_orphans(live_marker_filters(), globs)
    if m_orphans:
        print("MARKER-ORPHANED — these files are in a LIVE-bot marker grep "
              "but NOT in `paths:`.\nA [deploy-live-*] push touching only "
              "one of them fires NO workflow at all —\nthe real-money deploy "
              "is silently skipped.\n")
        for svc, atom in m_orphans:
            print(f"  {atom:<32} live marker grep -> service {svc}")
        print("\n  Fix: add the path to the `paths:` block in "
              ".github/workflows/railway-redeploy.yml.\n")

    # [2026-07-30 (hi)] PAIRED ARMS — reported BEFORE the file-level verdicts,
    # because an unpaired arm is not a missing file (every file here has a route)
    # and a reader scanning for orphans would never find it.
    arm_bad = arm_pairing_orphans()
    if arm_bad:
        print("ARM-PAIRING BROKEN — an A/B experiment's two arms do not deploy "
              "together.\nThe judge's ARM DRIFT gate then refuses every "
              "promotion: 'this window measures a\ncode delta, not edge'. The "
              "failure is not a red build — it is a promotion\npipeline that "
              "silently freezes.\n")
        for live, ctrl, why in arm_bad:
            print(f"  {live} / {ctrl}\n      {why}")
        print("\n  Fix: append BOTH service names in the SAME decide branch of "
              ".github/workflows/\n  railway-redeploy.yml, under one condition, "
              "so neither arm can ship alone.\n  Keep the SERVICE split (the "
              "control container holds no keys) — join the CLOCK.\n")

    if arm_bad and not (m_orphans or orphans or organ_orphans or census_bad):
        print(f"audit_deploy_coverage: {len(arm_bad)} UNPAIRED arm(s); "
              f"{len(ok_declared)} declared exception(s).")
        return 1
    if m_orphans and not (orphans or organ_orphans or census_bad):
        print(f"audit_deploy_coverage: {len(m_orphans)} MARKER-ORPHANED "
              f"file(s); {len(ok_declared)} declared exception(s).")
        return 1
    if orphans or organ_orphans:
        print("DEPLOY-ORPHANED — these ship in an auto-deployed image but no "
              "push can move them.\nEditing one is a SILENT NO-OP: green CI, "
              "green tests, old code still running.\n")
        seen = set()
        for f, svc, df in orphans:
            if f in seen:
                continue
            seen.add(f)
            print(f"  {f:<32} in {df} -> service {svc}")
        for o in organ_orphans:
            if o in seen:
                continue
            seen.add(o)
            print(f"  {o:<32} launched by run_all.sh -> service freqtrade-bots")
        print("\n  Fix: add the path to BOTH the `paths:` block AND the service's "
              "`grep -qE` in\n  .github/workflows/railway-redeploy.yml — or DECLARE "
              "it in DEPLOY_COVERAGE_OK\n  with a reason. Both lists bind: `paths:` "
              "gates whether the job RUNS,\n  the grep picks the service. A file in "
              "one and not the other cannot deploy.\n  (You CAN `git push` a "
              "workflow file — the PAT has the scope. TESTED 17-Jul,\n  ce446c7. "
              "The 'web editor only' caveat is FALSE and was steering sessions\n"
              "  away from CI fixes for weeks — see push-straight-to-main.)")
        print(f"\naudit_deploy_coverage: {len(seen)} ORPHANED file(s); "
              f"{len(ok_declared)} declared exception(s).")
        return 1
    if census_bad:
        print(f"audit_deploy_coverage: {len(census_bad)} UNROUTED image(s); "
              f"{len(ok_declared)} declared exception(s).")
        return 1

    print(f"audit_deploy_coverage: OK — every runnable file in an auto-deployed "
          f"image is covered by a push path or declared, and every image in the "
          f"repo is claimed by a deploy story ({len(ok_declared)} declared).")
    return 0


def _extract_live_marker_block():
    """The decide step's OPT-IN live-bot marker logic, lifted verbatim from the
    workflow: the lines from `msgs="$(git log ...` through the fi that closes the
    trail-blazer-live (Farmer) block. Returns the raw lines (list). Raises if the
    gate is missing/unclosed — a real-money deploy gate that vanished must not
    read as 'nothing to test'."""
    lines = _read(WORKFLOW).splitlines()
    try:
        start = next(i for i, l in enumerate(lines) if 'msgs="$(git log' in l)
    except StopIteration:
        raise AssertionError("live-bot marker block not found (no `msgs=$(git log` "
                             "line) — the opt-in real-money deploy gate may be gone")
    block, seen_farmer = [], False
    for l in lines[start:]:
        block.append(l)
        if "trail-blazer-live" in l:
            seen_farmer = True
        if seen_farmer and l.strip() == "fi":
            return block
    raise AssertionError("live-bot marker block never closed (no Farmer `fi`)")


def _marker_logic_selftest():
    """Behavioral test of the OPT-IN live-bot deploy markers, BOUND to the real
    decide-step bash (extracted above, run under bash) so a future edit that lets
    an UNMARKED push deploy real money turns this RED. Synthetic INPUTS, real
    LOGIC, safety-INVARIANT assertions — the covered() pattern applied to the
    marker gate. 'No marker -> no real-money deploy' is a CONTRACT, not today's
    tree state, so asserting it is not the good-news-fails trap _selftest() avoids
    elsewhere. Skips only if bash is genuinely absent (never on a real assertion)."""
    import shutil
    import subprocess
    if not shutil.which("bash"):
        print("  (marker-logic test SKIPPED — no bash on this host)")
        return
    block = _extract_live_marker_block()
    joined = "\n".join(block)
    # sanity: we grabbed the REAL gate, not a gutted stub (else a mutation that
    # deletes the block would make the behavioral cases vacuously pass)
    for needle in ("[deploy-live-taker]", "[deploy-live-farmer]", "[deploy-live]",
                   "tide-rider-lighter-live", "trail-blazer-live", "live_all"):
        assert needle in joined, f"marker gate missing {needle!r} — refusing to vouch"
    indent = min(len(l) - len(l.lstrip()) for l in block if l.strip())
    body = [l[indent:] if len(l) >= indent else l for l in block]
    body[0] = 'msgs="$2"'            # swap the git-log fetch for the fixture
    script = ("set -uo pipefail\n"
              'changed="$1"; svcs=""; live_all=0\n'
              "{\n" + "\n".join(body) + "\n} >/dev/null\n"   # drop the '-> marker' echoes
              'printf "%s" "$svcs"\n')

    def decide(changed, msgs):
        r = subprocess.run(["bash", "-c", script, "b", changed, msgs],
                           capture_output=True, text=True)
        assert r.returncode == 0, f"decide bash failed ({r.returncode}): {r.stderr}"
        return r.stdout.strip()

    # [2026-07-30 (hi)] `F` is now the Farmer's BRANCH OUTPUT, not one service:
    # its two experiment arms are appended together so neither can ship alone.
    # Every expectation below that previously read "trail-blazer-live" therefore
    # reads both — and that is the assertion, not a fixture accommodation: a
    # farmer deploy that emits only the live service is the arm-drift bug.
    T = "tide-rider-lighter-live"
    F = "trail-blazer-live,funding-farmer-shadow"
    cases = [
        # HAZARD — an unmarked push must NEVER deploy a real-money book
        ("lighter_funding_bot.py", "fix funding slope", ""),
        ("lighter_ticket_taker.py", "tweak taker", ""),
        ("venues/safety.py", "rails tweak", ""),
        (f"lighter_funding_bot.py\nvenues/safety.py", "Farmer WIP (dark)", ""),
        # intended deploys
        ("lighter_funding_bot.py", "ship [deploy-live-farmer]", F),
        ("lighter_funding_bot.py", "both [deploy-live]", F),
        ("lighter_ticket_taker.py", "ship [deploy-live-taker]", T),
        ("lighter_ticket_taker.py", "ship [deploy-live]", T),
        ("venues/safety.py", "shared [deploy-live]", f"{T},{F}"),
        # isolation: a bot-only [deploy-live] must NOT restart the other bot
        ("lighter_funding_bot.py", "farmer-only [deploy-live]", F),
        ("lighter_ticket_taker.py", "taker-only [deploy-live]", T),
        # wrong marker for the changed file does nothing
        ("lighter_funding_bot.py", "wrong [deploy-live-taker]", ""),
    ]
    for changed, msgs, exp in cases:
        got = decide(changed, msgs)
        assert got == exp, (f"marker gate BROKEN: changed={changed!r} msgs={msgs!r} "
                            f"-> {got!r}, want {exp!r}")


def _selftest_run_scalar_budget():
    """[(ls)] The extractor is pinned on fixtures with EXACT known lengths —
    dedent semantics included, because over-measuring indentation by ~10
    chars/line would keep this guard permanently red on a healthy file (the
    inverse cry-wolf). Mutation-verified at authoring time: dropping the
    dedent, the has-expr filter, or the budget comparison each reddens this."""
    fx = (
        "jobs:\n"
        "  j:\n"
        "    steps:\n"
        "      - name: short with expr\n"
        "        run: |\n"
        "          echo \"${{ github.event_name }}\"\n"
        "          echo two\n"
        "      - name: long no expr\n"
        "        run: |\n"
        "          " + "x" * 30000 + "\n"
        "      - name: single line\n"
        "        run: echo hi\n"
    )
    rows = run_scalar_lengths(fx)
    assert len(rows) == 3, rows
    # block 1: dedented content is exactly the two echo lines
    ln1, n1, e1 = rows[0]
    assert n1 == len('echo "${{ github.event_name }}"\n' + "echo two\n"), rows[0]
    assert e1 is True
    # block 2: 30000 x's + newline, NO expression -> never flagged
    _ln2, n2, e2 = rows[1]
    assert n2 == 30001 and e2 is False, rows[1]
    # single-line run measured too
    assert rows[2][1] == len("echo hi"), rows[2]
    # the guard flags ONLY expression-bearing scalars over budget
    assert oversized_run_scalars(fx) == [], \
        "a 30k scalar with no expression must not flag — GitHub only " \
        "templates the ones that interpolate"
    fat = ("jobs:\n  j:\n    steps:\n      - run: |\n"
           "          echo \"${{ x }}\"\n"
           "          " + "y" * (RUN_SCALAR_BUDGET + 10) + "\n")
    flagged = oversized_run_scalars(fat)
    assert len(flagged) == 1 and flagged[0][1] > RUN_SCALAR_BUDGET, flagged
    # and the REAL workflow is currently under budget with its expressions —
    # asserted on the live file because this is the guard's whole job; if it
    # reds here, TRIM THE SCALAR, do not touch the budget.
    assert oversized_run_scalars() == [], (
        "the deploy workflow's expression-bearing run scalar is over "
        f"budget ({RUN_SCALAR_BUDGET}); GitHub hard-fails at {RUN_SCALAR_CAP}")
    assert RUN_SCALAR_BUDGET < RUN_SCALAR_CAP


def _selftest():
    """Drives the parser against SYNTHETIC fixtures, never against today's real
    violations — a test that asserts the current breakage still exists demands
    the defect remain (tests-must-not-fail-on-good-news)."""
    _selftest_run_scalar_budget()
    fs = workflow_filters()
    assert "freqtrade-bots" in fs, fs.keys()
    assert "pnl-dashboard" in fs, fs.keys()
    m = lambda svc, p: any(rx.match(p) for rx in fs[svc])
    # POSITIVE: these four predate the 07-07 filter and must always be covered.
    for p in ("fleet_risk.py", "regime_oracle.py", "market_pulse.py",
              "freqtrade_pnl_poller.py"):
        assert m("freqtrade-bots", p), f"{p} should be covered"
    assert m("freqtrade-bots", "user_data/strategies/X.py"), "user_data/ prefix"
    # NEGATIVE — on a SYNTHETIC regex, never on the real tree.
    # [2026-07-17] This line used to be `assert not m("freqtrade-bots",
    # "bot_learn.py"), "brain must read as orphaned"` — and it went RED the hour
    # someone ADDED the brain to the filter. A test that fails on GOOD NEWS is a
    # test that demands the defect remain, and this file's own selftest docstring
    # says so three lines up. I wrote the warning and the violation in the same
    # commit. The detector's ability to SEE a gap is a property of the regex, so
    # prove it on a fixture whose gap cannot be fixed out from under it.
    import re as _re
    fake = [_re.compile(r"^(only_this\.py$)")]
    _m = lambda p: any(rx.match(p) for rx in fake)
    assert _m("only_this.py"), "fixture sanity"
    assert not _m("bot_learn.py"), "detector must be able to report a gap"
    assert not _m("x_only_this.py"), "must be anchored"
    assert not _m("only_this.pyc"), "must be exact, not a prefix"

    # COPY reconstruction, incl. the multi-source form
    import tempfile
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "Dockerfile.t")
        open(p, "w").write("FROM x\nCOPY a.py b.py /app/\nCOPY venues/ /app/venues/\n")
        f, ca = image_files(p)
        assert f == {"a.py", "b.py", "venues/"}, f
        assert ca is False
        open(p, "w").write("FROM x\nCOPY . .\n")
        _, ca = image_files(p)
        assert ca is True, "COPY . . must set catch_all (everything ships)"

    # BOTH lists bind: `paths:` gates the job, the greps pick the service.
    # Today the real workflow's two lists agree, so this is a LATENT false-OK —
    # it fires the moment someone edits one list and not the other, which is
    # precisely what extending this workflow requires. Fixtures, so the test
    # proves the RULE rather than today's accident.
    globs = ["'x'"] and ["bot_learn.py", "user_data/**"]
    assert _path_listed("bot_learn.py", globs)
    assert _path_listed("user_data/strategies/S.py", globs), "dir/** prefix"
    assert not _path_listed("fleet_risk.py", globs), "must not match by accident"
    assert not _path_listed("bot_learn.pyc", globs), "exact filename, not prefix"
    # the false-OK itself: in a grep, absent from paths: -> CANNOT deploy
    grep_ok = True
    assert not (grep_ok and _path_listed("fleet_risk.py", globs)), \
        "a file in the grep but not paths: must NOT read as covered"
    assert workflow_paths() is not None, "real paths: block must parse"
    assert len(workflow_paths()) > 5, "paths: parse looks truncated"

    # DRIVE covered() ITSELF — with injected fixtures, not around it.
    # My first two attempts at this test both mutation-SURVIVED: the assertions
    # exercised _path_listed() and a local lambda, so reverting the real rule to
    # grep-only changed nothing and the suite stayed green. Testing AROUND a
    # function is not testing it. covered() takes filters/globs as parameters
    # precisely so this can reach it.
    F = {"svc": [re.compile(r"^(a\.py$|b\.py$)")]}
    assert covered("svc", "a.py", F, ["a.py"]) is True, "in BOTH lists -> deploys"
    assert covered("svc", "b.py", F, ["a.py"]) is False, \
        "in the GREP but not paths: -> the job never runs -> must NOT read covered"
    assert covered("svc", "a.py", F, []) is False, "paths: empty -> nothing runs"
    assert covered("svc", "z.py", F, ["z.py"]) is False, \
        "in paths: but no grep -> job runs, deploys nothing -> not covered"
    assert covered("svc", "a.py", F, None) is False, \
        "unparseable paths: must fail CLOSED, never open"
    assert covered("nope", "a.py", F, ["a.py"]) is False, "unknown service"

    # [2026-07-29] the live-bot MARKER both-lists rule — fixtures first
    # (the rule must be provable on a gap that cannot be fixed out from
    # under the test), then the real workflow's parser shape.
    fx, pfx = marker_atoms(r"^(a\.py$|venues/|Dockerfile\.x$|junk)")
    assert fx == ["a.py", "Dockerfile.x"] and pfx == ["venues/"], (fx, pfx)
    mm = {"svc-live": r"^(a\.py$|venues/|loop\.sh$)"}
    assert marker_orphans(mm, ["a.py", "venues/**", "loop.sh"]) == [], \
        "all atoms in paths: -> no orphans"
    assert marker_orphans(mm, ["a.py", "venues/**"]) == [("svc-live", "loop.sh")], \
        "a grep-only file must be reported — the marker can never fire for it"
    assert marker_orphans(mm, ["a.py", "loop.sh"]) == [("svc-live", "venues/**")], \
        "a grep-only PREFIX must be reported too"
    assert marker_orphans(mm, None), "unparseable paths: must fail CLOSED"
    lm = live_marker_filters()
    assert "tide-rider-lighter-live" in lm and "trail-blazer-live" in lm, (
        "variable-form marker greps must parse — #100 moved them into shell "
        f"vars and the old parser lost both live services: {sorted(lm)}")
    # declared(): longest-prefix, so venues/ covers its children
    assert declared("venues/lighter_client.py"), "venues/ prefix must cover children"
    assert declared("lighter_funding_bot.py")
    assert declared("bot_learn.py") is None, "brain is NOT declared — it's a real gap"
    for k, v in DEPLOY_COVERAGE_OK.items():
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"
    # the OPT-IN live-bot marker gate — bound to the real workflow bash
    _marker_logic_selftest()

    # [2026-07-30 (hi)] PAIRED ARMS. Three states, and the middle one is the
    # whole reason this exists: "routed, but on a different push" is drift by a
    # slower route and reads as covered to every per-file check.
    with open(os.path.join(ROOT, WORKFLOW)) as _fh:
        _wf = _fh.read()
    assert arm_pairing_orphans(_wf) == [], (
        "the shipped workflow does not deploy the Farmer's two arms together: "
        f"{arm_pairing_orphans(_wf)}")
    _gone = arm_pairing_orphans(_wf.replace("funding-farmer-shadow", ""))
    assert len(_gone) == 1 and "NO deploy route" in _gone[0][2], _gone
    _split = arm_pairing_orphans(
        _wf.replace("trail-blazer-live,funding-farmer-shadow", "trail-blazer-live")
        + "\n# funding-farmer-shadow mentioned but never appended\n")
    assert len(_split) == 1 and "same decide branch" in _split[0][2], _split
    for _live, _ctrl in PAIRED_ARMS.items():
        assert _live != _ctrl and _ctrl, (_live, _ctrl)

    # [2026-08-04 (jb)] THE IMAGE CENSUS — fixtures first (the gap must be
    # provable on a set that cannot be fixed out from under the test), then
    # the real tree.
    got = dockerfile_census(names=["Dockerfile.newbot", "Dockerfile.old"],
                            auto={"Dockerfile.old"}, marker=set(), manual=set())
    assert got == ["Dockerfile.newbot"], got
    assert dockerfile_census(names=["Dockerfile.newbot"], auto=set(),
                             marker={"Dockerfile.newbot"}, manual=set()) == [], \
        "a live-marker-gated image is a claimed image"
    assert dockerfile_census(names=["Dockerfile.newbot"], auto=set(),
                             marker=set(), manual={"Dockerfile.newbot"}) == [], \
        "a declared manual image is a claimed image"
    assert dockerfile_census(names=["Dockerfile"], auto=set(), marker=set(),
                             manual=set()) == ["Dockerfile"], \
        "the bare Dockerfile is an image too — the census must see it"
    _lmdf = live_marker_dockerfiles()
    assert {"Dockerfile.tickettaker", "Dockerfile.fundinglighter"} <= _lmdf, (
        "the two LIVE images must be derivable from the marker greps — a "
        f"parser regression silently shrinks the claimed set: {sorted(_lmdf)}")
    for k, v in MANUAL_IMAGES_OK.items():
        assert os.path.exists(os.path.join(ROOT, k)), (
            f"{k} is declared manual but does not exist on disk — a "
            f"declaration for a deleted image is archaeology (I12); remove it")
        assert len(v) > 60, f"{k}: a reason must be a reason, not a label"
    assert not (set(MANUAL_IMAGES_OK) & set(AUTO_IMAGES)), \
        "an image cannot be both workflow-deployed and declared manual"
    assert dockerfile_census() == [], (
        "the shipped tree carries an UNROUTED image — run this script without "
        f"--selftest for the fix menu: {dockerfile_census()}")

    print("audit_deploy_coverage _selftest OK "
          "(parser + COPY reconstruction + declared-prefix + live-bot marker gate "
          "+ paired arms + image census, on fixtures)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
        sys.exit(0)
    sys.exit(main())
