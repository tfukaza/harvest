"""Helper factories for supported broker and storage components."""

from harvest.enum import BrokerType, StorageType


def load_storage(storage_type: StorageType):
    """Load a supported storage class.

    Args:
        storage_type: Supported storage backend identifier.

    Returns:
        The storage class for the requested backend.

    Raises:
        ValueError: If the storage type is not supported.
    """
    if storage_type.value == StorageType.BASE.value:
        from harvest.storage.schema.market import CentralStorage

        return CentralStorage
    if storage_type.value == StorageType.CSV.value:
        from harvest.storage.csv_storage import CSVStorage

        return CSVStorage

    raise ValueError(f"Unsupported storage option: {storage_type}")


def load_broker(broker_type: BrokerType):
    """Load a legacy broker class.

    .. deprecated::
        Legacy brokers are used by the Orchestrator runtime path.
        For agent-based workflows, use ``harvest.services.*Service`` classes.
    """
    import warnings
    warnings.warn(
        "load_broker() loads legacy broker implementations. "
        "For agent-based workflows, use harvest.services.*Service classes.",
        DeprecationWarning,
        stacklevel=2,
    )
    if broker_type.value == BrokerType.DUMMY.value:
        from harvest.broker.mock import DummyDataBroker

        return DummyDataBroker
    elif broker_type.value == BrokerType.YAHOO.value:
        from harvest.broker.yahoo import YahooBroker

        return YahooBroker
    elif broker_type.value == BrokerType.POLYGON.value:
        from harvest.broker.polygon import PolygonBroker

        return PolygonBroker
    elif broker_type.value == BrokerType.ROBINHOOD.value:
        from harvest.broker.robinhood import RobinhoodBroker

        return RobinhoodBroker
    elif broker_type.value == BrokerType.ALPACA.value:
        from harvest.broker.alpaca import AlpacaBroker

        return AlpacaBroker
    elif broker_type.value == BrokerType.WEBULL.value:
        from harvest.broker.webull import WebullBroker

        return WebullBroker
    elif broker_type.value == BrokerType.PAPER.value:
        from harvest.broker.paper import PaperBroker

        return PaperBroker
    elif broker_type.value == BrokerType.BASE_STREAMER.value:
        from harvest.broker._base import StreamBroker

        return StreamBroker
    else:
        raise ValueError(f"Invalid broker option: {broker_type}")
