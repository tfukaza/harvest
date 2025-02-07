"""
This is a helper module that provides a factory function to load the necessary modules and packages dynamically.
"""

from harvest.enum import BrokerType, StorageType
from harvest.storage.base_storage import BaseStorage


def load_storage(storage_type: StorageType) -> BaseStorage:
    if storage_type.value == StorageType.BASE.value:
        from harvest.storage.base_storage import BaseStorage

        return BaseStorage
    elif storage_type.value == StorageType.CSV.value:
        from harvest.storage.csv_storage import CSVStorage

        return CSVStorage
    elif storage_type.value == StorageType.PICKLE.value:
        from harvest.storage.pickle_storage import PickleStorage

        return PickleStorage
    elif storage_type.value == StorageType.DB.value:
        from harvest.storage.database_storage import DBStorage

        return DBStorage
    else:
        raise ValueError(f"Invalid storage option: {storage_type}")


def load_broker(broker_type: BrokerType):
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
