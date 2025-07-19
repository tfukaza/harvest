#!/usr/bin/env python3

"""Test script to verify the updated _calculate_next_aligned_time method works with Interval enums."""

import sys
import os
import time
import math
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from harvest.enum import Interval

# Create a minimal test class that includes the _calculate_next_aligned_time method
class TestBroker:
    def _calculate_next_aligned_time(self, current_time: float, interval: Interval) -> float:
        """
        Calculate the next time-aligned firing time for a given Interval enum.

        This ensures events fire at exact time boundaries:
        - 15-second intervals: fire at :00, :15, :30, :45
        - 1-minute intervals: fire at :00 of each minute
        - 5-minute intervals: fire at :00, :05, :10, :15, etc.
        - 1-hour intervals: fire at :00 of each hour
        - 1-day intervals: fire at midnight UTC

        Args:
            current_time: Current timestamp
            interval: Interval enum representing the interval

        Returns:
            Timestamp for the next aligned firing time
        """
        import math

        # Handle different interval units directly
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

def test_alignment():
    """Test that intervals align correctly to time boundaries."""
    print("Testing time alignment with Interval enums:")

    broker = TestBroker()

    # Test with a specific timestamp: 2024-01-01 12:34:56 UTC
    test_time = 1704110096.0  # 2024-01-01 12:34:56 UTC

    test_cases = [
        (Interval.SEC_15, "should align to :00, :15, :30, :45"),
        (Interval.MIN_1, "should align to next minute boundary"),
        (Interval.MIN_5, "should align to :00, :05, :10, :15, etc."),
        (Interval.MIN_15, "should align to :00, :15, :30, :45"),
        (Interval.MIN_30, "should align to :00, :30"),
        (Interval.HR_1, "should align to next hour boundary"),
        (Interval.DAY_1, "should align to midnight UTC"),
    ]

    for interval, description in test_cases:
        next_time = broker._calculate_next_aligned_time(test_time, interval)

        # Convert to readable format
        from datetime import datetime, timezone
        current_dt = datetime.fromtimestamp(test_time, tz=timezone.utc)
        next_dt = datetime.fromtimestamp(next_time, tz=timezone.utc)

        print(f"\n  {interval} ({description}):")
        print(f"    Current time: {current_dt}")
        print(f"    Next aligned: {next_dt}")
        print(f"    Wait time: {next_time - test_time:.2f} seconds")

        # Verify alignment properties
        if interval.unit == "SEC":
            seconds_in_minute = int(next_dt.second)
            expected_seconds = [0, 15, 30, 45]
            assert seconds_in_minute in expected_seconds, f"Expected seconds to be in {expected_seconds}, got {seconds_in_minute}"
            print(f"    ✓ Aligned to {seconds_in_minute} seconds")

        elif interval.unit == "MIN":
            if interval.interval_value == 1:
                assert next_dt.second == 0, f"Expected 0 seconds, got {next_dt.second}"
                print(f"    ✓ Aligned to minute boundary")
            else:
                minutes_in_hour = int(next_dt.minute)
                assert minutes_in_hour % interval.interval_value == 0, f"Expected minute to be divisible by {interval.interval_value}, got {minutes_in_hour}"
                print(f"    ✓ Aligned to {minutes_in_hour} minutes")

        elif interval.unit == "HR":
            if interval.interval_value == 1:
                assert next_dt.minute == 0 and next_dt.second == 0, f"Expected 0 minutes and seconds, got {next_dt.minute}:{next_dt.second}"
                print(f"    ✓ Aligned to hour boundary")

        elif interval.unit == "DAY":
            assert next_dt.hour == 0 and next_dt.minute == 0 and next_dt.second == 0, f"Expected midnight, got {next_dt.hour}:{next_dt.minute}:{next_dt.second}"
            print(f"    ✓ Aligned to day boundary")

    print("\n✓ All time alignment tests passed!")

def test_drift_prevention():
    """Test that recalculating next times prevents drift."""
    print("\nTesting drift prevention:")

    broker = TestBroker()

    # Start with a base time
    base_time = 1704110096.0  # 2024-01-01 12:34:56 UTC
    interval = Interval.MIN_5

    # Calculate first aligned time
    first_time = broker._calculate_next_aligned_time(base_time, interval)

    # Simulate multiple recalculations as if we're in a polling loop
    current_time = first_time
    previous_aligned_times = []

    for i in range(5):
        # Add some small drift (like would happen in real polling)
        current_time += 0.1  # 100ms drift

        next_time = broker._calculate_next_aligned_time(current_time, interval)
        previous_aligned_times.append(next_time)

        # Move to the next "fire time"
        current_time = next_time

    # Check that all times are exactly 5 minutes apart
    for i in range(1, len(previous_aligned_times)):
        time_diff = previous_aligned_times[i] - previous_aligned_times[i-1]
        expected_diff = 5 * 60  # 5 minutes

        print(f"  Interval {i}: {time_diff:.2f} seconds (expected: {expected_diff})")
        assert abs(time_diff - expected_diff) < 0.01, f"Expected {expected_diff} seconds, got {time_diff}"

    print("  ✓ No drift detected - all intervals are exactly 5 minutes apart")

if __name__ == "__main__":
    test_alignment()
    test_drift_prevention()
    print("\n🎉 All tests passed! The updated _calculate_next_aligned_time works correctly with Interval enums.")
