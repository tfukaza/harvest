#!/usr/bin/env python3
"""
Test script to verify MockBroker performance improvements.
"""
import time
import datetime as dt
from harvest.broker.mock import MockBroker
from harvest.enum import Interval

def test_mock_broker_no_sleep():
    """Test that MockBroker doesn't sleep when realistic_simulation=False"""
    print("Testing MockBroker with realistic_simulation=False...")

    # Create a MockBroker with fast simulation
    broker = MockBroker(
        realistic_simulation=False,
        current_time=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    )

    # Set max ticks to prevent infinite loop
    broker.set_max_ticks(3)

    # Track start time
    start_time = time.time()

    # Start the broker (should not sleep)
    broker.start({Interval.MIN_1: ["AAPL"]})

    # Check elapsed time
    elapsed = time.time() - start_time
    print(f"Elapsed time: {elapsed:.3f} seconds")

    # Should be very fast (< 0.1 seconds)
    assert elapsed < 0.1, f"Expected < 0.1s, got {elapsed:.3f}s"

    # Check that ticks were executed
    assert broker.get_tick_count() == 3, f"Expected 3 ticks, got {broker.get_tick_count()}"

    print("✓ Fast simulation test passed")

def test_mock_broker_with_mock_sleep():
    """Test that MockBroker uses injectable sleep function"""
    print("Testing MockBroker with mock sleep function...")

    sleep_calls = []

    def mock_sleep(seconds):
        sleep_calls.append(seconds)

    # Create a MockBroker with mock sleep function
    broker = MockBroker(
        realistic_simulation=True,
        current_time=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc),
        sleep_function=mock_sleep
    )

    # Set max ticks to prevent infinite loop
    broker.set_max_ticks(2)

    # Start the broker
    broker.start({Interval.MIN_1: ["AAPL"]})

    # Check that sleep was called
    assert len(sleep_calls) == 2, f"Expected 2 sleep calls, got {len(sleep_calls)}"
    assert sleep_calls[0] == 60, f"Expected 60 seconds sleep, got {sleep_calls[0]}"

    print("✓ Mock sleep test passed")

def test_price_history_performance():
    """Test that price history generation is efficient"""
    print("Testing price history generation performance...")

    broker = MockBroker(
        realistic_simulation=False,
        current_time=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    )

    # Test with a reasonable amount of data
    start_time = time.time()

    # Generate 1000 candles - should be fast
    frame = broker.fetch_price_history(
        "AAPL",
        Interval.MIN_1,
        dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc),
        dt.datetime(2023, 1, 2, tzinfo=dt.timezone.utc)
    )

    elapsed = time.time() - start_time
    print(f"Generated {len(frame.df)} candles in {elapsed:.3f} seconds")

    # Should be reasonable performance
    assert elapsed < 1.0, f"Expected < 1s, got {elapsed:.3f}s"
    assert len(frame.df) > 0, "Should have generated some data"

    print("✓ Price history performance test passed")

def test_large_data_limit():
    """Test that large data requests are limited"""
    print("Testing large data size limits...")

    broker = MockBroker(
        realistic_simulation=False,
        current_time=dt.datetime(2023, 1, 1, tzinfo=dt.timezone.utc)
    )

    try:
        # This should raise an error due to size limit
        broker.generate_random_data("AAPL", dt.datetime(2023, 1, 1), 2000000)
        assert False, "Should have raised ValueError for large data size"
    except ValueError as e:
        print(f"✓ Size limit correctly enforced: {e}")

    print("✓ Large data limit test passed")

def main():
    """Run all performance tests"""
    print("Running MockBroker performance tests...")

    test_mock_broker_no_sleep()
    test_mock_broker_with_mock_sleep()
    test_price_history_performance()
    test_large_data_limit()

    print("\n✅ All performance tests passed!")

if __name__ == "__main__":
    main()
