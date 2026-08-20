#!/usr/bin/env python3
"""
paper_broker.py — a tiny self-contained paper-trading account for the Hyperliquid
dry-run bots.

WHY THIS EXISTS
  The hl-perps-rsi and hl-momo-breakout bots run "dry-run" by reading the REAL
  Hyperliquid testnet account value and positions. When that testnet wallet is
  unfunded (account value 0), the bots can never book a trade and the dashboard
  shows equity 0.0 / 0 trades forever — they look alive but do nothing.

  This broker gives dry-run a real simulated account: it books fills at the live
  price, tracks positions, marks them to market, and reports an equity curve —
  so the bots actually exercise their logic and the dashboard reflects activity,
  with NO dependency on a funded testnet wallet.

MODEL (deliberately simple, cash-settled perps, leverage 1):
  equity = start + realized_pnl - fees + unrealized_pnl
  * open(coin, is_long, size, price): flips/replaces any existing position in the
    coin (realising its P&L first), then opens the new one and charges a taker fee.
  * close(coin, price): realises P&L and removes the position (taker fee charged).
  * mark(coin, price): updates the last price used for unrealised P&L.

It is intentionally dependency-free and pure so it can be unit-tested offline
(see __main__). Slippage is not modelled; this is a dry-run aid, not a backtest.
"""
from __future__ import annotations


class PaperBroker:
    def __init__(self, start_equity: float = 1000.0, fee_bps: float = 4.0):
        self.start = float(start_equity)
        self.fee = float(fee_bps) / 10_000.0   # 4 bps = 0.04% per side
        self.realized = 0.0
        self.fees = 0.0
        # coin -> (signed_size, entry_price)
        self.pos: dict[str, tuple[float, float]] = {}
        # coin -> last seen price (for mark-to-market)
        self.marks: dict[str, float] = {}

    # -- price feed ---------------------------------------------------------
    def mark(self, coin: str, price: float) -> None:
        if price and price > 0:
            self.marks[coin] = float(price)

    # -- order entry --------------------------------------------------------
    def close(self, coin: str, price: float) -> float:
        """Realise and remove a position. Returns realised P&L for the close."""
        if coin not in self.pos or not price or price <= 0:
            return 0.0
        size, entry = self.pos.pop(coin)
        pnl = size * (price - entry)          # signed size handles long/short
        self.realized += pnl
        self.fees += abs(size) * price * self.fee
        self.marks[coin] = price
        return pnl

    def open(self, coin: str, is_long: bool, size: float, price: float) -> None:
        """Open (or flip into) a position of `size` units at `price`."""
        if not size or size <= 0 or not price or price <= 0:
            return
        if coin in self.pos:
            self.close(coin, price)           # flip: realise the old side first
        signed = size if is_long else -size
        self.pos[coin] = (signed, price)
        self.fees += abs(signed) * price * self.fee
        self.marks[coin] = price

    # -- persistence ---------------------------------------------------------
    def to_state(self) -> dict:
        """JSON-safe snapshot of the whole account (for bot_pnl_store.save_state),
        so a redeploy/restart continues the SAME equity curve instead of
        resetting to start_equity."""
        return {
            "start": self.start,
            "realized": self.realized,
            "fees": self.fees,
            "pos": {c: [s, e] for c, (s, e) in self.pos.items()},
            "marks": dict(self.marks),
        }

    def restore_state(self, state: dict) -> bool:
        """Rehydrate from a to_state() snapshot. Returns True if applied.
        Defensive: a malformed/missing snapshot leaves the account untouched."""
        try:
            start = float(state["start"])
            realized = float(state.get("realized", 0.0))
            fees = float(state.get("fees", 0.0))
            pos = {str(c): (float(v[0]), float(v[1]))
                   for c, v in (state.get("pos") or {}).items()}
            marks = {str(c): float(p) for c, p in (state.get("marks") or {}).items()}
        except Exception:
            return False
        self.start, self.realized, self.fees = start, realized, fees
        self.pos, self.marks = pos, marks
        return True

    # -- reporting ----------------------------------------------------------
    def unrealized(self) -> float:
        tot = 0.0
        for coin, (size, entry) in self.pos.items():
            mark = self.marks.get(coin, entry)
            tot += size * (mark - entry)
        return tot

    def equity(self) -> float:
        return self.start + self.realized - self.fees + self.unrealized()

    def szi(self) -> dict[str, float]:
        """Signed position sizes, mirroring Hyperliquid's `szi` field."""
        return {coin: size for coin, (size, entry) in self.pos.items()}

    def open_count(self) -> int:
        return len(self.pos)


class MarginSpec:
    """One market's margin requirement, as FRACTIONS (0.05 = 5%).

    The venue publishes both in basis points on every `/api/v1/orderBookDetails`
    row; `fleet_bus.market_margins()` serves them since (se). `imf` caps the size
    an account may open; `mmf` is the level at which it is CLOSED OUT, and it is
    the number that decides ruin.
    """
    __slots__ = ("imf", "mmf")

    def __init__(self, imf: float, mmf: float):
        self.imf = float(imf)
        self.mmf = float(mmf)

    @classmethod
    def from_bps(cls, imf_bps: float, mmf_bps: float) -> "MarginSpec":
        return cls(float(imf_bps) / 10_000.0, float(mmf_bps) / 10_000.0)

    def __repr__(self) -> str:
        return f"MarginSpec(imf={self.imf:.4f}, mmf={self.mmf:.4f})"


#: The spec applied to a market whose real one could not be read. DELIBERATELY
#: the harshest tier the venue runs (20% initial / 12% maintenance, measured
#: 20-Aug across 212 active books) — an unknown margin must never be modelled as
#: a generous one. Same fail-closed direction as `fleet_bus.max_leverage`, and
#: for the same reason: the cost of a wrong default here is a liquidation.
UNKNOWN_MARGIN = MarginSpec(0.20, 0.12)


class LiquidatedError(Exception):
    """Raised by `check()` when the modelled account is closed out."""


class LeveredPaperBroker(PaperBroker):
    """[2026-08-20] A paper account that can actually BE LIQUIDATED.

    WHY THIS EXISTS, and why a levered book on the base class is not merely
    imprecise but WRONG. `PaperBroker` is "cash-settled perps, LEVERAGE 1": no
    margin requirement, no maintenance level, no liquidation. Run a 3x book on
    it and a drawdown that would have closed a real account out at −33% instead
    rides the position down, marks it back up, and **books the recovery** — the
    account reports a profit the venue would never have let it collect. That
    turns a leveraged shadow book from evidence into fiction, in the one
    direction that matters: it makes ruin invisible.

    THE MODEL is cross-margin, which is what `market_config.market_margin_mode
    == 0` means on this venue:

        gross               = SUM |size_i * mark_i|
        maintenance_req     = SUM |size_i * mark_i| * mmf_i        <- PER MARKET
        liquidated          <=>  equity <= maintenance_req
        cross_leverage      = gross / equity

    `mmf` is per market and it VARIES — measured 20-Aug across the 212 active
    books: 1.20% x7 · 2.40% x9 · 3.00% x25 · 6.00% x89 · 12% x40 · 20% x35. A
    single assumed maintenance rate is therefore wrong by up to 16x, which is
    exactly how a ruin table can conclude "the stop fires first" for a portfolio
    containing a market where it does not.

    LIQUIDATION IS TOTAL AND IT IS NOT POLITE. On breach every position closes at
    the current mark and a liquidation fee is charged. A real venue does not
    close one leg and ask you to top up; modelling it as a partial unwind would
    reintroduce the same optimism this class exists to remove.

    `check()` MUST be called after every mark update and before every open —
    a breach that is only noticed at the end of a loop is a breach the account
    was allowed to trade through.
    """

    #: Charged on the gross notional when the account is closed out. The venue
    #: publishes `liquidation_fee` per market (1.0 on the books sampled); this is
    #: the conservative flat stand-in, declared rather than silently zero.
    LIQUIDATION_FEE_FRAC = 0.01

    def __init__(self, start_equity: float = 1000.0, fee_bps: float = 4.0,
                 margins: "dict[str, MarginSpec] | None" = None,
                 default_spec: "MarginSpec | None" = None):
        super().__init__(start_equity=start_equity, fee_bps=fee_bps)
        self.margins: dict[str, MarginSpec] = dict(margins or {})
        self.default_spec = default_spec or UNKNOWN_MARGIN
        self.liquidated = False
        self.liquidation_events: list[dict] = []

    # -- margin surface ------------------------------------------------------
    def spec(self, coin: str) -> MarginSpec:
        """This market's margin spec, or the HARSH default. Never a guess that
        flatters the account."""
        return self.margins.get(coin) or self.default_spec

    def set_margins(self, margins: dict) -> None:
        """Accept `fleet_bus.market_margins()` output ({sym: {imf_bps, mmf_bps}})
        or a {sym: MarginSpec} map. Rows that cannot be parsed are SKIPPED, so
        the market keeps the harsh default rather than a half-read one."""
        for sym, row in (margins or {}).items():
            if isinstance(row, MarginSpec):
                self.margins[str(sym)] = row
                continue
            try:
                imf = float(row["imf_bps"]) / 10_000.0
                mmf = float(row["mmf_bps"]) / 10_000.0
            except (TypeError, ValueError, KeyError):
                continue
            if imf > 0 and mmf > 0:
                self.margins[str(sym)] = MarginSpec(imf, mmf)

    # -- exposure ------------------------------------------------------------
    def _mark_of(self, coin: str, entry: float) -> float:
        return self.marks.get(coin, entry)

    def gross_notional(self) -> float:
        return sum(abs(size * self._mark_of(coin, entry))
                   for coin, (size, entry) in self.pos.items())

    def maintenance_requirement(self) -> float:
        """SUM over positions of |notional| * that market's OWN mmf."""
        return sum(abs(size * self._mark_of(coin, entry)) * self.spec(coin).mmf
                   for coin, (size, entry) in self.pos.items())

    def initial_requirement(self) -> float:
        return sum(abs(size * self._mark_of(coin, entry)) * self.spec(coin).imf
                   for coin, (size, entry) in self.pos.items())

    def cross_leverage(self) -> float:
        eq = self.equity()
        return (self.gross_notional() / eq) if eq > 0 else float("inf")

    def margin_ratio(self) -> float:
        """equity / maintenance_requirement. <= 1.0 is liquidation. inf when flat."""
        req = self.maintenance_requirement()
        return (self.equity() / req) if req > 0 else float("inf")

    def distance_to_liquidation(self) -> float:
        """The fraction of GROSS notional the book may lose before close-out.
        None-safe: returns inf when flat. This is the number a leverage design
        must quote, and computing it as `1/L` — ignoring mmf — overstates it."""
        g = self.gross_notional()
        if g <= 0:
            return float("inf")
        return (self.equity() - self.maintenance_requirement()) / g

    # -- the ruin check ------------------------------------------------------
    def check(self, raise_on_liquidation: bool = False) -> bool:
        """True when the account is (or has been) liquidated.

        Call after EVERY mark update and before EVERY open. A breach noticed a
        loop later is a breach the account was allowed to trade through, which
        is the exact optimism this class removes.
        """
        if self.liquidated:
            return True
        if not self.pos:
            return False
        eq = self.equity()
        req = self.maintenance_requirement()
        if eq > req:
            return False
        # CLOSED OUT. Everything goes, at the current mark, plus the fee.
        gross = self.gross_notional()
        ev = {"equity_at": round(eq, 6), "maintenance_req": round(req, 6),
              "gross": round(gross, 6),
              "coins": sorted(self.pos), "n": len(self.pos)}
        for coin in list(self.pos):
            size, entry = self.pos[coin]
            self.close(coin, self._mark_of(coin, entry))
        self.fees += gross * self.LIQUIDATION_FEE_FRAC
        ev["equity_after"] = round(self.equity(), 6)
        self.liquidated = True
        self.liquidation_events.append(ev)
        if raise_on_liquidation:
            raise LiquidatedError(
                f"account closed out: equity {eq:.4f} <= maintenance {req:.4f} "
                f"on {ev['n']} position(s)")
        return True

    def can_open(self, coin: str, size: float, price: float) -> bool:
        """Would this order leave enough equity for the INITIAL margin of the
        whole book? A liquidated account can never open again."""
        if self.liquidated or not size or not price:
            return False
        add = abs(float(size) * float(price)) * self.spec(coin).imf
        return self.equity() >= (self.initial_requirement() + add)

    # -- persistence ---------------------------------------------------------
    def to_state(self) -> dict:
        st = super().to_state()
        st["liquidated"] = self.liquidated
        st["liquidation_events"] = list(self.liquidation_events)
        st["margins"] = {c: [m.imf, m.mmf] for c, m in self.margins.items()}
        return st

    def restore_state(self, state: dict) -> bool:
        if not super().restore_state(state):
            return False
        # A liquidation SURVIVES a restart. Losing that bit across a redeploy
        # would let a closed-out book quietly resume trading, which is the
        # memory-only-halt failure this fleet has already paid for.
        self.liquidated = bool((state or {}).get("liquidated", False))
        self.liquidation_events = list((state or {}).get("liquidation_events") or [])
        for c, v in ((state or {}).get("margins") or {}).items():
            try:
                self.margins[str(c)] = MarginSpec(float(v[0]), float(v[1]))
            except (TypeError, ValueError, IndexError):
                continue
        return True

    # -- reporting -----------------------------------------------------------
    def risk_extra(self) -> dict:
        """The block a levered book publishes so its ruin distance is never a
        thing a reader has to re-derive (and get wrong)."""
        d = self.distance_to_liquidation()
        return {
            "gross_usd": round(self.gross_notional(), 4),
            "gross_x": round(self.cross_leverage(), 4),
            "maint_req_usd": round(self.maintenance_requirement(), 4),
            "margin_ratio": (None if d == float("inf")
                             else round(self.margin_ratio(), 4)),
            "dist_to_liq_frac": (None if d == float("inf") else round(d, 6)),
            "liquidated": self.liquidated,
            "n_liquidations": len(self.liquidation_events),
        }


if __name__ == "__main__":
    # Offline self-test of the accounting (no network, no deps).
    b = PaperBroker(start_equity=1000.0, fee_bps=4.0)

    # Flat account starts exactly at start equity.
    assert abs(b.equity() - 1000.0) < 1e-9, b.equity()

    # Open 1 unit long BTC @ 100. Fee = 1*100*0.0004 = 0.04.
    b.open("BTC", True, 1.0, 100.0)
    assert b.open_count() == 1
    assert abs(b.equity() - (1000.0 - 0.04)) < 1e-9, b.equity()

    # Price rises to 110: unrealised +10. Equity = 1000 - 0.04 + 10.
    b.mark("BTC", 110.0)
    assert abs(b.equity() - (1010.0 - 0.04)) < 1e-9, b.equity()

    # Close @ 110: realise +10, pay close fee 110*0.0004 = 0.044.
    pnl = b.close("BTC", 110.0)
    assert abs(pnl - 10.0) < 1e-9, pnl
    assert b.open_count() == 0
    assert abs(b.equity() - (1010.0 - 0.04 - 0.044)) < 1e-9, b.equity()

    # Short 2 units @ 50, price falls to 40 -> unrealised +20.
    b.open("ETH", False, 2.0, 50.0)
    b.mark("ETH", 40.0)
    assert b.szi() == {"ETH": -2.0}, b.szi()
    eq_open_fee = 2 * 50 * 0.0004
    base = 1010.0 - 0.04 - 0.044
    assert abs(b.equity() - (base - eq_open_fee + 20.0)) < 1e-9, b.equity()

    # Flip the short to a long @ 40: realises the +20, opens long.
    b.open("ETH", True, 2.0, 40.0)
    assert b.szi() == {"ETH": 2.0}, b.szi()
    print("paper_broker self-test: OK")
