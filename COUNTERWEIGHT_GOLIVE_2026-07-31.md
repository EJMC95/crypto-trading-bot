# ⚖️ Counterweight — go-live readiness

**Status: PREPARED, NOT READY.** The live path exists, is gated and tested. The
book does not currently qualify, and the code refuses to arm until it does.

Operator ask (31-Jul): *"prepare Counterweight to go live"*, after a raised
concern was overridden. This records what was built, what the evidence says,
and the exact steps go-live would take.

---

## 1. Where the book actually stands (measured 31-Jul)

| | |
|---|---|
| Go-live gate | **3 of 6 bars** — fails `window` (13.0d < 30d), `closes` (28 < 30), `t` (1.23 < 2.0) |
| Passes | `mean` (+1.08%/trade), `halves` (+3.64/+2.56), `maxdd` (0.2% realised) |
| Equity | **$984.61** |
| Realised | +$7.29 over 48 closes |
| **Open P&L** | **−$22.68** across 24 legs |
| **True MTM** | **−$15.39** |
| Funding income (the thesis) | **$2.00** (`fund_realized` 1.4556 + `fund_open` 0.544) |
| Ledger integrity | clean — no same-pair overlaps, one writer |

**The book is losing money.** It has earned $2.00 of funding while carrying a
$22.68 open loss on the legs it holds to earn it.

### The trap this sits in

The three failing bars — window, closes, t — are **time and sample size only**.
At 2.15 closes/day it reaches n=30 within a day, 30 days ~17-Aug, and t=2.0 at
n≈74 (~21-Aug). Meanwhile `maxdd` reads **0.2% against a 15% bar** on a book
down 1.5% of capital, because the realised bar accumulates *closed* trades and
this book is **always-in** — its losses live in positions it has not closed.

So on trajectory **Counterweight passes all six bars in late August while its
equity is below $1,000.** That is the failure `(ia)` exists to prevent.

---

## 2. What was built

### (a) MTM drawdown folded into the gate — `scripts/golive_readiness.py`

`mtm_drawdown()` + `apply_mtm()` compute peak-to-trough drawdown from the
equity series `(hq)` started, and fold it into `max_dd_frac` **before**
`bar_map`/`grade` see it.

- **Strictly restrictive** — takes the **worse** of realised and MTM. It can
  only fail a book that currently passes; it never rescues one.
- **`bar_map` ≡ `grade` is preserved.** Neither function changed; only their
  input got honest. That equivalence is selftest-bound and load-bearing.
- **Floors** (`MTM_MIN_SAMPLES=200`, `MTM_MIN_DAYS=7`): below them the realised
  bar stands unchanged and `maxdd_basis` publishes `"realised"` plus a
  `mtm_why`, so a provisional verdict is never mistaken for a graded one. This
  is why `(hl)` refused to ship it on day one.
- **No series ⇒ byte-identical behaviour to before.**
- Payload gains `mtm`, `maxdd_basis`, `max_dd_pct_realised`.

### (b) A gated live path — `lighter_funding_spread_bot.py`

v1 refused `lighter_live` outright. v2 requires **three independent
conditions**, and with no env set the default is still to exit:

1. `VENUE=lighter_live` — the deployment choice
2. `FUNDSPREAD_GOLIVE=1` — a deliberate second act, this bot only
3. **the published go-live gate says `ready: true` for this book**

Condition 3 is what makes this preparation rather than a switch: the code
cannot get ahead of the evidence even with both env vars set.

**Fail-closed**, against this file's usual habit. A dark bus, a stale payload
(>25h), a missing book entry, an unparseable stamp, or `ready` being anything
other than exactly `True` all refuse. Elsewhere in this bot an organ outage
degrades to the operator's default because the cost is a missed shadow trade;
here the cost is unsupervised real money.

**The live arm is pinned to the validated config** — `K=5`, `$20/leg`, `$200`
gross — and takes **no capacity lever**. `(hs)` measured the growth rail
ratcheting `fundspread.k` 5 → 8 → 12 on a book at −$27.75; that lane must not
reach real money. Both terms of the exposure are pinned, since pinning `K`
alone would leave the clip free to reopen the hole from the other side.
`universe_n` still applies live — it widens what the book can *see*, not what
it holds.

### (c) Re-validation on Lighter's own tape

`scripts/backtest_xsect_funding_lighter.py --days 120`:

| | full | h1 | h2 | maxDD | funding |
|---|---|---|---|---|---|
| **Shipped live config (72/5/24)** | **+13.7%** | +3.5% | +9.3% | **9.6%** | +2.7pp |
| HL lab originally claimed | +13.7% | +5.7% | +8.9% | 11.9% | +6.8pp |

- **10 of 12 configs pass** — a real plateau, wider than the HL lab's 8/12
- **3× friction survival: PASS** — green in both halves at 5/10/15 bps per side
  (+13.7 / +11.2 / +8.8)
- Price mirror **−17.9%**, so the edge is the funding rank, not price momentum

**Two honest caveats.** Funding contributes **+2.7pp on Lighter vs +6.8pp
claimed on HL** — less of the return is carry than the original justification
implied. And `K=3` scored better (+18.0% / +21.1%) than `K=5`; K=5 stays the
choice because it is the pre-registered plateau centre, and picking the maximum
is fitting.

---

## 3. The distinction that matters

**The rule backtests well. The running book is losing money.** Both are true
and they are about different things:

- The backtest validates the *strategy* over 120d of Lighter tape.
- The gate reads the *shadow book's actual record*, which is 3/6 bars with a
  −$22.68 open loss.

The shadow period exists precisely because backtests can be optimistic. A good
backtest does not override a losing live book.

One material explanation for the divergence: **the book has not been running
the validated config.** It has been at K=8–12 (gross $320–480), above anything
the evidence covers, because of the `(hs)` defect. It is now unwinding to K=8
as that lever lapses. The live arm is pinned to K=5 for exactly this reason.

---

## 4. Go-live steps — for the operator, when it qualifies

Do **not** run these while the gate says NOT READY; step 4 will refuse anyway.

1. **Confirm the gate.** `/bus.json` → `golive_readiness.books
   ["perps-funding-spread-lshadow"]` shows `ready: true`, 6/6 bars, and check
   `maxdd_basis` — if it reads `"realised"`, the MTM series is still too thin
   and the drawdown number is provisional.
2. **Fund a dedicated sub-account** — its own keys, as every live book before
   it. Never share a sub-account (the `crypto-trend-daily-lighter` double-count
   is why).
3. **Set the service env**: `VENUE=lighter_live`, `FUNDSPREAD_GOLIVE=1`, plus
   the Lighter key vars. Leave `FUNDSPREAD_K` and `FUNDSPREAD_ORDER_USD` unset
   — the live arm pins them.
4. **Deploy and check the boot log.** It either prints `LIVE ARMED — gate
   READY` or a refusal naming the blocker. There is no silent third outcome.
5. **Verify by the published row**, not the deploy: `extra.svc` names the
   service and `extra.build`/`build_n` should match the repo `(fd)`-style.
6. **Add the new row to `CURRENT_BOTS`** and to the audit scope rule in
   CLAUDE.md — live books are always in audit scope.

**Kill switch:** unset `FUNDSPREAD_GOLIVE` (or set `VENUE=lighter_shadow`) and
redeploy. The book reverts to shadow without losing its ledger.

---

## 5. What is still not done

- **The MTM series is hours old**, not the ~30 days `(hl)` asked for. Until it
  crosses the floors, `maxdd_basis` will read `"realised"` and the drawdown bar
  remains the blind one. **This is the single thing standing between today and
  an honest go-live decision on this book.**
- **No live sub-account or keys exist** — operator-only.
- The always-in classification is deliberately *not* used: the worse-of rule
  applies uniformly, so no book needs classifying.
