# HARVEST_SKIP
# Builtin imports
import logging
import datetime as dt

# Harvest imports
from harvest.algo import BaseAlgo
from harvest.trader import LiveTrader
from harvest.api.kraken import Kraken
from harvest.storage.csv_storage import CSVStorage

# Third-party imports
import pandas as pd
import matplotlib.pyplot as plt
import mplfinance as mpf


class EMAlgo(BaseAlgo):
    def setup(self):
        now = dt.datetime.now()
        logging.info(f"EMAlgo.setup ran at: {now}")

        def init_ticker(ticker):
            fig = mpf.figure()
            ax1 = fig.add_subplot(2, 1, 1)
            ax2 = fig.add_subplot(3, 1, 3)
    
            return {
                ticker: {
                "initial_price": None, "ohlc": pd.DataFrame(),
                "fig": fig,
                "ax1": ax1,
                "ax2": ax2
                }
            }

        self.tickers = {}
        # self.tickers.update(init_ticker("@BTC"))
        self.tickers.update(init_ticker("@DOGE"))

    def main(self):
        now = dt.datetime.now()
        logging.info(f"EMAlgo.main ran at: {now}")

        if now - now.replace(hour=0, minute=0, second=0, microsecond=0) <= dt.timedelta(
            seconds=60
        ):
            logger.info(f"It's a new day! Clearning OHLC caches!")
            for ticker_value in self.tickers.values():
                ticker_value["ohlc"] = pd.DataFrame()

        for ticker, ticker_value in self.tickers.items():
            current_price = self.get_asset_price(ticker)
            current_ohlc = self.get_asset_candle(ticker)
            if ticker_value["initial_price"] is None:
                ticker_value["initial_price"] = current_price

            if current_ohlc.empty:
                logging.warn(f"{ticker}'s get_asset_candle_list returned an empty list.")
                return

            ticker_value["ohlc"] = ticker_value["ohlc"].append(current_ohlc)

            self.process_ticker(ticker, ticker_value, current_price)

    def process_ticker(self, ticker, ticker_data, current_price):
        initial_price = ticker_data["initial_price"]
        ohlc = ticker_data["ohlc"]

        # Calculate the price change
        delta_price = current_price - initial_price

        # Print stock info
        logging.info(f"{ticker} current price: ${current_price}")
        logging.info(f"{ticker} price change: ${delta_price}")

        # Update the OHLC graph
        ticker_data['ax1'].clear()
        ticker_data['ax2'].clear()
        mpf.plot(ohlc, ax=ticker_data['ax1'], volume=ticker_data['ax2'], type="candle")
        plt.pause(3)


if __name__ == "__main__":
    # Store the OHLC data in a folder called `em_storage` with each file stored as a csv document
    csv_storage = CSVStorage(save_dir="em_storage")
    # Our streamer and broker will be Alpaca. My secret keys are stored in `alpaca_secret.yaml`
    kraken = Kraken(
        path="accounts/kraken-secret.yaml"
    )
    em_algo = EMAlgo()
    trader = LiveTrader(streamer=kraken, broker=kraken, storage=csv_storage, debug=True)

    # trader.set_symbol("@BTC")
    trader.set_symbol("@DOGE")
    trader.set_algo(em_algo)
    mpf.show()

    # Update every minute
    trader.start("1MIN", all_history=False)
