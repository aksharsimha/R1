"""
Try fetching NXST closing price from multiple sources.
The goal is to get the official 3:30 PM NSE closing price (166.99).
"""
import yfinance as yf
import requests

# Yahoo Finance 1d ohlcv history — the Close column is the official NSE closing price
print("=== NXST.NS (NSE) 2d history ===")
t = yf.Ticker("NXST.NS")
hist = t.history(period="5d", interval="1d")
print(hist[["Open","High","Low","Close","Volume"]].to_string())

print()
print("=== NXST.BO (BSE) 2d history ===")
t = yf.Ticker("NXST.BO")
hist = t.history(period="5d", interval="1d")
print(hist[["Open","High","Low","Close","Volume"]].to_string())

print()
print("=== NXST.NS fast_info ===")
fi = yf.Ticker("NXST.NS").fast_info
print(f"  last_price:      {fi.last_price}")
print(f"  previous_close:  {fi.previous_close}")
print(f"  regular_market_price: {fi.regular_market_price if hasattr(fi,'regular_market_price') else 'N/A'}")
