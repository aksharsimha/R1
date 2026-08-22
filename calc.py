import json
import nse_live
with open('users/akshar/holdings.json', 'r') as f: holdings = json.load(f)['holdings']
total = 0
for h in holdings:
    p, _ = nse_live.get_live_price(h['identifier'])
    if p is None: p = 0
    total += p * h['quantity']
print(f"Current Total: {total:.2f}")
print(f"Invested Total: {sum(h['amount'] for h in holdings):.2f}")
