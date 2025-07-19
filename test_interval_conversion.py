#!/usr/bin/env python3

"""Test script to verify the interval conversion functionality."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '.'))

from harvest.broker._base import Broker
from harvest.enum import Interval

# Create a test broker class that implements the abstract methods
class TestBroker(Broker):
    def __init__(self):
        super().__init__()
        self.interval_list = [Interval.SEC_15, Interval.MIN_1, Interval.MIN_5, Interval.MIN_15, Interval.MIN_30, Interval.HR_1, Interval.DAY_1]
        self.exchange = "TEST"
        self.req_keys = []

    def create_secret(self):
        return {}

    def refresh_cred(self):
        pass

    def get_current_time(self):
        import datetime as dt
        return dt.datetime.now(dt.timezone.utc)

    def fetch_price_history(self, symbol, interval, start=None, end=None):
        pass

    def fetch_latest_price(self, symbol, interval):
        pass

    def fetch_chain_info(self, symbol):
        pass

    def fetch_chain_data(self, symbol, date):
        pass

    def fetch_option_market_data(self, symbol):
        pass

    def fetch_market_hours(self, date):
        pass

    def fetch_stock_positions(self):
        pass

    def fetch_option_positions(self):
        pass

    def fetch_crypto_positions(self):
        pass

    def fetch_account(self):
        pass

    def fetch_stock_order_status(self, id):
        pass

    def fetch_option_order_status(self, id):
        pass

    def fetch_crypto_order_status(self, id):
        pass

    def fetch_order_queue(self):
        pass

    def order_stock_limit(self, side, symbol, quantity, limit_price, in_force="gtc", extended=False):
        pass

    def order_crypto_limit(self, side, symbol, quantity, limit_price, in_force="gtc", extended=False):
        pass

    def order_option_limit(self, side, symbol, quantity, limit_price, option_type, exp_date, strike, in_force="gtc"):
        pass

    def cancel_stock_order(self, order_id):
        pass

    def cancel_crypto_order(self, order_id):
        pass

    def cancel_option_order(self, order_id):
        pass

def test_interval_conversion():
    """Test the interval to seconds conversion."""
    broker = TestBroker()

    # Test different intervals
    test_cases = [
        (Interval.SEC_15, 15.0),
        (Interval.MIN_1, 60.0),
        (Interval.MIN_5, 300.0),
        (Interval.MIN_15, 900.0),
        (Interval.MIN_30, 1800.0),
        (Interval.HR_1, 3600.0),
        (Interval.DAY_1, 86400.0),
    ]

    print("Testing interval to seconds conversion:")
    for interval, expected_seconds in test_cases:
        result = broker._interval_to_seconds(interval)
        print(f"  {interval} -> {result} seconds (expected: {expected_seconds})")
        assert result == expected_seconds, f"Expected {expected_seconds}, got {result}"

    print("✓ All interval conversion tests passed!")

if __name__ == "__main__":
    test_interval_conversion()
