import requests
import re
from bs4 import BeautifulSoup

def test_google_finance(ticker="RELIANCE:NSE"):
    url = f"https://www.google.com/finance/quote/{ticker}"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9"
    }
    r = requests.get(url, headers=headers, timeout=5)
    print(f"Google Finance {ticker} status:", r.status_code)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        # Print elements with numbers/currency or classes
        for tag in soup.find_all(attrs={"data-last-price": True}):
            print("data-last-price attr:", tag.get("data-last-price"))
        # find currency elements
        for div in soup.find_all(['div', 'span'], class_=True):
            cls = " ".join(div.get('class', []))
            if any(k in cls for k in ['YMlKec', 'fxKbKc', 'rPF6WZ', 'kf1m0']):
                print(f"Class [{cls}]:", div.text)
        
def test_bse():
    # BSE scrip code lookup / quote
    # Reliance is 500325, Tata Steel is 500470, REC is 532955
    scrip_map = {
        "RELIANCE": "500325",
        "TATASTEEL": "500470",
        "RECLTD": "532955",
        "JIOFIN": "543940",
        "COALINDIA": "533278",
        "IRCTC": "542830",
        "BEL": "500049",
        "SILVERBEES": "533100", # or ETF
    }
    for sym, scrip in scrip_map.items():
        url = f"https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Debtflag=&scripcode={scrip}&seriesid="
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Referer": "https://www.bseindia.com/",
            "Accept": "application/json, text/plain, */*"
        }
        try:
            r = requests.get(url, headers=headers, timeout=5)
            data = r.json()
            ltp = data.get("CurrRate", {}).get("LTP")
            print(f"BSE {sym} ({scrip}): LTP = {ltp}")
        except Exception as e:
            print(f"BSE {sym} error:", e)

if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    test_google_finance("RELIANCE:NSE")
    test_google_finance("TATASTEEL:NSE")
    test_google_finance("RECLTD:NSE")
    test_google_finance("JIOFIN:NSE")
    print("\n--- BSE Test ---")
    test_bse()
