import requests
from bs4 import BeautifulSoup
import sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.google.com/finance/quote/RELIANCE:NSE"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
r = requests.get(url, headers=headers, timeout=5)
soup = BeautifulSoup(r.text, 'html.parser')
n6 = soup.find('div', class_='N6SYTe')
if n6:
    print("Found N6SYTe:", n6.prettify()[:300])
    print("Parent:", n6.parent.get('class') if n6.parent else None)
