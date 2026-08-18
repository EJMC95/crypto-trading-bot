"""[(qc)] The suite must run in CI's regime EVERYWHERE: no DATABASE_URL.

The incident: a full-suite run in a shell carrying `export DATABASE_URL`
let a parliament book test publish a FABRICATED trade into the durable
paper_trades ledger through the real close path. The guard is the strip at
the top of the root conftest; this file is its tripwire — if the strip is
ever deleted, any contributor running tests from a study shell reddens HERE
instead of silently writing the production ledger.
"""
import os
import pathlib


def test_the_db_env_is_stripped_or_deliberately_allowed():
    if os.environ.get("TESTS_ALLOW_DB", "").strip() == "1":
        return  # explicit opt-in owns the consequences
    assert "DATABASE_URL" not in os.environ
    assert "DATABASE_PUBLIC_URL" not in os.environ


def test_the_strip_lives_in_the_ROOT_conftest_before_pytest_imports():
    """Structural: the pop must sit in the root conftest ABOVE the pytest
    import, because pytest loads the root conftest before any test module —
    a strip in a later fixture runs after module-level env reads have bound."""
    src = (pathlib.Path(__file__).resolve().parents[2] / "conftest.py").read_text()
    strip = src.index('os.environ.pop(_k, None)')
    assert strip < src.index("import pytest"), \
        "the strip must precede pytest's own import in the root conftest"
    assert 'TESTS_ALLOW_DB' in src
