from curl_cffi import requests
import json

s = requests.Session(impersonate="chrome120")

# Step 1: visit home
r0 = s.get("https://www.nseindia.com", headers={
    "authority": "www.nseindia.com",
    "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
    "accept-language": "en-US,en;q=0.9",
    "cache-control": "max-age=0",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "document",
    "sec-fetch-mode": "navigate",
    "sec-fetch-site": "none",
    "sec-fetch-user": "?1",
    "upgrade-insecure-requests": "1",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}, timeout=10)
print("NSE Home:", r0.status_code, "Cookies:", list(s.cookies.keys()))

# Step 2: Try quote with exact browser headers
api_headers = {
    "authority": "www.nseindia.com",
    "accept": "*/*",
    "accept-language": "en-US,en;q=0.9",
    "referer": "https://www.nseindia.com/get-quotes/equity?symbol=RELIANCE",
    "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
    "sec-ch-ua-mobile": "?0",
    "sec-ch-ua-platform": '"Windows"',
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

r1 = s.get("https://www.nseindia.com/api/quote-equity?symbol=RELIANCE", headers=api_headers, timeout=10)
print("Quote status:", r1.status_code)
if r1.status_code == 200:
    try:
        print("Price info:", r1.json().get("priceInfo"))
    except Exception as e:
        print("JSON parse error:", e)
else:
    print("Response text:", r1.text[:200])
