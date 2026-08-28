import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
from nse_live import get_live_price, _yahoo_to_nse

with open('quest_app/users/akshar/holdings.json') as f:
    holdings = json.load(f)['holdings']

total_val = 0.0
total_inv = sum(x['amount'] for x in holdings)
total_prev_day_val = 0.0

print(f"{'Name':<24} | {'Ticker':<12} | {'Qty':<5} | {'Invested':<9} | {'Avg Buy':<8} | {'Live LTP':<8} | {'Live Val':<9} | {'P&L':<9}")
print("-" * 105)

for x in holdings:
    ticker = x['identifier']
    qty = float(x['quantity'])
    inv = float(x['amount'])
    avg_buy = inv / qty if qty > 0 else 0
    p, src = get_live_price(ticker)
    val = (p or 0.0) * qty
    pnl = val - inv
    total_val += val
    print(f"{x['name']:<24} | {ticker:<12} | {qty:<5.0f} | {inv:<9.2f} | {avg_buy:<8.2f} | {str(p):<8} | {val:<9.2f} | {pnl:<9.2f}")

print("-" * 105)
print(f"Calculated Total Invested:  Rs. {total_inv:,.2f}")
print(f"Groww Total Invested:       Rs. 84,532.33")
print(f"Calculated Total Value:     Rs. {total_val:,.2f}")
print(f"Groww Total Value:          Rs. 86,249.86")
print(f"Calculated Total Returns:   Rs. {total_val - total_inv:,.2f} ({(total_val - total_inv)/total_inv*100:.2f}%)")
print(f"Groww Total Returns:        Rs. +1,717.53 (+2.03%)")
print(f"Discrepancy in Total Value: Rs. {total_val - 86249.86:,.2f}")
