import requests
from bs4 import BeautifulSoup
import re
import sys
import json
sys.stdout.reconfigure(encoding='utf-8')

def extract_gf_price(text: str):
    soup = BeautifulSoup(text, 'html.parser')
    
    # 1. Check jsname="Pdsbrc" or class N6SYTe or YMlKec fxKbKc
    for selector in ['div.N6SYTe', 'div.YMlKec.fxKbKc', 'span[jsname="Pdsbrc"]', 'div.YMlKec']:
        el = soup.select_one(selector)
        if el and el.text:
            cleaned = re.sub(r'[^\d.]', '', el.text)
            try:
                val = float(cleaned)
                if val > 0:
                    return val
            except ValueError:
                pass
                
    # 2. Check regex for price near header
    m = re.search(r'₹([\d,]+\.\d{2})', text)
    if m:
        try:
            return float(m.group(1).replace(',', ''))
        except ValueError:
            pass
            
    return None

def get_google_finance_price(symbol: str):
    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    for exch in ["NSE", "BOM"]:
        url = f"https://www.google.com/finance/quote/{clean}:{exch}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            r = requests.get(url, headers=headers, timeout=5)
            if r.status_code == 200:
                p = extract_gf_price(r.text)
                if p is not None:
                    return p, f"google_finance_{exch.lower()}"
        except Exception as e:
            pass
    return None, "failed"

if __name__ == "__main__":
    with open("holdings.json", "r") as f:
        data = json.load(f)
    for h in data["holdings"]:
        sym = h["identifier"]
        price, src = get_google_finance_price(sym)
        print(f"{sym:15} -> Price: {price} ({src})")
