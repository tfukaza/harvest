"""
This code uses the pickle storage class in action.
"""
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.api.yahoo import YahooStreamer
from harvest.api.paper import PaperBroker
from harvest.storage import PickleStorage


class Watch(BaseAlgo):
    def main(self):
        print(self.get_asset_price())


if __name__ == "__main__":

    # Fetch data from yfinance package.
    streamer = YahooStreamer()

    # A fake broker that simulates buying and selling assets.
    broker = PaperBroker()

    # Will create the given directory if it does not exist.
    # If no directory is provided, will use a directory called data.
    storage = PickleStorage("./dir_where_data_is_saved")

    t = Trader(streamer, broker, storage)
    t.set_symbol("AAPL")
    t.set_algo(Watch())

    t.start("1MIN")
