"""Minimal nrl.json feed service — identical pattern to the Railway pnl-dashboard.

Serves outputs/nrl.json (baked into the image at deploy time, refreshed on each
push) plus a health endpoint. The interactive dashboard artifact reads /nrl.json.
Stdlib only — no dependencies.
"""
from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "outputs"
FEED = OUT / "nrl.json"
DASH = OUT / "dashboard.html"


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802
        if self.path == "/":
            try:
                body, status, ctype = DASH.read_bytes(), 200, "text/html; charset=utf-8"
            except FileNotFoundError:
                body, status, ctype = b"dashboard not built yet", 503, "text/plain"
        elif self.path == "/nrl.json":
            try:
                body, status, ctype = FEED.read_bytes(), 200, "application/json"
            except FileNotFoundError:
                body = json.dumps({"error": "feed not built yet"}).encode()
                status, ctype = 503, "application/json"
        elif self.path == "/health":
            body, status, ctype = b'{"status":"ok"}', 200, "application/json"
        else:
            body, status, ctype = b"not found", 404, "text/plain"
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "max-age=60")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass  # keep Railway logs quiet


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8090))
    print(f"nrl.json feed on :{port}")
    HTTPServer(("0.0.0.0", port), Handler).serve_forever()
