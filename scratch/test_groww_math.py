import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup
import re
import yfinance as yf

with open('quest_app/users/akshar/holdings.json') as f:
    holdings = json.load(f)['holdings']

print(f"{'Name':<24} | {'Qty':<5} | {'Invested':<9} | {'LTP':<8} | {'PrevClose':<10} | {'1D P&L':<8} | {'Tot P&L':<9}")
print("-" * 95)

total_inv = 0.0
total_cur_val = 0.0
total_1d_pnl = 0.0
total_prev_val = 0.0

for x in holdings:
    t = x['identifier']
    clean = t.replace('.NS', '').replace('.BO', '')
    qty = float(x['quantity'])
    inv = float(x['amount'])
    total_inv += inv
    
    # Get Google Finance LTP and Previous Close
    ltp = None
    prev_close = None
    try:
        # Check NSE on GF
        for q in [f"{clean}:NSE", f"{clean}:BOM", f"543913:BOM" if "NXST" in clean else f"{clean}:NSE"]:
            r = requests.get(f"https://www.google.com/finance/quote/{q}", headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                el = soup.select_one('div.N6SYTe') or soup.select_one('div.YMlKec.fxKbKc')
                if el:
                    ltp = float(re.sub(r'[^\d.]', '', el.text))
                    
                # Find Previous close in table: <div class="P6K39c">Previous close</div> ...
                for row in soup.find_all('div', class_='gyFHrc'):
                    lbl = row.find('div', class_='mfs7Fc')
                    val_el = row.find('div', class_='P6K39c')
                    if lbl and 'Previous close' in lbl.text and val_el:
                        prev_close = float(re.sub(r'[^\d.]', '', val_el.text))
                        break
                if ltp and prev_close:
                    break
    except Exception as e:
        pass
        
    if not ltp or not prev_close:
        # Fallback to yfinance for prev_close / ltp
        try:
            fi = yf.Ticker(t).fast_info
            ltp = ltp or float(fi.last_price)
            prev_close = prev_close or float(fi.previous_close)
        except Exception:
            pass

    cur_val = (ltp or 0.0) * qty
    prev_val = (prev_close or ltp or 0.0) * qty
    day_pnl = ((ltp or 0.0) - (prev_close or ltp or 0.0)) * qty
    tot_pnl = cur_val - inv
    
    total_cur_val += cur_val
    total_prev_val += prev_val
    total_1d_pnl += day_pnl
    
    print(f"{x['name']:<24} | {qty:<5.0f} | {inv:<9.2f} | {str(ltp):<8} | {str(prev_close):<10} | {day_pnl:<8.2f} | {tot_pnl:<9.2f}")

print("-" * 95)
print(f"Total Invested:       Rs. {total_inv:,.2f} (Groww: Rs. 84,532.33)")
print(f"Current Value:        Rs. {total_cur_val:,.2f} (Groww: Rs. 86,249.86)")
print(f"Total Returns:        Rs. {total_cur_val - total_inv:+,.2f} ({(total_cur_val - total_inv)/total_inv*100:+.2f}%) (Groww: +Rs. 1,717.53, +2.03%)")
print(f"1D Returns:           Rs. {total_1d_pnl:+,.2f} ({(total_1d_pnl)/total_prev_val*100:+.2f}%) (Groww: -Rs. 305.14, -0.35%)")
