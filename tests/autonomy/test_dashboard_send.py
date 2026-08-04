"""[2026-08-04 (iy)] The dashboard's gzip send path — the fix for the measured
8.2 MB /bus.json and the 584 KB page the live station refetches every morph.

Why this file exists: `_send_ok` sits under EVERY consumer of the page and the
bus surface. A wrong Content-Length after compression, a gzip body without the
Content-Encoding header, or compression forced on a client that never asked
would break each of them at once — and the failure would look like a network
problem, not a code change. These tests drive the real handler method with a
stub transport (no socket, no DB), so they pin the contract, not a fixture's
idea of it.
"""
import gzip
import io
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

import pnl_dashboard  # noqa: E402


def _stub(accept_encoding):
    """A handler instance with the transport stubbed out. __new__ skips the
    socket machinery; we only exercise _send_ok and _no_cache."""
    h = pnl_dashboard.H.__new__(pnl_dashboard.H)
    h.headers = {"Accept-Encoding": accept_encoding} if accept_encoding is not None else {}
    h.sent = {"status": None, "headers": []}
    h.wfile = io.BytesIO()
    h.send_response = lambda code: h.sent.__setitem__("status", code)
    h.send_header = lambda k, v: h.sent["headers"].append((k, str(v)))
    h.end_headers = lambda: None
    return h


def _hdr(h, name):
    vals = [v for k, v in h.sent["headers"] if k.lower() == name.lower()]
    return vals[-1] if vals else None


def test_gzip_when_client_asks_and_body_is_big():
    h = _stub("gzip, deflate")
    body = (b"x" * 4096) + b"MARKER" + (b"y" * 4096)
    h._send_ok(body, "application/json")
    wire = h.wfile.getvalue()
    assert _hdr(h, "Content-Encoding") == "gzip"
    assert _hdr(h, "Vary") == "Accept-Encoding"
    # Content-Length must describe the COMPRESSED bytes actually written
    assert int(_hdr(h, "Content-Length")) == len(wire)
    assert len(wire) < len(body)
    assert gzip.decompress(wire) == body  # round-trips to the exact body


def test_no_gzip_when_client_does_not_ask():
    h = _stub(None)
    body = b"z" * 8192
    h._send_ok(body, "text/html; charset=utf-8")
    assert _hdr(h, "Content-Encoding") is None
    assert h.wfile.getvalue() == body
    assert int(_hdr(h, "Content-Length")) == len(body)


def test_no_gzip_on_tiny_bodies():
    # Below the 1 KB floor compression costs more than it saves; the body
    # must pass through untouched even for a gzip-capable client.
    h = _stub("gzip")
    body = b'{"ok": true}'
    h._send_ok(body, "application/json")
    assert _hdr(h, "Content-Encoding") is None
    assert h.wfile.getvalue() == body


def test_no_cache_semantics_survive_the_new_path():
    # The frozen-feed lesson (_no_cache docstring): a cached 200 reads as a
    # dead-flat fleet. The gzip path must keep the no-store contract.
    h = _stub("gzip")
    h._send_ok(b"x" * 4096, "application/json")
    cc = _hdr(h, "Cache-Control") or ""
    assert "no-store" in cc


def test_bus_serves_the_allocation_organ():
    # The organ published healthy 30-min payloads with NO surface serving it
    # (the (hw) wrong-surface class). Pin both halves of the fix: the serve
    # list carries the bot_state key, and the vitals roster carries the organ
    # so a dark allocation row is visible, not silent (I13).
    src = (Path(__file__).resolve().parents[2] / "pnl_dashboard.py").read_text()
    assert "'fleet-allocation', " in src, "bus.json serve list lost fleet-allocation"
    assert '"fleet_allocation": live.get("fleet-allocation")' in src
    assert '("fleet-allocation",' in src, "vitals roster lost the allocation organ"
