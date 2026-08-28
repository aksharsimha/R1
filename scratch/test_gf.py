import requests
from bs4 import BeautifulSoup
import re

def get_google_finance_price(symbol: str):
    # Try NSE first, then BOM (BSE)
    # Strip any suffix like .NS, .BO
    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    for exch in ["NSE", "BOM"]:
        url = f"https://www.google.com/finance/quote/{clean_sym}:{exch}"
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
        }
        try:
            r = requests.get(url, headers=headers, timeout=4)
            if r.status_code == 200:
                soup = BeautifulSoup(r.text, 'html.parser')
                # Primary class used by Google Finance for live price
                # <div class="YMlKec fxKbKc">₹1,299.00</div>
                price_div = soup.find('div', class_='YMlKec fxKbKc')
                if not price_div:
                    # fallback to any YMlKec
                    price_div = soup.find('div', class_=re.compile(r'\bYMlKec\b'))
                if price_div:
                    raw_text = price_div.text.replace('₹', '').replace(',', '').strip()
                    val = float(raw_text)
                    print(f"Google Finance [{clean_sym}:{exch}] -> {val}")
                    return val
        except Exception as e:
            print(f"Error {clean_sym}:{exch} -> {e}")
    return None

if __name__ == "__main__":
    symbols = ["RELIANCE.NS", "TATASTEEL.NS", "RECLTD.NS", "JIOFIN.NS", "COALINDIA.NS", "IRCTC.NS", "BEL.NS", "SILVERBEES.NS", "MON100.NS", "NXST.NS"]
    for s in symbols:
        p = get_google_finance_price(s)
        print(f"Result for {s}: {p}")
