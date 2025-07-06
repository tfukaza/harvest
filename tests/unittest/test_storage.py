import datetime as dt

from polars.testing import assert_frame_equal

from harvest.definitions import OrderEvent, OrderSide, TimeDelta, TimeSpan, Transaction
from harvest.enum import Interval
from harvest.storage._base import Storage
from harvest.util.helper import generate_ticker_frame


def test_storage_init():
    """
    If the base Storage class is initialized with no arguments,
    it should create an in-memory database.
    """
    storage = Storage()

    assert storage is not None


def test_storage_price_history():
    """
    Storage should be able to save and retrieve price history.
    """
    storage = Storage()

    original_df = generate_ticker_frame("A", Interval.MIN_1, 1)
    storage.insert_price_history(original_df)
    loaded_df = storage.get_price_history("A", Interval.MIN_1)

    # Get the first candle of each symbol
    original_first_candle = original_df[0]
    loaded_first_candle = loaded_df[0]

    assert original_first_candle == loaded_first_candle


def test_storage_price_history_insert_multiple_times():
    """
    Storage should be able to save price history multiple times.
    The data should be appended to the existing data, and overlapping data should be overwritten.
    """
    storage = Storage()

    df_0 = generate_ticker_frame("A", Interval.MIN_1, 10, start=dt.datetime(1970, 1, 1, 0, 0))
    storage.insert_price_history(df_0)
    df_1 = generate_ticker_frame("A", Interval.MIN_1, 10, start=dt.datetime(1970, 1, 1, 0, 5))
    storage.insert_price_history(df_1)
    loaded_df = storage.get_price_history("A", Interval.MIN_1)

    assert df_0[0] == loaded_df[0]
    assert df_1[0] == loaded_df[5]


def test_storage_price_history_insert_multiple_times_with_limit():
    """
    Storage should be able to limit the number of data points stored for price history.
    """
    storage = Storage(price_storage_limit={Interval.MIN_1: TimeDelta(TimeSpan.MINUTE, 15)})

    df_0 = generate_ticker_frame("A", Interval.MIN_1, 10)
    storage.insert_price_history(df_0)
    df_1 = generate_ticker_frame("A", Interval.MIN_1, 10, start=dt.datetime(1970, 1, 1, 0, 10))
    storage.insert_price_history(df_1)
    loaded_df = storage.get_price_history("A", Interval.MIN_1)

    # length of loaded_df should be 15
    assert len(loaded_df.df) == 15

    # first candle of loaded_df should be the fifth candle of df_0
    assert loaded_df[0] == df_0[5]


def test_store_price_multiple_symbol_with_limit():
    """
    Storage should be able to store price history for multiple symbols with a limit.
    """
    storage = Storage(price_storage_limit={Interval.MIN_1: TimeDelta(TimeSpan.MINUTE, 15)})
    df_a_0 = generate_ticker_frame("A", Interval.MIN_1, 10)
    df_b_0 = generate_ticker_frame("B", Interval.MIN_1, 10)
    storage.insert_price_history(df_a_0)
    storage.insert_price_history(df_b_0)

    df_a_1 = generate_ticker_frame("A", Interval.MIN_1, 10, start=dt.datetime(1970, 1, 1, 0, 10))
    df_b_1 = generate_ticker_frame(
        "B", Interval.MIN_1, 10, start=dt.datetime(1970, 1, 1, 0, 20)
    )  # Note the different starting date
    storage.insert_price_history(df_a_1)
    storage.insert_price_history(df_b_1)

    loaded_df_a = storage.get_price_history("A", Interval.MIN_1)
    loaded_df_b = storage.get_price_history("B", Interval.MIN_1)

    assert len(loaded_df_a.df) == 15
    assert len(loaded_df_b.df) == 10
    assert loaded_df_a[0] == df_a_0[5]
    assert loaded_df_b[0] == df_b_1[0]


def test_store_price_history_different_intervals():
    """
    Storage should be able to store data with different intervals.
    """
    storage = Storage()
    df_0 = generate_ticker_frame("A", Interval.MIN_1, 100)
    df_1 = generate_ticker_frame("A", Interval.MIN_5, 100)
    storage.insert_price_history(df_0)
    storage.insert_price_history(df_1)
    loaded_df = storage.get_price_history("A", Interval.MIN_1)
    loaded_df_5 = storage.get_price_history("A", Interval.MIN_5)

    assert len(loaded_df.df) == 100
    assert len(loaded_df_5.df) == 100
    assert_frame_equal(loaded_df.df, df_0.df)
    assert_frame_equal(loaded_df_5.df, df_1.df)


def test_store_price_overlapping_time_range():
    """
    Storage should be able to store price history with overlapping time range.
    """
    storage = Storage()
    df_0 = generate_ticker_frame("A", Interval.MIN_1, 100, start=dt.datetime(1970, 1, 1, 0, 0))
    df_1 = generate_ticker_frame("A", Interval.MIN_1, 100, start=dt.datetime(1970, 1, 1, 0, 50))
    storage.insert_price_history(df_0)
    storage.insert_price_history(df_1)
    loaded_df = storage.get_price_history("A", Interval.MIN_1)

    assert len(loaded_df.df) == 150
    assert loaded_df[50] == df_1[0]


def test_store_price_history_specific_time_range():
    """
    Storage should be able to store price history with a specific time range.
    """
    storage = Storage()
    df_0 = generate_ticker_frame("A", Interval.MIN_1, 100)
    storage.insert_price_history(df_0)
    loaded_df = storage.get_price_history(
        "A", Interval.MIN_1, start=dt.datetime(1970, 1, 1, 0, 10), end=dt.datetime(1970, 1, 1, 0, 20)
    )

    assert len(loaded_df.df) == 11
    assert loaded_df[0] == df_0[10]


def test_store_transaction():
    """
    Storage should be able to store transaction history.
    """
    storage = Storage()
    buy_transaction = Transaction(
        dt.datetime(1970, 1, 1, 0, 10), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name"
    )
    storage.insert_transaction(buy_transaction)
    loaded_df = storage.get_transaction_history("A", OrderSide.BUY, "algorithm_name")

    assert len(loaded_df.df) == 1
    assert loaded_df[0] == buy_transaction


def test_store_transaction_multiple_times():
    """
    Storage should be able to store transaction history multiple times.
    The data should be appended to the existing data.
    """
    storage = Storage()
    buy_transaction = Transaction(
        dt.datetime(1970, 1, 1, 0, 10), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name"
    )
    storage.insert_transaction(buy_transaction)
    buy_transaction_2 = Transaction(
        dt.datetime(1970, 1, 1, 0, 10), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name"
    )
    storage.insert_transaction(buy_transaction_2)
    loaded_df = storage.get_transaction_history("A", OrderSide.BUY, "algorithm_name")

    assert len(loaded_df.df) == 2
    assert loaded_df[0] == buy_transaction
    assert loaded_df[1] == buy_transaction_2


def test_store_transaction_with_limit():
    """
    Storage should be able to limit the number of data points stored for transaction history.
    """
    storage = Storage(transaction_storage_limit=TimeDelta(TimeSpan.MINUTE, 15))
    buy_list = [
        Transaction(dt.datetime(1970, 1, 1, 0, 10 + i), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name")
        for i in range(20)
    ]
    for buy_transaction in buy_list:
        storage.insert_transaction(buy_transaction)
    loaded_df = storage.get_transaction_history("A", OrderSide.BUY, "algorithm_name")

    assert len(loaded_df.df) == 15
    assert loaded_df[0] == buy_list[5]


def _generate_transaction_list(
    start_time: dt.datetime,
    symbol: str,
    side: OrderSide,
    quantity: int,
    price: float,
    event: OrderEvent,
    algorithm_name: str,
    count: int,
) -> list[Transaction]:
    return [
        Transaction(
            start_time + dt.timedelta(minutes=i),
            symbol,
            side,
            quantity,
            price,
            event,
            algorithm_name,
        )
        for i in range(count)
    ]


def test_store_transaction_with_limit_multiple_symbols():
    """
    Storage should be able to limit the number of data points stored for transaction history.
    """
    storage = Storage(transaction_storage_limit=TimeDelta(TimeSpan.MINUTE, 15))

    buy_list_a_0 = _generate_transaction_list(
        dt.datetime(1970, 1, 1, 0, 0), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name", 20
    )
    for buy_transaction in buy_list_a_0:
        storage.insert_transaction(buy_transaction)
    buy_list_b_0 = _generate_transaction_list(
        dt.datetime(1970, 1, 1, 0, 0), "B", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name", 20
    )
    for buy_transaction in buy_list_b_0:
        storage.insert_transaction(buy_transaction)
    loaded_df_a_0 = storage.get_transaction_history("A", OrderSide.BUY, "algorithm_name")
    loaded_df_b_0 = storage.get_transaction_history("B", OrderSide.BUY, "algorithm_name")

    buy_list_a_1 = _generate_transaction_list(
        dt.datetime(1970, 1, 1, 0, 40), "A", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name", 10
    )
    for buy_transaction in buy_list_a_1:
        storage.insert_transaction(buy_transaction)
    buy_list_b_1 = _generate_transaction_list(
        dt.datetime(1970, 1, 1, 0, 20), "B", OrderSide.BUY, 10, 100, OrderEvent.ORDER, "algorithm_name", 10
    )
    for buy_transaction in buy_list_b_1:
        storage.insert_transaction(buy_transaction)

    loaded_df_b_1 = storage.get_transaction_history("B", OrderSide.BUY, "algorithm_name")
    loaded_df_a_1 = storage.get_transaction_history("A", OrderSide.BUY, "algorithm_name")

    assert len(loaded_df_a_0.df) == 15
    assert len(loaded_df_b_0.df) == 15
    assert len(loaded_df_a_1.df) == 10
    assert len(loaded_df_b_1.df) == 15
    assert loaded_df_a_0[0] == buy_list_a_0[5]
    assert loaded_df_b_0[0] == buy_list_b_0[5]
    assert loaded_df_a_1[0] == buy_list_a_1[0]
    assert loaded_df_b_1[5] == buy_list_b_1[0]


# def test_store_overlap2(storage):
#     data = gen_data("A", 100)
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:])
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[:75])
#     loaded_data = storage.load("A", Interval.MIN_1)

#     assert not pd.isnull(data.iloc[0]["A"]["low"])
#     assert not pd.isnull(loaded_data.iloc[0]["A"]["low"])
#     assert_frame_equal(loaded_data, data)


# def test_store_within(storage):
#     data = gen_data("A", 100)
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:75])
#     storage.store("A", Interval.MIN_1, data.copy(True))
#     loaded_data = storage.load("A", Interval.MIN_1)

#     assert not pd.isnull(data.iloc[0]["A"]["low"])
#     assert not pd.isnull(loaded_data.iloc[0]["A"]["low"])
#     assert_frame_equal(loaded_data, data)


# def test_store_over(storage):
#     data = gen_data("A", 100)
#     storage.store("A", Interval.MIN_1, data.copy(True))
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[25:75])
#     loaded_data = storage.load("A", Interval.MIN_1)

#     assert not pd.isnull(data.iloc[0]["A"]["low"])
#     assert not pd.isnull(loaded_data.iloc[0]["A"]["low"])
#     assert_frame_equal(loaded_data, data)


# def test_load_no_interval(storage):
#     data = gen_data("A", 50)
#     storage.store("A", Interval.MIN_1, data.copy(True))
#     loaded_data = storage.load("A")

#     assert_frame_equal(loaded_data, data)


# def test_store_gap(storage):
#     data = gen_data("A", 100)
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[:25])
#     storage.store("A", Interval.MIN_1, data.copy(True).iloc[75:])
#     loaded_data_1 = storage.load("A", Interval.MIN_1)

#     assert not pd.isnull(data.iloc[0]["A"]["low"])
#     assert not pd.isnull(loaded_data_1.iloc[0]["A"]["low"])
#     loaded_data_2 = pd.concat([data.iloc[:25], data.iloc[75:]])
#     assert_frame_equal(loaded_data_1, loaded_data_2)


# @pytest.mark.skip(reason="Test not implemented yet")
# def test_agg_load():
#     storage = Storage()
#     data = gen_data("A", 100)
#     storage.store("A", Interval.MIN_1, data.copy(True))
#     loaded_data = storage.load("A", Interval.MIN_1)

#     assert not pd.isnull(data.iloc[0]["A"]["low"])
#     assert not pd.isnull(loaded_data.iloc[0]["A"]["low"])
#     assert loaded_data.shape == (20, 5)
