# Portfolio Risk Analyzer

Risk + P&L diagnostics + live monitoring for your mixed Indian portfolio
(equities, ETFs, mutual funds, digital gold).

## Files

| File | What it does |
|---|---|
| `risk_analyzer.py` | Core module — all metrics, scoring, fetchers, live loop |
| `portfolio_risk_analysis.ipynb` | Walkthrough notebook with charts + analysis |
| `live_monitor.py` | Standalone terminal monitor with hot-reload of amounts |
| `holdings.json` | Your portfolio. Edit ₹ amounts here |
| `requirements.txt` | Python deps |

## Setup

```bash
pip install -r requirements.txt
```

## Two ways to run

### A) Notebook (analysis-first)

```bash
jupyter notebook portfolio_risk_analysis.ipynb
```

Walks you through every metric, generates risk-vs-return scatter, correlation
heatmap, and ranking bar chart. Cell 9 starts the live loop.

### B) Standalone live monitor (terminal)

```bash
# First time: enter ₹ amounts interactively
python live_monitor.py --setup

# Run forever, refresh every 60s (default)
python live_monitor.py

# Faster refresh
python live_monitor.py --interval 30

# Run once and exit
python live_monitor.py --once
```

While it's running, edit `holdings.json` in any text editor → next refresh
picks up the new amounts.

## What you get

**Per asset:**
- Volatility, Beta vs Nifty, Max drawdown, Sharpe, VaR/CVaR
- Total return %, Annualized return, Profit factor, Win rate
- Live: RSI, 52-week position, distance from 50/200-DMA
- **Composite risk score (0–100)** + bucket: LOW / MODERATE / HIGH / SEVERE

**Portfolio:**
- Position-weighted risk score
- Risk **rank** for every holding
- Correlation matrix
- Annualized portfolio volatility
- Diversification ratio (>1 = diversification helping)
- Concentration HHI (1.0 = all in one asset; 1/N = perfectly equal)
- Weighted total return + annualized return

## Important caveats

1. **Mutual fund NAVs update once daily** (post-market, ~9 PM IST). "Live"
   only really applies to listed equities/ETFs during NSE hours
   (9:15–15:30 IST, Mon–Fri).

2. **PhonePe Gold** is proxied via `GOLDBEES.NS` (Nippon India Gold ETF) since
   digital gold isn't a listed instrument. Both track 24K gold spot — expense
   ratios differ slightly.

3. **Verify mutual fund scheme codes** before trusting the defaults. Run
   `search_mf_scheme("HDFC Flexi Cap")` in the notebook — schemes differ
   between Direct/Regular and Growth/IDCW plans.

4. **Beta** is meaningful only for equity-type assets vs Nifty 50. Reported as
   `NaN` for mutual funds and gold.

5. This is a research and education tool. Not investment advice.

## Composite score weights

| Component | Weight |
|---|---|
| Volatility | 20% |
| Drawdown | 20% |
| Sharpe | 15% |
| Distance from 200-DMA | 15% |
| Beta | 10% |
| VaR | 10% |
| RSI | 10% |

Edit `WEIGHTS` in `risk_analyzer.py` to retune.

## Troubleshooting

**Ticker fails to fetch** — yfinance occasionally lags on new listings.
For Tata Gold ETF specifically, if `TATAGOLD.NS` doesn't return data, swap
in `GOLDBEES.NS` as a proxy (same underlying).

**Mutual fund returns 404** — wrong scheme code. Use
`search_mf_scheme("fund name")` to find the right one.

**Nexus Select Trust shows NaN** — try `NXST-RR.NS` (Yahoo's alternate symbol).

**Beta is always NaN for one asset** — it has fewer than 30 overlapping days
with Nifty. Increase `period` to `"3y"` or `"5y"`.
