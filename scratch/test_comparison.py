import requests
import time
from bs4 import BeautifulSoup
import sys
sys.stdout.reconfigure(encoding='utf-8')

def test_speed_and_accuracy():
    symbols = {
        "RELIANCE": {"nse": "RELIANCE", "bse_code": "500325", "gf": "RELIANCE:NSE"},
        "TATASTEEL": {"nse": "TATASTEEL", "bse_code": "500470", "gf": "TATASTEEL:NSE"},
        "RECLTD": {"nse": "RECLTD", "bse_code": "532955", "gf": "RECLTD:NSE"},
        "JIOFIN": {"nse": "JIOFIN", "bse_code": "543940", "gf": "JIOFIN:NSE"},
        "ETERNAL": {"nse": "ETERNAL", "bse_code": "543320", "gf": "ETERNAL:NSE"},
        "COALINDIA": {"nse": "COALINDIA", "bse_code": "533278", "gf": "COALINDIA:NSE"},
        "IRCTC": {"nse": "IRCTC", "bse_code": "542830", "gf": "IRCTC:NSE"},
        "BEL": {"nse": "BEL", "bse_code": "500049", "gf": "BEL:NSE"},
        "SILVERBEES": {"nse": "SILVERBEES", "bse_code": "533100", "gf": "SILVERBEES:NSE"},
        "MON100": {"nse": "MON100", "bse_code": "533470", "gf": "MON100:NSE"},
        "NXST": {"nse": "NXST", "bse_code": "543913", "gf": "543913:BOM"},
    }
    
    session = requests.Session()
    session.headers.update({
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    })
    
    print(f"{'SYMBOL':<12} | {'GF PRICE':<10} | {'GF TIME':<8} | {'BSE PRICE':<10} | {'BSE TIME':<8}")
    print("-" * 60)
    
    for name, data in symbols.items():
        # Google Finance
        t0 = time.time()
        gf_price = None
        try:
            r = session.get(f"https://www.google.com/finance/quote/{data['gf']}", timeout=3)
            soup = BeautifulSoup(r.text, 'html.parser')
            el = soup.select_one('div.N6SYTe') or soup.select_one('div.YMlKec.fxKbKc') or soup.select_one('span[jsname="Pdsbrc"]')
            if el:
                import re
                cleaned = re.sub(r'[^\d.]', '', el.text)
                gf_price = float(cleaned)
        except Exception:
            pass
        t_gf = time.time() - t0
        
        # BSE
        t0 = time.time()
        bse_price = None
        try:
            r = session.get(
                f"https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Debtflag=&scripcode={data['bse_code']}&seriesid=",
                headers={"Referer": "https://www.bseindia.com/"},
                timeout=3
            )
            bse_price = float(r.json().get("CurrRate", {}).get("LTP", 0))
        except Exception:
            pass
        t_bse = time.time() - t0
        
        print(f"{name:<12} | {str(gf_price):<10} | {t_gf*1000:6.1f}ms | {str(bse_price):<10} | {t_bse*1000:6.1f}ms")

if __name__ == "__main__":
    test_speed_and_accuracy()
