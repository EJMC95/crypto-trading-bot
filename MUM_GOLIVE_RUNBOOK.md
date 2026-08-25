# 👩 MUM V2 GOES LIVE ON HER OWN SUB-ACCOUNT — the operator runbook

**Eamon, 25-Aug:** *"Get mum v2 ready to launch under a sub account."*

Third variant on the proven runner: `lighter_avo_live_bot.py` hosts 🙏 Avo,
🔮 georgia and now 👩 mum, selected by `FAMILY_LIVE_BOOK`. Unlike georgia's
launch there is **no predecessor to flatten and no key to move** — a fresh
sub-account gets fresh keys, created once in the venue UI and pasted once into
the new service. No credential is ever read from an existing service, which is
the property the (tb) plan change existed to buy, and here it comes free.

---

## The bar, stated once, plainly

**Mum v2 has not passed the go-live gate — her v2 era has not produced a close
yet.** The era began 2026-08-19 21:45Z; her 7 lifetime closes are 3 v1 closes
plus 4 `v1_legacy` flattens, all excluded from the v2 grade by construction
(era keys on the OPEN). The gate's 30-day window floor opens **2026-09-18**.
Her entry cell is **hypothesis-grade and stamped so in her own class
docstring** — (qu)'s measured `rsi<25` dose whose rolling dose-response has
decayed through zero. What she carries that no prior live book has: **her own
control arm** — `extra.control` publishes her mean against a matched-window
random-entry null every loop, so the verdict will be readable from the row
itself. Going live is an explicit operator act, and this is Eamon's, on the
record. What the code owes him is the arithmetic, published on the row every
loop.

---

## What is ALREADY DONE (prep, shipped 25-Aug)

* `lighter_avo_live_bot._BOOKS` carries `freqtrade-mum` → (`MUM`,
  `live.mum.clip_scale`). Her strategy comes from the family registry BY
  IDENTITY (OversoldRebound, 1h, −4% stop, 4 slots, roi 2%→0 over 24h) so the
  live and shadow arms cannot drift.
* `live.mum.clip_scale` is registered (cage [0.5, 1.0], restrict-only, lane
  `lighter-live`) **and** its prefix is in `_LIVE_PREFIX_OWNERS` — the (tb)
  registered-but-unwritable trap closed in the same commit.
* `fleet_books.ROW_ENTRY` maps `freqtrade-mum-lighter` →
  `lighter_avo_live_bot.py` (pre-mapped per the (jb) gate).
* `evidence_board.LIVE_CLIP_LEVERS` pre-maps her arm (the (sx) pattern; the
  board still acts on `LIVE_ROWS` alone).
* The `[deploy-live-mum]` rule sits **commented** in
  `railway-redeploy.yml` — uncomment WITH the service, same commit.
* `tests/autonomy/test_variant_host.py` drives a full `main()` cycle as mum
  (oversold tape → her cell opens, her row, her state key, her 4-slot
  geometry), pins her leverage arithmetic, and pins that her boot refusal
  names `FREQTRADE_MUM_MAX_NOTIONAL`.

## What only Eamon can do, in order

### 1 · Create the sub-account and its keys

In the Lighter UI: new sub-account, deposit, create an API key/secret for it.
These keys are BORN in this step and pasted in step 2 — they never exist
anywhere else.

### 2 · Create the `mum-live` service

Image **`Dockerfile.avolive`** (the same image Avo and georgia run). Set:

| var | value | note |
|---|---|---|
| `FAMILY_LIVE_BOOK` | `freqtrade-mum` | **exactly this.** Absent ⇒ Avo. Unknown or blank ⇒ the process REFUSES to start |
| `MUM_VENUE` | `lighter_live` | the only accepted value; anything else refuses |
| `FREQTRADE_MUM_MAX_NOTIONAL` | `deposit × MUM_GROSS_X` | hard boot gate — the process will not start without it, and the refusal names this exact variable |
| `MUM_GROSS_X` | see the table below | defaults to **1.0** — an unset value is unlevered, never a guess |
| Lighter API key / secret / account index | from step 1 | fresh, pasted once |
| `DATABASE_URL` | `${{Postgres.DATABASE_URL}}` | **a reference, never a pasted literal** ((kb)) |

`clip = equity × MUM_GROSS_X / 4` (her four slots).

### 3 · Uncomment the deploy rule, in the same commit as the service

`[deploy-live-mum]` in `.github/workflows/railway-redeploy.yml` → service
`mum-live`. A rule for a missing service is a red build; a missing rule is a
book that never receives a fix.

### 4 · After the row publishes `venue=lighter_live` — the feed-followers

These are TRIPWIRES checked against the live payload; editing them early
reddens CI (`audit_live_roster` diffs the declaration against
`live_rows_from_feed`, both directions, fail-closed on a dark feed). Move
them only once `/pnl.json` shows `freqtrade-mum-lighter` with
`extra.venue == "lighter_live"`. The (tb) swap called this list "eleven
registries" and the 25-Aug gap audit measured it at **thirteen** — two went
red on main when georgia's row replaced the Farmer's because the (tb) list
missed them. The full sweep:

* `fleet_books.DECLARED_LIVE` (scripts/fleet_books.py — the tripwire itself).
* `fleet_books.MARKER_GATED` gains `freqtrade-mum-lighter` →
  `("[deploy-live-mum]", "[deploy-live]")` — move this WITH the deploy-rule
  uncomment (step 3), not with the feed.
* `EVBOARD_LIVE_ROWS` env on `freqtrade-bots` — ONE shared roster read by
  BOTH `evidence_board.LIVE_ROWS` and `fleet_proprioception.LIVE_ROWS`
  (an earlier draft cited `PROP_LIVE_ROWS` and `fleet_books.LIVE_DEPLOY`;
  neither exists — corrected 25-Aug).
* `scripts/deploy_live_verify.py` `LIVE_SERVICES`: `mum-live` →
  `("freqtrade-mum-lighter", "[deploy-live-mum]")`.
* `fleet_agronomy` BookSpec (`live=True`, state key
  `freqtrade-mum-lighter:live`, lever `live.mum.clip_scale`) — and DELETE
  the `freqtrade-mum-lighter` entry from
  `tests/autonomy/test_agronomy_coverage.AGRONOMY_COVERAGE_OK` in the same
  commit (it declares the pre-provision omission; a live row hiding behind
  it is the unscanned-real-money failure).
* The marker-gate case table in `audit_deploy_coverage._marker_logic_selftest`
  gains the mum marker's routing (mum marker → `mum-live` only; the avo and
  georgia markers exclude it; `[deploy-live]` takes all three).
* `fleet_respiration.LIVE_BREATHS` += `"freqtrade-mum-lighter": 1800` — one
  of the two the (tb) list missed.
* `market_context.LIVE_CADENCE_SEC` += `"freqtrade-mum-lighter": 1200` — the
  other one.
* CLAUDE.md's live-audit-scope rule — the live set becomes Avo + georgia +
  mum (same file pair: `lighter_avo_live_bot.py` + `lighter_family_bot.py`).
* `HANDOFF.md` regenerated (`scripts/session_state.py`).

### 5 · Pre-activation follow-up (a session's job, before or at launch)

* **Port the control arm to the variant host.** `extra.control` is published
  by the family SHADOW loop only; the live host has no control-arm code, so
  until it is ported the null reads from **`freqtrade-mum-lshadow`** — same
  strategy object, same signals, the paired instrument (hm) requires. The
  port is mechanical (entry: record a random other coin's mark; close:
  settle the pair atomically; persist through redeploys per (rp)) and must
  bring (rp)-grade persistence tests with it.

---

## What `MUM_GROSS_X` buys — her stop is the tightest in the family

Stop **−4%** (Avo −10%, georgia −5%), so the same multiplier is the SMALLEST
book-level risk of the three. Venue's measured worst maintenance margin across
the family universe: **600bps** (IWM/MSTR; ADA/DOT/AVAX/LINK). The row
publishes the live number every loop (`leverage.*`).

| `GROSS_X` | all-slots-stop | liquidation gap | stop can fire? |
|---|---|---|---|
| 1.0 | 4% | −94.0% | yes |
| **3.7** | **14.8%** | −21.0% | yes — **strictly inside the gate's 15% maxDD bar** (3.75 is exactly ON it — the (gv) trap; ship inside, not on) |
| 5.0 | 20% | −14.0% | yes — above the gate bar, a deliberate operator setting |
| 9.5 | 38% | −4.5% | yes — barely |
| **10.0** | 40% | −4.0% | **NO.** Her ceiling lands EXACTLY at the 10x cap: `1/(0.04+0.06) = 10.0`. At the tie the stop and liquidation are the same price, and `stop_reachable` reads the tie as DEAD (the 25-Aug float-guard) |

`all_slots_stop = GROSS_X × 4%`, `liq gap = 1/GROSS_X − mmf`, both published
as fractions on the row (`leverage.all_slots_stop_pct`, `leverage.liq_gap_pct`),
with `stop_reachable` / `stop_dead_above` beside them.

`MUM_GROSS_X_MAX` defaults to **10.0** (Eamon's 22-Aug family ceiling). It is
a ceiling, not a setting. Leverage moves her **no closer to the gate** — it
multiplies mean and sd alike, so `t` is invariant (I22). It moves dollars and
drawdown, together, in both directions.

**A sizing suggestion, not a rule:** her book is one v2 entry old. At
`MUM_GROSS_X=1.0` a $500 deposit runs $125 clips — already 2.5× her shadow's
$50 — and every close she books grades the SAME hypothesis whatever the
multiplier, so starting at 1.0 and raising it after the control arm has an
answer costs nothing but patience.

---

## After it is live

* Her shadow arm (`freqtrade-mum-lshadow`, in `family-lighter-shadow`) keeps
  trading untouched — it is the control-cohort twin, same registry object.
* The brain's sizing reaches her restrict-only through the host (the (sp)
  invariant); her `live.mum.clip_scale` is the board's, restrict-only, cage
  [0.5, 1.0].
* Watch the first day for: `scan` census (why nothing opened — `rsi_bar` 25
  vs `rsi_med`), the control arm accruing on **`freqtrade-mum-lshadow`**'s
  `extra.control` (on the live row only once the §5 port lands), and
  `leverage.stop_reachable: true`.
