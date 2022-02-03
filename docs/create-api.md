## Creating an API

### Attributes

The following attributes can / should be implemented:

`interval_list`(List): Optional. A list of supported intervals to fetch asset OHLC data. Here are the intervals that Harvest supports:

* 1 minute
* 5 minutes
* 15 minutes
* 30 minutes
* 1 hour
* 1 day

`exchange`(str): Optional. The name of the exchange the broker trades on.

`req_keys`:(List): Optional. The keys of the loaded yaml secret file used to authenticate with the API.

### Functions

The following functions can / should be implemented and preferrable in the following order:

```python
__init__(self) -> None
```

Optional. Creates an instance of your API

```python
setup(self, stats: Stats, account: Account, trader_main: Callable = None) -> None
```  

Optional. Creates pointers to the methods passed in. Calculates the `poll_interval` which is the smallest interval presented in the `stats`'s watchlist.

```python
start(self) -> None
```  

Optional. Starts an infinite loop that call main on every `poll_interal`.

```python
main(self) -> None
```  

Optional. Gets the OHLC data for each asset and passes them to the trader's `main` function.

```python
exit(self) -> None
```  

Optional. Runs after all the algorithms finish.

```python
create_secret(self) -> Dict[str, str]
```

Optional. Walks users though the processes of getting their keys / tokens for this API and returns a python dictionary with that data. Used by the base API's `__init__` to create a yaml file with that information.

```python
refresh_cred(self) -> None
```  

Optional. Updates any temporary keys used to authenticate.

#### Streamer Methods

```python
get_current_time(self) -> dt.datetime
```  

Optional. Gets the current time with minute precision and in the UTC timezone.

```python
fetch_price_history(self, symbol: str, interval: Interval, start: Union[str, dt.datetime] = None, end: Union[str, dt.datetime] = None) -> pd.DataFrame:
```  

Required. Fetchs the asset's OHLC data. `start` and `end` are either ISO 8601 compliant strings or `datetime` objects. Returns a pandas `DataFrame` where the index is a pandas `DatetimeIndex` and the multi-level columns contain the asset's symbol and then the keys: `open`, `high`, `low`, `close`, and `volume`.

```python
fetch_latest_price(self, symbol: str) -> float
```  

Optional. Fetchs the latest price for given symbol.

```python
fetch_chain_info(self, symbol: str) -> Dict[str, Any]
```  

Optional. Fetchs chain info. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_chain_data(self, symbol: str, date: Union[str, dt.datetime]) -> pd.DataFrame:
```  

Optional. Fetchs chain data and returns a pandas `DataFrame`. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_option_market_data(self, symbol: str) -> Dict[str, Any]
```  

Optional. Fetchs option market data. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_market_hours(self, date: dt.date) -> Dict[str, Any]
```  

Required. Fetchs if the market is currently open, when it will open next, and the next time it will close.

#### Broker Methods

```python
fetch_stock_positions(self) -> List
```  

Optional. Returns a list of stock position the user owns. If not implemented, will return an empty list.

```python
fetch_option_positions(self) -> List
```  

Optional. Returns a list of option position the user owns. If not implemented, will return an empty list.

```python
fetch_crypto_positions(self) -> List
```  

Optional. Returns a list of crypto position the user owns. If not implemented, will return an empty list.

```python
fetch_account(self) -> Dict[str, float]
```  

Optional. Gets the user's account information. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_stock_order_status(self, id) -> Dict[str, Any]
```  

Optional. Gets the user's stock orders. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_option_order_status(self, id) -> Dict[str, Any]
```  

Optional. Gets the user's options orders. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_crypto_order_status(self, id) -> Dict[str, Any]
```  

Optional. Gets the user' crypto orders. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
fetch_order_queue(self) -> List
```  

Optional. Returns a list of all user's orders. If not implemented, will return an empty list.

#### Trading Methods

```python
order_stock_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]
```  

Optional. Places a stock limit order. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
order_option_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]
```  

Optional. Places a option limit order. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
order_crypto_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]
```  

Optional. Places a crypto limit order. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
cancel_stock_order(self, order_id) -> None
```  

Optional. Cancels a stock order. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
cancel_option_order(self, order_id) -> None
```  

Optional. Cancels an option order. If not implemented, any calls to this function, it will throw a `NotImplementError`.

```python
cancel_crypto_order(self, order_id) -> None
```  

Optional. Cancels a crypto order. If not implemented, any calls to this function, it will throw a `NotImplementError`.


### Skeleton Code

```python
# Builtins
import datetime as dt
from typing import Any, Callable, Dict, List, Tuple, Union

# External libraries
import pandas as pd

# Submodule imports
from harvest.definitions import *
from harvest.utils import *


class MY_API(API):
    """
    A description of your API and what requirements it needs
    """

    # List of intervals your API supports. These are all intervals that Harvest supports.
    interval_list = [
        Interval.MIN_1,
        Interval.MIN_5,
        Interval.MIN_15,
        Interval.MIN_30,
        Interval.HR_1,
        Interval.DAY_1,
    ]
    # Name of the exchange this API trades on
    exchange = ""
    # List of attributes that are required to be in the secret file
    req_keys = []

    def __init__(self, path: str = None) -> None:
        """
        Initalizes your class
        """
        super().__init__(path)
        # Other configurations such as authenticating to your API here.

    def setup(
        self, stats: Stats, account: Account, trader_main: Callable = None
    ) -> None:
        """
        This function is called right before the algorithm begins,
        and initializes several runtime parameters like
        the symbols to watch and what interval data is needed.

        :trader_main: A callback function to the trader which will pass the data to the algorithms.
        """
        super().setup(stats, account, trader_main)

    def start(self) -> None:
        """
        This method begins streaming data from the API.

        The default implementation below is for polling the API.
        If your brokerage provides a streaming API, you should override
        this method and configure it to use that API. In that case,
        make sure to set the callback function to self.main().
        """
        super().start()

    def main(self) -> None:
        """
        This method is called at the interval specified by the user.
        It should create a dictionary where each key is the symbol for an asset,
        and the value is the corresponding data in the following pandas dataframe format:
                      Symbol
                      open   high    low close   volume
            timestamp
            ---       ---    ---     --- ---     ---

        timestamp should be an offset-aware datetime object in UTC timezone.

        The dictionary should be passed to the trader by calling `self.trader_main(dict)`
        """
        # Iterate through securities in the watchlist. For those that have
        # intervals that needs to be called now, fetch the latest data
        super().main()

    def create_secret(self) -> Dict[str, str]:
        """
        This method is called when the yaml file with credentials
        is not found. It returns a dictionary containing the necessary credentials.
        """
        debugger.warning("Assuming API does not need account information.")

    # -------------- Streamer methods -------------- #

    def fetch_price_history(
        self,
        symbol: str,
        interval: Interval,
        start: Union[str, dt.datetime] = None,
        end: Union[str, dt.datetime] = None,
    ) -> pd.DataFrame:
        """
        Fetches historical price data for the specified asset and period
        using the API. The first row is the earliest entry and the last
        row is the latest entry.

        :param symbol: The stock/crypto to get data for. Note options are not supported.
        :param interval: The interval of requested historical data.
        :param start: The starting date of the period, inclusive.
        :param end: The ending date of the period, inclusive.
        :returns: A pandas dataframe, same format as main()
        """
        if start is None:
            if interval in [
                Interval.MIN_1,
                Interval.MIN_5,
                Interval.MIN_15,
                Interval.MIN_30,
            ]:
                start = self.get_current_time() - dt.timedelta(days=2)
            elif interval == Interval.HR_1:
                start = self.get_current_time() - dt.timedelta(days=14)
            else:
                start = self.get_current_time() - dt.timedelta(days=365)

        if end is None:
            end = self.get_current_time()

        start = convert_input_to_datetime(start)
        end = convert_input_to_datetime(end)
        results = # TODO: Fetch results and format them to Harvest's specification.
        return results

    def fetch_latest_price(self, symbol: str) -> float:
        interval = self.poll_interval
        end = self.get_current_time()
        start = end - interval_to_timedelta(interval) * 2
        price = self.fetch_price_history(symbol, interval, start, end)
        return price[symbol]["close"][-1]

    def fetch_chain_info(self, symbol: str) -> Dict[str, Any]:
        """
        Returns information about the symbol's options

        :param symbol: Stock symbol. Cannot use crypto.
        :returns: A dict with the following keys and values:
            - chain_id: ID of the option chain
            - exp_dates: List of expiration dates as datetime objects
            - multiplier: Multiplier of the option, usually 100
        """
        super().fetch_chain_info(symbol)

    def fetch_chain_data(
        self, symbol: str, date: Union[str, dt.datetime]
    ) -> pd.DataFrame:
        """
        Returns the option chain for the specified symbol.

        :param symbol: Stock symbol. Cannot use crypto.
        :param date: Expiration date.
        :returns: A dataframe in the following format:

                    exp_date strike  type
            OCC
            ---     ---      ---     ---
        exp_date should be a timezone-aware datetime object localized to UTC
        """
        super().fetch_chain_info(symbol, date)

    def fetch_option_market_data(self, symbol: str) -> Dict[str, Any]:
        """
        Retrieves data of specified option.

        :param symbol:    OCC symbol of option
        :returns:   A dictionary:
            - price: price of option
            - ask: ask price
            - bid: bid price
        """
        super().fetch_chain_info(symbol)

    def fetch_market_hours(self, date: dt.date) -> Dict[str, Any]:
        """
        Returns the market hours for a given day.
        Hours are based on the exchange specified in the class's 'exchange' attribute.

        :returns: A dictionary with the following keys and values:
            - is_open: Boolean indicating whether the market is open or closed
            - open_at: Time the market opens in UTC timezone.
            - close_at: Time the market closes in UTC timezone.
        """
        return # TODO: Fetch maket hours

    # ------------- Broker methods ------------- #

    # If you only want to implement a streamer, you can delete all the code below this line.

    def fetch_stock_positions(self) -> List:
        """
        Returns all current stock positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol of the stock
            - avg_price: The average price the stock was bought at
            - quantity: Quantity owned
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_stock_positions`. Returning an empty list."
        )
        return []

    def fetch_option_positions(self) -> List:
        """
        Returns all current option positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: OCC symbol of the option
            - base_symbol: Ticker symbol of the underlying stock
            - avg_price: Average price the option was bought at
            - quantity: Quantity owned
            - multiplier: How many stocks each option represents
            - exp_date: When the option expires
            - strike_price: Strike price of the option
            - type: 'call' or 'put'
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_option_positions`. Returning an empty list."
        )
        return []

    def fetch_crypto_positions(self) -> List:
        """
        Returns all current crypto positions

        :returns: A list of dictionaries with the following keys and values:
            - symbol: Ticker symbol for the crypto, prepended with an '@'
            - avg_price: The average price the crypto was bought at
            - quantity: Quantity owned
        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_crypto_positions`. Returning an empty list."
        )
        return []

    def fetch_account(self) -> Dict[str, float]:
        """
        Returns current account information from the brokerage.

        :returns: A dictionary with the following keys and values:
            - equity: Total assets in the brokerage
            - cash: Total cash in the brokerage
            - buying_power: Total buying power
            - multiplier: Scale of leverage, if leveraging
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_account`."
        )

    def fetch_stock_order_status(self, id) -> Dict[str, Any]:
        """
        Returns the status of a stock order with the given id.

        :id: ID of the stock order

        :returns: A dictionary with the following keys and values:
            - type: 'STOCK'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_stock_order_status`."
        )

    def fetch_option_order_status(self, id) -> Dict[str, Any]:
        """
        Returns the status of a option order with the given id.

        :id: ID of the option order

        :returns: A dictionary with the following keys and values:
            - type: 'OPTION'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_option_order_status`."
        )

    def fetch_crypto_order_status(self, id) -> Dict[str, Any]:
        """
        Returns the status of a crypto order with the given id.

        :id: ID of the crypto order

        :returns: A dictionary with the following keys and values:
            - type: 'CRYPTO'
            - order_id: ID of the order
            - quantity: Quantity ordered
            - filled_quantity: Quantity filled so far
            - side: 'buy' or 'sell'
            - time_in_force: Time the order is in force
            - status: Status of the order
            - filled_time: Time the order was filled
            - filled_price: Price the order was filled at
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `fetch_crypto_order_status`."
        )

    def fetch_order_queue(self) -> List:
        """
        Returns all current pending orders

        returns: A list of dictionaries with the following keys and values:
            For stocks and crypto:
                - order_type: "STOCK" or "CRYPTO"
                - symbol: Symbol of asset
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - order_id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - side: 'buy' or 'sell'
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at
            For options:
                - order_type: "OPTION",
                - symbol: OCC symbol of option
                - base_symbol:
                - quantity: Quantity ordered
                - filled_qty: Quantity filled
                - filled_time: Time the order was filled
                - filled_price: Price the order was filled at
                - order_id: ID of order
                - time_in_force: Time in force
                - status: Status of the order
                - side: 'buy' or 'sell'

        """
        debugger.error(
            f"{type(self).__name__} does not support this broker method: `fetch_order_queue`. Returning an empty list."
        )
        return []

    # --------------- Methods for Trading --------------- #

    def order_stock_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Dict[str, Any]:
        """
        Places a limit order.

        :symbol:    symbol of stock
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A dictionary with the following keys and values:
            - order_id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_stock_limit`."
        )

    def order_crypto_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        in_force: str = "gtc",
        extended: bool = False,
    ) -> Dict[str, Any]:
        """
        Places a limit order.

        :symbol:    symbol of crypto
        :side:      'buy' or 'sell'
        :quantity:  quantity to buy or sell
        :limit_price:   limit price
        :in_force:  'gtc' by default
        :extended:  'False' by default

        :returns: A dictionary with the following keys and values:
            - order_id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_crypto_limit`."
        )

    def order_option_limit(
        self,
        side: str,
        symbol: str,
        quantity: float,
        limit_price: float,
        option_type: str,
        exp_date: dt.datetime,
        strike: float,
        in_force: str = "gtc",
    ) -> Dict[str, Any]:
        """
        Order an option.

        :side:      'buy' or 'sell'
        :symbol:    symbol of asset
        :in_force:
        :limit_price: limit price
        :quantity:  quantity to sell or buy
        :exp_date:  expiration date
        :strike:    strike price
        :option_type:      'call' or 'put'

        :returns: A dictionary with the following keys and values:
            - order_id: ID of order
            - symbol: symbol of asset
            Raises an exception if order fails.
        """
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `order_option_limit`."
        )

    def cancel_stock_order(self, order_id) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `cancel_stock_order`."
        )

    def cancel_crypto_order(self, order_id) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `cancel_crypto_order`."
        )

    def cancel_option_order(self, order_id) -> None:
        raise NotImplementedError(
            f"{type(self).__name__} does not support this broker method: `cancel_option_order`."
        )

    # --------------- Helper Methods --------------- #

    # Place any helper and prive methods here.

```