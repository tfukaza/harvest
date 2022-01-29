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
  
### Dummy Streamer
  
Real-time, seeded, fake stock generator with data going back 30 years from the point when the Harvest instance is started with minute precision. 

  intervals\*: the intervals supported, these are 1 minute,  minutes, 15 minutes, 30 minutes, 1 hour, 1 day.

  req_keys\*                            super: what keys are required in the provided secret file; since dummy_streamer needs no credentials, this is not used and is initialized to be an empty list.
  
  void       init\*

  dictionary create_secret\*            super: does nothing since no secret keys are needed.

  void       setup\*                    super: 

  void       start\*                    super: tuns an infinite loop, calling main on interval.

  void       main\*: gets the asset data the user wants and calls the trader's main function.

  datetime   get_current_time\*

  dataframe  fetch_price_history\*

  dictionary fetch_option_market_data\*


### Polygon Streamer

A streamer using Polygon to get market data. Uses the `polygon-api-client` python package. 

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