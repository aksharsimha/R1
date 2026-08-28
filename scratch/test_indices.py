import requests
from bs4 import BeautifulSoup
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

for name, q in [("NIFTY 50", "NIFTY_50:INDEXNSE"), ("SENSEX", "SENSEX:INDEXBOM"), ("NIFTY BANK", "NIFTY_BANK:INDEXNSE")]:
    url = f"https://www.google.com/finance/quote/{q}"
    r = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=5)
    print(name, r.status_code)
    if r.status_code == 200:
        soup = BeautifulSoup(r.text, 'html.parser')
        el = soup.select_one('div.N6SYTe') or soup.select_one('div.YMlKec.fxKbKc') or soup.select_one('span[jsname="Pdsbrc"]')
        if el:
            cleaned = re.sub(r'[^\d.]', '', el.text)
            print(f"  {name} Live Quote: {cleaned}")
