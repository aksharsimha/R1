import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.stdout.reconfigure(encoding='utf-8')
import requests
from bs4 import BeautifulSoup
import re

with open('quest_app/users/akshar/holdings.json') as f:
    holdings = json.load(f)['holdings']

print(f"{'Name':<22} | {'Ticker':<13} | {'Qty':<5} | {'GF Price':<10} | {'BSE Price':<10} | {'YF Price':<10}")
print("-" * 80)

for x in holdings:
    t = x['identifier']
    clean = t.replace('.NS', '').replace('.BO', '')
    
    # GF
    gf_p = None
    try:
        r = requests.get(f"https://www.google.com/finance/quote/{clean}:NSE", headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        soup = BeautifulSoup(r.text, 'html.parser')
        el = soup.select_one('div.N6SYTe') or soup.select_one('div.YMlKec.fxKbKc')
        if el:
            gf_p = float(re.sub(r'[^\d.]', '', el.text))
    except Exception:
        pass

    # BSE
    bse_p = None
    try:
        # Check BSE
        r2 = requests.get(f"https://www.google.com/finance/quote/{clean}:BOM", headers={"User-Agent": "Mozilla/5.0"}, timeout=3)
        soup2 = BeautifulSoup(r2.text, 'html.parser')
        el2 = soup2.select_one('div.N6SYTe') or soup2.select_one('div.YMlKec.fxKbKc')
        if el2:
            bse_p = float(re.sub(r'[^\d.]', '', el2.text))
    except Exception:
        pass

    print(f"{x['name']:<22} | {t:<13} | {x['quantity']:<5.0f} | {str(gf_p):<10} | {str(bse_p):<10}")
