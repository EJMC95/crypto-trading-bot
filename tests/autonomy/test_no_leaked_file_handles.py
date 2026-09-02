"""[(xr)] A RATCHET on leaked file handles in the autonomy tests.

CodeQL flagged `open(...).read()` without a context manager three times in one
evening, across three different files I had just written. Fixing each instance
was not closing the class — which is the repo's own standard ("a fix closes a
class or it is not finished") — and the fourth would have arrived the same way.

WHY A RATCHET AND NOT A BAR. There are 50 pre-existing bare calls in this tree.
A guard that reddens the build on a pre-existing backlog gets exempted within a
day and then guards nothing — `(mz)`'s lesson, which I23 cites by name. So the
backlog may only SHRINK, and a NEW one fails the push that adds it.

AST, not grep: a docstring that MENTIONS `open(...)` is prose, and the first
cut of this counter counted my own explanation of the rule as a violation of it.
"""
import ast
import glob
import os

#: The measured backlog on the day this shipped. It may only go DOWN.
#: Lower it whenever you clean some up — never raise it.
MAX_BARE_OPENS = 50

_HERE = os.path.dirname(os.path.abspath(__file__))


def _bare_opens(path):
    """`open()` calls that are not the context expression of a `with`."""
    with open(path) as fh:
        tree = ast.parse(fh.read())
    managed = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.With, ast.AsyncWith)):
            for item in node.items:
                for sub in ast.walk(item.context_expr):
                    if isinstance(sub, ast.Call):
                        managed.add(id(sub))
    return [n.lineno for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Name)
            and n.func.id == "open" and id(n) not in managed]


def _census():
    out = {}
    for f in sorted(glob.glob(os.path.join(_HERE, "*.py"))):
        hits = _bare_opens(f)
        if hits:
            out[os.path.basename(f)] = hits
    return out


def test_the_backlog_of_leaked_handles_only_shrinks():
    census = _census()
    total = sum(len(v) for v in census.values())
    worst = sorted(census.items(), key=lambda kv: -len(kv[1]))[:5]
    assert total <= MAX_BARE_OPENS, (
        f"{total} bare open() calls, ratchet is {MAX_BARE_OPENS}. A NEW leaked "
        f"handle fails the push that adds it — wrap it in `with`. Worst files: "
        f"{[(k, len(v)) for k, v in worst]}")


def test_the_ratchet_is_not_slack():
    """A ratchet set above the real count is a guard that guards nothing — the
    same vacuous shape this file exists to prevent. If the backlog has been
    cleaned up, LOWER `MAX_BARE_OPENS` to match."""
    total = sum(len(v) for v in _census().values())
    assert total >= MAX_BARE_OPENS - 5, (
        f"only {total} bare open() calls remain but the ratchet still reads "
        f"{MAX_BARE_OPENS} — lower it so it keeps biting")


def test_the_counter_reads_calls_not_prose():
    """The first cut of this counter was a regex, and it counted this very
    file's docstring — which says `open(...)` — as a violation."""
    import tempfile
    src = ('"""A docstring mentioning open(...) and open(x).read()."""\n'
           "with open('a') as fh:\n    pass\n"
           "y = open('b').read()\n")
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fh:
        fh.write(src)
        p = fh.name
    try:
        hits = _bare_opens(p)
        assert len(hits) == 1, hits   # only the real bare call
    finally:
        os.unlink(p)
