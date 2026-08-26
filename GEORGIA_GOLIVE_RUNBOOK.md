# 🔮 GEORGIA TAKES 💸 THE FARMER'S SUB-ACCOUNT — the operator runbook

**Eamon, 22-Aug:** *"just replace farmer with georgia as weve done so many times
before"* / *"thats easier, once your metrics and paramters are finished
obviously"* / *"update and sync everywhere afterwards obviously"*.

This supersedes the new-sub-account plan this file carried before. The swap is
cheaper and it is the fleet's own precedent: 🎫 the Ticket Taker took 🌊 Tide
Rider's live row on the same service/keys/sub-account (17-Jul), and 🙏 Avo took
the Taker's (13-Aug (ma)).

---

## Why — the fleet's own grader, not an opinion about a bad week

`golive-readiness`, published 21-Aug 22:31Z:

| row | n | mean/trade | t | halves | maxDD | horizon |
|---|---|---|---|---|---|---|
| 💸 `perps-funding-lighter-lighter` **(LIVE)** | 91 | **−0.160%** | −0.88 | +2.51 / **−7.65** | pass | **unreachable** |
| 💸 `perps-funding-lighter-lshadow` | 161 | **−0.195%** | −0.95 | +5.71 / **−18.32** | pass | **unreachable** |
| 🔮 `freqtrade-georgia-lshadow` | 151 | **+0.171%** | 1.48 | **+5.65 / +10.08** | pass | on_track |

Both Farmer arms agree in sign **and** in verdict. `unreachable` is the grader's
own phrase for *"mean ≤ 0 — more of the same closes cannot flip mean/t/halves"*,
and it is the (mr)/(nf) red-stop class landing on the real-money row.

**STATE THE BAR PLAINLY, ONCE: georgia has NOT passed the go-live gate.** She is
5 of 6 — window, closes, mean, halves and maxDD all pass; **`t` reads 1.48
against a 2.0 bar**. Go-live is an explicit operator act and this is Eamon's,
made on the record. What the code owes him is the arithmetic, published every
loop on the row, which is what `leverage` and `scan` are for.

---

## The order is the safety property

Two processes must never hold one sub-account. If georgia boots while the Farmer
still runs there, the Farmer reads her positions as untracked and can flatten
them, and her equity guard reads his fills as unexplained capital.

### 1 · Retire the Farmer's live arm and let it flatten

```
git commit -m "... [deploy-live-farmer]"      # marker in the SUBJECT, never the body
git push
```

The guard is already in the code. On the first loop after the deploy the live
arm latches its own daily-halt path, which **flattens every held coin, retries
until flat, blocks entries and keeps heart-beating**. The shadow twin is
untouched and keeps trading — it is the control arm.

**WAIT FOR THE RECEIPT.** On `/pnl.json`:

```
perps-funding-lighter-lighter  status=halted  extra.retired.open == 0
```

`extra.retired.open` is the number of positions still held. **`open == 0` is the
only signal that it is safe to move the keys.** Verify `extra.build` /
`extra.build_n` changed too — a green workflow run has never meant a container
took the deploy.

Closes are booked `long_retired` / `short_retired`, not `daily_loss`, so the
ledger says what actually happened.

### 2 · Create `georgia-live` and move the sub-account

Service `georgia-live`, image **`Dockerfile.avolive`** (the same image 🙏 Avo
runs — `lighter_avo_live_bot.py` is a variant host since (sx), so this is one
container with a different book selected by env).

Move from `trail-blazer-live`, do not copy: the Lighter API key / secret /
account index for that sub-account, so exactly one service holds them.

Then set:

| var | value | note |
|---|---|---|
| `FAMILY_LIVE_BOOK` | `freqtrade-georgia` | **must be exactly this.** Absent ⇒ Avo. Set-but-blank ⇒ the process REFUSES to start (a typo must never point georgia's service at Avo's row, state key and real positions) |
| `GEORGIA_VENUE` | `lighter_live` | the only accepted value; anything else refuses |
| `FREQTRADE_GEORGIA_MAX_NOTIONAL` | `deposit × GEORGIA_GROSS_X` | hard boot gate — the process will not start without it, and the refusal message names this exact variable |
| `GEORGIA_GROSS_X` | see the table below | defaults to **1.0**, so an unset value is unlevered, never a guess |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | **a reference, never a pasted literal** ((kb)) |

At the Farmer's current equity (**$186.86**, 21-Aug) and 5 slots:
`clip = equity × GROSS_X / 5`.

### 3 · Uncomment the deploy rule, in the same commit as the service

`.github/workflows/railway-redeploy.yml` carries georgia's `[deploy-live-georgia]`
rule commented out, because the resolve step fails on a service that does not
exist. Uncomment it **with** the service — a rule for a missing service is a red
build, and a missing rule is a book that never receives a fix.

---

## What `GEORGIA_GROSS_X` buys, and the two numbers that are not appetite

Her stop is **−5%** (half Avo's), so the same multiplier means half the
book-level risk — and the venue's worst maintenance margin across her universe
is **600bps**, measured, not assumed.

| `GROSS_X` | all-slots-stop | liquidation gap | stop can fire? |
|---|---|---|---|
| 1.0 | 5% | −94.0% | yes |
| **2.8** | **14%** | −29.7% | yes — **strictly inside the gate's 15% maxDD bar**, the (sr) choice |
| 3.0 | 15% | −27.3% | yes — but **exactly ON the bar**, not inside it: the gate is `maxDD < 15%`, so an all-slots stop makes her ineligible at the same instant it fires ((gv)'s 📊 Index Rider trap). This is why `(sr)` shipped 🙏 Avo at 1.4 and not 1.5 |
| **5.0** | 25% | −14.0% | yes — Eamon's stated setting; above the gate bar, deliberately |
| 9.09 | 45.5% | −5.0% | **the last setting at which the protective stop fires at all** |
| **10.0** | 50% | −4.0% | **NO — the venue liquidates first and the stop is dead code** |

`all_slots_stop = GROSS_X × |stoploss|` and `liquidation gap = 1/GROSS_X − mmf`,
both published on the row every loop (`leverage.all_slots_stop_pct`,
`leverage.liq_gap_pct`) as FRACTIONS.

The ceiling `AVO_GROSS_X_MAX` / `GEORGIA_GROSS_X_MAX` is **10.0** per Eamon,
22-Aug (*"let avo go up to 10x, and georgia also"*). It is a **ceiling**, not a
setting. The one line above that is not a matter of appetite is the last row:
above 9.09x her `-5%` stop cannot execute before liquidation, so it stops being
a rail. The row publishes `leverage.stop_reachable` and
`leverage.stop_dead_above` every loop so this is readable rather than argued.

Leverage moves her **no closer to the gate** — it multiplies mean and sd alike,
so `t` is invariant (I22, seven prior rejections). It moves dollars and drawdown,
together, in both directions.

---

## After it is live

* **Add her to the evidence board's live set** — `EVBOARD_LIVE_ROWS` on
  `freqtrade-bots`: `perps-funding-lighter-lighter,freqtrade-avo-maria-lighter,freqtrade-georgia-lighter`
  (drop the Farmer once its row is pruned). `live.georgia.clip_scale` is already
  registered and mapped; the board acts on `LIVE_ROWS` alone.
* **Hide + prune the Farmer's live row** — `RETIRED_ROWS` in `pnl_dashboard.py`
  and `LEGACY_BOTS` in `cleanup_legacy_bots.py`, **after** `open == 0` is
  confirmed. Doing it before blinds the very feed the flatten is verified on
  (`/pnl.json` is filtered by the dashboard's roster). Ledgers are kept either
  way — the 136 real-money closes live in `paper_trades`.
* **The 🧪 judge has already stood down** — it publishes
  `phase="stood_down"` naming the retirement rather than silently never
  promoting. Zero `live.*` levers were open at the retirement, so nothing was
  stranded.
* **Resurrecting the Farmer** needs `FARMER_LIVE_RETIRED_OVERRIDE=run` on
  **both** `trail-blazer-live` and `freqtrade-bots` — the bot and the judge read
  one declaration (`fleet_bus.RETIRED_LIVE_ARMS`) and parse the override
  identically. A half-set override is a live book with no judge.
