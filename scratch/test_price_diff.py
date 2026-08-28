"""
Deep dive: compare QUEST prices vs exact Groww closing settlement prices.
Groww official closing prices from the screenshot taken at 16:54 IST:
"""
import yfinance as yf

# ---- EXACT prices Groww is using from your screenshot ----
GROWW_EXACT = {
    "ITC.NS":        {"name": "ITC",                   "qty": 55,  "cur": 14795.00, "inv": 15975.85},
    "MON100.NS":     {"name": "Motilal-NASDAQ 100",    "qty": 32,  "cur": 10462.08, "inv": 7407.36},
    "IRCTC.NS":      {"name": "IRCTC",                 "qty": 16,  "cur": 7800.80,  "inv": 8843.52},
    "ETERNAL.NS":    {"name": "Eternal (Zomato)",      "qty": 22,  "cur": 7227.00,  "inv": 5649.82},
    "JIOFIN.NS":     {"name": "JIO Financial",         "qty": 29,  "cur": 6904.90,  "inv": 7175.76},
    "TATAGOLD.NS":   {"name": "TATAGOLD",              "qty": 377, "cur": 5764.33,  "inv": 5244.07},
    "BEL.NS":        {"name": "Bharat Electronics",    "qty": 14,  "cur": 5754.00,  "inv": 5783.68},
    "NXST.BO":       {"name": "Nexus Select Trust",    "qty": 34,  "cur": 5677.66,  "inv": 5480.46},
    "TATASTEEL.NS":  {"name": "Tata Steel",            "qty": 30,  "cur": 5604.00,  "inv": 5781.90},
    "RECLTD.NS":     {"name": "REC Limited",           "qty": 17,  "cur": 5455.30,  "inv": 6197.01},
    "SILVERBEES.NS": {"name": "Silver BeES",           "qty": 24,  "cur": 5432.88,  "inv": 5752.32},
    "COALINDIA.NS":  {"name": "Coal India",            "qty": 12,  "cur": 4800.00,  "inv": 5061.00},
    "ZEELEARN.NS":   {"name": "Zee Learn",             "qty": 12,  "cur": 93.84,    "inv": 92.28},
    "IDEA.NS":       {"name": "Vodafone Idea",         "qty": 6,   "cur": 89.82,    "inv": 87.30},
}

print(f"{'Stock':<22} | {'GrowwLTP':<9} | {'YF_LTP':<9} | {'YF_Prev':<10} | {'Diff':<7}")
print("-" * 70)

for sym, d in GROWW_EXACT.items():
    groww_ltp = d["cur"] / d["qty"]
    try:
        fi = yf.Ticker(sym).fast_info
        yf_ltp  = round(float(fi.last_price), 4)
        yf_prev = round(float(fi.previous_close), 4)
    except Exception as e:
        yf_ltp = yf_prev = None
    diff = round(yf_ltp - groww_ltp, 4) if yf_ltp else None
    print(f"{d['name']:<22} | {groww_ltp:<9.4f} | {str(yf_ltp):<9} | {str(yf_prev):<10} | {str(diff):<7}")

print()
groww_total = sum(d["cur"] for d in GROWW_EXACT.values())
print(f"Groww total: {groww_total:,.2f}")
