import requests
import re
res = requests.get('https://www.google.com/finance/quote/NXST:NSE', headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36'})
m = re.search(r'<div class="YMlKec fxKbKc">₹([^<]+)</div>', res.text)
if m:
    val = m.group(1).replace(',', '')
    print(float(val))
else:
    match2 = re.search(r'data-last-price="([^"]+)"', res.text)
    if match2:
        print("data-last-price:", match2.group(1))
    else:
        print("Still not found. Here is a snippet:")
        idx = res.text.find('NXST')
        print(res.text[max(0, idx-100):idx+500])
