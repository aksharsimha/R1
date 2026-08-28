"""
Fetch BSE official EOD closing price for NXST (scrip 543913).
BSE publishes official closing prices at: https://www.bseindia.com/markets/equity/EQReports/StockPriceData.aspx
Or via: https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?scripcode=543913&flag=0&fromdate=&todate=&seriesid=
"""
import requests

# Try BSE official EOD via the 1-day graph data endpoint
def fetch_bse_eod_close(scrip_code: str):
    url = f"https://api.bseindia.com/BseIndiaAPI/api/StockReachGraph/w?scripcode={scrip_code}&flag=0&fromdate=&todate=&seriesid="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.bseindia.com/",
        "Accept": "application/json, text/plain, */*"
    }
    r = requests.get(url, headers=headers, timeout=5)
    data = r.json()
    return data

# Method 2: scrip header (the same one we use for LTP)
def fetch_bse_scrip_header(scrip_code: str):
    url = f"https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Debtflag=&scripcode={scrip_code}&seriesid="
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
        "Referer": "https://www.bseindia.com/",
        "Accept": "application/json, text/plain, */*"
    }
    r = requests.get(url, headers=headers, timeout=5)
    data = r.json()
    return data

# Method 3: NSE quote for NXST
def fetch_nse_closing_price(symbol: str):
    import yfinance as yf
    t = yf.Ticker(symbol)
    hist = t.history(period="2d", interval="1d")
    print(f"NSE hist for {symbol}:")
    print(hist[["Close", "Volume"]].to_string())
    return hist

print("=== BSE scrip header for NXST (543913) ===")
data = fetch_bse_scrip_header("543913")
print("CurrRate:", data.get("CurrRate"))
print("Header:", {k: v for k, v in data.items() if k not in ["CurrRate", "ChartData"]})

print()
print("=== NXST.BO 2d history ===")
fetch_nse_closing_price("NXST.BO")
