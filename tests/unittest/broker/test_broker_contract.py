"""Sanity tests for the broker contract."""



def test_broker_surface_exposes_runtime_hooks() -> None:
    from harvest.broker._base import Broker

    assert hasattr(Broker, "setup")
    assert hasattr(Broker, "set_event_bus")


def test_broker_surface_exposes_price_publication_helpers() -> None:
    from harvest.broker._base import Broker

    assert hasattr(Broker, "_publish_ticker_candle")
    assert hasattr(Broker, "_publish_all_ticker_candle")
