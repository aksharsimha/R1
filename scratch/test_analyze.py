import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')

import json
from risk_analyzer import Asset, analyze_portfolio

with open('quest_app/users/akshar/holdings.json', encoding='utf-8') as f:
    raw = json.load(f)['holdings']

assets = [Asset(**x) for x in raw]

df, summary = analyze_portfolio(assets, period="2y", verbose=True)

print("\n--- Summary ---")
for k, v in summary.items():
    print(f"{k}: {v}")

print("\n--- DataFrame ---")
cols = ["Name", "Invested (₹)", "Quantity", "Last Price", "Current Value (₹)", "Price Source", "P&L (₹)", "P&L %"]
print(df[cols].to_string())
