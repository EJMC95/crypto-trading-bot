#!/usr/bin/env python3
"""Commit safely from a worktree that OTHER Claude sessions are editing.

    python3 scripts/session_commit.py -m "subject (xx)" -- a.py b.py
    python3 scripts/session_commit.py -m "..." --shared CHANGELOG.md -- a.py
    python3 scripts/session_commit.py --selftest

WHY THIS EXISTS (2026-08-16 (nx)). Three sessions routinely share this one
worktree, and `(lz)` recorded the damage: another session's `git add` landing in
this session's staged set, a `git commit` sweeping this session's CHANGELOG entry
under THEIR subject, and a partial-staging commit DELETING 91 lines of an entry
that had landed in between. CLAUDE.md's answer was `git commit -o <paths>`.

**MEASURED 16-Aug — that answer is half a fix, and the missing half is the half
that keeps biting.** In a scratch repo with one session editing `shared.md` and
another editing `mine.py`:

  * `git commit -o mine.py`   -> their `shared.md` edit is NOT swept.  Correct.
  * `git commit -o shared.md` -> their content is committed WITH mine.

`--only` commits the WORKING-TREE CONTENT of the named path. It ignores the
shared *index*, which is what the doctrine claimed and what it delivers — but it
cannot ignore the shared *working tree*, so the moment your path list names a
file another session is also editing, you commit their work under your subject.
That is precisely how `48c04b4` took this session's CLAUDE.md correction. The two
files it happens to every time are the two every session must touch:
**CHANGELOG.md and CLAUDE.md**.

WHAT THIS TOOL MAKES STRUCTURAL (not advice — the failure becomes impossible or
loud):

  1. **A PRIVATE INDEX.** Every git call runs with `GIT_INDEX_FILE` pointed at a
     throwaway file, so a concurrent `git add` cannot reach this commit and this
     commit cannot disturb anyone's staged set. The `(lz)` index half is gone.
  2. **PATHS ARE MANDATORY.** There is no bare-commit and no `-a` path through
     this tool; a commit is always an explicit list.
  3. **SHARED DOCTRINE FILES NEED OPT-IN.** `CHANGELOG.md` / `CLAUDE.md` are
     refused unless passed via `--shared`. Committing them stops being a
     side effect of a path list and becomes a deliberate act — the one gate
     `48c04b4` would have had to walk through.
  4. **THEIR DIFF IS SHOWN BEFORE IT LANDS.** For every `--shared` file the full
     diff is printed, because the only way to know a hunk is not yours is to
     look at it, and the doctrine's existing "READ BACK what landed" fires one
     step too late — after it is already committed and pushed.
  5. **SNAPSHOT -> COMMIT -> READ BACK.** Each path's bytes are captured before
     the commit and compared against `git show HEAD:<path>` after it. A write
     landing mid-commit is caught rather than discovered days later.

WHAT IT DOES NOT DO, said plainly: it cannot tell whose edit a hunk is. Git does
not record that, so no tool built on git can. A pre-existing foreign edit sitting
in a `--shared` file is surfaced (rule 4) and never auto-detected. **The only
complete fix is isolation** — one worktree per session:

    git worktree add .claude/worktrees/<name>

which gives a private index AND a private working tree, after which none of this
is needed. Three of this repo's sessions already work that way; the collisions
all came from the ones sharing the main worktree.
"""
import argparse
import os
import subprocess
import sys
import tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

#: Files EVERY session must edit, so they are the ones a path list silently
#: collects someone else's work in. Not a blocklist — an opt-in list.
SHARED_DOCTRINE = ("CHANGELOG.md", "CLAUDE.md")


def _git(*args, index=None, check=False, cwd=None):
    """Run git with a PRIVATE index when one is supplied."""
    env = dict(os.environ)
    if index:
        env["GIT_INDEX_FILE"] = index
    r = subprocess.run(("git",) + args, cwd=cwd or ROOT, env=env,
                       capture_output=True, text=True)
    if check and r.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed:\n{r.stderr}")
    return r


def classify(paths, shared):
    """-> (ok_paths, undeclared_shared). Pure, so the selftest can drive it.

    A shared doctrine file reaching the commit WITHOUT `--shared` is the
    refusal: it means the path list picked it up rather than the author
    choosing it.
    """
    declared = set(shared or ())
    ok, undeclared = [], []
    for p in paths:
        base = os.path.basename(p)
        if base in SHARED_DOCTRINE and p not in declared:
            undeclared.append(p)
        else:
            ok.append(p)
    return ok, undeclared


def snapshot(paths):
    """-> {path: bytes} for every path that exists. Missing files are deletions
    and carry None, so a delete still round-trips through the read-back."""
    out = {}
    for p in paths:
        full = os.path.join(ROOT, p)
        try:
            with open(full, "rb") as fh:
                out[p] = fh.read()
        except FileNotFoundError:
            out[p] = None
    return out


def removed_entry_headers(diff_text):
    """-> [header] for every `## <date> (<letter>)` the diff DELETES.

    [2026-08-16 (nx)] WHY THIS EXISTS, and it is the incident that closed this
    tool's own loop. Committing THIS tool, a `perl -pi -e 's/(nv)/(nx)/g'`
    letter-rename matched not only my own new header but ANOTHER SESSION'S
    entry of the same letter, and the file lost 90 lines of their work. The
    tool committed it faithfully and the read-back reported success — **which
    was true and useless**: `verify_readback` proves the commit matches the
    WORKING TREE, and the working tree was already wrong. A receipt for
    fidelity is not a receipt for correctness.

    So the one check that catches this is structural and cheap: a commit should
    ADD changelog entries, never REMOVE them. `(lz)` recorded the same
    destruction (91 lines) from a different cause, which is what makes it a
    class rather than a slip. Pure, so the selftest can drive it.
    """
    added, removed = set(), []
    for ln in (diff_text or "").splitlines():
        if ln.startswith("+## ") and not ln.startswith("+++"):
            added.add(ln[1:].strip())
        elif ln.startswith("-## ") and not ln.startswith("---"):
            removed.append(ln[1:].strip())
    # [(nx)] A MOVED ENTRY IS NOT A DELETED ONE — subtract the additions.
    # Caught by this guard firing on its own commit: entries here are prepended
    # constantly, so an entry that shifts position shows as BOTH `-##` and
    # `+##`, and reporting the minus alone blocks ordinary reshuffles. A guard
    # that fires on the normal case is one the next session learns to bypass,
    # which is how a real deletion then walks through ((gl)).
    return [h for h in removed if h not in added]


def verify_readback(snap, index=None):
    """-> [path] whose COMMITTED bytes differ from what we snapshotted.

    The commit is the claim; this is the receipt. `git diff --cached` is stale
    the moment it is read in a shared tree, so the only sound check is what the
    commit object actually holds.
    """
    bad = []
    for p, want in snap.items():
        r = _git("show", f"HEAD:{p}", index=index)
        got = r.stdout.encode() if r.returncode == 0 else None
        if want is None:
            if r.returncode == 0:
                bad.append(p)
            continue
        if got is None or got.replace(b"\r\n", b"\n") != want.replace(b"\r\n", b"\n"):
            bad.append(p)
    return bad


def main(argv=None):
    ap = argparse.ArgumentParser(
        description="Commit explicit paths from a shared worktree, safely.")
    ap.add_argument("-m", "--message", help="commit message")
    ap.add_argument("--shared", nargs="*", default=[],
                    help=f"explicitly include a shared doctrine file "
                         f"({', '.join(SHARED_DOCTRINE)})")
    ap.add_argument("--dry-run", action="store_true",
                    help="show what would be committed, commit nothing")
    ap.add_argument("--selftest", action="store_true")
    ap.add_argument("paths", nargs="*", help="paths to commit")
    a = ap.parse_args(argv)

    if a.selftest:
        return selftest()
    if not a.message:
        ap.error("-m/--message is required")

    paths = list(a.paths) + list(a.shared)
    if not paths:
        ap.error("no paths given — this tool never commits an implicit set")

    ok, undeclared = classify(list(a.paths), a.shared)
    if undeclared:
        print("\nREFUSING — shared doctrine file(s) in the path list without "
              "--shared:\n", file=sys.stderr)
        for p in undeclared:
            print(f"    {p}", file=sys.stderr)
        print("\nEvery session edits these, so a path list picks up THEIR "
              "unstaged work\nand commits it under your subject "
              "(measured: `git commit -o <shared>` does\nexactly this; it "
              "ignores the shared INDEX, never the shared WORKING TREE).\n"
              "Re-run with `--shared " + " ".join(undeclared) + "` after "
              "reading the diff below it prints.\n", file=sys.stderr)
        return 2

    # A private index: a concurrent `git add` cannot reach this commit, and this
    # commit cannot disturb anyone else's staged set.
    fd, index = tempfile.mkstemp(prefix="claude-session-index-")
    os.close(fd)
    os.unlink(index)
    try:
        # [(nx)] SEED IT FROM HEAD. An EMPTY private index has no tracked paths,
        # so `git diff HEAD -- p` reports every file as DELETED — which silently
        # broke the one feature that matters most here: the shared-file diff
        # printed `deleted file mode` instead of the foreign hunks it exists to
        # surface. The commit was correct throughout (`--only` reads the working
        # tree, not the index); only the DISPLAY lied, which is worse than a
        # crash — an operator who sees garbage once stops reading the output,
        # and this output is the whole safety mechanism ((gl)). Found by running
        # the tool end-to-end against the real incident shape rather than
        # trusting its unit tests.
        # A repo with no commits has no HEAD; an empty index is correct there.
        if _git("rev-parse", "--verify", "HEAD", index=index).returncode == 0:
            _git("read-tree", "HEAD", index=index, check=True)
        for p in a.shared:
            d = _git("diff", "HEAD", "--", p, index=index)
            if d.stdout.strip():
                print(f"\n=== FULL DIFF of shared file {p} — every hunk here "
                      f"lands in YOUR commit ===")
                print(d.stdout)
        # [(nx)] STAGE INTO THE PRIVATE INDEX EXACTLY ONCE, then commit that
        # index — do NOT use `git commit --only`, and do NOT stage twice.
        # Both were found by running this tool on its own commit:
        #   * `--only` requires every path to be KNOWN to git, so the two NEW
        #     files were silently dropped and the "will commit" summary listed
        #     neither. A tool that quietly commits LESS than you asked is worse
        #     than one that errors.
        #   * staging a second time then blew up on a DELETED path — the first
        #     `add` had already recorded the deletion, so the pathspec matched
        #     nothing on disk or in the index (`fatal: pathspec ... did not
        #     match any files`). One add, reused for the summary and the commit.
        # `add -A` covers additions, modifications AND deletions; the index is
        # private and seeded from HEAD, so the resulting tree is exactly
        # HEAD + these paths, and no concurrent `git add` can reach it.
        add = _git("add", "-A", "--", *paths, index=index)
        if add.returncode != 0:
            sys.stderr.write(add.stderr)
            return 1
        st = _git("diff", "--cached", "--stat", "HEAD", index=index)
        print("\n=== will commit ===")
        print(st.stdout or "  (no changes)")

        # [(nx)] A COMMIT MUST NOT DELETE A CHANGELOG ENTRY. Checked on the
        # STAGED diff, i.e. before anything lands. See `removed_entry_headers`
        # for the incident: this tool's own commit destroyed a concurrent
        # session's entry via a global letter-rename, and the read-back passed
        # because the working tree was already corrupt. Refuses rather than
        # warns — a warning on a passing run is not a guard ((gl)).
        gone = removed_entry_headers(
            _git("diff", "--cached", "HEAD", "--", "CHANGELOG.md",
                 index=index).stdout)
        if gone:
            print("\nREFUSING — this commit DELETES changelog entr(ies):\n",
                  file=sys.stderr)
            for h in gone:
                print(f"    {h[:100]}", file=sys.stderr)
            print("\nAlmost always a global in-place edit (a `perl -pi`/`sed`\n"
                  "letter-rename) that matched another session's entry too, or a\n"
                  "file rebuilt from a stale snapshot. Restore them\n"
                  "(`git show HEAD:CHANGELOG.md`) and re-run. If a deletion is\n"
                  "genuinely intended, commit CHANGELOG.md separately.\n",
                  file=sys.stderr)
            return 4
        if a.dry_run:
            print("--dry-run: nothing committed")
            return 0

        snap = snapshot(paths)
        r = _git("commit", "-m", a.message, index=index)
        sys.stdout.write(r.stdout)
        if r.returncode != 0:
            sys.stderr.write(r.stderr)
            return 1

        bad = verify_readback(snap, index=index)
        if bad:
            print("\nCOMMITTED CONTENT DOES NOT MATCH WHAT WAS SNAPSHOTTED — "
                  "a concurrent write\nlanded mid-commit:", file=sys.stderr)
            for p in bad:
                print(f"    {p}", file=sys.stderr)
            print("\nThe commit EXISTS. Inspect it (`git show --stat HEAD`) "
                  "before pushing.", file=sys.stderr)
            return 3
        # [(ob)] REFRESH THE WORKTREE'S REAL INDEX FOR OUR PATHS ONLY.
        # The commit was built in a PRIVATE index, so the worktree's own index
        # never learned about it and still reports our files as modified (and a
        # newly added file as DELETED). That is invisible in a shared tree — the
        # index there is already churning — but in a per-session worktree it is
        # immediately fatal: `git rebase` refuses with "you have unstaged
        # changes", so the publish step cannot run. Found by dogfooding the
        # worktree flow this same commit introduces.
        # Scoped with `-- <paths>` deliberately: a bare `git reset` would also
        # unstage whatever ANOTHER session had staged, which is the very thing
        # this tool exists not to do.
        rs = _git("reset", "-q", "HEAD", "--", *paths, index=None)
        if rs.returncode != 0:
            print("note: could not refresh the worktree index for "
                  f"{' '.join(paths)} — `git status` may show phantom changes "
                  "until you run `git reset HEAD -- <paths>`", file=sys.stderr)
        files = _git("show", "--stat", "--format=", "HEAD", index=index).stdout
        print("\n=== read-back OK — the commit holds exactly these bytes ===")
        print(files)
        return 0
    finally:
        if os.path.exists(index):
            os.unlink(index)


def selftest():
    # classify — a shared file must be opted into, by BASENAME not full path
    ok, und = classify(["a.py", "CHANGELOG.md"], [])
    assert ok == ["a.py"] and und == ["CHANGELOG.md"]
    ok, und = classify(["a.py"], ["CHANGELOG.md"])
    assert ok == ["a.py"] and und == []
    ok, und = classify(["a.py", "CLAUDE.md"], ["CLAUDE.md"])
    assert und == [], "an opted-in shared file is not a refusal"
    # a shared NAME in another directory is still shared — the collision is
    # about the name every session edits, and a nested copy is the same trap
    _ok, und = classify(["docs/CLAUDE.md"], [])
    assert und == ["docs/CLAUDE.md"]
    # ordinary files never trip it
    ok, und = classify(["scripts/x.py", "tests/y.py"], [])
    assert ok == ["scripts/x.py", "tests/y.py"] and und == []
    assert classify([], []) == ([], [])

    # snapshot round-trips bytes and marks a missing file as a deletion
    import tempfile as _tf
    d = _tf.mkdtemp()
    global ROOT
    _root = ROOT
    try:
        ROOT = d
        with open(os.path.join(d, "f.txt"), "wb") as fh:
            fh.write(b"hello\n")
        snap = snapshot(["f.txt", "gone.txt"])
        assert snap["f.txt"] == b"hello\n"
        assert snap["gone.txt"] is None, "a missing file is a DELETION, not a skip"
    finally:
        ROOT = _root

    # [(nx)] removed_entry_headers — the incident that closed the tool's loop
    d = ("--- a/CHANGELOG.md\n+++ b/CHANGELOG.md\n"
         "+## 2026-08-16 (nx) — mine\n"
         "-## 2026-08-16 (nv) — THEIRS, destroyed by a global rename\n"
         "-some body line\n")
    got = removed_entry_headers(d)
    assert got == ["## 2026-08-16 (nv) — THEIRS, destroyed by a global rename"], got
    assert removed_entry_headers(
        "--- a/x\n+++ b/x\n+## 2026-08-16 (nx) — only additions\n") == [], \
        "an ADDED header is not a deletion"
    assert removed_entry_headers("") == [] and removed_entry_headers(None) == []
    assert removed_entry_headers("-## not-a-date (xx) — junk") == [
        "## not-a-date (xx) — junk"], "shape-matched on the header prefix"
    # a MOVED entry appears as both - and + : not a deletion
    moved = ("-## 2026-08-16 (nx) — mine\n+## 2026-08-16 (nx) — mine\n"
             "-## 2026-08-16 (nv) — theirs, really gone\n")
    assert removed_entry_headers(moved) == [
        "## 2026-08-16 (nv) — theirs, really gone"], \
        "a repositioned entry must not read as deleted"

    print("session_commit selftest OK (shared files need opt-in incl. nested; "
          "snapshot round-trips bytes and records deletions; a commit that DELETES a changelog entry is refused)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
