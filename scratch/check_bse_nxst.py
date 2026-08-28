import requests
import json

url = "https://api.bseindia.com/BseIndiaAPI/api/getScripHeaderData/w?Debtflag=&scripcode=543913&seriesid="
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36",
    "Referer": "https://www.bseindia.com/",
    "Accept": "application/json, text/plain, */*"
}

r = requests.get(url, headers=headers, timeout=5)
data = r.json()
print("BSE Scrip 543913:", json.dumps(data.get("CurrRate", {}), indent=2))
