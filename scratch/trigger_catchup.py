
from portfolio_ledger import ewma_catchup
from risk_analyzer import analyze_portfolio, load_holdings, HOLDINGS_FILE

print("Running EWMA catch-up...")
# We need the seeds (historical_mu and historical_sigma)
current_assets = load_holdings(HOLDINGS_FILE)
df, summary = analyze_portfolio(current_assets, period="2y", verbose=False)

if not df.empty:
    vol_ann_seed = summary.get('portfolio_volatility', 0.15)
    mu_ann_seed = summary.get('weighted_ann_return', 12.0) / 100.0
    current_val_seed = summary.get('total_value', 0.0)
    
    hist_mu_daily = current_val_seed * (((1 + mu_ann_seed) ** (1/365)) - 1)
    hist_sigma_daily = current_val_seed * (vol_ann_seed / (252 ** 0.5))

    processed = ewma_catchup(historical_mu=hist_mu_daily, historical_sigma=hist_sigma_daily)
    print(f"Processed {processed} new entries.")
else:
    print("Portfolio empty, cannot calculate seeds.")
