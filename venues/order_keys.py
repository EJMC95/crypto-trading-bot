"""[2026-09-03 (xt)] The identity a venue order is filed under — one owner.

Deliberately a LEAF module: no imports, no SDK, no venue client. The live host
needs this name at module import time to stamp `raw.order_key` on every order,
and `venues.lighter_client` needs the identical rule for its pending-fill
queue. Importing the client to get it would drag the Lighter SDK and its
asyncio loop into the host's import graph at load time — which the host
deliberately avoids (it imports `LighterClient` lazily, inside a function).

A SECOND COPY OF THIS RULE IS A SECOND RULE ((hj)). If the queue keyed one way
and the ledger another, every deferred resolution would miss its row while
both sides looked perfectly correct — and the failure would be silent, which
is the shape this fleet keeps paying for.
"""


def fill_key(client_id=None, tx_hash=None):
    """`tx:<hash>` | `cid:<n>` | None.

    The tx hash is senior because it identifies the SETTLED transaction, while
    a client order index identifies only what we asked for. None when the venue
    echoed neither: an order that cannot be named cannot be resolved later, and
    saying so beats inventing a key that would match the wrong row."""
    if tx_hash:
        return f"tx:{tx_hash}"
    if client_id is not None:
        return f"cid:{client_id}"
    return None
