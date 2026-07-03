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
