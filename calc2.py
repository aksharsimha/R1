import json
with open('users/akshar/holdings.json', 'r') as f:
    holdings = json.load(f)['holdings']
for h in holdings:
    print(f"{h['name']}: {h['amount']}")
