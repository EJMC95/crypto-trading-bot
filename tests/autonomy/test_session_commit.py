"""[2026-08-16 (nx)] COMMITTING FROM A WORKTREE THREE SESSIONS SHARE.

THE INCIDENT. `(lz)` recorded the shared-tree damage: another session's `git add`
in this session's staged set, a `git commit` sweeping this session's CHANGELOG
entry under THEIR subject, a partial-staging commit deleting 91 lines of an entry
that landed in between. CLAUDE.md's answer was `git commit -o <paths>`.

MEASURED 16-Aug — that answer is HALF a fix, and it failed again the same day
(`48c04b4` committed this session's CLAUDE.md correction under another session's
subject). In a scratch repo:

    git commit -o mine.py    -> their shared.md edit NOT swept      (correct)
    git commit -o shared.md  -> their content committed WITH mine   (the hole)

`--only` commits the WORKING-TREE CONTENT of the named path: it ignores the
shared *index*, exactly as documented, and cannot ignore the shared *working
tree*. So the protection evaporates precisely on the two files every session must
touch — CHANGELOG.md and CLAUDE.md.

WHAT IS PINNED HERE:
  * a shared doctrine file in the path list without `--shared` is REFUSED —
    committing one becomes a deliberate act instead of a side effect;
  * basename matching, so `docs/CLAUDE.md` is not a bypass;
  * a private `GIT_INDEX_FILE`, so a concurrent `git add` can neither enter this
    commit nor be disturbed by it;
  * snapshot -> commit -> READ BACK against the commit object, because
    `git diff --cached` is stale the moment it is read in a shared tree;
  * a deletion round-trips (a missing file is a deletion, never a skip).

MUTATION-VERIFIED — each reddens this file:
  1. `classify` matching full paths instead of basenames (docs/CLAUDE.md slips)
  2. `SHARED_DOCTRINE` emptied (the refusal never fires)
  3. `snapshot` skipping missing files instead of recording None
  4. `verify_readback` returning [] unconditionally (the receipt goes blind)
  5. dropping the `read-tree HEAD` seed (the shared-file diff prints garbage)
  6. reverting to the ORIGINAL shipped form — no `git add`, `git commit --only`
     — which reddens both dogfooding tests below

NOTE ON MUTATION 6, because two narrower attempts SURVIVED and that is the
informative part: swapping `commit` back to `commit --only` alone, or adding a
second `git add`, both stay green. The single `git add -A` into the private
index is what does the work — with the paths staged, `--only` finds them and a
redundant second add merely fails into an unchecked return code. So the fix is
the ADD, not the removal of `--only`, and only reverting BOTH together
reproduces the original defect. A mutation that survives because the code no
longer depends on the thing you mutated is not a gap; recording which one is
faithful is how the next reader avoids re-deriving that.
"""
import os
import subprocess
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scripts"))
TOOL = os.path.join(ROOT, "scripts", "session_commit.py")


@pytest.fixture(scope="module")
def sc():
    return pytest.importorskip("session_commit")


# --------------------------------------------------------------- classify
def test_a_shared_file_in_the_path_list_is_refused(sc):
    """The 48c04b4 shape: a path list that happens to name CLAUDE.md."""
    ok, undeclared = sc.classify(["mine.py", "CLAUDE.md"], [])
    assert ok == ["mine.py"]
    assert undeclared == ["CLAUDE.md"]


def test_opting_in_makes_it_allowed(sc):
    ok, undeclared = sc.classify(["mine.py"], ["CHANGELOG.md"])
    assert undeclared == [] and ok == ["mine.py"]


def test_matching_is_by_BASENAME_so_a_nested_copy_is_not_a_bypass(sc):
    """`docs/CLAUDE.md` is the same trap wearing a directory.

    Full-path matching looks equivalent and silently lets any nested copy of a
    shared doctrine file through without the opt-in.
    """
    _ok, undeclared = sc.classify(["docs/CLAUDE.md"], [])
    assert undeclared == ["docs/CLAUDE.md"]


def test_ordinary_files_are_never_refused(sc):
    ok, undeclared = sc.classify(["scripts/a.py", "tests/b.py"], [])
    assert ok == ["scripts/a.py", "tests/b.py"] and undeclared == []


def test_shared_doctrine_list_is_non_empty(sc):
    """An empty list would make the refusal unreachable while every unit test
    about ordinary files still passed."""
    assert sc.SHARED_DOCTRINE, "the opt-in list is the whole guard"
    assert "CHANGELOG.md" in sc.SHARED_DOCTRINE
    assert "CLAUDE.md" in sc.SHARED_DOCTRINE


# --------------------------------------------------------------- snapshot
def test_snapshot_records_a_missing_file_as_a_deletion(sc, tmp_path, monkeypatch):
    """A deletion must round-trip through the read-back.

    Skipping missing files would make `verify_readback` blind to a delete —
    the commit could drop a file and the receipt would still read clean.
    """
    monkeypatch.setattr(sc, "ROOT", str(tmp_path))
    (tmp_path / "f.txt").write_bytes(b"hello\n")
    snap = sc.snapshot(["f.txt", "gone.txt"])
    assert snap["f.txt"] == b"hello\n"
    assert "gone.txt" in snap and snap["gone.txt"] is None


# ------------------------------------------------- end-to-end in a real repo
def _repo(tmp_path):
    r = tmp_path / "repo"
    (r / "scripts").mkdir(parents=True)
    def g(*a):
        return subprocess.run(("git",) + a, cwd=r, capture_output=True, text=True)
    g("init", "-q", ".")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    import shutil
    shutil.copy(TOOL, r / "scripts" / "session_commit.py")
    (r / "CLAUDE.md").write_text("line1\nline2\n")
    (r / "mine.py").write_text("base\n")
    g("add", "-A")
    g("commit", "-qm", "base")
    return r, g


def _run(repo, *args):
    return subprocess.run(
        [sys.executable, "scripts/session_commit.py", *args],
        cwd=repo, capture_output=True, text=True, timeout=120)


def test_end_to_end_refuses_the_incident_shape(tmp_path):
    repo, _g = _repo(tmp_path)
    (repo / "CLAUDE.md").write_text("line1\nline2\nTHEIR EDIT\n")
    (repo / "mine.py").write_text("base\nmine\n")
    r = _run(repo, "-m", "my work", "--", "mine.py", "CLAUDE.md")
    assert r.returncode == 2, r.stdout + r.stderr
    assert "REFUSING" in r.stderr and "CLAUDE.md" in r.stderr


def test_end_to_end_leaves_a_concurrent_edit_and_a_concurrent_stage_alone(tmp_path):
    """The two halves of (lz), in one run.

    Their unstaged CLAUDE.md edit must not enter my commit, and their STAGED
    file must neither enter my commit nor be unstaged by it — the private index.
    """
    repo, g = _repo(tmp_path)
    (repo / "CLAUDE.md").write_text("line1\nline2\nTHEIR EDIT\n")   # them, unstaged
    (repo / "theirs.py").write_text("x\n")
    g("add", "theirs.py")                                          # them, STAGED
    (repo / "mine.py").write_text("base\nmine\n")                  # me

    r = _run(repo, "-m", "mine only", "--", "mine.py")
    assert r.returncode == 0, r.stdout + r.stderr

    files = g("show", "--stat", "--format=", "HEAD").stdout
    assert "CLAUDE.md" not in files, "their unstaged edit was swept in"
    assert "theirs.py" not in files, "their STAGED file was swept in"
    assert "mine.py" in files
    staged = g("diff", "--cached", "--name-only").stdout
    assert "theirs.py" in staged, "my commit disturbed their staged set"


def test_the_shared_diff_shows_real_hunks_not_a_phantom_deletion(tmp_path):
    """THE BUG THIS TOOL SHIPPED WITH, and the reason it is pinned.

    The private index started EMPTY, so `git diff HEAD -- p` saw no tracked
    paths and printed `deleted file mode` for the shared file — garbage, in the
    one output the whole design rests on. The commit was correct throughout
    (`--only` reads the working tree), so nothing failed loudly; only the
    display lied, which is worse: an operator who sees nonsense once stops
    reading it ((gl)). Fixed by seeding the index with `read-tree HEAD`.
    """
    repo, _g = _repo(tmp_path)
    (repo / "CLAUDE.md").write_text("line1\nline2\nTHEIR EDIT\nmy line\n")
    r = _run(repo, "-m", "doctrine", "--dry-run", "--shared", "CLAUDE.md")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "THEIR EDIT" in r.stdout, "the foreign hunk must be visible BEFORE it lands"
    assert "deleted file mode" not in r.stdout, "phantom deletion — index unseeded"
    assert "1 file changed, 1 deletion" not in r.stdout


def test_dry_run_commits_nothing(tmp_path):
    repo, g = _repo(tmp_path)
    (repo / "mine.py").write_text("base\nmine\n")
    before = g("rev-parse", "HEAD").stdout.strip()
    r = _run(repo, "-m", "x", "--dry-run", "--", "mine.py")
    assert r.returncode == 0
    assert g("rev-parse", "HEAD").stdout.strip() == before


def test_readback_confirms_the_commit_holds_the_snapshotted_bytes(tmp_path):
    repo, g = _repo(tmp_path)
    (repo / "mine.py").write_text("base\nmine\n")
    r = _run(repo, "-m", "x", "--", "mine.py")
    assert r.returncode == 0 and "read-back OK" in r.stdout
    assert g("show", "HEAD:mine.py").stdout == "base\nmine\n"


def test_readback_DETECTS_a_mismatch(sc, tmp_path, monkeypatch):
    """The receipt must be able to say NO — pinned because it could not.

    The first version of this file asserted only that `read-back OK` appears on
    a clean run, which stays true when `verify_readback` returns `[]`
    unconditionally. A check that can only pass is not a check; the mutation
    survived until this test existed.
    """
    repo, _g = _repo(tmp_path)
    monkeypatch.setattr(sc, "ROOT", str(repo))

    # matches what HEAD holds -> clean
    assert sc.verify_readback({"mine.py": b"base\n"}) == []
    # does NOT match -> must be reported
    assert sc.verify_readback({"mine.py": b"SOMETHING ELSE\n"}) == ["mine.py"]
    # a path absent from HEAD but expected present -> reported
    assert sc.verify_readback({"nope.py": b"x\n"}) == ["nope.py"]
    # snapshot says DELETED but HEAD still carries it -> reported
    assert sc.verify_readback({"mine.py": None}) == ["mine.py"]
    # snapshot says deleted and HEAD agrees -> clean
    assert sc.verify_readback({"nope.py": None}) == []


def test_a_NEW_file_is_actually_committed(tmp_path):
    """BUG FOUND BY DOGFOODING, pinned so it cannot come back.

    The first cut used `git commit --only`, which requires every path to be
    KNOWN to git — so untracked files were **silently dropped** and the "will
    commit" summary listed neither of them. A tool whose failure mode is quietly
    committing LESS than you asked is worse than one that errors, and it was
    caught only by running the tool on its own commit.
    """
    repo, g = _repo(tmp_path)
    (repo / "brand_new.py").write_text("new\n")
    r = _run(repo, "-m", "adds a file", "--", "brand_new.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "brand_new.py" in g("show", "--stat", "--format=", "HEAD").stdout
    assert g("show", "HEAD:brand_new.py").stdout == "new\n"


def test_add_edit_and_DELETE_in_one_commit(tmp_path):
    """The second dogfooding bug: staging twice broke on a deleted path.

    The summary and the commit each ran `git add -A`; the first recorded the
    deletion, so the second matched nothing on disk OR in the index and aborted
    with `fatal: pathspec ... did not match any files`. One add, reused.
    """
    repo, g = _repo(tmp_path)
    (repo / "doomed.py").write_text("x\n")
    g("add", "doomed.py")
    g("commit", "-qm", "add doomed")

    (repo / "brand_new.py").write_text("new\n")
    (repo / "mine.py").write_text("base\nedit\n")
    os.remove(repo / "doomed.py")

    r = _run(repo, "-m", "add+edit+delete", "--",
             "brand_new.py", "mine.py", "doomed.py")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "fatal" not in (r.stdout + r.stderr)
    files = g("show", "--stat", "--format=", "HEAD").stdout
    assert "brand_new.py" in files and "mine.py" in files and "doomed.py" in files
    assert g("cat-file", "-e", "HEAD:doomed.py").returncode != 0, \
        "the deletion must be IN the commit"
    assert "read-back OK" in r.stdout


def test_an_implicit_commit_is_impossible(tmp_path):
    """No paths, no commit — there is no bare-commit path through this tool."""
    repo, _g = _repo(tmp_path)
    r = _run(repo, "-m", "x")
    assert r.returncode == 2


def test_tool_selftest_passes():
    r = subprocess.run([sys.executable, TOOL, "--selftest"],
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr

def test_a_commit_that_DELETES_a_changelog_entry_is_refused(sc, tmp_path):
    """THE INCIDENT THAT CLOSED THIS TOOL'S OWN LOOP.

    Committing this tool, a `perl -pi -e 's/(nv)/(nx)/g'` letter-rename matched
    my own new header AND a concurrent session's entry of the same letter; the
    file lost 90 lines of their work, the tool committed it faithfully, and the
    read-back reported success. **True and useless** — `verify_readback` proves
    the commit matches the WORKING TREE, and the working tree was already
    corrupt. A receipt for fidelity is not a receipt for correctness, and the
    only reason it surfaced was the doctrine's separate "did my commit remove an
    entry?" check.

    `(lz)` records the same destruction (91 lines) from a different cause, which
    is what makes it a class rather than a slip.
    """
    repo = tmp_path / "r"
    (repo / "scripts").mkdir(parents=True)
    def g(*a):
        return subprocess.run(("git",) + a, cwd=repo, capture_output=True, text=True)
    g("init", "-q", ".")
    g("config", "user.email", "t@t")
    g("config", "user.name", "t")
    import shutil
    shutil.copy(TOOL, repo / "scripts" / "session_commit.py")
    (repo / "CHANGELOG.md").write_text(
        "## 2026-08-16 (nv) — THEIR ENTRY\n\ntheir body\n\n"
        "## 2026-08-15 (na) — old\n\nbody\n")
    g("add", "-A")
    g("commit", "-qm", "base")
    before = g("rev-parse", "HEAD").stdout.strip()

    # the global rename destroys theirs while adding mine
    (repo / "CHANGELOG.md").write_text(
        "## 2026-08-16 (nx) — MY ENTRY\n\nmy body\n\n"
        "## 2026-08-15 (na) — old\n\nbody\n")

    r = subprocess.run(
        [sys.executable, "scripts/session_commit.py", "-m", "mine",
         "--shared", "CHANGELOG.md"],
        cwd=repo, capture_output=True, text=True, timeout=120)
    assert r.returncode == 4, r.stdout + r.stderr
    assert "DELETES changelog entr" in r.stderr
    assert "(nv)" in r.stderr, "the destroyed entry must be NAMED (I8)"
    assert g("rev-parse", "HEAD").stdout.strip() == before, "nothing may commit"


def test_removed_entry_headers_is_pure_and_directional(sc):
    """Additions are not deletions — the check must not fire on every commit."""
    d = ("+## 2026-08-16 (nx) — mine\n"
         "-## 2026-08-16 (nv) — theirs\n-body\n")
    assert sc.removed_entry_headers(d) == ["## 2026-08-16 (nv) — theirs"]
    assert sc.removed_entry_headers(
        "+## 2026-08-16 (nx) — only additions\n") == []
    assert sc.removed_entry_headers("") == []
    assert sc.removed_entry_headers(None) == []


def test_a_MOVED_entry_is_not_a_deleted_one(sc):
    """The guard's own false positive, caught when it blocked this commit.

    Entries here are prepended constantly, so a repositioned entry shows as
    BOTH `-##` and `+##`. Reporting the minus alone blocks ordinary reshuffles —
    and a guard that fires on the normal case is one the next session learns to
    bypass, which is how a real deletion then walks through ((gl)).
    """
    moved_only = ("-## 2026-08-16 (nx) — mine\n"
                  "+## 2026-08-16 (nx) — mine\n")
    assert sc.removed_entry_headers(moved_only) == []

    moved_plus_real_deletion = (
        "-## 2026-08-16 (nx) — mine\n"
        "+## 2026-08-16 (nx) — mine\n"
        "-## 2026-08-16 (nv) — theirs, really gone\n")
    assert sc.removed_entry_headers(moved_plus_real_deletion) == [
        "## 2026-08-16 (nv) — theirs, really gone"], \
        "a real deletion alongside a move must still be caught"
