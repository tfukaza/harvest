#!/usr/bin/env python3

"""Test script to verify the interval enum usage in polling system."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from harvest.enum import Interval

def test_interval_enum_properties():
    """Test that Interval enum has the expected properties."""
    print("Testing Interval enum properties:")

    test_cases = [
        (Interval.SEC_15, "SEC", 15),
        (Interval.MIN_1, "MIN", 1),
        (Interval.MIN_5, "MIN", 5),
        (Interval.MIN_15, "MIN", 15),
        (Interval.MIN_30, "MIN", 30),
        (Interval.HR_1, "HR", 1),
        (Interval.DAY_1, "DAY", 1),
    ]

    for interval, expected_unit, expected_value in test_cases:
        print(f"  {interval}:")
        print(f"    unit: {interval.unit} (expected: {expected_unit})")
        print(f"    interval_value: {interval.interval_value} (expected: {expected_value})")
        print(f"    enum value: {interval.value}")

        assert str(interval.unit) == expected_unit, f"Expected unit {expected_unit}, got {interval.unit}"
        assert interval.interval_value == expected_value, f"Expected value {expected_value}, got {interval.interval_value}"

        print(f"    ✓ {interval} properties are correct")

    print("\n✓ All interval enum properties are correct!")

def test_interval_conversion():
    """Test that we can extract seconds from the enum properties."""
    print("\nTesting interval conversion using enum properties:")

    test_cases = [
        (Interval.SEC_15, 15.0),
        (Interval.MIN_1, 60.0),
        (Interval.MIN_5, 300.0),
        (Interval.MIN_15, 900.0),
        (Interval.MIN_30, 1800.0),
        (Interval.HR_1, 3600.0),
        (Interval.DAY_1, 86400.0),
    ]

    for interval, expected_seconds in test_cases:
        # Manual conversion using enum properties
        if interval.unit == "SEC":
            seconds = float(interval.interval_value)
        elif interval.unit == "MIN":
            seconds = float(interval.interval_value * 60)
        elif interval.unit == "HR":
            seconds = float(interval.interval_value * 60 * 60)
        elif interval.unit == "DAY":
            seconds = float(interval.interval_value * 60 * 60 * 24)
        else:
            raise ValueError(f"Unknown unit: {interval.unit}")

        print(f"  {interval} -> {seconds} seconds (expected: {expected_seconds})")
        assert seconds == expected_seconds, f"Expected {expected_seconds}, got {seconds}"

    print("\n✓ All interval conversions work correctly using enum properties!")

if __name__ == "__main__":
    test_interval_enum_properties()
    test_interval_conversion()
    print("\n🎉 All tests passed! The polling system can now use Interval enums directly.")
