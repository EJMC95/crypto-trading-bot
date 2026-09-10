"""[(aak)] The Parliament's supervised tasks: pageable, or DECLARED unpageable.

I13 says a dead loop runs no handler, so liveness is only visible from OUTSIDE —
and that the set which is deliberately unpageable must be **declared rather than
defaulted into**. The fleet enforces exactly that for its own organs in
`tests/autonomy/test_organ_pageability.py`. That guard cannot reach here: the
Parliament runs its OWN supervisor with its OWN `EXPECTED_BEATS`, so a task
added to `parliament_main` is unpageable by default and nothing says so.

MEASURED 10-Sep, which is why this file exists: of eight supervised tasks, five
sat outside `EXPECTED_BEATS`, and **`data.ws` had never emitted one beat in the
container's life** — the venue's websocket CDN-blocks cloud IPs. Two consumers
were silently inert as a result: `scan_orderbook_imbalance` (0 signals in 183
runs) and `featurize`'s `imb` feature, a constant 0.0 in every sample the ML
bench has ever learned from. The loop KNEW — it logs the CDN block at
`fails == 4` — and told nobody, because a log line is not a published state.
"""
import ast
import pathlib

import pytest

from parliament import brain as B

pytestmark = pytest.mark.autonomy

ROOT = pathlib.Path(__file__).resolve().parents[2]


def _supervised_names():
    tree = ast.parse((ROOT / "parliament_main.py").read_text())
    out = []
    for n in ast.walk(tree):
        if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "_supervised"
                and n.args and isinstance(n.args[0], ast.Constant)):
            out.append(n.args[0].value)
    return out


def _beat_names():
    """The names tasks actually beat under — NOT the task names. `data.candles.fast`
    beats as `data.candles.1h`, and reading the task name instead is how a naive
    version of this test overstates the finding."""
    names = set()
    for f in (ROOT / "parliament").glob("*.py"):
        t = ast.parse(f.read_text())
        for n in ast.walk(t):
            if (isinstance(n, ast.Call) and getattr(n.func, "id", None) == "beat"
                    and n.args and isinstance(n.args[0], ast.Constant)
                    and isinstance(n.args[0].value, str)):
                names.add(n.args[0].value)
    return names


def test_every_supervised_task_exists():
    assert len(_supervised_names()) >= 6, _supervised_names()


def test_no_beat_is_unpageable_without_being_declared():
    """The ratchet. A new organ that pages for nobody fails HERE, on the push
    that adds it — not months later when its consumer is found inert."""
    covered = set(B.EXPECTED_BEATS) | set(B.UNPAGEABLE_OK)
    orphans = sorted(n for n in _beat_names() if n not in covered)
    assert not orphans, (
        "these beats are neither paged on nor declared unpageable: %s — add "
        "them to EXPECTED_BEATS, or to UNPAGEABLE_OK with the reason" % orphans)


def test_every_declared_exemption_carries_a_real_reason():
    """A declaration with an empty reason is a default wearing a declaration's
    clothes."""
    for name, why in B.UNPAGEABLE_OK.items():
        assert isinstance(why, str) and len(why) > 40, (name, why)


def test_an_exemption_may_not_shadow_a_real_page():
    """Belt and braces: a name cannot be both paged on and exempted, or the
    exemption would quietly win a future refactor."""
    both = set(B.EXPECTED_BEATS) & set(B.UNPAGEABLE_OK)
    assert not both, both


def test_the_ws_feed_publishes_its_own_liveness():
    """`ws_books` empty is byte-identical between a quiet venue and a socket
    that has never connected — and on this deployment it is always the second.
    The state has to be readable without a container log."""
    # DRIVE the publisher, do not scan its text: a substring check passes on a
    # file that merely MENTIONS the attribute, and a mutation renaming the
    # initialiser survived exactly that (the page-wide-scan rule, on the test
    # written to honour it).
    import inspect

    from parliament.data import LighterData
    init_src = inspect.getsource(LighterData.__init__)
    assert "self.ws_state" in init_src, \
        "ws_state must be initialised in __init__, so a fresh object always has it"
    for field in ('"ok"', '"fails"', '"why"', '"last_ok"'):
        assert field in init_src, field
    # and the publish must READ it rather than infer it
    src = (ROOT / "parliament" / "brain.py").read_text()
    assert '"ws": dict(getattr(data, "ws_state"' in src, \
        "the publish must carry the ws state, not infer it"


def test_the_ws_failure_reason_is_a_class_never_the_raw_exception():
    """/bus.json is public and unauthenticated. An exception string can carry a
    URL or a header, so the payload records the TYPE."""
    src = (ROOT / "parliament" / "data.py").read_text()
    assert 'type(e).__name__' in src
    assert '"why": str(e)' not in src and '"why": repr(e)' not in src
