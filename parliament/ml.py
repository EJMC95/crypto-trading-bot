#!/usr/bin/env python3
"""
parliament/ml.py — Layer 3: KEATING's 🔭 model bench (5 models + ensemble).

Learns p(win) for a candidate entry from the ecosystem DB's closed trades —
its own six books AND any other bot whose rows carry entry-time features
(Howard ingests the wider fleet's ledger; rows without features are simply
not trainable and are skipped). Everything is ONLINE and prequential:
each label first SCORES every model's prior prediction (a true
out-of-sample grade), then updates it — so the ensemble's weights are
earned on unseen data, never in-sample.

THE BENCH (numpy; the wheel is in every image and in requirements-test)
  1 logit    online logistic regression (SGD, L2)
  2 ridge    ridge regression on ±1 labels, closed-form refit on a window
  3 nb       Gaussian naive Bayes (per-class online mean/var)
  4 stumps   AdaBoost over depth-1 stumps, refit on a window
  5 knn      k-nearest-neighbours on standardized recent samples

ENSEMBLE: weight_i = max(0, oos_acc_i - 0.5) (decayed EMA) — a model that
cannot beat a coin flip out-of-sample gets weight ZERO. Cold or edge-less
ensemble -> p = 0.5 and ready=False.

AUTHORITY (fleet doctrine — reduce-only, like the brain's stake mults):
the ML gate may SKIP an entry or SHRINK its stake; it can never boost
above 1.0x or conjure an entry. Cold model = neutral. numpy absent =
neutral. A learning layer must never be able to add risk.
"""
from __future__ import annotations

import logging
import math
import os
import time

try:
    import numpy as np
except Exception:  # noqa: BLE001 — degraded: gates neutral, nothing trains
    np = None

log = logging.getLogger("parliament.ml")

# Fixed feature order — the contract between featurize() at entry time and
# every model. Extend by APPENDING (stored feature dicts are keyed).
FEATURES = ["direction", "ret4", "rsi_n", "vol_ratio", "funding_apr_n",
            "prem_n", "imb", "trend", "strength", "hour_sin", "hour_cos"]

MIN_READY_SAMPLES = int(os.environ.get("PARL_ML_MIN_SAMPLES", "200"))
ACC_HALFLIFE = 200.0            # samples; decayed OOS accuracy EMA
WINDOW = 1500                   # refit window for ridge/stumps/knn


def featurize(sym: str, direction: int, data, signal: dict | None = None) -> dict:
    """Entry-time feature dict from the shared LighterData. Pure reads —
    None-safe on every missing input (a dark field is 0.0, never a crash)."""
    from .scanners import rsi, realized_vol, ema  # local: avoid cycle at import

    st = (data.stats(sym) or {}) if data is not None else {}
    from . import data as _d
    fast = data.get_candles(sym, _d.RES_FAST) if data is not None else []
    slow = data.get_candles(sym, _d.RES_SLOW) if data is not None else []
    closes_f = [b["c"] for b in fast]
    closes_s = [b["c"] for b in slow]

    ret4 = 0.0
    if len(closes_f) >= 5 and closes_f[-5] > 0:
        ret4 = closes_f[-1] / closes_f[-5] - 1.0
    r = rsi(closes_f) if len(closes_f) >= 20 else None
    vol_ratio = 1.0
    if len(closes_s) >= 60:
        rec = realized_vol(closes_s[-24:])
        base = realized_vol(closes_s[-120:-24])
        if rec and base and base > 0:
            vol_ratio = rec / base
    trend = 0.0
    if len(closes_s) >= 60:
        e12, e48 = ema(closes_s, 12), ema(closes_s, 48)
        if e12 is not None and e48 is not None and e48 > 0:
            trend = max(-1.0, min(1.0, (e12 / e48 - 1.0) * 50.0))
    ws = (data.ws_books or {}).get(sym) if data is not None else None
    imb = ws["imb"] if ws and time.time() - ws["ts"] < 120 else 0.0
    apr = (data.funding or {}).get(sym, 0.0) if data is not None else 0.0
    hour = time.gmtime().tm_hour + time.gmtime().tm_min / 60.0
    return {
        "direction": float(direction),
        "ret4": max(-0.2, min(0.2, ret4)) * 5.0,
        "rsi_n": ((r if r is not None else 50.0) - 50.0) / 50.0,
        "vol_ratio": max(-1.0, min(1.0, math.log(vol_ratio) if vol_ratio > 0 else 0.0)),
        "funding_apr_n": max(-1.0, min(1.0, apr / 100.0)),
        "prem_n": max(-1.0, min(1.0, float(st.get("prem_bps") or 0.0) / 100.0)),
        "imb": float(imb),
        "trend": trend,
        "strength": float((signal or {}).get("strength") or 0.0),
        "hour_sin": math.sin(2 * math.pi * hour / 24.0),
        "hour_cos": math.cos(2 * math.pi * hour / 24.0),
    }


def vector(features: dict) -> "np.ndarray | None":
    if np is None:
        return None
    return np.array([float(features.get(k) or 0.0) for k in FEATURES],
                    dtype=float)


# ---------------------------------------------------------------------------
# the five models — tiny, dependency-light, online-friendly
# ---------------------------------------------------------------------------

class _OnlineLogit:
    name = "logit"

    def __init__(self, dim: int, lr: float = 0.05, l2: float = 1e-4):
        self.w = np.zeros(dim + 1)
        self.lr, self.l2 = lr, l2

    def predict(self, x) -> float:
        z = self.w[0] + float(self.w[1:] @ x)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))

    def update(self, x, y: int) -> None:
        p = self.predict(x)
        g = p - y
        self.w[0] -= self.lr * g
        self.w[1:] -= self.lr * (g * x + self.l2 * self.w[1:])


class _WindowModel:
    """Base for models refit on a rolling window."""

    def __init__(self, dim: int):
        self.dim = dim
        self.X: list = []
        self.Y: list = []
        self.dirty = 0

    def _push(self, x, y: int) -> None:
        self.X.append(x)
        self.Y.append(y)
        if len(self.X) > WINDOW:
            self.X.pop(0)
            self.Y.pop(0)
        self.dirty += 1

    def update(self, x, y: int) -> None:
        self._push(x, y)
        if self.dirty >= 25:      # amortized refits, not per-sample
            self.dirty = 0
            try:
                self.refit()
            except Exception as e:  # noqa: BLE001
                log.warning("%s refit failed (%s)", self.name, e)

    def refit(self) -> None:  # pragma: no cover — overridden
        raise NotImplementedError


class _Ridge(_WindowModel):
    name = "ridge"

    def __init__(self, dim: int, lam: float = 1.0):
        super().__init__(dim)
        self.lam = lam
        self.w = None

    def refit(self) -> None:
        if len(self.X) < 30:
            return
        X = np.hstack([np.ones((len(self.X), 1)), np.array(self.X)])
        y = np.array(self.Y) * 2.0 - 1.0
        A = X.T @ X + self.lam * np.eye(X.shape[1])
        self.w = np.linalg.solve(A, X.T @ y)

    def predict(self, x) -> float:
        if self.w is None:
            return 0.5
        z = float(self.w[0] + self.w[1:] @ x)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, 2.0 * z))))


class _GaussianNB:
    name = "nb"

    def __init__(self, dim: int):
        self.n = [0, 0]
        self.mean = [np.zeros(dim), np.zeros(dim)]
        self.m2 = [np.ones(dim) * 1e-3, np.ones(dim) * 1e-3]

    def update(self, x, y: int) -> None:
        c = int(y)
        self.n[c] += 1
        d = x - self.mean[c]
        self.mean[c] += d / self.n[c]
        self.m2[c] += d * (x - self.mean[c])

    def predict(self, x) -> float:
        if min(self.n) < 5:
            return 0.5
        logp = []
        for c in (0, 1):
            var = self.m2[c] / max(1, self.n[c] - 1) + 1e-6
            ll = -0.5 * float(np.sum((x - self.mean[c]) ** 2 / var
                                     + np.log(2 * math.pi * var)))
            ll += math.log(self.n[c] / (self.n[0] + self.n[1]))
            logp.append(ll)
        m = max(logp)
        e0, e1 = math.exp(logp[0] - m), math.exp(logp[1] - m)
        return e1 / (e0 + e1)


class _StumpBoost(_WindowModel):
    name = "stumps"

    def __init__(self, dim: int, rounds: int = 10):
        super().__init__(dim)
        self.rounds = rounds
        self.stumps: list[tuple[int, float, int, float]] = []  # (feat, thr, sign, alpha)

    def refit(self) -> None:
        if len(self.X) < 40:
            return
        X = np.array(self.X)
        y = np.array(self.Y) * 2.0 - 1.0
        w = np.ones(len(y)) / len(y)
        stumps = []
        for _ in range(self.rounds):
            best = None
            for f in range(X.shape[1]):
                col = X[:, f]
                for thr in np.percentile(col, [20, 35, 50, 65, 80]):
                    for sign in (1, -1):
                        pred = np.where(col > thr, sign, -sign)
                        err = float(np.sum(w * (pred != np.sign(y).astype(int))))
                        if best is None or err < best[0]:
                            best = (err, f, float(thr), sign)
            err, f, thr, sign = best
            err = min(max(err, 1e-6), 1 - 1e-6)
            if err >= 0.5:
                break
            alpha = 0.5 * math.log((1 - err) / err)
            pred = np.where(X[:, f] > thr, sign, -sign)
            w = w * np.exp(-alpha * y * pred)
            w = w / np.sum(w)
            stumps.append((f, thr, sign, alpha))
        self.stumps = stumps

    def predict(self, x) -> float:
        if not self.stumps:
            return 0.5
        z = sum(alpha * (sign if x[f] > thr else -sign)
                for f, thr, sign, alpha in self.stumps)
        return 1.0 / (1.0 + math.exp(-max(-30.0, min(30.0, z))))


class _KNN(_WindowModel):
    name = "knn"

    def __init__(self, dim: int, k: int = 15):
        super().__init__(dim)
        self.k = k
        self._mu = None
        self._sd = None

    def refit(self) -> None:
        if len(self.X) < 30:
            return
        X = np.array(self.X)
        self._mu = X.mean(axis=0)
        self._sd = X.std(axis=0) + 1e-6

    def predict(self, x) -> float:
        if self._mu is None or len(self.X) < 30:
            return 0.5
        X = (np.array(self.X) - self._mu) / self._sd
        q = (x - self._mu) / self._sd
        d = np.sum((X - q) ** 2, axis=1)
        idx = np.argsort(d)[: self.k]
        return float(np.mean(np.array(self.Y)[idx]))


class MLEngine:
    """The bench + prequentially-weighted ensemble."""

    def __init__(self, db=None):
        self.db = db
        self.enabled = np is not None
        dim = len(FEATURES)
        self.models = []
        if self.enabled:
            self.models = [_OnlineLogit(dim), _Ridge(dim), _GaussianNB(dim),
                           _StumpBoost(dim), _KNN(dim)]
        self.acc = {m.name: 0.5 for m in self.models}   # decayed OOS accuracy
        self.n_seen = 0
        self._trained_ids: set[str] = set()

    # -- inference ------------------------------------------------------------
    def predict(self, features: dict) -> tuple[float, bool]:
        """(p_win, ready). Neutral 0.5/False when cold, disabled, or edgeless."""
        if not self.enabled or self.n_seen < MIN_READY_SAMPLES:
            return 0.5, False
        x = vector(features)
        num = den = 0.0
        for m in self.models:
            w = max(0.0, self.acc[m.name] - 0.5)
            if w <= 0:
                continue
            try:
                num += w * m.predict(x)
                den += w
            except Exception:  # noqa: BLE001 — one sick model never vetoes
                continue
        if den <= 0:
            return 0.5, False
        return max(0.01, min(0.99, num / den)), True

    # -- learning -------------------------------------------------------------
    def learn(self, features: dict, won: bool) -> None:
        """Prequential: score each model's PRIOR prediction, then update it."""
        if not self.enabled:
            return
        x = vector(features)
        y = 1 if won else 0
        decay = 0.5 ** (1.0 / ACC_HALFLIFE)
        for m in self.models:
            try:
                p = m.predict(x)
                hit = 1.0 if (p >= 0.5) == bool(won) else 0.0
                self.acc[m.name] = self.acc[m.name] * decay + hit * (1 - decay)
                m.update(x, y)
            except Exception as e:  # noqa: BLE001
                log.warning("model %s update failed (%s)", m.name, e)
        self.n_seen += 1

    def train_from_db(self) -> int:
        """Replay closed trades (with stored features) not yet learned —
        restart-proof memory, and the door other bots' rows come in through."""
        if not self.enabled or self.db is None:
            return 0
        rows = self.db.closed_trades(days=30.0)
        rows = [r for r in rows
                if r["features"] and r["pnl_abs"] is not None
                and r["trade_id"] not in self._trained_ids]
        rows.sort(key=lambda r: r["closed_ts"] or 0)
        for r in rows:
            self.learn(r["features"], r["pnl_abs"] > 0)
            self._trained_ids.add(r["trade_id"])
        if len(self._trained_ids) > 20000:   # bounded memory
            self._trained_ids = set(list(self._trained_ids)[-10000:])
        return len(rows)

    # -- reporting ------------------------------------------------------------
    def snapshot(self) -> dict:
        return {"enabled": self.enabled, "n_seen": self.n_seen,
                "ready": self.enabled and self.n_seen >= MIN_READY_SAMPLES,
                "oos_acc": {k: round(v, 4) for k, v in self.acc.items()}}

    async def run_forever(self, interval: float = 300.0, beat=None):
        import asyncio
        while True:
            n = self.train_from_db()
            if beat:
                beat("keating.ml", f"+{n} samples (n={self.n_seen})")
            await asyncio.sleep(interval)
