import requests
from bs4 import BeautifulSoup
import re
import sys
sys.stdout.reconfigure(encoding='utf-8')

url = "https://www.google.com/finance/quote/RELIANCE:NSE"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "en-US,en;q=0.9",
}
r = requests.get(url, headers=headers, timeout=5)
print("Status:", r.status_code)
soup = BeautifulSoup(r.text, 'html.parser')
# Find all divs containing currency or numbers with 2 decimals
for div in soup.find_all(['div', 'span']):
    text = div.text.strip()
    if text.startswith('₹') and len(text) < 20:
        print(f"Tag <{div.name} class='{div.get('class')}'>: {text}")
