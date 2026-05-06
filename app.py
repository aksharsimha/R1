import streamlit as st
import pandas as pd
import os
import sys
import time
from datetime import datetime
import plotly.express as px
import plotly.graph_objects as go
import numpy as np
from risk_analyzer import analyze_portfolio, generate_recommendations, load_holdings, save_holdings, DEFAULT_PORTFOLIO, Asset, AssetType
from portfolio_ledger import get_transactions, update_asset_holdings, update_asset_percentage, add_asset, remove_asset, HOLDINGS_FILE
from portfolio_ledger import save_daily_prediction, evaluate_past_predictions, get_predictions, ewma_catchup, confirm_manual_close
from news_sentiment import get_asset_sentiment, get_archived_articles
from adaptive_engine import adaptive_forecast, get_learning_log, get_days_trained
from streamlit_autorefresh import st_autorefresh

# --- Page Config ---
st.set_page_config(page_title="Portfolio Risk Monitor", page_icon="📈", layout="wide")

import plotly.io as pio
import plotly.graph_objects as go
pio.templates["custom_neon"] = go.layout.Template(
    layout=go.Layout(
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="Inter", color="#94a3b8"),
        xaxis=dict(showgrid=False, zeroline=False),
        yaxis=dict(showgrid=True, gridcolor="rgba(255,255,255,0.06)", zeroline=False),
        colorway=['#38bdf8', '#a78bfa', '#34d399', '#fb923c', '#f472b6', '#facc15', '#60a5fa', '#4ade80', '#f87171', '#e879f9']
    )
)
pio.templates.default = "custom_neon"

if "show_risk_breakdown" not in st.session_state:
    st.session_state.show_risk_breakdown = False

# Custom CSS for aesthetics (Ultra Premium Dark Mode)
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap');
    
    html, body, [class*="css"] {
        font-family: 'Inter', sans-serif;
    }
    
    /* Background & Aurora Animation */
    .stApp {
        background-color: transparent !important;
        color: #e2e8f0;
    }
    html, body {
        background-color: #050510 !important;
    }
    
    .stApp::before {
        content: '';
        position: fixed;
        top: 0; left: 0; right: 0; bottom: 0;
        z-index: -1;
        background-image: 
            radial-gradient(600px circle at 0% 0%, rgba(76,29,149,0.15), transparent 60%),
            radial-gradient(600px circle at 100% 0%, rgba(6,78,59,0.12), transparent 60%),
            radial-gradient(600px circle at 50% 100%, rgba(30,58,138,0.1), transparent 60%);
        background-repeat: no-repeat;
        animation: aurora-move 20s ease-in-out infinite;
    }
    
    @keyframes aurora-move {
        0%, 100% { background-position: 0px 0px, 0px 0px, 0px 0px; }
        50% { background-position: 80px 80px, -80px 80px, 0px -80px; }
    }
    
    /* Hide specific streamlit header elements but keep toggle */
    #MainMenu {visibility: hidden;}
    .stDeployButton {display: none;}
    header { background: transparent !important; }
    
    /* Sidebar Styling */
    section[data-testid="stSidebar"] {
        background-color: rgba(0, 0, 0, 0.3) !important;
        backdrop-filter: blur(25px);
        border-right: 1px solid rgba(255, 255, 255, 0.06);
    }
    
    /* Sidebar Separators */
    section[data-testid="stSidebar"] hr {
        border-top: 1px solid rgba(255, 255, 255, 0.06);
        margin: 12px 0;
    }
    
    /* Inputs */
    .stTextInput input, .stNumberInput input, .stSelectbox > div[data-baseweb="select"] {
        background: rgba(255,255,255,0.06) !important;
        border: 1px solid rgba(255,255,255,0.1) !important;
        border-radius: 8px !important;
        color: #e2e8f0 !important;
    }
    
    /* Glassmorphism Cards (All stAlert, stMetric, dashboard-header, stDataFrame) */
    .dashboard-header, div[data-testid="stMetric"], div[data-testid="stDataFrame"], .stAlert {
        background: rgba(255, 255, 255, 0.04) !important;
        backdrop-filter: blur(20px) !important;
        -webkit-backdrop-filter: blur(20px) !important;
        border: 1px solid rgba(255, 255, 255, 0.08) !important;
        border-radius: 16px !important;
        transition: all 0.25s ease;
    }
    
    /* Metric Card Hover & Glow */
    div[data-testid="stMetric"]:hover, div[data-testid="stDataFrame"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 0 24px rgba(99, 179, 237, 0.12);
        border-color: rgba(255, 255, 255, 0.15) !important;
    }
    
    /* Hero Metric Top Borders using nth-of-type targeting */
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] { border-top: 3px solid #00ff87 !important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(2) div[data-testid="stMetric"] { border-top: 3px solid #7dd3fc !important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(3) div[data-testid="stMetric"] { 
        border-top: 3px solid #ff4d6d !important;
        cursor: pointer;
    }
    div[data-testid="stHorizontalBlock"]:nth-of-type(1) div[data-testid="column"]:nth-child(3) div[data-testid="stMetric"]:hover {
        box-shadow: 0 0 32px rgba(255, 77, 109, 0.2) !important;
    }
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(1) div[data-testid="stMetric"] { border-top: 3px solid rgba(255,255,255,0.3) !important; }
    div[data-testid="stHorizontalBlock"]:nth-of-type(2) div[data-testid="column"]:nth-child(2) div[data-testid="stMetric"] { border-top: 3px solid rgba(255,255,255,0.3) !important; }
    
    /* Typography & Monospace for Numbers */
    .dashboard-header {
        padding: 2.5rem 2rem;
        margin-bottom: 2rem;
        position: relative;
        overflow: hidden;
    }
    .dashboard-header h1 {
        font-size: 2.5rem;
        font-weight: 700;
        margin: 0;
        background: linear-gradient(90deg, #e2e8f0, #94a3b8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    .dashboard-header p {
        color: #94a3b8;
        font-size: 1.1rem;
        margin-top: 0.5rem;
    }
    
    div[data-testid="stMetricValue"], div[data-testid="stDataFrame"] table {
        font-family: 'JetBrains Mono', Courier, monospace !important;
    }
    
    div[data-testid="stMetricValue"] {
        font-size: 2.2rem !important;
        font-weight: 700 !important;
        color: #7dd3fc !important;
    }
    
    div[data-testid="stMetricLabel"] {
        font-size: 0.95rem !important;
        color: #94a3b8 !important;
        font-weight: 500 !important;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Positive / Negative P&L Colors */
    div[data-testid="stMetricDelta"] svg {
        display: none; /* Hide the default streamlit arrow to use purely colors */
    }
    div[data-testid="stMetricDelta"] > div {
        font-family: 'JetBrains Mono', Courier, monospace !important;
        font-weight: 600;
    }
    div[data-testid="stMetricDelta"][class*="positive"] > div {
        color: #00ff87 !important;
    }
    div[data-testid="stMetricDelta"][class*="negative"] > div {
        color: #ff4d6d !important;
    }
    
    /* Pill Style Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 12px;
        background-color: transparent;
        padding-bottom: 5px;
    }
    .stTabs [data-baseweb="tab"] {
        height: 40px;
        background-color: transparent;
        border-radius: 999px;
        color: #94a3b8;
        font-weight: 500;
        border: 1px solid rgba(255, 255, 255, 0.08);
        padding: 6px 16px;
        transition: all 0.25s ease;
    }
    .stTabs [aria-selected="true"] {
        background-color: rgba(255, 255, 255, 0.08) !important;
        color: #e2e8f0 !important;
        border: 1px solid rgba(255, 255, 255, 0.2) !important;
        box-shadow: 0 0 12px rgba(99, 179, 237, 0.15);
    }
    .stTabs [data-baseweb="tab-highlight"] {
        display: none !important;
    }
    
    /* Buttons */
    .stButton button, .stFormSubmitButton button {
        background: linear-gradient(135deg, #3b82f6, #6366f1) !important;
        border: none !important;
        border-radius: 8px !important;
        color: white !important;
        font-weight: 500 !important;
        padding: 0.6rem 1.2rem !important;
        transition: all 0.3s ease !important;
    }
    .stButton button:hover, .stFormSubmitButton button:hover {
        background: rgba(99, 179, 237, 0.15) !important;
        border-color: rgba(99, 179, 237, 0.4) !important;
        box-shadow: 0 0 15px rgba(99, 179, 237, 0.2) !important;
    }
    
    /* Plotly Chart Containers */
    div[data-testid="stPlotlyChart"] {
        background: transparent !important;
    }
    div[data-testid="stPlotlyChart"] > div {
        background: rgba(255,255,255,0.03) !important;
        border: 1px solid rgba(255,255,255,0.06) !important;
        border-radius: 12px !important;
        padding: 16px !important;
    }
    
    /* All DATA TABLES (stDataFrame uses glide-data-grid, but we style HTML fallback and headers) */
    div[data-testid="stDataFrame"] {
        border-radius: 12px !important;
        overflow: hidden !important;
    }
    div[data-testid="stDataFrame"] table tbody tr { background: transparent !important; }
    div[data-testid="stDataFrame"] table tbody tr:nth-of-type(odd) { background: rgba(255,255,255,0.02) !important; }
    div[data-testid="stDataFrame"] table tbody tr:nth-of-type(even) { background: transparent !important; }
    div[data-testid="stDataFrame"] table tbody tr:hover { background: rgba(255,255,255,0.05) !important; }
    div[data-testid="stDataFrame"] table thead tr th {
        background: rgba(255,255,255,0.05) !important;
        color: #94a3b8 !important;
        font-size: 12px !important;
        letter-spacing: 0.05em !important;
        text-transform: uppercase !important;
    }
    div[data-testid="stDataFrame"] table th, div[data-testid="stDataFrame"] table td {
        border: 1px solid rgba(255,255,255,0.06) !important;
    }
</style>
""", unsafe_allow_html=True)

# Auto-refresh every 60 seconds
st_autorefresh(interval=60 * 1000, key="data_refresh")

# --- Sidebar: Interactive Controls ---
# NOTE: holdings.json is NEVER seeded here — it must exist on disk.
# If it is genuinely absent, load_holdings() below will raise a clear error.
st.sidebar.title("🛠️ Portfolio Manager")

# Load current assets for dropdowns
try:
    current_assets = load_holdings(HOLDINGS_FILE)
    asset_names = [a.name for a in current_assets]
except Exception:
    current_assets = []
    asset_names = []

action = st.sidebar.radio("Action", ["Update Amount", "Update Target %", "Add Asset", "Remove Asset"])

if action == "Update Amount":
    with st.sidebar.form("update_amount_form"):
        selected_asset = st.selectbox("Select Asset", asset_names)
        current_amt = next((a.amount for a in current_assets if a.name == selected_asset), 0.0) if current_assets else 0.0
        new_invested = st.number_input("Invested Amount (₹)", min_value=0.0, value=float(current_amt), step=100.0)
        current_qty = next((a.quantity for a in current_assets if a.name == selected_asset), 0.0) if current_assets else 0.0
        new_quantity = st.number_input("Quantity (Units)", min_value=0.0, value=float(current_qty), step=1.0)
        if st.form_submit_button("Update"):
            if update_asset_holdings(selected_asset, new_invested, new_quantity):
                st.sidebar.success(f"Updated {selected_asset}")
                time.sleep(1)
                st.rerun()

elif action == "Update Target %":
    with st.sidebar.form("update_perc_form"):
        st.write("Calculate required ₹ amount to match a target % of the portfolio.")
        selected_asset = st.selectbox("Select Asset", asset_names)
        target_perc = st.slider("Target Portfolio %", min_value=0.0, max_value=99.0, value=10.0, step=1.0)
        if st.form_submit_button("Update"):
            if update_asset_percentage(selected_asset, target_perc / 100.0):
                st.sidebar.success(f"Updated {selected_asset} to target {target_perc}%")
                time.sleep(1)
                st.rerun()

elif action == "Add Asset":
    with st.sidebar.form("add_asset_form"):
        new_name = st.text_input("Asset Name")
        new_type = st.selectbox("Asset Type", [AssetType.EQUITY, AssetType.ETF, AssetType.MUTUAL_FUND, AssetType.DIGITAL_GOLD])
        new_id = st.text_input("Identifier (Ticker/Code)", help="e.g. RELIANCE.NS, 119551")
        new_amount = st.number_input("Initial Amount (₹)", min_value=0.0, value=0.0, step=100.0)
        new_quantity = st.number_input("Quantity (Units)", min_value=0.0, value=0.0, step=1.0)
        if st.form_submit_button("Add Asset"):
            if new_name and add_asset(new_name, new_type, new_id, new_amount, new_quantity):
                st.sidebar.success(f"Added {new_name}")
                time.sleep(1)
                st.rerun()
            else:
                st.sidebar.error("Could not add asset (already exists or invalid name).")

elif action == "Remove Asset":
    with st.sidebar.form("remove_asset_form"):
        selected_asset = st.selectbox("Select Asset to Remove", asset_names)
        if st.form_submit_button("Remove Asset"):
            if remove_asset(selected_asset):
                st.sidebar.success(f"Removed {selected_asset}")
                time.sleep(1)
                st.rerun()

# --- Main Dashboard ---
st.markdown("""
<div class="dashboard-header">
    <h1>⚡ QUEST</h1>
    <p>Quantitative Unified Equity Surveillance Tracker</p>
</div>
""", unsafe_allow_html=True)

# Analyze Data
with st.spinner("Analyzing portfolio data..."):
    try:
        df, summary = analyze_portfolio(current_assets, period="2y", verbose=False)
        
        # ── Step 1: Compute EWMA seeds from historical market data ─────────
        if not df.empty:
            has_mf = any(a.asset_type == AssetType.MUTUAL_FUND for a in current_assets)
            _vol_ann_seed = summary.get('portfolio_volatility', 0.15)
            if pd.isna(_vol_ann_seed): _vol_ann_seed = 0.15
            _mu_ann_seed = summary.get('weighted_ann_return', 12.0)
            if pd.isna(_mu_ann_seed): _mu_ann_seed = 12.0
            _mu_ann_seed = _mu_ann_seed / 100.0
            _current_val_seed = summary.get('total_value', 0.0)
            _hist_mu_daily = _current_val_seed * (((1 + _mu_ann_seed) ** (1/365)) - 1)
            _hist_sigma_daily = _current_val_seed * (_vol_ann_seed / (252 ** 0.5))

            # ── Step 2: EWMA catch-up — FIRST thing on every app load ────────
            # Scans ALL graded entries in predictions_log.json that are not yet
            # in adaptive_state.json's learning_log, and applies EWMA updates
            # immediately, regardless of when those entries were graded.
            ewma_catchup(
                historical_mu=_hist_mu_daily,
                historical_sigma=_hist_sigma_daily,
            )

            # ── Step 3: Grade any new predictions + cascade ───────────────────
            evaluate_past_predictions(
                _current_val_seed,
                has_mf,
                historical_mu=_hist_mu_daily,
                historical_sigma=_hist_sigma_daily,
            )

    except Exception as e:
        st.error(f"Error fetching market data: {e}")
        st.stop()

# ── Portfolio Sentiment Score (cached 5 min so news isn’t re-fetched every 60s refresh) ──
# Compute once and store in session_state with a timestamp.
_SENT_TTL = 300  # seconds
_now_ts = __import__('time').time()
if (
    "_sentiment_score" not in st.session_state
    or (_now_ts - st.session_state.get("_sentiment_ts", 0)) > _SENT_TTL
):
    try:
        _total_val_sent = summary.get('total_value', 1.0) or 1.0
        _sent_score_accum = 0.0
        _sent_weight_accum = 0.0
        _sent_negative_count = 0
        for _sa in current_assets:
            if not _sa.identifier:
                continue
            try:
                _sd = get_asset_sentiment(_sa.identifier, stock_name=_sa.name, limit=4)
                _sv = _sd.get('score', 0.0) or 0.0
                # weight by portfolio share
                _asset_row = df[df['Name'] == _sa.name] if not df.empty else None
                _asset_val = float(_asset_row['Current Value (₹)'].iloc[0]) if (_asset_row is not None and not _asset_row.empty) else 0.0
                _w = _asset_val / _total_val_sent
                _sent_score_accum += _sv * _w
                _sent_weight_accum += _w
                if _sv < -0.15:
                    _sent_negative_count += 1
            except Exception:
                pass
        st.session_state['_sentiment_score'] = _sent_score_accum / _sent_weight_accum if _sent_weight_accum > 0 else 0.0
        st.session_state['_sentiment_neg_count'] = _sent_negative_count
        st.session_state['_sentiment_ts'] = _now_ts
    except Exception:
        st.session_state.setdefault('_sentiment_score', 0.0)
        st.session_state.setdefault('_sentiment_neg_count', 0)
        st.session_state['_sentiment_ts'] = _now_ts

portfolio_sentiment_score = st.session_state.get('_sentiment_score', 0.0)
_sentiment_neg_count = st.session_state.get('_sentiment_neg_count', 0)

# Top Metrics
total_invested = df["Invested (₹)"].sum() if not df.empty else 0.0
total_pnl = df["P&L (₹)"].sum() if not df.empty else 0.0
total_pnl_perc = (total_pnl / total_invested * 100) if total_invested > 0 else 0.0

if not df.empty and total_invested > 0:
    total_val = summary['total_value']
    
    # 1. Concentration Risk
    top_asset = df.loc[df["Current Value (₹)"].idxmax()]
    top_pct = (top_asset["Current Value (₹)"] / total_val) * 100
    hhi = (df["Current Value (₹)"] / total_val).pow(2).sum() * 10000
    score_conc = min(100, hhi / 100)
    
    # 2. Volatility Risk
    vol_ann = summary.get('portfolio_volatility', 0)
    if pd.isna(vol_ann): vol_ann = 0
    vol_daily_pct = (vol_ann / np.sqrt(252)) * 100
    vol_rupees = total_val * (vol_daily_pct / 100)
    score_vol = max(0, min(100, 40 * vol_daily_pct - 20))
    
    # 3. Drawdown Risk
    losers = df[df["P&L (₹)"].astype(float) < 0]
    unrealised_loss = abs(losers["P&L (₹)"].astype(float).sum())
    loss_pct = unrealised_loss / total_val if total_val > 0 else 0
    score_dd = min(100, loss_pct * 1000)
    
    # 4. Correlation Risk
    corr_mat = summary.get("correlation_matrix", pd.DataFrame())
    if not corr_mat.empty and len(corr_mat.columns) > 1:
        vals = corr_mat.values.copy()
        np.fill_diagonal(vals, np.nan)
        mean_corr = np.nanmean(vals)
    else:
        mean_corr = 0
    score_corr = max(0, min(100, mean_corr * 100)) # If mean_corr > 0, it adds risk
    
    # 5. Momentum Risk
    neg_mom = df[df["1M Ret %"].astype(float) < 0]
    mom_count = len(neg_mom)
    mom_weight = neg_mom["Current Value (₹)"].astype(float).sum() / total_val if not neg_mom.empty else 0
    score_mom = mom_weight * 100

    # 6. Sentiment Risk (uses portfolio_sentiment_score computed above)
    # +1.0 (all bullish) → risk = 10 | 0 (neutral) → 50 | -1.0 (all bearish) → 90
    score_sent = max(0, min(100, 50 - (portfolio_sentiment_score * 40)))

    # Rebalanced weights: Conc 22, Vol 22, DD 17, Corr 12, Mom 12, Sent 15
    comp_score = (
        (score_conc * 0.22)
        + (score_vol  * 0.22)
        + (score_dd   * 0.17)
        + (score_corr * 0.12)
        + (score_mom  * 0.12)
        + (score_sent * 0.15)
    )
    summary['portfolio_risk_score'] = comp_score
    if comp_score > 70:
        summary['portfolio_risk_bucket'] = "HIGH"
    elif comp_score > 40:
        summary['portfolio_risk_bucket'] = "MODERATE"
    else:
        summary['portfolio_risk_bucket'] = "LOW"

col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Current Market Value", f"₹ {summary['total_value']:,.2f}", f"{total_pnl_perc:+.2f}% (₹{total_pnl:+,.2f})", delta_color="normal")
    st.caption("Live via yfinance — may lag 15–30 min after market close")
col2.metric("Total Invested", f"₹ {total_invested:,.2f}")

with col3:
    st.metric("Risk Score", f"{summary['portfolio_risk_score']:.1f}", summary['portfolio_risk_bucket'], delta_color="inverse")
    _risk_clicked = st.button(" ", key="risk_trigger_btn")
    if _risk_clicked:
        st.session_state.show_risk_breakdown = True
        st.rerun()

st.markdown("""
<style>
/* ── Risk card: make col3 a positioning context ── */
div[data-testid="column"]:nth-of-type(3) {
    position: relative;
}
/* ── HIDE the button container entirely — display:none removes all visual trace ── */
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"],
div[data-testid="column"]:nth-of-type(3) div.stButton,
div[data-testid="column"]:nth-of-type(3) > div:last-child > div[data-testid="stButtonContainer"] {
    display: none !important;
}
/* ── Transparent full-coverage clickable overlay via ::before ── */
div[data-testid="column"]:nth-of-type(3)::before {
    content: "";
    position: absolute;
    inset: 0;
    z-index: 10;
    cursor: pointer;
}
/* ── But we still need the actual Streamlit button to receive the click ──
   Re-show it at full size inside ::before's hit area, fully transparent ── */
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"] {
    display: block !important;
    position: absolute !important;
    inset: 0 !important;
    z-index: 11 !important;
    margin: 0 !important;
    padding: 0 !important;
}
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"] button {
    width: 100% !important;
    height: 100% !important;
    background: transparent !important;
    border: none !important;
    box-shadow: none !important;
    color: transparent !important;
    font-size: 0 !important;
    line-height: 0 !important;
    padding: 0 !important;
    cursor: pointer !important;
}
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"] button:focus,
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"] button:hover,
div[data-testid="column"]:nth-of-type(3) div[data-testid="stButtonContainer"] button:active {
    outline: none !important;
    box-shadow: none !important;
    background: transparent !important;
    border: none !important;
}
/* ── Metric card hover glow ── */
div[data-testid="column"]:nth-of-type(3) div[data-testid="metric-container"] {
    border-radius: 12px;
    transition: transform 0.22s ease, box-shadow 0.22s ease, background 0.22s ease;
    animation: risk-pulse 2.5s infinite;
}
div[data-testid="column"]:nth-of-type(3):hover div[data-testid="metric-container"] {
    transform: translateY(-2px);
    box-shadow: 0 0 20px 4px rgba(255,77,109,0.32);
    background: rgba(255,77,109,0.05);
}
/* ── Subtle "↗ View Breakdown" hint ── */
div[data-testid="column"]:nth-of-type(3)::after {
    content: "\2197 View Breakdown";
    position: absolute;
    bottom: -14px;
    right: 4px;
    font-size: 0.71rem;
    color: #ff4d6d;
    font-weight: 600;
    pointer-events: none;
    opacity: 0.8;
}
@keyframes risk-pulse {
    0%   { box-shadow: 0 0 0 0 rgba(255,77,109,0.32); }
    70%  { box-shadow: 0 0 0 9px rgba(255,77,109,0); }
    100% { box-shadow: 0 0 0 0 rgba(255,77,109,0); }
}
</style>
""", unsafe_allow_html=True)


col4, col5 = st.columns(2)
col4.metric("Assets Analyzed", summary['n_assets'])
col5.metric("Last Updated", datetime.now().strftime("%H:%M:%S"))

st.markdown("---")

if st.session_state.show_risk_breakdown:
    c_back, _ = st.columns([1, 4])
    if c_back.button("← Back to Dashboard"):
        st.session_state.show_risk_breakdown = False
        st.rerun()
        
    st.subheader("Composite Risk Score Breakdown")
    if not df.empty and total_invested > 0:
        # Gauge Chart for Score
        fig_gauge = go.Figure(go.Indicator(
            mode = "gauge+number",
            value = comp_score,
            title = {'text': "Overall Risk Score"},
            gauge = {
                'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': "rgba(255,255,255,0.5)"},
                'bar': {'color': "rgba(255,255,255,0.8)", 'thickness': 0.2},
                'bgcolor': "rgba(0,0,0,0)",
                'borderwidth': 2,
                'bordercolor': "rgba(255,255,255,0.1)",
                'steps': [
                    {'range': [0, 40], 'color': "rgba(0, 255, 135, 0.2)"},
                    {'range': [40, 70], 'color': "rgba(255, 166, 0, 0.2)"},
                    {'range': [70, 100], 'color': "rgba(255, 77, 109, 0.2)"}],
                'threshold': {
                    'line': {'color': "#fff", 'width': 4},
                    'thickness': 0.75,
                    'value': comp_score}
            }
        ))
        fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), font=dict(family="Inter", color="#fff"), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
        st.plotly_chart(fig_gauge, use_container_width=True)
        
        # Verdict
        bucket_color = "#00ff87" if comp_score <= 40 else "#ffa600" if comp_score <= 70 else "#ff4d6d"
        st.markdown(f"<h4 style='text-align: center; color: {bucket_color}; font-family: \"Inter\", sans-serif;'>Your portfolio carries {summary['portfolio_risk_bucket']} risk. The primary drivers are your highest-scoring components below.</h4>", unsafe_allow_html=True)
        st.markdown("---")
        
        def render_component(title, weight, score, text, formula):
            c_color = "#00ff87" if score <= 40 else "#ffa600" if score <= 70 else "#ff4d6d"
            contrib = score * (weight/100)
            return f"""
            <div style="background: rgba(255,255,255,0.02); border: 1px solid rgba(255,255,255,0.05); border-radius: 12px; padding: 1.2rem; height: 100%; margin-bottom: 1rem;">
                <h4 style="margin-top: 0; margin-bottom: 0.2rem; color: #fff;">{title}</h4>
                <p style="color: #94a3b8; font-size: 0.8rem; margin-top: 0;">Weight: {weight}% | Contributes {contrib:.1f} pts</p>
                
                <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                    <div style="flex-grow: 1; background: rgba(255,255,255,0.1); height: 8px; border-radius: 4px; overflow: hidden; margin-right: 15px;">
                        <div style="width: {score}%; background: {c_color}; height: 100%;"></div>
                    </div>
                    <span style="font-family: 'JetBrains Mono', monospace; font-weight: 700; color: {c_color}; font-size: 1.2rem;">{score:.1f}</span>
                </div>
                
                <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.5;">{text}</p>
                <div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 0.5rem; margin-top: 1rem;">
                    <code style="color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">{formula}</code>
                </div>
            </div>
            """
            
        r1, r2, r3 = st.columns(3)
        with r1:
            st.markdown(render_component(
                "Concentration Risk", 22, score_conc,
                f"Your top asset ({top_asset['Name']}) holds {top_pct:.1f}% of your portfolio. If perfectly equal across {len(df)} assets, each would be {100/len(df):.1f}%.",
                "HHI = Σ(wᵢ²) × 10000"
            ), unsafe_allow_html=True)

        with r2:
            st.markdown(render_component(
                "Volatility Risk", 22, score_vol,
                f"Your portfolio's daily standard deviation is ₹{vol_rupees:,.2f} ({vol_daily_pct:.2f}%). On a bad day, expect to move this much.",
                "σₚ = √(wᵀΣw)"
            ), unsafe_allow_html=True)

        with r3:
            st.markdown(render_component(
                "Drawdown Risk", 17, score_dd,
                f"Your losing positions ({len(losers)} assets) collectively represent ₹{unrealised_loss:,.2f} of unrealised loss.",
                "Loss Contrib = Σ(wᵢ × |P&Lᵢ|) for P&L < 0"
            ), unsafe_allow_html=True)

        r4, r5, r6 = st.columns(3)
        with r4:
            st.markdown(render_component(
                "Correlation Risk", 12, score_corr,
                f"Your average inter-asset correlation is {mean_corr:.2f}. A perfectly diversified portfolio would be close to 0.",
                "Mean Corr = (2 / n(n-1)) × Σ ρᵢⱼ"
            ), unsafe_allow_html=True)

        with r5:
            st.markdown(render_component(
                "Momentum Risk", 12, score_mom,
                f"{mom_count} out of {len(df)} assets are in a negative 1-month trend, representing {mom_weight*100:.1f}% of your portfolio by value.",
                "Score = % Weight of Assets w/ 1M Ret < 0"
            ), unsafe_allow_html=True)

        with r6:
            _sent_label = "Bullish" if portfolio_sentiment_score > 0.15 else "Bearish" if portfolio_sentiment_score < -0.15 else "Neutral"
            st.markdown(render_component(
                "News Sentiment Risk", 15, score_sent,
                f"Based on today’s financial news about your holdings. "
                f"{_sentiment_neg_count} of your {len(current_assets)} stocks have negative news coverage right now. "
                f"Overall portfolio sentiment is {_sent_label} ({portfolio_sentiment_score:+.2f}).",
                "score = 50 − (sentiment_score × 40)"
            ), unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### 🛠️ How to lower your score")
        st.markdown("Based on the mathematical breakdown, taking these actions will most efficiently reduce your composite risk:")

        scores_dict = {
            "Concentration": score_conc,
            "Volatility":    score_vol,
            "Drawdown":      score_dd,
            "Correlation":   score_corr,
            "Momentum":      score_mom,
            "Sentiment":     score_sent,
        }
        sorted_scores = sorted(scores_dict.items(), key=lambda x: x[1], reverse=True)

        for k, v in sorted_scores[:3]:
            if k == "Concentration":
                st.info(f"**Reduce Concentration:** Trim **{top_asset['Name']}** from {top_pct:.1f}% to under {100/len(df) * 1.5:.1f}%. This alone would heavily reduce your Concentration sub-score.")
            elif k == "Volatility":
                st.info(f"**Lower Volatility:** Shift capital from high-beta equities into lower volatility assets like Digital Gold or Bonds.")
            elif k == "Drawdown":
                st.info(f"**Cut Losers:** Sell off your largest unrealised losing position to instantly clear the Drawdown risk penalty.")
            elif k == "Correlation":
                st.info(f"**Improve Diversification:** Sell highly correlated assets in identical sectors and add uncorrelated assets (like commodities).")
            elif k == "Momentum":
                st.info(f"**Trim Downward Trends:** {mom_count} of your assets are actively dropping in the 1-month window. Don't average down until momentum flips positive.")
            elif k == "Sentiment":
                st.info(f"**Monitor News Flow:** {_sentiment_neg_count} of your holdings currently have negative news sentiment. Watch for earnings misses, downgrades, or sector-level headwinds.")
                
    st.stop() # Halt execution so the main dashboard doesn't render below the breakdown view

# Split view for Data and Insights
tab1, tab2, tab_math, tab3, tab4, tab5, tab6, tab_michael = st.tabs(["📊 Portfolio Data", "📈 Performance & Visuals", "🔢 Math Engine", "💡 AI Recommendations", "📜 Transaction Ledger", "🔮 Future Projections", "📰 News & Sentiment", "⚡ MICHAEL"])

with tab1:
    st.subheader("Asset Breakdown & Quick Edit")
    st.markdown("You can **double-click the Invested (₹)** or **Quantity** cells below to update your portfolio. Press **Enter** to save.")
    
    if not df.empty:
        display_df = df.copy()
        
        # Display as an interactive dataframe
        edited_df = st.data_editor(
            display_df,
            use_container_width=True,
            column_config={
                "Invested (₹)": st.column_config.NumberColumn("Invested (₹)", min_value=0.0, format="₹ %.2f", step=0.01),
                "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, format="%.4f", step=0.0001),
                "Current Value (₹)": st.column_config.NumberColumn("Current Value", format="₹ %.2f"),
                "P&L (₹)": st.column_config.NumberColumn("P&L", format="₹ %.2f"),
                "P&L %": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
                "Weight %": st.column_config.ProgressColumn("Weight %", format="%.1f %%", min_value=0, max_value=100),
                "1M Ret %": st.column_config.NumberColumn("1M Return", format="%.1f%%"),
                "6M Ret %": st.column_config.NumberColumn("6M Return", format="%.1f%%"),
                "1Y Ret %": st.column_config.NumberColumn("1Y Return", format="%.1f%%"),
                "Risk Score": st.column_config.NumberColumn("Risk Score", format="%.1f"),
                "Risk Bucket": st.column_config.TextColumn("Risk")
            },
            disabled=["Risk Rank", "Name", "Type", "Last Price", "Current Value (₹)", "P&L (₹)", "P&L %", "Volatility %", "Beta", "Max DD %", "Sharpe", "1d VaR %", "1M Ret %", "6M Ret %", "1Y Ret %", "Total Return %", "Ann Return %", "Profit Factor", "Win Rate %", "RSI", "52w Pos", "Dist 200DMA %", "Risk Score", "Risk Bucket", "Weight %"],
            hide_index=True,
            key="portfolio_editor"
        )
        
        # Check if amounts were edited
        changes_made = False
        for idx, row in edited_df.iterrows():
            original_inv = df.loc[idx, "Invested (₹)"]
            original_qty = df.loc[idx, "Quantity"]
            new_inv = row["Invested (₹)"]
            new_qty = row["Quantity"]
            if original_inv != new_inv or original_qty != new_qty:
                update_asset_holdings(row["Name"], float(new_inv), float(new_qty))
                changes_made = True
                
        if changes_made:
            st.success("Changes saved successfully!")
            time.sleep(0.5)
            st.rerun()

    else:
        st.info("No assets in portfolio. Add some from the sidebar!")

with tab2:
    st.subheader("Visual Analytics")
    if not df.empty and df["Current Value (₹)"].sum() > 0:
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Portfolio Allocation (By Current Value)**")
            fig = px.pie(df[df["Current Value (₹)"] > 0], values='Current Value (₹)', names='Name', hole=0.4)
            fig.update_layout(margin=dict(t=0, b=0, l=0, r=0))
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("**Asset Correlation Matrix**")
            corr = summary.get("correlation_matrix", pd.DataFrame())
            if not corr.empty:
                fig2 = px.imshow(corr, text_auto=True, color_continuous_scale=['#1e3a5f', '#ffffff', '#7f1d1d'], range_color=[-1, 1], aspect='auto')
                fig2.update_xaxes(tickangle=45, tickfont=dict(size=12))
                fig2.update_yaxes(tickfont=dict(size=12))
                fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=max(400, len(corr.columns) * 48), autosize=True)
                st.plotly_chart(fig2, use_container_width=True)
                
                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: ρ(X,Y) = Cov(X,Y) / (σₓ · σᵧ)</p>", unsafe_allow_html=True)
                    corr_mat = corr.copy()
                    np.fill_diagonal(corr_mat.values, -1.0)
                    if not corr_mat.empty and len(corr_mat.columns) > 1:
                        max_idx = corr_mat.values.argmax()
                        r_idx, c_idx = np.unravel_index(max_idx, corr_mat.shape)
                        stock_x, stock_y = corr_mat.index[r_idx], corr_mat.columns[c_idx]
                        rho = corr_mat.iloc[r_idx, c_idx]
                        returns_df = summary.get("returns_df")
                        if returns_df is not None and not returns_df.empty:
                            cov_xy = returns_df[stock_x].cov(returns_df[stock_y])
                            std_x = returns_df[stock_x].std()
                            std_y = returns_df[stock_y].std()
                            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Inputs:<br>Cov({stock_x}, {stock_y}) = {cov_xy:.6f}<br>σ_{stock_x} = {std_x:.6f}, σ_{stock_y} = {std_y:.6f}</p>", unsafe_allow_html=True)
                            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: ρ = {rho:.4f}</p>", unsafe_allow_html=True)
                            st.markdown("A value above 0.7 means these assets move together 70%+ of the time.")
            else:
                st.info("Not enough data to calculate correlation yet.")
                
        st.markdown("---")
        st.markdown("### Diversification Health Check")
        st.markdown(f"Imagine your {len(df)} assets are {len(df)} musicians. True diversification means they're all playing different songs — so if one fails, the others carry the show. But if most of them are secretly following the same conductor (the broader market), then when the market crashes, ALL of them crash together. This check tells you how many independent songs are actually playing in your portfolio.")
        
        explained_var = summary.get("pca_explained_var", [])
        if len(explained_var) > 0:
            c3, c4 = st.columns(2)
            
            with c3:
                pca_df = pd.DataFrame({
                    "Hidden Force": [f"Force {i+1}" for i in range(len(explained_var))],
                    "Control %": explained_var * 100
                })
                # Show top 5 forces
                fig_pca = px.bar(pca_df.head(5), x="Hidden Force", y="Control %", text_auto='.1f', title="Forces Controlling Your Portfolio")
                fig_pca.update_traces(marker_color='#818cf8')
                fig_pca.update_layout(margin=dict(t=30, b=0, l=0, r=0))
                fig_pca.update_xaxes(showgrid=False)
                fig_pca.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
                st.plotly_chart(fig_pca, use_container_width=True)
                
                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: Σ = VΛVᵀ (eigendecomposition)</p>", unsafe_allow_html=True)
                    eigenvalues = summary.get("pca_eigenvalues", [])
                    if len(eigenvalues) >= 1:
                        l1 = eigenvalues[0]
                        l2 = eigenvalues[1] if len(eigenvalues) > 1 else 0
                        l3 = eigenvalues[2] if len(eigenvalues) > 2 else 0
                        sum_l = np.sum(eigenvalues)
                        st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Inputs: λ₁ = {l1:.6f}, λ₂ = {l2:.6f}, λ₃ = {l3:.6f}<br>Σλⱼ = {sum_l:.6f}</p>", unsafe_allow_html=True)
                        pct1 = (l1 / sum_l) * 100 if sum_l > 0 else 0
                        st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: Explained Variance % = λ₁ / Σλⱼ × 100 = {pct1:.2f}%</p>", unsafe_allow_html=True)
                
            with c4:
                top_factor_var = explained_var[0] * 100
                st.markdown(f"### **{top_factor_var:.1f}%**")
                st.markdown(f"**{top_factor_var:.1f}% of your portfolio's movement is controlled by a single hidden force** — most likely the overall Indian market direction.")
                
                st.markdown("<br>", unsafe_allow_html=True)
                
                if top_factor_var < 60:
                    st.success("🟢 **Good Diversification** — your stocks are behaving independently enough.")
                elif top_factor_var <= 75:
                    st.warning("🟡 **Moderate Risk** — most of your stocks rise and fall together. Consider adding assets from different sectors.")
                else:
                    st.error("🔴 **False Diversification** — you effectively own one position. A market crash will hit everything at once.")
                    
        st.markdown("---")
        st.markdown("**Growth & Fall (Time Periods)**")
        perf_cols = ["Name", "1M Ret %", "6M Ret %", "1Y Ret %"]
        if all(c in df.columns for c in perf_cols):
            perf_df = df[perf_cols].copy()
            perf_df.set_index("Name", inplace=True)
            st.bar_chart(perf_df)
            
            with st.expander("∑ Show Math"):
                st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: Return % = (Pₜ - P₀) / P₀ × 100</p>", unsafe_allow_html=True)
                first_asset = df.iloc[0]
                # Approximation of P0 from current value and return
                pt = first_asset.get("Last Price", 0)
                pnl_pct = first_asset.get("P&L %", 0) / 100.0
                if pnl_pct != -1:
                    p0 = pt / (1 + pnl_pct)
                    ret_all = (pt - p0) / p0 * 100 if p0 > 0 else 0
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Example ({first_asset['Name']}):<br>Inputs: P₀ = ₹{p0:.2f}, Pₜ = ₹{pt:.2f}</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: Return % = {ret_all:.2f}%</p>", unsafe_allow_html=True)

with tab_math:
    st.subheader("Academic Visibility — Under the Hood")
    st.markdown("This section exposes the raw linear algebra operations running on your portfolio.")
    
    if not df.empty and summary.get("returns_df") is not None and not summary["returns_df"].empty:
        import numpy as np
        import pandas as pd
        import plotly.graph_objects as go
        
        returns_df = summary["returns_df"]
        # Convert to numpy array A (time periods x assets)
        A = returns_df.values
        asset_names = returns_df.columns.tolist()
        
        # --- SECTION 1 ---
        st.markdown("---")
        st.markdown("### SECTION 1 — QR Decomposition")
        st.markdown("##### QR Decomposition — Return Matrix Factorisation")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #38bdf8;'>A = QR  <span style='color: #94a3b8; font-size: 1rem; font-weight: 400;'>(where Q is orthogonal (QᵀQ = I) and R is upper triangular)</span></p>", unsafe_allow_html=True)
        st.markdown("We apply QR decomposition to the asset returns matrix A (rows = time periods, columns = assets). This separates the returns into an orthogonal basis Q and an upper triangular matrix R. The QR algorithm is also the numerical method used to extract eigenvalues in the next section.")
        
        # Compute QR
        Q, R = np.linalg.qr(A)
        
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("**Q Matrix (Orthogonal Basis)**")
            q_display = pd.DataFrame(Q[:5, :5])
            if Q.shape[0] > 5 or Q.shape[1] > 5:
                st.caption(f"showing first {min(5, Q.shape[0])} periods × {min(5, Q.shape[1])} assets")
            st.dataframe(q_display.style.format("{:.4f}"), use_container_width=True)
            
        with c2:
            st.markdown("**R Matrix (Upper Triangular)**")
            r_display = pd.DataFrame(R[:5, :5])
            if R.shape[0] > 5 or R.shape[1] > 5:
                st.caption(f"showing first {min(5, R.shape[0])} periods × {min(5, R.shape[1])} assets")
            st.dataframe(r_display.style.format("{:.4f}"), use_container_width=True)
            
        st.markdown("**Verification: QᵀQ ≈ I**")
        qtq = np.dot(Q.T, Q)
        qtq_display = pd.DataFrame(qtq[:5, :5])
        st.dataframe(qtq_display.style.format("{:.4f}"), use_container_width=True)
        
        # --- SECTION 2 ---
        st.markdown("---")
        st.markdown("### SECTION 2 — Eigenvalue Extraction")
        st.markdown("##### Eigenvalue Analysis — Covariance Matrix Decomposition")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #ff4d6d;'>det(Σ - λI) = 0</p>", unsafe_allow_html=True)
        st.markdown("We compute the covariance matrix Σ from the asset returns, then solve the characteristic equation to find eigenvalues λ. Each eigenvalue represents the variance explained by one independent 'factor' driving the portfolio.")
        
        cov_matrix = returns_df.cov().values
        
        st.markdown("**Step 1 — Covariance Matrix Σ**")
        st.dataframe(pd.DataFrame(cov_matrix, index=asset_names, columns=asset_names).style.format("{:.6f}"), use_container_width=True)
        
        st.markdown("**Step 2 — QR Algorithm Iterations**")
        st.caption("Converging to diagonal form — diagonal entries become the eigenvalues.")
        
        A_k = cov_matrix.copy()
        for k in range(3):
            Q_k, R_k = np.linalg.qr(A_k)
            A_k = np.dot(R_k, Q_k)
            with st.expander(f"Iteration {k+1}: A_{k} = Q_{k}R_{k} → A_{k+1} = R_{k}Q_{k}"):
                st.dataframe(pd.DataFrame(A_k).style.format("{:.6f}"), use_container_width=True)
                
        st.markdown("**Step 3 — Extracted Eigenvalues**")
        eigenvalues = summary.get("pca_eigenvalues", [])
        explained_var = summary.get("pca_explained_var", [])
        
        for i, (eval_val, evar_val) in enumerate(zip(eigenvalues, explained_var)):
            st.markdown(f"**λ_{i+1} = {eval_val:.6f}** → explains **{evar_val*100:.2f}%** of portfolio variance")
            
        st.markdown("**Step 4 — Eigenvectors (Principal Components)**")
        eigenvectors = summary.get("pca_eigenvectors", [])
        if len(eigenvectors) > 0:
            top_k = min(3, len(eigenvectors[0]))
            eigen_df = pd.DataFrame(eigenvectors[:, :top_k], index=asset_names, columns=[f"Factor {i+1}" for i in range(top_k)])
            st.dataframe(eigen_df.style.format("{:.4f}"), use_container_width=True)
            
        # --- SECTION 3 ---
        st.markdown("---")
        st.markdown("### SECTION 3 — Factor Return Attribution")
        st.markdown("##### Factor Attribution — Systematic vs Idiosyncratic Returns")
        st.markdown("<p style='font-family: \"JetBrains Mono\", Courier, monospace; font-size: 1.2rem; font-weight: 600; color: #00ff87;'>Rᵢ = βᵢ · Rₘ + αᵢ + εᵢ</p>", unsafe_allow_html=True)
        st.markdown("Where: Rᵢ = return of asset i, Rₘ = market return (portfolio average), βᵢ = systematic risk coefficient (derived via QR-based least squares), αᵢ = idiosyncratic return, εᵢ = residual error")
        
        market_return = returns_df.mean(axis=1).values.reshape(-1, 1)
        X = np.hstack([np.ones((len(market_return), 1)), market_return])
        Q_x, R_x = np.linalg.qr(X)
        
        beta_data = []
        for i, asset in enumerate(asset_names):
            y = returns_df[asset].values.reshape(-1, 1)
            # Solve normal equations: R * beta = Q^T * y
            coeffs = np.linalg.solve(R_x, np.dot(Q_x.T, y))
            alpha, beta = coeffs[0][0], coeffs[1][0]
            
            var_total = np.var(y)
            var_sys = (beta**2) * np.var(market_return)
            sys_pct = min(1.0, var_sys / var_total) if var_total > 0 else 0.0
            idio_pct = 1.0 - sys_pct
            
            beta_data.append({
                "Asset": asset,
                "Beta": beta,
                "Systematic %": sys_pct * 100,
                "Idiosyncratic %": idio_pct * 100
            })
            
        beta_df = pd.DataFrame(beta_data)
        
        fig_beta = go.Figure()
        fig_beta.add_trace(go.Bar(
            y=beta_df["Asset"],
            x=beta_df["Systematic %"],
            name='Systematic (Market)',
            orientation='h',
            marker=dict(color='#38bdf8'),
            text=beta_df["Systematic %"].apply(lambda x: f"{x:.1f}%"),
            textposition='inside'
        ))
        fig_beta.add_trace(go.Bar(
            y=beta_df["Asset"],
            x=beta_df["Idiosyncratic %"],
            name='Idiosyncratic (Unique)',
            orientation='h',
            marker=dict(color='#00ff87'),
            text=beta_df["Idiosyncratic %"].apply(lambda x: f"{x:.1f}%"),
            textposition='inside'
        ))
        fig_beta.update_layout(
            barmode='stack',
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#94a3b8"),
            margin=dict(t=10, b=0, l=0, r=0),
            xaxis=dict(showgrid=False),
            yaxis=dict(showgrid=False)
        )
        st.plotly_chart(fig_beta, use_container_width=True)
        
        for _, row in beta_df.iterrows():
            st.markdown(f"**{row['Asset']}**: β = {row['Beta']:.2f} — {row['Systematic %']:.1f}% of its movement is explained by the overall market. Only {row['Idiosyncratic %']:.1f}% is unique to this asset.")
            
    else:
        st.info("Not enough historical data to run the Math Engine.")

with tab3:
    st.subheader("Actionable Recommendations")
    
    if not df.empty:
        total_val = summary.get('total_value', 1.0)
        import numpy as np
        
        # --- SECTION A ---
        st.markdown("### SECTION A — Buy / Sell / Hold Signals")
        signals_data = []
        avg_sharpe = df["Sharpe Ratio"].mean() if "Sharpe Ratio" in df.columns else 0
        
        for _, row in df.iterrows():
            name = row["Name"]
            pnl_perc = row.get("P&L %", 0)
            ret_1m = row.get("1M Ret %", 0)
            ret_6m = row.get("6M Ret %", 0)
            ret_1y = row.get("1Y Ret %", 0)
            sharpe = row.get("Sharpe Ratio", 0)
            
            if pnl_perc > 0 and ret_1m > 0 and sharpe > avg_sharpe:
                signal = "🟢 BUY"
                reason = f"Up {pnl_perc:.2f}% and showing positive momentum across recent timeframes."
            elif pnl_perc < -8 or (ret_1m < 0 and ret_6m < 0 and ret_1y < 0):
                signal = "🔴 SELL"
                if pnl_perc < -8:
                    reason = f"Has fallen {pnl_perc:.2f}%, breaking the -8% stop-loss threshold."
                else:
                    reason = "Consistently negative returns across 1M, 6M, and 1Y horizons."
            else:
                signal = "🟡 HOLD"
                reason = "No strong momentum signals in either direction. Continue monitoring."
                
            signals_data.append({
                "Asset": name,
                "Signal": signal,
                "Reason": reason
            })
            
        st.dataframe(pd.DataFrame(signals_data), use_container_width=True, hide_index=True)
        st.markdown("---")
        
        # --- SECTION B ---
        st.markdown("### SECTION B — Rebalancing Suggestions")
        rebal_data = []
        for _, row in df.iterrows():
            name = row["Name"]
            val = row.get("Current Value (₹)", 0)
            pct = (val / total_val) * 100 if total_val > 0 else 0
            
            if pct > 25:
                action = "Overweight — consider trimming."
            elif pct < 3 and val > 0:
                action = "Underweight — consider increasing or removing."
            elif val > 0:
                action = "Optimal — no action needed."
            else:
                continue
                
            if val > 0:
                rebal_data.append({
                    "Asset": name,
                    "Current %": f"{pct:.1f}%",
                    "Target Range": "3% - 25%",
                    "Action": action
                })
                
        st.dataframe(pd.DataFrame(rebal_data), use_container_width=True, hide_index=True)
        st.markdown("---")
        
        # --- SECTION C ---
        st.markdown("### SECTION C — Risk Warnings in Plain English")
        
        # 1. Concentration Risk
        if not df.empty and total_val > 0:
            top_asset = df.loc[df["Current Value (₹)"].idxmax()]
            top_pct = (top_asset["Current Value (₹)"] / total_val) * 100
            loss_10_perc = top_asset["Current Value (₹)"] * 0.10
            st.warning(f"**Concentration Risk:** Your top holding **{top_asset['Name']}** makes up **{top_pct:.1f}%** of your portfolio. If it drops 10%, you lose **₹{loss_10_perc:,.2f}**.")
            
        # 2. Correlation Warning
        corr = summary.get("correlation_matrix", pd.DataFrame())
        corr_found = False
        if not corr.empty and len(corr.columns) > 1:
            for i in range(len(corr.columns)):
                for j in range(i+1, len(corr.columns)):
                    if corr.iloc[i, j] > 0.7:
                        stock_a = corr.columns[i]
                        stock_b = corr.columns[j]
                        st.error(f"**Correlation Warning:** **{stock_a}** and **{stock_b}** move almost identically (correlation > 0.7). Owning both gives you less protection than you think.")
                        corr_found = True
        
        # 3. Volatility Warning
        vol_found = False
        for _, row in df.iterrows():
            name = row["Name"]
            vol_ann = row.get("Volatility %", 0) / 100.0
            if pd.notna(vol_ann):
                daily_vol_perc = (vol_ann / np.sqrt(252)) * 100
                if daily_vol_perc > 3.0:
                    st.error(f"**Volatility Warning:** **{name}** is highly volatile. Its normal daily swing is over 3% of its price.")
                    vol_found = True
                    
        if not corr_found and not vol_found:
            st.success("No extreme correlation or daily volatility risks detected. Your diversification is holding up well.")
            
        st.markdown("---")
        
        # --- SECTION D ---
        st.markdown("### SECTION D — What's Dragging Your Portfolio")
        if "P&L (₹)" in df.columns:
            sorted_df = df.sort_values(by="P&L (₹)", ascending=True)
            loser_count = 0
            for i, row in sorted_df.iterrows():
                name = row["Name"]
                pnl_rupees = row["P&L (₹)"]
                pnl_perc = row.get("P&L %", 0)
                
                if pnl_rupees < 0:
                    if loser_count == 0:
                        st.error(f"**{name} is your biggest drag** — it alone has cost you **₹{abs(pnl_rupees):,.2f}** ({pnl_perc:+.2f}% loss). It has been underperforming its historical average. Do not average down yet.")
                    else:
                        st.warning(f"**{name} is losing money** — down **₹{abs(pnl_rupees):,.2f}** ({pnl_perc:+.2f}%). Keep a close eye on this position.")
                    loser_count += 1
                elif pnl_rupees > 0:
                    st.success(f"**{name} is generating wealth** — up **₹{pnl_rupees:,.2f}** ({pnl_perc:+.2f}% gain). It is strongly contributing to your portfolio's growth.")

with tab4:
    st.subheader("Transaction History")
    txs = get_transactions()
    if txs:
        tx_df = pd.DataFrame(txs)
        # Rearrange and format
        tx_df = tx_df[["timestamp", "action", "asset", "amount", "details"]]
        tx_df["amount"] = tx_df["amount"].apply(lambda x: f"₹ {x:,.2f}" if isinstance(x, (int, float)) else x)
        tx_df.columns = ["Timestamp", "Action", "Asset", "Amount", "Details"]
        st.dataframe(tx_df, use_container_width=True, hide_index=True)
    else:
        st.info("No transactions logged yet.")
        
    st.markdown("---")
    st.markdown("### 🍔 Lifetime Asset Explorer")
    st.markdown("Select an asset from the dropdown menu to view its complete lifetime movement since inception.")
    
    if current_assets:
        selected_lifetime_asset_name = st.selectbox("Select Asset", asset_names, key="lifetime_asset_select")
        selected_asset_obj = next((a for a in current_assets if a.name == selected_lifetime_asset_name), None)
        
        if selected_asset_obj:
            with st.spinner(f"Fetching lifetime data for {selected_lifetime_asset_name}..."):
                try:
                    import yfinance as yf
                    if selected_asset_obj.asset_type == AssetType.MUTUAL_FUND:
                        from risk_analyzer import fetch_mf_history
                        hist_df = fetch_mf_history(selected_asset_obj.identifier, lookback_years=20)
                    elif selected_asset_obj.asset_type == AssetType.DIGITAL_GOLD:
                        hist_df = yf.download("GOLDBEES.NS", period="max", progress=False, auto_adjust=True, multi_level_index=False)
                    else:
                        hist_df = yf.download(selected_asset_obj.identifier, period="max", progress=False, auto_adjust=True, multi_level_index=False)
                    
                    if not hist_df.empty:
                        fig = px.line(hist_df, x=hist_df.index, y="Close")
                        fig.update_layout(
                            title=f"Lifetime Price History: {selected_lifetime_asset_name}",
                            xaxis_title="Date", 
                            yaxis_title="Price (₹)", 
                            margin=dict(t=40, b=0, l=0, r=0),
                            plot_bgcolor="rgba(0,0,0,0)",
                            paper_bgcolor="rgba(0,0,0,0)",
                            font=dict(family="Inter", color="#94a3b8")
                        )
                        fig.update_xaxes(showgrid=False)
                        fig.update_yaxes(showgrid=True, gridwidth=1, gridcolor='rgba(255,255,255,0.05)')
                        
                        # Add a beautiful gradient fill
                        fig.update_traces(line_color='#00ff87', fill='tozeroy', fillcolor='rgba(0, 255, 135, 0.1)')
                        
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No historical data found for this asset.")
                except Exception as e:
                    st.error(f"Could not fetch history: {e}")

with tab5:
    st.subheader("Future Portfolio Projections")
    
    if not df.empty and summary['total_value'] > 0:
        import numpy as np
        
        import datetime as dt
        tomorrow_date = (dt.datetime.now() + dt.timedelta(days=1)).strftime("%d %b %Y")
        
        # 1-Day Forecast (Tomorrow)
        st.markdown(f"### 🌤️ Forecast for {tomorrow_date} (1-Day Outlook)")
        st.markdown("Predicting tomorrow's exact value is impossible due to market noise, but we can mathematically calculate the expected probability range based on your portfolio's historical volatility.")
        
        vol = summary.get('portfolio_volatility', float('nan'))
        if pd.isna(vol):
            vol = 0.15

        current_val = summary['total_value']

        # ── Use EWMA σₚ directly from adaptive_state (Rs. terms, 1-day) ──
        # This is the model-trained daily volatility, not the yfinance % vol
        try:
            from adaptive_engine import _load_state as _ae_load
            _ae_st = _ae_load()
            sigma_p = _ae_st.get('sigma_ewma', None)
            mu_p    = _ae_st.get('mu_ewma', None)
            days_tr = _ae_st.get('days_trained', 0)
        except Exception:
            sigma_p = None
            mu_p    = None
            days_tr = 0

        # Fall back to percent-vol if EWMA not yet trained
        if sigma_p and days_tr >= 1:
            one_day_move_rupees = sigma_p          # 1.0 × σₚ  (68% range)
            var_95_move         = 1.645 * sigma_p  # 1.645 × σₚ  (95% VaR)
            sigma_source        = f"σₚ = ₹{sigma_p:,.2f} (EWMA-trained, {days_tr} days)"
        else:
            one_day_vol         = vol / np.sqrt(252)
            one_day_move_rupees = current_val * one_day_vol
            var_95_move         = 1.645 * one_day_move_rupees
            sigma_source        = f"σₚ = ₹{one_day_move_rupees:,.2f} (historical vol, EWMA not yet trained)"

        # Base for the range: use latest graded real_val if available
        _preds_all  = get_predictions()
        _graded     = [p for p in _preds_all if p.get('real_val') is not None]
        if _graded:
            _graded.sort(key=lambda x: x['target_date'])
            base_pred = _graded[-1]['real_val']
            base_label = f"V₀ = ₹{base_pred:,.2f} (confirmed close {_graded[-1]['target_date']})"
        else:
            base_pred  = current_val
            base_label = f"V₀ = ₹{base_pred:,.2f} (live yfinance — no graded close yet)"

        # Prediction from EWMA if available, else use base_pred
        if mu_p and days_tr >= 1:
            _bias_5d = _ae_st.get('learning_log', [{}])[-1].get('bias_5d', 0) if _ae_st.get('learning_log') else 0
            range_centre = base_pred + mu_p + _bias_5d
            centre_label = f"centre = V₀ + μₚ + bias₅d = {base_pred:,.2f} + {mu_p:+.2f} + {_bias_5d:+.2f} = {range_centre:,.2f}"
        else:
            range_centre = base_pred
            centre_label = f"centre = V₀ = {base_pred:,.2f} (no EWMA μₚ yet)"

        c1, c2 = st.columns(2)
        with c1:
            st.info(
                f"**Expected Range (68% Probability)**\n\n"
                f"There is a ~68% chance your portfolio will close on **{tomorrow_date}** between:\n\n"
                f"**₹{range_centre - one_day_move_rupees:,.2f}** and **₹{range_centre + one_day_move_rupees:,.2f}**"
            )

        with c2:
            st.warning(
                f"**Maximum Expected Loss (95% VaR)**\n\n"
                f"We are 95% confident your portfolio will NOT drop below:\n\n"
                f"**₹{range_centre - var_95_move:,.2f}**\n\n"
                f"(A maximum loss of ₹{var_95_move:,.2f} on {tomorrow_date})."
            )

        with st.expander("∑ Show Math"):
            c1_math, c2_math = st.columns(2)
            with c1_math:
                st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula (68% Range): Range = (V₀ + μₚ + bias) ± 1.0 × σₚ</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>{base_label}<br>{sigma_source}<br>{centre_label}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: [₹{range_centre - one_day_move_rupees:,.2f}, ₹{range_centre + one_day_move_rupees:,.2f}]</p>", unsafe_allow_html=True)
            with c2_math:
                st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #ff4d6d;'>Formula (95% VaR): Floor = centre − 1.645 × σₚ</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>{sigma_source}<br>z = 1.645 (95% of normal distribution falls above this point)</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: Floor = ₹{range_centre - var_95_move:,.2f}</p>", unsafe_allow_html=True)
                
        st.markdown("---")
        
        # Individual Stock Forecast
        st.markdown(f"### 🎯 Individual Stock Forecast (Direction for {tomorrow_date})")
        st.markdown("Predicted direction and mathematical expected move based on short-term expected returns and daily volatility.")
        
        if not df.empty:
            forecast_data = []
            
            # Fetch the exact 'mu' (annualized return) used in the long-term table to guarantee 100% mathematical alignment
            mu_portfolio = summary.get('weighted_ann_return', float('nan'))
            if pd.isna(mu_portfolio):
                mu_portfolio = 0.12
            else:
                mu_portfolio = mu_portfolio / 100.0
                
            # EXACT mathematical alignment with long-term compounding projection
            # Tomorrow is 1 day (1/365 of a year)
            portfolio_expected_tomorrow = current_val * ((1 + mu_portfolio) ** (1/365))
            total_expected_portfolio_change = portfolio_expected_tomorrow - current_val
            
            drivers_dict = {}
            
            for _, row in df.iterrows():
                name = row["Name"]
                last_price = row.get("Last Price", 0)
                holding_val = row.get("Current Value (₹)", 0)
                vol_ann = row.get("Volatility %", 0) / 100.0 if "Volatility %" in row else 0
                ret_ann = row.get("Ann Return %", 0) / 100.0 if "Ann Return %" in row else 0
                
                if last_price > 0:
                    day_vol = vol_ann / np.sqrt(252)
                    
                    # Align individual day return to the exact same compounding formula (1+r)^(1/365) - 1
                    day_ret_compound = ((1 + ret_ann) ** (1/365)) - 1
                    
                    expected_price_change = last_price * day_ret_compound
                    portfolio_impact = holding_val * day_ret_compound
                    
                    drivers_dict[name] = portfolio_impact
                    range_rupee = last_price * day_vol
                    
                    if expected_price_change > (last_price * 0.0001):
                        direction = "⬆️ UP"
                    elif expected_price_change < -(last_price * 0.0001):
                        direction = "⬇️ DOWN"
                    else:
                        direction = "➡️ FLAT"
                        
                    forecast_data.append({
                        "Asset": name,
                        "Last Price": f"₹{last_price:,.2f}",
                        "Expected Direction": direction,
                        "Expected Price Move": f"₹{expected_price_change:+.2f}",
                        "Volatility Range (±)": f"₹{range_rupee:.2f}"
                    })
                    
            # Safe defaults — overwritten below if forecast_data is non-empty
            days_trained = get_days_trained()
            calibrating = days_trained < 3
            confidence = "calibrating"

            if forecast_data:
                st.dataframe(pd.DataFrame(forecast_data), use_container_width=True, hide_index=True)
                
                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: E[ΔP] = P₀ · r_daily  |  r_daily = (1 + r_annual)^(1/252) - 1</p>", unsafe_allow_html=True)
                    example = forecast_data[0]
                    name = example["Asset"]
                    row_ex = df[df["Name"] == name].iloc[0]
                    r_ann = row_ex.get("Ann Return %", 0) / 100.0
                    r_day = ((1 + r_ann)**(1/365)) - 1
                    p0 = row_ex.get("Last Price", 0)
                    e_dp = p0 * r_day
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Example ({name}):<br>Inputs: r_annual = {r_ann*100:.2f}%, P₀ = ₹{p0:,.2f}<br>r_daily = {r_day*100:.4f}%</p>", unsafe_allow_html=True)
                    st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Output: E[ΔP] = ₹{e_dp:+.4f}</p>", unsafe_allow_html=True)
                    
                # ── Adaptive forecast (replaces static P = V₀ + μₚ) ───────────────
                import datetime as dt
                from adaptive_engine import adaptive_forecast, get_learning_log, get_days_trained

                _mu_ann_raw = summary.get('weighted_ann_return', float('nan'))
                if pd.isna(_mu_ann_raw): _mu_ann_raw = 12.0
                _mu_ann_ratio = _mu_ann_raw / 100.0

                _vol_ann_raw = summary.get('portfolio_volatility', float('nan'))
                if pd.isna(_vol_ann_raw): _vol_ann_raw = 0.15

                # Historical daily ₹ mu and sigma (seeds for cold-start)
                _hist_mu_daily = current_val * (((1 + _mu_ann_ratio) ** (1/365)) - 1)
                _hist_sigma_daily = current_val * (_vol_ann_raw / (252 ** 0.5))

                forecast = adaptive_forecast(
                    last_confirmed_close=current_val,
                    historical_mu=_hist_mu_daily,
                    historical_sigma=_hist_sigma_daily,
                )

                portfolio_expected_tomorrow = forecast["predicted_val"]
                total_expected_portfolio_change = portfolio_expected_tomorrow - current_val
                mu_used_display = forecast["mu_used"]
                sigma_used_display = forecast["sigma_used"]
                bias_display = forecast["bias"]
                alpha_display = forecast["alpha"]
                days_trained = forecast["days_trained"]
                calibrating = forecast["calibrating"]
                confidence = forecast["confidence"]

                # ── Sentiment adjustment on top of EWMA forecast ──────────────
                _vol_for_sent = forecast["sigma_used"]  # adaptive σₚ in ₹
                _raw_sent_adj = portfolio_sentiment_score * _vol_for_sent * 0.15
                # Cap to ±₹200
                _sent_adj = max(-200.0, min(200.0, _raw_sent_adj))
                _ewma_base = portfolio_expected_tomorrow
                portfolio_expected_tomorrow = _ewma_base + _sent_adj
                total_expected_portfolio_change = portfolio_expected_tomorrow - current_val

                tomorrow_str = (dt.datetime.now() + dt.timedelta(days=1)).strftime("%Y-%m-%d")
                save_daily_prediction(
                    tomorrow_str,
                    portfolio_expected_tomorrow,
                    total_expected_portfolio_change,
                    drivers_dict,
                    base_close=current_val,
                )

                # ── Sentiment adjustment display line ─────────────────────────
                _sent_clr = "#00ff87" if _sent_adj > 0 else "#ff4d6d" if _sent_adj < 0 else "#94a3b8"
                st.markdown(
                    f"""
                    <div style="background:rgba(255,255,255,0.03); border:1px solid rgba(255,255,255,0.07);
                                border-radius:10px; padding:12px 18px; margin-bottom:1rem;
                                font-family:'JetBrains Mono',monospace; font-size:0.85rem;">
                        <span style="color:#94a3b8;">Base (EWMA):</span>
                        <span style="color:#e2e8f0; margin:0 6px;">₹{_ewma_base:,.2f}</span>
                        <span style="color:#64748b;">|</span>
                        <span style="color:#94a3b8; margin:0 6px;">Sentiment adj:</span>
                        <span style="color:{_sent_clr}; margin-right:6px;">{_sent_adj:+.2f}</span>
                        <span style="color:#64748b;">|</span>
                        <span style="color:#7dd3fc; margin-left:6px; font-weight:700;">Final: ₹{portfolio_expected_tomorrow:,.2f}</span>
                    </div>
                    """,
                    unsafe_allow_html=True
                )
                
        # ── Confidence Indicator + Calibration Notice ───────────────────────────
        _conf_colors = {
            "high":        ("#00ff87", "🟢", "High Confidence",   "Last 3 errors all under ₹300 — model is well-calibrated."),
            "medium":      ("#ffa600", "🟡", "Medium Confidence",  "Errors between ₹300-₹600 — model is learning."),
            "low":         ("#ff4d6d", "🔴", "Low Confidence",     "Recent errors above ₹600 or inconsistent direction — treat forecast with caution."),
            "calibrating": ("#7dd3fc", "🔵", "Calibrating",        f"Model has seen {days_trained} graded day(s). Accuracy improves from day 4 onwards."),
        }
        _conf_clr, _conf_icon, _conf_label, _conf_desc = _conf_colors.get(confidence, _conf_colors["calibrating"])

        st.markdown(
            f"""
            <div style="display:inline-flex; align-items:center; gap:10px;
                        background:rgba(255,255,255,0.04); border:1px solid {_conf_clr}44;
                        border-left:4px solid {_conf_clr}; border-radius:10px;
                        padding:10px 18px; margin-bottom:1rem;">
                <span style="font-size:1.3rem;">{_conf_icon}</span>
                <div>
                    <span style="color:{_conf_clr}; font-weight:700; font-family:'JetBrains Mono',monospace;">{_conf_label}</span>
                    <span style="color:#94a3b8; font-size:0.85rem; margin-left:10px;">{_conf_desc}</span>
                </div>
            </div>
            """,
            unsafe_allow_html=True
        )

        if calibrating:
            st.caption("⚠️ Model is still calibrating — accuracy will improve as more data is collected.")

        # ── Show Prediction Tracker ──────────────────────────────────────────────
        st.markdown("### 📝 Daily Prediction Tracker")
        st.markdown("Historical accuracy of our 1-Day adaptive forecasts against actual market closes.")
        pred_logs = get_predictions()
        if pred_logs:
            import datetime as dt
            _now = dt.datetime.now()
            _after_close = _now.hour > 15 or (_now.hour == 15 and _now.minute >= 30)
            _today_str = _now.strftime("%Y-%m-%d")

            tracker_data = []
            pending_entries = []   # ungraded entries eligible for manual override
            for p in reversed(pred_logs):  # Show newest first
                t_date = dt.datetime.strptime(p["target_date"], "%Y-%m-%d")
                is_weekend = t_date.weekday() >= 5

                if p.get("real_val"):
                    verified = " ✅" if p.get("manually_confirmed") else ""
                    actual = f"₹{p['real_val']:,.2f}{verified}"
                    err_val = p['real_val'] - p['expected_val']
                    reason = p.get("variance_reason", "")
                elif is_weekend:
                    actual = "MKT CLOSED"
                    err_val = None
                    reason = "Weekend"
                else:
                    actual = "Waiting..."
                    err_val = None
                    reason = "⏳ Pending close"
                    # Eligible for manual override if past close time
                    if _after_close:
                        pending_entries.append(p)

                row_entry = {
                    "Target Date": p["target_date"],
                    "Expected Value": f"₹{p['expected_val']:,.2f}",
                    "Actual Value": actual,
                    "Error (₹)": f"{err_val:+,.2f}" if err_val is not None else "-",
                    "Variance Reason": reason,
                }
                tracker_data.append(row_entry)
            st.dataframe(pd.DataFrame(tracker_data), use_container_width=True, hide_index=True)

            # ── Manual close override (shown only after 3:30 PM for ungraded entries) ──
            if pending_entries:
                st.markdown("""
                <div style='background:rgba(251,191,36,0.08);border:1px solid rgba(251,191,36,0.25);
                border-left:4px solid #fbbf24;border-radius:10px;padding:0.9rem 1.2rem;margin-top:0.8rem'>
                <span style='color:#fbbf24;font-weight:700;font-size:0.85rem;letter-spacing:1px'>
                ⏰ MARKET CLOSED — MANUAL CLOSE OVERRIDE</span><br>
                <span style='color:#94a3b8;font-size:0.82rem'>
                yfinance data for Indian markets can lag 15–30 minutes after close.
                Enter the actual NSE portfolio close below to grade immediately.
                Leave empty to let yfinance auto-grade on the next app load.
                </span>
                </div>
                """, unsafe_allow_html=True)

                for p_entry in pending_entries:
                    _entry_date = p_entry["target_date"]
                    st.markdown(f"**Override for {_entry_date}** &nbsp; (expected: ₹{p_entry['expected_val']:,.2f})")
                    _oc1, _oc2 = st.columns([3, 1])
                    with _oc1:
                        _manual_val = st.number_input(
                            f"Actual close price for {_entry_date} (₹)",
                            min_value=0.0,
                            value=0.0,
                            step=1.0,
                            format="%.2f",
                            key=f"manual_close_{_entry_date}",
                            label_visibility="collapsed",
                            placeholder="Enter actual NSE portfolio close price...",
                        )
                    with _oc2:
                        if st.button("Confirm ✓", key=f"confirm_close_{_entry_date}",
                                     use_container_width=True, type="primary"):
                            if _manual_val and _manual_val > 0:
                                ok = confirm_manual_close(_entry_date, _manual_val)
                                if ok:
                                    # Immediately fire EWMA catchup with the now-graded entry
                                    ewma_catchup(
                                        historical_mu=_hist_mu_daily,
                                        historical_sigma=_hist_sigma_daily,
                                    )
                                    st.success(f"✅ Close confirmed for {_entry_date}: ₹{_manual_val:,.2f}. EWMA updated.")
                                    st.rerun()
                                else:
                                    st.error("Could not find that prediction entry. It may already be graded.")
                            else:
                                st.warning("Enter a value greater than 0 to confirm.")
        else:
            st.info("No predictions logged yet. Check back tomorrow!")

        # ── Learning Log ─────────────────────────────────────────────────────────
        learning_log = get_learning_log()
        if learning_log:
            with st.expander(f"🧠 Learning Log — {len(learning_log)} graded day(s) of adaptive memory"):
                st.markdown(
                    "This table shows how the adaptive EWMA model updates its expected return (μₚ) "
                    "and volatility (σₚ) after each day's actual close is confirmed. "
                    "The model's memory compounds: each new entry shifts the model's expectation toward recent reality."
                )
                log_display = []
                for entry in reversed(learning_log):  # newest first
                    log_display.append({
                        "Date":          entry["date"],
                        "Actual Return (₹)": f"{entry['actual_return']:+,.2f}",
                        "Prev μₚ (₹)":   f"₹{entry['mu_old']:,.2f}",
                        "Updated μₚ (₹)": f"₹{entry['mu_new']:,.2f}",
                        "Updated σₚ (₹)": f"₹{entry['sigma_new']:,.2f}",
                        "Error (₹)":     f"{entry['error']:+,.2f}",
                        "Bias 5d (₹)":   f"{entry['bias_5d']:+,.2f}",
                        "α used":        entry["alpha_used"],
                    })
                st.dataframe(pd.DataFrame(log_display), use_container_width=True, hide_index=True)

                with st.expander("∑ Show EWMA Math"):
                    st.markdown(
                        "<p style='font-family:\"JetBrains Mono\",monospace; color:#38bdf8;'>"
                        "μₚ_new = α × actual_return_t + (1-α) × μₚ_old<br>"
                        "σₚ_new = √(α × (actual_return_t − μₚ_new)² + (1-α) × σₚ_old²)<br>"
                        "P_tomorrow = last_close + μₚ_new + bias_5d</p>",
                        unsafe_allow_html=True
                    )
                    if log_display:
                        last = learning_log[-1]
                        st.markdown(
                            f"<p style='font-family:\"JetBrains Mono\",monospace;'>"
                            f"Last update ({last['date']}):<br>"
                            f"α = {last['alpha_used']} | actual_return = {last['actual_return']:+,.2f}<br>"
                            f"μₚ: {last['mu_old']:+,.4f} → {last['mu_new']:+,.4f}<br>"
                            f"σₚ: {last['sigma_old']:,.4f} → {last['sigma_new']:,.4f}<br>"
                            f"Error corrected: {last['error']:+,.2f} | Bias applied: {last['bias_5d']:+,.2f}</p>",
                            unsafe_allow_html=True
                        )
        else:
            st.info("📚 No learning history yet — the model will start adapting after its first graded prediction day.")
            
        st.markdown("---")
        
        # Long Term
        st.markdown("### 📈 Long-Term Wealth Projection")
        st.markdown("Predictive values based on your portfolio's historical **Annualized Return** and **Volatility**.")
        mu = summary.get('weighted_ann_return', float('nan'))

        if pd.isna(mu):
            st.warning("Not enough historical data to generate reliable projections. Using 12% default expected return.")
            mu = 0.12
        else:
            mu = mu / 100.0

        # ── V₀: use most recent graded real_val from predictions_log, not live price ──
        _preds_lt   = get_predictions()
        _graded_lt  = [p for p in _preds_lt if p.get('real_val') is not None]
        if _graded_lt:
            _graded_lt.sort(key=lambda x: x['target_date'])
            v0          = _graded_lt[-1]['real_val']
            _v0_src     = f"confirmed close {_graded_lt[-1]['target_date']}"
            _v0_manual  = _graded_lt[-1].get('manually_confirmed', False)
        else:
            v0          = current_val
            _v0_src     = "live yfinance (no graded close yet)"
            _v0_manual  = False

        _v0_badge = " ✅" if _v0_manual else ""
        st.caption(f"V₀ = ₹{v0:,.2f} ({_v0_src}){_v0_badge}")

        import datetime as dt
        today = dt.datetime.now()

        horizons = [
            ("1 Month",  today + pd.DateOffset(months=1),  1/12),
            ("3 Months", today + pd.DateOffset(months=3),  3/12),
            ("6 Months", today + pd.DateOffset(months=6),  6/12),
            ("1 Year",   today + pd.DateOffset(years=1),   1.0),
            ("3 Years",  today + pd.DateOffset(years=3),   3.0),
            ("5 Years",  today + pd.DateOffset(years=5),   5.0),
        ]

        proj_data = []
        for label, exact_date, t in horizons:
            expected = v0 * ((1 + mu) ** t)
            bull     = v0 * ((1 + mu + vol) ** t)
            bear     = v0 * ((1 + mu - vol) ** t)
            if bear < 0: bear = 0
            date_str = exact_date.strftime("%d %b %Y")
            proj_data.append({
                "Target Date":      f"{date_str} ({label})",
                "Bear Case (Poor)": bear,
                "Expected Value":   expected,
                "Bull Case (Great)": bull,
            })

        proj_df = pd.DataFrame(proj_data)

        t_vals = np.linspace(0, 5, 60)
        line_data = pd.DataFrame({
            "Months":     t_vals * 12,
            "Bear Case":  np.maximum(0, v0 * ((1 + mu - vol) ** t_vals)),
            "Expected":   v0 * ((1 + mu) ** t_vals),
            "Bull Case":  v0 * ((1 + mu + vol) ** t_vals),
        })
        
        fig_proj = go.Figure()
        fig_proj.add_trace(go.Scatter(x=line_data["Months"], y=line_data["Bull Case"], fill=None, mode='lines', line_color='rgba(0, 255, 135, 0.8)', name='Bull Case'))
        fig_proj.add_trace(go.Scatter(x=line_data["Months"], y=line_data["Expected"], fill='tonexty', mode='lines', line_color='rgba(99, 179, 237, 0.8)', name='Expected'))
        fig_proj.add_trace(go.Scatter(x=line_data["Months"], y=line_data["Bear Case"], fill='tonexty', mode='lines', line_color='rgba(255, 77, 109, 0.5)', name='Bear Case'))
        fig_proj.update_layout(
            xaxis_title="Months from Now", 
            yaxis_title="Projected Portfolio Value (₹)", 
            margin=dict(t=20, b=20, l=0, r=0),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="Inter", color="#94a3b8")
        )
        fig_proj.update_xaxes(showgrid=False)
        fig_proj.update_yaxes(showgrid=True, gridcolor="rgba(255,255,255,0.05)")
        
        st.plotly_chart(fig_proj, use_container_width=True)
        
        with st.expander("∑ Show Math"):
            st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: V(t) = V₀ · (1 + r)^t</p>", unsafe_allow_html=True)
            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Inputs: V₀ = ₹{v0:,.2f} ({_v0_src}){_v0_badge}<br>μₚ = {mu*100:.2f}%, σₚ = {vol*100:.2f}%</p>", unsafe_allow_html=True)
            exp_1y  = v0 * ((1 + mu) ** 1)
            exp_5y  = v0 * ((1 + mu) ** 5)
            bear_1y = v0 * ((1 + mu - vol) ** 1)
            bear_5y = v0 * ((1 + mu - vol) ** 5)
            bull_1y = v0 * ((1 + mu + vol) ** 1)
            bull_5y = v0 * ((1 + mu + vol) ** 5)
            st.markdown(f"<p style='font-family: \"JetBrains Mono\", monospace;'>Outputs (Expected | Bear | Bull):<br>t = 1 Year: ₹{exp_1y:,.2f} | ₹{max(0, bear_1y):,.2f} | ₹{bull_1y:,.2f}<br>t = 5 Years: ₹{exp_5y:,.2f} | ₹{max(0, bear_5y):,.2f} | ₹{bull_5y:,.2f}</p>", unsafe_allow_html=True)
        # Display Table
        st.dataframe(
            proj_df,
            use_container_width=True,
            column_config={
                "Bear Case (Poor)": st.column_config.NumberColumn(format="₹ %.2f"),
                "Expected Value": st.column_config.NumberColumn(format="₹ %.2f"),
                "Bull Case (Great)": st.column_config.NumberColumn(format="₹ %.2f")
            },
            hide_index=True
        )
    else:
        st.info("Add some assets to see future projections.")

with tab6:
    import datetime as _dt

    # ── Inject CSS ─────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .news-card {
        background: rgba(255,255,255,0.03);
        border: 1px solid rgba(255,255,255,0.07);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.2rem;
        backdrop-filter: blur(6px);
    }
    .art-card {
        background: rgba(255,255,255,0.025);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        transition: background 0.2s;
    }
    .art-card:hover { background: rgba(255,255,255,0.05); }
    .art-link {
        color: #e2e8f0;
        text-decoration: none;
        font-weight: 600;
        font-size: 0.95rem;
        line-height: 1.4;
        transition: color 0.2s, text-shadow 0.2s;
    }
    .art-link:hover {
        color: #7dd3fc;
        text-shadow: 0 0 8px rgba(125,211,252,0.6);
    }
    .badge {
        display: inline-block;
        font-size: 0.72rem;
        font-family: 'JetBrains Mono', monospace;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 6px;
        background: rgba(0,0,0,0.4);
    }
    .summary-bar {
        background: rgba(125,211,252,0.06);
        border: 1px solid rgba(125,211,252,0.15);
        border-radius: 12px;
        padding: 0.9rem 1.4rem;
        margin-bottom: 1.6rem;
        font-size: 0.9rem;
        color: #cbd5e1;
        font-family: 'Inter', sans-serif;
    }
    .skeleton {
        background: linear-gradient(90deg, rgba(255,255,255,0.04) 25%,
                    rgba(255,255,255,0.09) 50%, rgba(255,255,255,0.04) 75%);
        background-size: 400% 100%;
        animation: shimmer 1.4s infinite;
        border-radius: 10px;
        height: 100px;
        margin-bottom: 12px;
    }
    @keyframes shimmer {
        0%   { background-position: 100% 50%; }
        100% { background-position:   0% 50%; }
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Helpers ─────────────────────────────────────────────────────
    def _parse_pub_date(raw):
        if not raw:
            return None
        try:
            if isinstance(raw, (int, float)):
                return _dt.datetime.utcfromtimestamp(raw)
            return _dt.datetime.fromisoformat(str(raw)[:19])
        except Exception:
            return None

    def _render_article(art, idx):
        """Render a single article card as HTML."""
        sent_label = art.get('sentiment_label', '⚪ Neutral')
        art_color = (
            '#00ff87' if 'Positive' in sent_label
            else '#ff4d6d' if 'Negative' in sent_label
            else 'transparent'
        )
        border = f'border-left: 3px solid {art_color};' if art_color != 'transparent' else ''

        conn_score = art.get('connection_score', 0)
        conn_badge = art.get('connection_badge', '⚪ Low')
        if conn_score >= 75:
            conn_color = '#ff4d6d'
        elif conn_score >= 40:
            conn_color = '#ffa600'
        else:
            conn_color = '#64748b'

        sent_color = '#00ff87' if 'Positive' in sent_label else '#ff4d6d' if 'Negative' in sent_label else '#94a3b8'
        score_val = art.get('score', 0.0)

        pub_dt = _parse_pub_date(art.get('date'))
        date_str = pub_dt.strftime('%d %b %Y') if pub_dt else ''
        provider  = art.get('provider', 'Unknown')
        title     = art.get('title', '(no title)')
        summary   = art.get('summary', '')
        link      = art.get('link', '#')
        # Cap summary to 2 lines via CSS max-height
        summary_snippet = (summary[:220] + '…') if len(summary) > 220 else summary

        return f"""
        <div class="art-card" style="{border}">
            <a class="art-link" href="{link}" target="_blank">{title}</a>
            <p style="font-size:0.78rem; color:#64748b; margin:4px 0 8px;">
                {provider} &bull; {date_str}
            </p>
            <span class="badge" style="color:{conn_color};">Relevance: {conn_badge} ({conn_score})</span>
            <span class="badge" style="color:{sent_color};">Sentiment: {score_val:+.2f}</span>
            <p style="font-size:0.82rem; color:#94a3b8; margin-top:8px; line-height:1.5;">{summary_snippet}</p>
        </div>
        """

    def _render_stock_card(asset_name, status, score, articles_html_list, article_count, stale_count):
        """Render the outer stock card header."""
        s_icon  = '🟢' if status == 'Bullish' else '🔴' if status == 'Bearish' else '⚪'
        s_color = '#00ff87' if status == 'Bullish' else '#ff4d6d' if status == 'Bearish' else '#94a3b8'
        stale_note = f' &middot; {stale_count} stale hidden' if stale_count else ''
        return f"""
        <div class="news-card">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.6rem;">
                <h4 style="margin:0; color:#fff; font-family:'Inter',sans-serif;">{asset_name}</h4>
                <span style="color:{s_color}; font-weight:700; font-size:0.9rem;">
                    {s_icon} {status} &nbsp;
                    <span style="font-family:'JetBrains Mono',monospace;">{score:+.2f}</span>
                </span>
            </div>
            <p style="margin:0 0 0.8rem; font-size:0.78rem; color:#64748b;">
                {article_count} article(s) today{stale_note}
            </p>
        """

    if not df.empty:
        _cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=30)

        # ── Summary bar ────────────────────────────────────────────
        # Use the cached sentiment computed at app startup
        _ps = portfolio_sentiment_score
        _ps_label = 'Bullish' if _ps > 0.15 else 'Bearish' if _ps < -0.15 else 'Neutral'
        _ps_color = '#00ff87' if _ps > 0.15 else '#ff4d6d' if _ps < -0.15 else '#94a3b8'

        # Retrieve per-stock statuses from session cache if available
        _cached_statuses = st.session_state.get('_news_statuses', {})
        _n_bull = sum(1 for v in _cached_statuses.values() if v == 'Bullish')
        _n_bear = sum(1 for v in _cached_statuses.values() if v == 'Bearish')
        _n_neut = len(current_assets) - _n_bull - _n_bear

        # Sentinel adj from session_state (set when prediction was computed)
        _sent_adj_disp = st.session_state.get('_sent_adj_display', None)
        _adj_part = (
            f" &nbsp;|&nbsp; Sentiment adjustment to tomorrow's prediction: "
            f"<span style='color:{'#00ff87' if _sent_adj_disp and _sent_adj_disp > 0 else '#ff4d6d' if _sent_adj_disp and _sent_adj_disp < 0 else '#94a3b8'};'"
            f">{f'{_sent_adj_disp:+.2f}' if _sent_adj_disp is not None else 'N/A'}</span>"
        ) if True else ''

        st.markdown(
            f"""<div class="summary-bar">
                <strong style='color:#7dd3fc;'>Today's Sentiment:</strong>
                &nbsp;
                <span style='color:#00ff87;'>🟢 {_n_bull} Bullish</span>
                &nbsp;&nbsp;&bull;&nbsp;&nbsp;
                <span style='color:#ff4d6d;'>🔴 {_n_bear} Bearish</span>
                &nbsp;&nbsp;&bull;&nbsp;&nbsp;
                <span style='color:#94a3b8;'>⚪ {_n_neut} Neutral</span>
                &nbsp;&nbsp; across your {len(current_assets)} holdings
                &nbsp;&nbsp;&bull;&nbsp;&nbsp;
                Overall: <span style='color:{_ps_color}; font-weight:700; font-family:"JetBrains Mono",monospace;'>{_ps:+.2f} ({_ps_label})</span>
                {_adj_part}
            </div>""",
            unsafe_allow_html=True
        )

        # ── Per-stock cards ─────────────────────────────────────────────
        _new_statuses = {}

        for asset_obj in current_assets:
            asset_name = asset_obj.name
            identifier = asset_obj.identifier

            if not identifier:
                st.warning(f"No valid identifier for {asset_name} — skipping.")
                continue

            # Loading skeleton shown while spinner spins
            _ph = st.empty()
            _ph.markdown('<div class="skeleton"></div>', unsafe_allow_html=True)

            try:
                with st.spinner(''):
                    sentiment_data = get_asset_sentiment(
                        identifier, stock_name=asset_name, limit=8
                    )

                # Filter stale
                fresh = []
                stale_count = 0
                for art in sentiment_data.get('articles', []):
                    pub_dt = _parse_pub_date(art.get('date'))
                    if pub_dt is None or pub_dt >= _cutoff:
                        fresh.append(art)
                    else:
                        stale_count += 1

                # Sort by connection score descending
                fresh.sort(key=lambda a: a.get('connection_score', 0), reverse=True)

                status = sentiment_data.get('status', 'Neutral')
                score  = sentiment_data.get('score', 0.0)
                _new_statuses[identifier] = status

                _ph.empty()  # remove skeleton

                # Build article HTML
                top4_html   = ''.join(_render_article(a, i) for i, a in enumerate(fresh[:4]))
                extra_html  = ''.join(_render_article(a, i+4) for i, a in enumerate(fresh[4:]))

                # Stock card header
                st.markdown(
                    _render_stock_card(asset_name, status, score, [], len(fresh), stale_count),
                    unsafe_allow_html=True
                )

                if fresh:
                    st.markdown(top4_html, unsafe_allow_html=True)
                    if extra_html:
                        with st.expander(f"Show {len(fresh) - 4} more article(s)"):
                            st.markdown(extra_html, unsafe_allow_html=True)
                else:
                    err = sentiment_data.get('error', '')
                    if err:
                        st.caption(f"No news available — {err}")
                    elif stale_count:
                        st.caption(f"All {stale_count} available articles are older than 30 days.")
                    else:
                        st.caption(f"No recent news found for {asset_name} — sentiment defaulting to neutral.")

                # Close card div
                st.markdown('</div>', unsafe_allow_html=True)

            except Exception:
                _ph.empty()
                st.markdown(
                    f'<div class="news-card"><h4 style="color:#94a3b8;">{asset_name}</h4>'
                    f'<p style="color:#64748b;">News unavailable — No news available</p></div>',
                    unsafe_allow_html=True
                )

        # Save statuses for summary bar next render
        if _new_statuses:
            st.session_state['_news_statuses'] = _new_statuses

        # ── News Archive section ──────────────────────────────────────────
        st.markdown('---')
        with st.expander('🗂️ News Archive — Browse past articles by date'):
            st.caption('Articles are saved every time news is fetched. Select a date to review what was circulating on that day.')

            _archive = get_archived_articles()  # full dict {ticker: [articles]}

            # Collect all dates present in the archive
            _all_dates = set()
            for _ticker_arts in _archive.values():
                for _a in _ticker_arts:
                    _d = _a.get('date', '')
                    if _d:
                        _all_dates.add(_d[:10])

            if not _all_dates:
                st.info('No archived articles yet. Articles will appear here after the first news fetch.')
            else:
                _min_date = _dt.date.fromisoformat(min(_all_dates))
                _max_date = _dt.date.fromisoformat(max(_all_dates))
                _sel_date = st.date_input(
                    'Select date',
                    value=_max_date,
                    min_value=_min_date,
                    max_value=_max_date,
                    key='news_archive_date',
                )
                _sel_str = str(_sel_date)

                _found_any = False
                for asset_obj in current_assets:
                    _ticker = asset_obj.identifier
                    if not _ticker:
                        continue
                    _ticker_arts = _archive.get(_ticker, [])
                    _day_arts = [
                        a for a in _ticker_arts
                        if a.get('date', '')[:10] == _sel_str
                    ]
                    if not _day_arts:
                        continue
                    _found_any = True

                    # Sort by connection_score descending
                    _day_arts.sort(key=lambda a: a.get('connection_score', 0), reverse=True)

                    _arch_status = 'Neutral'
                    _arch_score  = sum(a.get('sentiment_score', 0) for a in _day_arts) / len(_day_arts)
                    if _arch_score > 0.15: _arch_status = 'Bullish'
                    elif _arch_score < -0.15: _arch_status = 'Bearish'

                    # Map archive record fields to art-card expected keys
                    def _arch_to_art(a):
                        return {
                            'title':            a.get('title', ''),
                            'summary':          a.get('summary', ''),
                            'link':             a.get('url', '#'),
                            'provider':         a.get('provider', 'Archived'),
                            'date':             a.get('date', ''),
                            'score':            a.get('sentiment_score', 0.0),
                            'sentiment_label':  a.get('sentiment_label', '⚪ Neutral'),
                            'connection_score': a.get('connection_score', 0),
                            'connection_badge': ('🔴 High' if a.get('connection_score', 0) >= 75
                                                 else '🟡 Medium' if a.get('connection_score', 0) >= 40
                                                 else '⚪ Low'),
                        }

                    st.markdown(
                        _render_stock_card(asset_obj.name, _arch_status, _arch_score, [], len(_day_arts), 0),
                        unsafe_allow_html=True
                    )
                    st.markdown(
                        ''.join(_render_article(_arch_to_art(a), i) for i, a in enumerate(_day_arts)),
                        unsafe_allow_html=True
                    )
                    st.markdown('</div>', unsafe_allow_html=True)

                if not _found_any:
                    st.info(f'No articles archived for {_sel_str}.')

    else:
        st.info('Add some assets to see live news sentiment.')

# =============================================================================
# MICHAEL — Portfolio Intelligence Assistant (last tab)
# =============================================================================
with tab_michael:

    # ── Styles ────────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .m-header {
        background: linear-gradient(135deg,rgba(99,102,241,.12),rgba(168,85,247,.08));
        border:1px solid rgba(99,102,241,.25);
        border-left:4px solid #818cf8;
        border-radius:14px;
        padding:1.4rem 1.8rem;
        margin-bottom:1.4rem;
    }
    .m-header h2 {
        margin:0 0 .3rem 0;font-size:1.6rem;font-weight:700;
        background:linear-gradient(90deg,#818cf8,#c084fc);
        -webkit-background-clip:text;-webkit-text-fill-color:transparent;
        font-family:Inter,sans-serif;
    }
    .m-header p{margin:0;color:#94a3b8;font-size:.9rem}
    .cu{display:flex;justify-content:flex-end;margin:.7rem 0}
    .cu-b{background:rgba(99,102,241,.18);border:1px solid rgba(99,102,241,.3);
          border-radius:18px 18px 4px 18px;padding:.75rem 1.1rem;
          max-width:72%;color:#e2e8f0;font-size:.95rem;line-height:1.5}
    .cm{display:flex;justify-content:flex-start;margin:.7rem 0}
    .cm-w{max-width:78%}
    .cm-lbl{font-size:.72rem;font-family:"JetBrains Mono",monospace;color:#818cf8;
            font-weight:700;letter-spacing:1.5px;margin-bottom:4px;padding-left:4px}
    .cm-b{background:rgba(255,255,255,.04);border:1px solid rgba(255,255,255,.09);
          border-radius:4px 18px 18px 18px;padding:.85rem 1.1rem;
          color:#cbd5e1;font-size:.95rem;line-height:1.6;white-space:pre-wrap}
    .cm-ts{font-size:.68rem;color:#475569;margin-top:4px;padding-left:4px;
           font-family:"JetBrains Mono",monospace}
    .ti{display:flex;align-items:center;gap:5px;padding:.6rem 1rem}
    .td{width:7px;height:7px;border-radius:50%;background:#818cf8;
        animation:tb 1.2s infinite ease-in-out}
    .td:nth-child(2){animation-delay:.2s}
    .td:nth-child(3){animation-delay:.4s}
    @keyframes tb{0%,80%,100%{transform:scale(.7);opacity:.5}40%{transform:scale(1.1);opacity:1}}
    .m-notice{font-size:.78rem;color:#64748b;margin-top:4px}
    </style>
    """, unsafe_allow_html=True)

    # ── Header ────────────────────────────────────────────────────────────────
    st.markdown("""
    <div class="m-header">
      <h2>⚡ MICHAEL</h2>
      <p>Portfolio Intelligence Assistant &nbsp;&middot;&nbsp; Quantitative Unified Equity Surveillance Tracker</p>
    </div>
    """, unsafe_allow_html=True)

    # ── Session state ─────────────────────────────────────────────────────────
    if "michael_history" not in st.session_state:
        st.session_state.michael_history = []
    if "michael_api_key" not in st.session_state:
        st.session_state.michael_api_key = ""
    if "michael_pending" not in st.session_state:
        st.session_state.michael_pending = None

    # ── API key ───────────────────────────────────────────────────────────────
    key_set = bool(st.session_state.michael_api_key.strip())
    with st.expander("🔑 Gemini API Key" + (" ✅" if key_set else " — required"), expanded=not key_set):
        rk = st.text_input("API key", type="password",
            value=st.session_state.michael_api_key,
            key="michael_key_input", placeholder="AIza...",
            label_visibility="collapsed")
        if rk != st.session_state.michael_api_key:
            st.session_state.michael_api_key = rk
        st.markdown(
            '<div class="m-notice">🔒 Your key is never saved to disk and never logged.</div>',
            unsafe_allow_html=True)

    api_key = st.session_state.michael_api_key.strip()

    # ── Context builder (compact — target < 1000 tokens) ─────────────────────
    def _m_context():
        import datetime as _dt
        L = []

        # Section 1: Portfolio summary — totals + top 3 gainers/losers only
        L.append("=== PORTFOLIO SUMMARY ===")
        if not df.empty:
            tv   = summary.get("total_value", 0)
            icol = "Invested (₹)" if "Invested (₹)" in df.columns else "Invested"
            pcol = "P&L (₹)"      if "P&L (%)" in df.columns else "P&L"
            ppcol= "P&L %"        if "P&L %" in df.columns else "P&L %"
            ti   = df[icol].sum() if icol in df.columns else 0
            tp   = df[pcol].sum() if pcol in df.columns else 0
            tpp  = (tp / ti * 100) if ti > 0 else 0
            rs   = summary.get("portfolio_risk_score", 0)
            rb   = summary.get("portfolio_risk_bucket", "?")
            L += [
                f"Value: Rs.{tv:,.2f} | Invested: Rs.{ti:,.2f} | P&L: Rs.{tp:+,.2f} ({tpp:+.2f}%)",
                f"Risk: {rs:.1f}/100 ({rb})",
            ]
            if ppcol in df.columns:
                sorted_df = df.sort_values(ppcol, ascending=False)
                top3    = sorted_df.head(3)
                bottom3 = sorted_df.tail(3)
                L.append("Top 3 gainers:")
                for _, r in top3.iterrows():
                    L.append(f"  {r['Name']}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
                L.append("Top 3 losers:")
                for _, r in bottom3.iterrows():
                    L.append(f"  {r['Name']}: {r.get(ppcol,0):+.2f}% (Rs.{r.get(pcol,0):+,.2f})")
        else:
            L.append("No data.")

        # Section 2: EWMA state — last 2 learning entries only
        L += ["", "=== EWMA STATE ==="]
        try:
            from adaptive_engine import _load_state as _ae
            ae = _ae()
            ll = ae.get("learning_log", [])
            L += [
                f"mu_ewma: Rs.{ae.get('mu_ewma','?')} | sigma_ewma: Rs.{ae.get('sigma_ewma','?')}",
                f"days_trained: {ae.get('days_trained',0)} | bias_5d: Rs.{ll[-1].get('bias_5d',0):+.4f}" if ll else "days_trained: 0",
            ]
            if ll:
                L.append("Last 2 learning entries:")
                for e in ll[-2:]:
                    L.append(f"  {e['date']} ret=Rs.{e['actual_return']:+,.2f} mu:{e['mu_old']:+.2f}->{e['mu_new']:+.2f} err=Rs.{e['error']:+,.2f}")
        except Exception:
            L.append("EWMA unavailable.")

        # Section 3: Predictions — last 3 only
        L += ["", "=== RECENT PREDICTIONS (last 3) ==="]
        preds = get_predictions()
        for p in sorted(preds, key=lambda x: x["target_date"])[-3:]:
            act = f"Rs.{p['real_val']:,.2f}" if p.get("real_val") else "Pending"
            err = f"Rs.{(p['real_val']-p['expected_val']):+,.2f}" if p.get("real_val") else "-"
            L.append(f"  {p['target_date']} exp=Rs.{p['expected_val']:,.2f} act={act} err={err}")

        # Section 4: News — sentiment label + score only, no headlines
        L += ["", "=== NEWS SENTIMENT ==="]
        try:
            from news_sentiment import get_archived_articles as _ga
            arch = _ga()
            for a in current_assets:
                if not a.identifier: continue
                arts = [x for x in arch.get(a.identifier, []) if x.get("sentiment_score", 0) != 0]
                if arts:
                    sc = sum(x["sentiment_score"] for x in arts[:5]) / min(5, len(arts))
                    lb = "Bullish" if sc > 0.15 else "Bearish" if sc < -0.15 else "Neutral"
                    L.append(f"  {a.name}: {lb} ({sc:+.3f})")
        except Exception:
            L.append("News unavailable.")

        # Section 5: System state
        L += ["", "=== SYSTEM STATE ==="]
        now = _dt.datetime.now()
        mkt = now.weekday() < 5 and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30))
        L.append(f"{now.strftime('%Y-%m-%d %H:%M')} IST | Market: {'OPEN' if mkt else 'CLOSED'}")
        pending = [p for p in preds if not p.get("real_val")]
        if pending:
            L.append(f"Next pred: {pending[0]['target_date']} Rs.{pending[0]['expected_val']:,.2f}")

        ctx = "\n".join(L)
        print(f"[MICHAEL] Context size: {len(ctx)} chars / ~{len(ctx)//4} tokens", file=sys.stderr)
        return ctx

    # ── Gemini call — auto-probes model names until one works ─────────────────
    _GEMINI_MODELS = [
        "gemini-1.5-flash-latest",
        "gemini-1.5-flash",
        "gemini-1.5-pro-latest",
        "gemini-1.5-pro",
        "gemini-2.0-flash",
        "gemini-2.0-flash-lite",
        "gemini-pro",
    ]
    _GEMINI_BASE = "https://generativelanguage.googleapis.com/v1beta/models"

    def _m_gemini(key, q, ctx):
        import urllib.request, json as _j
        SYS = (
            "You are MICHAEL, the portfolio intelligence assistant for QUEST "
            "(Quantitative Unified Equity Surveillance Tracker). "
            "You have complete context about the user's real Indian stock market portfolio. "
            "You are knowledgeable about Indian markets, NSE stocks, ETFs, and quantitative finance. "
            "Personality: direct, confident, honest. Do not sugarcoat bad news. "
            "Ground every answer in the data provided. Never invent numbers. "
            "Keep responses concise. Use short paragraphs. Use Rs. for rupees. "
            "No markdown headers — plain text with line breaks."
        )
        full = f"{SYS}\n\n--- PORTFOLIO CONTEXT ---\n{ctx}\n--- END ---\n\nUser: {q}"
        payload = _j.dumps({
            "contents": [{"parts": [{"text": full}]}],
            "generationConfig": {"temperature": 0.7, "maxOutputTokens": 1024}
        }).encode()

        # Use cached working model if already discovered this session
        models_to_try = (
            [st.session_state["_michael_model"]]
            if "_michael_model" in st.session_state
            else _GEMINI_MODELS
        )

        last_error = "No models attempted."
        for model in models_to_try:
            url = f"{_GEMINI_BASE}/{model}:generateContent?key={key}"
            req = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            try:
                with urllib.request.urlopen(req, timeout=30) as r:
                    res = _j.loads(r.read().decode())
                # Cache this model so we don't probe on every message
                st.session_state["_michael_model"] = model
                print(f"[MICHAEL] Using model: {model}", file=sys.stderr)
                return res["candidates"][0]["content"]["parts"][0]["text"].strip()
            except urllib.error.HTTPError as e:
                body = e.read().decode("utf-8", errors="ignore")
                print(f"[MICHAEL] HTTP {e.code} for model '{model}': {body}", file=sys.stderr)
                if e.code in (400, 403):
                    return "__BAD_KEY__"
                # 429 or 404 — try the next model before giving up
                last_error = f"HTTP {e.code}: {body[:400]}"
                continue
            except Exception as ex:
                print(f"[MICHAEL] Exception for model '{model}': {ex}", file=sys.stderr)
                last_error = str(ex)
                continue

        # All models exhausted — return the last error body so user can diagnose
        return f"__RATE_LIMIT__ {last_error}"

    # ── Send / process helpers ────────────────────────────────────────────────
    def _m_send(q):
        if not q.strip(): return
        ts = datetime.now().strftime("%H:%M")
        st.session_state.michael_history.append({"role": "user", "text": q.strip(), "ts": ts})
        if len(st.session_state.michael_history) > 20:
            st.session_state.michael_history = st.session_state.michael_history[-20:]
        st.session_state.michael_pending = q.strip()

    def _m_process():
        q = st.session_state.michael_pending
        if not q: return
        st.session_state.michael_pending = None
        raw = _m_gemini(api_key, q, _m_context())
        ts = datetime.now().strftime("%H:%M")
        if raw == "__BAD_KEY__":
            txt = ("MICHAEL is unavailable — the API key is invalid or the Generative Language API "
                   "is not enabled for this key. Go to https://aistudio.google.com, create a new key, "
                   "and paste it above.")
        elif raw.startswith("__RATE_LIMIT__"):
            detail = raw[len("__RATE_LIMIT__"):].strip()
            txt = (f"All Gemini models returned an error. Most likely cause: the Generative Language "
                   f"API is not enabled for your key, or you have no quota.\n\n"
                   f"Go to https://aistudio.google.com and create a fresh API key, then paste it above.\n\n"
                   f"Raw error from Google: {detail}")
        elif raw.startswith("__ERROR__"):
            txt = f"MICHAEL error: {raw[9:].strip()}"
        else:
            txt = raw
        st.session_state.michael_history.append({"role": "michael", "text": txt, "ts": ts})

    # ── Main UI ───────────────────────────────────────────────────────────────
    if not api_key:
        st.info("🔑 Please enter your Gemini API key above to activate MICHAEL.")
    else:
        history = st.session_state.michael_history

        if not history:
            # Welcome + starter chips
            st.markdown("""
            <div class="cm">
              <div class="cm-w">
                <div class="cm-lbl">MICHAEL</div>
                <div class="cm-b">I am MICHAEL. I have read your portfolio. Ask me anything.</div>
                <div class="cm-ts">ready</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            starters = [
                f"Why is my risk score {summary.get('portfolio_risk_score', 0):.1f}?",
                "Which stock is dragging my portfolio the most?",
                "Was yesterday's prediction accurate?",
                "Should I be worried about IRCTC?",
                "What does today's news mean for my portfolio?",
            ]
            cols = st.columns(len(starters))
            for i, (c, q) in enumerate(zip(cols, starters)):
                with c:
                    if st.button(q, key=f"m_chip_{i}", use_container_width=True):
                        _m_send(q)
                        st.rerun()
        else:
            # Render history
            for msg in history:
                if msg["role"] == "user":
                    st.markdown(
                        f'<div class="cu"><div class="cu-b">{msg["text"]}</div></div>',
                        unsafe_allow_html=True)
                else:
                    st.markdown(
                        f'<div class="cm"><div class="cm-w">'                        f'<div class="cm-lbl">MICHAEL</div>'                        f'<div class="cm-b">{msg["text"]}</div>'                        f'<div class="cm-ts">{msg["ts"]}</div></div></div>',
                        unsafe_allow_html=True)
            # Typing indicator
            if st.session_state.michael_pending:
                st.markdown("""
                <div class="cm"><div class="cm-w">
                  <div class="cm-lbl">MICHAEL</div>
                  <div class="cm-b"><div class="ti">
                    <div class="td"></div><div class="td"></div><div class="td"></div>
                  </div></div>
                </div></div>
                """, unsafe_allow_html=True)

        # Process pending (API call)
        if st.session_state.michael_pending:
            _m_process()
            st.rerun()

        # Input bar
        st.markdown("<br>", unsafe_allow_html=True)
        ic, bc = st.columns([5, 1])
        with ic:
            user_input = st.text_input("Ask MICHAEL", key="michael_input",
                placeholder="Type your question...", label_visibility="collapsed")
        with bc:
            if st.button("Send ⚡", key="michael_send", use_container_width=True):
                if user_input.strip():
                    _m_send(user_input)
                    st.rerun()
