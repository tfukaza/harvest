### Main Loop

```python
trader.start()
streamer.start() # infinite loop
  streamer.main()
  trader.main()
  algo1.main()
  broker.fns()
  algo2.main()
  broker.fns()
```


## APIs

### API

An abstract streamer and broker.

`intervals`: List of intervals to aggregate OHLC data. 

* 1 minute
* 5 minutes
* 15 minutes
* 30 minutes
* 1 hour
* 1 day

`req_keys`: What keys are required in the provided secret file. For APIs that do not need credentials, this is not used and is initialized to be an empty list.

#### General Methods

`__init__(self, path: str = None) -> None`:

Creates an `API` instance.

* `self`(API): A reference to the instance.
* `path`(str): The path to a secret file holding API keys. 

`create_secret(self) -> Dict[str, str]`:

Warns the user's that this API does not need credentials.

* `self`(API): A reference to the instance.

`refresh_cred(self) -> None`:

Informs the user that credentials are being refreshed.

* `self`(API): A reference to the instance.

Returns a dictionary where the keys are the ones in the `req_keys` and the values are the API keys.

`setup(self, stats: Stats, account: Account, trader_main: Callable=None) -> None`:

Setups the API with data coming from the Trader and ultimately the user.

* `self`(API): A reference to the instance.
* `stats`(Stats):  Holds the timestamp, timezone, and watchlist.
* `account`(Account): Holds the user's cash, equity, positions, orders, etc.
* `trader_main`(Callable): reference to the trader's main function.

`start(self) -> None`:

Runs an infinite loop and calls the API's `main` function every `poll_interval`.

* `self`(API): A reference to the instance.

`main(self) -> None`:

Gets the OHLC data for the assets at the requested interval and passes it to the trader's `main` function.

* `self`(API): A reference to the instance.

`exit(self) -> None`:

Informs the user that the trader's `main` function has ended.

* `self`(API): A reference to the instance.

#### Streamer Methods

`get_current_time(self) -> dt.datetime`:

Returns the current time according to the API

* `self`(API): A reference to the instance.

Returns a `datetime` object with at least minute precision with a UTC timezone.

`fetch_price_history(self, symbol: str, interval: Interval, start: Union[str, dt.datetime] = None, end: Union[str, dt.datetime] = None) -> pd.DataFrame`

Get OHLC data.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.
* `interval`(Interval): The interval to aggregate the data.
* `start`(Union[str, dt.datetime]): The oldest point of time to get data from. If this is a string, then it must follow the ISO 8601 format.
* `end`(Union[str, dt.datetime]): The most recent point of time to get data from. If this is a string, then it must follow the ISO 8601 format.

Throws `NotImplementedError`.

`fetch_latest_price(self, symbol: str) -> float`:

Gets the most recent `close` value from OHLC data.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.

Returns a float.

`fetch_chain_info(self, symbol: str) -> Dict[str, Any]`:

Returns information about the symbol's options.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.

Throw `NotImplemenedError`.

`fetch_chain_data(self, symbol: str, date) -> pd.DataFrame`:

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.
* `date`(dt.datetime): The expiration data of the option.

Throws `NotImplementedError`.

`fetch_option_market_data(self, symbol: str) -> Dict[str, Any]`:

Fetches data for a particular option.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.

Throws `NotImplementedError`.

`fetch_market_hours(self, date: dt.date) -> Dict[str, Any]`:

Gets whether the market is open, the next time it opens, and the next time it closes.

* `self`(API): A reference to the instance.
* `date`(dt.date): The date for which the market's status is checked on.

Return a python dictionary.

#### Broker Methods

`fetch_stock_positions(self) -> List`:

Gets all current stock positions.

* `self`(API): A reference to the instance.

Returns an empty list.

`fetch_option_positions(self) -> List`:

Gets all current option positions.

* `self`(API): A reference to the instance.

Returns an empty list.

`fetch_crypto_positions(self) -> List`:

Gets all current crypto positions.

* `self`(API): A reference to the instance.

Returns an empty list.

`fetch_account(self) -> Dict[str, float]`:

Gets the user's account information.

* `self`(API): A reference to the instance.

Throws `NotImplementedError`.

`fetch_stock_order_status(self, id) -> Dict[str, Any]`:

Returns the stock order with the given `id`.

* `self`(API): A reference to the instance.
* `id`(Any): A unique identifier for the stock order.

Throws `NotImplemedtedError`.

`fetch_option_order_status(self, id) -> Dict[str, Any]`:

Returns the option order with the given `id`.

* `self`(API): A reference to the instance.
* `id`(Any): A unique identifier for the option order.

Throws `NotImplemedtedError`.

`fetch_crypto_order_status(self, id) -> Dict[str, Any]`:

Returns the crypto order with the given `id`.

* `self`(API): A reference to the instance.
* `id`(Any): A unique identifier for the crypto order.

Throws `NotImplemedtedError`.

`fetch_order_queue(self) -> List`:

Returns all current pending orders.

* `self`(API): A reference to the instance.

Returns an empty list.

#### Trading Methods

`order_stock_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]`:

Places a limit order for stocks.

* `self`(API): A reference to the instance.
* `side`(str): Either `BUY` or `SELL`.
* `symbol`(str): The asset's ticker.
* `quantity`(float): The amount of the asset you want to buy or sell.
* `limit_price`(float): The absolute max price to buy or the absolute min price to sell one quantity of the asset.
* `in_force`(str): IDK
* `extended`(bool): Whether to allow trading during extended market hours.

Throws `NotImplemedtedError`. 

`order_crypto_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]`:

Places a limit order for cryptos.

* `self`(API): A reference to the instance.
* `side`(str): Either `BUY` or `SELL`.
* `symbol`(str): The asset's ticker. Crypto assets should have an `@` prepended to them.
* `quantity`(float): The amount of the asset you want to buy or sell.
* `limit_price`(float): The absolute max price to buy or the absolute min price to sell one quantity of the asset.
* `in_force`(str): IDK
* `extended`(bool): Whether to allow trading during extended market hours.

Throws `NotImplemedtedError`. 

`order_stock_limit(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]`:

Places a limit order for options.

* `self`(API): A reference to the instance.
* `side`(str): Either `BUY` or `SELL`.
* `symbol`(str): The asset's ticker.
* `quantity`(float): The amount of the asset you want to buy or sell.
* `limit_price`(float): The absolute max price to buy or the absolute min price to sell one quantity of the asset.
* `in_force`(str): IDK
* `extended`(bool): Whether to allow trading during extended market hours.

Throws `NotImplemedtedError`. 

`cancel_stock_order(self, order_id) -> None`:

Cancels a stock order.

* `self`(API): A reference to the instance.
* `order_id`(Any): The id of the stock order.

Throws `NotImplemedtedError`. 

`cancel_stock_order(self, order_id) -> None`:

Cancels a crypto order.

* `self`(API): A reference to the instance.
* `order_id`(Any): The id of the crypto order.

Throws `NotImplemedtedError`. 

`cancel_stock_order(self, order_id) -> None`:

Cancels a option order.

* `self`(API): A reference to the instance.
* `order_id`(Any): The id of the option order.

Throws `NotImplemedtedError`. 

`buy(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]`:

Buys the asset with the given `symbol`.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker.
* `quantity`(float): The amount of the asset you want to buy or sell.
* `limit_price`(float): The absolute max price to buy one quantity of the asset.
* `in_force`(str): IDK
* `extended`(bool): Whether to allow trading during extended market hours.

Returns a python dictionary with the order id.

`sell(self, side: str, symbol: str, quantity: float, limit_price: float, in_force: str = "gtc", extended: bool = False) -> Dict[str, Any]`:

Sells the asset with the given `symbol`.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker.
* `quantity`(float): The amount of the asset you want to buy or sell.
* `limit_price`(float): The absolute min price to sell one quantity of the asset.
* `in_force`(str): IDK
* `extended`(bool): Whether to allow trading during extended market hours.

Returns a python dictionary with the order id.

`cancel(self, order_id) -> None`:

Cancels an order.

* `self`(API): A reference to the instance.
* `order_id`: The id of the order.

#### Helper Methods

`has_interval(self, interval: Interval) -> bool`:

Checks that the given `interval` is supported by the API.

* `self`(API): A reference to the instance.
* `order_id`: The id of the order.

Returns true if the interval is supported by the API and false otherwise.

`data_to_occ(self, symbol: str, date: dt.datetime, option_type: str, price: float) -> str`

Converts the given data into the OCC format.

* `self`(API): A reference to the instance.
* `symbol`(str): The asset's ticker.
* `date`(dt.datetime): The timestamp.
* `option_type`(str): The type of option.
* `price`(float): The price of one unit of the asset.

Returns a string representation of the OCC.

`occ_to_data(self, symbol: str) -> Tuple[str, dt.datetime, str, float]`:

* `self`(API): A reference to the instance.
* `symbol`(str): An OCC formatted string.

Returns the symbol, date, option_type, and price.

`current_timestamp(self) -> dt.datetime`:

Gets the current time.

* `self`(API): A reference to the instance.

Returns a python `datetime.datetime` object with the current time with minute precision and in the UTC timezone.

`_exception_handler(func: Callable) -> Callable`:

Wrapper on other functions so, if the error, will rerun the function two more times. Also prevents exceptions from stopping Harvest.

* `func`(Callable): The function to provide exception handling.

Returns a wrapped function.

`_run_once(func: Callable) -> Callable`:

Wrapper on other functions so that function will only run once.

* `func`(Callable): The function to ensure it runs only once.

Returns a wrapped function.

### Stream

An abstract child class of the `API` with handling for APIs with streaming services such as Websockets.

`intervals`: See parent class.

`req_keys`: See parent class.

#### General Methods

`__init__(self, path: str = None) -> None`:

Calls its parent method. Initializes a lock and queue.

* `self`(StreamAPI): A reference to the instance.
* `path`(str): The path to a secret file holding API keys. 

`start(self) -> None`:

Logs that the function has been called.

* `self`(StreamAPI): A reference to the instance.

`main(self, df_dict: Dict[str, Any]) -> None`:

Waits for data and when it gets all asset OHLC data, calls the trader `main` method.

* `self`(StreamAPI): A reference to the instance.
* `df_dict`(Dict[str, Any]): A dictionary where the keys are asset tickers and the values are `pd.DataFrames` with OHLC data.

`timeout(self) -> None`:

Waits one second for any missing OHLC data and if none is recieved populate the OHLC data with zeros.

* `self`(StreamAPI): A reference to the instance.

`flush(self) -> None`:

* `self`(StreamAPI): A reference to the instance.

For all assets that have no OHLC data, create a `pd.DataFrame` with all OHLC values set to zero and called the trader's `main`.

### Dummy Streamer
  
Real-time, seeded, fake stock generator with data going back 30 years from the point when the Harvest instance is started with minute precision. 

`intervals`:

* 1 minute
* 5 minutes
* 15 minutes
* 30 minutes
* 1 hour
* 1 day

`req_keys`: 

* None
  
public functions:

`__init__(self, current_time: Union[str, dt.datetime] = None, stock_market_times: bool = False, realistic_simulation: bool = True) -> None`

Creates a `DummyStreamer` instance.

* `self`(DummyStreamer): A reference to the instance.
* `current_time`(Union[str, dt.datetime]): The time you want the data from. Useful if you want to start at a fixed time no matter what the real time is.
* `stock_market_times`(bool): If true, only show results when the US stock market is open. If false, results will span 24/7 without gaps.
* `realistic_simulation`(bool): If true, the main loop will pause for the smallest interval that an asset is being updated on. If false, no pause will occur.

`setup(self, stats: Stats, account: Account, trader_main: Callable=None) -> None`

Called by the trader to setup watchlists.

* `self`(DummyStreamer): A reference to the instance.
* `stats`(Stats):  Holds the timestamp, timezone, and watchlist.
* `account`(Account): Holds the user's cash, equity, positions, orders, etc.
* `trader_main`(Callable): reference to the trader's main function.

`start(self) -> None`

Starts an infinite loop and calls `main` on the smallest interval in watchlist. Can simulate real intervals by waiting or ignore the interval and loop as fast as possible.

* `self`(DummyStreamer): A reference to the instance.

`main(self) -> None`

Advances the streamer's `current_time` by the smallest interval in the watchlist. Fetches the most recent OHLC data for the assets in the watchlists passes those values to the trader's `main` function.

* `self`(DummyStreamer): A reference to the instance.

`get_current_time(self) -> dt.datetime`

Return the streamer's `current_time`

* `self`(DummyStreamer): A reference to the instance.

  req_keys\*                            super: 
  

  dictionary create_secret\*            super: does nothing since no secret keys are needed.



  dataframe  fetch_price_history\*

  dictionary fetch_option_market_data\*


### Polygon Streamer

A streamer using Polygon to get market data. Uses the `requests` python package. 

`interval`: 

* 1 minute
* 5 minutes
* 1 hour
* 1 day intervals

`req_keys`: 

* `polygon_api_key`: Your polygon api key.

public functions:

`__init__(self, path: str = None, is_basic_account: bool = False) -> None`

Creates a `PolygonStreamer` instance.

* `self`(PolygonStreamer): A reference to the instance.
* `path`(str): The path to a yaml file with the polygon api key.
* `is_basic_account`(boolean): Whether the account is basic or not. [Here](https://polygon.io/pricing) are the difference between basic and pro accounts.


`setup(self, stats: Stats, account: Account, trader_main: Callable=None) -> None`

Called by the trader to setup watchlists.

* `self`(PolygonStreamer): A reference to the instance.
* `stats`(Stats):  Holds the timestamp, timezone, and watchlist.
* `account`(Account): Holds the user's cash, equity, positions, orders, etc.
* `trader_main`(Callable): reference to the trader's main function.

`exit(self) -> None`

Clears any cached information after the all the algorithms finish running.

* `self`(PolygonStreamer): A reference to the instance.

`main(self) -> None`

Get the most recent asset data from the given watchlist and pass it to the trader's `main` function.

* `self`(PolygonStreamer): A reference to the instance.


`fetch_price_history(self, symbol: str, interval: Interval, start: dt.datetime = None, end: dt.datetime = None) -> pd.DataFrame`

Get the asset OHLC data for the given symbol.

* `self`(PolygonStreamer): A reference to the instance.
* `symbol`(str): Either a stock symbol or a crypto symbol. For crypto symbols, prepend an `@` symbol.
* `interval`(str): An enum to indicate the unit and interval to aggergate data.
* `start`(Union[str,dt.datetime]): The earliest timestamp of data, inclusive.
* `end`(Union[str,dt.datetime]): The latest timestamp of data, inclusive.

Returns a pandas multi-index dataframe of OHLC data where the first index is the asset name and the second index contains `open`, `high`, `low`, `close`, `volume`. The index is a `pd.DatetimeIndex`. The dataframe is sorted with oldest timestamps at the top and the most recent timestamps at the bottom. 

`create_secret(self) -> Dict[str, str]`

Creates a dictionary with the `req_keys` for polygon.

* `self`(PolygonStreamer): A reference to the instance.

Returns a python dictionary containing the necessary credentials to use Polygon's api.

  
### Paper Broker

A fake broker with configurations to account for commission fees.

  intervals*: the intervals supported, these are 1 minute,  minutes, 15 minutes, 30 minutes, 1 hour, 1 day.
  req_keys* super: what keys are required in the provided secret file; since dummy_streamer needs no credentials, this is not used and is initialized to be an empty list.


### Alpaca

### Kraken

---

### RULES

* Private functions should begin with an underscore (\_) and be placed below public functions.
* Typing for everything.
* Dataframes that get asset data must return multi-index dataframes where the first index is the asset symbol, and the second index contains `open`, `high`, `low`, `close`, and `volume`. The index must be `pd.DatetimeIndex` object with a UTC timezone. The dataframe must be sorted in ascending order, where the oldest data is at the top and the most recent data is at the bottom.  
* The time source of truth should be the streamer's `get_current_time` function.
* Users should be able to enter ISO 8601 compliant string, or datetimes with or without timezones. If timezones are not provided, we should assume it is in their local timezones.
* All shown time should be in ISO 8601 format localized to the user's timezone. The timezone should not be displayed.


### TESTING PIPLINE

1. Preform linting tests with `black`.

```bash
python setup.py lint
```

2. Run unitests with `coverage`.

```bash
python setup.py test
```

3. Run GNAT for full testing.

```bash
python gnat.py config.yaml
```