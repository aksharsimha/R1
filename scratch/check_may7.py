import yfinance as yf
import json
from datetime import datetime

holdings = [
    {"identifier": "RECLTD.NS", "quantity": 12.0},
    {"identifier": "JIOFIN.NS", "quantity": 18.0},
    {"identifier": "TATASTEEL.NS", "quantity": 20.0},
    {"identifier": "ETERNAL.NS", "quantity": 15.0},
    {"identifier": "IRCTC.NS", "quantity": 7.0},
    {"identifier": "COALINDIA.NS", "quantity": 8.0},
    {"identifier": "NXST.NS", "quantity": 22.0},
    {"identifier": "SILVERBEES.NS", "quantity": 15.0},
    {"identifier": "MON100.NS", "quantity": 32.0},
    {"identifier": "BEL.NS", "quantity": 1.0},
]

target_date = "2026-05-07"
# Use a range to get the specific day
start_date = "2026-05-07"
end_date = "2026-05-08"

total_val = 0.0
print(f"Fetching prices for {target_date}...")

for h in holdings:
    ticker = h["identifier"]
    qty = h["quantity"]
    data = yf.download(ticker, start=start_date, end=end_date, progress=False)
    if not data.empty:
        close_price = float(data['Close'].iloc[0])
        asset_val = close_price * qty
        total_val += asset_val
        print(f"{ticker}: {close_price:.2f} * {qty} = {asset_val:.2f}")
    else:
        print(f"No data for {ticker}")

print(f"\nTotal Portfolio Value on {target_date}: Rs.{total_val:,.2f}")
