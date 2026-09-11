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

ARMING [(aag)]: `ready` is TWO bars, not one — `n_seen >= MIN_READY_SAMPLES`
AND the best model measurably better than chance (`acc_z() >= ACC_Z_BAR`).
The count alone was the whole rule until 10-Sep, and a count is not evidence:
driven on pure noise the bench reaches ~0.538 decayed accuracy by luck, which
under the old rule ARMED `ml_gate` and started refusing entries on nothing.
`is_ready()` is the single owner; `readiness()` publishes the distance and
names the binding constraint, so `ready: false` is never again byte-identical
between "warming up" and "structurally impossible".

DURABLE [(aaj)]: `n_seen`, `acc` and the trained-id set are PERSISTED, so the
prequential history survives the container instead of being recomputed from
whatever the store still holds. Model WEIGHTS are deliberately NOT persisted —
`warm()` re-feeds the retained rows update-only at boot; see `_STATE_KEY`.

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

from .ecosystem_db import TRADE_KEEP_DAYS

log = logging.getLogger("parliament.ml")

# Fixed feature order — the contract between featurize() at entry time and
# every model. Extend by APPENDING (stored feature dicts are keyed).
FEATURES = ["direction", "ret4", "rsi_n", "vol_ratio", "funding_apr_n",
            "prem_n", "imb", "trend", "strength", "hour_sin", "hour_cos"]

MIN_READY_SAMPLES = int(os.environ.get("PARL_ML_MIN_SAMPLES", "200"))
ACC_HALFLIFE = 200.0            # samples; decayed OOS accuracy EMA
WINDOW = 1500                   # refit window for ridge/stumps/knn
NUM_T = (int, float)            # NB bool subclasses int — reject it explicitly

#: [(aag)] THE TRAINING HORIZON IS THE RETENTION, BY IDENTITY. `n_seen` resets
#: to 0 on every boot and is rebuilt from the rows still in the `trades` table,
#: so the ceiling on what this ensemble can ever learn is the size of that
#: pool — never `MIN_READY_SAMPLES`. Pointing the query at the pruner's own
#: constant is what stops the two drifting apart ((hj)). Full measurement in
#: `ecosystem_db.TRADE_KEEP_DAYS`.
TRAIN_DAYS = TRADE_KEEP_DAYS

#: [(aag)] A COUNT IS NOT EVIDENCE — the bar that decides whether the ensemble
#: may ACT. `ready` used to mean "has seen 200 rows", so the gate would arm at
#: whatever accuracy happened to obtain: measured 10-Sep the best model read
#: **0.5082**, which is 0.23 SE from a coin flip, and `ml_gate` would then have
#: refused live entries on noise. This is I15/I16 in an actuator — rank on a
#: measured lower bound, never on the bare number. One-sided z on the decayed
#: accuracy against 0.5; 1.28 is the fleet's own one-sided 90% value
#: (`fleet_allocation.Z_LOWER`), pinned to it by test rather than imported, so
#: the Parliament keeps its self-contained import graph (born-dark rule).
ACC_Z_BAR = float(os.environ.get("PARL_ML_ACC_Z", "1.28"))

#: [(aas)] THE FETCH CAP IS PART OF THE HORIZON, AND A SILENT ONE IS A LIE.
#: `(aag)` raised the retention to 90d and pointed the query at it — and the
#: query it pointed carried `closed_trades(..., limit=2000)`, a default this
#: call site never overrode, so the horizon it published was not the horizon it
#: read. Measured 11-Sep on the live payload: `train_days: 90` beside
#: `pool: 89`, where 89 is exactly the trainable count of the newest **2,000**
#: rows — about 19-22 days of the ingested fleet. The `blocked_by` string then
#: named the RETENTION as the binding gate (I18) while the gate that actually
#: bound was the cap, and the fix shipped the night before was largely inert.
#:
#: So the cap is DECLARED, and — the half that closes the class — its binding
#: is PUBLISHED. `(qz)`: a result exactly equal to its own limit is a
#: truncation signature, and `head`/`LIMIT` are silent by construction, so the
#: only durable defence is to notice the equality and say so. The default is
#: set well above what the retention can hold (measured ~95 rows/day fleet-wide
#: => ~8.5k at 90d), which makes it a memory backstop rather than a horizon;
#: if the fleet ever outgrows it, `readiness().truncated` says so on the
#: payload instead of the pool quietly flattening again.
TRAIN_LIMIT = int(os.environ.get("PARL_ML_TRAIN_LIMIT", "25000"))

#: [(aas)] when is the retention window "full"? Only a FULL window licenses
#: the word `unreachable` — a half-filled one is still accruing, and calling
#: that unreachable is exactly the defect I17 was amended for (a thin sample
#: reported as a measured exclusion). 0.95 leaves a day of slack at 90d.
WINDOW_FULL_FRAC = 0.95


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
        self._trained_order: list[str] = []   # insertion order for the trim
        #: [(aag)] trainable rows inside `TRAIN_DAYS` at the last pass — the
        #: CEILING on `n_seen`, which is what makes "cold" and "unreachable"
        #: distinguishable. None until a pass has run: UNKNOWN, never 0, or a
        #: dark DB would publish a confident `unreachable` (I6).
        self._pool: int | None = None
        #: [(aas)] did the FETCH cap bind at the last pass, and how many days
        #: of tape did the pool actually span? Both None/False until a pass
        #: has run — UNKNOWN is never 0 (I6).
        self._truncated = False
        self._pool_span_d: float | None = None
        #: [(aaj)] set once, on the first training pass — see `_restore_state`.
        self._restored = False
        self._provenance = "cold"
        self._warmed = 0

    # -- readiness ------------------------------------------------------------
    def acc_z(self) -> float | None:
        """One-sided z of the BEST model's decayed accuracy against a coin flip.

        The EMA's memory is about one halflife of samples, so its effective n is
        `min(n_seen, ACC_HALFLIFE)` — deliberately the CONSERVATIVE reading. The
        true effective n of an EMA with smoothing a is (2-a)/a ~ 576 here, which
        would make the bar EASIER to clear; using the halflife keeps it stricter,
        the fail-safe direction for something that gates entries. None when there
        is nothing to grade."""
        vals = [v for v in self.acc.values() if isinstance(v, (int, float))]
        if not vals or self.n_seen <= 0:
            return None
        n_eff = min(float(self.n_seen), ACC_HALFLIFE)
        se = (0.25 / n_eff) ** 0.5
        if se <= 0:
            return None
        return (max(vals) - 0.5) / se

    def readiness(self) -> dict:
        """WHY `ready` is what it is — the distance and the binding constraint.

        `ready: false` was byte-identical between "warming up, ready Tuesday"
        and "structurally impossible, forever" ((lv): a component that produces
        nothing must publish its own census at its own bar). It reads
        `unreachable` when the training POOL itself cannot hold the bar, which
        names the gate that actually binds (I18) — the retention window, not
        the sample count."""
        z, pool = self.acc_z(), self._pool
        span = self._pool_span_d
        d = {"n_seen": self.n_seen, "min_samples": MIN_READY_SAMPLES,
             # [(aaj)] where this history came from. A restored `n_seen` and a
             # replayed one are byte-identical numbers about different things.
             "provenance": self._provenance, "warmed": self._warmed,
             "n_short": max(0, MIN_READY_SAMPLES - self.n_seen),
             "pool": pool, "train_days": TRAIN_DAYS,
             # [(aas)] the fetch cap and the tape the pool ACTUALLY spans.
             # Without these, `pool` is a number with no horizon attached and
             # `train_days` reads as one it may never have seen.
             "fetch_limit": TRAIN_LIMIT, "truncated": self._truncated,
             "pool_span_d": None if span is None else round(span, 1),
             "acc_z": None if z is None else round(z, 3),
             "acc_z_bar": ACC_Z_BAR}
        if not self.enabled:
            d["verdict"], d["blocked_by"] = "disabled", "numpy absent"
        elif self.n_seen < MIN_READY_SAMPLES:
            # [(aas)] NAME THE GATE THAT ACTUALLY BINDS (I18). There are three
            # here and they take different actions: raise the cap, raise the
            # retention, or wait. Naming the wrong one sends the next session
            # to fix a gate with room in it — which is what happened to (aag).
            if not isinstance(pool, int):
                d["verdict"] = "cold"
                d["blocked_by"] = "no training pass has run yet — pool UNKNOWN"
            elif pool >= MIN_READY_SAMPLES:
                d["verdict"] = "cold"
                d["blocked_by"] = f"{d['n_short']} more sample(s)"
            elif self._truncated:
                d["verdict"] = "unreachable"
                d["blocked_by"] = (
                    f"the {TRAIN_LIMIT}-row FETCH CAP binds: the query returned "
                    f"exactly its own limit"
                    + (f", spanning {span:.1f}d" if span else "")
                    + f" of a {TRAIN_DAYS:g}d retention — raise "
                      f"PARL_ML_TRAIN_LIMIT; raising the retention does nothing")
            elif span is not None and span >= TRAIN_DAYS * WINDOW_FULL_FRAC:
                d["verdict"] = "unreachable"
                d["blocked_by"] = (
                    f"the {TRAIN_DAYS:g}d RETENTION binds: {pool} trainable "
                    f"closes over a window that is FULL ({span:.1f}d) against a "
                    f"{MIN_READY_SAMPLES} bar — more time alone never arms this")
            else:
                # The window is not full, so supply is still accruing. Calling
                # that `unreachable` is the I17 defect (a thin sample reported
                # as an exclusion); it is `cold`, and it has a date.
                rate = (pool / span) if (span and span > 0) else None
                eta = ((MIN_READY_SAMPLES - pool) / rate) if rate else None
                d["verdict"] = "cold"
                d["blocked_by"] = (
                    f"{pool} trainable close(s)"
                    + (f" in {span:.1f}d of a {TRAIN_DAYS:g}d window that is "
                       f"NOT full yet" if span is not None else "")
                    + " — the CLOSE RATE binds, not the retention"
                    + (f"; at {rate:.1f}/day the {MIN_READY_SAMPLES} bar "
                       f"arrives in ~{eta:.0f}d" if eta is not None else ""))
        elif z is None or z < ACC_Z_BAR:
            best = max([v for v in self.acc.values()
                        if isinstance(v, (int, float))], default=None)
            d["verdict"] = "edgeless"
            d["blocked_by"] = (
                f"best model {'unknown' if best is None else format(best, '.4f')} is "
                f"z={'unknown' if z is None else round(z, 2)} from a coin flip, under "
                f"the {ACC_Z_BAR} bar — a count is not evidence")
        else:
            d["verdict"], d["blocked_by"] = "ready", None
        return d

    def is_ready(self) -> bool:
        """The ONE owner of the arming decision — `predict` and `snapshot` both
        call it, so the payload can never claim a readiness inference does not
        have (the `bar_map`-bound-to-`grade` discipline)."""
        return self.readiness()["verdict"] == "ready"

    # -- inference ------------------------------------------------------------
    def predict(self, features: dict) -> tuple[float, bool]:
        """(p_win, ready). Neutral 0.5/False when cold, disabled, or edgeless."""
        if not self.is_ready():
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

    # -- durable learning state -----------------------------------------------
    #: [(aaj)] WHAT IS PERSISTED, AND — the load-bearing half — WHAT IS NOT.
    #:
    #: NOT the model weights. Three of the five are `_WindowModel`s holding up
    #: to WINDOW raw samples each, so serialising them would duplicate the
    #: `trades` table into a ~1 MB blob rewritten every training pass, and it
    #: would put a numpy array's SHAPE in durable storage — where a later
    #: `FEATURES` extension (the module docstring invites one: "extend by
    #: APPENDING") silently restores weights of the wrong dimension. The window
    #: models are a FUNCTION of the retained rows and the DB already holds
    #: those, so they are rebuilt by `warm()` instead.
    #:
    #: What genuinely cannot be recovered is the PREQUENTIAL history: `acc`
    #: depends on the order of the samples and on predictions made by model
    #: states that no longer exist, and `n_seen` on rows the retention has
    #: since dropped. Those are the two the boot was destroying, and those are
    #: what this stores — three small scalars-and-strings, no arrays.
    _STATE_KEY = "keating.ml.state"
    _STATE_V = 1
    #: ids kept durable. Bounded well under the trim in `train_from_db`; the
    #: retained window holds ~a few hundred rows at any measured close rate.
    _TRAINED_KEEP = 4000

    def _save_state(self) -> None:
        """Never raises: a dark store costs the memory, never the training."""
        if not self.enabled or self.db is None:
            return
        try:
            self.db.remember(self._STATE_KEY, {
                "v": self._STATE_V,
                "dim": len(FEATURES),
                "models": [m.name for m in self.models],
                "n_seen": int(self.n_seen),
                "acc": {k: float(v) for k, v in self.acc.items()},
                "trained": list(self._trained_order[-self._TRAINED_KEEP:]),
            })
        except Exception:  # noqa: BLE001
            pass

    def _restore_state(self) -> str:
        """-> a provenance word, PUBLISHED, never a bare bool.

        Fail-safe is one-directional: any doubt returns without mutating a
        single field, so the engine falls back to the boot replay it has always
        done. A restore that half-lands is the only outcome worse than none —
        `acc` describing a roster or a feature space that is not the one in
        memory is a confident number about the wrong thing."""
        if not self.enabled or self.db is None:
            return "no-db"
        try:
            st = self.db.recall(self._STATE_KEY)
        except Exception:  # noqa: BLE001
            return "unreadable"
        if not isinstance(st, dict) or not st:
            return "none"
        if st.get("v") != self._STATE_V:
            return "version-changed"
        if st.get("dim") != len(FEATURES):
            return "features-changed"
        if list(st.get("models") or []) != [m.name for m in self.models]:
            return "roster-changed"
        acc, n = st.get("acc"), st.get("n_seen")
        if (not isinstance(acc, dict) or not isinstance(n, int)
                or isinstance(n, bool) or n < 0):
            return "junk"
        if set(acc) != set(self.acc) or not all(
                isinstance(v, NUM_T) and not isinstance(v, bool)
                and 0.0 <= v <= 1.0 for v in acc.values()):
            return "junk"
        ids = st.get("trained")
        if not isinstance(ids, list) or not all(isinstance(i, str) for i in ids):
            return "junk"
        self.acc = {k: float(v) for k, v in acc.items()}
        self.n_seen = int(n)
        self._trained_order = list(ids)
        self._trained_ids = set(ids)
        return "restored"

    # -- learning -------------------------------------------------------------
    def learn(self, features: dict, won: bool, *, score: bool = True) -> None:
        """Prequential: score each model's PRIOR prediction, then update it.

        `score=False` is the WARM path — see `warm()`. One function with a flag
        rather than two, so the update half cannot drift between them."""
        if not self.enabled:
            return
        x = vector(features)
        y = 1 if won else 0
        decay = 0.5 ** (1.0 / ACC_HALFLIFE)
        for m in self.models:
            try:
                if score:
                    p = m.predict(x)
                    hit = 1.0 if (p >= 0.5) == bool(won) else 0.0
                    self.acc[m.name] = self.acc[m.name] * decay + hit * (1 - decay)
                m.update(x, y)
            except Exception as e:  # noqa: BLE001
                log.warning("model %s update failed (%s)", m.name, e)
        if score:
            self.n_seen += 1

    def warm(self, features: dict, won: bool) -> None:
        """[(aaj)] Rebuild model state from a sample ALREADY counted — update,
        never score.

        A RESTORED `acc`/`n_seen` describes models that do not exist any more:
        the objects are fresh at every boot. So the retained rows have to be
        re-fed or the bench would sit UNTRAINED behind an `n_seen` claiming
        otherwise — the exact catastrophe that makes persisting the counters
        alone worse than persisting nothing. But re-SCORING them would count
        the same closes into the prequential EMA a second time and flatter it,
        which is what made the old boot-replay a deterministic artifact in the
        first place. Update only."""
        self.learn(features, won, score=False)

    def train_from_db(self) -> int:
        """Replay closed trades (with stored features) not yet learned —
        restart-proof memory, and the door other bots' rows come in through."""
        if not self.enabled or self.db is None:
            return 0
        rows = self.db.closed_trades(days=TRAIN_DAYS, limit=TRAIN_LIMIT)
        # [(aas)] the cap is passed EXPLICITLY so the horizon this engine
        # publishes is the horizon it reads, and its binding is measured here
        # rather than inferred downstream: a fetch that returns exactly its
        # own limit is truncated until proven otherwise ((qz)).
        self._truncated = len(rows) >= TRAIN_LIMIT
        trainable = [r for r in rows
                     if r["features"] and r["pnl_abs"] is not None]
        self._pool = len(trainable)
        _ts = [r["closed_ts"] for r in trainable
               if isinstance(r.get("closed_ts"), NUM_T)]
        self._pool_span_d = (
            max(0.0, (time.time() - min(_ts)) / 86400.0) if _ts else None)
        if not self._restored:
            # [(aaj)] ONCE per process, and BEFORE the new-row filter, because
            # what it restores is exactly the set that filter reads.
            self._restored = True
            self._provenance = self._restore_state()
            if self._provenance == "restored":
                # The counters came back; the MODELS did not (fresh objects at
                # every boot). Re-feed the rows they already account for —
                # update-only, so the prequential EMA is not double-counted.
                warm = sorted((r for r in trainable
                               if r["trade_id"] in self._trained_ids),
                              key=lambda r: r["closed_ts"] or 0)
                for r in warm:
                    self.warm(r["features"], r["pnl_abs"] > 0)
                self._warmed = len(warm)
        rows = [r for r in trainable
                if r["trade_id"] not in self._trained_ids]
        rows.sort(key=lambda r: r["closed_ts"] or 0)
        for r in rows:
            self.learn(r["features"], r["pnl_abs"] > 0)
            self._trained_ids.add(r["trade_id"])
            self._trained_order.append(r["trade_id"])
        # [2026-07-21 AUDIT FIX] bounded memory must drop the OLDEST ids —
        # trimming via set order kept an ARBITRARY half, so dropped ids still
        # inside the 30d fetch window were re-learned every 300s pass,
        # double-training samples and flattering the prequential accuracy.
        # An insertion-order list drives the trim; the set stays the O(1)
        # membership test.
        if len(self._trained_order) > 20000:
            keep = self._trained_order[-10000:]
            self._trained_order = keep
            self._trained_ids = set(keep)
        self._save_state()
        return len(rows)

    # -- reporting ------------------------------------------------------------
    def snapshot(self) -> dict:
        return {"enabled": self.enabled, "n_seen": self.n_seen,
                "ready": self.is_ready(),
                "readiness": self.readiness(),
                "oos_acc": {k: round(v, 4) for k, v in self.acc.items()}}

    async def run_forever(self, interval: float = 300.0, beat=None):
        import asyncio
        while True:
            n = self.train_from_db()
            if beat:
                r = self.readiness()
                beat("keating.ml",
                     f"+{n} samples (n={self.n_seen}/{MIN_READY_SAMPLES}, "
                     f"pool={r['pool']}, {r['verdict']})")
            await asyncio.sleep(interval)
