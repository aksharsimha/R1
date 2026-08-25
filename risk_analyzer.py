"""
Portfolio Risk Analyzer
=======================
Risk + P&L analysis and live monitoring for a mixed Indian portfolio
(listed equities, ETFs, mutual funds, digital gold).

Data sources
------------
- Equities/ETFs : yfinance       (NSE: TICKER.NS, BSE: TICKER.BO)
- Mutual funds  : api.mfapi.in   (AMFI scheme codes)
- Digital gold  : GOLDBEES.NS    (Nippon India Gold ETF as 24K-gold proxy)

Built for Akshar / ARA / WealthQuest.
"""

from __future__ import annotations

import json
import os
import time
import warnings
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import requests
import yfinance as yf

try:
    from nse_live import get_live_price, is_market_open, get_market_status
    _HAS_NSE_LIVE = True
except ImportError:
    _HAS_NSE_LIVE = False

try:
    import streamlit as st
    _cache = st.cache_data(ttl=180, show_spinner=False)
except ImportError:
    _cache = lambda f: f

warnings.filterwarnings("ignore")

# =====================================================================
# Constants
# =====================================================================
TRADING_DAYS = 252
RISK_FREE_RATE = 0.07              # India ~10y G-sec proxy
BENCHMARK = "^NSEI"                # Nifty 50
GOLD_PROXY = "GOLDBEES.NS"         # for PhonePe digital gold
MFAPI_BASE = "https://api.mfapi.in/mf"

# Component weights for the composite risk score (must sum to 1.0)
WEIGHTS = {
    "volatility": 0.20,
    "beta":       0.10,
    "drawdown":   0.20,
    "sharpe":     0.15,
    "var":        0.10,
    "rsi":        0.10,
    "distance":   0.15,
}


# =====================================================================
# Asset model
# =====================================================================
class AssetType:
    EQUITY       = "equity"
    ETF          = "etf"
    MUTUAL_FUND  = "mf"
    DIGITAL_GOLD = "gold"


@dataclass
class Asset:
    name: str               # human-readable
    asset_type: str         # one of AssetType.*
    identifier: str         # ticker / scheme code / "" for digital gold
    amount: float = 0.0     # ₹ invested
    quantity: float = 0.0   # number of units/shares

    @property
    def is_listed(self) -> bool:
        return self.asset_type in (AssetType.EQUITY, AssetType.ETF)


# =====================================================================
# Data fetchers
# =====================================================================
@_cache
def fetch_listed_history(ticker: str, period: str = "2y") -> pd.DataFrame:
    """Fetch OHLCV via yfinance for a listed ticker."""
    df = yf.download(ticker, period=period, progress=False,
                     auto_adjust=True, multi_level_index=False)
    if df is None or df.empty:
        raise ValueError(f"No data returned for {ticker}")
    return df


@_cache
def fetch_mf_history(scheme_code, lookback_years: float = 2) -> pd.DataFrame:
    """Fetch NAV history for an Indian MF via api.mfapi.in.

    Returns OHLCV-shaped DataFrame (Open=High=Low=Close=NAV, Volume=0).
    """
    url = f"{MFAPI_BASE}/{scheme_code}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    data = r.json()
    if "data" not in data or not data["data"]:
        raise ValueError(f"No NAV data for scheme {scheme_code}")

    df = pd.DataFrame(data["data"])
    df["date"] = pd.to_datetime(df["date"], format="%d-%m-%Y")
    df["nav"]  = df["nav"].astype(float)
    df = df.sort_values("date").set_index("date")

    cutoff = datetime.now() - timedelta(days=int(365 * lookback_years))
    df = df[df.index >= cutoff]

    df = df.rename(columns={"nav": "Close"})
    df["Open"] = df["High"] = df["Low"] = df["Close"]
    df["Volume"] = 0
    return df[["Open", "High", "Low", "Close", "Volume"]]


def search_mf_scheme(query: str, n: int = 10) -> pd.DataFrame:
    """Search AMFI scheme codes by name. Use to find scheme_code for your funds."""
    r = requests.get(f"{MFAPI_BASE}/search", params={"q": query}, timeout=15)
    r.raise_for_status()
    return pd.DataFrame(r.json()).head(n)


def fetch_history(asset: Asset, period: str = "2y") -> pd.DataFrame:
    """Unified history fetcher across asset types."""
    if asset.asset_type == AssetType.MUTUAL_FUND:
        years = {"6mo": 0.5, "1y": 1, "2y": 2, "3y": 3, "5y": 5}.get(period, 2)
        return fetch_mf_history(asset.identifier, lookback_years=years)
    if asset.asset_type == AssetType.DIGITAL_GOLD:
        return fetch_listed_history(GOLD_PROXY, period)
    return fetch_listed_history(asset.identifier, period)


def get_current_price(asset: Asset, hist_close: float = None,
                      prefetched: Optional[Dict[str, tuple]] = None) -> tuple:
    """Get the best available live price for an asset.

    If prefetched prices are provided (from batch fetch), uses those
    instead of making individual HTTP calls.

    Args:
        asset: The Asset to get the price for.
        hist_close: Last historical close price (fallback).
        prefetched: Optional dict of {ticker: (price, source)} from batch fetch.

    Returns:
        Tuple of (price: float, source: str).
        Source is one of: 'nse_live', 'yfinance', 'historical', 'mfapi'.
    """
    # Mutual funds don't trade on NSE — use historical NAV
    if asset.asset_type == AssetType.MUTUAL_FUND:
        return (hist_close or 0.0), "mfapi"

    # For listed equities/ETFs/gold, try live sources
    ticker = asset.identifier
    if asset.asset_type == AssetType.DIGITAL_GOLD:
        ticker = GOLD_PROXY

    # Use pre-fetched price if available (fast path — no HTTP call)
    if prefetched and ticker in prefetched:
        price, source = prefetched[ticker]
        if price is not None:
            return price, source

    # Fallback: individual fetch (only if not pre-fetched)
    if _HAS_NSE_LIVE:
        price, source = get_live_price(ticker, allow_yf_fallback=True)
        if price is not None:
            return price, source

    # Final fallback: last historical close
    return (hist_close or 0.0), "historical"


def batch_fetch_live_prices(assets: List[Asset]) -> Dict[str, tuple]:
    """Batch-fetch live prices for all listed assets upfront.

    This is called ONCE before the analysis loop to avoid sequential
    HTTP calls inside analyze_asset().

    Returns:
        Dict of {ticker: (price, source)} for each asset.
    """
    results: Dict[str, tuple] = {}
    if not _HAS_NSE_LIVE:
        return results

    tickers = []
    for a in assets:
        if a.asset_type == AssetType.MUTUAL_FUND:
            continue  # MFs don't use NSE
        ticker = a.identifier
        if a.asset_type == AssetType.DIGITAL_GOLD:
            ticker = GOLD_PROXY
        if ticker not in tickers:
            tickers.append(ticker)

    if not tickers:
        return results

    def _fetch(ticker: str):
        try:
            price, source = get_live_price(ticker, allow_yf_fallback=True)
            if price is not None:
                return ticker, (price, source)
        except Exception:
            pass  # Will fall back to historical in get_current_price
        return ticker, None

    # Fetch concurrently. The NSE session serializes at the network layer
    # via its own lock, but DNS/parse/yfinance-fallback overhead overlaps,
    # cutting total wait from ~N×gap to roughly the slowest single call.
    max_workers = min(8, len(tickers))
    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = [pool.submit(_fetch, t) for t in tickers]
        for fut in as_completed(futures):
            ticker, value = fut.result()
            if value is not None:
                results[ticker] = value

    return results


# =====================================================================
# Historical risk metrics
# =====================================================================
def annualized_volatility(returns: pd.Series) -> float:
    return float(returns.std() * np.sqrt(TRADING_DAYS))


def beta(stock_returns: pd.Series, market_returns: pd.Series) -> float:
    aligned = pd.concat([stock_returns, market_returns], axis=1, join="inner").dropna()
    if len(aligned) < 30:
        return float("nan")
    cov = aligned.cov().iloc[0, 1]
    var = aligned.iloc[:, 1].var()
    return float(cov / var) if var > 0 else float("nan")


def max_drawdown(prices: pd.Series) -> float:
    cum_max = prices.cummax()
    return float(((prices - cum_max) / cum_max).min())


def sharpe_ratio(returns: pd.Series, rf: float = RISK_FREE_RATE) -> float:
    vol = annualized_volatility(returns)
    if vol == 0 or np.isnan(vol):
        return float("nan")
    excess = returns.mean() * TRADING_DAYS - rf
    return float(excess / vol)


def historical_var(returns: pd.Series, confidence: float = 0.95) -> float:
    return float(np.percentile(returns.dropna(), (1 - confidence) * 100))


def conditional_var(returns: pd.Series, confidence: float = 0.95) -> float:
    var = historical_var(returns, confidence)
    tail = returns[returns <= var]
    return float(tail.mean()) if len(tail) > 0 else float("nan")


# =====================================================================
# P&L metrics
# =====================================================================
def total_return(prices: pd.Series) -> float:
    if len(prices) < 2:
        return float("nan")
    return float((prices.iloc[-1] / prices.iloc[0] - 1) * 100)


def annualized_return(prices: pd.Series) -> float:
    if len(prices) < 2:
        return float("nan")
    days = (prices.index[-1] - prices.index[0]).days
    if days <= 0:
        return float("nan")
    years = days / 365.25
    total = prices.iloc[-1] / prices.iloc[0]
    if total <= 0:
        return float("nan")
    return float((total ** (1 / years) - 1) * 100)


def profit_factor(returns: pd.Series) -> float:
    """Sum of positive returns / |sum of negative returns|. Higher = better."""
    gains  = returns[returns > 0].sum()
    losses = -returns[returns < 0].sum()
    if losses == 0:
        return float("inf") if gains > 0 else float("nan")
    return float(gains / losses)


def win_rate(returns: pd.Series) -> float:
    nz = returns[returns != 0].dropna()
    if len(nz) == 0:
        return float("nan")
    return float((nz > 0).sum() / len(nz) * 100)


# =====================================================================
# Live indicators
# =====================================================================
def rsi(prices: pd.Series, period: int = 14) -> float:
    delta = prices.diff()
    gain  = delta.where(delta > 0, 0)
    loss  = -delta.where(delta < 0, 0)
    avg_g = gain.ewm(span=period, adjust=False).mean()
    avg_l = loss.ewm(span=period, adjust=False).mean()
    rs    = avg_g / avg_l.replace(0, np.nan)
    series = 100 - 100 / (1 + rs)
    return float(series.iloc[-1])


def position_in_52w(prices: pd.Series) -> float:
    last_year = prices.tail(252)
    high, low = last_year.max(), last_year.min()
    if high == low:
        return 0.5
    return float((prices.iloc[-1] - low) / (high - low))


def distance_from_ma(prices: pd.Series, window: int) -> float:
    if len(prices) < window:
        return float("nan")
    ma = prices.rolling(window).mean().iloc[-1]
    return float((prices.iloc[-1] - ma) / ma * 100)


# =====================================================================
# Scoring (each component → 0–100, higher = riskier)
# =====================================================================
def _clip(x, lo=0, hi=100):
    return float(max(min(x, hi), lo))


def score_volatility(vol):
    if np.isnan(vol): return 50.0
    if vol < 0.15: return _clip(15 + (vol / 0.15) * 15)
    if vol < 0.30: return _clip(30 + ((vol - 0.15) / 0.15) * 30)
    if vol < 0.50: return _clip(60 + ((vol - 0.30) / 0.20) * 30)
    return _clip(90 + (vol - 0.50) * 40)


def score_beta(b):
    if np.isnan(b): return 50.0
    if b < 0.5:  return 25.0
    if b < 1.0:  return _clip(25 + (b - 0.5) * 60)
    if b < 1.5:  return _clip(55 + (b - 1.0) * 40)
    return _clip(75 + (b - 1.5) * 30)


def score_drawdown(dd):
    if np.isnan(dd): return 50.0
    a = abs(dd)
    if a < 0.10: return _clip(15 + a * 100)
    if a < 0.30: return _clip(25 + (a - 0.10) * 200)
    return _clip(65 + (a - 0.30) * 100)


def score_sharpe(s):
    if np.isnan(s): return 60.0
    if s > 1.5: return 15.0
    if s > 1.0: return 25.0
    if s > 0.5: return 40.0
    if s > 0.0: return 60.0
    return 85.0


def score_var(v):
    if np.isnan(v): return 50.0
    a = abs(v)
    if a < 0.015: return 25.0
    if a < 0.025: return 45.0
    if a < 0.040: return 65.0
    return _clip(80 + (a - 0.04) * 200)


def score_rsi(r):
    if np.isnan(r): return 40.0
    if r > 75: return 75.0
    if r > 65: return 55.0
    if r < 25: return 70.0
    if r < 35: return 50.0
    return 30.0


def score_distance(d50, d200):
    if np.isnan(d200): return 50.0
    if d200 < -10: return 80.0
    if d200 < 0:   return 65.0
    if d200 > 30:  return 70.0
    return 35.0


def bucket(score: float) -> str:
    if score < 35: return "LOW"
    if score < 55: return "MODERATE"
    if score < 75: return "HIGH"
    return "SEVERE"


# =====================================================================
# Per-asset analysis
# =====================================================================
@dataclass
class StockReport:
    name: str
    identifier: str
    asset_type: str
    invested_amount: float
    quantity: float
    last_price: float
    current_value: float
    pnl_abs: float
    pnl_perc: float

    volatility: float
    beta: float
    max_dd: float
    sharpe: float
    var_95: float
    cvar_95: float

    total_return: float
    ann_return: float
    ret_1m: float
    ret_6m: float
    ret_1y: float
    profit_factor: float
    win_rate: float

    rsi: float
    pos_52w: float
    dist_50dma: float
    dist_200dma: float

    risk_score: float
    risk_bucket: str
    components: Dict[str, float] = field(default_factory=dict)
    price_source: str = "historical"  # 'nse_live', 'yfinance', 'historical', 'mfapi'
    timestamp: str = ""


def analyze_asset(asset: Asset,
                  period: str = "2y",
                  market_df: Optional[pd.DataFrame] = None,
                  prefetched_prices: Optional[Dict[str, tuple]] = None) -> StockReport:
    """Run full analysis on one asset."""
    df = fetch_history(asset, period=period)
    prices = df["Close"]
    returns = prices.pct_change().dropna()

    # Beta only meaningful for equity-like vs Nifty
    if (market_df is None
        or asset.asset_type in (AssetType.MUTUAL_FUND, AssetType.DIGITAL_GOLD)):
        beta_val = float("nan")
    else:
        market_returns = market_df["Close"].pct_change().dropna()
        beta_val = beta(returns, market_returns)

    vol  = annualized_volatility(returns)
    dd   = max_drawdown(prices)
    sr   = sharpe_ratio(returns)
    var  = historical_var(returns)
    cvar = conditional_var(returns)

    tr   = total_return(prices)
    ar   = annualized_return(prices)
    
    def get_ret(p, days):
        if len(p) > days:
            return float((p.iloc[-1] / p.iloc[-days-1] - 1) * 100)
        return float('nan')
        
    r_1m = get_ret(prices, 21)
    r_6m = get_ret(prices, 126)
    r_1y = get_ret(prices, 252)
    
    pf   = profit_factor(returns)
    wr   = win_rate(returns)

    rsi_v  = rsi(prices)
    pos52  = position_in_52w(prices)
    d50    = distance_from_ma(prices, 50)
    d200   = distance_from_ma(prices, 200)

    components = {
        "volatility": score_volatility(vol),
        "beta":       score_beta(beta_val) if not np.isnan(beta_val) else 50,
        "drawdown":   score_drawdown(dd),
        "sharpe":     score_sharpe(sr),
        "var":        score_var(var),
        "rsi":        score_rsi(rsi_v),
        "distance":   score_distance(d50, d200),
    }
    risk_score = sum(components[k] * WEIGHTS[k] for k in WEIGHTS)

    # Use real-time NSE price for current valuation (falls back gracefully)
    hist_close = float(prices.iloc[-1])
    live_price, price_source = get_current_price(asset, hist_close=hist_close,
                                                  prefetched=prefetched_prices)
    curr_val = asset.quantity * live_price
    pnl_abs = curr_val - asset.amount
    pnl_perc = (pnl_abs / asset.amount * 100) if asset.amount > 0 else 0.0

    return StockReport(
        name=asset.name, identifier=asset.identifier,
        asset_type=asset.asset_type, 
        invested_amount=asset.amount, quantity=asset.quantity,
        last_price=live_price, price_source=price_source,
        current_value=curr_val, pnl_abs=pnl_abs, pnl_perc=pnl_perc,
        volatility=vol, beta=beta_val, max_dd=dd, sharpe=sr,
        var_95=var, cvar_95=cvar,
        total_return=tr, ann_return=ar,
        ret_1m=r_1m, ret_6m=r_6m, ret_1y=r_1y,
        profit_factor=pf, win_rate=wr,
        rsi=rsi_v, pos_52w=pos52,
        dist_50dma=d50, dist_200dma=d200,
        risk_score=risk_score, risk_bucket=bucket(risk_score),
        components=components,
        timestamp=datetime.now().isoformat(timespec="seconds"),
    )


# =====================================================================
# Portfolio analysis
# =====================================================================

def get_portfolio_growth(df: pd.DataFrame, summary: dict) -> dict:
    """Calculate centralized growth metrics to ensure UI consistency."""
    total_invested = df['Invested (₹)'].sum() if df is not None and not df.empty else 0.0
    total_value = summary.get('total_value', 0.0)
    growth_abs = total_value - total_invested
    growth_pct = (growth_abs / total_invested * 100) if total_invested > 0 else 0.0
    return {
        "invested": total_invested,
        "current": total_value,
        "growth_abs": growth_abs,
        "growth_pct": growth_pct
    }

def analyze_portfolio(assets: List[Asset], period: str = "2y",
                      verbose: bool = True,
                      prefetched_prices: Optional[Dict[str, tuple]] = None
                      ) -> Tuple[pd.DataFrame, Dict[str, Any]]:
    """Run analysis on every asset and aggregate to portfolio level.

    Returns:
        df       : DataFrame, one row per asset, sorted by Risk Score desc
        summary  : dict with portfolio-wide metrics
    """
    if verbose:
        print(f"Fetching benchmark ({BENCHMARK})...")
    try:
        market_df = fetch_listed_history(BENCHMARK, period=period)
    except Exception as e:
        print(f"  ⚠️  Benchmark fetch failed ({e}). Beta will be NaN.")
        market_df = None

    # Batch-fetch all NSE live prices UPFRONT (one pass, ~5s total)
    # This avoids sequential HTTP calls inside the per-asset loop.
    # If prefetched_prices are provided (from app.py session_state cache),
    # use those instead of fetching again.
    if prefetched_prices is not None:
        prefetched = prefetched_prices
    else:
        if verbose:
            print("  Fetching live prices from NSE...")
        prefetched = batch_fetch_live_prices(assets)
        if verbose:
            print(f"  Got {len(prefetched)} live prices.")

    reports = []
    price_history: Dict[str, pd.Series] = {}

    for a in assets:
        try:
            if verbose:
                print(f"  Analyzing {a.name}...")
            r = analyze_asset(a, period=period, market_df=market_df,
                              prefetched_prices=prefetched)
            reports.append(r)
            df_h = fetch_history(a, period=period)
            price_history[a.name] = df_h["Close"]
        except Exception as e:
            print(f"  ⚠️  Failed: {a.name} ({a.identifier}) → {e}")

    rows = []
    for r in reports:
        rows.append({
            "Name": r.name, "Type": r.asset_type,
            "Invested (₹)": r.invested_amount, "Quantity": r.quantity, 
            "Current Value (₹)": r.current_value,
            "P&L (₹)": r.pnl_abs, "P&L %": r.pnl_perc,
            "Last Price": r.last_price,
            "Price Source": r.price_source,
            "Volatility %": r.volatility * 100,
            "Beta": r.beta,
            "Max DD %": r.max_dd * 100,
            "Sharpe": r.sharpe,
            "1d VaR %": r.var_95 * 100,
            "1M Ret %": r.ret_1m,
            "6M Ret %": r.ret_6m,
            "1Y Ret %": r.ret_1y,
            "Total Return %": r.total_return,
            "Ann Return %": r.ann_return,
            "Profit Factor": r.profit_factor,
            "Win Rate %": r.win_rate,
            "RSI": r.rsi,
            "52w Pos": r.pos_52w,
            "Dist 200DMA %": r.dist_200dma,
            "Risk Score": r.risk_score,
            "Risk Bucket": r.risk_bucket,
        })

    df = pd.DataFrame(rows)
    if df.empty:
        return df, {"error": "No assets could be analyzed"}

    df = df.sort_values("Risk Score", ascending=False).reset_index(drop=True)
    df.insert(0, "Risk Rank", df.index + 1)

    total_value = df["Current Value (₹)"].sum()
    df["Weight %"] = (df["Current Value (₹)"] / total_value * 100) if total_value > 0 else 0.0

    if total_value > 0:
        portfolio_score = float((df["Risk Score"] * df["Weight %"] / 100).sum())
    else:
        portfolio_score = float(df["Risk Score"].mean())

    # Correlation + portfolio vol + diversification ratio + PCA (Eigenvalues)
    if len(price_history) > 1:
        prices_df = pd.concat(price_history.values(), axis=1, join="inner")
        prices_df.columns = list(price_history.keys())
        returns_df = prices_df.pct_change().dropna()
        corr = returns_df.corr()
        
        # PCA / Eigenvalue calculation
        cov_daily = returns_df.cov()
        try:
            eigenvalues, eigenvectors = np.linalg.eigh(cov_daily)
            # eigh returns ascending, reverse for descending (largest first)
            eigenvalues = eigenvalues[::-1]
            eigenvectors = eigenvectors[:, ::-1]
            total_eigen_var = np.sum(eigenvalues)
            explained_var = (eigenvalues / total_eigen_var) if total_eigen_var > 0 else np.zeros_like(eigenvalues)
        except Exception:
            eigenvalues = np.array([])
            explained_var = np.array([])
            eigenvectors = np.array([])
    else:
        returns_df = pd.DataFrame()
        corr = pd.DataFrame()
        eigenvalues = np.array([])
        explained_var = np.array([])
        eigenvectors = np.array([])

    if len(price_history) > 1 and total_value > 0:
        weights = (df.set_index("Name")["Current Value (₹)"] / total_value).to_dict()
        wvec = np.array([weights.get(n, 0) for n in returns_df.columns])
        weighted_vol = float(np.sum(wvec * returns_df.std() * np.sqrt(TRADING_DAYS)))
        cov_matrix = returns_df.cov() * TRADING_DAYS
        port_vol = float(np.sqrt(wvec @ cov_matrix.values @ wvec))
        div_ratio = weighted_vol / port_vol if port_vol > 0 else float("nan")
    else:
        port_vol = float("nan")
        div_ratio = float("nan")

    herfindahl = float(((df["Current Value (₹)"] / total_value) ** 2).sum()) if total_value > 0 else float("nan")

    # Weighted P&L: how the portfolio would have performed
    if total_value > 0:
        weighted_total_return = float((df["Total Return %"] * df["Weight %"] / 100).sum())
        weighted_ann_return   = float((df["Ann Return %"]   * df["Weight %"] / 100).sum())
    else:
        weighted_total_return = float("nan")
        weighted_ann_return = float("nan")

    # Determine dominant price source for the UI
    source_counts = {}
    for r in reports:
        source_counts[r.price_source] = source_counts.get(r.price_source, 0) + 1
    dominant_source = max(source_counts, key=source_counts.get) if source_counts else "historical"

    # Market status
    if _HAS_NSE_LIVE:
        _mkt_status = get_market_status()
        _mkt_open = is_market_open()
    else:
        _mkt_status = "Unknown"
        _mkt_open = False

    summary = {
        "total_value":              total_value,
        "n_assets":                 len(reports),
        "portfolio_risk_score":     portfolio_score,
        "portfolio_risk_bucket":    bucket(portfolio_score),
        "portfolio_volatility":     port_vol,
        "diversification_ratio":    div_ratio,
        "concentration_hhi":        herfindahl,
        "weighted_total_return":    weighted_total_return,
        "weighted_ann_return":      weighted_ann_return,
        "correlation_matrix":       corr,
        "returns_df":               returns_df,
        "pca_eigenvalues":          eigenvalues,
        "pca_explained_var":        explained_var,
        "pca_eigenvectors":         eigenvectors,
        "price_sources":            source_counts,
        "dominant_source":          dominant_source,
        "market_status":            _mkt_status,
        "market_open":              _mkt_open,
        "as_of":                    datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    return df, summary


# =====================================================================
# Holdings persistence + live monitor
# =====================================================================
def load_holdings(path: str) -> List[Asset]:
    with open(path) as f:
        data = json.load(f)
    return [Asset(**item) for item in data["holdings"]]


def save_holdings(assets: List[Asset], path: str) -> None:
    with open(path, "w") as f:
        json.dump({"holdings": [asdict(a) for a in assets]}, f, indent=2)


def _format_dashboard(df: pd.DataFrame, summary: Dict[str, Any], iteration: int) -> str:
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    lines = []
    lines.append("┌" + "─" * 90 + "┐")
    lines.append(f"│  PORTFOLIO RISK MONITOR  ·  refresh #{iteration}  ·  {ts}".ljust(91) + "│")
    lines.append("└" + "─" * 90 + "┘")

    cols = ["Risk Rank", "Name", "Amount (₹)", "Weight %",
            "Last Price", "Total Return %", "Profit Factor",
            "Risk Score", "Risk Bucket"]
    cols = [c for c in cols if c in df.columns]
    lines.append("")
    lines.append(df[cols].round(2).to_string(index=False))

    lines.append("")
    lines.append("PORTFOLIO SUMMARY")
    lines.append(f"  Total value         : ₹{summary['total_value']:>14,.2f}")
    lines.append(f"  Risk score          : {summary['portfolio_risk_score']:>6.1f}  ({summary['portfolio_risk_bucket']})")
    lines.append(f"  Portfolio vol (ann) : {summary['portfolio_volatility']*100:>6.2f}%"
                 if not np.isnan(summary['portfolio_volatility']) else
                 "  Portfolio vol (ann) :    n/a")
    lines.append(f"  Diversification     : {summary['diversification_ratio']:>6.2f}"
                 if not np.isnan(summary['diversification_ratio']) else
                 "  Diversification     :    n/a")
    lines.append(f"  Concentration (HHI) : {summary['concentration_hhi']:>6.3f}"
                 if not np.isnan(summary['concentration_hhi']) else
                 "  Concentration (HHI) :    n/a")
    lines.append(f"  Weighted total ret  : {summary['weighted_total_return']:>6.2f}%")
    lines.append(f"  Weighted ann ret    : {summary['weighted_ann_return']:>6.2f}%")
    return "\n".join(lines)


def live_monitor(
    assets: Optional[List[Asset]] = None,
    holdings_file: Optional[str] = None,
    period: str = "2y",
    interval_seconds: int = 60,
    n_iterations: Optional[int] = None,
    use_clear_output: bool = True,
):
    """
    Live monitoring loop.

    Args:
        assets           : initial list of Asset objects (ignored if holdings_file given)
        holdings_file    : path to a JSON file. Edit it any time and the next refresh
                           will pick up new amounts.
        period           : history lookback ('1y','2y','5y',...)
        interval_seconds : seconds between refreshes
        n_iterations     : stop after N iterations (None = forever, Ctrl+C to stop)
        use_clear_output : True for Jupyter (in-place update), False for terminal
    """
    if holdings_file is None and assets is None:
        raise ValueError("Provide either `holdings_file` or `assets`")

    iteration = 0
    while True:
        iteration += 1

        if holdings_file:
            try:
                assets = load_holdings(holdings_file)
            except Exception as e:
                print(f"⚠️ Could not load {holdings_file}: {e}")

        # Clear screen
        if use_clear_output:
            try:
                from IPython.display import clear_output
                clear_output(wait=True)
            except ImportError:
                os.system("cls" if os.name == "nt" else "clear")
        else:
            os.system("cls" if os.name == "nt" else "clear")

        try:
            df, summary = analyze_portfolio(assets, period=period, verbose=False)
            print(_format_dashboard(df, summary, iteration))
        except Exception as e:
            print(f"⚠️  Analysis failed this cycle: {e}")

        if holdings_file:
            print(f"\nEdit {holdings_file} to update amounts. Next refresh in {interval_seconds}s. Ctrl+C to stop.")
        else:
            print(f"\nNext refresh in {interval_seconds}s. Ctrl+C to stop.")

        if n_iterations and iteration >= n_iterations:
            break

        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n\nStopped.")
            break


# =====================================================================
# Default portfolio (Akshar's holdings) — amounts are placeholders
# =====================================================================
DEFAULT_PORTFOLIO = [
    Asset("Motilal Nasdaq 100 ETF", AssetType.ETF,    "MON100.NS",     0),
    Asset("REC Limited",            AssetType.EQUITY, "RECLTD.NS",     0),
    Asset("Jio Financial Services", AssetType.EQUITY, "JIOFIN.NS",     0),
    Asset("Tata Steel",             AssetType.EQUITY, "TATASTEEL.NS",  0),
    Asset("Eternal (Zomato)",       AssetType.EQUITY, "ETERNAL.NS",    0),
    Asset("IRCTC",                  AssetType.EQUITY, "IRCTC.NS",      0),
    Asset("Coal India",             AssetType.EQUITY, "COALINDIA.NS",  0),
    Asset("Nexus Select Trust",     AssetType.ETF,    "NXST.NS",       0),
    Asset("Silver BeES",            AssetType.ETF,    "SILVERBEES.NS", 0),
    Asset("Tata Gold ETF",          AssetType.ETF,    "TATAGOLD.NS",   0),
    Asset("PhonePe Gold (proxy)",   AssetType.DIGITAL_GOLD, "",        0),
    # Mutual funds — VERIFY scheme codes via search_mf_scheme() before relying on them
    Asset("HDFC Flexi Cap (Direct G)",        AssetType.MUTUAL_FUND, "119551", 0),
    Asset("HDFC Nifty 50 Index (Direct G)",   AssetType.MUTUAL_FUND, "147622", 0),
    Asset("Nippon Smallcap 250 Index (DG)",   AssetType.MUTUAL_FUND, "147625", 0),
]


# =====================================================================
# Recommendations Engine
# =====================================================================
def generate_recommendations(df: pd.DataFrame, summary: Dict[str, Any]) -> List[Dict[str, str]]:
    """Generates a list of actionable insights based on the analyzed portfolio dataframe, with step-by-step math."""
    recs = []
    
    if df.empty:
        return [{"header": "Add some assets to your portfolio to get recommendations.", "math": "", "type": "info"}]

    # 4. Correlation check (Portfolio Level)
    corr_matrix = summary.get("correlation_matrix", pd.DataFrame())
    if not corr_matrix.empty and len(corr_matrix.columns) > 1:
        # Find highly correlated pairs
        pairs = []
        for i in range(len(corr_matrix.columns)):
            for j in range(i+1, len(corr_matrix.columns)):
                c = corr_matrix.iloc[i, j]
                if c > 0.85:
                    pairs.append((corr_matrix.columns[i], corr_matrix.columns[j], c))
        
        for asset1, asset2, c in pairs:
            recs.append({
                "type": "warning",
                "header": f"🔗 **{asset1} & {asset2} (Fake Diversification)**: These two assets are highly correlated. Consider picking the better-performing one and selling the other.",
                "math": (
                    f"**The Math:** `Pearson Correlation Coefficient (r) = {c:.3f}` (or {c*100:.1f}%). This is calculated as `Covariance(A, B) / (StdDev(A) * StdDev(B))`.\n\n"
                    f"**Impact:** Since `r > 0.85`, they move up and down together almost identically. Holding both does not actually diversify your risk; it essentially doubles your exposure to the exact same market forces."
                )
            })

    for _, row in df.iterrows():
        name = row["Name"]
        score = row["Risk Score"]
        bucket = row["Risk Bucket"]
        weight = row["Weight %"]
        d200 = row["Dist 200DMA %"]
        vol = row.get("Volatility %", 0)
        dd = row.get("Max DD %", 0)
        sharpe = row.get("Sharpe", 0)
        price = row.get("Last Price", 0)
        asset_val = row.get("Current Value (₹)", 0)
        total_val = summary.get("total_value", 0)
        
        # 1. Extreme Risk
        if bucket == "SEVERE" and weight > 0:
            recs.append({
                "type": "warning",
                "header": f"⚠️ **{name} (Critical Risk)**: This asset has a dangerously high Risk Score of **{score:.1f}/100**. Strongly consider exiting this position, or strictly limiting it to less than 2%.",
                "math": (
                    f"**The Math:** Calculated via a weighted matrix: `(20% × Volatility [{vol:.1f}%]) + (20% × Max Drawdown [{dd:.1f}%]) + (15% × Sharpe Ratio [{sharpe:.2f}]) + (45% × Other Factors)`.\n\n"
                    f"**Impact:** The underlying math reveals extreme historical price swings. Holding this exposes your portfolio to sudden large losses."
                )
            })
        elif bucket == "HIGH" and weight > 15.0:
            recs.append({
                "type": "warning",
                "header": f"✂️ **{name} (High Risk & Overweight)**: This asset takes up a massive **{weight:.1f}%** of your portfolio while carrying a High Risk Score ({score:.1f}/100). Consider trimming to reduce exposure to 5-10%.",
                "math": (
                    f"**The Math:** Checks if `Risk Score ({score:.1f}) > 55 (Threshold)` AND `Weight ({weight:.1f}%) > 15% (Threshold)`.\n\n"
                    f"**Impact:** It has high historical volatility (Vol: {vol:.1f}%, Max Drop: {dd:.1f}%). If this single stock crashes, its sheer size in your portfolio will drag your entire net worth down significantly."
                )
            })
            
        # 2. Negative Momentum
        if d200 < -15.0 and weight > 0:
            # Reverse calculate 200DMA to show the math
            ma200 = price / (1 + d200 / 100.0) if price > 0 else 0
            recs.append({
                "type": "warning",
                "header": f"📉 **{name} (Negative Trend/Momentum)**: This asset is heavily underperforming its long-term average. Do not 'buy the dip' yet; wait for the trend to reverse.",
                "math": (
                    f"**The Math:** `200-Day Moving Average = ₹{ma200:,.2f}`. `Current Price = ₹{price:,.2f}`.\n"
                    f"`Distance = (Current - Average) / Average = (₹{price:,.2f} - ₹{ma200:,.2f}) / ₹{ma200:,.2f} * 100 = {d200:.1f}%`.\n\n"
                    f"**Impact:** Falling more than 15% below its 200-Day average is a mathematical indicator of a confirmed downtrend and heavy institutional selling."
                )
            })
            
        # 3. Over-concentration
        if weight > 30.0:
            recs.append({
                "type": "warning",
                "header": f"⚖️ **{name} (Dangerous Concentration)**: Your portfolio is heavily reliant on this one asset. Rebalance by taking some capital out and reinvesting into low-risk index funds or gold.",
                "math": (
                    f"**The Math:** `Weight = (Asset Value / Total Portfolio) * 100 = (₹{asset_val:,.2f} / ₹{total_val:,.2f}) * 100 = {weight:.1f}%`.\n\n"
                    f"**Impact:** Since {weight:.1f}% > 30% (our mathematical safety threshold), a 10% drop in this single asset alone wipes out {weight * 0.10:.1f}% of your entire portfolio's value."
                )
            })

    if not recs:
        recs.append({
            "type": "success",
            "header": "✅ **Portfolio is Mathematically Sound!** Your portfolio looks well-balanced right now. None of your current holdings trigger our quantitative risk, momentum, or concentration warnings.",
            "math": ""
        })
        
    return recs


if __name__ == "__main__":
    df, summary = analyze_portfolio(DEFAULT_PORTFOLIO, period="2y")
    print(df.round(2).to_string(index=False))
    print()
    print(f"Portfolio risk: {summary['portfolio_risk_score']:.1f} ({summary['portfolio_risk_bucket']})")
