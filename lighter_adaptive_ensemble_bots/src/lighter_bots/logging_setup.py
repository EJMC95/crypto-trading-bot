"""Structured JSON logging with a hard secret filter.

The filter is not decoration. A signed Lighter payload and an auth token are
both long opaque strings that look like ordinary debug output, and the private
key is an env var any careless f-string can pick up. So redaction happens at
the HANDLER, below every call site: a module that logs the wrong thing is
still safe, which is the only version of this that survives contact with a
real incident.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any

#: Substrings that mark a field as secret no matter what module emitted it.
SECRET_KEYS = ("private_key", "privatekey", "api_private", "secret", "signature",
               "signed", "auth_token", "authorization", "tx_info", "password")

#: A 40+ char hex run is a key, a signature or a signed tx body. Never log one.
_HEX_RUN = re.compile(r"\b(?:0x)?[0-9a-fA-F]{40,}\b")
_REDACTED = "<redacted>"


def scrub(value: Any) -> Any:
    """Recursively redact secrets. Total by construction: an unknown type is
    stringified and still passed through the hex filter."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            if any(s in str(k).lower() for s in SECRET_KEYS):
                out[k] = _REDACTED
            else:
                out[k] = scrub(v)
        return out
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return _HEX_RUN.sub(_REDACTED, value)
    return value


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(record.created)),
            "level": record.levelname,
            "logger": record.name,
            "msg": scrub(record.getMessage()),
        }
        extra = getattr(record, "extra_fields", None)
        if isinstance(extra, dict):
            payload.update(scrub(extra))
        if record.exc_info:
            payload["exc"] = _HEX_RUN.sub(_REDACTED,
                                          self.formatException(record.exc_info))
        return json.dumps(payload, default=str, sort_keys=True)


def setup(level: str = "INFO", logfile: str | None = None) -> logging.Logger:
    root = logging.getLogger("lighter_bots")
    root.setLevel(getattr(logging, str(level).upper(), logging.INFO))
    root.handlers.clear()
    root.propagate = False
    h = logging.StreamHandler(sys.stdout)
    h.setFormatter(JsonFormatter())
    root.addHandler(h)
    if logfile:
        os.makedirs(os.path.dirname(logfile) or ".", exist_ok=True)
        fh = logging.FileHandler(logfile)
        fh.setFormatter(JsonFormatter())
        root.addHandler(fh)
    return root


def get(name: str) -> logging.Logger:
    return logging.getLogger(f"lighter_bots.{name}")


def event(logger: logging.Logger, msg: str, **fields: Any) -> None:
    """Log one structured event. Fields are scrubbed by the formatter."""
    logger.info(msg, extra={"extra_fields": fields})
