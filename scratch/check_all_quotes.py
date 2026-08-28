import requests
from bs4 import BeautifulSoup
import re
import yfinance as yf
import json

headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/125.0.0.0 Safari/537.36"}

tickers = [
    ("ITC", "ITC.NS", "ITC:NSE"),
    ("MON100", "MON100.NS", "MON100:NSE"),
    ("IRCTC", "IRCTC.NS", "IRCTC:NSE"),
    ("ETERNAL", "ETERNAL.NS", "ETERNAL:NSE"),
    ("JIOFIN", "JIOFIN.NS", "JIOFIN:NSE"),
    ("TATAGOLD", "TATAGOLD.NS", "TATAGOLD:NSE"),
    ("BEL", "BEL.NS", "BEL:NSE"),
    ("NXST", "NXST.BO", "543913:BOM"),
    ("TATASTEEL", "TATASTEEL.NS", "TATASTEEL:NSE"),
    ("RECLTD", "RECLTD.NS", "RECLTD:NSE"),
    ("SILVERBEES", "SILVERBEES.NS", "SILVERBEES:NSE"),
    ("COALINDIA", "COALINDIA.NS", "COALINDIA:NSE"),
    ("ZEELEARN", "ZEELEARN.NS", "ZEELEARN:NSE"),
    ("IDEA", "IDEA.NS", "IDEA:NSE"),
]

print(f"{'Stock':<12} | {'GF LTP':<10} | {'GF PrevClose':<12} | {'YF LTP':<10} | {'YF PrevClose':<12}")
print("-" * 65)

for name, yf_sym, gf_sym in tickers:
    # GF
    gf_ltp, gf_pc = None, None
    try:
        r = requests.get(f"https://www.google.com/finance/quote/{gf_sym}", headers=headers, timeout=4)
        if r.status_code == 200:
            soup = BeautifulSoup(r.text, 'html.parser')
            el = soup.select_one('div.YMlKec.fxKbKc') or soup.select_one('div.N6SYTe')
            if el:
                gf_ltp = float(re.sub(r'[^\d.]', '', el.text))
            for row in soup.find_all('div', class_='gyFHrc'):
                lbl = row.find('div', class_='mfs7Fc')
                val = row.find('div', class_='P6K39c')
                if lbl and 'Previous close' in lbl.text and val:
                    gf_pc = float(re.sub(r'[^\d.]', '', val.text))
                    break
    except Exception as e:
        pass

    # YF
    yf_ltp, yf_pc = None, None
    try:
        fi = yf.Ticker(yf_sym).fast_info
        yf_ltp = fi.last_price
        yf_pc = fi.previous_close
    except Exception:
        pass

    print(f"{name:<12} | {str(gf_ltp):<10} | {str(gf_pc):<12} | {str(round(yf_ltp, 2) if yf_ltp else None):<10} | {str(round(yf_pc, 2) if yf_pc else None):<12}")
