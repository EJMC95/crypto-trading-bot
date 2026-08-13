# CUTOVER — 🙏 Avo Maria takes the live slot (tide-rider-lighter-live)

**Operator decision, 13-Aug-2026** (*"Change ticket taker to Avo Maria bot and
make live immediately, as we have done in the past - swap the bot routine.
Adjust metrics and parameters to the equity balance"*). The 17-Jul
Tide Rider → Ticket Taker pattern, third occupant: same service, same keys,
same sub-account (~$62.80), new routine.

**Everything is BUILT, TESTED and ON MAIN — and inert.** The live service is
not git-connected; nothing below happens until the activation dispatch. The
running Taker container keeps managing the (flat, self-halted) book meanwhile.

**Evidence basis, stated honestly (I19):** Avo Maria's shadow record at
build time — n≈10 closes, +1.378%/trade, t=+1.68, 3/6 go-live bars, horizon
`on_track`. It does NOT pass the (fk) gate; this is an explicit operator
go-live against the gate's advice, which go-live has always been the
operator's act. The shadow twin keeps running as the control arm.

## What is on main (all inert until dispatch)

| Piece | File |
|---|---|
| Live runner (SwingDip imported from the family registry — same signal, ROI ladder, −10% stop, protections; clip = equity/4; all live rails) | `lighter_avo_live_bot.py` |
| Image (born-dark-audited COPY set) | `Dockerfile.avolive` |
| Config-as-code repoint (the swap mechanism — filename kept deliberately, see its header) | `railway.tickettaker.toml` |
| Deploy routes (paths + `[deploy-live-taker]` marker grep carry the new image set) | `.github/workflows/railway-redeploy.yml` |
| Selftest registered (11 offline fixtures, mutation-verified ×7) | `tests/test_selftests.py` |
| Staged retirement of the old live row (apply ONLY after step 4) | `CUTOVER_AVO_LIVE_2026-08-13.patch` |

## Activation — two commands, in this order

**Pre-check (10 s):** the Taker live row must be FLAT — dashboard row
`lighter-ticket-taker-lighter`, `open` = 0. It has been 0/4 (self-halted)
since 13-Aug 03:11Z. If a position is open, wait for its bracket or flatten
first; the new bot would inherit management of any leftover position
(venue-truth loop), but a clean handover is cleaner evidence.

**1 — set the identity + balance-sized rails** (Railway auto-restarts the
old Taker image on a var change — harmless; it just keeps standing by):

```bash
railway variables --service tide-rider-lighter-live --set "AVO_VENUE=lighter_live" --set "FREQTRADE_AVO_MARIA_MAX_NOTIONAL=63" --set "LIGHTER_MAX_DAILY_LOSS=6"
```

* `AVO_VENUE` — the identity guard; the new image REFUSES to run without it.
* `FREQTRADE_AVO_MARIA_MAX_NOTIONAL=63` — hard cap ≈ the balance (SafetyRails
  boot-refuses live without an explicit cap).
* `LIGHTER_MAX_DAILY_LOSS=6` — the absolute daily-loss rail, ~10% of the
  book (the default $30 would be 48% of a $63 book — "adjust parameters to
  the equity balance" includes the rails). The 10% percent rail runs too.
* Already on the service, unchanged: `REAL_MONEY_KILL=DISARMED_I_UNDERSTAND`,
  `LIGHTER_API_PRIVATE_KEY`, `LIGHTER_ACCOUNT_INDEX`, `LIGHTER_API_KEY_INDEX`.
* If `RAILWAY_DOCKERFILE_PATH` is still set on the service from the 17-Jul
  era, REMOVE it (`railway variables --service tide-rider-lighter-live
  --remove RAILWAY_DOCKERFILE_PATH`) — a leftover would override the toml
  and rebuild the Taker. Step 4's stamp readback catches this regardless.

**2 — deploy the slot** (builds `Dockerfile.avolive` via the toml):

```bash
gh workflow run 305025607 -f services="tide-rider-lighter-live"
```

**3 — tell the session / verify.** A green run has never implied a container
took it — verify by STAMP READBACK on the new row
`freqtrade-avo-maria-lighter` in `/pnl.json`:

```bash
python3 -c "import bot_pnl_store as b; print(b.build_compute('lighter_avo_live_bot.py'))"
```

row `extra.build` must equal that id (and `extra.venue` = `lighter_live`,
`initial_equity` ≈ the balance at cutover). First publish within ~5 min of
the deploy finishing.

**4 — retire the old live row** (prevents the $62.80 double-counting the
fleet total — the exact reason the Tide Rider live row HAD to be retired on
17-Jul). After step 3 verifies:

```bash
git apply CUTOVER_AVO_LIVE_2026-08-13.patch
```

then commit/push (any session can do this; both halves — `RETIRED_ROWS`
hides the card, `LEGACY_BOTS` prunes the frozen row; the 56-close ledger is
kept as history). The Taker SHADOW arm is untouched and keeps grading.

## Rollback

`railway variables --service tide-rider-lighter-live --set "AVO_VENUE="`
(the identity guard refuses; the row goes error/standby, book flat) — then
repoint `railway.tickettaker.toml` back to `Dockerfile.tickettaker` and
dispatch again to restore the Taker. The kill switch
(`REAL_MONEY_KILL` → anything but the token) flattens + halts either bot.

## After cutover (housekeeping, any session)

* Prune the Taker entries from the `taker_files` marker grep in
  `railway-redeploy.yml` (left in during the transition, noted in-line).
* The judge/veto machinery specific to the Taker live arm goes quiet on its
  own (its row stops publishing); no organ change needed.
* Day-31 (~13-Sep): the new row has a policy-stamped, single-policy era from
  birth — `golive_readiness` grades it mechanically.
