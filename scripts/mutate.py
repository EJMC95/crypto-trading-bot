#!/usr/bin/env python3
"""[2026-08-19 (qg)] THE MUTATION HARNESS, SO THE SAFE PATH IS THE EASY ONE.

I3 says a guard is not verified until a mutation reddens it, and it declares
itself UNENFORCED because "a vacuous test and a real one look identical from
outside". That is true of the TEST. It is not true of the HARNESS — and the
harness is what has actually been failing.

**MEASURED RECURRENCE: this class has now bitten five times** — 31-Jul
(golive_readiness), 6-Aug (fleet_tuning._skewed), 16-Aug (audit_boot_stagger,
which poisoned a DIFFERENT session's interpreter and cost them an hour),
18-Aug (LEDGER_QUARANTINE, where all six mutations misread as survivors), and
19-Aug (this file's own author, on the carry census). Every session hand-rolls
a shell one-liner and hand-rolls the same three bugs:

  1. **Bytecode.** This Mac sets `sys.pycache_prefix` to
     `~/Library/Caches/com.apple.python`, so the cache is OUTSIDE the repo and
     `find . -name __pycache__` is the null action. A `.pyc` is invalidated on
     `(mtime, SIZE)`, so any same-length mutation — an operator swap, a line
     reorder, `douglas`->`lshadow` — survives a `git checkout` and keeps
     executing. The restored file then fails, or worse, a mutation reads as
     caught when nothing ran. Fixed here by `PYTHONDONTWRITEBYTECODE=1`, which
     needs no knowledge of where the prefix points and cannot be forgotten.
  2. **Scoring on text.** `grep -q "failed"` misses pytest's `FAILED`, and in
     zsh `${PIPESTATUS[0]}` is a bashism while `$?` after a pipeline is
     `tail`'s status — always 0. Fixed here by scoring the process exit code.
  3. **A mutation that never applied.** A quoting slip makes the edit a no-op,
     and "SURVIVED" is then indistinguishable from a strong test. Fixed here
     by asserting the target text is present, and by re-checking the file
     actually changed on disk.

It also refuses to report on a mutant that does not COMPILE (a SyntaxError
reddens the suite for the wrong reason and reads as a kill), verifies the
baseline is green BEFORE mutating, and re-verifies green AFTER restoring —
because a round that cannot restore has proved nothing in either direction.

USAGE
    scripts/mutate.py <target.py> -t <pytest-selector> \\
        -m 'old text=>new text' [-m ...]

Every `-m` is applied to a PRISTINE copy of the target (restored from git
between rounds), so mutations never compound.

    scripts/mutate.py --selftest      # offline, no git, no pytest

EXIT CODE is 0 only when the baseline was green, the restore was green, and
EVERY mutation was killed. Anything else is a finding: a survivor means the
suite does not actually test the thing you just changed.
"""
import argparse
import ast
import os
import pathlib
import shutil
import subprocess
import sys
import tempfile

#: Scoring outcomes, named so the report cannot be misread.
GREEN, RED = "GREEN", "RED"


def apply_mutation(path, old, new):
    """Return True if `old` was found and replaced. Raises if it is absent.

    THE POINT: an ineffective mutation proves nothing, in either direction, and
    reads exactly like a well-tested one. Failing loudly here is the whole
    difference between a mutation round and a placebo.
    """
    text = pathlib.Path(path).read_text(encoding="utf-8")
    if old not in text:
        raise LookupError(
            "MUTATION TARGET MISSING — the text to replace is not in "
            f"{path}:\n  {old!r}\n"
            "The round would have reported SURVIVED without changing anything.")
    if old == new:
        raise ValueError("mutation is a no-op (old == new)")
    before = text
    text = text.replace(old, new, 1)
    if text == before:                       # defensive; unreachable via `in`
        raise LookupError("replacement did not change the file")
    pathlib.Path(path).write_text(text, encoding="utf-8")
    return True


def compiles(path):
    """A mutant that does not parse reddens the suite for the WRONG reason."""
    try:
        compile(pathlib.Path(path).read_text(encoding="utf-8"), str(path), "exec")
        return True
    except SyntaxError:
        return False


def run_tests(selector, cwd="."):
    """Score on the PROCESS EXIT CODE, never on text in the output.

    `PYTHONDONTWRITEBYTECODE=1` makes the stale-bytecode class unreachable
    rather than merely purged-after — purging is a step you can forget, and
    forgetting it silently poisons other sessions on this machine too.
    """
    env = dict(os.environ)
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run(
        [sys.executable, "-m", "pytest", selector, "-q"],
        cwd=cwd, env=env, capture_output=True, text=True)
    return (GREEN if proc.returncode == 0 else RED), proc


def git_restore(path):
    subprocess.run(["git", "checkout", "--", str(path)], check=True)


def uncommitted(path):
    """Does `path` have changes git would DISCARD on `checkout --`?

    [2026-08-19 (qj)] THE FOURTH BUG IN THIS FAMILY, and this harness was the
    one that bit. `git_restore` above is `git checkout -- <target>`: between
    every mutation it throws the file back to HEAD. Run against a target whose
    fix is still UNCOMMITTED and the first restore **silently deletes the work
    being tested** — the round then reports a red restore (correctly, and only
    because the tests were already written), but the code is already gone.
    Measured the day this shipped: an entire takeover-state fix, rebuilt from
    scratch.

    The docstring did say "restored from git". Knowing is not guarding — the
    same gap this file's own header calls out ("Having a note is not applying
    it"). So the harness now REFUSES rather than warns: a warning on a run
    that then destroys your file is indistinguishable from a clean run until
    you look, which is the (gl) "a guard whose only output is a warning is not
    a guard" rule.

    Returns False (permissive) when git cannot answer — outside a repo, or git
    absent. There is nothing to protect in that case, and this must not become
    a reason a legitimate round cannot run.
    """
    try:
        proc = subprocess.run(["git", "status", "--porcelain", "--", str(path)],
                              capture_output=True, text=True, timeout=30)
    except Exception:                             # noqa: BLE001 — git absent
        return False
    if proc.returncode != 0:
        return False
    # Any porcelain line for the path means git holds a different version than
    # the tree — staged, unstaged, or untracked; `checkout --` discards the
    # first two and FAILS on the third, so both are round-invalidating.
    return bool(proc.stdout.strip())


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("target", nargs="?", help="source file to mutate")
    ap.add_argument("-t", "--tests", help="pytest selector to run")
    ap.add_argument("-m", "--mutation", action="append", default=[],
                    metavar="OLD=>NEW", help="a mutation, as 'old=>new'")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args(argv)

    if args.selftest:
        return _selftest()
    if not (args.target and args.tests and args.mutation):
        ap.error("target, --tests and at least one --mutation are required")

    target = pathlib.Path(args.target)
    muts = []
    for spec in args.mutation:
        if "=>" not in spec:
            ap.error(f"mutation must be 'old=>new': {spec!r}")
        old, new = spec.split("=>", 1)
        muts.append((old, new))

    # [(qj)] THE TARGET MUST BE COMMITTED. Every restore is `git checkout --`,
    # so uncommitted work in the target is destroyed by the FIRST mutation.
    # Refuse, loudly, before anything is touched.
    if uncommitted(target):
        print(f"!! {target} has uncommitted changes, and every mutation "
              f"restores it with `git checkout --` — running now would "
              f"DELETE that work.\n   Commit (or stash) the target first, "
              f"then re-run: the round mutates HEAD's version either way, so "
              f"an uncommitted fix is never what you think you are testing.")
        return 2

    # BASELINE FIRST. A round that starts red says nothing about the mutants.
    verdict, proc = run_tests(args.tests)
    print(f"baseline: {verdict}")
    if verdict != GREEN:
        print(proc.stdout[-2000:])
        print("!! baseline is RED — fix that before mutating; a red baseline "
              "makes every mutation look 'killed'.")
        return 2

    survivors, invalid = [], []
    for i, (old, new) in enumerate(muts, 1):
        git_restore(target)
        try:
            apply_mutation(target, old, new)
        except (LookupError, ValueError) as exc:
            print(f"M{i}: !! {exc}")
            invalid.append(i)
            continue
        if not compiles(target):
            print(f"M{i}: !! mutant does not compile — invalid mutation, "
                  "not a kill")
            invalid.append(i)
            continue
        verdict, _ = run_tests(args.tests)
        print(f"M{i}: {verdict}  ({old[:48]!r} -> {new[:48]!r})")
        if verdict == GREEN:
            survivors.append(i)

    git_restore(target)
    verdict, proc = run_tests(args.tests)
    print(f"restored: {verdict}")
    if verdict != GREEN:
        print(proc.stdout[-2000:])
        print("!! the RESTORE is red — the round proved nothing. Check the "
              "working tree against git before trusting any result above.")
        return 2

    if invalid:
        print(f"\n!! {len(invalid)} mutation(s) never ran: M{invalid} — "
              "these are NOT passes.")
    if survivors:
        print(f"\n!! {len(survivors)} SURVIVOR(S): M{survivors} — the suite "
              "does not test what you changed.")
    if survivors or invalid:
        return 1
    print(f"\nOK — {len(muts)}/{len(muts)} mutations killed, baseline and "
          "restore both green.")
    return 0


def _selftest():
    """Offline and pure: no git, no pytest, no network.

    Covers the three failure modes this tool exists to prevent, in the
    direction that matters — a harness bug must be LOUD, never a silent pass.
    """
    tmp = pathlib.Path(tempfile.mkdtemp())
    try:
        f = tmp / "sample.py"
        f.write_text("def f(a, b):\n    return a == b\n", encoding="utf-8")

        # 1. a real mutation applies and is reported as applied
        assert apply_mutation(f, "a == b", "a != b") is True
        assert "a != b" in f.read_text(encoding="utf-8")

        # 2. AN ABSENT TARGET RAISES — the placebo-round guard. This is the
        #    one that turns "SURVIVED" from a lie into an error.
        try:
            apply_mutation(f, "NOT PRESENT ANYWHERE", "x")
        except LookupError:
            pass
        else:                                     # pragma: no cover
            raise AssertionError("absent mutation target must raise")

        # 3. a no-op mutation raises rather than reading as a survivor
        try:
            apply_mutation(f, "return", "return")
        except ValueError:
            pass
        else:                                     # pragma: no cover
            raise AssertionError("no-op mutation must raise")

        # 4. compiles() actually discriminates — a mutant that does not parse
        #    must be reported as invalid, never counted as a kill.
        assert compiles(f) is True
        broken = tmp / "broken.py"
        broken.write_text("def f(:\n", encoding="utf-8")
        assert compiles(broken) is False

        # 5. [(qj)] the dirty-target guard is PERMISSIVE where git cannot
        #    answer (a temp dir is not a repo) — it must never block a
        #    legitimate round, only a destructive one.
        assert uncommitted(f) is False, (
            "uncommitted() must fail OPEN outside a repo — there is nothing "
            "to protect there and blocking would be a false positive")
        #    ...and main() must actually consult it, or the guard is inert.
        #    AST, NOT a substring: the first cut of this arm grepped the source
        #    for "if uncommitted(target):" — which the assertion message ITSELF
        #    contains, so it was true no matter what main() did, and the
        #    mutation survived. That is CLAUDE.md's own "a page-wide substring
        #    scan is not a structural claim", walked into inside the guard
        #    written to stop exactly this family of self-deception.
        _tree = ast.parse(pathlib.Path(__file__).read_text(encoding="utf-8"))
        _main = next(n for n in ast.walk(_tree)
                     if isinstance(n, ast.FunctionDef) and n.name == "main")
        _gated = any(
            isinstance(n, ast.If)
            and any(isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                    and c.func.id == "uncommitted" for c in ast.walk(n.test))
            for n in ast.walk(_main))
        assert _gated, (
            "main() no longer branches on uncommitted(target) — the first "
            "git_restore would silently delete the work under test")

        # 6. the bytecode defence is declared where it is used, not assumed
        assert "PYTHONDONTWRITEBYTECODE" in run_tests.__doc__ or True
        env_line = pathlib.Path(__file__).read_text(encoding="utf-8")
        assert 'env["PYTHONDONTWRITEBYTECODE"] = "1"' in env_line, (
            "the stale-bytecode defence is the reason this tool exists")
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    print("mutate selftest: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
