# 🔮 georgia — live-arm runbook

_Written 2026-08-22 (sx). The code is ready and INERT. Nothing below has been
done; every step is Eamon's._

## Where the gate stands

She is **5 of 6 go-live bars, failing only `t` (1.48 against the 2.0 bar)** —
n=163, +0.163%/trade, both halves positive, maxDD inside the bar, window and
close-count already clear. `golive_readiness` publishes `READY: []` for the
whole fleet today.

`(sv)` raised her entries-per-hour cap 2 → 3 on measured evidence, so at her
recent rate the remaining ~135 closes is **~10 days**; at her lifetime rate it
is ~33. Go-live has always been an explicit operator act — the arm below is
built so the decision is a switch, not a project.

## What 5x means on her

Her stop is **−5%**, half 🙏 Avo's, so the same multiplier is half the drawdown.
Nothing here is hand-typed: the leverage layer reads `S.stoploss`.

| | 🔮 georgia | 🙏 Avo |
|---|---|---|
| all-slots-stop at 5x | **25%** | 50% |
| gross the 15% maxDD bar allows at `N_eff` 1 | **3.00x** | 1.50x |
| …at her basket today (`N_eff` 1.457) | **3.62x** | — |
| …after a diversified fill (`N_eff` 3.390) | **5.52x** | — |

**5x is inside her own drawdown budget once the basket spreads**, and it spreads
by inheritance — `diversified_order` offers WTI before BTC. Below `N_eff` 2.78
she is above budget; the row publishes `leverage.vol_target_here` every loop so
that is readable rather than argued.

## Step 1 — create the Railway service

Name it `georgia-live`. Same image as Avo's live arm (`Dockerfile.avolive`) —
the runner is a variant host, so **no new Dockerfile and no new build**.

## Step 2 — the sub-account

The sub-account IS `LIGHTER_ACCOUNT_INDEX`. Set it to the new account index on
this service only. Its keys are its own; nothing is shared with Avo's service.

    LIGHTER_API_PRIVATE_KEY      <the sub-account's key>
    LIGHTER_ACCOUNT_INDEX        <the new sub-account index>
    LIGHTER_API_KEY_INDEX        <as issued>
    DATABASE_URL                 ${{Postgres.DATABASE_URL}}   # a REFERENCE, never a literal ((kb))

## Step 3 — identity and sizing

    FAMILY_LIVE_BOOK             freqtrade-georgia
    GEORGIA_VENUE                lighter_live      # exact string or it refuses to boot
    GEORGIA_GROSS_X              5
    GEORGIA_GROSS_X_MAX          5
    FREQTRADE_GEORGIA_MAX_NOTIONAL   <see step 4>
    REAL_MONEY_KILL              DISARMED_I_UNDERSTAND   # exact token or SafetyRails refuses

A typo in `FAMILY_LIVE_BOOK` — including a blank value — **refuses to boot**
rather than falling back to Avo. That matters: the fallback would have pointed
this service at Avo's row, state key and live positions.

## Step 4 — size the notional cap to the deposit

`clip = equity × gross_x ÷ 5 slots`, and all five slots must fit under the cap
or the book silently settles below capacity (the `(sr)` defect that cost 🙏 Avo
a slot). So:

    FREQTRADE_GEORGIA_MAX_NOTIONAL  =  deposit × 5   (+ a few % of headroom)

e.g. a **$250** deposit → clip $250, gross $1,250 → set the cap to **$1,300**.
The row publishes `cap_slots`; if it reads below 5, the cap is what is holding
her down, not the signal.

## Step 5 — deploy

Uncomment the `[deploy-live-georgia]` block in
`.github/workflows/railway-redeploy.yml` **in the same commit that creates the
service** (a rule naming a service that does not exist fails the resolve step).
It has its own marker on purpose: two live books share this image, and every
georgia fix would otherwise restart Avo — a restart wipes memory-only halts.

Verify the deploy landed by the row's `extra.build` + `extra.build_n`, never by
a green run.

## Step 6 — the day she is funded

    EVBOARD_LIVE_ROWS  perps-funding-lighter-lighter,freqtrade-avo-maria-lighter,freqtrade-georgia-lighter

That switches the evidence board's live-clip arm on for her. The lever
(`live.georgia.clip_scale`) is already registered and restrict-only.

## What to read on the row

* `scan` — the (st) census: why nothing opened, with the RSI gauge and idle clocks
* `cap_slots` — below 5 means the cap, not the signal, is the constraint
* `leverage.{set, n_eff, basket_rho, vol_target_here, all_slots_stop_pct}` —
  `set` above `vol_target_here` is the risk being taken, stated
* `entry_vetoes` — every gate that can stop her, including the brain and the
  fleet long budget

## Not done, and deliberately

The go-live gate holds her closed at `t=1.48`. This runbook builds the arm; it
does not open the gate, and nothing here should be read as saying she has
passed it.
