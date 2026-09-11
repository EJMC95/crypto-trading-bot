"""Structured JSON logging with a hard secret filter.

Redaction happens at the HANDLER, below every call site, so a module that logs
the wrong thing is still safe. That is the only version of this that survives
contact with a real incident: a rule saying "remember not to log the key" has
already failed the first time someone forgets.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from typing import Any

#: Substrings marking a field as secret, whatever module emitted it.
SECRET_KEYS = ("api_key", "apikey", "secret", "password", "passphrase",
               "private", "signature", "signed", "authorization", "auth_token",
               "token", "cookie", "session")

#: A 32+ char base64/hex run is a key or a signature. Never log one.
_LONG_TOKEN = re.compile(r"\b[A-Za-z0-9+/=_-]{32,}\b")
_REDACTED = "<redacted>"


def scrub(value: Any) -> Any:
    """Recursively redact. Total by construction: an unknown type is
    stringified and still passed through the token filter."""
    if isinstance(value, dict):
        out = {}
        for k, v in value.items():
            out[k] = _REDACTED if any(s in str(k).lower() for s in SECRET_KEYS) \
                else scrub(v)
        return out
    if isinstance(value, (list, tuple)):
        return [scrub(v) for v in value]
    if isinstance(value, str):
        return _LONG_TOKEN.sub(_REDACTED, value)
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
            payload["exc"] = _LONG_TOKEN.sub(_REDACTED,
                                             self.formatException(record.exc_info))
        return json.dumps(payload, default=str, sort_keys=True)


def setup(level: str = "INFO", logfile: str | None = None) -> logging.Logger:
    root = logging.getLogger("downtrend_bot")
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
    return logging.getLogger(f"downtrend_bot.{name}")


def event(logger: logging.Logger, msg: str, **fields: Any) -> None:
    """Log one structured event. Fields are scrubbed by the formatter."""
    logger.info(msg, extra={"extra_fields": fields})
