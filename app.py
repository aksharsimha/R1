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
    ["Overview", "Analytics", "Projections", "Insights", "News", "Activity", "Chat", "MICHAEL"],
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

import datetime as _dt
_today = _dt.date.today()
if section == "Overview":
    # ── Hero / Overview header (themed) ──────────────────────────────────────
    _pnl_pos = total_pnl >= 0
    _pnl_cls = 'q-pos' if _pnl_pos else 'q-neg'
    _pnl_sign = '+' if _pnl_pos else ''
    _score = summary['portfolio_risk_score']
    _risk_bucket = summary['portfolio_risk_bucket']
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
            _dot = (f"<span style='display:block;width:5px;height:5px;border-radius:50%;"
                    f"background:{_pal['neg']};margin:2px auto 0;'></span>") if (_in_month and _hol_desc) else ""
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
                        for _n, _sym in _resolved:
                            _s = _cmp_series(_sym, "6mo")
                            if _s is None:
                                continue
                            _norm[_sym] = _s / _s.iloc[0] * 100
                            _ret = (_s.iloc[-1] / _s.iloc[0] - 1) * 100
                            _vol = _s.pct_change().std() * (252 ** 0.5) * 100
                            try:
                                _r = _cmp_rsi(_s)
                            except Exception:
                                _r = float('nan')
                            _ma = _s.rolling(min(200, len(_s))).mean().iloc[-1]
                            _above = _s.iloc[-1] > _ma
                            if not pd.isna(_r) and _r < 35 and _above:
                                _sig = "🟢 Accumulate"
                            elif not pd.isna(_r) and _r > 70:
                                _sig = "🔴 Overbought"
                            elif not _above:
                                _sig = "🟠 Below 200-DMA"
                            else:
                                _sig = "⚪ Neutral"
                            _rows.append({"Stock": _n, "Ticker": _sym, "6M %": round(_ret, 1),
                                          "Vol %": round(_vol, 1), "RSI": round(_r, 0) if not pd.isna(_r) else None,
                                          "Signal": _sig})
                        if not _norm.empty:
                            _fign = px.line(_norm, labels={"value": "Growth (rebased to 100)", "index": "", "variable": "Stock"})
                            _fign.update_layout(height=340, margin=dict(t=10, b=0, l=0, r=0))
                            ui_theme.style_fig(_fign)
                            st.plotly_chart(_fign, use_container_width=True)
                            st.dataframe(pd.DataFrame(_rows), use_container_width=True, hide_index=True)
                            st.caption("Signals are heuristic (RSI + 200-DMA) — research, not financial advice.")

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
                    <div style="background:var(--q-surface-2); border:1px solid rgba(255,255,255,0.07);
                                border-radius:10px; padding:12px 18px; margin-bottom:1rem;
                                font-family:'JetBrains Mono',monospace; font-size:0.85rem;">
                        <span style="color:#94a3b8;">Base (EWMA):</span>
                        <span style="color:var(--q-text); margin:0 6px;">₹{_ewma_base:,.2f}</span>
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
                        background:var(--q-surface-2); border:1px solid {_conf_clr}44;
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
        
        ui_theme.style_fig(fig_proj)
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
