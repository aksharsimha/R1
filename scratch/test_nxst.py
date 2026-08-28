import yfinance as yf

for sym in ["NXST.NS", "NXST.BO", "543913.BO"]:
    try:
        t = yf.Ticker(sym)
        fi = t.fast_info
        print(f"{sym}: last_price = {fi.last_price}, prev_close = {fi.previous_close}")
    except Exception as e:
        print(f"{sym}: error {e}")
