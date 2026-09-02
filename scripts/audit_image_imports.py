#!/usr/bin/env python3
"""
audit_image_imports.py — the BORN-DARK guard (2026-07-17).

WHY THIS EXISTS
Three times now, code shipped that its IMAGE never contained. Every time the
failure was SILENT, because the fleet (correctly) guards optional imports:
  * 15-Jul `fleet_bus` — missing from the freqtrade image: the L2 veto and L4
    stake-mults never executed there. `try: import fleet_bus / except: pass`.
  * 16-Jul `event_sentinel.py` — added to run_all.sh, never COPY'd: the organ
    ran zero times from the day it "shipped".
  * 17-Jul `brain_stats.py` — imported by bot_learn behind try/except, never
    COPY'd: the brain ran its FROZEN v2 engine for a day while every doc,
    memory and consumer assumed v3. Nothing crashed. The only tell was a
    None field in its own payload.

The defect class: **the repo says a module exists; the image does not** — and
an import guard turns that into a degraded fallback instead of a crash.

WHAT IT CHECKS (pure static analysis; no network, no DB, stdlib only)
For every Dockerfile, reconstruct the FILE SET the image actually contains
(`COPY a.py b.py /dst/`, `COPY venues/ ./venues/`, `COPY . .`), then walk the
imports of EVERY python file in that set — including files inside COPY'd
DIRECTORIES (venues/, user_data/strategies/), which is where the real-money
surface lives — and report any repo-local module imported but not present.
Guarded imports are reported precisely BECAUSE the guard is what makes them
silent. Seeds also from every run path: the Dockerfile's CMD/ENTRYPOINT, any
COPY'd *.sh, and the service's railway*.toml `startCommand`.

DECLARING INTENT
Some omissions are deliberate ("this image's bots don't join the growth
rail"). Those go in BORN_DARK_OK with a REASON — the point is that
"optional by design" is DECLARED and reviewable, never invisible.

USAGE
    python3 scripts/audit_image_imports.py            # audit; exit 1 on findings
    python3 scripts/audit_image_imports.py --selftest

RUN IT whenever you add a module, a new import to shipped code, or a COPY
(CLAUDE.md rule). Dependency-free; runs in milliseconds.
"""
import ast
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# DECLARED-DELIBERATE omissions: (Dockerfile, module) -> why.
# An entry here says "this image is SUPPOSED to run without that module, and
# the guarded import's fallback is the intended behaviour". Anything not
# listed is a finding.
# ---------------------------------------------------------------------------
BORN_DARK_OK = {
    # [2026-09-02 (xl)] the JUDGE's receipt guard imports lighter_family_bot to
    # DRIVE `mum_bars` instead of grepping it for a literal — (xl) made that
    # function derive its keys from `MUM_LEVER_ATTRS`, which is strictly more
    # correct (the next lever cannot arrive unstamped) and defeats a substring
    # scan, this repo's own "a page-wide substring scan is not a structural
    # claim". The judge's image deliberately does NOT carry the family module —
    # that is exactly why every other check in that block reads the file as
    # TEXT — so the import is inside `_selftest_body`, reachable only under
    # `--selftest` (never on the container's run path), and is
    # except-ImportError'd with an explicit documented fallback to the text
    # check. The driven form runs where both modules exist: the repo, on every
    # CI push.
    ("Dockerfile.freqtrade", "lighter_family_bot"):
        "selftest-only receipt guard: drives mum_bars rather than grepping it, "
        "except-ImportError'd with a text-check fallback; the judge reads the "
        "family bot as text in production and never imports it",
    # [2026-07-30 PER-ASSET GATE step 2] the family selftest's DRIFT GUARD
    # (`NONCRYPTO_SYMS == regime_oracle.NONCRYPTO`) imports regime_oracle
    # only to compare two constant sets, guarded by except ImportError with
    # a skip. The family image deliberately does NOT carry the oracle
    # module (it consumes the oracle's PUBLISHED payload via fleet_bus /
    # bot_state, never the module — and the image has no pandas/numpy, the
    # oracle's hard deps). The drift check runs where both modules exist:
    # the repo, on every CI push. Runtime behavior needs only the static
    # set, which is present by definition.
    ("Dockerfile.familyshadow", "regime_oracle"):
        "selftest-only drift guard (static NONCRYPTO_SYMS vs the oracle's "
        "set), except-ImportError'd; the gate consumes the oracle's "
        "published payload via fleet_bus, never the module; CI runs the "
        "real check on every push from the repo",
    # venues/__init__.py guards `import fleet_tuning` ("images without the
    # module: lever inert"). These images are SHADOW/paper books that are not
    # in the evidence board's LIVE_ROWS, so they must NOT be sized by
    # `live.clip_scale` — a lever earned by the funding/trend bots' evidence.
    # Absent module -> _tuning is None -> operator env sizing. Deliberate.
    # (The two REAL-money images, fundinglighter + trendlighter, DO copy it.)
    **{(df, "fleet_tuning"): "shadow book outside the board's LIVE_ROWS — the "
                             "growth-rail clip lever must not size it; "
                             "venues/__init__ falls back to env sizing"
       # [(wv)] Dockerfile.familyshadow LEFT this list: the family image
       # copies fleet_tuning now — 👩 mum's shadow twin reads xp.mum.* as the
       # judge's experiment arm (venues/__init__ still clamps clip levers).
       for df in ("Dockerfile.dislocation",
                  "Dockerfile.funding", "Dockerfile.fundspread",
                  "Dockerfile.indexshadow", "Dockerfile.momolive",
                  "Dockerfile.momoshadow", "Dockerfile.perpslive",
                  "Dockerfile.psniper",
                  # [2026-08-13 (ls)] 🏦 Rich Dad — env-only config by
                  # design (no tuning lane, the Garrett choice), so the
                  # module would be a dead file in its image
                  "Dockerfile.kiyosaki",
                  # [2026-08-13 (mb)-(me)] the BOOKS cohort's second wave —
                  # 🧘 Douglas, 📐 Grimes, 🧙 Schwager, 🧮 Hull: all four
                  # env-only by design (the same Garrett choice), so the
                  # module would be a dead file in each image
                  "Dockerfile.douglas", "Dockerfile.grimes",
                  "Dockerfile.schwager", "Dockerfile.hull",
                  # [2026-08-18] 🪁 band-kelly — env-only by design (same
                  # Garrett choice); the ghost module it imports
                  # (lighter_dislocation_bot) also guard-imports
                  # fleet_tuning, so one declaration covers both sites
                  "Dockerfile.bandkelly",
                  # [2026-08-19 (ri)] 🧭 nav-cook — env-only by design (the
                  # same Garrett/Kelly choice, so its (hm) clock is
                  # single-policy by construction); like band-kelly it imports
                  # the retired ghost module for book_view/reference_prices,
                  # and that module guard-imports fleet_tuning, so this one
                  # declaration covers both sites. A book with no tuning lane
                  # must not carry the growth rail's clip lever.
                  "Dockerfile.navcook")},
    # [2026-07-17 VENUE SWAP] market-context COPYs venues/ purely for
    # venues.symbol_map.from_lighter (the fleet<->Lighter symbol authority)
    # after moving off Hyperliquid. It is an INSTRUMENT-ONLY collector: it
    # never calls venue_context(), constructs no client and places no order,
    # so neither module is reachable — but both are declared, not silent.
    ("Dockerfile.marketcontext", "fleet_tuning"):
        "instrument-only collector — never constructs a venue client, so "
        "venues/__init__'s guarded growth-rail import is inert by design; it "
        "imports venues.symbol_map (from_lighter) and nothing else. A "
        "collector that never trades must not be sized by a clip lever.",
    ("Dockerfile.marketcontext", "paper_broker"):
        "venues/shadow.py rides along in the COPY'd package but is imported "
        "LAZILY (venues/__init__:144, inside venue_context()) and this image "
        "never calls it — market_context only trades data, never orders. "
        "NOTE the latent trap this declares away: if anything in this image "
        "ever imports venues.shadow, it will crash on boot. Copy "
        "paper_broker.py rather than widening this reason.",
    # These two COPY user_data/ (for its configs/strategy files) but never
    # RUN the four fleet_bus-importing strategies with a live bus:
    ("Dockerfile.regime", "fleet_bus"):
        "runs RegimeSwitchV1 only (which does not import fleet_bus); service "
        "perps-regime-switch is RETIRED (RETIRED_ROWS + removed from "
        "railway-redeploy.yml 16-Jul)",
    ("Dockerfile.trainer", "fleet_bus"):
        "backtest/hyperopt image (freqtrade_retrain.py) — fleet_bus is inert "
        "in backtests by design (no DATABASE_URL); the strategies' import is "
        "try/except fail-open",
}

# Repo module names that COLLIDE with a stdlib name would make `import json`
# ambiguous. None exist today; this is a smell detector, NOT a noise filter
# (the import test below already restricts to repo-local names, so a gap here
# produces no false positives — it can only MASK a finding, hence the warn).
_STDLIB_NAMES = set(sys.builtin_module_names) | {
    "os", "sys", "re", "ast", "json", "time", "math", "logging", "argparse",
    "urllib", "datetime", "collections", "itertools", "functools", "typing",
    "dataclasses", "pathlib", "random", "statistics", "decimal", "bisect",
    "hashlib", "subprocess", "shutil", "glob", "csv", "io", "traceback",
    "warnings", "contextlib", "copy", "enum", "abc", "threading", "queue",
    "signal", "socket", "ssl", "base64", "uuid", "zoneinfo", "calendar",
    "textwrap", "string", "unittest", "sqlite3", "pickle", "gzip", "tempfile",
}


def repo_modules():
    """Importable repo-local top-level names: `foo.py` -> "foo", and package
    dirs (containing __init__.py) -> "venues"."""
    out = set()
    for f in os.listdir(ROOT):
        p = os.path.join(ROOT, f)
        if f.endswith(".py"):
            out.add(f[:-3])
        elif os.path.isdir(p) and os.path.exists(os.path.join(p, "__init__.py")):
            out.add(f)
    return out


def _imports_of_path(path, repo):
    """Repo-local top-level modules imported by ONE file (absolute imports).

    AST-based, so imports inside try/except AND inside functions are found —
    both are the silent shapes (the strategies import fleet_bus inside
    confirm_trade_entry, under try/except). Relative imports (`from .base
    import X`) are package-internal and satisfied by the directory COPY.
    """
    names = set()
    try:
        tree = ast.parse(open(path, encoding="utf-8", errors="ignore").read())
    except Exception:  # noqa: BLE001
        return names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                top = a.name.split(".")[0]
                if top in repo:
                    names.add(top)
        elif isinstance(node, ast.ImportFrom):
            if node.level:                      # relative -> package-internal
                continue
            top = (node.module or "").split(".")[0]
            if top in repo:
                names.add(top)
    return names


def parse_copies(dockerfile_path):
    """(sources, unparsed) for one Dockerfile.

    Sources are basenamed repo paths. `--from=<stage>` copies come from a
    build stage, not the repo, and are skipped. Forms we cannot reason about
    (globs, JSON-array COPY) are returned in `unparsed` and reported LOUDLY —
    a guard that silently mis-parses a correct Dockerfile into a bogus
    finding gets disabled, which is how you get the next born-dark incident.
    """
    out, unparsed = set(), []
    try:
        text = open(dockerfile_path).read()
    except Exception:  # noqa: BLE001
        return out, unparsed
    text = text.replace("\\\n", " ")
    for line in text.splitlines():
        line = line.strip()
        if not re.match(r"^COPY\s", line, re.I):
            continue
        if re.search(r"--from=", line, re.I):
            continue                            # from a build stage, not the repo
        body = re.sub(r"^COPY\s+", "", line, flags=re.I)
        if body.lstrip().startswith("["):       # JSON-array form
            unparsed.append(line)
            continue
        toks = [t for t in body.split() if not t.startswith("--")]
        if len(toks) < 2:
            continue
        for src in toks[:-1]:                   # last token is the destination
            if any(ch in src for ch in "*?"):
                unparsed.append(line)
                continue
            out.add(src.rstrip("/"))
    return out, unparsed


def _sh_modules(path):
    """Modules a shell script invokes: `python3 /freqtrade/x.py`, `python x.py`,
    `python3 -m x`. The path prefix is OPTIONAL — requiring a "/" would have
    missed the event_sentinel incident had run_all.sh used a relative path."""
    try:
        text = open(path).read()
    except Exception:  # noqa: BLE001
        return set()
    out = set(re.findall(r"python3?\s+(?:-\S+\s+)*(?:\S*/)?([A-Za-z_0-9]+)\.py",
                         text))
    out |= set(re.findall(r"python3?\s+-m\s+([A-Za-z_0-9]+)", text))
    return out


def entry_modules(dockerfile_path):
    """Modules named in this Dockerfile's CMD/ENTRYPOINT (continuations joined,
    same as parse_copies — a continued CMD was previously half-read)."""
    try:
        text = open(dockerfile_path).read().replace("\\\n", " ")
    except Exception:  # noqa: BLE001
        return set()
    out = set()
    for m in re.finditer(r"^(?:CMD|ENTRYPOINT)\s+(.+)$", text, re.I | re.M):
        out |= set(re.findall(r"([A-Za-z_0-9]+)\.py", m.group(1)))
    return out


def railway_start_modules():
    """{dockerfile: {modules}} from railway*.toml `startCommand`s — a REAL run
    path the Dockerfile never names (railway.momo.toml runs
    hyperliquid_momo_bot.py against the base Dockerfile, whose CMD is only a
    placeholder). Missing this leaves 4 services unaudited."""
    out = {}
    for f in sorted(os.listdir(ROOT)):
        if not (f.startswith("railway") and f.endswith(".toml")):
            continue
        try:
            text = open(os.path.join(ROOT, f)).read()
        except Exception:  # noqa: BLE001
            continue
        df = re.search(r'dockerfilePath\s*=\s*"([^"]+)"', text)
        sc = re.search(r'^\s*startCommand\s*=\s*"([^"]+)"', text, re.M)
        if not (df and sc):
            continue
        mods = set(re.findall(r"([A-Za-z_0-9]+)\.py", sc.group(1)))
        mods |= set(re.findall(r"-m\s+([A-Za-z_0-9]+)", sc.group(1)))
        if mods:
            out.setdefault(df.group(1), set()).update(mods)
    return out


def image_contents(dockerfile):
    """(present_top, files) for one image.

    present_top — names importable from the image's workdir: a COPY'd
      `foo.py` -> "foo"; a COPY'd package dir -> "venues"; `COPY . .` ->
      everything. Members of a COPY'd dir are deliberately NOT injected into
      the top-level namespace (venues/safety.py is `venues.safety`, not
      `safety`) — doing so would silently satisfy a missing top-level COPY.
    files — every repo .py file inside the image, to be import-walked.
    """
    path = os.path.join(ROOT, dockerfile)
    copies, unparsed = parse_copies(path)
    repo = repo_modules()
    present_top, files = set(), set()

    for src in copies:
        if src in (".", "./"):                  # whole-repo COPY
            present_top |= repo
            for r, _d, fs in os.walk(ROOT):
                if any(part in (".git", "__pycache__", ".venv", "scripts")
                       for part in r.split(os.sep)):
                    continue
                files |= {os.path.relpath(os.path.join(r, f), ROOT)
                          for f in fs if f.endswith(".py")}
            continue
        p = os.path.join(ROOT, src)
        if src.endswith(".py") and os.path.exists(p):
            present_top.add(os.path.basename(src)[:-3])
            files.add(os.path.relpath(p, ROOT))
        elif os.path.isdir(p):
            present_top.add(os.path.basename(src))
            for r, _d, fs in os.walk(p):
                if "__pycache__" in r:
                    continue
                files |= {os.path.relpath(os.path.join(r, f), ROOT)
                          for f in fs if f.endswith(".py")}
    return present_top, files, copies, unparsed


def audit_image(dockerfile):
    """[(importer, missing_module)] for one Dockerfile."""
    repo = repo_modules()
    present_top, files, copies, _unparsed = image_contents(dockerfile)
    path = os.path.join(ROOT, dockerfile)

    findings = []
    # 1. Every python file IN the image (incl. inside COPY'd dirs) must have
    #    its repo-local absolute imports present.
    for rel in sorted(files):
        for dep in sorted(_imports_of_path(os.path.join(ROOT, rel), repo)):
            if dep in present_top:
                continue
            if (dockerfile, dep) in BORN_DARK_OK:
                continue                        # declared deliberate
            findings.append((rel, dep))
    # 2. Every module the image RUNS must be present at all.
    runs = entry_modules(path) & repo
    runs |= railway_start_modules().get(dockerfile, set()) & repo
    for src in copies:
        p = os.path.join(ROOT, src)
        if src.endswith(".sh") and os.path.exists(p):
            runs |= _sh_modules(p) & repo
    for mod in sorted(runs):
        if mod not in present_top and (dockerfile, mod) not in BORN_DARK_OK:
            findings.append(("<CMD/startCommand/*.sh>", mod))
    return sorted(set(findings))


def _dockerfiles():
    return sorted(f for f in os.listdir(ROOT)
                  if f == "Dockerfile" or f.startswith("Dockerfile."))


def main():
    repo = repo_modules()
    shadowed = repo & _STDLIB_NAMES
    if shadowed:
        print(f"WARNING: repo modules shadow stdlib names {sorted(shadowed)} — "
              f"imports of these are ambiguous and are NOT audited.")
    total, unparsed_total = 0, 0
    for df in _dockerfiles():
        _pt, _f, _c, unparsed = image_contents(df)
        for line in unparsed:
            unparsed_total += 1
            print(f"{df}: UNPARSED COPY (not audited): {line.strip()}")
        findings = audit_image(df)
        if findings:
            total += len(findings)
            print(f"\n{df}:")
            for importer, missing in findings:
                print(f"  MISSING {missing}.py — imported/run by {importer}"
                      f"   (fix: COPY it, or declare it in BORN_DARK_OK "
                      f"with a reason)")
    if total or unparsed_total:
        print(f"\n{total} born-dark risk(s), {unparsed_total} unparsed COPY "
              f"line(s), across {len(_dockerfiles())} images. A guarded import "
              f"makes this SILENT in production — fix before shipping (see the "
              f"17-Jul brain_stats postmortem).")
        return 1
    print(f"audit_image_imports: OK — {len(_dockerfiles())} images; every "
          f"repo-local import (incl. inside COPY'd packages) is present or "
          f"declared in BORN_DARK_OK ({len(BORN_DARK_OK)} declared).")
    return 0


def _selftest():
    import tempfile
    repo = repo_modules()

    # --- parser: multi-source, flags, continuations, --from, globs, JSON ---
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "Dockerfile.t")
        open(p, "w").write(
            "FROM x\nCOPY a.py /app/a.py\n"
            "COPY --chown=u:u b.py c.py /app/\n"
            "COPY d.py \\\n     e.py /app/\n"
            "COPY --from=build /out/z.py /app/z.py\n"
            "COPY ./rel.py /app/rel.py\n"
            "CMD [\"sh\", \"-c\", \\\n  \"python3 /app/a.py\"]\n")
        got, unparsed = parse_copies(p)
        assert got == {"a.py", "b.py", "c.py", "d.py", "e.py", "./rel.py"}, got
        assert unparsed == [], unparsed          # --from is skipped, not unparsed
        assert entry_modules(p) == {"a"}, entry_modules(p)   # continuation joined
        p2 = os.path.join(d, "Dockerfile.g")
        open(p2, "w").write("FROM x\nCOPY *.py /app/\n")
        assert parse_copies(p2)[1], "a glob COPY must be reported UNPARSED"

    # --- shell scripts: absolute, relative, and -m invocations ---
    with tempfile.TemporaryDirectory() as d:
        p = os.path.join(d, "run.sh")
        open(p, "w").write("python3 /freqtrade/foo.py || true\n"
                           "python3 bar.py --once\n"
                           "python3 -m baz\n"
                           "freqtrade trade --config x.json\n")
        assert _sh_modules(p) == {"foo", "bar", "baz"}, _sh_modules(p)

    # --- guarded + function-level imports are found (the silent shapes) ---
    assert "brain_stats" in _imports_of_path(
        os.path.join(ROOT, "bot_learn.py"), repo), "try/except import missed"
    assert "fleet_bus" in _imports_of_path(
        os.path.join(ROOT, "user_data/strategies/DayTraderV5Gated.py"), repo), \
        "function-level guarded import missed"
    assert "fleet_tuning" in _imports_of_path(
        os.path.join(ROOT, "venues/__init__.py"), repo), \
        "guarded import inside a COPY'd PACKAGE missed"

    # --- packages are importable names; dir members are NOT top-level ---
    assert "venues" in repo, "package dirs must be repo modules"
    pt, files, _c, _u = image_contents("Dockerfile.trendlighter")
    assert "venues" in pt and "safety" not in pt, \
        "a package's members must not enter the top-level namespace"
    assert any(f.startswith("venues/") for f in files), \
        "files inside a COPY'd package must be walked"

    # --- NEGATIVE FIXTURE: the regression bar that the old vacuous
    # "repo is clean" check could never provide. An image COPYing a package
    # whose code imports a module the image lacks MUST be a finding.
    # (Modelled on the REAL 15-Jul fleet_bus incident.)
    probe = os.path.join(ROOT, "Dockerfile.borndarkselftest")
    try:
        open(probe, "w").write(
            "FROM python:3.11\nWORKDIR /app\n"
            "COPY lighter_trend_bot.py bot_pnl_store.py paper_broker.py ./\n"
            "COPY venues/ ./venues/\n")          # deliberately NO fleet_tuning
        f = audit_image("Dockerfile.borndarkselftest")
        assert any(m == "fleet_tuning" and i.startswith("venues/")
                   for i, m in f), \
            f"guard must flag a missing module imported INSIDE a COPY'd package: {f}"
    finally:
        os.remove(probe)

    # --- railway startCommands are a real run path ---
    rs = railway_start_modules()
    assert rs.get("Dockerfile", set()) >= {"hyperliquid_momo_bot",
                                           "lighter_perp_sniper"}, rs

    # --- the real repo must be clean (with intent DECLARED, not silent) ---
    bad = {df: audit_image(df) for df in _dockerfiles()}
    bad = {k: v for k, v in bad.items() if v}
    assert not bad, f"born-dark risk present: {bad}"
    print("audit_image_imports selftest OK (parser forms, sh/-m/CMD run paths, "
          "guarded+function-level+in-package imports, package namespacing, "
          "NEGATIVE fixture, railway startCommands, repo clean)")


if __name__ == "__main__":
    if "--selftest" in sys.argv:
        _selftest()
    else:
        sys.exit(main())
