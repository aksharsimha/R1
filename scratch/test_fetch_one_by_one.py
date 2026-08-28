import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import nse_live

with open('quest_app/users/akshar/holdings.json', encoding='utf-8') as f:
    holdings = json.load(f)['holdings']

print("Holdings count:", len(holdings), flush=True)

for i, x in enumerate(holdings):
    ticker = x['identifier']
    print(f"[{i+1}/{len(holdings)}] Fetching {ticker} ({x['name']})...", flush=True)
    p, src = nse_live.get_live_price(ticker)
    qty = float(x['quantity'])
    inv = float(x['amount'])
    val = (p or 0.0) * qty
    print(f"   -> Price: {p} ({src}), Qty: {qty}, Val: {val:.2f}, Invested: {inv:.2f}", flush=True)

print("Done!", flush=True)
