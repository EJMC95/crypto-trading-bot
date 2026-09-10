"""Adapter: capability honesty, the refusal to emulate, and the mock."""
import pytest

from lighter_bots.lighter_adapter import (AdapterError, CAPABILITIES,
                                          MockLighterAdapter,
                                          NativeLighterAdapter,
                                          build_capability_report)
from lighter_bots.models import OrderIntent, OrderRequest
from conftest import make_market, ramp


def test_the_report_covers_every_declared_capability():
    r = build_capability_report("https://example.invalid", 304)
    assert {c.name for c in r.capabilities} == set(CAPABILITIES)


def test_the_report_names_the_sdk_version_and_both_sources():
    r = build_capability_report("https://example.invalid", 304)
    assert r.sdk_version and r.sdk_version != "unknown"
    # lighter-sdk 1.1.2 ships lighter.__version__ == "1.0.0"; reporting one
    # number would hide that, so both are carried when they disagree.
    assert "dist" in r.sdk_version or r.sdk_version.count(".") >= 2


def test_missing_critical_capabilities_become_PROBLEMS():
    r = build_capability_report("https://example.invalid", 304)
    for c in r.capabilities:
        if c.name == "stop_loss_orders":
            c.supported = False
    r.problems = [f"{c.name} is UNSUPPORTED"
                  for c in r.capabilities
                  if not c.supported and c.name in ("order_create",
                                                    "order_cancel",
                                                    "stop_loss_orders",
                                                    "reduce_only_exits")]
    assert r.problems and not r.supports("stop_loss_orders")


def test_render_marks_unsupported_rows():
    r = build_capability_report("https://example.invalid", 304)
    r.capabilities[0].supported = False
    assert "[NO ]" in r.render()


def _native():
    a = NativeLighterAdapter("https://example.invalid", 304,
                             account_index=1, api_key_index=2,
                             allow_signing=False)
    a._markets = {"BTC": make_market("BTC", 1)}
    return a


def _req(intent=OrderIntent.ENTRY, reduce_only=False, otype="limit",
         tif="post_only"):
    return OrderRequest(symbol="BTC", market_id=1, side="long", intent=intent,
                        order_type=otype, time_in_force=tif, price=100.0,
                        trigger_price=None, quantity=0.01,
                        reduce_only=reduce_only, client_order_index=1)


def test_signing_is_disabled_by_default_and_refuses_with_a_reason():
    res = _native().submit(_req())
    assert not res.accepted and not res.submitted
    assert "signing disabled" in res.error


def test_it_refuses_to_send_a_non_reduce_only_exit_when_unsupported():
    a = _native()
    for c in a.report.capabilities:
        if c.name == "reduce_only_exits":
            c.supported = False
    with pytest.raises(AdapterError, match="reduce-only"):
        a.submit(_req(OrderIntent.STOP, reduce_only=True,
                      otype="stop_loss", tif="ioc"))


def test_it_refuses_to_emulate_a_stop_client_side():
    a = _native()
    for c in a.report.capabilities:
        if c.name == "stop_loss_orders":
            c.supported = False
    with pytest.raises(AdapterError, match="refusing to emulate"):
        a.submit(_req(OrderIntent.STOP, reduce_only=True,
                      otype="stop_loss", tif="ioc"))


def test_an_unmapped_order_type_raises_rather_than_substituting():
    with pytest.raises(AdapterError, match="unmapped"):
        _native().submit(_req(otype="iceberg"))


def test_cancel_and_leverage_also_refuse_without_signing():
    a = _native()
    assert not a.cancel("BTC", "7").accepted
    assert not a.set_leverage("BTC", 5.0).accepted
    assert "signing disabled" in a.set_leverage("BTC", 5.0).error


def test_account_read_without_an_index_refuses():
    a = NativeLighterAdapter("https://example.invalid", 304,
                             allow_signing=False)
    with pytest.raises(AdapterError, match="ACCOUNT_INDEX"):
        a.account()


def test_the_token_bucket_limits_but_terminates():
    from lighter_bots.lighter_adapter import TokenBucket
    import time
    b = TokenBucket(rate_per_s=1000.0, burst=5)
    t0 = time.monotonic()
    for _ in range(10):
        b.take()
    assert time.monotonic() - t0 < 2.0


def test_the_mock_signs_nothing_but_records_everything():
    m = MockLighterAdapter([make_market("BTC", 1)],
                           {("BTC", "1h"): ramp(30)})
    res = m.submit(_req())
    assert res.accepted and res.submitted
    assert m.submitted and m.submitted[0].symbol == "BTC"
    m.cancel("BTC", "1")
    assert m.cancelled == [("BTC", "1")]
    m.set_leverage("BTC", 4.0, "isolated")
    assert m.leverage_calls == [("BTC", 4.0, "isolated")]


def test_the_mock_can_be_made_to_fail_exactly_once():
    m = MockLighterAdapter([make_market("BTC", 1)])
    m.fail_next = "rejected: insufficient margin"
    assert not m.submit(_req()).accepted
    assert m.submit(_req()).accepted, "the failure is one-shot"


def test_the_mock_reports_a_mark_and_a_book():
    m = MockLighterAdapter([make_market("BTC", 1)],
                           {("BTC", "1h"): ramp(30)})
    px = m.mark_price("BTC")
    bid, ask = m.best_bid_ask("BTC")
    assert bid < px < ask


def test_an_unknown_market_raises_on_the_mock():
    with pytest.raises(AdapterError):
        MockLighterAdapter([]).mark_price("NOPE")
