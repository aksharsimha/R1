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

# --- Auth imports ---
from login_page import render_login_page
from auth import clear_remember_me
import chat_system
import portfolio_ledger
import adaptive_engine
import news_sentiment
import firebase_db

# --- Page Config ---
st.set_page_config(page_title="Portfolio Risk Monitor", page_icon="📈", layout="wide")

# ══════════════════════════════════════════════════════════════════════════════
# Firebase Initialization — must come BEFORE auth
# ══════════════════════════════════════════════════════════════════════════════
firebase_db.init_firebase()

# ══════════════════════════════════════════════════════════════════════════════
# Authentication Gate — must come BEFORE any dashboard code
# ══════════════════════════════════════════════════════════════════════════════
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    render_login_page()  # This calls st.stop() internally

# ── User is authenticated — set up their data directory ──────────────────────
_user_info = st.session_state.user_info
_username = _user_info["username"]

# For backward compatibility, create a local data dir and redirect modules
# (portfolio_ledger and adaptive_engine still use file-based storage locally
# but data is also synced to Firebase for persistence)
import os
import firebase_sync
_HERE = os.path.dirname(os.path.abspath(__file__))
_user_data_dir = os.path.join(_HERE, "users", _username)
os.makedirs(_user_data_dir, exist_ok=True)

# Hydrate local files from Firestore (pull cloud data → local on each session start)
if "firebase_hydrated" not in st.session_state:
    try:
        firebase_sync.hydrate(_username, _user_data_dir)
    except Exception:
        pass  # offline, or a guest/demo user with no cloud data — keep going
    st.session_state.firebase_hydrated = True

portfolio_ledger.set_data_dir(_user_data_dir, username=_username)
adaptive_engine.set_data_dir(_user_data_dir, username=_username)
news_sentiment.set_data_dir(_user_data_dir)

# Store username and data dir in session for sync functions
st.session_state._quest_username = _username
st.session_state._quest_data_dir = _user_data_dir

# Re-import HOLDINGS_FILE after redirection so it points to user's directory
from portfolio_ledger import HOLDINGS_FILE

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

# ── Theme & design system (see ui_theme.py) ──
import ui_theme
ui_theme.init_theme()
st.markdown(ui_theme.css(), unsafe_allow_html=True)

# Auto-refresh every 30 seconds for near real-time updates
st_autorefresh(interval=30 * 1000, key="data_refresh")

# --- Sidebar: User Info & Logout ---
_hour = datetime.now().hour
_greeting = "Good morning" if _hour < 12 else "Good afternoon" if _hour < 17 else "Good evening"

st.sidebar.markdown(f"""
<div class="quest-profile-card">
    <div class="quest-profile-label">Signed in as</div>
    <div class="quest-profile-name">👤 {_user_info['display_name']}</div>
    <div class="quest-profile-user">@{_user_info['username']}</div>
</div>
""", unsafe_allow_html=True)

if st.sidebar.button("🚪 Sign Out", use_container_width=True, key="logout_btn"):
    clear_remember_me()
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.rerun()

ui_theme.theme_toggle()

st.sidebar.markdown("---")
section = st.sidebar.radio(
    "Navigate",
    ["Overview", "Planner", "Analytics", "Projections", "Insights", "News", "Activity", "Chat", "MICHAEL"],
    key="nav_section",
    label_visibility="collapsed",
)
st.sidebar.markdown("---")

# --- Sidebar: Interactive Controls ---
# NOTE: holdings.json is NEVER seeded here — it must exist on disk.
# If it is genuinely absent, load_holdings() below will raise a clear error.

# Load current assets for dropdowns
try:
    current_assets = load_holdings(HOLDINGS_FILE)
    asset_names = [a.name for a in current_assets]
except Exception:
    current_assets = []
    asset_names = []

# --- Main Dashboard ---
st.markdown(f"""
<div class="dashboard-header">
    <h1>⚡ QUEST</h1>
    <p>Quantitative Unified Equity Surveillance Tracker</p>
    <div style="margin-top:1rem;font-size:1.1rem;color:var(--q-text-3);font-weight:500;text-transform:none;letter-spacing:0;">
        {_greeting}, <span style="color:var(--q-text);font-weight:500;">{_user_info['display_name']}</span>
    </div>
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

# Safe defaults so a brand-new / empty portfolio never crashes the dashboard
summary.setdefault('portfolio_risk_score', 0.0)
summary.setdefault('portfolio_risk_bucket', 'LOW')
summary.setdefault('total_value', 0.0)
summary.setdefault('n_assets', 0)

import datetime as _dt
_today = _dt.date.today()
if section == "Overview":
    if df.empty:
        st.markdown(
            "<div class='q-card q-enter' style='margin-bottom:16px;border-left:3px solid var(--q-accent);border-radius:0 12px 12px 0;'>"
            "<div style='font-size:1.1rem;font-weight:500;color:var(--q-text);margin-bottom:4px;'>👋 Welcome to QUEST!</div>"
            "<div style='font-size:.9rem;color:var(--q-text-2);line-height:1.6;'>Your portfolio is empty. "
            "Scroll down to <b>＋ Add a stock</b> (type a company name and we'll find the ticker for you) — "
            "then your live value, risk score, news, and forecast all come to life.</div></div>",
            unsafe_allow_html=True)

    # ── Hero / Overview header (themed) ──────────────────────────────────────
    _pnl_pos = total_pnl >= 0
    _pnl_cls = 'q-pos' if _pnl_pos else 'q-neg'
    _pnl_sign = '+' if _pnl_pos else ''
    _score = summary.get('portfolio_risk_score', 0.0)
    _risk_bucket = summary.get('portfolio_risk_bucket', 'LOW')
    _risk_tone = 'pos' if _score <= 40 else 'warn' if _score <= 70 else 'neg'

    _mkt_status = summary.get('market_status', 'Unknown')
    _mkt_open = summary.get('market_open', False)
    _dominant_src = summary.get('dominant_source', 'historical')
    _mkt_tone = 'pos' if _mkt_open else 'neg'

    _src_map = {
        'nse_live':   ('Live · NSE real-time', 'pos'),
        'yfinance':   ('yfinance · ~15min delay', 'warn'),
        'cached':     ('Last-known price (cached)', 'accent'),
        'historical': ('Historical close', 'accent'),
    }
    _src_label, _src_tone = _src_map.get(_dominant_src, ('Historical close', 'accent'))

    # ── Animated hero: portfolio value + NIFTY/SENSEX benchmarks (count-up) ──
    _hp = ui_theme.palette()
    def _pill_cols(tone):
        return {
            'pos': (_hp['pos_weak'], _hp['pos']),
            'neg': (_hp['neg_weak'], _hp['neg']),
            'warn': (_hp['warn_weak'], _hp['warn']),
            'accent': (_hp['accent_weak'], _hp['accent']),
        }.get(tone, (_hp['accent_weak'], _hp['accent']))
    _mkt_bg, _mkt_fg = _pill_cols(_mkt_tone)
    _src_bg, _src_fg = _pill_cols(_src_tone)
    _pnl_color = _hp['pos'] if _pnl_pos else _hp['neg']
    _prev_val = float(st.session_state.get('_hero_prev_val', 0.0))
    _cur_val = float(summary['total_value'])
    st.session_state['_hero_prev_val'] = _cur_val

    @st.cache_data(ttl=300, show_spinner=False)
    def _fetch_index_quotes():
        out = {}
        try:
            import yfinance as yf
            for _k, _tk in (('NIFTY 50', '^NSEI'), ('SENSEX', '^BSESN')):
                try:
                    _fi = yf.Ticker(_tk).fast_info
                    _last = float(_fi.last_price)
                    _prev = float(_fi.previous_close)
                    out[_k] = {'last': _last, 'chg': ((_last - _prev) / _prev * 100) if _prev else 0.0}
                except Exception:
                    pass
        except Exception:
            pass
        return out
    _idx = _fetch_index_quotes()

    def _idx_card(label, data):
        if not data:
            return ''
        _c = _hp['pos'] if data['chg'] >= 0 else _hp['neg']
        _ar = '▲' if data['chg'] >= 0 else '▼'
        return (
            f"<div style='background:{_hp['surface_2']};border-radius:12px;padding:11px 14px;'>"
            f"<div style='font-size:.68rem;color:{_hp['text_3']};text-transform:uppercase;letter-spacing:.6px;'>{label}</div>"
            f"<div class='cu mono' data-start='0' data-target='{data['last']}' data-dec='2' "
            f"style='font-size:1.2rem;font-weight:500;color:{_hp['text']};margin-top:2px;'>{data['last']:,.2f}</div>"
            f"<div class='mono' style='font-size:.76rem;color:{_c};'>{_ar} {abs(data['chg']):.2f}%</div></div>"
        )
    _idx_html = _idx_card('NIFTY 50', _idx.get('NIFTY 50')) + _idx_card('SENSEX', _idx.get('SENSEX'))
    _idx_col = (f"<div style='flex:1;min-width:160px;display:flex;flex-direction:column;gap:10px;'>{_idx_html}</div>"
                if _idx_html else "")

    import streamlit.components.v1 as components
    _hero_comp = f'''<!doctype html><html><head><meta charset="utf-8">
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500&family=JetBrains+Mono:wght@400;500&display=swap');
    *{{margin:0;box-sizing:border-box;}} html,body{{background:transparent;}}
    body{{font-family:Inter,sans-serif;}}
    .mono{{font-family:"JetBrains Mono",monospace;}}
    .pill{{display:inline-flex;align-items:center;font-size:.72rem;padding:3px 10px;border-radius:999px;}}
    @keyframes fin{{from{{opacity:0;transform:translateY(8px);}}to{{opacity:1;transform:translateY(0);}}}}
    .fin{{animation:fin .5s cubic-bezier(.22,.61,.36,1) both;}}
    </style></head><body>
    <div class="fin" style="display:flex;gap:20px;flex-wrap:wrap;align-items:flex-start;">
      <div style="flex:2;min-width:240px;">
        <div style="font-size:.78rem;color:{_hp['text_3']};">Portfolio value</div>
        <div id="qv" class="cu mono" data-start="{_prev_val}" data-target="{_cur_val}" data-dec="2" data-prefix="₹" style="font-size:2.4rem;font-weight:500;color:{_hp['text']};letter-spacing:-1.2px;line-height:1.1;">₹{_cur_val:,.2f}</div>
        <div class="mono" style="font-size:1rem;font-weight:500;margin-top:2px;color:{_pnl_color};">{_pnl_sign}{total_pnl_perc:.2f}% · {_pnl_sign}₹{total_pnl:,.2f}</div>
        <div style="display:flex;gap:8px;margin-top:10px;flex-wrap:wrap;">
          <span class="pill" style="background:{_mkt_bg};color:{_mkt_fg};">{_mkt_status}</span>
          <span class="pill" style="background:{_src_bg};color:{_src_fg};">{_src_label}</span>
        </div>
      </div>
      {_idx_col}
    </div>
    <script>
    (function(){{
      var rm=window.matchMedia('(prefers-reduced-motion:reduce)').matches;
      function fmt(n,dec,prefix){{return (prefix||'')+Number(n).toLocaleString('en-IN',{{minimumFractionDigits:dec,maximumFractionDigits:dec}});}}
      document.querySelectorAll('.cu').forEach(function(el){{
        var start=parseFloat(el.getAttribute('data-start'))||0;
        var target=parseFloat(el.getAttribute('data-target'))||0;
        var dec=parseInt(el.getAttribute('data-dec')||'2');
        var prefix=el.getAttribute('data-prefix')||'';
        if(rm||Math.abs(target-start)<0.01){{el.textContent=fmt(target,dec,prefix);return;}}
        var t0=null,d=1100;
        requestAnimationFrame(function s(ts){{if(!t0)t0=ts;var p=Math.min((ts-t0)/d,1);var e=1-Math.pow(1-p,3);el.textContent=fmt(start+(target-start)*e,dec,prefix);if(p<1)requestAnimationFrame(s);}});
      }});
    }})();
    </script></body></html>'''
    components.html(_hero_comp, height=185)

    st.markdown(f'''
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin:4px 0 22px;">
      <div class="q-metric q-enter" style="animation-delay:.05s;"><div class="lbl">Invested</div><div class="val">₹{total_invested:,.2f}</div></div>
      <div class="q-metric q-enter" style="animation-delay:.10s;"><div class="lbl">Assets</div><div class="val">{summary['n_assets']}</div></div>
      <div class="q-metric q-enter" style="animation-delay:.15s;"><div class="lbl">Risk score</div><div class="val" style="color:var(--q-{_risk_tone});">{_score:.1f} · {_risk_bucket.title()}</div></div>
    </div>
    ''', unsafe_allow_html=True)

    # ── Market Holiday Calendar (Google-Calendar style) ──────────────────────
    import calendar as _calmod
    import datetime as _dt
    import nse_live as _nse

    @st.cache_data(ttl=604800, show_spinner=False)  # refresh weekly
    def _load_market_holidays():
        try:
            _nse.refresh_holiday_calendar()
        except Exception:
            pass
        return _nse.get_holiday_calendar()

    _holidays_map = _load_market_holidays()
    _today = _dt.date.today()
    _pal = ui_theme.palette()

    # Load the user's Planner events so the Overview calendar reflects them too
    import json as _ovj, os as _ovo
    try:
        with open(_ovo.path.join(st.session_state.get("_quest_data_dir", "."), "events.json"), encoding="utf-8") as _ovf:
            _ov_events_raw = _ovj.load(_ovf)
    except Exception:
        _ov_events_raw = []
    _ov_evset = {}
    for _ove in _ov_events_raw:
        _ov_evset.setdefault(_ove.get("date", ""), []).append(_ove.get("title", ""))

    if 'cal_offset' not in st.session_state:
        st.session_state.cal_offset = 0

    # Resolve the displayed month from today + offset
    _base_idx = _today.year * 12 + (_today.month - 1) + st.session_state.cal_offset
    _disp_year, _disp_month = divmod(_base_idx, 12)
    _disp_month += 1

    _cprev, _ctitle, _cnext = st.columns([1, 4, 1])
    with _cprev:
        if st.button('‹', key='cal_prev', use_container_width=True):
            st.session_state.cal_offset -= 1
            st.rerun()
    with _cnext:
        if st.button('›', key='cal_next', use_container_width=True):
            st.session_state.cal_offset += 1
            st.rerun()
    with _ctitle:
        _hdr = _dt.date(_disp_year, _disp_month, 1).strftime('%B %Y')
        st.markdown(
            f"<div style='text-align:center;font-size:1.05rem;font-weight:500;"
            f"color:{_pal['text']};font-family:\"JetBrains Mono\",monospace;padding-top:6px;'>"
            f"{_hdr}</div>", unsafe_allow_html=True)

    # Build the month grid (weeks of datetime.date, Monday-first)
    _weeks = _calmod.Calendar(firstweekday=0).monthdatescalendar(_disp_year, _disp_month)
    _dow = "".join(
        f"<div style='text-align:center;font-size:0.68rem;color:{_pal['text_3']};"
        f"font-weight:500;text-transform:uppercase;letter-spacing:1px;padding:4px 0;'>{d}</div>"
        for d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
    )
    _cells = ""
    for _wk in _weeks:
        for _day in _wk:
            _ds = _day.strftime('%Y-%m-%d')
            _in_month = (_day.month == _disp_month)
            _is_today = (_day == _today)
            _is_weekend = (_day.weekday() >= 5)
            _hol_desc = _holidays_map.get(_ds)
            # base styling (theme-aware)
            _bg = "transparent"
            _color = _pal['text'] if _in_month else _pal['border_2']
            _border = "1px solid transparent"
            _extra = ""
            _title = ""
            if not _in_month:
                _color = _pal['border_2']
            elif _hol_desc:
                _bg = _pal['neg_weak']
                _color = _pal['neg']
                _border = f"1px solid {_pal['neg']}"
                _title = _hol_desc
            elif _is_weekend:
                _color = _pal['text_3']
            if _is_today:
                _border = f"2px solid {_pal['accent']}"
                _extra = "font-weight:500;"
            _has_ev = _in_month and _ds in _ov_evset
            if _has_ev:
                _dot = (f"<span style='display:block;width:5px;height:5px;border-radius:50%;"
                        f"background:{_pal['accent']};margin:2px auto 0;'></span>")
                _title = "; ".join(t for t in _ov_evset[_ds] if t) or _title
            elif _in_month and _hol_desc:
                _dot = (f"<span style='display:block;width:5px;height:5px;border-radius:50%;"
                        f"background:{_pal['neg']};margin:2px auto 0;'></span>")
            else:
                _dot = ""
            _cells += (
                f"<div title='{_title}' style='height:36px;display:flex;flex-direction:column;"
                f"align-items:center;justify-content:center;border-radius:7px;background:{_bg};"
                f"border:{_border};color:{_color};font-size:0.76rem;"
                f"font-family:\"JetBrains Mono\",monospace;{_extra}'>{_day.day}{_dot}</div>"
            )

    # Next upcoming holiday note
    _upcoming = sorted(d for d in _holidays_map if d >= _today.strftime('%Y-%m-%d'))
    if _upcoming:
        _nh = _upcoming[0]
        _nh_date = _dt.datetime.strptime(_nh, '%Y-%m-%d').date()
        _days_to = (_nh_date - _today).days
        _when = "today" if _days_to == 0 else ("tomorrow" if _days_to == 1 else f"in {_days_to} days")
        _next_note = (f"<span style='color:{_pal['neg']};'>●</span> Next holiday: "
                      f"<b style='color:{_pal['text']};'>{_holidays_map[_nh]}</b> "
                      f"<span style='color:{_pal['text_3']};'>· {_nh_date.strftime('%d %b')} ({_when})</span>")
    else:
        _next_note = f"<span style='color:{_pal['text_3']};'>No upcoming holidays on record.</span>"

    st.markdown(f"""
    <div class="q-card q-enter" style="margin-bottom:8px;">
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:4px;">{_dow}</div>
      <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:6px;">{_cells}</div>
      <div style="display:flex;justify-content:space-between;align-items:center;flex-wrap:wrap;
           gap:8px;margin-top:14px;padding-top:12px;border-top:1px solid {_pal['border']};
           font-size:0.72rem;">
        <div style="display:flex;gap:14px;color:{_pal['text_3']};">
          <span><span style="color:{_pal['accent']};">▢</span> Today</span>
          <span><span style="color:{_pal['accent']};">●</span> Event</span>
          <span><span style="color:{_pal['neg']};">●</span> Holiday</span>
          <span><span style="color:{_pal['text_3']};">▪</span> Weekend</span>
        </div>
        <div>{_next_note}</div>
      </div>
    </div>
    """, unsafe_allow_html=True)

    _risk_clicked = st.button('View Risk Breakdown ↗', key='risk_trigger_btn')
    if _risk_clicked:
        st.session_state.show_risk_breakdown = True
        st.rerun()

    st.markdown("---")

    if st.session_state.show_risk_breakdown:
        c_back, _ = st.columns([1, 4])
        if c_back.button("← Back to Dashboard"):
            st.session_state.show_risk_breakdown = False
            st.rerun()
        
        _rtab1, _rtab2 = st.tabs(["📊 Risk Breakdown", "🔬 Compare & Analyze"])
        with _rtab1:
            st.subheader("Composite Risk Score Breakdown")
            if not df.empty and total_invested > 0:
                # Gauge Chart for Score
                fig_gauge = go.Figure(go.Indicator(
                    mode = "gauge+number",
                    value = comp_score,
                    title = {'text': "Overall Risk Score"},
                    gauge = {
                        'axis': {'range': [0, 100], 'tickwidth': 1, 'tickcolor': _pal['text_3']},
                        'bar': {'color': _pal['accent'], 'thickness': 0.22},
                        'bgcolor': "rgba(0,0,0,0)",
                        'borderwidth': 1,
                        'bordercolor': _pal['border'],
                        'steps': [
                            {'range': [0, 40], 'color': _pal['pos_weak']},
                            {'range': [40, 70], 'color': _pal['warn_weak']},
                            {'range': [70, 100], 'color': _pal['neg_weak']}],
                        'threshold': {
                            'line': {'color': _pal['text'], 'width': 3},
                            'thickness': 0.75,
                            'value': comp_score}
                    }
                ))
                fig_gauge.update_layout(height=300, margin=dict(l=10, r=10, t=40, b=10), font=dict(family="Inter", color=_pal['text_2']), plot_bgcolor="rgba(0,0,0,0)", paper_bgcolor="rgba(0,0,0,0)")
                ui_theme.style_fig(fig_gauge)
                st.plotly_chart(fig_gauge, use_container_width=True)
        
                # Verdict
                bucket_color = _pal['pos'] if comp_score <= 40 else _pal['warn'] if comp_score <= 70 else _pal['neg']
                st.markdown(f"<h4 style='text-align: center; color: {bucket_color}; font-family: \"Inter\", sans-serif;'>Your portfolio carries {summary['portfolio_risk_bucket']} risk. The primary drivers are your highest-scoring components below.</h4>", unsafe_allow_html=True)
                st.markdown("---")
        
                def render_component(title, weight, score, text, formula):
                    c_color = _pal['pos'] if score <= 40 else _pal['warn'] if score <= 70 else _pal['neg']
                    contrib = score * (weight/100)
                    return f"""
                    <div style="background: var(--q-surface); border: 1px solid var(--q-border); border-radius: 12px; padding: 1.2rem; height: 100%; margin-bottom: 1rem; font-family: 'Inter', sans-serif;">
                        <h4 style="margin-top: 0; margin-bottom: 0.2rem; color: var(--q-text);">{title}</h4>
                        <p style="color: var(--q-text-3); font-size: 0.8rem; margin-top: 0;">Weight: {weight}% | Contributes {contrib:.1f} pts</p>
                        <div style="display: flex; align-items: center; margin-bottom: 1rem;">
                            <div style="flex-grow: 1; background: var(--q-surface-2); height: 8px; border-radius: 4px; overflow: hidden; margin-right: 15px;">
                                <div class="q-bar" style="width: {score}%; background: {c_color}; height: 100%;"></div>
                            </div>
                            <span style="font-family: 'JetBrains Mono', monospace; font-weight: 500; color: {c_color}; font-size: 1.2rem;">{score:.1f}</span>
                        </div>
                        <p style="color: #cbd5e1; font-size: 0.95rem; line-height: 1.5;">{text}</p>
                        <div style="background: rgba(0,0,0,0.3); border-radius: 6px; padding: 0.5rem; margin-top: 1rem;">
                            <code style="color: #38bdf8; font-family: 'JetBrains Mono', monospace; font-size: 0.75rem;">{formula}</code>
                        </div>
                    </div>
                    """
            
                r1, r2, r3 = st.columns(3)
                with r1:
                    st.html(render_component(
                        "Concentration Risk", 22, score_conc,
                        f"Your top asset ({top_asset['Name']}) holds {top_pct:.1f}% of your portfolio. If perfectly equal across {len(df)} assets, each would be {100/len(df):.1f}%.",
                        "HHI = \u03a3(w\u1d62\u00b2) \u00d7 10000"
                    ))

                with r2:
                    st.html(render_component(
                        "Volatility Risk", 22, score_vol,
                        f"Your portfolio's daily standard deviation is \u20b9{vol_rupees:,.2f} ({vol_daily_pct:.2f}%). On a bad day, expect to move this much.",
                        "\u03c3\u209a = \u221a(w\u1d40\u03a3w)"
                    ))

                with r3:
                    st.html(render_component(
                        "Drawdown Risk", 17, score_dd,
                        f"Your losing positions ({len(losers)} assets) collectively represent \u20b9{unrealised_loss:,.2f} of unrealised loss.",
                        "Loss Contrib = \u03a3(w\u1d62 \u00d7 |P&amp;L\u1d62|) for P&amp;L &lt; 0"
                    ))

                r4, r5, r6 = st.columns(3)
                with r4:
                    st.html(render_component(
                        "Correlation Risk", 12, score_corr,
                        f"Your average inter-asset correlation is {mean_corr:.2f}. A perfectly diversified portfolio would be close to 0.",
                        "Mean Corr = (2 / n(n-1)) \u00d7 \u03a3 \u03c1\u1d62\u2c7c"
                    ))

                with r5:
                    st.html(render_component(
                        "Momentum Risk", 12, score_mom,
                        f"{mom_count} out of {len(df)} assets are in a negative 1-month trend, representing {mom_weight*100:.1f}% of your portfolio by value.",
                        "Score = % Weight of Assets w/ 1M Ret &lt; 0"
                    ))

                with r6:
                    _sent_label = "Bullish" if portfolio_sentiment_score > 0.15 else "Bearish" if portfolio_sentiment_score < -0.15 else "Neutral"
                    st.html(render_component(
                        "News Sentiment Risk", 15, score_sent,
                        f"Based on today's financial news about your holdings. "
                        f"{_sentiment_neg_count} of your {len(current_assets)} stocks have negative news coverage right now. "
                        f"Overall portfolio sentiment is {_sent_label} ({portfolio_sentiment_score:+.2f}).",
                        "score = 50 \u2212 (sentiment_score \u00d7 40)"
                    ))

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

        with _rtab2:
            if not df.empty:
                # ── Compare & Analyze ────────────────────────────────────────────
                st.markdown("---")
                st.markdown("### 🔬 Compare & Analyze")
                import yfinance as _yf
                import urllib.request as _ur, urllib.parse as _up, json as _json

                def _cmp_lookup(name):
                    try:
                        u = "https://query2.finance.yahoo.com/v1/finance/search?q=" + _up.quote(name.strip())
                        rq = _ur.Request(u, headers={"User-Agent": "Mozilla/5.0"})
                        with _ur.urlopen(rq, timeout=4) as r:
                            d = _json.load(r)
                        qs = d.get("quotes", [])
                        for suf in (".NS", ".BO"):
                            for q in qs:
                                if str(q.get("symbol", "")).endswith(suf):
                                    return q["symbol"]
                        return qs[0].get("symbol") if qs else None
                    except Exception:
                        return None

                @st.cache_data(ttl=900, show_spinner=False)
                def _cmp_series(ticker, period="6mo"):
                    try:
                        h = _yf.Ticker(ticker).history(period=period)["Close"].dropna()
                        return h if len(h) > 5 else None
                    except Exception:
                        return None

                def _cmp_rsi(s, n=14):
                    d = s.diff()
                    up = d.clip(lower=0).rolling(n).mean()
                    dn = (-d.clip(upper=0)).rolling(n).mean()
                    rs = up / dn.replace(0, float('nan'))
                    return float((100 - 100 / (1 + rs)).iloc[-1])

                _ct1, _ct2 = st.tabs(["📈 Portfolio vs Market", "🔍 Compare stocks"])

                with _ct1:
                    try:
                        _pw = float((df["Weight %"] * df["1Y Ret %"]).sum() / 100.0)
                    except Exception:
                        _pw = float('nan')

                    @st.cache_data(ttl=900, show_spinner=False)
                    def _idx_ret(tk):
                        s = _cmp_series(tk, "1y")
                        if s is None or len(s) < 2:
                            return None
                        return float((s.iloc[-1] / s.iloc[0] - 1) * 100)
                    _nret, _sret = _idx_ret("^NSEI"), _idx_ret("^BSESN")
                    _bx = ["Your portfolio", "NIFTY 50", "SENSEX"]
                    _by = [_pw, _nret if _nret is not None else 0.0, _sret if _sret is not None else 0.0]
                    _figc = px.bar(x=_bx, y=_by, text=[f"{v:.1f}%" for v in _by],
                                   labels={"x": "", "y": "1-year return %"})
                    _figc.update_traces(marker_color=[_pal['accent'], _pal['text_3'], _pal['text_3']])
                    _figc.update_layout(height=300, margin=dict(t=10, b=0, l=0, r=0))
                    ui_theme.style_fig(_figc)
                    st.plotly_chart(_figc, use_container_width=True)
                    if _nret is not None and not pd.isna(_pw):
                        _delta = _pw - _nret
                        if _delta >= 0:
                            st.success(f"You're **beating NIFTY by {_delta:.1f}%** over the last year.")
                        else:
                            st.warning(f"You're **trailing NIFTY by {abs(_delta):.1f}%** over the last year.")

                with _ct2:
                    _names = st.text_input("Enter 2+ companies (comma-separated)",
                                           placeholder="e.g. Reliance, TCS, Infosys", key="cmp_names")
                    _cc1, _cc2 = st.columns(2)
                    _plbl = _cc1.selectbox("Period", ["1D", "1M", "3M", "6M", "1Y", "3Y", "5Y", "Custom"],
                                           index=3, key="cmp_period")
                    _ctype = _cc2.selectbox("Chart type", ["Line", "Area", "Bar", "Candlestick"], key="cmp_ctype")
                    _pmap = {"1D": ("1d", "15m"), "1M": ("1mo", "1d"), "3M": ("3mo", "1d"),
                             "6M": ("6mo", "1d"), "1Y": ("1y", "1d"), "3Y": ("3y", "1wk"), "5Y": ("5y", "1wk")}
                    _start = _end = None
                    if _plbl == "Custom":
                        import datetime as _cdt
                        _dc1, _dc2 = st.columns(2)
                        _start = _dc1.date_input("From", value=_cdt.date.today() - _cdt.timedelta(days=180), key="cmp_from")
                        _end = _dc2.date_input("To", value=_cdt.date.today(), key="cmp_to")

                    @st.cache_data(ttl=900, show_spinner=False)
                    def _cmp_fetch(ticker, plbl, start, end):
                        try:
                            if plbl == "Custom":
                                h = _yf.Ticker(ticker).history(start=str(start), end=str(end))
                            else:
                                _per, _iv = _pmap[plbl]
                                h = _yf.Ticker(ticker).history(period=_per, interval=_iv)
                            h = h.dropna()
                            return h if len(h) > 2 else None
                        except Exception:
                            return None

                    @st.cache_data(ttl=900, show_spinner=False)
                    def _cmp_indic(ticker):
                        """1-year-based indicators: RSI, 50/200 cross, MACD, 52-week position."""
                        out = {}
                        try:
                            s = _yf.Ticker(ticker).history(period="1y")["Close"].dropna()
                            if len(s) < 30:
                                return out
                            out["rsi"] = _cmp_rsi(s)
                            if len(s) >= 200:
                                _m50, _m200 = s.rolling(50).mean().iloc[-1], s.rolling(200).mean().iloc[-1]
                                out["trend"] = "🟢 Golden" if _m50 > _m200 else "🔴 Death"
                            else:
                                out["trend"] = "—"
                            _e12, _e26 = s.ewm(span=12).mean(), s.ewm(span=26).mean()
                            _macd = _e12 - _e26
                            _sigl = _macd.ewm(span=9).mean()
                            out["macd"] = "🟢 Bull" if _macd.iloc[-1] > _sigl.iloc[-1] else "🔴 Bear"
                            _hi, _lo = s.max(), s.min()
                            out["pos52"] = round((s.iloc[-1] - _lo) / (_hi - _lo) * 100) if _hi > _lo else None
                        except Exception:
                            pass
                        return out

                    @st.cache_data(ttl=3600, show_spinner=False)
                    def _cmp_fund(ticker):
                        try:
                            info = _yf.Ticker(ticker).info
                            return {"pe": info.get("trailingPE"), "mcap": info.get("marketCap"),
                                    "dy": info.get("dividendYield"), "beta": info.get("beta")}
                        except Exception:
                            return {}

                    if st.button("Compare", key="cmp_go") and _names.strip():
                        _resolved = []
                        for _n in [x.strip() for x in _names.split(",") if x.strip()]:
                            _sym = _cmp_lookup(_n)
                            if _sym:
                                _resolved.append((_n, _sym))
                        if not _resolved:
                            st.warning("Couldn't resolve any tickers from those names.")
                        else:
                            _norm = pd.DataFrame()
                            _rows = []
                            _ohlc_first, _first_sym = None, None
                            for _n, _sym in _resolved:
                                _h = _cmp_fetch(_sym, _plbl, _start, _end)
                                if _h is None or _h.empty:
                                    continue
                                _s = _h["Close"].dropna()
                                if len(_s) < 2:
                                    continue
                                if _ohlc_first is None:
                                    _ohlc_first, _first_sym = _h, _sym
                                _norm[_sym] = _s / _s.iloc[0] * 100
                                _ret = (_s.iloc[-1] / _s.iloc[0] - 1) * 100
                                _vol = _s.pct_change().std() * (252 ** 0.5) * 100
                                try:
                                    _r = _cmp_rsi(_s)
                                except Exception:
                                    _r = float('nan')
                                _ind = _cmp_indic(_sym)
                                _rsi_v = _ind.get("rsi", _r)
                                if pd.isna(_rsi_v):
                                    _rsi_v = _r
                                _ma = _s.rolling(min(200, len(_s))).mean().iloc[-1]
                                _above = _s.iloc[-1] > _ma
                                if not pd.isna(_rsi_v) and _rsi_v < 35 and _above:
                                    _sig = "🟢 Accumulate"
                                elif not pd.isna(_rsi_v) and _rsi_v > 70:
                                    _sig = "🔴 Overbought"
                                elif not _above:
                                    _sig = "🟠 Below 200-DMA"
                                else:
                                    _sig = "⚪ Neutral"
                                _rows.append({"Stock": _n, "Return %": round(_ret, 1),
                                              "Vol %": round(_vol, 1),
                                              "RSI": round(_rsi_v) if not pd.isna(_rsi_v) else None,
                                              "50/200": _ind.get("trend", "—"),
                                              "MACD": _ind.get("macd", "—"),
                                              "52w %": _ind.get("pos52"),
                                              "Signal": _sig})

                            if _ctype == "Candlestick" and _ohlc_first is not None:
                                _figk = go.Figure(go.Candlestick(
                                    x=_ohlc_first.index, open=_ohlc_first["Open"], high=_ohlc_first["High"],
                                    low=_ohlc_first["Low"], close=_ohlc_first["Close"], name=_first_sym))
                                _cl = _ohlc_first["Close"]
                                _sma20 = _cl.rolling(20).mean()
                                _std20 = _cl.rolling(20).std()
                                _figk.add_scatter(x=_ohlc_first.index, y=_sma20, mode="lines", name="SMA 20",
                                                  line=dict(width=1.2, color=_pal['accent']))
                                _figk.add_scatter(x=_ohlc_first.index, y=_sma20 + 2 * _std20, mode="lines", name="BB upper",
                                                  line=dict(width=1, color=_pal['text_3'], dash="dot"))
                                _figk.add_scatter(x=_ohlc_first.index, y=_sma20 - 2 * _std20, mode="lines", name="BB lower",
                                                  line=dict(width=1, color=_pal['text_3'], dash="dot"))
                                if len(_cl) >= 50:
                                    _figk.add_scatter(x=_ohlc_first.index, y=_cl.rolling(50).mean(), mode="lines",
                                                      name="SMA 50", line=dict(width=1.2, color=_pal['warn']))
                                _figk.update_layout(height=400, margin=dict(t=30, b=0, l=0, r=0),
                                                    title=f"{_first_sym} · {_plbl}", xaxis_rangeslider_visible=False)
                                ui_theme.style_fig(_figk)
                                st.plotly_chart(_figk, use_container_width=True)
                                if len(_resolved) > 1:
                                    st.caption("Candlestick shows the first stock only — use Line/Area/Bar to compare several.")
                            elif not _norm.empty:
                                _lbls = {"value": "Growth (rebased to 100)", "index": "", "variable": "Stock"}
                                if _ctype == "Bar":
                                    _fign = px.bar(_norm, barmode="group", labels=_lbls)
                                elif _ctype == "Area":
                                    _fign = px.area(_norm, labels=_lbls)
                                else:
                                    _fign = px.line(_norm, labels=_lbls)
                                _fign.update_layout(height=360, margin=dict(t=10, b=0, l=0, r=0))
                                ui_theme.style_fig(_fign)
                                st.plotly_chart(_fign, use_container_width=True)

                            if _rows:
                                st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
                                st.caption(f"{_plbl} window · 50/200, MACD, RSI, 52w computed on 1-year data · heuristic, not advice.")

                            if _first_sym:
                                _f = _cmp_fund(_first_sym)
                                if any(v is not None for v in _f.values()):
                                    with st.expander(f"📋 Fundamentals · {_first_sym}"):
                                        _fc = st.columns(4)
                                        _fc[0].metric("P/E", f"{_f['pe']:.1f}" if _f.get('pe') else "—")
                                        _fc[1].metric("Market cap", f"₹{_f['mcap']/1e7:,.0f} Cr" if _f.get('mcap') else "—")
                                        _fc[2].metric("Div yield", f"{_f['dy']*100:.2f}%" if _f.get('dy') else "—")
                                        _fc[3].metric("Beta", f"{_f['beta']:.2f}" if _f.get('beta') is not None else "—")

        st.stop() # Halt execution so the main dashboard doesn't render below the breakdown view

# Split view for Data and Insights
# ── Section routing (sidebar nav replaces 9 tabs) ──────────────────────────
_SEC_OF = {
    "tab1": "Overview",
    "tab2": "Analytics", "tab_math": "Analytics",
    "tab5": "Projections",
    "tab3": "Insights",
    "tab6": "News",
    "tab4": "Activity",
    "tab_chat": "Chat",
    "tab_michael": "MICHAEL",
}

def _active(name):
    """True if the tab's section is the one currently selected. Inactive
    sections are skipped entirely — no flash, and only one section's code
    runs per rerun (much faster)."""
    return section == _SEC_OF[name]

if _active("tab1"):
    st.markdown(
        f"<div style='font-size:1.15rem;font-weight:500;color:var(--q-text);margin-bottom:10px;'>"
        f"Holdings <span style='color:var(--q-text-3);'>· {len(df)}</span></div>",
        unsafe_allow_html=True,
    )

    if not df.empty:
        def _risk_tone(b):
            b = str(b).upper()
            return 'pos' if b == 'LOW' else 'warn' if b == 'MODERATE' else 'neg'

        _cards = ""
        for _, r in df.iterrows():
            _pos = r['P&L (₹)'] >= 0
            _cls = 'q-pos' if _pos else 'q-neg'
            _sgn = '+' if _pos else '−'
            _tone = _risk_tone(r['Risk Bucket'])
            _wt = min(float(r['Weight %']), 100.0)
            _barcol = 'var(--q-pos)' if _pos else 'var(--q-text-3)'
            _cards += (
                "<div class='q-card q-enter' style='padding:13px 16px;margin-bottom:8px;'>"
                "<div style='display:flex;justify-content:space-between;align-items:center;'>"
                "<div style='display:flex;align-items:center;gap:10px;'>"
                f"<span style='font-weight:500;color:var(--q-text);'>{r['Name']}</span>"
                f"<span class='q-pill' style='background:var(--q-surface-2);color:var(--q-text-2);'>{str(r['Type']).upper()}</span></div>"
                "<div style='text-align:right;font-family:\"JetBrains Mono\",monospace;'>"
                f"<div style='font-weight:500;color:var(--q-text);'>₹{r['Current Value (₹)']:,.2f}</div>"
                f"<div class='{_cls}' style='font-size:.8rem;'>{_sgn}{abs(r['P&L %']):.2f}% · {_sgn}₹{abs(r['P&L (₹)']):,.2f}</div></div></div>"
                "<div style='display:flex;justify-content:space-between;align-items:center;margin-top:7px;font-size:.72rem;color:var(--q-text-3);'>"
                f"<span style='font-family:\"JetBrains Mono\",monospace;'>{r['Quantity']:g} units · invested ₹{r['Invested (₹)']:,.2f}</span>"
                f"{ui_theme.pill(str(r['Risk Bucket']).title() + ' risk', _tone)}</div>"
                "<div style='height:5px;background:var(--q-surface-2);border-radius:3px;margin-top:9px;overflow:hidden;'>"
                f"<div class='q-bar' style='width:{_wt:.1f}%;height:100%;background:{_barcol};'></div></div></div>"
            )
        st.markdown(_cards, unsafe_allow_html=True)

        # ── Inline management (replaces the sidebar Portfolio Manager) ──
        def _lookup_ticker(name):
            """Resolve a company name → exchange ticker via Yahoo search (prefers NSE)."""
            if not name or not name.strip():
                return None
            try:
                import urllib.request, urllib.parse, json as _json
                url = "https://query2.finance.yahoo.com/v1/finance/search?q=" + urllib.parse.quote(name.strip())
                req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
                with urllib.request.urlopen(req, timeout=4) as r:
                    data = _json.load(r)
                quotes = data.get("quotes", [])
                # Prefer NSE (.NS), then BSE (.BO), else first equity match
                for suffix in (".NS", ".BO"):
                    for q in quotes:
                        if str(q.get("symbol", "")).endswith(suffix):
                            return q["symbol"]
                return quotes[0].get("symbol") if quotes else None
            except Exception:
                return None

        with st.expander("＋  Add a stock"):
            _na = st.text_input("Company / fund name", key="ov_add_name",
                                placeholder="e.g. Reliance Industries")
            _cfind, _cnote = st.columns([1, 2])
            with _cfind:
                if st.button("🔎 Find ticker", key="ov_find_ticker", use_container_width=True):
                    _sym = _lookup_ticker(st.session_state.get("ov_add_name", ""))
                    if _sym:
                        st.session_state["ov_add_id"] = _sym
                        st.session_state["_ov_lookup_msg"] = ("ok", _sym)
                    else:
                        st.session_state["_ov_lookup_msg"] = ("err", "")
            _msg = st.session_state.get("_ov_lookup_msg")
            if _msg and _msg[0] == "ok":
                _cnote.success(f"Found **{_msg[1]}** — verify below, then add.")
            elif _msg and _msg[0] == "err":
                _cnote.warning("No match found — enter the ticker manually.")

            _ty = st.selectbox("Type", [AssetType.EQUITY, AssetType.ETF, AssetType.MUTUAL_FUND, AssetType.DIGITAL_GOLD], key="ov_add_type")
            _id = st.text_input("Identifier (ticker / scheme code)", key="ov_add_id",
                                help="Auto-filled from the name — verify it's correct before adding.")
            _am = st.number_input("Invested amount (₹)", min_value=0.0, value=0.0, step=100.0, key="ov_add_amt")
            _qt = st.number_input("Quantity (units)", min_value=0.0, value=0.0, step=1.0, key="ov_add_qty")
            if st.button("Add stock", key="ov_add_submit"):
                if _na and add_asset(_na, _ty, _id, _am, _qt):
                    st.session_state.pop("_ov_lookup_msg", None)
                    st.success(f"Added {_na}")
                    time.sleep(0.6)
                    st.rerun()
                else:
                    st.error("Could not add (already exists or invalid).")

        with st.expander("✎  Edit amounts & quantities"):
            edited_df = st.data_editor(
                df.copy(),
                use_container_width=True,
                column_config={
                    "Invested (₹)": st.column_config.NumberColumn("Invested (₹)", min_value=0.0, format="₹ %.2f", step=0.01),
                    "Quantity": st.column_config.NumberColumn("Quantity", min_value=0.0, format="%.4f", step=0.0001),
                    "Current Value (₹)": st.column_config.NumberColumn("Current Value", format="₹ %.2f"),
                    "P&L (₹)": st.column_config.NumberColumn("P&L", format="₹ %.2f"),
                    "P&L %": st.column_config.NumberColumn("P&L %", format="%.2f%%"),
                    "Weight %": st.column_config.ProgressColumn("Weight %", format="%.1f %%", min_value=0, max_value=100),
                    "Risk Score": st.column_config.NumberColumn("Risk Score", format="%.1f"),
                    "Risk Bucket": st.column_config.TextColumn("Risk"),
                },
                disabled=["Risk Rank", "Name", "Type", "Last Price", "Current Value (₹)", "P&L (₹)", "P&L %", "Volatility %", "Beta", "Max DD %", "Sharpe", "1d VaR %", "1M Ret %", "6M Ret %", "1Y Ret %", "Total Return %", "Ann Return %", "Profit Factor", "Win Rate %", "RSI", "52w Pos", "Dist 200DMA %", "Risk Score", "Risk Bucket", "Weight %"],
                hide_index=True,
                key="portfolio_editor",
            )
            changes_made = False
            for idx, row in edited_df.iterrows():
                if df.loc[idx, "Invested (₹)"] != row["Invested (₹)"] or df.loc[idx, "Quantity"] != row["Quantity"]:
                    update_asset_holdings(row["Name"], float(row["Invested (₹)"]), float(row["Quantity"]))
                    changes_made = True
            if changes_made:
                st.success("Saved!")
                time.sleep(0.5)
                st.rerun()

        with st.expander("🗑  Remove a stock"):
            with st.form("ov_remove_form"):
                _rm = st.selectbox("Select stock to remove", list(df["Name"]))
                if st.form_submit_button("Remove"):
                    if remove_asset(_rm):
                        st.success(f"Removed {_rm}")
                        time.sleep(0.6)
                        st.rerun()

    else:
        st.info("No assets in portfolio yet. Use **＋ Add a stock** to get started.")

if _active("tab2"):
    st.subheader("Visual Analytics")
    if not df.empty and df["Current Value (₹)"].sum() > 0:
        c1, c2 = st.columns(2)
        
        with c1:
            st.markdown("**Portfolio Allocation (By Current Value)**")
            fig = px.pie(df[df["Current Value (₹)"] > 0], values='Current Value (₹)', names='Name', hole=0.62)
            # Clean look: percentages inside slices, hide labels for tiny ones
            fig.update_traces(
                textposition='inside', textinfo='percent', insidetextorientation='radial',
                texttemplate='%{percent:.0%}', sort=True,
                marker=dict(line=dict(color=ui_theme.palette()['bg'], width=2)),
            )
            fig.update_layout(
                margin=dict(t=0, b=0, l=0, r=0), uniformtext_minsize=10,
                uniformtext_mode='hide',
                legend=dict(orientation='v', y=0.5, font=dict(size=11)),
            )
            ui_theme.style_fig(fig)
            st.plotly_chart(fig, use_container_width=True)
            
        with c2:
            st.markdown("**Asset Correlation Matrix**")
            corr = summary.get("correlation_matrix", pd.DataFrame())
            if not corr.empty:
                fig2 = px.imshow(corr, text_auto=True, color_continuous_scale=['#1e3a5f', '#ffffff', '#7f1d1d'], range_color=[-1, 1], aspect='auto')
                fig2.update_xaxes(tickangle=45, tickfont=dict(size=12))
                fig2.update_yaxes(tickfont=dict(size=12))
                fig2.update_layout(margin=dict(t=0, b=0, l=0, r=0), height=max(400, len(corr.columns) * 48), autosize=True)
                ui_theme.style_fig(fig2)
                st.plotly_chart(fig2, use_container_width=True)
                
                with st.expander("∑ Show Math"):
                    st.markdown("<p style='font-family: \"JetBrains Mono\", monospace; color: #38bdf8;'>Formula: ρ(X,Y) = Cov(X,Y) / (σₓ · σᵧ)</p>", unsafe_allow_html=True)
                    corr_mat = corr.copy()
                    _corr_vals = corr_mat.values.copy()
                    np.fill_diagonal(_corr_vals, -1.0)
                    corr_mat = pd.DataFrame(_corr_vals, index=corr_mat.index, columns=corr_mat.columns)
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
                ui_theme.style_fig(fig_pca)
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

if _active("tab_math"):
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
        ui_theme.style_fig(fig_beta)
        st.plotly_chart(fig_beta, use_container_width=True)
        
        for _, row in beta_df.iterrows():
            st.markdown(f"**{row['Asset']}**: β = {row['Beta']:.2f} — {row['Systematic %']:.1f}% of its movement is explained by the overall market. Only {row['Idiosyncratic %']:.1f}% is unique to this asset.")
            
    else:
        st.info("Not enough historical data to run the Math Engine.")

if _active("tab3"):
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

if _active("tab4"):
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
                        
                        ui_theme.style_fig(fig)
                        st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.warning("No historical data found for this asset.")
                except Exception as e:
                    st.error(f"Could not fetch history: {e}")

if _active("tab5"):
    st.subheader("Future Portfolio Projections")

    # ── v2 risk/range forecast (the honest box) ──────────────────────────────
    if not df.empty and summary['total_value'] > 0:
        import prediction_engine as _pe
        import datetime as _vdt
        import nse_live as _vnse
        _vpal = ui_theme.palette()

        _nd = _vdt.date.today() + _vdt.timedelta(days=1)
        for _ in range(10):
            if _nd.weekday() < 5 and not _vnse.is_nse_holiday(_nd):
                break
            _nd += _vdt.timedelta(days=1)

        # Holdings as (ticker, quantity) — forecast anchors to the settled close
        from risk_analyzer import GOLD_PROXY as _GOLD, AssetType as _AT
        _holdings = []
        for _a in current_assets:
            _tk = _GOLD if _a.asset_type == _AT.DIGITAL_GOLD else _a.identifier
            if _tk and _a.asset_type != _AT.MUTUAL_FUND:
                _holdings.append((_tk, float(_a.quantity)))

        # ── Self-correction: grade matured forecasts, derive a bias (₹) from recent errors ──
        import json as _tj2, os as _to2
        _tlog_file = _to2.path.join(st.session_state.get("_quest_data_dir", "."), "v2_forecast_log.json")
        try:
            with open(_tlog_file, encoding="utf-8") as _tf:
                _tlog = _tj2.load(_tf)
        except Exception:
            _tlog = []
        _today_str = _vdt.date.today().strftime("%Y-%m-%d")
        _target_str = _nd.strftime("%Y-%m-%d")
        _cur_val = round(float(summary['total_value']), 2)
        for _e in _tlog:
            if _e.get("actual") is None and _e.get("target_date") == _today_str:
                _e["actual"] = _cur_val
                _e["error"] = round(_cur_val - _e["predicted"], 2)
                if _e.get("base") is not None:
                    _e["hit"] = ((_cur_val - _e["base"]) >= 0) == ((_e["predicted"] - _e["base"]) >= 0)
        _graded = [e for e in _tlog if e.get("actual") is not None and e.get("error") is not None]
        # bias = mean recent error (actual − predicted), clamped to ±0.5% of value
        _bias = 0.0
        if _graded:
            _recent_err = [e["error"] for e in sorted(_graded, key=lambda x: x["target_date"])[-10:]]
            _bias = sum(_recent_err) / len(_recent_err)
            _cap = 0.005 * _cur_val
            _bias = max(-_cap, min(_cap, _bias))

        # Forecast LOCKED per trading day (keyed by date) → one stable number everywhere
        @st.cache_data(ttl=86400, show_spinner="Training the forecast model on 5 years of data…")
        def _v2_forecast(holdings, day, bias, sent):
            return _pe.live_forecast(list(holdings), bias=bias, sentiment=sent)

        _fc = _v2_forecast(tuple(_holdings), _today_str,
                           round(float(_bias), 2),
                           round(float(portfolio_sentiment_score), 3))

        if _fc and not _fc.get("error"):
            _up = _fc['center_ret_pct'] >= 0
            _arrow = '▲' if _up else '▼'
            _tone = 'pos' if _up else 'neg'
            _acc = _fc['recent_dir_acc_pct'] if _fc['recent_dir_acc_pct'] is not None else '—'
            _sent_lbl = ('positive' if _fc['sentiment'] > 0.15
                         else 'negative' if _fc['sentiment'] < -0.15 else 'neutral')
            st.markdown(f"""
            <div class="q-card q-enter" style="margin-bottom:14px;">
              <div style="font-size:.8rem;color:var(--q-text-3);margin-bottom:10px;">Tomorrow's outlook · next trading day: <b style="color:var(--q-text);">{_nd.strftime('%a %d %b')}</b></div>
              <div style="display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;">
                <span class="q-mono" style="font-size:1.9rem;font-weight:500;color:var(--q-text);letter-spacing:-.5px;">₹{_fc['center']:,.2f}</span>
                <span class="q-mono" style="color:var(--q-{_tone});font-weight:500;font-size:1rem;">{_arrow} {abs(_fc['center_ret_pct']):.2f}%</span>
                <span class="q-pill" style="background:var(--q-warn-weak);color:var(--q-warn);">LOW confidence · {_acc}% directional</span>
              </div>
              <div style="margin-top:14px;display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px;">
                <div class="q-metric"><div class="lbl">Likely range · 68% (1σ)</div><div class="val">₹{_fc['range1_low']:,.2f} – ₹{_fc['range1_high']:,.2f}</div></div>
                <div class="q-metric"><div class="lbl">Wider range · 95% (2σ)</div><div class="val">₹{_fc['range2_low']:,.2f} – ₹{_fc['range2_high']:,.2f}</div></div>
              </div>
              <div style="margin-top:12px;font-size:.88rem;color:var(--q-text-2);line-height:1.9;">
                <div>📊 <b style="color:var(--q-text);">{_fc['p_big_move_pct']}%</b> chance of a move bigger than ±2%</div>
                <div>🛡️ <b>95% VaR:</b> you're unlikely to lose more than <b style="color:var(--q-text);">₹{_fc['var95']:,.2f}</b> tomorrow</div>
              </div>
              <div style="margin-top:14px;padding-top:12px;border-top:1px solid var(--q-border);">
                <div style="font-size:.76rem;color:var(--q-text-3);margin-bottom:7px;">What's driving it</div>
                <div style="display:flex;gap:8px;flex-wrap:wrap;">
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">Volatility · {_fc['vol_regime']} ({_fc['dvol_port_pct']}%/day)</span>
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">News · {_sent_lbl}</span>
                  <span class="q-pill" style="background:var(--q-surface-2);color:var(--q-text-2);">Momentum · {_fc['pos_momentum']}/{_fc['n_stocks']} trending up</span>
                </div>
              </div>
              <div style="margin-top:12px;font-size:.72rem;color:var(--q-text-3);line-height:1.6;">
                ⓘ Model scorecard: {_acc}% directional — barely above chance. <b style="color:var(--q-text-2);">Trust the range, not the arrow.</b> Range error beats the old EWMA model. Re-trained on fresh data each day.
              </div>
            </div>
            """, unsafe_allow_html=True)

            with st.expander("📋 Per-stock outlook"):
                _vrows = [{
                    "Stock": s['ticker'].replace('.NS', '').replace('.BO', ''),
                    "Est. move": f"{s['est_move_pct']:+.2f}%",
                    "Tomorrow range": f"₹{s['low']:.1f} – ₹{s['high']:.1f}",
                    "Daily vol": f"{s['dvol_pct']:.1f}%",
                    "Risk": ("🔴 " if s['flag'] == 'high vol' else "🟠 " if s['flag'] == 'elevated' else "🟢 ") + s['flag'],
                } for s in _fc['per_stock']]
                st.dataframe(pd.DataFrame(_vrows), use_container_width=True, hide_index=True)

            st.markdown("---")
            # ── Prediction tracker (v2): log each forecast, grade it next trading day ──
            import json as _tj2, os as _to2, datetime as _td2
            _tlog_file = _to2.path.join(st.session_state.get("_quest_data_dir", "."), "v2_forecast_log.json")
            try:
                with open(_tlog_file, encoding="utf-8") as _tf:
                    _tlog = _tj2.load(_tf)
            except Exception:
                _tlog = []
            _today_str = _td2.date.today().strftime("%Y-%m-%d")
            _target_str = _nd.strftime("%Y-%m-%d")
            _cur_val = round(float(summary['total_value']), 2)

            _changed = False
            for _e in _tlog:
                if _e.get("actual") is None and _e.get("target_date") == _today_str:
                    _e["actual"] = _cur_val
                    _e["error"] = round(_cur_val - _e["predicted"], 2)
                    if _e.get("base") is not None:
                        _e["hit"] = ((_cur_val - _e["base"]) >= 0) == ((_e["predicted"] - _e["base"]) >= 0)
                    _changed = True
            if not any(_e.get("target_date") == _target_str for _e in _tlog):
                _tlog.append({"made_on": _today_str, "target_date": _target_str,
                              "base": _cur_val, "predicted": round(float(_fc['center']), 2),
                              "actual": None, "error": None, "hit": None})
                _changed = True
            if _changed:
                try:
                    with open(_tlog_file, "w", encoding="utf-8") as _tf:
                        _tj2.dump(_tlog[-90:], _tf, indent=2)
                except Exception:
                    pass

            st.markdown("##### Prediction tracker")
            st.caption("Each forecast graded against what actually happened. Builds forward from today — honest, no backfilled guesses.")
            _graded = [e for e in _tlog if e.get("actual") is not None]
            if _graded:
                _hits = sum(1 for e in _graded if e.get("hit"))
                _dacc = _hits / len(_graded) * 100
                _mae = sum(abs(e["error"]) for e in _graded) / len(_graded)
                st.markdown(f"**Track record:** {len(_graded)} graded day(s) · directional accuracy **{_dacc:.0f}%** · avg error **₹{_mae:,.2f}**")
                _trows = [{"Target date": e["target_date"],
                           "Predicted": f"₹{e['predicted']:,.2f}",
                           "Actual": f"₹{e['actual']:,.2f}",
                           "Error": f"{e['error']:+,.2f}",
                           "Direction": ("hit ✅" if e.get("hit") else "miss ❌" if e.get("hit") is not None else "-")}
                          for e in sorted(_graded, key=lambda x: x["target_date"], reverse=True)[:15]]
                st.dataframe(pd.DataFrame(_trows), use_container_width=True, hide_index=True)
            else:
                _pending = [e for e in _tlog if e.get("actual") is None]
                if _pending:
                    _p = _pending[-1]
                    st.info(f"First forecast logged: ₹{_p['predicted']:,.2f} for {_p['target_date']}. "
                            f"It gets graded when you open QUEST on that trading day — the track record grows from here.")

if _active("tab6"):
    import datetime as _dt

    # ── Inject CSS ─────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .news-card {
        background: var(--q-surface);
        border: 1px solid var(--q-border);
        border-radius: 14px;
        padding: 1.2rem 1.4rem;
        margin-bottom: 1.2rem;
    }
    .art-card {
        background: var(--q-surface-2);
        border-radius: 10px;
        padding: 12px 14px;
        margin-bottom: 10px;
        transition: background 0.2s;
    }
    .art-card:hover { background: var(--q-accent-weak); }
    .art-link {
        color: var(--q-text);
        text-decoration: none;
        font-weight: 500;
        font-size: 0.95rem;
        line-height: 1.4;
        transition: color 0.2s;
    }
    .art-link:hover {
        color: var(--q-accent);
    }
    .badge {
        display: inline-block;
        font-size: 0.72rem;
        font-family: 'JetBrains Mono', monospace;
        padding: 2px 8px;
        border-radius: 4px;
        margin-right: 6px;
        background: var(--q-surface-2);
        color: var(--q-text-2);
    }
    .summary-bar {
        background: var(--q-accent-weak);
        border: 1px solid var(--q-border);
        border-radius: 12px;
        padding: 0.9rem 1.4rem;
        margin-bottom: 1.6rem;
        font-size: 0.9rem;
        color: var(--q-text-2);
        font-family: 'Inter', sans-serif;
    }
    .skeleton {
        background: var(--q-surface-2);
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
        _np = ui_theme.palette()
        sent_label = art.get('sentiment_label', '⚪ Neutral')
        art_color = (
            _np['pos'] if 'Positive' in sent_label
            else _np['neg'] if 'Negative' in sent_label
            else 'transparent'
        )
        border = f'border-left: 3px solid {art_color};' if art_color != 'transparent' else ''

        conn_score = art.get('connection_score', 0)
        conn_badge = art.get('connection_badge', '⚪ Low')
        if conn_score >= 75:
            conn_color = _np['neg']
        elif conn_score >= 40:
            conn_color = _np['warn']
        else:
            conn_color = _np['text_3']

        sent_color = _np['pos'] if 'Positive' in sent_label else _np['neg'] if 'Negative' in sent_label else _np['text_3']
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
            <p style="font-size:0.78rem; color:var(--q-text-3); margin:4px 0 8px;">
                {provider} &bull; {date_str}
            </p>
            <span class="badge" style="color:{conn_color};">Relevance: {conn_badge} ({conn_score})</span>
            <span class="badge" style="color:{sent_color};">Sentiment: {score_val:+.2f}</span>
            <p style="font-size:0.82rem; color:var(--q-text-2); margin-top:8px; line-height:1.5;">{summary_snippet}</p>
        </div>
        """

    def _render_stock_card(asset_name, status, score, articles_html_list, article_count, stale_count):
        """Render the outer stock card header."""
        _sp = ui_theme.palette()
        s_icon  = '🟢' if status == 'Bullish' else '🔴' if status == 'Bearish' else '⚪'
        s_color = _sp['pos'] if status == 'Bullish' else _sp['neg'] if status == 'Bearish' else _sp['text_3']
        stale_note = f' &middot; {stale_count} stale hidden' if stale_count else ''
        return f"""
        <div class="news-card">
            <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:0.6rem;">
                <h4 style="margin:0; color:var(--q-text); font-family:'Inter',sans-serif;">{asset_name}</h4>
                <span style="color:{s_color}; font-weight:700; font-size:0.9rem;">
                    {s_icon} {status} &nbsp;
                    <span style="font-family:'JetBrains Mono',monospace;">{score:+.2f}</span>
                </span>
            </div>
            <p style="margin:0 0 0.8rem; font-size:0.78rem; color:var(--q-text-3);">
                {article_count} article(s) today{stale_note}
            </p>
        """

    if not df.empty:
        _cutoff = _dt.datetime.utcnow() - _dt.timedelta(days=30)

        # ── Summary bar ────────────────────────────────────────────
        # Use the cached sentiment computed at app startup
        _nsp = ui_theme.palette()
        _ps = portfolio_sentiment_score
        _ps_label = 'Bullish' if _ps > 0.15 else 'Bearish' if _ps < -0.15 else 'Neutral'
        _ps_color = _nsp['pos'] if _ps > 0.15 else _nsp['neg'] if _ps < -0.15 else _nsp['text_3']

        # Retrieve per-stock statuses from session cache if available
        _cached_statuses = st.session_state.get('_news_statuses', {})
        _n_bull = sum(1 for v in _cached_statuses.values() if v == 'Bullish')
        _n_bear = sum(1 for v in _cached_statuses.values() if v == 'Bearish')
        _n_neut = len(current_assets) - _n_bull - _n_bear

        # Sentinel adj from session_state (set when prediction was computed)
        _sent_adj_disp = st.session_state.get('_sent_adj_display', None)
        _adj_color = (_nsp['pos'] if _sent_adj_disp and _sent_adj_disp > 0
                      else _nsp['neg'] if _sent_adj_disp and _sent_adj_disp < 0
                      else _nsp['text_3'])
        _adj_part = (
            f" &nbsp;|&nbsp; Prediction adjustment: "
            f"<span style='color:{_adj_color};'>{f'{_sent_adj_disp:+.2f}' if _sent_adj_disp is not None else 'N/A'}</span>"
        )

        st.markdown(
            f"""<div class="summary-bar" style="display:flex;flex-wrap:wrap;align-items:center;gap:16px;">
                <span style='color:var(--q-text-2);font-weight:500;'>Today's sentiment</span>
                <span style='color:{_nsp['pos']};'>● {_n_bull} bullish</span>
                <span style='color:{_nsp['neg']};'>● {_n_bear} bearish</span>
                <span style='color:var(--q-text-3);'>● {_n_neut} neutral</span>
                <span style='color:var(--q-text-3);'>across {len(current_assets)} holdings</span>
                <span style='margin-left:auto;color:var(--q-text-3);'>Overall
                  <span style='color:{_ps_color}; font-weight:500; font-family:"JetBrains Mono",monospace;'>{_ps:+.2f} ({_ps_label})</span>
                  {_adj_part}
                </span>
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
                    f'<div class="news-card"><h4 style="color:var(--q-text);">{asset_name}</h4>'
                    f'<p style="color:var(--q-text-3);">News unavailable — No news available</p></div>',
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
# 💬 CHAT TAB
# =============================================================================
if _active("tab_chat"):
    _chat_user = _user_info["username"]
    _chat_display = _user_info["display_name"]

    # ── Chat CSS ─────────────────────────────────────────────────────────────
    st.markdown("""
    <style>
        .chat-msg-row { display: flex; margin-bottom: 10px; }
        .chat-msg-row.sent { justify-content: flex-end; }
        .chat-msg-row.received { justify-content: flex-start; }
        .chat-msg-row.system-row { justify-content: center; }
        .chat-bubble {
            max-width: 70%;
            padding: 10px 14px;
            border-radius: 16px;
            font-size: 0.9rem;
            line-height: 1.45;
            word-wrap: break-word;
        }
        .chat-bubble.sent {
            background: var(--q-accent-weak);
            color: var(--q-text);
            border: 1px solid var(--q-accent);
            border-bottom-right-radius: 4px;
        }
        .chat-bubble.received {
            background: var(--q-surface-2);
            color: var(--q-text);
            border: 1px solid var(--q-border);
            border-bottom-left-radius: 4px;
        }
        .chat-bubble.system-msg {
            background: var(--q-surface-2);
            color: var(--q-text-3);
            font-size: 0.78rem;
            font-style: italic;
            padding: 6px 12px;
            border-radius: 8px;
        }
        .chat-sender {
            font-size: 0.72rem;
            color: var(--q-accent);
            font-weight: 500;
            margin-bottom: 3px;
        }
        .chat-time {
            font-size: 0.68rem;
            color: var(--q-text-3);
            margin-top: 4px;
        }
        .portfolio-card {
            background: var(--q-accent-weak);
            border: 1px solid var(--q-border);
            border-radius: 12px;
            padding: 12px 14px;
            margin-top: 6px;
        }
        .portfolio-card h4 { margin: 0 0 8px 0; color: var(--q-accent); font-size: 0.85rem; font-weight: 500; }
        .portfolio-card .val { font-family: 'JetBrains Mono', monospace; color: var(--q-text); font-weight: 500; }
        .portfolio-card .label { color: var(--q-text-3); font-size: 0.78rem; }
        .unread-badge {
            background: var(--q-accent-weak);
            color: var(--q-accent);
            font-size: 0.7rem;
            font-weight: 500;
            padding: 2px 7px;
            border-radius: 10px;
            margin-left: 8px;
        }
    </style>
    """, unsafe_allow_html=True)

    # ── Session state init ───────────────────────────────────────────────────
    if "active_chat_id" not in st.session_state:
        st.session_state.active_chat_id = None

    # ── Layout: sidebar + chat area ──────────────────────────────────────────
    chat_sidebar, chat_main = st.columns([1, 2.5])

    with chat_sidebar:
        st.markdown("#### 👥 Conversations")

        # ── Friend Requests ──────────────────────────────────────────────────
        pending = chat_system.get_friend_requests(_chat_user)
        if pending:
            with st.expander(f"📨 Friend Requests ({len(pending)})", expanded=True):
                for req_from in pending:
                    rc1, rc2, rc3 = st.columns([2, 1, 1])
                    rc1.markdown(f"**{req_from}**")
                    if rc2.button("✓", key=f"acc_{req_from}", help="Accept"):
                        chat_system.accept_friend_request(_chat_user, req_from)
                        st.rerun()
                    if rc3.button("✗", key=f"dec_{req_from}", help="Decline"):
                        chat_system.decline_friend_request(_chat_user, req_from)
                        st.rerun()

        # ── Chat list ────────────────────────────────────────────────────────
        user_chats = chat_system.get_user_chats(_chat_user)

        if user_chats:
            for chat_info in user_chats:
                cid = chat_info["chat_id"]
                name = chat_info["display_name"]
                unread = chat_info["unread"]
                icon = "👤" if chat_info["type"] == "direct" else "👥"

                # Build label
                label = f"{icon} {name}"
                if unread > 0:
                    label += f"  ({unread} new)"

                is_active = st.session_state.active_chat_id == cid
                if st.button(
                    label,
                    key=f"chat_sel_{cid}",
                    use_container_width=True,
                    type="primary" if is_active else "secondary"
                ):
                    st.session_state.active_chat_id = cid
                    chat_system.mark_as_read(cid, _chat_user)
                    st.rerun()
        else:
            st.caption("No conversations yet. Add a friend below!")

        st.markdown("---")

        # ── Add Friend ───────────────────────────────────────────────────────
        with st.expander("➕ Add Friend"):
            with st.form("add_friend_form", clear_on_submit=True, border=False):
                friend_username = st.text_input("Username", placeholder="Enter username", label_visibility="collapsed")
                if st.form_submit_button("Send Request", use_container_width=True):
                    if friend_username:
                        ok, msg = chat_system.send_friend_request(_chat_user, friend_username.strip().lower())
                        if ok:
                            st.success(msg)
                        else:
                            st.error(msg)
                        st.rerun()

        # ── Create Group ─────────────────────────────────────────────────────
        friends = chat_system.get_friends(_chat_user)
        if friends:
            with st.expander("👥 Create Group Chat"):
                with st.form("create_group_form", clear_on_submit=True, border=False):
                    group_name = st.text_input("Group Name", placeholder="e.g. Portfolio Crew", label_visibility="collapsed")
                    members = st.multiselect("Add friends", friends, key="grp_members")
                    if st.form_submit_button("Create Group", use_container_width=True):
                        if group_name and members:
                            ok, msg, gid = chat_system.create_group_chat(_chat_user, group_name, members)
                            if ok:
                                st.session_state.active_chat_id = gid
                                st.success(msg)
                            else:
                                st.error(msg)
                            st.rerun()

        # ── Sent requests ────────────────────────────────────────────────────
        sent = chat_system.get_sent_requests(_chat_user)
        if sent:
            with st.expander(f"📤 Sent Requests ({len(sent)})"):
                for s in sent:
                    st.caption(f"⏳ {s} — pending")

    # ── Chat Main Area ───────────────────────────────────────────────────────
    with chat_main:
        active_id = st.session_state.active_chat_id

        if not active_id:
            st.markdown("""
            <div style="display:flex;flex-direction:column;align-items:center;justify-content:center;min-height:400px;color:#334155;">
                <div style="font-size:3rem;margin-bottom:1rem;">💬</div>
                <div style="font-size:1.1rem;font-weight:500;">Select a conversation</div>
                <div style="font-size:0.85rem;margin-top:4px;">Or add a friend to start chatting</div>
            </div>
            """, unsafe_allow_html=True)
        else:
            chat_info = chat_system.get_chat_info(active_id)
            if not chat_info:
                st.error("Chat not found.")
            else:
                # Mark as read
                chat_system.mark_as_read(active_id, _chat_user)

                # ── Chat header ──────────────────────────────────────────────
                hdr1, hdr2, hdr3 = st.columns([3, 1, 1])
                with hdr1:
                    icon = "👤" if chat_info["type"] == "direct" else "👥"
                    if chat_info["type"] == "direct":
                        other = [p for p in chat_info["participants"] if p != _chat_user]
                        title = other[0] if other else "Chat"
                    else:
                        title = chat_info["name"]
                        members_str = ", ".join(chat_info["participants"])
                    st.markdown(f"### {icon} {title}")
                    if chat_info["type"] == "group":
                        st.caption(f"Members: {members_str}")
                with hdr2:
                    if st.button("🔄", key="chat_refresh", help="Refresh messages"):
                        st.rerun()
                with hdr3:
                    if st.button("📊", key="share_portfolio", help="Share portfolio"):
                        snapshot = chat_system.build_portfolio_snapshot(df, summary, _chat_user)
                        pnl_s = f"+₹{snapshot['total_pnl']:,.2f}" if snapshot['total_pnl'] >= 0 else f"-₹{abs(snapshot['total_pnl']):,.2f}"
                        text = f"📊 Portfolio Snapshot from {_chat_display}"
                        chat_system.send_message(
                            active_id, _chat_user, text,
                            msg_type="portfolio_share",
                            portfolio_data=snapshot,
                        )
                        st.rerun()

                st.markdown("---")

                # ── Messages ─────────────────────────────────────────────────
                messages = chat_system.get_messages(active_id, limit=100)

                if not messages:
                    st.caption("No messages yet. Say hello! 👋")
                else:
                    # Scrollable container
                    msgs_html = ""
                    for msg in messages:
                        ts = msg.get("timestamp", "")
                        try:
                            time_str = datetime.fromisoformat(ts).strftime("%I:%M %p")
                        except Exception:
                            time_str = ""

                        if msg.get("type") == "system":
                            msgs_html += f"""
                            <div class="chat-msg-row system-row">
                                <div class="chat-bubble system-msg">{msg['text']}</div>
                            </div>"""
                        elif msg["from"] == _chat_user:
                            # ── Sent message ─────────────────────────────────
                            bubble = f'<div class="chat-bubble sent">{msg["text"]}'
                            if msg.get("type") == "portfolio_share" and msg.get("portfolio_data"):
                                pd_data = msg["portfolio_data"]
                                pnl_color = "#34d399" if pd_data.get("total_pnl", 0) >= 0 else "#f87171"
                                bubble += f"""
                                <div class="portfolio-card">
                                    <h4>📊 {pd_data.get('username', 'User')}'s Portfolio</h4>
                                    <div class="label">Value</div>
                                    <div class="val">₹{pd_data.get('total_value', 0):,.2f}</div>
                                    <div class="label" style="margin-top:6px;">P&L</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('pnl_pct', 0):+.1f}%</div>
                                    <div class="label" style="margin-top:6px;">Risk</div>
                                    <div class="val">{pd_data.get('risk_score', 0):.0f} ({pd_data.get('risk_bucket', 'N/A')})</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row sent">{bubble}</div>'
                        else:
                            # ── Received message ─────────────────────────────
                            sender = msg["from"]
                            bubble = f'<div class="chat-bubble received"><div class="chat-sender">{sender}</div>{msg["text"]}'
                            if msg.get("type") == "portfolio_share" and msg.get("portfolio_data"):
                                pd_data = msg["portfolio_data"]
                                pnl_color = "#34d399" if pd_data.get("total_pnl", 0) >= 0 else "#f87171"
                                bubble += f"""
                                <div class="portfolio-card">
                                    <h4>📊 {pd_data.get('username', 'User')}'s Portfolio</h4>
                                    <div class="label">Value</div>
                                    <div class="val">₹{pd_data.get('total_value', 0):,.2f}</div>
                                    <div class="label" style="margin-top:6px;">P&L</div>
                                    <div class="val" style="color:{pnl_color}">{pd_data.get('pnl_pct', 0):+.1f}%</div>
                                    <div class="label" style="margin-top:6px;">Risk</div>
                                    <div class="val">{pd_data.get('risk_score', 0):.0f} ({pd_data.get('risk_bucket', 'N/A')})</div>
                                </div>"""
                            bubble += f'<div class="chat-time">{time_str}</div></div>'
                            msgs_html += f'<div class="chat-msg-row received">{bubble}</div>'

                    st.markdown(f'<div style="max-height:450px;overflow-y:auto;padding:8px 0;">{msgs_html}</div>', unsafe_allow_html=True)

                # ── Message input ────────────────────────────────────────────
                st.markdown("<br>", unsafe_allow_html=True)
                ic, bc = st.columns([5, 1])
                with ic:
                    new_msg = st.text_input(
                        "Message", key="chat_msg_input",
                        placeholder="Type a message...",
                        label_visibility="collapsed",
                    )
                with bc:
                    if st.button("Send", key="chat_send_btn", use_container_width=True):
                        if new_msg and new_msg.strip():
                            chat_system.send_message(active_id, _chat_user, new_msg)
                            st.rerun()

# =============================================================================
# ⚡ MICHAEL TAB (AI Chat Assistant)
# =============================================================================
if _active("tab_michael"):

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
        margin:0 0 .3rem 0;font-size:1.6rem;font-weight:500;
        color:var(--q-text);
        font-family:Inter,sans-serif;
    }
    .m-header p{margin:0;color:var(--q-text-3);font-size:.9rem}
    .cu{display:flex;justify-content:flex-end;margin:.7rem 0}
    .cu-b{background:var(--q-accent-weak);border:1px solid var(--q-accent);
          border-radius:18px 18px 4px 18px;padding:.75rem 1.1rem;
          max-width:72%;color:var(--q-text);font-size:.95rem;line-height:1.5}
    .cm{display:flex;justify-content:flex-start;margin:.7rem 0}
    .cm-w{max-width:78%}
    .cm-lbl{font-size:.72rem;font-family:"JetBrains Mono",monospace;color:var(--q-accent);
            font-weight:500;letter-spacing:1.5px;margin-bottom:4px;padding-left:4px}
    .cm-b{background:var(--q-surface-2);border:1px solid var(--q-border);
          border-radius:4px 18px 18px 18px;padding:.85rem 1.1rem;
          color:var(--q-text-2);font-size:.95rem;line-height:1.6;white-space:pre-wrap}
    .cm-ts{font-size:.68rem;color:var(--q-text-3);margin-top:4px;padding-left:4px;
           font-family:"JetBrains Mono",monospace}
    .ti{display:flex;align-items:center;gap:5px;padding:.6rem 1rem}
    .td{width:7px;height:7px;border-radius:50%;background:var(--q-accent);
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
    import json as _mcj, os as _mco
    _mchat_file = _mco.path.join(st.session_state.get("_quest_data_dir", "."), "michael_chat.json")

    def _m_persist():
        try:
            with open(_mchat_file, "w", encoding="utf-8") as _f:
                _mcj.dump(st.session_state.michael_history[-100:], _f, indent=2)
        except Exception:
            pass

    if "michael_history" not in st.session_state:
        # Load persisted conversation from the user's folder (memory across sessions)
        try:
            with open(_mchat_file, encoding="utf-8") as _f:
                st.session_state.michael_history = _mcj.load(_f)
        except Exception:
            st.session_state.michael_history = []
    if "michael_api_key" not in st.session_state:
        st.session_state.michael_api_key = ""
    if "michael_pending" not in st.session_state:
        st.session_state.michael_pending = None

    # ── Provider/key resolution: shared key (from secrets) first, user override second
    def _provider_of(k):
        return "groq" if k.startswith("gsk_") else "gemini"

    _shared_key = ""
    try:
        _shared_key = (str(st.secrets.get("GROQ_API_KEY", "")).strip()
                       or str(st.secrets.get("GEMINI_API_KEY", "")).strip())
    except Exception:
        _shared_key = ""

    if _shared_key:
        api_key = _shared_key
        provider = _provider_of(_shared_key)
        st.caption("⚡ MICHAEL is powered for you — no key needed.")
        with st.expander("Advanced · use your own key"):
            rk = st.text_input("Your Groq (gsk_…, free) or Gemini key", type="password",
                               value=st.session_state.michael_api_key,
                               key="michael_key_input", label_visibility="collapsed")
            if rk != st.session_state.michael_api_key:
                st.session_state.michael_api_key = rk
            if st.session_state.michael_api_key.strip():
                api_key = st.session_state.michael_api_key.strip()
                provider = _provider_of(api_key)
    else:
        key_set = bool(st.session_state.michael_api_key.strip())
        with st.expander("🔑 AI API Key" + (" ✅" if key_set else " — required"), expanded=not key_set):
            rk = st.text_input("Groq (gsk_…, free) or Gemini key", type="password",
                               value=st.session_state.michael_api_key,
                               key="michael_key_input", placeholder="gsk_...",
                               label_visibility="collapsed")
            if rk != st.session_state.michael_api_key:
                st.session_state.michael_api_key = rk
            st.markdown('<div class="m-notice">🔒 Never saved to disk or logged. '
                        'Get a free Groq key at console.groq.com.</div>', unsafe_allow_html=True)
        api_key = st.session_state.michael_api_key.strip()
        provider = _provider_of(api_key) if api_key else "gemini"

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

        # Section 5: System state (holiday-aware)
        L += ["", "=== SYSTEM STATE ==="]
        now = _dt.datetime.now()
        try:
            import nse_live as _nsl
            L.append(f"{now.strftime('%Y-%m-%d %H:%M')} IST | Market: {_nsl.get_market_status()}")
            _tom = (now + _dt.timedelta(days=1)).date()
            _nd = _tom
            for _ in range(10):
                if _nd.weekday() < 5 and not _nsl.is_nse_holiday(_nd):
                    break
                _nd = _nd + _dt.timedelta(days=1)
            if _tom.weekday() >= 5 or _nsl.is_nse_holiday(_tom):
                _why = "weekend" if _tom.weekday() >= 5 else _nsl.get_holiday_calendar().get(_tom.strftime('%Y-%m-%d'), 'holiday')
                L.append(f"IMPORTANT: tomorrow ({_tom}) is NOT a trading day ({_why}). "
                         f"Do not give a next-day prediction for it. Next trading day: {_nd}.")
        except Exception:
            mkt = now.weekday() < 5 and (9 <= now.hour < 15 or (now.hour == 15 and now.minute <= 30))
            L.append(f"{now.strftime('%Y-%m-%d %H:%M')} IST | Market: {'OPEN' if mkt else 'CLOSED'}")
        pending = [p for p in preds if not p.get("real_val")]
        if pending:
            L.append(f"Latest stored prediction target: {pending[0]['target_date']} "
                     f"Rs.{pending[0]['expected_val']:,.2f} (only meaningful on a trading day).")

        # Section 6: Planner — upcoming events + open to-do tasks
        L += ["", "=== PLANNER (calendar + to-do) ==="]
        try:
            import json as _mj, os as _mo
            _mpd = st.session_state.get("_quest_data_dir", ".")
            try:
                with open(_mo.path.join(_mpd, "events.json"), encoding="utf-8") as _mf:
                    _m_evs = _mj.load(_mf)
            except Exception:
                _m_evs = []
            try:
                with open(_mo.path.join(_mpd, "tasks.json"), encoding="utf-8") as _mf:
                    _m_tks = _mj.load(_mf)
            except Exception:
                _m_tks = []
            _tstr = _dt.date.today().strftime("%Y-%m-%d")
            _up = sorted([e for e in _m_evs if e.get("date", "") >= _tstr], key=lambda x: x.get("date", ""))[:5]
            if _up:
                L.append("Upcoming events:")
                for e in _up:
                    L.append(f"  {e.get('date')}: {e.get('title')}" + (f" — {e.get('note')}" if e.get('note') else ""))
            else:
                L.append("No upcoming events.")
            _open_t = [t for t in _m_tks if not t.get("done")]
            if _open_t:
                L.append(f"Open tasks ({len(_open_t)}):")
                for t in _open_t[:8]:
                    L.append(f"  [ ] {t.get('text')}")
            else:
                L.append("No open tasks.")
        except Exception:
            L.append("Planner unavailable.")

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
            "You are MICHAEL, the daily intelligence assistant inside QUEST — a personal "
            "investing + planning app for an Indian retail investor. "
            "You can see the user's live portfolio, risk metrics, predictions, news sentiment, "
            "AND their planner: upcoming calendar events and open to-do tasks. "
            "Behave like a proactive personal assistant: connect their schedule to their money — "
            "flag upcoming results/holidays, remind them of open tasks, relate market events to their holdings, "
            "and suggest what to focus on today. "
            "You are knowledgeable about Indian markets, NSE/BSE stocks, ETFs, and quantitative finance. "
            "PERSONALITY: you are a sharp, seasoned Mumbai trading-desk veteran — quick-witted, a little blunt, "
            "with dry humour, but genuinely in the user's corner. Open with one short line that fits the time of "
            "day and the market mood, then get to the point. Direct and honest — never sugarcoat bad news, but never preachy. "
            "Ground every answer in the data provided. Never invent numbers. "
            "Keep responses concise, short paragraphs, Rs. for rupees, plain text (no markdown headers)."
        )
        # Recent conversation for continuity (last few turns, excluding the current question)
        _hist = st.session_state.get("michael_history", [])
        _convo = ""
        for _hm in _hist[-7:-1]:
            _convo += f"{'User' if _hm.get('role') == 'user' else 'MICHAEL'}: {_hm.get('text','')}\n"
        full = f"{SYS}\n\n--- CONTEXT ---\n{ctx}\n--- END ---\n\n{_convo}User: {q}\nMICHAEL:"
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

    # ── Live-data tools MICHAEL can call on demand ────────────────────────────
    def _tool_quote(query):
        import urllib.request as _U, urllib.parse as _P, json as _J, yfinance as _yf2
        try:
            u = "https://query2.finance.yahoo.com/v1/finance/search?q=" + _P.quote(str(query))
            with _U.urlopen(_U.Request(u, headers={"User-Agent": "Mozilla/5.0"}), timeout=5) as r:
                qs = _J.load(r).get("quotes", [])
            sym = None
            for suf in (".NS", ".BO"):
                for q2 in qs:
                    if str(q2.get("symbol", "")).endswith(suf):
                        sym = q2["symbol"]; break
                if sym:
                    break
            if not sym and qs:
                sym = qs[0].get("symbol")
            if not sym:
                return _J.dumps({"error": f"no ticker found for '{query}'"})
            h = _yf2.Ticker(sym).history(period="1y")["Close"].dropna()
            if len(h) < 2:
                return _J.dumps({"ticker": sym, "error": "no price data"})
            last = float(h.iloc[-1])
            ret6 = (last / h.iloc[-126] - 1) * 100 if len(h) >= 126 else (last / h.iloc[0] - 1) * 100
            _d = h.diff(); _up = _d.clip(lower=0).rolling(14).mean(); _dn = (-_d.clip(upper=0)).rolling(14).mean()
            _rs = _up / _dn.replace(0, float('nan')); rsi = float((100 - 100 / (1 + _rs)).iloc[-1])
            m50 = h.rolling(50).mean().iloc[-1] if len(h) >= 50 else None
            m200 = h.rolling(200).mean().iloc[-1] if len(h) >= 200 else None
            trend = "golden_cross" if (m50 and m200 and m50 > m200) else ("death_cross" if (m50 and m200) else "n/a")
            hi, lo = h.max(), h.min()
            pos = round((last - lo) / (hi - lo) * 100) if hi > lo else None
            return _J.dumps({"ticker": sym, "price": round(last, 2), "six_month_return_pct": round(ret6, 1),
                             "rsi14": round(rsi), "trend_50_200": trend, "pct_of_52w_range": pos})
        except Exception as e:
            return _J.dumps({"error": str(e)})

    def _tool_index(name):
        import json as _J, yfinance as _yf2
        mp = {"nifty": "^NSEI", "nifty50": "^NSEI", "nifty 50": "^NSEI", "sensex": "^BSESN",
              "bank nifty": "^NSEBANK", "banknifty": "^NSEBANK", "nifty bank": "^NSEBANK"}
        tk = mp.get(str(name).lower().strip(), "^NSEI")
        try:
            fi = _yf2.Ticker(tk).fast_info
            last = float(fi.last_price); prev = float(fi.previous_close)
            return _J.dumps({"index": name, "value": round(last, 2),
                             "day_change_pct": round((last - prev) / prev * 100, 2)})
        except Exception as e:
            return _J.dumps({"error": str(e)})

    _TOOLS = [
        {"type": "function", "function": {
            "name": "get_quote",
            "description": "Get the LIVE price and key technical indicators (RSI, 50/200 trend, 52-week range "
                           "position, 6-month return) for ANY Indian stock by company name or ticker. Use this "
                           "whenever asked about a specific stock's market performance, or to ground a stock "
                           "recommendation in real current data.",
            "parameters": {"type": "object", "properties": {
                "query": {"type": "string", "description": "Company name or ticker, e.g. 'Reliance' or 'TCS.NS'"}},
                "required": ["query"]}}},
        {"type": "function", "function": {
            "name": "get_index",
            "description": "Get the live value and day change for an Indian market index (NIFTY 50, SENSEX, Bank Nifty).",
            "parameters": {"type": "object", "properties": {
                "name": {"type": "string", "description": "Index name: 'NIFTY 50', 'SENSEX', or 'Bank Nifty'"}},
                "required": ["name"]}}},
    ]

    def _m_groq(key, q, ctx):
        import urllib.request, json as _j
        SYS = (
            "You are MICHAEL, the daily intelligence assistant inside QUEST — a personal "
            "investing + planning app for an Indian retail investor. "
            "You can see the user's live portfolio, risk metrics, predictions, news sentiment, and planner "
            "(events + to-dos). You ALSO have live tools: get_quote (real-time price + indicators for any stock) "
            "and get_index (live NIFTY/SENSEX/Bank Nifty). ALWAYS call get_quote or get_index when asked about a "
            "specific stock, an index, or to recommend stocks — never quote prices from memory; fetch them. "
            "When recommending, name candidates then call get_quote on them to ground it in real data, and be clear "
            "these are research ideas, not advice. "
            "PERSONALITY: a sharp, seasoned Mumbai trading-desk veteran — quick-witted, a little blunt, dry humour, "
            "but genuinely in the user's corner. Open with one short line fitting the time of day and market mood, then "
            "get to the point. Direct and honest — never sugarcoat, never preachy. "
            "Ground every answer in the data/tools; never invent numbers. "
            "Concise, short paragraphs, Rs. for rupees, plain text (no markdown headers)."
        )
        msgs = [{"role": "system", "content": SYS + "\n\n--- CONTEXT ---\n" + ctx + "\n--- END ---"}]
        for _hm in st.session_state.get("michael_history", [])[-7:-1]:
            msgs.append({"role": "user" if _hm.get("role") == "user" else "assistant",
                         "content": _hm.get("text", "")})
        msgs.append({"role": "user", "content": q})
        H = {"Content-Type": "application/json", "Authorization": f"Bearer {key}",
             "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                           "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"}

        def _post(messages, use_tools=True):
            body = {"model": "llama-3.3-70b-versatile", "messages": messages,
                    "temperature": 0.6, "max_tokens": 1024}
            if use_tools:
                body["tools"] = _TOOLS
                body["tool_choice"] = "auto"
            req = urllib.request.Request("https://api.groq.com/openai/v1/chat/completions",
                                         data=_j.dumps(body).encode(), headers=H, method="POST")
            with urllib.request.urlopen(req, timeout=40) as r:
                return _j.loads(r.read().decode())

        try:
            m = {}
            for _round in range(4):  # allow a couple of tool round-trips
                try:
                    res = _post(msgs, use_tools=True)
                except urllib.error.HTTPError as _te:
                    _tb = _te.read().decode("utf-8", errors="ignore")
                    # Llama sometimes botches the tool-call format → answer without tools
                    if _te.code == 400 and "tool_use_failed" in _tb:
                        print("[MICHAEL/groq] tool_use_failed — retrying without tools", file=sys.stderr)
                        res = _post(msgs, use_tools=False)
                    else:
                        raise
                m = res["choices"][0]["message"]
                tcs = m.get("tool_calls")
                if not tcs:
                    return (m.get("content") or "").strip()
                msgs.append({"role": "assistant", "content": m.get("content"), "tool_calls": tcs})
                for tc in tcs:
                    fn = tc.get("function", {}).get("name", "")
                    try:
                        args = _j.loads(tc.get("function", {}).get("arguments") or "{}")
                    except Exception:
                        args = {}
                    if fn == "get_quote":
                        out = _tool_quote(args.get("query", ""))
                    elif fn == "get_index":
                        out = _tool_index(args.get("name", ""))
                    else:
                        out = _j.dumps({"error": "unknown tool"})
                    print(f"[MICHAEL/tool] {fn}({args}) -> {out[:120]}", file=sys.stderr)
                    msgs.append({"role": "tool", "tool_call_id": tc.get("id"), "content": out})
            return (m.get("content") or "I pulled the data but ran out of steps — ask me once more.").strip()
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="ignore")
            print(f"[MICHAEL/groq] HTTP {e.code}: {body}", file=sys.stderr)
            if e.code in (401, 403):
                return "__BAD_KEY__"
            return f"__RATE_LIMIT__ HTTP {e.code}: {body[:300]}"
        except Exception as ex:
            print(f"[MICHAEL/groq] {ex}", file=sys.stderr)
            return f"__RATE_LIMIT__ {ex}"

    def _m_ask(q, ctx):
        return _m_groq(api_key, q, ctx) if provider == "groq" else _m_gemini(api_key, q, ctx)

    # ── Send / process helpers ────────────────────────────────────────────────
    def _m_send(q):
        if not q.strip(): return
        # Per-session rate limit (protects the shared key): 15 msgs / 5 min
        import time as _mt
        _now = _mt.time()
        _hits = [t for t in st.session_state.get("_m_hits", []) if _now - t < 300]
        if len(_hits) >= 15:
            st.session_state.michael_history.append({
                "role": "michael", "ts": datetime.now().strftime("%H:%M"),
                "text": "You've hit the message limit (15 per 5 minutes). Give me a moment, then ask again."})
            return
        _hits.append(_now)
        st.session_state["_m_hits"] = _hits
        ts = datetime.now().strftime("%H:%M")
        st.session_state.michael_history.append({"role": "user", "text": q.strip(), "ts": ts})
        _m_persist()
        st.session_state.michael_pending = q.strip()

    def _m_process():
        q = st.session_state.michael_pending
        if not q: return
        st.session_state.michael_pending = None
        raw = _m_ask(q, _m_context())
        ts = datetime.now().strftime("%H:%M")
        if raw == "__BAD_KEY__":
            txt = ("MICHAEL is unavailable — the API key is invalid or not authorised. "
                   "Check the key in the app's secrets (Groq: console.groq.com).")
        elif raw.startswith("__RATE_LIMIT__"):
            detail = raw[len("__RATE_LIMIT__"):].strip()
            txt = ("MICHAEL hit a snag talking to the AI service (rate limit or a transient error). "
                   "Give it a moment and try again.\n\n"
                   f"Details: {detail}")
        elif raw.startswith("__ERROR__"):
            txt = f"MICHAEL error: {raw[9:].strip()}"
        else:
            txt = raw
        st.session_state.michael_history.append({"role": "michael", "text": txt, "ts": ts})
        _m_persist()

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
                <div class="cm-b">I am MICHAEL. I can see your portfolio, your risk, the news, and your planner (events + to-dos). Ask me anything — or get your daily briefing.</div>
                <div class="cm-ts">ready</div>
              </div>
            </div>
            """, unsafe_allow_html=True)
            starters = [
                "Give me my daily briefing",
                "What's on my plate today?",
                "Which stock is dragging my portfolio?",
                "Any events or results coming up?",
                "What should I focus on this week?",
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

        # Input bar — form clears the box automatically after sending
        st.markdown("<br>", unsafe_allow_html=True)
        with st.form("michael_form", clear_on_submit=True):
            ic, bc = st.columns([5, 1])
            user_input = ic.text_input("Ask MICHAEL", key="michael_input",
                placeholder="Type your question...", label_visibility="collapsed")
            _sent = bc.form_submit_button("Send ⚡", use_container_width=True)
        if _sent and user_input.strip():
            _m_send(user_input)
            st.rerun()

        if st.session_state.michael_history:
            if st.button("🗑 Clear MICHAEL's memory", key="m_clear"):
                st.session_state.michael_history = []
                _m_persist()
                st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# PLANNER — editable calendar + to-do (Overview keeps a read-only quick glance)
# ══════════════════════════════════════════════════════════════════════════════
if section == "Planner":
    import json as _pj, os as _po, calendar as _pcal, datetime as _pdt
    _ppal = ui_theme.palette()
    _pdir = st.session_state.get("_quest_data_dir", ".")
    _ev_file = _po.path.join(_pdir, "events.json")
    _tk_file = _po.path.join(_pdir, "tasks.json")

    def _pload(path, default):
        try:
            with open(path, encoding="utf-8") as f:
                return _pj.load(f)
        except Exception:
            return default

    def _psave(path, data):
        try:
            with open(path, "w", encoding="utf-8") as f:
                _pj.dump(data, f, indent=2)
        except Exception:
            pass

    _events = _pload(_ev_file, [])
    _tasks = _pload(_tk_file, [])

    st.markdown(
        f"<div style='font-size:1.4rem;font-weight:500;color:var(--q-text);margin-bottom:2px;'>Planner</div>"
        f"<div style='font-size:.85rem;color:var(--q-text-3);margin-bottom:14px;'>Your events and to-dos — "
        f"the Overview calendar is a read-only glance; edit here.</div>", unsafe_allow_html=True)

    _ptab1, _ptab2 = st.tabs(["📅 Calendar", "✓  To-do"])

    # ── Calendar tab ──────────────────────────────────────────────────────────
    with _ptab1:
        if "plan_offset" not in st.session_state:
            st.session_state.plan_offset = 0
        _ptoday = _pdt.date.today()
        _pbi = _ptoday.year * 12 + (_ptoday.month - 1) + st.session_state.plan_offset
        _pyr, _pmo = divmod(_pbi, 12)
        _pmo += 1

        _pc1, _pc2, _pc3 = st.columns([1, 4, 1])
        if _pc1.button("‹", key="plan_prev", use_container_width=True):
            st.session_state.plan_offset -= 1
            st.rerun()
        if _pc3.button("›", key="plan_next", use_container_width=True):
            st.session_state.plan_offset += 1
            st.rerun()
        _pc2.markdown(
            f"<div style='text-align:center;font-size:1.05rem;font-weight:500;color:var(--q-text);"
            f"font-family:\"JetBrains Mono\",monospace;padding-top:6px;'>"
            f"{_pdt.date(_pyr, _pmo, 1).strftime('%B %Y')}</div>", unsafe_allow_html=True)

        _ev_dates = {}
        for _e in _events:
            _ev_dates.setdefault(_e.get("date", ""), []).append(_e)
        try:
            import nse_live as _nse_p
            _hols = _nse_p.get_holiday_calendar()
        except Exception:
            _hols = {}

        _dow = "".join(
            f"<div style='text-align:center;font-size:.68rem;color:{_ppal['text_3']};"
            f"font-weight:500;text-transform:uppercase;letter-spacing:1px;padding:4px 0;'>{_d}</div>"
            for _d in ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"))
        _cells = ""
        for _wk in _pcal.Calendar(firstweekday=0).monthdatescalendar(_pyr, _pmo):
            for _day in _wk:
                _ds = _day.strftime("%Y-%m-%d")
                _in = _day.month == _pmo
                _color = _ppal['text'] if _in else _ppal['border_2']
                _border = "1px solid transparent"
                _extra = ""
                _title = ""
                if _ds in _hols and _in:
                    _border = f"1px solid {_ppal['neg']}"
                    _title = _hols[_ds]
                if _day == _ptoday:
                    _border = f"2px solid {_ppal['accent']}"
                    _extra = "font-weight:500;"
                _dots = ""
                if _in and _ds in _ev_dates:
                    _dots = f"<span style='display:block;width:5px;height:5px;border-radius:50%;background:{_ppal['accent']};margin:2px auto 0;'></span>"
                    _title = "; ".join(e.get("title", "") for e in _ev_dates[_ds])
                elif _in and _ds in _hols:
                    _dots = f"<span style='display:block;width:5px;height:5px;border-radius:50%;background:{_ppal['neg']};margin:2px auto 0;'></span>"
                _cells += (
                    f"<div title='{_title}' style='height:42px;display:flex;flex-direction:column;"
                    f"align-items:center;justify-content:center;border-radius:7px;border:{_border};"
                    f"color:{_color};font-size:.8rem;font-family:\"JetBrains Mono\",monospace;{_extra}'>{_day.day}{_dots}</div>")

        st.markdown(
            f"<div class='q-card q-enter' style='margin-bottom:10px;'>"
            f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:4px;'>{_dow}</div>"
            f"<div style='display:grid;grid-template-columns:repeat(7,1fr);gap:5px;margin-top:6px;'>{_cells}</div>"
            f"<div style='margin-top:12px;padding-top:10px;border-top:1px solid {_ppal['border']};font-size:.72rem;color:{_ppal['text_3']};'>"
            f"<span style='color:{_ppal['accent']};'>●</span> Your event &nbsp;&nbsp;"
            f"<span style='color:{_ppal['neg']};'>●</span> Market holiday</div></div>", unsafe_allow_html=True)

        with st.expander("＋  Add an event"):
            with st.form("plan_add_event"):
                _ed = st.date_input("Date", value=_ptoday, key="ev_date")
                _et = st.text_input("Title", key="ev_title", placeholder="e.g. Review portfolio, RELIANCE results")
                _en = st.text_input("Note (optional)", key="ev_note")
                if st.form_submit_button("Add event"):
                    if _et.strip():
                        _events.append({"date": str(_ed), "title": _et.strip(), "note": _en.strip()})
                        _psave(_ev_file, _events)
                        st.success("Event added")
                        time.sleep(0.4)
                        st.rerun()

        _month_ev = sorted([e for e in _events if e.get("date", "")[:7] == f"{_pyr:04d}-{_pmo:02d}"],
                           key=lambda x: x.get("date", ""))
        if _month_ev:
            st.markdown("**Events this month**")
            for _i, _e in enumerate(_month_ev):
                _ec1, _ec2 = st.columns([8, 1])
                _note = f" — <span style='color:{_ppal['text_3']};'>{_e.get('note','')}</span>" if _e.get("note") else ""
                _ec1.markdown(
                    f"<div style='padding:7px 0;'><span style='font-family:\"JetBrains Mono\",monospace;color:{_ppal['accent']};'>"
                    f"{_e.get('date','')}</span> · <b style='color:var(--q-text);'>{_e.get('title','')}</b>{_note}</div>",
                    unsafe_allow_html=True)
                if _ec2.button("🗑", key=f"del_ev_{_i}_{_e.get('date','')}"):
                    _events.remove(_e)
                    _psave(_ev_file, _events)
                    st.rerun()

    # ── To-do tab ─────────────────────────────────────────────────────────────
    with _ptab2:
        _tc1, _tc2 = st.columns([5, 1])
        _newtask = _tc1.text_input("New task", key="new_task", placeholder="What needs doing?",
                                   label_visibility="collapsed")
        if _tc2.button("Add", key="add_task", use_container_width=True) and _newtask.strip():
            _tasks.append({"text": _newtask.strip(), "done": False})
            _psave(_tk_file, _tasks)
            st.rerun()

        _open_tasks = [t for t in _tasks if not t.get("done")]
        _done_tasks = [t for t in _tasks if t.get("done")]
        _n_open = len(_open_tasks)
        st.markdown(f"<div style='font-size:.8rem;color:var(--q-text-3);margin:8px 0;'>"
                    f"{_n_open} open · {len(_done_tasks)} done</div>", unsafe_allow_html=True)

        for _i, _t in enumerate(_tasks):
            _tk1, _tk2 = st.columns([9, 1])
            _checked = _tk1.checkbox(_t.get("text", ""), value=_t.get("done", False), key=f"task_{_i}")
            if _checked != _t.get("done", False):
                _t["done"] = _checked
                _psave(_tk_file, _tasks)
                st.rerun()
            if _tk2.button("🗑", key=f"del_task_{_i}"):
                _tasks.remove(_t)
                _psave(_tk_file, _tasks)
                st.rerun()

        if not _tasks:
            st.info("No tasks yet — add your first above.")
