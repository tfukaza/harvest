storages = {
    "memory": "BaseStorage",
    "csv": "CSVStorage",
    "pickle": "PickleStorage",
    "db": "DBStorage",
}

streamers = {
    "dummy": "DummyStreamer",
    "yahoo": "YahooStreamer",
    "polygon": "PolygonStreamer",
    "robinhood": "Robinhood",
    "alpaca": "Alpaca",
    "kraken": "Kraken",
    "webull": "Webull",
}

brokers = {
    "paper": "PaperBroker",
    "robinhood": "Robinhood",
    "alpaca": "Alpaca",
    "kraken": "Kraken",
    "webull": "Webull",
}

apis = list(k for k in streamers.keys()) + list(k for k in brokers.keys())


def load_storage(name: str) -> type:
    if name == "base":
        from harvest.storage.base_storage import BaseStorage

        return BaseStorage
    elif name == "csv":
        from harvest.storage.csv_storage import CSVStorage

        return CSVStorage
    elif name == "pickle":
        from harvest.storage.pickle_storage import PickleStorage

        return PickleStorage
    elif name == "db":
        from harvest.storage.database_storage import DBStorage

        return DBStorage
    else:
        raise ValueError(f"Invalid storage option: {name}")


def load_api(name: str) -> type:
    if name == "dummy":
        from harvest.api.dummy import DummyStreamer

        return DummyStreamer
    elif name == "yahoo":
        from harvest.api.yahoo import YahooStreamer

        return YahooStreamer
    elif name == "polygon":
        from harvest.api.polygon import PolygonStreamer

        return PolygonStreamer
    elif name == "robinhood":
        from harvest.api.robinhood import Robinhood

        return Robinhood
    elif name == "alpaca":
        from harvest.api.alpaca import Alpaca

        return Alpaca
    elif name == "kraken":
        from harvest.api.kraken import Kraken

        return Kraken
    elif name == "webull":
        from harvest.api.webull import Webull

        return Webull
    elif name == "paper":
        from harvest.api.paper import PaperBroker

        return PaperBroker
    else:
        raise ValueError(f"Invalid api option: {name}")
