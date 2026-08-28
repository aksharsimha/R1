"""
Fetch the NSE official 3:30 PM closing price for NXST.
NSE publishes this via the quote API.
"""
import requests, json

SESSION = requests.Session()

def nse_headers():
    return {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Accept": "*/*",
        "Referer": "https://www.nseindia.com/",
        "Accept-Language": "en-US,en;q=0.9"
    }

# Warm up NSE session
print("Warming up NSE session...")
SESSION.get("https://www.nseindia.com", headers=nse_headers(), timeout=5)

# Try NSE quote for NXST - Note: NXST is a REIT on NSE as well
try:
    r = SESSION.get(
        "https://www.nseindia.com/api/quote-equity?symbol=NXST",
        headers=nse_headers(),
        timeout=5
    )
    print(f"NSE quote status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        pi = data.get("priceInfo", {})
        print(f"  lastPrice: {pi.get('lastPrice')}")
        print(f"  closePrice: {pi.get('closePrice')}")
        print(f"  previousClose: {pi.get('previousClose')}")
        print(f"  open: {pi.get('open')}")
    else:
        print(r.text[:500])
except Exception as e:
    print(f"Error: {e}")

# Also try NSE EQ bhavcopy or quote-derivative
try:
    r = SESSION.get(
        "https://www.nseindia.com/api/quote-equity?symbol=NEXUSSELECT",
        headers=nse_headers(),
        timeout=5
    )
    print(f"\nNSE quote NEXUSSELECT status: {r.status_code}")
    if r.status_code == 200:
        data = r.json()
        pi = data.get("priceInfo", {})
        print(f"  lastPrice: {pi.get('lastPrice')}")
        print(f"  closePrice: {pi.get('closePrice')}")
except Exception as e:
    print(f"Error: {e}")
