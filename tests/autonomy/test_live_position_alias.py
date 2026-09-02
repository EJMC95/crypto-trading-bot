#!/usr/bin/env python3
"""[2026-09-02 (wz)] ONE POSITION, ONE SPELLING — AND AN UNTRACKED LEG IS
ADOPTED INTO THE BRACKET, NEVER MANAGED FROM AN EMPTY META.

Found in Eamon's "mum doing well, today doesn't seem great — deep dive"
(2-Sep). Beside the tape (10 levered longs into a sliding BTC), the live host
had a real defect on a 1000-market: it opened `1000PEPE` (the scout's spelling,
which its universe/entries/meta carry) and `venue.positions()` handed the leg
back as `kPEPE` (`venues.symbol_map.from_lighter`). Two names for one real
position, so the reconciler read "1000PEPE in meta but NOT on the venue —
dropping meta" five minutes after the open, and then managed `kPEPE` from an
EMPTY meta: `age_min` pinned at zero (no `opened_ts`), so the 24h `max_hold`
could never fire, the roi ladder never decayed past its first rung, and the
close row booked untagged with a zero hold. On the real-money row: kPEPE and
kBONK closed 31-Aug as `long_roi` with `opened_at == closed_at`; 1000PEPE
opened 2-Sep 09:06:52Z was orphaned at 09:11:52Z ($442 of a $3.3k book).

The 🎫 taker closed this class on 17-Jul (`_live_pos` maps venue positions
back through `to_lighter`); the family live host never got it. These tests
DRIVE the real `main()` one cycle (the (sz) boot-smoke harness) rather than
grep the source:

  1  a 1000-market held on the venue keeps its bracket across the cycle — no
     drop, tag intact, `held` on the row names it (mutation: remove the
     `to_lighter` map at the positions read -> RED);
  2  a venue leg with NO meta is adopted: `opened_ts` stamped, tag `adopted`,
     loudly printed (mutation: remove the adoption block -> RED);
  3  the rescue — a pre-(wz) container's meta stranded under the ALIAS spelling
     is merged, not lost (its accrued funding survives) (mutation: remove the
     alias merge -> RED);
  4  an adopted leg OBEYS the bracket: past the time cap it closes
     `long-adopted_max_hold` through the venue — the whole point of adopting;
  5  a genuinely phantom meta (nothing on the venue) is still dropped — the
     reconciler's original job is untouched.
"""
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.autonomy.test_variant_host import loaded, _driven   # noqa: E402

ROW = "freqtrade-mum-lighter"


def _last_close():
    # the (sz) harness's oversold tape: 100 * 0.998^i, mark = last close
    return 100.0 * (0.998 ** 239)


def _state(meta):
    return {"initial_equity": 200.0, "meta": meta,
            "day_start": {"day": time.strftime("%Y-%m-%d", time.gmtime()),
                          "equity": 200.0}}


def _cycle(pos, meta):
    with loaded("freqtrade-mum", MUM_GROSS_X="2") as m:
        with _driven(m, tape="oversold") as box:
            box["venue"].pos = dict(pos)
            box["state"][m.STATE_KEY] = _state(meta)
            m.main(_ctx={"venue": box["venue"], "rails": box["rails"]},
                   once=True)
            out = dict(box)
            out["meta"] = (box["state"].get(m.STATE_KEY) or {}).get("meta") or {}
            out["held"] = [p for b, p in box["published"] if b == ROW][-1] \
                ["extra"]["held"]
    return out


# ---- 1  the bracket survives the alias ------------------------------------

def test_a_1000_market_keeps_its_bracket_across_the_cycle():
    px = _last_close()
    out = _cycle(
        pos={"kPEPE": {"size": 100.0, "entry": px}},
        meta={"1000PEPE": {"entry": px, "opened_ts": time.time() - 3600,
                           "tag": "oversold-rebound", "size": 100.0,
                           "accrued": 0.0}})
    assert not any("dropping meta" in p for p in out["printed"]), \
        [p for p in out["printed"] if "meta" in p]
    assert out["meta"].get("1000PEPE", {}).get("tag") == "oversold-rebound", \
        out["meta"]
    assert "kPEPE" not in out["meta"], out["meta"]
    assert out["held"] == {"1000PEPE": "oversold-rebound"}, out["held"]
    assert out["venue"].closes == [], out["venue"].closes


# ---- 2  an untracked leg is adopted ---------------------------------------

def test_a_venue_leg_with_no_meta_is_adopted_into_the_bracket():
    px = _last_close()
    out = _cycle(pos={"1000BONK": {"size": 100.0, "entry": px}}, meta={})
    m = out["meta"].get("1000BONK") or {}
    assert m.get("tag") == "adopted", out["meta"]
    assert float(m.get("opened_ts") or 0.0) > time.time() - 120, m
    assert out["held"] == {"1000BONK": "adopted"}, out["held"]
    assert any("ADOPTED" in p and "1000BONK" in p for p in out["printed"]), \
        out["printed"][-5:]


# ---- 3  the rescue of a stranded alias meta ---------------------------------

def test_a_meta_stranded_under_the_alias_spelling_is_merged_not_lost():
    px = _last_close()
    out = _cycle(
        pos={"kPEPE": {"size": 100.0, "entry": px}},
        # the exact shape a pre-(wz) container leaves behind: the reconciler
        # dropped `1000PEPE` and then wrote size/entry/last_px/accrued under
        # the venue's own key, with no tag and no clock.
        meta={"kPEPE": {"entry": px, "size": 100.0, "last_px": px,
                        "accrued": -0.5}})
    assert "kPEPE" not in out["meta"], out["meta"]
    m = out["meta"].get("1000PEPE") or {}
    assert m.get("tag") == "adopted", out["meta"]
    assert abs(float(m.get("accrued")) - (-0.5)) < 0.05, m   # carried over
    assert float(m.get("opened_ts") or 0.0) > 0, m


# ---- 4  an adopted leg obeys the bracket -----------------------------------

def test_an_adopted_leg_closes_on_the_time_cap_through_the_venue():
    px = _last_close()
    out = _cycle(
        pos={"1000BONK": {"size": 100.0, "entry": px * 1.005}},
        meta={"1000BONK": {"entry": px * 1.005,        # -0.5%: no roi, no stop
                           "opened_ts": time.time() - 25 * 3600,
                           "tag": "adopted", "size": 100.0, "accrued": 0.0}})
    assert out["venue"].closes == ["1000BONK"], out["venue"].closes
    rows = [kw for b, kw in out["paper"] if b == ROW]
    assert rows and rows[-1]["reason"] == "long-adopted_max_hold", \
        [r.get("reason") for r in rows]


# ---- 5  a real phantom is still dropped -------------------------------------

def test_a_meta_with_nothing_on_the_venue_is_still_dropped():
    px = _last_close()
    out = _cycle(
        pos={},
        meta={"SOL": {"entry": px, "opened_ts": time.time() - 3600,
                      "tag": "oversold-rebound", "size": 1.0,
                      "accrued": 0.0}})
    assert any("SOL in meta but NOT on the venue" in p
               for p in out["printed"]), out["printed"][-5:]
    assert "SOL" not in out["meta"], out["meta"]
