import json
import os

PRED_FILE = r"c:\Users\aksha\OneDrive\Desktop\R1\predictions_log.json"

# Values to restore
may7 = {
    "target_date": "2026-05-07",
    "expected_val": 42275.15,
    "expected_change": 267.86,
    "drivers": {
      "Motilal Nasdaq 100 ETF": 10.0,
      "Silver BeES": 5.0,
      "Tata Steel": 2.0,
      "Eternal (Zomato)": 1.5
    },
    "real_val": 42185.39,
    "variance_reason": "Underperformed by Rs.89.76. Unexpected negative pressure, likely dragged by market volatility.",
    "base_close": 42007.29
}

may8 = {
    "target_date": "2026-05-08",
    "expected_val": 42571.92,
    "expected_change": 386.53,
    "drivers": {
      "IRCTC": -2.87,
      "Jio Financial Services": -2.14,
      "REC Limited": -1.44,
      "Eternal (Zomato)": 1.58,
      "Tata Steel": 1.97,
      "Silver BeES": 5.25,
      "BEL": 0.39,
      "Motilal Nasdaq 100 ETF": 10.39,
      "Coal India": 0.78,
      "Nexus Select Trust": 1.32
    },
    "real_val": None,
    "variance_reason": None,
    "base_close": 42185.39
}

try:
    with open(PRED_FILE, "r", encoding="utf-8") as f:
        preds = json.load(f)
except:
    preds = []

# Filter out existing entries for these dates to avoid duplicates
preds = [p for p in preds if p["target_date"] not in ["2026-05-07", "2026-05-08"]]

# Insert at the beginning, keeping it chronological if possible, but reversed is used in UI anyway
# Let's just sort it at the end
preds.append(may7)
preds.append(may8)
preds.sort(key=lambda x: x["target_date"])

with open(PRED_FILE, "w", encoding="utf-8") as f:
    json.dump(preds, f, indent=2)

print(f"Restored May 7 and May 8. Total entries: {len(preds)}")
