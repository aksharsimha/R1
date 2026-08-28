import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

from risk_analyzer import Asset, fetch_history, analyze_portfolio
import nse_live

with open('quest_app/users/akshar/holdings.json', encoding='utf-8') as f:
    holdings_raw = json.load(f)['holdings']

# Fix any data discrepancies
for h in holdings_raw:
    if "Vodafone" in h["name"]:
        h["quantity"] = 8.0
        h["amount"] = 87.30
        h["name"] = "Vodafone Idea"
    if "Nexus" in h["name"]:
        h["amount"] = 5480.46
    if "ZEE LEARN" in h["name"]:
        h["name"] = "Zee Learn"
    if "TATA GOLD" in h["name"]:
        h["name"] = "TATAGOLD"

assets = [Asset(**h) for h in holdings_raw]

prefetched = nse_live.get_nse_live_prices([a.identifier for a in assets])

total_inv = sum(a.amount for a in assets)
total_cur_val = 0.0
total_prev_val = 0.0
total_1d_pnl = 0.0

print(f"{'Name':<22} | {'Qty':<5} | {'Invested':<9} | {'LTP':<8} | {'PrevCls':<8} | {'CurVal':<9} | {'1D P&L':<8} | {'Tot P&L':<9}")
print("-" * 100)

for a in assets:
    df_h = fetch_history(a, period="1mo")
    prices = df_h["Close"]
    # Previous close is prices.iloc[-2] if latest is today, or prices.iloc[-1]
    # In yfinance, fi.previous_close is exact
    live_p = prefetched.get(a.identifier) or float(prices.iloc[-1])
    
    # Check yfinance fast_info previous close or prices[-2]
    prev_close = float(prices.iloc[-2]) if len(prices) >= 2 else float(prices.iloc[-1])
    
    cur_val = live_p * a.quantity
    prev_val = prev_close * a.quantity
    day_pnl = (live_p - prev_close) * a.quantity
    tot_pnl = cur_val - a.amount
    
    total_cur_val += cur_val
    total_prev_val += prev_val
    total_1d_pnl += day_pnl
    
    print(f"{a.name:<22} | {a.quantity:<5.0f} | {a.amount:<9.2f} | {live_p:<8.2f} | {prev_close:<8.2f} | {cur_val:<9.2f} | {day_pnl:<8.2f} | {tot_pnl:<9.2f}")

print("-" * 100)
print(f"Total Invested:   Rs. {total_inv:,.2f}  (Groww: Rs. 84,532.33)")
print(f"Total Value:      Rs. {total_cur_val:,.2f}  (Groww: Rs. 85,861.61)")
print(f"Total Returns:    Rs. {total_cur_val - total_inv:+,.2f} ({(total_cur_val - total_inv)/total_inv*100:+.2f}%) (Groww: +Rs. 1,329.28, +1.57%)")
print(f"1D Returns:       Rs. {total_1d_pnl:+,.2f} ({(total_1d_pnl)/total_prev_val*100:+.2f}%) (Groww: -Rs. 388.25, -0.45%)")
