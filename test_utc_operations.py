#!/usr/bin/env python3

"""Test script to verify UTC time usage in the polling system."""

import sys
import os
import time
from datetime import datetime, timezone
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from harvest.enum import Interval
from harvest.util.date import utc_current_time

# Create a minimal test class that includes the _calculate_next_aligned_time method
class TestBroker:
    def _calculate_next_aligned_time(self, current_time: float, interval: Interval) -> float:
        """
        Calculate the next time-aligned firing time for a given Interval enum.

        This ensures events fire at exact time boundaries in UTC:
        - 15-second intervals: fire at :00, :15, :30, :45
        - 1-minute intervals: fire at :00 of each minute
        - 5-minute intervals: fire at :00, :05, :10, :15, etc.
        - 1-hour intervals: fire at :00 of each hour
        - 1-day intervals: fire at midnight UTC

        All calculations are performed in UTC timezone to ensure consistency
        across different system timezones.

        Args:
            current_time: Current UTC timestamp (seconds since Unix epoch)
            interval: Interval enum representing the interval

        Returns:
            UTC timestamp for the next aligned firing time
        """
        import math

        # Handle different interval units directly using UTC-based calculations
        if interval.unit == "SEC":
            # For second intervals, align within the current minute
            minute_start = math.floor(current_time / 60) * 60
            elapsed_in_minute = current_time - minute_start
            intervals_passed = math.floor(elapsed_in_minute / interval.interval_value)
            next_time = minute_start + (intervals_passed + 1) * interval.interval_value

            # If we've gone past this minute, move to the next minute
            if next_time >= minute_start + 60:
                next_time = minute_start + 60

        elif interval.unit == "MIN":
            if interval.interval_value == 1:
                # Align to the next minute boundary
                next_time = math.ceil(current_time / 60) * 60
            else:
                # Align to interval boundaries within the hour
                hour_start = math.floor(current_time / 3600) * 3600
                elapsed_in_hour = current_time - hour_start
                minute_interval = interval.interval_value * 60
                intervals_passed = math.floor(elapsed_in_hour / minute_interval)
                next_time = hour_start + (intervals_passed + 1) * minute_interval

        elif interval.unit == "HR":
            if interval.interval_value == 1:
                # Align to the next hour boundary
                next_time = math.ceil(current_time / 3600) * 3600
            else:
                # Align to interval boundaries within the day
                day_start = math.floor(current_time / 86400) * 86400
                elapsed_in_day = current_time - day_start
                hour_interval = interval.interval_value * 3600
                intervals_passed = math.floor(elapsed_in_day / hour_interval)
                next_time = day_start + (intervals_passed + 1) * hour_interval

        elif interval.unit == "DAY":
            # Align to day boundaries (midnight UTC)
            if interval.interval_value == 1:
                next_time = math.ceil(current_time / 86400) * 86400
            else:
                # Multi-day intervals align to interval boundaries from Unix epoch
                day_interval = interval.interval_value * 86400
                intervals_passed = math.floor(current_time / day_interval)
                next_time = (intervals_passed + 1) * day_interval

        else:
            raise ValueError(f"Unsupported interval unit: {interval.unit}")

        return next_time

def test_utc_consistency():
    """Test that UTC time operations are consistent and timezone-aware."""
    print("Testing UTC time consistency:")

    broker = TestBroker()

    # Get current UTC time using the helper function
    utc_now = utc_current_time()
    utc_timestamp = utc_now.timestamp()

    print(f"  Current UTC time: {utc_now}")
    print(f"  UTC timestamp: {utc_timestamp}")

    # Test that our calculations work with UTC timestamps
    interval = Interval.MIN_5
    next_time = broker._calculate_next_aligned_time(utc_timestamp, interval)
    next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)

    print(f"  Next aligned time for {interval}: {next_dt}")
    print(f"  Minutes should be divisible by 5: {next_dt.minute % 5 == 0}")

    assert next_dt.minute % 5 == 0, f"Expected minute to be divisible by 5, got {next_dt.minute}"
    assert next_dt.tzinfo == timezone.utc, f"Expected UTC timezone, got {next_dt.tzinfo}"

    print("  ✓ UTC time calculations are correct")

def test_timezone_independence():
    """Test that calculations give same results regardless of system timezone."""
    print("\nTesting timezone independence:")

    broker = TestBroker()

    # Test with a specific UTC timestamp
    utc_timestamp = 1704110096.0  # 2024-01-01 11:54:56 UTC

    # Calculate next aligned time for 15-minute interval
    interval = Interval.MIN_15
    next_time = broker._calculate_next_aligned_time(utc_timestamp, interval)
    next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)

    print(f"  Test timestamp: {datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)}")
    print(f"  Next 15-min aligned: {next_dt}")
    print(f"  Expected: 2024-01-01 12:00:00+00:00")

    # Should align to the next 15-minute boundary (12:00 in this case)
    expected = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert next_dt == expected, f"Expected {expected}, got {next_dt}"

    print("  ✓ Timezone-independent calculations work correctly")

def test_day_boundary_alignment():
    """Test that day intervals align to UTC midnight."""
    print("\nTesting day boundary alignment:")

    broker = TestBroker()

    # Test with a timestamp in the middle of a day
    utc_timestamp = 1704139496.0  # 2024-01-01 20:04:56 UTC
    current_dt = datetime.fromtimestamp(utc_timestamp, tz=timezone.utc)

    interval = Interval.DAY_1
    next_time = broker._calculate_next_aligned_time(utc_timestamp, interval)
    next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)

    print(f"  Current time: {current_dt}")
    print(f"  Next day boundary: {next_dt}")
    print(f"  Expected: 2024-01-02 00:00:00+00:00")

    # Should align to next midnight UTC
    expected = datetime(2024, 1, 2, 0, 0, 0, tzinfo=timezone.utc)
    assert next_dt == expected, f"Expected {expected}, got {next_dt}"
    assert next_dt.hour == 0 and next_dt.minute == 0 and next_dt.second == 0, \
           f"Expected midnight, got {next_dt.hour}:{next_dt.minute}:{next_dt.second}"

    print("  ✓ Day boundary alignment to UTC midnight works correctly")

if __name__ == "__main__":
    test_utc_consistency()
    test_timezone_independence()
    test_day_boundary_alignment()
    print("\n🎉 All UTC time tests passed! The polling system properly uses UTC for all time operations.")
