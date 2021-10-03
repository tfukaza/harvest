# Builtin imports
import logging
import datetime as dt

# Harvest imports
from harvest.algo import BaseAlgo
from harvest.trader import Trader
from harvest.api.alpaca import Alpaca
from harvest.storage.csv_storage import CSVStorage

# Third-party imports
import pandas as pd
import mplfinance as mpf

class EMAlgo(BaseAlgo):
    def setup(self):
        now = dt.datetime.now()
        logging.info(f'EMAlgo.setup ran at: {now}')

        def init_ticker(ticker):
            return {
                ticker: {
                    'initial_price': None,
                    'ohlc': pd.DataFrame()
                }
            }

        self.tickers = {}
        self.tickers.update(init_ticker('AAPL'))
        self.tickers.update(init_ticker('MSFT'))

    def main(self):
        now = dt.datetime.now()
        logging.info(f'EMAlgo.main ran at: {now}')

        if now - now.replace(hour=0, minute=0, second=0, microsecond=0) <= dt.timedelta(seconds=60):
            logger.info(f'It\'s a new day! Clearning OHLC caches!')
            for ticker_value in self.tickers.values():
                ticker_value['ohlc'] = pd.DataFrame()

        for ticker, ticker_value in self.tickers:
            current_price = self.get_asset_price(ticker)
            current_ohlc = self.get_asset_ohlc(ticker)
            if ticker_value['initial_price'] is None:
                ticker_value['initial_price'] = current_price

            self.process_ticker(ticker, ticker_value, current_price, current_ohlc)

    def process_ticker(self, ticker, ticker_data, current_price, current_ohlc):
        initial_price = ticker_data['initial_price']
        ohlc = ticker_data['ohlc']

        # Calculate the price change
        delta_price = current_price - initial_price

        # Print stock info
        logging.info(f'{ticker} current price: ${current_price}')
        logging.info(f'{ticker} price change: ${delta_price}')

        # Update the OHLC data

        # Update the OHLC graph
        mpf.plot(ohlc)


if __name__ == '__main__':
    # Store the OHLC data in a folder called `em_storage` with each file stored as a csv document
    csv_storage = CSVStorage(save_dir='em_storage')
    # Our streamer and broker will be Alpaca. My secret keys are stored in `alpaca_secret.yaml`
    alpaca = Alpaca(path='accounts/alpaca_account.yaml', is_basic_account=True, paper_trader=True)
    em_algo = EMAlgo()
    trader = Trader(streamer=alpaca, broker=alpaca, storage=csv_storage, debug=True)

    # Watch for Apple and Microsoft
    trader.set_symbol('AAPL')
    trader.set_symbol('MSFT')

    trader.set_algo(em_algo)

    # Update every minute
    trader.start('1MIN', all_history=False)


