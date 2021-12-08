# HARVEST_SKIP
# Builtin imports
import logging
import datetime as dt

# Harvest imports
from harvest.algo import BaseAlgo
from harvest.trader import LiveTrader
from harvest.api.polygon import PolygonStreamer
from harvest.api.paper import PaperBroker
from harvest.storage.csv_storage import CSVStorage

# Third-party imports
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf


class EMAlgo(BaseAlgo):
    def config(self):
        self.watchlist = ["@BTC"]
        self.interval = "1MIN"

    def setup(self):
        now = dt.datetime.now()
        logging.info(f"EMAlgo.setup ran at: {now}")

        def init_ticker(ticker):
            return {ticker: {"initial_price": None, "ohlc": pd.DataFrame()}}

        self.tickers = {}
        for ticker in self.watchlist:
            self.tickers.update(init_ticker(ticker))

    def main(self):
        now = dt.datetime.now()
        logging.info("*" * 20)
        logging.info(f"EMAlgo.main ran at: {now}")

        if now - now.replace(hour=0, minute=0, second=0, microsecond=0) <= dt.timedelta(
            seconds=60
        ):
            logger.info(f"It's a new day! Clearning OHLC caches!")
            for ticker_value in self.tickers.values():
                ticker_value["ohlc"] = pd.DataFrame(
                    columns=["open", "high", "low", "close", "volume"],
                    index=["timestamp"],
                )

        for ticker, ticker_value in self.tickers.items():
            current_price = self.get_asset_price(ticker)
            current_ohlc = self.get_asset_candle(ticker)
            if current_ohlc is None:
                logging.warn("No ohlc returned!")
                return
            ticker_value["ohlc"] = ticker_value["ohlc"].append(current_ohlc)
            ticker_value["ohlc"] = ticker_value["ohlc"][
                ~ticker_value["ohlc"].index.duplicated(keep="first")
            ]

            if ticker_value["initial_price"] is None:
                ticker_value["initial_price"] = current_price

            logging.info("-" * 5 + ticker + "-" * 5)
            self.process_ticker(ticker, ticker_value, current_price)
            logging.info("-" * 20)
        logging.info("*" * 20)

    def process_ticker(self, ticker, ticker_data, current_price):
        initial_price = ticker_data["initial_price"]
        ohlc = ticker_data["ohlc"]

        if ohlc.empty:
            logging.warning(f"{ticker} does not have ohlc info! Not processing.")
            return

        # Calculate the price change
        delta_price = current_price - initial_price

        # Print stock info
        logging.info(f"{ticker} current price: ${current_price}")
        logging.info(f"{ticker} price change: ${delta_price}")

        axes.clear()
        mpf.plot(ohlc, ax=axes, block=False)
        plt.pause(3)


if __name__ == "__main__":
    # Store the OHLC data in a folder called `em_storage` with each file stored as a csv document
    csv_storage = CSVStorage(save_dir="em-polygon-storage")
    # Our streamer will be Polygon and the broker will be Harvest's paper trader. My secret keys are stored in `polygon-secret.yaml`
    polygon = PolygonStreamer(
        path="accounts/polygon-secret.yaml", is_basic_account=True
    )
    paper = PaperBroker()
    em_algo = EMAlgo()
    trader = LiveTrader(streamer=polygon, broker=paper, storage=csv_storage, debug=True)

    trader.set_algo(em_algo)

    fig = mpf.figure()
    axes = fig.add_subplot(1, 1, 1)
    # Update every minute
    trader.start("1MIN", all_history=False)
