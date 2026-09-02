# 🎫 Ticket Taker — go-live runbook (georgia's successor)

_Prepared 2026-09-02 (wi) after Eamon retired 🔮 georgia and asked to "prepare
the best candidate to take Georgia's place." This is a STAGED runbook: the taker
is not gate-ready yet (ETA ~3-Oct). Nothing here goes live until it passes the
gate AND Eamon funds it AND Eamon gives the explicit go-live word — the
un-amendable core. This document is the preparation, not the act._

## Why the taker is the best candidate

Measured on the live payload 2026-09-02, ranked against every non-live shadow book:

| Book | bars | t (cluster) | edge | n | ETA | shape |
|---|---|---|---|---|---|---|
| **🎫 taker** | **4/6** | **1.46** | **+0.691%/on-class-trade, +$85 realised** | **246** | **~3-Oct** | long+short, 5 lenses |
| pm-turnbull | 5/6 | 1.42 | +0.389%, **+$3.5 total** | 35 | ~13-Oct | thin, directional |
| 🌾 carry | 1/6 in-era | 3.07 pooled | best quality, **clean era n=7 flat** | 16 | ~months | funding (see below) |

The taker wins on the combination that matters for a real-money slot:

1. **The longest, cleanest track record in the shadow fleet** — n=246, a stable
   single-policy era since 30-Jul (150 closes), +$85 realised, on-class edge
   **+0.691%/trade** (n=145, t=1.46). turnbull passes one more bar but has almost
   no economic substance (+$3.5 over 35 closes).
2. **It diversifies mum, not doubles her.** mum is long-only oversold (pure
   directional beta). The taker trades **both sides across 5 lenses**
   (dip/breakout/breakoutup/momentum/divergence), so it is far less
   regime-correlated with mum than another long-only book would be.
3. **It is already proven live infrastructure** — it held the live slot before
   🙏 avo took it (13-Aug); the live arm code, the `LIVE_SIDES` hard gate
   (divergence-short-only on real money), and the safety rails all exist and
   were exercised on real money.
4. **Its only blockers are TIME, not tuning.** It fails `t` (1.46 < 2, needs
   ~290 closes, ~3-Oct at 4.48/day) and both-halves (its era's early-negative
   first half must roll off). Neither is a design flaw.

**The go-live clock is safe.** The era signature is `venue/bull/lenses/sides`
only ((jf)); the scout tuner moves the taker's BRACKET levers (`momo_chg`,
`max_hold_h`, `div_gap_pp`) but those are not in the signature, so ordinary
tuning does NOT reset its 30-day clock. No freeze is needed — it accumulates
cleanly to the gate. Do NOT change its lenses/sides/venue before go-live (that
WOULD reset it).

## What it must clear before go-live (the un-amendable gate)

Graded by `scripts/golive_readiness.py`, no exceptions:
- [ ] **t ≥ 2.0** — currently 1.46 (cluster). Binding. ETA ~3-Oct.
- [ ] **both halves positive** — currently era h1 negative (−6.85 / +71.63); the
      early-era negative window must age out.
- [x] window ≥ 30d · [x] ≥ 30 closes · [x] mean > 0 · [x] maxDD < 15% (2.3%).

A pass is 6/6 with a clean single-policy era. Go-live remains Eamon's explicit
act even at 6/6 — the gate is the door, not the decision.

## The go-live steps (execute only when 6/6 AND Eamon says go)

1. **Fund a sub-account.** georgia's freed `trail-blazer-live` account is drained
   to ~$0.01 (capital moved to mum). The taker needs its own funded sub-account
   — Eamon deposits and creates/points the keys, exactly as for 👩 mum's launch
   (never through the repo; a one-shot provisioner carries credentials).
2. **Pick the service.** Either repoint `trail-blazer-live` to the taker's live
   arm (`lighter_ticket_taker.py`, `Dockerfile.tickettaker`) or a fresh service.
   The taker's marker is **`[deploy-live-taker]` → tide-rider-lighter-live** in
   the current workflow, which is now avo's — so a new/renamed service + a new
   marker mapping is required. Resolve the service name against
   `railway service list` and add its `paths:`/grep rule
   (`audit_deploy_coverage.py` binds both).
3. **Verify live-code currency first** — `scripts/audit_code_currency.py` against
   the taker's own entry file. Its live arm has not run since 13-Aug; confirm the
   `LIVE_SIDES` gate (divergence-short-only), the notional cap env, and the
   `REAL_MONEY_KILL` disarm token are all set before it takes an order.
4. **Deploy** with the marker in the commit SUBJECT (never the body — (hj));
   verify by the `extra.build`+`build_n` stamp readback on the row, never a green
   run.
5. **Kill switch is Eamon's hand.** `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND` is set
   by Eamon, the same disarm he did for mum — the boot-refuse is the safety, and
   arming it is how the book is stopped.
6. **Watch the first close** for tag form, entry/exit prices, and pnl_pct×notional
   to the cent (the birth-audit contract every live book has passed).

## The strategic note Eamon should have: the live fleet is going all-directional

After this, the live fleet is mum + avo + taker — **all directional**, all
exposed to item-18 (Lighter's tape is one falling-BTC regime). The taker's
long/short breadth softens this, but the true regime diversifier is a **FUNDING**
book, which earns from funding rather than price direction.

**🌾 carry is that book** — the fleet's best edge quality (pooled t=3.07,
regime-agnostic) — but its CLEAN, on-screen era is only n=7 and flat (9 of its 16
era closes are the non-crypto class its own screen now refuses, and they are the
whole −$14.96). It is ~months from decidable at ~0.49 closes/day. **Recommendation:
develop carry in parallel as the fleet's regime hedge — not as georgia's immediate
successor, but as the next slot after the taker.** Its path to the gate is supply
+ time, not a rebuild.
