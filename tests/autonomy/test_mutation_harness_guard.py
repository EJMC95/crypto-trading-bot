"""[2026-08-19 (qj)] THE MUTATION HARNESS MUST REFUSE A DIRTY TARGET — and this
is the POSITIVE CONTROL its own selftest structurally cannot carry.

WHY THIS FILE EXISTS AT ALL. `scripts/mutate.py` restores between mutations
with `git checkout -- <target>`. Point it at a file whose fix is still
UNCOMMITTED and the first restore DELETES the work under test — measured the
day this shipped: an entire takeover-state fix, rebuilt from scratch. The
harness now refuses first.

The module's own `_selftest` is contractually "offline and pure: no git, no
pytest, no network", so it can only ever exercise `uncommitted()`'s PERMISSIVE
path (a temp dir is not a repo → False). That is a negative result, and
CLAUDE.md is explicit that **empty output is not a negative result until the
check has been seen to produce a positive one** — a guard that returns False
everywhere would satisfy the selftest completely. Measured, not theorised:
mutating `return bool(proc.stdout.strip())` → `return True` SURVIVED the
selftest, because that line is never reached outside a repo.

So the positive control lives here, where a real `git init` is allowed:
dirty → True, clean → False, untracked → True, and a path OUTSIDE any repo →
False. Together with the selftest's AST arm (main() branches on it), that is
the whole contract.
"""
import pathlib
import subprocess
import sys

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[2] / "scripts"))
import mutate  # noqa: E402

pytestmark = pytest.mark.autonomy


def _git(repo, *args):
    return subprocess.run(
        ["git", "-c", "user.email=t@t", "-c", "user.name=t", *args],
        cwd=repo, capture_output=True, text=True, check=True)


@pytest.fixture()
def repo(tmp_path):
    _git(tmp_path, "init", "-q")
    (tmp_path / "sample.py").write_text("X = 1\n", encoding="utf-8")
    _git(tmp_path, "add", "sample.py")
    _git(tmp_path, "commit", "-qm", "seed")
    return tmp_path


def test_a_committed_target_is_clean(repo, monkeypatch):
    monkeypatch.chdir(repo)
    assert mutate.uncommitted("sample.py") is False


def test_an_unstaged_edit_is_refused(repo, monkeypatch):
    """THE POSITIVE CONTROL. This is the exact state that cost a session its
    work: the fix written, tests written, nothing committed yet."""
    monkeypatch.chdir(repo)
    (repo / "sample.py").write_text("X = 2\n", encoding="utf-8")
    assert mutate.uncommitted("sample.py") is True


def test_a_staged_edit_is_refused_too(repo, monkeypatch):
    """`git checkout --` discards the index version as well, so staged-but-
    uncommitted is destroyed just the same."""
    monkeypatch.chdir(repo)
    (repo / "sample.py").write_text("X = 3\n", encoding="utf-8")
    _git(repo, "add", "sample.py")
    assert mutate.uncommitted("sample.py") is True


def test_an_untracked_target_is_refused(repo, monkeypatch):
    """A brand-new file has no HEAD version at all — `git checkout --` FAILS
    on it (check=True → the round dies mid-way), so it must never start."""
    monkeypatch.chdir(repo)
    (repo / "brand_new.py").write_text("Y = 1\n", encoding="utf-8")
    assert mutate.uncommitted("brand_new.py") is True


def test_outside_a_repo_it_fails_open(tmp_path, monkeypatch):
    """Permissive where git cannot answer: nothing is protected there, and a
    false positive would block legitimate rounds."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "loose.py").write_text("Z = 1\n", encoding="utf-8")
    assert mutate.uncommitted("loose.py") is False
