import yfinance as yf

symbols = ["RELIANCE.NS", "TATASTEEL.NS", "RECLTD.NS", "JIOFIN.NS", "COALINDIA.NS", "IRCTC.NS", "BEL.NS", "SILVERBEES.NS", "MON100.NS"]
for s in symbols:
    t = yf.Ticker(s)
    try:
        p = t.fast_info.last_price
        print(f"YF {s:15}: {p}")
    except Exception as e:
        print(f"YF {s:15}: Error {e}")
