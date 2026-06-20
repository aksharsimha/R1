"""
Unit tests for nse_live.py — the live-price resolution layer.

Run with:
    python -m unittest tests.test_nse_live -v
    # or, from the project root:
    python -m pytest tests/test_nse_live.py

These tests use mocks and never hit the network.
"""

import os
import sys
import time
import unittest
from datetime import date
from unittest import mock

# Make the project root importable when run directly
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import nse_live


class TestYahooToNSE(unittest.TestCase):
    def test_strips_ns_suffix(self):
        self.assertEqual(nse_live._yahoo_to_nse("TATASTEEL.NS"), "TATASTEEL")

    def test_strips_bo_suffix(self):
        self.assertEqual(nse_live._yahoo_to_nse("RECLTD.BO"), "RECLTD")

    def test_plain_symbol_unchanged(self):
        self.assertEqual(nse_live._yahoo_to_nse("IRCTC"), "IRCTC")

    def test_index_returns_empty(self):
        self.assertEqual(nse_live._yahoo_to_nse("^NSEI"), "")


class TestHolidayDetection(unittest.TestCase):
    def test_known_holiday(self):
        self.assertTrue(nse_live.is_nse_holiday(date(2026, 1, 26)))  # Republic Day

    def test_regular_weekday_not_holiday(self):
        self.assertFalse(nse_live.is_nse_holiday(date(2026, 6, 23)))  # a Tuesday

    def test_unknown_year_degrades_gracefully(self):
        # Year not in table → False, never crashes
        self.assertFalse(nse_live.is_nse_holiday(date(1999, 1, 1)))


class TestCircuitBreaker(unittest.TestCase):
    def test_allows_until_threshold(self):
        cb = nse_live._CircuitBreaker(threshold=3, cooldown=60)
        self.assertTrue(cb.allow())
        cb.record_failure()
        cb.record_failure()
        self.assertTrue(cb.allow())  # 2 failures < 3
        cb.record_failure()
        self.assertFalse(cb.allow())  # 3 failures → open

    def test_success_resets(self):
        cb = nse_live._CircuitBreaker(threshold=2, cooldown=60)
        cb.record_failure()
        cb.record_failure()
        self.assertTrue(cb.is_open)
        cb.record_success()
        self.assertFalse(cb.is_open)
        self.assertTrue(cb.allow())

    def test_half_open_after_cooldown(self):
        cb = nse_live._CircuitBreaker(threshold=1, cooldown=0)  # instant cooldown
        cb.record_failure()
        self.assertTrue(cb.is_open)
        # cooldown=0 means the next allow() should let a trial through
        self.assertTrue(cb.allow())


class TestPersistentStore(unittest.TestCase):
    def setUp(self):
        self.path = os.path.join(os.path.dirname(__file__), "_test_price_cache.json")
        if os.path.exists(self.path):
            os.remove(self.path)

    def tearDown(self):
        if os.path.exists(self.path):
            os.remove(self.path)

    def test_set_and_get(self):
        store = nse_live._PersistentPriceStore(path=self.path, max_age=3600)
        store.set("TATASTEEL", 142.5)
        self.assertEqual(store.get("TATASTEEL"), 142.5)

    def test_survives_reload(self):
        store = nse_live._PersistentPriceStore(path=self.path, max_age=3600)
        store.set("IRCTC", 780.0)
        store2 = nse_live._PersistentPriceStore(path=self.path, max_age=3600)
        self.assertEqual(store2.get("IRCTC"), 780.0)

    def test_expiry(self):
        store = nse_live._PersistentPriceStore(path=self.path, max_age=1)
        store.set("BEL", 400.0)
        with mock.patch("nse_live.time.time", return_value=time.time() + 10):
            self.assertIsNone(store.get("BEL"))

    def test_missing_symbol(self):
        store = nse_live._PersistentPriceStore(path=self.path, max_age=3600)
        self.assertIsNone(store.get("NOPE"))


class TestGetLivePriceFallbackChain(unittest.TestCase):
    """The core resolution order: NSE → yfinance → cached → historical."""

    def test_nse_success(self):
        with mock.patch.object(nse_live, "get_nse_live_price", return_value=100.0):
            price, src = nse_live.get_live_price("TATASTEEL.NS")
        self.assertEqual((price, src), (100.0, "nse_live"))

    def test_falls_back_to_yfinance(self):
        with mock.patch.object(nse_live, "get_nse_live_price", return_value=None), \
             mock.patch.object(nse_live, "_yf_fast_price", return_value=99.0):
            price, src = nse_live.get_live_price("TATASTEEL.NS")
        self.assertEqual((price, src), (99.0, "yfinance"))

    def test_falls_back_to_cached(self):
        nse_live._persistent_store.set("TATASTEEL", 88.0)
        with mock.patch.object(nse_live, "get_nse_live_price", return_value=None), \
             mock.patch.object(nse_live, "_yf_fast_price", return_value=None):
            price, src = nse_live.get_live_price("TATASTEEL.NS")
        self.assertEqual((price, src), (88.0, "cached"))

    def test_all_fail_returns_historical(self):
        with mock.patch.object(nse_live, "get_nse_live_price", return_value=None), \
             mock.patch.object(nse_live, "_yf_fast_price", return_value=None), \
             mock.patch.object(nse_live._persistent_store, "get", return_value=None):
            price, src = nse_live.get_live_price("ZZZZ.NS")
        self.assertEqual((price, src), (None, "historical"))

    def test_yf_fallback_disabled(self):
        with mock.patch.object(nse_live, "get_nse_live_price", return_value=None), \
             mock.patch.object(nse_live, "_yf_fast_price", return_value=99.0) as yf_mock, \
             mock.patch.object(nse_live._persistent_store, "get", return_value=None):
            price, src = nse_live.get_live_price("TATASTEEL.NS", allow_yf_fallback=False)
        self.assertEqual((price, src), (None, "historical"))
        yf_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main(verbosity=2)
