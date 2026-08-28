import yfinance as yf
import json

tickers = [
    ("ITC", "ITC.NS", 55.0, 15975.85),
    ("Motilal-NASDAQ 100", "MON100.NS", 32.0, 7407.36),
    ("IRCTC", "IRCTC.NS", 16.0, 8843.52),
    ("Eternal (Zomato)", "ETERNAL.NS", 22.0, 5649.82),
    ("JIO Financial Serv.", "JIOFIN.NS", 29.0, 7175.76),
    ("TATAGOLD", "TATAGOLD.NS", 377.0, 5244.07),
    ("Bharat Electronics", "BEL.NS", 14.0, 5783.68),
    ("Nexus Select Trust", "NXST.BO", 34.0, 5480.46),
    ("Tata Steel", "TATASTEEL.NS", 30.0, 5781.90),
    ("RECL", "RECLTD.NS", 17.0, 6197.01),
    ("SILVERBEES", "SILVERBEES.NS", 24.0, 5752.32),
    ("Coal India", "COALINDIA.NS", 12.0, 5061.00),
    ("Zee Learn", "ZEELEARN.NS", 12.0, 92.28),
    ("Vodafone Idea", "IDEA.NS", 6.0, 87.30),
]

total_cur = 0.0
total_inv = 0.0
total_prev = 0.0
total_1d = 0.0

print(f"{'Stock':<22} | {'Qty':<5} | {'Invested':<9} | {'LTP':<8} | {'PrevClose':<10} | {'CurVal':<10} | {'1D P&L':<8} | {'Tot P&L':<9}")
print("-" * 105)

for name, sym, qty, inv in tickers:
    t = yf.Ticker(sym)
    fi = t.fast_info
    ltp = round(float(fi.last_price), 2)
    prev = round(float(fi.previous_close), 2)
    
    # Specific adjustment if any for exact settlement
    cur_val = round(ltp * qty, 2)
    day_pnl = round((ltp - prev) * qty, 2)
    tot_pnl = round(cur_val - inv, 2)
    
    total_cur += cur_val
    total_inv += inv
    total_prev += (prev * qty)
    total_1d += day_pnl
    
    print(f"{name:<22} | {qty:<5.0f} | {inv:<9.2f} | {ltp:<8.2f} | {prev:<10.2f} | {cur_val:<10.2f} | {day_pnl:<8.2f} | {tot_pnl:<9.2f}")

print("-" * 105)
print(f"Total Invested:   Rs. {total_inv:,.2f}  (Groww: Rs. 84,532.33)")
print(f"Total Value:      Rs. {total_cur:,.2f}  (Groww: Rs. 85,861.61)")
print(f"Total Returns:    Rs. {total_cur - total_inv:+,.2f} ({(total_cur - total_inv)/total_inv*100:+.2f}%) (Groww: +Rs. 1,329.28, +1.57%)")
print(f"1D Returns:       Rs. {total_1d:+,.2f} ({(total_1d)/total_prev*100:+.2f}%) (Groww: -Rs. 388.25, -0.45%)")
