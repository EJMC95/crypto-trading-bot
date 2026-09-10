"""Append-only dashboard safety (spec section 17).

THE POSTURE: this package does NOT patch the existing fleet dashboard. It
ships the VERIFIER that would make such a patch provable, and the verifier
fails closed.

Why that is the right call rather than a dodge: the existing dashboard serves
a live fleet with real-money rows, and the spec's own rules -- never modify
SLOW_LOOP, STALE_SECONDS, existing filters, or existing entries in EXPECTED /
LABELS / CURRENT_BOTS -- are exactly the rules that are impossible to
guarantee by inspection alone. So the guarantee is made EXECUTABLE:

  snapshot()          record /pnl.json before
  forbidden_edits()   AST/textual diff refusing any touch to protected names
  append_only()       the only permitted shape of change
  verify_unchanged()  every pre-existing bot row identical afterwards

`verify_unchanged` treats an unreadable feed as a FAILURE, never as "nothing
changed" -- the one inversion that would make the whole check worthless.
"""
from __future__ import annotations

import json
import re
import time
import urllib.request
from dataclasses import dataclass, field
from typing import Any

DEFAULT_FEED = "https://pnl-dashboard-production-858c.up.railway.app/pnl.json"

#: Names a patch may never touch. Ordered by how expensive the mistake is.
PROTECTED_NAMES = ("SLOW_LOOP", "STALE_SECONDS", "CURRENT_BOTS", "EXPECTED",
                   "LABELS", "RETIRED_ROWS", "LEGACY_BOTS")

#: Fields on an existing row that must be byte-identical after a patch.
ROW_FIELDS = ("bot", "status", "equity", "pnl_abs", "pnl_pct", "closed_trades",
              "open_trades", "wins", "losses")


class DashboardVerificationError(RuntimeError):
    pass


@dataclass
class Snapshot:
    fetched_at: float
    rows: dict[str, dict[str, Any]]
    raw_len: int = 0
    source: str = ""

    @property
    def bots(self) -> set[str]:
        return set(self.rows)

    def as_dict(self) -> dict[str, Any]:
        return {"fetched_at": self.fetched_at, "source": self.source,
                "bots": sorted(self.rows), "n": len(self.rows)}


def _fetch(feed: str, timeout: int = 45) -> Any:
    if feed.startswith("http"):
        req = urllib.request.Request(feed, headers={"User-Agent": "audit"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read())
    with open(feed) as fh:
        return json.load(fh)


def snapshot(feed: str = DEFAULT_FEED) -> Snapshot:
    """Read /pnl.json. Raises on anything unusable -- the caller turns that
    into 'do not modify the dashboard', which is the required behaviour."""
    try:
        doc = _fetch(feed)
    except Exception as exc:                            # noqa: BLE001
        raise DashboardVerificationError(
            f"cannot read {feed}: {exc}. Per spec 17, the dashboard must NOT "
            "be modified when /pnl.json cannot be verified.") from exc
    rows = doc.get("bots") if isinstance(doc, dict) else doc
    if isinstance(rows, dict):
        rows = list(rows.values())
    if not isinstance(rows, list) or not rows:
        raise DashboardVerificationError(
            f"{feed} carried no rows; refusing to treat an empty feed as a "
            "clean baseline")
    out: dict[str, dict[str, Any]] = {}
    for r in rows:
        bot = str(r.get("bot") or "")
        if not bot:
            continue
        out[bot] = {k: r.get(k) for k in ROW_FIELDS}
    return Snapshot(time.time(), out, len(json.dumps(doc)), feed)


def verify_unchanged(before: Snapshot, after: Snapshot,
                     allow_new: bool = True) -> tuple[bool, list[str]]:
    """Every bot present BEFORE must be present after with identical fields.

    Live P&L moves between two reads, so `equity`, `pnl_abs`, `pnl_pct`,
    `closed_trades`, `open_trades`, `wins` and `losses` are compared only for
    PRESENCE and TYPE -- a changed number is the fleet trading, a vanished or
    retyped field is a patch defect. `bot` and `status` must match exactly."""
    problems: list[str] = []
    missing = before.bots - after.bots
    if missing:
        problems.append(f"rows DISAPPEARED after the patch: {sorted(missing)}")
    for bot in sorted(before.bots & after.bots):
        b, a = before.rows[bot], after.rows[bot]
        if b.get("bot") != a.get("bot"):
            problems.append(f"{bot}: bot id changed")
        if b.get("status") != a.get("status"):
            problems.append(f"{bot}: status {b.get('status')!r} -> "
                            f"{a.get('status')!r}")
        for f in ROW_FIELDS:
            if f in ("bot", "status"):
                continue
            if (b.get(f) is None) != (a.get(f) is None):
                problems.append(f"{bot}.{f}: presence changed "
                                f"({b.get(f)!r} -> {a.get(f)!r})")
            elif b.get(f) is not None and \
                    type(b[f]) is not type(a[f]):        # noqa: E721
                problems.append(f"{bot}.{f}: type changed "
                                f"{type(b[f]).__name__} -> {type(a[f]).__name__}")
    new = after.bots - before.bots
    if new and not allow_new:
        problems.append(f"unexpected new rows: {sorted(new)}")
    return (not problems), problems


def forbidden_edits(before_src: str, after_src: str) -> list[str]:
    """Refuse any diff that touches a protected name's definition, deletes a
    line, or reorders existing entries. APPEND-ONLY means the old text is a
    PREFIX-preserving subsequence of the new one."""
    problems: list[str] = []
    for name in PROTECTED_NAMES:
        pat = re.compile(rf"^{re.escape(name)}\s*[:=]", re.M)
        b = pat.findall(before_src)
        a = pat.findall(after_src)
        if len(b) != len(a):
            problems.append(f"{name}: definition count changed "
                            f"{len(b)} -> {len(a)}")
            continue
        for m_b, m_a in zip(_blocks(before_src, name), _blocks(after_src, name)):
            if m_b != m_a and not m_a.startswith(m_b.rstrip().rstrip("}]),")):
                problems.append(f"{name}: existing block was MODIFIED, not "
                                "appended to")
    b_lines = [l for l in before_src.splitlines() if l.strip()]
    a_lines = [l for l in after_src.splitlines() if l.strip()]
    it = iter(a_lines)
    for line in b_lines:
        for cand in it:
            if cand == line:
                break
        else:
            problems.append(f"line removed or reordered: {line.strip()[:70]!r}")
            break
    return problems


def _blocks(src: str, name: str) -> list[str]:
    out, lines = [], src.splitlines()
    for i, line in enumerate(lines):
        if re.match(rf"^{re.escape(name)}\s*[:=]", line):
            depth = line.count("{") + line.count("[") + line.count("(") \
                - line.count("}") - line.count("]") - line.count(")")
            block = [line]
            j = i + 1
            while depth > 0 and j < len(lines):
                block.append(lines[j])
                depth += (lines[j].count("{") + lines[j].count("[")
                          + lines[j].count("(") - lines[j].count("}")
                          - lines[j].count("]") - lines[j].count(")"))
                j += 1
            out.append("\n".join(block))
    return out


@dataclass
class PatchPlan:
    """The only permitted change: new keys appended to a new namespace."""
    additions: dict[str, Any] = field(default_factory=dict)
    touched_names: list[str] = field(default_factory=list)

    def safe(self) -> tuple[bool, list[str]]:
        bad = [n for n in self.touched_names if n in PROTECTED_NAMES]
        return (not bad), [f"patch touches protected name {n}" for n in bad]


def append_only(existing: dict[str, Any], additions: dict[str, Any]
                ) -> dict[str, Any]:
    """Merge that REFUSES to overwrite. Returns a new dict; raises on a clash,
    because the whole point is that nothing existing may change."""
    clash = set(existing) & set(additions)
    if clash:
        raise DashboardVerificationError(
            f"append-only violated: keys already exist: {sorted(clash)}")
    out = dict(existing)
    out.update(additions)
    return out
